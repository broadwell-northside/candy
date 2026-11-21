extends RefCounted

const JsonFile = preload("res://scripts/json_file.gd")
const PATH := "res://data/stage2_humanoid.json"

# Unused by the beach. A later rigged glTF humanoid, with blendshapes,
# IK, and a navmesh, can replace the Stage 1 plate. This does not build a body.


func load_spec() -> Dictionary:
    var data = JsonFile.read(PATH)
    if typeof(data) != TYPE_DICTIONARY:
        return {}
    return data
