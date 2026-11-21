"""Which computer is running the first tests.

The M5 Max is the default. The desktop cards stay in the file for later.
A file at outputs/machine_profile.json, or EASY_STUDIO_MACHINE, can pick another id.
"""
import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "machine_profiles.json")


def _root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load():
    with open(_FILE, encoding="utf-8") as f:
        data = json.load(f)
    env = os.environ.get("EASY_STUDIO_MACHINE")
    if env:
        data["default"] = env
    path = os.path.join(os.environ.get("EASY_STUDIO_OUTPUTS") or os.path.join(_root(), "outputs"), "machine_profile.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            over = json.load(f)
        if isinstance(over, dict) and over.get("default"):
            data["default"] = over["default"]
    return data


def active():
    data = load()
    chosen = data.get("default") or "m5_max"
    profiles = data.get("profiles") or {}
    row = dict(profiles.get(chosen) or profiles["m5_max"])
    row["id"] = chosen if chosen in profiles else "m5_max"
    return row


def check_chroma_file(filename):
    """The Mac profile cannot be pointed at an fp8-only Chroma weight."""
    row = active()
    name = str(filename or "")
    if row.get("forbid_fp8_chroma") and "fp8" in name.lower():
        raise ValueError("This machine needs a bf16 or fp16 Chroma file, not an fp8-only weight.")
    return name
