"""Lanes that were built apart, checked together through the running app (stand-in engine, stand-in Keychain).

Nothing here sends a request to a hosted service: every hosted case is one the app must refuse before it sends."""
import os

SENTINEL = "sk-integration0123456789abcdefABCDEF"
ADULT = {"name": "Beach", "gender": "woman", "age": 31, "style": "photo"}


def unit(check):
    """The smallest first run: only the age check and the Wan 5B group on disk. Nothing is run; this reads the cards."""
    print("\n[integration] The smallest download set: age check + Wan 2.2 5B")
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
    import routes_models as R
    import videomodels as VM
    cat = R.catalog()
    have = {f["name"] for g in ("video-wan5b", "safety") for f in cat[g]["files"]}
    rows = VM.public(have)
    ready = [(r["id"], r["mode"]) for r in rows if r["ready"]]
    check("with only the age check and the Wan 5B group installed, exactly the two 5B cards are ready",
          sorted(ready) == [("wan22_5b_i2v", "i2v"), ("wan22_5b_t2v", "t2v")], ready)
    t2v = next((r["id"] for r in rows if r["ready"] and r["mode"] == "t2v"), None)
    i2v = next((r["id"] for r in rows if r["ready"] and r["mode"] == "i2v"), None)
    check("Build a video then picks the 5B models: words only -> text to video, with a start picture -> picture to video",
          (t2v, i2v) == ("wan22_5b_t2v", "wan22_5b_i2v"), (t2v, i2v))
    check("their templates need only files that group installs",
          all(set(VM.model_files(VM.load(w))) <= have for w in ("vm_wan22_5b_t2v_api.json", "vm_wan22_5b_i2v_api.json")))
    check("the age check's group puts every file the checker needs on disk",
          {"model.safetensors", "config.json", "preprocessor_config.json", "yunet_final.pth"} <= have)


def e2e(a, mock_url, requests):
    check = a.check
    print("\n[integration] Models page, hosted extend and the first-run switch, through the running app")
    r = a.get("/api/models/groups")
    st = r.json() if r.status_code == 200 else {}
    groups = {g["id"]: g for g in st.get("groups") or []}
    check("the Models page lists the download groups with the 50 GB floor and a free-space reading",
          r.status_code == 200 and st.get("floor_bytes") == 50 * 1024 ** 3 and "safety" in groups and "image" in groups, r.text[:200])
    check("a group the lock does not pin yet cannot be downloaded, and says so",
          all(g.get("can_download") is False and g.get("reason") for g in groups.values() if g.get("unpinned")), [g["id"] for g in groups.values() if g.get("unpinned")])
    refused = a.post("/api/models/download", json={"group": "no_such_group"})
    check("a download click for an unknown group is refused plainly", refused.status_code == 400, refused.text[:160])
    evil = a.s.post(a.base + "/api/models/download", json={"group": "safety"}, headers={"Host": "example.com"}, timeout=30)
    check("a download click that does not come from this computer's own address is refused", evil.status_code in (400, 403), evil.status_code)
    check("the phase two switch starts hidden", a.get("/api/phase_two").json() == {"hidden": True})
    check("while Phase two is hidden the Models page has no face check group, and no other group holds its files",
          "face" not in groups and not [g["id"] for g in groups.values() if any(f["name"].endswith(".onnx") for f in g["files"])],
          sorted(groups))

    j = a.job("create", {"dna": dict(ADULT), "extra_scene": "fully clothed in a linen shirt, walking on a quiet beach", "count": 1,
                         "aspect": "wide", "look": "realistic", "advanced": {"seed": 20261121}})
    still = (j.get("results") or [None])[0]
    check("I1: a still of one fictional adult", j["status"] == "done" and still, j.get("error"))
    if not still:
        return
    j = a.job("video", {"image": still["id"], "text": "a woman walks down the beach", "seconds": 2, "mode": "fast", "quality": "480"})
    vid = (j.get("results") or [None])[0]
    check("I2: a clip is built from it", j["status"] == "done" and vid, j.get("error"))
    if not vid:
        return

    def sent():
        return len(requests.get(mock_url + "/mock/log").json())

    n0 = sent()
    params = {"video": vid["id"], "segments": [{"text": "she stops and looks up at the trees", "seconds": 2}], "engine": "dashscope_video"}
    j = a.job("extend", params)
    check("I3: extending on a hosted engine with no key is refused plainly, and nothing ran anywhere",
          j["status"] in ("error", "refused") and "key" in (j.get("error") or "").lower() and sent() == n0, j.get("error"))
    r = a.post("/api/providers/key", json={"name": "dashscope", "key": SENTINEL})
    check("I4: a key typed once is stored and never shown back", r.status_code == 200 and SENTINEL not in r.text and SENTINEL not in a.get("/api/providers").text, r.text[:160])
    try:
        j = a.job("extend", params)
        check("I5: with a key but the hosted-media switch off, the hosted extend is refused before any call",
              j["status"] in ("error", "refused") and "hosted media" in (j.get("error") or "").lower() and sent() == n0, j.get("error"))
        a.post("/api/providers/hosted-media", json={"on": True, "confirm": "I understand"})
        j = a.job("extend", dict(params, loras=["anything.safetensors"]))
        check("I6: with the switch on, a LoRA still keeps the clip on this machine: refused before any call",
              j["status"] in ("error", "refused") and sent() == n0, j.get("error"))
        j = a.job("video_api", {"image": still["id"], "text": "a woman walks", "seconds": 3, "advanced": {"loras": [{"name": "x.safetensors", "strength": 1}]}})
        check("I7: the Video (API) job refuses a LoRA too, before any call",
              j["status"] in ("error", "refused") and "LoRA" in (j.get("error") or ""), j.get("error"))
    finally:
        a.post("/api/providers/hosted-media", json={"on": False})
        a.s.delete(a.base + "/api/providers/key/dashscope", timeout=30)
    left = a.get("/api/providers").json()
    check("I8: the switch is off again and the key is gone", left["hosted_media"] is False and all(k["configured"] is False for k in left["keys"]), left)
    leaked = []
    for d, _s, fs in os.walk(os.environ.get("EASY_STUDIO_OUTPUTS") or "."):
        for f in fs:
            if f.endswith((".json", ".txt", ".log", ".md")) and "node_modules" not in d:
                try:
                    if SENTINEL in open(os.path.join(d, f), errors="ignore").read():
                        leaked.append(f)
                except OSError:
                    pass
    check("I9: the key is in no file under the outputs folder", not leaked, leaked)
