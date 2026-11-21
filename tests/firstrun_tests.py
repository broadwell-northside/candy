# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""First run: the PHASE_TWO switch and SD 1.5 as a Create engine. No network, no weights; the mock ComfyUI draws."""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "app"))


def unit(check):
    print("\n[firstrun] PHASE_TWO file, the SD 1.5 template, its lock row and profile card")
    import phase_two
    import sd15
    import machine_profiles
    with tempfile.TemporaryDirectory() as out:
        check("phase two is hidden when nothing is saved", phase_two.hidden(out) is True)
        check("the switch shows it and keeps the choice", phase_two.set_hidden(out, False) is False and phase_two.hidden(out) is False)
        check("the switch hides it again", phase_two.set_hidden(out, True) is True and phase_two.hidden(out) is True)
        open(os.path.join(out, phase_two.FILE), "w").write("not json")
        check("a broken file means hidden", phase_two.hidden(out) is True)
    wf = json.load(open(os.path.join(ROOT, "app", "workflows", sd15.WORKFLOW), encoding="utf-8"))
    titles = {n.get("_meta", {}).get("title") for n in wf.values()}
    check("the SD 1.5 template has the titled nodes Create fills in", {"POSITIVE", "NEGATIVE", "SIZE", "SEED"} <= titles, titles)
    ckpt = [n["inputs"]["ckpt_name"] for n in wf.values() if n["class_type"] == "CheckpointLoaderSimple"]
    lock = json.load(open(os.path.join(ROOT, "config", "server_model_lock.json"), encoding="utf-8"))
    row = next((r for r in lock["rows"] if r["id"] == "sd15.v1_5_pruned_emaonly"), None)
    check("the template's checkpoint is the locked SD 1.5 file", row and ckpt == [row["comfy_link"]["name"]], ckpt)
    check("the lock row is pinned and hashed (metadata only, nothing downloaded)",
          row and re.fullmatch(r"[0-9a-f]{40}", row["rev"]) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and row["size"] > 4e9)
    eng = machine_profiles.load()["engines"]["sd15"]
    check("the machine profiles carry an SD 1.5 card that names the template and the lock row",
          eng["workflow"] == sd15.WORKFLOW and eng["lock_id"] == row["id"] and "m5_max" in eng["fits"])
    check("SD 1.5 sizes stay near 512 pixels", all(w * h <= 768 * 512 for w, h in map(sd15.size_for, ("portrait", "square", "wide", "x"))))


def e2e(a):
    check = a.check
    print("\n[firstrun] Phase two switch and Photo (SD 1.5) through the app")
    check("phase two is hidden by default", a.get("/api/phase_two").json() == {"hidden": True})
    check("a non-boolean is refused", a.post("/api/phase_two", json={"hidden": "no"}).status_code == 400)
    check("the switch shows phase two", a.post("/api/phase_two", json={"hidden": False}).json() == {"hidden": False}
          and a.get("/api/phase_two").json() == {"hidden": False})
    a.post("/api/phase_two", json={"hidden": True})
    check("and hides it again", a.get("/api/phase_two").json() == {"hidden": True})
    feats = {f["id"]: f for f in a.get("/api/status").json()["features"]}
    check("SD 1.5 is a listed tool", "create_sd15" in feats, list(feats)[:5])
    dna = {"gender": "woman", "age": 27, "style": "photo", "name": "Sd"}
    j = a.job("create", {"dna": dna, "count": 1, "engine": "sd15"})
    check("Create with Photo (SD 1.5) makes a picture", j["status"] == "done" and len(j["results"]) == 1, j.get("error"))
    if j.get("results"):
        prov = j["results"][0].get("provenance") or {}
        check("it says which engine drew it", prov.get("workflow") == "image_sd15_api.json" and j["results"][0].get("model") == "Stable Diffusion 1.5", prov)
        wf = a.get("/api/jobs/%s/workflow" % j["id"]).json()["workflows"][-1]
        blob = json.dumps(wf)
        sizes = [n["inputs"] for n in wf.values() if isinstance(n, dict) and n.get("class_type") == "EmptyLatentImage"]
        check("the graph that ran is the SD 1.5 one, at about 512 pixels",
              "v1-5-pruned-emaonly" in blob and sizes and sizes[0]["width"] * sizes[0]["height"] <= 768 * 512, sizes)
    j = a.job("create", {"dna": {**dna, "age": 17}, "count": 1, "engine": "sd15"})
    check("a stated age under 21 is still refused on SD 1.5", j["status"] in ("refused", "error") and not j.get("results"), j.get("status"))
    j = a.job("create", {"dna": {**dna, "style": "anime"}, "count": 1, "engine": "sd15"})
    check("SD 1.5 is for the Realistic photo style only", j["status"] in ("refused", "error") and "photo" in (j.get("error") or "").lower(), j.get("error"))
    j = a.job("create", {"dna": dna, "count": 1, "engine": "sd15"}, area="adult")
    check("SD 1.5 does not run in the 18+ section", j["status"] in ("refused", "error") and not j.get("results"), j.get("status"))
