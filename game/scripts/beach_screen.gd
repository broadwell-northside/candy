extends Control

signal leave
signal open_settings
signal activity(kind: String)
signal talk

const UI = preload("res://scripts/ui_kit.gd")

# The people already on the shore are this size. A solid imported picture uses
# the same box, so it stands with them instead of covering the beach.
const PERSON_W := 140.0
const PERSON_H := 240.0
const STANDEE_FEET := 0.78
const STANDEE_CENTER := 0.78

var bg: TextureRect
var time_label: Label
var name_label: Label
var close_label: Label
var portrait: TextureRect
var talk_button: Button
var notice: Label
var walker_root: Control
var present_id := ""


func _ready() -> void:
    UI.sync()
    UI.fill(self)
    mouse_filter = Control.MOUSE_FILTER_STOP
    bg = UI.backdrop("")
    add_child(bg)

    var shade := ColorRect.new()
    shade.color = UI.with_alpha(UI.DARK["bg"], 0.28)
    shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
    shade.anchor_left = 0
    shade.anchor_right = 1
    shade.anchor_top = 0.72
    shade.anchor_bottom = 1
    add_child(shade)

    walker_root = Control.new()
    UI.fill(walker_root)
    walker_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(walker_root)

    _chip("Swim", 0.18, 0.46, "swim")
    _chip("Walk the shoreline", 0.40, 0.69, "walk")
    _chip("Lie in the sun", 0.24, 0.8, "sun")

    portrait = TextureRect.new()
    _place_panel()
    portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(portrait)

    var card := UI.panel(UI.color("surface"), 16, 24)
    UI.place(card, 0.84, 0.86, 168, 100)
    add_child(card)
    var column := UI.vbox(8)
    card.add_child(column)
    name_label = UI.label("", 20, UI.color("text"))
    column.add_child(name_label)
    close_label = UI.label("", 14, UI.color("accent"))
    column.add_child(close_label)
    talk_button = UI.button("Talk", 240, true)
    talk_button.pressed.connect(func(): talk.emit())
    column.add_child(talk_button)

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
    header.offset_left = 24
    header.offset_right = -24
    header.offset_top = 16
    header.offset_bottom = 80
    add_child(header)
    var back := UI.button("Map", 120, false)
    back.pressed.connect(func(): leave.emit())
    header.add_child(back)
    var where := UI.label("Beach", 32, UI.color("text"))
    where.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    where.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    header.add_child(where)
    time_label = UI.label("", 16, UI.color("muted"))
    time_label.custom_minimum_size = Vector2(230, 0)
    time_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    header.add_child(time_label)
    var later := UI.button("Let a little time pass", 250, false)
    later.pressed.connect(_advance)
    header.add_child(later)
    var settings := UI.button("Settings", 140, false)
    settings.pressed.connect(func(): open_settings.emit())
    header.add_child(settings)

    var note := UI.panel(UI.with_alpha(UI.color("surface"), 0.94), 12, 12)
    note.anchor_left = 0
    note.anchor_top = 1
    note.anchor_right = 0
    note.anchor_bottom = 1
    note.offset_left = 24
    note.offset_top = -72
    note.offset_right = 560
    note.offset_bottom = -16
    note.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(note)
    notice = UI.label("Take your time. The light changes on its own.", 14, UI.color("muted"), true)
    note.add_child(notice)

    var timer := Timer.new()
    timer.wait_time = 70
    timer.timeout.connect(_advance)
    timer.autostart = true
    add_child(timer)
    refresh()
    _ambience()


func _chip(text: String, x: float, y: float, kind: String) -> void:
    var node := UI.button(text, 210, false)
    UI.place(node, x, y, 120, 26)
    node.pressed.connect(func(): activity.emit(kind))
    add_child(node)


func refresh() -> void:
    var time_of_day := str(SaveGame.progress.get("time_of_day", "morning"))
    var background := "res://assets/backgrounds/beach_%s.png" % time_of_day
    if ResourceLoader.exists(background):
        bg.texture = load(background)
    time_label.text = time_of_day.capitalize() + "  ·  Day " + str(int(SaveGame.progress.get("day", 1)))
    present_id = LocationDB.present("beach", time_of_day)
    var character: Dictionary = CharacterDB.characters.get(present_id, {})
    var full_name := str(character.get("name", "Someone"))
    name_label.text = full_name
    close_label.text = SaveGame.closeness_label(present_id)
    talk_button.text = "Talk to " + full_name.split(" ")[0]
    show_portrait(CharacterDB.portrait(character, "smile", Settings.adult_content))
    _walkers()


