"""Easy Studio 3 tools: Video studio (any model / your own workflow), Train my character, Godot export.
Registers its jobs in pipelines.JOBS."""
import json
import os
import re
import shutil
import time

from PIL import Image

import age_guard
import assets
import catalog
import comfy_client as cc
import pipelines as P
import shot_qc
import presets
import safety
import trainer as T
import video_tools as V
import videomodels as VM
import wfdetect as D
from library import PERSON_ROLES
from pipelines import UserError, _txt, _safe_neg, _adv, _person, _character, _hero, _rand_seed, first, _refuse_uploaded_undress

BYO_DIR = None  # set by the server: outputs/byo
COMFY_DIR = None
ROOT = None


# ---------------------------------------------------------------------------
# Bring-your-own workflows
# ---------------------------------------------------------------------------
def check_byo(wf, object_info=None):
    """All the safety rules for an imported workflow. Returns the analysis or raises UserError."""
    ok, msg = safety.check_workflow(wf)
    if not ok:
        raise UserError(msg)
    for nid, n in wf.items():
        ct = n["class_type"]
        if object_info is not None:
            info = object_info.get(ct)
            if info is None:
                raise UserError(f"This workflow uses '{ct}', which your ComfyUI doesn't have. Install that custom node first.")
            if info.get("api_node"):
                raise UserError(f"'{ct}' sends your pictures to an online paid service. Easy Studio only runs workflows "
                                "on your own PC, so it can't use this node.")
        if ct in D.OTHER_FILE_LOADERS:
            raise UserError(f"Node {nid} ('{ct}') loads a file from the PC. Imported workflows can only load the start / "
                            "end pictures Easy Studio gives them.")
    a = D.analyse(wf)
    if not a["prompt"]:
        raise UserError("Easy Studio couldn't find the prompt box in this workflow.")
    if a["output_type"] != "video":
        raise UserError("This workflow doesn't save a video (it needs a Save Video / Video Combine node).")
    if any(i["role"] == "extra" for i in a["images"]):
        raise UserError("This workflow loads more than two pictures. Easy Studio can fill a start and an end picture only.")
    return a


def byo_list():
    out = []
    if BYO_DIR and os.path.isdir(BYO_DIR):
        for f in sorted(os.listdir(BYO_DIR)):
            if f.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(BYO_DIR, f)))
                    out.append({k: d.get(k) for k in ("id", "name", "mode", "summary", "created", "fps", "rule")})
                except Exception:
                    pass
    return out


def byo_get(bid):
    if not re.fullmatch(r"[a-f0-9]{6,32}", str(bid or "")):
        raise UserError("Unknown imported workflow.")
    p = os.path.join(BYO_DIR, bid + ".json")
    if not os.path.exists(p):
        raise UserError("That imported workflow was deleted.")
    return json.load(open(p))


# ---------------------------------------------------------------------------
# Video studio: one job for every model
# ---------------------------------------------------------------------------
def _pick_model(p):
    mid = str(p.get("model") or "wan22_i2v")
    if mid.startswith("byo:"):
        d = byo_get(mid[4:])
        return {"id": mid, "label": d["name"], "family": "your workflow", "mode": d["mode"], "fps": d.get("fps") or 16,
                "rule": d.get("rule") or 4, "base": (832, 480), "hi": (1280, 720), "max_s": 10, "byo": d}
    m = VM.BY_ID.get(mid)
    if not m:
        raise UserError("Pick a video model.")
    return m


def _model_workflow(ctx, m, quality):
    if m.get("byo"):
        wf = m["byo"]["workflow"]
        a = check_byo(wf, ctx.comfy.object_info() if hasattr(ctx.comfy, "object_info") else None)
        return wf, a
    wf = VM.load(VM.workflow_file(m, quality))
    return wf, D.analyse(wf)


