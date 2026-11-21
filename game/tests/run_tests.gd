extends Node

var failed := 0
const CharacterScript = preload("res://scripts/character_db.gd")
const LocationScript = preload("res://scripts/location_db.gd")
const DialogueScript = preload("res://scripts/dialogue_db.gd")
const RunnerScript = preload("res://scripts/dialogue_runner.gd")
const SceneScript = preload("res://scripts/scene_catalog.gd")
const SaveScript = preload("res://scripts/save_game.gd")
const SettingsScript = preload("res://scripts/settings.gd")
const ChatScript = preload("res://scripts/chat_brain.gd")
const SettingsScreen = preload("res://scripts/settings_screen.gd")


func _ready() -> void:
    print("Stillwater tests")
    _age()
    _manifest()
    _saves()
    _dialogue()
    _locations()
    _settings()
    _content_mode()
    _door_puzzle()
    _theme()
    _screens()
    _standee()
    _chat()
    _launch()
    await _beach_3d()
    print("----")
    if failed == 0:
        print("all tests passed")
    else:
        print("%d failed" % failed)
    get_tree().quit(failed)


func check(name: String, cond: bool, extra := "") -> void:
    if cond:
        print("PASS ", name)
    else:
        failed += 1
        print("FAIL ", name, " ", extra)


func _age() -> void:
    var db = CharacterScript.new()
    var errors: Array = db.reload("res://data/characters")
    check("shipping characters load", errors.is_empty(), str(errors))
    check("mira, leo and nia are present", db.characters.has("mira") and db.characters.has("leo") and db.characters.has("nia"))
    for id in db.characters.keys():
        check("stated age is at least 21 for " + str(id), float(db.characters[id].get("stated_age", 0)) >= 21.0)

    db = CharacterScript.new()
    errors = db.reload("res://tests/fixtures/underage")
    check("under 21 is refused", errors.size() == 1 and not db.characters.has("bad_young"), str(errors))
    check("underage error names the character and the rule", errors.size() == 1 and str(errors[0]).find("Rejected Example") >= 0 and str(errors[0]).find("21") >= 0, str(errors))

    db = CharacterScript.new()
    errors = db.reload("res://tests/fixtures/missing")
    check("missing age is refused", errors.size() == 1 and not db.characters.has("bad_missing"), str(errors))
    check("missing age error is explicit", errors.size() == 1 and str(errors[0]).find("missing") >= 0 and str(errors[0]).find("No Age") >= 0, str(errors))

    db = CharacterScript.new()
    errors = db.reload("res://tests/fixtures/text_age")
    check("an age that is not a number is refused", errors.size() == 1 and not db.characters.has("bad_text"), str(errors))

    db = CharacterScript.new()
    errors = db.reload("res://tests/fixtures/adult")
    check("stated age 21 is accepted", errors.is_empty() and db.characters.has("ok_adult"), str(errors))

    db = CharacterScript.new()
    errors = db.reload("res://tests/fixtures/mixed")
    check("a mixed folder keeps the adult and drops the underage file", errors.size() == 1 and db.characters.has("ok_adult") and not db.characters.has("bad_young"), str(errors))

    db = CharacterScript.new()
    errors = db.reload("res://tests/fixtures/gate_ages")
    check("ages 21 and 32 load from a mixed age folder", db.characters.has("age_21") and db.characters.has("age_32"), str(db.characters.keys()))
    check("ages 18, 19 and 20 are refused", not db.characters.has("age_18") and not db.characters.has("age_19") and not db.characters.has("age_20"), str(errors))
    check("a fraction, a blank and the word 21 are refused", not db.characters.has("age_fraction") and not db.characters.has("age_blank") and not db.characters.has("age_word"), str(errors))
    var joined := ""
    for problem in errors:
        joined += str(problem) + "\n"
    check("age 18 is refused as 18", joined.find("is 18") >= 0, joined)
    check("age 21.5 is refused as a fraction", joined.find("21.5") >= 0 and joined.find("whole") >= 0, joined)

    var edge = CharacterScript.new()
    for young in [18, 19, 20]:
        var msg := edge.check_character({"name": "Edge", "stated_age": young}, "edge.json")
        check("character age %s is refused and not clamped" % str(young), msg.find("is %s" % str(young)) >= 0 and msg.find("under") >= 0, msg)
    var fraction := edge.check_character({"name": "Edge", "stated_age": 21.5}, "edge.json")
    check("character age 21.5 is refused and not clamped", fraction.find("21.5") >= 0 and fraction.find("whole") >= 0 and fraction.find("is 21,") < 0, fraction)
    var blank := edge.check_character({"name": "Edge", "stated_age": ""}, "edge.json")
    check("a blank character age is refused", blank.find("missing") >= 0, blank)
    var word := edge.check_character({"name": "Edge", "stated_age": "21"}, "edge.json")
    check("the word 21 is refused for a character", word != "" and word.find("must be a number") >= 0, word)
    check("character age 21 is accepted", edge.check_character({"name": "Edge", "stated_age": 21}, "edge.json") == "")
    check("character age 32 is accepted", edge.check_character({"name": "Edge", "stated_age": 32}, "edge.json") == "")
    check("a yes/no character age is refused", edge.check_character({"name": "Edge", "stated_age": true}, "edge.json") != "")

    var sample := {"portraits": {"neutral": {"covered": "res://covered.png", "adult": "res://adult.png"}}}
    check("covered portrait is used when adult pictures are off", db.portrait(sample, "neutral", false) == "res://covered.png")
    check("adult portrait is used only when adult pictures are on", db.portrait(sample, "neutral", true) == "res://adult.png")


func _manifest() -> void:
    var catalog = SceneScript.new()
    var scenes: Array = catalog.load_manifest("res://data/scenes.json")
    check("scene manifest loads", scenes.size() >= 4, str(scenes.size()))
    var ids := {}
    var unique := true
    for scene in scenes:
        var id := str(scene.get("id", ""))
        if ids.has(id):
            unique = false
        ids[id] = true
    check("scene ids are unique", unique)

    var covered = catalog.resolve("beach", "mira", "morning", "swim", false, 0)
    check("swim uses the covered variant when adult pictures are off", covered.get("ok", false) and covered.get("variant") == "covered" and str(covered.get("id")) == "beach_swim", str(covered))
    check("covered swim points at a video clip", str(covered.get("video")).ends_with(".ogv"))

    var adult = catalog.resolve("beach", "mira", "morning", "swim", true, 0)
    check("swim uses the adult variant when adult pictures are on", adult.get("variant") == "adult" and str(adult.get("still")).ends_with("swim_adult.png"), str(adult))
    check("an empty video falls back to the still path", str(adult.get("video")) == "" and str(adult.get("still")) != "")

    var early = catalog.resolve("beach", "mira", "morning", "sun", false, 0)
    check("low closeness uses the general sun scene", str(early.get("id")) == "beach_sun", str(early))
    var close = catalog.resolve("beach", "mira", "night", "sun", false, 2)
    check("closeness unlocks Mira's sun scene", str(close.get("id")) == "beach_sun_mira", str(close))
    var leo = catalog.resolve("beach", "leo", "sunset", "sun", false, 4)
    check("Leo does not get Mira's scene", str(leo.get("id")) == "beach_sun", str(leo))

    var trap = SceneScript.new()
    trap.load_manifest("res://tests/fixtures/scenes_adult_only.json")
    var safe = trap.resolve("beach", "mira", "morning", "swim", false, 0)
    check("an adult-only scene is not chosen while adult pictures are off", str(safe.get("id")) == "covered_swim" and safe.get("variant") == "covered", str(safe))


