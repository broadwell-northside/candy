extends RefCounted

const INK := Color("1B2A30")
const CREAM := Color("FBF6EE")
const SAND := Color("E7C99A")
const SEA := Color("0E3C48")
const CLAY := Color("C46B4A")
const DEEP := Color("08262E")

const MAIN_BUTTON_HEIGHT := 52.0
const MIN_CONTROL_HEIGHT := 44.0

const LIGHT := {
    "bg": Color("FBF6EE"),
    "surface": Color("FFFFFF"),
    "surface-2": Color("F3E6D4"),
    "text": Color("1B2A30"),
    "muted": Color("5C6B70"),
    "line": Color("E4D5C3"),
    "accent": Color("C46B4A"),
    "on-accent": Color("FBF6EE"),
    "ok": Color("2F6F5E"),
    "warn": Color("A15C2F"),
    "bad": Color("8C3A3A"),
}

const DARK := {
    "bg": Color("08262E"),
    "surface": Color("0E3C48"),
    "surface-2": Color("143F4A"),
    "text": Color("FBF6EE"),
    "muted": Color("C9D4D0"),
    "line": Color("1E5560"),
    "accent": Color("C46B4A"),
    "on-accent": Color("FBF6EE"),
    "ok": Color("8FCBB4"),
    "warn": Color("E0B089"),
    "bad": Color("F0B4B4"),
}

static var _mode := "match"


static func bind(mode: String) -> void:
    if mode == "light" or mode == "dark" or mode == "match":
        _mode = mode
    else:
        _mode = "match"


static func sync() -> void:
    var mode := "match"
    var loop = Engine.get_main_loop()
    if loop is SceneTree and loop.root != null:
        var settings = loop.root.get_node_or_null("Settings")
        if settings != null:
            mode = str(settings.appearance)
    bind(mode)


static func is_dark() -> bool:
    if _mode == "dark":
        return true
    if _mode == "light":
        return false
    return system_prefers_dark()


static func system_prefers_dark() -> bool:
    if DisplayServer.has_method("is_dark_mode_supported") and DisplayServer.has_method("is_dark_mode"):
        if DisplayServer.is_dark_mode_supported():
            return DisplayServer.is_dark_mode()
    return _desktop_file_prefers_dark()


static func _desktop_file_prefers_dark() -> bool:
    var gtk := OS.get_environment("GTK_THEME").to_lower()
    if gtk.ends_with(":dark") or gtk.contains("-dark"):
        return true
    var home := OS.get_environment("HOME")
    if home == "":
        return false
    for path in [home + "/.config/gtk-4.0/settings.ini", home + "/.config/gtk-3.0/settings.ini"]:
        if not FileAccess.file_exists(path):
            continue
        var text := FileAccess.get_file_as_string(path).to_lower()
        if text.contains("prefer-dark") or text.contains("gtk-application-prefer-dark-theme=1"):
            return true
        if text.contains("gtk-theme-name=") and text.contains("dark"):
            return true
    return false


static func color(token: String) -> Color:
    var swatch: Dictionary = DARK if is_dark() else LIGHT
    return swatch[token]


static func with_alpha(base: Color, alpha: float) -> Color:
    return Color(base.r, base.g, base.b, alpha)


static func fill(node: Control) -> void:
    node.set_anchors_preset(Control.PRESET_FULL_RECT)
    node.offset_left = 0
    node.offset_top = 0
    node.offset_right = 0
    node.offset_bottom = 0
    node.grow_horizontal = Control.GROW_DIRECTION_BOTH
    node.grow_vertical = Control.GROW_DIRECTION_BOTH


static func style(bg: Color, radius := 12, border := Color(0, 0, 0, 0), pad_x := 16, pad_y := 12, border_width := 2) -> StyleBoxFlat:
    var box := StyleBoxFlat.new()
    box.bg_color = bg
    box.corner_radius_top_left = radius
    box.corner_radius_top_right = radius
    box.corner_radius_bottom_left = radius
    box.corner_radius_bottom_right = radius
    box.content_margin_left = pad_x
    box.content_margin_right = pad_x
    box.content_margin_top = pad_y
    box.content_margin_bottom = pad_y
    if border.a > 0.0 and border_width > 0:
        box.border_color = border
        box.set_border_width_all(border_width)
    return box


