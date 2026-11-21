extends Control

signal closed

const UI = preload("res://scripts/ui_kit.gd")
const Runner = preload("res://scripts/dialogue_runner.gd")

var conversation: Dictionary = {}
var runner = Runner.new()
var revealing := false
var full_text := ""
var shown := 0.0
var showing_reply := false

var body: Label
var choices_box: VBoxContainer
var continue_button: Button
var name_label: Label
var closeness: Label
var portrait: TextureRect
var free_box: VBoxContainer
var line_edit: LineEdit


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    var time_of_day := str(SaveGame.progress.get("time_of_day", "morning"))
    add_child(UI.backdrop("res://assets/backgrounds/beach_%s.png" % time_of_day))
    var dim := ColorRect.new()
    dim.color = UI.with_alpha(UI.DARK["bg"], 0.35)
    UI.fill(dim)
    dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(dim)

    var card := UI.panel(UI.with_alpha(UI.color("surface"), 0.97), 16)
    card.anchor_left = 0
    card.anchor_right = 1
    card.anchor_top = 0.38
    card.anchor_bottom = 1
    card.offset_left = 32
    card.offset_right = -32
    card.offset_top = 0
    card.offset_bottom = -24
    add_child(card)

    var row := UI.hbox(16)
    card.add_child(row)
    portrait = TextureRect.new()
    portrait.custom_minimum_size = Vector2(220, 300)
    portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    row.add_child(portrait)

    var column := UI.vbox(12)
    column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    row.add_child(column)
    name_label = UI.label("", 32, UI.color("text"))
    column.add_child(name_label)
    closeness = UI.label("", 14, UI.color("accent"))
    column.add_child(closeness)
    body = UI.label("", 20, UI.color("text"), true)
    body.custom_minimum_size = Vector2(0, 96)
    column.add_child(body)
    choices_box = UI.vbox(12)
    column.add_child(choices_box)
    free_box = UI.vbox(8)
    column.add_child(free_box)
    line_edit = UI.line_edit("Say something in your own words")
    line_edit.custom_minimum_size = Vector2(480, UI.MIN_CONTROL_HEIGHT)
    line_edit.text_submitted.connect(func(_text): _send())
    free_box.add_child(line_edit)
    var send := UI.button("Say it", 180, true)
    send.pressed.connect(_send)
    free_box.add_child(send)
    free_box.hide()
    continue_button = UI.button("Continue", 220, true)
    continue_button.pressed.connect(_on_continue)
    column.add_child(continue_button)

    _show_view(runner.start(conversation))


func _set_text(text: String) -> void:
    full_text = text
    if OS.get_environment("STILLWATER_CAPTURE") != "" or Settings.text_speed == "fast":
        body.text = full_text
        revealing = false
        return
    shown = 0
    revealing = true
    body.text = ""


func _finish_reveal() -> void:
    revealing = false
    body.text = full_text


func _process(delta: float) -> void:
    if not revealing:
        return
    shown += Settings.characters_per_second() * delta
    if int(shown) >= full_text.length():
        _finish_reveal()
    else:
        body.text = full_text.substr(0, int(shown))


func _show_view(view: Dictionary) -> void:
    var speaker := str(view.get("speaker", ""))
    var character: Dictionary = CharacterDB.characters.get(speaker, {})
    name_label.text = str(character.get("name", speaker))
    closeness.text = SaveGame.closeness_label(speaker)
    var path := CharacterDB.portrait(character, str(view.get("mood", "neutral")), Settings.adult_content)
    if path != "" and ResourceLoader.exists(path):
        portrait.texture = load(path)
    if not showing_reply:
        _set_text(str(view.get("text", "")))
    for child in choices_box.get_children():
        child.queue_free()
    continue_button.hide()
    free_box.hide()
    if view.get("ended", false):
        _finish_talk()
        return
    if view.get("awaiting_line", false):
        free_box.show()
        line_edit.grab_focus()
        return
    var choices: Array = view.get("choices", [])
    if choices.is_empty():
        continue_button.show()
        continue_button.text = "Close" if view.get("terminal", false) else "Continue"
        return
    for index in choices.size():
        var button := UI.button(str(choices[index].get("label", "")), 640, false)
        var picked: int = index
        button.pressed.connect(func(): _pick(picked))
        choices_box.add_child(button)


func _pick(index: int) -> void:
    _finish_reveal()
    showing_reply = false
    var view := runner.pick(index)
    if int(runner.last_effect.get("affection", 0)) != 0:
        SaveGame.apply_effect(str(conversation.get("character", "")), runner.last_effect)
        SaveGame.autosave()
    _show_view(view)


func _send() -> void:
    var line := line_edit.text.strip_edges()
    if line == "":
        return
    line_edit.text = ""
    var character: Dictionary = CharacterDB.characters.get(str(conversation.get("character", "")), {})
    ChatBrain.ask(character, [], line, func(text):
        showing_reply = true
        _set_text(str(text))
        free_box.hide()
        continue_button.show()
        continue_button.text = "Continue"
    )


func _on_continue() -> void:
    if revealing:
        _finish_reveal()
        return
    if showing_reply:
        showing_reply = false
        _show_view(runner.finish_free_talk())
        return
    var view := runner.continue_line()
    if view.get("ended", false):
        _finish_talk()
        return
    _show_view(view)


func _finish_talk() -> void:
    SaveGame.mark_seen(str(conversation.get("id", "")))
    SaveGame.autosave()
    closed.emit()


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        _finish_talk()
        get_viewport().set_input_as_handled()
        return
    if event.is_action_pressed("ui_accept") and continue_button.visible:
        _on_continue()
        get_viewport().set_input_as_handled()
