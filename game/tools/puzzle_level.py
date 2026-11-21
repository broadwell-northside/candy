#!/usr/bin/env python3
# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The door-unlock co-op puzzle level: the ONE schema implementation (PRD §6.5).

Python validates the level and writes it with its sha256. Godot loads it, checks the hash, and does not
validate it a second time (game/scripts/door_puzzle.gd). The rules of play are code in that script; this
file holds content and tuning only.

    python3 game/tools/puzzle_level.py check            # validate the committed level and its hash
    python3 game/tools/puzzle_level.py write-default    # rewrite data/puzzles/beach_door.json + .sha256
    python3 game/tools/puzzle_level.py promote [--draft PATH]
        # keep an "Edit this place" draft: only its positions are taken, applied to the committed level,
        # validated here, and written with a new hash. Everything else in the draft is ignored.

Rails checked here (PRD §7–§8): every node carries sfw_safe and requires_full_21_mode and an actors list;
every actor has consent "mutual"; every fictional actor's age comes from that actor's own character record
and must be a whole number of 21 or more (missing, words, fractions and under 21 are refused, never filled
in); there are no states for coercion or incapacitation; the dare deck ships empty.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys

GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVEL_PATH = os.path.join(GAME_ROOT, "data", "puzzles", "beach_door.json")
CHARACTERS = os.path.join(GAME_ROOT, "data", "characters")
DARE_DECK_SCHEMA = os.path.join(os.path.dirname(GAME_ROOT), "schemas", "dare_deck.json")
SCHEMA = "stillwater-level/1"
NOTICE = "PRIVATE BUILD — NOT FOR DISTRIBUTION"
MIN_AGE = 21
PAD_SPACING = 2.0
DOOR_CLEARANCE = 1.5
NODE_KINDS = ("pressure_pad", "prop", "door", "plate", "action")
ACTIONS = ("stand_on_far_pad", "take_key")
# No states for coercion or incapacitation exist in this schema. Any of these words in an id, kind,
# label or state refuses the file.
_DENIED_STATE = re.compile(r"coerc|forc(?:e|ed|ing)\b|incapacit|unconscious|asleep|sleeping|drunk|drugged|"
                           r"intoxicat|passed[\s_-]*out|restrain|non[\s_-]*consent|unwilling", re.I)


class LevelError(ValueError):
    pass


