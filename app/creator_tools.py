"""Creator path and the studio workflow editor.

Mock engine only. No GPU, no weight download, no RunPod. Me is Andrew, the
player, not an NPC. Fictional adults are 21 or older. A missing strength stays
UNKNOWN. Sending a pack to the island is optional.
"""
import json
import os
import re
import threading

import safety

STAGES = ("still", "refine", "train", "outfit", "film", "island")
PHASES = ("queued", "loading", "rendering", "checking", "saving")
CARD_KINDS = ("still", "edit", "video")
MOCK_CAPTION = "Mock picture. Not a photograph."
STUDIO_SENTENCE = "The studio works on its own, and sending a pack to the island is optional."
DURABLE_ACK = "durable-checkpoint-acknowledged"
REVIEW_ACK = "i-reviewed-this-hold"
PRESS_SURPRISE = "surprise-me"
PRESS_BEACH = "beach-day"
CLOTHING_CONFIRM = "clothing-reference"
WIPE_TEST_STRENGTH = 0.8
CHECKPOINT_RE = re.compile(r"_\d{9}(?:_high_noise|_low_noise)?\.safetensors$")
_UNDRESS = re.compile(
    r"clothing[\s\-]*remov|remove\s+(?:(?:her|his|their|the)\s+)?(?:clothes|clothing|shirt|dress|top|outfit)"
    r"|undress|\bstrip(?:ped|ping)?\b|\bnude\b|\bnaked\b",
    re.I)
_LOCK = threading.Lock()
_ROOT = ""

SURPRISE_LOOK = {
    "id": "calm-stillwater",
    "label": "Calm Stillwater",
    "look": "natural skin, calm expression, linen shirt, warm sand, soft shore light",
    "wardrobe": "jeans_tee",
    "light": "soft daylight",
    "place": "a quiet shore",
    "style": "photo",
}
BEACH_DAY = {
    "id": "beach-day",
    "label": "Beach day",
    "light": "warm daylight",
    "skin": "natural skin",
    "place": "a quiet lagoon shore",
    "wardrobe": "sundress",
    "swimwear": "onepiece",
    "look": "natural skin, warm daylight, a quiet lagoon shore, wearing a one-piece swimsuit",
}
GUIDE_SLOTS = (
    ("identity", "One identity.", ("character", "face", "player")),
    ("style_or_skin", "One style or skin.", ("style", "skin")),
    ("motion_or_light", "One motion or light.", ("motion", "light")),
)
FILM_LIMITS = {
    "touching": "Two people touching is not solved.",
    "sound": "Wan has no sound.",
    "seconds": [2, 5],
}


def set_root(path):
    global _ROOT
    _ROOT = os.path.abspath(path) if path else ""


def studio_root():
    if not _ROOT:
        raise ValueError("The studio folder is not set.")
    return _ROOT


def empty_state():
    return {
        "tray": None,
        "history": [],
        "beach": None,
        "surprise": None,
        "shots": [],
        "reviews": [],
        "face": None,
        "measurements": {},
        "resume": None,
        "pipelines": [],
    }


def _state_file(root=None):
    return os.path.join(root or studio_root(), "creator_state.json")


def load_state(root=None):
    path = _state_file(root)
    if not os.path.isfile(path):
        return empty_state()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return empty_state()
    base = empty_state()
    if isinstance(data, dict):
        for key in base:
            if key in data:
                base[key] = data[key]
    return base


def save_state(state, root=None):
    path = _state_file(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with _LOCK:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=1)
        os.replace(tmp, path)
    return state


def _mutate(root, fn):
    with _LOCK:
        state = load_state(root)
        fn(state)
        path = _state_file(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=1)
        os.replace(tmp, path)
        return state


def stated_age(item, character=None):
    """The age the player stored. Nothing is guessed or raised to 21."""
    ages = []
    records = []
    if isinstance(item, dict):
        dna = item.get("dna")
        if isinstance(dna, dict) and safety.explicit_age_fields(dna):
            records.append(dna)
        elif item.get("stated_age") is not None or item.get("age") is not None:
            records.append({"age": item.get("stated_age", item.get("age"))})
    if isinstance(character, dict) and safety.explicit_age_fields(character):
        records.append(character)
    if not records:
        raise ValueError("Missing stated age: age is missing. Age is not inferred from appearance.")
    for record in records:
        ok, age, msg = safety.require_stated_age(record)
        if not ok:
            raise ValueError(msg)
        ages.append(age)
    if len(set(ages)) != 1:
        raise ValueError("The stated age on this picture does not match the saved person.")
    return ages[0]


