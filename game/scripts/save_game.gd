extends Node

const JsonFile = preload("res://scripts/json_file.gd")
const ORDER := ["morning", "midday", "sunset", "night"]

var root := "user://saves/"
var active_slot := 0
var progress := {}


func _init() -> void:
    progress = blank()


func _ready() -> void:
    root = "user://saves/"
    if progress.is_empty():
        progress = blank()


func blank() -> Dictionary:
    return {
        "version": 1,
        "slot": 0,
        "location": "map",
        "time_of_day": "morning",
        "day": 1,
        "affection": {},
        "flags": [],
        "seen": [],
    }


func slot_path(slot: int) -> String:
    return root.rstrip("/") + "/slot%d.json" % slot


func autosave_path() -> String:
    return root.rstrip("/") + "/autosave.json"


func slot_exists(slot: int) -> bool:
    return FileAccess.file_exists(slot_path(slot))


func has_autosave() -> bool:
    return FileAccess.file_exists(autosave_path())


func start_new(slot: int) -> void:
    active_slot = slot
    progress = blank()
    progress.slot = slot
    for id in CharacterDB.characters.keys():
        progress.affection[str(id)] = 0
    write_active()
    autosave()


func write_active() -> void:
    if active_slot >= 1 and active_slot <= 3:
        progress.slot = active_slot
        JsonFile.write(slot_path(active_slot), progress)


func autosave() -> void:
    if active_slot >= 1 and active_slot <= 3:
        write_active()
    JsonFile.write(autosave_path(), progress)


func read_slot(slot: int) -> Dictionary:
    if not slot_exists(slot):
        return {}
    return _normalise(JsonFile.read(slot_path(slot)))


func read_autosave() -> Dictionary:
    if not has_autosave():
        return {}
    return _normalise(JsonFile.read(autosave_path()))


func load_slot(slot: int) -> bool:
    if not slot_exists(slot):
        return false
    progress = read_slot(slot)
    active_slot = slot
    return true


func load_autosave() -> bool:
    if not has_autosave():
        return false
    progress = read_autosave()
    active_slot = int(progress.get("slot", 0))
    return true


func summary(slot: int) -> String:
    var data := read_slot(slot)
    if data.is_empty():
        return ""
    var place := "Beach" if str(data.get("location")) == "beach" else "Island map"
    var when := str(data.get("time_of_day", "morning")).capitalize()
    return "Day %d · %s · %s" % [int(data.get("day", 1)), place, when]


func affection(id: String) -> int:
    return int(progress.get("affection", {}).get(id, 0))


func closeness_label(id: String) -> String:
    var amount := affection(id)
    if amount <= 0:
        return "Just met"
    if amount == 1:
        return "Easy company"
    if amount == 2:
        return "Warm"
    return "Close"


func has_flag(flag: String) -> bool:
    return flag in progress.get("flags", [])


func add_flag(flag: String) -> void:
    if flag != "" and not has_flag(flag):
        progress.flags.append(flag)


func seen(id: String) -> bool:
    return id in progress.get("seen", [])


func mark_seen(id: String) -> void:
    if id != "" and not seen(id):
        progress.seen.append(id)


func apply_effect(character_id: String, effect: Dictionary) -> bool:
    var amount := int(effect.get("affection", 0))
    if amount == 0 or character_id == "":
        return false
    var flag := str(effect.get("flag", ""))
    if flag != "" and has_flag(flag):
        return false
    if flag != "":
        add_flag(flag)
    if typeof(progress.affection) != TYPE_DICTIONARY:
        progress.affection = {}
    progress.affection[character_id] = affection(character_id) + amount
    return true


func advance_time() -> void:
    var index := ORDER.find(str(progress.get("time_of_day", "morning")))
    if index < 0:
        index = 0
    index += 1
    if index >= ORDER.size():
        index = 0
        progress.day = int(progress.get("day", 1)) + 1
    progress.time_of_day = ORDER[index]


func _normalise(data) -> Dictionary:
    var out := blank()
    if typeof(data) != TYPE_DICTIONARY:
        return out
    out.slot = int(data.get("slot", 0))
    out.location = str(data.get("location", "map"))
    out.time_of_day = str(data.get("time_of_day", "morning"))
    out.day = int(data.get("day", 1))
    var affection_data = data.get("affection", {})
    if typeof(affection_data) == TYPE_DICTIONARY:
        for key in affection_data.keys():
            out.affection[str(key)] = int(affection_data[key])
    for key in ["flags", "seen"]:
        var items = data.get(key, [])
        if typeof(items) == TYPE_ARRAY:
            for item in items:
                out[key].append(str(item))
    return out
