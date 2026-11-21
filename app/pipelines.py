"""What each button does: builds the ComfyUI job(s), runs them, saves results to the gallery.

Every job function gets a JobContext (ctx) and its params, and returns nothing -- results are
added with ctx.add(). Safety checks happen here (server side), not just in the web page.
"""
import re
import copy
import json
import os
import random
import shutil
import tempfile
import threading
import time

from PIL import Image

import assets
import catalog
import character as charmod
import comfy_client as cc
import extend_compose as EC
import machine_profiles
import mesh_check
import outfit_contract
import photoreal
import pipeline_candidates
import presets
import shot_qc
import safety
import sd15
import video_tools as V
from library import PERSON_ROLES, UPLOAD_ROLES, file_type

HERE = os.path.dirname(os.path.abspath(__file__))
POSE_DIR = os.path.join(HERE, "static", "poses")

EDIT_NEG = "low quality, blurry, deformed, extra limbs, bad hands, watermark, text"
KEEP = "Keep the same face, hair, body shape, skin tone and identity."


class Cancelled(Exception):
    pass


class UserError(Exception):
    """A problem the user can fix; the message is shown as-is."""


# which section the running job belongs to: "default" (no nudity) or "adult" (the 18+ section).
# Set by the server's worker for each job from a server-side check of the unlock cookie -- never from the request body.
_LOCAL = threading.local()
AGE_GUARD = None   # age_guard.AgeGuard, set by the server
LORA_LIB = None    # loras.LoraLibrary, set by the server
HARDWARE = None    # hardware_map.HardwareMap, set by the server (memory-free on a model-family switch)


def require_checker_on():
    """Create, video, train, and export do not run while the appearance checker is off."""
    import age_guard
    if AGE_GUARD is None or not AGE_GUARD.enabled:
        raise UserError(age_guard.CHECKER_OFF_REASON)


def set_area(area):
    _LOCAL.area = "adult" if area == "adult" else "default"


def area():
    return getattr(_LOCAL, "area", "default")


def _txt(*texts):
    ok, msg = safety.check_all(*texts)
    if not ok:
        raise UserError(msg)
    for t in texts:
        ok, msg = safety.check_area(t, area())
        if not ok:
            raise UserError(msg)


def _require_person_ages(record):
    """Refuse before a record is normalised or a job is accepted.

    A group container (people/persons/...) is not itself a person, so it does
    not also need a top-level age. A person record does.
    """
    if safety.people_in(record):
        ok, _, msg = safety.require_group_ages(record)
        if not ok:
            raise UserError(msg)
        if not safety.explicit_age_fields(record):
            return
    ok, _, msg = safety.require_stated_age(record)
    if not ok:
        raise UserError(msg)


def _bound_age_record(ctx, it, depth=0):
    """The declared age record for an item, walking parent/character links. Never invented."""
    if not isinstance(it, dict) or depth > 5:
        return None
    dna = it.get("dna")
    if isinstance(dna, dict) and safety.explicit_age_fields(dna):
        return dna
    if it.get("stated_age") is not None:
        return {"age": it.get("stated_age")}
    if it.get("character") and getattr(ctx, "chars", None) is not None:
        try:
            ch = ctx.chars.get(it["character"])
            if isinstance(ch, dict) and safety.explicit_age_fields(ch):
                return ch
        except Exception:
            pass
    parent_id = it.get("parent")
    if parent_id:
        try:
            return _bound_age_record(ctx, ctx.lib.get(parent_id), depth + 1)
        except Exception:
            return None
    return None


def safe_neg_for(neg, area_name):
    n = safety.safe_negative(neg)
    return f"{n}, {safety.NUDITY_NEGATIVE}" if area_name != "adult" else n


def _safe_neg(neg):
    return safe_neg_for(neg, area())


def _lora_hook(f, main_model_file):
    """Called for every LoRA x main-model loader: checks the LoRA is allowed here and fits this model."""
    import loras as L
    fam = L.family_of_model_file(main_model_file)
    rec = None
    if LORA_LIB is not None:
        try:
            rec = LORA_LIB.check_usable(f, fam if fam != "unknown" else None, area())
        except ValueError as e:
            raise UserError(str(e))
    else:
        ok, why = safety.check_lora(f)
        if not ok:
            raise UserError(why)
    pair = (rec or {}).get("pair")
    if pair and "high_noise" in main_model_file:
        return pair.get("high_noise") or f
    if pair and "low_noise" in main_model_file:
        return pair.get("low_noise") or f
    return f


cc.LORA_HOOK = _lora_hook


def _pair_hook(f):
    """The high/low halves the LoRA library recorded for a Wan 2.2 14B LoRA, or None."""
    if LORA_LIB is None or not LORA_LIB.available():
        return None
    try:
        rec = LORA_LIB.get(f)
    except Exception:
        return None
    pair = (rec or {}).get("pair")
    return pair if isinstance(pair, dict) else None


cc.PAIR_HOOK = _pair_hook


def _trigger_hook(lora_file):
    if LORA_LIB is None or not LORA_LIB.available():
        return []
    try:
        r = LORA_LIB.get(lora_file)
    except Exception:
        return []
    out = []
    for w in (r.get("trigger_words") or [])[:3]:
        ok, _ = safety.check_prompt(w)
        if ok and safety.check_area(w, area())[0]:
            out.append(w)
    return out


cc.TRIGGER_HOOK = _trigger_hook
catalog.AREA_FN = area


def _rand_seed():
    return random.randint(1, 2**31 - 1)


def _adv(p):
    a = p.get("advanced") or {}
    if not isinstance(a, dict):
        return {}
    out = {}
    for k in ("seed", "steps", "cfg", "sampler", "scheduler", "denoise"):
        if a.get(k) not in (None, ""):
            out[k] = a[k]
    loras = []
    for l in (a.get("loras") or [])[:4]:
        if isinstance(l, dict) and l.get("name"):
            name = str(l["name"])
            ok, why = safety.check_lora(name)
            if not ok:
                raise UserError(why)
            if ".." in name or name.startswith(("/", "\\")) or not re.fullmatch(r"[\w\-. /\\()+\[\]]+\.(safetensors|pt|ckpt|bin)", name):
                raise UserError(f"'{name}' isn't a LoRA file name. Pick one from the list.")
            loras.append((name, max(-2.0, min(2.0, float(l.get("strength", 1.0))))))
    if loras:
        out["loras"] = loras
    try:
        if "steps" in out:
            out["steps"] = max(1, min(150, int(out["steps"])))
        if "cfg" in out:
            out["cfg"] = max(0.0, min(30.0, float(out["cfg"])))
        if "denoise" in out:
            out["denoise"] = max(0.0, min(1.0, float(out["denoise"])))
        if "seed" in out:
            out["seed"] = int(out["seed"])
    except (TypeError, ValueError):
        raise UserError("One of the Advanced numbers isn't a number.")
    return out


# Tools whose seed comes from the saved character or the picture they start from, not from the request: a retry with a
# new seed is not possible, so a discarded result there says "change something" instead of offering one.
RETRY_NO_SEED = frozenset({"keep_face", "refine_skin", "refine_anatomy"})


class JobContext:
    def __init__(self, job, comfy, lib, chars):
        self.job, self.comfy, self.lib, self.chars = job, comfy, lib, chars
        self.tmp = tempfile.mkdtemp(prefix=f"job_{job['id']}_", dir=os.path.join(lib.root, "tmp"))
        self.uploaded = {}
        self.total = 1
        self.done = 0

    # progress -----------------------------------------------------------
    def steps(self, n):
        self.total = max(1, n)

    def progress(self, frac, msg=None):
        if self.job.get("cancel"):
            raise Cancelled()
        self.job["progress"] = round(min(0.999, (self.done + max(0.0, min(1.0, frac))) / self.total), 3)
        if msg:
            self.job["message"] = msg

    def next_step(self, msg=None):
        self.done += 1
        self.progress(0, msg)

    # ComfyUI ------------------------------------------------------------
    def upload_path(self, path, name):
        if path in self.uploaded:
            return self.uploaded[path]
        dst = os.path.join(self.tmp, name)
        if not name.endswith(".png") or not path.endswith(".png"):
            assets.to_png(path, dst)
        else:
            shutil.copyfile(path, dst)
        self.uploaded[path] = self.comfy.upload_image(dst)
        return self.uploaded[path]

    def upload_item(self, item):
        return self.upload_path(self.lib.path(item), f"es_{item['id']}.png")

    def run(self, wf, label):
        self.progress(0, label + " ...")
        self.job.setdefault("workflows", []).append(cc.finalize(wf))
        self.job["workflows"] = self.job["workflows"][-4:]
        out_dir = tempfile.mkdtemp(dir=self.tmp)
        def cb(f, m):
            self.progress(f, f"{label} -- {m}")
        if self.job.get("cancel"):
            raise Cancelled()
        if HARDWARE is not None:
            import hardware_map
            HARDWARE.before_run(hardware_map.family_of_graph(wf), self.comfy)
        res = self.comfy.run(cc.finalize(wf), out_dir, on_progress=cb, by_node=True)
        if self.job.get("cancel"):
            raise Cancelled()
        return res

    def add(self, path, kind, role="made", **meta):
        meta.setdefault("project", self.job["params"].get("project") or None)
        meta["area"] = area()
        t = file_type(path)
        if AGE_GUARD is not None and t in ("image", "video") and role != "skeleton":
            import age_guard
            if t == "image":
                res = AGE_GUARD.check(path)
            else:
                res = age_guard.check_video(AGE_GUARD, path, self.tmp, V.ffmpeg_bin())
            appearance = dict(res.get("appearance_check") or {})
            appearance.pop("age", None)
            appearance.pop("stated_age", None)
            meta["age_check"] = res.get("status")
            meta["appearance_check"] = appearance
            if age_guard.held_unusable(res):
                raise age_guard.AgeCheckBlocked(
                    res.get("reason") or "The age check held this result, so it was not saved for use.")
            if res.get("status") == "flag":
                # D-C-51 with D-C-49a: a flagged result is deleted, in every section. It is never saved, never shown,
                # never blurred. This reads no setting and no policy. The job ends with a plain message and offers a
                # retry with a new seed (routes_retry).
                try:
                    os.remove(path)
                except OSError:
                    pass  # the job's own folder is removed when the job ends, so a file that stays is never saved
                seedable = self.job.get("kind") not in RETRY_NO_SEED
                message = age_guard.DISCARDED if seedable else age_guard.DISCARDED_NO_SEED
                kept = len(self.job.get("results") or [])
                if kept:  # earlier results of this job were already saved: say so
                    message += " The %d earlier result%s of this job %s kept." % (kept, "" if kept == 1 else "s", "was" if kept == 1 else "were")
                self.job["can_retry"] = seedable
                self.job["warning"] = message
                raise age_guard.AgeCheckDiscarded(message, seedable)
        it = self.lib.add(path, kind, role=role, job=self.job["id"], **meta)
        self.job.setdefault("results", []).append(it["id"])
        return it

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def first(res, title_wf=None, title=None):
    """Pick output paths: from the node with a given title, else all of them."""
    if title and title_wf is not None and cc.has_title(title_wf, title):
        return res.get(cc.title_id(title_wf, title), [])
    return [p for v in res.values() for p in v]