def make_clip(ctx, m, quality, prompt, seconds, start=None, end=None, aspect=None, size=None, seed=None, adv=None,
              label="Making the video"):
    wf, a = _model_workflow(ctx, m, quality)
    need = {"t2v": 0, "i2v": 1, "flf2v": 2}[a["mode"]]
    if need >= 1 and not start:
        raise UserError(f"{m['label']} needs a start picture.")
    if need == 2 and not end:
        raise UserError(f"{m['label']} needs a start AND an end picture.")
    if need == 0 and start:
        raise UserError(f"{m['label']} makes video from words only. Pick a 'picture to video' model to use a picture.")
    imgs = {}
    if start:
        imgs["start"] = ctx.upload_path(start, f"es_start_{abs(hash(start)) % 10**8}.png")
    if end and need == 2:
        imgs["end"] = ctx.upload_path(end, f"es_end_{abs(hash(end)) % 10**8}.png")
    if size is None:
        isz = None
        if start:
            with Image.open(start) as im:
                isz = im.size
        size = VM.size_for(m, isz, quality, aspect) if not m.get("byo") else presets.size_for_aspect(
            *(isz or {"wide": (16, 9), "tall": (9, 16), "square": (1, 1)}.get(aspect or "wide", (16, 9))),
            1280 * 720 if quality == "best" else 832 * 480)
    seconds = max(1.0, min(float(m.get("max_s") or 10), float(seconds)))
    while presets.frames_for_seconds(seconds) > shot_qc.max_frames() and seconds > 1:
        seconds -= 0.25
    if m.get("rule") == 8 or m["family"].startswith("LTX"):
        seconds = max(1, round(seconds))
    neg = _safe_neg(presets.VIDEO_NEGATIVE)
    adv = adv or {}
    seed = int(adv.get("seed") or seed or _rand_seed())
    wf = D.fill(wf, a, prompt=prompt, negative=neg if a["negative"] else None, images=imgs, seed=seed, seconds=seconds,
                width=size[0], height=size[1], fast=(quality != "best"), frame_rule=m.get("rule", 4))
    if not a["negative"]:
        P._txt(prompt)
    cc.inject_loras(wf, adv.get("loras"))
    res = ctx.run(wf, label)
    outs = [x for x in first(res) if x.lower().endswith((".mp4", ".webm", ".mov", ".webp"))]
    if not outs:
        raise UserError("ComfyUI finished but returned no video.")
    return outs[0], seed


def _motion(p):
    mlist = catalog.MOTIONS + (catalog.ADULT_MOTIONS if P.area() == "adult" else [])
    mo = catalog.find(mlist, p.get("motion")) if p.get("motion") else None
    free = str(p.get("text") or "")[:800]
    t = ", ".join(x for x in [mo["p"] if mo else "", free] if x)
    if not t:
        raise UserError("Describe what happens in the video (or pick a motion).")
    t = safety.add_adult_hint(t)
    _txt(t)
    return t


# Any word that stands for a person. A video made from words alone asks for a stated age when the words carry one of these,
# even when the person counter does not count a person ("she ...", "a girl ...", "two women ..."): over-asking costs one field.
_PERSON_WORD = re.compile(
    r"\b(she|her|hers|herself|he|him|his|himself|they|them|their|woman|women|lady|ladies|girl|girls|man|men|guy|guys|boy|boys|"
    r"person|people|someone|somebody|model|models|couple|dancer|dancers|stranger|friend|friends)\b", re.I)


def words_only_age(p, prompt, src_item=None):
    """The stated age to keep on a clip made from words alone, or None when a picture or a saved character brings the record.

    A person the words introduce needs a stated age of 21 or more, as for any other person; without it the job is refused here,
    and the clip would have no record for the extend job to read. The age is then reconciled with the words the way a Create
    request is: the number of people in the words has to match the one record, and an age written in the words has to match it."""
    if src_item is not None or p.get("character") or p.get("start") or p.get("extend_from"):
        return None
    if safety.people_mentioned(prompt) < 1 and not _PERSON_WORD.search(prompt or ""):
        return None
    ok, age, msg = safety.require_stated_age({"age": p.get("stated_age")})
    if not ok:
        raise UserError(msg)
    records = [{"age": age}]
    for check in (safety.check_group_prompt, safety.reconcile_prompt_ages):
        ok, msg = check(prompt, records)
        if not ok:
            raise UserError(msg)
    return age


