# PRIVATE BUILD — NOT FOR DISTRIBUTION
extends Node3D

## The door puzzle on the 3D beach: pads, the sea-cave door with two lamps, the brass key, and the
## companion as a Stage 1 plate with hitboxes and a {u, v, depth} hand socket. The rules are in
## door_puzzle.gd. "Edit this place" is a mode of Play: move the pads, door and key, then save a draft.
## Placeholder art only (simple meshes and the stand-in plate).

const DoorPuzzle = preload("res://scripts/door_puzzle.gd")
const UI = preload("res://scripts/ui_kit.gd")
const PlateScript = preload("res://scripts/beach_plate.gd")

signal changed

var puzzle = DoorPuzzle.new()
var player: Node3D
var draft_path := DoorPuzzle.DRAFT_PATH
var level_path := DoorPuzzle.LEVEL_PATH
var editing := false
var selected := ""
var meshes: Dictionary = {}
var companion_plate: MeshInstance3D
var door_leaf: MeshInstance3D
var lamp_pads: MeshInstance3D
var lamp_key: MeshInstance3D
var hud: CanvasLayer
var hint_label: Label
var verbs: HBoxContainer
var edit_box: VBoxContainer
var edit_note: Label
var last_message := ""
var _companion_home := Vector3.ZERO


func _ready() -> void:
    name = "DoorPuzzle"
    _ensure_actions()
    _build_hud()
    if not puzzle.load_level(level_path, draft_path):
        hint_label.text = "The door puzzle is resting. " + puzzle.error
        return
    _build_world()
    refresh()


func setup(player_node: Node3D) -> void:
    player = player_node


func _ensure_actions() -> void:
    for pair in [["edit_place", KEY_E], ["puzzle_use", KEY_F]]:
        if not InputMap.has_action(pair[0]):
            InputMap.add_action(pair[0])
        var event := InputEventKey.new()
        event.physical_keycode = pair[1]
        if not InputMap.action_has_event(pair[0], event):
            InputMap.action_add_event(pair[0], event)


# ------------------------------------------------------------------ world
func _material(color: Color, glow := 0.0) -> StandardMaterial3D:
    var mat := StandardMaterial3D.new()
    mat.albedo_color = color
    mat.roughness = 0.8
    if glow > 0.0:
        mat.emission_enabled = true
        mat.emission = color
        mat.emission_energy_multiplier = glow
    return mat


func _build_world() -> void:
    var radius: float = puzzle.pad_radius()
    for pad in puzzle.pads():
        var disc := MeshInstance3D.new()
        disc.name = "Pad_" + pad
        var mesh := CylinderMesh.new()
        mesh.top_radius = radius
        mesh.bottom_radius = radius
        mesh.height = 0.08
        disc.mesh = mesh
        disc.material_override = _material(Color(0.62, 0.55, 0.45))
        add_child(disc)
        meshes[pad] = disc
    var door := Node3D.new()
    door.name = "Door"
    add_child(door)
    meshes[puzzle.rule("door")] = door
    for side in [-1.0, 1.0]:
        var post := MeshInstance3D.new()
        var box := BoxMesh.new()
        box.size = Vector3(0.3, 2.6, 0.4)
        post.mesh = box
        post.position = Vector3(side * 1.0, 1.3, 0.0)
        post.material_override = _material(Color(0.45, 0.40, 0.36))
        door.add_child(post)
    var lintel := MeshInstance3D.new()
    var top := BoxMesh.new()
    top.size = Vector3(2.3, 0.3, 0.4)
    lintel.mesh = top
    lintel.position = Vector3(0.0, 2.75, 0.0)
    lintel.material_override = _material(Color(0.45, 0.40, 0.36))
    door.add_child(lintel)
    door_leaf = MeshInstance3D.new()
    door_leaf.name = "Leaf"
    var leaf := BoxMesh.new()
    leaf.size = Vector3(1.7, 2.5, 0.12)
    door_leaf.mesh = leaf
    door_leaf.position = Vector3(0.0, 1.25, 0.0)
    door_leaf.material_override = _material(Color(0.36, 0.25, 0.17))
    door.add_child(door_leaf)
    lamp_pads = _lamp(door, Vector3(-0.45, 2.95, 0.22), "LampPads")
    lamp_key = _lamp(door, Vector3(0.45, 2.95, 0.22), "LampKey")
    var key := MeshInstance3D.new()
    key.name = "Key"
    var bar := BoxMesh.new()
    bar.size = Vector3(0.45, 0.09, 0.09)
    key.mesh = bar
    key.material_override = _material(Color(0.82, 0.66, 0.28), 0.4)
    add_child(key)
    meshes[puzzle.rule("key")] = key
    companion_plate = PlateScript.new()
    companion_plate.name = "Companion"
    add_child(companion_plate)
    var body := StaticBody3D.new()
    body.name = "PlateBody"
    body.collision_layer = 2  # for clicking her hitboxes only; the player walks through a Stage 1 plate
    body.collision_mask = 0
    var shape := CollisionShape3D.new()
    var hit := BoxShape3D.new()
    var spec: Dictionary = puzzle.nodes.get(puzzle.rule("companion"), {}).get("plate", {})
    hit.size = Vector3(float(spec.get("width", 0.72)), float(spec.get("height", 1.8)), 0.08)
    shape.shape = hit
    shape.position = Vector3(0.0, float(spec.get("height", 1.8)) * 0.5, 0.0)
    body.add_child(shape)
    companion_plate.add_child(body)
    meshes[puzzle.rule("companion")] = companion_plate
    _companion_home = puzzle.position_of(puzzle.rule("companion"))
    _place_all()


