# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The face-check worker: YuNet finds the face and its five landmarks, SFace makes the embedding.

It runs in the picture engine's own Python (the one that has OpenCV), reads one JSON line per request on stdin and
answers one JSON line, as app/face_check.py describes. Its first line is {"ready": true, "model": ..., "threshold": ...}
or {"ready": false, "code": ...}. The rules live in app/workers/face_logic.py; the three functions here are the only
ones that touch OpenCV:  load(path), detect(image) and embed(image, face).

  python face_worker.py <folder with the two model files>

Both files are checked against the SHA-256 pinned in face_logic.MODEL_FILES before anything is loaded. Nothing is
downloaded, and the worker opens no network connection. It reads only the picture paths it is asked about.

What it cannot do: tell a real person from a recording or from a staged series of pictures (see face_logic.py).
If OpenCV 4.14.0.94 does not import with the numpy that is installed, the documented alternative is
opencv-python-headless 4.13.0.92 (config/server_model_lock.json, runtimes.opencv_python_headless.fallback).
"""
import hashlib
import json
import os
import sys

import face_logic as L

MAX_SIDE = 2048  # a larger picture is looked at in a copy scaled down to this, so a huge file cannot stall the worker


def say(obj):
    print(json.dumps(obj), flush=True)


def model_name():
    """The model's identity: both files' short hashes. A different file means a different model."""
    return "yunet-2023mar:%s+sface-2021dec:%s" % (L.MODEL_FILES["detector"]["sha256"][:8], L.MODEL_FILES["embedder"]["sha256"][:8])


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_files(folder):
    """The paths of the two model files, or a (code, nothing) answer: files_missing or hash_mismatch."""
    paths = {}
    for key, want in L.MODEL_FILES.items():
        path = os.path.join(folder or "", want["file"])
        if not os.path.isfile(path):
            return "files_missing", None
        paths[key] = path
    for key, want in L.MODEL_FILES.items():
        if sha256(paths[key]) != want["sha256"]:
            return "hash_mismatch", None
    return None, paths


# ---- the three calls that need OpenCV ----------------------------------------------------------------------------
class Engine:
    def __init__(self, cv2, paths):
        self.cv2 = cv2
        self.detector = cv2.FaceDetectorYN.create(paths["detector"], "", (320, 320), 0.7, 0.3, 5000)
        self.embedder = cv2.FaceRecognizerSF.create(paths["embedder"], "")

    def load(self, path):
        image = self.cv2.imread(path)
        if image is None:
            return None
        h, w = image.shape[:2]
        if max(h, w) > MAX_SIDE:
            scale = MAX_SIDE / float(max(h, w))
            image = self.cv2.resize(image, (int(w * scale), int(h * scale)))
        return image

    def detect(self, image):
        """Every face found: [{"row": the detector's row, "landmarks": five (x, y) points, "score": number}]."""
        h, w = image.shape[:2]
        self.detector.setInputSize((w, h))
        _ok, faces = self.detector.detect(image)
        out = []
        for row in (faces if faces is not None else []):
            numbers = [float(v) for v in row]
            out.append({"row": row, "landmarks": [(numbers[4 + 2 * i], numbers[5 + 2 * i]) for i in range(5)], "score": numbers[14]})
        return out

    def embed(self, image, face):
        aligned = self.embedder.alignCrop(image, face["row"])
        return [float(v) for v in self.embedder.feature(aligned).flatten()]


def look(engine, path):
    """One picture: the number of faces and, for exactly one, its pose, shape and embedding."""
    image = engine.load(path)
    if image is None:
        return {"faces": 0, "pose": None, "shape": None, "embedding": []}
    faces = engine.detect(image)
    if len(faces) != 1:
        return {"faces": len(faces), "pose": None, "shape": None, "embedding": []}
    lm = faces[0]["landmarks"]
    p = L.pose(lm)
    return {"faces": 1, "pose": p, "shape": L.shape(lm), "embedding": engine.embed(image, faces[0]) if p else []}


def answer(engine, ask):
    if "liveness" in ask:
        rows = []
        for item in ask["liveness"]:
            seen = look(engine, str(item["path"]))
            rows.append(dict(seen, step=str(item.get("step") or "")))
        live, reason = L.verdict(rows, L.THRESHOLD)
        return {"live": live, "reason": reason}
    seen = look(engine, str(ask["path"]))
    ok = seen["faces"] == 1 and seen["pose"] is not None and L.step_ok(str(ask.get("step") or ""), seen["pose"])
    return {"faces": seen["faces"], "step_ok": bool(ok), "embedding": seen["embedding"]}


def main(argv):
    folder = argv[1] if len(argv) > 1 else ""
    code, paths = check_files(folder)
    if code:
        say({"ready": False, "code": code})
        return 0
    try:
        import cv2
        engine = Engine(cv2, paths)
    except Exception:  # noqa: BLE001 - whatever stopped the library or the models from loading
        say({"ready": False, "code": "library_failed"})
        return 0
    say({"ready": True, "model": model_name(), "threshold": L.THRESHOLD, "liveness": L.LIVENESS_KIND,
         "library": "opencv " + str(getattr(cv2, "__version__", "?"))})
    for line in sys.stdin:
        try:
            out = answer(engine, json.loads(line))
        except Exception as exc:  # noqa: BLE001 - one bad request must not stop the worker
            out = {"faces": 0, "step_ok": False, "embedding": [], "error": type(exc).__name__}
        say(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
