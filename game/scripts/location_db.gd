extends Node

const JsonFile = preload("res://scripts/json_file.gd")

var locations: Array = []
var by_id := {}


func _ready() -> void:
    load_from("res://data/locations.json")


func load_from(path: String) -> void:
    locations = []
    by_id = {}
    var data = JsonFile.read(path)
    if typeof(data) != TYPE_DICTIONARY:
        return
    for loc in data.get("locations", []):
        if typeof(loc) != TYPE_DICTIONARY:
            continue
        locations.append(loc)
        by_id[str(loc.get("id", ""))] = loc


func get_location(id: String) -> Dictionary:
    var loc = by_id.get(id, {})
    return loc if typeof(loc) == TYPE_DICTIONARY else {}


func is_unlocked(id: String) -> bool:
    return bool(get_location(id).get("unlocked", false))


func status_text(loc: Dictionary) -> String:
    if bool(loc.get("unlocked", false)):
        return str(loc.get("blurb", ""))
    return "Coming soon"


func try_enter(id: String) -> Dictionary:
    var loc := get_location(id)
    if loc.is_empty():
        return {"ok": false, "message": "That place is coming soon."}
    if not bool(loc.get("unlocked", false)):
        return {"ok": false, "message": "%s is coming soon." % str(loc.get("name", "That place"))}
    return {"ok": true, "message": "", "location": loc}


func present(location_id: String, time_of_day: String) -> String:
    var table = get_location(location_id).get("present", {})
    if typeof(table) != TYPE_DICTIONARY:
        return ""
    return str(table.get(time_of_day, ""))