func _lamp(parent: Node3D, at: Vector3, lamp_name: String) -> MeshInstance3D:
    var lamp := MeshInstance3D.new()
    lamp.name = lamp_name
    var ball := SphereMesh.new()
    ball.radius = 0.12
    ball.height = 0.24
    lamp.mesh = ball
    lamp.position = at
    parent.add_child(lamp)
    return lamp


func _place_all() -> void:
    for id in [puzzle.rule("near_pad"), puzzle.rule("far_pad"), puzzle.rule("door"), puzzle.rule("key"), puzzle.rule("companion")]:
        if meshes.has(id):
            (meshes[id] as Node3D).position = puzzle.position_of(id) + (Vector3(0, 0.04, 0) if id.begins_with("pad") else Vector3.ZERO)


# ------------------------------------------------------------------ HUD
func _build_hud() -> void:
    hud = CanvasLayer.new()
    hud.name = "PuzzleHud"
    add_child(hud)
    var panel := UI.panel(UI.with_alpha(UI.color("surface"), 0.92), 12, 12)
    panel.name = "PuzzlePanel"
    panel.anchor_top = 1.0
    panel.anchor_bottom = 1.0
    panel.offset_left = 16.0
    panel.offset_top = -200.0
    panel.offset_right = 470.0
    panel.offset_bottom = -64.0
    hud.add_child(panel)
    var col := UI.vbox(8)
    panel.add_child(col)
    hint_label = UI.label("", 18, UI.color("text"), true)
    hint_label.name = "PuzzleHint"
    col.add_child(hint_label)
    verbs = UI.hbox(8)
    verbs.name = "Verbs"
    col.add_child(verbs)
    var edit := UI.button("Edit this place", 200, false)
    edit.name = "EditPlace"
    edit.pressed.connect(func(): set_editing(not editing))
    col.add_child(edit)
    edit_box = UI.vbox(6)
    edit_box.name = "EditBox"
    edit_box.visible = false
    col.add_child(edit_box)


func _verb(text: String, fn: Callable) -> void:
    var b := UI.button(text, 220, true)
    b.pressed.connect(fn)
    verbs.add_child(b)


func _player_xz() -> Vector2:
    if player == null or not is_instance_valid(player):
        return Vector2(INF, INF)
    return Vector2(player.global_position.x, player.global_position.z)


func _near(id: String, distance: float) -> bool:
    var p := (meshes[id] as Node3D).global_position if meshes.has(id) else puzzle.position_of(id)
    return _player_xz().distance_to(Vector2(p.x, p.z)) <= distance


