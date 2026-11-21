extends Control

signal closed

const UI = preload("res://scripts/ui_kit.gd")

var settings_node: Node
var sfw_check: CheckButton
var page: ColorRect
var card: PanelContainer


func _using() -> Node:
    return settings_node if settings_node != null else Settings


func _ready() -> void:
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    page = ColorRect.new()
    UI.fill(page)
    add_child(page)

    var scroll := ScrollContainer.new()
    scroll.anchor_left = 0.5
    scroll.anchor_right = 0.5
    scroll.anchor_top = 0
    scroll.anchor_bottom = 1
    scroll.offset_left = -420
    scroll.offset_right = 420
    scroll.offset_top = 24
    scroll.offset_bottom = -24
    add_child(scroll)

    card = PanelContainer.new()
    card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    scroll.add_child(card)
    _fill()


func _fill() -> void:
    var settings := _using()
    UI.bind(str(settings.appearance))
    page.color = UI.color("bg")
    card.add_theme_stylebox_override("panel", UI.style(UI.color("surface"), 16, UI.color("line"), 24, 24, 1))
    for child in card.get_children():
        card.remove_child(child)
        child.free()

    var box := UI.vbox(32)
    card.add_child(box)
    box.add_child(UI.label("Settings", 32, UI.color("text")))

    var look := UI.vbox(8)
    box.add_child(look)
    look.add_child(UI.label("Appearance", 16, UI.color("text")))
    var appearance := UI.option_button()
    appearance.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    appearance.add_item("Match this computer", 0)
    appearance.add_item("Light", 1)
    appearance.add_item("Dark", 2)
    var appearance_index: int = int({"match": 0, "light": 1, "dark": 2}.get(str(settings.appearance), 0))
    appearance.select(appearance_index)
    appearance.item_selected.connect(func(index):
        settings.appearance = ["match", "light", "dark"][index]
        settings.save_settings()
        _fill.call_deferred()
    )
    look.add_child(appearance)

    var sound := UI.vbox(8)
    box.add_child(sound)
    sound.add_child(UI.label("Volume", 16, UI.color("text")))
    var volume := UI.slider()
    volume.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    volume.value = settings.volume * 100.0
    volume.value_changed.connect(func(value):
        settings.volume = float(value) / 100.0
        settings.apply()
        settings.save_settings()
    )
    sound.add_child(volume)

    var fullscreen := UI.check_button("Fullscreen")
    fullscreen.set_pressed_no_signal(settings.fullscreen)
    fullscreen.toggled.connect(func(on):
        settings.fullscreen = on
        settings.apply()
        settings.save_settings()
    )
    box.add_child(fullscreen)

    var reading := UI.vbox(8)
    box.add_child(reading)
    reading.add_child(UI.label("Text speed", 16, UI.color("text")))
    var speed := UI.option_button()
    speed.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    speed.add_item("Slow", 0)
    speed.add_item("Normal", 1)
    speed.add_item("Fast", 2)
    var speed_index: int = int({"slow": 0, "normal": 1, "fast": 2}.get(str(settings.text_speed), 1))
    speed.select(speed_index)
    speed.item_selected.connect(func(index):
        settings.text_speed = ["slow", "normal", "fast"][index]
        settings.save_settings()
    )
    reading.add_child(speed)

    var pictures := UI.vbox(8)
    box.add_child(pictures)
    sfw_check = UI.check_button("SFW mode")
    sfw_check.set_pressed_no_signal(settings.effective_sfw_mode())
    sfw_check.disabled = not settings.gate_passed()
    sfw_check.toggled.connect(func(on):
        settings.sfw_mode = on
        settings.save_settings()
    )
    pictures.add_child(sfw_check)
    pictures.add_child(UI.label("On keeps everyone covered: covered pictures only, and a calm hold card when a moment has no covered version yet. Off is full 21+ mode. Passing the 21+ gate turns it off; switch it back on any time. Everyone here is a fictional adult either way.", 14, UI.color("muted"), true))

    var helper := UI.vbox(8)
    box.add_child(helper)
    helper.add_child(UI.label("Conversation helper", 16, UI.color("text")))
    var chat := UI.option_button()
    chat.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    chat.add_item("Built-in lines (works offline)", 0)
    chat.add_item("Ollama on this computer", 1)
    chat.select(1 if settings.chat_mode == "ollama" else 0)
    chat.item_selected.connect(func(index):
        settings.chat_mode = "ollama" if index == 1 else "canned"
        settings.save_settings()
    )
    helper.add_child(chat)
    var url := UI.line_edit("http://127.0.0.1:11434")
    url.text = settings.ollama_url
    url.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    url.text_changed.connect(func(value):
        settings.ollama_url = value
        settings.save_settings()
    )
    helper.add_child(url)
    var model := UI.line_edit("model name, such as llama3.2")
    model.text = settings.ollama_model
    model.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    model.text_changed.connect(func(value):
        settings.ollama_model = value
        settings.save_settings()
    )
    helper.add_child(model)
    helper.add_child(UI.label("Leave the helper on built-in lines unless Ollama is already running. If it does not answer, the game uses its own lines.", 14, UI.color("muted"), true))

    var graphics := UI.vbox(8)
    box.add_child(graphics)
    graphics.add_child(UI.label("Graphics", 16, UI.color("text")))
    var renderer := UI.option_button()
    renderer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    renderer.add_item("GL Compatibility", 0)
    renderer.add_item("Forward+", 1)
    var renderer_choice := str(settings.rendering_method)
    if renderer_choice != "forward_plus" and renderer_choice != "gl_compatibility":
        renderer_choice = RendererBoot.current_method()
    renderer.select(1 if renderer_choice == "forward_plus" else 0)
    renderer.item_selected.connect(func(index):
        settings.rendering_method = "forward_plus" if index == 1 else "gl_compatibility"
        settings.save_settings()
        var boot := get_node_or_null("/root/RendererBoot")
        if boot != null and boot.has_method("apply_desktop_choice"):
            boot.apply_desktop_choice()
    )
    graphics.add_child(renderer)

    var back := UI.button("Back", 360, true)
    back.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    back.pressed.connect(func(): closed.emit())
    box.add_child(back)


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        closed.emit()
        get_viewport().set_input_as_handled()
