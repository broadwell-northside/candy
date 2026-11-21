#!/usr/bin/env python3
"""Copy an Easy Studio workshop pack into Stillwater.

The pack is a zip or a folder. The island reads:

    assets/characters/<name>/character.json
    assets/characters/<name>/portraits/
    assets/characters/<name>/videos/
    assets/characters/<name>/models/

The zip also holds a preview project.godot and export_presets.cfg. Those files
are never opened and never copied over the island.

The character's age must be a whole number, 21 or older. A missing, blank,
word, yes/no, or fractional age is refused. When both stated_age and age are
present they must match. The script never fills in 21.

Explicit files are copied only when --variant adult is set, and then only into
the adult slot. Otherwise the covered files are used. look.lora_id is copied
when the pack has one. An id is never invented.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


MIN_AGE = 21
AGE_RULE = "Every character must be a fictional adult aged 21 or older."
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi", ".ogv"}
STILL_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MODEL_EXTS = {".glb", ".gltf"}
MOOD_WORDS = ("smile", "thoughtful", "neutral", "happy", "sad", "idle")
PROTECTED_NAMES = {"project.godot", "export_presets.cfg"}
GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GameImportError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def _classify_age(raw):
    """Return (kind, whole). kind is blank, invalid, fraction, or whole."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return "blank", None
    if isinstance(raw, bool):
        return "invalid", None
    if isinstance(raw, int):
        return "whole", raw
    if isinstance(raw, float):
        if not raw.is_integer():
            return "fraction", None
        return "whole", int(raw)
    return "invalid", None


def _age_problem(source, raw, kind):
    if kind == "blank":
        return f"stated_age is missing. {AGE_RULE}"
    if kind == "fraction":
        return f"{source} is {raw}, which is not a whole number. {AGE_RULE}"
    return f"{source} must be a number. {AGE_RULE}"


def validate_stated_age(data):
    """Return (ok, message, age).

    Easy Studio stores the age as "age". The game stores "stated_age".
    One of those fields is enough. When both are present they must be the
    same whole number. Words, yes/no values, blanks, and fractions are refused.
    A lower age is left as written and refused. It is never raised to 21.
    """
    if not isinstance(data, dict):
        return False, "The character file is not a JSON object.", None
    has_stated = "stated_age" in data
    has_age = "age" in data
    if not has_stated and not has_age:
        return False, f"stated_age is missing. {AGE_RULE}", None
    if has_stated and has_age:
        stated_raw = data.get("stated_age")
        age_raw = data.get("age")
        stated_kind, stated_whole = _classify_age(stated_raw)
        age_kind, age_whole = _classify_age(age_raw)
        if stated_kind == "whole" and age_kind == "whole" and stated_whole == age_whole:
            chosen = stated_whole
        elif stated_kind == age_kind and stated_raw == age_raw:
            return False, _age_problem("stated_age", stated_raw, stated_kind), None
        else:
            return False, f"stated_age and age disagree. {AGE_RULE}", None
    else:
        source = "stated_age" if has_stated else "age"
        raw = data.get(source)
        kind, chosen = _classify_age(raw)
        if kind != "whole":
            return False, _age_problem(source, raw, kind), None
    if chosen < MIN_AGE:
        return False, f"stated_age is {chosen}, which is under 21. {AGE_RULE}", None
    return True, "", chosen


def validate_pack(data, variant):
    """Return (ok, message) for a workshop pack.

    Older exports that only carry age still pass. A pack with stillwater_export
    must name both ages, say it is fictional, and say which picture set it is.
    --variant must match that set. A real person is refused either way.
    """
    if not isinstance(data, dict):
        return False, "The character file is not a JSON object."
    if data.get("real_person") is True or data.get("fictional") is False:
        return False, "This pack is for a fictional adult. A real person is not imported."
    if "variant" in data and data.get("variant") != variant:
        return False, f"variant is {data.get('variant')}, which does not match --variant {variant}."
    if "stillwater_export" not in data:
        return True, ""
    marker = data.get("stillwater_export")
    if type(marker) is not int or marker != 1:
        return False, "This island reads stillwater_export 1. This pack is a different one."
    if "stated_age" not in data or "age" not in data:
        return False, f"stated_age is missing. {AGE_RULE}"
    if data.get("fictional") is not True or data.get("real_person") is not False:
        return False, "This pack is for a fictional adult. A real person is not imported."
    if data.get("variant") not in ("covered", "adult"):
        return False, "variant must be covered or adult."
    return True, ""


