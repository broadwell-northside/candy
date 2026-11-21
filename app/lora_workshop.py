"""LoRA workshop: import, usage card, stack conflicts, a mock benchmark, and training.

The catalogue in app/fixtures/lora_catalogue.json is metadata only. Tests set
EASY_STUDIO_LORA_OFFLINE=1 so a pasted Civitai link never calls the network.
A future Civitai token is an op:// reference. This module does not print one.
"""
import hashlib
import json
import os
import re
import shutil
import struct

import loras as L
import safety
import trainer as T

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE_PATH = os.path.join(HERE, "fixtures", "lora_catalogue.json")
CHECKER_KINDS = ("lora_benchmark", "workshop_train", "workshop_me_train")
RESUME_ACK = "inference-lora-is-not-a-checkpoint"
BENCH_STRENGTHS = (0.4, 0.6, 0.8, 1.0)
STRENGTH_SUM_WARN = 1.5
APP_KINDS = {"create", "still", "train:shot"}
SEXUAL_ME = re.compile(
    r"\b(nude|naked|topless|nsfw|sex|erotic|lingerie|explicit|undress|strip|remove\s+clothes|clothing\s+removal)\b",
    re.I)
EMPTY_TRIGGER = "No trigger words were listed. That is not proof this LoRA has no trigger."
RESUME_TEXT = ("An inference LoRA is not a resumable training checkpoint. "
               "Resume only from a durable checkpoint you have acknowledged.")
ME_TEXT = "Me is the player, Andrew, not an NPC."
ME_SEX = "Sexual content is not offered for Me. Me is the player, Andrew, not a partner."
# An uploaded photo with two tick boxes does not show who is in it, so that path is closed.
ME_CAPTURE_ONLY = ("Me photos are not taken by upload. Enrolment happens only through the in-app camera capture, "
                   "and that is not built yet. No photo was saved and nothing was trained.")
MOCK_CAPTION = "Mock picture. Not a photograph."
PRIVATE_NOTICE = "PRIVATE BUILD — NOT FOR DISTRIBUTION"
TOKEN_TEXT = "A future Civitai token is an op:// reference. This page does not ask for it and does not print it."

ENGINES = [
    {"id": "zimage_turbo", "label": "Z-Image Turbo", "family": "zimage", "wan_version": "", "wan_expert": ""},
    {"id": "wan22_high", "label": "Wan 2.2 High Noise", "family": "wan14b", "wan_version": "2.2", "wan_expert": "high_noise"},
    {"id": "flux", "label": "Chroma / Flux", "family": "flux", "wan_version": "", "wan_expert": ""},
    {"id": "sdxl", "label": "SDXL", "family": "sdxl", "wan_version": "", "wan_expert": ""},
]

_CATALOGUE = None


class UseNetwork(Exception):
    """The id is not in the fixture catalogue, and this process may call Civitai."""


def offline():
    return os.environ.get("EASY_STUDIO_LORA_OFFLINE") == "1"


def limits():
    return {
        "notice": PRIVATE_NOTICE,
        "trainer": "ai-toolkit",
        "trainer_line": "The trainer is ai-toolkit. Other trainers are not in this version.",
        "merge_or_publish": False,
        "merge_line": "A full merge or a publish to Civitai is not in this version.",
        "resume": RESUME_TEXT,
        "spend": False,
        "spend_line": "This practice run does not download weights and does not spend money.",
        "download_weights_on_train": False,
        "token": TOKEN_TEXT,
        "empty_trigger": EMPTY_TRIGGER,
        "mock_caption": MOCK_CAPTION,
        "me": ME_TEXT,
        "me_sexual": ME_SEX,
        "me_capture_only": ME_CAPTURE_ONLY,
        "face_check": "The face check compares a result with its reference. A miss or an unsure mock score shows a hold on the LoRA card, the LoRA cannot be marked accepted, and a pack sent to the island is refused while the hold is on. The hold does not yet stop the LoRA from being used in other jobs.",
        "built": ["one-tap sample prompt", "stack coach", "outfit try-on", "face check", "defect hold", "surprise me"],
        "engines": ENGINES,
        "benchmark_strengths": list(BENCH_STRENGTHS),
    }


def catalogue():
    global _CATALOGUE
    if _CATALOGUE is None:
        with open(CATALOGUE_PATH, encoding="utf-8") as handle:
            _CATALOGUE = json.load(handle)
    return _CATALOGUE


def entry_by_id(entry_id):
    for entry in catalogue():
        if entry["id"] == entry_id:
            return entry
    return None