func _saves() -> void:
    var root := "user://stillwater_tests/"
    _wipe(root)
    var save = SaveScript.new()
    save.root = root
    save.start_new(1)
    save.progress.affection["mira"] = 2
    save.progress.time_of_day = "sunset"
    save.progress.day = 3
    save.progress.location = "beach"
    save.progress.flags = ["sun_mira"]
    save.write_active()
    save.autosave()

    var again = SaveScript.new()
    again.root = root
    var loaded: Dictionary = again.read_slot(1)
    check("slot 1 round trip keeps the day", int(loaded.get("day", 0)) == 3, str(loaded))
    check("slot 1 round trip keeps the time of day", str(loaded.get("time_of_day")) == "sunset", str(loaded))
    check("slot 1 round trip keeps affection", int(loaded.get("affection", {}).get("mira", 0)) == 2, str(loaded))
    check("slot 1 round trip keeps the place", str(loaded.get("location")) == "beach")
    check("slot 2 stays empty", not again.slot_exists(2))

    var restored = SaveScript.new()
    restored.root = root
    check("autosave loads", restored.load_autosave())
    check("autosave restores the beach", str(restored.progress.get("location")) == "beach", str(restored.progress))
    check("autosave restores affection", int(restored.progress.get("affection", {}).get("mira", 0)) == 2)
    check("autosave remembers the slot", restored.active_slot == 1)

    save.start_new(2)
    save.progress.affection["leo"] = 1
    save.write_active()
    check("slot 2 does not erase slot 1", int(again.read_slot(1).get("affection", {}).get("mira", 0)) == 2)
    check("slot 2 keeps its own affection", int(save.read_slot(2).get("affection", {}).get("leo", 0)) == 1)

    var effects = SaveScript.new()
    effects.root = root
    effects.start_new(3)
    var first := effects.apply_effect("nia", {"affection": 1, "flag": "swim_nia"})
    var second := effects.apply_effect("nia", {"affection": 1, "flag": "swim_nia"})
    check("affection is granted once for the same flag", first and not second and effects.affection("nia") == 1)
    effects.progress.time_of_day = "night"
    effects.progress.day = 2
    effects.advance_time()
    check("night rolls into the next morning", str(effects.progress.time_of_day) == "morning" and int(effects.progress.day) == 3)
    _wipe(root)


func _dialogue() -> void:
    var db = DialogueScript.new()
    db.load_from("res://data/dialogues")
    var shore := _find(db, "mira_shore")
    var sunspot := _find(db, "mira_sunspot")
    check("Mira has a starting conversation and a locked one", not shore.is_empty() and int(sunspot.get("min_affection", 0)) == 2)
    var open: Array = db.available("mira", 0)
    var warm: Array = db.available("mira", 2)
    check("closeness 0 hides the later conversation", open.size() == 1 and str(open[0].get("id")) == "mira_shore", str(open.size()))
    check("closeness 2 unlocks the later conversation", warm.size() == 2)

    var runner = RunnerScript.new()
    var view: Dictionary = runner.start(shore)
    check("the talk starts with more than one choice", view.get("choices", []).size() >= 2, str(view))
    runner.pick(0)
    check("the first choice branches to welcome", runner.node_id == "welcome" and int(runner.last_effect.get("affection", 0)) == 1)
    runner.continue_line()
    check("the welcome line can end the talk", runner.ended)

    runner = RunnerScript.new()
    runner.start(shore)
    runner.pick(1)
    check("the second choice branches somewhere else", runner.node_id == "quiet" and int(runner.last_effect.get("affection", 0)) == 0)

    runner = RunnerScript.new()
    runner.start(shore)
    var free: Dictionary = runner.pick(2)
    check("free talk waits for the player's own line", free.get("awaiting_line", false) and runner.node_id == "start")

    for convo in db.conversations:
        var who := str(convo.get("character", ""))
        check("dialogue only talks to a known character", CharacterDB.characters.has(who), who)


func _locations() -> void:
    var db = LocationScript.new()
    db.load_from("res://data/locations.json")
    check("the beach is unlocked", db.is_unlocked("beach") and db.try_enter("beach").get("ok", false))
    for id in ["lagoon", "cliffs", "village", "hut"]:
        var loc := db.get_location(id)
        check(id + " is locked", not db.is_unlocked(id) and not db.try_enter(id).get("ok", false))
        check(id + " says coming soon", db.status_text(loc) == "Coming soon" and str(db.try_enter(id).get("message", "")).to_lower().find("coming soon") >= 0)


func _settings() -> void:
    var fresh = SettingsScript.new()
    check("adult pictures default to off", fresh.adult_content == false)
    check("a fresh profile has not passed the age gate", fresh.age_confirmed == false and fresh.age_gate_version != 21)
    check("fullscreen defaults to off", fresh.fullscreen == false)
    check("appearance defaults to match this computer", fresh.appearance == "match")
    check("a fresh profile is in SFW mode", fresh.effective_sfw_mode() == true and fresh.sfw_mode == true)
    fresh.path = "user://stillwater_tests/settings.json"
    fresh.adult_content = true
    check("without the 21 gate the adult switch cannot turn SFW off", fresh.adult_content == false and fresh.effective_sfw_mode())
    var gated = SettingsScript.new()
    gated.path = "user://stillwater_tests/gated.json"
    gated.confirm_age()
    check("passing the 21 gate turns SFW mode off", gated.effective_sfw_mode() == false and gated.adult_content == true)
    var gated_file = preload("res://scripts/json_file.gd").read(gated.path)
    check("the settings file stores sfw_mode and the old field derived from it", typeof(gated_file) == TYPE_DICTIONARY and gated_file.get("sfw_mode") == false and gated_file.get("adult_content") == true, str(gated_file))
    var gated_again = SettingsScript.new()
    gated_again.path = gated.path
    gated_again.load_settings()
    check("SFW off survives a restart after the gate", gated_again.effective_sfw_mode() == false)
    gated_again.sfw_mode = true
    check("the SFW switch is one step away after the gate", gated_again.effective_sfw_mode() and gated_again.adult_content == false)
    gated.free()
    gated_again.free()
    fresh.volume = 0.25
    fresh.text_speed = "slow"
    fresh.save_settings()
    var loaded = SettingsScript.new()
    loaded.path = fresh.path
    loaded.load_settings()
    check("settings round trip keeps SFW on, volume and text speed", loaded.effective_sfw_mode() and abs(loaded.volume - 0.25) < 0.001 and loaded.text_speed == "slow")
    check("a saved profile keeps match until the player changes it", loaded.appearance == "match")
    fresh.appearance = "dark"
    fresh.age_confirmed = true
    fresh.save_settings()
    var themed = SettingsScript.new()
    themed.path = fresh.path
    themed.load_settings()
    check("settings round trip keeps appearance and the age flag", themed.appearance == "dark" and themed.age_confirmed)
    check("the old age flag does not become the 21 gate", themed.age_gate_version != 21)
    var JsonFile = preload("res://scripts/json_file.gd")
    JsonFile.write(fresh.path, {"volume": 0.4, "adult_content": true, "age_confirmed": false})
    var legacy = SettingsScript.new()
    legacy.path = fresh.path
    legacy.load_settings()
    check("a settings file without appearance still matches this computer", legacy.appearance == "match" and legacy.age_confirmed == false)
    check("an old adult switch without the 21 gate stays in SFW mode", legacy.adult_content == false and legacy.effective_sfw_mode())
    JsonFile.write(fresh.path, {"appearance": "sepia", "volume": 0.4})
    var unknown = SettingsScript.new()
    unknown.path = fresh.path
    unknown.load_settings()
    check("an unknown appearance falls back to match", unknown.appearance == "match" and abs(unknown.volume - 0.4) < 0.001)

    var screen = SettingsScreen.new()
    screen.settings_node = SettingsScript.new()
    add_child(screen)
    check("the settings screen shows SFW mode on for a fresh profile", screen.sfw_check != null and screen.sfw_check.button_pressed == true)
    screen.queue_free()
    _wipe("user://stillwater_tests/")


