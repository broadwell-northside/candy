"""A stand-in for the few OpenCV calls app/workers/face_worker.py makes. Tests only; it reads no picture.

A "picture" is a file path. If a file `<path>.lm.json` sits next to it, it holds what the stand-in sees:
  {"faces": [[x, y, w, h, 10 landmark numbers, score], ...], "embedding": [numbers]}
With no such file, imread returns None, like OpenCV for a file it cannot read.
"""
import json
import os

__version__ = "0.0-stand-in"


class _Image:
    def __init__(self, path, side):
        self.path, self.side, self.shape = path, side, (side, side, 3)


class _Vector(list):
    def flatten(self):
        return self


def imread(path):
    try:
        with open(path + ".lm.json", encoding="utf-8") as f:
            side = int(json.load(f).get("side") or 640)
    except (OSError, ValueError):
        return None
    return _Image(path, side)


def resize(image, size):
    return _Image(image.path, max(size))


def _seen(image):
    with open(image.path + ".lm.json", encoding="utf-8") as f:
        return json.load(f)


class FaceDetectorYN:
    @staticmethod
    def create(model, config, size, score, nms, top_k):
        return FaceDetectorYN()

    def setInputSize(self, size):
        self.size = size

    def detect(self, image):
        faces = _seen(image).get("faces") or []
        return 1, ([list(map(float, row)) for row in faces] or None)


class FaceRecognizerSF:
    @staticmethod
    def create(model, config):
        return FaceRecognizerSF()

    def alignCrop(self, image, row):
        return image

    def feature(self, aligned):
        return _Vector(float(v) for v in (_seen(aligned).get("embedding") or []))