def _terrain():
    spec = importlib.util.spec_from_file_location("stillwater_beach_export", os.path.join(GAME_ROOT, "tools", "export_beach_gltf.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.terrain_height


def _pos(x, z):
    """A point on the sand: y comes from the same terrain the beach glTF is built from."""
    return {"x": float(x), "y": round(float(_terrain()(x, z)), 3), "z": float(z)}


def default_level():
    flags = {"sfw_safe": True, "requires_full_21_mode": False}
    both = ["player", "mira"]
    return {
        "schema": SCHEMA,
        "notice": NOTICE,
        "id": "beach_door",
        "title": "The sea-cave door",
        "place": "beach",
        "bounds": {"min_x": -14.0, "max_x": 14.0, "min_z": 7.5, "max_z": 21.0},
        "actors": [
            {"id": "player", "role": "player", "consent": "mutual"},
            {"id": "mira", "role": "companion", "character": "mira", "consent": "mutual"},
        ],
        "rules": {"pads_needed": 2, "key": "key", "door": "door", "companion": "companion",
                  "far_pad": "pad_far", "near_pad": "pad_near", "pad_radius": 0.9, "reach": 1.8},
        "nodes": [
            {"id": "pad_near", "kind": "pressure_pad", "label": "Near pad", "position": _pos(-3.5, 11.0),
             "actors": both, **flags},
            {"id": "pad_far", "kind": "pressure_pad", "label": "Far pad", "position": _pos(3.5, 9.5),
             "actors": both, **flags},
            {"id": "key", "kind": "prop", "label": "Brass key", "position": _pos(-1.8, 10.2),
             "actors": both, **flags},
            {"id": "door", "kind": "door", "label": "Sea-cave door", "position": _pos(5.8, 8.4),
             "socket": "keyhole", "actors": both, **flags},
            {"id": "companion", "kind": "plate", "label": "Mira", "actor": "mira", "position": _pos(2.0, 12.0),
             "plate": {"width": 0.72, "height": 1.8, "spec": "res://data/plate.json"},
             "hitboxes": [
                 {"id": "hand", "rect": {"u0": 0.55, "v0": 0.40, "u1": 0.90, "v1": 0.62}, "action": "take_key"},
                 {"id": "body", "rect": {"u0": 0.15, "v0": 0.10, "u1": 0.85, "v1": 0.98}, "action": "stand_on_far_pad"},
             ],
             "sockets": [{"id": "hand_r", "kind": "hand", "u": 0.70, "v": 0.50, "depth": 0.06}],
             "actors": ["mira"], **flags},
            {"id": "stand_on_far_pad", "kind": "action", "label": "Stand on the far pad", "actors": both, **flags},
            {"id": "take_key", "kind": "action", "label": "Take the key", "actors": both, **flags},
        ],
        "hints": {
            "key": "Pick up the brass key",
            "give": "Give Mira the key",
            "near": "Stand on the near pad",
            "far": "Ask Mira to hold the far pad",
            "open": "The door is open",
        },
    }


# --------------------------------------------------------------------------- validation
def _whole_age(raw):
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    return None


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise LevelError(f"{where} must be a number.")
    return float(value)


def _actor_age(character_id, characters_dir):
    path = os.path.join(characters_dir, f"{character_id}.json")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", str(character_id or "")) or not os.path.isfile(path):
        raise LevelError(f"Actor {character_id!r} has no character record, so it has no stated age.")
    try:
        record = json.load(open(path, encoding="utf-8"))
    except ValueError:
        raise LevelError(f"Actor {character_id!r}: the character record is not readable.")
    age = _whole_age(record.get("stated_age"))
    if age is None:
        raise LevelError(f"Actor {character_id!r}: stated_age must be a whole number. It is never filled in.")
    if age < MIN_AGE:
        raise LevelError(f"Actor {character_id!r} is {age}. Every fictional actor is 21 or older.")
    return age


def _scan_states(value, where="level"):
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and _DENIED_STATE.search(k):
                raise LevelError(f"{where}: there are no states for coercion or incapacitation.")
            _scan_states(v, where)
    elif isinstance(value, list):
        for v in value:
            _scan_states(v, where)
    elif isinstance(value, str) and _DENIED_STATE.search(value):
        raise LevelError(f"{where}: there are no states for coercion or incapacitation.")


def validate(level, characters_dir=CHARACTERS):
    """Return the level unchanged, or raise LevelError with a plain message."""
    if not isinstance(level, dict) or level.get("schema") != SCHEMA:
        raise LevelError("This is not a Stillwater level file.")
    if level.get("notice") != NOTICE:
        raise LevelError("The private-build notice is missing.")
    if level.get("place") != "beach":
        raise LevelError("This puzzle lives on the beach.")
    _scan_states({k: v for k, v in level.items() if k not in ("notice", "hints")}, "level")
    b = level.get("bounds") or {}
    min_x, max_x = _number(b.get("min_x"), "bounds.min_x"), _number(b.get("max_x"), "bounds.max_x")
    min_z, max_z = _number(b.get("min_z"), "bounds.min_z"), _number(b.get("max_z"), "bounds.max_z")
    if min_x >= max_x or min_z >= max_z:
        raise LevelError("The bounds are empty.")
    actors = level.get("actors")
    if not isinstance(actors, list) or not actors:
        raise LevelError("A level needs its actors.")
    ids = set()
    players = 0
    for actor in actors:
        if not isinstance(actor, dict) or not actor.get("id"):
            raise LevelError("Every actor needs an id.")
        if actor.get("consent") != "mutual":
            raise LevelError(f"Actor {actor.get('id')!r}: consent must be \"mutual\". This level does not load.")
        if actor.get("role") == "player":
            players += 1
            if any(k in actor for k in ("age", "stated_age", "character")):
                raise LevelError("The player is not a fictional actor. No player age is stored, and no images of Me are used here.")
        elif actor.get("role") == "companion":
            _actor_age(actor.get("character"), characters_dir)
        else:
            raise LevelError(f"Actor {actor.get('id')!r} has an unknown role.")
        ids.add(actor["id"])
    if players != 1:
        raise LevelError("A level has exactly one player.")
    rules = level.get("rules") or {}
    needed = _whole_age(rules.get("pads_needed"))
    if needed != 2:
        raise LevelError("This puzzle needs exactly two pads held at once.")
    for key in ("pad_radius", "reach"):
        if _number(rules.get(key), "rules." + key) <= 0:
            raise LevelError(f"rules.{key} must be more than 0.")
    nodes = level.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise LevelError("A level needs nodes.")
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            raise LevelError("Every node needs an id.")
        nid = node["id"]
        if nid in by_id:
            raise LevelError(f"Node {nid!r} appears twice.")
        for flag in ("sfw_safe", "requires_full_21_mode"):
            if not isinstance(node.get(flag), bool):
                raise LevelError(f"Node {nid!r} is missing {flag}. Every node and card carries both flags.")
        listed = node.get("actors")
        if not isinstance(listed, list) or not listed or any(a not in ids for a in listed):
            raise LevelError(f"Node {nid!r} must list its actors, and each must be an actor of this level.")
        if node.get("kind") not in NODE_KINDS:
            raise LevelError(f"Node {nid!r} has an unknown kind.")
        if node["kind"] != "action":
            p = node.get("position") or {}
            x, z = _number(p.get("x"), f"{nid}.x"), _number(p.get("z"), f"{nid}.z")
            _number(p.get("y"), f"{nid}.y")
            if not (min_x <= x <= max_x and min_z <= z <= max_z):
                raise LevelError(f"{node.get('label') or nid} is off the sand. Move it inside the beach.")
        by_id[nid] = node
    for want, kind in ((rules.get("near_pad"), "pressure_pad"), (rules.get("far_pad"), "pressure_pad"),
                       (rules.get("key"), "prop"), (rules.get("door"), "door"), (rules.get("companion"), "plate")):
        if (by_id.get(want) or {}).get("kind") != kind:
            raise LevelError(f"The rules point at {want!r}, which is not a {kind.replace('_', ' ')}.")
    for action in ACTIONS:
        if (by_id.get(action) or {}).get("kind") != "action":
            raise LevelError(f"The {action.replace('_', ' ')} action is missing.")

    def dist(a, b):
        pa, pb = by_id[a]["position"], by_id[b]["position"]
        return math.hypot(pa["x"] - pb["x"], pa["z"] - pb["z"])

    near, far, door, key = rules["near_pad"], rules["far_pad"], rules["door"], rules["key"]
    if dist(near, far) < PAD_SPACING:
        raise LevelError(f"The two pads must be at least {PAD_SPACING:g} m apart, or one person could hold both.")
    for pad in (near, far):
        if dist(door, pad) < DOOR_CLEARANCE:
            raise LevelError("The door cannot sit on a pad.")
        if dist(key, pad) < 0.5:
            raise LevelError("The key cannot sit on a pad.")
    plate = by_id[rules["companion"]]
    if plate.get("actor") not in ids or plate.get("actor") == "player":
        raise LevelError("The plate must show the companion, a fictional actor.")
    spec = plate.get("plate") or {}
    if _number(spec.get("width"), "plate.width") <= 0 or _number(spec.get("height"), "plate.height") <= 0:
        raise LevelError("The plate needs a size.")
    for hb in plate.get("hitboxes") or []:
        r = hb.get("rect") or {}
        u0, v0, u1, v1 = (_number(r.get(k), f"hitbox {hb.get('id')}.{k}") for k in ("u0", "v0", "u1", "v1"))
        if not (0.0 <= u0 < u1 <= 1.0 and 0.0 <= v0 < v1 <= 1.0):
            raise LevelError(f"Hitbox {hb.get('id')!r} must sit inside the plate (0 to 1).")
        if hb.get("action") not in ACTIONS:
            raise LevelError(f"Hitbox {hb.get('id')!r} points at an unknown action.")
    if not plate.get("hitboxes"):
        raise LevelError("The plate needs hitboxes.")
    for sock in plate.get("sockets") or []:
        u, v = _number(sock.get("u"), "socket.u"), _number(sock.get("v"), "socket.v")
        depth = _number(sock.get("depth"), "socket.depth")
        if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0) or abs(depth) > 1.0:
            raise LevelError("A Stage 1 socket is {u, v, depth}: u and v from 0 to 1, depth within 1 m.")
        if sock.get("kind") == "intimate_contact":
            raise LevelError("This puzzle has no contact sockets.")
    return level


def validate_dare_deck(deck):
    """The dare and forfeit deck ships empty until its own authoring session (M3)."""
    if not isinstance(deck, dict) or deck.get("schema") != "stillwater-dare-deck/1":
        raise LevelError("This is not a dare deck.")
    if deck.get("cards") != []:
        raise LevelError("The dare deck ships empty this milestone. Cards are authored in M3.")
    return deck


# --------------------------------------------------------------------------- writing
def canonical_bytes(level):
    return (json.dumps(level, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(blob):
    return hashlib.sha256(blob).hexdigest()


def write(level, path=LEVEL_PATH, characters_dir=CHARACTERS):
    validate(level, characters_dir)
    blob = canonical_bytes(level)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for target, data in ((path, blob), (path + ".sha256", (sha256_hex(blob) + "\n").encode("ascii"))):
        tmp = target + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    return sha256_hex(blob)


def read_checked(path=LEVEL_PATH, characters_dir=CHARACTERS):
    blob = open(path, "rb").read()
    want = open(path + ".sha256", encoding="ascii").read().strip()
    if sha256_hex(blob) != want:
        raise LevelError("The level file does not match its sha256.")
    level = json.loads(blob.decode("utf-8"))
    validate(level, characters_dir)
    if canonical_bytes(level) != blob:
        raise LevelError("The level file was not written by puzzle_level.py.")
    return level


def apply_positions(level, draft):
    """Take only x/z positions from a draft (Edit this place) and keep everything else from the level."""
    out = json.loads(json.dumps(level))
    moved = {}
    for node in (draft or {}).get("nodes") or []:
        if isinstance(node, dict) and isinstance(node.get("position"), dict):
            moved[node.get("id")] = node["position"]
    terrain = _terrain()
    for node in out["nodes"]:
        p = moved.get(node["id"])
        if p is None or node["kind"] == "action":
            continue
        x, z = _number(p.get("x"), f"{node['id']}.x"), _number(p.get("z"), f"{node['id']}.z")
        node["position"] = {"x": round(x, 3), "y": round(float(terrain(x, z)), 3), "z": round(z, 3)}
    return out


def default_draft_path():
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support", "Godot", "app_userdata", "Stillwater")
    elif os.name == "nt":
        base = os.path.join(os.environ.get("APPDATA", home), "Godot", "app_userdata", "Stillwater")
    else:
        base = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share")), "godot", "app_userdata", "Stillwater")
    return os.path.join(base, "levels", "beach_door.draft.json")


def promote(draft_path, path=LEVEL_PATH, characters_dir=CHARACTERS):
    blob = open(draft_path, "rb").read()
    sha_file = draft_path + ".sha256"
    if not os.path.isfile(sha_file) or open(sha_file, encoding="ascii").read().strip() != sha256_hex(blob):
        raise LevelError("The draft does not match its sha256, so it was not kept.")
    draft = json.loads(blob.decode("utf-8"))
    level = apply_positions(read_checked(path, characters_dir), draft)
    return write(level, path, characters_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description="The Stillwater door puzzle level (one schema, Python).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("write-default")
    p = sub.add_parser("promote")
    p.add_argument("--draft", default=default_draft_path())
    args = parser.parse_args(argv)
    try:
        if args.cmd == "check":
            read_checked()
            if canonical_bytes(default_level()) != open(LEVEL_PATH, "rb").read():
                print("note: the level was edited and promoted; it differs from the default layout")
            validate_dare_deck(json.load(open(DARE_DECK_SCHEMA, encoding="utf-8"))["example"]) if os.path.isfile(DARE_DECK_SCHEMA) else None
            print("ok: " + os.path.relpath(LEVEL_PATH, GAME_ROOT) + " and its sha256")
        elif args.cmd == "write-default":
            print("wrote " + os.path.relpath(LEVEL_PATH, GAME_ROOT) + " sha256 " + write(default_level()))
        else:
            print("kept the draft as the level; sha256 " + promote(args.draft))
    except (LevelError, OSError, ValueError) as exc:
        print("refused: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