func _content_mode() -> void:
    # The same cases app/content_mode.py runs, so the studio and the game cannot drift.
    var vectors = preload("res://scripts/json_file.gd").read("res://tests/fixtures/content_mode_vectors.json")
    check("the shared sfw_mode cases load", typeof(vectors) == TYPE_DICTIONARY and vectors.get("game_settings", []).size() >= 10)
    var probe = SettingsScript.new()
    for row in vectors.get("game_settings", []):
        check("sfw_mode case: " + str(row.get("name")), probe.map_sfw_mode(row.get("file")) == bool(row.get("sfw_mode")), str(row))
    probe.free()
    var hold = SceneScript.new()
    hold.load_manifest("res://tests/fixtures/scenes_hold.json")
    var held = hold.resolve("beach", "mira", "morning", "sun", false, 0)
    check("SFW mode shows a hold card when only a 21+ version exists", held.get("ok", false) and held.get("variant") == "hold" and str(held.get("still")) == "" and str(held.get("video")) == "", str(held))
    check("the hold card says it is waiting, in plain words", str(held.get("caption")).find("no covered version yet") >= 0)
    var open = hold.resolve("beach", "mira", "morning", "sun", true, 0)
    check("full 21+ mode uses that version", open.get("variant") == "adult" and str(open.get("still")).ends_with("sun_adult.png"), str(open))
    hold.free()


func _put(path: String, text: String) -> void:
    DirAccess.make_dir_recursive_absolute(path.get_base_dir())
    var f := FileAccess.open(path, FileAccess.WRITE)
    f.store_string(text)
    f.close()


func _door_puzzle() -> void:
    var Puzzle = preload("res://scripts/door_puzzle.gd")
    var root := "user://stillwater_tests/puzzle/"
    _wipe(root)
    var p = Puzzle.new()
    check("the door puzzle loads and its sha256 matches", p.load_level(Puzzle.LEVEL_PATH, root + "no_draft.json"), p.error)
    check("the puzzle file keeps the private-build notice", str(p.level.get("notice")) == "PRIVATE BUILD — NOT FOR DISTRIBUTION")
    var all_reachable := true
    for row in p.level.get("nodes", []):
        all_reachable = all_reachable and Puzzle.reachable(row, true)
    check("every puzzle node is reachable in SFW mode", all_reachable)
    check("a node that needs full 21+ mode is unreachable in SFW mode", not Puzzle.reachable({"sfw_safe": true, "requires_full_21_mode": true}, true) and Puzzle.reachable({"sfw_safe": true, "requires_full_21_mode": true}, false))
    check("a node missing a flag is never reachable", not Puzzle.reachable({"sfw_safe": true}, false) and not Puzzle.reachable({"requires_full_21_mode": false}, true))
    var raw := FileAccess.get_file_as_string(Puzzle.LEVEL_PATH)
    _put(root + "tampered.json", raw.replace("Brass key", "Iron key"))
    _put(root + "tampered.json.sha256", FileAccess.get_file_as_string(Puzzle.LEVEL_PATH + ".sha256"))
    var bad = Puzzle.new()
    check("a puzzle file that does not match its sha256 is refused", not bad.load_level(root + "tampered.json", "") and bad.error.find("sha256") >= 0, bad.error)
    _put(root + "no_hash.json", raw)
    check("a puzzle file without its sha256 is refused", not Puzzle.new().load_level(root + "no_hash.json", ""))
    check("pads_needed is read as a whole number", p.pads_needed() == 2)

    var near: String = p.rule("near_pad")
    var far: String = p.rule("far_pad")
    var mira: String = p.companion()
    check("the companion is a fictional actor from the character files", mira == "mira")
    check("the first hint is the key", p.next_hint() == p.hint("key"), p.next_hint())
    p.step_on("player", near)
    check("one pad alone does not open the door", not p.door_open and not p.pads_held())
    p.step_on("player", far)
    check("one person cannot hold both pads", p.on_pad.size() == 1 and not p.pads_held())
    p.reset()
    check("she cannot take a key you do not hold", p.companion_action("take_key").find("not holding") >= 0)
    check("you can pick up the key", p.pick_up_key("player") and p.next_hint() == p.hint("give"))
    p.step_on("player", near)
    p.companion_action("stand_on_far_pad")
    check("both pads held without the key keeps the door shut", p.pads_held() and not p.door_open)
    p.companion_action("take_key")
    check("she steps off her pad to set the key", p.key_set and not p.actor_pad.has(mira) and not p.door_open)
    p.companion_action("stand_on_far_pad")
    check("key set and both pads held: the door opens", p.door_open and p.next_hint() == p.hint("open"))
    p.step_off("player")
    check("stepping off a pad closes it again", not p.door_open)
    p.reset()
    p.pick_up_key("player")
    p.companion_action("take_key")
    p.step_on("player", near)
    p.companion_action("stand_on_far_pad")
    check("the other order opens it too", p.door_open)

    check("a click on her hand is Take the key", p.hitbox_at(0.7, 0.5) == "take_key")
    check("a click on her body is Stand on the far pad", p.hitbox_at(0.3, 0.8) == "stand_on_far_pad")
    check("a click beside her does nothing", p.hitbox_at(0.02, 0.02) == "")
    var sock: Vector3 = p.socket_local("hand_r")
    check("the hand socket {u, v, depth} maps onto the plate", abs(sock.x - 0.144) < 0.01 and abs(sock.y - 0.9) < 0.01 and abs(sock.z - 0.06) < 0.001, str(sock))

    var key_id: String = p.rule("key")
    var before: Vector3 = p.position_of(key_id)
    p.edit_move(key_id, 1.0, -1.0)
    check("Edit this place moves the key", abs(p.position_of(key_id).x - (before.x + 1.0)) < 0.001 and abs(p.position_of(key_id).z - (before.z - 1.0)) < 0.001)
    p.edit_move(key_id, -100.0, 0.0)
    check("a move stays on the sand", abs(p.position_of(key_id).x - p.bounds().position.x) < 0.001)
    check("the plate's actor and the actions cannot be moved as level pieces", not p.edit_move("take_key", 1.0, 0.0))
    var rows: Array = p.draft_dict().get("nodes", [])
    var only_positions := rows.size() == 4
    for row in rows:
        only_positions = only_positions and row.keys().size() == 2 and row.has("id") and row.has("position")
    check("a draft holds positions only", only_positions, str(rows))
    check("a draft saves with its sha256", p.save_draft(root + "draft.json") and Puzzle.hash_ok(root + "draft.json"))
    var again = Puzzle.new()
    again.load_level(Puzzle.LEVEL_PATH, root + "draft.json")
    check("the saved draft is used next time", again.source == "draft" and abs(again.position_of(key_id).x - again.bounds().position.x) < 0.001)
    _put(root + "draft.json", FileAccess.get_file_as_string(root + "draft.json").replace("pad_far", "pad_fa"))
    var fallback = Puzzle.new()
    fallback.load_level(Puzzle.LEVEL_PATH, root + "draft.json")
    check("a draft that does not match its sha256 is not used", fallback.source == "level" and fallback.draft_note.find("sha256") >= 0, fallback.draft_note)
    var sneaky := JSON.stringify({"nodes": [{"id": "door", "position": {"x": 2.0, "y": 0.5, "z": 19.0}, "requires_full_21_mode": true, "sfw_safe": false}],
        "actors": [{"id": "mira", "consent": "none"}]})
    _put(root + "sneaky.json", sneaky)
    _put(root + "sneaky.json.sha256", sneaky.sha256_text())
    var kept = Puzzle.new()
    kept.load_level(Puzzle.LEVEL_PATH, root + "sneaky.json")
    var door: Dictionary = kept.nodes.get("door", {})
    check("a draft cannot change flags or consent, only positions", kept.source == "draft" and abs(kept.position_of("door").x - 2.0) < 0.001
        and door.get("requires_full_21_mode") == false and door.get("sfw_safe") == true and str(kept.level["actors"][1].get("consent")) == "mutual")
    var src := FileAccess.get_file_as_string("res://scripts/door_puzzle.gd") + FileAccess.get_file_as_string("res://scripts/door_puzzle_view.gd")
    var code := ""
    for line in src.split("\n"):
        if not line.strip_edges().begins_with("#"):
            code += line + "\n"
    check("the puzzle never calls chat, dialogue or the scene catalog", code.find("ChatBrain") < 0 and code.find("chat_brain") < 0 and code.find("dialogue_runner") < 0 and code.find("scenes.json") < 0 and code.find("SceneCatalog") < 0)
    check("Godot carries no second level schema", code.find("consent") < 0 and code.find("stated_age") < 0)
    _wipe(root)


