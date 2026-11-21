# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Add photos (D-C-54): the owner's own photos from disk, kept only if they show the enrolled person.

"An upload is never a source" became "only pictures of the enrolled person are a source". After enrolment a
photo is kept only when ALL of these hold, in this order:
  1. the age check clears it (status ok; a flag is final, an unchecked or unavailable answer is a drop);
  2. the age check and the face check each find exactly one face (a body photo counts when his face is visible);
  3. that face matches the enrolled face (same model, score at or above the threshold stored at enrolment).
Anything else is dropped with one plain message and leaves nothing behind: no file, no record, no embedding of
a person who may not be him. Kept photos go to outputs/owner/photos with the same mark as the captures
(owner_likeness, owner_id, age_check) and are never library items, so no picture job can take one as an input.
Training takes the captures plus the kept photos (owner_train.capture_set).

Limits: the photo goes through the same age check and face check as any capture, and a photo of him is
accepted wherever it came from; this does not prove the picture is recent or that nobody else is in a part of it
the detector cannot see. HEIC files are not read (export as JPEG or PNG). A face the detector does not find
(very small, turned away, masked) is a drop.
"""
import hashlib
import json
import os
import secrets
import time

from PIL import Image, ImageOps

import face_check
import owner as O

DROPPED = "that photo doesn't show the enrolled person"
MAX_PHOTOS = 300
MAX_PHOTO_BYTES = O.MAX_FRAME_BYTES * 2   # a phone photo is a few MB; 40 MB is a generous ceiling
NOT_A_PICTURE = "That file isn't a picture this app can read. Use a JPEG or PNG."
# What the page shows for each photo that was not kept. Plain words; the codes are the same ones the tests use.
REASON_WORDS = {
    "no_match": DROPPED,
    "no_face": "no single clear face was found in it",
    "two_faces": "more than one face is in it",
    "flagged": "the age check flagged it, which is final",
    "age_not_cleared": "the age check could not clear it",
    "duplicate": "it was already added",
    "not_a_picture": "it is not a picture this app can read (use JPEG or PNG)",
}


def photos_dir(out):
    return os.path.join(O.owner_dir(out), "photos")


def records(out):
    """Every kept photo's record. A record that cannot be read is skipped here; training verifies files itself."""
    rows = []
    try:
        names = sorted(os.listdir(photos_dir(out)))
    except OSError:
        return rows
    for name in names:
        if name.endswith(".json"):
            try:
                with open(os.path.join(photos_dir(out), name), encoding="utf-8") as f:
                    row = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(row, dict) and row.get("id"):
                rows.append(row)
    return rows


def count(out):
    return len([f for f in O._listdir(photos_dir(out)) if f.endswith(".png")])


def _drop(reason, score=None):
    """A photo that was not kept. The score is a number only, shown so the threshold can be tuned; nothing else is kept."""
    out = {"kept": False, "message": REASON_WORDS.get(reason, DROPPED), "reason": reason}
    if score is not None:
        out["score"] = score
    return out


