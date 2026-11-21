extends Node3D

signal leave

const UI = preload("res://scripts/ui_kit.gd")
const Files = preload("res://scripts/gltf_files.gd")
const LEVEL_GLTF := "res://assets/beach/level.gltf"

const Day = preload("res://scripts/beach_day.gd")
const PersonScript = preload("res://scripts/beach_person.gd")

var player: CharacterBody3D
var people: Node3D
var place_label: Label
var _pin_feet := false


func _ready() -> void:
    UI.sync()
    var method := RendererBoot.current_method()
    _sky(method)
    _sun(method)
    var level := _level()
    _terrain(level)
    _ocean(level, method)
    _navigation(level)
    _hide_static_plate(level)
    _player(level)
    _people()
    _hud()
    _puzzle()


func make_environment(method: String) -> Environment:
    var env := Environment.new()
    var sky := Sky.new()
    var sky_mat := ProceduralSkyMaterial.new()
    sky_mat.sky_top_color = Color(0.40, 0.58, 0.84)
    sky_mat.sky_horizon_color = Color(0.97, 0.66, 0.38)
    sky_mat.ground_horizon_color = Color(0.86, 0.62, 0.40)
    sky_mat.ground_bottom_color = Color(0.45, 0.36, 0.28)
    sky_mat.sun_angle_max = 26.0
    sky_mat.sky_energy_multiplier = 1.05
    sky.sky_material = sky_mat
    env.background_mode = Environment.BG_SKY
    env.sky = sky
    env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
    env.ambient_light_energy = 0.8
    env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
    # Volumetric fog is Forward+ only. GL Compatibility leaves it off.
    if method == "forward_plus":
        env.volumetric_fog_enabled = true
        env.volumetric_fog_density = 0.008
        env.volumetric_fog_albedo = Color(1.0, 0.78, 0.55)
        env.volumetric_fog_length = 42.0
    else:
        env.volumetric_fog_enabled = false
    return env


func _sky(method: String) -> void:
    var world := WorldEnvironment.new()
    world.name = "WorldEnvironment"
    world.environment = make_environment(method)
    add_child(world)


func _sun(method: String) -> void:
    var sun := DirectionalLight3D.new()
    sun.name = "Sun"
    sun.rotation_degrees = Vector3(-16, 38, 0)
    sun.light_color = Color(1.0, 0.74, 0.46)
    sun.light_energy = 1.55
    sun.shadow_enabled = method == "forward_plus"
    add_child(sun)


func _level() -> Node:
    # The committed glTF is the level. This does not open a .godot import.
    var level := Node3D.new()
    level.name = "Level"
    var nodes := Files.load_nodes(LEVEL_GLTF)
    for node_name in ["Terrain", "Ocean", "Navmesh", "PlayerStart", "Plate"]:
        var spec: Dictionary = nodes.get(node_name, {})
        var node := Node3D.new()
        if spec.get("mesh") != null:
            var mesh_node := MeshInstance3D.new()
            mesh_node.mesh = spec.get("mesh")
            node = mesh_node
        node.name = node_name
        node.position = spec.get("translation", Vector3.ZERO)
        level.add_child(node)
    add_child(level)
    return level


func _terrain(level: Node) -> void:
    var terrain := _find_named(level, "Terrain") as MeshInstance3D
    if terrain == null:
        return
    var sand := ShaderMaterial.new()
    sand.shader = Files.shader_from_file("res://shaders/sand.gdshader")
    terrain.material_override = sand
    terrain.create_trimesh_collision()
    var body := terrain.get_child(0) as StaticBody3D
    if body != null:
        body.name = "TerrainBody"
        for child in body.get_children():
            if child is CollisionShape3D:
                var concave := child.shape as ConcavePolygonShape3D
                if concave != null:
                    concave.backface_collision = true


func _ocean(level: Node, method: String) -> void:
    var ocean := _find_named(level, "Ocean") as MeshInstance3D
    if ocean == null:
        return
    var mat := ShaderMaterial.new()
    var shader_path := "res://shaders/ocean_gl.gdshader"
    if method == "forward_plus":
        shader_path = "res://shaders/ocean_forward.gdshader"
    mat.shader = Files.shader_from_file(shader_path)
    ocean.material_override = mat
    ocean.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _navigation(level: Node) -> void:
    var visual := _find_named(level, "Navmesh") as MeshInstance3D
    var region := NavigationRegion3D.new()
    region.name = "Navigation"
    if visual != null and visual.mesh != null:
        visual.visible = false
        region.navigation_mesh = _nav_from_mesh(visual.mesh)
    add_child(region)


func _nav_from_mesh(source: Mesh) -> NavigationMesh:
    var arrays: Array = source.surface_get_arrays(0)
    var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    var nav := NavigationMesh.new()
    nav.vertices = verts
    var cursor := 0
    while cursor + 2 < indices.size():
        nav.add_polygon(PackedInt32Array([indices[cursor], indices[cursor + 1], indices[cursor + 2]]))
        cursor += 3
    return nav


func _hide_static_plate(level: Node) -> void:
    # The level file keeps a plate so the glTF shows a person on the sand.
    # The one that walks is the character glTF on the player.
    var placed := _find_named(level, "Plate")
    if placed is Node3D:
        placed.visible = false


