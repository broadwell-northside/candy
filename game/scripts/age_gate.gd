extends Control

signal confirmed
signal declined

const UI = preload("res://scripts/ui_kit.gd")


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    var bg := ColorRect.new()
    bg.color = UI.color("bg")
    UI.fill(bg)
    add_child(bg)
    var wash := UI.backdrop("res://assets/backgrounds/beach_sunset.png")
    wash.modulate = UI.with_alpha(Color.WHITE, 0.45)
    add_child(wash)

    var card := UI.panel(UI.color("surface"), 22)
    UI.place(card, 0.5, 0.5, 360, 270)
    add_child(card)
    var box := UI.vbox(12)
    card.add_child(box)
    box.add_child(UI.label("STILLWATER", 14, UI.color("accent")))
    box.add_child(UI.label("Before you step onto the island", 32, UI.color("text")))
    box.add_child(UI.label("This is a private game for one adult player. Everyone you can meet is a fictional adult, written as 21 or older. There are no real people here.", 16, UI.color("text"), true))
    box.add_child(UI.label("Please confirm you are 21 or older.", 16, UI.color("text"), true))
    var yes := UI.button("I am 21 or older", 640, true)
    yes.pressed.connect(func(): confirmed.emit())
    box.add_child(yes)
    var no := UI.button("I am under 21", 640, false)
    no.pressed.connect(func(): declined.emit())
    box.add_child(no)
    yes.grab_focus()