def job_video_any(ctx, p):
    P.require_checker_on()
    m = _pick_model(p)
    quality = "best" if p.get("quality") == "best" else "fast"
    prompt = _motion(p)
    look = P._video_look(p)
    prompt = P.EC.lock(prompt)  # the realism lock on every video
    _txt(prompt)
    try:
        adv = _adv(P.EC.with_loras(p, P.LORA_LIB))  # top-level `loras` join the Advanced ones
    except P.EC.ExtendError as e:
        raise UserError(str(e))
    start = end = None
    src_item = None
    if p.get("extend_from"):
        try:
            vid = ctx.lib.get(p["extend_from"])
        except (KeyError, PermissionError) as e:
            raise UserError(str(e))
        if vid["type"] != "video" or vid.get("role") not in PERSON_ROLES or vid.get("age_flag"):
            raise UserError("Pick a video Easy Studio made (and that passed the age check) to continue.")
        src_item = vid
        start = V.last_frame(ctx.lib.path(vid), os.path.join(ctx.tmp, "last.png"))
    elif p.get("start"):
        src_item = _person(ctx, p, "start")
        start = ctx.lib.path(src_item)
    if p.get("end"):
        end = ctx.lib.path(_person(ctx, p, "end"))
    if src_item is not None:
        _refuse_uploaded_undress(src_item, prompt, p.get("text"), p.get("motion"), ctx=ctx)
    _wf, analysis = _model_workflow(ctx, m, quality)
    P._preflight_loras(_wf, adv)  # a LoRA that does not fit this model is refused before anything runs
    need = {"t2v": 0, "i2v": 1, "flf2v": 2}[analysis["mode"]]
    if need == 0 and start:
        raise UserError(f"{m['label']} makes video from words only. Pick a 'picture to video' model to use a picture.")
    if need == 2 and not end:
        raise UserError(f"{m['label']} needs a start AND an end picture.")
    if need >= 1 and src_item is not None and not p.get("extend_from"):
        try:
            P.scored_keyframes(ctx, p, src_item)
            shot_qc.guard_plan(p)
            shot_qc.check_motion_words(prompt)
        except shot_qc.ShotQCError as e:
            raise UserError(str(e))
    seconds = float(p.get("seconds") or 5)
    stated = words_only_age(p, prompt, src_item)
    ctx.steps(2 if src_item and p.get("extend_from") else 1)
    clip, seed = make_clip(ctx, m, quality, prompt, seconds, start=start, end=end, aspect=p.get("aspect"), adv=adv,
                           label=f"{m['label'].split(' -- ')[0]}: making the video")
    meta = {"prompt": prompt, "model": m["label"], "seed": seed,
            "provenance": {"look": look, "seed": seed, "model": m["label"],
                           "loras": [{"name": f, "strength": s_} for f, s_ in (adv.get("loras") or [])]}}
    if src_item:
        meta.update(parent=src_item["id"], character=src_item.get("character"), style=src_item.get("style"),
                    **P.proof_mark(src_item, P._lineage_get(ctx)))
    if p.get("character"):
        meta["character"] = p["character"]
    if stated is not None:
        meta["stated_age"] = stated  # so the clip can be extended later: the extend job reads the age from the clip
    if p.get("extend_from"):
        ctx.next_step("Joining the clips")
        out = os.path.join(ctx.tmp, f"extended_{ctx.job['id']}.mp4")
        V.stitch([ctx.lib.path(src_item), clip], out)
        ctx.add(out, "video:extend", **meta)
    else:
        ctx.add(clip, "video:" + m["mode"], **meta)


# ---------------------------------------------------------------------------
# Train my character
# ---------------------------------------------------------------------------
def _training_character(ctx, p):
    ch = _character(ctx, p)
    if not ch:
        raise UserError("Pick a saved character to train.")
    return ch


def _check_training_source(ctx, it, ch):
    """The deliberate training limit: only pictures of THIS saved character that Easy Studio made, or the user's
    own drawn / 3D-rendered fictional art (role my_character, confirmed with the tick box). Never photos."""
    if it["type"] != "image":
        raise UserError("Only pictures can be used for training.")
    if it.get("role") not in PERSON_ROLES:
        raise UserError("Training can only use pictures Easy Studio made of your character, or your own drawn / 3D "
                        "character art uploaded as 'My fictional character'.")
    if it.get("character") != ch["id"] and it["id"] != ch.get("hero"):
        raise UserError("Every training picture must belong to this character.")
    if it.get("age_flag"):
        raise UserError("A picture flagged by the age check can't be used for training.")
    if P.is_proof(it, P._lineage_get(ctx)):
        raise UserError("A picture from an unscored motion proof can't be used for training.")
    if P.has_remote_ancestor(it, P._lineage_get(ctx)):
        raise UserError("Anything made by a hosted service, or from a frame of its clip, is never trained on.")
    if it.get("role") == "my_character" and not it.get("confirmed"):
        raise UserError("That upload wasn't confirmed as your own fictional character art.")
    return it


