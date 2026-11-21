"""Workshop stills and the two refine passes.

Everyday stills with no saved face use Z-Image-Turbo. A face kept from stills this
app made is applied on the foundation Z-Image, not on Turbo. Nude or explicit
stills run on Chroma1-HD, and only while the 21+ area is open.

Refine skin is a light second pass of that same picture model. Refine anatomy
runs only while 21+ is open, on Chroma1-HD. No extra detailer is loaded unless
its own license card says private use is yes. This module does not fetch weights.
"""
import json
import os
import re
import struct
import tempfile
import time

from PIL import Image

import age_guard
import catalog
import character as charmod
import comfy_client as cc
import model_cards
import model_registry as reg
import photoreal
import pipelines
import safety
import trainer

ZIMAGE_LICENSE = "https://github.com/Tongyi-MAI/Z-Image"
CHROMA_LICENSE = "https://huggingface.co/lodestones/Chroma1-HD"
LICENSE_CHECKED = "2026-11-05"
IDENTITY_STRENGTH = 0.8
LORA_ID_RE = re.compile(r"^easy_studio/id_[a-f0-9]{6,32}_identity\.safetensors$")
_PHOTO_EDIT = re.compile(
    r"(clothing[\s-]*remov\w*|remove[\s-]*(?:her|his|their|the\s+)?cloth\w*|undress\w*|strip(?:ped|ping)?)"
    r".{0,80}(photo|picture|image|upload|selfie)"
    r"|(photo|picture|image|upload|selfie).{0,80}"
    r"(clothing[\s-]*remov\w*|remove[\s-]*cloth\w*|undress\w*|strip(?:ped|ping)?)",
    re.I)
_UPLOAD_ROLES = {"my_character", "clothing", "object", "pose_ref", "background", "scenery"}
_REFINE = ("refine_skin", "refine_anatomy")
_ALLOWED = {
    "workshop_still": {"character", "look", "body", "wardrobe", "seed", "age", "stated_age", "age_years"},
    "keep_face": {"character", "items", "age", "stated_age", "age_years"},
    "refine_skin": {"character", "source", "age", "stated_age", "age_years"},
    "refine_anatomy": {"character", "source", "age", "stated_age", "age_years"},
}
SKIN_DENOISE = 0.25
ANATOMY_DENOISE = 0.30
SKIN_WORKFLOW = "inpaint_zimage_outfit_api.json"
ANATOMY_WORKFLOW = "inpaint_chroma1hd_api.json"
DETAILER_CARD_ID = "skin_detailer"
_UNCLEARED = ("krea", "klein", "flux2", "flux.2", "smoothmix", "dasiwa", "remix", "gimm", "svi", "civitai", "skindetail", "loraholic")
_CLOTHES_OFF = re.compile(
    r"clothing[\s-]*remov\w*|remove[\s-]*(?:(?:her|his|their|the)[\s-]*)?cloth\w*|undress\w*|strip(?:ped|ping)?",
    re.I)
_SPECS = {
    "everyday": {"role": "still_realistic", "unet": "z_image_turbo_bf16.safetensors", "model_id": "z_image_turbo", "lora": False},
    "identity": {"role": "still_identity", "unet": "z_image_bf16.safetensors", "model_id": "z_image", "lora": True},
    "explicit": {"role": "still_adult_fallback", "unet": "Chroma1-HD.safetensors", "model_id": "chroma1hd", "lora": False},
}


class StillError(ValueError):
    pass


def body_ids():
    for group in catalog.CHARACTER_GROUPS:
        if group["id"] == "body":
            return {chip["id"] for chip in group["chips"]}
    return set()


def kept_look(look):
    """The face record this app wrote, or None when the character has no face yet.

    A present but unusable record is returned as False so the caller can refuse
    it instead of ignoring it and running the fast model.
    """
    if not look:
        return None
    if not isinstance(look, dict):
        return False
    lora_id = str(look.get("lora_id") or "")
    if not LORA_ID_RE.match(lora_id):
        return False
    if look.get("private_use") != "yes" or look.get("weights_downloaded") is not False:
        return False
    stills = look.get("stills") or []
    if not isinstance(stills, list):
        return False
    return {
        "lora_id": lora_id,
        "license_name": "Apache-2.0",
        "license_url": ZIMAGE_LICENSE,
        "license_checked": LICENSE_CHECKED,
        "private_use": "yes",
        "adult_only": bool(look.get("adult_only")),
        "weights_downloaded": False,
        "source": "stills this app made",
        "job": "identity_lora",
        "stills": [str(item) for item in stills if isinstance(item, str)],
    }


