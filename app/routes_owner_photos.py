# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Routes for Add photos (D-C-54). They sit under /api/owner so the server's own-computer guard covers them.

A photo is accepted only after the passphrase unlock, only once somebody is enrolled, and is kept only if it
shows the enrolled face (app/owner_photos.py). The answer for a photo is one plain sentence and a reason code, and for a photo that
did not match, the match score (a number); no picture content and no embedding is sent back.
"""
import owner as O
import owner_photos as OP
import routes_owner


def register(server):
    from fastapi import File, Request, UploadFile

    S = server

    def need_unlock(request):
        if not routes_owner.unlocked(request):
            S.err("Unlock with your passphrase first. An unlock lasts five minutes.")

    @S.app.get("/api/owner/photos")
    def photos_status(request: Request):
        need_unlock(request)
        return {"count": OP.count(S.OUT), "max": OP.MAX_PHOTOS}

    @S.app.post("/api/owner/photos")
    async def photos_add(request: Request, file: UploadFile = File(...)):
        need_unlock(request)
        data = await file.read(OP.MAX_PHOTO_BYTES + 1)
        try:
            got = OP.add_photo(S.OWNER, data)
        except O.OwnerError as exc:
            S.err(str(exc))
        return {"kept": got["kept"], "message": got["message"], "reason": got.get("reason", ""), "score": got.get("score"),
                "count": OP.count(S.OUT)}

    @S.app.delete("/api/owner/photos")
    def photos_remove(request: Request):
        need_unlock(request)
        if routes_owner._owner_jobs_active():
            S.err("A likeness job is waiting or running. Let it finish or cancel it, then remove photos.")
        with S.OWNER.lock:
            return {"removed": OP.remove_all(S.OUT)}