def next_stage(stage):
    try:
        index = STAGES.index(stage)
    except ValueError:
        raise ValueError("That step is not on the creator path.")
    if index + 1 >= len(STAGES):
        raise ValueError("Island pack is the last step.")
    return STAGES[index + 1]


def _held(item):
    if not isinstance(item, dict):
        return False
    return bool(item.get("age_flag") or item.get("held") or item.get("body_flag"))


def place(item, stage, character=None):
    if stage not in STAGES:
        raise ValueError("That step is not on the creator path.")
    age = stated_age(item, character)
    if _held(item):
        raise ValueError("A held picture is not carried.")
    if item.get("role") == "scenery" or item.get("place") is True:
        raise ValueError("This photo is a place, not a person.")
    return {
        "item_id": item.get("id") or "",
        "stage": stage,
        "stated_age": age,
        "character": (character or {}).get("id") or item.get("character") or "",
        "identity": item.get("identity") or "",
        "reupload": False,
    }


def carry(item, source, target, character=None):
    """Move the same gallery id to the next step. The file is not copied."""
    if target != next_stage(source):
        raise ValueError("Carry this result to the next step. The drop does not skip a step or the age gate.")
    moved = place(item, target, character)
    if item.get("identity") == "player_me" and target == "outfit":
        raise ValueError("Outfit try-on is not offered for Me. Me is the player, Andrew.")
    moved["from"] = source
    moved["item_id"] = item.get("id") or ""
    return moved


def remember_tray(root, tray):
    def apply(state):
        state["tray"] = tray
        history = list(state.get("history") or [])
        history.append({"stage": tray.get("stage"), "item_id": tray.get("item_id")})
        state["history"] = history[-40:]
    return _mutate(root, apply)


def surprise(press, rng=None):
    """Fill the look on a press. The age is never picked here: a person types it (PRD rail 1).

    `rng` is kept for callers that pass one; nothing is rolled."""
    if press != PRESS_SURPRISE:
        raise ValueError("Surprise me runs only when you press it. A missing age is still rejected.")
    return {"age": None, "look": dict(SURPRISE_LOOK), "source": "press", "stored": False,
            "age_note": "Type the age yourself. Surprise me never picks an age."}


def apply_beach(press):
    if press != PRESS_BEACH:
        raise ValueError("Beach day applies when you press it.")
    preset = dict(BEACH_DAY)
    blob = " ".join(str(preset.get(key) or "") for key in ("label", "light", "skin", "place", "look", "wardrobe"))
    if "blue lagoon" in blob.lower():
        raise ValueError("This preset does not use that title.")
    ok, msg = safety.check_prompt(preset["look"])
    if not ok:
        raise ValueError(msg)
    return preset


def _estimate(samples):
    if not samples:
        return {"text": "No measured estimate yet.", "estimate": False, "seconds": None}
    shown = round(sum(samples) / len(samples), 1)
    unit = "second" if shown == 1 else "seconds"
    return {"seconds": shown, "estimate": True, "text": "About %s %s. This is an estimate." % (shown, unit)}


def record_measurement(state, phase, started, finished):
    if phase not in PHASES:
        raise ValueError("That phase is not on the line.")
    if not isinstance(started, (int, float)) or not isinstance(finished, (int, float)) or isinstance(started, bool):
        raise ValueError("An estimate is shown only after a run has been measured.")
    seconds = float(finished) - float(started)
    if seconds < 0:
        raise ValueError("An estimate is shown only after a run has been measured.")
    bucket = state.setdefault("measurements", {}).setdefault(phase, [])
    bucket.append(round(seconds, 2))
    del bucket[:-20]
    return estimate_payload(state, phase)


def estimate_payload(state, phase=None):
    measurements = state.get("measurements") if isinstance(state.get("measurements"), dict) else {}
    if phase in PHASES and measurements.get(phase):
        row = _estimate(measurements[phase])
        row["phase"] = phase
        return row
    for name in reversed(PHASES):
        if measurements.get(name):
            row = _estimate(measurements[name])
            row["phase"] = name
            row["text"] = "Last measured phase %s. %s" % (name, row["text"])
            return row
    return {"text": "No measured estimate yet.", "estimate": False, "seconds": None, "phase": phase or ""}


def live_guide(items):
    rows = []
    for slot, label, roles in GUIDE_SLOTS:
        names = []
        for item in items or []:
            if not isinstance(item, dict) or item.get("blocked"):
                continue
            if (item.get("role") or "") in roles:
                names.append(item.get("title") or item.get("name") or "LoRA")
        count = len(names)
        state = "open" if count == 0 else "filled" if count == 1 else "over"
        rows.append({"slot": slot, "label": label, "count": count, "state": state, "names": names})
    return rows


