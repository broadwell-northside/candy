"""A guided 3D prop from a still this app made, or from a scenery photo.

The mesh is the TRELLIS workflow already in the app. It is a rough glTF prop.
It is not a rigged body and it is not a scan you can walk inside.

A scenery photo is a place, not a person. A face in it is blurred, or the photo
is refused when that blur cannot be confirmed. The gated encoder token is an
op:// reference stored on the license card. This module never prints it.
"""
import re

from PIL import Image, ImageFilter

import age_guard
import comfy_client as cc
import model_cards
import pipelines
import safety
import stills

WORKFLOW = "3d_trellis2_api.json"
LICENSE_CHECKED = "2026-11-05"
LIMIT = ("The result is a rough prop mesh. It can have holes and a soft back. "
         "It is not a rigged person, and it is not a scan you can walk inside.")
_ALLOWED = {"source", "image", "age", "stated_age", "age_years"}
_SECRET = "op://"
_FAIL_STATUS = {"off", "unavailable", "error", "timeout", age_guard.BLOCKED_AGE_CHECK}
_FACE = re.compile(r"face[\s\-]*swap", re.I)
_CLOTHES = re.compile(
    r"clothing[\s\-]*remov\w*|remove[\s\-]*(?:(?:her|his|their|the)[\s\-]*)?cloth\w*|undress\w*|strip(?:ped|ping)?",
    re.I)
_REFERENCE = re.compile(r"character\s+reference", re.I)
_SPLAT = re.compile(r"gaussian|\bsplat\b", re.I)


class PropError(ValueError):
    def __init__(self, message):
        text = str(message or "")
        if _SECRET in text.lower():
            text = "This step was refused. A secret reference is not shown."
        super().__init__(text)


def _gated_reference_ok(row):
    """True when the card points at a secret reference. The value is not returned."""
    ref = row.get("token_ref") if isinstance(row, dict) else None
    if not isinstance(ref, str) or _SECRET not in ref.lower():
        return False
    if any(ch.isspace() for ch in ref):
        return False
    prefix, sep, rest = ref.partition("://")
    if sep != "://" or prefix.lower() != "op" or not rest:
        return False
    parts = [part for part in rest.split("/") if part]
    return len(parts) >= 3


def _cards(area_name):
    try:
        wf = cc.load_workflow(WORKFLOW)
        stills.require_licensed(wf, area_name)
        trellis = stills.require_model_card("trellis2", area_name)
        encoder = stills.require_model_card("dinov3", area_name)
        remover = stills.require_model_card("birefnet", area_name)
    except stills.StillError as exc:
        raise PropError(str(exc)) from exc
    if trellis.get("license_name") != "MIT" or trellis.get("license_checked") != LICENSE_CHECKED:
        raise PropError("This prop step will not run. The TRELLIS.2 license card is missing or not cleared.")
    if encoder.get("license_name") != "dinov3-license" or encoder.get("license_checked") != LICENSE_CHECKED:
        raise PropError("This prop step will not run. The encoder license card is missing or not cleared.")
    scope = str(encoder.get("private_use_scope") or "")
    if encoder.get("private_use") != "yes" or "do not distribute" not in scope:
        raise PropError("This prop step will not run. The encoder is not cleared for this private machine.")
    if encoder.get("download") != "gated" or not _gated_reference_ok(encoder):
        raise PropError("This prop step will not run. The gated encoder download has no secret reference.")
    if remover.get("license_name") != "MIT" or remover.get("private_use") != "yes":
        raise PropError("This prop step will not run. The background remover has no cleared license card.")
    return wf


def public_licenses():
    """License names safe to store on a result. The secret reference is left out."""
    out = []
    for card_id in ("trellis2", "dinov3", "birefnet"):
        row = model_cards.card(card_id) or {}
        out.append({
            "id": card_id,
            "license_name": row.get("license_name"),
            "license_checked": row.get("license_checked"),
            "private_use": row.get("private_use"),
        })
    return out


def _phrases(params):
    blob = " ".join(str(value) for value in params.values() if isinstance(value, str))
    if _FACE.search(blob):
        raise PropError("This step does not do a face swap.")
    if _CLOTHES.search(blob):
        raise PropError("A clothing-removal edit is refused.")
    if _REFERENCE.search(blob):
        raise PropError("This step does not take a character reference.")
    if _SPLAT.search(blob):
        raise PropError("This step does not build a Gaussian splat.")


