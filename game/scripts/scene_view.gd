extends Control

signal closed

const UI = preload("res://scripts/ui_kit.gd")

var resolved: Dictionary = {}
var activity := ""


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    var bg := ColorRect.new()
    bg.color = UI.color("bg")
    UI.fill(bg)
    add_child(bg)

    var still := TextureRect.new()
    still.anchor_left = 0.08
    still.anchor_right = 0.92
    still.anchor_top = 0.06
    still.anchor_bottom = 0.78
    still.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    still.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    still.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(still)

    var video := VideoStreamPlayer.new()
    video.anchor_left = 0.08
    video.anchor_right = 0.92
    video.anchor_top = 0.06
    video.anchor_bottom = 0.78
    video.expand = true
    video.visible = false
    add_child(video)

    var still_path := str(resolved.get("still", ""))
    var video_path := str(resolved.get("video", ""))
    if still_path != "" and ResourceLoader.exists(still_path):
        still.texture = load(still_path)
    var play_video := video_path != "" and ResourceLoader.exists(video_path) and OS.get_environment("STILLWATER_CAPTURE") == ""
    if play_video:
        var stream = load(video_path)
        if stream != null:
            video.stream = stream
            video.visible = true
            video.play()
            video.finished.connect(func():
                video.visible = false
            )

    var caption := str(resolved.get("caption", ""))
    if caption == "":
        caption = "You stay with the moment a little longer."
    var variant_name := str(resolved.get("variant", "covered"))
    var variant := "Covered version"
    if variant_name == "adult":
        variant = "Adult variant"
    elif variant_name == "hold":
        variant = "On hold · no covered version yet"
    var words := UI.vbox(4)
    words.anchor_left = 0.08
    words.anchor_right = 0.68
    words.anchor_top = 0.8
    words.anchor_bottom = 0.96
    words.mouse_filter = Control.MOUSE_FILTER_IGNORE
    words.add_child(UI.label(caption, 16, UI.color("text"), true))
    words.add_child(UI.label(variant, 14, UI.color("muted")))
    add_child(words)

    var back := UI.button("Back to the beach", 280, true)
    UI.place(back, 0.84, 0.9, 150, 28)
    back.pressed.connect(func(): closed.emit())
    add_child(back)
    back.grab_focus()


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel") or event.is_action_pressed("ui_accept"):
        closed.emit()
        get_viewport().set_input_as_handled()