static func button(text: String, wide := 320.0, primary := false) -> Button:
    var node := Button.new()
    node.text = text
    node.custom_minimum_size = Vector2(wide, MAIN_BUTTON_HEIGHT)
    node.add_theme_font_size_override("font_size", 20)
    node.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
    var fill := color("accent") if primary else color("surface-2")
    var ink := color("on-accent") if primary else color("text")
    var hover := fill.lightened(0.08) if primary else color("surface")
    var pressed := fill.darkened(0.08) if primary else color("line")
    var edge := Color(0, 0, 0, 0) if primary else color("line")
    var edge_width := 0 if primary else 1
    var focus_edge := color("on-accent") if primary else color("accent")
    for key in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
        node.add_theme_color_override(key, ink)
    node.add_theme_color_override("font_disabled_color", color("muted"))
    var normal := style(fill, 12, edge, 16, 0, edge_width)
    var hovered := style(hover, 12, edge, 16, 0, edge_width)
    var down := style(pressed, 12, edge, 16, 0, edge_width)
    var off := style(color("surface-2"), 12, color("line"), 16, 0, 1)
    var focused := style(fill, 12, focus_edge, 16, 0, 2)
    node.add_theme_stylebox_override("normal", normal)
    node.add_theme_stylebox_override("hover", hovered)
    node.add_theme_stylebox_override("pressed", down)
    node.add_theme_stylebox_override("hover_pressed", down)
    node.add_theme_stylebox_override("disabled", off)
    node.add_theme_stylebox_override("focus", focused)
    return node


static func label(text: String, size := 16, font_color := Color(0, 0, 0, 0), wrap := false) -> Label:
    var node := Label.new()
    node.text = text
    node.add_theme_font_size_override("font_size", size)
    var paint := font_color if font_color.a > 0.0 else color("text")
    node.add_theme_color_override("font_color", paint)
    node.add_theme_constant_override("line_spacing", int(round(float(size) * 0.5)))
    if wrap:
        node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    return node


static func line_edit(placeholder := "") -> LineEdit:
    var node := LineEdit.new()
    node.placeholder_text = placeholder
    node.custom_minimum_size = Vector2(360, MIN_CONTROL_HEIGHT)
    node.add_theme_font_size_override("font_size", 16)
    node.add_theme_color_override("font_color", color("text"))
    node.add_theme_color_override("font_placeholder_color", color("muted"))
    node.add_theme_color_override("font_selected_color", color("on-accent"))
    node.add_theme_color_override("caret_color", color("text"))
    node.add_theme_color_override("selection_color", with_alpha(color("accent"), 0.45))
    var normal := style(color("surface-2"), 12, color("line"), 12, 8, 1)
    var focus := style(color("surface-2"), 12, color("accent"), 12, 8, 2)
    node.add_theme_stylebox_override("normal", normal)
    node.add_theme_stylebox_override("focus", focus)
    node.add_theme_stylebox_override("read_only", normal)
    return node