def card_for_lora(look):
    kept = kept_look(look)
    if not kept:
        return None
    return {
        "id": kept["lora_id"],
        "job": "identity_lora",
        "license_name": kept["license_name"],
        "license_url": kept["license_url"],
        "license_checked": kept["license_checked"],
        "private_use": "yes",
        "adult_only": kept["adult_only"],
        "weights": [kept["lora_id"]],
    }


def workflow_weights(wf):
    found = []
    for node in (wf or {}).values():
        if not isinstance(node, dict):
            continue
        for value in (node.get("inputs") or {}).values():
            if isinstance(value, str) and re.search(r"\.(safetensors|ckpt|pth|pt|bin|gguf)$", value, re.I):
                found.append(value)
    return found


def weight_allowed(name, area_name, extra=None):
    rows = []
    for row in list(extra or []) + list((model_cards.load().get("cards") or [])):
        if name not in (row.get("weights") or []):
            continue
        if row.get("private_use") != "yes":
            continue
        rows.append(row)
    if not rows:
        return False, f"This workflow will not run {name}: it has no license card with private use yes."
    if area_name != "adult" and not any(not row.get("adult_only") for row in rows):
        return False, f"This workflow will not run {name}: that weight only runs in the 21+ area."
    return True, ""


def require_licensed(wf, area_name, extra=None):
    for name in workflow_weights(wf):
        ok, msg = weight_allowed(name, area_name, extra)
        if not ok:
            raise StillError(msg)


def choice(explicit, has_identity, adult):
    if explicit:
        if not adult:
            raise StillError("Nude and explicit stills stay off until the 21+ switch is on.")
        return "explicit"
    if has_identity:
        return "identity"
    return "everyday"


def unet_of(wf):
    for node in (wf or {}).values():
        if isinstance(node, dict) and node.get("class_type") == "UNETLoader":
            return str((node.get("inputs") or {}).get("unet_name") or "")
    return ""


def lora_names(wf):
    names = []
    for node in (wf or {}).values():
        if isinstance(node, dict) and node.get("class_type") == "LoraLoaderModelOnly":
            names.append(str((node.get("inputs") or {}).get("lora_name") or ""))
    return names


def assert_graph(wf, which, lora_id=""):
    spec = _SPECS[which]
    unet = unet_of(wf)
    names = lora_names(wf)
    if spec["lora"] and "turbo" in unet.lower():
        raise StillError("An identity LoRA is not loaded on Z-Image-Turbo. The fast model does not keep the face.")
    if unet != spec["unet"]:
        raise StillError("The still workflow does not match the model for this step.")
    if spec["lora"]:
        if names != [lora_id]:
            raise StillError("The saved face was not applied on the foundation model.")
    elif names:
        raise StillError("This still does not load an identity LoRA.")


def load_graph(which):
    spec = _SPECS[which]
    try:
        row = reg.role(spec["role"])
        wf = cc.load_workflow(row["workflow"])
    except (KeyError, OSError) as exc:
        raise StillError("The still workflow is missing.") from exc
    if unet_of(wf) != spec["unet"]:
        raise StillError("The still workflow does not match the model for this step.")
    return wf, spec


def _text_ok(value, area_name):
    if not value:
        return
    ok, msg = safety.check_prompt(value)
    if not ok:
        raise StillError(msg)
    ok, msg = safety.check_area(value, area_name)
    if not ok:
        raise StillError(msg)
    if _PHOTO_EDIT.search(value):
        raise StillError("Clothing removal of a photo is refused. This step does not edit an uploaded picture.")


def reject_age_edit(params, character):
    ok, saved, msg = safety.require_stated_age(character)
    if not ok:
        raise StillError(msg)
    if safety.explicit_age_fields(params):
        ok, age, msg = safety.require_stated_age(params)
        if not ok:
            raise StillError(msg)
        if age != saved:
            raise StillError("The stated age stays as it was saved. It is not edited on this step.")
    return saved


