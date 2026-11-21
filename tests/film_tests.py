"""Guided short film. Mock engine only: no GPU, no weight download, no RunPod."""
import json
import os
import subprocess
import tempfile

import comfy_client as cc
import films
import model_cards
import stills

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAN = "https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B"
_OFF = ("lightx2v", "krea", "klein", "gimm", "svi", "remix", "smoothmix", "dasiwa")


def _still(age=32, **extra):
    item = {
        "id": "still1", "type": "image", "role": "made", "kind": "create",
        "dna": {"age": age, "stated_age": age},
        "age_check": "ok", "appearance_check": {"status": "ok", "held": False},
    }
    item.update(extra)
    return item


def _lookup(item):
    def get_item(iid):
        return item if iid == item.get("id") else None
    return get_item


def _raises(fn, needle):
    try:
        fn()
    except films.FilmError as exc:
        return needle in str(exc), str(exc)
    except Exception as exc:
        return False, repr(exc)
    return False, "no error"


def _no_audio(data):
    handle, name = tempfile.mkstemp(suffix=".mp4")
    try:
        os.write(handle, data)
        os.close(handle)
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", name],
            capture_output=True, text=True, check=False)
        streams = json.loads(out.stdout or "{}").get("streams") or []
        return not any(row.get("codec_type") == "audio" for row in streams) and any(
            row.get("codec_type") == "video" for row in streams)
    finally:
        if os.path.exists(name):
            os.remove(name)


