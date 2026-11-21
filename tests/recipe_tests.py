"""M1: the Graphic Workflow Editor's recipes, on the mock engine only.

No GPU, no weight download, no RunPod, no network beyond the local mock.
"""
import json
import os
import struct
import time
import zlib

import requests

import comfy_client as cc
import hardware_map as HW
import lora_workshop
import recipes as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATENCY_FILE = os.path.join(ROOT, "docs", "M1_MOCK_LATENCY.json")


def _err(fn):
    try:
        fn()
    except (R.RecipeError, cc.LoraRouteError, ValueError) as exc:
        return exc
    return None


def _doc(**stages):
    return {"recipe": "portrait_still", "stages": {k: {"on": True, "values": v} for k, v in stages.items()}}


def _png_with(key, text):
    raw = b"\x00\x00\x00\x00"
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", key.encode() + b"\x00" + text.encode())
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class _Client:
    def __init__(self):
        self.frees = 0

    def free_memory(self):
        self.frees += 1


def unit(check):
    print("\n[M1] Recipes: shape, hashes, keys, LoRA routing, imports, hardware map")
    check("stages are the fixed seven, in order", R.STAGES == ("subject", "look", "pose", "scene", "camera", "quality", "output"))
    e = _err(lambda: R.normalize({"recipe": "portrait_still", "order": list(reversed(R.STAGES))}))
    check("reordering stages is refused", e is not None and "cannot be reordered" in str(e), e)
    e = _err(lambda: R.normalize({"recipe": "portrait_still", "stages": {"lighting": {}}}))
    check("an unknown stage is refused", e is not None and "no stage called lighting" in str(e), e)
    doc = R.normalize({"recipe": "portrait_still", "stages": {"subject": {"on": False}}})
    check("Subject cannot be switched off", doc["stages"]["subject"]["on"] is True)
    doc = R.normalize({"recipe": "one_actor_film", "stages": {"look": {"on": True, "values": {"look": "red hair"}}}})
    check("a stage the recipe does not use stays off", doc["stages"]["look"]["on"] is False)
    e = _err(lambda: R.normalize(_doc(look={"look": "op://vault/item/field"})))
    check("a recipe never holds a secret reference", e is not None and "secret" in str(e), e)
    e = _err(lambda: R.normalize(_doc(subject={"age": 30})))
    check("a stage never takes an age", e is not None and e.stage == "subject", e)
    for bad in ("1.5", 2.5, True, "seven", -1):
        e = _err(lambda: R.normalize({"recipe": "portrait_still", "seed": bad}))
        check(f"a seed of {bad!r} is refused", e is not None and e.stage == "output", e)
    check("a typed seed is kept as typed", R.normalize({"recipe": "portrait_still", "seed": "42"})["seed"] == 42)
    e = _err(lambda: R.compile_recipe({"recipe": "portrait_still", "stages": {"look": {"values": {"wardrobe": "jeans_tee"}}}},
                                      R.Context("default", True, lambda _c: None, lambda _i: None, lambda _i: "")))
    check("a recipe without a saved character is refused at Subject", e is not None and e.stage == "subject", e)

    me = {"id": "me1", "name": "Andrew", "age": 40, "stated_age": 40, "real_person": True}
    ctx = R.Context("default", True, lambda _c: me, lambda _i: None, lambda _i: "")
    e = _err(lambda: R.compile_recipe(_doc(subject={"character": "me1"}, look={"wardrobe": "jeans_tee"}), ctx))
    check("the player (Me) is refused as a recipe subject", e is not None and "fictional adults only" in str(e), e)
    noage = {"id": "n1", "name": "Noa", "gender": "woman", "style": "photo"}
    ctx = R.Context("default", True, lambda _c: noage, lambda _i: None, lambda _i: "")
    e = _err(lambda: R.compile_recipe(_doc(subject={"character": "n1"}, look={"wardrobe": "jeans_tee"}), ctx))
    check("a saved character without a typed age is refused, never defaulted", e is not None and "age" in str(e).lower(), e)

    nested = {"a": "op://v/i/f", "b": ["ok", "op://x", {"c": "uses op://y", "op://key": 1, "d": "fine"}], "e": {"f": ["op://z"]}}
    check("op:// strings are removed at every depth, keys too",
          R.strip_secrets(nested) == {"b": ["ok", {"d": "fine"}], "e": {"f": []}}, R.strip_secrets(nested))
    text = R.export_recipe({"recipe": "portrait_still", "name": "op://vault/name", "notes": ["op://a", "keep"],
                            "stages": {"subject": {"on": True, "values": {"character": "c1", "age": 30, "stated_age": 30}}}})
    check("an export carries no op:// string", "op://" not in text, text)
    check("an export never carries an age", '"age"' not in text and "stated_age" not in text, text)
    check("an export carries the private notice", R.PRIVATE_NOTICE in text)

    g1 = {"2": {"class_type": "B", "inputs": {"y": 1, "x": 2}, "_meta": {"title": "SEED"}}, "1": {"class_type": "A", "inputs": {}}}
    g2 = {"1": {"inputs": {}, "class_type": "A"}, "2": {"inputs": {"x": 2, "y": 1}, "class_type": "B"}}
    check("the canonical hash ignores _meta and key order", R.canonical_hash(g1) == R.canonical_hash(g2))
    fields = {"template": "image_zimage_turbo_api.json", "seed": 7, "loras": [["a.safetensors", 0.8, "model_only"]],
              "garment_state": "jeans_tee", "sfw_mode": True, "camera": "portrait_85", "source_sha256": "text_only"}
    key = R.cache_key(fields)
    check("a full cache key is a sha256", isinstance(key, str) and len(key) == 64)
    for name in R.CACHE_FIELDS:
        check(f"a cache key without {name} is a miss", R.cache_key({**fields, name: None}) is None)
    check("a LoRA without its clip strength is a miss", R.cache_key({**fields, "loras": [["a.safetensors", 0.8, None]]}) is None)
    check("the cache key changes with sfw_mode", R.cache_key({**fields, "sfw_mode": False}) != key)
    check("the cache key changes with the seed", R.cache_key({**fields, "seed": 8}) != key)
    check("the cache key changes with a LoRA strength", R.cache_key({**fields, "loras": [["a.safetensors", 0.6, "model_only"]]}) != key)

    still_wf = cc.load_workflow("image_zimage_turbo_api.json")
    film_wf = cc.load_workflow("video_wan22_i2v_quality_api.json")
    check("the still template keeps POSITIVE, NEGATIVE, SEED and SIZE", all(cc.has_title(still_wf, t) for t in ("POSITIVE", "SEED", "SIZE")))
    check("the film template keeps POSITIVE, NEGATIVE, SEED, START IMAGE and SIZE",
          all(cc.has_title(film_wf, t) for t in ("POSITIVE", "NEGATIVE", "SEED", "START IMAGE", "SIZE")))
    e = _err(lambda: R.apply_quality(film_wf, {"steps": 30}))
    check("Quality never writes steps on a template with two KSamplerAdvanced nodes", e is not None and e.stage == "quality", e)
    steps_before = [n["inputs"].get("steps") for n in film_wf.values() if n["class_type"] == "KSamplerAdvanced"]
    check("the film template's steps are untouched", steps_before == [n["inputs"].get("steps") for n in
                                                                       cc.load_workflow("video_wan22_i2v_quality_api.json").values()
                                                                       if n["class_type"] == "KSamplerAdvanced"])
    R.apply_quality(still_wf, {"steps": 7})
    check("Quality can set steps on a single-sampler template",
          any(n["inputs"].get("steps") == 7 for n in still_wf.values() if n["class_type"] == "KSampler"))
    check("a graph with a LoadImage of the still passes the pixel handoff", _err(lambda: R.assert_pixel_handoff(
        {"1": {"class_type": "LoadImage", "inputs": {"image": "es_abc.png"}}}, "es_abc.png")) is None)
    e = _err(lambda: R.assert_pixel_handoff({"1": {"class_type": "LoadImage", "inputs": {"image": "es_abc.png"}},
                                              "2": {"class_type": "LoadLatent", "inputs": {}}}, "es_abc.png"))
    check("a latent crossing families is refused", e is not None, e)

    old_pair, old_hook = cc.PAIR_HOOK, cc.LORA_HOOK
    cc.PAIR_HOOK, cc.LORA_HOOK = (lambda f: None), None
    try:
        e = _err(lambda: cc.route_lora("style.safetensors", "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"))
        check("an unpaired LoRA on a Wan 14B half is a hard error", isinstance(e, cc.LoraRouteError) and "pair" in str(e), e)
        check("the same LoRA on Z-Image attaches as it is",
              cc.route_lora("style.safetensors", "z_image_turbo_bf16.safetensors") == "style.safetensors")
        check("Wan 5B is one loader, not a half", cc.route_lora("style.safetensors", "wan2.2_ti2v_5B_fp16.safetensors") == "style.safetensors")
        pair = {"high_noise": "p_high_noise.safetensors", "low_noise": "p_low_noise.safetensors"}
        cc.PAIR_HOOK = lambda f: pair if f == "p_high_noise.safetensors" else None
        check("a pair puts its high half on the high loader",
              cc.route_lora("p_high_noise.safetensors", "wan2.2_i2v_high_noise_14B.safetensors") == pair["high_noise"])
        check("and its low half on the low loader",
              cc.route_lora("p_high_noise.safetensors", "wan2.2_i2v_low_noise_14B.safetensors") == pair["low_noise"])
        calls = []
        real = cc.route_lora
        cc.route_lora = lambda f, u: calls.append((f, u)) or real(f, u)
        try:
            wf = cc.load_workflow("image_zimage_turbo_api.json")
            lora_workshop._attach_lora(wf, "bench.safetensors", 0.6)
            cc.inject_loras(cc.load_workflow("image_zimage_turbo_api.json"), [("inject.safetensors", 0.5)])
        finally:
            cc.route_lora = real
        check("the LoRA benchmark attaches through route_lora", any(f == "bench.safetensors" for f, _ in calls), calls)
        check("inject_loras attaches through route_lora", any(f == "inject.safetensors" for f, _ in calls), calls)
        tmpl = [n for n in film_wf.values() if n["class_type"] == "LoraLoaderModelOnly"]
        check("the quality film template carries no fast LoRA of its own", tmpl == [])
        fast = cc.load_workflow("video_wan22_i2v_fast_api.json")
        check("the fast template keeps its lightx2v LoRAs inside the template",
              any("lightx2v" in str(n["inputs"].get("lora_name", "")) for n in fast.values() if n["class_type"] == "LoraLoaderModelOnly"))
    finally:
        cc.PAIR_HOOK, cc.LORA_HOOK = old_pair, old_hook

    ui = {"nodes": [{"id": 1, "type": "CheckpointLoaderSimple", "widgets_values": ["model.safetensors"]},
                    {"id": 2, "type": "SomeCustomNode", "widgets_values": []}], "links": []}
    found = R.import_recipe(json.dumps(ui), known_nodes={"CheckpointLoaderSimple"})
    check("a ComfyUI UI graph is one-way: reported, not decompiled",
          found["kind"] == "third_party" and found["decompiled"] is False and found["format"] == "ui")
    check("the report names missing node types and models",
          found["report"]["missing_node_types"] == ["SomeCustomNode"] and found["report"]["models"] == ["model.safetensors"], found)
    api = {"1": {"class_type": "ReActorFaceSwap", "inputs": {}}, "2": {"class_type": "SaveImage", "inputs": {}}}
    found = R.import_recipe(json.dumps(api))
    check("a face-swap node in an import is refused, not allowed through",
          found["report"]["refused_nodes"] == ["ReActorFaceSwap"] and found["report"]["can_run_as_raw"] is False, found)
    found = R.import_recipe(_png_with("prompt", json.dumps({"1": {"class_type": "KSampler", "inputs": {}}})))
    check("PNG metadata is read one-way", found["kind"] == "third_party" and found["format"] == "png_api", found)

    check("the still template is the Z-Image family", HW.family_of_graph(cc.load_workflow("image_zimage_turbo_api.json")) == "zimage")
    check("the film template is the Wan 14B family", HW.family_of_graph(film_wf) == "wan14b")
    hw = HW.HardwareMap(default_url="http://mock")
    check("8188 is GPU0 for Z-Image; 8189 is GPU1 for Wan 14B",
          hw.process_for("zimage")["port"] == 8188 and hw.process_for("zimage")["gpu"] == 0
          and hw.process_for("wan14b")["port"] == 8189 and hw.process_for("wan14b")["gpu"] == 1)
    e = _err(lambda: HW.HardwareMap([{"port": 1, "gpu": 0, "families": ["a"]}, {"port": 2, "gpu": 0, "families": ["b"]}]))
    check("two processes never share a GPU", e is not None and "share a GPU" in str(e), e)
    client = _Client()
    hw.before_run("zimage", client)
    hw.before_run("zimage", client)
    hw.before_run("wan14b", client)
    check("no memory-free while one process keeps its family", client.frees == 0)
    hw.before_run("qwen_edit", client)
    check("a family change on one process frees memory first", client.frees == 1 and hw.freed[-1]["port"] == 8188, hw.freed)


