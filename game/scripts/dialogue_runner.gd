extends RefCounted

var conversation := {}
var node_id := ""
var ended := false
var awaiting_line := false
var last_effect := {"affection": 0, "flag": ""}


func start(convo: Dictionary) -> Dictionary:
    conversation = convo
    node_id = str(convo.get("start", "start"))
    ended = false
    awaiting_line = false
    last_effect = {"affection": 0, "flag": ""}
    if not _nodes().has(node_id):
        ended = true
    return view()


func view() -> Dictionary:
    var node := _node()
    var choices: Array = []
    for choice in node.get("choices", []):
        if typeof(choice) != TYPE_DICTIONARY:
            continue
        choices.append({
            "label": str(choice.get("label", "")),
            "free_talk": bool(choice.get("free_talk", false)),
        })
    var terminal := bool(node.get("end", false)) or (choices.is_empty() and not node.has("next"))
    return {
        "id": str(conversation.get("id", "")),
        "speaker": str(conversation.get("character", "")),
        "mood": str(node.get("mood", "neutral")),
        "text": str(node.get("text", "")),
        "choices": choices,
        "terminal": terminal,
        "ended": ended,
        "awaiting_line": awaiting_line,
    }


func pick(index: int) -> Dictionary:
    if ended:
        return view()
    var raw: Array = _node().get("choices", [])
    if index < 0 or index >= raw.size():
        return view()
    var choice = raw[index]
    if typeof(choice) != TYPE_DICTIONARY:
        return view()
    last_effect = {
        "affection": int(choice.get("affection", 0)),
        "flag": str(choice.get("flag", "")),
    }
    if bool(choice.get("free_talk", false)):
        awaiting_line = true
        return view()
    _go(str(choice.get("to", "")))
    return view()


func finish_free_talk() -> Dictionary:
    awaiting_line = false
    return view()


func continue_line() -> Dictionary:
    if ended or awaiting_line:
        return view()
    var node := _node()
    if node.get("choices", []).size() > 0:
        return view()
    if bool(node.get("end", false)) or not node.has("next"):
        ended = true
        return view()
    _go(str(node.get("next")))
    return view()


func _go(target: String) -> void:
    if target == "" or not _nodes().has(target):
        ended = true
        return
    node_id = target


func _nodes() -> Dictionary:
    var nodes = conversation.get("nodes", {})
    return nodes if typeof(nodes) == TYPE_DICTIONARY else {}


func _node() -> Dictionary:
    var node = _nodes().get(node_id, {})
    return node if typeof(node) == TYPE_DICTIONARY else {}