# ---------------------------------------------------------------------------
# helpers shared by several tools
# ---------------------------------------------------------------------------
def _character(ctx, p):
    cid = p.get("character")
    if not cid:
        return None
    try:
        return ctx.chars.get(cid)
    except Exception:
        raise UserError("That saved character no longer exists.")


_UNDO_UPLOAD = re.compile(
    r"\b(nude|nudes|nudity|naked|topless|bottomless|undress\w*|uncloth\w*|no\s+clothes|without\s+clothes|"
    r"take\s+off|takes\s+off|strip(?:s|ped|ping)?|remove\s+(?:her|his|their|the)\s+(?:clothes|clothing|top|shirt|dress|bra|outfit))\b",
    re.I)


def _lineage_get(ctx):
    """Item lookup for the lineage walk. It reads the whole library, so a 21+ ancestor is still seen."""
    lib = getattr(ctx, "lib", None)
    lib = getattr(lib, "lib", lib)
    return getattr(lib, "get", None)


def has_upload_ancestor(img, get_item):
    """True when this picture or any ancestor up to the root has an upload role.

    `derived_role` relabels an edit of an upload as "made", so the role of the picture alone is not
    enough. A parent that cannot be found (deleted, or no way to look it up) counts as an upload, and so
    does a loop: the walk fails closed.
    """
    if not isinstance(img, dict):
        return False
    seen = set()
    cur = img
    while True:
        if cur.get("role") in UPLOAD_ROLES:
            return True
        parent_id = cur.get("parent")
        if not parent_id:
            return False
        if parent_id in seen or len(seen) >= 64 or get_item is None:
            return True
        seen.add(parent_id)
        try:
            cur = get_item(parent_id)
        except Exception:
            return True
        if not isinstance(cur, dict):
            return True


def _refuse_uploaded_undress(img, *parts, ctx=None, get_item=None):
    """An uploaded picture can be dressed. It cannot have its clothes taken off.

    That also holds for anything made from an upload, however many steps back: the walk follows
    `parent` to the root. Pictures with no upload anywhere in their lineage are unchanged.
    """
    if not img:
        return
    blob = " ".join(str(p or "") for p in parts)
    if not _UNDO_UPLOAD.search(blob):
        return
    lookup = get_item if get_item is not None else (_lineage_get(ctx) if ctx is not None else None)
    if has_upload_ancestor(img, lookup):
        raise UserError(
            "Easy Studio won't remove clothes from an uploaded picture, or from anything made from one. "
            "Change the outfit on a picture this app made from text, or describe a garment that stays on.")


def _person(ctx, p, key="image"):
    try:
        it = ctx.lib.person_image(p.get(key))
    except (KeyError, PermissionError, ValueError) as e:
        raise UserError(str(e))
    records = _bound_people(ctx, it)
    if not records:
        raise UserError("Missing stated age: age is missing. This picture has no per-person age record.")
    for record in records:
        ok, _age, msg = safety.require_stated_age(record)
        if not ok:
            raise UserError(msg)
    it = dict(it)
    it["dna"] = records[0]
    if len(records) > 1:
        it["people"] = records
    return it


def _style_of(ctx, item, p):
    if p.get("style") in ("anime", "photo", "render3d", "painted"):
        return p["style"]
    ch = item.get("character")
    if ch:
        try:
            return ctx.chars.get(ch).get("style", "photo")
        except Exception:
            pass
    return item.get("style") or "photo"


def _pose_path(ctx, pose):
    """A preset id (static/poses/<id>.png) or a gallery item with role 'skeleton'."""
    if not pose:
        return None
    if any(pose == pid for pid, _ in catalog.POSES + catalog.ADULT_POSES):
        return os.path.join(POSE_DIR, pose + ".png")
    try:
        it = ctx.lib.get(pose)
    except (KeyError, PermissionError):
        raise UserError("Unknown pose.")
    if it.get("role") != "skeleton":
        raise UserError("Only stick-figure poses can be used as a pose.")
    return ctx.lib.path(it)


def _bound_people(ctx, it, depth=0):
    """Every declared person record on an item, walking parent links. Never invented."""
    if not isinstance(it, dict) or depth > 5:
        return []
    people = it.get("people")
    if isinstance(people, list) and people and all(isinstance(person, dict) for person in people):
        return [dict(person) for person in people]
    dna = it.get("dna")
    if isinstance(dna, dict) and safety.people_in(dna) and not safety.explicit_age_fields(dna):
        return [dict(person) for person in safety.people_in(dna)]
    record = _bound_age_record(ctx, it, depth)
    return [record] if record else []


def _meta_from(item, character=None):
    meta = {"parent": item["id"], "character": character or item.get("character"), "style": item.get("style")}
    people = item.get("people")
    if isinstance(people, list) and len(people) > 1:
        meta["people"] = people
    if is_proof(item):  # D-C-28: anything made from an unscored proof stays a proof
        meta.update(proof=True, qc_status=UNSCORED_PROOF)
    if item.get("remote"):  # made by a hosted service: stays marked, never trained on
        meta["remote"] = True
    return meta


def qwen_edit(ctx, image_item, instruction, image2=None, image3=None, angles=False, adv=None, label="Editing",
              seed=None, kind="edit"):
    wf = cc.load_workflow("angles_qwen2511_api.json" if angles else "edit_qwen2511_api.json")
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(image_item))
    for title, src in (("IMAGE 2", image2), ("IMAGE 3", image3)):
        if src is None:
            cc.drop_title(wf, title)
        else:
            name = ctx.upload_path(src, f"es_ref_{abs(hash(src)) % 10**8}.png") if isinstance(src, str) \
                else ctx.upload_item(src)
            cc.set_in(wf, title, image=name)
    full = instruction.strip() + " The person is a fictional adult."
    _txt(full)
    cc.set_in(wf, "POSITIVE", prompt=full)
    cc.set_in(wf, "NEGATIVE", prompt=_safe_neg(EDIT_NEG))
    cc.set_seed(wf, seed if seed is not None else _rand_seed())
    cc.apply_advanced(wf, adv)
    res = ctx.run(wf, label)
    outs = first(res)
    if not outs:
        raise UserError("ComfyUI finished but returned no picture.")
    return outs[0], full