def find_entry(model_id, version_id=None):
    for entry in catalogue():
        if int(entry["civitai_model_id"]) != int(model_id or 0):
            continue
        if version_id and int(entry["civitai_version_id"]) != int(version_id):
            continue
        return entry
    return None


def lora_bytes(entry):
    family = L.civitai_family(entry.get("baseModel"))
    keys = ["lora_unet.lora_down.weight", "lora_unet.lora_up.weight"]
    header = {"__metadata__": {"es_base": family, "workshop_id": entry["id"],
                               "ss_base_model_version": str(entry.get("baseModel") or "")}}
    offset = 0
    for key in keys:
        header[key] = {"dtype": "F16", "shape": [8, 8], "data_offsets": [offset, offset + 8]}
        offset += 8
    raw = json.dumps(header).encode()
    return struct.pack("<Q", len(raw)) + raw + (b"\0" * offset)


def listed_hash(entry, data):
    if "sha256" in entry and entry.get("sha256") is not None:
        return str(entry.get("sha256") or "")
    return hashlib.sha256(data).hexdigest()


def _model(entry):
    return {"id": entry["civitai_model_id"], "name": entry["name"], "type": entry.get("type") or "LORA",
            "poi": bool(entry.get("poi")), "minor": bool(entry.get("minor")), "mode": entry.get("mode") or "",
            "nsfw": bool(entry.get("nsfw")), "tags": entry.get("tags") or [],
            "description": entry.get("author_notes") or "", "scans": entry.get("scans") or []}


def _version(entry, sha):
    hashes = {"SHA256": sha} if sha else {}
    return {"id": entry["civitai_version_id"], "name": entry.get("version") or "",
            "baseModel": entry.get("baseModel") or "", "trainedWords": list(entry.get("trainedWords") or []),
            "mode": entry.get("mode") or "", "scans": entry.get("scans") or [],
            "files": [{"name": entry["file"], "primary": True, "sizeKB": 1,
                       "metadata": {"format": "SafeTensor"}, "hashes": hashes, "scans": entry.get("scans") or []}],
            "model": {"name": entry["name"], "type": entry.get("type") or "LORA",
                      "poi": bool(entry.get("poi")), "mode": entry.get("mode") or ""}}


def assess(entry):
    data = lora_bytes(entry)
    sha = listed_hash(entry, data)
    model, version = _model(entry), _version(entry, sha)
    ok, why = L.civitai_check(model, version)
    version_name, expert = L.wan_parts(entry.get("baseModel"))
    return {"ok": ok, "reason": why or "", "sha256": sha, "data": data,
            "family": L.civitai_family(entry.get("baseModel")),
            "wan_version": version_name, "wan_expert": expert}


def public_entry(entry, gate=None):
    gate = gate or assess(entry)
    words = list(entry.get("trainedWords") or [])
    examples = []
    for example in entry.get("examples") or []:
        row = dict(example)
        row["label"] = example_label(row)
        examples.append({key: row[key] for key in ("prompt", "source_id", "author_id", "source_author", "authorship", "label") if key in row})
    return {"id": entry["id"], "name": entry["name"], "version": entry.get("version") or "",
            "baseModel": entry.get("baseModel") or "", "family": gate["family"], "family_label": L.FAMILIES.get(gate["family"], gate["family"]),
            "trainedWords": words, "role": entry.get("role") or "", "author_notes": entry.get("author_notes") or "",
            "scans": entry.get("scans") or [], "mode": L.civitai_mode(_model(entry), _version(entry, gate["sha256"])),
            "poi": bool(entry.get("poi")), "minor": bool(entry.get("minor")),
            "sha256": gate["sha256"], "hash_status": "listed" if gate["sha256"] else "UNKNOWN",
            "file": entry["file"], "ok": gate["ok"], "reason": gate["reason"],
            "wan_version": gate["wan_version"], "wan_expert": gate["wan_expert"],
            "authorship": entry.get("authorship") or "unverified", "examples": examples,
            "model_id": entry["civitai_model_id"], "version_id": entry["civitai_version_id"],
            "trigger_words": words, "strength_model": "UNKNOWN", "strength_clip": "UNKNOWN",
            "download": "Weights download only after you confirm."}


def catalogue_public():
    rows = [public_entry(entry) for entry in catalogue()]
    rows.sort(key=lambda row: (not row["ok"], row["name"]))
    return {"notice": PRIVATE_NOTICE, "token": TOKEN_TEXT, "source": "fixture", "network": False, "entries": rows}


def lookup_url(url):
    model_id, version_id = L.parse_civitai_url(url)
    entry = find_entry(model_id, version_id)
    if entry:
        return public_entry(entry)
    if offline():
        raise ValueError("This build does not call Civitai. That model is not in the workshop catalogue.")
    raise UseNetwork()


