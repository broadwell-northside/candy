extends Control

signal travel(id: String)
signal open_settings
signal leave

const UI = preload("res://scripts/ui_kit.gd")

var notice: Label


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    add_child(UI.backdrop("res://assets/backgrounds/map.png"))

    var bar := ColorRect.new()
    bar.color = UI.color("surface")
    bar.anchor_right = 1
    bar.offset_bottom = 96
    bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(bar)
    var rule := ColorRect.new()
    rule.color = UI.color("line")
    rule.anchor_right = 1
    rule.offset_top = 96
    rule.offset_bottom = 97
    rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(rule)

    var header := UI.hbox(12)
    header.anchor_left = 0
    header.anchor_right = 1
    header.anchor_top = 0
    header.anchor_bottom = 0
    header.offset_left = 24
    header.offset_right = -24
    header.offset_top = 16
    header.offset_bottom = 80
    add_child(header)
    var back := UI.button("Title", 140, false)
    back.pressed.connect(func(): leave.emit())
    header.add_child(back)
    var title := UI.label("The island", 32, UI.color("text"))
    title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    header.add_child(title)
    var day := UI.label("Day %d" % int(SaveGame.progress.get("day", 1)), 16, UI.color("muted"))
    day.custom_minimum_size = Vector2(90, 0)
    day.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    day.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    header.add_child(day)
    var settings := UI.button("Settings", 150, false)
    settings.pressed.connect(func(): open_settings.emit())
    header.add_child(settings)

    for loc in LocationDB.locations:
        _pin(loc)

    notice = UI.label("", 16, UI.color("text"), true)
    notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    var note_panel := UI.panel(UI.color("surface-2"), 12, 12)
    UI.place(note_panel, 0.5, 0.1, 280, 28)
    note_panel.add_child(notice)
    note_panel.visible = false
    note_panel.name = "Notice"
    note_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(note_panel)


func _pin(loc: Dictionary) -> void:
    var unlocked := bool(loc.get("unlocked", false))
    var pin := UI.panel(UI.color("surface") if unlocked else UI.color("surface-2"), 16, 12)
    var box := UI.vbox(0)
    pin.add_child(box)
    box.add_child(UI.label(str(loc.get("name", "")), 16, UI.color("text")))
    var status_color := UI.color("text") if unlocked else UI.color("accent")
    var status := UI.label(LocationDB.status_text(loc), 14, status_color, true)
    status.add_theme_constant_override("line_spacing", 2)
    status.custom_minimum_size = Vector2(180, 0)
    box.add_child(status)
    var map_pos = loc.get("map", {})
    var x := float(map_pos.get("x", 0.5)) if typeof(map_pos) == TYPE_DICTIONARY else 0.5
    var y := float(map_pos.get("y", 0.5)) if typeof(map_pos) == TYPE_DICTIONARY else 0.5
    UI.place(pin, x, y, 116, 40)
    pin.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
    pin.gui_input.connect(func(event):
        if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
            travel.emit(str(loc.get("id", "")))
    )
    add_child(pin)


func show_notice(text: String) -> void:
    notice.text = text
    var panel := notice.get_parent()
    panel.visible = true
    panel.modulate.a = 1.0
    var tween := create_tween()
    tween.tween_interval(3.2)
    tween.tween_property(panel, "modulate:a", 0.0, 0.8)


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        leave.emit()
        get_viewport().set_input_as_handled()
