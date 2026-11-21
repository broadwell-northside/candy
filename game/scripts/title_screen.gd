extends Control

signal continue_pressed
signal new_pressed
signal load_pressed
signal settings_pressed
signal quit_pressed

const UI = preload("res://scripts/ui_kit.gd")

var has_continue := false


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    add_child(UI.backdrop("res://assets/backgrounds/title.png"))

    var card := UI.panel(UI.with_alpha(UI.color("surface"), 0.96), 16)
    card.anchor_left = 0
    card.anchor_right = 0
    card.anchor_top = 0
    card.anchor_bottom = 1
    card.offset_left = 48
    card.offset_top = 48
    card.offset_right = 540
    card.offset_bottom = -48
    add_child(card)

    var box := UI.vbox(12)
    card.add_child(box)
    box.add_child(UI.label("A PRIVATE ISLAND", 14, UI.color("accent")))
    box.add_child(UI.label("PRIVATE BUILD — NOT FOR DISTRIBUTION", 14, UI.color("accent")))
    box.add_child(UI.label("Stillwater", 32, UI.color("text")))
    box.add_child(UI.label("A quiet day of water, light, and conversation. One player. Nothing here is in a hurry.", 16, UI.color("text"), true))
    box.add_child(UI.gap(8))
    if has_continue:
        var carry := UI.button("Continue", 420, true)
        carry.pressed.connect(func(): continue_pressed.emit())
        box.add_child(carry)
        carry.grab_focus()
    var new_game := UI.button("New game", 420, not has_continue)
    new_game.pressed.connect(func(): new_pressed.emit())
    box.add_child(new_game)
    if not has_continue:
        new_game.grab_focus()
    var load_game := UI.button("Load", 420, false)
    load_game.pressed.connect(func(): load_pressed.emit())
    box.add_child(load_game)
    var settings := UI.button("Settings", 420, false)
    settings.pressed.connect(func(): settings_pressed.emit())
    box.add_child(settings)
    var quit := UI.button("Quit", 420, false)
    quit.pressed.connect(func(): quit_pressed.emit())
    box.add_child(quit)
    box.add_child(UI.gap(8))
    box.add_child(UI.label("Fictional adults, aged 21 and older. The game keeps an autosave for you.", 14, UI.color("muted"), true))
