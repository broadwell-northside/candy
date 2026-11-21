"""Stand-in for the face-check worker in tests (no model). Same line protocol as app/workers/face_worker.py.

It reads a code the tests paint into the bottom-right corner of each picture: red = whose face
(a number per made-up person), green = which step the picture shows, blue = how many faces.
For the liveness request it says "not live" when any picture has the replay code (7, 7, 7) in its
bottom-left corner, and when the worker is told to give no verdict (FAKE_FACE_NO_VERDICT file).
"""
import os
import hashlib
import json
import sys

from PIL import Image

STEPS = ("face_camera", "turn_left", "turn_right", "tilt", "look_up")
hello = {"ready": True, "model": "test-stand-in", "liveness": "poses_only"}
if os.environ.get("FAKE_FACE_LIVENESS") == "none":  # a worker that names no kind of live verdict
    del hello["liveness"]
elif "FAKE_FACE_LIVENESS" in os.environ:
    hello["liveness"] = os.environ["FAKE_FACE_LIVENESS"]
print(json.dumps(hello), flush=True)
for line in sys.stdin:
    try:
        ask = json.loads(line)
        if "liveness" in ask:
            if os.path.exists(os.environ.get("FAKE_FACE_NO_VERDICT", "/nonexistent")):
                print(json.dumps({"faces": 0}), flush=True)
                continue
            replay = False
            for row in ask["liveness"]:
                with Image.open(row["path"]) as im:
                    replay = replay or im.convert("RGB").getpixel((4, im.size[1] - 4)) == (7, 7, 7)
            print(json.dumps({"live": not replay, "reason": "replay code" if replay else ""}), flush=True)
            continue
        with Image.open(ask["path"]) as im:
            im = im.convert("RGB")
            r, g, b = im.getpixel((im.size[0] - 4, im.size[1] - 4))
        told = os.environ.get("FAKE_FACE_INJECT", "/nonexistent")
        if os.path.exists(told):  # tests say what the worker sees in a generated picture: {"faces": n, "person": id}
            spec = json.load(open(told, encoding="utf-8"))
            r, b = int(spec.get("person", 0)), int(spec.get("faces", 0)) * 60
        faces = round(b / 60)
        shown = STEPS[round(g / 40) - 1] if 1 <= round(g / 40) <= len(STEPS) else ""
        person = round(r / 50) % 8
        jitter = hashlib.sha256(open(ask["path"], "rb").read()).digest()
        emb = [(1.0 if i == person else 0.0) + jitter[i] / 2550.0 for i in range(8)]
        out = {"faces": faces, "step_ok": bool(ask.get("step")) and shown == ask.get("step"), "embedding": emb if faces == 1 else []}
    except Exception as exc:  # noqa: BLE001
        out = {"faces": 0, "step_ok": False, "embedding": [], "error": str(exc)}
    print(json.dumps(out), flush=True)