def outfit_source_ok(item, character, text, confirm):
    if confirm != CLOTHING_CONFIRM:
        raise ValueError("Confirm this is a clothing reference. This try-on does not remove clothes from a photo of a real person.")
    if not isinstance(item, dict):
        raise ValueError("Pick a still this app made of a fictional adult.")
    if item.get("identity") == "player_me" or str(item.get("role") or "").startswith("player_me"):
        raise ValueError("Outfit try-on is not offered for Me. Me is the player, Andrew, not a partner.")
    if item.get("real_person") is True or (isinstance(item.get("dna"), dict) and item["dna"].get("real_person") is True):
        raise ValueError("Outfit try-on does not use a photo of a real person, and it does not remove their clothes.")
    if item.get("role") != "made" or item.get("kind") == "upload":
        raise ValueError("Outfit try-on uses a still this app made. It does not remove clothes from a photo of a real person.")
    if _held(item) or item.get("age_check") not in ("ok",):
        raise ValueError("The age check has to clear this still before a try-on.")
    if _UNDRESS.search(str(text or "")):
        raise ValueError("This try-on does not remove clothing, and it does not remove clothing from a photo of a real person.")
    ok, msg = safety.check_prompt(str(text or ""))
    if not ok:
        raise ValueError(msg)
    return stated_age(item, character)


def clothing_ref_ok(item):
    if not isinstance(item, dict) or item.get("type") != "image":
        raise ValueError("Add a clothing reference.")
    if item.get("role") != "clothing":
        raise ValueError("The second picture has to be a clothing reference, not a person and not a place.")
    if item.get("identity") == "player_me" or item.get("real_person") is True:
        raise ValueError("A photo of a real person is not a clothing reference.")
    blob = " ".join(str(item.get(key) or "") for key in ("title", "caption", "prompt"))
    if _UNDRESS.search(blob):
        raise ValueError("This try-on does not remove clothing from a photo of a real person.")
    return item.get("id") or ""


def wipe_strength(record):
    usage = record.get("usage") if isinstance(record, dict) and isinstance(record.get("usage"), dict) else {}
    preset = usage.get("tested_preset") if isinstance(usage.get("tested_preset"), dict) else None
    if preset and preset.get("strength_model") not in (None, "", "UNKNOWN"):
        return float(preset["strength_model"]), (
            "My tested preset. Model strength %s. Clip strength UNKNOWN. This is not a new recommendation."
            % preset["strength_model"])
    return WIPE_TEST_STRENGTH, "Test strength 0.8. This is not a recommendation. Clip strength UNKNOWN."


def _score(score, status, reason):
    if score is None:
        label = "Mock score unavailable. This is not a measurement from a GPU."
    else:
        label = "Mock score %s. This is not a measurement from a GPU." % score
    return {
        "score": score,
        "status": status,
        "held": status != "match",
        "reason": reason,
        "mock": True,
        "label": label,
    }


def face_check(reference, result):
    if not isinstance(reference, dict) or not isinstance(result, dict):
        return _score(None, "unsure", "The check needs a reference and a result, so this LoRA stays held.")
    if reference.get("id") and reference.get("id") == result.get("id"):
        row = _score(90, "match", "The result is the same still as the reference.")
    elif (reference.get("identity") == "player_me") != (result.get("identity") == "player_me"):
        row = _score(20, "miss", "Me is the player, Andrew, not an NPC. This face does not match.")
    elif reference.get("age_flag") or result.get("age_flag"):
        row = _score(40, "miss", "The age check flagged a picture, so the face check holds the LoRA.")
    elif reference.get("age_check") not in (None, "", "ok") or result.get("age_check") not in (None, "", "ok"):
        row = _score(55, "unsure", "The check is unsure, so the LoRA stays held.")
    elif reference.get("character") and result.get("character") and reference.get("character") != result.get("character"):
        row = _score(32, "miss", "Identity drift. The result does not match the reference.")
    elif reference.get("identity") == "player_me" and reference.get("stated_age") != result.get("stated_age"):
        row = _score(55, "unsure", "The check is unsure, so the LoRA stays held.")
    elif reference.get("identity") == "player_me":
        row = _score(88, "match", "Mock score matches Andrew, the player.")
    else:
        row = _score(86, "match", "Mock score matches the reference.")
    row["reference_id"] = reference.get("id") or ""
    row["result_id"] = result.get("id") or ""
    row["character"] = reference.get("character") or result.get("character") or ""
    if row["score"] is None:
        row["label"] = "Mock score unavailable. This is not a measurement from a GPU."
    return row