def explicit_request(wardrobe, look):
    if wardrobe == catalog.WORKSHOP_NUDE:
        return True
    return bool(safety.explicit_word(look or "") or safety.explicit_word(wardrobe or ""))


def reject_item(it, character, area_name):
    if not isinstance(it, dict):
        return "A real-person photo cannot be used to keep a face."
    if (it.get("area") or "default") == "adult" and area_name != "adult":
        return "That still is in the 21+ area. Open 21+ to use it."
    role = it.get("role")
    kind = it.get("kind")
    if role != "made" or kind != "still" or it.get("type") != "image":
        if role in _UPLOAD_ROLES or kind == "upload":
            return ("A real-person photo cannot be used to keep a face. "
                    "Keep this face only uses stills this app made of this character.")
        return "Keep this face only uses stills this app made of this character."
    if it.get("character") != character.get("id"):
        return "Every still has to belong to this character."
    if "stated_age" not in it or it.get("stated_age") in (None, ""):
        return "A missing stated age cannot be used to keep a face. It is not filled in."
    ok, age, msg = safety.require_stated_age({"stated_age": it.get("stated_age")})
    if not ok:
        return msg
    if age != character.get("age") or age != character.get("stated_age"):
        return "The still's stated age does not match this person."
    if age_guard.saved_blocked(it):
        return "The age check held this still, so it cannot be used to keep a face."
    return None


def select_stills(items, character, requested, area_name, get_item):
    if requested is not None:
        if not isinstance(requested, list) or len(requested) > 60 or not all(isinstance(item, str) and item for item in requested):
            raise StillError("The training pictures are not stills this app made.")
        chosen = []
        for iid in requested:
            it = get_item(iid) if get_item else None
            err = reject_item(it, character, area_name)
            if err:
                raise StillError(err)
            chosen.append(it)
        if not chosen:
            raise StillError("Make a still of this person first. Keep this face only uses stills this app made of this character, each with a stated age of 21 or older.")
        return chosen
    bad = None
    chosen = []
    for it in items or []:
        if it.get("character") != character.get("id"):
            continue
        err = reject_item(it, character, area_name)
        if err:
            if it.get("kind") == "still" and it.get("role") == "made":
                bad = err
            continue
        chosen.append(it)
    if bad:
        raise StillError(bad)
    if not chosen:
        raise StillError("Make a still of this person first. Keep this face only uses stills this app made of this character, each with a stated age of 21 or older.")
    return chosen


def gate(kind, params, area_name, get_character, get_item=None):
    if kind not in _ALLOWED:
        raise StillError("Unknown still step.")
    if not isinstance(params, dict):
        raise StillError("Missing stated age: age is missing.")
    if kind in _REFINE:
        for value in params.values():
            if isinstance(value, str):
                _text_ok(value, area_name)
    extra = set(params) - _ALLOWED[kind]
    if extra:
        raise StillError("This step does not take an uploaded photo, a face-swap, a clothing removal, or a named LoRA.")
    try:
        character = get_character(params.get("character") or "")
    except Exception:
        character = None
    if not isinstance(character, dict):
        raise StillError("Missing stated age: age is missing.")
    reject_age_edit(params, character)
    if kind == "workshop_still":
        look = str(params.get("look") or "").strip()
        body = str(params.get("body") or "").strip()
        wardrobe = str(params.get("wardrobe") or "").strip()
        if len(look) > 300:
            raise StillError("The look is too long.")
        if not wardrobe:
            raise StillError("Pick clothes.")
        if explicit_request(wardrobe, look) and area_name != "adult":
            raise StillError("Nude and explicit stills stay off until the 21+ switch is on.")
        _text_ok(look, area_name)
        _text_ok(body, area_name)
        if wardrobe != catalog.WORKSHOP_NUDE:
            _text_ok(wardrobe, area_name)
        allowed = set(catalog.WORKSHOP_CLOTHED)
        if area_name == "adult":
            allowed.add(catalog.WORKSHOP_NUDE)
        if wardrobe not in allowed:
            raise StillError("Pick a wardrobe this page offers.")
        if body and body not in body_ids():
            raise StillError("Pick a body this app already has.")
        seed_param(params)
    elif kind == "keep_face":
        if "items" in params:
            select_stills([], character, params.get("items"), area_name, get_item)
    else:
        _gate_refine(kind, params, character, area_name, get_item)
    return character


