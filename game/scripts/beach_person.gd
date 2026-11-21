extends Node3D

var person_id := ""
var stated_age = null
var plate: MeshInstance3D


func show_person(record: Dictionary) -> void:
    # The plate's origin is the feet. The name sits above the head.
    if not record.has("stated_age"):
        return
    person_id = str(record.get("id", ""))
    stated_age = record["stated_age"]
    if plate == null:
        plate = preload("res://scripts/beach_plate.gd").new()
        plate.name = "Plate"
        add_child(plate)
        var label := Label3D.new()
        label.name = "Name"
        label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
        label.double_sided = true
        label.font_size = 48
        label.pixel_size = 0.008
        label.outline_size = 6
        label.modulate = Color("FBF6EE")
        label.outline_modulate = Color("1B2A30")
        label.position = Vector3(0, 2.2, 0)
        label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
        add_child(label)
    var name_label := get_node("Name") as Label3D
    name_label.text = str(record.get("name", ""))
