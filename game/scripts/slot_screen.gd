extends Control

signal chosen(slot: int)
signal closed

const UI = preload("res://scripts/ui_kit.gd")

var mode := "new"
var pending_slot := 0
var buttons := {}


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    add_child(UI.backdrop("res://assets/backgrounds/map.png"))
    var dim := ColorRect.new()
    dim.color = UI.with_alpha(UI.DARK["bg"], 0.45)
    UI.fill(dim)
    dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(dim)

    var card := UI.panel(UI.color("surface"), 16)
    UI.place(card, 0.5, 0.5, 390, 310)
    add_child(card)
    var box := UI.vbox(12)
    card.add_child(box)
    var title := "Choose a story to keep" if mode == "new" else "Choose a story to load"
    box.add_child(UI.label(title, 32, UI.color("text")))
    box.add_child(UI.label("Three slots. The game also writes an autosave whenever you move, talk, or the light changes.", 16, UI.color("text"), true))
    for slot_number in [1, 2, 3]:
        var slot := int(slot_number)
        var node := UI.button("", 680, false)
        buttons[slot] = node
        _label(node, slot)
        var picked: int = slot
        node.pressed.connect(func(): _press(picked))
        box.add_child(node)
    var back := UI.button("Back", 680, false)
    back.pressed.connect(func(): closed.emit())
    box.add_child(back)


func _label(node: Button, slot: int) -> void:
    var summary := SaveGame.summary(slot)
    var empty := summary == ""
    var text := "Slot %d" % slot
    if empty:
        text += "  ·  Empty"
    elif mode == "new" and pending_slot == slot:
        text += "  ·  Replace this story?"
    else:
        text += "  ·  " + summary
    node.text = text
    node.disabled = mode == "load" and empty


func _press(slot: int) -> void:
    var empty := SaveGame.summary(slot) == ""
    if mode == "load":
        if not empty:
            chosen.emit(slot)
        return
    if not empty and pending_slot != slot:
        pending_slot = slot
        for key in buttons.keys():
            _label(buttons[key], int(key))
        return
    chosen.emit(slot)


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        closed.emit()
        get_viewport().set_input_as_handled()