def lookup_id(entry_id):
    entry = entry_by_id(entry_id)
    if not entry:
        raise ValueError("That LoRA is not in the workshop catalogue.")
    return public_entry(entry)


def import_entry(lib, entry_id, confirm):
    if confirm != "yes":
        raise ValueError("Download weights only after you confirm.")
    entry = entry_by_id(entry_id)
    if not entry:
        raise ValueError("That LoRA is not in the workshop catalogue.")
    gate = assess(entry)
    if not gate["ok"]:
        raise ValueError(gate["reason"] or "Blocked.")
    data = gate["data"]
    expected = gate["sha256"]
    folder = lib.dir
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, ".workshop_%s.part" % entry["id"])
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
        status = L.hash_status(tmp, expected)
        if status == "mismatch":
            raise ValueError("Blocked: the downloaded file hash does not match the published SHA256.")
        words = list(entry.get("trainedWords") or [])
        version_name, expert = gate["wan_version"], gate["wan_expert"]
        usage = {"author_notes": entry.get("author_notes") or "", "trained_words": words,
                 "trained_words_listed": bool(words), "strength_model": None, "strength_clip": None,
                 "hash_status": status, "sha256": expected, "role": entry.get("role") or "",
                 "base_model": entry.get("baseModel") or "", "wan_version": version_name, "wan_expert": expert,
                 "authorship": entry.get("authorship") or "unverified", "examples": entry.get("examples") or [],
                 "recipe": entry.get("recipe") or "", "recipe_source_id": entry.get("recipe_source_id") or "",
                 "scans": entry.get("scans") or [], "mode": entry.get("mode") or ""}
        side = {"source": "Workshop catalogue", "title": entry["name"], "trigger_words": words,
                "base": gate["family"], "usage": usage,
                "civitai": {"model": entry["civitai_model_id"], "version": entry["civitai_version_id"],
                            "base": entry.get("baseModel") or ""}}
        return lib.add_file(tmp, entry["file"], **side)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def example_label(example):
    if (example.get("authorship") == "verified" and example.get("author_id")
            and example.get("author_id") == example.get("source_author")):
        return "Author example"
    return "Resource example (authorship unverified)"


def _strength_text(usage, key):
    if not isinstance(usage, dict) or key not in usage or usage.get(key) in (None, ""):
        return "UNKNOWN"
    return usage.get(key)


def usage_card(record):
    usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
    if "trained_words" in usage:
        words = [str(word).strip() for word in (usage.get("trained_words") or []) if str(word).strip()]
    else:
        words = list(record.get("trigger_words") or [])
    empty = "" if words else EMPTY_TRIGGER
    examples = []
    for example in usage.get("examples") or []:
        if not isinstance(example, dict):
            continue
        examples.append({"prompt": example.get("prompt") or "", "source_id": example.get("source_id") or "",
                         "label": example_label(example), "weight": record.get("name") or ""})
    recipe = None
    if usage.get("authorship") == "verified" and (words or usage.get("recipe")):
        recipe = {"label": "Author recipe",
                  "text": usage.get("recipe") or ("Start the prompt with " + ", ".join(words) + "."),
                  "source_id": usage.get("recipe_source_id") or ""}
    suggestion = {"label": "App suggestion",
                  "text": empty or "Put the listed trigger words at the start of the prompt. This app does not suggest a strength. Model strength and clip strength stay separate."}
    preset = usage.get("tested_preset") if isinstance(usage.get("tested_preset"), dict) else None
    if preset:
        preset = dict(preset)
        preset["label"] = "My tested preset"
        if preset.get("strength_clip") in (None, ""):
            preset["strength_clip"] = "UNKNOWN"
    return {"name": record.get("name") or "", "title": record.get("title") or "",
            "author_notes": usage.get("author_notes") or "", "trained_words": words,
            "empty_trigger_note": empty, "strength_model": _strength_text(usage, "strength_model"),
            "strength_clip": _strength_text(usage, "strength_clip"), "author_recipe": recipe,
            "app_suggestion": suggestion, "tested_preset": preset, "examples": examples,
            "hash_status": usage.get("hash_status") or "UNKNOWN", "sha256": usage.get("sha256") or "",
            "weight": record.get("name") or "", "identity": record.get("identity") or "",
            "player_only": bool(record.get("player_only")), "family": record.get("family") or "",
            "role": usage.get("role") or "", "accepted": usage.get("accepted", None),
            "face_hold": bool(usage.get("face_hold")),
            "face_check": usage.get("face_check") if isinstance(usage.get("face_check"), dict) else None}


