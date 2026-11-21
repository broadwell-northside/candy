"""LoRA workshop checks. No network, no GPU, no weight download from Civitai."""
import io
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
os.environ["EASY_STUDIO_LORA_OFFLINE"] = "1"

import lora_workshop as W  # noqa: E402
import loras as L  # noqa: E402
import requests  # noqa: E402


def unit(check):
    print("\n[31] LoRA workshop gates")
    def boom(*_a, **_k):
        raise AssertionError("network")
    old = requests.get
    requests.get = boom
    try:
        rows = {row["id"]: row for row in W.catalogue_public()["entries"]}
        check("catalogue does not call the network", "clay-shore" in rows and W.catalogue_public()["network"] is False)
        check("catalogue has no download url", all("download_url" not in row for row in rows.values()))
        check("taken down is refused", not rows["taken-down"]["ok"] and "TakenDown" in rows["taken-down"]["reason"])
        check("archived is refused", not rows["archived-pack"]["ok"] and "Archived" in rows["archived-pack"]["reason"])
        check("real person is refused", not rows["poi-person"]["ok"] and "real person" in rows["poi-person"]["reason"])
        check("minor flag is refused", not rows["minor-flag"]["ok"] and ("minor" in rows["minor-flag"]["reason"].lower() or "21" in rows["minor-flag"]["reason"]))
        check("face swap is refused", not rows["face-swap"]["ok"])
        check("under-21 trigger words are refused", not rows["under-21-words"]["ok"])
        check("empty trigger list is not proof", rows["no-trigger"]["ok"] and rows["no-trigger"]["trainedWords"] == [] and "not proof" in W.EMPTY_TRIGGER)
        check("listed strength is UNKNOWN", rows["clay-shore"]["strength_model"] == "UNKNOWN" and rows["clay-shore"]["strength_clip"] == "UNKNOWN")
        info = W.lookup_url("https://civitai.com/models/9001")
        check("fixture url resolves offline", info["ok"] and info["id"] == "clay-shore" and info["baseModel"] == "Z-Image")
        try:
            W.lookup_url("https://civitai.com/models/999999")
            check("unknown civitai id stays offline", False)
        except ValueError as exc:
            check("unknown civitai id stays offline", "does not call Civitai" in str(exc))
    finally:
        requests.get = old

    card_entry = W.public_entry(W.entry_by_id("clay-shore"))
    label = card_entry["examples"][0]["label"]
    check("verified example is an author example", label == "Author example" and "civitai:9001:90011:image:1" in card_entry["examples"][0]["source_id"])
    other = W.public_entry(W.entry_by_id("quiet-ink"))["examples"][0]["label"]
    check("unverified example keeps the source id and the unverified label", other == "Resource example (authorship unverified)")
    sample = W.apply_sample(W.entry_by_id("clay-shore")["examples"][0], "easy_studio/clay_shore.safetensors")
    check("sample prompt does not change the weight file", sample["weight"] == "easy_studio/clay_shore.safetensors" and sample["weight_changed"] is False and sample["source_id"].startswith("civitai:"))
    inserted = W.insert_triggers("warm sand", ["clayshore"], "easy_studio/clay_shore.safetensors")
    check("trigger insert keeps the same weight", inserted["prompt"].startswith("clayshore") and inserted["weight_changed"] is False)
    empty = W.insert_triggers("warm sand", [], "easy_studio/nope.safetensors")
    check("empty triggers do not claim there is no trigger", "not proof" in empty["note"] and empty["prompt"] == "warm sand")

    wan = {"name": "easy_studio/wan21_face.safetensors", "title": "Wan face twenty one", "family": "wan14b",
           "role": "character", "wan_version": "2.1", "strength_model": None, "strength_clip": None}
    report = W.stack_report([wan], "wan22_high")
    check("Wan 2.1 on Wan 2.2 High Noise is a soft conflict",
          not report["blocked"] and report["soft"][0]["text"] == "Wan 2.1 LoRA in Wan 2.2 High Noise" and report["coach"])
    pair = [wan, {"name": "b.safetensors", "title": "Second", "family": "wan14b", "role": "face", "wan_version": "2.1", "strength_model": None}]
    report = W.stack_report(pair, "wan22_high")
    check("two character or face LoRAs warn", any(row["id"] == "two_characters" for row in report["soft"]))
    styles = [
        {"name": "a.safetensors", "title": "A", "family": "sdxl", "role": "style", "strength_model": 0.8},
        {"name": "b.safetensors", "title": "B", "family": "sdxl", "role": "style", "strength_model": 0.9},
    ]
    report = W.stack_report(styles, "sdxl")
    check("style fighting style warns", any(row["id"] == "style_fight" for row in report["soft"]))
    check("high total strength warns and is not a recommendation", any(row["id"] == "strength_high" and "not a recommended strength" in row["text"] for row in report["soft"]))
    mismatch = W.stack_report([{"name": "f.safetensors", "title": "Flux style", "family": "flux", "role": "style", "strength_model": None}], "zimage_turbo")
    check("wrong base model is a hard block", mismatch["blocked"] and "won't work" in mismatch["hard"][0]["text"])
    blocked = W.stack_report([{"name": "teen.safetensors", "title": "Teen", "family": "sdxl", "role": "style", "blocked": True, "blocked_reason": "Blocked: minor"}], "sdxl")
    check("an already blocked LoRA stays a hard block", blocked["blocked"])

    try:
        W.me_gate("me.png", "", "andrew-player", "not-an-npc", "linen shirt", "default")
        check("Me rejects a missing age", False)
    except ValueError as exc:
        check("Me rejects a missing age", "missing" in str(exc).lower())
    try:
        W.me_gate("me.png", 20, "andrew-player", "not-an-npc", "linen shirt", "default")
        check("Me rejects age 20", False)
    except ValueError as exc:
        check("Me rejects age 20", "under 21" in str(exc).lower())
    try:
        W.me_gate("me.png", 32, "", "not-an-npc", "linen shirt", "default")
        check("Me rejects someone else's photo", False)
    except ValueError as exc:
        check("Me rejects someone else's photo", "Andrew" in str(exc))
    try:
        W.me_gate("me.png", 32, "andrew-player", "not-an-npc", "nude on the sand", "default")
        check("Me rejects sexual content", False)
    except ValueError as exc:
        check("Me rejects sexual content", "not offered" in str(exc).lower())
    check("Me accepts Andrew at 32", W.me_gate("me.png", 32, "andrew-player", "not-an-npc", "linen shirt", "default") == 32)
    try:
        W.require_resume("resume the lora")
        check("an inference LoRA is not a checkpoint", False)
    except ValueError as exc:
        check("an inference LoRA is not a checkpoint", "not a resumable training checkpoint" in str(exc))
    text = open(W.CATALOGUE_PATH, encoding="utf-8").read()
    check("the catalogue has no token", "api_key" not in text and "Bearer" not in text)
    limits = W.limits()
    check("the built extras are the two helpers plus the four PR #39 features taken",
          limits["built"] == ["one-tap sample prompt", "stack coach", "outfit try-on", "face check", "defect hold", "surprise me"])
    check("private notice is the workshop notice", limits["notice"] == "PRIVATE BUILD — NOT FOR DISTRIBUTION")

    me_lora = {"name": "easy_studio/player_portrait.safetensors", "identity": "player_me"}
    me_still = {"id": "st1", "role": "player_me_still", "stated_age": 32}
    avatar = W.avatar_record(me_lora, me_still, 32)
    check("the player avatar is Andrew and not an NPC", avatar["who"] == "Andrew" and avatar["not_npc"] is True and avatar["sexual"] is False)
    for label, args in (("another LoRA", ({"name": "x.safetensors", "identity": ""}, me_still, 32)),
                        ("a picture that is not a curated Me still", (me_lora, {"id": "u1", "role": "made", "stated_age": 32}, 32)),
                        ("an age under 21", (me_lora, me_still, 20)),
                        ("an age that does not match the still", (me_lora, me_still, 40))):
        try:
            W.avatar_record(*args)
            check("the player avatar refuses " + label, False)
        except ValueError:
            check("the player avatar refuses " + label, True)
    check("the closed-upload message names the camera capture", "in-app camera capture" in W.ME_CAPTURE_ONLY
          and W.limits()["me_capture_only"] == W.ME_CAPTURE_ONLY)
    _recheck_unit(check)