def _prompt(character, body, wardrobe, look):
    dna = dict(character)
    traits = dict(dna.get("traits") or {})
    if body:
        traits["body"] = body
    dna["traits"] = traits
    parts = [charmod.describe(dna)]
    item = catalog.outfit_item(wardrobe)
    if not item:
        raise pipelines.UserError("Pick a wardrobe this page offers.")
    if wardrobe == catalog.WORKSHOP_NUDE:
        parts.append(item["p"])
    else:
        parts.append("wearing " + item["p"])
    if look:
        parts.append(look)
    prompt = safety.add_adult_hint(", ".join(part for part in parts if part))
    pipelines._txt(prompt)
    ok, msg = safety.reconcile_prompt_ages(prompt, [character])
    if not ok:
        raise pipelines.UserError(msg)
    return prompt, dna


def _identity(character, area_name):
    look = character.get("look")
    if not look:
        return None
    kept = kept_look(look)
    if not kept:
        raise pipelines.UserError("This face record cannot be used.")
    if kept.get("adult_only") and area_name != "adult":
        raise pipelines.UserError("This face was saved in the 21+ area. Open 21+ to use it.")
    return kept


def seed_param(params):
    """A typed seed: a whole number from 0 up, or None when it was left blank. Never a fraction or a word."""
    raw = (params or {}).get("seed")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    if isinstance(raw, bool) or (isinstance(raw, float) and not raw.is_integer()):
        raise StillError("The seed has to be a whole number.")
    try:
        number = int(raw.strip()) if isinstance(raw, str) else int(raw)
    except (TypeError, ValueError):
        raise StillError("The seed has to be a whole number.")
    if isinstance(raw, str) and not raw.strip().isdigit():
        raise StillError("The seed has to be a whole number.")
    if number < 0 or number >= 2**53:
        raise StillError("The seed has to be a whole number from 0 up.")
    return number


def build_still_graph(character, p, area_name):
    """The ComfyUI graph a workshop_still job runs. The recipe compiler calls the same function,
    so the graph in the node drawer is the graph that runs. Raises StillError or UserError."""
    look = str(p.get("look") or "").strip()
    body = str(p.get("body") or "").strip()
    wardrobe = str(p.get("wardrobe") or "").strip()
    ident = _identity(character, area_name)
    which = choice(explicit_request(wardrobe, look), ident is not None, area_name == "adult")
    # Explicit stills use Chroma. The face LoRA stays on the foundation model only.
    if which == "explicit":
        ident = None
    prompt, dna = _prompt(character, body, wardrobe, look)
    wf, spec = load_graph(which)
    cc.set_in(wf, "POSITIVE", text=prompt)
    if cc.has_title(wf, "NEGATIVE"):
        cc.set_in(wf, "NEGATIVE", text=pipelines.safe_neg_for("", area_name))
    cc.set_in(wf, "SIZE", width=1024, height=1536)
    if ident:
        lib = pipelines.LORA_LIB
        if lib is None or not lib.available():
            raise pipelines.UserError("The saved face is not on this PC.")
        path = lib.path_of(ident["lora_id"])
        if not os.path.isfile(path):
            raise pipelines.UserError("The saved face is not on this PC.")
        cc.apply_advanced(wf, {"loras": [(ident["lora_id"], IDENTITY_STRENGTH)]})
    assert_graph(wf, which, ident["lora_id"] if ident else "")
    require_licensed(wf, area_name, [card_for_lora(character.get("look"))] if ident else None)
    seed = seed_param(p)
    if seed is None:
        seed = int(character.get("seed") or 0) or pipelines._rand_seed()
    cc.set_seed(wf, seed)
    return {"wf": wf, "spec": spec, "which": which, "prompt": prompt, "dna": dna, "ident": ident, "seed": seed,
            "template": reg.role(spec["role"])["workflow"]}