def insert_triggers(prompt, words, weight):
    prompt = str(prompt or "")
    words = [str(word).strip() for word in (words or []) if str(word).strip()]
    if not words:
        return {"prompt": prompt, "weight": weight, "weight_changed": False, "note": EMPTY_TRIGGER}
    missing = [word for word in words if word.lower() not in prompt.lower()]
    if missing:
        prompt = ", ".join(missing) + (", " + prompt if prompt else "")
    return {"prompt": prompt, "weight": weight, "weight_changed": False, "note": ""}


def apply_sample(example, weight):
    row = dict(example or {})
    return {"prompt": row.get("prompt") or "", "source_id": row.get("source_id") or "",
            "label": example_label(row), "weight": weight, "weight_changed": False}


def engine_by_id(engine_id):
    for engine in ENGINES:
        if engine["id"] == engine_id:
            return engine
    raise ValueError("Pick an engine from the list.")


def policy_reason(item, engine, area="default"):
    if item.get("blocked"):
        return item.get("blocked_reason") or "This LoRA is blocked."
    if item.get("player_only") or item.get("identity") == "player_me":
        return "This LoRA is the player, Andrew. It is not an NPC, and it is not used to make pictures of anyone else."
    if item.get("area") == "adult" and area != "adult":
        return "This LoRA is kept in the 21+ section."
    family = item.get("family") or "unknown"
    model_family = (engine or {}).get("family") or ""
    if model_family and family not in ("unknown", model_family) and not ({family, model_family} <= {"wan14b"}):
        title = item.get("title") or item.get("name") or "This LoRA"
        return "LoRA '%s' was made for %s, so it won't work with %s." % (
            title, L.FAMILIES.get(family, family), L.FAMILIES.get(model_family, model_family))
    return ""


def wan_conflict(item, engine):
    if item.get("wan_version") == "2.1" and engine.get("wan_version") == "2.2" and engine.get("wan_expert") == "high_noise":
        return {"level": "soft", "id": "wan21_in_wan22_high", "name": item.get("name") or "",
                "text": "Wan 2.1 LoRA in Wan 2.2 High Noise",
                "coach": "Take this Wan 2.1 LoRA off the Wan 2.2 High Noise engine. The stack coach does not load a different weight file."}
    if item.get("wan_version") == "2.1" and engine.get("wan_version") == "2.2":
        return {"level": "soft", "id": "wan21_on_wan22", "name": item.get("name") or "",
                "text": "This Wan 2.1 LoRA is on a Wan 2.2 engine.",
                "coach": "Wan 2.1 and Wan 2.2 are not the same file. Take it off this stack if the motion looks wrong."}
    return None


def stack_report(items, engine, area="default"):
    if isinstance(engine, str):
        engine = engine_by_id(engine)
    hard, soft = [], []
    for item in items or []:
        reason = policy_reason(item, engine, area)
        if reason:
            hard.append({"level": "hard", "id": "policy", "name": item.get("name") or "", "text": reason,
                         "coach": reason + " The stack coach does not load a different weight file."})
            continue
        row = wan_conflict(item, engine)
        if row:
            soft.append(row)
    if sum(1 for item in items or [] if item.get("role") in ("character", "face") and not item.get("blocked")) >= 2:
        soft.append({"level": "soft", "id": "two_characters", "text": "Two character or face LoRAs are on this stack.",
                     "coach": "Keep one character or face LoRA. Taking one off this stack does not delete its file."})
    if sum(1 for item in items or [] if item.get("role") == "style" and not item.get("blocked")) >= 2:
        soft.append({"level": "soft", "id": "style_fight", "text": "Two style LoRAs are on this stack. Style can fight style.",
                     "coach": "Keep one style LoRA if the picture starts to pull two ways."})
    known, missing = [], False
    for item in items or []:
        value = item.get("strength_model")
        if value in (None, "", "UNKNOWN"):
            missing = True
        else:
            known.append(float(value))
    if known and missing:
        soft.append({"level": "soft", "id": "strength_unknown",
                     "text": "A model strength is UNKNOWN, so the stack total is not known. Missing strengths are not treated as zero.",
                     "coach": "Leave an unknown strength as UNKNOWN. Do not fill in a number that was not tested."})
    if known and sum(known) > STRENGTH_SUM_WARN:
        soft.append({"level": "soft", "id": "strength_high",
                     "text": "The known model strengths add up to %.2f, which is over 1.5. This is a warning, not a recommended strength." % sum(known),
                     "coach": "Lower a model strength you have already tested, or take one LoRA off the stack."})
    if any(value > 1 for value in known):
        soft.append({"level": "soft", "id": "strength_over_one",
                     "text": "A known model strength is over 1. This is a warning, not a recommended strength.",
                     "coach": "The card does not invent a strength. Use a tested preset if you have one."})
    rows = hard + soft
    return {"engine": engine, "hard": hard, "soft": soft, "blocked": bool(hard),
            "coach": [row["coach"] for row in rows] or ["Nothing to change. This stack has no warning."]}


