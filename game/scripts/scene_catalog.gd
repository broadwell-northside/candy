extends Node

const JsonFile = preload("res://scripts/json_file.gd")

const HOLD_CAPTION := "This moment has no covered version yet, so it waits while SFW mode is on."

var scenes: Array = []


func _ready() -> void:
    load_manifest("res://data/scenes.json")


func load_manifest(path: String) -> Array:
    scenes = []
    var data = JsonFile.read(path)
    if typeof(data) != TYPE_DICTIONARY:
        return scenes
    for scene in data.get("scenes", []):
        if typeof(scene) == TYPE_DICTIONARY:
            scenes.append(scene)
    return scenes


func resolve(location: String, character_id: String, time_of_day: String, activity: String, adult_on: bool, affection: int) -> Dictionary:
    var best := {}
    var best_variant := "covered"
    var best_score := -1
    var held := {}
    for scene in scenes:
        if str(scene.get("location", "")) != location:
            continue
        var scene_activity := str(scene.get("activity", "any"))
        if scene_activity != "any" and scene_activity != activity:
            continue
        var scene_character := str(scene.get("character", "any"))
        if scene_character != "any" and scene_character != character_id:
            continue
        var scene_time := str(scene.get("time", "any"))
        if scene_time != "any" and scene_time != time_of_day:
            continue
        if int(scene.get("min_affection", 0)) > affection:
            continue
        var variants = scene.get("variants", {})
        if typeof(variants) != TYPE_DICTIONARY:
            continue
        var variant_name := "covered"
        if adult_on and _has_media(variants.get("adult", {})):
            variant_name = "adult"
        elif not _has_media(variants.get("covered", {})):
            if not adult_on and _has_media(variants.get("adult", {})) and held.is_empty():
                held = scene
            continue
        var score := 0
        if scene_character == character_id and character_id != "":
            score += 4
        if scene_time == time_of_day:
            score += 2
        if scene_activity == activity:
            score += 1
        if score > best_score:
            best_score = score
            best = scene
            best_variant = variant_name
    if best.is_empty():
        if not held.is_empty():
            # SFW mode and only a full 21+ version exists: a calm hold card. Never the adult file,
            # never a silent re-render.
            return {"ok": true, "variant": "hold", "still": "", "video": "", "id": str(held.get("id", "")),
                "caption": HOLD_CAPTION}
        return {"ok": false, "variant": "covered", "still": "", "video": "", "caption": "", "id": ""}
    var chosen := best_variant
    var media = best.get("variants", {}).get(chosen, {})
    if typeof(media) != TYPE_DICTIONARY:
        media = {}
    return {
        "ok": true,
        "id": str(best.get("id", "")),
        "variant": chosen,
        "still": str(media.get("still", "")),
        "video": str(media.get("video", "")),
        "caption": str(best.get("caption", "")),
    }


func _has_media(media) -> bool:
    if typeof(media) != TYPE_DICTIONARY:
        return false
    return str(media.get("still", "")) != "" or str(media.get("video", "")) != ""
