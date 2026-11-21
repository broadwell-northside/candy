extends CharacterBody3D

const SPEED := 4.2
const GRAVITY := 14.0

var camera_rig: Node3D
var camera: Camera3D
var plate: MeshInstance3D
var agent: NavigationAgent3D
var first_person := false
var use_scripted := false
var scripted := Vector2.ZERO
var pitch := 0.0
var base_pitch := 0.0


func _ready() -> void:
    _ensure_actions()
    _collision()
    _camera()
    _agent()
    plate = preload("res://scripts/beach_plate.gd").new()
    plate.name = "Plate"
    add_child(plate)
    _place_camera()


func _collision() -> void:
    var shape := CapsuleShape3D.new()
    shape.radius = 0.28
    shape.height = 1.7
    var col := CollisionShape3D.new()
    col.name = "Collision"
    col.shape = shape
    col.position = Vector3(0, 0.85, 0)
    add_child(col)
    up_direction = Vector3.UP
    floor_snap_length = 0.25
    motion_mode = CharacterBody3D.MOTION_MODE_GROUNDED


func _camera() -> void:
    camera_rig = Node3D.new()
    camera_rig.name = "CameraRig"
    camera_rig.position = Vector3(0, 1.55, 0)
    add_child(camera_rig)
    camera = Camera3D.new()
    camera.name = "Camera3D"
    camera.current = true
    camera.fov = 52.0
    camera_rig.add_child(camera)


func _agent() -> void:
    agent = NavigationAgent3D.new()
    agent.name = "NavigationAgent3D"
    agent.avoidance_enabled = false
    agent.path_desired_distance = 0.45
    agent.target_desired_distance = 0.5
    agent.radius = 0.3
    agent.height = 1.7
    add_child(agent)


func _place_camera() -> void:
    if camera == null:
        return
    if first_person:
        camera.position = Vector3(0, 0, 0.04)
        camera.rotation = Vector3(pitch, 0, 0)
        if plate != null:
            plate.visible = false
    else:
        camera.position = Vector3(0, 0.32, 3.8)
        camera.rotation = Vector3.ZERO
        camera.look_at(camera_rig.global_position, Vector3.UP)
        base_pitch = camera.rotation.x
        camera.rotation.x = base_pitch + pitch * 0.35
        if plate != null:
            plate.visible = true


func toggle_view() -> void:
    first_person = not first_person
    _place_camera()


func _physics_process(delta: float) -> void:
    var wish := scripted if use_scripted else _read_wish()
    drive(wish, delta)


func drive(wish: Vector2, delta: float) -> void:
    var forward := Vector3(0, 0, -1)
    var right := Vector3(1, 0, 0)
    if camera != null:
        forward = -camera.global_transform.basis.z
        right = camera.global_transform.basis.x
    forward.y = 0.0
    right.y = 0.0
    if forward.length_squared() < 0.001:
        forward = Vector3(0, 0, -1)
    else:
        forward = forward.normalized()
    if right.length_squared() > 0.001:
        right = right.normalized()
    var direction := right * wish.x + forward * wish.y
    if direction.length_squared() > 0.001:
        direction = direction.normalized()
        velocity.x = direction.x * SPEED
        velocity.z = direction.z * SPEED
    else:
        velocity.x = move_toward(velocity.x, 0.0, SPEED)
        velocity.z = move_toward(velocity.z, 0.0, SPEED)
    if not is_on_floor():
        velocity.y -= GRAVITY * delta
    else:
        velocity.y = -0.4
    move_and_slide()


func _read_wish() -> Vector2:
    var wish := Vector2.ZERO
    if InputMap.has_action("move_left"):
        wish.x = Input.get_axis("move_left", "move_right")
        wish.y = Input.get_axis("move_back", "move_forward")
    if wish == Vector2.ZERO:
        wish.x = Input.get_axis("ui_left", "ui_right")
        wish.y = Input.get_axis("ui_down", "ui_up")
    return wish


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("view_toggle"):
        toggle_view()
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and camera_rig != null:
        camera_rig.rotate_y(-event.relative.x * 0.004)
        pitch = clampf(pitch - event.relative.y * 0.003, -0.4, 0.45)
        if camera != null:
            if first_person:
                camera.rotation.x = pitch
            else:
                camera.rotation.x = base_pitch + pitch * 0.35
        return
    if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
        Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _ensure_actions() -> void:
    _bind("move_forward", KEY_W)
    _bind("move_back", KEY_S)
    _bind("move_left", KEY_A)
    _bind("move_right", KEY_D)
    _bind("view_toggle", KEY_V)


func _bind(action: String, key: Key) -> void:
    if not InputMap.has_action(action):
        InputMap.add_action(action)
    var event := InputEventKey.new()
    event.physical_keycode = key
    if not InputMap.action_has_event(action, event):
        InputMap.action_add_event(action, event)


func _exit_tree() -> void:
    if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
        Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
