"""Creator path, face hold, shot board, and the studio workflow editor."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
os.environ.setdefault("EASY_STUDIO_LORA_OFFLINE", "1")

import creator_tools as C  # noqa: E402
import safety  # noqa: E402


def _still(item_id="still1", age=32, character="char-1"):
    return {"id": item_id, "type": "image", "role": "made", "kind": "still", "stated_age": age,
            "character": character, "age_check": "ok", "identity": ""}


def unit(check):
    print("\n[33] Creator tools")
    item = _still()
    moved = C.carry(item, "still", "refine")
    check("carry keeps the same picture id", moved["item_id"] == "still1" and moved["reupload"] is False and moved["stated_age"] == 32)
    try:
        C.carry(item, "still", "train")
        check("carry does not skip a step", False)
    except ValueError as exc:
        check("carry does not skip a step", "does not skip" in str(exc))
    try:
        C.carry(_still(age=20), "still", "refine")
        check("carry rejects age 20", False)
    except ValueError as exc:
        check("carry rejects age 20", "under 21" in str(exc).lower())
    try:
        C.carry({"id": "x", "role": "made", "type": "image"}, "still", "refine")
        check("carry rejects a missing age", False)
    except ValueError as exc:
        check("carry rejects a missing age", "missing" in str(exc).lower())
    me = _still()
    me["identity"] = "player_me"
    me["role"] = "player_me_still"
    try:
        C.carry(me, "train", "outfit")
        check("outfit is not offered for Me", False)
    except ValueError as exc:
        check("outfit is not offered for Me", "Me" in str(exc))
    chain = item
    stage = "still"
    for target in ("refine", "train", "outfit", "film", "island"):
        chain_row = C.carry(chain, stage, target)
        check("carry %s keeps the id" % target, chain_row["item_id"] == "still1")
        stage = target

    class Boom:
        def randint(self, _a, _b):
            raise AssertionError("rolled")
    try:
        C.surprise("", Boom())
        check("surprise does not roll without a press", False)
    except ValueError as exc:
        check("surprise does not roll without a press", "only when you press" in str(exc))
    rolls = [C.surprise(C.PRESS_SURPRISE) for _ in range(5)]
    check("surprise never picks an age (PRD rail 1: ages are typed)", all(r["age"] is None and r["stored"] is False for r in rolls))
    check("surprise never rolls even with a random source", C.surprise(C.PRESS_SURPRISE, Boom())["age"] is None)
    look = C.surprise(C.PRESS_SURPRISE)["look"]
    check("surprise uses the calm Stillwater look", look["label"] == "Calm Stillwater" and "linen" in look["look"])
    beach = C.apply_beach(C.PRESS_BEACH)
    blob = " ".join(str(beach[key]) for key in beach)
    check("beach day is warm daylight and natural skin", beach["light"] == "warm daylight" and beach["skin"] == "natural skin" and "swimsuit" in beach["look"])
    check("beach day does not use the lagoon film title", "blue lagoon" not in blob.lower())

    made = _still()
    cloth = {"id": "cloth1", "type": "image", "role": "clothing", "title": "linen shirt"}
    check("outfit gate accepts a fictional still", C.outfit_source_ok(made, {"id": "char-1", "age": 32}, "linen shirt", C.CLOTHING_CONFIRM) == 32)
    check("clothing reference is the second picture", C.clothing_ref_ok(cloth) == "cloth1")
    try:
        C.outfit_source_ok(made, None, "remove her clothes", C.CLOTHING_CONFIRM)
        check("try-on refuses clothing removal", False)
    except ValueError as exc:
        check("try-on refuses clothing removal", "does not remove" in str(exc).lower())
    upload = dict(made, role="my_character", kind="upload")
    try:
        C.outfit_source_ok(upload, None, "linen shirt", C.CLOTHING_CONFIRM)
        check("try-on refuses an uploaded person", False)
    except ValueError as exc:
        check("try-on refuses an uploaded person", "real person" in str(exc).lower())

    same = C.face_check(made, dict(made))
    check("the same still matches", same["status"] == "match" and same["held"] is False and "Mock score" in same["label"])
    other = C.face_check(made, _still("other", character="char-2"))
    check("a different person is identity drift", other["status"] == "miss" and other["held"] is True and "drift" in other["reason"].lower())
    unsure = C.face_check(dict(made, id="ref-u", age_check="unchecked"), dict(made, id="out-u", age_check="unchecked"))
    check("an unsure face check holds", unsure["status"] == "unsure" and unsure["held"] is True)
    record = {"name": "easy_studio/hero.safetensors", "identity": "", "usage": {"role": "character", "face_hold": True}}
    try:
        C.accept_lora(record, other)
        check("a held face check cannot be accepted", False)
    except ValueError as exc:
        check("a held face check cannot be accepted", "drift" in str(exc).lower() or "held" in str(exc).lower())
    accepted = C.accept_lora(record, same)
    check("a matching face check can be accepted", accepted["accepted"] is True and accepted["face_hold"] is False)

    young = {"id": "young", "age": 18}
    held = C.pack_status(young, None, None, [])
    check("a failed age holds the pack", held["held"] and held["defects"][0]["id"] == "failed_age" and held["defects"][0]["review"] is False)
    try:
        C.review_defect(held["defects"], "failed_age", C.REVIEW_ACK, "young", "")
        check("review does not send an under-21 age", False)
    except ValueError as exc:
        check("review does not send an under-21 age", "does not change the age" in str(exc))
    adult = {"id": "char-1", "age": 32}
    drift = C.pack_status(adult, made, dict(other, character="char-1"), [])
    check("identity drift holds the pack", any(row["id"] == "identity_drift" for row in drift["defects"]))
    review = C.review_defect(drift["defects"], "identity_drift", C.REVIEW_ACK, "char-1", "still1")
    cleared = C.pack_status(adult, made, dict(other, character="char-1"), [review])
    check("an explicit review clears identity drift", not any(row["id"] == "identity_drift" for row in cleared["defects"]))
    flagged = dict(made, body_flag=True)
    body = C.pack_status(adult, flagged, None, [])
    check("a flagged body check holds the pack", any(row["id"] == "body_flag" and row["review"] for row in body["defects"]))

    empty = C.estimate_payload({"measurements": {}})
    check("an unmeasured phase has no number", empty["estimate"] is False and not any(ch.isdigit() for ch in empty["text"]))
    state = {"measurements": {}}
    labeled = C.record_measurement(state, "rendering", 10, 12.2)
    check("a measured phase is labeled an estimate", labeled["estimate"] is True and "estimate" in labeled["text"] and "2.2" in labeled["text"])

    cards = [
        {"id": "a", "kind": "still", "prompt": "natural skin, linen shirt", "wardrobe": "sundress"},
        {"id": "b", "kind": "edit", "prompt": "a linen shirt"},
        {"id": "c", "kind": "video", "prompt": "walks slowly along the shore", "seconds": 2, "motion_lora": "easy_studio/clay.safetensors"},
    ]
    workflow = C.export_workflow(cards)
    ok, msg = safety.check_workflow(workflow)
    check("exported API JSON passes the workflow check", ok, msg)
    restored = C.import_workflow(workflow)
    check("import restores the cards", [row["kind"] for row in restored] == ["still", "edit", "video"]
          and restored[0]["prompt"] == cards[0]["prompt"] and restored[2]["seconds"] == 2)
    check("the studio sentence is plain", C.STUDIO_SENTENCE == "The studio works on its own, and sending a pack to the island is optional.")
    check("island send is off unless explicitly true", C.wants_island(None) is False and C.wants_island(False) is False and C.wants_island(True) is True)
    try:
        C.import_workflow({"1": {"class_type": "ReActorFaceSwap", "inputs": {"text": "a fictional adult"}}})
        check("import refuses a face-swap node", False)
    except ValueError as exc:
        check("import refuses a face-swap node", "Blocked" in str(exc) or "face" in str(exc).lower())
    shots = C.normalize_shots([
        {"id": "s1", "prompt": "walks slowly", "motion_lora": "easy_studio/move.safetensors", "seconds": 5},
        {"id": "s2", "prompt": "stands on the shore", "motion_lora": "easy_studio/move.safetensors", "seconds": 2},
    ])
    flipped = C.reorder_ids(shots, ["s2", "s1"])
    check("shots can be reordered", [row["id"] for row in flipped] == ["s2", "s1"])


def e2e(a, mock_url, comfy_dir):
    import io
    from PIL import Image
    check = a.check
    print("\n[34] Creator screens")
    before = a.get("/api/creator/state").json()
    check("surprise has not fired", before.get("surprise") is None and before.get("beach") is None)
    check("the workflow sentence is on the API", before.get("sentence") == C.STUDIO_SENTENCE)
    pressed = a.post("/api/creator/surprise", json={"press": "surprise-me"})
    check("a press fills the look and leaves the age to be typed", pressed.status_code == 200 and pressed.json().get("age") is None
          and pressed.json().get("source") == "press" and pressed.json().get("look", {}).get("label") == "Calm Stillwater", pressed.text[:300])
    after = a.get("/api/creator/state").json()
    check("surprise stores no age", isinstance(after.get("surprise"), dict) and "age" not in after["surprise"], str(after.get("surprise"))[:200])
    check("surprise without a press does nothing", a.post("/api/creator/surprise", json={}).status_code == 400)

    character = a.post("/api/characters", json={"name": "Sable", "gender": "woman", "style": "photo", "age": 34}).json()
    still = a.job("workshop_still", {"character": character["id"], "wardrobe": "sundress", "look": "natural skin, linen shirt"})
    check("a still exists to carry", still.get("status") == "done" and still.get("results"), still.get("error"))
    if not still.get("results"):
        return
    item_id = still["results"][0]["id"]
    me = a.get("/api/loras/workshop/me").json()
    cloth_buf = io.BytesIO()
    Image.new("RGB", (64, 80), (180, 40, 40)).save(cloth_buf, "PNG")
    cloth = a.post("/api/upload", files={"file": ("linen.png", cloth_buf.getvalue(), "image/png")}, data={"role": "clothing", "confirm": "yes"})
    check("a clothing reference uploads", cloth.status_code == 200, cloth.text[:200])
    if me.get("photos") and cloth.status_code == 200:
        refused = a.job("creator_outfit", {"image": me["photos"][0]["id"], "ref": cloth.json()["id"], "text": "linen shirt", "confirm": "clothing-reference"})
        check("Me cannot try on an outfit", refused["status"] == "refused" and "me" in (refused.get("error") or "").lower(), refused.get("error"))
    if cloth.status_code == 200:
        tried = a.job("creator_outfit", {"image": item_id, "ref": cloth.json()["id"], "text": "linen shirt", "confirm": "clothing-reference"}, timeout=180)
        check("outfit try-on uses the mock edit", tried["status"] == "done" and tried.get("results"), tried.get("error"))

    library = a.get("/api/loras").json()["loras"]
    lora_name = next((row["name"] for row in library if row.get("family") == "zimage" and not row.get("blocked") and not row.get("player_only")), "")
    trained = next((row["name"] for row in library if (row.get("usage") or {}).get("role") == "character"), "")
    if not lora_name:
        added = a.post("/api/loras/workshop/import", json={"id": "clay-shore", "confirm": "yes"})
        if added.status_code == 200:
            lora_name = added.json()["name"]
    others = a.get("/api/gallery", params={"limit": 400}).json()["items"]
    other = next((row for row in others if row.get("character") and row.get("character") != character["id"] and row.get("type") == "image" and row.get("age_check") == "ok" and row.get("role") == "made"), None)
    check("a character LoRA exists for the face hold", bool(trained))
    if other and trained:
        miss = a.post("/api/loras/workshop/face-check", json={"name": trained, "reference": item_id, "result": other["id"]})
        check("the player can see a face hold", miss.status_code == 200 and miss.json().get("held") is True and "Mock score" in miss.json().get("label", ""), miss.text[:300])
        denied = a.post("/api/loras/workshop/accept", json={"name": trained})
        check("accept stays off while the face is held", denied.status_code == 400)
        pack = a.post("/api/creator/pack", json={"character": character["id"], "item": item_id})
        check("identity drift holds send", pack.status_code == 200 and pack.json().get("held") is True and any(row["id"] == "identity_drift" for row in pack.json().get("defects") or []), pack.text[:300])
        blocked = a.job("export_godot", {"character": character["id"], "creator_pack": True, "pack_item": item_id})
        check("send to the island is refused while held", blocked["status"] == "refused" and "held" in (blocked.get("error") or "").lower(), blocked.get("error"))
        reviewed = a.post("/api/creator/review", json={"character": character["id"], "item": item_id, "ack": "i-reviewed-this-hold", "defect": "identity_drift"})
        check("an explicit review can clear the drift", reviewed.status_code == 200 and not reviewed.json().get("held"), reviewed.text[:300])
    matched = a.post("/api/loras/workshop/face-check", json={"name": trained, "reference": item_id, "result": item_id}) if trained else None
    if matched is not None:
        check("a matching face can be accepted", matched.status_code == 200 and matched.json().get("status") == "match", matched.text[:240])
        ok_accept = a.post("/api/loras/workshop/accept", json={"name": trained})
        check("accept records the match", ok_accept.status_code == 200 and ok_accept.json().get("face_hold") is False, ok_accept.text[:240])