# ---------------------------------------------------------------------------
# 1. Character creator
# ---------------------------------------------------------------------------
def job_create(ctx, p):
    require_checker_on()
    raw = p.get("dna") if isinstance(p.get("dna"), dict) else None
    if raw and safety.people_in(raw) and safety.explicit_age_fields(raw) and not isinstance(p.get("people"), list):
        raise UserError("Unsupported group shape: a group container cannot also carry its own age.")
    declared = safety.scene_records(p)
    if not declared:
        raise UserError("Missing stated age: age is missing.")
    validated = []
    for person in declared:
        one, err = charmod.normalise(person)
        if err:
            raise UserError(err)
        validated.append(one)
    extra = str(p.get("extra_scene") or "")[:300]
    ok, msg = safety.check_group_prompt(extra, validated)
    if not ok:
        raise UserError(msg)
    _txt(extra)
    dna = validated[0]
    records = list(validated)
    outfit = catalog.outfit_item(p.get("outfit")) if p.get("outfit") else None
    scene = catalog.find(catalog.SCENES, p.get("scene") or "studio")
    light = catalog.find(catalog.LIGHTING, p.get("lighting") or "soft")
    cam = catalog.find(catalog.CAMERAS, p.get("camera") or "half")
    count = max(1, min(4, int(p.get("count") or 4)))
    style = dna["style"]
    parts = [charmod.describe(dna)]
    if outfit:
        parts.append("wearing " + outfit["p"])
    parts += [cam["p"] if cam else "", scene["p"] if scene else "", light["p"] if light else "", extra]
    prompt = ", ".join(x for x in parts if x)
    if style == "anime":
        g = "mature female" if dna["gender"] == "woman" else "mature male"
        prompt = f"masterpiece, best quality, newest, absurdres, {g}, " + prompt
    sd = sd15.wants(p)
    if sd and area() == "adult":
        raise UserError("Photo (SD 1.5) is in the everyday section only.")
    if sd and style != "photo":
        raise UserError("Photo (SD 1.5) is for the Realistic photo style.")
    try:
        row = None if sd else photoreal.choose_still(p, style, area(), [prompt])
    except photoreal.PhotorealError as e:
        raise UserError(str(e))
    if sd:
        wfname, mdl = sd15.WORKFLOW, sd15.LABEL
    elif row is None and style == "anime":
        wfname, mdl = "image_noobai_xl_api.json", "NoobAI-XL"
    elif row is None:
        wfname, mdl = "image_chroma1hd_api.json", "Chroma1-HD"
    else:
        wfname, mdl = row["workflow"], row["label"]
    if row is not None:
        clause = photoreal.skin_clause(row)
        if clause:
            prompt = prompt + ", " + clause
        lens = catalog.find(photoreal.LENSES, p.get("lens")) if p.get("lens") else None
        if lens:
            prompt = prompt + ", " + lens["p"]
    want_contact = p.get("preset") == "contact_explicit" or (area() == "adult" and p.get("preset") != "off")
    if want_contact:
        if area() != "adult":
            raise UserError("The contact preset is only in the 18+ section.")
        prompt = prompt + ". " + shot_qc.contact_clause()
    prompt = safety.add_adult_hint(prompt)
    if len(validated) > 1:
        prompt = " and ".join(charmod.describe(one, include_style=False) for one in validated) + ", " + prompt
    ok, msg = safety.reconcile_prompt_ages(prompt, records)
    if not ok:
        raise UserError(msg)
    _txt(prompt)
    neg = sd15.NEGATIVE if sd else presets.IMAGE_MODELS["Anime / illustrated (NoobAI-XL)" if style == "anime" else
                                                         "Realistic / painterly (Chroma1-HD)"]["negative"]
    adv = _adv(p)
    base_seed = int(adv.pop("seed", 0) or p.get("seed") or dna.get("seed") or 0) or _rand_seed()
    aspect = p.get("aspect") or "portrait"
    if sd:
        w, h = sd15.size_for(aspect)
    elif row is not None:
        w, h = photoreal.size_for(row, aspect if aspect in ("portrait", "square", "wide") else "portrait")
    else:
        w, h = presets.size_for_aspect(*{"portrait": (2, 3), "square": (1, 1), "tall": (9, 16), "wide": (16, 9)}
                                       .get(aspect, (2, 3)), 1024 * 1024)
    try:
        skin = photoreal.skin_lora_slot(p, row) if row is not None else None
    except photoreal.PhotorealError as e:
        raise UserError(str(e))
    if skin:
        adv.setdefault("loras", []).append(skin)
    if row and sum(bool(p.get(key)) for key in ("face_fix", "skin_lora", "finisher")) > 1:
        raise UserError("Run the skin LoRA, the face fix, or one finisher by itself. Do not stack them.")
    plan = photoreal.detailer_plan(row["id"], photoreal.sex_of(params=p), aspect == "portrait" and p.get("camera") == "full", area(), face_fix=bool(p.get("face_fix"))) if row else []
    ctx.steps(count)
    for i in range(count):
        wf = cc.load_workflow(wfname)
        if row and row.get("id") == "chroma":
            for node in wf.values():
                if node.get("class_type") == "UNETLoader":
                    try:
                        machine_profiles.check_chroma_file(node["inputs"].get("unet_name"))
                    except ValueError as e:
                        raise UserError(str(e))
                    # The profile's chroma_dtype says which file this machine loads (fp16 or bf16, never fp8-only).
                    # ComfyUI 0.43.0's UNETLoader has no fp16/bf16 choice: "default" loads the file's own precision.
                    node["inputs"]["weight_dtype"] = "default"
        if row and row.get("shift") is not None:
            for node in wf.values():
                if node["class_type"] == "ModelSamplingAuraFlow":
                    node["inputs"]["shift"] = row["shift"]
        cc.set_in(wf, "POSITIVE", text=prompt)
        if cc.has_title(wf, "NEGATIVE"):
            cc.set_in(wf, "NEGATIVE", text=_safe_neg(neg))
        cc.set_in(wf, "SIZE", width=w, height=h)
        cc.apply_advanced(wf, adv)
        cc.set_seed(wf, base_seed + i)
        res = ctx.run(wf, f"Picture {i + 1} of {count}")
        for path in first(res):
            if row and row.get("grain"):
                photoreal.film_finish(path, row["grain"])
            prov = {"look": None if row is None else row["id"], "model": mdl, "workflow": wfname,
                    "shift": None if row is None else row.get("shift"), "detailers": plan,
                    "seed": base_seed + i, "request_id": ctx.job.get("request_id"),
                    "regenerated_from": p.get("character_id") if p.get("regenerate") else None}
            note = pipeline_candidates.selection_note("still")
            if note:
                prov["pipeline_candidate"] = note
            ctx.add(path, "create", prompt=prompt, seed=base_seed + i, model=mdl, style=style,
                    character=p.get("character_id") or None, dna=dna,
                    people=validated if len(validated) > 1 else None, provenance=prov)
        ctx.next_step()


# ---------------------------------------------------------------------------
# 2. Edits: outfit / pose / scene / object / expression / camera / custom
# ---------------------------------------------------------------------------
def build_instruction(ctx, p, has_ref):
    op = p.get("op")
    free = str(p.get("text") or "")[:500]
    _txt(free)
    if op == "outfit":
        if has_ref:
            what = free or "outfit"
            return f"The person in image 1 now wears the {what} shown in image 2. Keep the pose and background. {KEEP}"
        it = catalog.outfit_item(p.get("item"))
        color = catalog.find(catalog.COLORS, p.get("color")) if p.get("color") else None
        mat = catalog.find(catalog.MATERIALS, p.get("material")) if p.get("material") else None
        desc = " ".join(x for x in [color["p"] if color else "", mat["p"] if mat else "", it["p"] if it else ""] if x)
        desc = ", ".join(x for x in [desc, free] if x)
        if not desc:
            raise UserError("Pick an outfit (or describe one).")
        return f"Change the person's clothing to: {desc}. Keep the same pose and background. {KEEP}"
    if op == "pose":
        return (f"Make the person in image 1 take exactly the pose of the stick figure in image 2. "
                f"Keep the same outfit and background. {KEEP} {free}")
    if op == "scene":
        sc = catalog.find(catalog.SCENES, p.get("scene")) if p.get("scene") else None
        li = catalog.find(catalog.LIGHTING, p.get("lighting")) if p.get("lighting") else None
        if has_ref:
            return (f"Place the person from image 1 into the setting shown in image 2, with matching lighting and "
                    f"shadows. Keep the same outfit and pose. {KEEP} {free}")
        desc = ", ".join(x for x in [sc["p"] if sc else "", li["p"] if li else "", free] if x)
        if not desc:
            raise UserError("Pick a scene (or describe one).")
        return f"Change the background and setting to: {desc}. Relight the person to match. Keep the same outfit and pose. {KEEP}"
    if op == "object":
        ob = catalog.find(catalog.OBJECTS, p.get("object")) if p.get("object") else None
        pl = catalog.find(catalog.PLACEMENTS, p.get("placement") or "beside")
        if has_ref:
            return f"Add the object shown in image 2 {pl['p']}, with natural lighting, scale and shadows. Keep everything else unchanged. {free}"
        desc = ", ".join(x for x in [ob["p"] if ob else "", free] if x)
        if not desc:
            raise UserError("Pick an object (or describe one).")
        return f"Add {desc} {pl['p']}, with natural lighting, scale and shadows. Keep everything else unchanged. {KEEP}"
    if op == "expression":
        ex = catalog.find(catalog.EXPRESSIONS, p.get("expression") or "smile")
        return f"Change only the facial expression to: {ex['p']}. Keep the same outfit, pose and background. {KEEP}"
    if op == "camera":
        cam = catalog.find(catalog.CAMERAS, p.get("camera") or "full")
        return f"Show the same person as a {cam['p']}. Keep the same outfit and background. {KEEP}"
    if op == "custom":
        if not free:
            raise UserError("Describe the change you want.")
        return f"{free}. {KEEP}"
    raise UserError("Unknown edit type.")


def job_edit(ctx, p):
    img = _person(ctx, p)
    ref = None
    if p.get("ref"):
        try:
            allowed = {"outfit": ("clothing", "made", "my_character"), "object": ("object", "made"),
                       "scene": ("background", "made")}.get(p.get("op"), ())
            ref = ctx.lib.ref_image(p["ref"], allowed)
        except (KeyError, PermissionError, ValueError) as e:
            raise UserError(str(e))
    image2 = ref
    if p.get("op") == "pose":
        path = _pose_path(ctx, p.get("pose"))
        if not path:
            raise UserError("Pick a pose first.")
        image2 = path
    instr = build_instruction(ctx, p, has_ref=ref is not None)
    _refuse_uploaded_undress(img, instr, p.get("text"), p.get("item"), ctx=ctx)
    if ref is not None and p.get("reference_strength") is not None:
        try:
            instr = instr + " " + photoreal.reference_clause(p.get("reference_strength"))
        except photoreal.PhotorealError as e:
            raise UserError(str(e))
    count = max(1, min(4, int(p.get("count") or 1)))
    adv = _adv(p)
    seed0 = int(adv.pop("seed", 0) or 0) or _rand_seed()
    ctx.steps(count)
    for i in range(count):
        out, full = qwen_edit(ctx, img, instr, image2=image2, adv=adv, seed=seed0 + i,
                              label=f"{p.get('op', 'edit').title()} {i + 1}/{count}")
        ctx.add(out, "edit:" + str(p.get("op")), prompt=full, seed=seed0 + i, model="Qwen-Image-Edit-2511",
                **_meta_from(img))
        ctx.next_step()


def job_inpaint(ctx, p):
    img = _person(ctx, p)
    text = str(p.get("text") or "")[:600]
    if not text:
        raise UserError("Describe what should appear in the painted area.")
    _refuse_uploaded_undress(img, text, ctx=ctx)
    _txt(text)
    style = _style_of(ctx, img, p)
    w, h = img.get("w"), img.get("h")
    if not w:
        with Image.open(ctx.lib.path(img)) as im:
            w, h = im.size
    src_path, src_name = ctx.lib.path(img), None
    if w * h > 2_400_000:  # e.g. an upscaled picture: painting at 10+ megapixels is very slow / runs out of memory
        f = (1_600_000 / (w * h)) ** 0.5
        w, h = int(w * f) // 8 * 8, int(h * f) // 8 * 8
        src_path = os.path.join(ctx.tmp, f"small_{ctx.job['id']}.png")
        with Image.open(ctx.lib.path(img)) as im:
            im.convert("RGB").resize((w, h), Image.LANCZOS).save(src_path)
        src_name = ctx.upload_path(src_path, f"es_small_{ctx.job['id']}.png")
    mask_path = os.path.join(ctx.tmp, f"mask_{ctx.job['id']}.png")
    try:
        assets.prepare_mask(p.get("mask"), (w, h), mask_path)
    except ValueError as e:
        raise UserError(str(e))
    anime = style == "anime"
    wf = cc.load_workflow("inpaint_noobai_xl_api.json" if anime else "inpaint_chroma1hd_api.json")
    prompt = safety.add_adult_hint(("masterpiece, best quality, " if anime else "photorealistic, detailed, ") + text)
    cc.set_in(wf, "IMAGE 1", image=src_name or ctx.upload_item(img))
    cc.set_in(wf, "MASK", image=ctx.upload_path(mask_path, f"es_mask_{ctx.job['id']}.png"))
    cc.set_in(wf, "MASK GROW", expand=int(max(0, min(64, int(p.get("grow") or 8)))))
    cc.set_in(wf, "POSITIVE", text=prompt)
    cc.set_in(wf, "NEGATIVE", text=_safe_neg(presets.IMAGE_MODELS[
        "Anime / illustrated (NoobAI-XL)" if anime else "Realistic / painterly (Chroma1-HD)"]["negative"]))
    strength = max(0.3, min(1.0, float(p.get("strength") or 0.9)))
    cc.set_in(wf, "STRENGTH" if cc.has_title(wf, "STRENGTH") else "SEED", denoise=strength)
    adv = _adv(p)
    cc.apply_advanced(wf, adv)
    if not adv.get("seed"):
        cc.set_seed(wf, _rand_seed())
    res = ctx.run(wf, "Painting the change")
    for path in first(res):
        ctx.add(path, "edit:paint", prompt=prompt, model="NoobAI-XL" if anime else "Chroma1-HD", **_meta_from(img))