func refresh() -> void:
    if puzzle.level.is_empty():
        return
    _place_dynamic()
    for pad in puzzle.pads():
        var held: bool = puzzle.on_pad.has(pad)
        (meshes[pad] as MeshInstance3D).material_override = _material(Color(0.95, 0.72, 0.36) if held else Color(0.62, 0.55, 0.45), 1.2 if held else 0.0)
    lamp_pads.material_override = _material(Color(0.4, 0.9, 0.6) if puzzle.pads_held() else Color(0.3, 0.3, 0.3), 1.5 if puzzle.pads_held() else 0.0)
    lamp_key.material_override = _material(Color(0.4, 0.9, 0.6) if puzzle.key_set else Color(0.3, 0.3, 0.3), 1.5 if puzzle.key_set else 0.0)
    door_leaf.position = Vector3(0.0, 1.25, 0.0) if not puzzle.door_open else Vector3(1.6, 1.25, -0.2)
    door_leaf.rotation.y = 0.0 if not puzzle.door_open else -1.2
    var text: String = puzzle.next_hint()
    if editing:
        text = "Edit this place: pick a piece, move it on the sand, then save a draft."
    elif last_message != "":
        text = last_message + "  Next: " + text if not puzzle.door_open else last_message + "  " + text
    if puzzle.draft_note != "" and not editing:
        text += "\n" + puzzle.draft_note
    hint_label.text = text
    _rebuild_verbs()
    changed.emit()


func _place_dynamic() -> void:
    var comp_id: String = puzzle.rule("companion")
    var who: String = puzzle.companion()
    var plate := meshes[comp_id] as Node3D
    if puzzle.actor_pad.has(who):
        plate.position = puzzle.position_of(str(puzzle.actor_pad[who]))
    elif puzzle.key_set:
        plate.position = puzzle.position_of(puzzle.rule("door")) + Vector3(-1.6, 0.0, -1.2)
    else:
        plate.position = puzzle.position_of(comp_id)
    if player != null and is_instance_valid(player):
        var look := player.global_position
        look.y = plate.global_position.y
        if look.distance_to(plate.global_position) > 0.2:
            plate.look_at(look, Vector3.UP, true)
    var key := meshes[puzzle.rule("key")] as Node3D
    if puzzle.key_set:
        key.global_position = (meshes[puzzle.rule("door")] as Node3D).global_position + Vector3(0.0, 1.2, -0.25)
    elif puzzle.key_holder == DoorPuzzle.PLAYER and player != null and is_instance_valid(player):
        key.global_position = player.global_position + Vector3(0.0, 0.2, 0.0)
    elif puzzle.key_holder == who:
        key.global_position = plate.to_global(puzzle.socket_local("hand_r"))
    else:
        key.position = puzzle.position_of(puzzle.rule("key")) + Vector3(0.0, 0.05, 0.0)


func available_verbs() -> Array:
    var out: Array = []
    if editing or puzzle.door_open:
        return out
    if puzzle.key_holder == "" and not puzzle.key_set and _near(puzzle.rule("key"), puzzle.reach()):
        out.append(["Pick up the key", "pick_up_key"])
    if _near(puzzle.rule("companion"), puzzle.reach() + 0.6):
        if puzzle.key_holder == DoorPuzzle.PLAYER:
            out.append(["Give her the key", "take_key"])
        if not puzzle.actor_pad.has(puzzle.companion()):
            out.append(["Stand on the far pad", "stand_on_far_pad"])
    return out


var _verb_key := "-"


func _rebuild_verbs() -> void:
    var wanted := available_verbs()
    var key := str(wanted)
    if key == _verb_key:
        return
    _verb_key = key
    for child in verbs.get_children():
        child.queue_free()
    for row in wanted:
        var action: String = row[1]
        _verb(row[0], func(): act(action))


func act(action: String) -> void:
    match action:
        "pick_up_key":
            last_message = "You have the key." if puzzle.pick_up_key(DoorPuzzle.PLAYER) else ""
        _:
            last_message = puzzle.companion_action(action)
    refresh()


func pick_plate(u: float, v: float) -> String:
    var action: String = puzzle.hitbox_at(u, v)
    if action != "":
        act(action)
    return action


func _process(_delta: float) -> void:
    if puzzle.level.is_empty() or editing:
        return
    var changed_pad := false
    var standing := ""
    for pad in puzzle.pads():
        if _near(pad, puzzle.pad_radius()):
            standing = pad
    var current := str(puzzle.actor_pad.get(DoorPuzzle.PLAYER, ""))
    if standing != current:
        if standing == "":
            puzzle.step_off(DoorPuzzle.PLAYER)
        else:
            puzzle.step_on(DoorPuzzle.PLAYER, standing)
        changed_pad = true
    if changed_pad or Engine.get_process_frames() % 15 == 0:
        refresh()


