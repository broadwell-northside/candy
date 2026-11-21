# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The face check behind enrolment: one small interface, with the model in a worker process.

The worker reads one JSON line per request and answers one JSON line. It has two requests:
  {"path": ..., "step": ...}                      -> {"faces": n, "step_ok": true|false, "embedding": [numbers]}
  {"liveness": [{"path": ..., "step": ...}, ...]} -> {"live": true|false, "reason": "..."}
It starts with {"ready": true, "model": "..."}; anything else means it is not installed.

The liveness request is the worker's own verdict on a whole capture. A posted picture with the right
nonce proves nothing by itself, so enrolment needs that verdict to be true. What the shipped worker judges:
each frame shows the pose that was asked, the frames are distinct pictures, and one face runs through
all of them. What it cannot judge, because it sees five landmarks on still pictures: whether the person
is real and in front of the camera, or a recording of a person making the poses, or a staged series of pictures
shown to the camera in turn. A single still photograph is unlikely to pass. That limit is stated in
app/workers/face_logic.py and in the pull request that ships the worker. The worker names the kind of
verdict it gives in its first line ("liveness"); the app accepts only the kinds in ACCEPTED_LIVENESS and records
the kind with the enrolment, so a worker that names none, or an unknown one, saves nothing.

The worker needs the two model files and the library in the picture engine's Python. Without them it
says why in one of a few fixed ways (REASONS), and everything that needs a face check refuses.

The worker's path can be swapped for a stand-in only in a test run: EASY_STUDIO_FACE_WORKER is read only
when EASY_STUDIO_TEST_RUN is 1 as well, so a stray variable alone changes nothing.
"""
import json
import math
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ("face_camera", "turn_left", "turn_right", "tilt", "look_up")
MATCH_AT = 0.80      # cosine similarity a face needs when the worker names no threshold of its own (the test stand-in)
ACCEPTED_LIVENESS = ("poses_only", "pad")  # "pad": a worker with a real presentation-attack check. Nothing else is accepted.
MIN_MATCH = 0.363    # never below this: the value OpenCV publishes for "same person" with the shipped embedding
NOT_INSTALLED = "The face check is not installed on this machine yet, so enrolment cannot start."
REASONS = {  # what a worker may say it could not start for; anything else is shown as NOT_INSTALLED
    "files_missing": "The face check is not installed on this machine yet: its two model files are missing, so enrolment cannot start.",
    "hash_mismatch": "The face check's model files are not the ones this app expects, so enrolment cannot start. Fetch them again from the model lock.",
    "library_failed": "The face check's library (OpenCV) did not start, so enrolment cannot start. The setup notes name the older version to use instead.",
}


def testing():
    """True in a test run only. Environment overrides of the worker and of the backup tool need it."""
    return os.environ.get("EASY_STUDIO_TEST_RUN") == "1"


class FaceUnavailable(RuntimeError):
    """No working face check. Callers refuse; they never carry on without it."""


def worker_path():
    if testing() and os.environ.get("EASY_STUDIO_FACE_WORKER"):
        return os.environ["EASY_STUDIO_FACE_WORKER"]
    return os.path.join(HERE, "workers", "face_worker.py")


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def centroid(vectors):
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(len(vectors[0]))]


def matches(embedding, match_set, model):
    """True when a face is the enrolled one. No match set, no model name, or a different model, is never a match:
    the enrolment's numbers mean nothing for another model."""
    if not isinstance(match_set, dict) or not match_set.get("centroid") or not embedding:
        return False, 0.0
    if not model or match_set.get("model") != model:
        return False, 0.0
    score = cosine(embedding, match_set["centroid"])
    return score >= max(float(match_set.get("threshold") or MATCH_AT), MIN_MATCH), round(score, 4)