# ---------------------------------------------------------------------------
# 3. Background tools, upscale, pose reading
# ---------------------------------------------------------------------------
def _remove_bg(ctx, item, label="Removing background"):
    wf = cc.load_workflow("remove_bg_api.json")
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(item))
    res = ctx.run(wf, label)
    cut = first(res, wf, "CUTOUT")
    if not cut:
        raise UserError("The background remover returned nothing.")
    return cut[0]


def job_remove_bg(ctx, p):
    try:
        item = ctx.lib.ref_image(p.get("image"), ("made", "my_character", "clothing", "object"))
    except (KeyError, PermissionError, ValueError) as e:
        raise UserError(str(e))
    cut = _remove_bg(ctx, item)
    ctx.add(cut, "cutout", role=ctx.lib.derived_role(item), **_meta_from(item))


def job_bg_quick(ctx, p):
    img = _person(ctx, p)
    ctx.steps(2)
    cut = _remove_bg(ctx, img)
    ctx.next_step("Placing on the new background")
    out = os.path.join(ctx.tmp, f"bgswap_{ctx.job['id']}.png")
    with Image.open(cut) as c:
        size = c.size
    if p.get("background"):
        try:
            bg = ctx.lib.ref_image(p["background"], ("background", "made"))
        except (KeyError, PermissionError, ValueError) as e:
            raise UserError(str(e))
        assets.composite(cut, ctx.lib.path(bg), out, scale=float(p.get("scale") or 0.92))
    else:
        color = str(p.get("color") or "#FFFFFF")
        if not __import__("re").fullmatch(r"#[0-9A-Fa-f]{6}", color):
            color = "#FFFFFF"
        bgp = assets.solid_background(size, color, os.path.join(ctx.tmp, "solid.png"))
        assets.composite(cut, bgp, out, scale=1.0)
    ctx.add(out, "edit:bg_quick", **_meta_from(img))


def job_upscale(ctx, p):
    try:
        item = ctx.lib.ref_image(p.get("image"), ("made", "my_character", "clothing", "object", "background"))
    except (KeyError, PermissionError, ValueError) as e:
        raise UserError(str(e))
    scale = 4 if str(p.get("scale")) == "4" else 2
    wf = cc.load_workflow("upscale_api.json")
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(item))
    cc.set_in(wf, "SCALE", scale_by=1.0 if scale == 4 else 0.5)
    res = ctx.run(wf, f"Upscaling x{scale}")
    note = pipeline_candidates.selection_note("upscale")
    for path in first(res):
        ctx.add(path, "upscale", role=ctx.lib.derived_role(item),
                provenance={"pipeline_candidate": note} if note else None, **_meta_from(item))


def job_pose_extract(ctx, p):
    try:
        item = ctx.lib.ref_image(p.get("image"), ("pose_ref", "made", "my_character"))
    except (KeyError, PermissionError, ValueError) as e:
        raise UserError(str(e))
    wf = cc.load_workflow("pose_extract_api.json")
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(item))
    res = ctx.run(wf, "Reading the pose")
    for path in first(res):
        ctx.add(path, "pose", role="skeleton", parent=item["id"], title=p.get("name") or "My pose")


def job_pose_new(ctx, p):
    """A brand-new picture of a saved character in a pose (Z-Image Turbo + pose ControlNet)."""
    ch = _character(ctx, p)
    if not ch:
        raise UserError("Pick a saved character first.")
    path = _pose_path(ctx, p.get("pose"))
    if not path:
        raise UserError("Pick a pose first.")
    outfit = catalog.outfit_item(p.get("outfit")) if p.get("outfit") else None
    scene = catalog.find(catalog.SCENES, p.get("scene") or "studio")
    prompt = safety.add_adult_hint(", ".join(x for x in [charmod.describe(ch), "full body",
                                   ("wearing " + outfit["p"]) if outfit else "", scene["p"]] if x))
    _txt(prompt)
    wf = cc.load_workflow("pose_zimage_api.json")
    cc.set_in(wf, "POSITIVE", text=prompt)
    cc.set_in(wf, "POSE IMAGE", image=ctx.upload_path(path, "es_pose_" + os.path.basename(path)))
    with Image.open(path) as im:
        pw, ph = im.size
    w, h = presets.size_for_aspect(pw, ph, 1024 * 1024)
    cc.set_in(wf, "SIZE", width=w, height=h)
    cc.set_in(wf, "POSE STRENGTH", strength=max(0.2, min(1.0, float(p.get("strength") or 0.8))))
    adv = _adv(p)
    cc.apply_advanced(wf, adv)
    if not adv.get("seed"):
        cc.set_seed(wf, ch.get("seed") or _rand_seed())
    res = ctx.run(wf, "Drawing the pose")
    for path in first(res):
        ctx.add(path, "pose_new", prompt=prompt, model="Z-Image Turbo + pose control", character=ch["id"],
                style=ch.get("style"))


# ---------------------------------------------------------------------------
# 4. Video
# ---------------------------------------------------------------------------
def _motion_text(p, default=None, hint=True):
    m = catalog.find(catalog.MOTIONS + (catalog.ADULT_MOTIONS if area() == "adult" else []), p.get("motion")) if p.get("motion") else None
    free = str(p.get("text") or "")[:500]
    _txt(free)
    t = ", ".join(x for x in [m["p"] if m else "", free] if x) or default
    if not t:
        raise UserError("Pick a motion (or describe one).")
    _txt(t)
    return safety.add_adult_hint(t) if hint else t


def _video_size(img_path, quality):
    with Image.open(img_path) as im:
        w, h = im.size
    return presets.size_for_aspect(w, h, 1280 * 720 if quality == "720" else 832 * 480)


def _stack_video_loras(p, item):
    """Motion LoRAs from Advanced, plus 18+ anatomy LoRAs when this job is in that section."""
    try:
        adv = _adv(EC.with_loras(p, LORA_LIB))  # the top-level `loras` join the Advanced ones (same checks, same cap)
    except EC.ExtendError as e:
        raise UserError(str(e))
    try:
        extra = photoreal.anatomy_loras(p.get("anatomy"), area(), photoreal.sex_of(item, p))
    except photoreal.PhotorealError as e:
        raise UserError(str(e))
    if extra:
        adv.setdefault("loras", []).extend(extra)
    return adv


def _video_look(p):
    """Video is always photographic: look defaults to realistic, anime and other drawn looks are refused."""
    try:
        return EC.resolve_look(p)
    except EC.ExtendError as e:
        raise UserError(str(e))


def _template_for(five_b, end=False, best=False):
    i2v = __import__("model_registry").role("video_i2v")
    if five_b and not end:
        return cc.load_workflow(FIVE_B_WORKFLOW)
    if end:
        return cc.load_workflow(i2v["workflow_flf_quality"] if best else i2v["workflow_flf_fast"])
    return cc.load_workflow(i2v["workflow_quality"] if best else i2v["workflow_fast"])


def _preflight_loras(wf, adv):
    """Refuse a LoRA that does not fit this model before any frame is cut or any model runs."""
    EC.preflight_loras(wf, (adv or {}).get("loras"), UserError)


def _video_clip(ctx, start_path, motion, seconds, size, best, end_path=None, adv=None, label="Animating", info=None):
    i2v = __import__("model_registry").role("video_i2v")
    if end_path:
        name = i2v["workflow_flf_quality"] if best else i2v["workflow_flf_fast"]
    else:
        name = i2v["workflow_quality"] if best else i2v["workflow_fast"]
    wf = cc.load_workflow(name)
    cc.set_in(wf, "POSITIVE", text=motion)
    cc.set_in(wf, "NEGATIVE", text=_safe_neg(presets.VIDEO_NEGATIVE))
    cc.set_in(wf, "START IMAGE", image=ctx.upload_path(start_path, f"es_start_{abs(hash(start_path)) % 10**8}.png"))
    if end_path:
        cc.set_in(wf, "END IMAGE", image=ctx.upload_path(end_path, f"es_end_{abs(hash(end_path)) % 10**8}.png"))
    length, chained = shot_qc.cap_frames(presets.frames_for_seconds(seconds))
    fps = float(i2v.get("fps") or presets.WAN_FPS)
    cc.set_in(wf, "SIZE", width=size[0], height=size[1], length=length)
    cc.set_in(wf, "FPS", fps=fps)
    cc.apply_advanced(wf, adv or {})
    seed = (adv or {}).get("seed")
    if not seed:
        seed = _rand_seed()
        cc.set_seed(wf, seed)
    res = ctx.run(wf, label)
    outs = [x for x in first(res) if x.lower().endswith((".mp4", ".webm"))]
    if not outs:
        raise UserError("ComfyUI finished but returned no video.")
    if info is not None:
        info.update(workflow=name, model=i2v["label"], frames=length, fps=fps, seed=seed, chained=chained,
                    width=int(size[0]), height=int(size[1]))
    return outs[0], chained


FIVE_B_WORKFLOW = "vm_wan22_5b_i2v_api.json"
FIVE_B_MODEL = "Wan 2.2 5B TI2V"
FIVE_B_EXTEND_LIMIT = ("On this machine, video uses the Wan 2.2 5B model, which starts from the last frame only. "
                       "A-to-B and loop need the 14B model on the server.")


def five_b_profile(profile=None):
    """True when this machine animates with the Wan 2.2 5B model (the Mac, the 4090 preview card)."""
    profile = machine_profiles.active() if profile is None else profile
    return profile.get("video_proof") == "wan22_ti2v_5b"