func _theme() -> void:
    const UI = preload("res://scripts/ui_kit.gd")
    var light_spec := {
        "bg": "fbf6ee",
        "surface": "ffffff",
        "surface-2": "f3e6d4",
        "text": "1b2a30",
        "muted": "5c6b70",
        "line": "e4d5c3",
        "accent": "c46b4a",
        "on-accent": "fbf6ee",
        "ok": "2f6f5e",
        "warn": "a15c2f",
        "bad": "8c3a3a",
    }
    var dark_spec := {
        "bg": "08262e",
        "surface": "0e3c48",
        "surface-2": "143f4a",
        "text": "fbf6ee",
        "muted": "c9d4d0",
        "line": "1e5560",
        "accent": "c46b4a",
        "on-accent": "fbf6ee",
        "ok": "8fcbb4",
        "warn": "e0b089",
        "bad": "f0b4b4",
    }
    UI.bind("light")
    for token in light_spec.keys():
        var got := UI.color(token).to_html(false)
        check("light " + str(token), got == str(light_spec[token]), got)
    var clay := UI.color("accent")
    UI.bind("dark")
    for token in dark_spec.keys():
        var got_dark := UI.color(token).to_html(false)
        check("dark " + str(token), got_dark == str(dark_spec[token]), got_dark)
    check("clay is the accent in both modes", UI.color("accent") == clay)
    UI.bind("match")
    var matched := UI.color("bg")
    check("match resolves to the light or dark page", matched == UI.LIGHT["bg"] or matched == UI.DARK["bg"])
    var main := UI.button("Continue", 420, true)
    check("main buttons stay 52 pixels tall", is_equal_approx(main.custom_minimum_size.y, 52.0), str(main.custom_minimum_size.y))
    var quiet := UI.button("Load", 420, false)
    check("other buttons are at least 44 pixels tall", quiet.custom_minimum_size.y >= 44.0)
    var field := UI.line_edit("Say something in your own words")
    check("text fields are at least 44 pixels tall", field.custom_minimum_size.y >= 44.0)
    var choice := UI.option_button()
    check("menus are at least 44 pixels tall", choice.custom_minimum_size.y >= 44.0)
    var toggle := UI.check_button("Fullscreen")
    check("checks are at least 44 pixels tall", toggle.custom_minimum_size.y >= 44.0)
    var volume := UI.slider()
    check("the volume slider is at least 44 pixels tall", volume.custom_minimum_size.y >= 44.0)
    UI.bind("light")
    var primary := UI.button("New game", 420, true)
    add_child(primary)
    var normal := primary.get_theme_stylebox("normal") as StyleBoxFlat
    check("the primary button uses clay", normal != null and normal.bg_color.to_html(false) == "c46b4a")
    check("primary button text is on accent", primary.get_theme_color("font_color").to_html(false) == "fbf6ee")
    var secondary := UI.button("Settings", 420, false)
    add_child(secondary)
    var focus := secondary.get_theme_stylebox("focus") as StyleBoxFlat
    check("a focused border uses the accent", focus != null and focus.border_color.to_html(false) == "c46b4a")
    primary.queue_free()
    secondary.queue_free()
    UI.bind("match")


func _screens() -> void:
    for path in [
        "res://scripts/title_screen.gd",
        "res://scripts/map_screen.gd",
        "res://scripts/beach_screen.gd",
        "res://scripts/dialogue_screen.gd",
        "res://scripts/settings_screen.gd",
        "res://scripts/age_gate.gd",
        "res://scripts/slot_screen.gd",
        "res://scripts/scene_view.gd",
        "res://scripts/main.gd",
    ]:
        var script = load(path)
        check(path + " parses", script is GDScript and script.can_instantiate())

    var title = load("res://scripts/title_screen.gd").new()
    add_child(title)
    var title_text := _texts(title)
    check("the title shows the private-build line", title_text.find("PRIVATE BUILD — NOT FOR DISTRIBUTION") >= 0, title_text)
    check("the title still names Stillwater", title_text.find("Stillwater") >= 0)
    for node in _buttons(title):
        check("title button stays 52 tall: " + node.text, is_equal_approx(node.custom_minimum_size.y, 52.0))
    title.queue_free()

    var gate = load("res://scripts/age_gate.gd").new()
    add_child(gate)
    var gate_text := _texts(gate)
    check("the gate says I am 21 or older", gate_text.find("I am 21 or older") >= 0, gate_text)
    check("the gate says I am under 21", gate_text.find("I am under 21") >= 0, gate_text)
    check("the gate asks for 21", gate_text.find("Please confirm you are 21 or older.") >= 0, gate_text)
    check("the gate does not ask for 18", gate_text.find("18") < 0, gate_text)
    gate.queue_free()

    var panel = SettingsScreen.new()
    panel.settings_node = SettingsScript.new()
    add_child(panel)
    check("SFW mode still starts on on the settings screen", panel.sfw_check != null and panel.sfw_check.button_pressed == true)
    var options := _option_items(panel)
    check("appearance offers match, light, and dark", options.find("Match this computer") >= 0 and options.find("Light") >= 0 and options.find("Dark") >= 0, options)
    for node in _buttons(panel):
        check("settings buttons are at least 44 tall", node.custom_minimum_size.y >= 44.0, node.text)
    for node in _fields(panel):
        check("settings fields are at least 44 tall", node.custom_minimum_size.y >= 44.0, node.get_class())
    panel.queue_free()


func _standee() -> void:
    var beach = preload("res://scripts/beach_screen.gd").new()
    add_child(beach)
    check(
        "a cutout portrait stays in the foreground frame",
        is_equal_approx(beach.portrait.anchor_top, 0.18) and is_equal_approx(beach.portrait.offset_left, -340.0),
        str(beach.portrait.anchor_top) + " " + str(beach.portrait.offset_left),
    )
    var opaque := Image.create(280, 420, false, Image.FORMAT_RGBA8)
    opaque.fill(Color(0.77, 0.42, 0.29, 1))
    beach.show_portrait_texture(ImageTexture.create_from_image(opaque))
    var width: float = beach.portrait.offset_right - beach.portrait.offset_left
    var height: float = beach.portrait.offset_bottom - beach.portrait.offset_top
    check(
        "a solid pack picture is person-sized",
        width <= 140.0 and height <= 240.0 and width >= 120.0 and height >= 180.0,
        str(width) + "x" + str(height),
    )
    check(
        "the standee stands on the sand",
        is_equal_approx(beach.portrait.anchor_bottom, 0.78) and is_equal_approx(beach.portrait.offset_bottom, 0.0),
    )
    var cutout := Image.create(48, 72, false, Image.FORMAT_RGBA8)
    cutout.fill(Color(0, 0, 0, 0))
    cutout.set_pixel(24, 36, Color(0.8, 0.4, 0.3, 1))
    beach.show_portrait_texture(ImageTexture.create_from_image(cutout))
    check(
        "a cutout figure keeps the foreground frame",
        is_equal_approx(beach.portrait.anchor_top, 0.18) and is_equal_approx(beach.portrait.offset_left, -340.0),
    )
    beach.free()


func _texts(node: Node) -> String:
    var found := ""
    if node is Label or node is Button:
        found += node.text + "\n"
    for child in node.get_children():
        found += _texts(child)
    return found


func _buttons(node: Node) -> Array:
    var found: Array = []
    if node is OptionButton or node is CheckButton:
        pass
    elif node is Button:
        found.append(node)
    for child in node.get_children():
        found.append_array(_buttons(child))
    return found


func _fields(node: Node) -> Array:
    var found: Array = []
    if node is LineEdit or node is OptionButton or node is CheckButton or node is HSlider:
        found.append(node)
    for child in node.get_children():
        found.append_array(_fields(child))
    return found


func _option_items(node: Node) -> String:
    var found := ""
    if node is OptionButton:
        for index in node.item_count:
            found += node.get_item_text(index) + "\n"
    for child in node.get_children():
        found += _option_items(child)
    return found