func _input(event: InputEvent) -> void:
    if puzzle.level.is_empty():
        return
    if event.is_action_pressed("edit_place"):
        set_editing(not editing)
        get_viewport().set_input_as_handled()
        return
    if editing and event is InputEventKey and event.pressed:
        var step := {KEY_LEFT: Vector2(-0.5, 0), KEY_RIGHT: Vector2(0.5, 0), KEY_UP: Vector2(0, -0.5), KEY_DOWN: Vector2(0, 0.5)}
        if step.has(event.physical_keycode) and selected != "":
            nudge(step[event.physical_keycode].x, step[event.physical_keycode].y)
            get_viewport().set_input_as_handled()
        return
    if event.is_action_pressed("puzzle_use") and verbs.get_child_count() > 0:
        (verbs.get_child(0) as Button).pressed.emit()
        get_viewport().set_input_as_handled()
        return
    # A click on the companion's plate hits one of its hitboxes (Stage 1: plates and hitboxes).
    if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
        var camera := get_viewport().get_camera_3d()
        if camera == null or companion_plate == null:
            return
        var from := camera.project_ray_origin(event.position)
        var to := from + camera.project_ray_normal(event.position) * 60.0
        var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, to, 2))
        if hit.is_empty() or hit.get("collider") == null or (hit["collider"] as Node).get_parent() != companion_plate:
            return
        var local := companion_plate.to_local(hit["position"])
        var spec: Dictionary = puzzle.nodes.get(puzzle.rule("companion"), {}).get("plate", {})
        var u := local.x / float(spec.get("width", 0.72)) + 0.5
        var v := 1.0 - local.y / float(spec.get("height", 1.8))
        if pick_plate(u, v) != "":
            get_viewport().set_input_as_handled()


# ------------------------------------------------------------------ Edit this place
func set_editing(on: bool) -> void:
    editing = on
    edit_box.visible = on
    for child in edit_box.get_children():
        child.queue_free()
    if on:
        selected = str(puzzle.movable()[0]) if puzzle.movable().size() > 0 else ""
        var pick := UI.hbox(6)
        for id in puzzle.movable():
            var b := UI.button(str(puzzle.nodes[id].get("label", id)), 140, false)
            b.name = "Pick_" + id
            b.pressed.connect(func(): selected = id; _edit_status())
            pick.add_child(b)
        edit_box.add_child(pick)
        var arrows := UI.hbox(6)
        for pair in [["◀", -0.5, 0.0], ["▶", 0.5, 0.0], ["▲", 0.0, -0.5], ["▼", 0.0, 0.5]]:
            var a := UI.button(pair[0], 64, false)
            var dx: float = pair[1]
            var dz: float = pair[2]
            a.pressed.connect(func(): nudge(dx, dz))
            arrows.add_child(a)
        var save := UI.button("Save draft", 160, true)
        save.name = "SaveDraft"
        save.pressed.connect(func(): save_draft())
        arrows.add_child(save)
        edit_box.add_child(arrows)
        edit_note = UI.label("", 14, UI.color("muted"), true)
        edit_box.add_child(edit_note)
        _edit_status()
    else:
        puzzle.reset()
        last_message = ""
    refresh()


func nudge(dx: float, dz: float) -> void:
    if selected == "":
        return
    puzzle.edit_move(selected, dx, dz)
    var p: Vector3 = puzzle.position_of(selected)
    puzzle.move_to(selected, p.x, p.z, _ground_y(p.x, p.z, p.y))
    _place_all()
    _edit_status()
    refresh()


func save_draft() -> bool:
    var ok: bool = puzzle.save_draft(draft_path)
    if edit_note != null:
        edit_note.text = ("Draft saved. It is used next time you visit. To keep it as the real level, run: python3 game/tools/puzzle_level.py promote" if ok else "The draft could not be saved.")
    return ok


func _edit_status() -> void:
    if edit_note == null:
        return
    var label := str(puzzle.nodes.get(selected, {}).get("label", selected))
    var warn: String = puzzle.layout_note()
    edit_note.text = "Moving: " + label + " (arrow keys or the arrows, half a metre at a time)." + ("\n" + warn if warn != "" else "")


func _ground_y(x: float, z: float, fallback: float) -> float:
    var space := get_world_3d().direct_space_state if is_inside_tree() else null
    if space == null:
        return fallback
    var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, 30.0, z), Vector3(x, -10.0, z), 1))
    if hit.is_empty():
        return fallback
    return float(hit["position"].y)