static func option_button() -> OptionButton:
    var node := OptionButton.new()
    node.custom_minimum_size = Vector2(360, MIN_CONTROL_HEIGHT)
    node.add_theme_font_size_override("font_size", 16)
    var ink := color("text")
    for key in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
        node.add_theme_color_override(key, ink)
    node.add_theme_color_override("font_disabled_color", color("muted"))
    var fill := color("surface-2")
    var normal := style(fill, 12, color("line"), 12, 8, 1)
    var hovered := style(color("surface"), 12, color("line"), 12, 8, 1)
    var down := style(fill, 12, color("accent"), 12, 8, 2)
    var focused := style(fill, 12, color("accent"), 12, 8, 2)
    node.add_theme_stylebox_override("normal", normal)
    node.add_theme_stylebox_override("hover", hovered)
    node.add_theme_stylebox_override("pressed", down)
    node.add_theme_stylebox_override("hover_pressed", down)
    node.add_theme_stylebox_override("disabled", normal)
    node.add_theme_stylebox_override("focus", focused)
    var popup := node.get_popup()
    popup.add_theme_font_size_override("font_size", 16)
    popup.add_theme_color_override("font_color", ink)
    popup.add_theme_color_override("font_hover_color", color("on-accent"))
    popup.add_theme_color_override("font_disabled_color", color("muted"))
    popup.add_theme_stylebox_override("panel", style(color("surface"), 12, color("line"), 8, 8, 1))
    popup.add_theme_stylebox_override("hover", style(color("accent"), 8, Color(0, 0, 0, 0), 8, 4, 0))
    return node


static func check_button(text: String) -> CheckButton:
    var node := CheckButton.new()
    node.text = text
    node.custom_minimum_size = Vector2(0, MIN_CONTROL_HEIGHT)
    node.add_theme_font_size_override("font_size", 16)
    var ink := color("text")
    for key in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
        node.add_theme_color_override(key, ink)
    node.add_theme_color_override("font_disabled_color", color("muted"))
    return node


static func slider() -> HSlider:
    var node := HSlider.new()
    node.min_value = 0
    node.max_value = 100
    node.step = 1
    node.custom_minimum_size = Vector2(360, MIN_CONTROL_HEIGHT)
    node.add_theme_stylebox_override("slider", style(color("surface-2"), 8, Color(0, 0, 0, 0), 0, 0, 0))
    var filled := style(color("accent"), 8, Color(0, 0, 0, 0), 0, 0, 0)
    node.add_theme_stylebox_override("grabber_area", filled)
    node.add_theme_stylebox_override("grabber_area_highlight", filled)
    node.add_theme_icon_override("grabber", _dot(color("accent")))
    node.add_theme_icon_override("grabber_highlight", _dot(color("accent").lightened(0.12)))
    node.add_theme_icon_override("grabber_disabled", _dot(color("muted")))
    return node


static func _dot(fill: Color) -> Texture2D:
    var size := 18
    var image := Image.create(size, size, false, Image.FORMAT_RGBA8)
    image.fill(Color(0, 0, 0, 0))
    var center := Vector2(8.5, 8.5)
    for y in size:
        for x in size:
            if Vector2(x + 0.5, y + 0.5).distance_to(center) <= 8.0:
                image.set_pixel(x, y, fill)
    return ImageTexture.create_from_image(image)


static func vbox(separation := 12) -> VBoxContainer:
    var node := VBoxContainer.new()
    node.add_theme_constant_override("separation", separation)
    return node


static func hbox(separation := 12) -> HBoxContainer:
    var node := HBoxContainer.new()
    node.add_theme_constant_override("separation", separation)
    return node


static func gap(height: float) -> Control:
    var node := Control.new()
    node.custom_minimum_size = Vector2(0, height)
    node.mouse_filter = Control.MOUSE_FILTER_IGNORE
    return node


static func panel(bg: Color, radius := 16, pad := 24) -> PanelContainer:
    var node := PanelContainer.new()
    node.add_theme_stylebox_override("panel", style(bg, radius, color("line"), pad, pad, 1))
    return node


static func backdrop(path: String) -> TextureRect:
    var node := TextureRect.new()
    fill(node)
    node.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    node.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
    node.mouse_filter = Control.MOUSE_FILTER_IGNORE
    if path != "" and ResourceLoader.exists(path):
        node.texture = load(path)
    return node


static func place(node: Control, x: float, y: float, half_w: float, half_h: float) -> void:
    node.anchor_left = x
    node.anchor_right = x
    node.anchor_top = y
    node.anchor_bottom = y
    node.offset_left = -half_w
    node.offset_right = half_w
    node.offset_top = -half_h
    node.offset_bottom = half_h
