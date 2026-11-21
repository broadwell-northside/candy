extends Control

const UI = preload("res://scripts/ui_kit.gd")


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    var bg := ColorRect.new()
    bg.color = UI.color("bg")
    UI.fill(bg)
    add_child(bg)
    var card := UI.panel(UI.color("surface"), 16)
    UI.place(card, 0.5, 0.5, 420, 260)
    add_child(card)
    var box := UI.vbox(12)
    card.add_child(box)
    box.add_child(UI.label("This character cannot be used", 32, UI.color("text")))
    box.add_child(UI.label("The game will not start until every character file gives an age of 21 or older. Fix the file, or take it out of game/data/characters.", 16, UI.color("text"), true))
    for problem in CharacterDB.errors:
        box.add_child(UI.label("• " + str(problem), 16, UI.color("bad"), true))
    var quit := UI.button("Quit", 640, true)
    quit.pressed.connect(func(): get_tree().quit())
    box.add_child(quit)
