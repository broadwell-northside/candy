"""Send a character pack to the island. Mock zip and mock engine only.

No GPU, no weight download, no RunPod.
"""
import io
import json
import os
import tempfile
import zipfile

from PIL import Image

import pipelines
import pipelines_v3
from library import AreaView, Library

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LORA = "easy_studio/id_abc123def0_identity.safetensors"


class _Checker:
    enabled = True


class _Chars:
    def __init__(self, row):
        self.row = row

    def get(self, cid):
        if not isinstance(self.row, dict) or cid != self.row.get("id"):
            raise KeyError(cid)
        return self.row


class _Ctx:
    def __init__(self, view, chars):
        self.tmp = tempfile.mkdtemp()
        self.lib = view
        self.chars = chars
        self.job = {"id": "pack", "results": [], "params": {}}

    def steps(self, n):
        self.step_count = n

    def next_step(self):
        return None

    def add(self, path, kind, **meta):
        it = self.lib.lib.add(path, kind, **meta)
        self.job["results"].append(it["id"])
        return it


def _person(**extra):
    row = {
        "id": "abc123def0", "name": "Mara", "age": 32, "stated_age": 32,
        "gender": "woman", "style": "photo", "notes": "Warm and unhurried.",
        "extra": "", "traits": {}, "fictional": True, "real_person": False,
    }
    row.update(extra)
    return row


def _png(path, color):
    Image.new("RGB", (8, 8), color).save(path)


def _add(lib, name, kind="still", **meta):
    path = os.path.join(lib.root, name)
    if name.endswith(".mp4"):
        open(path, "wb").write(b"fake-mp4")
    else:
        _png(path, meta.pop("color", (20, 80, 40)))
    base = {
        "character": "abc123def0", "area": "default", "age_check": "ok",
        "appearance_check": {"status": "ok", "held": False},
        "prompt": "olive skin, a linen shirt", "favourite": True,
    }
    base.update(meta)
    return lib.add(path, kind, **base)


def _pack(character, specs, area="default"):
    root = tempfile.mkdtemp()
    lib = Library(root)
    for spec in specs:
        _add(lib, spec["name"], spec.get("kind", "still"), **spec.get("meta", {}))
    view = AreaView(lib, area)
    ctx = _Ctx(view, _Chars(character))
    old_guard, old_enc = pipelines.AGE_GUARD, pipelines_v3.V.has_encoder
    pipelines.AGE_GUARD = _Checker()
    pipelines.set_area(area)
    pipelines_v3.V.has_encoder = lambda _name: False
    try:
        pipelines_v3.job_export_godot(ctx, {"character": character["id"]})
    finally:
        pipelines.AGE_GUARD = old_guard
        pipelines.set_area("default")
        pipelines_v3.V.has_encoder = old_enc
    item = lib.get(ctx.job["results"][-1])
    blob = open(lib.path(item), "rb").read()
    return zipfile.ZipFile(io.BytesIO(blob))


def _record(z):
    name = next(n for n in z.namelist() if n.endswith("/character.json"))
    return json.loads(z.read(name)), name


def _paths(record, bucket, slot):
    found = []
    for row in (record.get(bucket) or {}).values():
        if isinstance(row, dict) and row.get(slot):
            found.append(row[slot])
    return found


def _refused(character):
    root = tempfile.mkdtemp()
    lib = Library(root)
    ctx = _Ctx(AreaView(lib, "default"), _Chars(character))
    old_guard = pipelines.AGE_GUARD
    pipelines.AGE_GUARD = _Checker()
    pipelines.set_area("default")
    try:
        pipelines_v3.job_export_godot(ctx, {"character": character.get("id") or "abc123def0"})
    except pipelines.UserError as exc:
        zips = [it for it in lib.items.values() if str(it.get("kind") or "").startswith("export")]
        return str(exc), zips
    finally:
        pipelines.AGE_GUARD = old_guard
    return "", ["the pack was written"]


