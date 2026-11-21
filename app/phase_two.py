# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The PHASE_TWO switch: the likeness machinery is hidden from the first-run path by default.

Phase two is the My likeness card, enrolment and the face worker, Add photos and the 3D self-model.
The code stays in the app. This file only holds one answer: are those screens shown? The default is
hidden. One switch in Setup shows them; it is kept in outputs/phase_two.json.
Other code asks `hidden(out_dir)`. Hiding is a screen decision: the rails and the routes do not change.
"""
import json
import os

FILE = "phase_two.json"


def _path(out_dir):
    return os.path.join(out_dir, FILE)


def hidden(out_dir):
    """True unless the owner switched phase two on."""
    try:
        with open(_path(out_dir), encoding="utf-8") as f:
            return json.load(f).get("show") is not True
    except (OSError, ValueError, AttributeError):
        return True


def set_hidden(out_dir, value):
    os.makedirs(out_dir, exist_ok=True)
    tmp = _path(out_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"show": not bool(value)}, f)
    os.replace(tmp, _path(out_dir))
    return hidden(out_dir)
