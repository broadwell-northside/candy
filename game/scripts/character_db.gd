extends Node

const MIN_AGE := 21
const JsonFile = preload("res://scripts/json_file.gd")

var characters := {}
var errors: Array = []


func _ready() -> void:
    reload("res://data/characters")


func reload(dir: String) -> Array:
    characters = {}
    errors = []
    if not DirAccess.dir_exists_absolute(dir):
        errors.append("The characters folder is missing (%s)." % dir)
        return errors
    var names := DirAccess.get_files_at(dir)
    names.sort()
    var found := 0
    for name in names:
        if not str(name).ends_with(".json"):
            continue
        found += 1
        var path := dir.rstrip("/") + "/" + str(name)
        var data = JsonFile.read(path)
        if typeof(data) != TYPE_DICTIONARY:
            errors.append("Could not read %s. It is not valid JSON." % name)
            continue
        var problem := check_character(data, str(name))
        if problem != "":
            errors.append(problem)
            continue
        var id := str(data.get("id", str(name).get_basename()))
        characters[id] = data
    if found == 0:
        errors.append("No character files were found in %s." % dir)
    return errors


func check_character(data: Dictionary, filename: String) -> String:
    var who := str(data.get("name", filename))
    if who == "":
        who = filename
    if not data.has("stated_age") or data["stated_age"] == null:
        return _missing_age(who, filename)
    var age = data["stated_age"]
    if typeof(age) == TYPE_STRING and str(age).strip_edges() == "":
        return _missing_age(who, filename)
    if typeof(age) != TYPE_INT and typeof(age) != TYPE_FLOAT:
        return "%s (%s): stated_age must be a number. Every character must be a fictional adult aged %d or older." % [who, filename, MIN_AGE]
    if typeof(age) == TYPE_FLOAT and age != floor(age):
        return "%s (%s): stated_age is %s, which is not a whole number. Every character must be a fictional adult aged %d or older." % [who, filename, str(age), MIN_AGE]
    var whole := int(age)
    if whole < MIN_AGE:
        return "%s (%s): stated_age is %s, which is under %d. Every character must be a fictional adult aged %d or older." % [who, filename, str(whole), MIN_AGE, MIN_AGE]
    return ""


func accepted_age(age):
    if check_character({"name": "character", "stated_age": age}, "character.json") != "":
        return null
    return int(age)


func _missing_age(who: String, filename: String) -> String:
    return "%s (%s): stated_age is missing. Every character must be a fictional adult aged %d or older." % [who, filename, MIN_AGE]


func portrait(character: Dictionary, mood: String, adult: bool) -> String:
    var portraits = character.get("portraits", {})
    if typeof(portraits) != TYPE_DICTIONARY:
        return ""
    var moods = portraits.get(mood, portraits.get("neutral", {}))
    if typeof(moods) != TYPE_DICTIONARY:
        return ""
    if adult and str(moods.get("adult", "")) != "":
        return str(moods.get("adult"))
    return str(moods.get("covered", ""))


func blocked() -> bool:
    return not errors.is_empty()
