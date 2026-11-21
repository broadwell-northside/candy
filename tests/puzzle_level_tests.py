"""M2: the door puzzle level. Python is the one schema; Godot only checks the hash.

No GPU, no network. Writes go to temporary folders, never to the committed level.
"""
import copy
import importlib.util
import json
import os
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "game", "tools", "puzzle_level.py")


def _tool():
    spec = importlib.util.spec_from_file_location("stillwater_puzzle_level", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _refused(P, level, chars=None):
    try:
        P.validate(level, chars or P.CHARACTERS)
    except P.LevelError as exc:
        return str(exc)
    return ""


def _node(level, nid):
    return next(n for n in level["nodes"] if n["id"] == nid)


def _chars(**ages):
    folder = tempfile.mkdtemp(prefix="pz_chars_")
    for cid, age in ages.items():
        json.dump({"id": cid, "name": cid.title(), "stated_age": age}, open(os.path.join(folder, cid + ".json"), "w"))
    return folder


def unit(check):
    print("\n[M2] Door puzzle level: one schema in Python, written with its sha256")
    P = _tool()
    base = P.default_level()
    check("the default level validates", _refused(P, base) == "")
    committed = open(P.LEVEL_PATH, "rb").read()
    check("the committed level is the writer's exact bytes (no drift)", committed == P.canonical_bytes(base))
    check("the committed sha256 matches the file",
          open(P.LEVEL_PATH + ".sha256").read().strip() == P.sha256_hex(committed))
    check("the committed level reads back through the hash check", P.read_checked()["id"] == "beach_door")
    check("positions sit on the beach terrain", abs(_node(base, "pad_near")["position"]["y"]) < 3.0)
    flags = [n for n in base["nodes"] if not (isinstance(n.get("sfw_safe"), bool) and isinstance(n.get("requires_full_21_mode"), bool))]
    check("every node carries sfw_safe and requires_full_21_mode", flags == [])
    check("this puzzle is reachable in SFW mode", all(n["sfw_safe"] and not n["requires_full_21_mode"] for n in base["nodes"]))

    for flag in ("sfw_safe", "requires_full_21_mode"):
        bad = copy.deepcopy(base)
        _node(bad, "door").pop(flag)
        check(f"a node missing {flag} does not load", flag in _refused(P, bad))
    bad = copy.deepcopy(base)
    bad["actors"][1]["consent"] = "yes"
    check("an actor without consent \"mutual\" does not load", "mutual" in _refused(P, bad))
    bad = copy.deepcopy(base)
    bad["actors"][1].pop("consent")
    check("an actor with no consent entry does not load", "mutual" in _refused(P, bad))
    for age, word in ((20, "20"), ("21", "whole number"), (21.5, "whole number"), (None, "whole number"), (True, "whole number")):
        check(f"a companion whose record says {age!r} is refused", word in _refused(P, base, _chars(mira=age)))
    check("a companion with no character record is refused", "no character record" in _refused(P, base, _chars()))
    check("a companion of 21 is accepted", _refused(P, base, _chars(mira=21)) == "")
    check("21.0 from JSON counts as the whole number 21", _refused(P, base, _chars(mira=21.0)) == "")
    bad = copy.deepcopy(base)
    bad["actors"][0]["stated_age"] = 40
    check("no player age is stored and no Me images are used", "No player age" in _refused(P, bad))
    for word in ("asleep", "drugged", "coerced"):
        bad = copy.deepcopy(base)
        _node(bad, "door")["state"] = word
        check(f"a {word} state does not exist in this schema", "coercion or incapacitation" in _refused(P, bad))
    bad = copy.deepcopy(base)
    _node(bad, "pad_far")["position"] = dict(_node(bad, "pad_near")["position"])
    check("two pads on top of each other are refused (one person could hold both)", "apart" in _refused(P, bad))
    bad = copy.deepcopy(base)
    _node(bad, "door")["position"] = dict(_node(bad, "pad_far")["position"])
    check("a door on a pad is refused", "door cannot sit on a pad" in _refused(P, bad))
    bad = copy.deepcopy(base)
    _node(bad, "key")["position"]["x"] = 40.0
    check("a key in the sea is refused", "off the sand" in _refused(P, bad))
    bad = copy.deepcopy(base)
    _node(bad, "companion")["sockets"][0]["u"] = 1.4
    check("a Stage 1 socket must be {u, v, depth} inside the plate", "{u, v, depth}" in _refused(P, bad))
    bad = copy.deepcopy(base)
    _node(bad, "companion")["sockets"].append({"id": "x", "kind": "intimate_contact", "u": 0.5, "v": 0.5, "depth": 0.0})
    check("this puzzle has no contact sockets", "contact" in _refused(P, bad))
    bad = copy.deepcopy(base)
    _node(bad, "companion")["hitboxes"][0]["action"] = "kiss"
    check("a hitbox must point at one of the two actions", "unknown action" in _refused(P, bad))
    bad = copy.deepcopy(base)
    bad["rules"]["pads_needed"] = 2.5
    check("pads_needed must be the whole number 2", "two pads" in _refused(P, bad))

    deck = json.load(open(os.path.join(ROOT, "schemas", "dare_deck.json")))
    check("the dare deck schema ships empty", deck["properties"]["cards"]["maxItems"] == 0
          and P.validate_dare_deck(deck["example"])["cards"] == [])
    try:
        P.validate_dare_deck({"schema": "stillwater-dare-deck/1", "cards": [{"id": "c1"}]})
        refused = ""
    except P.LevelError as exc:
        refused = str(exc)
    check("a dare card is refused this milestone", "ships empty" in refused, refused)

    folder = tempfile.mkdtemp(prefix="pz_level_")
    path = os.path.join(folder, "beach_door.json")
    shutil.copy(P.LEVEL_PATH, path)
    shutil.copy(P.LEVEL_PATH + ".sha256", path + ".sha256")
    draft = copy.deepcopy(base)
    _node(draft, "key")["position"] = {"x": -8.0, "y": 99.0, "z": 10.0}
    draft["actors"][1]["consent"] = "none"
    _node(draft, "door")["requires_full_21_mode"] = True
    blob = P.canonical_bytes(draft)
    open(os.path.join(folder, "draft.json"), "wb").write(blob)
    open(os.path.join(folder, "draft.json.sha256"), "w").write(P.sha256_hex(blob) + "\n")
    P.promote(os.path.join(folder, "draft.json"), path)
    kept = P.read_checked(path)
    check("promote keeps the moved key", _node(kept, "key")["position"]["x"] == -8.0 and _node(kept, "key")["position"]["z"] == 10.0)
    check("promote recomputes height from the terrain, not the draft", _node(kept, "key")["position"]["y"] != 99.0)
    check("promote takes positions only: consent and flags come from the checked level",
          kept["actors"][1]["consent"] == "mutual" and _node(kept, "door")["requires_full_21_mode"] is False)
    _node(draft, "pad_far")["position"] = dict(_node(draft, "pad_near")["position"])
    blob = P.canonical_bytes(draft)
    open(os.path.join(folder, "draft.json"), "wb").write(blob)
    open(os.path.join(folder, "draft.json.sha256"), "w").write(P.sha256_hex(blob) + "\n")
    try:
        P.promote(os.path.join(folder, "draft.json"), path)
        msg = ""
    except P.LevelError as exc:
        msg = str(exc)
    check("an unsolvable draft is not kept", "apart" in msg, msg)
    open(os.path.join(folder, "draft.json.sha256"), "w").write("0" * 64 + "\n")
    try:
        P.promote(os.path.join(folder, "draft.json"), path)
        msg = ""
    except P.LevelError as exc:
        msg = str(exc)
    check("a draft that does not match its hash is not kept", "sha256" in msg, msg)
    check("the committed level was not touched by these tests", open(P.LEVEL_PATH, "rb").read() == committed)
    check("Godot does not carry a second schema", "LevelError" not in open(os.path.join(ROOT, "game", "scripts", "door_puzzle.gd")).read()
          if os.path.exists(os.path.join(ROOT, "game", "scripts", "door_puzzle.gd")) else True)
