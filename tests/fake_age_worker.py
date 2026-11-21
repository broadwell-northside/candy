"""Stand-in for app/workers/age_check_worker.py in tests (no torch / no model download).
Same line protocol. 'Flags' any picture whose top-left 16x16 corner is magenta (the mock ComfyUI paints that
when a prompt contains the test word), says 'unchecked' for flat one-colour pictures (no face), else 'ok'."""
import json
import os
import sys

from PIL import Image

print(json.dumps({"ready": True, "device": "cpu (fake)"}), flush=True)
LOG = os.environ.get("MOCK_AGE_LOG")
INJECT = os.environ.get("MOCK_AGE_INJECT")
for line in sys.stdin:
    path = ""
    try:
        path = json.loads(line)["path"]
        name = os.path.basename(path)
        injected = None
        if INJECT and os.path.exists(INJECT):
            spec = json.load(open(INJECT, encoding="utf-8"))
            if spec.get("apply") == "still" and "agecheck_" not in name:
                injected = dict(spec.get("result") or {"status": "unchecked", "reason": "injected unchecked disposition"})
        if injected is not None:
            out = injected
        else:
            with Image.open(path) as im:
                im = im.convert("RGB")
                c = im.getpixel((4, 4))
                flat = im.getextrema() and all(lo == hi for lo, hi in im.getextrema())
            if os.environ.get("MOCK_HOLD_MIDDLE_FRAME") == "1" and "agecheck_" in name and name.endswith("_1.png"):
                out = {"status": "unchecked", "faces": 0, "reason": "middle frame was not checked"}
            elif c == (1, 2, 3):
                out = {"status": "unchecked", "faces": 0, "reason": "held for the test"}
            elif c == (255, 0, 255):
                out = {"status": "flag", "faces": 1, "p_under21": 0.93}
            elif flat:
                out = {"status": "unchecked", "faces": 0}
            else:
                out = {"status": "ok", "faces": 1, "p_under21": 0.04}
    except Exception as e:
        out = {"status": "unavailable", "reason": str(e)}
    if LOG:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{path}\t{out.get('status')}\t{out.get('reason') or ''}\n")
    print(json.dumps(out), flush=True)