def job_train_dataset(ctx, p):
    """Make 12-24 varied pictures of the character from her portrait (angles, framing, expressions, outfits,
    places, light), each with a caption that only names what changes."""
    P.require_checker_on()
    ch = _training_character(ctx, p)
    hero = _hero(ctx, ch)
    _check_training_source(ctx, hero, ch)
    n = max(8, min(len(T.DATASET_SHOTS), int(p.get("count") or 20)))
    shots = T.DATASET_SHOTS[:n] if n == len(T.DATASET_SHOTS) else _spread(T.DATASET_SHOTS, n)
    trigger = T.make_trigger(ch["name"])
    project = f"Training set: {ch['name']}"
    ctx.job["params"]["project"] = project
    ctx.steps(len(shots))
    seed0 = _rand_seed()
    for i, (kind, instr, words) in enumerate(shots):
        out, full = P.qwen_edit(ctx, hero, instr + " " + P.KEEP, seed=seed0 + i, label=f"Training picture {i + 1} of {len(shots)}")
        ctx.add(out, "train:shot", prompt=full, model="Qwen-Image-Edit-2511", parent=hero["id"], character=ch["id"],
                style=ch.get("style"), project=project, caption=T.caption(trigger, ch.get("style"), words), trigger=trigger)
        ctx.next_step()


def _usable(ctx, **kw):
    f = getattr(ctx.lib, "list_usable", None)
    return f(**kw) if f else ctx.lib.list(**kw)


def _spread(lst, n):
    """n items spread over the list so every kind (angle / outfit / scene...) is represented."""
    step = len(lst) / float(n)
    return [lst[int(i * step)] for i in range(n)]


def job_train_lora(ctx, p):
    P.require_checker_on()
    ch = _training_character(ctx, p)
    base = p.get("base") or {"anime": "anime"}.get(ch.get("style"), "photo")
    if base not in T.BASES:
        raise UserError("Pick what the LoRA is for (realistic, fast, anime or video).")
    if not T.installed(ROOT):
        raise UserError("The trainer isn't installed yet. On the PC run install/install_trainer.sh "
                        "(Windows: install_trainer.bat), then try again.")
    if not P.AGE_GUARD.installed():
        raise UserError("Training needs the automatic age check switched on and installed "
                        "(python install/download_models.py --only safety).")
    ids = [str(x) for x in (p.get("items") or [])][:T.MAX_PICTURES]
    if not ids:
        ids = [i["id"] for i in _usable(ctx, character=ch["id"], limit=5000)
               if i["kind"] in ("train:shot",) or i["id"] == ch.get("hero")][:T.MAX_PICTURES]
    items = []
    for iid in dict.fromkeys(ids):
        try:
            it = ctx.lib.get(iid)
        except (KeyError, PermissionError) as e:
            raise UserError(str(e))
        _check_training_source(ctx, it, ch)
        items.append(it)
    if len(items) < T.MIN_PICTURES:
        raise UserError(f"Training needs at least {T.MIN_PICTURES} pictures of the character (you have {len(items)}). "
                        "Press 'Make training pictures' first.")
    trigger = T.make_trigger(ch["name"])
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9]+", "_", ch["name"])[:30].strip("_") or "character"
    name = f"{safe}_{base}_{stamp}"
    job_dir = os.path.join(ctx.lib.root, "training", name)
    ds = os.path.join(job_dir, "dataset")
    os.makedirs(ds, exist_ok=True)
    ctx.steps(10)
    ctx.progress(0, "Checking the training pictures")
    adult = False
    for k, it in enumerate(items):
        src = ctx.lib.path(it)
        if it.get("held") or (it.get("appearance_check") or {}).get("held") or it.get("age_check") in (
                "unchecked", "blocked_age_check_unavailable", "unavailable", "error", "timeout", "off"):
            raise UserError("A held age check cannot be used for training.")
        res = P.AGE_GUARD.check(src)  # re-check right before training, whatever the gallery says
        if res.get("status") == "flag":
            raise UserError("A training picture was flagged by the age check, so training was stopped. Remove it and try again.")
        if age_guard.held_unusable(res) or res.get("status") in (
                "unchecked", "unavailable", "error", "timeout", "blocked_age_check_unavailable", "off"):
            raise UserError("The age check held this picture, so training can't start: " + str(res.get("reason") or res.get("status")))
        dst = os.path.join(ds, f"{k:03d}.png")
        assets.to_png(src, dst) if not src.endswith(".png") else shutil.copyfile(src, dst)
        cap = it.get("caption") or T.caption(trigger, ch.get("style"), "")
        _txt(cap.replace("[trigger]", trigger))
        open(os.path.join(ds, f"{k:03d}.txt"), "w").write(cap)
        adult = adult or (it.get("area") == "adult")
    cfg = T.write_config(job_dir, name, base, trigger, ds, steps=p.get("steps"), rank=p.get("rank"))
    # free the GPU: ComfyUI unloads its models while training runs
    try:
        ctx.comfy.free_memory()
    except Exception:
        pass
    ctx.done = 1

    def prog(frac, msg):
        ctx.progress(frac * 8, msg)
    ok = T.run_training(ROOT, cfg, prog, lambda: bool(ctx.job.get("cancel")), os.path.join(job_dir, "training_log.txt"))
    if not ok:
        raise P.Cancelled()
    try:
        outs = T.find_outputs(job_dir, name)
    except ValueError as exc:
        raise UserError(str(exc))
    if not outs:
        raise UserError("Training finished but no LoRA file was written. See training_log.txt in " + job_dir)
    ctx.done = 9
    ctx.progress(0, "Adding the LoRA to your library")
    lib = P.LORA_LIB
    if lib is None or not lib.available():
        raise UserError("Training worked, but the ComfyUI LoRA folder isn't on this PC (set COMFY_DIR). The file is in " + job_dir)
    side = {"trigger_words": [trigger], "base": T.BASES[base]["family"], "source": "Easy Studio training",
            "character": ch["id"], "title": f"{ch['name']} ({T.BASES[base]['label']})",
            "area": "adult" if adult else "default", "trained": {"base": base, "pictures": len(items), "when": stamp}}
    dest = os.path.join(lib.dir, "easy_studio")
    os.makedirs(dest, exist_ok=True)
    if "single" in outs:
        fn = f"{name}.safetensors"
        shutil.copyfile(outs["single"], os.path.join(dest, fn))
        rec_name = f"easy_studio/{fn}"
    else:
        pair = {}
        for half, src in outs.items():
            fn = f"{name}_{half}.safetensors"
            shutil.copyfile(src, os.path.join(dest, fn))
            pair[half] = f"easy_studio/{fn}"
        rec_name = pair.get("high_noise") or next(iter(pair.values()))
        side["pair"] = pair
    lib.write_sidecar(rec_name, **side)
    for other in (side.get("pair") or {}).values():
        if other != rec_name:
            lib.write_sidecar(other, **{**side, "hidden": True})
    try:
        hero = ctx.lib.get(ch.get("hero"))
        shutil.copyfile(ctx.lib.path(hero), os.path.splitext(lib.path_of(rec_name))[0] + ".preview.png")
    except Exception:
        pass
    ctx.job["message"] = f"Done. Your LoRA is '{side['title']}'. Trigger word: {trigger}"
    ctx.job["lora"] = rec_name


