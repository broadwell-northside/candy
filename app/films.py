"""A guided short film from a still this app kept.

The clip is Wan 2.2 I2V-A14B, the quality workflow already in the app.
It is 2 or 5 seconds, and it has no sound. The fast lightx2v LoRAs stay off.
Two people touching is still the weak spot. This step does not claim to fix it.
"""
import json
import os
import re

import age_guard
import catalog
import comfy_client as cc
import model_registry as reg
import presets
import safety
import shot_qc
import stills
import pipelines

WAN_URL = "https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B"
LICENSE_CHECKED = "2026-11-05"
WORKFLOW = "video_wan22_i2v_quality_api.json"
CARD_ID = "wan22_i2v"
MODEL_NAME = "Wan 2.2 I2V-A14B"
CONTACT = "Two people touching is still the weak spot. It is not solved."
_ALLOWED = {"image", "seconds", "motion", "text", "seed", "age", "stated_age", "age_years"}
_OFF = ("lightx2v", "krea", "klein", "flux.2", "flux2", "gimm", "svi", "remix", "smoothmix", "dasiwa")
_FACE = re.compile(r"face[\s\-]*swap|swap(?:ping|s)?\s+(?:her|his|their|the)\s+face", re.I)
_LIKENESS = re.compile(
    r"real[\s\-]*person|likeness|looks?\s+like\s+(?:me|a\s+real|my)|my\s+(?:photo|face|selfie|likeness)",
    re.I)
_CLOTHES = re.compile(
    r"clothing[\s\-]*remov\w*|remove[\s\-]*(?:(?:her|his|their|the)[\s\-]*)?cloth\w*|undress\w*|strip(?:ped|ping)?",
    re.I)
_PHOTO_WORD = r"(?:\b(?:photo|picture|image|selfie)s?\b|\buploaded\b|\buploads?\b)"
_PHOTO_CLOTHES = re.compile(
    r"(clothing[\s\-]*remov\w*|remove[\s\-]*(?:(?:her|his|their|the)[\s\-]*)?cloth\w*|undress\w*|strip(?:ped|ping)?)"
    r".{0,80}" + _PHOTO_WORD +
    r"|" + _PHOTO_WORD + r".{0,80}"
    r"(clothing[\s\-]*remov\w*|remove[\s\-]*(?:(?:her|his|their|the)[\s\-]*)?cloth\w*|undress\w*|strip(?:ped|ping)?)",
    re.I)
_REPAIR = re.compile(r"repair\s+contact|fix(?:es|ed|ing)?\s+(?:the\s+)?(?:contact|join)|repaint\s+the\s+join", re.I)


class FilmError(ValueError):
    pass


def _blob(params):
    if not isinstance(params, dict):
        return ""
    return " ".join(str(value) for value in params.values() if isinstance(value, str))


def _phrases(params):
    blob = _blob(params)
    if _FACE.search(blob):
        raise FilmError("This step does not do a face swap.")
    if _LIKENESS.search(blob):
        raise FilmError("A real person's likeness cannot start a film.")
    if _PHOTO_CLOTHES.search(blob):
        raise FilmError("A clothing-removal edit of an uploaded photo is refused.")
    if _REPAIR.search(blob):
        raise FilmError(CONTACT + " This step does not repair it.")
    ok, msg = safety.check_prompt(blob)
    if not ok:
        raise FilmError(msg)


def _seconds(value):
    if isinstance(value, bool) or value is None:
        raise FilmError("Choose 2 or 5 seconds.")
    if isinstance(value, float) and not value.is_integer():
        raise FilmError("Choose 2 or 5 seconds.")
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[0-9]+", text):
            raise FilmError("Choose 2 or 5 seconds.")
        number = int(text)
    else:
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise FilmError("Choose 2 or 5 seconds.")
    allowed = [int(n) for n in reg.clip_lengths()]
    if number not in allowed or number not in (2, 5):
        raise FilmError("Choose 2 or 5 seconds. Those are the only lengths.")
    return number


def _lookup(get_item, iid):
    if not iid or not get_item:
        return None
    try:
        found = get_item(iid)
    except Exception:
        return None
    return found if isinstance(found, dict) else None