def stack_item(record):
    usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
    strength = usage.get("strength_model") if isinstance(usage, dict) and "strength_model" in usage else None
    return {"name": record.get("name") or "", "title": record.get("title") or "", "family": record.get("family") or "unknown",
            "role": usage.get("role") or "", "blocked": bool(record.get("blocked")),
            "blocked_reason": record.get("blocked_reason") or "", "area": record.get("area") or "default",
            "identity": record.get("identity") or "", "player_only": bool(record.get("player_only")),
            "wan_version": usage.get("wan_version") or "", "wan_expert": usage.get("wan_expert") or "",
            "strength_model": strength if strength not in ("",) else None,
            "strength_clip": usage.get("strength_clip") if isinstance(usage, dict) and "strength_clip" in usage else None}


def me_gate(filename, age, confirm_player, confirm_not_npc, caption, area):
    if area == "adult":
        raise ValueError(ME_SEX)
    if confirm_player != "andrew-player":
        raise ValueError("These photos have to be Andrew's own photos. Me is the player, not anyone else.")
    if confirm_not_npc != "not-an-npc":
        raise ValueError(ME_TEXT)
    ok, stated, msg = safety.require_stated_age({"age": age})
    if not ok:
        raise ValueError(msg)
    text = " ".join(part for part in (filename or "", caption or "") if part)
    ok, msg = safety.check_prompt(text)
    if not ok:
        raise ValueError(msg)
    if SEXUAL_ME.search(text) or not safety.check_area(text, "default")[0]:
        raise ValueError(ME_SEX)
    return stated


def still_source_ok(item):
    if not isinstance(item, dict) or item.get("type") != "image":
        return False
    if item.get("kind") not in APP_KINDS:
        return False
    if item.get("role") not in ("made", "", None):
        return False
    if item.get("identity") == "player_me" or str(item.get("role") or "").startswith("player_me"):
        return False
    if item.get("age_flag") or item.get("held"):
        return False
    if item.get("remote") is True:  # made by a hosted service, or from a frame of its clip: never trained on
        return False
    if item.get("age_check") in ("unchecked", "blocked_age_check_unavailable", "unavailable", "error", "timeout", "off"):
        return False
    return True


def still_age(item, chars):
    rec = None
    dna = item.get("dna")
    if isinstance(dna, dict) and safety.explicit_age_fields(dna):
        rec = dna
    elif item.get("stated_age") is not None:
        rec = {"age": item.get("stated_age")}
    elif item.get("character") and chars is not None:
        try:
            found = chars.get(item["character"])
        except Exception:
            found = None
        if isinstance(found, dict) and safety.explicit_age_fields(found):
            rec = found
    if not rec:
        raise ValueError("Missing stated age: age is missing. Age is not inferred from appearance.")
    ok, age, msg = safety.require_stated_age(rec)
    if not ok:
        raise ValueError(msg)
    return age


def require_resume(ack):
    if ack != RESUME_ACK:
        raise ValueError(RESUME_TEXT)


def _write_dataset(folder, items, path_of, caption):
    os.makedirs(folder, exist_ok=True)
    text = caption if "[trigger]" in str(caption or "") else "[trigger], " + str(caption or "").strip()
    for index, item in enumerate(items):
        dst = os.path.join(folder, "%03d.png" % index)
        shutil.copyfile(path_of(item), dst)
        with open(os.path.join(folder, "%03d.txt" % index), "w", encoding="utf-8") as handle:
            handle.write(text)