def _safe_token(value, fallback):
    token = re.sub(r"[^a-z0-9_]+", "_", str(value).lower()).strip("_")
    return (token or fallback)[:40]


def _name_slot(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    match = re.search(r"_(covered|adult)$", stem, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).lower()


def _stem_without_slot(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    stripped = re.sub(r"_(covered|adult)$", "", stem, count=1, flags=re.IGNORECASE)
    return stripped or stem


def guess_mood(stem):
    low = stem.lower()
    for mood in MOOD_WORDS:
        if mood in low:
            return mood
    if low in ("portrait", "image", "hero"):
        return "neutral"
    return _safe_token(stem, "neutral")


def _text(value, limit=400):
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def personality_text(exported):
    """The game still stores personality as one string. A pack object becomes that string."""
    raw = exported.get("personality")
    if isinstance(raw, dict):
        parts = [part for part in (_text(raw.get("summary")), _text(raw.get("style"))) if part]
        likes = [_text(item, 80) for item in (raw.get("likes") or []) if isinstance(item, str) and item.strip()]
        limits = [_text(item, 80) for item in (raw.get("limits") or []) if isinstance(item, str) and item.strip()]
        if likes:
            parts.append("Likes " + ", ".join(likes[:12]) + ".")
        if limits:
            parts.append("Limits: " + ", ".join(limits[:12]) + ".")
        text = " ".join(parts).strip()
        if text:
            return text[:400]
    elif isinstance(raw, str) and raw.strip():
        return raw.strip()[:400]
    notes = _text(exported.get("notes"))
    if notes:
        return notes
    return "Imported from Easy Studio."


def _lora_id(value):
    """The pack's id, or empty. This never builds a path."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def apply_look(record, exported):
    look = record.get("look")
    if not isinstance(look, dict):
        look = {}
    incoming = exported.get("look") if isinstance(exported.get("look"), dict) else None
    if incoming is None:
        summary = _text(look.get("summary")) or _text(exported.get("extra"))
        lora = _lora_id(look.get("lora_id")) if "lora_id" in look else ""
    else:
        if "summary" in incoming:
            summary = _text(incoming.get("summary"))
        else:
            summary = _text(look.get("summary")) or _text(exported.get("extra"))
        if "lora_id" in incoming:
            lora = _lora_id(incoming.get("lora_id"))
        else:
            lora = _lora_id(look.get("lora_id")) if "lora_id" in look else ""
    record["look"] = {"summary": summary, "lora_id": lora}
    return record


def load_json(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_character_file(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise GameImportError("The character file is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise GameImportError("The character file is not a JSON object.", code=2)
    return data


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def _allowed_write(root, path):
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(path)
    if os.path.basename(path_abs).lower() in PROTECTED_NAMES:
        return False
    try:
        rel = os.path.relpath(path_abs, root_abs)
    except ValueError:
        return False
    if rel.startswith("..") or os.path.isabs(rel):
        return False
    parts = rel.split(os.sep)
    if parts[0].lower() in PROTECTED_NAMES:
        return False
    if len(parts) == 3 and parts[0] == "data" and parts[1] == "characters" and parts[2].endswith(".json"):
        return True
    if rel == os.path.join("data", "scenes.json"):
        return True
    if len(parts) >= 3 and parts[0] == "assets" and parts[1] == "imports":
        return True
    return False


def _require_allowed(root, path):
    if not _allowed_write(root, path):
        raise GameImportError("Refusing to write outside the island import folders.")


def safe_unzip(zip_path, dest):
    with zipfile.ZipFile(zip_path) as archive:
        dest_abs = os.path.abspath(dest)
        for info in archive.infolist():
            target = os.path.abspath(os.path.join(dest, info.filename))
            if target != dest_abs and not target.startswith(dest_abs + os.sep):
                raise GameImportError("Unsafe path in the export: " + info.filename)
        archive.extractall(dest)


def find_character_dirs(root):
    if os.path.isfile(os.path.join(root, "character.json")):
        return [root]
    base = os.path.join(root, "assets", "characters")
    found = []
    if not os.path.isdir(base):
        return found
    for slug in sorted(os.listdir(base)):
        folder = os.path.join(base, slug)
        if os.path.isfile(os.path.join(folder, "character.json")):
            found.append(folder)
    return found


FFMPEG_CANDIDATES = ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/opt/ffmpeg-full/bin/ffmpeg")


def _has_encoder(binary, encoder):
    try:
        out = subprocess.run([binary, "-hide_banner", "-encoders"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(line.split()[1:2] == [encoder] for line in out.splitlines() if line.strip())


def _ffmpeg(encoder=None):
    """The ffmpeg to use: EASY_STUDIO_FFMPEG, then Homebrew's ffmpeg-full, then PATH.

    With an encoder (libtheora for .ogv), the first one that has it. Homebrew's core ffmpeg has had no
    libtheora since its formula split, so on a Mac `brew install ffmpeg-full` provides it."""
    seen = []
    for binary in (os.environ.get("EASY_STUDIO_FFMPEG"), *FFMPEG_CANDIDATES, shutil.which("ffmpeg")):
        if not binary or binary in seen or not os.path.isfile(binary) or not os.access(binary, os.X_OK):
            continue
        seen.append(binary)
        if encoder is None or _has_encoder(binary, encoder):
            return binary
    if seen and encoder:
        raise GameImportError(f"No ffmpeg here has the {encoder} encoder, so the video cannot be converted to .ogv. "
                              "On a Mac: brew install ffmpeg-full (or set EASY_STUDIO_FFMPEG).")
    raise GameImportError("ffmpeg is not installed, so the video cannot be converted to .ogv.")


def convert_to_ogv(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if src.lower().endswith(".ogv"):
        shutil.copyfile(src, dest)
        return
    binary = _ffmpeg("libtheora")
    with_audio = [binary, "-y", "-v", "error", "-i", src, "-c:v", "libtheora", "-q:v", "7", "-c:a", "libvorbis", "-q:a", "5", dest]
    if subprocess.call(with_audio) != 0:
        silent = [binary, "-y", "-v", "error", "-i", src, "-c:v", "libtheora", "-q:v", "7", "-an", dest]
        subprocess.check_call(silent)


def extract_still(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if src.lower().endswith(".ogv") or src.lower().endswith(tuple(VIDEO_EXTS)):
        subprocess.check_call([_ffmpeg(), "-y", "-v", "error", "-i", src, "-frames:v", "1", dest])
        return
    shutil.copyfile(src, dest)


def _resolve_pack_file(export_root, rel, required=True):
    if not isinstance(rel, str):
        raise GameImportError("The character file has a path that is not text.")
    cleaned = rel.replace("\\", "/").strip()
    if cleaned.startswith("res://"):
        cleaned = cleaned[len("res://"):]
    cleaned = cleaned.lstrip("/")
    if cleaned == "" or os.path.isabs(rel) or re.match(r"^[A-Za-z]:", cleaned):
        raise GameImportError("Unsafe path in the character file: " + rel)
    parts = [part for part in cleaned.split("/") if part != ""]
    if any(part == ".." for part in parts):
        raise GameImportError("Unsafe path in the character file: " + rel)
    root_abs = os.path.abspath(export_root)
    full = os.path.abspath(os.path.join(root_abs, *parts))
    if full != root_abs and not full.startswith(root_abs + os.sep):
        raise GameImportError("Unsafe path in the character file: " + rel)
    if os.path.basename(full).lower() in PROTECTED_NAMES:
        raise GameImportError("The pack's project.godot is not copied onto the island.")
    if not os.path.isfile(full):
        if not required:
            return None
        raise GameImportError("The character file names a missing picture or clip: " + rel)
    return full


def _keep_slot(slot, cli_variant):
    """Explicit files stay out unless the adult switch is on."""
    if slot not in ("covered", "adult"):
        return False
    if cli_variant == "covered":
        return slot == "covered"
    return True


def _check_name_slot(src, slot):
    named = _name_slot(src)
    if named is None or named == slot:
        return
    if named == "adult":
        raise GameImportError(
            "An explicit file is listed with the covered pictures. "
            "Explicit files are only used when --variant adult is set."
        )
    raise GameImportError("A covered file is listed with the adult pictures. It stays in the covered slot.")


def _mapped_media(export_root, mapping, cli_variant, kind):
    planned = []
    if not isinstance(mapping, dict):
        return planned
    allowed = STILL_EXTS if kind == "portrait" else VIDEO_EXTS
    for mood, row in mapping.items():
        if not isinstance(row, dict):
            continue
        safe_mood = _safe_token(mood, "neutral" if kind == "portrait" else "clip")
        for slot in ("covered", "adult"):
            rel = row.get(slot)
            if not isinstance(rel, str) or rel.strip() == "":
                continue
            src = _resolve_pack_file(export_root, rel, required=_keep_slot(slot, cli_variant))
            if src is None or not _keep_slot(slot, cli_variant):
                continue
            _check_name_slot(src, slot)
            if os.path.splitext(src)[1].lower() not in allowed:
                label = "picture" if kind == "portrait" else "clip"
                raise GameImportError(f"The character file names a file that is not a {label}: {rel}")
            planned.append((src, safe_mood, slot))
    return planned


def _scanned_media(files, cli_variant, kind):
    planned = []
    for src in files:
        if os.path.basename(src).lower() in PROTECTED_NAMES:
            continue
        named = _name_slot(src)
        slot = named or cli_variant
        if not _keep_slot(slot, cli_variant):
            continue
        _check_name_slot(src, slot)
        stem = _stem_without_slot(src)
        if kind == "portrait":
            mood = guess_mood(stem)
        else:
            mood = _safe_token(stem, "clip")
        planned.append((src, mood, slot))
    return planned


def _model_files(export_root, folder, exported, cli_variant):
    found = []
    body = exported.get("body") if isinstance(exported.get("body"), dict) else {}
    listed = body.get("gltf") if isinstance(body, dict) else ""
    if isinstance(listed, str) and listed.strip():
        found.append(_resolve_pack_file(export_root, listed))
    for src in _collect(os.path.join(folder, "models"), MODEL_EXTS):
        if os.path.basename(src).lower() in PROTECTED_NAMES:
            raise GameImportError("The pack's project.godot is not copied onto the island.")
        if src not in found:
            found.append(src)
    kept = []
    for src in found:
        named = _name_slot(src)
        if named == "adult" and cli_variant != "adult":
            continue
        if os.path.splitext(src)[1].lower() not in MODEL_EXTS:
            continue
        kept.append(src)
    return kept


def _blank_character(character_id, exported, age):
    packed_name = _text(exported.get("name"), 60) or character_id
    return {
        "id": character_id,
        "name": packed_name,
        "stated_age": age,
        "age": age,
        "personality": personality_text(exported),
        "look": {"summary": "", "lora_id": ""},
        "portraits": {},
        "clips": {},
    }


def _merge_media(bucket, key, variant, path):
    current = bucket.get(key)
    if not isinstance(current, dict):
        current = {}
    current[variant] = path
    bucket[key] = current


def import_export(export, character, root=GAME_ROOT, variant="covered", source="", location="beach",
                  time_of_day="any", activity="talk", dry_run=False):
    if variant not in ("covered", "adult"):
        raise GameImportError("Variant must be covered or adult.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", character or ""):
        raise GameImportError("Use a simple id such as mira (lowercase letters, numbers, underscore).")
    if not os.path.exists(export):
        raise GameImportError("Could not find the export: " + export)

    cleanup = None
    export_root = export
    if os.path.isfile(export):
        cleanup = tempfile.mkdtemp(prefix="stillwater_import_")
        safe_unzip(export, cleanup)
        export_root = cleanup
    try:
        return _import_folder(
            export_root, character, root, variant, source, location, time_of_day, activity, dry_run,
        )
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)


def _import_folder(export_root, character, root, variant, source, location, time_of_day, activity, dry_run):
    folders = find_character_dirs(export_root)
    if source:
        folders = [folder for folder in folders if os.path.basename(folder) == source or folder == source]
    if not folders:
        raise GameImportError("No character.json was found in that export.")
    if len(folders) > 1:
        names = ", ".join(os.path.basename(folder) for folder in folders)
        raise GameImportError("That export has more than one character (" + names + "). Pass --source with the folder name.")
    folder = folders[0]
    exported = read_character_file(os.path.join(folder, "character.json"))
    ok, message, age = validate_stated_age(exported)
    if not ok:
        who = exported.get("name", character) if isinstance(exported, dict) else character
        raise GameImportError(f"{who}: {message}", code=2)
    ok, message = validate_pack(exported, variant)
    if not ok:
        who = exported.get("name", character) if isinstance(exported, dict) else character
        raise GameImportError(f"{who}: {message}", code=2)

    portrait_plan, video_plan, model_plan = _plan_media(export_root, folder, exported, variant)
    dest_dir = os.path.join(root, "assets", "imports", character)
    character_path = os.path.join(root, "data", "characters", character + ".json")
    manifest_path = os.path.join(root, "data", "scenes.json")
    _require_allowed(root, character_path)
    if video_plan:
        _require_allowed(root, manifest_path)

    portrait_out = []
    for src, mood, slot in portrait_plan:
        ext = os.path.splitext(src)[1].lower()
        dest = os.path.join(dest_dir, "portraits", f"{mood}_{slot}{ext}")
        _require_allowed(root, dest)
        portrait_out.append((src, dest, mood, slot, _res_path(root, dest)))
    video_out = []
    for src, mood, slot in video_plan:
        ogv = os.path.join(dest_dir, "clips", f"{mood}_{slot}.ogv")
        still = os.path.join(dest_dir, "clips", f"{mood}_{slot}.png")
        _require_allowed(root, ogv)
        _require_allowed(root, still)
        video_out.append((src, ogv, still, mood, slot, _res_path(root, ogv), _res_path(root, still)))
    model_out = []
    for src in model_plan:
        dest = os.path.join(dest_dir, "models", os.path.basename(src))
        _require_allowed(root, dest)
        model_out.append((src, dest, _res_path(root, dest)))

    if dry_run:
        return {
            "character": character,
            "stated_age": age,
            "dry_run": True,
            "portraits": len(portrait_out),
            "videos": len(video_out),
        }

    record = _character_record(character_path, exported, character, age)
    for _src, _dest, mood, slot, rel in portrait_out:
        _merge_media(record["portraits"], mood, slot, rel)
    for _src, _ogv, _still, mood, slot, video_rel, _still_rel in video_out:
        _merge_media(record["clips"], mood, slot, video_rel)
    if model_out:
        body = record.get("body") if isinstance(record.get("body"), dict) else {}
        body["gltf"] = model_out[0][2]
        packed_body = exported.get("body") if isinstance(exported.get("body"), dict) else {}
        rig = packed_body.get("rig")
        if isinstance(rig, str) and rig.strip():
            body["rig"] = rig.strip()[:40]
        record["body"] = body

    manifest = None
    if video_out:
        manifest = _scenes_for_videos(
            load_json(manifest_path, {"scenes": []}), video_out, character, record, variant, location, time_of_day, activity,
        )

    for src, dest, _mood, _slot, _rel in portrait_out:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
    for src, ogv, still, _mood, _slot, _video_rel, _still_rel in video_out:
        convert_to_ogv(src, ogv)
        extract_still(src, still)
    for src, dest, _rel in model_out:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)

    save_json(character_path, record)
    if manifest is not None:
        save_json(manifest_path, manifest)
    return {
        "character": character,
        "stated_age": age,
        "dry_run": False,
        "portraits": len(portrait_out),
        "videos": len(video_out),
        "character_path": character_path,
        "manifest_path": manifest_path,
    }


def _plan_media(export_root, folder, exported, variant):
    if isinstance(exported.get("portraits"), dict):
        portraits = _mapped_media(export_root, exported.get("portraits"), variant, "portrait")
    else:
        found = _collect(os.path.join(folder, "portraits"), STILL_EXTS)
        sprites = _collect(os.path.join(folder, "sprites"), STILL_EXTS)
        if not found and sprites:
            found = sprites[:1]
        portraits = _scanned_media(found, variant, "portrait")
    if isinstance(exported.get("clips"), dict):
        videos = _mapped_media(export_root, exported.get("clips"), variant, "video")
    else:
        videos = _scanned_media(_collect(os.path.join(folder, "videos"), VIDEO_EXTS), variant, "video")
    models = _model_files(export_root, folder, exported, variant)
    return portraits, videos, models


def _character_record(character_path, exported, character, age):
    record = load_json(character_path, None)
    if not isinstance(record, dict):
        record = _blank_character(character, exported, age)
    record["id"] = character
    record["stated_age"] = age
    record["age"] = age
    packed_name = exported.get("name")
    if isinstance(packed_name, str) and packed_name.strip():
        record["name"] = packed_name.strip()[:60]
    elif not str(record.get("name") or "").strip():
        record["name"] = character
    record["personality"] = personality_text(exported)
    if "fictional" in exported:
        record["fictional"] = exported.get("fictional") is True
    if "real_person" in exported:
        record["real_person"] = exported.get("real_person") is True
    apply_look(record, exported)
    if not isinstance(record.get("portraits"), dict):
        record["portraits"] = {}
    if not isinstance(record.get("clips"), dict):
        record["clips"] = {}
    return record


def _scenes_for_videos(manifest, video_out, character, record, variant, location, time_of_day, activity):
    if not isinstance(manifest, dict) or not isinstance(manifest.get("scenes"), list):
        manifest = {"scenes": []}
    grouped = {}
    for _src, _ogv, _still, mood, slot, video_rel, still_rel in video_out:
        grouped.setdefault(mood, {})[slot] = (still_rel, video_rel)
    who = record.get("name", character)
    for mood, slots in grouped.items():
        scene_id = f"import_{character}_{mood}_{variant}"
        scene = {
            "id": scene_id,
            "location": location,
            "character": character,
            "time": time_of_day,
            "activity": activity,
            "min_affection": 0,
            "caption": f"A moment with {who}.",
            "variants": {},
        }
        replaced = False
        for existing in manifest["scenes"]:
            if isinstance(existing, dict) and existing.get("id") == scene_id:
                scene = existing
                replaced = True
                break
        variants = scene.get("variants") if isinstance(scene.get("variants"), dict) else {}
        for slot, (still_rel, video_rel) in slots.items():
            variants[slot] = {"still": still_rel, "video": video_rel}
        scene["variants"] = variants
        if not replaced:
            manifest["scenes"].append(scene)
    return manifest


def _collect(folder, extensions):
    found = []
    if not os.path.isdir(folder):
        return found
    for dirpath, _dirs, files in os.walk(folder):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in extensions:
                found.append(os.path.join(dirpath, name))
    return found


def _res_path(root, path):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return "res://" + rel


def main(argv=None):
    parser = argparse.ArgumentParser(description="Copy an Easy Studio Godot export into Stillwater.")
    parser.add_argument("export", help="Zip or folder from Easy Studio's Export to Godot 4")
    parser.add_argument("--character", required=True, help="Id used by the game, such as mira")
    parser.add_argument("--source", default="", help="Folder name inside the export, if it contains more than one character")
    parser.add_argument(
        "--variant", choices=("covered", "adult"), default="covered",
        help="covered copies everyday files. adult is the switch that also copies explicit files into the adult slot",
    )
    parser.add_argument("--location", default="beach")
    parser.add_argument("--time", default="any", dest="time_of_day")
    parser.add_argument("--activity", default="talk")
    parser.add_argument("--root", default=GAME_ROOT, help="The game folder, the one that contains project.godot")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = import_export(
            args.export, args.character, root=args.root, variant=args.variant, source=args.source,
            location=args.location, time_of_day=args.time_of_day, activity=args.activity, dry_run=args.dry_run,
        )
    except GameImportError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    if summary.get("dry_run"):
        print(f"Ready to copy {summary['portraits']} picture(s) and {summary['videos']} video(s) for {summary['character']} (age {summary['stated_age']}). Nothing was written.")
    else:
        print(f"Imported {summary['character']} (age {summary['stated_age']}): {summary['portraits']} picture(s), {summary['videos']} video(s).")
        print("Open the game in Godot and let it import the new files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