func _walkers() -> void:
    for child in walker_root.get_children():
        child.queue_free()
    var starts := [0.16, 0.58]
    var durations := [24.0, 32.0]
    var index := 0
    for id in CharacterDB.characters.keys():
        if str(id) == present_id:
            continue
        var character: Dictionary = CharacterDB.characters[id]
        var sprite := TextureRect.new()
        sprite.mouse_filter = Control.MOUSE_FILTER_IGNORE
        sprite.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
        sprite.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
        var image := "res://assets/characters/%s/walker.png" % str(id)
        if ResourceLoader.exists(image):
            sprite.texture = load(image)
        sprite.anchor_top = 0.58
        sprite.anchor_bottom = 0.58
        sprite.offset_top = -(PERSON_H - 40.0)
        sprite.offset_bottom = 40
        sprite.offset_left = -PERSON_W * 0.5
        sprite.offset_right = PERSON_W * 0.5
        walker_root.add_child(sprite)
        _walk(sprite, starts[index % starts.size()], durations[index % durations.size()])
        index += 1


func _walk(sprite: Control, start_x: float, duration: float) -> void:
    _set_x(sprite, start_x)
    var tween := sprite.create_tween().set_loops()
    tween.tween_method(func(x): _set_x(sprite, x), start_x, 1.2, duration * (1.2 - start_x) / 1.4)
    tween.tween_method(func(x): _set_x(sprite, x), -0.18, start_x, duration * (start_x + 0.18) / 1.4)


func _set_x(sprite: Control, x: float) -> void:
    sprite.anchor_left = x
    sprite.anchor_right = x


func show_portrait(path: String) -> void:
    if path == "" or not ResourceLoader.exists(path):
        show_portrait_texture(null)
        return
    show_portrait_texture(load(path))


func show_portrait_texture(texture: Texture2D) -> void:
    portrait.texture = texture
    # A cutout already has empty space around the figure, so the foreground
    # frame still shows the beach. A solid picture would fill that frame.
    if texture == null or _cutout(texture):
        _place_panel()
    else:
        _place_standee(texture.get_size())


func _place_panel() -> void:
    portrait.anchor_left = 1
    portrait.anchor_right = 1
    portrait.anchor_top = 0.18
    portrait.anchor_bottom = 0.78
    portrait.offset_left = -340
    portrait.offset_right = -24
    portrait.offset_top = 0
    portrait.offset_bottom = 0


func _place_standee(size: Vector2) -> void:
    var width := PERSON_W
    var height := PERSON_H
    if size.x > 1.0 and size.y > 1.0:
        var aspect := size.x / size.y
        if aspect > PERSON_W / PERSON_H:
            height = width / aspect
        else:
            width = height * aspect
    portrait.anchor_left = STANDEE_CENTER
    portrait.anchor_right = STANDEE_CENTER
    portrait.anchor_top = STANDEE_FEET
    portrait.anchor_bottom = STANDEE_FEET
    portrait.offset_left = -width * 0.5
    portrait.offset_right = width * 0.5
    portrait.offset_top = -height
    portrait.offset_bottom = 0


func _cutout(texture: Texture2D) -> bool:
    var image := texture.get_image()
    if image == null:
        return true
    if image.is_compressed():
        image = image.duplicate()
        if image.decompress() != OK:
            return true
    var w := image.get_width()
    var h := image.get_height()
    if w < 2 or h < 2:
        return true
    var clear := 0
    for point in [Vector2i(0, 0), Vector2i(w - 1, 0), Vector2i(0, h - 1), Vector2i(w - 1, h - 1)]:
        if image.get_pixel(point.x, point.y).a < 0.08:
            clear += 1
    return clear >= 3


func _advance() -> void:
    SaveGame.advance_time()
    SaveGame.autosave()
    refresh()
    notice.text = "The light has shifted. Saved."


func _ambience() -> void:
    if OS.get_environment("STILLWATER_CAPTURE") != "":
        return
    _loop("res://assets/audio/waves.wav", -6.0)
    _loop("res://assets/audio/wind.wav", -16.0)


func _loop(path: String, db: float) -> void:
    if not ResourceLoader.exists(path):
        return
    var stream = load(path)
    if stream == null:
        return
    stream = stream.duplicate()
    if stream is AudioStreamWAV:
        stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
    var player := AudioStreamPlayer.new()
    player.stream = stream
    player.volume_db = db
    add_child(player)
    player.play()


func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        leave.emit()
        get_viewport().set_input_as_handled()