func _chat() -> void:
    var chat = ChatScript.new()
    var mira: Dictionary = CharacterDB.characters.get("mira", {"name": "Mira Costa", "stated_age": 32, "personality": "Calm."})
    var canned := chat.canned_reply(mira, "hello there")
    check("a canned reply works with nothing installed", canned != "" and canned.find("Mira") >= 0, canned)
    var body: Dictionary = chat.build_ollama_body(mira, [], "The sea is quiet.", "llama3.2")
    check("the Ollama body posts to the chat API shape", body.get("model") == "llama3.2" and body.get("stream") == false, str(body))
    var messages: Array = body.get("messages", [])
    check("the Ollama body starts with a system rule and ends with the player", messages.size() >= 2 and messages[0].get("role") == "system" and messages[-1].get("role") == "user" and messages[-1].get("content") == "The sea is quiet.")
    check("the system prompt states the 21 and fictional-adult rule", str(messages[0].get("content")).find("21") >= 0 and str(messages[0].get("content")).to_lower().find("fictional") >= 0)
    check("the system prompt uses Mira's stated age", str(messages[0].get("content")).find("aged 32") >= 0, str(messages[0].get("content")))
    var missing := {"name": "Mira Costa", "personality": "Calm."}
    var missing_prompt := chat.system_prompt(missing)
    check("a missing age does not build the talking prompt", missing_prompt == "" and chat.build_ollama_body(missing, [], "hello", "llama3.2").is_empty(), missing_prompt)
    check("a missing age is not filled in as 21", missing_prompt.find("21") < 0, missing_prompt)
    check("the word 21 does not build the talking prompt", chat.system_prompt({"name": "Mira Costa", "stated_age": "21", "personality": "Calm."}) == "")
    check("a blank age does not build the talking prompt", chat.system_prompt({"name": "Mira Costa", "stated_age": ""}) == "")
    check("age 18 does not build the talking prompt", chat.system_prompt({"name": "Mira Costa", "stated_age": 18}) == "")
    check("age 21.5 does not build the talking prompt", chat.system_prompt({"name": "Mira Costa", "stated_age": 21.5}) == "")
    var exact := chat.system_prompt({"name": "Ada", "stated_age": 21, "personality": "Calm."})
    check("a stated age of 21 is spoken as 21", exact.find("Ada") >= 0 and exact.find("aged 21") >= 0, exact)
    check("the endpoint is Ollama's /api/chat", chat.endpoint("http://127.0.0.1:11434/") == "http://127.0.0.1:11434/api/chat")
    var fallback := chat.text_or_canned(chat.parse_ollama({"error": "nope"}), mira, "hello")
    check("a bad model response falls back to the canned line", fallback == chat.canned_reply(mira, "hello"), fallback)


func _launch() -> void:
    var JsonFile = preload("res://scripts/json_file.gd")
    var path := "user://stillwater_tests/launch_settings.json"
    var previous_path := Settings.path
    var previous_capture := OS.get_environment("STILLWATER_CAPTURE")
    var previous_root := SaveGame.root
    var slot_before := SaveGame.active_slot
    var place_before := str(SaveGame.progress.get("location", ""))
    var day_before := int(SaveGame.progress.get("day", 1))
    Settings.path = path
    var gate_script = load("res://scripts/age_gate.gd")
    var title_script = load("res://scripts/title_screen.gd")
    var main_script = load("res://scripts/main.gd")

    JsonFile.write(path, {"age_confirmed": true, "volume": 0.5})
    Settings.load_settings()
    OS.set_environment("STILLWATER_CAPTURE", "/tmp/stillwater_capture_should_not_skip")
    var captured = main_script.new()
    add_child(captured)
    check("capture does not skip the gate", captured.screen != null and captured.screen.get_script() == gate_script)
    var during = JsonFile.read(path)
    check("capture does not write the 21 gate", typeof(during) == TYPE_DICTIONARY and not during.has("age_gate_version"), str(during))
    check("capture does not set the gate in memory", Settings.age_gate_version != 21)
    check("showing the gate does not load a slot", SaveGame.active_slot == slot_before and str(SaveGame.progress.get("location", "")) == place_before)
    remove_child(captured)
    captured.free()

    OS.set_environment("STILLWATER_CAPTURE", "")
    JsonFile.write(path, {"age_confirmed": true, "stated_age": 32, "age_gate_version": "21"})
    var worded = main_script.new()
    add_child(worded)
    check("the word 21 in settings does not skip the gate", worded.screen != null and worded.screen.get_script() == gate_script)
    remove_child(worded)
    worded.free()

    var save_root := "user://stillwater_tests/launch_saves/"
    SaveGame.root = save_root
    JsonFile.write(save_root.rstrip("/") + "/autosave.json", {
        "version": 1,
        "slot": 1,
        "location": "beach",
        "time_of_day": "morning",
        "day": 4,
        "affection": {"mira": 2},
        "flags": [],
        "seen": [],
        "age_confirmed": true,
        "age_gate_version": 21,
        "stated_age": 32,
    })
    JsonFile.write(path, {"age_confirmed": true})
    var from_save = main_script.new()
    add_child(from_save)
    check("a save field does not skip the gate", from_save.screen != null and from_save.screen.get_script() == gate_script)
    check("a save is not loaded before the gate", SaveGame.active_slot == slot_before and int(SaveGame.progress.get("day", 1)) == day_before)
    remove_child(from_save)
    from_save.free()
    SaveGame.root = previous_root

    JsonFile.write(path, {"age_confirmed": false, "age_gate_version": 21})
    var passed = main_script.new()
    add_child(passed)
    check("version 21 in settings shows the title", passed.screen != null and passed.screen.get_script() == title_script)
    remove_child(passed)
    passed.free()

    var reader = main_script.new()
    check("main reads integer version 21", reader.launch_gate_passed(path))
    check("main accepts only integer version 21", reader.gate_version_accepted({"age_gate_version": 21, "age_confirmed": false}))
    check("main accepts a whole 21 stored by Godot JSON", reader.gate_version_accepted({"age_gate_version": 21.0}))
    check("main refuses version 18", not reader.gate_version_accepted({"age_gate_version": 18, "age_confirmed": true}))
    check("main refuses version 19", not reader.gate_version_accepted({"age_gate_version": 19}))
    check("main refuses version 20", not reader.gate_version_accepted({"age_gate_version": 20}))
    check("main refuses a fractional gate version", not reader.gate_version_accepted({"age_gate_version": 21.5}))
    check("main refuses the word 21", not reader.gate_version_accepted({"age_gate_version": "21", "age_confirmed": true}))
    check("main refuses a blank settings file", not reader.gate_version_accepted({}))
    check("main refuses the old boolean", not reader.gate_version_accepted({"age_confirmed": true}))
    check("main refuses a save-shaped age", not reader.gate_version_accepted({"version": 1, "slot": 1, "stated_age": 32, "age_confirmed": true}))

    var confirmed = SettingsScript.new()
    confirmed.path = path
    confirmed.age_confirmed = true
    confirmed.confirm_age()
    var written = JsonFile.read(path)
    var stored = written.get("age_gate_version") if typeof(written) == TYPE_DICTIONARY else null
    check("confirming the gate stores version 21", Settings.whole_number(stored) == 21 and typeof(stored) != TYPE_STRING, str(written))
    check("main reads the stored gate", reader.launch_gate_passed(path))
    reader.free()

    var source := FileAccess.get_file_as_string("res://scripts/main.gd")
    check("main keeps the private-build header", source.begins_with("# PRIVATE BUILD — NOT FOR DISTRIBUTION"))
    var tour_at := source.find("func _capture_tour")
    var tour := source.substr(tour_at)
    var next_func := tour.find("\nfunc ")
    if next_func > 0:
        tour = tour.substr(0, next_func)
    check("the capture tour does not write the gate", tour_at >= 0 and tour.find("confirm_age") < 0 and tour.find("age_gate_version") < 0 and tour.find("age_confirmed") < 0, tour)
    check("declining the gate quits", source.find("declined.connect(func(): get_tree().quit())") >= 0)

    Settings.path = previous_path
    Settings.load_settings()
    SaveGame.root = previous_root
    OS.set_environment("STILLWATER_CAPTURE", previous_capture)
    _wipe("user://stillwater_tests/")
    _wipe("user://stillwater_tests/launch_saves/")