def accept_lora(record, check):
    usage = dict(record.get("usage") or {})
    needs = record.get("identity") == "player_me" or usage.get("role") in ("character", "player") or usage.get("face_hold")
    if needs:
        if not isinstance(check, dict) or check.get("held") or check.get("status") != "match":
            reason = check.get("reason") if isinstance(check, dict) else ""
            raise ValueError(reason or "Held. The face check has to match before this LoRA is accepted.")
        kept = {key: check.get(key) for key in ("score", "status", "held", "reason", "label", "reference_id", "result_id")}
        usage["face_check"] = kept
        usage["face_hold"] = False
        usage["accepted"] = True
    else:
        usage["accepted"] = True
        usage["face_hold"] = False
    return usage


def pack_status(character, item, face, reviews):
    defects = []
    try:
        if isinstance(character, dict):
            ok, _age, msg = safety.require_stated_age(character)
            if not ok:
                defects.append({
                    "id": "failed_age", "text": msg, "review": False, "stated_under_21": True,
                })
        elif item is None:
            defects.append({
                "id": "failed_age",
                "text": "Missing stated age: age is missing.",
                "review": False,
                "stated_under_21": True,
            })
    except ValueError as exc:
        defects.append({"id": "failed_age", "text": str(exc), "review": False, "stated_under_21": True})
    if isinstance(item, dict) and (item.get("age_flag") or item.get("age_check") not in (None, "", "ok")):
        if not any(row["id"] == "failed_age" for row in defects):
            flagged = bool(item.get("age_flag") or item.get("age_check") == "flag")
            defects.append({
                "id": "failed_age",
                "text": "The age check did not clear this picture.",
                "review": flagged,
                "stated_under_21": False,
            })
    if isinstance(face, dict) and face.get("held") and character and face.get("character") == character.get("id"):
        defects.append({
            "id": "identity_drift",
            "text": face.get("reason") or "Identity drift. The face check holds this pack.",
            "review": True,
            "stated_under_21": False,
        })
    appearance = item.get("appearance_check") if isinstance(item, dict) and isinstance(item.get("appearance_check"), dict) else {}
    if isinstance(item, dict) and (item.get("body_flag") or appearance.get("body") == "flag"):
        defects.append({
            "id": "body_flag",
            "text": "A body check flagged this picture.",
            "review": True,
            "stated_under_21": False,
        })
    active = []
    item_id = item.get("id") if isinstance(item, dict) else ""
    character_id = character.get("id") if isinstance(character, dict) else ""
    for defect in defects:
        reviewed = False
        for review in reviews or []:
            if review.get("id") != defect["id"] or review.get("ack") != REVIEW_ACK:
                continue
            if review.get("character") not in ("", character_id):
                continue
            if item_id and review.get("item_id") not in ("", item_id):
                continue
            reviewed = True
        if reviewed and defect.get("review") and not defect.get("stated_under_21"):
            continue
        active.append(defect)
    message = ""
    if active:
        message = "This pack is held. " + " ".join(row["text"] for row in active)
    return {"held": bool(active), "defects": active, "message": message}


def review_defect(defects, defect_id, ack, character_id, item_id):
    if ack != REVIEW_ACK:
        raise ValueError("Review this hold before the pack can be sent.")
    found = next((row for row in defects or [] if row.get("id") == defect_id), None)
    if not found:
        raise ValueError("That hold is not on this pack.")
    if not found.get("review") or found.get("stated_under_21"):
        raise ValueError("A failed stated age is not sent. Review does not change the age.")
    return {"id": defect_id, "ack": ack, "character": character_id or "", "item_id": item_id or ""}


def _card_id(value, index, seen):
    text = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", text):
        text = "card-%d" % (index + 1)
    base = text
    n = 2
    while text in seen:
        text = "%s-%d" % (base, n)
        n += 1
    seen.add(text)
    return text


def normalize_cards(cards):
    import catalog
    if not isinstance(cards, list) or not cards:
        raise ValueError("Add at least one card.")
    if len(cards) > 8:
        raise ValueError("A pipeline can have up to 8 cards.")
    seen = set()
    out = []
    allowed = set(catalog.WORKSHOP_CLOTHED)
    for index, raw in enumerate(cards):
        if not isinstance(raw, dict):
            raise ValueError("A card has to be a still, an edit, or a video.")
        kind = raw.get("kind")
        if kind not in CARD_KINDS:
            raise ValueError("A card has to be a still, an edit, or a video.")
        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("Each card needs a prompt.")
        if len(prompt) > 300:
            raise ValueError("That prompt is too long.")
        ok, msg = safety.check_prompt(prompt)
        if not ok:
            raise ValueError(msg)
        if kind == "edit" and _UNDRESS.search(prompt):
            raise ValueError("This edit does not remove clothing from a photo of a real person.")
        card = {"id": _card_id(raw.get("id"), index, seen), "kind": kind, "prompt": prompt}
        if kind == "still":
            wardrobe = str(raw.get("wardrobe") or "sundress")
            if wardrobe not in allowed:
                raise ValueError("Pick a wardrobe this page offers.")
            card["wardrobe"] = wardrobe
        if kind == "video":
            seconds = raw.get("seconds")
            if seconds not in (2, 5, "2", "5"):
                raise ValueError("Choose 2 or 5 seconds.")
            card["seconds"] = int(seconds)
            motion = str(raw.get("motion_lora") or "").strip()
            if motion:
                card["motion_lora"] = motion
        out.append(card)
    return out