def _five_b_timing(wf, seconds):
    """(frames, chained, fps) for the 5B template: its own frame rate (24) and its own longest clip (121 frames)."""
    fps, cap = 24.0, 121
    for node in wf.values():
        if node.get("class_type") == "CreateVideo" and node["inputs"].get("fps"):
            fps = float(node["inputs"]["fps"])
        if node.get("class_type") == "Wan22ImageToVideoLatent" and isinstance(node["inputs"].get("length"), int):
            cap = node["inputs"]["length"]
    want = presets.frames_for_seconds(seconds, fps)
    return min(want, cap), want > cap, fps


def _video_clip_5b(ctx, start_path, motion, seconds, size, adv, label="Motion proof", info=None):
    """A clip on the 5B fp16 model. Used by the Mac and the 4090 preview profile.

    The frame count follows the template's 24 fps, so 2 s is 49 frames. Width and height are
    multiples of 32, which the 5B model needs.
    """
    wf = cc.load_workflow(FIVE_B_WORKFLOW)
    cc.set_in(wf, "CLIP Text Encode (Positive Prompt)", text=motion)
    cc.set_in(wf, "CLIP Text Encode (Negative Prompt)", text=_safe_neg(presets.VIDEO_NEGATIVE))
    cc.set_in(wf, "LoadImage", image=ctx.upload_path(start_path, f"es_start_{abs(hash(start_path)) % 10**8}.png"))
    length, chained, fps = _five_b_timing(wf, seconds)
    width, height = max(32, int(size[0]) // 32 * 32), max(32, int(size[1]) // 32 * 32)
    seed = int((adv or {}).get("seed") or 0) or _rand_seed()
    for node in wf.values():
        if node["class_type"] == "Wan22ImageToVideoLatent":
            node["inputs"]["width"] = width
            node["inputs"]["height"] = height
            node["inputs"]["length"] = length
        if node["class_type"] == "UNETLoader":  # the file is fp16 already; ComfyUI 0.43.0 has no fp16 choice
            node["inputs"]["weight_dtype"] = "default"
        if node["class_type"] == "KSampler":
            node["inputs"]["seed"] = seed
    cc.inject_loras(wf, (adv or {}).get("loras"))
    res = ctx.run(wf, label)
    outs = [x for x in first(res) if x.lower().endswith((".mp4", ".webm"))]
    if not outs:
        raise UserError("ComfyUI finished but returned no video.")
    if info is not None:
        info.update(workflow=FIVE_B_WORKFLOW, model=FIVE_B_MODEL, frames=length, fps=fps, seed=seed,
                    chained=chained, width=width, height=height)
    return outs[0], chained


def _checkpoint_choice(p):
    chosen = p.get("checkpoint") or "wan22_i2v"
    for row in reg_checkpoints():
        if row.get("id") == chosen:
            return row
    raise UserError("That video checkpoint is not in the registry.")


def reg_checkpoints():
    import model_registry as reg
    return reg.video_checkpoints()


def _video_lora_choice(p):
    name = p.get("video_lora")
    if not name:
        return None
    import model_registry as reg
    row = reg.video_lora(name)
    if not row:
        raise UserError("That video LoRA is not in the registry.")
    if row.get("adult_only") and area() != "adult":
        raise UserError("That LoRA only runs inside the 18+ section.")
    return row


UNSCORED_PROOF = "unscored_proof"
UNSCORED_PROOF_NOTE = ("Unscored motion proof (D-C-28): nobody scored the keyframes, so this clip is a proof only. "
                       "It is never trained on, never used as a scored keyframe, and never counted as QC-passed.")


def is_proof(item, get_item=None):
    """True for an unscored motion proof, or anything made from one.

    Jobs copy the mark onto what they make from a proof (_meta_from). With get_item the check also walks
    the parent links, so a path that did not copy the mark still counts. A parent that can no longer be
    found ends the walk: this is a quality gate, and a deleted picture does not block its children.
    """
    seen = set()
    cur = item
    while isinstance(cur, dict):
        if cur.get("proof") is True or cur.get("qc_status") == UNSCORED_PROOF:
            return True
        parent = cur.get("parent")
        if not parent or get_item is None or parent in seen or len(seen) >= 64:
            return False
        seen.add(parent)
        try:
            cur = get_item(parent)
        except Exception:
            return False
    return False


def has_remote_ancestor(item, get_item=None):
    """True for a result a hosted service made (remote: true), or anything made from one. Like is_proof,
    a parent that can no longer be found ends the walk (the mark is copied onto children as well)."""
    seen = set()
    cur = item
    while isinstance(cur, dict):
        if cur.get("remote") is True:
            return True
        parent = cur.get("parent")
        if not parent or get_item is None or parent in seen or len(seen) >= 64:
            return False
        seen.add(parent)
        try:
            cur = get_item(parent)
        except Exception:
            return False
    return False


def proof_mark(item, get_item=None):
    """The fields that keep a proof's mark on something made from it, or nothing."""
    return {"proof": True, "qc_status": UNSCORED_PROOF} if is_proof(item, get_item) else {}


def unscored_proof_allowed(p, profile, end=None):
    """D-C-28: on the first-test machine, the 5B proof may run with no keyframe scores at all.

    Only with no qc in the request (a failing or partial score is still refused), no end picture,
    not for a photoreal (finished) clip, and only in the everyday section. Every safety rail runs as before.
    """
    return (p.get("qc") is None and not p.get("photoreal") and profile.get("first_test") is True
            and five_b_profile(profile) and not end and area() != "adult")


def scored_keyframes(ctx, p, img):
    """The still-first gate: two or more scored keyframes, the animated one passing. A proof is never one of them."""
    gate = shot_qc.require_variants(p.get("qc"), img["id"])
    for variant in gate["variants"]:
        if is_proof(_person(ctx, {"image": variant["image"]}), _lineage_get(ctx)):
            raise shot_qc.ShotQCError("A still taken from an unscored motion proof can't be a scored keyframe.")
    return gate


def job_video(ctx, p):
    require_checker_on()
    img = _person(ctx, p)
    end = None
    if p.get("end_image"):
        end = _person(ctx, p, "end_image")
    profile = machine_profiles.active()
    unscored = unscored_proof_allowed(p, profile, end)
    try:
        if unscored:
            gate = {"status": UNSCORED_PROOF, "use": img["id"], "variants": [], "scores": None, "worst_axis": "",
                    "note": UNSCORED_PROOF_NOTE}
        else:
            gate = scored_keyframes(ctx, p, img)
        plan = shot_qc.guard_plan(p)
        if p.get("fail_fast") is not None and not shot_qc.fail_fast_ok(p.get("fail_fast")):
            raise shot_qc.ShotQCError("Fail-fast at 0:02: hands, genitals, contact, and face must all be OK, or abort.")
        if p.get("action") or p.get("camera_move") or p.get("pace"):
            motion = shot_qc.i2v_prompt(p.get("action"), p.get("camera_move"), p.get("pace"))
            motion = safety.add_adult_hint(motion)
            _txt(motion)
        else:
            motion = _motion_text(p, "the person moves smoothly and naturally from the first pose into the last pose" if end else None)
            shot_qc.check_motion_words(motion)
        _refuse_uploaded_undress(img, motion, p.get("text"), p.get("motion"), p.get("action"), ctx=ctx)
    except shot_qc.ShotQCError as e:
        raise UserError(str(e))
    checkpoint = _checkpoint_choice(p)
    video_lora = _video_lora_choice(p)
    look = _video_look(p)
    motion = EC.lock(motion)  # the realism lock, on every first-run video
    _txt(motion)
    preview = bool(p.get("preview"))
    seconds = photoreal.snap_seconds(p.get("seconds"), bool(p.get("photoreal")), preview=preview)
    size = _video_size(ctx.lib.path(img), p.get("quality"))
    adv = _stack_video_loras(p, img)
    use_proof = five_b_profile(profile) and not end
    _preflight_loras(_template_for(use_proof, bool(end), p.get("mode") == "best"), adv)
    clip = {}
    if use_proof:
        out, chained = _video_clip_5b(ctx, ctx.lib.path(img), motion, seconds, size, adv,
                                      label="Motion proof on the 5B model", info=clip)
    else:
        out, chained = _video_clip(ctx, ctx.lib.path(img), motion, seconds, size, p.get("mode") == "best",
                                   end_path=ctx.lib.path(end) if end else None, adv=adv,
                                   label="Animating (A to B)" if end else "Animating", info=clip)
    stages = None
    if p.get("photoreal"):
        ctx.progress(0.9, "Photoreal chain: frame rate")
        out, stages = photoreal.apply_video_chain(out, ctx.tmp, V.ffmpeg_bin(), preview=preview)
    i2v = __import__("model_registry").role("video_i2v")
    sampling = __import__("model_registry").sampling()
    frames = clip["frames"]
    shot_qc.append_shot_log({
        "shot_id": ctx.job["id"], "character_id": img.get("character") or "",
        "still_model": (img.get("provenance") or {}).get("model") or img.get("model") or "",
        "still_seed": img.get("seed") or "", "lora_stack": (video_lora or {}).get("id") or "",
        "wan_variant": checkpoint["id"], "steps": checkpoint.get("steps") or checkpoint.get("high_steps") or "",
        "cfg": checkpoint.get("cfg") or sampling.get("nag_when_cfg") or "",
        "shift": checkpoint.get("shift") or sampling.get("shift_default") or "",
        "frames": frames, "i2v_prompt": motion, "negatives": "nag" if sampling.get("nag_when_cfg") == 1 else "",
        "score_total": "", "worst_axis": gate["worst_axis"],
        "notes": ("unscored proof (D-C-28): no keyframe scores, proof only" if unscored else
                  "still gate passed; fail-fast is due at 0:02") + ("; chain the rest" if chained else ""),
    })
    meta = _meta_from(img)
    if unscored:
        meta.update(proof=True, qc_status=UNSCORED_PROOF)
    ctx.add(out, "video", prompt=motion, model=FIVE_B_MODEL if use_proof else i2v["label"] + (" FLF2V" if end else " I2V"),
            dna=img.get("dna"),
            stated_age=(img.get("dna") or {}).get("age") or img.get("stated_age"),
            provenance={"chain": stages, "look": look, "still_look": (img.get("provenance") or {}).get("look"),
                        "loras": [{"name": f, "strength": s_} for f, s_ in (adv.get("loras") or [])],
                        "keyframe": img.get("id"), "photoreal": bool(p.get("photoreal")),
                        "seconds": seconds, "lengths": "fixed" if p.get("photoreal") else "free",
                        "qc": gate, "plan": plan, "checkpoint": checkpoint["id"],
                        "video_lora": None if video_lora is None else video_lora["id"],
                        "frames": frames, "chained": chained, "fps": clip["fps"], "seed": clip["seed"],
                        "workflow": clip["workflow"], "model": clip["model"],
                        "machine": profile.get("id"),
                        "video_proof": "wan22_ti2v_5b" if use_proof else "wan22_14b_i2v",
                        "clean_pass_steps": sampling.get("clean_pass_steps"),
                        "proofer": sampling.get("proofer") if p.get("proof") else None},
            **meta)


MAX_EXTEND_PARTS = 6


def _plain_instruction(s):
    """The words of one part (catalogue motion and/or free text), checked as typed, with no hint and no lock."""
    return _motion_text(s, hint=False)


def job_extend(ctx, p):
    """Add one or more parts after an existing video. Each part is an instruction in plain words; each starts from
    the previous last frame, is composed into the model's prompt (same person and place, realism lock), and the
    clips are joined with a colour match at every join."""
    require_checker_on()
    try:
        vid = ctx.lib.get(p.get("video"))
    except (KeyError, PermissionError) as e:
        raise UserError(str(e))
    if vid["type"] != "video" or vid.get("role") not in PERSON_ROLES:
        raise UserError("Pick a video Easy Studio made.")
    if vid.get("age_flag"):
        raise UserError("The automatic age check flagged that video, so it can't be extended.")
    segs = p.get("segments") or [{"motion": p.get("motion"), "text": p.get("text"), "seconds": p.get("seconds")}]
    segs = [s for s in segs if isinstance(s, dict)]
    if not segs:
        raise UserError("Describe at least one part to add.")
    if len(segs) > MAX_EXTEND_PARTS:
        raise UserError(f"One request can add at most {MAX_EXTEND_PARTS} parts. Send the rest as a second request.")
    loop = bool(p.get("loop"))
    profile = machine_profiles.active()
    five_b = five_b_profile(profile)
    engine = str(p.get("engine") or p.get("provider") or "local").strip() or "local"
    remote = engine.lower() != "local"
    if (five_b or remote) and (loop or any(s.get("end_image") for s in segs)):
        raise UserError(FIVE_B_EXTEND_LIMIT if five_b else "A hosted model adds parts from the last picture only.")
    # everything that can be refused is refused here, before a frame is cut or a model runs
    instructions = [_plain_instruction(s) for s in segs]
    prev_text, prev_seed, prev_look = EC.previous_of(vid)
    look = _video_look(p if p.get("look") or not prev_look else dict(p, look=prev_look))
    adv = _stack_video_loras(p, vid)
    best = p.get("mode") == "best"
    provider = None
    if remote:
        provider = EC.get_provider(engine)
        if provider is None or getattr(provider, "kind", "") != "video":
            raise UserError(f"'{engine}' is not a video provider this app knows.")
        if not provider.configured():
            raise UserError(f"{engine} has no key yet. Add it in Setup, or use the local engine.")
        why = EC.provider_refusal(p, area(), vid, EC.likeness_marked(vid, _lineage_get(ctx)), adv.get("loras"))
        if why:
            raise UserError(why)
        # the providers' own guard, the same one the Video (API) job uses: area, switch, marks, LoRAs, the picture's age check
        # and ancestry. Run here before any frame is cut, and again for every frame just before it is sent.
        from providers import Refused as _Refused, guard as _PG
        lib_root = getattr(getattr(ctx.lib, "lib", ctx.lib), "root", None)
        try:
            _PG.check_call(media=True)
            _PG.check_params_marks(p)
            _PG.check_loras(adv)
            _PG.check_picture(vid, _lineage_get(ctx), lib_root)
        except _Refused as e:
            raise UserError(str(e)) from None
    else:
        _preflight_loras(_template_for(five_b, False, best), adv)
        if not five_b and (loop or any(s.get("end_image") for s in segs)):
            _preflight_loras(_template_for(False, True, best), adv)
    likeness = EC.likeness_marked(vid, _lineage_get(ctx))
    ctx.steps(len(segs) + 1)
    first_frame = os.path.join(ctx.tmp, "first.png")
    V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", ctx.lib.path(vid), "-frames:v", "1", first_frame])
    clips = [ctx.lib.path(vid)]
    prev = clips[0]
    seed = adv.get("seed") or prev_seed
    added, colour = [], []
    for i, s in enumerate(segs):
        words = instructions[i]
        # the text provider may polish the words on this machine's behalf; a hosted video engine gets the plain composition
        image_part = bool(p.get("image") or any(x.get("end_image") for x in segs))
        polished = None if remote else EC.polish(words, area(), likeness, p, _txt, has_image=image_part)
        instruction = polished or words
        composed = EC.compose(instruction, prev_text)
        _txt(composed)
        motion = safety.add_adult_hint(composed)
        lf = V.last_frame(prev, os.path.join(ctx.tmp, f"last_{i}.png"))
        end = None
        if s.get("end_image"):
            end = ctx.lib.path(_person(ctx, s, "end_image"))
        if loop and i == len(segs) - 1:
            end = first_frame
        info = V.probe(prev)
        seconds = photoreal.snap_seconds(s.get("seconds"), bool(p.get("photoreal")))
        size = (info["width"] // 16 * 16, info["height"] // 16 * 16)
        label = f"Extension {i + 1} of {len(segs)}"
        made = {}
        seg_adv = dict(adv, seed=int(seed)) if seed else dict(adv)
        if remote:  # the engine the request named: its own model, from the last picture
            ctx.progress(0, f"{label} on {engine} ...")
            try:
                _PG.clear_frame(vid, _lineage_get(ctx), lib_root, lf)  # this frame, once, from a clip that passed
                got = EC.run_provider_clip(provider, motion, lf, seconds, p.get("model"), folder=ctx.tmp)
            except _Refused as e:
                raise UserError(str(e)) from None
            import age_guard
            hosted_check = age_guard.check_video(AGE_GUARD, got, ctx.tmp, V.ffmpeg_bin())  # nothing comes back unchecked
            if hosted_check.get("status") != "ok":
                os.remove(got)
                raise UserError("The age check did not clear the clip that came back, so it was deleted and nothing was kept. You can try again.")
            clip = os.path.join(ctx.tmp, f"remote_{i}.mp4")
            shutil.copyfile(got, clip)
            one = V.probe(clip)
            made.update(workflow=None, model=f"{engine} (hosted)", frames=one["frames"], fps=one["fps"], seed=None)
        elif five_b:  # the Mac: the 5B model from the last frame, then an ffmpeg join
            clip, _chained = _video_clip_5b(ctx, lf, motion, seconds, size, seg_adv, label=label, info=made)
        else:
            clip, _chained = _video_clip(ctx, lf, motion, seconds, size, best, end_path=end, adv=seg_adv, label=label,
                                         info=made)
        made.update(seconds=seconds, instruction=instruction, prompt=motion)
        clip, rec = EC.match_colour(prev, clip, ctx.tmp, i + 1)
        colour.append(rec)
        clips.append(clip)
        added.append(made)
        prev, prev_text, seed = clip, EC.clean_previous(instruction), made.get("seed") or seed
        ctx.next_step()
    ctx.progress(0, "Joining the clips")
    out = os.path.join(ctx.tmp, f"extended_{ctx.job['id']}.mp4")
    joins = join_points(clips)
    for point, rec in zip(joins, colour):
        point.update(colour_gain=rec["gain_rgb"], colour_matched=rec["applied"])
    V.stitch(clips, out)
    if loop:  # the very last frame equals the first: drop it so the loop doesn't stutter
        n = V.probe(out)["frames"]
        trimmed = out.replace(".mp4", "_loop.mp4")
        V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", out, "-vf", f"trim=end_frame={max(1, n - 1)},setpts=PTS-STARTPTS",
                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", trimmed])
        out = trimmed
    stages = None
    if p.get("photoreal"):
        ctx.progress(0.95, "Photoreal chain: frame rate")
        out, stages = photoreal.apply_video_chain(out, ctx.tmp, V.ffmpeg_bin(), preview=bool(p.get("preview")))
    model = added[0]["model"] if added else (FIVE_B_MODEL if five_b else __import__("model_registry").role("video_i2v")["label"])
    extra = {"remote": True} if remote else {}
    ctx.add(out, "video:extend", prompt=" | ".join(a["instruction"] for a in added),
            model=model, loop=loop,
            provenance={"chain": stages, "photoreal": bool(p.get("photoreal")), "source": vid["id"],
                        "machine": profile.get("id"), "look": look, "engine": engine if remote else "local",
                        "video_proof": "hosted" if remote else ("wan22_ti2v_5b" if five_b else "wan22_14b_i2v"),
                        "workflow": added[0]["workflow"] if added else None, "model": model,
                        "loras": [{"name": f, "strength": s_} for f, s_ in (adv.get("loras") or [])],
                        "continuity": {"from": vid["id"], "previous": EC.previous_of(vid)[0], "seed": adv.get("seed") or EC.previous_of(vid)[1]},
                        "segments": [{k: one.get(k) for k in ("workflow", "seconds", "frames", "fps", "seed", "instruction", "prompt")}
                                     for one in added],
                        "join_points": joins, "colour_match": colour,
                        "join": "last frame of each clip starts the next; each is colour-matched to the one before; ffmpeg joins them"},
            **extra, **_meta_from(vid))


def join_points(clips):
    """Where each added clip starts in the joined video.

    V.stitch drops the first frame of every added clip (it repeats the last frame before it)
    and plays the result at the first clip's frame rate.
    """
    points, at = [], 0.0
    fps0 = None
    for i, path in enumerate(clips):
        info = V.probe(path)
        fps = info["fps"] or presets.WAN_FPS
        fps0 = fps0 or fps
        frames = int(info["frames"] or 0)
        if i:
            points.append({"clip": i, "seconds": round(at, 3), "frame": int(round(at * fps0))})
            frames = max(0, frames - 1)
        at += frames / fps
    return points


# ---------------------------------------------------------------------------
# 5. 3D
# ---------------------------------------------------------------------------
QUALITY_3D = {"game": (50000, 1024, 1024), "standard": (200000, 1024, 2048), "max": (700000, 1536, 2048)}
MODEL3D_ENGINES = {
    "trellis": {"workflow": "3d_trellis2_api.json", "model": "TRELLIS.2"},
    "hunyuan": {"workflow": "3d_hunyuan21_shape_api.json", "model": "Hunyuan3D 2.1 (shape)"},
}


def model3d_engine(p=None, profile=None):
    """The request's engine, else the machine profile's: hunyuan on the Mac (TRELLIS.2 needs CUDA), trellis on the server."""
    profile = machine_profiles.active() if profile is None else profile
    engine = (p or {}).get("engine") or profile.get("model3d_engine") or "trellis"
    if engine not in MODEL3D_ENGINES:
        raise UserError("Pick a 3D engine: trellis or hunyuan.")
    return engine


def job_model3d(ctx, p):
    img = _person(ctx, p) if p.get("image") else None
    if img is None:
        raise UserError("Pick a picture first.")
    profile = machine_profiles.active()
    engine = model3d_engine(p, profile)
    spec = MODEL3D_ENGINES[engine]
    wf = cc.load_workflow(spec["workflow"])
    if engine == "trellis":
        faces, detail, tex = QUALITY_3D.get(p.get("quality") or "standard", QUALITY_3D["standard"])
        cc.set_in(wf, "FACES", target_face_count=faces)
        cc.set_in(wf, "DETAIL", target_resolution=detail)
        cc.set_in(wf, "TEXTURE SIZE", texture_size=tex)
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(img))
    adv = _adv(p)
    seed = adv.get("seed") or _rand_seed()
    cc.set_seed(wf, seed)
    res = ctx.run(wf, "Building the 3D model (about a minute)")
    outs = [x for x in first(res) if x.lower().endswith(".glb")]
    if not outs:
        raise UserError("ComfyUI finished but returned no 3D file.")
    try:  # N05: a file is saved only when it is a well-formed binary glTF with a real mesh in it
        mesh = mesh_check.glb_stats(outs[0])
    except ValueError as e:
        raise UserError(f"ComfyUI returned a 3D file that is not a valid .glb ({e}), so it was not saved.")
    ctx.add(outs[0], "model3d", model=spec["model"], quality=p.get("quality") or "standard",
            provenance={"engine": engine, "workflow": spec["workflow"], "model": spec["model"],
                        "machine": profile.get("id"), "seed": seed, "keyframe": img.get("id"),
                        "quality": (p.get("quality") or "standard") if engine == "trellis" else None,
                        "mesh": mesh},
            **_meta_from(img))


# ---------------------------------------------------------------------------
# 6. Sets: photoshoot, turnaround, expressions, sprites, export
# ---------------------------------------------------------------------------
def _hero(ctx, ch):
    if not ch.get("hero"):
        raise UserError("This character has no portrait yet. Open it in the Creator and pick a favourite picture.")
    try:
        return ctx.lib.person_image(ch["hero"])
    except (KeyError, PermissionError, ValueError) as e:
        raise UserError(str(e))


def job_photoshoot(ctx, p):
    ch = _character(ctx, p)
    if not ch:
        raise UserError("Pick a saved character first.")
    hero = _hero(ctx, ch)
    pack = next((x for x in catalog.all_shoot_packs() if x["id"] == p.get("pack")), None)
    if not pack:
        raise UserError("Pick a photoshoot pack.")
    project = p.get("project") or f"{ch['name']} - {pack['label']}"
    ctx.job["params"]["project"] = project
    ctx.steps(len(pack["shots"]))
    seed0 = _rand_seed()
    for i, (scene, light, cam, pose, outfit) in enumerate(pack["shots"]):
        bits = []
        if outfit:
            bits.append("wearing " + catalog.outfit_item(outfit)["p"])
        bits.append("in " + catalog.find(catalog.SCENES, scene)["p"])
        bits.append(catalog.find(catalog.LIGHTING, light)["p"])
        bits.append("framed as a " + catalog.find(catalog.CAMERAS, cam)["p"])
        instr = "Photograph the same person " + ", ".join(bits) + "."
        image2 = None
        if pose:
            instr += " The person takes exactly the pose of the stick figure in image 2."
            image2 = os.path.join(POSE_DIR, pose + ".png")
        instr += " " + KEEP
        out, full = qwen_edit(ctx, hero, instr, image2=image2, seed=seed0 + i, label=f"Shot {i + 1} of {len(pack['shots'])}")
        ctx.add(out, "photoshoot", prompt=full, model="Qwen-Image-Edit-2511", parent=hero["id"], character=ch["id"],
                style=ch.get("style"), project=project, **proof_mark(hero, _lineage_get(ctx)))
        ctx.next_step()


def job_turnaround(ctx, p):
    img = _person(ctx, p)
    ctx.steps(len(catalog.TURNAROUND) + 1)
    paths, labels = [], []
    seed = _rand_seed()
    for i, (lab, words) in enumerate(catalog.TURNAROUND):
        if lab == "front" and p.get("keep_front", True):
            paths.append(ctx.lib.path(img))
        else:
            out, _ = qwen_edit(ctx, img, words, angles=True, seed=seed, label=f"View: {lab}")
            it = ctx.add(out, "turnaround:" + lab, model="Qwen edit + Multiple-Angles LoRA", **_meta_from(img))
            paths.append(ctx.lib.path(it))
        labels.append(lab.upper())
        ctx.next_step()
    sheet = os.path.join(ctx.tmp, f"turnaround_{ctx.job['id']}.png")
    assets.sheet(paths, labels, sheet, cols=len(paths))
    ctx.add(sheet, "sheet:turnaround", **_meta_from(img))


def job_expressions(ctx, p):
    img = _person(ctx, p)
    ids = [e for e in (p.get("expressions") or [x["id"] for x in catalog.EXPRESSIONS])
           if catalog.find(catalog.EXPRESSIONS, e)][:8]
    ctx.steps(len(ids) + 1)
    paths = []
    seed = _rand_seed()
    for e in ids:
        instr = build_instruction(ctx, {"op": "expression", "expression": e}, False)
        out, _ = qwen_edit(ctx, img, instr, seed=seed, label=f"Expression: {e}")
        it = ctx.add(out, "expression:" + e, model="Qwen-Image-Edit-2511", **_meta_from(img))
        paths.append(ctx.lib.path(it))
        ctx.next_step()
    sheet = os.path.join(ctx.tmp, f"expressions_{ctx.job['id']}.png")
    assets.sheet(paths, [catalog.find(catalog.EXPRESSIONS, e)["label"] for e in ids], sheet, cols=4, cell_h=512)
    ctx.add(sheet, "sheet:expressions", **_meta_from(img))


def job_sprites(ctx, p):
    try:
        vid = ctx.lib.get(p.get("video"))
    except (KeyError, PermissionError) as e:
        raise UserError(str(e))
    if vid["type"] != "video":
        raise UserError("Pick a video.")
    if vid.get("age_flag"):
        raise UserError("The automatic age check flagged that video, so it can't be used.")
    n = max(2, min(64, int(p.get("frames") or 16)))
    cols = max(1, min(16, int(p.get("columns") or 8)))
    info = V.probe(ctx.lib.path(vid))
    total = max(1, info["frames"])
    fdir = os.path.join(ctx.tmp, "frames")
    os.makedirs(fdir, exist_ok=True)
    step = max(1, total // n)
    V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", ctx.lib.path(vid), "-vf",
            f"select='not(mod(n\\,{step}))'", "-fps_mode", "vfr", "-frames:v", str(n), os.path.join(fdir, "f_%03d.png")])
    frames = sorted(os.path.join(fdir, f) for f in os.listdir(fdir))
    if not frames:
        raise UserError("Couldn't read frames from that video.")
    if p.get("remove_bg"):
        ctx.steps(len(frames) + 1)
        cut = []
        for i, f in enumerate(frames):
            wf = cc.load_workflow("remove_bg_api.json")
            cc.set_in(wf, "IMAGE 1", image=ctx.upload_path(f, f"es_frame_{ctx.job['id']}_{i:03d}.png"))
            res = ctx.run(wf, f"Cutting out frame {i + 1}/{len(frames)}")
            cut.append(first(res, wf, "CUTOUT")[0])
            ctx.next_step()
        frames = cut
    png = os.path.join(ctx.tmp, f"sprites_{ctx.job['id']}.png")
    js = os.path.join(ctx.tmp, f"sprites_{ctx.job['id']}.json")
    assets.sprite_sheet(frames, png, js, cols=cols)
    it = ctx.add(png, "sheet:sprites", **_meta_from(vid))
    ctx.add(js, "sheet:sprites_atlas", parent=it["id"], character=vid.get("character"))