def _character(get_character, cid):
    if not cid or not get_character:
        return None
    try:
        found = get_character(cid)
    except Exception:
        return None
    return found if isinstance(found, dict) else None


def _own_record(it):
    if not isinstance(it, dict):
        return None
    dna = it.get("dna")
    if isinstance(dna, dict) and safety.explicit_age_fields(dna) and not safety.people_in(dna):
        return dna
    if any(key in it for key in safety.STATED_AGE_FIELDS):
        return {key: it.get(key) for key in safety.STATED_AGE_FIELDS if key in it}
    return None


def _one_age(it, get_item, get_character, depth=0):
    if not isinstance(it, dict) or depth > 5:
        raise FilmError("Missing stated age: age is missing.")
    records = []
    own = _own_record(it)
    if own is not None:
        records.append(own)
    person = _character(get_character, it.get("character"))
    if isinstance(person, dict) and safety.explicit_age_fields(person) and not safety.people_in(person):
        records.append(person)
    if not records and it.get("parent") and get_item and depth < 5:
        parent = _lookup(get_item, it.get("parent"))
        if isinstance(parent, dict):
            return _one_age(parent, get_item, get_character, depth + 1)
    if not records:
        raise FilmError("Missing stated age: age is missing.")
    ages = []
    for record in records:
        if record.get("real_person") is True:
            raise FilmError("A real person's likeness cannot start a film.")
        ok, age, msg = safety.require_stated_age(record)
        if not ok:
            raise FilmError(msg)
        ages.append(age)
    if len(set(ages)) != 1:
        raise FilmError("The still's stated age does not match this person.")
    return [ages[0]]


def _ages(it, get_item, get_character):
    people = it.get("people")
    dna = it.get("dna") if isinstance(it.get("dna"), dict) else None
    group = people if isinstance(people, list) and people else None
    if group is None and isinstance(dna, dict) and safety.people_in(dna):
        group = safety.people_in(dna)
    if isinstance(group, list) and len(group) >= 2:
        if any(not isinstance(person, dict) or not safety.explicit_age_fields(person) for person in group):
            shared = _own_record(it) or (dna if isinstance(dna, dict) and safety.explicit_age_fields(dna) else None)
            if shared is not None:
                raise FilmError("Each person needs a stated age. One shared age is not enough.")
            raise FilmError("Missing stated age: age is missing.")
        ok, ages, msg = safety.require_group_ages({"people": group})
        if not ok:
            raise FilmError(msg)
        return list(ages)
    if it.get("real_person") is True or (isinstance(dna, dict) and dna.get("real_person") is True):
        raise FilmError("A real person's likeness cannot start a film.")
    return _one_age(it, get_item, get_character)


def _explicit_still(it):
    provenance = it.get("provenance") if isinstance(it.get("provenance"), dict) else {}
    if provenance.get("explicit") or (it.get("area") or "default") == "adult":
        return True
    return bool(safety.explicit_word(str(it.get("prompt") or "")))


def _still(it, get_item, get_character, area_name):
    if not isinstance(it, dict):
        raise FilmError("Choose a still this app kept. A missing still cannot start a film.")
    if it.get("role") == "scenery" or it.get("place") is True:
        raise FilmError("This photo is a place, not a person. It cannot start a film.")
    if it.get("type") != "image" or it.get("role") != "made" or it.get("kind") == "upload":
        raise FilmError(
            "Choose a still this app kept. An uploaded photo cannot start a film, "
            "copy a real person, swap a face, or have its clothes removed.")
    if (it.get("area") or "default") == "adult" and area_name != "adult":
        raise FilmError("Explicit films stay off until the 21+ switch is on.")
    appearance = it.get("appearance_check") if isinstance(it.get("appearance_check"), dict) else {}
    if it.get("age_flag") or appearance.get("status") == "flag":
        raise FilmError("This still was rejected, so it cannot start a film.")
    if age_guard.saved_blocked(it) or it.get("age_check") != "ok":
        raise FilmError("The age check held this still, so it cannot start a film.")
    if _explicit_still(it) and area_name != "adult":
        raise FilmError("Explicit films stay off until the 21+ switch is on.")
    return _ages(it, get_item, get_character)