def _wait(a, jid, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = a.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled", "blocked_age_check_unavailable"):
            return j
        time.sleep(0.2)
    return {"status": "timeout"}


def _compile(a, doc, area=None):
    return a.post("/api/recipes/compile", json={"recipe": doc, **({"area": area} if area else {})})


def e2e(a, mock_url):
    print("\n[M1] Recipes through the server (mock engine)")
    check = a.check
    cat = a.get("/api/recipes").json()
    check("Make lists three recipes", [r["id"] for r in cat["recipes"]] == ["portrait_still", "one_actor_film", "send_to_island"])
    check("the page gets the stages in their fixed order", [s["id"] for s in cat["stages"]] == list(R.STAGES))
    check("SFW mode: the nude wardrobe is not offered", all(w["id"] != "nude" for w in cat["wardrobe"]))
    check("the hardware map is reported as mock", cat["hardware"]["mock"] is True and len(cat["hardware"]["processes"]) == 2)
    ch = a.post("/api/characters", json={"name": "Mara", "age": 32, "gender": "woman", "style": "photo"})
    check("a new fictional adult is saved with a typed age", ch.status_code == 200 and ch.json().get("age") == 32, ch.text[:200])
    if ch.status_code != 200:
        return
    cid = ch.json()["id"]
    doc = _doc(subject={"character": cid}, look={"wardrobe": "jeans_tee"}, pose={"pose": "standing"},
               scene={"scene": "beach_golden"}, camera={})
    r = _compile(a, doc)
    check("the portrait still compiles", r.status_code == 200, r.text[:300])
    if r.status_code != 200:
        return
    comp = r.json()
    check("it compiles to the existing workshop_still kind", comp["kind"] == "workshop_still"
          and set(comp["params"]) <= {"character", "wardrobe", "look", "body", "seed"})
    check("a blank seed was drawn once and written back", isinstance(comp["recipe"]["seed"], int) and comp["params"]["seed"] == comp["recipe"]["seed"])
    check("pose, scene and the default camera become plain words in the look",
          "standing relaxed" in comp["params"]["look"] and "golden hour" in comp["params"]["look"] and "85mm" in comp["params"]["look"])
    check("the node drawer graph is the API graph with no _meta", comp["graph"] and all("_meta" not in n for n in comp["graph"].values()))
    check("the process is GPU0 (8188)", (comp.get("process") or {}).get("port") == 8188)
    again = _compile(a, comp["recipe"]).json()
    check("the same recipe and seed compile to the same hash", again["canonical_hash"] == comp["canonical_hash"])
    nude = _compile(a, _doc(subject={"character": cid}, look={"wardrobe": "nude"}))
    check("SFW mode: a nude wardrobe is refused at the Look stage", nude.status_code == 400 and nude.json().get("stage") == "look", nude.text[:200])

    control0 = requests.get(mock_url + "/mock/control").json()
    t0 = time.time()
    job = a.post("/api/jobs", json={"kind": comp["kind"], "params": comp["params"],
                                    "recipe": {"cache_key": comp["cache_key"], "canonical_hash": comp["canonical_hash"],
                                               "name": "Portrait still"}})
    check("the compiled job is accepted by the normal job queue", job.status_code == 200, job.text[:200])
    j = _wait(a, job.json()["id"]) if job.status_code == 200 else {"status": "refused"}
    latency = round(time.time() - t0, 3)
    check("the portrait still finishes on the mock engine", j["status"] == "done" and j.get("results"), j.get("error"))
    if j["status"] != "done":
        return
    flows = a.get(f"/api/jobs/{job.json()['id']}/workflow").json()["workflows"]
    check("the executed graph hashes the same as the compiled one", R.canonical_hash(flows[-1]) == comp["canonical_hash"])
    still = a.get(f"/api/items/{j['results'][0]['id']}").json()
    check("the result carries the recipe cache key and its file sha256",
          still.get("recipe_cache_key") == comp["cache_key"] and len(still.get("sha256") or "") == 64, still)
    check("the result keeps the stated age typed for the character", still.get("stated_age") == 32)
    cached = _compile(a, comp["recipe"]).json()
    check("compiling the same recipe again finds the saved result", (cached.get("cached") or {}).get("id") == still["id"])
    os.makedirs(os.path.dirname(LATENCY_FILE), exist_ok=True)
    json.dump({"measured": "portrait still recipe, submit to done, through /api/jobs",
               "engine": "mock (tests/mock_comfy.py); no GPU, no weights", "seconds": latency,
               "date": time.strftime("%Y-%m-%d"), "note": "Mock timing only. No GPU timing is claimed."},
              open(LATENCY_FILE, "w"), indent=1)
    check("one mock latency was measured and recorded", latency > 0 and os.path.exists(LATENCY_FILE), latency)

    exp = a.post("/api/recipes/export", json={"recipe": comp["recipe"]}).json()
    check("the export is a local .esrecipe.json", exp["filename"].endswith(".esrecipe.json") and "op://" not in exp["text"])
    back = a.post("/api/recipes/import", files={"file": (exp["filename"], exp["text"].encode(), "application/json")}).json()
    check("the exported recipe re-imports to the same canonical hash",
          back.get("kind") == "own" and back.get("matches") is True and back["canonical_hash"] == comp["canonical_hash"], back)
    ui = json.dumps({"nodes": [{"id": 1, "type": "MysteryNode", "widgets_values": []}], "links": []})
    third = a.post("/api/recipes/import", files={"file": ("graph.json", ui.encode(), "application/json")}).json()
    check("a third-party graph is stored, reported, and never decompiled",
          third.get("kind") == "third_party" and third.get("decompiled") is False and len(third.get("stored") or "") == 64, third)

    film_doc = {"recipe": "one_actor_film", "stages": {"subject": {"on": True, "values": {"still": still["id"]}},
                                                        "pose": {"on": True, "values": {"motion": "wind"}},
                                                        "camera": {"on": True, "values": {}},
                                                        "output": {"on": True, "values": {"seconds": 2}}}}
    fr = _compile(a, film_doc)
    check("the film compiles on that still", fr.status_code == 200, fr.text[:300])
    if fr.status_code != 200:
        return
    film = fr.json()
    check("it compiles to the existing film kind", film["kind"] == "film" and film["params"]["image"] == still["id"])
    check("the handoff is pixels plus a sidecar", film["sidecar"]["sha256"] == still["sha256"]
          and set(film["sidecar"]) >= {"width", "height", "seed", "model_family", "workflow_id", "sha256"}, film["sidecar"])
    check("the film reads the still with LoadImage", any(n["class_type"] == "LoadImage" and n["inputs"].get("image") == f"es_{still['id']}.png"
                                                         for n in film["graph"].values()))
    check("the film runs on GPU1 (8189)", (film.get("process") or {}).get("port") == 8189)
    fj = a.post("/api/jobs", json={"kind": film["kind"], "params": film["params"],
                                   "recipe": {"cache_key": film["cache_key"], "canonical_hash": film["canonical_hash"]}})
    fjob = _wait(a, fj.json()["id"]) if fj.status_code == 200 else {"status": "refused", "error": fj.text}
    check("the film finishes on the mock engine", fjob["status"] == "done", fjob.get("error"))
    if fjob["status"] == "done":
        flows = a.get(f"/api/jobs/{fj.json()['id']}/workflow").json()["workflows"]
        check("the executed film graph hashes the same as the compiled one", R.canonical_hash(flows[-1]) == film["canonical_hash"])
    seconds = _compile(a, {**film_doc, "stages": {**film_doc["stages"], "output": {"on": True, "values": {}}}})
    check("a film without a length is refused at Output", seconds.status_code == 400 and seconds.json().get("stage") == "output")

    edit = a.job("edit", {"image": still["id"], "op": "outfit", "text": "a straw sun hat"})
    control1 = requests.get(mock_url + "/mock/control").json()
    check("switching model family on one process frees memory first", edit["status"] == "done"
          and control1.get("frees", 0) > control0.get("frees", 0), (edit.get("error"), control0.get("frees"), control1.get("frees")))

    isl = _compile(a, {"recipe": "send_to_island", "stages": {"subject": {"on": True, "values": {"character": cid}}}})
    check("send to the island compiles to export_godot", isl.status_code == 200 and isl.json()["kind"] == "export_godot", isl.text[:200])
    pack = a.job("export_godot", isl.json()["params"]) if isl.status_code == 200 else {"status": "refused"}
    check("the island pack is made", pack["status"] == "done" and pack.get("results"), pack.get("error"))
    if pack.get("results"):
        dry = a.post("/api/island/dry-run", json={"item": pack["results"][0]["id"], "character": "mara"})
        body = dry.json() if dry.status_code == 200 else {}
        check("the island accepts the pack in dry-run, and project.godot is unchanged",
              dry.status_code == 200 and body.get("project_godot_unchanged") is True and body["summary"]["dry_run"] is True, dry.text[:300])