class _Guard:
    """A stand-in appearance checker: answers per file name, and remembers what it was asked."""

    def __init__(self, answers=None, enabled=True):
        self.answers, self.enabled, self.seen = answers or {}, enabled, []

    def check(self, path):
        import age_guard
        self.seen.append(os.path.basename(path))
        answer = self.answers.get(os.path.basename(path), {"status": "ok", "faces": 1, "p_under21": 0.04})
        if isinstance(answer, Exception):
            raise answer
        return age_guard.gate(answer) if isinstance(answer, dict) else answer


def _recheck_unit(check):
    """SAFETY.md, Training: every training picture is age-checked again right before training. One flag stops the run."""
    import types

    import pipelines as P
    import trainer as T
    print("\n[31b] Workshop training re-checks every picture's age right before the run")
    ctx = types.SimpleNamespace(lib=types.SimpleNamespace(path=lambda item: "/pictures/" + item["id"] + ".png"))
    clean = [{"id": "p%02d" % n, "age_check": "ok"} for n in range(10)]

    def refusal(guard, items=clean, run=None):
        old = P.AGE_GUARD
        P.AGE_GUARD = guard
        try:
            (run or (lambda: W.recheck_training_pictures(ctx, items)))()
        except P.UserError as exc:
            return str(exc)
        finally:
            P.AGE_GUARD = old
        return ""

    guard = _Guard()
    check("ten clear pictures pass, and every one was checked again",
          refusal(guard) == "" and guard.seen == ["p%02d.png" % n for n in range(10)], guard.seen)
    guard = _Guard({"p07.png": {"status": "flag", "faces": 1, "p_under21": 0.93}})
    said = refusal(guard)
    check("one flagged picture stops the run", "flagged by the age check" in said and "p08.png" not in guard.seen, said)
    for status in ("unchecked", "unavailable", "error", "timeout", "off", "blocked_age_check_unavailable", "surprise"):
        said = refusal(_Guard({"p03.png": {"status": status, "reason": "test " + status}}))
        check("a picture the check answers '%s' for stops the run" % status, "held this picture" in said, said)
    check("a checker that gives no answer stops the run", "held this picture" in refusal(_Guard({"p00.png": "nothing"})))
    check("a checker that crashes stops the run", "held this picture" in refusal(_Guard({"p00.png": RuntimeError("worker died")})))
    check("no checker stops the run", "appearance checker is off" in refusal(None))
    check("a checker that is switched off stops the run", "appearance checker is off" in refusal(_Guard(enabled=False)))
    for field, value in (("age_flag", True), ("held", True), ("appearance_check", {"held": True}), ("age_check", "unchecked"),
                         ("age_check", "timeout"), ("age_check", "off")):
        guard = _Guard()
        stored = [dict(row) for row in clean]
        stored[4][field] = value
        said = refusal(guard, stored)
        check("a stored hold (%s=%r) stops the run before that picture is used" % (field, value),
              "held age check" in said and "p04.png" not in guard.seen, said)

    # The gate both workshop trainers share calls the re-check, after its cheaper refusals.
    old_installed = T.installed
    T.installed = lambda _root: True
    try:
        def gate(items=clean):
            return W._train_common(ctx, "fast", "shoretrigger", items, "linen shirt", W.RESUME_ACK)
        guard = _Guard()
        check("the shared training gate re-checks every picture", refusal(guard, run=gate) == "" and len(guard.seen) == 10, guard.seen)
        guard = _Guard({"p09.png": {"status": "flag", "faces": 1, "p_under21": 0.8}})
        check("the shared training gate stops on a flag", "flagged by the age check" in refusal(guard, run=gate))
        guard = _Guard()
        said = refusal(guard, run=lambda: gate(clean[:9]))
        check("too few pictures is still refused first, with no picture checked", "at least" in said and guard.seen == [], said)
    finally:
        T.installed = old_installed


