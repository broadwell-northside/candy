"""A character's "DNA": the chips/sliders that describe them, saved as JSON, turned into prompts."""
import json
import os
import re
import shutil
import time
import uuid

import catalog
import safety

TEXT_FIELDS = ("name", "notes", "extra")


def _chip(group_id, chip_id):
    for g in catalog.CHARACTER_GROUPS:
        if g["id"] == group_id:
            return catalog.find(g["chips"], chip_id)
    return None


def _reject_stated_age(raw):
    """Check the caller's ages before any field is rewritten. Returns an error, or None."""
    if safety.people_in(raw):
        ok, _, msg = safety.require_group_ages(raw)
        if not ok:
            return msg
    ok, _, msg = safety.require_stated_age(raw)
    return None if ok else msg


def normalise(dna):
    """Clean user input. A stated age of 21 or older is required first.

    Invalid or missing ages are not defaulted or clamped. On failure the original
    record is returned unchanged so the caller's age value is still visible.
    Returns (dna, error_message_or_None)."""
    raw = dict(dna or {})
    age_error = _reject_stated_age(raw)
    if age_error:
        return raw, age_error
    ok, stated, _ = safety.require_stated_age(raw)
    dna = raw
    out = {"id": dna.get("id") or uuid.uuid4().hex[:10],
           "name": str(dna.get("name") or "New character")[:60],
           "notes": str(dna.get("notes") or "")[:4000],
           "extra": str(dna.get("extra") or "")[:500],
           "style": dna.get("style") if catalog.find(catalog.STYLES, dna.get("style")) else "photo",
           "gender": dna.get("gender") if catalog.find(catalog.GENDERS, dna.get("gender")) else "woman",
           "age": stated,
           "stated_age": stated,
           "traits": {}, "seed": int(dna.get("seed") or 0) % (2**53),
           "hero": dna.get("hero") or "", "created": dna.get("created") or time.time(), "updated": time.time()}
    if not re.fullmatch(r"[a-f0-9]{6,32}", out["id"]):
        out["id"] = uuid.uuid4().hex[:10]
    for g in catalog.CHARACTER_GROUPS:
        v = (dna.get("traits") or {}).get(g["id"])
        if g.get("multi"):
            vals = [x for x in (v or []) if _chip(g["id"], x)]
            if vals:
                out["traits"][g["id"]] = vals
        elif v and _chip(g["id"], v):
            c = _chip(g["id"], v)
            if c.get("only") and c["only"] != out["gender"]:
                continue
            out["traits"][g["id"]] = v
    ok, msg = safety.check_all(*(out[k] for k in TEXT_FIELDS))
    return out, (None if ok else msg)


def describe(dna, include_style=True):
    """The words that describe the character (no camera/scene)."""
    gender = catalog.find(catalog.GENDERS, dna["gender"])["p"]
    age = dna["age"]
    bits = [f"a {age}-year-old adult {gender}"]
    if dna["gender"] == "woman" and age < 30:
        bits.append("mature adult woman")
    for g in catalog.CHARACTER_GROUPS:
        v = dna["traits"].get(g["id"])
        for cid in (v if isinstance(v, list) else [v] if v else []):
            c = _chip(g["id"], cid)
            if c:
                bits.append(c["p"])
    if dna.get("extra"):
        bits.append(dna["extra"])
    if include_style:
        bits.insert(0, catalog.find(catalog.STYLES, dna["style"])["p"])
    return ", ".join(bits)


def short_identity(dna):
    """A short identity reminder for edit prompts ('keep ...')."""
    t = dna["traits"]
    parts = []
    for gid in ("hair_color", "hair_style", "eyes", "skin"):
        c = _chip(gid, t.get(gid)) if t.get(gid) else None
        if c:
            parts.append(c["p"])
    return ", ".join(parts)


class Store:
    """Characters saved as outputs/characters/<id>.json (deleted ones go to outputs/_trash)."""

    def __init__(self, root):
        self.dir = os.path.join(root, "characters")
        self.trash = os.path.join(root, "_trash")
        os.makedirs(self.dir, exist_ok=True)

    def _p(self, cid):
        if not re.fullmatch(r"[a-f0-9]{6,32}", cid or ""):
            raise KeyError("bad id")
        return os.path.join(self.dir, cid + ".json")

    def list(self):
        out = []
        for f in sorted(os.listdir(self.dir)):
            if f.endswith(".json"):
                try:
                    out.append(json.load(open(os.path.join(self.dir, f), encoding="utf-8")))
                except Exception:
                    pass
        return sorted(out, key=lambda d: -d.get("updated", 0))

    def get(self, cid):
        with open(self._p(cid), encoding="utf-8") as f:
            return json.load(f)

    def save(self, dna):
        tmp = self._p(dna["id"]) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dna, f, indent=2)
        os.replace(tmp, self._p(dna["id"]))
        return dna

    def delete(self, cid):
        os.makedirs(self.trash, exist_ok=True)
        shutil.move(self._p(cid), os.path.join(self.trash, f"character_{cid}_{int(time.time())}.json"))