class FaceCheck:
    def __init__(self, python=None, timeout=30, model_dir=None):
        self.python = python or sys.executable
        self.timeout = timeout
        self.model_dir = model_dir
        self.proc = None
        self.model = None
        self.threshold = MATCH_AT
        self.liveness_kind = None
        self.lock = threading.Lock()
        self.last_error = ""

    def _kill(self):
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None

    def _read(self):
        box = {}

        def read():
            try:
                box["line"] = self.proc.stdout.readline()
            except Exception as exc:  # noqa: BLE001
                box["err"] = exc

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        thread.join(self.timeout)
        if thread.is_alive() or box.get("err") or not str(box.get("line") or "").strip():
            raise FaceUnavailable("The face check did not answer.")
        try:
            return json.loads(box["line"])
        except ValueError:
            raise FaceUnavailable("The face check gave an answer that could not be read.")

    def _start(self):
        script = worker_path()
        if not os.path.isfile(script):
            raise FaceUnavailable(NOT_INSTALLED)
        self.proc = subprocess.Popen([self.python, script] + ([self.model_dir] if self.model_dir else []), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                     env=dict(os.environ, PYTHONUNBUFFERED="1"))
        try:
            hello = self._read()
        except FaceUnavailable:
            self._kill()
            raise FaceUnavailable(NOT_INSTALLED)
        if not isinstance(hello, dict) or hello.get("ready") is not True or not hello.get("model"):
            self._kill()
            raise FaceUnavailable(REASONS.get(hello.get("code") if isinstance(hello, dict) else None, NOT_INSTALLED))
        self.model = str(hello["model"])
        kind = hello.get("liveness")
        self.liveness_kind = kind if isinstance(kind, str) else None
        said = hello.get("threshold")
        ok = isinstance(said, (int, float)) and not isinstance(said, bool) and math.isfinite(said)
        self.threshold = max(float(said), MIN_MATCH) if ok else MATCH_AT

    def available(self):
        with self.lock:
            try:
                if not self.proc or self.proc.poll() is not None:
                    self._start()
                self.last_error = ""
                return True
            except FaceUnavailable as exc:
                self.last_error = str(exc)
                return False

    def inspect(self, path, step=""):
        """One picture: how many faces, whether it shows the asked step, and the face's embedding."""
        with self.lock:
            try:
                if not self.proc or self.proc.poll() is not None:
                    self._start()
                self.proc.stdin.write(json.dumps({"path": os.path.abspath(path), "step": step}) + "\n")
                self.proc.stdin.flush()
                answer = self._read()
            except FaceUnavailable:
                self._kill()
                raise
            except Exception as exc:  # noqa: BLE001
                self._kill()
                raise FaceUnavailable("The face check stopped: %s" % exc)
        if not isinstance(answer, dict) or not isinstance(answer.get("faces"), int):
            raise FaceUnavailable("The face check gave an answer that could not be read.")
        emb = answer.get("embedding")
        if not (isinstance(emb, list) and emb and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in emb)):
            emb = []
        return {"faces": answer["faces"], "step_ok": answer.get("step_ok") is True, "embedding": emb, "model": self.model}

    def liveness(self, frames):
        """The worker's verdict on a whole capture. Only an explicit {"live": true} counts."""
        with self.lock:
            try:
                if not self.proc or self.proc.poll() is not None:
                    self._start()
                ask = {"liveness": [{"path": os.path.abspath(f["path"]), "step": f["step"]} for f in frames]}
                self.proc.stdin.write(json.dumps(ask) + "\n")
                self.proc.stdin.flush()
                answer = self._read()
            except FaceUnavailable:
                self._kill()
                raise
            except Exception as exc:  # noqa: BLE001
                self._kill()
                raise FaceUnavailable("The face check stopped: %s" % exc)
        if not isinstance(answer, dict) or not isinstance(answer.get("live"), bool):
            raise FaceUnavailable("The face check gave no live-check answer.")
        if self.liveness_kind not in ACCEPTED_LIVENESS:
            raise FaceUnavailable("The live check this face check offers is not one the app accepts.")
        return answer["live"], str(answer.get("reason") or "")

    def stop(self):
        with self.lock:
            self._kill()
