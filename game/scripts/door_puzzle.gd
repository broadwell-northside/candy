# PRIVATE BUILD — NOT FOR DISTRIBUTION
extends RefCounted

## The door-unlock co-op puzzle: the rules of play live here, in code. The level file holds content and
## tuning only. It is written and validated by game/tools/puzzle_level.py (the one schema); this script
## checks the file's sha256 and does not validate it a second time. JSON numbers go through
## Settings.whole_number(). The puzzle never calls chat_brain.gd, dialogue_runner.gd or scenes.json.
##
## Goal: both pressure pads held at the same time (you and your companion), and the brass key passed to
## the companion, who sets it in the door. The two goals can be met in either order.

const LEVEL_PATH := "res://data/puzzles/beach_door.json"
const DRAFT_PATH := "user://levels/beach_door.draft.json"
const PLAYER := "player"

var level: Dictionary = {}
var nodes: Dictionary = {}
var error := ""
var source := ""
var on_pad: Dictionary = {}
var actor_pad: Dictionary = {}
var key_holder := ""
var key_set := false
var door_open := false
var draft_note := ""


static func read_hash(path: String) -> String:
    var sha_path := path + ".sha256"
    if not FileAccess.file_exists(sha_path):
        return ""
    return FileAccess.get_file_as_string(sha_path).strip_edges()


static func hash_ok(path: String) -> bool:
    if not FileAccess.file_exists(path):
        return false
    var want := read_hash(path)
    return want != "" and want == FileAccess.get_sha256(path)


static func reachable(node: Dictionary, sfw_mode: bool) -> bool:
    # A node without both flags is never reachable. In SFW mode only sfw_safe, non-21 nodes are.
    if typeof(node.get("sfw_safe")) != TYPE_BOOL or typeof(node.get("requires_full_21_mode")) != TYPE_BOOL:
        return false
    if not sfw_mode:
        return true
    return bool(node["sfw_safe"]) and not bool(node["requires_full_21_mode"])


func load_level(path := LEVEL_PATH, draft_path := DRAFT_PATH) -> bool:
    error = ""
    source = ""
    level = {}
    nodes = {}
    if not FileAccess.file_exists(path):
        error = "The puzzle file is missing."
        return false
    if not hash_ok(path):
        error = "The puzzle file does not match its sha256, so it was not loaded."
        return false
    var data = JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(data) != TYPE_DICTIONARY or typeof(data.get("nodes")) != TYPE_ARRAY:
        error = "The puzzle file is not readable."
        return false
    level = data
    for row in level["nodes"]:
        if typeof(row) == TYPE_DICTIONARY:
            nodes[str(row.get("id", ""))] = row
    source = "level"
    if draft_path != "" and apply_draft(draft_path):
        source = "draft"
    reset()
    return true


func reset() -> void:
    on_pad = {}
    actor_pad = {}
    key_holder = ""
    key_set = false
    door_open = false


func rule(name: String) -> String:
    return str(level.get("rules", {}).get(name, ""))


func companion() -> String:
    return str(nodes.get(rule("companion"), {}).get("actor", ""))


func pads() -> Array:
    var out: Array = []
    for id in nodes.keys():
        if str(nodes[id].get("kind", "")) == "pressure_pad":
            out.append(id)
    out.sort()
    return out


func pads_needed() -> int:
    return Settings.whole_number(level.get("rules", {}).get("pads_needed", 0))


func pad_radius() -> float:
    return float(level.get("rules", {}).get("pad_radius", 0.9))


func reach() -> float:
    return float(level.get("rules", {}).get("reach", 1.8))


func hint(key: String) -> String:
    return str(level.get("hints", {}).get(key, ""))


func position_of(id: String) -> Vector3:
    var p = nodes.get(id, {}).get("position", {})
    if typeof(p) != TYPE_DICTIONARY:
        return Vector3.ZERO
    return Vector3(float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 0.0)))


# ------------------------------------------------------------------ play
func step_on(actor: String, pad: String) -> bool:
    if not nodes.has(pad) or str(nodes[pad].get("kind", "")) != "pressure_pad":
        return false
    if on_pad.has(pad) and str(on_pad[pad]) != actor:
        return false
    if actor_pad.has(actor) and str(actor_pad[actor]) == pad:
        return true
    step_off(actor)
    on_pad[pad] = actor
    actor_pad[actor] = pad
    _evaluate()
    return true


func step_off(actor: String) -> void:
    if actor_pad.has(actor):
        on_pad.erase(actor_pad[actor])
        actor_pad.erase(actor)
    _evaluate()


func pick_up_key(actor: String) -> bool:
    if key_set or key_holder != "":
        return false
    key_holder = actor
    return true


func give_key(from_actor: String, to_actor: String) -> bool:
    if key_holder != from_actor:
        return false
    key_holder = to_actor
    return true


func set_key(actor: String) -> bool:
    # Only the companion sets the key. She steps off her pad to reach the door.
    if key_holder != actor or actor != companion():
        return false
    step_off(actor)
    key_holder = ""
    key_set = true
    _evaluate()
    return true


func companion_action(action: String) -> String:
    var who := companion()
    var who_label := str(nodes.get(rule("companion"), {}).get("label", who))
    match action:
        "stand_on_far_pad":
            if step_on(who, rule("far_pad")):
                return who_label + " holds the far pad."
            return "Someone is already on the far pad."
        "take_key":
            if give_key(PLAYER, who) and set_key(who):
                return who_label + " sets the key in the door."
            return "You are not holding the key."
    return ""