def _motion_row(motion_id):
    row = catalog.find(catalog.MOTIONS, motion_id)
    if row:
        return row, False
    row = catalog.find(catalog.ADULT_MOTIONS, motion_id)
    if row:
        return row, True
    return None, False


def _phrase(params, area_name):
    text = str(params.get("text") or "").strip()
    motion_id = params.get("motion")
    phrase = ""
    if motion_id not in (None, ""):
        if not isinstance(motion_id, str):
            raise FilmError("Choose one of the motions on this page.")
        row, adult = _motion_row(motion_id)
        if row is None:
            raise FilmError("Choose one of the motions on this page.")
        if adult and area_name != "adult":
            raise FilmError("Explicit films stay off until the 21+ switch is on.")
        phrase = str(row.get("p") or "")
    if text:
        phrase = text
    if not phrase:
        phrase = "moves a little, slowly, camera still"
    if _CLOTHES.search(phrase) and area_name != "adult":
        raise FilmError("Explicit films stay off until the 21+ switch is on.")
    if area_name != "adult" and safety.explicit_word(phrase):
        raise FilmError("Explicit films stay off until the 21+ switch is on.")
    ok, msg = safety.check_prompt(phrase)
    if not ok:
        raise FilmError(msg)
    ok, msg = safety.check_area(phrase, area_name)
    if not ok:
        if area_name != "adult" and (safety.explicit_word(phrase) or _CLOTHES.search(phrase)):
            raise FilmError("Explicit films stay off until the 21+ switch is on.")
        raise FilmError(msg)
    return phrase


def _cards(area_name):
    try:
        row = stills.require_model_card(CARD_ID, area_name)
    except stills.StillError as exc:
        raise FilmError(str(exc)) from exc
    if (row.get("license_name") != "Apache-2.0" or row.get("license_checked") != LICENSE_CHECKED
            or row.get("license_url") != WAN_URL or row.get("private_use") != "yes"):
        raise FilmError("This film step will not run. The Wan license card is missing or not cleared.")
    if row.get("adult_only"):
        raise FilmError("This film step will not run. The Wan card is not the everyday film model.")
    try:
        wf = cc.load_workflow(WORKFLOW)
        for name in stills.workflow_weights(wf):
            low = name.lower()
            if any(part in low for part in _OFF):
                raise FilmError("This film step will not run " + name + ".")
            if stills.uncleared_name(name):
                raise FilmError("This film step will not run " + name + ". That weight has no cleared license card.")
        if stills.lora_names(wf):
            raise FilmError("This film step does not load a fast LoRA.")
        stills.refuse_uncleared(wf)
        stills.require_licensed(wf, area_name)
    except stills.StillError as exc:
        raise FilmError(str(exc)) from exc
    return wf


def public_license():
    row = {}
    try:
        import model_cards
        row = model_cards.card(CARD_ID) or {}
    except Exception:
        row = {}
    return {
        "id": CARD_ID,
        "license_name": row.get("license_name"),
        "license_url": row.get("license_url"),
        "license_checked": row.get("license_checked"),
        "private_use": row.get("private_use"),
    }


def gate(params, area_name, get_character, get_item):
    """Refuse before a job is queued. A bad age never reaches the engine."""
    if not isinstance(params, dict):
        raise FilmError("Missing stated age: age is missing.")
    _phrases(params)
    param_age = None
    if safety.explicit_age_fields(params):
        ok, param_age, msg = safety.require_stated_age(params)
        if not ok:
            raise FilmError(msg)
    extra = set(params) - _ALLOWED
    if extra:
        raise FilmError("This step only takes a still this app kept, and a length of 2 or 5 seconds.")
    seconds = _seconds(params.get("seconds"))
    try:
        stills.seed_param(params)
    except stills.StillError as exc:
        raise FilmError(str(exc)) from exc
    phrase = _phrase(params, area_name)
    it = _lookup(get_item, params.get("image"))
    ages = _still(it, get_item, get_character, area_name)
    if param_age is not None and param_age not in ages:
        raise FilmError("The stated age stays on the still. It is not edited on this step.")
    _cards(area_name)
    return it, ages, seconds, phrase


