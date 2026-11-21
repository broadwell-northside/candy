extends RefCounted

const BEACH := "beach"


static func terrain_height(x: float, z: float) -> float:
    # Same sand height the beach mesh was built with.
    var inland := clampf((z - 0.5) / 24.0, 0.0, 1.0)
    var dune := sin(x * 0.16) * 0.32 * inland
    dune += sin(x * 0.05 + z * 0.19) * 0.7 * inland * inland
    var shelf := _smoothstep(-1.0, 7.0, z) * 0.62
    return shelf + dune


static func _smoothstep(edge0: float, edge1: float, value: float) -> float:
    var span := edge1 - edge0
    if span == 0.0:
        return 0.0
    var t := clampf((value - edge0) / span, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


static func present(characters: Dictionary, time_of_day: String) -> Array:
    var ids: Array = characters.keys()
    ids.sort()
    var found: Array = []
    for id in ids:
        var person = characters[id]
        if typeof(person) != TYPE_DICTIONARY:
            continue
        var record: Dictionary = person.duplicate()
        if str(record.get("id", "")) == "":
            record["id"] = str(id)
        var spot = spot_for(record, time_of_day)
        if typeof(spot) != TYPE_DICTIONARY:
            continue
        found.append(spot)
    return found


static func spot_for(person: Dictionary, time_of_day: String):
    # Age has to be written on the person. A missing or refused age is left out.
    if typeof(person) != TYPE_DICTIONARY or not person.has("stated_age"):
        return null
    var age = CharacterDB.accepted_age(person["stated_age"])
    if age == null:
        return null
    var who := str(person.get("name", "")).strip_edges()
    if who == "":
        return null
    var point = _spot(person.get("schedule", null), time_of_day)
    if point == null:
        return null
    return {
        "id": str(person.get("id", "")),
        "name": who,
        "stated_age": int(age),
        "x": point.x,
        "z": point.y,
    }


static func _spot(schedule, time_of_day: String):
    if typeof(schedule) != TYPE_ARRAY:
        return null
    for entry in schedule:
        if typeof(entry) != TYPE_DICTIONARY:
            continue
        if str(entry.get("time", "")) != time_of_day:
            continue
        if str(entry.get("location", "")) != BEACH:
            continue
        if not entry.has("spot"):
            return null
        return _pair(entry["spot"])
    return null


static func _pair(spot):
    if typeof(spot) != TYPE_ARRAY or spot.size() != 2:
        return null
    if not _number(spot[0]) or not _number(spot[1]):
        return null
    return Vector2(float(spot[0]), float(spot[1]))


static func _number(value) -> bool:
    return typeof(value) == TYPE_INT or (typeof(value) == TYPE_FLOAT and is_finite(value))
