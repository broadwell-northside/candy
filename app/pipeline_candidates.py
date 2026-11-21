"""Selectable still and upscale configs from research track 1.

The numbers live in pipeline_candidates.json. This module does not choose a
default. A candidate runs only after a local test records tested_locally and
an override file selects its id. Until then the existing registry pipeline
stays in place. No model weights are downloaded here.
"""
import copy
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_FILE = os.path.join(_HERE, "pipeline_candidates.json")
_EXTRA = os.path.join(_HERE, "research_candidates.json")


def _root():
    return os.path.abspath(os.path.join(_HERE, ".."))


def override_path():
    env = os.environ.get("EASY_STUDIO_PIPELINE_CANDIDATES")
    if env:
        return env
    out = os.environ.get("EASY_STUDIO_OUTPUTS") or os.path.join(_root(), "outputs")
    return os.path.join(out, "pipeline_candidates.json")


def load():
    with open(_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if os.path.isfile(_EXTRA):
        with open(_EXTRA, encoding="utf-8") as f:
            extra = json.load(f)
        data["finishing_order"] = extra.get("finishing_order") or []
        data["video_finishing_order"] = extra.get("video_finishing_order") or []
        data["motion_3d_order"] = extra.get("motion_3d_order") or []
        data["research_commit"] = extra.get("source_commit")
        have = {row.get("id") for row in data.get("candidates") or []}
        for row in extra.get("candidates") or []:
            if row.get("id") not in have:
                data.setdefault("candidates", []).append(row)
                have.add(row.get("id"))
    path = override_path()
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            over = json.load(f)
        if isinstance(over, dict):
            if "selected" in over:
                data["selected"] = over.get("selected")
            flags = over.get("tested_locally") or {}
            if isinstance(flags, dict):
                for row in data.get("candidates") or []:
                    if row["id"] in flags:
                        row["tested_locally"] = bool(flags[row["id"]])
    data["selected"] = data.get("selected") or None
    return data


def candidates():
    return copy.deepcopy(load().get("candidates") or [])


def candidate(cid):
    for row in candidates():
        if row["id"] == cid:
            return row
    return None


def widgets(row, node_type):
    """Published widget list for the first node of this type. None if absent."""
    if not row:
        return None
    for node in row.get("nodes") or []:
        if node.get("type") == node_type:
            return node.get("widgets_values")
    return None


def active(kind=None):
    """The selected candidate, only after a local test. Otherwise None.

    kind is "still" or "upscale". A still_refine row answers a still request.
    """
    data = load()
    chosen = data.get("selected")
    if not chosen:
        return None
    for row in data.get("candidates") or []:
        if row["id"] != chosen:
            continue
        if not row.get("tested_locally"):
            return None
        if kind and row.get("kind") != kind and not (kind == "still" and row.get("kind") == "still_refine"):
            return None
        return copy.deepcopy(row)
    return None


def finishing_order():
    return list(load().get("finishing_order") or [])


def video_finishing_order():
    return list(load().get("video_finishing_order") or [])


def motion_3d_order():
    return list(load().get("motion_3d_order") or [])


def selection_note(kind):
    """Provenance for a tested selection. Untested candidates add nothing."""
    row = active(kind)
    if not row:
        return None
    return {"id": row["id"], "status": row.get("status") or "NOT_RUN", "tested_locally": True}