def add_photo(owner, data):
    """One photo's bytes. Returns {"kept": bool, "message": str, "reason": str}. Raises OwnerError for a problem that
    is not about the photo's content (nobody enrolled, checker off, no face check, not a picture, too many)."""
    out = owner.out
    with owner.lock:
        rec, ms = O.load(out), O.match_set(out)
        if not rec or not ms or ms.get("owner_id") != rec["owner_id"]:
            raise O.OwnerError("Nobody is enrolled yet. Enrol at the camera first, then add photos.")
        if not owner.age_enabled():
            raise O.OwnerError("The appearance checker is off, so photos can't be added.")
        if not owner.faces.available():
            raise O.OwnerError(face_check.NOT_INSTALLED)
        if owner.faces.model != ms.get("model"):
            raise O.OwnerError("The face check is not the one you enrolled with, so photos can't be matched. "
                               "Enrol again or restore the same face check.")
        if not data or len(data) > MAX_PHOTO_BYTES:
            raise O.OwnerError("Each photo has to be under 40 MB.")
        if count(out) >= MAX_PHOTOS:
            raise O.OwnerError("There are already %d photos. Remove some before adding more." % MAX_PHOTOS)
        src_sha = hashlib.sha256(data).hexdigest()
        if any(r.get("src_sha256") == src_sha for r in records(out)):
            return _drop("duplicate")
        work = os.path.join(O.ensure_private_folder(out), "photos")  # nothing is written before the backup exclusion held
        os.makedirs(work, mode=0o700, exist_ok=True)
        os.chmod(work, 0o700)
        tag = secrets.token_hex(8)
        raw, upright, path = (os.path.join(work, "incoming_%s%s" % (tag, ext)) for ext in (".bin", "_up.png", ".png"))
        try:
            with open(os.open(raw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
                f.write(data)
            try:
                with Image.open(raw) as im:   # a phone photo's rotation lives in its metadata: apply it, then drop it
                    ImageOps.exif_transpose(im).convert("RGB").save(upright, "PNG")
                owner.to_png(upright, path)
            except Exception:  # noqa: BLE001
                return _drop("not_a_picture")
            os.chmod(path, 0o600)
            age = owner.age_check(path)
            if not isinstance(age, dict) or age.get("status") != "ok":
                return _drop("flagged" if isinstance(age, dict) and age.get("status") == "flag" else "age_not_cleared")
            faces = age.get("faces")
            if faces != 1:
                return _drop("two_faces" if isinstance(faces, int) and faces >= 2 else "no_face")
            try:
                seen = owner.faces.inspect(path, "")
            except face_check.FaceUnavailable as exc:
                raise O.OwnerError(str(exc))
            if seen["faces"] >= 2:
                return _drop("two_faces")
            if seen["faces"] != 1 or not seen["embedding"]:
                return _drop("no_face")
            same, score = face_check.matches(seen["embedding"], ms, owner.faces.model)
            if not same:
                return _drop("no_match", score)
            gid = secrets.token_hex(8)
            final = os.path.join(work, gid + ".png")
            os.replace(path, final)
            row = {"id": gid, "file": gid + ".png", "sha256": O.file_sha256(final), "src_sha256": src_sha,
                   "step": "photo", "age_check": "ok", "p_under21": age.get("p_under21"), "owner_likeness": True,
                   "owner_id": rec["owner_id"], "model": owner.faces.model, "score": score,
                   "threshold": ms.get("threshold"), "at": time.time()}
            O._write_private(os.path.join(work, gid + ".json"), row)
            return {"kept": True, "message": "Photo added.", "reason": "", "id": gid, "score": score}
        finally:
            for leftover in (raw, upright, path):
                if os.path.exists(leftover):
                    os.remove(leftover)


def remove_all(out):
    """Delete every kept photo and its record. Returns how many photos went."""
    gone = 0
    for name in O._listdir(photos_dir(out)):
        if name.endswith((".png", ".json", ".bin")):
            try:
                os.remove(os.path.join(photos_dir(out), name))
                gone += name.endswith(".png")
            except OSError:
                pass
    return gone


def photo_items(out, record):
    """The kept photos as training items, each checked against its record and the enrolled owner. Raises ValueError
    with a plain message if one was changed, removed or does not belong to this enrolment."""
    items = []
    for row in records(out):
        path = os.path.join(photos_dir(out), os.path.basename(str(row.get("file") or "")))
        if (row.get("owner_id") != record.get("owner_id") or row.get("owner_likeness") is not True
                or not os.path.isfile(path) or O.file_sha256(path) != row.get("sha256")):
            raise ValueError("A kept photo was changed or removed since it was added, so training will not start. "
                             "Remove the added photos and add them again.")
        items.append({"id": row["file"], "path": path, "age_check": row.get("age_check") or "ok"})
    return items