def unit(check):
    print("\n[37] short film license card and gates")
    cards = model_cards.load().get("cards") or []
    wan = next((row for row in cards if row.get("id") == "wan22_i2v"), {})
    check("Wan 2.2 I2V-A14B card is Apache-2.0 on 2026-11-05",
          wan.get("license_name") == "Apache-2.0" and wan.get("private_use") == "yes"
          and wan.get("license_checked") == "2026-11-05" and wan.get("license_url") == WAN
          and wan.get("adult_only") is False and wan.get("job") == "video_cutscene")
    weights = " ".join(wan.get("weights") or [])
    check("the quality Wan weights are on the card",
          "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" in weights
          and "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" in weights
          and "umt5_xxl_fp8_e4m3fn_scaled.safetensors" in weights
          and "wan_2.1_vae.safetensors" in weights
          and "lightx2v" not in weights.lower())
    cleared = []
    for row in cards:
        if row.get("private_use") == "yes":
            cleared.append(str(row.get("id") or ""))
            cleared.extend(row.get("weights") or [])
    blob = " ".join(cleared).lower()
    for part in _OFF:
        check(part + " has no private-use card", part not in blob, blob)
    quality = cc.load_workflow(films.WORKFLOW)
    for name in stills.workflow_weights(quality):
        ok, msg = stills.weight_allowed(name, "default")
        check("film weight " + name + " has a private-use card", ok, msg)
    fast = cc.load_workflow("video_wan22_i2v_fast_api.json")
    fast_names = stills.workflow_weights(fast)
    try:
        stills.require_licensed(fast, "default")
        blocked, detail = False, "ran"
    except stills.StillError as exc:
        blocked, detail = "no license card" in str(exc), str(exc)
    check("the fast lightx2v path cannot run", blocked and any("lightx2v" in name for name in fast_names), detail)
    extra = json.loads(json.dumps(quality))
    extra["99"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "no_card_weight.safetensors", "strength_model": 1}}
    try:
        stills.require_licensed(extra, "default")
        blocked, detail = False, "ran"
    except stills.StillError as exc:
        blocked, detail = "no license card" in str(exc), str(exc)
    check("a weight with no card does not run", blocked, detail)

    item = _still()
    found, ages, seconds, phrase = films.gate(
        {"image": item["id"], "seconds": 5, "motion": "wind"}, "default", lambda _cid: None, _lookup(item))
    check("a kept still can start a 5 second film",
          found["id"] == item["id"] and ages == [32] and seconds == 5 and "wind" in phrase)

    def boom(_iid):
        raise AssertionError("the still was read")

    ok, detail = _raises(lambda: films.gate(
        {"image": "x", "seconds": 5, "age": 18}, "default", lambda _c: None, boom), "under 21")
    check("age 18 never reaches a film lookup", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"image": "x", "seconds": 5, "stated_age": ""}, "default", lambda _c: None, boom), "Missing stated age")
    check("a blank age never reaches a film lookup", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"image": "x", "seconds": 5, "motion": "undress"}, "default", lambda _c: None, boom), "21+")
    check("an explicit film never reaches a lookup while 21+ is off", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"image": "x", "seconds": 5, "text": "face swap her"}, "default", lambda _c: None, boom), "face swap")
    check("a face swap never starts a film", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"seconds": 5}, "default", lambda _c: None, boom), "missing")
    check("a missing still never starts a film", ok, detail)

    missing = _still()
    missing.pop("dna")
    ok, detail = _raises(lambda: films.gate(
        {"image": missing["id"], "seconds": 5}, "default", lambda _c: None, _lookup(missing)), "Missing stated age")
    check("a still with no age is refused", ok, detail)
    young = _still(20)
    ok, detail = _raises(lambda: films.gate(
        {"image": young["id"], "seconds": 2}, "default", lambda _c: None, _lookup(young)), "under 21")
    check("a still aged 20 is refused and not raised", ok and "not raised" in detail, detail)
    rejected = _still(age_flag=True, age_check="flag")
    ok, detail = _raises(lambda: films.gate(
        {"image": rejected["id"], "seconds": 5}, "default", lambda _c: None, _lookup(rejected)), "rejected")
    check("a rejected still cannot start a film", ok, detail)
    held = _still(age_check="unchecked", appearance_check={"status": "unchecked", "held": True})
    ok, detail = _raises(lambda: films.gate(
        {"image": held["id"], "seconds": 5}, "default", lambda _c: None, _lookup(held)), "held")
    check("a held still cannot start a film", ok, detail)
    upload = _still(role="my_character", kind="upload")
    ok, detail = _raises(lambda: films.gate(
        {"image": upload["id"], "seconds": 5}, "default", lambda _c: None, _lookup(upload)), "uploaded photo")
    check("an uploaded photo cannot start a film", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"image": upload["id"], "seconds": 5, "text": "remove her clothes from this uploaded photo"},
        "default", lambda _c: None, boom), "clothing-removal")
    check("clothing removal of an uploaded photo never starts a film", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"image": item["id"], "seconds": 4}, "default", lambda _c: None, _lookup(item)), "2 or 5")
    check("a 4 second film is refused", ok, detail)
    ok, detail = _raises(lambda: films.gate(
        {"image": item["id"], "seconds": 5, "text": "repair contact so the join looks fixed"},
        "default", lambda _c: None, _lookup(item)), "not solved")
    check("a contact repair cannot start a film", ok, detail)
    pair = _still(people=[{"name": "Ada"}, {"name": "Bea"}], dna={"age": 30})
    ok, detail = _raises(lambda: films.gate(
        {"image": pair["id"], "seconds": 5}, "default", lambda _c: None, _lookup(pair)), "shared age")
    check("two people cannot share one age", ok, detail)
    pair_ok = _still(people=[{"age": 32, "stated_age": 32}, {"age": 41, "stated_age": 41}], dna={})
    found, ages, _seconds, _phrase = films.gate(
        {"image": pair_ok["id"], "seconds": 2}, "default", lambda _c: None, _lookup(pair_ok))
    check("two stated ages can start a film", ages == [32, 41] and found["id"] == pair_ok["id"])
    nude = _still(prompt="fully nude, standing")
    ok, detail = _raises(lambda: films.gate(
        {"image": nude["id"], "seconds": 5}, "default", lambda _c: None, _lookup(nude)), "21+")
    check("an explicit still stays off while 21+ is off", ok, detail)
    found, ages, seconds, phrase = films.gate(
        {"image": item["id"], "seconds": "2", "motion": "undress"}, "adult", lambda _c: None, _lookup(item))
    check("an explicit motion runs only while 21+ is open", seconds == 2 and ages == [32] and "takes off" in phrase, phrase)


def _refused(a, mock_url, requests, params, needle):
    before_log = requests.get(mock_url + "/mock/log", timeout=30).json()
    before_jobs = len(a.get("/api/jobs").json())
    response = a.post("/api/jobs", json={"kind": "film", "params": params})
    after_log = requests.get(mock_url + "/mock/log", timeout=30).json()
    text = response.text
    return (response.status_code == 400 and needle in text and after_log == before_log
            and len(a.get("/api/jobs").json()) == before_jobs, text)


