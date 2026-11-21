extends Node

# A small seam for a local model. The game talks to an Ollama-compatible
# POST /api/chat endpoint when the player asks for it. With nothing installed,
# canned_reply answers so the island still works offline.


func endpoint(base: String) -> String:
    return base.strip_edges().trim_suffix("/") + "/api/chat"


func chat_url() -> String:
    return endpoint(Settings.ollama_url)


func system_prompt(character: Dictionary) -> String:
    if not character.has("stated_age"):
        return ""
    var age = CharacterDB.accepted_age(character["stated_age"])
    if age == null:
        return ""
    return (
        "You speak as %s, a fictional adult aged %s. Personality: %s. "
        + "This is a calm private island game for one adult player. "
        + "Every character is a fictional adult aged 21 or older. "
        + "Never describe minors. Never describe real people. "
        + "Keep the reply to one or two peaceful sentences."
    ) % [
        str(character.get("name", "A resident")),
        str(age),
        str(character.get("personality", "")),
    ]


func build_ollama_body(character: Dictionary, history: Array, player_line: String, model: String) -> Dictionary:
    var prompt := system_prompt(character)
    if prompt == "":
        return {}
    var messages: Array = [{"role": "system", "content": prompt}]
    for turn in history:
        if typeof(turn) == TYPE_DICTIONARY and turn.has("role") and turn.has("content"):
            messages.append({"role": str(turn.get("role")), "content": str(turn.get("content"))})
    messages.append({"role": "user", "content": player_line})
    return {"model": model, "messages": messages, "stream": false}


func parse_ollama(body) -> String:
    if typeof(body) != TYPE_DICTIONARY:
        return ""
    var message = body.get("message", null)
    if typeof(message) != TYPE_DICTIONARY:
        return ""
    return str(message.get("content", "")).strip_edges()


func canned_reply(character: Dictionary, player_line: String) -> String:
    var name := str(character.get("name", "They")).split(" ")[0]
    var line := player_line.to_lower()
    if line.find("sea") >= 0 or line.find("water") >= 0 or line.find("swim") >= 0:
        return name + " looks at the water. \"It's warm if you take it slowly.\""
    if line.find("sun") >= 0 or line.find("hot") >= 0 or line.find("light") >= 0:
        return name + " nods. \"The light will change when it changes. We can wait.\""
    if line.find("you") >= 0 or line.find("hello") >= 0 or line.find("hi") >= 0:
        return name + " smiles. \"I'm glad you said it in your own words.\""
    return name + " is quiet for a moment. \"The island has time. So do we.\""


func text_or_canned(parsed: String, character: Dictionary, player_line: String) -> String:
    if parsed.strip_edges() == "":
        return canned_reply(character, player_line)
    return parsed


func ask(character: Dictionary, history: Array, player_line: String, on_done: Callable) -> void:
    if Settings.chat_mode != "ollama":
        on_done.call(text_or_canned("", character, player_line))
        return
    var payload := build_ollama_body(character, history, player_line, Settings.ollama_model)
    if payload.is_empty():
        on_done.call(text_or_canned("", character, player_line))
        return
    var http := HTTPRequest.new()
    add_child(http)
    http.timeout = 8.0
    var done := false
    http.request_completed.connect(func(result, code, _headers, body):
        if done:
            return
        done = true
        var parsed := ""
        if result == HTTPRequest.RESULT_SUCCESS and code == 200:
            var decoded = JSON.parse_string(body.get_string_from_utf8())
            parsed = parse_ollama(decoded)
        var text := text_or_canned(parsed, character, player_line)
        http.queue_free()
        on_done.call(text)
    )
    var err := http.request(chat_url(), ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(payload))
    if err != OK:
        done = true
        http.queue_free()
        on_done.call(text_or_canned("", character, player_line))