def job_export(ctx, p):
    require_checker_on()
    ch = _character(ctx, p)
    if not ch:
        raise UserError("Pick a saved character first.")
    import age_guard
    items = [i for i in ctx.lib.list(character=ch["id"], limit=5000)
             if (i.get("favourite") or i["kind"].startswith(("sheet", "model3d")) or i["id"] == ch.get("hero"))
             and not age_guard.saved_blocked(i)]
    pairs = []
    dna_path = os.path.join(ctx.tmp, "character.json")
    with open(dna_path, "w") as f:
        json.dump(ch, f, indent=2)
    pairs.append((dna_path, "character.json"))
    folder = {"image": "images", "video": "videos", "model": "3d", "file": "data"}
    for it in items:
        sub = "sheets" if it["kind"].startswith("sheet") else folder.get(it["type"], "other")
        pairs.append((ctx.lib.path(it), f"{sub}/{os.path.basename(it['file'])}"))
    readme = os.path.join(ctx.tmp, "README.txt")
    with open(readme, "w") as f:
        f.write(f"Easy Studio export: {ch['name']}\nFictional adult character. Not a real person.\n\n"
                "images/  favourite pictures (PNG)\nsheets/  turnaround / expression / sprite sheets (+ .json atlas)\n"
                "3d/      .glb models: Blender > File > Import > glTF 2.0; Unity/Godot: drag the .glb in\n"
                "videos/  MP4 clips\ncharacter.json  the character's settings (import it back into Easy Studio)\n")
    pairs.append((readme, "README.txt"))
    safe = "".join(c if c.isalnum() else "_" for c in ch["name"])[:40] or "character"
    out = os.path.join(ctx.tmp, f"{safe}_export.zip")
    assets.zip_files(pairs, out)
    ctx.add(out, "export", character=ch["id"])