def _audio_streams(path):
    import video_tools as V
    out = V._run([V.ffprobe_bin(), "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", path])
    data = json.loads(out or "{}")
    return [row for row in data.get("streams") or [] if row.get("codec_type") == "audio"]


def _silent(src, dst):
    import video_tools as V
    V._run([
        V.ffmpeg_bin(), "-y", "-v", "error", "-i", src,
        "-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart", dst,
    ])
    if _audio_streams(dst):
        raise FilmError("Wan has no sound. This clip was not saved.")
    return dst


def _get(ctx, iid):
    lib = getattr(ctx.lib, "lib", ctx.lib)
    return _lookup(lib.get, iid)


def build_film_graph(phrase, seconds, area_name, image_path, start_name, seed=None):
    """The ComfyUI graph a film job runs. The recipe compiler calls the same function, so the graph in
    the node drawer is the graph that runs. The still enters as pixels through START IMAGE (a LoadImage);
    no latent crosses model families. Raises FilmError."""
    wf = _cards(area_name)
    spoken = safety.add_adult_hint(phrase)
    pipelines._txt(spoken)
    size = pipelines._video_size(image_path, "720")
    length, chained = shot_qc.cap_frames(presets.frames_for_seconds(seconds))
    if chained or length > shot_qc.max_frames():
        raise FilmError("Choose 2 or 5 seconds. Those are the only lengths.")
    cc.set_in(wf, "POSITIVE", text=spoken)
    cc.set_in(wf, "NEGATIVE", text=pipelines.safe_neg_for(presets.VIDEO_NEGATIVE, area_name))
    cc.set_in(wf, "START IMAGE", image=start_name)
    cc.set_in(wf, "SIZE", width=size[0], height=size[1], length=length)
    cc.set_in(wf, "FPS", fps=float(presets.WAN_FPS))
    seed = seed if seed is not None else pipelines._rand_seed()
    cc.set_seed(wf, seed)
    if stills.lora_names(wf) or any(part in name.lower() for name in stills.workflow_weights(wf) for part in _OFF):
        raise FilmError("This film step does not load a fast LoRA.")
    stills.require_licensed(wf, area_name)
    return {"wf": wf, "spoken": spoken, "length": length, "seed": seed, "template": WORKFLOW}


def job_film(ctx, p):
    pipelines.require_checker_on()
    try:
        still, ages, seconds, phrase = gate(p, pipelines.area(), ctx.chars.get, lambda iid: _get(ctx, iid))
        built = build_film_graph(phrase, seconds, pipelines.area(), ctx.lib.path(still), ctx.upload_item(still),
                                 stills.seed_param(p))
    except (FilmError, stills.StillError) as exc:
        raise pipelines.UserError(str(exc)) from exc
    wf, spoken, length = built["wf"], built["spoken"], built["length"]
    res = ctx.run(wf, "Making a short film")
    outs = [path for path in pipelines.first(res) if str(path).lower().endswith(".mp4")]
    if not outs:
        raise pipelines.UserError("The film step finished but did not return a clip.")
    silent = os.path.join(ctx.tmp, "film_%s.mp4" % ctx.job["id"])
    try:
        _silent(outs[0], silent)
    except FilmError as exc:
        raise pipelines.UserError(str(exc)) from exc
    except Exception as exc:
        raise pipelines.UserError("Wan has no sound. This clip was not saved.") from exc
    meta = pipelines._meta_from(still)
    if len(ages) == 1:
        meta["stated_age"] = ages[0]
        meta["dna"] = {"age": ages[0], "stated_age": ages[0], "age_source": "stated"}
    else:
        people = meta.get("people") if isinstance(meta.get("people"), list) else None
        if not people or len(people) != len(ages):
            meta["people"] = [{"stated_age": age, "age": age} for age in ages]
    meta["provenance"] = {
        "model": MODEL_NAME,
        "workflow": WORKFLOW,
        "sound": False,
        "seconds": seconds,
        "frames": length,
        "fps": presets.WAN_FPS,
        "quality": "720",
        "license": public_license(),
        "contact": CONTACT,
        "fast_lora": False,
        "seed": built["seed"],
    }
    ctx.add(silent, "video:film", prompt=spoken, model=MODEL_NAME, seed=built["seed"], **meta)