def _png():
    im = Image.new("RGB", (80, 100), (40, 90, 140))
    ImageDraw.Draw(im).ellipse([20, 15, 60, 60], fill=(230, 190, 170))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def e2e(a, mock_url, comfy_dir):
    check = a.check
    print("\n[32] LoRA workshop screens")
    cat = a.get("/api/loras/workshop/catalogue").json()
    check("workshop catalogue is fixture metadata", cat.get("network") is False and any(row["id"] == "taken-down" and not row["ok"] for row in cat["entries"]))
    before = requests.get(mock_url + "/mock/log").json()
    missing = a.post("/api/loras/workshop/lookup", json={"url": "https://civitai.com/models/999999"})
    check("lookup does not call the network", missing.status_code == 400 and "does not call Civitai" in missing.text)
    check("download waits for confirm", a.post("/api/loras/workshop/import", json={"id": "clay-shore"}).status_code == 400)
    refused = a.post("/api/loras/workshop/import", json={"id": "taken-down", "confirm": "yes"})
    check("taken-down weights are not saved", refused.status_code == 400 and "TakenDown" in refused.text)
    bad = a.post("/api/loras/workshop/import", json={"id": "bad-hash", "confirm": "yes"})
    check("a hash mismatch is refused", bad.status_code == 400 and "hash" in bad.text.lower())
    check("the bad file is not in the library", not any("bad_hash" in row["name"] for row in a.get("/api/loras").json()["loras"]))
    added = a.post("/api/loras/workshop/import", json={"id": "clay-shore", "confirm": "yes"})
    check("confirm downloads the fixture and verifies the hash", added.status_code == 200 and added.json().get("usage", {}).get("hash_status") == "verified", added.text[:400])
    name = added.json()["name"]
    card = a.get("/api/loras/workshop/card", params={"name": name}).json()
    check("usage card keeps strengths UNKNOWN", card["strength_model"] == "UNKNOWN" and card["strength_clip"] == "UNKNOWN")
    check("usage card has the three recipe labels",
          card["author_recipe"]["label"] == "Author recipe" and card["app_suggestion"]["label"] == "App suggestion" and card["tested_preset"] is None)
    check("author example keeps its source id", card["examples"][0]["label"] == "Author example" and card["examples"][0]["source_id"])
    inserted = a.post("/api/loras/workshop/prompt", json={"name": name, "prompt": "warm sand", "action": "triggers"}).json()
    check("putting triggers in the prompt does not load another file", inserted["weight"] == name and inserted["weight_changed"] is False and inserted["prompt"].startswith("clayshore"))
    sample = a.post("/api/loras/workshop/prompt", json={"name": name, "action": "sample", "example": 0}).json()
    check("one-tap sample keeps the source id and the weight", sample["label"] == "Author example" and sample["source_id"] and sample["weight"] == name)
    empty = a.post("/api/loras/workshop/import", json={"id": "no-trigger", "confirm": "yes"}).json()
    empty_card = a.get("/api/loras/workshop/card", params={"name": empty["name"]}).json()
    check("empty trained words are not a verified no-trigger", "not proof" in empty_card["empty_trigger_note"] and empty_card["author_recipe"] is None)
    wan = a.post("/api/loras/workshop/import", json={"id": "wan21-face", "confirm": "yes"}).json()
    second = a.post("/api/loras/workshop/import", json={"id": "second-face", "confirm": "yes"}).json()
    report = a.post("/api/loras/workshop/stack", json={"names": [wan["name"]], "engine": "wan22_high"}).json()
    check("stack coach names the Wan conflict", report["soft"][0]["text"] == "Wan 2.1 LoRA in Wan 2.2 High Noise" and "Stack coach" not in report["soft"][0]["text"] and report["coach"])
    report = a.post("/api/loras/workshop/stack", json={"names": [wan["name"], second["name"]], "engine": "zimage_turbo"}).json()
    check("a wrong base model blocks the stack", report["blocked"])
    quiet = a.post("/api/loras/workshop/import", json={"id": "quiet-ink", "confirm": "yes"}).json()
    ink_card = a.get("/api/loras/workshop/card", params={"name": quiet["name"]}).json()
    check("unverified authorship is a resource example", ink_card["examples"][0]["label"] == "Resource example (authorship unverified)")

    weight_path = os.path.join(comfy_dir, "models", "loras", name)
    size_before = os.path.getsize(weight_path)
    job = a.job("lora_benchmark", {"name": name, "prompt": "a fictional adult, age 32, linen shirt, warm sand", "stated_age": 32, "seed": 4242}, timeout=180)
    results = job.get("results") or []
    check("benchmark returns eight mock cells", job["status"] == "done" and len(results) == 8, job.get("error"))
    if len(results) == 8:
        strengths = [row.get("bench_strength_model") for row in results]
        seeds = {row.get("bench_seed") for row in results}
        weights = {row.get("bench_weight") for row in results}
        flags = [row.get("bench_triggers") for row in results]
        check("benchmark uses one seed and the four strengths, with and without triggers",
              seeds == {4242} and strengths == [0.4, 0.6, 0.8, 1.0, 0.4, 0.6, 0.8, 1.0] and flags == [False, False, False, False, True, True, True, True] and weights == {name})
        check("clip strength stays UNKNOWN and the picture is not a photograph",
              all(row.get("bench_strength_clip") == "UNKNOWN" and row.get("title") == "Mock picture. Not a photograph." for row in results))
        saved = a.post("/api/loras/workshop/preset", json={"name": name, "item": results[6]["id"]})
        check("the winning cell becomes My tested preset", saved.status_code == 200 and saved.json()["tested_preset"]["label"] == "My tested preset"
              and saved.json()["tested_preset"]["strength_model"] == 0.8 and saved.json()["strength_clip"] == "UNKNOWN", saved.text[:400])
        check("saving the preset keeps the same weight file", saved.json()["weight"] == name)
    log = requests.get(mock_url + "/mock/log").json()
    new = log[len(before):]
    bench = [wf for wf in new if any((node.get("inputs") or {}).get("lora_name") == name for node in wf.values())]
    check("the mock engine ran the benchmark and did not set clip strength",
          len(bench) == 8 and all("strength_clip" not in (node.get("inputs") or {}) or node.get("class_type") != "LoraLoaderModelOnly"
                                  for wf in bench for node in wf.values()))
    check("the benchmark did not download a new weight file", os.path.getsize(weight_path) == size_before)

    chars = a.get("/api/characters").json()
    vera = next((row for row in chars if row.get("name") == "Vera"), None)
    shots = []
    if vera:
        shots = [row["id"] for row in a.get("/api/gallery", params={"character": vera["id"], "limit": 100}).json()["items"] if row.get("kind") == "train:shot"]
    check("the character's approved stills are available", bool(vera) and len(shots) >= 10, (None if not vera else vera.get("id"), len(shots)))
    check("character train needs the resume acknowledgement",
          a.job("workshop_train", {"kind": "character", "character": (vera or {}).get("id"), "base": "fast", "items": shots[:12], "caption": "warm sand"})["status"] in ("error", "refused"))
    if len(shots) >= 10 and vera:
        trained = a.job("workshop_train", {"kind": "character", "character": vera["id"], "base": "fast", "trigger": "verashore",
                                            "caption": "linen shirt, warm sand", "items": shots[:12],
                                            "resume_ack": "inference-lora-is-not-a-checkpoint"}, timeout=180)
        check("guided train uses the mock trainer", trained["status"] == "done" and trained.get("lora"), trained.get("error"))
        if trained.get("lora"):
            trained_card = a.get("/api/loras/workshop/card", params={"name": trained["lora"]}).json()
            check("a new character LoRA does not invent a strength", trained_card["strength_model"] == "UNKNOWN" and trained_card["strength_clip"] == "UNKNOWN")

    young = a.post("/api/loras/workshop/me/photo", files={"file": ("andrew.png", _png(), "image/png")},
                   data={"age": "20", "confirm_player": "andrew-player", "confirm_not_npc": "not-an-npc", "caption": "linen shirt"})
    check("Me upload rejects age 20", young.status_code == 400 and "under 21" in young.text.lower())
    missing_age = a.post("/api/loras/workshop/me/photo", files={"file": ("andrew.png", _png(), "image/png")},
                         data={"confirm_player": "andrew-player", "confirm_not_npc": "not-an-npc", "caption": "linen shirt"})
    check("Me upload rejects a missing age", missing_age.status_code == 400 and "missing" in missing_age.text.lower())
    other = a.post("/api/loras/workshop/me/photo", files={"file": ("andrew.png", _png(), "image/png")},
                   data={"age": "32", "confirm_not_npc": "not-an-npc", "caption": "linen shirt"})
    check("Me upload rejects a photo that is not Andrew's", other.status_code == 400)
    nude = a.post("/api/loras/workshop/me/photo", files={"file": ("andrew.png", _png(), "image/png")},
                  data={"age": "32", "confirm_player": "andrew-player", "confirm_not_npc": "not-an-npc", "caption": "nude"})
    check("Me upload rejects sexual content", nude.status_code == 400 and "not offered" in nude.text.lower())
    # R0: the upload path for Me is closed. A request that passes every earlier check is still refused,
    # and nothing is saved, curated or trained. Enrolment waits for the in-app camera capture.
    valid = {"age": "32", "confirm_player": "andrew-player", "confirm_not_npc": "not-an-npc", "caption": "player portrait, linen shirt"}
    me_before = a.get("/api/loras/workshop/me").json()
    refused_uploads = [a.post("/api/loras/workshop/me/photo", files={"file": ("andrew.png", _png(), "image/png")}, data=valid)
                       for _ in range(3)]
    check("a Me upload that passes every earlier check is still refused",
          all(row.status_code == 400 and "in-app camera capture" in row.text for row in refused_uploads), refused_uploads[0].text[:300])
    me_after = a.get("/api/loras/workshop/me").json()
    check("a refused Me upload saves no photo",
          me_after["photos"] == [] and me_after["stills"] == [] and me_before["photos"] == [] and me_after.get("upload_closed") is True, me_after)
    everything = a.get("/api/gallery", params={"limit": 2000}).json()["items"]
    check("no gallery item is a Me photo or a Me still",
          not [row["id"] for row in everything if str(row.get("role") or "").startswith("player_me") or row.get("identity") == "player_me"])
    for role in ("player_me_photo", "player_me_still", "owner_capture"):
        minted = a.upload(Image.open(io.BytesIO(_png())), role, age=32)
        check("the general upload route cannot make a '%s' item" % role, minted.status_code == 400, minted.text[:200])
    curated = a.post("/api/loras/workshop/me/curate", json={"ids": [], "caption": "player portrait, linen shirt"})
    check("curating Me photos is closed", curated.status_code == 400 and "in-app camera capture" in curated.text, curated.text[:300])
    some_still = a.post("/api/loras/workshop/me/curate", json={"ids": shots[:1], "caption": "player portrait, linen shirt"})
    check("curate does not turn any other picture into a Me still", some_still.status_code == 400 and "in-app camera capture" in some_still.text)
    me_train = {"base": "fast", "trigger": "playershore", "caption": "player portrait, linen shirt", "items": shots[:12],
                "stated_age": 32, "confirm_player": "andrew-player", "confirm_not_npc": "not-an-npc",
                "resume_ack": "inference-lora-is-not-a-checkpoint"}
    loras_before = sorted(row["name"] for row in a.get("/api/loras").json()["loras"])
    me_job = a.job("workshop_me_train", me_train, timeout=180)
    check("Me training is closed and trains nothing", me_job["status"] in ("error", "refused") and not me_job.get("lora")
          and "in-app camera capture" in (me_job.get("error") or ""), me_job.get("error"))
    check("the closed Me training added no LoRA", sorted(row["name"] for row in a.get("/api/loras").json()["loras"]) == loras_before)
    young_job = a.job("workshop_me_train", dict(me_train, stated_age=20))
    check("Me training still refuses age 20 with its own message", young_job["status"] in ("error", "refused")
          and "under 21" in (young_job.get("error") or "").lower(), young_job.get("error"))
    # A Me LoRA that already exists on disk stays locked to the player (seeded here: no training path makes one now).
    from v3_tests import fake_lora
    seeded = "player_me_seed.safetensors"
    fake_lora(os.path.join(comfy_dir, "models", "loras", seeded), ["lora_x.lora_down.weight", "lora_x.lora_up.weight"], {})
    with open(os.path.join(comfy_dir, "models", "loras", "player_me_seed.es.json"), "w", encoding="utf-8") as handle:
        json.dump({"title": "Player portrait", "identity": "player_me", "player_only": True, "area": "default",
                   "trigger_words": ["playershore"], "source": "Me portrait"}, handle)
    used = a.job("create", {"dna": {"gender": "woman", "age": 32, "style": "photo", "name": "Mara"}, "count": 1,
                             "advanced": {"loras": [{"name": seeded, "strength": 0.6}]}})
    check("Me cannot be used as someone else's LoRA", used["status"] in ("error", "refused") and "player" in (used.get("error") or "").lower(), used.get("error"))
    avatar = a.post("/api/loras/workshop/me/avatar", json={"lora": seeded, "portrait": (shots or ["none"])[0], "stated_age": 32})
    check("setting the player avatar is closed too, even with a Me LoRA on disk",
          avatar.status_code == 400 and "in-app camera capture" in avatar.text, avatar.text[:300])
    check("the closed avatar route wrote no avatar record", a.get("/api/loras/workshop/me").json().get("avatar") is None)

    # R0: the re-check runs for real through the job. The stored records say "ok"; the checker now says otherwise.
    inject = os.environ.get("MOCK_AGE_INJECT")
    if inject and len(shots) >= 10 and vera:
        train = {"kind": "character", "character": vera["id"], "base": "fast", "trigger": "verashore", "caption": "linen shirt, warm sand",
                 "items": shots[:12], "resume_ack": "inference-lora-is-not-a-checkpoint"}
        loras_before = sorted(row["name"] for row in a.get("/api/loras").json()["loras"])
        try:
            for answer, words in (({"status": "flag", "faces": 1, "p_under21": 0.93}, "flagged by the age check"),
                                  ({"status": "unchecked", "faces": 0, "reason": "no face found"}, "held this picture"),
                                  ({"status": "error", "reason": "worker failed"}, "held this picture")):
                with open(inject, "w", encoding="utf-8") as handle:
                    json.dump({"apply": "still", "result": answer}, handle)
                stopped = a.job("workshop_train", train, timeout=180)
                check("training stops when the re-check answers '%s' for a picture the gallery calls ok" % answer["status"],
                      stopped["status"] in ("error", "refused") and not stopped.get("lora") and words in (stopped.get("error") or ""),
                      stopped.get("error"))
        finally:
            if os.path.exists(inject):
                os.remove(inject)
        check("a stopped training run added no LoRA", sorted(row["name"] for row in a.get("/api/loras").json()["loras"]) == loras_before)
        again = a.job("workshop_train", train, timeout=180)
        check("with the checker clear again, the same pictures train", again["status"] == "done" and again.get("lora"), again.get("error"))
    off = a.post("/api/settings", json={"age_check": False, "confirm": "I understand"})
    check("the checker can be switched off for this test", off.status_code == 200)
    blocked = a.job("lora_benchmark", {"name": name, "stated_age": 32, "prompt": "a fictional adult on warm sand", "seed": 3})
    check("the benchmark will not run while the appearance checker is off", blocked["status"] == "refused" and "will not run" in (blocked.get("error") or "").lower(), blocked.get("error"))
    a.post("/api/settings", json={"age_check": True})