def _raw_text(wf):
    found = []
    stack = [wf]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            found.append(item)
    return found


def job_raw(ctx, p):
    wf = p.get("workflow")
    if isinstance(wf, str):
        try:
            wf = json.loads(wf)
        except ValueError:
            raise UserError("That text isn't valid JSON.")
    ok, msg = safety.check_workflow(wf)
    if not ok:
        raise UserError(msg)
    bound = []
    loaded = []
    person_nodes = [n for n in wf.values() if isinstance(n, dict) and n.get("class_type") in
                    ("LoadImage", "LoadImageOutput", "LoadVideo", "CLIPTextEncode", "TextEncodeQwenImageEditPlus")]
    for nid, node in wf.items():  # pictures it loads must be ones the server uploaded for Easy Studio
        if node.get("class_type") in ("LoadImage", "LoadImageMask", "LoadImageOutput", "LoadVideo"):
            img = node.get("inputs", {}).get("image") or node.get("inputs", {}).get("file")
            if isinstance(img, str) and not (img.startswith("es_")):
                raise UserError(f"Node {nid} loads '{img}'. In raw mode, pictures must come from the gallery: "
                                "use the 'Insert gallery picture' button (it puts es_<id>.png names in).")
            if isinstance(img, str):
                iid = img[3:].split(".")[0]
                try:
                    if node["class_type"] == "LoadImageMask":
                        mask_item = ctx.lib.get(iid)
                        loaded.append(mask_item)
                        ctx.upload_item(mask_item)
                    else:
                        it = _person(ctx, {"image": iid})
                        loaded.append(it)
                        ctx.upload_item(it)
                        if isinstance(it.get("dna"), dict):
                            bound.append(it["dna"])
                except (KeyError, PermissionError, ValueError) as e:
                    raise UserError(str(e))
    texts = _raw_text(wf)
    for it in loaded:  # the upload-ancestry walk covers every picture a raw graph loads
        _refuse_uploaded_undress(it, *texts, ctx=ctx)
    for text in texts:
        ok, msg = safety.reconcile_prompt_ages(text, bound)
        if not ok:
            raise UserError(msg)
    if not bound and person_nodes and any(n.get("class_type") != "LoadImageMask" for n in person_nodes):
        raise UserError("This raw workflow is unavailable without an explicit per-person age record.")
    res = ctx.run(copy.deepcopy(wf), "Running your workflow")
    for path in first(res):
        ctx.add(path, "raw", model="raw workflow", dna=bound[0] if bound else None)