def unit(check):
    print("\n[38] Island pack from a mock zip")
    ignore = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("game/assets/imports stays gitignored", "game/assets/imports/" in ignore, ignore)
    check("the test does not create game/assets/imports",
          not os.path.isdir(os.path.join(ROOT, "game", "assets", "imports")))

    covered = _pack(_person(), [
        {"name": "smile.png"},
        {"name": "shore.mp4", "kind": "video:film"},
        {"name": "nude.png", "meta": {"area": "adult", "prompt": "nude on the sand"}},
        {"name": "beach.png", "meta": {"prompt": "nude on the beach"}},
        {"name": "held.png", "meta": {"appearance_check": {"status": "unchecked", "held": True}, "age_check": "unchecked"}},
        {"name": "flagged.png", "meta": {"age_flag": True, "age_check": "flag",
                                          "appearance_check": {"status": "flag", "held": True}}},
    ])
    record, json_name = _record(covered)
    names = covered.namelist()
    check("the pack keeps one project.godot", [n for n in names if n.endswith("project.godot")] == ["project.godot"], names)
    check("character.json, portraits, and videos are in the zip",
          json_name.startswith("assets/characters/mara/") and any("/portraits/" in n for n in names)
          and any("/videos/" in n for n in names), names)
    check("the island fields are on the saved character",
          record.get("stillwater_export") == 1 and record.get("name") == "Mara" and record.get("gender") == "woman"
          and record.get("age") == 32 and record.get("stated_age") == 32 and record.get("fictional") is True
          and record.get("real_person") is False and record.get("variant") == "covered"
          and record.get("notes") == "Warm and unhurried."
          and record.get("personality") == {
              "summary": "Warm and unhurried.", "style": "", "likes": [], "limits": [], "voice_id": ""}
          and record.get("look", {}).get("lora_id") == "", record)
    covered_pics = _paths(record, "portraits", "covered")
    adult_pics = _paths(record, "portraits", "adult")
    check("a covered portrait is in the covered slot",
          any(path.endswith("smile_covered.png") for path in covered_pics) and adult_pics == [],
          (covered_pics, adult_pics))
    check("explicit, held, and flagged files stay out of a covered pack",
          not any("nude" in n or "beach" in n or "held" in n or "flagged" in n for n in names), names)
    check("the readme says the importer is a separate step",
          pipelines_v3.ISLAND_SENTENCE in covered.read("README.txt").decode())

    made_up = _person(look={"lora_id": "easy_studio/mira", "summary": "Olive skin"})
    record, _name = _record(_pack(made_up, [{"name": "smile.png"}]))
    check("a made-up LoRA id is not written", record["look"]["lora_id"] == "" and record["look"]["summary"] == "Olive skin",
          record.get("look"))

    kept = _person(look={
        "lora_id": LORA, "private_use": "yes", "weights_downloaded": False, "stills": ["s1"],
        "summary": "Olive skin",
    }, personality={"summary": "Short sentences.", "style": "Quiet.", "likes": ["morning swims"],
                    "limits": ["She will not be rushed."], "voice_id": "af_bella"})
    record, _name = _record(_pack(kept, [{"name": "smile.png"}]))
    check("a LoRA this app recorded is kept", record["look"]["lora_id"] == LORA, record.get("look"))
    check("personality is the saved object, not a new one",
          record["personality"]["summary"] == "Short sentences." and record["personality"]["likes"] == ["morning swims"]
          and record["personality"]["voice_id"] == "af_bella" and record["notes"] == "Warm and unhurried.",
          record.get("personality"))

    adult = _pack(_person(), [
        {"name": "smile.png", "meta": {"prompt": "a linen shirt"}},
        {"name": "nude.png", "meta": {"area": "adult", "prompt": "nude"}},
        {"name": "said.png", "meta": {"prompt": "nude on the beach"}},
    ], area="adult")
    record, _name = _record(adult)
    names = adult.namelist()
    covered_pics = _paths(record, "portraits", "covered")
    adult_pics = _paths(record, "portraits", "adult")
    check("an adult pack says variant adult", record.get("variant") == "adult" and record.get("age") == 32, record.get("variant"))
    check("explicit files are only in the adult slot",
          any(path.endswith("nude_adult.png") for path in adult_pics)
          and any(path.endswith("said_adult.png") for path in adult_pics)
          and any(path.endswith("smile_covered.png") for path in covered_pics)
          and not any("nude" in path or "said" in path for path in covered_pics)
          and all(path in names for path in adult_pics + covered_pics),
          (covered_pics, adult_pics, names))

    for label, row, needle in (
            ("missing age", _person(age=None), "missing"),
            ("age only", {k: v for k, v in _person().items() if k != "stated_age"}, "missing"),
            ("under 21", _person(age=20, stated_age=20), "under 21"),
            ("mismatched ages", _person(age=16, stated_age=21), "16"),
            ("ages that do not match", _person(age=32, stated_age=40), "Conflicting"),
            ("age as words", _person(age="21", stated_age="21"), "Invalid"),
            ("age as yes/no", _person(age=True, stated_age=True), "Invalid"),
            ("fractional age", _person(age=21.5, stated_age=21.5), "21.5"),
            ("a real person", _person(real_person=True), "real person"),
    ):
        if label == "missing age":
            row = _person()
            row["age"] = None
            row["stated_age"] = None
        text, zips = _refused(row)
        check(f"{label} is not exported", needle.lower() in text.lower() and zips == [], (text, zips))

    check("export_age accepts 21", pipelines_v3.export_age(_person(age=21, stated_age=21)) == 21)


def e2e(a, mock_url):
    import requests
    check = a.check
    print("\n[39] Send to the island through the mock engine")
    before = requests.get(mock_url + "/mock/log").json()
    missing = a.post("/api/jobs", json={"kind": "export_godot", "params": {}})
    check("a pack with no character never reaches the engine",
          missing.status_code == 400 and "character" in missing.text.lower()
          and requests.get(mock_url + "/mock/log").json() == before, missing.text)
    character = a.post("/api/characters", json={
        "name": "Mara", "gender": "woman", "style": "photo", "age": 32, "traits": {},
        "notes": "Warm and unhurried.",
    }).json()
    still = a.job("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "look": "olive skin, a linen shirt"})
    check("the mock engine made a still for the pack", still.get("status") == "done" and still.get("results"), still.get("error"))
    sent = requests.get(mock_url + "/mock/log").json()
    pack = a.job("export_godot", {"character": character["id"]})
    after = requests.get(mock_url + "/mock/log").json()
    check("the pack job does not call the engine", pack.get("status") == "done" and after == sent, pack.get("error"))
    if pack.get("results"):
        z = zipfile.ZipFile(io.BytesIO(a.file(pack["results"][0])))
        names = z.namelist()
        record, _name = _record(z)
        check("the engine pack is what the importer reads",
              record.get("stillwater_export") == 1 and record.get("stated_age") == 32 and record.get("age") == 32
              and record.get("variant") == "covered" and record.get("look", {}).get("lora_id") == ""
              and record.get("fictional") is True and record.get("real_person") is False
              and [n for n in names if n.endswith("project.godot")] == ["project.godot"]
              and any(n.endswith("_covered.png") for n in names)
              and not any("_adult" in n for n in names)
              and pipelines_v3.ISLAND_SENTENCE in z.read("README.txt").decode(),
              (record.get("variant"), record.get("look"), names[:12]))