def e2e(a, mock_url):
    import requests
    check = a.check
    print("\n[38] short film through the mock engine")
    made = a.job("create", {"dna": {"age": 32, "gender": "woman", "style": "photo", "name": "Ada"}, "count": 1})
    still = (made.get("results") or [None])[0]
    check("a kept still exists for the film", made.get("status") == "done" and still and still.get("id") and not still.get("age_flag"),
          made.get("error"))
    if not still:
        return
    refused, text = _refused(a, mock_url, requests, {"image": still["id"], "seconds": 5, "age": 18}, "under 21")
    check("an under-21 age never reaches the film job", refused, text)
    refused, text = _refused(a, mock_url, requests, {"image": still["id"], "seconds": 5, "stated_age": ""}, "Missing stated age")
    check("a missing age never reaches the film job", refused, text)
    refused, text = _refused(a, mock_url, requests, {"seconds": 5}, "missing")
    check("a missing still never reaches the film job", refused, text)
    refused, text = _refused(a, mock_url, requests, {"image": still["id"], "seconds": 3}, "2 or 5")
    check("only 2 or 5 seconds can start a film", refused, text)
    refused, text = _refused(a, mock_url, requests, {"image": still["id"], "seconds": 5, "motion": "undress"}, "21+")
    check("an explicit film stays off while the 21+ switch is off", refused, text)
    refused, text = _refused(a, mock_url, requests, {"image": still["id"], "seconds": 5, "text": "face swap"}, "face")
    check("a face swap never reaches the film job", refused, text)
    flagged = a.job("create", {"dna": {"age": 34, "gender": "woman", "style": "photo", "name": "Flag"},
                                "count": 1, "extra_scene": "magentatest"})
    check("a rejected still is deleted, so there is nothing to send to the film job",
          flagged.get("status") == "error" and not flagged.get("results") and flagged.get("can_retry") is True, flagged.get("error"))
    job = a.job("film", {"image": still["id"], "seconds": 5, "motion": "wind"})
    result = (job.get("results") or [None])[0]
    blob = a.file(result) if result else b""
    provenance = (result or {}).get("provenance") or {}
    check("a kept still becomes a silent film",
          job.get("status") == "done" and result and result.get("kind") == "video:film"
          and result.get("stated_age") == 32 and result.get("model") == "Wan 2.2 I2V-A14B"
          and provenance.get("sound") is False and provenance.get("seconds") == 5
          and provenance.get("fast_lora") is False and "not solved" in str(provenance.get("contact"))
          and blob[:8] != b"" and _no_audio(blob),
          job.get("error") or result)
    wf = {}
    if job.get("id"):
        wf = a.get("/api/jobs/%s/workflow" % job["id"]).json()["workflows"][-1]
    names = stills.workflow_weights(wf)
    dumped = json.dumps(wf).lower()
    lengths = [node["inputs"].get("length") for node in wf.values()
               if node.get("class_type") == "WanImageToVideo"]
    rates = [node["inputs"].get("fps") for node in wf.values()
             if node.get("class_type") == "CreateVideo"]
    loras = [node.get("class_type") for node in wf.values() if "lora" in str(node.get("class_type") or "").lower()]
    check("the film uses Wan 2.2 I2V-A14B and not the fast LoRAs",
          "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" in names
          and "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" in names
          and "lightx2v" not in dumped and "gimm" not in dumped and "smoothmix" not in dumped
          and "dasiwa" not in dumped and not loras
          and lengths == [81] and rates == [16.0],
          (names, lengths, rates, loras))
    short = a.job("film", {"image": still["id"], "seconds": 2})
    short_wf = {}
    if short.get("id"):
        short_wf = a.get("/api/jobs/%s/workflow" % short["id"]).json()["workflows"][-1]
    short_lengths = [node["inputs"].get("length") for node in short_wf.values()
                     if node.get("class_type") == "WanImageToVideo"]
    check("a 2 second film stays inside the allowed length",
          short.get("status") == "done" and ((short.get("results") or [{}])[0].get("provenance") or {}).get("seconds") == 2
          and short_lengths == [33],
          (short.get("error"), short.get("status"), short_lengths))