func _beach_3d() -> void:
    var JsonFile = preload("res://scripts/json_file.gd")
    var PlateScript = preload("res://scripts/beach_plate.gd")
    var Day = preload("res://scripts/beach_day.gd")
    var previous_root := SaveGame.root
    var previous_place := str(SaveGame.progress.get("location", ""))
    var previous_slot := SaveGame.active_slot
    var previous_time := str(SaveGame.progress.get("time_of_day", "morning"))
    var previous_day := int(SaveGame.progress.get("day", 1))
    SaveGame.root = "user://stillwater_tests/beach3d/"
    SaveGame.progress.time_of_day = "morning"
    SaveGame.progress.day = 1
    _day_rules(Day)
    var host = load("res://scripts/main.gd").new()
    add_child(host)
    host._show_beach()
    var beach: Node = host.screen
    check("the beach the player enters is 3D", beach is Node3D, str(beach))
    if not (beach is Node3D):
        _finish_beach(host, previous_root, previous_place, previous_slot, previous_time, previous_day)
        return

    check("this headless run stays on GL Compatibility", RendererBoot.current_method() == "gl_compatibility")
    var project := FileAccess.get_file_as_string("res://project.godot")
    check("the project names Forward+ for a desktop run", project.find("desktop_rendering_method=\"forward_plus\"") >= 0)
    check("the project default stays on GL Compatibility", project.find("renderer/rendering_method=\"gl_compatibility\"") >= 0)
    check("headless does not request a renderer restart", not RendererBoot.restart_requested())

    var terrain := _find_named(beach, "Terrain") as MeshInstance3D
    if terrain == null or terrain.mesh == null:
        check("the beach is a terrain mesh", false, "the glTF level did not load")
        _finish_beach(host, previous_root, previous_place, previous_slot, previous_time, previous_day)
        return
    var spread := _height_spread(terrain.mesh)
    check("the beach is a terrain mesh", terrain != null and terrain.mesh != null and terrain.mesh.get_surface_count() > 0)
    check("the terrain is not flat", spread > 0.35, str(spread))
    check("the terrain collision is a body, not a flat rectangle", _find_named(beach, "TerrainBody") is StaticBody3D)
    check("the beach level is glTF", FileAccess.file_exists("res://assets/beach/level.gltf"))

    var ocean := _find_named(beach, "Ocean") as MeshInstance3D
    var ocean_mat := ocean.material_override as ShaderMaterial
    var ocean_code := ocean_mat.shader.code if ocean_mat != null and ocean_mat.shader != null else ""
    check("the ocean uses a shader", ocean_code != "")
    check("the ocean shader draws a foam line", ocean_code.find("foam") >= 0)
    var forward_water := FileAccess.get_file_as_string("res://shaders/ocean_forward.gdshader")
    var gl_water := FileAccess.get_file_as_string("res://shaders/ocean_gl.gdshader")
    check("Forward+ water keeps a foam line and a wave normal", forward_water.find("foam") >= 0 and forward_water.find("world_normal") >= 0)
    check("GL water stays the simpler shader", gl_water.find("foam") >= 0 and gl_water.find("world_normal") < 0)

    var env := (beach.get_node("WorldEnvironment") as WorldEnvironment).environment
    var sky_mat := env.sky.sky_material as ProceduralSkyMaterial
    check("a sky is present", env.sky != null and sky_mat != null)
    check("the horizon is the warm part of the sky", sky_mat.sky_horizon_color.r > sky_mat.sky_top_color.r)
    var sun := beach.get_node("Sun") as DirectionalLight3D
    check("the sun is a low warm light", sun.rotation_degrees.x < -8.0 and sun.rotation_degrees.x > -35.0 and sun.light_color.r > sun.light_color.b)
    check("GL Compatibility leaves volumetric fog off", env.volumetric_fog_enabled == false and sun.shadow_enabled == false)
    var fog_src := FileAccess.get_file_as_string("res://scripts/beach_world.gd")
    var fog_at := fog_src.find("volumetric_fog_enabled = true")
    var forward_at := fog_src.find("if method == \"forward_plus\":")
    check("only Forward+ turns on volumetric fog", forward_at >= 0 and fog_at > forward_at)

    var plate := beach.get_node("Player/Plate") as MeshInstance3D
    var plate_script: Object = plate
    check("the person is a glTF plate", plate.mesh != null and _vertex_count(plate.mesh) >= 4 and _vertex_count(plate.mesh) <= 6)
    check("the plate is not a block body", not (plate.mesh is BoxMesh) and not (plate.mesh is CapsuleMesh) and not (plate.mesh is PrismMesh))
    check("the beach has no rigged body", _find_type(beach, "Skeleton3D") == null)
    check("the plate is at eye level", abs(float(plate_script.eye_level) - 1.55) < 0.001)
    check("the plate feet sit on the player", abs(plate.position.y) < 0.001 and _height_spread(plate.mesh) > 1.4)
    var plate_shader := (plate.material_override as ShaderMaterial).shader.code
    check("the plate breathes", plate_shader.find("sin(TIME") >= 0)
    check("the plate has parallax", plate_shader.find("parallax") >= 0)
    var spec = JsonFile.read("res://data/plate.json")
    check("the stand-in is not marked as the finished look", spec.get("finished_look") == false and str(spec.get("label")) == "Stand-in")
    check("the plate file has no SFW switch of its own", not spec.has("sfw_mode"))
    check("the shipped stand-in is rated covered", str(spec.get("content_rating", "")) == "sfw")
    check("the visible plate uses the full slot", str(plate_script.slot) == "full" and str(plate_script.shown_still).ends_with("stand_in.png"))
    check("the plate character is a glTF file", str(spec.get("mesh", "")).ends_with(".gltf"))
    var full_choice: Dictionary = plate_script.choose_media({
        "still": "res://full.png",
        "clip": "res://full.ogv",
        "sfw_still": "res://sfw.png",
        "sfw_clip": "res://sfw.ogv",
    }, false)
    var sfw_choice: Dictionary = plate_script.choose_media({
        "still": "res://full.png",
        "clip": "",
        "sfw_still": "res://sfw.png",
        "sfw_clip": "",
    }, true)
    var hold_choice: Dictionary = plate_script.choose_media({
        "content_rating": "full_21",
        "still": "res://full.png",
        "clip": "res://full.ogv",
        "sfw_still": "",
        "sfw_clip": "",
    }, true)
    var unrated_choice: Dictionary = plate_script.choose_media({"still": "res://full.png"}, true)
    check("SFW mode holds a full 21+ plate with no covered file", hold_choice.get("slot") == "hold" and str(hold_choice.get("still")) == "" and str(hold_choice.get("clip")) == "")
    check("an unrated plate counts as full 21+ in SFW mode", unrated_choice.get("slot") == "hold")
    check("full mode keeps the main still and clip", full_choice.get("slot") == "full" and full_choice.get("still") == "res://full.png" and full_choice.get("clip") == "res://full.ogv")
    check("SFW mode can choose its own file", sfw_choice.get("slot") == "sfw" and sfw_choice.get("still") == "res://sfw.png")
    Settings.adult_content = false
    plate_script.load_default()
    check("SFW mode keeps the covered stand-in on the plate", str(plate_script.slot) == "full" and plate.visible and not plate_script.held)
    var stand_in := Image.load_from_file(ProjectSettings.globalize_path("res://assets/plates/stand_in.png"))
    var corner := stand_in.get_pixel(2, 2)
    var middle := stand_in.get_pixel(stand_in.get_width() / 2, stand_in.get_height() / 2)
    check("the stand-in is a cutout", stand_in != null and corner.a < 0.1 and middle.a > 0.8, str(corner.a) + " " + str(middle.a))

    var stage2 = preload("res://scripts/stage2_humanoid.gd").new().load_spec()
    check("stage 2 is stored and unused", stage2.get("used_by_beach") == false and str(stage2.get("gltf")) == "" and str(stage2.get("navmesh")) == "")
    check("stage 2 names blendshapes and IK", stage2.has("blendshapes") and stage2.get("ik", {}).get("enabled", true) == false)
    var beach_source := ""
    for path in ["res://scripts/beach_world.gd", "res://scripts/beach_player.gd", "res://scripts/beach_plate.gd", "res://scenes/beach_3d.tscn"]:
        beach_source += FileAccess.get_file_as_string(path)
    check("the visible beach does not build the stage 2 body", beach_source.find("stage2_humanoid") < 0 and beach_source.find("Skeleton3D") < 0)
    check("the beach loads the glTF level", beach_source.find("level.gltf") >= 0 and beach_source.find("ArrayMesh.new") < 0)
    check("the plate loads its glTF mesh", beach_source.find("plate.gltf") >= 0)

    var hud_text := _texts(beach.get_node("Hud"))
    var hud_controls := _buttons(beach.get_node("Hud")).size() + _label_count(beach.get_node("Hud"))
    check("the beach keeps to a few labels", hud_controls <= 5 and hud_text.find("Talk") < 0 and hud_text.find("Swim") < 0, hud_text)
    check("the beach time control is on the bar", hud_text.find("Let a little time pass") >= 0, hud_text)
    check("the beach names the stand-in", hud_text.find("Stand-in") >= 0, hud_text)
    check("the beach does not call itself swimwear", hud_text.to_lower().find("swimwear") < 0 and hud_text.to_lower().find("covered") < 0, hud_text)

    var puzzle_view := beach.get_node_or_null("DoorPuzzle")
    check("the door puzzle stands on the 3D beach", puzzle_view != null and puzzle_view.puzzle.error == "", str(puzzle_view.puzzle.error) if puzzle_view != null else "missing")
    if puzzle_view != null and puzzle_view.puzzle.error == "":
        var parts_ok := true
        for part in ["Pad_pad_near", "Pad_pad_far", "Door", "Key", "Companion"]:
            parts_ok = parts_ok and puzzle_view.get_node_or_null(part) != null
        check("the beach shows two pads, the door, the key and the companion plate", parts_ok)
        check("the companion is a Stage 1 plate on the stand-in drawing", puzzle_view.get_node("Companion") is MeshInstance3D and str(puzzle_view.get_node("Companion").shown_still).ends_with("stand_in.png"))
        check("the puzzle names the next step on screen", str(puzzle_view.hint_label.text).find("key") >= 0, puzzle_view.hint_label.text)
        var leaf_shut: Vector3 = puzzle_view.door_leaf.position
        check("a click on her hand plate hitbox is Take the key", puzzle_view.pick_plate(0.7, 0.5) == "take_key")
        puzzle_view.act("pick_up_key")
        puzzle_view.act("take_key")
        puzzle_view.puzzle.step_on("player", puzzle_view.puzzle.rule("near_pad"))
        puzzle_view.act("stand_on_far_pad")
        check("solving it on the beach opens the door", puzzle_view.puzzle.door_open and puzzle_view.door_leaf.position.distance_to(leaf_shut) > 0.5)
        var key_node := puzzle_view.get_node("Key") as Node3D
        var door_node := puzzle_view.get_node("Door") as Node3D
        check("the key sits in the door", key_node.global_position.distance_to(door_node.global_position) < 1.6)
        puzzle_view.draft_path = "user://stillwater_tests/puzzle_view/draft.json"
        puzzle_view.set_editing(true)
        check("Edit this place is a mode of Play", puzzle_view.editing and puzzle_view.edit_box.visible and puzzle_view.edit_box.get_child_count() >= 2)
        puzzle_view.selected = puzzle_view.puzzle.rule("key")
        var key_before: Vector3 = puzzle_view.puzzle.position_of(puzzle_view.selected)
        puzzle_view.nudge(0.5, 0.0)
        check("Edit this place moves a piece on the sand", abs(puzzle_view.puzzle.position_of(puzzle_view.selected).x - key_before.x - 0.5) < 0.001)
        check("Edit this place saves a draft with its hash", puzzle_view.save_draft() and FileAccess.file_exists("user://stillwater_tests/puzzle_view/draft.json.sha256"))
        puzzle_view.set_editing(false)
        _wipe("user://stillwater_tests/puzzle_view/")

    var player := beach.get_node("Player") as CharacterBody3D
    for _i in 90:
        if player.is_on_floor():
            break
        await get_tree().physics_frame
    check("the player stands on the sand", player.is_on_floor(), str(player.global_position))
    await _morning_adults(beach, JsonFile)
    var cam := player.get_node("CameraRig/Camera3D") as Camera3D
    var eye: Vector3 = player.get_node("CameraRig").global_position
    var toward := (eye - cam.global_position).normalized()
    check("the camera sits back from the player", cam.global_position.distance_to(player.global_position) > 2.0)
    check("the camera looks toward eye level", (-cam.global_transform.basis.z).normalized().dot(toward) > 0.75)

    var start := player.global_position
    player.use_scripted = true
    player.scripted = Vector2(0, 1)
    for _i in 30:
        await get_tree().physics_frame
    player.scripted = Vector2.ZERO
    check("the player can walk", player.global_position.distance_to(start) > 0.45, str(player.global_position.distance_to(start)))

    var region := beach.get_node("Navigation") as NavigationRegion3D
    var nav := region.navigation_mesh
    check("a navmesh is loaded", nav != null and nav.get_polygon_count() >= 2, str(nav.get_polygon_count() if nav != null else 0))
    for _i in 5:
        await get_tree().physics_frame
    var map := region.get_navigation_map()
    var path := NavigationServer3D.map_get_path(map, nav.vertices[0], nav.vertices[2], true)
    check("the navmesh can make a path", path.size() >= 2, str(path.size()))
    player.agent.target_position = nav.vertices[2]
    await get_tree().physics_frame
    await get_tree().physics_frame
    var next: Vector3 = player.agent.get_next_path_position()
    check("the navigation agent has a point on the beach", next.distance_to(player.global_position) > 0.05 or path.size() >= 2, str(next))

    player.toggle_view()
    check("first person hides the plate", player.first_person and not plate.visible)
    player.toggle_view()
    check("third person shows the plate", not player.first_person and plate.visible)

    var main_source := FileAccess.get_file_as_string("res://scripts/main.gd")
    check("main still opens this beach", main_source.find("beach_3d.tscn") >= 0)
    check("main keeps the private-build header", main_source.begins_with("# PRIVATE BUILD — NOT FOR DISTRIBUTION"))
    _finish_beach(host, previous_root, previous_place, previous_slot, previous_time, previous_day)


