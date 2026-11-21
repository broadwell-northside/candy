# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Routes for the owner's own likeness. Slice 1: enrolment by the app's camera, and the unlock.

Every route here answers only on this computer's own address (the server's guard checks the Host
name and the caller). A picture is accepted only as the next step of an open capture session, and
the session enrols nobody unless the face check says the whole capture was live. The frame route
still receives a file over HTTP, so the nonce and the step order are not treated as proof of a camera.
"""
import os

import face_check
import owner as O

OWNER_COOKIE = "es_owner"
S = None
OWNER = None


def unlocked(request):
    return bool(OWNER and request is not None and OWNER.unlocked(request.cookies.get(OWNER_COOKIE)))


OWNER_JOB_KINDS = ("owner_train", "owner_picture")
DELETE_WORDS = "delete my likeness"


def gate_job(request, kind, area):
    """For a job that uses the owner's likeness: who may queue it. Returns the owner's id, which the server
    stores on the job, or None for any other kind. The job checks that id again when it runs."""
    if kind not in OWNER_JOB_KINDS:
        return None
    name = S._host_name(request.headers.get("host"))
    local = request.client is not None and request.client.host in ("127.0.0.1", "::1")
    if name not in S._LOOPBACK_NAMES or not local:
        S.err("Request blocked (this part of the app answers only on this computer).", 403)
    record = O.load(S.OUT)
    if not record:
        S.err("Nobody is enrolled yet. Enrol with the camera first.")
    if kind == "owner_train" and area != "default":
        S.err("Training the likeness happens in the everyday section only.")
    if not unlocked(request):
        S.err("Unlock with your passphrase first. An unlock lasts five minutes.")
    if kind == "owner_picture":
        import owner_generate
        import pipelines
        try:
            owner_generate.gates(area, OWNER)  # the 18+ consent record and the live-match window
        except pipelines.UserError as exc:
            S.err(str(exc))
    return record["owner_id"]


def _owner_jobs_active():
    return [j["id"] for j in list(S.JOBS.values())
            if j.get("kind") in OWNER_JOB_KINDS and j.get("status") in ("queued", "running")]


def register(server):
    global S, OWNER
    from fastapi import Body, File, Form, Request, UploadFile
    from fastapi.responses import JSONResponse

    S = server
    app = server.app
    OWNER = O.Owner(server.OUT, face_check.FaceCheck(python=server.COMFY_PYTHON, model_dir=os.path.join(server.COMFY_DIR, "models", "easy_studio", "face_check")),
                    server.AGE.check,
                    lambda: server.AGE.enabled, server.safety.require_stated_age, server.assets.to_png)
    server.OWNER = OWNER
    server.owner_unlocked = unlocked
    import loras
    import owner_generate
    import owner_policy
    import owner_train
    from fastapi.responses import FileResponse

    owner_generate.OWNER = OWNER
    owner_generate.COMFY_DIR = server.COMFY_DIR
    lora_dir = server.LORAS.dir if server.LORAS.available() else None
    # The lock by SHA-256, asked for every LoRA before anything else about it.
    loras.LIKENESS_GUARD = lambda path: owner_policy.lora_refusal(S.OUT, path)
    loras.LIKENESS_ALLOWED = lambda path: bool(owner_policy.current()) and owner_policy._sha(path) == owner_policy.current()["sha256"]
    server.cc.GRAPH_GUARD = lambda wf: owner_policy.graph_refusal(S.OUT, lora_dir, wf)
    owner_generate.sweep(S.OUT, lora_dir)  # a crash leaves no link, download or engine output behind

    @app.get("/api/owner/trainer")
    def owner_trainer():
        return owner_train.status(S.OUT)

    # ------------------------------------------------------------------ the live match, the 18+ consent
    @app.post("/api/owner/live/start")
    def owner_live_start(request: Request):
        if not unlocked(request):
            S.err("Unlock with your passphrase first. An unlock lasts five minutes.")
        try:
            return OWNER.live_start()  # frames and the commit go through the same two capture routes
        except O.OwnerError as exc:
            refuse(exc)

    @app.get("/api/owner/consent")
    def owner_consent_get():
        return {"consent_18": OWNER.consent_valid(), "window_open": OWNER.window_open(), "statement": O.CONSENT_STATEMENT}

    @app.post("/api/owner/consent")
    def owner_consent(request: Request, body: dict = Body(...)):
        if not unlocked(request):
            S.err("Unlock with your passphrase first. An unlock lasts five minutes.")
        try:
            if body.get("give") is True:
                if not S.adult_unlocked(request):
                    S.err("Open the 18+ section on this device first.")
                return OWNER.consent_give()
            if body.get("give") is not False:
                S.err("Say give: true or give: false.")
            return OWNER.consent_withdraw()
        except O.OwnerError as exc:
            refuse(exc)

    # ------------------------------------------------------------------ the private gallery
    def _may_see(request, row):
        return unlocked(request) and ((row.get("area") or "adult") != "adult" or S.adult_unlocked(request))

    @app.get("/api/owner/gallery")
    def owner_gallery(request: Request):
        if not unlocked(request):
            S.err("Unlock with your passphrase first. An unlock lasts five minutes.")
        rows = [row for row in O.gallery_list(S.OUT) if _may_see(request, row)]
        return {"items": [{"id": r["id"], "area": r.get("area"), "created": r.get("created"), "seed": r.get("seed"),
                           "base": r.get("base"), "age_override": (r.get("provenance") or {}).get("age_override"),
                           "url": "/api/owner/gallery/%s/file" % r["id"]} for r in rows]}

    @app.get("/api/owner/gallery/{gid}/file")
    def owner_gallery_file(request: Request, gid: str):
        row = next((r for r in O.gallery_list(S.OUT) if r.get("id") == gid), None)
        if not row or not _may_see(request, row):
            S.err("Not found", 404)
        path = os.path.join(O.gallery_dir(S.OUT), os.path.basename(str(row.get("file") or "")))
        if not os.path.isfile(path):
            S.err("Not found", 404)
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    # ------------------------------------------------------------------ the kill switch
    @app.delete("/api/owner/likeness")
    def owner_delete(request: Request, body: dict = Body(default={})):
        # An unlock, or the typed words: a forgotten passphrase must not leave the files and the lock in place.
        if not unlocked(request) and str(body.get("confirm") or "").strip().lower() != DELETE_WORDS:
            S.err('Unlock first, or type "%s" to delete without the passphrase.' % DELETE_WORDS)
        if _owner_jobs_active():
            S.err("A likeness job is waiting or running. Let it finish or cancel it, then delete.")
        try:
            done = OWNER.remove_everything(lora_dir)
        except O.OwnerError as exc:
            refuse(exc)
        owner_generate.sweep(S.OUT, lora_dir)
        resp = JSONResponse(done)
        resp.delete_cookie(OWNER_COOKIE, path="/")
        return resp

    def refuse(exc):
        S.err(str(exc))

    @app.get("/api/owner/status")
    def owner_status(request: Request):
        return {**OWNER.status(), "unlocked": unlocked(request), "consent_18": OWNER.consent_valid(),
                "window_open": OWNER.window_open(),
                "how": "Enrolment is by this computer's camera, in a capture session with a live check. "
                       "A picture file on its own is never accepted."}

    @app.post("/api/owner/enrol/start")
    def owner_start(body: dict = Body(...)):
        try:
            return OWNER.start(body.get("age"), body.get("passphrase"))
        except O.OwnerError as exc:
            refuse(exc)

    @app.post("/api/owner/enrol/frame")
    async def owner_frame(file: UploadFile = File(...), session: str = Form(""), index: str = Form(""),
                          nonce: str = Form("")):
        data = await file.read(O.MAX_FRAME_BYTES + 1)
        try:
            return OWNER.frame(session, index, nonce, data)
        except O.OwnerError as exc:
            refuse(exc)

    @app.post("/api/owner/enrol/commit")
    def owner_commit(body: dict = Body(...)):
        try:
            return OWNER.commit(body.get("session"))
        except O.OwnerError as exc:
            refuse(exc)

    @app.post("/api/owner/enrol/cancel")
    def owner_cancel(body: dict = Body(...)):
        OWNER.cancel(body.get("session"))
        return {"ok": True}

    @app.post("/api/owner/unlock")
    def owner_unlock(body: dict = Body(...)):
        try:
            token = OWNER.unlock(body.get("passphrase"))
        except O.OwnerError as exc:
            refuse(exc)
        resp = JSONResponse({"unlocked": True, "seconds": O.FRESH_SECONDS})
        resp.set_cookie(OWNER_COOKIE, token, max_age=O.FRESH_SECONDS, httponly=True, samesite="strict", path="/")
        return resp

    @app.post("/api/owner/lock")
    def owner_lock(request: Request):
        OWNER.relock(request.cookies.get(OWNER_COOKIE))
        resp = JSONResponse({"unlocked": False})
        resp.delete_cookie(OWNER_COOKIE, path="/")
        return resp