def wants_island(value):
    return value is True


def export_workflow(cards):
    """ComfyUI API JSON. One node per card. The player does not wire nodes."""
    normalized = normalize_cards(cards)
    workflow = {}
    for index, card in enumerate(normalized):
        kind = card["kind"]
        class_type = {"still": "CLIPTextEncode", "edit": "TextEncodeQwenImageEditPlus", "video": "WanImageToVideo"}[kind]
        inputs = {"text": card["prompt"], "_studio_step": kind, "_studio_id": card["id"]}
        if kind == "still":
            inputs["_studio_wardrobe"] = card["wardrobe"]
        if kind == "video":
            inputs["_studio_seconds"] = card["seconds"]
            if card.get("motion_lora"):
                inputs["_studio_motion"] = card["motion_lora"]
        workflow[str(index + 1)] = {"class_type": class_type, "inputs": inputs}
        workflow[str((index + 1) * 10)] = {"class_type": "KSampler", "inputs": {"seed": index + 1}}
    ok, msg = safety.check_workflow(workflow)
    if not ok:
        raise ValueError(msg)
    return workflow


def _ordered_nodes(workflow):
    def key(nid):
        return (0, int(nid)) if str(nid).isdigit() else (1, str(nid))
    return [(nid, workflow[nid]) for nid in sorted(workflow, key=key) if isinstance(workflow.get(nid), dict)]


def _kind_of(node):
    inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
    step = inputs.get("_studio_step")
    if step in CARD_KINDS:
        return step
    class_type = str(node.get("class_type") or "")
    if re.search(r"wan|imagetovideo|videocombine", class_type, re.I):
        return "video"
    if re.search(r"edit|qwen", class_type, re.I):
        return "edit"
    if re.search(r"cliptext|unetloader|ksampler|emptylatent", class_type, re.I):
        return "still"
    return ""


def import_workflow(workflow):
    if isinstance(workflow, dict) and isinstance(workflow.get("prompt"), dict):
        workflow = workflow["prompt"]
    if isinstance(workflow, dict) and isinstance(workflow.get("prompts"), list):
        cards = []
        for prompt in workflow["prompts"]:
            cards.extend(import_workflow(prompt))
        return normalize_cards(cards)
    if not isinstance(workflow, dict) or not workflow:
        raise ValueError("That isn't an API-format workflow.")
    ok, msg = safety.check_workflow(workflow)
    if not ok:
        raise ValueError(msg)
    ordered = _ordered_nodes(workflow)
    marked = []
    for _nid, node in ordered:
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        if inputs.get("_studio_step") in CARD_KINDS:
            marked.append(node)
    if marked:
        raw = []
        for node in marked:
            inputs = node["inputs"]
            card = {
                "id": inputs.get("_studio_id") or "",
                "kind": inputs.get("_studio_step"),
                "prompt": inputs.get("text") or inputs.get("prompt") or "",
            }
            if card["kind"] == "still":
                card["wardrobe"] = inputs.get("_studio_wardrobe") or "sundress"
            if card["kind"] == "video":
                card["seconds"] = inputs.get("_studio_seconds") if inputs.get("_studio_seconds") in (2, 5) else 2
                if inputs.get("_studio_motion"):
                    card["motion_lora"] = inputs.get("_studio_motion")
            raw.append(card)
        return normalize_cards(raw)
    kind = "still"
    texts = []
    for _nid, node in ordered:
        found = _kind_of(node)
        if found == "video":
            kind = "video"
        elif found == "edit" and kind != "video":
            kind = "edit"
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        for key in ("text", "prompt"):
            value = inputs.get(key)
            if isinstance(value, str) and value.strip() and not str(value).startswith("_"):
                texts.append(value.strip())
    prompt = max(texts, key=len) if texts else "Imported step"
    card = {"kind": kind, "prompt": prompt}
    if kind == "still":
        card["wardrobe"] = "sundress"
    if kind == "video":
        card["seconds"] = 2
    return normalize_cards([card])