# ---------------------------------------------------------------------------
# Godot 4 export
# ---------------------------------------------------------------------------
GODOT_PROJECT = """; Engine configuration file made by Easy Studio (Godot 4).
config_version=5

[application]
config/name="{name}"
config/features=PackedStringArray("4.3")

[rendering]
textures/canvas_textures/default_texture_filter=1
"""


def _godot_export_presets(name):
    """Desktop export presets (Windows, Linux, macOS). Godot fills in any option left out with its default;
    the export templates are a one-time download inside Godot (Editor > Manage Export Templates)."""
    safe = re.sub(r"[^A-Za-z0-9]+", "", name)[:30] or "Game"
    out = []
    for i, (plat, path, opts) in enumerate([
            ("Windows Desktop", f"build/windows/{safe}.exe", ['binary_format/embed_pck=true', 'binary_format/architecture="x86_64"']),
            ("Linux", f"build/linux/{safe}.x86_64", ['binary_format/embed_pck=true', 'binary_format/architecture="x86_64"']),
            ("macOS", f"build/macos/{safe}.zip", ['binary_format/architecture="universal"',
                                                    f'application/bundle_identifier="local.easystudio.{safe.lower()}"',
                                                    'codesign/codesign=1'])]):
        out += [f"[preset.{i}]", "", f'name="{plat}"', f'platform="{plat}"', "runnable=true", "dedicated_server=false",
                'custom_features=""', 'export_filter="all_resources"', 'include_filter=""', 'exclude_filter=""',
                f'export_path="{path}"', 'encryption_include_filters=""', 'encryption_exclude_filters=""',
                "encrypt_pck=false", "encrypt_directory=false", "", f"[preset.{i}.options]", "",
                'custom_template/debug=""', 'custom_template/release=""'] + opts + [""]
    return "\n".join(out)


def _godot_spriteframes(frames, fps, anim="default"):
    lines = [f'[gd_resource type="SpriteFrames" load_steps={len(frames) + 1} format=3]', ""]
    for i, f in enumerate(frames):
        lines.append(f'[ext_resource type="Texture2D" path="{f}" id="{i + 1}"]')
    lines += ["", "[resource]", "animations = [{", '"frames": ['
              + ", ".join('{"duration": 1.0, "texture": ExtResource("%d")}' % (i + 1) for i in range(len(frames))) + "],",
              '"loop": true,', f'"name": &"{anim}",', f'"speed": {float(fps)}', "}]", ""]
    return "\n".join(lines)


