# PRIVATE BUILD — NOT FOR DISTRIBUTION
extends Control

const UI = preload("res://scripts/ui_kit.gd")
const JsonFile = preload("res://scripts/json_file.gd")

var screen: Node
var capture := ""
var settings_return := "title"


func _ready() -> void:
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_IGNORE
    capture = OS.get_environment("STILLWATER_CAPTURE")
    if CharacterDB.blocked():
        _swap(preload("res://scripts/error_screen.gd").new())
        return
    # Read the gate before any slot, save, or capture tour. The old boolean does not count.
    if not launch_gate_passed():
        _show_age()
        return
    if capture != "":
        _capture_tour()
        return
    _show_title()


func launch_gate_passed(path: String = "") -> bool:
    var file_path := Settings.path if path == "" else path
    return gate_version_accepted(JsonFile.read(file_path))


func gate_version_accepted(data) -> bool:
    if typeof(data) != TYPE_DICTIONARY:
        return false
    if not data.has(Settings.AGE_GATE_KEY):
        return false
    return Settings.whole_number(data[Settings.AGE_GATE_KEY]) == Settings.AGE_GATE_VERSION


func _swap(next: Node) -> void:
    if screen != null and is_instance_valid(screen):
        screen.queue_free()
    screen = next
    add_child(next)


func _show_age() -> void:
    var gate := preload("res://scripts/age_gate.gd").new()
    gate.confirmed.connect(func():
        Settings.confirm_age()
        _show_title()
    )
    gate.declined.connect(func(): get_tree().quit())
    _swap(gate)


func _show_title() -> void:
    var title := preload("res://scripts/title_screen.gd").new()
    title.has_continue = SaveGame.has_autosave()
    title.continue_pressed.connect(func():
        if SaveGame.load_autosave():
            _enter_progress()
    )
    title.new_pressed.connect(func(): _show_slots("new"))
    title.load_pressed.connect(func(): _show_slots("load"))
    title.settings_pressed.connect(func(): _open_settings("title"))
    title.quit_pressed.connect(func(): get_tree().quit())
    _swap(title)


func _show_slots(mode: String) -> void:
    var slots := preload("res://scripts/slot_screen.gd").new()
    slots.mode = mode
    slots.closed.connect(_show_title)
    slots.chosen.connect(func(slot):
        if mode == "new":
            SaveGame.start_new(slot)
            _show_map()
        elif SaveGame.load_slot(slot):
            _enter_progress()
    )
    _swap(slots)


func _open_settings(back_to: String) -> void:
    settings_return = back_to
    var panel := preload("res://scripts/settings_screen.gd").new()
    panel.closed.connect(_close_settings)
    _swap(panel)


func _close_settings() -> void:
    match settings_return:
        "beach":
            _show_beach()
        "map":
            _show_map()
        _:
            _show_title()


func _enter_progress() -> void:
    if str(SaveGame.progress.get("location", "map")) == "beach":
        _show_beach()
    else:
        _show_map()


func _show_map() -> void:
    var map := preload("res://scripts/map_screen.gd").new()
    map.travel.connect(_on_travel)
    map.open_settings.connect(func(): _open_settings("map"))
    map.leave.connect(_show_title)
    _swap(map)
    if not SaveGame.has_flag("intro_map"):
        SaveGame.add_flag("intro_map")
        SaveGame.autosave()
        map.show_notice("The beach is open. Everywhere else can wait.")


func _on_travel(id: String) -> void:
    var result := LocationDB.try_enter(id)
    if not result.get("ok", false):
        if screen != null and screen.has_method("show_notice"):
            screen.show_notice(str(result.get("message", "Coming soon.")))
        return
    SaveGame.progress.location = id
    SaveGame.autosave()
    if id == "beach":
        _show_beach()


func _show_beach() -> void:
    SaveGame.progress.location = "beach"
    SaveGame.autosave()
    var beach := preload("res://scenes/beach_3d.tscn").instantiate()
    beach.leave.connect(func():
        SaveGame.progress.location = "map"
        SaveGame.autosave()
        _show_map()
    )
    _swap(beach)


func _on_activity(kind: String) -> void:
    var time_of_day := str(SaveGame.progress.get("time_of_day", "morning"))
    var character_id := LocationDB.present("beach", time_of_day)
    var resolved := SceneCatalog.resolve("beach", character_id, time_of_day, kind, Settings.adult_content, SaveGame.affection(character_id))
    if not resolved.get("ok", false):
        resolved = {
            "ok": true,
            "id": "",
            "variant": "covered",
            "still": "res://assets/backgrounds/beach_%s.png" % time_of_day,
            "video": "",
            "caption": _fallback_line(kind),
        }
    var view := preload("res://scripts/scene_view.gd").new()
    view.resolved = resolved
    view.activity = kind
    view.closed.connect(func():
        if kind == "sun" or kind == "swim":
            SaveGame.apply_effect(character_id, {"affection": 1, "flag": "%s_%s" % [kind, character_id]})
        SaveGame.autosave()
        _show_beach()
    )
    _swap(view)


func _fallback_line(kind: String) -> String:
    match kind:
        "walk":
            return "You walk the shoreline. The sand is warm, and nothing asks you to hurry."
        "swim":
            return "You swim out until your feet leave the sand. The water holds you up."
        "sun":
            return "You lie in the sun and let the day go quiet."
        _:
            return "You stay with the moment a little longer."


func _on_talk() -> void:
    var character_id := LocationDB.present("beach", str(SaveGame.progress.get("time_of_day", "morning")))
    var convo := DialogueDB.best(character_id, SaveGame.affection(character_id))
    if convo.is_empty():
        return
    var talk := preload("res://scripts/dialogue_screen.gd").new()
    talk.conversation = convo
    talk.closed.connect(_show_beach)
    _swap(talk)


func _capture_tour() -> void:
    # Screenshot pacing only. This does not confirm the gate and does not write settings.
    Settings.adult_content = false
    Settings.text_speed = "fast"
    Settings.apply()
    _show_title()
    await _shot("01_title")
    SaveGame.start_new(1)
    _show_map()
    await _shot("02_map")
    _show_beach()
    await _shot("03_beach")
    _on_talk()
    await _shot("04_dialogue")
    _on_activity("swim")
    await _shot("05_scene")
    get_tree().quit(0)


func _shot(name: String) -> void:
    await get_tree().create_timer(0.45).timeout
    await RenderingServer.frame_post_draw
    var image := get_viewport().get_texture().get_image()
    var path := capture.rstrip("/") + "/" + name + ".png"
    var err := image.save_png(path)
    print("SHOT ", path, " ", image.get_width(), "x", image.get_height(), " err", err)