def _own_record(it):
    if not isinstance(it, dict):
        return None
    dna = it.get("dna")
    if isinstance(dna, dict) and safety.explicit_age_fields(dna):
        return dna
    if any(key in it for key in safety.STATED_AGE_FIELDS):
        return {key: it.get(key) for key in safety.STATED_AGE_FIELDS if key in it}
    return None


def _character(get_character, cid):
    if not cid or not get_character:
        return None
    try:
        found = get_character(cid)
    except Exception:
        return None
    return found if isinstance(found, dict) else None


def _stated_age(it, get_item, get_character, depth=0):
    if not isinstance(it, dict) or depth > 5:
        raise PropError("Missing stated age: age is missing.")
    records = []
    own = _own_record(it)
    if own is not None:
        records.append(own)
    person = _character(get_character, it.get("character"))
    if isinstance(person, dict) and safety.explicit_age_fields(person):
        records.append(person)
    if not records and it.get("parent") and get_item and depth < 5:
        try:
            parent = get_item(it.get("parent"))
        except Exception:
            parent = None
        if isinstance(parent, dict):
            return _stated_age(parent, get_item, get_character, depth + 1)
    if not records:
        raise PropError("Missing stated age: age is missing.")
    ages = []
    for record in records:
        if record.get("real_person") is True:
            raise PropError("A real person's photo cannot be used to build a body.")
        ok, age, msg = safety.require_stated_age(record)
        if not ok:
            raise PropError(msg)
        ages.append(age)
    if len(set(ages)) != 1:
        raise PropError("The still's stated age does not match this person.")
    return ages[0]


def _lookup(get_item, iid):
    if not iid or not get_item:
        return None
    try:
        found = get_item(iid)
    except Exception:
        return None
    return found if isinstance(found, dict) else None


def _still(it, get_item, get_character, area_name):
    if not isinstance(it, dict) or it.get("type") != "image":
        raise PropError("Choose a still this app made of a fictional adult.")
    if it.get("role") == "scenery" or it.get("place") is True:
        raise PropError("This photo is a place, not a person. It cannot be used to build a body.")
    if it.get("role") != "made" or it.get("kind") == "upload":
        raise PropError("Choose a still this app made of a fictional adult. A real person's photo cannot be used to build a body.")
    if (it.get("area") or "default") == "adult" and area_name != "adult":
        raise PropError("That still is in the 21+ area. Open 21+ to use it.")
    if age_guard.saved_blocked(it):
        raise PropError("The age check held this still, so it cannot be used.")
    return _stated_age(it, get_item, get_character)


def _scenery(it):
    if not isinstance(it, dict) or it.get("type") != "image" or it.get("role") != "scenery" or it.get("place") is not True:
        raise PropError("Choose a photo marked as scenery. A photo is a place, not a person.")
    if it.get("person") is True or it.get("face_check") not in ("clear", "blurred"):
        raise PropError("This photo was refused. The face check could not confirm it is only a place.")
    if it.get("age_flag"):
        raise PropError("This photo was refused. The face check could not confirm it is only a place.")
    return it


def gate(params, area_name, get_character, get_item):
    """Refuse before a job is queued. A bad age never reaches the engine."""
    if not isinstance(params, dict):
        raise PropError("Missing stated age: age is missing.")
    _phrases(params)
    param_age = None
    if safety.explicit_age_fields(params):
        ok, param_age, msg = safety.require_stated_age(params)
        if not ok:
            raise PropError(msg)
    extra = set(params) - _ALLOWED
    if extra:
        raise PropError("This step only takes a still this app made, or a photo marked as scenery.")
    source = params.get("source")
    if source not in ("still", "scenery"):
        raise PropError("Choose a still this app made of a fictional adult, or a photo marked as scenery.")
    it = _lookup(get_item, params.get("image"))
    if source == "scenery":
        if param_age is not None:
            raise PropError("A scenery photo is a place, not a person. It does not take a character age.")
        _scenery(it)
        _cards(area_name)
        return "scenery", it, None
    age = _still(it, get_item, get_character, area_name)
    if param_age is not None and param_age != age:
        raise PropError("The stated age stays on the still. It is not edited on this step.")
    _cards(area_name)
    return "still", it, age