_MOOD_WORDS = ("smile", "thoughtful", "neutral", "happy", "sad", "idle")
_VOICE_ID = re.compile(r"^[a-z]{2}_[a-z0-9_]{1,32}$")
ISLAND_SENTENCE = (
    "This pack is what the island importer reads, and dropping it into the island is a separate game update."
)


def export_age(character):
    """Whole number written into the pack. A missing, invalid, or under-21 age is not exported."""
    if not isinstance(character, dict):
        raise UserError("Missing stated age: age is missing. It is not exported.")
    if character.get("real_person") is True or character.get("fictional") is False:
        raise UserError("This pack is for a fictional adult. A real person is not exported.")
    if "age" not in character or "stated_age" not in character:
        raise UserError("Missing stated age: age is missing. It is not exported.")
    parsed = {}
    for key in ("age", "stated_age"):
        raw = character.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int):
            ok, _age, msg = safety.require_stated_age({key: raw})
            if not ok:
                raise UserError(msg + " It is not exported.")
            raise UserError("Invalid stated age: %s=%r. It is not exported." % (key, raw))
        if raw < safety.MIN_AGE:
            raise UserError("Stated age is under 21: %s=%s. It is not exported." % (key, raw))
        parsed[key] = raw
    if parsed["age"] != parsed["stated_age"]:
        raise UserError("Conflicting stated ages: age=%s, stated_age=%s. It is not exported."
                        % (parsed["age"], parsed["stated_age"]))
    return parsed["age"]


def _explicit_item(it):
    if not isinstance(it, dict):
        return False
    if (it.get("area") or "default") == "adult":
        return True
    provenance = it.get("provenance") if isinstance(it.get("provenance"), dict) else {}
    if provenance.get("explicit") or provenance.get("pass") == "anatomy":
        return True
    return bool(safety.explicit_word(str(it.get("prompt") or "")) or safety.explicit_word(str(it.get("kind") or "")))


def _export_cleared(it):
    """Skip anything whose appearance check is not ok. That status is not an age."""
    if age_guard.saved_blocked(it):
        return False
    appearance = it.get("appearance_check") if isinstance(it.get("appearance_check"), dict) else {}
    if it.get("type") in ("image", "video"):
        return appearance.get("status") == "ok"
    if appearance and appearance.get("status") not in ("ok",):
        return False
    return True


def _pack_candidate(it, ch):
    if it.get("role") == "scenery" or it.get("place") is True:
        return False
    kind = str(it.get("kind") or "")
    if it.get("favourite") or kind.startswith(("sheet", "model3d")) or it.get("id") == ch.get("hero"):
        return True
    if kind == "still" or it.get("type") == "video":
        return True
    return False


def _media_slot(it, adult_on):
    """Explicit files use the adult slot only. With 21+ off they are left out of the zip."""
    if _explicit_item(it):
        return "adult" if adult_on else None
    return "covered"


def _mood_name(stem):
    low = str(stem or "").lower()
    for word in _MOOD_WORDS:
        if word in low:
            return word
    if low in ("portrait", "image", "hero"):
        return "neutral"
    token = re.sub(r"[^a-z0-9_]+", "_", low).strip("_")[:40]
    return token or "neutral"


def _assign_slot(bucket, mood, slot, path):
    key = mood
    n = 2
    while bucket.get(key, {}).get(slot):
        key = "%s_%d" % (mood, n)
        n += 1
    row = bucket.setdefault(key, {"covered": "", "adult": ""})
    row[slot] = path
    return key


def _personality(character):
    raw = character.get("personality")
    notes = str(character.get("notes") or "")[:400]
    summary, style, likes, limits, voice = "", "", [], [], ""
    if isinstance(raw, dict):
        summary = str(raw.get("summary") or "")[:400]
        style = str(raw.get("style") or "")[:400]
        likes = [str(item)[:80] for item in (raw.get("likes") or []) if isinstance(item, str)][:12]
        limits = [str(item)[:80] for item in (raw.get("limits") or []) if isinstance(item, str)][:12]
        voice = str(raw.get("voice_id") or "")
    elif isinstance(raw, str):
        summary = raw[:400]
    if not summary:
        summary = notes
    if not _VOICE_ID.fullmatch(voice):
        voice = ""
    return {"summary": summary, "style": style, "likes": likes, "limits": limits, "voice_id": voice}


