extends MeshInstance3D

const JsonFile = preload("res://scripts/json_file.gd")
const Files = preload("res://scripts/gltf_files.gd")
const SPEC_PATH := "res://data/plate.json"

var eye_level := 1.55
var plate_height := 1.8
var slot := "full"
var held := false
var shown_still := ""
var using_clip := false
var finished_look := false
var _clip_view: SubViewport


func _ready() -> void:
    load_default()


func load_default() -> void:
    var data = JsonFile.read(SPEC_PATH)
    if typeof(data) != TYPE_DICTIONARY:
        data = {}
    apply_spec(data)


func apply_spec(spec: Dictionary) -> void:
    # The main still and clip are rated by content_rating (missing = full_21).
    # The game's one SFW switch (Settings.sfw_mode) decides what is drawn: in SFW
    # mode a full_21 slot without a covered file is held, never shown. The
    # shipped picture is a covered stand-in until a still or a short clip is added.
    # The body is the plate glTF, with its feet on the ground.
    finished_look = bool(spec.get("finished_look", false))
    eye_level = float(spec.get("eye_level", eye_level))
    plate_height = float(spec.get("height", plate_height))
    mesh = _mesh_from_gltf(str(spec.get("mesh", "res://assets/plates/plate.gltf")))
    position = Vector3.ZERO
    extra_cull_margin = 1.5
    cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    var chosen := choose_media(spec)
    slot = str(chosen.get("slot", "full"))
    held = slot == "hold"
    visible = not held
    _apply_material(spec, chosen)


func _mesh_from_gltf(path: String) -> Mesh:
    # plate.gltf is the committed character file, read without the import cache.
    var nodes := Files.load_nodes(path)
    var plate: Dictionary = nodes.get("Plate", {})
    return plate.get("mesh")


func choose_media(spec: Dictionary, sfw = null) -> Dictionary:
    var sfw_on: bool = Settings.effective_sfw_mode() if sfw == null else bool(sfw)
    if sfw_on:
        var sfw_still := str(spec.get("sfw_still", ""))
        var sfw_clip := str(spec.get("sfw_clip", ""))
        if sfw_still != "" or sfw_clip != "":
            return {"still": sfw_still, "clip": sfw_clip, "slot": "sfw"}
        if str(spec.get("content_rating", "full_21")) != "sfw":
            # No covered version: a calm hold, never the full picture, never a re-render.
            return {"still": "", "clip": "", "slot": "hold"}
    return {
        "still": str(spec.get("still", "")),
        "clip": str(spec.get("clip", "")),
        "slot": "full",
    }


func _apply_material(spec: Dictionary, chosen: Dictionary) -> void:
    var mat := ShaderMaterial.new()
    mat.shader = Files.shader_from_file("res://shaders/plate.gdshader")
    var still := str(chosen.get("still", ""))
    var clip := str(chosen.get("clip", ""))
    shown_still = still
    using_clip = false
    if clip != "" and FileAccess.file_exists(clip) and _play_clip(mat, clip):
        using_clip = true
    else:
        _set_still(mat, still)
    var depth_path := str(spec.get("depth", ""))
    var depth := Files.texture_from_file(depth_path)
    if depth != null:
        mat.set_shader_parameter("depth_tex", depth)
    material_override = mat


func _set_still(mat: ShaderMaterial, still: String) -> void:
    var picture := Files.texture_from_file(still)
    if picture != null:
        mat.set_shader_parameter("albedo_tex", picture)


func _play_clip(mat: ShaderMaterial, path: String) -> bool:
    # Slot for a short Wan clip that Godot can play (.ogv). Nothing is downloaded here.
    var stream = load(path)
    if stream == null or not (stream is VideoStream):
        return false
    if _clip_view != null and is_instance_valid(_clip_view):
        _clip_view.queue_free()
    _clip_view = SubViewport.new()
    _clip_view.name = "ClipViewport"
    _clip_view.transparent_bg = true
    _clip_view.size = Vector2i(480, 1080)
    _clip_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    var player := VideoStreamPlayer.new()
    player.stream = stream
    player.autoplay = true
    player.loop = true
    player.expand = true
    player.set_anchors_preset(Control.PRESET_FULL_RECT)
    _clip_view.add_child(player)
    add_child(_clip_view)
    mat.set_shader_parameter("albedo_tex", _clip_view.get_texture())
    player.play()
    return true


func _process(_delta: float) -> void:
    if not visible:
        return
    var cam := get_viewport().get_camera_3d()
    if cam == null:
        return
    var aim := Vector3(cam.global_position.x, global_position.y, cam.global_position.z)
    if aim.distance_squared_to(global_position) < 0.0004:
        return
    # QuadMesh faces +Z. Turn that face toward the camera and stay upright.
    look_at(aim, Vector3.UP)
    rotate_y(PI)