func _day_rules(Day) -> void:
    var morning_spot := [{"time": "morning", "location": "beach", "spot": [1.0, 8.0]}]
    var placed = Day.spot_for({"id": "ada", "name": "Ada", "stated_age": 21, "schedule": morning_spot}, "morning")
    check("age 21 with a written spot is placed", typeof(placed) == TYPE_DICTIONARY and int(placed.get("stated_age", 0)) == 21, str(placed))
    check("a missing age is not placed on the beach", Day.spot_for({"id": "x", "name": "No Age", "schedule": morning_spot}, "morning") == null)
    check("a blank age is not placed on the beach", Day.spot_for({"id": "x", "name": "Blank", "stated_age": "", "schedule": morning_spot}, "morning") == null)
    check("the word 21 is not placed on the beach", Day.spot_for({"id": "x", "name": "Word", "stated_age": "21", "schedule": morning_spot}, "morning") == null)
    check("age 20 is not placed on the beach", Day.spot_for({"id": "x", "name": "Young", "stated_age": 20, "schedule": morning_spot}, "morning") == null)
    check("age 21.5 is not placed on the beach", Day.spot_for({"id": "x", "name": "Fraction", "stated_age": 21.5, "schedule": morning_spot}, "morning") == null)
    var no_spot = Day.spot_for({"id": "ada", "name": "Ada", "stated_age": 32, "schedule": [{"time": "morning", "location": "beach"}]}, "morning")
    check("a missing spot is not invented", no_spot == null)
    var elsewhere = Day.spot_for({"id": "ada", "name": "Ada", "stated_age": 32, "schedule": [{"time": "morning", "location": "cove", "spot": [1.0, 8.0]}]}, "morning")
    check("another place is not built on this beach", elsewhere == null)
    var morning: Array = Day.present(CharacterDB.characters, "morning")
    var midday: Array = Day.present(CharacterDB.characters, "midday")
    check("morning places two adults from the character files", morning.size() == 2, str(morning))
    var ids := PackedStringArray()
    var moved := true
    for item in morning:
        ids.append(str(item.get("id", "")))
        var later := {}
        for other in midday:
            if str(other.get("id", "")) == str(item.get("id", "")):
                later = other
        if later.is_empty() or Vector2(float(item["x"]), float(item["z"])).distance_to(Vector2(float(later["x"]), float(later["z"]))) < 2.0:
            moved = false
    check("the morning adults are Mira and Nia", ids.has("mira") and ids.has("nia") and not ids.has("leo"), str(ids))
    check("the written midday spots are different", moved and midday.size() == 2)
    var day_source := FileAccess.get_file_as_string("res://scripts/beach_day.gd")
    var person_source := FileAccess.get_file_as_string("res://scripts/beach_person.gd")
    var world_source := FileAccess.get_file_as_string("res://scripts/beach_world.gd")
    check(
        "placement does not default an age",
        day_source.find("stated_age\", 21") < 0 and day_source.find("stated_age\",21") < 0 and day_source.find("stated_age = 21") < 0 and person_source.find("stated_age = 21") < 0 and person_source.find("stated_age := 21") < 0,
    )
    check("the adults are not a canned walk loop", day_source.find("set_loops") < 0 and person_source.find("set_loops") < 0 and world_source.find("set_loops") < 0 and world_source.find("Timer") < 0 and world_source.find("AnimationPlayer") < 0)
    check("this beach slice has no dialogue tree", world_source.find("dialogue") < 0 and world_source.find("Talk") < 0)
    var lowered := (day_source + person_source).to_lower()
    var world_lowered := world_source.to_lower()
    # The M2 door puzzle lives on this beach by design (beach_world.gd builds it); the day layer stays free of games.
    check("the day layer has no puzzle or party game", lowered.find("puzzle") < 0 and lowered.find("spin the bottle") < 0 and lowered.find("truth or dare") < 0)
    check("the beach has no party game yet", world_lowered.find("spin the bottle") < 0 and world_lowered.find("truth or dare") < 0)


