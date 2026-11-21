extends Node

const JsonFile = preload("res://scripts/json_file.gd")

var conversations: Array = []


func _ready() -> void:
    load_from("res://data/dialogues")


func load_from(dir: String) -> void:
    conversations = []
    if not DirAccess.dir_exists_absolute(dir):
        return
    var names := DirAccess.get_files_at(dir)
    names.sort()
    for name in names:
        if not str(name).ends_with(".json"):
            continue
        var data = JsonFile.read(dir.rstrip("/") + "/" + str(name))
        if typeof(data) != TYPE_DICTIONARY:
            continue
        for convo in data.get("conversations", []):
            if typeof(convo) == TYPE_DICTIONARY:
                conversations.append(convo)


func for_character(character_id: String) -> Array:
    var out: Array = []
    for convo in conversations:
        if str(convo.get("character", "")) == character_id:
            out.append(convo)
    return out


func available(character_id: String, affection: int) -> Array:
    var out: Array = []
    for convo in for_character(character_id):
        if int(convo.get("min_affection", 0)) <= affection:
            out.append(convo)
    return out


func best(character_id: String, affection: int) -> Dictionary:
    var options := available(character_id, affection)
    if options.is_empty():
        return {}
    options.sort_custom(func(a, b):
        var a_unseen := not SaveGame.seen(str(a.get("id", "")))
        var b_unseen := not SaveGame.seen(str(b.get("id", "")))
        if a_unseen != b_unseen:
            return a_unseen
        return int(a.get("min_affection", 0)) > int(b.get("min_affection", 0))
    )
    return options[0]
