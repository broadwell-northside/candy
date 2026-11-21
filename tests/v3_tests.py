"""Easy Studio 3 checks (run from run_tests.py): 18+ section, age check, Video studio, imported workflows,
LoRA library, Train my character, Godot export, and the v3 safety rules."""
import io
import json
import os
import struct
import sys
import time
import zipfile

import requests
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import loras as L  # noqa: E402
import safety  # noqa: E402
import trainer as T  # noqa: E402


def fake_lora(path, keys, meta=None, shape=(16, 2048)):
    hdr = {"__metadata__": {k: str(v) for k, v in (meta or {}).items()}}
    off = 0
    for k in keys:
        hdr[k] = {"dtype": "F16", "shape": list(shape), "data_offsets": [off, off + 8]}
        off += 8
    h = json.dumps(hdr).encode()
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(h)) + h + b"\0" * off)
    return path


SDXL_KEYS = ["lora_unet_input_blocks_4_1_proj_in.lora_down.weight", "lora_te2_text_model_encoder_layers_0_mlp_fc1.lora_up.weight"]
FLUX_KEYS = ["transformer.single_blocks.0.attn.to_q.lora_A.weight", "transformer.double_blocks.0.img_attn.qkv.lora_B.weight"]
WAN_KEYS = ["diffusion_model.blocks.0.self_attn.q.lora_A.weight", "diffusion_model.blocks.0.cross_attn.k.lora_B.weight"]


def unit(check):
    print("\n[19] v3 word rules (fewer false alarms, same hard blocks)")
    for t in ["petite", "yoga pants", "bikini", "lingerie", "swimsuit", "a petite woman in yoga pants", "red bikini on the beach",
              "one-piece swimsuit", "cumulus clouds", "cucumber salad", "cocktail dress", "sexy bikini", "she is 21"]:
        ok, msg = safety.check_prompt(t)
        ok2, msg2 = safety.check_area(t, "default")
        check(f"allowed everywhere: {t!r}", ok and ok2, msg or msg2)
    for t in ["nude", "topless", "naked on the bed", "cumshot"]:
        check(f"normal area sends {t!r} to the 18+ section", not safety.check_area(t, "default")[0])
        check(f"18+ section allows {t!r}", safety.check_area(t, "adult")[0])
    for t in ["nude schoolgirl", "student in her dorm, nude", "asleep and nude", "drunk", "stepsister", "hidden camera",
              "petite with a flat chest", "innocent", "forced", "school uniform", "young looking", "she looks very young"]:
        check(f"18+ section still blocks {t!r}", not safety.check_area(t, "adult")[0])
    for t in ["nude 16 year old", "topless teen", "naked loli", "\u0455choolgirl", "t\u0435\u0435n"]:  # last two: Cyrillic look-alike letters
        check(f"minors blocked in 18+ too: {t!r}", not safety.check_prompt(t)[0])
    for t in ["young woman, 25", "youthful skin glow", "cheerleader outfit, 25", "college girl, 22"]:
        check(f"not over-blocked: {t!r}", safety.check_prompt(t)[0] and safety.check_area(t, "adult")[0])
    for t in ["a youthful-looking woman", "youthful looking face", "youthful-looking"]:
        check(f"youthful-looking is refused: {t!r}", not safety.check_prompt(t)[0] and not safety.check_area(t, "adult")[0])
    check("youthful-looking LoRA is refused", not safety.check_lora("youthful_looking.safetensors")[0])
    check("named celebrity refused in prompts", not safety.check_prompt("Taylor Swift in lingerie")[0] and not safety.check_prompt("emma-watson nude")[0])
    check("ordinary words near celebrity names still fine", safety.check_prompt("a swift runner named Emma, rose petals, park bench")[0])
    check("age 20 not allowed (21 is the youngest)", not safety.check_prompt("she is 20 years old")[0])
    print("\n[20] LoRA checks and base-model detection")
    for n in ["freckled_face_style.safetensors", "detail_tweaker.safetensors", "cyberpunk_city.safetensors", "lace_lingerie.safetensors"]:
        check(f"LoRA allowed: {n}", L.safety.check_lora(n)[0], L.safety.check_lora(n)[1])
    for n in ["reactor_faceswap.safetensors", "celebrity_lookalike.safetensors", "loli_style.safetensors", "teen_body.safetensors",
              "instantid_face.safetensors", "real_person_v1.safetensors", "schoolgirl_xl.safetensors",
              "taylor_swift_v2.safetensors", "Scarlett-Johansson.safetensors", "age_slider.safetensors", "my_face.safetensors"]:
        check(f"LoRA blocked: {n}", not safety.check_lora(n)[0])
    check("LoRA blocked by trigger word", not safety.check_lora("style.safetensors", None, ["teen girl"])[0])
    check("LoRA blocked by metadata", not safety.check_lora("x.safetensors", {"ss_tag_frequency": '{"a": {"child": 3}}'})[0])
    check("detect: SDXL keys", L.detect_family({}, {k: [16, 640] for k in SDXL_KEYS}) == "sdxl")
    check("detect: Flux/Chroma keys", L.detect_family({}, {k: [16, 3072] for k in FLUX_KEYS}) == "flux")
    check("detect: Wan 14B keys", L.detect_family({}, {k: [16, 5120] for k in WAN_KEYS}) == "wan14b")
    check("detect: Wan 5B keys (dim 3072)", L.detect_family({}, {k: [16, 3072] for k in WAN_KEYS}) == "wan5b")
    check("detect: metadata wins", L.detect_family({"ss_base_model_version": "sdxl_base_v1-0"}, {k: [1, 1] for k in WAN_KEYS}) == "sdxl")
    check("triggers from metadata", L.triggers_from({"ss_tag_frequency": '{"x": {"mystyle": 9, "red": 2}}'})[0] == "mystyle")
    print("\n[21] Civitai rules (no network: fake answers)")
    good = {"id": 1, "name": "Neon glow style", "type": "LORA", "tags": ["style"], "nsfw": False,
            "modelVersions": [{"id": 11, "name": "v1", "baseModel": "Illustrious", "trainedWords": ["neonglow"],
                               "files": [{"name": "neon.safetensors", "primary": True, "sizeKB": 1000, "downloadUrl": "https://x/d",
                                          "metadata": {"format": "SafeTensor"}}], "images": []}]}

    class R:
        def __init__(self, code, js):
            self.status_code, self._js = code, js

        def json(self):
            return self._js

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

    class Sess:
        def __init__(self, model, code=200):
            self.model, self.code = model, code

        def get(self, url, **kw):
            return R(self.code, self.model)
    i = L.civitai_lookup("https://civitai.com/models/1/neon", session=Sess(good))
    check("civitai: good style LoRA ok, family + trigger read", i["ok"] and i["family"] == "sdxl" and i["trigger_words"] == ["neonglow"], i)
    i = L.civitai_lookup("https://civitai.com/models/1", session=Sess({**good, "poi": True}))
    check("civitai: real person (POI) blocked", not i["ok"] and "real person" in i["reason"])
    i = L.civitai_lookup("https://civitai.com/models/1", session=Sess({**good, "tags": ["celebrity"]}))
    check("civitai: celebrity tag blocked", not i["ok"])
    i = L.civitai_lookup("https://civitai.com/models/1", session=Sess({**good, "type": "Checkpoint"}))
    check("civitai: checkpoints refused (LoRAs only)", not i["ok"])
    i = L.civitai_lookup("https://civitai.com/models/1", session=Sess({**good, "nsfw": True}))
    check("civitai: adult LoRA marked for the 18+ section", i["ok"] and i["nsfw"])
    try:
        L.civitai_lookup("https://civitai.com/models/1", session=Sess(good, 401))
        check("civitai: login-only models ask for an API key", False)
    except ValueError as e:
        check("civitai: login-only models ask for an API key", "API key" in str(e))
    try:
        L.parse_civitai_url("https://example.com/x")
        check("civitai: other links refused", False)
    except ValueError:
        check("civitai: other links refused", True)
    print("\n[22] Trainer settings")
    check("trigger word is short and rare", T.make_trigger("Mira Stone") == T.make_trigger("Mira Stone") and "zx" in T.make_trigger("Mira"))
    import tempfile
    d = tempfile.mkdtemp()
    cfg = json.load(open(T.write_config(d, "n", "video", "mirazx1", d)))
    pr = cfg["config"]["process"][0]
    check("video LoRA: Wan 2.2 high+low pair, sampling off", pr["network"].get("split_multistage_loras") and pr["train"]["disable_sampling"]
          and pr["model"]["arch"] == "wan22_14b", pr)
    cfg = json.load(open(T.write_config(d, "n", "anime", "x", d)))
    check("anime LoRA: SDXL (NoobAI)", cfg["config"]["process"][0]["model"].get("is_xl") or cfg["config"]["process"][0]["model"].get("arch") == "sdxl")