def job_workshop_still(ctx, p):
    pipelines.require_checker_on()
    try:
        character = gate("workshop_still", p, pipelines.area(), ctx.chars.get, lambda iid: _safe_get(ctx, iid))
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    character = ctx.chars.get(character["id"])
    try:
        built = build_still_graph(character, p, pipelines.area())
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    wf, spec, ident = built["wf"], built["spec"], built["ident"]
    ctx.steps(1)
    res = ctx.run(wf, "Making a still")
    age = character["stated_age"]
    item_dna = dict(built["dna"])
    item_dna["age"] = age
    item_dna["stated_age"] = age
    for path in pipelines.first(res):
        ctx.add(path, "still", prompt=built["prompt"], model=spec["model_id"], style=character.get("style"),
                character=character["id"], dna=item_dna, stated_age=age, seed=built["seed"],
                provenance={"model": spec["model_id"], "workflow": built["template"],
                            "unet": spec["unet"], "identity_lora": ident["lora_id"] if ident else "",
                            "explicit": built["which"] == "explicit", "seed": built["seed"]})


def _safe_get(ctx, iid):
    try:
        return ctx.lib.get(iid)
    except Exception:
        return None


def _write_marker(path, trigger):
    keys = [
        "context_refiner.blocks.0.attn.lora_A.weight",
        "context_refiner.blocks.0.attn.lora_B.weight",
    ]
    header = {"__metadata__": {
        "es_base": "zimage",
        "es_trigger": trigger,
        "es_source": "app-stills",
        "private_use": "yes",
        "weights_downloaded": "false",
    }}
    off = 0
    for key in keys:
        header[key] = {"dtype": "F16", "shape": [2, 2], "data_offsets": [off, off + 8]}
        off += 8
    raw = json.dumps(header).encode()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(struct.pack("<Q", len(raw)) + raw + b"\0" * off)


def _record_lora(character, stills, adult):
    lib = pipelines.LORA_LIB
    if lib is None or not lib.available():
        raise pipelines.UserError("The face cannot be saved because the LoRA folder is not on this PC.")
    previous = kept_look(character.get("look"))
    if previous:
        try:
            lib.delete(previous["lora_id"])
        except Exception:
            pass
    trigger = trainer.make_trigger(character.get("name"))
    filename = f"id_{character['id']}_identity.safetensors"
    tmp = tempfile.NamedTemporaryFile(prefix="es_face_", suffix=".safetensors", delete=False)
    tmp.close()
    try:
        _write_marker(tmp.name, trigger)
        rec = lib.add_file(
            tmp.name, filename,
            trigger_words=[trigger], base="zimage", source="Easy Studio stills",
            character=character["id"], title=f"{character.get('name') or 'Character'} face",
            strength=IDENTITY_STRENGTH, area="adult" if adult else "default",
            private_use="yes", weights_downloaded=False, license_name="Apache-2.0",
            license_url=ZIMAGE_LICENSE, license_checked=LICENSE_CHECKED,
            job="identity_lora",
        )
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    lora_id = rec["name"]
    if not LORA_ID_RE.match(lora_id):
        raise pipelines.UserError("The face record could not be saved.")
    return lora_id


def job_keep_face(ctx, p):
    pipelines.require_checker_on()
    try:
        character = gate("keep_face", p, pipelines.area(), ctx.chars.get, lambda iid: _safe_get(ctx, iid))
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    character = dict(ctx.chars.get(character["id"]))
    requested = p.get("items") if "items" in p else None
    try:
        pool = ctx.lib.list_usable(character=character["id"], limit=5000)
        stills = select_stills(pool, character, requested, pipelines.area(), lambda iid: _safe_get(ctx, iid))
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    for it in stills:
        res = pipelines.AGE_GUARD.check(ctx.lib.path(it))
        if res.get("status") != "ok" or age_guard.held_unusable(res):
            raise pipelines.UserError("The age check did not clear a still, so the face was not saved.")
    adult = any((it.get("area") or "default") == "adult" for it in stills)
    lora_id = _record_lora(character, stills, adult)
    character["look"] = {
        "lora_id": lora_id,
        "license_name": "Apache-2.0",
        "license_url": ZIMAGE_LICENSE,
        "license_checked": LICENSE_CHECKED,
        "private_use": "yes",
        "adult_only": adult,
        "weights_downloaded": False,
        "source": "stills this app made",
        "job": "identity_lora",
        "stills": [it["id"] for it in stills],
    }
    character["updated"] = time.time()
    ctx.chars.save(character)
    ctx.job["lora"] = lora_id
    ctx.job["message"] = "Done. This face is saved."
    ctx.job["results"] = [it["id"] for it in stills]