func _player(level: Node) -> void:
    player = preload("res://scripts/beach_player.gd").new()
    player.name = "Player"
    var start := _find_named(level, "PlayerStart") as Node3D
    var feet := start.global_position if start != null else Vector3(0, 1, 14)
    player.position = feet + Vector3(0, 1.5, 0)
    add_child(player)


func _puzzle() -> void:
    # The door-unlock co-op puzzle (M2). Its file is checked by hash; its rules are code.
    var view := preload("res://scripts/door_puzzle_view.gd").new()
    view.setup(player)
    add_child(view)


func _people() -> void:
    people = Node3D.new()
    people.name = "People"
    add_child(people)
    place_people()


func place_people() -> void:
    # Each adult stands on the spot written for this time of day.
    var when := str(SaveGame.progress.get("time_of_day", "morning"))
    var records: Array = Day.present(CharacterDB.characters, when)
    var keep := {}
    for record in records:
        var id := str(record.get("id", ""))
        if id == "":
            continue
        keep[id] = true
        var person := people.get_node_or_null(id) as Node3D
        if person == null:
            person = PersonScript.new()
            person.name = id
            people.add_child(person)
        person.show_person(record)
        var x := float(record["x"])
        var z := float(record["z"])
        person.position = Vector3(x, _sand_y(x, z), z)
    var extra: Array = []
    for child in people.get_children():
        if not keep.has(str(child.name)):
            extra.append(child)
    for child in extra:
        people.remove_child(child)
        child.free()
    if place_label != null:
        place_label.text = "Beach · " + when.capitalize()
    _pin_feet = true


func _sand_y(x: float, z: float) -> float:
    var hit = _ray_y(x, z)
    if hit == null:
        return Day.terrain_height(x, z)
    return float(hit)


func _ray_y(x: float, z: float):
    var world := get_world_3d()
    if world == null:
        return null
    var space := world.direct_space_state
    if space == null:
        return null
    var query := PhysicsRayQueryParameters3D.create(Vector3(x, 24.0, z), Vector3(x, -4.0, z))
    var hit := space.intersect_ray(query)
    if hit.is_empty():
        return null
    return float(hit.position.y)


func _physics_process(_delta: float) -> void:
    if not _pin_feet or people == null:
        return
    var settled := people.get_child_count() > 0
    for child in people.get_children():
        var hit = _ray_y(child.position.x, child.position.z)
        if hit == null:
            settled = false
            continue
        child.position.y = float(hit)
    if settled:
        _pin_feet = false


func _let_time_pass() -> void:
    SaveGame.advance_time()
    SaveGame.autosave()
    place_people()


func _find_named(node: Node, wanted: String) -> Node:
    if node != null and str(node.name) == wanted:
        return node
    if node == null:
        return null
    for child in node.get_children():
        var found := _find_named(child, wanted)
        if found != null:
            return found
    return null


func _hud() -> void:
    var layer := CanvasLayer.new()
    layer.name = "Hud"
    add_child(layer)
    var root := Control.new()
    root.name = "Bar"
    root.anchor_right = 1.0
    root.offset_bottom = 76.0
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE
    layer.add_child(root)
    var wash := ColorRect.new()
    wash.color = UI.with_alpha(UI.color("surface"), 0.92)
    wash.anchor_right = 1.0
    wash.anchor_bottom = 1.0
    wash.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(wash)
    var row := UI.hbox(12)
    row.anchor_right = 1.0
    row.anchor_bottom = 1.0
    row.offset_left = 24.0
    row.offset_right = -24.0
    row.offset_top = 12.0
    row.offset_bottom = -12.0
    row.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(row)
    var title := UI.label("Beach", 28, UI.color("text"))
    title.name = "Place"
    title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    row.add_child(title)
    place_label = title
    place_label.text = "Beach · " + str(SaveGame.progress.get("time_of_day", "morning")).capitalize()
    var view := UI.button("View", 120, false)
    view.pressed.connect(player.toggle_view)
    row.add_child(view)
    var later := UI.button("Let a little time pass", 250, false)
    later.name = "Later"
    later.pressed.connect(_let_time_pass)
    row.add_child(later)
    var back := UI.button("Map", 120, false)
    back.pressed.connect(func(): leave.emit())
    row.add_child(back)
    var caption := UI.label("Stand-in, not the finished photo", 14, UI.color("text"))
    caption.name = "StandIn"
    caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    var note := UI.panel(UI.with_alpha(UI.color("surface"), 0.9), 8, 8)
    note.anchor_left = 0.5
    note.anchor_right = 0.5
    note.anchor_top = 1.0
    note.anchor_bottom = 1.0
    note.offset_left = -150.0
    note.offset_right = 150.0
    note.offset_top = -44.0
    note.offset_bottom = -12.0
    note.mouse_filter = Control.MOUSE_FILTER_IGNORE
    layer.add_child(note)
    note.add_child(caption)


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
            Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
        else:
            leave.emit()
        get_viewport().set_input_as_handled()


func _exit_tree() -> void:
    if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
        Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