def _finish_lora(ctx, job_dir, name, side):
    import pipelines as P
    try:
        outs = T.find_outputs(job_dir, name)
    except ValueError as exc:
        raise P.UserError(str(exc))
    if not outs:
        raise P.UserError("Training finished but no LoRA file was written.")
    lib = P.LORA_LIB
    if lib is None or not lib.available():
        raise P.UserError("The LoRA folder is not on this PC, so the file was not added.")
    dest = os.path.join(lib.dir, "easy_studio")
    os.makedirs(dest, exist_ok=True)
    if "single" in outs:
        filename = name + ".safetensors"
        shutil.copyfile(outs["single"], os.path.join(dest, filename))
        rec_name = "easy_studio/" + filename
    else:
        pair = {}
        for half, src in outs.items():
            filename = "%s_%s.safetensors" % (name, half)
            shutil.copyfile(src, os.path.join(dest, filename))
            pair[half] = "easy_studio/" + filename
        rec_name = pair.get("high_noise") or next(iter(pair.values()))
        side["pair"] = pair
    checkpoints = []
    out_dir = os.path.join(job_dir, "output", name)
    if os.path.isdir(out_dir):
        checkpoints = [fn for fn in sorted(os.listdir(out_dir)) if re.search(r"_\d{6,}", fn)]
    side.setdefault("usage", {})
    side["usage"]["inference_lora_is_not_a_checkpoint"] = True
    side["usage"]["checkpoints_not_loaded"] = checkpoints
    side["usage"]["resume"] = RESUME_TEXT
    lib.write_sidecar(rec_name, **side)
    ctx.job["lora"] = rec_name
    ctx.job["message"] = "Done. The library file is an inference LoRA. " + RESUME_TEXT
    return rec_name


def _train_common(ctx, base, trigger, items, caption, ack):
    import pipelines as P
    P.require_checker_on()
    try:
        require_resume(ack)
    except ValueError as exc:
        raise P.UserError(str(exc))
    if base not in T.BASES:
        raise P.UserError("Pick a base. ai-toolkit is the trainer in this version.")
    if not T.installed(_root()):
        raise P.UserError("The trainer isn't installed yet.")
    ok, msg = safety.check_prompt(trigger)
    if not ok:
        raise P.UserError(msg)
    ok, msg = safety.check_prompt(str(caption or "").replace("[trigger]", ""))
    if not ok:
        raise P.UserError(msg)
    if len(items) < T.MIN_PICTURES:
        raise P.UserError("Training needs at least %d pictures (you have %d)." % (T.MIN_PICTURES, len(items)))
    recheck_training_pictures(ctx, items)
    return trigger


_AGE_NOT_CLEARED = ("unchecked", "blocked_age_check_unavailable", "unavailable", "error", "timeout", "off")


def recheck_training_pictures(ctx, items):
    """SAFETY.md, Training: every training picture is age-checked again right before training. One flag stops the run.

    Whatever the gallery record says, each file is checked again here. It fails closed: no checker, a stored
    hold or flag, a flag now, or any answer that is not a clear pass stops the run before a dataset is written.
    """
    import age_guard
    import pipelines as P
    guard = P.AGE_GUARD
    if guard is None or not guard.enabled:
        raise P.UserError(age_guard.CHECKER_OFF_REASON)
    for item in items:
        appearance = item.get("appearance_check") if isinstance(item.get("appearance_check"), dict) else {}
        if item.get("age_flag") or item.get("held") or appearance.get("held") or item.get("age_check") in _AGE_NOT_CLEARED:
            raise P.UserError("A held age check cannot be used for training.")
        try:
            res = guard.check(ctx.lib.path(item))
        except Exception as exc:
            raise P.UserError("The age check held this picture, so training can't start: " + str(exc))
        if not isinstance(res, dict):
            raise P.UserError("The age check held this picture, so training can't start: the checker gave no answer")
        if res.get("status") == "flag":
            raise P.UserError("A training picture was flagged by the age check, so training was stopped. "
                              "Remove it and try again.")
        if age_guard.held_unusable(res) or res.get("status") != "ok":
            raise P.UserError("The age check held this picture, so training can't start: "
                              + str(res.get("reason") or res.get("status")))


