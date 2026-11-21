extends Node

const PATH := "user://settings.json"
const AGE_GATE_KEY := "age_gate_version"
const AGE_GATE_VERSION := 21

var volume := 0.8
var fullscreen := false
var appearance := "match"
var text_speed := "normal"
# One content switch (PRD §7). This file is the only place the game maps old fields to it:
# adult_content <=> not sfw_mode, and without the 21+ gate sfw_mode is always true.
# app/content_mode.py does the same for the studio; both run game/tests/fixtures/content_mode_vectors.json.
var sfw_mode := true
var adult_content: bool:
    get:
        return not effective_sfw_mode()
    set(value):
        sfw_mode = not bool(value)
var age_confirmed := false
var age_gate_version := 0
var chat_mode := "canned"
var ollama_url := "http://127.0.0.1:11434"
var ollama_model := "llama3.2"
var rendering_method := ""
var path := PATH


func _ready() -> void:
    load_settings()
    apply()


func load_settings() -> void:
    var data = preload("res://scripts/json_file.gd").read(path)
    if typeof(data) != TYPE_DICTIONARY:
        return
    volume = clampf(float(data.get("volume", volume)), 0.0, 1.0)
    fullscreen = bool(data.get("fullscreen", false))
    var choice := str(data.get("appearance", "match"))
    appearance = choice if (choice == "light" or choice == "dark") else "match"
    text_speed = str(data.get("text_speed", "normal"))
    if text_speed != "slow" and text_speed != "fast":
        text_speed = "normal"
    age_confirmed = bool(data.get("age_confirmed", false))
    age_gate_version = whole_number(data.get(AGE_GATE_KEY, 0))
    sfw_mode = map_sfw_mode(data)
    chat_mode = "ollama" if str(data.get("chat_mode", "canned")) == "ollama" else "canned"
    ollama_url = str(data.get("ollama_url", ollama_url))
    ollama_model = str(data.get("ollama_model", ollama_model))
    var renderer := str(data.get("rendering_method", ""))
    rendering_method = renderer if (renderer == "forward_plus" or renderer == "gl_compatibility") else ""


func to_dict() -> Dictionary:
    return {
        "volume": volume,
        "fullscreen": fullscreen,
        "appearance": appearance,
        "text_speed": text_speed,
        "sfw_mode": effective_sfw_mode(),
        "adult_content": not effective_sfw_mode(),
        "age_confirmed": age_confirmed,
        "age_gate_version": age_gate_version,
        "chat_mode": chat_mode,
        "ollama_url": ollama_url,
        "ollama_model": ollama_model,
        "rendering_method": rendering_method,
    }


func save_settings() -> void:
    preload("res://scripts/json_file.gd").write(path, to_dict())


func confirm_age() -> void:
    # The 21+ attestation is stored: full 21+ mode from now on. SFW stays one switch away in Settings.
    age_gate_version = AGE_GATE_VERSION
    sfw_mode = false
    save_settings()


func gate_passed() -> bool:
    return age_gate_version == AGE_GATE_VERSION


func effective_sfw_mode() -> bool:
    return true if not gate_passed() else sfw_mode


func map_sfw_mode(data) -> bool:
    # No 21+ gate: always SFW. Gate stored: sfw_mode if it is true/false, else the old adult_content
    # flag inverted, else false (full 21+ after the attestation).
    if typeof(data) != TYPE_DICTIONARY:
        return true
    if whole_number(data.get(AGE_GATE_KEY, 0)) != AGE_GATE_VERSION:
        return true
    if typeof(data.get("sfw_mode")) == TYPE_BOOL:
        return data["sfw_mode"]
    if typeof(data.get("adult_content")) == TYPE_BOOL:
        return not data["adult_content"]
    return false


func whole_number(value) -> int:
    # Godot 4.3 reads every JSON number as a float. A float is accepted only
    # when it is already a whole number. Words, blanks, and fractions stay refused.
    if typeof(value) == TYPE_INT:
        return value
    if typeof(value) == TYPE_FLOAT and value == floor(value):
        return int(value)
    return 0


func apply() -> void:
    var bus := AudioServer.get_bus_index("Master")
    if volume <= 0.001:
        AudioServer.set_bus_mute(bus, true)
    else:
        AudioServer.set_bus_mute(bus, false)
        AudioServer.set_bus_volume_db(bus, linear_to_db(volume))
    if DisplayServer.get_name() == "headless":
        return
    if fullscreen:
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
    else:
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)


func characters_per_second() -> float:
    match text_speed:
        "slow":
            return 22.0
        "fast":
            return 140.0
        _:
            return 52.0