def _faces(result):
    try:
        return int(result.get("faces") or 0)
    except (TypeError, ValueError):
        return 0


def _check_ran(result):
    return isinstance(result, dict) and result.get("status") not in _FAIL_STATUS and result.get("status") in ("ok", "flag", "unchecked")


def blur_regions(path, boxes):
    """Blur the face boxes in a place photo. This is not a splat."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        width, height = im.size
        changed = False
        for raw in boxes or []:
            if not isinstance(raw, (list, tuple)) or len(raw) != 4:
                continue
            try:
                x1, y1, x2, y2 = [int(float(value)) for value in raw]
            except (TypeError, ValueError):
                continue
            left, right = sorted((max(0, x1), min(width, x2)))
            top, bottom = sorted((max(0, y1), min(height, y2)))
            if right - left < 2 or bottom - top < 2:
                continue
            crop = im.crop((left, top, right, bottom))
            tiny = max(1, min(4, crop.size[0] // 16 or 1))
            small = crop.resize((tiny, max(1, tiny * crop.size[1] // max(1, crop.size[0]))), Image.BILINEAR)
            soft = small.resize(crop.size, Image.NEAREST).filter(ImageFilter.GaussianBlur(radius=12))
            im.paste(soft, (left, top))
            changed = True
        if not changed:
            raise PropError("A face is in this photo, and the blur could not be confirmed, so the photo was refused.")
        im.save(path)


def screen_scenery(path, check):
    """Accept a place photo, blur a found face, or refuse when the blur cannot be confirmed."""
    first = check(path)
    if not _check_ran(first):
        raise PropError("This photo was refused. The face check could not confirm it is only a place.")
    if _faces(first) <= 0:
        return {"place": True, "person": False, "face_check": "clear", "face_blurred": False}
    boxes = first.get("boxes") if isinstance(first.get("boxes"), list) else []
    if not boxes:
        raise PropError("A face is in this photo, and the blur could not be confirmed, so the photo was refused.")
    try:
        blur_regions(path, boxes)
    except PropError:
        raise
    except Exception as exc:
        raise PropError("A face is in this photo, and the blur could not be confirmed, so the photo was refused.") from exc
    second = check(path)
    if not _check_ran(second) or _faces(second) > 0:
        raise PropError("A face is in this photo, and the blur could not be confirmed, so the photo was refused.")
    return {"place": True, "person": False, "face_check": "blurred", "face_blurred": True}


def _get(ctx, iid):
    lib = getattr(ctx.lib, "lib", ctx.lib)
    try:
        found = lib.get(iid)
    except Exception:
        return None
    return found if isinstance(found, dict) else None


def job_prop(ctx, p):
    try:
        source, item, age = gate(p, pipelines.area(), ctx.chars.get, lambda iid: _get(ctx, iid))
        wf = _cards(pipelines.area())
    except PropError as exc:
        raise pipelines.UserError(str(exc)) from exc
    faces, detail, tex = pipelines.QUALITY_3D["standard"]
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(item))
    cc.set_in(wf, "FACES", target_face_count=faces)
    cc.set_in(wf, "DETAIL", target_resolution=detail)
    cc.set_in(wf, "TEXTURE SIZE", texture_size=tex)
    cc.set_seed(wf, pipelines._rand_seed())
    res = ctx.run(wf, "Making a 3D prop")
    outs = [path for path in pipelines.first(res) if str(path).lower().endswith((".glb", ".gltf"))]
    if not outs:
        raise pipelines.UserError("The prop step finished but did not return a glTF file.")
    provenance = {
        "format": "gltf",
        "importer": "godot",
        "rigged": False,
        "kind": "prop",
        "engine": "trellis2",
        "source": source,
        "licenses": public_licenses(),
        "limit": LIMIT,
    }
    meta = {"provenance": provenance, "model": "TRELLIS.2"}
    if source == "still":
        meta.update(pipelines._meta_from(item))
        meta["stated_age"] = age
        meta["dna"] = {"age": age, "stated_age": age, "age_source": "stated"}
    else:
        meta["parent"] = item["id"]
    ctx.add(outs[0], "model3d:prop", **meta)