func _morning_adults(beach: Node3D, JsonFile) -> void:
    var people := beach.get_node_or_null("People")
    check("the morning beach has a people group", people != null)
    if people == null:
        return
    check("two adults stand on the morning beach", people.get_child_count() == 2, str(people.get_child_count()))
    var mira := people.get_node_or_null("mira") as Node3D
    var nia := people.get_node_or_null("nia") as Node3D
    if mira == null or nia == null:
        check("mira and nia are the two plates", false, str(people.get_child_count()))
        return
    var mira_file = JsonFile.read("res://data/characters/mira.json")
    var nia_file = JsonFile.read("res://data/characters/nia.json")
    check("mira's plate uses the age in her file", int(mira.stated_age) == int(mira_file["stated_age"]) and int(mira_file["stated_age"]) >= 21, str(mira.stated_age))
    check("nia's plate uses the age in her file", int(nia.stated_age) == int(nia_file["stated_age"]) and int(nia_file["stated_age"]) >= 21, str(nia.stated_age))
    check("mira is a stage 1 plate", _plate_mesh(mira.get_node("Plate")))
    check("nia is a stage 1 plate", _plate_mesh(nia.get_node("Plate")))
    var mira_name := mira.get_node("Name") as Label3D
    var nia_name := nia.get_node("Name") as Label3D
    check("a name label is enough for mira", mira_name != null and mira_name.text == str(mira_file["name"]), mira_name.text if mira_name != null else "")
    check("a name label is enough for nia", nia_name != null and nia_name.text == str(nia_file["name"]), nia_name.text if nia_name != null else "")
    var mira_feet := _sand_delta(beach, mira)
    var nia_feet := _sand_delta(beach, nia)
    check("mira's feet are on the sand", mira_feet < 0.08, str(mira_feet))
    check("nia's feet are on the sand", nia_feet < 0.08, str(nia_feet))
    var mira_at: Vector3 = mira.global_position
    var nia_at: Vector3 = nia.global_position
    check("the two adults stand apart", mira_at.distance_to(nia_at) > 2.0, str(mira_at.distance_to(nia_at)))
    var later := _find_named(beach, "Later") as Button
    check("the time control can be pressed", later != null and later.text == "Let a little time pass")
    if later == null:
        return
    later.pressed.emit()
    for _i in 8:
        await get_tree().physics_frame
    check("one press moves mira", mira.global_position.distance_to(mira_at) > 2.0, str(mira.global_position.distance_to(mira_at)))
    check("one press moves nia", nia.global_position.distance_to(nia_at) > 2.0, str(nia.global_position.distance_to(nia_at)))
    check("one press keeps both adults", people.get_child_count() == 2)
    check("one press reaches midday", str(SaveGame.progress.get("time_of_day")) == "midday")
    var midday_mira: Vector3 = mira.global_position
    later.pressed.emit()
    check("the next press is another spot", mira.global_position.distance_to(midday_mira) > 2.0 and mira.global_position.distance_to(mira_at) > 2.0, str(mira.global_position))
    var mira_plate := mira.get_node("Plate") as Node3D
    check("the plate feet stay on the person", mira_plate != null and abs(mira_plate.position.y) < 0.001)


func _plate_mesh(plate: Node) -> bool:
    if not (plate is MeshInstance3D):
        return false
    var mesh := (plate as MeshInstance3D).mesh
    if mesh == null or mesh is BoxMesh or mesh is CapsuleMesh or mesh is PrismMesh:
        return false
    var count := _vertex_count(mesh)
    return count >= 4 and count <= 6


func _sand_delta(beach: Node3D, person: Node3D) -> float:
    var plate := person.get_node_or_null("Plate") as Node3D
    if plate == null or abs(plate.position.y) > 0.001:
        return 999.0
    var space := beach.get_world_3d().direct_space_state
    if space == null:
        return 999.0
    var origin := person.global_position
    var query := PhysicsRayQueryParameters3D.create(origin + Vector3(0, 4.0, 0), origin + Vector3(0, -4.0, 0))
    var hit: Dictionary = space.intersect_ray(query)
    if hit.is_empty():
        return 999.0
    return abs(origin.y - float(hit.position.y))


func _finish_beach(host: Node, root: String, place: String, slot: int, when: String, day: int) -> void:
    if host != null and is_instance_valid(host):
        host.free()
    SaveGame.root = root
    SaveGame.progress.location = place
    SaveGame.active_slot = slot
    SaveGame.progress.time_of_day = when
    SaveGame.progress.day = day
    _wipe("user://stillwater_tests/beach3d/")


func _vertex_count(mesh: Mesh) -> int:
    if mesh == null or mesh.get_surface_count() < 1:
        return 0
    var verts: PackedVector3Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
    return verts.size()


func _find_named(node: Node, wanted: String) -> Node:
    if node != null and str(node.name) == wanted:
        return node
    if node == null:
        return null
    for child in node.get_children():
        var found := _find_named(child, wanted)
        if found != null:
            return found
    return null


func _height_spread(mesh: Mesh) -> float:
    if mesh == null or mesh.get_surface_count() < 1:
        return 0.0
    var verts: PackedVector3Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
    if verts.is_empty():
        return 0.0
    var low := verts[0].y
    var high := verts[0].y
    for point in verts:
        low = minf(low, point.y)
        high = maxf(high, point.y)
    return high - low


func _label_count(node: Node) -> int:
    var found := 0
    if node is Label and not (node is Button):
        found += 1
    for child in node.get_children():
        found += _label_count(child)
    return found


func _find_type(node: Node, kind: String) -> Node:
    if node.is_class(kind):
        return node
    for child in node.get_children():
        var found := _find_type(child, kind)
        if found != null:
            return found
    return null


func _find(db, id: String) -> Dictionary:
    for convo in db.conversations:
        if str(convo.get("id", "")) == id:
            return convo
    return {}


func _wipe(dir: String) -> void:
    if not DirAccess.dir_exists_absolute(dir):
        return
    for name in DirAccess.get_files_at(dir):
        DirAccess.remove_absolute(dir.rstrip("/") + "/" + str(name))