def _export_lora_id(character):
    """Empty, or the id of a LoRA this app already recorded. Never a made-up path."""
    look = character.get("look") if isinstance(character.get("look"), dict) else {}
    import stills
    kept = stills.kept_look(look)
    if kept:
        return kept["lora_id"]
    raw = str(look.get("lora_id") or "").strip()
    if not raw:
        return ""
    lib = P.LORA_LIB
    if lib is None or not getattr(lib, "available", lambda: False)():
        return ""
    try:
        rec = lib.get(raw)
    except Exception:
        return ""
    if not isinstance(rec, dict) or rec.get("blocked") or rec.get("character") != character.get("id"):
        return ""
    source = str(rec.get("source") or "")
    if "Easy Studio" not in source and not rec.get("trained"):
        return ""
    name = str(rec.get("name") or "")
    if not name.endswith(".safetensors") or ".." in name.replace("\\", "/").split("/"):
        return ""
    return name


def _island_record(ch, age, adult_on, portraits, clips):
    """The saved character, plus the fields the island importer reads. Current keys stay."""
    record = dict(ch)
    record["age"] = age
    record["stated_age"] = age
    record["stillwater_export"] = 1
    record["fictional"] = True
    record["real_person"] = False
    record["variant"] = "adult" if adult_on else "covered"
    personality = _personality(ch)
    record["personality"] = personality
    if not str(record.get("notes") or "").strip() and personality.get("summary"):
        record["notes"] = personality["summary"]
    look = dict(ch.get("look")) if isinstance(ch.get("look"), dict) else {}
    if not str(look.get("summary") or "").strip():
        look["summary"] = str(ch.get("extra") or "")
    look["lora_id"] = _export_lora_id(ch)
    record["look"] = look
    record["portraits"] = portraits
    record["clips"] = clips
    return record