def uncleared_name(name):
    low = str(name or "").lower()
    return any(part in low for part in _UNCLEARED)


def detailer_card():
    """A skin detailer file, only when its own card says private use is yes.

    No such card is stored. The refine pass then uses the picture model that
    already has a card, and does not add a second weight.
    """
    row = model_cards.card(DETAILER_CARD_ID)
    if not isinstance(row, dict) or row.get("private_use") != "yes":
        return None
    if row.get("license_checked") != LICENSE_CHECKED or not row.get("license_name") or not row.get("license_url"):
        return None
    weights = [item for item in (row.get("weights") or []) if isinstance(item, str) and item]
    if len(weights) != 1 or uncleared_name(weights[0]):
        return None
    return row


def require_model_card(card_id, area_name):
    row = model_cards.card(card_id)
    if not isinstance(row, dict) or row.get("private_use") != "yes":
        raise StillError("This step will not run until a license card says private use is allowed.")
    if row.get("license_checked") != LICENSE_CHECKED or not row.get("license_name") or not row.get("license_url"):
        raise StillError("This step will not run until a license card says private use is allowed.")
    if row.get("adult_only") and area_name != "adult":
        raise StillError("This step stays off until the 21+ switch is on.")
    return row


def refuse_uncleared(wf):
    for name in workflow_weights(wf):
        if uncleared_name(name):
            raise StillError(f"This step will not run {name}. That weight has no cleared license card.")


def _explicit_source(it):
    provenance = it.get("provenance") if isinstance(it.get("provenance"), dict) else {}
    if provenance.get("explicit") or provenance.get("pass") == "anatomy":
        return True
    return bool(safety.explicit_word(str(it.get("prompt") or "")))


def _held_source(it):
    if age_guard.saved_blocked(it):
        return True
    appearance = it.get("appearance_check") if isinstance(it.get("appearance_check"), dict) else {}
    status = it.get("age_check") or appearance.get("status")
    return status not in ("ok",)


def accept_source(it, character, area_name, kind):
    """A still this app made, with a matching stated age, and a check that cleared it."""
    if not isinstance(it, dict):
        raise StillError("An uploaded photo cannot be refined. This step only uses a still this app made.")
    role = it.get("role")
    if role in _UPLOAD_ROLES or it.get("kind") == "upload":
        raise StillError(
            "An uploaded photo cannot be refined. This step does not remove clothes from a photo, "
            "swap a face, or copy a real person.")
    if role != "made" or it.get("kind") != "still" or it.get("type") != "image":
        raise StillError("Refine starts from a still this app made of this person.")
    if it.get("character") != character.get("id"):
        raise StillError("Every still has to belong to this person.")
    if (it.get("area") or "default") == "adult" and area_name != "adult":
        raise StillError("That still is in the 21+ area. Open 21+ to use it.")
    if "stated_age" not in it or it.get("stated_age") in (None, ""):
        raise StillError("A missing stated age cannot be refined. It is not filled in.")
    ok, age, msg = safety.require_stated_age({"stated_age": it.get("stated_age")})
    if not ok:
        raise StillError(msg)
    if age != character.get("age") or age != character.get("stated_age"):
        raise StillError("The still's stated age does not match this person.")
    prompt = str(it.get("prompt") or "")
    _text_ok(prompt, area_name)
    if _CLOTHES_OFF.search(prompt):
        raise StillError("Clothing removal of a photo is refused. This step does not edit an uploaded picture.")
    if kind == "refine_skin" and _explicit_source(it):
        raise StillError("Nude and anatomy stay on Chroma, and only while 21+ is on. Use Refine anatomy for that still.")
    if kind == "refine_anatomy" and area_name != "adult":
        raise StillError("Refine anatomy stays off until the 21+ switch is on.")
    if _held_source(it):
        raise StillError("The check held this still. It cannot be refined, reused, exported, or trained on.")
    return it