def job_benchmark(ctx, params):
    import comfy_client as cc
    import pipelines as P
    P.require_checker_on()
    name = str(params.get("name") or "")
    ok, age, msg = safety.require_stated_age({"age": params.get("stated_age")})
    if not ok:
        raise P.UserError(msg)
    prompt = str(params.get("prompt") or "").strip()
    if not prompt:
        raise P.UserError("Type a prompt first.")
    ok, msg = safety.check_prompt(prompt)
    if ok:
        ok, msg = safety.check_area(prompt, P.area())
    if not ok:
        raise P.UserError(msg)
    ok, msg = safety.reconcile_prompt_ages(prompt, [{"age": age}])
    if not ok:
        raise P.UserError(msg)
    if params.get("seed") in (None, ""):
        raise P.UserError("Type a seed. Every cell in this grid uses that same seed.")
    try:
        seed = int(params.get("seed"))
    except (TypeError, ValueError):
        raise P.UserError("The seed has to be a whole number.")
    lib = P.LORA_LIB
    if lib is None or not lib.available():
        raise P.UserError("The LoRA folder is not on this PC.")
    try:
        record = lib.check_usable(name, "zimage", P.area())
    except ValueError as exc:
        raise P.UserError(str(exc))
    if not record:
        raise P.UserError("Pick a LoRA that is in the library.")
    card = usage_card(record)
    words = card["trained_words"]
    cells = [(flag, strength) for flag in (False, True) for strength in BENCH_STRENGTHS]
    ctx.steps(len(cells))
    made = []
    for index, (with_triggers, strength) in enumerate(cells):
        text = insert_triggers(prompt, words, name)["prompt"] if with_triggers else prompt
        wf = cc.load_workflow("image_zimage_turbo_api.json")
        cc.set_in(wf, "POSITIVE", text=text)
        if cc.has_title(wf, "NEGATIVE"):
            cc.set_in(wf, "NEGATIVE", text=safety.safe_negative(""))
        cc.set_in(wf, "SIZE", width=384, height=384)
        cc.set_seed(wf, seed)
        _attach_lora(wf, name, strength)
        res = ctx.run(wf, "Benchmark %d of %d" % (index + 1, len(cells)))
        for path in P.first(res):
            item = ctx.add(path, "lora:benchmark", role="benchmark", title=MOCK_CAPTION, prompt=text,
                           stated_age=age, dna={"age": age, "stated_age": age, "age_source": "stated"},
                           bench_seed=seed, bench_strength_model=strength, bench_strength_clip="UNKNOWN",
                           bench_triggers=with_triggers, bench_weight=name, bench_index=index,
                           bench_note=card["empty_trigger_note"],
                           provenance={"mock": True, "not_a_photograph": True, "seed": seed,
                                       "strength_model": strength, "strength_clip": "UNKNOWN",
                                       "with_triggers": with_triggers, "weight": name})
            made.append(item["id"])
        ctx.next_step()
    ctx.job["message"] = "Done. " + MOCK_CAPTION
    return made


def _attach_lora(wf, name, strength):
    import comfy_client as cc
    loaders = [nid for nid, node in wf.items() if node.get("class_type") in ("UNETLoader", "CheckpointLoaderSimple")]
    nxt = max(int(key) for key in wf if str(key).isdigit()) + 1000
    for loader in loaders:
        inputs = wf[loader].get("inputs") or {}
        chosen = cc.route_lora(name, inputs.get("unet_name") or inputs.get("ckpt_name") or "")
        if not chosen:
            continue
        src = [loader, 0]
        nid = str(nxt)
        nxt += 1
        wf[nid] = {"class_type": "LoraLoaderModelOnly",
                   "inputs": {"model": src, "lora_name": chosen, "strength_model": float(strength)}}
        for node_id, node in wf.items():
            if node_id == nid:
                continue
            for key, value in list((node.get("inputs") or {}).items()):
                if isinstance(value, list) and len(value) == 2 and value[0] == loader and value[1] == 0:
                    node["inputs"][key] = [nid, 0]