def magenta(size=(640, 900)):
    im = Image.new("RGB", size, (120, 100, 90))
    ImageDraw.Draw(im).rectangle([0, 0, 15, 15], fill=(255, 0, 255))
    ImageDraw.Draw(im).ellipse([200, 100, 440, 400], fill=(230, 200, 180))
    return im


def person(size=(640, 900), col=(90, 120, 160)):
    im = Image.new("RGB", size, col)
    ImageDraw.Draw(im).ellipse([200, 100, 440, 400], fill=(230, 200, 180))
    return im


def e2e(a, mock_url, comfy_dir, App, ffprobe_frames, img_of, out=None):
    check = a.check
    base = a.base
    print("\n[23] 18+ section gate")
    st = a.get("/api/adult/status").json()
    check("18+ locked at first", not st["unlocked"] and not st["device_confirmed"])
    check("18+ gallery refused while locked", a.get("/api/gallery?area=adult").status_code == 403)
    check("18+ job refused while locked", a.post("/api/jobs", json={"kind": "create", "area": "adult", "params": {"dna": {"age": 30}}}).status_code == 403)
    check("unlock needs both ticks", a.post("/api/adult/unlock", json={"confirm_age": True}).status_code == 400)
    check("PIN must be 4-8 digits", a.post("/api/adult/unlock", json={"confirm_age": True, "confirm_rules": True, "new_pin": "12"}).status_code == 400)
    r = a.post("/api/adult/unlock", json={"confirm_age": True, "confirm_rules": True, "new_pin": "2468"})
    check("unlock with ticks + new PIN", r.status_code == 200 and r.json()["pin"], r.text)
    ck = {c.name: c for c in a.s.cookies}
    check("18+ cookies are HttpOnly", all(c.has_nonstandard_attr("HttpOnly") or c._rest.get("HttpOnly") is not None for c in ck.values())
          and "es_adult_device" in ck and "es_adult_session" in ck, list(ck))
    check("18+ open on this device", a.get("/api/adult/status").json()["unlocked"])
    other = App(base)
    check("another browser is still locked", not other.get("/api/adult/status").json()["unlocked"])
    cat = a.get("/api/catalog").json()
    check("18+ presets only when unlocked", "adult" in cat and cat["adult"]["motions"] and "adult" not in other.get("/api/catalog").json())
    check("normal outfits have no nude category", not any(c["id"] == "nude" for c in other.get("/api/catalog").json()["outfits"]))

    dna = {"gender": "woman", "age": 29, "style": "photo", "name": "Vera", "traits": {"hair_color": "black"}}
    j = a.job("create", {"dna": dna, "count": 1, "extra_scene": "nude on silk sheets"}, area="adult")
    check("18+ section: explicit picture of a 21+ character", j["status"] == "done" and j["results"], j.get("error"))
    adult_it = j["results"][0] if j["results"] else {"id": "x", "url": "/files/x"}
    check("18+ result is marked 18+", adult_it.get("area") == "adult", adult_it)
    sent = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("18+ prompt still says adult + under-age negative", "adult" in sent and "child" in sent)
    check("explicit keyframe uses Chroma", "Chroma1-HD.safetensors" in sent, sent[:400])
    other_still = a.job("create", {"dna": dna, "count": 1, "extra_scene": "standing in a studio"}, area="adult")
    other_id = (other_still.get("results") or [{}])[0].get("id")
    import shot_qc
    qc = shot_qc.passing_qc(adult_it["id"], other_id)
    jv = a.job("video", {"image": adult_it["id"], "motion": "wind", "seconds": 2, "photoreal": True, "qc": qc,
                         "advanced": {"loras": [{"name": "my_style_lora.safetensors", "strength": 0.8}]},
                         "anatomy": [{"category": "breasts", "name": "my_style_lora.safetensors", "strength": 0.6}]},
                area="adult")
    check("photoreal video runs in the 18+ section", jv["status"] == "done" and jv.get("results"), jv.get("error"))
    chain = ((jv.get("results") or [{}])[0].get("provenance") or {}).get("chain") or []
    check("chain is motion, repair, SeedVR2, then 30 fps",
          [c.get("stage") for c in chain] == ["i2v", "fix", "upscale", "interpolate"] and chain[-1].get("to_fps") == 30, chain)
    sentv = requests.get(mock_url + "/mock/log").json()[-1]
    names = [n["inputs"].get("lora_name") for n in sentv.values() if n.get("class_type") == "LoraLoaderModelOnly"]
    check("motion and anatomy LoRAs are both on the video graph", names.count("my_style_lora.safetensors") >= 2, names)
    # On the server, extend runs on Wan 2.2 14B (high + low). A single, unpaired LoRA file is a hard error there (PRD §5.2).
    # On the Mac's 5B profile extend uses the 5B model, so this check runs with the server profile switched on.
    over = os.path.join(out, "machine_profile.json") if out else None
    if over:
        with open(over, "w", encoding="utf-8") as f:
            json.dump({"default": "rtx_pro_6000"}, f)
    try:
        jbad = a.job("extend", {"video": jv["results"][0]["id"], "motion": "look", "seconds": 2, "photoreal": True,
                                "anatomy": [{"category": "skin", "name": "my_style_lora.safetensors", "strength": 0.5}]}, area="adult") if jv.get("results") else {"status": "error"}
    finally:
        if over and os.path.exists(over):
            os.remove(over)
    check("extend refuses an unpaired LoRA on Wan 2.2 14B", jbad["status"] == "error" and "high-noise and low-noise pair" in (jbad.get("error") or ""), jbad.get("error"))
    jx = a.job("extend", {"video": jv["results"][0]["id"], "motion": "look", "seconds": 2, "photoreal": True}, area="adult") if jv.get("results") else {"status": "error"}
    check("extend uses the photoreal chain", jx["status"] == "done" and ((jx.get("results") or [{}])[0].get("provenance") or {}).get("chain"), jx.get("error"))
    j = a.job("create", {"dna": dna, "count": 1, "extra_scene": "nude on silk sheets"})
    check("normal area: explicit words are sent to the 18+ section", j["status"] == "refused" and "18+" in (j.get("error") or ""), j)
    j = a.job("create", {"dna": dna, "count": 1, "extra_scene": "on the beach"})
    sent = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("normal area adds 'no nudity' to the negative", "nudity" in sent)
    j = a.job("create", {"dna": dna, "count": 1, "extra_scene": "nude, asleep"}, area="adult")
    check("18+ section refuses sleeping / non-consent themes", j["status"] == "refused", j)
    r = a.post("/api/jobs", json={"kind": "create", "area": "adult", "params": {"dna": {**dna, "age": 16}, "count": 1, "extra_scene": "nude"}})
    check("18+ section: age 16 is refused and not rewritten to 21", r.status_code == 400 and "age=16" in r.text and "16-year" not in r.text, r.text)
    g = a.get("/api/gallery").json()
    check("18+ pictures are not in the normal gallery", all(i["id"] != adult_it["id"] for i in g["items"]))
    g = a.get("/api/gallery?area=adult").json()
    check("18+ gallery shows them", any(i["id"] == adult_it["id"] for i in g["items"]) and all(i.get("area") == "adult" for i in g["items"]))
    check("18+ file hidden from a locked browser", other.get(adult_it["url"]).status_code == 404)
    check("18+ item hidden from a locked browser", other.get(f"/api/items/{adult_it['id']}").status_code == 404)
    check("18+ file shown when unlocked", a.get(adult_it["url"]).status_code == 200)
    j = a.job("edit", {"image": adult_it["id"], "op": "outfit", "item": "dressy:cocktail"})
    check("normal area can't use an 18+ picture", j["status"] in ("error", "refused"), j)
    check("lock the 18+ section", a.post("/api/adult/lock").status_code == 200 and not a.get("/api/adult/status").json()["unlocked"])
    check("after locking, 18+ files hidden", a.get(adult_it["url"]).status_code == 404)
    check("wrong PIN refused", a.post("/api/adult/unlock", json={"pin": "0000"}).status_code == 403)
    check("right PIN re-opens (no ticks needed again on this device)", a.post("/api/adult/unlock", json={"pin": "2468"}).status_code == 200)
    import still_tests
    still_tests.explicit_case(a, mock_url)

    print("\n[24] Automatic age check")
    st = a.get("/api/status").json()
    check("age check on and installed", st["age_check"]["enabled"] and st["age_check"]["installed"], st["age_check"])
    j = a.job("create", {"dna": dna, "count": 1, "extra_scene": "magentatest"})
    check("possibly-under-21 result is deleted: the job ends with no result and offers a retry",
          j["status"] == "error" and not j.get("results") and j.get("can_retry") is True, j)
    check("job says plainly that it was deleted and offers a new seed",
          "deleted" in (j.get("error") or "") and "new seed" in (j.get("error") or "") and "under 21" in (j.get("error") or ""), j.get("error"))
    check("nothing flagged is listed in the gallery, blurred or otherwise",
          not [i for i in a.get("/api/gallery").json()["items"] if i.get("age_flag") or i.get("age_check") == "flag"])
    import discard_tests
    discard_tests.e2e(a, mock_url)
    import policy_gate_tests
    policy_gate_tests.e2e(a, out)
    r = a.upload(magenta(), "my_character", name="my_oc.png", age="30")
    check("upload of own art that looks under 21 refused", r.status_code == 400 and "21" in r.text, r.text)
    r = a.upload(person(), "my_character", name="my_oc.png", age="30")
    check("upload of own adult character art ok", r.status_code == 200 and r.json().get("age_check") == "ok", r.text)
    check("settings: switching the check off needs confirmation", a.post("/api/settings", json={"age_check": False}).status_code == 400)

    print("\n[25] Video studio: any model")
    vm = a.get("/api/video/models").json()
    ids = {m["id"]: m for m in vm["models"]}
    check("video models listed (Wan, LTX, Hunyuan, Kandinsky)", all(k in ids for k in ("wan22_i2v", "wan22_t2v", "wan22_5b_t2v", "ltx25_t2v", "hunyuan15_i2v", "kandinsky5_t2v")), list(ids))
    check("every model shows ready / missing", all("ready" in m for m in vm["models"]))
    j = a.job("create", {"dna": dna, "count": 1})
    still = j["results"][0]
    j_b = a.job("create", {"dna": dna, "count": 1, "extra_scene": "standing by a window"})
    still_b = j_b["results"][0]
    import shot_qc as _shot_qc
    i2v_qc = _shot_qc.passing_qc(still["id"], still_b["id"])
    r = a.post("/api/characters", json={**dna, "hero": still["id"]})
    ch = r.json()
    for mid, extra in [("wan22_t2v", {}), ("wan22_5b_t2v", {}), ("ltx25_t2v", {}), ("hunyuan15_t2v", {}), ("kandinsky5_t2v", {}),
                       ("wan22_5b_i2v", {"start": still["id"], "qc": i2v_qc}), ("ltx25_i2v", {"start": still["id"], "qc": i2v_qc}),
                       ("hunyuan15_i2v", {"start": still["id"], "qc": i2v_qc}), ("kandinsky5_i2v", {"start": still["id"], "qc": i2v_qc}),
                       ("ltx25_flf2v", {"start": still["id"], "end": still["id"], "qc": i2v_qc}), ("wan22_i2v", {"start": still["id"], "qc": i2v_qc})]:
        j = a.job("video_any", {"model": mid, "text": "she turns and smiles", "seconds": 3, "stated_age": "30", **extra}, timeout=300)
        ok = j["status"] == "done" and j["results"]
        if ok:
            n, w, h = ffprobe_frames(a.file(j["results"][0]))
            rule = 8 if mid.startswith("ltx") else 4
            ok = (n - 1) % rule == 0 and w % 16 == 0 and h % 16 == 0
            detail = (n, w, h)
        else:
            detail = j.get("error")
        check(f"video studio: {mid}", ok, detail)
    j = a.job("video_any", {"model": "wan22_t2v", "text": "walking", "start": still["id"]})
    check("words-only model refuses a start picture (explains)", j["status"] == "error" and "words only" in (j.get("error") or ""), j.get("error"))
    j = a.job("video_any", {"model": "ltx25_flf2v", "text": "walking", "start": still["id"]})
    check("A-to-B model asks for the end picture", j["status"] == "error" and "end picture" in (j.get("error") or ""), j.get("error"))
    j = a.job("video_any", {"model": "wan22_t2v", "text": "a woman walking in the rain", "seconds": 3, "character": ch["id"]})
    v1 = j["results"][0]
    j = a.job("video_any", {"model": "wan22_i2v", "text": "she keeps walking", "extend_from": v1["id"], "seconds": 3})
    n1 = ffprobe_frames(a.file(v1))[0]
    check("extend a clip (continues from the last frame)", j["status"] == "done" and ffprobe_frames(a.file(j["results"][0]))[0] > n1, j.get("error"))
    j = a.job("video_any", {"model": "wan22_t2v", "text": "she undresses, nude"})
    check("video studio: explicit words only in 18+", j["status"] == "refused", j)
    j = a.job("video_any", {"model": "wan22_t2v", "motion": "undress", "seconds": 3, "stated_age": "30"}, area="adult")
    check("18+ motion preset works in the 18+ section", j["status"] == "done" and j["results"][0].get("area") == "adult", j.get("error"))
    j = a.job("video_any", {"model": "wan22_t2v", "text": "a teen dancing"})
    check("video studio: minors refused", j["status"] == "refused")

    print("\n[26] Your own ComfyUI video workflow")
    wf = json.load(open(os.path.join(HERE, "..", "app", "workflows", "vm_wan22_5b_t2v_api.json")))
    r = a.post("/api/byo", json={"name": "My Wan 5B", "workflow": wf})
    check("import an API-format workflow", r.status_code == 200 and r.json()["mode"] == "t2v", r.text)
    bid = r.json().get("id")
    check("imported workflow listed with the models", any(b["id"] == bid for b in a.get("/api/video/models").json()["byo"]))
    j = a.job("video_any", {"model": f"byo:{bid}", "text": "a dancer spins slowly", "seconds": 2})
    check("a person the words bring in is refused without a stated age, also on an imported workflow",
          j["status"] in ("error", "refused") and "stated age" in (j.get("error") or "").lower(), j.get("error"))
    j = a.job("video_any", {"model": f"byo:{bid}", "text": "a dancer spins slowly", "seconds": 2, "stated_age": "30"})
    check("run an imported workflow", j["status"] == "done" and j["results"], j.get("error"))
    sent = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("imported workflow gets the safety negative", "child" in sent)
    bad = json.loads(json.dumps(wf))
    bad["999"] = {"class_type": "ReActorFaceSwap", "inputs": {}}
    check("import: face-swap node refused", a.post("/api/byo", json={"name": "x", "workflow": bad}).status_code == 400)
    bad = json.loads(json.dumps(wf))
    bad["999"] = {"class_type": "TotallyMadeUpNode", "inputs": {}}
    r = a.post("/api/byo", json={"name": "x", "workflow": bad})
    check("import: unknown custom node explained", r.status_code == 400 and "doesn't have" in r.text, r.text)
    bad = json.loads(json.dumps(wf))
    bad["999"] = {"class_type": "LoadVideo", "inputs": {"file": "secret.mp4"}}
    check("import: loading other files from the PC refused", a.post("/api/byo", json={"name": "x", "workflow": bad}).status_code == 400)
    bad = json.loads(json.dumps(wf))
    for n in bad.values():
        if n["class_type"] == "CLIPTextEncode":
            n["inputs"]["text"] = "a 15 year old"
    check("import: texts inside are checked", a.post("/api/byo", json={"name": "x", "workflow": bad}).status_code == 400)
    pic = json.load(open(os.path.join(HERE, "..", "app", "workflows", os.listdir(os.path.join(HERE, "..", "app", "workflows"))[0])))
    check("import: picture-only workflow explained", a.post("/api/byo", json={"name": "x", "workflow": {"1": {"class_type": "SaveImage", "inputs": {}}}}).status_code == 400)
    check("import: not JSON explained", a.post("/api/byo", json={"name": "x", "workflow": "{nope"}).status_code == 400)
    check("delete an imported workflow", a.s.delete(base + f"/api/byo/{bid}").status_code == 200
          and not any(b["id"] == bid for b in a.get("/api/video/models").json()["byo"]))
    del pic

    print("\n[27] LoRA library")
    tmp = os.path.join(comfy_dir, "tmp_loras")
    os.makedirs(tmp, exist_ok=True)

    def up(path, confirm="yes", area=""):
        return a.post("/api/loras/upload", files={"file": (os.path.basename(path), open(path, "rb").read())},
                      data={"confirm": confirm, "area": area})
    p = fake_lora(os.path.join(tmp, "ink_anime_style.safetensors"), SDXL_KEYS, {"ss_base_model_version": "sdxl_base_v1-0", "ss_tag_frequency": '{"a": {"inkstyle": 10}}'})
    check("upload needs the 'not a real person' tick", up(p, confirm="").status_code == 400)
    r = up(p)
    check("upload a LoRA (drag and drop)", r.status_code == 200, r.text)
    rec = r.json()
    check("base model detected (SDXL)", rec.get("family") == "sdxl", rec)
    check("trigger word read from the file", rec.get("trigger_words") == ["inkstyle"], rec)
    p2 = os.path.join(tmp, "notes.txt")
    open(p2, "w").write("hi")
    check("non-.safetensors refused", up(p2).status_code == 400)
    p3 = fake_lora(os.path.join(tmp, "full_model.safetensors"), ["model.diffusion_model.input_blocks.0.weight"])
    check("a full model (not a LoRA) refused", up(p3).status_code == 400)
    p4 = fake_lora(os.path.join(tmp, "celebrity_face.safetensors"), SDXL_KEYS)
    check("celebrity LoRA refused", up(p4).status_code == 400)
    p5 = fake_lora(os.path.join(tmp, "nice_style.safetensors"), SDXL_KEYS, {"modelspec.trigger_phrase": "schoolgirl uniform"})
    check("LoRA with a minor trigger word refused", up(p5).status_code == 400)
    pf = fake_lora(os.path.join(tmp, "soft_light_flux.safetensors"), FLUX_KEYS)
    rf = up(pf).json()
    pw = fake_lora(os.path.join(tmp, "slow_pan_wan.safetensors"), WAN_KEYS, shape=(16, 5120))
    rw = up(pw).json()
    check("Wan video LoRA detected", rw.get("family") == "wan14b", rw)
    lst = a.get("/api/loras").json()
    check("library lists LoRAs with family names", lst["folder"] and any(x["name"] == rec["name"] for x in lst["loras"]) and lst["families"]["sdxl"])
    r = a.s.patch(base + "/api/loras", json={"name": rec["name"], "strength": 0.6, "trigger_words": ["inkstyle", "bold lines"], "title": "Ink style"})
    check("edit strength / trigger / title", r.status_code == 200 and r.json()["strength"] == 0.6 and r.json()["title"] == "Ink style", r.text)
    r = a.s.patch(base + "/api/loras", json={"name": rec["name"], "title": "Taylor Swift lookalike"})
    check("renaming to a real person refused", r.status_code == 400)
    open(os.path.join(comfy_dir, "models", "loras", os.path.splitext(rec["name"])[0] + ".preview.png"), "wb").write(
        (lambda b: (person((64, 64)).save(b, "PNG"), b.getvalue())[1])(io.BytesIO()))
    lst = a.get("/api/loras").json()
    th = next(x for x in lst["loras"] if x["name"] == rec["name"]).get("thumb_url")
    check("thumbnail shown", th and a.get(th).status_code == 200)
    opts = a.get("/api/advanced/options").json()
    check("library LoRAs offered in Advanced", rec["name"] in opts["loras"], opts["loras"][:10])
    j = a.job("create", {"dna": {**dna, "style": "anime"}, "count": 1, "advanced": {"loras": [{"name": rec["name"], "strength": 0.6}, {"name": "detail_tweaker.safetensors", "strength": 0.3}]}})
    sent = requests.get(mock_url + "/mock/log").json()[-1]
    lo = [n["inputs"]["lora_name"] for n in sent.values() if n["class_type"] in ("LoraLoaderModelOnly", "LoraLoader")]
    check("stack two LoRAs on an anime picture", j["status"] == "done" and rec["name"] in lo and "detail_tweaker.safetensors" in lo, (j.get("error"), lo))
    j = a.job("create", {"dna": dna, "count": 1, "advanced": {"loras": [{"name": rec["name"], "strength": 1}]}})
    check("SDXL LoRA on the realistic (Chroma) model explained", j["status"] == "error" and "won't work" in (j.get("error") or ""), j.get("error"))
    j = a.job("video_any", {"model": "wan22_t2v", "text": "slow pan", "seconds": 2, "advanced": {"loras": [{"name": rw["name"], "strength": 0.8}]}})
    sent = requests.get(mock_url + "/mock/log").json()[-1]
    lo = [n["inputs"]["lora_name"] for n in sent.values() if n["class_type"] == "LoraLoaderModelOnly"]
    check("a single Wan LoRA file is refused on Wan 2.2 14B, in plain words", j["status"] == "error"
          and "high-noise and low-noise pair" in (j.get("error") or "") and rw["name"] not in lo, (j.get("error"), lo))
    j = a.job("video_any", {"model": "ltx25_t2v", "text": "slow pan", "seconds": 2, "advanced": {"loras": [{"name": rw["name"], "strength": 0.8}]}})
    check("Wan LoRA on LTX explained", j["status"] == "error" and "won't work" in (j.get("error") or ""), j.get("error"))
    pa = fake_lora(os.path.join(tmp, "boudoir_light.safetensors"), FLUX_KEYS)
    ra = up(pa, area="adult")
    check("adult LoRA added inside the 18+ section", ra.status_code == 200 and ra.json()["area"] == "adult", ra.text)
    check("18+ LoRAs hidden from the normal list", not any(x["name"] == ra.json()["name"] for x in a.get("/api/loras").json()["loras"]))
    check("18+ LoRAs listed in the 18+ section", any(x["name"] == ra.json()["name"] for x in a.get("/api/loras?area=adult").json()["loras"]))
    j = a.job("create", {"dna": dna, "count": 1, "advanced": {"loras": [{"name": ra.json()["name"], "strength": 1}]}})
    check("18+ LoRA refused in the normal area", j["status"] in ("error", "refused"), j.get("error"))
    j = a.job("create", {"dna": dna, "count": 1, "look": "chroma", "advanced": {"loras": [{"name": ra.json()["name"], "strength": 1}]}}, area="adult")
    check("18+ LoRA works in the 18+ section", j["status"] == "done", j.get("error"))
    hidden = os.path.join(comfy_dir, "models", "loras", "my_sneaky_teen.safetensors")
    fake_lora(hidden, SDXL_KEYS)
    lst = a.get("/api/loras").json()
    bl = next((x for x in lst["loras"] if x["name"] == "my_sneaky_teen.safetensors"), {})
    check("LoRAs copied in by hand are checked too (blocked)", bl.get("blocked") is True, bl)
    j = a.job("create", {"dna": {**dna, "style": "anime"}, "count": 1, "advanced": {"loras": [{"name": "my_sneaky_teen.safetensors", "strength": 1}]}})
    check("blocked LoRA can't be used", j["status"] in ("error", "refused"), j.get("error"))
    check("civitai: bad link explained", a.post("/api/loras/civitai/lookup", json={"url": "https://example.com"}).status_code == 400)
    check("civitai download needs the tick", a.post("/api/loras/civitai/download", json={"url": "https://civitai.com/models/1"}).status_code == 400)
    r = a.s.delete(base + "/api/loras", params={"name": rf["name"]})
    check("delete a LoRA (moved to _trash)", r.status_code == 200 and not any(x["name"] == rf["name"] for x in a.get("/api/loras").json()["loras"]))

    print("\n[28] Train my character")
    ts = a.get(f"/api/train/status?character={ch['id']}").json()
    check("trainer found", ts["installed"] and ts["age_check"]["installed"], ts)
    j = a.job("train_lora", {"character": ch["id"], "base": "photo"})
    check("training needs 10+ pictures (explains)", j["status"] == "error" and "at least" in (j.get("error") or ""), j.get("error"))
    j = a.job("train_dataset", {"character": ch["id"], "count": 12}, timeout=400)
    shots = j.get("results") or []
    check("make 12 varied training pictures", j["status"] == "done" and len(shots) == 12, j.get("error"))
    check("each has a caption with [trigger]", all("[trigger]" in (s.get("caption") or "") for s in shots), shots[:1])
    sent = requests.get(mock_url + "/mock/log").json()[-12:]
    prompts = {json.dumps(w)[:0] + next((n["inputs"].get("prompt") for n in w.values() if n["class_type"] == "TextEncodeQwenImageEditPlus"), "") for w in sent}
    check("training pictures are all different shots", len(prompts) >= 10, len(prompts))
    ts = a.get(f"/api/train/status?character={ch['id']}").json()
    check("Train tab shows the pictures", len(ts["pictures"]) == 12)
    cloth = a.upload(person(col=(10, 200, 10)), "clothing", name="dress.png").json()
    j = a.job("train_lora", {"character": ch["id"], "base": "photo", "items": [s["id"] for s in shots] + [cloth["id"]]})
    check("training refuses non-character pictures", j["status"] == "error" and "Training can only use" in (j.get("error") or ""), j.get("error"))
    # age-flagged pictures are now deleted before they are saved; an older item that still carries the flag is
    # refused for training in still_tests ("an older flagged item cannot be trained on") and discard_tests.
    j = a.job("train_lora", {"character": ch["id"], "base": "photo"}, timeout=300)
    check("train a picture LoRA (fake trainer)", j["status"] == "done" and j.get("lora"), j.get("error"))
    tl = j.get("lora")
    lst = a.get("/api/loras").json()["loras"]
    rec = next((x for x in lst if x["name"] == tl), {})
    check("trained LoRA in the library with trigger + character", rec.get("character") == ch["id"] and rec.get("trigger_words") == [T.make_trigger("Vera")]
          and rec.get("family") == "flux" and rec.get("thumb"), rec)
    check("progress was shown", "LoRA" in (j.get("message") or ""), j.get("message"))
    j2 = a.job("create", {"dna": {**dna, "style": "render3d"}, "count": 1, "advanced": {"loras": [{"name": tl, "strength": 1}]}})
    check("trained LoRA usable in Create", j2["status"] == "done", j2.get("error"))
    j = a.job("train_lora", {"character": ch["id"], "base": "video"}, timeout=300)
    check("train a Wan 2.2 video LoRA (high+low pair)", j["status"] == "done" and j.get("lora"), j.get("error"))
    vrec = next((x for x in a.get("/api/loras").json()["loras"] if x["name"] == j.get("lora")), {})
    check("video LoRA knows its pair", (vrec.get("pair") or {}).get("low_noise"), vrec)
    j2 = a.job("video_any", {"model": "wan22_t2v", "text": "she waves", "seconds": 2, "stated_age": "30", "advanced": {"loras": [{"name": j.get("lora"), "strength": 1}]}})
    sent = requests.get(mock_url + "/mock/log").json()[-1]
    lo = [n["inputs"]["lora_name"] for n in sent.values() if n["class_type"] == "LoraLoaderModelOnly"]
    pair = vrec.get("pair") or {}

    def _expert_of(node_id, depth=0):
        node = sent.get(node_id) or {}
        if node.get("class_type") == "UNETLoader" or depth > 20:
            name = str((node.get("inputs") or {}).get("unet_name") or "")
            return "high_noise" if "high_noise" in name else ("low_noise" if "low_noise" in name else "")
        src = (node.get("inputs") or {}).get("model")
        return _expert_of(src[0], depth + 1) if isinstance(src, list) else ""
    placed = {n["inputs"]["lora_name"]: _expert_of(nid) for nid, n in sent.items()
              if n["class_type"] == "LoraLoaderModelOnly" and n["inputs"]["lora_name"] in pair.values()}
    check("video LoRA: high half on the high model, low half on the low model", j2["status"] == "done"
          and placed.get(pair.get("high_noise")) == "high_noise" and placed.get(pair.get("low_noise")) == "low_noise", (j2.get("error"), placed, pair))
    r = a.post("/api/settings", json={"age_check": False, "confirm": "I understand"})
    check("age check can be switched off", r.status_code == 200 and r.json().get("age_check") is False, r.text)
    before_log = requests.get(mock_url + "/mock/log").json()
    before_jobs = len(a.get("/api/jobs").json())
    r = a.post("/api/jobs", json={"kind": "create", "params": {"dna": {"name": "No Age", "gender": "woman"}}})
    check("a missing age is still rejected while the checker is off",
          r.status_code == 400 and "age is missing" in r.text and "25" not in r.text, r.text)
    off_cases = [
        ("create", {"dna": dna, "count": 1}),
        ("video", {"image": still["id"], "motion": "wind", "seconds": 2, "qc": i2v_qc}),
        ("video_any", {"model": "wan22_t2v", "text": "she waves", "seconds": 2}),
        ("train_dataset", {"character": ch["id"], "count": 12}),
        ("train_lora", {"character": ch["id"], "base": "photo"}),
        ("export", {"character": ch["id"]}),
        ("export_godot", {"character": ch["id"]}),
        ("workshop_still", {"character": ch["id"], "wardrobe": "jeans_tee", "look": "short dark hair"}),
        ("keep_face", {"character": ch["id"]}),
        ("refine_skin", {"character": ch["id"]}),
        ("refine_anatomy", {"character": ch["id"]}),
        ("lora_benchmark", {"stated_age": 32, "prompt": "a fictional adult on warm sand", "seed": 7, "name": "missing.safetensors"}),
        ("workshop_train", {"kind": "concept", "base": "fast", "trigger": "shorex", "caption": "warm sand", "items": []}),
        ("workshop_me_train", {"stated_age": 32, "confirm_player": "andrew-player", "confirm_not_npc": "not-an-npc"}),
    ]
    made_video = next((i for i in a.get("/api/gallery").json()["items"] if i.get("type") == "video" and i.get("stated_age")), None)
    check("a made video still carries its stated age", bool(made_video), made_video)
    if made_video:
        off_cases.append(("extend", {"video": made_video["id"], "motion": "look", "seconds": 2}))
        off_cases.append(("video_still", {"video": made_video["id"], "frame": "last"}))
    for kind, params in off_cases:
        j = a.job(kind, params, area="adult" if kind == "refine_anatomy" else None)
        check(f"{kind} will not run while the appearance checker is off",
              j["status"] == "refused" and "will not run" in (j.get("error") or "").lower()
              and "won't be checked" not in (j.get("error") or "").lower(), j.get("error"))
    after_log = requests.get(mock_url + "/mock/log").json()
    check("checker-off jobs never reach the engine",
          after_log == before_log and len(a.get("/api/jobs").json()) == before_jobs)
    r = a.upload(person(), "my_character", name="checker_off.png", age="32")
    check("a character picture is not saved while the checker is off",
          r.status_code == 400 and "not saved" in r.text.lower(), r.text)
    a.post("/api/settings", json={"age_check": True})
    check("age check back on", a.get("/api/settings").json()["age_check"])

    print("\n[29] Godot 4 export")
    j = a.job("sprites", {"video": v1["id"], "frames": 8})
    j = a.job("export_godot", {"character": ch["id"]}, timeout=300)
    check("export a Godot 4 project", j["status"] == "done" and j["results"], j.get("error"))
    if j.get("results"):
        z = zipfile.ZipFile(io.BytesIO(a.file(j["results"][0])))
        names = z.namelist()
        check("has project.godot + README + portraits", "project.godot" in names and "README.txt" in names and any("/portraits/" in n for n in names), names[:20])
        check("project.godot is Godot 4 format", "config_version=5" in z.read("project.godot").decode())
        ep = z.read("export_presets.cfg").decode() if "export_presets.cfg" in names else ""
        check("export presets for Windows, Linux and macOS", all(f'platform="{x}"' in ep for x in ("Windows Desktop", "Linux", "macOS")), ep[:200])
    j = a.job("export_godot", {"character": ch["id"]}, area="adult")
    check("18+ export works in the 18+ section", j["status"] == "done", j.get("error"))

    print("\n[30] PIN lock-out")
    a.post("/api/adult/lock")
    codes = [a.post("/api/adult/unlock", json={"pin": "1111"}).status_code for _ in range(6)]
    check("5 wrong PINs lock it for a while", codes[-1] == 429, codes)