def normalize_shots(shots):
    if not isinstance(shots, list):
        raise ValueError("The shot board is a list.")
    if len(shots) > 12:
        raise ValueError("The board can hold 12 shots.")
    seen = set()
    out = []
    for index, raw in enumerate(shots):
        if not isinstance(raw, dict):
            raise ValueError("Each shot needs a prompt, a motion LoRA, and a duration.")
        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("Each shot needs a prompt.")
        ok, msg = safety.check_prompt(prompt)
        if not ok:
            raise ValueError(msg)
        seconds = raw.get("seconds")
        if seconds not in (2, 5, "2", "5"):
            raise ValueError("Choose 2 or 5 seconds.")
        motion = str(raw.get("motion_lora") or "").strip()
        if not motion:
            raise ValueError("Pick a motion LoRA for this shot.")
        out.append({
            "id": _card_id(raw.get("id"), index, seen),
            "prompt": prompt,
            "motion_lora": motion,
            "seconds": int(seconds),
            "result": str(raw.get("result") or ""),
        })
    return out


def reorder_ids(rows, order):
    by = {row["id"]: row for row in rows or []}
    if not isinstance(order, list) or len(order) != len(by) or set(order) != set(by):
        raise ValueError("Reorder uses these same cards.")
    return [by[item_id] for item_id in order]


def motion_record_ok(record):
    if not isinstance(record, dict):
        raise ValueError("Pick a motion LoRA for this shot.")
    if record.get("blocked") or record.get("player_only") or record.get("identity") == "player_me":
        raise ValueError("That LoRA cannot be a motion LoRA here. Me is the player, not a character LoRA.")
    return record.get("name") or ""


def _rel(root, path):
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    if rel.startswith("..") or os.path.isabs(rel):
        raise ValueError("That file is outside the studio folder.")
    return rel.replace("\\", "/")


def _safe(root, rel):
    rel = str(rel or "").replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        raise ValueError("That file is outside the studio folder.")
    path = os.path.abspath(os.path.join(root, rel))
    root_abs = os.path.abspath(root)
    if path != root_abs and not path.startswith(root_abs + os.sep):
        raise ValueError("That file is outside the studio folder.")
    return path


