"""Check every Easy Studio workflow against a REAL ComfyUI (no GPU needed).

It creates tiny fake model files (so ComfyUI's dropdown lists contain the right names),
then sends each workflow to ComfyUI's /prompt endpoint. ComfyUI validates every node name,
every input name, every link type and every dropdown value before it accepts a job --
so "accepted" means the workflow is correct for that ComfyUI version.
(The jobs then fail instantly when ComfyUI tries to read the fake model files; that is expected.)

  python tests/validate_real_comfy.py --comfy-dir /path/to/ComfyUI --url http://127.0.0.1:8188
Only use this on a TEST copy of ComfyUI: it adds empty placeholder model files.
"""
import argparse, glob, json, os, sys, uuid, importlib.util
import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("dm", os.path.join(ROOT, "install", "download_models.py"))
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)
INPUTS = ["image1.png", "image2.png", "image3.png", "mask.png", "pose.png", "start.png", "end.png"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comfy-dir", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8188")
    a = ap.parse_args()
    made = []
    for group in dm.MODELS.values():
        for folder, name, _url, _size in group:
            p = os.path.join(a.comfy_dir, "models", folder, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if not os.path.exists(p):
                open(p, "wb").close(); made.append(p)
    inp = os.path.join(a.comfy_dir, "input"); os.makedirs(inp, exist_ok=True)
    for n in INPUTS:
        Image.new("RGB", (512, 512), (128, 100, 90)).save(os.path.join(inp, n))
    ok = True
    sys.path.insert(0, os.path.join(ROOT, "app"))
    import wfdetect
    for f in sorted(glob.glob(os.path.join(ROOT, "app", "workflows", "*.json"))):
        wf = json.load(open(f))
        if os.path.basename(f).startswith("vm_"):  # Video studio models: fill them the way the app does
            an = wfdetect.analyse(wf)
            wf = wfdetect.fill(wf, an, prompt="an adult woman smiles", negative="blurry",
                               images={"start": "start.png", "end": "end.png"}, seed=1, seconds=3,
                               width=640, height=384, frame_rule=8 if "ltx" in f else 4)
        for node in wf.values():
            node.pop("_meta", None)
        r = requests.post(a.url.rstrip("/") + "/prompt", json={"prompt": wf, "client_id": str(uuid.uuid4())}, timeout=30)
        j = r.json()
        good = r.status_code == 200 and not j.get("node_errors")
        ok &= good
        print(("ACCEPTED " if good else "REJECTED ") + os.path.basename(f) + ("" if good else "  " + json.dumps(j)[:800]))
    requests.post(a.url.rstrip("/") + "/queue", json={"clear": True}, timeout=10)
    print(f"(created {len(made)} placeholder model files)")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
