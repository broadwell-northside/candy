#!/usr/bin/env python3
"""Checks for the Easy Studio importer. No Godot and no network."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import import_easy_studio as importer


FAILED = 0


def check(name, cond, extra=""):
    global FAILED
    if cond:
        print("PASS", name)
    else:
        FAILED += 1
        print("FAIL", name, extra)


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def png_bytes(marker=b""):
    return PNG_BYTES + marker


def tiny_png(path, marker=b""):
    # A 1x1 PNG is enough. The importer copies bytes; it does not open the picture.
    with open(path, "wb") as handle:
        handle.write(png_bytes(marker))


ISLAND_PROJECT = 'config_version=5\nconfig/name="Stillwater"\nISLAND-PROJECT-SENTINEL\n'
PACK_PROJECT = 'config_version=5\nconfig/name="Mara (Easy Studio)"\nPACK-PROJECT-SENTINEL\n'


def tree_has(root, needle):
    if isinstance(needle, str):
        needle = needle.encode()
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            with open(os.path.join(dirpath, name), "rb") as handle:
                if needle in handle.read():
                    return True
    return False


def project_paths(root):
    found = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name == "project.godot":
                found.append(os.path.join(dirpath, name))
    return found


def tiny_mp4(path):
    subprocess.check_call([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x1F8A8A:s=160x90:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", path,
    ])


def write_export(root, age=None, stated_age=None, name="Mira Costa"):
    folder = os.path.join(root, "assets", "characters", "mira_costa")
    os.makedirs(os.path.join(folder, "portraits"))
    os.makedirs(os.path.join(folder, "videos"))
    data = {"id": "abc123", "name": name, "notes": "Likes the morning swim."}
    if age is not None:
        data["age"] = age
    if stated_age is not None:
        data["stated_age"] = stated_age
    with open(os.path.join(folder, "character.json"), "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    tiny_png(os.path.join(folder, "portraits", "smile.png"))
    tiny_mp4(os.path.join(folder, "videos", "shore.mp4"))
    return folder


def game_root():
    root = tempfile.mkdtemp(prefix="stillwater_game_")
    os.makedirs(os.path.join(root, "data", "characters"))
    with open(os.path.join(root, "data", "scenes.json"), "w", encoding="utf-8") as handle:
        json.dump({"scenes": []}, handle)
    return root


def test_ages():
    ok, message, age = importer.validate_stated_age({"age": 32, "name": "Mira"})
    check("easy studio age 32 is accepted", ok and age == 32, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 21})
    check("stated age 21 is accepted", ok and age == 21, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 21, "age": 21})
    check("matching ages of 21 are accepted", ok and age == 21, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 32, "age": 32})
    check("matching ages of 32 are accepted", ok and age == 32, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 21, "age": 16})
    check("stated_age and age are refused when they disagree", not ok and age is None and "disagree" in message, message)
    ok, message, age = importer.validate_stated_age({"name": "Nope"})
    check("a missing age is refused", not ok and age is None and "missing" in message, message)
    ok, message, age = importer.validate_stated_age({"stated_age": ""})
    check("a blank age is refused", not ok and age is None and "missing" in message, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 16, "name": "Nope"})
    check("an age under 21 is refused", not ok and age is None and "under 21" in message, message)
    for young in (18, 19, 20):
        ok, message, age = importer.validate_stated_age({"stated_age": young})
        check(
            f"age {young} is refused and not clamped",
            not ok and age is None and f"is {young}" in message and "under 21" in message,
            message,
        )
    ok, message, age = importer.validate_stated_age({"stated_age": 18, "age": 18})
    check("matching ages of 18 are refused and not clamped", not ok and age is None and "is 18" in message, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 21.0, "age": 21})
    check("a whole 21.0 matches 21", ok and age == 21, message)
    ok, message, age = importer.validate_stated_age({"stated_age": 21.5})
    check("21.5 is refused and not clamped", not ok and age is None and "21.5" in message and "whole" in message, message)
    ok, message, age = importer.validate_stated_age({"stated_age": "21"})
    check("an age written as words is refused", not ok and age is None, message)
    ok, message, age = importer.validate_stated_age({"stated_age": True})
    check("a yes/no age is refused", not ok and age is None, message)


def test_disagree_writes_nothing():
    export = tempfile.mkdtemp()
    root = game_root()
    folder = os.path.join(export, "assets", "characters", "mira_costa")
    os.makedirs(folder)
    with open(os.path.join(folder, "character.json"), "w", encoding="utf-8") as handle:
        json.dump({"name": "Mira Costa", "stated_age": 21, "age": 16}, handle)
    try:
        importer.import_export(export, "mira", root=root)
        check("disagreeing ages raise", False)
    except importer.GameImportError as exc:
        check("disagreeing ages stop the import", exc.code == 2 and "disagree" in str(exc), str(exc))
    written = os.path.join(root, "data", "characters", "mira.json")
    check("disagreeing ages write no character", not os.path.exists(written))
    shutil.rmtree(export)
    shutil.rmtree(root)


def test_refuse_writes_nothing():
    export = tempfile.mkdtemp()
    root = game_root()
    write_export(export, age=16)
    try:
        importer.import_export(export, "mira", root=root)
        check("underage import raises", False)
    except importer.GameImportError as exc:
        check("underage import stops", exc.code == 2 and "under 21" in str(exc), str(exc))
    check("underage import writes no character", not os.path.exists(os.path.join(root, "data", "characters", "mira.json")))
    shutil.rmtree(export)
    shutil.rmtree(root)


def test_happy_path_and_zip_and_dry_run():
    export = tempfile.mkdtemp()
    root = game_root()
    write_export(export, age=28)
    dry = importer.import_export(export, "mira", root=root, dry_run=True)
    check("dry run writes nothing", dry["dry_run"] and not os.path.exists(os.path.join(root, "data", "characters", "mira.json")))
    summary = importer.import_export(export, "mira", root=root, variant="covered", location="beach", time_of_day="sunset", activity="swim")
    check("import reports the age", summary["stated_age"] == 28 and summary["videos"] == 1 and summary["portraits"] == 1)
    character = json.load(open(os.path.join(root, "data", "characters", "mira.json"), encoding="utf-8"))
    check("character file keeps the stated age and the picture", character["stated_age"] == 28 and character["portraits"]["smile"]["covered"].endswith("smile_covered.png"))
    ogv = os.path.join(root, "assets", "imports", "mira", "clips", "shore_covered.ogv")
    still = os.path.join(root, "assets", "imports", "mira", "clips", "shore_covered.png")
    check("mp4 became an ogv and a still", os.path.isfile(ogv) and os.path.getsize(ogv) > 0 and os.path.isfile(still))
    manifest = json.load(open(os.path.join(root, "data", "scenes.json"), encoding="utf-8"))
    scene = manifest["scenes"][0]
    check("manifest gained a covered scene", scene["id"] == "import_mira_shore_covered" and scene["variants"]["covered"]["video"].endswith(".ogv") and scene["activity"] == "swim")
    importer.import_export(export, "mira", root=root, variant="adult")
    character = json.load(open(os.path.join(root, "data", "characters", "mira.json"), encoding="utf-8"))
    check("a second import adds the adult variant beside covered", "adult" in character["portraits"]["smile"] and "covered" in character["portraits"]["smile"])

    zpath = os.path.join(export, "pack.zip")
    with zipfile.ZipFile(zpath, "w") as archive:
        for dirpath, _dirs, files in os.walk(os.path.join(export, "assets")):
            for name in files:
                full = os.path.join(dirpath, name)
                archive.write(full, os.path.relpath(full, export))
    other = game_root()
    summary = importer.import_export(zpath, "leo", root=other, variant="covered")
    check("a zip import works", summary["stated_age"] == 28 and os.path.isfile(os.path.join(other, "data", "characters", "leo.json")))

    slip = os.path.join(export, "slip.zip")
    with zipfile.ZipFile(slip, "w") as archive:
        archive.writestr("../evil.json", "{}")
    try:
        importer.import_export(slip, "mira", root=other)
        check("zip slip is refused", False)
    except importer.GameImportError as exc:
        check("zip slip is refused", "Unsafe path" in str(exc), str(exc))
    shutil.rmtree(export)
    shutil.rmtree(root)
    shutil.rmtree(other)


def workshop_record(**overrides):
    data = {
        "id": "abc123def0",
        "name": "Mara Ellison",
        "age": 32,
        "stated_age": 32,
        "gender": "woman",
        "notes": "Warm and unhurried.",
        "fictional": True,
        "real_person": False,
        "stillwater_export": 1,
        "variant": "covered",
        "personality": {
            "summary": "Warm and unhurried.",
            "style": "Short sentences.",
            "likes": ["morning swims"],
            "limits": ["She will not be rushed."],
            "voice_id": "",
        },
        "look": {"summary": "Olive skin, a linen shirt.", "lora_id": ""},
        "portraits": {
            "smile": {
                "covered": "assets/characters/mara/portraits/smile_covered.png",
                "adult": "",
            },
        },
        "clips": {},
        "appearance_check": {"status": "ok"},
    }
    data.update(overrides)
    return data


def write_workshop(root, data=None, adult_portrait=True, model=True):
    folder = os.path.join(root, "assets", "characters", "mara")
    os.makedirs(os.path.join(folder, "portraits"))
    os.makedirs(os.path.join(folder, "models"))
    tiny_png(os.path.join(folder, "portraits", "smile_covered.png"), b"SMILE")
    if adult_portrait:
        tiny_png(os.path.join(folder, "portraits", "nude_adult.png"), b"NUDE")
    if model:
        with open(os.path.join(folder, "models", "mara.glb"), "wb") as handle:
            handle.write(b"glTF-fake")
    with open(os.path.join(root, "project.godot"), "w", encoding="utf-8") as handle:
        handle.write(PACK_PROJECT)
    with open(os.path.join(root, "export_presets.cfg"), "w", encoding="utf-8") as handle:
        handle.write("PACK-PRESETS\n")
    with open(os.path.join(root, "README.txt"), "w", encoding="utf-8") as handle:
        handle.write("PACK-README\n")
    if data is None:
        data = workshop_record()
    with open(os.path.join(folder, "character.json"), "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return folder


def zip_pack(export):
    dest_dir = tempfile.mkdtemp()
    zpath = os.path.join(dest_dir, "mara_godot.zip")
    with zipfile.ZipFile(zpath, "w") as archive:
        for dirpath, _dirs, files in os.walk(export):
            for name in files:
                full = os.path.join(dirpath, name)
                archive.write(full, os.path.relpath(full, export))
    return zpath


def island_root():
    root = game_root()
    with open(os.path.join(root, "project.godot"), "w", encoding="utf-8") as handle:
        handle.write(ISLAND_PROJECT)
    with open(os.path.join(root, "export_presets.cfg"), "w", encoding="utf-8") as handle:
        handle.write("ISLAND-PRESETS\n")
    with open(os.path.join(root, "data", "characters", "leo.json"), "w", encoding="utf-8") as handle:
        json.dump({"id": "leo", "name": "Leo Maren", "stated_age": 34, "personality": "Quiet."}, handle)
        handle.write("\n")
    return root


def test_workshop_pack_lands():
    export = tempfile.mkdtemp()
    root = island_root()
    bare = game_root()
    try:
        write_workshop(export)
        zpath = zip_pack(export)
        dry = importer.import_export(zpath, "mara", root=root, variant="covered", dry_run=True)
        check("a workshop dry run writes nothing", dry["dry_run"] and dry["portraits"] == 1 and dry["stated_age"] == 32
              and not os.path.exists(os.path.join(root, "data", "characters", "mara.json")))
        before_project = open(os.path.join(root, "project.godot"), encoding="utf-8").read()
        before_presets = open(os.path.join(root, "export_presets.cfg"), encoding="utf-8").read()
        before_leo = open(os.path.join(root, "data", "characters", "leo.json"), encoding="utf-8").read()
        before_scenes = open(os.path.join(root, "data", "scenes.json"), encoding="utf-8").read()
        summary = importer.import_export(zpath, "mara", root=root, variant="covered")
        check("a workshop zip reports the age", summary["stated_age"] == 32 and summary["portraits"] == 1 and summary["videos"] == 0)
        character = json.load(open(os.path.join(root, "data", "characters", "mara.json"), encoding="utf-8"))
        check("the game id is the one asked for", character["id"] == "mara" and character.get("id") != "abc123def0")
        check("the imported name is the pack name", character["name"] == "Mara Ellison")
        check("both ages are kept", character["stated_age"] == 32 and character["age"] == 32)
        check("an empty lora id stays empty", character["look"]["lora_id"] == "" and character["look"]["summary"] == "Olive skin, a linen shirt.")
        text = open(os.path.join(root, "data", "characters", "mara.json"), encoding="utf-8").read()
        check("a lora id is not invented", "easy_studio/" not in text, text)
        check("personality is the summary text",
              character["personality"].startswith("Warm and unhurried.")
              and "morning swims" in character["personality"]
              and "{" not in character["personality"],
              character["personality"])
        covered = character["portraits"]["smile"]["covered"]
        check("the covered picture is the covered file", covered.endswith("smile_covered.png") and "adult" not in character["portraits"]["smile"])
        picture = os.path.join(root, "assets", "imports", "mara", "portraits", "smile_covered.png")
        check("the covered bytes are the clothed picture", open(picture, "rb").read().endswith(b"SMILE"))
        check("an unlisted explicit file is not copied", not tree_has(root, b"NUDE"))
        check("a model is recorded and a rig is not invented",
              character["body"]["gltf"].endswith("mara.glb") and "rig" not in character["body"])
        check("the island project is the same file",
              open(os.path.join(root, "project.godot"), encoding="utf-8").read() == before_project == ISLAND_PROJECT
              and project_paths(root) == [os.path.join(root, "project.godot")])
        check("presets, another character, and scenes stay put",
              open(os.path.join(root, "export_presets.cfg"), encoding="utf-8").read() == before_presets
              and open(os.path.join(root, "data", "characters", "leo.json"), encoding="utf-8").read() == before_leo
              and open(os.path.join(root, "data", "scenes.json"), encoding="utf-8").read() == before_scenes)
        check("the pack project is not copied onto the island", not tree_has(root, b"PACK-PROJECT-SENTINEL") and not tree_has(root, b"PACK-README"))

        importer.import_export(zpath, "mara", root=bare, variant="covered")
        check("a pack does not create a second project.godot",
              not os.path.exists(os.path.join(bare, "project.godot"))
              and not os.path.exists(os.path.join(bare, "export_presets.cfg")))

        kept = workshop_record(look={"summary": "Olive skin", "lora_id": "easy_studio/id_abc123def0_identity.safetensors"})
        kept_export = tempfile.mkdtemp()
        kept_root = game_root()
        write_workshop(kept_export, kept, adult_portrait=False, model=False)
        importer.import_export(kept_export, "mara", root=kept_root, variant="covered")
        kept_character = json.load(open(os.path.join(kept_root, "data", "characters", "mara.json"), encoding="utf-8"))
        check("a lora id from the pack is copied as written",
              kept_character["look"]["lora_id"] == "easy_studio/id_abc123def0_identity.safetensors")

        existing_root = island_root()
        mira = {
            "id": "mira",
            "name": "Mira Costa",
            "stated_age": 32,
            "personality": "Old personality.",
            "look": {"summary": "old", "lora_id": "easy_studio/mira_costa"},
            "portraits": {
                "smile": {
                    "covered": "res://assets/characters/mira/smile_covered.png",
                    "adult": "res://assets/characters/mira/smile_adult.png",
                },
                "neutral": {"covered": "res://assets/characters/mira/neutral_covered.png", "adult": ""},
            },
            "clips": {"idle": {"covered": "", "adult": ""}},
        }
        with open(os.path.join(existing_root, "data", "characters", "mira.json"), "w", encoding="utf-8") as handle:
            json.dump(mira, handle)
        importer.import_export(zpath, "mira", root=existing_root, variant="covered")
        merged = json.load(open(os.path.join(existing_root, "data", "characters", "mira.json"), encoding="utf-8"))
        check("importing onto mira keeps the id and takes the pack name",
              merged["id"] == "mira" and merged["name"] == "Mara Ellison")
        check("an empty pack lora replaces a made-up one", merged["look"]["lora_id"] == "")
        check("the adult slot already on the island is left alone",
              merged["portraits"]["smile"]["adult"] == "res://assets/characters/mira/smile_adult.png"
              and merged["portraits"]["neutral"]["covered"].endswith("neutral_covered.png"))
        check("the new covered file is the clothed one",
              open(os.path.join(existing_root, "assets", "imports", "mira", "portraits", "smile_covered.png"), "rb").read().endswith(b"SMILE"))
        shutil.rmtree(kept_export)
        shutil.rmtree(kept_root)
        shutil.rmtree(existing_root)
    finally:
        shutil.rmtree(export, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(bare, ignore_errors=True)


def test_explicit_files_follow_the_adult_switch():
    export = tempfile.mkdtemp()
    covered_root = island_root()
    adult_root = island_root()
    listed_root = island_root()
    try:
        adult = workshop_record(
            variant="adult",
            portraits={
                "smile": {
                    "covered": "assets/characters/mara/portraits/smile_covered.png",
                    "adult": "",
                },
                "nude": {
                    "covered": "",
                    "adult": "assets/characters/mara/portraits/nude_adult.png",
                },
            },
        )
        write_workshop(export, adult)
        try:
            importer.import_export(export, "mara", root=covered_root, variant="covered")
            check("an adult pack is refused for a covered import", False)
        except importer.GameImportError as exc:
            check("an adult pack is refused for a covered import",
                  exc.code == 2 and "does not match" in str(exc), str(exc))
        check("a refused adult pack writes nothing",
              not os.path.exists(os.path.join(covered_root, "data", "characters", "mara.json"))
              and not os.path.isdir(os.path.join(covered_root, "assets", "imports"))
              and open(os.path.join(covered_root, "project.godot"), encoding="utf-8").read() == ISLAND_PROJECT)

        summary = importer.import_export(export, "mara", root=adult_root, variant="adult")
        check("an adult import copies both slots", summary["portraits"] == 2 and summary["stated_age"] == 32)
        character = json.load(open(os.path.join(adult_root, "data", "characters", "mara.json"), encoding="utf-8"))
        smile = os.path.join(adult_root, "assets", "imports", "mara", "portraits", "smile_covered.png")
        nude = os.path.join(adult_root, "assets", "imports", "mara", "portraits", "nude_adult.png")
        check("explicit bytes stay in the adult slot",
              open(smile, "rb").read().endswith(b"SMILE")
              and open(nude, "rb").read().endswith(b"NUDE")
              and character["portraits"]["smile"]["covered"].endswith("smile_covered.png")
              and character["portraits"]["nude"]["adult"].endswith("nude_adult.png")
              and not character["portraits"]["nude"].get("covered")
              and "nude" not in character["portraits"]["smile"]["covered"])
        check("the adult import still does not replace the island project",
              open(os.path.join(adult_root, "project.godot"), encoding="utf-8").read() == ISLAND_PROJECT
              and not tree_has(adult_root, b"PACK-PROJECT-SENTINEL"))

        listed = workshop_record(portraits={
            "smile": {"covered": "assets/characters/mara/portraits/smile_covered.png", "adult": ""},
            "nude": {"covered": "", "adult": "assets/characters/mara/portraits/nude_adult.png"},
        })
        listed_export = tempfile.mkdtemp()
        write_workshop(listed_export, listed)
        importer.import_export(listed_export, "mara", root=listed_root, variant="covered")
        check("a covered import uses the covered file and leaves the explicit one",
              os.path.isfile(os.path.join(listed_root, "assets", "imports", "mara", "portraits", "smile_covered.png"))
              and not tree_has(listed_root, b"NUDE"))

        pointed = workshop_record(portraits={
            "smile": {"covered": "assets/characters/mara/portraits/nude_adult.png", "adult": ""},
        })
        pointed_export = tempfile.mkdtemp()
        pointed_root = island_root()
        write_workshop(pointed_export, pointed)
        try:
            importer.import_export(pointed_export, "mara", root=pointed_root, variant="covered")
            check("an explicit file listed as covered is refused", False)
        except importer.GameImportError as exc:
            check("an explicit file listed as covered is refused", "explicit" in str(exc).lower(), str(exc))
        check("that refusal writes no character and keeps the island project",
              not os.path.exists(os.path.join(pointed_root, "data", "characters", "mara.json"))
              and open(os.path.join(pointed_root, "project.godot"), encoding="utf-8").read() == ISLAND_PROJECT)
        shutil.rmtree(listed_export)
        shutil.rmtree(pointed_export)
        shutil.rmtree(pointed_root)
    finally:
        shutil.rmtree(export, ignore_errors=True)
        shutil.rmtree(covered_root, ignore_errors=True)
        shutil.rmtree(adult_root, ignore_errors=True)
        shutil.rmtree(listed_root, ignore_errors=True)


def test_bad_packs_write_nothing():
    cases = [
        ("missing age", workshop_record(age=None, stated_age=None), "missing"),
        ("only stated_age 21", {key: value for key, value in workshop_record(stated_age=21).items() if key != "age"}, "missing"),
        ("only age 21", {key: value for key, value in workshop_record(age=21).items() if key != "stated_age"}, "missing"),
        ("under 21", workshop_record(age=20, stated_age=20), "under 21"),
        ("ages that disagree", workshop_record(age=16, stated_age=21), "disagree"),
        ("a real person", workshop_record(real_person=True), "real person"),
        ("not fictional", workshop_record(fictional=False), "real person"),
        ("appearance is not an age", {
            "name": "Mara",
            "appearance_check": {"status": "ok"},
            "stillwater_export": 1,
            "fictional": True,
            "real_person": False,
            "variant": "covered",
            "look": {"lora_id": ""},
        }, "missing"),
    ]
    # workshop_record(age=None) still leaves the key, with value None. That is a missing age.
    for label, data, needle in cases:
        export = tempfile.mkdtemp()
        root = island_root()
        try:
            if label == "missing age":
                data = workshop_record()
                data.pop("age")
                data.pop("stated_age")
            write_workshop(export, data, adult_portrait=False, model=False)
            try:
                importer.import_export(export, "mara", root=root, variant="covered")
                check(f"{label} is refused", False)
            except importer.GameImportError as exc:
                check(f"{label} is refused", exc.code == 2 and needle in str(exc).lower(), str(exc))
            written = os.path.join(root, "data", "characters", "mara.json")
            check(f"{label} writes no character and does not fill in 21",
                  not os.path.exists(written)
                  and not os.path.isdir(os.path.join(root, "assets", "imports"))
                  and open(os.path.join(root, "project.godot"), encoding="utf-8").read() == ISLAND_PROJECT)
        finally:
            shutil.rmtree(export, ignore_errors=True)
            shutil.rmtree(root, ignore_errors=True)

    export = tempfile.mkdtemp()
    root = island_root()
    try:
        folder = os.path.join(export, "assets", "characters", "mara")
        os.makedirs(folder)
        with open(os.path.join(folder, "character.json"), "w", encoding="utf-8") as handle:
            handle.write("{")
        try:
            importer.import_export(export, "mara", root=root, variant="covered")
            check("invalid json is refused", False)
        except importer.GameImportError as exc:
            check("invalid json is refused", "not valid JSON" in str(exc), str(exc))
        check("invalid json writes nothing", not os.path.exists(os.path.join(root, "data", "characters", "mara.json")))

        pointed = workshop_record(portraits={
            "smile": {"covered": "project.godot", "adult": ""},
        })
        pointed_export = tempfile.mkdtemp()
        write_workshop(pointed_export, pointed, adult_portrait=False, model=False)
        try:
            importer.import_export(pointed_export, "mara", root=root, variant="covered")
            check("a portrait path of project.godot is refused", False)
        except importer.GameImportError as exc:
            check("a portrait path of project.godot is refused", "project.godot" in str(exc), str(exc))
        check("pointing at project.godot does not replace the island",
              open(os.path.join(root, "project.godot"), encoding="utf-8").read() == ISLAND_PROJECT
              and not os.path.exists(os.path.join(root, "data", "characters", "mara.json")))

        slipped = workshop_record(portraits={
            "smile": {"covered": "../../project.godot", "adult": ""},
        })
        slip_export = tempfile.mkdtemp()
        write_workshop(slip_export, slipped, adult_portrait=False, model=False)
        try:
            importer.import_export(slip_export, "mara", root=root, variant="covered")
            check("a path out of the pack is refused", False)
        except importer.GameImportError as exc:
            check("a path out of the pack is refused", "Unsafe path" in str(exc), str(exc))
        check("an escaped path leaves the island project alone",
              open(os.path.join(root, "project.godot"), encoding="utf-8").read() == ISLAND_PROJECT)

        kept = workshop_record(age=21, stated_age=21)
        kept_export = tempfile.mkdtemp()
        kept_root = game_root()
        write_workshop(kept_export, kept, adult_portrait=False, model=False)
        summary = importer.import_export(kept_export, "mara", root=kept_root, variant="covered")
        saved = json.load(open(os.path.join(kept_root, "data", "characters", "mara.json"), encoding="utf-8"))
        check("a real age of 21 is kept", summary["stated_age"] == 21 and saved["stated_age"] == 21 and saved["age"] == 21)
        shutil.rmtree(pointed_export, ignore_errors=True)
        shutil.rmtree(slip_export, ignore_errors=True)
        shutil.rmtree(kept_export, ignore_errors=True)
        shutil.rmtree(kept_root, ignore_errors=True)
    finally:
        shutil.rmtree(export, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def test_legacy_explicit_name_stays_out():
    export = tempfile.mkdtemp()
    root = game_root()
    try:
        write_export(export, age=28)
        nude = os.path.join(export, "assets", "characters", "mira_costa", "portraits", "nude_adult.png")
        tiny_png(nude, b"NUDE")
        importer.import_export(export, "mira", root=root, variant="covered")
        check("a covered import of an untagged pack skips an adult file name",
              os.path.isfile(os.path.join(root, "assets", "imports", "mira", "portraits", "smile_covered.png"))
              and not tree_has(root, b"NUDE"))
        character = json.load(open(os.path.join(root, "data", "characters", "mira.json"), encoding="utf-8"))
        check("the legacy covered slot does not gain that explicit file",
              "nude" not in json.dumps(character["portraits"]))
    finally:
        shutil.rmtree(export, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)


def test_imports_are_gitignored():
    repo = os.path.dirname(os.path.dirname(TOOLS))
    with open(os.path.join(repo, ".gitignore"), encoding="utf-8") as handle:
        ignore = handle.read()
    check("game/assets/imports stays gitignored", "game/assets/imports/" in ignore)
    check("the importer tests do not create game/assets/imports",
          not os.path.isdir(os.path.join(repo, "game", "assets", "imports")))


def test_beach_exports_are_gltf():
    root = os.path.dirname(os.path.dirname(TOOLS))
    level_path = os.path.join(root, "game", "assets", "beach", "level.gltf")
    plate_path = os.path.join(root, "game", "assets", "plates", "plate.gltf")
    level = json.load(open(level_path, encoding="utf-8"))
    plate = json.load(open(plate_path, encoding="utf-8"))
    check("the beach level is glTF 2", level.get("asset", {}).get("version") == "2.0")
    check("the plate character is glTF 2", plate.get("asset", {}).get("version") == "2.0")
    level_names = {node.get("name") for node in level.get("nodes", [])}
    check(
        "the level glTF has terrain, water, a navmesh, and the plate",
        {"Terrain", "Ocean", "Navmesh", "PlayerStart", "Plate"} <= level_names,
    )
    plate_names = {node.get("name") for node in plate.get("nodes", [])}
    check("the character glTF is the plate", "Plate" in plate_names)
    check("the level file is not a Godot scene", "gd_scene" not in json.dumps(level))
    check("the plate file is not a Godot scene", "gd_scene" not in json.dumps(plate))
    check(
        "the glTF buffers are on disk",
        os.path.isfile(os.path.join(root, "game", "assets", "beach", "level.buffer"))
        and os.path.isfile(os.path.join(root, "game", "assets", "plates", "plate.buffer")),
    )


def test_ffmpeg_resolver_picks_an_encoder():
    """EASY_STUDIO_FFMPEG wins when it has the encoder; a binary without it is skipped with a plain message."""
    tmp = tempfile.mkdtemp(prefix="ffmpeg_pick_")
    def fake(name, encoders):
        path = os.path.join(tmp, name)
        with open(path, "w") as f:
            f.write("#!/bin/sh\necho 'Encoders:'\n" + "".join(f"echo ' V..... {e} fake'\n" for e in encoders))
        os.chmod(path, 0o755)
        return path
    with_theora = fake("ffmpeg_full", ["libx264", "libtheora"])
    without = fake("ffmpeg_core", ["libx264"])
    saved_env, saved_cands = os.environ.get("EASY_STUDIO_FFMPEG"), importer.FFMPEG_CANDIDATES
    saved_which = importer.shutil.which
    try:
        importer.FFMPEG_CANDIDATES = ()
        importer.shutil.which = lambda _name: without
        os.environ["EASY_STUDIO_FFMPEG"] = with_theora
        check("the env override with libtheora is used", importer._ffmpeg("libtheora") == with_theora)
        os.environ["EASY_STUDIO_FFMPEG"] = without
        try:
            importer._ffmpeg("libtheora")
            check("an ffmpeg without libtheora is refused", False)
        except importer.GameImportError as exc:
            check("an ffmpeg without libtheora is refused with the brew hint", "ffmpeg-full" in str(exc), str(exc))
        check("without an encoder ask, any ffmpeg will do", importer._ffmpeg() == without)
    finally:
        importer.FFMPEG_CANDIDATES = saved_cands
        importer.shutil.which = saved_which
        if saved_env is None:
            os.environ.pop("EASY_STUDIO_FFMPEG", None)
        else:
            os.environ["EASY_STUDIO_FFMPEG"] = saved_env
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_beach_exports_are_gltf()
    test_ages()
    test_disagree_writes_nothing()
    test_refuse_writes_nothing()
    test_happy_path_and_zip_and_dry_run()
    test_workshop_pack_lands()
    test_explicit_files_follow_the_adult_switch()
    test_bad_packs_write_nothing()
    test_legacy_explicit_name_stays_out()
    test_imports_are_gitignored()
    test_ffmpeg_resolver_picks_an_encoder()
    print("----")
    if FAILED:
        print(FAILED, "failed")
        return 1
    print("all importer tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