def _job_dir(path, training_root):
    cur = os.path.dirname(os.path.abspath(path))
    root = os.path.abspath(training_root)
    while cur == root or cur.startswith(root + os.sep):
        if os.path.isfile(os.path.join(cur, "config.json")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return ""


def _base_of(config_path):
    import trainer as T
    with open(config_path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    process = ((cfg.get("config") or {}).get("process") or [{}])[0]
    model = process.get("model") or {}
    needle = model.get("name_or_path")
    for base_id, spec in T.BASES.items():
        if (spec.get("model") or {}).get("name_or_path") == needle:
            return base_id
    return ""


def list_checkpoints(root):
    training = os.path.join(root, "training")
    found = []
    if not os.path.isdir(training):
        return found
    for dirpath, dirnames, filenames in os.walk(training):
        dirnames[:] = [name for name in dirnames if name != "_trash" and not name.startswith(".")]
        for filename in filenames:
            if not CHECKPOINT_RE.search(filename):
                continue
            path = os.path.join(dirpath, filename)
            job_dir = _job_dir(path, training)
            if not job_dir:
                continue
            config = os.path.join(job_dir, "config.json")
            dataset = os.path.join(job_dir, "dataset")
            if not os.path.isdir(dataset):
                continue
            try:
                base = _base_of(config)
                found.append({
                    "id": _rel(root, path),
                    "name": filename,
                    "dataset": _rel(root, dataset),
                    "base": base,
                    "config": _rel(root, config),
                    "parent_checkpoint": _rel(root, path),
                    "durable": True,
                })
            except (OSError, ValueError):
                continue
    found.sort(key=lambda row: row["id"])
    return found


def resume_record(root, rel_checkpoint, ack):
    import lora_workshop as W
    if ack != DURABLE_ACK:
        raise ValueError("Acknowledge this durable checkpoint before resume. " + W.RESUME_TEXT)
    path = _safe(root, rel_checkpoint)
    if not os.path.isfile(path) or not CHECKPOINT_RE.search(os.path.basename(path)):
        raise ValueError(W.RESUME_TEXT)
    training = os.path.join(root, "training")
    job_dir = _job_dir(path, training)
    if not job_dir:
        raise ValueError(W.RESUME_TEXT)
    config = os.path.join(job_dir, "config.json")
    dataset = os.path.join(job_dir, "dataset")
    if not os.path.isfile(config) or not os.path.isdir(dataset):
        raise ValueError("Resume records the dataset, the base, the config, and the parent checkpoint.")
    base = _base_of(config)
    if not base:
        raise ValueError("The base was not recorded on this checkpoint.")
    return {
        "dataset": _rel(root, dataset),
        "base": base,
        "config": _rel(root, config),
        "parent_checkpoint": _rel(root, path),
        "acknowledged": True,
        "inference_lora": False,
    }


def validate_resume(root, params):
    if not isinstance(params, dict):
        raise ValueError("Acknowledge this durable checkpoint before resume.")
    return resume_record(root, params.get("checkpoint"), params.get("ack"))


def job_outfit(ctx, params):
    import pipelines as P
    P.require_checker_on()
    try:
        item = ctx.lib.get(str(params.get("image") or ""))
    except (KeyError, PermissionError) as exc:
        raise P.UserError(str(exc))
    try:
        ref = ctx.lib.get(str(params.get("ref") or ""))
    except (KeyError, PermissionError) as exc:
        raise P.UserError(str(exc))
    character = None
    if item.get("character"):
        try:
            character = ctx.chars.get(item["character"])
        except Exception:
            character = None
    try:
        outfit_source_ok(item, character, params.get("text") or "", params.get("confirm"))
        clothing_ref_ok(ref)
    except ValueError as exc:
        raise P.UserError(str(exc))
    P.job_edit(ctx, {
        "image": item["id"],
        "op": "outfit",
        "ref": ref["id"],
        "text": str(params.get("text") or "linen shirt"),
        "count": 1,
        "reference_strength": 0.6,
    })
    ctx.job["message"] = "Done. Outfit try-on used the still and the clothing reference. No clothes were removed from a real photo."


def job_compare(ctx, params):
    import comfy_client as cc
    import lora_workshop as W
    import pipelines as P
    P.require_checker_on()
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
    try:
        seed = int(params.get("seed"))
    except (TypeError, ValueError):
        raise P.UserError("The seed has to be a whole number. The wipe uses that same seed.")
    name = str(params.get("name") or "")
    lib = P.LORA_LIB
    if lib is None or not lib.available():
        raise P.UserError("The LoRA folder is not on this PC.")
    try:
        record = lib.check_usable(name, "zimage", P.area())
    except ValueError as exc:
        raise P.UserError(str(exc))
    if not record:
        raise P.UserError("Pick a LoRA that is in the library.")
    strength, note = wipe_strength(record)
    spoken = safety.add_adult_hint(prompt)
    ctx.steps(2)
    for index, with_lora in enumerate((False, True)):
        wf = cc.load_workflow("image_zimage_turbo_api.json")
        cc.set_in(wf, "POSITIVE", text=spoken)
        if cc.has_title(wf, "NEGATIVE"):
            cc.set_in(wf, "NEGATIVE", text=safety.safe_negative(""))
        cc.set_in(wf, "SIZE", width=384, height=384)
        cc.set_seed(wf, seed)
        if with_lora:
            W._attach_lora(wf, name, strength)
        res = ctx.run(wf, "Compare %d of 2" % (index + 1))
        for path in P.first(res):
            ctx.add(path, "lora:compare", title=MOCK_CAPTION, prompt=spoken, stated_age=age,
                    dna={"age": age, "stated_age": age, "age_source": "stated"},
                    compare_seed=seed, compare_lora=with_lora,
                    compare_strength_model=strength if with_lora else None,
                    compare_strength_clip="UNKNOWN", compare_note=note,
                    compare_weight=name if with_lora else "",
                    provenance={"mock": True, "not_a_photograph": True, "seed": seed,
                                "with_lora": with_lora, "strength_clip": "UNKNOWN"})
        ctx.next_step()
    ctx.job["message"] = "Done. " + note + " " + MOCK_CAPTION


def job_shot(ctx, params):
    import films
    import pipelines as P
    P.require_checker_on()
    motion = str(params.get("motion_lora") or "")
    lib = P.LORA_LIB
    if lib is None or not motion:
        raise P.UserError("Pick a motion LoRA for this shot.")
    try:
        motion_record_ok(lib.get(motion))
    except (ValueError, OSError) as exc:
        raise P.UserError(str(exc) or "Pick a motion LoRA for this shot.")
    text = str(params.get("text") or params.get("prompt") or "")
    film_params = {"image": params.get("image"), "seconds": params.get("seconds"), "text": text}
    films.job_film(ctx, film_params)
    result_id = (ctx.job.get("results") or [""])[-1]
    ctx.job["shot"] = {
        "motion_lora": motion,
        "seconds": int(params.get("seconds") or 0),
        "prompt": text,
        "result": result_id,
        "weights_downloaded": False,
        "sound": False,
    }
    ctx.job["message"] = "Done. " + FILM_LIMITS["sound"] + " " + FILM_LIMITS["touching"] + " The mock did not download a weight file."


def _fresh(ctx, before):
    now = list(ctx.job.get("results") or [])
    return [item_id for item_id in now if item_id not in before]


def _latest_image(ctx, ids):
    for item_id in reversed(ids):
        try:
            item = ctx.lib.get(item_id)
        except (KeyError, PermissionError):
            continue
        if item.get("type") == "image" and not item.get("age_flag"):
            return item
    return None


def job_pipeline(ctx, params):
    import films
    import pipelines as P
    import stills
    P.require_checker_on()
    try:
        character = ctx.chars.get(str(params.get("character") or ""))
    except Exception:
        character = None
    if not isinstance(character, dict):
        raise P.UserError("Save a fictional adult first. The age is not guessed.")
    ok, age, msg = safety.require_stated_age({"age": params.get("stated_age")})
    if not ok:
        raise P.UserError(msg)
    ok, saved, msg = safety.require_stated_age(character)
    if not ok:
        raise P.UserError(msg)
    if age != saved:
        raise P.UserError("The stated age stays as it was saved. It is not edited on this step.")
    try:
        cards = normalize_cards(params.get("cards") or [])
    except ValueError as exc:
        raise P.UserError(str(exc))
    island = wants_island(params.get("island"))
    if island:
        face = None
        reviews = []
        if _ROOT:
            state = load_state(_ROOT)
            face = state.get("face")
            reviews = state.get("reviews") or []
        report = pack_status(character, None, face, reviews)
        if report["held"]:
            raise P.UserError(report["message"])
    current = None
    ctx.progress(0.02, "loading")
    for card in cards:
        before = set(ctx.job.get("results") or [])
        ctx.progress(0.1, "rendering")
        if card["kind"] == "still":
            stills.job_workshop_still(ctx, {
                "character": character["id"],
                "look": card["prompt"],
                "wardrobe": card["wardrobe"],
            })
            image = _latest_image(ctx, _fresh(ctx, before))
            if image:
                current = image["id"]
        elif card["kind"] == "edit":
            if not current:
                raise P.UserError("This edit needs a still from the previous card. You do not upload it again.")
            P.job_edit(ctx, {
                "image": current,
                "op": "outfit",
                "text": card["prompt"],
                "item": card.get("wardrobe") or "",
                "count": 1,
            })
            image = _latest_image(ctx, _fresh(ctx, before))
            if image:
                current = image["id"]
        else:
            if not current:
                raise P.UserError("This video needs a still from the previous card. You do not upload it again.")
            films.job_film(ctx, {"image": current, "seconds": card["seconds"], "text": card["prompt"]})
        ctx.progress(0.8, "checking")
    if island:
        import pipelines_v3
        pipelines_v3.job_export_godot(ctx, {"character": character["id"]})
        ctx.job["message"] = "Done. The studio ran this pipeline on its own. A pack was also sent because you asked for it."
    else:
        ctx.job["message"] = "Done. The studio ran this pipeline on its own. Sending a pack to the island was left off."


def job_resume(ctx, params):
    import lora_workshop as W
    import pipelines as P
    import trainer as T
    P.require_checker_on()
    if not _ROOT:
        raise P.UserError("The studio folder is not set.")
    try:
        record = validate_resume(_ROOT, params)
    except ValueError as exc:
        raise P.UserError(str(exc))
    config = _safe(_ROOT, record["config"])
    dataset = _safe(_ROOT, record["dataset"])
    if not T.installed(W._root()):
        raise P.UserError("The trainer isn't installed yet.")
    if len([name for name in os.listdir(dataset) if name.endswith(".png")]) < T.MIN_PICTURES:
        raise P.UserError("The dataset on this checkpoint is incomplete.")
    job_dir = os.path.dirname(config)
    log_path = os.path.join(job_dir, "resume_log.txt")

    def prog(frac, msg):
        ctx.progress(frac, msg or "rendering")

    ok = T.run_training(W._root(), config, prog, lambda: bool(ctx.job.get("cancel")), log_path)
    if not ok:
        raise P.Cancelled()
    state = load_state(_ROOT)
    state["resume"] = record
    save_state(state, _ROOT)
    ctx.job["resume"] = record
    ctx.job["message"] = (
        "Done. Resume recorded the dataset, the base, the config, and the parent checkpoint. " + W.RESUME_TEXT)