func pads_held() -> bool:
    var actors := {}
    for pad in pads():
        if on_pad.has(pad):
            actors[str(on_pad[pad])] = true
    return pads_needed() > 0 and actors.size() >= pads_needed()


func _evaluate() -> void:
    door_open = key_set and pads_held()


func next_hint() -> String:
    if door_open:
        return hint("open")
    if not key_set:
        if key_holder == "":
            return hint("key")
        if key_holder == PLAYER:
            return hint("give")
    if not on_pad.has(rule("near_pad")):
        return hint("near")
    return hint("far")


# ------------------------------------------------------------------ plates (Stage 1)
func hitbox_at(u: float, v: float) -> String:
    for hb in nodes.get(rule("companion"), {}).get("hitboxes", []):
        var r: Dictionary = hb.get("rect", {})
        if u >= float(r.get("u0", 2.0)) and u <= float(r.get("u1", -1.0)) and v >= float(r.get("v0", 2.0)) and v <= float(r.get("v1", -1.0)):
            return str(hb.get("action", ""))
    return ""


func socket_local(socket_id: String) -> Vector3:
    # Stage 1 socket {u, v, depth} on the plate quad: u across, v down from the top, depth toward the camera.
    var plate: Dictionary = nodes.get(rule("companion"), {})
    var spec: Dictionary = plate.get("plate", {})
    var width := float(spec.get("width", 0.72))
    var height := float(spec.get("height", 1.8))
    for sock in plate.get("sockets", []):
        if str(sock.get("id", "")) == socket_id:
            return Vector3((float(sock.get("u", 0.5)) - 0.5) * width, (1.0 - float(sock.get("v", 0.5))) * height, float(sock.get("depth", 0.0)))
    return Vector3(0.0, height * 0.5, 0.0)


# ------------------------------------------------------------------ Edit this place
func bounds() -> Rect2:
    var b: Dictionary = level.get("bounds", {})
    var min_x := float(b.get("min_x", 0.0))
    var min_z := float(b.get("min_z", 0.0))
    return Rect2(min_x, min_z, float(b.get("max_x", 0.0)) - min_x, float(b.get("max_z", 0.0)) - min_z)


func movable() -> Array:
    var out: Array = []
    for id in [rule("near_pad"), rule("far_pad"), rule("door"), rule("key")]:
        if nodes.has(id):
            out.append(id)
    return out


func move_to(id: String, x: float, z: float, y = null) -> bool:
    if not movable().has(id) and id != rule("companion"):
        return false
    var r := bounds()
    var p: Dictionary = nodes[id].get("position", {}).duplicate()
    p["x"] = clampf(x, r.position.x, r.end.x)
    p["z"] = clampf(z, r.position.y, r.end.y)
    if y != null:
        p["y"] = float(y)
    nodes[id]["position"] = p
    return true


func edit_move(id: String, dx: float, dz: float) -> bool:
    var p := position_of(id)
    return move_to(id, p.x + dx, p.z + dz)


func layout_note() -> String:
    var a := position_of(rule("near_pad"))
    var b := position_of(rule("far_pad"))
    if Vector2(a.x, a.z).distance_to(Vector2(b.x, b.z)) < 2.0:
        return "The pads are under 2 m apart, so one person could hold both. Keeping this draft will be refused."
    var d := position_of(rule("door"))
    for p in [a, b]:
        if Vector2(d.x, d.z).distance_to(Vector2(p.x, p.z)) < 1.5:
            return "The door is on a pad. Keeping this draft will be refused."
    return ""


func draft_dict() -> Dictionary:
    # Positions only. The level checker takes nothing else from a draft.
    var rows: Array = []
    for id in movable():
        var p := position_of(id)
        rows.append({"id": id, "position": {"x": snappedf(p.x, 0.001), "y": snappedf(p.y, 0.001), "z": snappedf(p.z, 0.001)}})
    return {"schema": "stillwater-level-draft/1", "notice": "PRIVATE BUILD — NOT FOR DISTRIBUTION",
        "id": str(level.get("id", "")), "nodes": rows}


func save_draft(path := DRAFT_PATH) -> bool:
    DirAccess.make_dir_recursive_absolute(path.get_base_dir())
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(JSON.stringify(draft_dict(), "  ", true) + "\n")
    file.close()
    var sha := FileAccess.open(path + ".sha256", FileAccess.WRITE)
    if sha == null:
        return false
    sha.store_string(FileAccess.get_sha256(path) + "\n")
    sha.close()
    return true


func apply_draft(path: String) -> bool:
    draft_note = ""
    if not FileAccess.file_exists(path):
        return false
    if not hash_ok(path):
        draft_note = "Your saved draft does not match its sha256, so the checked level is used."
        return false
    var data = JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(data) != TYPE_DICTIONARY or typeof(data.get("nodes")) != TYPE_ARRAY:
        return false
    for row in data["nodes"]:
        if typeof(row) != TYPE_DICTIONARY or typeof(row.get("position")) != TYPE_DICTIONARY:
            continue
        var id := str(row.get("id", ""))
        if not movable().has(id):
            continue
        var p: Dictionary = row["position"]
        var x = p.get("x")
        var z = p.get("z")
        if (typeof(x) != TYPE_FLOAT and typeof(x) != TYPE_INT) or (typeof(z) != TYPE_FLOAT and typeof(z) != TYPE_INT):
            continue
        var y = p.get("y")
        move_to(id, float(x), float(z), float(y) if (typeof(y) == TYPE_FLOAT or typeof(y) == TYPE_INT) else null)
    draft_note = "Using your saved draft from Edit this place."
    return true