def job_train(ctx, params):
    import pipelines as P
    kind = params.get("kind") or "character"
    if kind not in ("character", "concept"):
        raise P.UserError("Pick a character LoRA or a concept LoRA.")
    if kind == "character":
        try:
            character = ctx.chars.get(params.get("character") or "")
        except Exception:
            character = None
        if not isinstance(character, dict):
            raise P.UserError("Pick a saved fictional adult first.")
        if character.get("real_person") is True:
            raise P.UserError("A character LoRA is for a fictional adult. Andrew's photos stay on the Me path.")
        ok, _, msg = safety.require_stated_age(character)
        if not ok:
            raise P.UserError(msg)
        trigger = str(params.get("trigger") or T.make_trigger(character.get("name") or ""))
        title = character.get("name") or "Character"
        character_id = character.get("id")
    else:
        character_id = ""
        title = str(params.get("concept") or "").strip()
        if not title:
            raise P.UserError("Name the concept.")
        ok, msg = safety.check_prompt(title)
        if not ok:
            raise P.UserError(msg)
        trigger = str(params.get("trigger") or "").strip()
        if not trigger:
            raise P.UserError("Type a trigger for this concept.")
    caption = str(params.get("caption") or title)
    items = []
    for iid in dict.fromkeys(str(x) for x in (params.get("items") or [])):
        try:
            item = ctx.lib.get(iid)
        except (KeyError, PermissionError) as exc:
            raise P.UserError(str(exc))
        if not still_source_ok(item):
            raise P.UserError("Training uses stills this app made. Uploads, Me photos, and held pictures stay out.")
        if P.has_remote_ancestor(item, P._lineage_get(ctx)):
            raise P.UserError("Anything made by a hosted service, or from a frame of its clip, is never trained on.")
        if kind == "character" and item.get("character") != character_id:
            raise P.UserError("Every still has to belong to this character.")
        try:
            still_age(item, ctx.chars)
        except ValueError as exc:
            raise P.UserError(str(exc))
        items.append(item)
    _train_common(ctx, params.get("base") or "", trigger, items, caption, params.get("resume_ack"))
    if not T.installed(_root()):
        raise P.UserError("The trainer isn't installed yet.")
    stamp = __import__("time").strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9]+", "_", title)[:30].strip("_") or "concept"
    name = "%s_%s_%s" % (safe, params.get("base"), stamp)
    job_dir = os.path.join(ctx.lib.root, "training", name)
    _write_dataset(os.path.join(job_dir, "dataset"), items, ctx.lib.path, caption)
    cfg = T.write_config(job_dir, name, params.get("base"), trigger, os.path.join(job_dir, "dataset"))
    _run(ctx, cfg, job_dir)
    side = {"trigger_words": [trigger], "base": T.BASES[params["base"]]["family"], "source": "Workshop training",
            "title": title, "character": character_id or None,
            "usage": {"author_notes": "Trained in this app. ai-toolkit. No merge and no Civitai publish.",
                      "trained_words": [trigger], "trained_words_listed": True,
                      "strength_model": None, "strength_clip": None, "hash_status": "UNKNOWN",
                      "role": "character" if kind == "character" else "concept",
                      "authorship": "unverified", "examples": [],
                      "accepted": False if kind == "character" else True,
                      "face_hold": kind == "character"}}
    return _finish_lora(ctx, job_dir, name, side)


def job_me_train(ctx, params):
    import pipelines as P
    if P.area() == "adult":
        raise P.UserError(ME_SEX)
    try:
        me_gate("player_andrew_portrait.safetensors", params.get("stated_age"),
                params.get("confirm_player"), params.get("confirm_not_npc"),
                params.get("caption") or "player portrait", "default")
    except ValueError as exc:
        raise P.UserError(str(exc))
    trigger = str(params.get("trigger") or "").strip()
    if not trigger:
        raise P.UserError("Type a trigger for the Me LoRA.")
    if SEXUAL_ME.search(trigger):
        raise P.UserError(ME_SEX)
    # Closed until the in-app camera capture exists: the only stills this trainer ever took came from
    # uploaded photos, and an upload does not show who is in the picture.
    raise P.UserError(ME_CAPTURE_ONLY)


def _root():
    import pipelines_v3 as P3
    return P3.ROOT or os.path.dirname(os.path.dirname(HERE))


def _run(ctx, config_path, job_dir):
    import pipelines as P

    def prog(frac, msg):
        ctx.progress(frac, msg)

    ok = T.run_training(_root(), config_path, prog, lambda: bool(ctx.job.get("cancel")),
                        os.path.join(job_dir, "training_log.txt"))
    if not ok:
        raise P.Cancelled()


def save_preset(record, item):
    if item.get("kind") != "lora:benchmark":
        raise ValueError("Save a cell from this LoRA's benchmark.")
    if item.get("bench_weight") != record.get("name"):
        raise ValueError("That cell belongs to a different weight file.")
    usage = dict(record.get("usage") or {})
    usage["tested_preset"] = {"label": "My tested preset", "strength_model": item.get("bench_strength_model"),
                              "strength_clip": None, "with_triggers": bool(item.get("bench_triggers")),
                              "seed": item.get("bench_seed"), "prompt": item.get("prompt") or "",
                              "source_id": "benchmark:%s:%s" % (item.get("job") or "", item.get("bench_index")),
                              "weight": record.get("name")}
    usage["strength_model"] = item.get("bench_strength_model")
    usage["strength_clip"] = None
    return usage


def avatar_record(lora_record, portrait, stated_age):
    if lora_record.get("identity") != "player_me":
        raise ValueError("The player avatar uses the Me LoRA only.")
    ok, age, msg = safety.require_stated_age({"age": stated_age})
    if not ok:
        raise ValueError(msg)
    if not isinstance(portrait, dict) or portrait.get("role") != "player_me_still":
        raise ValueError("Pick a curated still of Andrew, the player.")
    if int(portrait.get("stated_age") or 0) != int(age):
        raise ValueError("The still's stated age does not match the age you typed.")
    return {"who": "Andrew", "role": "player", "not_npc": True, "sexual": False,
            "lora": lora_record["name"], "portrait": portrait["id"], "stated_age": age, "notice": ME_TEXT}