def job_contact_repair(ctx, p):
    """Inpaint the contact area on a still. Does not start a video."""
    if area() != "adult":
        raise UserError("Contact repair is only in the 18+ section.")
    img = _person(ctx, p)
    text = str(p.get("text") or "clear separation at the contact, two distinct bodies")[:500]
    _txt(text)
    with Image.open(ctx.lib.path(img)) as im:
        w, h = im.size
    mask = shot_qc.contact_mask_box(w, h)
    mask_path = os.path.join(ctx.tmp, "contact_mask.png")
    mask.save(mask_path)
    wf = cc.load_workflow("inpaint_chroma1hd_api.json")
    prompt = safety.add_adult_hint(text + ". " + shot_qc.contact_clause())
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(img))
    cc.set_in(wf, "MASK", image=ctx.upload_path(mask_path, f"es_mask_{ctx.job['id']}.png"))
    cc.set_in(wf, "POSITIVE", text=prompt)
    cc.set_in(wf, "NEGATIVE", text=_safe_neg(""))
    cc.set_in(wf, "MASK GROW", expand=8)
    adv = _adv(p)
    cc.apply_advanced(wf, adv)
    if not adv.get("seed"):
        cc.set_seed(wf, _rand_seed())
    res = ctx.run(wf, "Repairing the contact in the still")
    for path in first(res):
        ctx.add(path, "edit:contact", prompt=prompt, model="Chroma1-HD",
                provenance={"repair": "contact", "preset": "contact_explicit"}, **_meta_from(img))


def job_regenerate(ctx, p):
    """A new picture of a saved character. Same description, new seed. Outfit edits stay separate."""
    ch = _character(ctx, p)
    if not ch:
        raise UserError("Pick a saved character first.")
    try:
        seed = int(p.get("seed") or 0) or _rand_seed()
    except (TypeError, ValueError):
        raise UserError("Seed must be a number.")
    job_create(ctx, {
        "dna": ch, "count": 1, "seed": seed, "look": p.get("look"),
        "character_id": ch["id"], "regenerate": True,
        "camera": p.get("camera") or "half", "outfit": p.get("outfit"),
        "extra_scene": p.get("extra_scene") or "",
    })


def job_video_still(ctx, p):
    """Save one frame of a video Easy Studio made. Age-flagged clips are refused."""
    require_checker_on()
    try:
        vid = ctx.lib.get(p.get("video"))
    except (KeyError, PermissionError) as e:
        raise UserError(str(e))
    if vid["type"] != "video":
        raise UserError("Pick a video.")
    if vid.get("age_flag"):
        raise UserError("The automatic age check flagged that video, so a still can't be saved from it.")
    which = str(p.get("frame") or "last")
    if which not in ("first", "middle", "last"):
        raise UserError("Pick the first, middle, or last frame.")
    src = ctx.lib.path(vid)
    out = os.path.join(ctx.tmp, f"still_{ctx.job['id']}.png")
    if which == "last":
        V.last_frame(src, out)
    elif which == "first":
        V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", src, "-frames:v", "1", out])
    else:
        info = V.probe(src)
        V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{max(0.0, info['duration'] / 2.0):.3f}",
                "-i", src, "-frames:v", "1", out])
    ctx.add(out, "still:video", model="frame grab",
            provenance={"source_video": vid["id"], "frame": which}, **_meta_from(vid))


def job_outfit_locked(ctx, p):
    """Change clothes only. Face, hands and the background stay outside the mask."""
    img = _person(ctx, p)
    text = str(p.get("text") or "")[:500]
    if p.get("item"):
        it = catalog.outfit_item(p.get("item"))
        if it:
            text = (it["p"] + (", " + text if text else ""))
    if not text:
        raise UserError("Pick an outfit or describe the clothes.")
    _refuse_uploaded_undress(img, text, p.get("item"), ctx=ctx)
    _txt("wearing " + text)
    source_id = outfit_contract.approved_source_id(img)
    source = img if source_id == img["id"] else _person(ctx, {"image": source_id})
    supplied = p.get("body_card") if isinstance(p.get("body_card"), dict) else None
    source_dna = img.get("dna") if isinstance(img.get("dna"), dict) else None
    if source_dna is None and isinstance(source.get("dna"), dict):
        source_dna = source["dna"]
    if source_dna is None:
        for owner in (source, img):
            if owner.get("character"):
                try:
                    source_dna = ctx.chars.get(owner["character"])
                    break
                except Exception:
                    source_dna = None
    if supplied is not None:
        record = supplied if any(k in supplied for k in ("age", "stated_age", "age_years")) else {"age": supplied.get("stated_age")}
        _require_person_ages(record)
        card = supplied
    elif not isinstance(source_dna, dict):
        raise UserError("Missing stated age: age is missing. This picture has no character record.")
    else:
        _require_person_ages(source_dna)
        try:
            card = photoreal.body_card(source_dna)
        except photoreal.PhotorealError as e:
            raise UserError(str(e))
    if card.get("real_person"):
        raise UserError("This outfit edit is for fictional characters. The Me slot is not built.")
    spec = None
    if source.get("character"):
        try:
            spec = ctx.chars.get(source["character"]).get("spec_version")
        except Exception:
            spec = None
    with Image.open(ctx.lib.path(source)) as im:
        w, h = im.size
    mask = photoreal.clothing_mask(w, h)
    mask_path = os.path.join(ctx.tmp, "outfit_mask.png")
    mask.save(mask_path)
    wf = cc.load_workflow("inpaint_zimage_outfit_api.json")
    prompt = safety.add_adult_hint("wearing " + text + ", " + photoreal.SKIN_WORDS + ". Keep the same face, hands and background.")
    _txt(prompt)
    cc.set_in(wf, "IMAGE 1", image=ctx.upload_item(source))
    cc.set_in(wf, "MASK", image=ctx.upload_path(mask_path, f"es_mask_{ctx.job['id']}.png"))
    cc.set_in(wf, "POSITIVE", text=prompt)
    cc.set_in(wf, "NEGATIVE", text=_safe_neg(""))
    adv = _stack_video_loras(p, img)
    cc.apply_advanced(wf, adv)
    if not adv.get("seed"):
        cc.set_seed(wf, _rand_seed())
    res = ctx.run(wf, "Changing the clothes, keeping the body")
    for path in first(res):
        merged = os.path.join(ctx.tmp, "outfit_composite.png")
        checks = outfit_contract.composite_unmasked(ctx.lib.path(source), path, mask, merged)
        ctx.add(merged, "edit:outfit_locked", prompt=prompt, model="Z-Image Turbo",
                provenance={"body_card": card, "protected": card["protected"], "mask": "clothing_and_revealed_skin",
                            "approved_source": source_id, "outfit_contract": 1, "spec_version": spec,
                            "checks": {"identity": checks["identity"], "garment": text,
                                       "unchanged_region": checks["unchanged_region"]}},
                **_meta_from(source))


JOBS = {"create": job_create, "edit": job_edit, "inpaint": job_inpaint, "outfit_locked": job_outfit_locked,
        "contact_repair": job_contact_repair,
        "regenerate": job_regenerate, "video_still": job_video_still,
        "remove_bg": job_remove_bg,
        "bg_quick": job_bg_quick, "upscale": job_upscale, "pose_extract": job_pose_extract, "pose_new": job_pose_new,
        "video": job_video, "extend": job_extend, "model3d": job_model3d, "photoshoot": job_photoshoot,
        "turnaround": job_turnaround, "expressions": job_expressions, "sprites": job_sprites, "export": job_export,
        "raw": job_raw}