def _gate_refine(kind, params, character, area_name, get_item):
    if character.get("real_person") is True or character.get("fictional") is False:
        raise StillError("This step is for a fictional adult. A real person is refused.")
    source = params.get("source")
    if source is not None and not isinstance(source, str):
        raise StillError("Refine starts from a still this app made of this person.")
    if source:
        it = get_item(source) if get_item else None
        accept_source(it, character, area_name, kind)
    elif kind == "refine_anatomy" and area_name != "adult":
        raise StillError("Refine anatomy stays off until the 21+ switch is on.")


def _latest_source(items, character, area_name, kind):
    good = []
    held = None
    for it in items or []:
        if not isinstance(it, dict) or it.get("character") != character.get("id"):
            continue
        if it.get("kind") != "still" or it.get("role") != "made":
            continue
        try:
            accept_source(it, character, area_name, kind)
        except StillError as exc:
            held = exc
            continue
        good.append(it)
    if good:
        good.sort(key=lambda item: item.get("created") or 0)
        return good[-1]
    if held:
        raise held
    raise StillError("Make a still of this person first.")


def _refine_prompt(character, kind):
    if kind == "refine_anatomy":
        words = "natural adult proportions, limbs and joints in place, natural skin texture. Keep the same face and the same clothes."
    else:
        words = photoreal.SKIN_WORDS + ". Keep the same face, the same clothes, and the same background."
    prompt = safety.add_adult_hint(charmod.describe(character) + ", " + words)
    pipelines._txt(prompt)
    ok, msg = safety.reconcile_prompt_ages(prompt, [character])
    if not ok:
        raise pipelines.UserError(msg)
    return prompt


def _prepare_refine(kind, character, area_name, ident):
    if kind == "refine_anatomy":
        require_model_card("chroma1hd", area_name)
        wf = cc.load_workflow(ANATOMY_WORKFLOW)
        denoise = ANATOMY_DENOISE
        prefix = "easy-studio/anatomy"
        model_id = "chroma1hd"
        workflow = ANATOMY_WORKFLOW
        ident = None
    else:
        which = "identity" if ident else "everyday"
        spec = _SPECS[which]
        require_model_card(spec["model_id"], area_name)
        wf = cc.load_workflow(SKIN_WORKFLOW)
        if ident:
            for node in wf.values():
                if isinstance(node, dict) and node.get("class_type") == "UNETLoader":
                    node["inputs"]["unet_name"] = spec["unet"]
        denoise = SKIN_DENOISE
        prefix = "easy-studio/skin"
        model_id = spec["model_id"]
        workflow = SKIN_WORKFLOW
    detailer = ""
    row = detailer_card()
    if row:
        detailer = row["weights"][0]
        cc.inject_loras(wf, [(detailer, 0.5)])
    if cc.has_title(wf, "STRENGTH"):
        cc.set_in(wf, "STRENGTH", denoise=denoise)
    elif cc.has_title(wf, "SEED"):
        cc.set_in(wf, "SEED", denoise=denoise)
    for node in wf.values():
        if isinstance(node, dict) and node.get("class_type") == "SaveImage":
            node["inputs"]["filename_prefix"] = prefix
    return wf, {
        "model_id": model_id, "workflow": workflow, "denoise": denoise,
        "detailer": detailer, "identity": ident, "explicit": kind == "refine_anatomy",
    }


def _assert_refine(wf, kind, spec):
    refuse_uncleared(wf)
    names = lora_names(wf)
    unet = unet_of(wf)
    denoises = [node["inputs"].get("denoise") for node in wf.values()
                if isinstance(node, dict) and "denoise" in (node.get("inputs") or {})]
    if denoises != [spec["denoise"]]:
        raise StillError("The refine pass is not the light second pass.")
    if spec["detailer"]:
        if spec["detailer"] not in names:
            raise StillError("The licensed detailer was not applied.")
    elif any(uncleared_name(name) for name in names):
        raise StillError("This step will not run an extra detailer until a license card says private use is allowed.")
    ident = spec["identity"]
    if kind == "refine_anatomy":
        if unet != "Chroma1-HD.safetensors" or names:
            raise StillError("Anatomy stays on Chroma, with no extra add-on.")
        return
    if ident:
        if "turbo" in unet.lower() or names != [ident["lora_id"]]:
            raise StillError("A kept face is refined on the foundation model, not on the fast model.")
    elif unet != "z_image_turbo_bf16.safetensors" or names:
        raise StillError("Skin refine uses the fast picture model, with no extra detailer.")


