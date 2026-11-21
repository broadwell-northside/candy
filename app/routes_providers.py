# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Routes for the API keys panel. The key goes in, once, and is never sent back out.

POST reads the body itself so no validation message can echo the key; GET answers only yes or no per key.
Both answer only on this computer's own address.
"""
import provider_jobs  # noqa: F401  (registers the video_api job)
from providers import guard, keychain, key_names, list_providers, KEY_LABELS

S = None
SAVE = None
BAD = "That request could not be read."


def register(server):
    global S
    from fastapi import Request
    S = server
    import routes_v3
    guard.SETTINGS = server.SETTINGS
    app = server.app

    def local_only(request):
        name = S._host_name(request.headers.get("host"))
        local = request.client is not None and request.client.host in ("127.0.0.1", "::1")
        if name not in S._LOOPBACK_NAMES or not local:
            S.err("Request blocked (the API keys answer only on this computer).", 403)

    def state():
        return {"providers": list_providers(), "hosted_media": guard.hosted_media_on(),
                "keys": [{"name": k, "label": KEY_LABELS[k], "configured": keychain.configured(k)} for k in key_names()]}

    @app.get("/api/providers")
    def providers_state(request: Request):
        local_only(request)
        return state()

    @app.post("/api/providers/key")
    async def save_key(request: Request):
        local_only(request)
        try:
            body = await request.json()
            name, value = body["name"], body["key"]
        except Exception:
            S.err(BAD)
        if name not in KEY_LABELS or not isinstance(value, str):
            S.err(BAD)
        try:
            keychain.set_key(name, value)
        except keychain.KeychainError as exc:
            S.err(str(exc))
        return state()

    @app.delete("/api/providers/key/{name}")
    def remove_key(request: Request, name: str):
        local_only(request)
        if name not in KEY_LABELS:
            S.err(BAD, 404)
        keychain.delete_key(name)
        return state()

    @app.post("/api/providers/hosted-media")
    async def hosted_media(request: Request):
        local_only(request)
        try:
            body = await request.json()
            on = body["on"] is True
        except Exception:
            S.err(BAD)
        if on and body.get("confirm") != "I understand":
            S.err("Turning this on needs confirmation.")
        server.SETTINGS["hosted_media"] = on
        routes_v3._save_settings()
        return state()