def job_export_godot(ctx, p):
    """The zip Easy Studio already writes, with the island fields on character.json.

    One preview project.godot stays in the zip. The importer does not open it, and this
    step does not write another one. Explicit files are omitted unless 21+ is on, and
    then they are recorded only in the adult slot.
    """
    P.require_checker_on()
    ch = _character(ctx, p)
    if not ch:
        raise UserError("Pick a saved character first.")
    age = export_age(ch)
    adult_on = P.area() == "adult"
    items = []
    for it in _usable(ctx, character=ch["id"], limit=5000):
        if not _pack_candidate(it, ch) or not _export_cleared(it):
            continue
        if _media_slot(it, adult_on) is None:
            continue
        items.append(it)
    safe = re.sub(r"[^a-z0-9]+", "_", ch["name"].lower()).strip("_")[:40] or "character"
    base = f"assets/characters/{safe}"
    pairs = []
    pj = os.path.join(ctx.tmp, "project.godot")
    open(pj, "w").write(GODOT_PROJECT.format(name=f"{ch['name']} (Easy Studio)"))
    pairs.append((pj, "project.godot"))
    ep = os.path.join(ctx.tmp, "export_presets.cfg")
    open(ep, "w").write(_godot_export_presets(ch["name"]))
    pairs.append((ep, "export_presets.cfg"))
    ctx.steps(max(1, len(items)))
    has_theora = V.has_encoder("libtheora")
    notes = []
    portraits = {}
    clips = {}
    for it in items:
        src = ctx.lib.path(it)
        fn = os.path.basename(it["file"])
        slot = _media_slot(it, adult_on)
        kind = str(it.get("kind") or "")
        if kind == "sheet:sprites":
            pairs.append((src, f"{base}/sprites/{fn}"))
            atlas = next((x for x in _usable(ctx, limit=5000) if x.get("parent") == it["id"] and x["kind"] == "sheet:sprites_atlas"), None)
            if atlas and _export_cleared(atlas) and _media_slot(atlas, adult_on):
                frames_dir = os.path.join(ctx.tmp, "frames_" + it["id"])
                names = assets.split_sprite_sheet(src, ctx.lib.path(atlas), frames_dir)
                for nme in names:
                    pairs.append((os.path.join(frames_dir, nme), f"{base}/sprites/{it['id']}/{nme}"))
                tres = os.path.join(ctx.tmp, f"{it['id']}.tres")
                open(tres, "w").write(_godot_spriteframes([f"res://{base}/sprites/{it['id']}/{n}" for n in names],
                                                          int(p.get("fps") or 12)))
                pairs.append((tres, f"{base}/sprites/{safe}_{it['id']}_frames.tres"))
        elif kind.startswith("sheet"):
            pairs.append((src, f"{base}/sheets/{fn}"))
        elif it.get("type") == "model":
            pairs.append((src, f"{base}/models/{fn}"))
        elif it.get("type") == "video":
            ext = os.path.splitext(fn)[1].lower() or ".mp4"
            if has_theora:
                ogv = os.path.join(ctx.tmp, os.path.splitext(fn)[0] + ".ogv")
                V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", src, "-c:v", "libtheora", "-q:v", "8",
                        "-c:a", "libvorbis", "-q:a", "5", ogv])
                src, ext = ogv, ".ogv"
            else:
                notes.append("ffmpeg here has no Theora encoder, so videos are MP4: convert them to .ogv for Godot.")
            mood = _mood_name(os.path.splitext(fn)[0])
            clip_name = "%s_%s%s" % (mood, slot, ext)
            rel = f"{base}/videos/{clip_name}"
            n = 2
            while any(name == rel for _src, name in pairs):
                clip_name = "%s_%d_%s%s" % (mood, n, slot, ext)
                rel = f"{base}/videos/{clip_name}"
                n += 1
            pairs.append((src, rel))
            _assign_slot(clips, mood, slot, rel)
        elif it.get("type") == "image":
            mood = _mood_name(os.path.splitext(fn)[0])
            ext = os.path.splitext(fn)[1].lower() or ".png"
            portrait_name = "%s_%s%s" % (mood, slot, ext)
            rel = f"{base}/portraits/{portrait_name}"
            n = 2
            while any(name == rel for _src, name in pairs):
                portrait_name = "%s_%d_%s%s" % (mood, n, slot, ext)
                rel = f"{base}/portraits/{portrait_name}"
                n += 1
            pairs.append((src, rel))
            _assign_slot(portraits, mood, slot, rel)
        ctx.next_step()
    record = _island_record(ch, age, adult_on, portraits, clips)
    dna = os.path.join(ctx.tmp, "character.json")
    json.dump(record, open(dna, "w"), indent=2)
    pairs.append((dna, f"{base}/character.json"))
    readme = os.path.join(ctx.tmp, "README.txt")
    open(readme, "w").write(
        f"Easy Studio -> Godot 4 export: {ch['name']}\nFictional adult character (21+). Not a real person.\n"
        + ISLAND_SENTENCE + "\n\n"
        "Open: Godot 4 > Import > pick this folder's project.godot.\n"
        "Export: Project > Export has Windows, Linux and macOS presets ready (first time: Manage Export Templates > Download).\n"
        f"res://{base}/portraits  pictures (PNG)\n"
        f"res://{base}/sprites    sprite sheets + one PNG per frame + *_frames.tres (SpriteFrames: drop on an AnimatedSprite2D)\n"
        f"res://{base}/models     .glb 3D models (Godot imports glTF directly)\n"
        f"res://{base}/videos     .ogv clips for VideoStreamPlayer\n" + "".join("\nNote: " + n for n in notes) + "\n")
    pairs.append((readme, "README.txt"))
    if sum(1 for _src, name in pairs if name == "project.godot" or name.endswith("/project.godot")) != 1:
        raise UserError("The pack could not be written.")
    out = os.path.join(ctx.tmp, f"{safe}_godot.zip")
    assets.zip_files(pairs, out)
    ctx.add(out, "export:godot", character=ch["id"])


import stills  # noqa: E402
import props  # noqa: E402
import films  # noqa: E402

import lora_workshop  # noqa: E402
import creator_tools  # noqa: E402

P.JOBS.update({"video_any": job_video_any, "train_dataset": job_train_dataset, "train_lora": job_train_lora,
               "export_godot": job_export_godot, "workshop_still": stills.job_workshop_still,
               "keep_face": stills.job_keep_face, "refine_skin": stills.job_refine_skin,
               "refine_anatomy": stills.job_refine_anatomy, "prop": props.job_prop,
               "film": films.job_film, "lora_benchmark": lora_workshop.job_benchmark,
               "workshop_train": lora_workshop.job_train, "workshop_me_train": lora_workshop.job_me_train,
               "creator_outfit": creator_tools.job_outfit})
import owner_train  # noqa: E402  (the owner's likeness trainer and the trainer self-test)
import owner_generate  # noqa: E402  (pictures of the owner, with every gate)
P.JOBS.update({"owner_train": owner_train.job_owner_train, "owner_train_selftest": owner_train.job_selftest,
               "owner_picture": owner_generate.job_owner_picture})
import provider_jobs  # noqa: E402,F401  (registers the hosted Video (API) job)