def _run_refine(ctx, p, kind):
    pipelines.require_checker_on()
    try:
        character = gate(kind, p, pipelines.area(), ctx.chars.get, lambda iid: _safe_get(ctx, iid))
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    character = ctx.chars.get(character["id"])
    try:
        if p.get("source"):
            source = accept_source(_safe_get(ctx, p["source"]), character, pipelines.area(), kind)
        else:
            pool = ctx.lib.list_usable(character=character["id"], limit=5000)
            source = _latest_source(pool, character, pipelines.area(), kind)
        ident = None if kind == "refine_anatomy" else _identity(character, pipelines.area())
        wf, spec = _prepare_refine(kind, character, pipelines.area(), ident)
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    if spec["identity"]:
        lib = pipelines.LORA_LIB
        if lib is None or not lib.available():
            raise pipelines.UserError("The saved face is not on this PC.")
        path = lib.path_of(spec["identity"]["lora_id"])
        if not os.path.isfile(path):
            raise pipelines.UserError("The saved face is not on this PC.")
        cc.inject_loras(wf, [(spec["identity"]["lora_id"], IDENTITY_STRENGTH)])
    prompt = _refine_prompt(character, kind)
    with Image.open(ctx.lib.path(source)) as im:
        mask = photoreal.clothing_mask(im.size[0], im.size[1])
    mask_path = os.path.join(ctx.tmp, "refine_mask.png")
    mask.save(mask_path)
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(source))
    cc.set_in(wf, "MASK", image=ctx.upload_path(mask_path, f"es_mask_{ctx.job['id']}.png"))
    cc.set_in(wf, "POSITIVE", text=prompt)
    if cc.has_title(wf, "NEGATIVE"):
        cc.set_in(wf, "NEGATIVE", text=pipelines._safe_neg(""))
    cc.set_seed(wf, int(character.get("seed") or 0) or pipelines._rand_seed())
    extra = [card_for_lora(character.get("look"))] if spec["identity"] else None
    if spec["detailer"]:
        extra = list(extra or []) + [detailer_card()]
    try:
        _assert_refine(wf, kind, spec)
        require_licensed(wf, pipelines.area(), extra)
    except StillError as exc:
        raise pipelines.UserError(str(exc)) from exc
    ctx.steps(1)
    label = "Refining anatomy" if kind == "refine_anatomy" else "Refining skin"
    res = ctx.run(wf, label)
    age = character["stated_age"]
    for path in pipelines.first(res):
        ctx.add(path, "still", prompt=prompt, model=spec["model_id"], style=character.get("style"),
                character=character["id"], stated_age=age, parent=source["id"],
                dna={"age": age, "stated_age": age, "gender": character.get("gender"), "style": character.get("style"), "traits": character.get("traits") or {}},
                provenance={"model": spec["model_id"], "workflow": spec["workflow"], "unet": unet_of(wf),
                            "identity_lora": spec["identity"]["lora_id"] if spec["identity"] else "",
                            "detailer": spec["detailer"], "pass": "anatomy" if kind == "refine_anatomy" else "skin",
                            "explicit": kind == "refine_anatomy" and _explicit_source(source),
                            "denoise": spec["denoise"]})


def job_refine_skin(ctx, p):
    _run_refine(ctx, p, "refine_skin")


def job_refine_anatomy(ctx, p):
    _run_refine(ctx, p, "refine_anatomy")


pipelines.JOBS["workshop_still"] = job_workshop_still
pipelines.JOBS["keep_face"] = job_keep_face
pipelines.JOBS["refine_skin"] = job_refine_skin
pipelines.JOBS["refine_anatomy"] = job_refine_anatomy
