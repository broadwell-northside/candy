# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The owner's own likeness: enrolment.

One person, the owner (D-C-46). Pictures are accepted only inside a capture session with a random
step plan. Each frame is age-checked and face-checked before it is kept, and the whole capture
needs the face check's live verdict before anyone is enrolled.
Nothing is written under outputs/owner until that folder is excluded from backups, and owner.json
is written only when an enrolment commits, so a failed try never locks the app.

Design: docs/design/SELF-LIKENESS-v2-20261119.md. This is the thin first version (D-C-48):
plain files, a passphrase in place of a passkey, and a face check behind an interface.
"""
import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time

import face_check

MIN_AGE_MESSAGE = "The stated age has to be 21 or older."
ONE_PERSON = "This app already has its one enrolled person. A second enrolment is refused."
NOT_EXCLUDED = ("The likeness folder could not be kept out of backups on this machine, so nothing was saved "
                "and enrolment cannot start.")
PLAN_STEPS = 12          # one frame per step; training later needs at least ten pictures
STEP_SECONDS = 30        # how long one step stays open
SESSION_SECONDS = 15 * 60
FRESH_SECONDS = 5 * 60   # how long an unlock stays fresh
LIVE_STEPS = 3           # a live match is a short plan
ADULT_LIVE_KIND = "pad"  # 18+ pictures of the likeness need an enrolment made with a real presentation-attack check
ADULT_NEEDS = "18+ pictures of your likeness need a live check this face check does not have yet. Everyday pictures are not affected."
WINDOW_SECONDS = 10 * 60 # how long 18+ likeness jobs may start after a live match
MAX_FRAME_BYTES = 20 * 1024 * 1024
MIN_PASSPHRASE = 10
_SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1, "dklen": 32}
CONSENT_STATEMENT = ("I am the person enrolled on this app. I agree that pictures of my own likeness may be made in "
                     "the 18+ section of this app, on this machine, for me alone. I can take this back at any time, "
                     "and taking it back deletes those pictures.")
REVOKED_FILE = "owner_revoked.json"   # kept outside outputs/owner: the kill switch deletes that folder
REMOVED_FILE = "owner_removed.json"


class OwnerError(ValueError):
    """A refusal with a plain message. It never carries a passphrase or a file's contents."""


def owner_dir(out):
    return os.path.join(out, "owner")


def _backup_tool():
    if face_check.testing() and os.environ.get("EASY_STUDIO_BACKUP_TOOL"):  # a stand-in, in a test run only
        return os.environ["EASY_STUDIO_BACKUP_TOOL"]
    return "/usr/bin/tmutil"


def _tool(*args):
    tool = _backup_tool()
    cmd = ([sys.executable, tool] if tool.endswith(".py") else [tool]) + list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


def backup_excluded(path):
    done = _tool("isexcluded", path)
    return bool(done and done.returncode == 0 and "[Excluded]" in (done.stdout or ""))


def ensure_private_folder(out):
    """Create outputs/owner, keep it out of backups, and check that held. Nothing is written inside before this.

    Raises OwnerError when the exclusion cannot be set or confirmed: then no likeness file is ever saved."""
    folder = owner_dir(out)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    if not backup_excluded(folder):
        _tool("addexclusion", folder)
        if not backup_excluded(folder):
            raise OwnerError(NOT_EXCLUDED)
    return folder


def _listdir(path):
    try:
        return os.listdir(path)
    except OSError:
        return []


def _owner_file(out):
    return os.path.join(owner_dir(out), "owner.json")


def load(out):
    try:
        with open(_owner_file(out), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("owner_id") else None
    except (OSError, ValueError):
        return None


def enrolled(out):
    return os.path.exists(_owner_file(out))


def match_set(out):
    try:
        with open(os.path.join(owner_dir(out), "match_set.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _hash(passphrase, salt):
    return hashlib.scrypt(str(passphrase).encode("utf-8"), salt=bytes.fromhex(salt), maxmem=2 ** 26, **_SCRYPT).hex()


def _write_private(path, data):
    tmp = path + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# The likeness registry: which LoRA files are the owner's likeness, by SHA-256, not by name.
# Thin first version: the signing key is a private file beside it. A later version keeps it in the Keychain.
# ---------------------------------------------------------------------------
def _registry_file(out):
    return os.path.join(owner_dir(out), "likeness_registry.json")


def _registry_key(out, create=False):
    path = os.path.join(owner_dir(out), "registry.key")
    try:
        with open(path, encoding="utf-8") as f:
            return bytes.fromhex(f.read().strip())
    except (OSError, ValueError):
        if not create:
            return None
    key = secrets.token_bytes(32)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        f.write(key.hex())
    return key


def _entry_mac(key, entry):
    body = json.dumps({k: entry.get(k) for k in ("sha256", "owner_id", "file", "base", "capture_session", "created")},
                      sort_keys=True).encode("utf-8")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def registry(out):
    """Every registered likeness LoRA. An entry whose signature does not verify still counts as a likeness
    (the lock fails closed), and is marked not valid so it is never loaded."""
    try:
        with open(_registry_file(out), encoding="utf-8") as f:
            rows = json.load(f)
    except (OSError, ValueError):
        return []
    key = _registry_key(out)
    out_rows = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("sha256"):
            good = bool(key) and secrets.compare_digest(str(row.get("mac") or ""), _entry_mac(key, row))
            out_rows.append({**row, "valid": good})
    return out_rows


def registry_add(out, sha256, owner_id, file, base, capture_session):
    folder = ensure_private_folder(out)
    key = _registry_key(out, create=True)
    entry = {"sha256": sha256, "owner_id": owner_id, "file": file, "base": base, "capture_session": capture_session,
             "created": time.time(), "owner_likeness": True}
    entry["mac"] = _entry_mac(key, entry)
    rows = [{k: v for k, v in row.items() if k != "valid"} for row in registry(out) if row["sha256"] != sha256]
    _write_private(os.path.join(folder, "likeness_registry.json"), rows + [entry])
    return entry


def is_likeness_hash(out, sha256):
    return any(row["sha256"] == sha256 for row in registry(out))


def revoked_hashes(out):
    try:
        with open(os.path.join(out, REVOKED_FILE), encoding="utf-8") as f:
            rows = json.load(f)
        return {str(x) for x in rows} if isinstance(rows, list) else set()
    except (OSError, ValueError):
        return set()


def private_lora_files(out):
    folder = os.path.join(owner_dir(out), "loras")
    try:
        return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.endswith(".safetensors")]
    except OSError:
        return []


_HASHES = {}
_HASH_LOCK = threading.Lock()


def cached_sha256(path):
    """The file's SHA-256, hashed once per (file, size, change time). None when the file cannot be read."""
    try:
        st = os.stat(path)
        key = (os.path.realpath(path), st.st_size, st.st_mtime_ns)
        with _HASH_LOCK:
            if key not in _HASHES:
                if len(_HASHES) > 512:
                    _HASHES.clear()
                _HASHES[key] = file_sha256(path)
            return _HASHES[key]
    except OSError:
        return None


def likeness_hashes(out):
    """Every hash that is the owner's likeness: the registry, any file in the private LoRA folder (a file is
    moved there before it is registered), and the hashes revoked by the kill switch."""
    found = {row["sha256"] for row in registry(out)} | revoked_hashes(out)
    return found | {h for h in map(cached_sha256, private_lora_files(out)) if h}


def usable_lora(out, owner_id, base=None):
    """The newest registered likeness LoRA that verifies and still has its hash, or None."""
    for row in sorted(registry(out), key=lambda r: r.get("created") or 0, reverse=True):
        if not row["valid"] or row.get("owner_id") != owner_id or (base and row.get("base") != base):
            continue
        path = os.path.join(owner_dir(out), "loras", os.path.basename(str(row.get("file") or "")))
        try:
            if os.path.isfile(path) and file_sha256(path) == row["sha256"]:
                return dict(row, path=path)
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------
# The private gallery: likeness pictures are plain files here, never items in the shared library,
# so no ordinary job can take one as an input and no export can reach one.
# ---------------------------------------------------------------------------
def gallery_dir(out):
    return os.path.join(owner_dir(out), "gallery")


def gallery_add(out, src, record):
    folder = os.path.join(ensure_private_folder(out), "gallery")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    gid = secrets.token_hex(8)
    final = os.path.join(folder, gid + ".png")
    shutil.move(src, final)
    os.chmod(final, 0o600)
    row = dict(record, id=gid, file=gid + ".png", sha256=file_sha256(final), owner_likeness=True, created=time.time())
    _write_private(os.path.join(folder, gid + ".json"), row)
    return row


def gallery_list(out):
    rows = []
    try:
        names = sorted(os.listdir(gallery_dir(out)))
    except OSError:
        return rows
    for name in names:
        if name.endswith(".json"):
            try:
                with open(os.path.join(gallery_dir(out), name), encoding="utf-8") as f:
                    row = json.load(f)
            except (OSError, ValueError):
                # A record that cannot be read still stands for a likeness picture: 18+ until shown otherwise.
                row = {"id": name[:-5], "file": name[:-5] + ".png", "area": "adult", "owner_likeness": True, "unreadable": True}
            rows.append(row)
    return sorted(rows, key=lambda r: r.get("created") or 0, reverse=True)


def gallery_remove(out, only_area=None):
    """Delete likeness pictures for good. A record that cannot be read counts as 18+."""
    gone = 0
    for row in gallery_list(out):
        if only_area and (row.get("area") or "adult") != only_area:
            continue
        for name in (str(row.get("file") or ""), str(row.get("id") or "") + ".json"):
            path = os.path.join(gallery_dir(out), os.path.basename(name))
            if name and os.path.exists(path):
                os.remove(path)
        gone += 1
    return gone


def remove_copies(lora_dir, hashes):
    """The kill switch: delete every file in the engine's LoRA folder whose SHA-256 is one of these, whatever
    its name. Returns how many were deleted. Other files are not touched."""
    gone, seen = 0, set()
    for folder, subs, files in os.walk(lora_dir, followlinks=True) if lora_dir and hashes else ():
        real = os.path.realpath(folder)
        if real in seen:  # a link that leads back into the folder: do not walk it again
            subs[:] = []
            continue
        seen.add(real)
        for name in files:
            path = os.path.join(folder, name)
            if cached_sha256(path) in hashes:
                try:
                    os.remove(path)
                    gone += 1
                except OSError:
                    pass
    return gone


def sweep_engine_links(lora_dir):
    """Remove every job-scoped link to a likeness LoRA from the engine's LoRA folder. Links only: a file of
    the same name that somebody put there is theirs, and the lock by hash still refuses it if it is a copy."""
    try:
        names = os.listdir(lora_dir) if lora_dir else []
    except OSError:
        names = []
    for name in names:
        if name.startswith("owner_") and name.endswith(".safetensors") and os.path.islink(os.path.join(lora_dir, name)):
            try:
                os.remove(os.path.join(lora_dir, name))
            except OSError:
                pass


class Owner:
    """Capture sessions and unlocks. Both live in memory only; a restart ends them."""

    def __init__(self, out, faces, age_check, age_enabled, require_age, to_png):
        self.out, self.faces = out, faces
        self.age_check, self.age_enabled, self.require_age, self.to_png = age_check, age_enabled, require_age, to_png
        self.lock = threading.Lock()
        self.sessions = {}
        self.unlocks = {}
        self.failures = []
        self.window = None      # {"owner_id", "until"}: opened by a live match, in memory only
        self.busy = 0           # owner jobs queued or running; the kill switch waits for zero

    # ------------------------------------------------------------------ status
    def status(self):
        return {"enrolled": enrolled(self.out), "checker_on": bool(self.age_enabled()),
                "face_check": self.faces.available(), "face_check_message": self.faces.last_error or "",
                "live_check": self.faces.liveness_kind,
                "steps": PLAN_STEPS, "min_passphrase": MIN_PASSPHRASE}

    # ------------------------------------------------------------------ enrolment
    def start(self, age, passphrase):
        if enrolled(self.out):
            raise OwnerError(ONE_PERSON)
        if not self.age_enabled():
            raise OwnerError("The appearance checker is off, so enrolment will not start.")
        ok, stated, msg = self.require_age({"age": age})
        if not ok:
            raise OwnerError(msg or MIN_AGE_MESSAGE)
        if not isinstance(passphrase, str) or len(passphrase) < MIN_PASSPHRASE:
            raise OwnerError("Choose a passphrase of at least %d characters." % MIN_PASSPHRASE)
        if not self.faces.available():
            raise OwnerError(face_check.NOT_INSTALLED)
        folder = ensure_private_folder(self.out)
        salt = secrets.token_hex(16)
        return self._open("enrol", os.path.join(folder, "captures"), PLAN_STEPS,
                          stated_age=stated, salt=salt, hash=_hash(passphrase, salt))

    def _open(self, purpose, parent, count, **extra):
        """A capture session: a random plan of steps, one frame each. Enrolment and the live match both use it."""
        rng = secrets.SystemRandom()
        steps = list(face_check.STEPS) * 3
        rng.shuffle(steps)
        steps = steps[:count]
        if count >= len(face_check.STEPS):
            for need in face_check.STEPS:  # every pose is asked at least once
                if need not in steps:
                    steps[rng.randrange(len(steps))] = need
        sid = secrets.token_hex(16)
        now = time.time()
        with self.lock:
            for old in [k for k, v in self.sessions.items() if v["ends"] <= now]:
                self._end(old)
            if self.sessions:
                raise OwnerError("A capture is already under way. Finish it or cancel it first.")
            self.sessions[sid] = {
                "purpose": purpose, "ends": now + SESSION_SECONDS, "next": 0, "opened": now, "frames": [],
                "plan": [{"step": s, "nonce": secrets.token_hex(8)} for s in steps],
                "dir": os.path.join(parent, sid), "dead": False, **extra}
            plan = [{"index": i, "step": row["step"]} for i, row in enumerate(self.sessions[sid]["plan"])]
            first = self.sessions[sid]["plan"][0]["nonce"]
        return {"session": sid, "plan": plan, "nonce": first, "step_seconds": STEP_SECONDS}

    # ------------------------------------------------------------------ the live match and its window
    def live_start(self):
        """A short capture that has to match the enrolled face. Passing it opens the 18+ window."""
        if not load(self.out) or not match_set(self.out):
            raise OwnerError("Nobody is enrolled yet.")
        if not self.age_enabled():
            raise OwnerError("The appearance checker is off, so the live match will not start.")
        if not self.faces.available():
            raise OwnerError(face_check.NOT_INSTALLED)
        folder = ensure_private_folder(self.out)
        return self._open("live", os.path.join(folder, "live"), LIVE_STEPS)

    def window_open(self):
        rec = load(self.out)
        win = self.window
        return bool(rec and win and win.get("owner_id") == rec["owner_id"] and win["until"] > time.time())

    def window_close(self):
        self.window = None

    def _session(self, sid):
        sess = self.sessions.get(str(sid or ""))
        if not sess or sess["ends"] < time.time():
            raise OwnerError("That capture session is not open. Start again from the camera page.")
        if sess["dead"]:
            raise OwnerError("That capture session was stopped. Start again, alone in front of the camera.")
        return sess

    def _end(self, sid, remove=True):
        sess = self.sessions.pop(str(sid or ""), None)
        if sess and remove:
            shutil.rmtree(sess["dir"], ignore_errors=True)

    def cancel(self, sid):
        with self.lock:
            self._end(sid)

    def frame(self, sid, index, nonce, data):
        """One camera frame for the step the plan asks next. Returns the next step's nonce, or done."""
        with self.lock:
            sess = self._session(sid)
            row = sess["plan"][sess["next"]] if sess["next"] < len(sess["plan"]) else None
            if row is None:
                raise OwnerError("Every step already has its picture. Finish the enrolment.")
            if str(index) != str(sess["next"]) or not secrets.compare_digest(str(nonce or ""), row["nonce"]):
                raise OwnerError("That picture does not belong to the step the plan asks for now.")
            if time.time() - sess["opened"] > STEP_SECONDS:
                self._end(sid)
                raise OwnerError("That step ran out of time. Start again from the camera page.")
            if not data or len(data) > MAX_FRAME_BYTES:
                raise OwnerError("Each picture has to be under 20 MB.")
            digest = hashlib.sha256(data).hexdigest()
            if digest in [f["sha256"] for f in sess["frames"]]:
                raise OwnerError("That picture was already sent. Each step needs a new one.")
            os.makedirs(sess["dir"], mode=0o700, exist_ok=True)
            raw = os.path.join(sess["dir"], "incoming.bin")
            path = os.path.join(sess["dir"], "%02d.png" % sess["next"])
            try:
                with open(os.open(raw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
                    f.write(data)
                try:
                    self.to_png(raw, path)
                except Exception:
                    raise OwnerError("That is not a picture.")
                os.chmod(path, 0o600)
                age = self.age_check(path)
                faces = age.get("faces") if isinstance(age, dict) else None
                if isinstance(faces, int) and faces >= 2:
                    self._end(sid)
                    raise OwnerError("More than one face was in the picture, so the capture was stopped. "
                                     "Enrolment is for one person, alone in front of the camera.")
                if not isinstance(age, dict) or age.get("status") != "ok" or faces != 1:
                    raise OwnerError("The age check did not clear that picture, so it was not kept.")
                try:
                    seen = self.faces.inspect(path, row["step"])
                except face_check.FaceUnavailable as exc:
                    raise OwnerError(str(exc))
                if seen["faces"] >= 2:
                    self._end(sid)
                    raise OwnerError("More than one face was in the picture, so the capture was stopped. "
                                     "Enrolment is for one person, alone in front of the camera.")
                if seen["faces"] != 1 or not seen["embedding"]:
                    raise OwnerError("No single clear face was found in that picture, so it was not kept.")
                if not seen["step_ok"]:
                    raise OwnerError("That picture does not show the step that was asked, so it was not kept.")
            except OwnerError:
                if os.path.exists(path):
                    os.remove(path)
                raise
            finally:
                if os.path.exists(raw):
                    os.remove(raw)
            sess["frames"].append({"file": os.path.basename(path), "sha256": digest, "step": row["step"],
                                   "embedding": seen["embedding"], "age_check": "ok", "at": time.time()})
            sess["next"] += 1
            sess["opened"] = time.time()
            done = sess["next"] >= len(sess["plan"])
            return {"done": done, "next": None if done else sess["next"],
                    "nonce": None if done else sess["plan"][sess["next"]]["nonce"]}

    def commit(self, sid):
        """Close the session. Only now is the person enrolled: the match set and owner.json are written."""
        with self.lock:
            sess = self._session(sid)
            if sess.get("purpose") != "live" and enrolled(self.out):
                self._end(sid)
                raise OwnerError(ONE_PERSON)
            if sess["next"] < len(sess["plan"]):
                raise OwnerError("The plan is not finished: %d of %d steps have a picture."
                                 % (sess["next"], len(sess["plan"])))
            if sess.get("purpose") == "live":
                return self._commit_live(sid, sess)
            vectors = [f["embedding"] for f in sess["frames"]]
            centre = face_check.centroid(vectors)
            scores = [face_check.cosine(v, centre) for v in vectors]
            if min(scores) < max(self.faces.threshold, face_check.MIN_MATCH):
                self._end(sid)
                raise OwnerError("The pictures do not all show the same face, so nothing was saved.")
            # A posted picture with the right nonce is not proof of a camera. The face check has to say the
            # whole capture was a live person; no answer, or any answer but "live", saves nothing.
            try:
                live, _why = self.faces.liveness([{"path": os.path.join(sess["dir"], f["file"]), "step": f["step"]}
                                                  for f in sess["frames"]])
            except face_check.FaceUnavailable as exc:
                self._end(sid)
                raise OwnerError(str(exc) + " Nothing was saved.")
            if live is not True:
                self._end(sid)
                raise OwnerError("The live check did not pass, so nothing was saved. Enrolment needs you, live, "
                                 "in front of this computer's camera.")
            folder = ensure_private_folder(self.out)
            owner_id = secrets.token_hex(16)
            _write_private(os.path.join(folder, "match_set.json"), {
                "owner_id": owner_id, "model": self.faces.model, "threshold": max(self.faces.threshold, face_check.MIN_MATCH),
                "centroid": centre, "count": len(vectors), "session": sid, "liveness": self.faces.liveness_kind,
                # Numbers only, kept so the threshold can be tuned after the first real run.
                "scores": {"min": round(min(scores), 4), "mean": round(sum(scores) / len(scores), 4)}})
            _write_private(os.path.join(sess["dir"], "session.json"), {
                "owner_id": owner_id, "session": sid, "stated_age": sess["stated_age"], "model": self.faces.model,
                "liveness": self.faces.liveness_kind,
                "frames": [{k: f[k] for k in ("file", "sha256", "step", "age_check", "at")} for f in sess["frames"]]})
            _write_private(_owner_file(self.out), {
                "owner_id": owner_id, "stated_age": sess["stated_age"], "created": time.time(),
                "passphrase": {"kind": "scrypt", "salt": sess["salt"], "hash": sess["hash"],
                               **{k: _SCRYPT[k] for k in ("n", "r", "p")}},
                "capture_session": sid, "frames": len(sess["frames"]), "consent_18": False})
            self._end(sid, remove=False)
            return {"enrolled": True, "frames": len(vectors)}

    def _commit_live(self, sid, sess):
        """Every frame has to be the enrolled face, and the face check has to call the capture live.
        The pictures are deleted either way; only the window (in memory) remains."""
        try:
            ms = match_set(self.out)
            rec = load(self.out)
            if not rec or not ms or ms.get("owner_id") != rec["owner_id"]:
                raise OwnerError("Nobody is enrolled yet.")
            if not all(face_check.matches(f["embedding"], ms, self.faces.model)[0] for f in sess["frames"]):
                raise OwnerError("The live match did not pass: the face is not the enrolled one.")
            try:
                live, _why = self.faces.liveness([{"path": os.path.join(sess["dir"], f["file"]), "step": f["step"]}
                                                  for f in sess["frames"]])
            except face_check.FaceUnavailable as exc:
                raise OwnerError(str(exc))
            if live is not True:
                raise OwnerError("The live match did not pass. It needs you, live, in front of this computer's camera.")
        finally:
            self._end(sid)
        self.window = {"owner_id": rec["owner_id"], "until": time.time() + WINDOW_SECONDS}
        return {"window": True, "seconds": WINDOW_SECONDS}

    # ------------------------------------------------------------------ the 18+ consent record
    def _consent_file(self):
        return os.path.join(owner_dir(self.out), "consent_18.json")

    def _consent_mac(self, key, row):
        body = json.dumps({k: row.get(k) for k in ("owner_id", "at", "statement_sha256")}, sort_keys=True).encode()
        return hmac.new(key, body, hashlib.sha256).hexdigest()

    def consent_valid(self):
        """True only for a record that verifies, is the enrolled owner's, and is for the statement shown today."""
        rec = load(self.out)
        key = _registry_key(self.out)
        try:
            with open(self._consent_file(), encoding="utf-8") as f:
                row = json.load(f)
        except (OSError, ValueError):
            return False
        return bool(rec and key and isinstance(row, dict) and row.get("owner_id") == rec["owner_id"]
                    and row.get("statement_sha256") == hashlib.sha256(CONSENT_STATEMENT.encode()).hexdigest()
                    and secrets.compare_digest(str(row.get("mac") or ""), self._consent_mac(key, row)))

    def adult_live_ok(self):
        """True only when the enrolment was made with a live check that can tell a person from a recording."""
        ms = match_set(self.out)
        return bool(ms and ms.get("liveness") == ADULT_LIVE_KIND)

    def consent_give(self):
        """Off until given. Needs an enrolment made with a real live check, and a live match in the same sitting."""
        rec = load(self.out)
        if not rec:
            raise OwnerError("Nobody is enrolled yet.")
        if not self.adult_live_ok():
            raise OwnerError(ADULT_NEEDS)
        if not self.window_open():
            raise OwnerError("Do the live match first. The 18+ consent is given live, by you, in front of the camera.")
        ensure_private_folder(self.out)
        key = _registry_key(self.out, create=True)
        row = {"owner_id": rec["owner_id"], "at": time.time(),
               "statement_sha256": hashlib.sha256(CONSENT_STATEMENT.encode()).hexdigest()}
        row["mac"] = self._consent_mac(key, row)
        _write_private(self._consent_file(), row)
        return {"consent_18": True}

    def consent_withdraw(self):
        """Needs no live match: stopping is easier than starting. The 18+ likeness pictures are deleted."""
        if os.path.exists(self._consent_file()):
            os.remove(self._consent_file())
        self.window_close()
        return {"consent_18": False, "removed": gallery_remove(self.out, only_area="adult")}

    # ------------------------------------------------------------------ the kill switch
    def remove_everything(self, lora_dir=None):
        """Delete the captures, the match set, the LoRAs, every likeness picture and the records.

        The LoRA hashes are kept in a revoked list outside the folder, so a stray copy stays refused."""
        with self.lock:
            if self.busy:
                raise OwnerError("A likeness job is waiting or running. Let it finish or cancel it, then delete.")
            hashes = {row["sha256"] for row in registry(self.out)}
            for path in private_lora_files(self.out):
                try:
                    hashes.add(file_sha256(path))
                except OSError:
                    pass
            counts = {"loras": len(hashes), "pictures": len(gallery_list(self.out)),
                      # the enrolment frames and the kept photos: both are pictures of him kept as training input
                      "captures": sum(len([f for f in fs if f.endswith(".png")])
                                      for sub in ("captures", "photos")
                                      for _d, _s, fs in os.walk(os.path.join(owner_dir(self.out), sub)))}
            revoked = sorted(revoked_hashes(self.out) | hashes)
            with open(os.path.join(self.out, REVOKED_FILE), "w", encoding="utf-8") as f:
                json.dump(revoked, f)
            counts["copies"] = remove_copies(lora_dir, set(revoked))  # before the folder goes: a link is a copy too
            sweep_engine_links(lora_dir)
            shutil.rmtree(owner_dir(self.out), ignore_errors=True)
            left = [os.path.join(d, f) for d, _s, fs in os.walk(owner_dir(self.out)) for f in fs]
            self.sessions, self.unlocks, self.failures, self.window = {}, {}, [], None
            with open(os.path.join(self.out, REMOVED_FILE), "w", encoding="utf-8") as f:
                json.dump({"at": time.time(), "removed": counts, "left": len(left)}, f)
            return {"removed": counts, "left": len(left)}

    # ------------------------------------------------------------------ unlock
    def unlock(self, passphrase):
        now = time.time()
        with self.lock:
            self.failures = [t for t in self.failures if now - t < FRESH_SECONDS]
            if len(self.failures) >= 5:
                raise OwnerError("Too many wrong tries. Wait a few minutes and try again.")
            rec = load(self.out)
            stored = (rec or {}).get("passphrase") or {}
            if not rec or not stored.get("salt"):
                raise OwnerError("Nobody is enrolled yet.")
            good = isinstance(passphrase, str) and secrets.compare_digest(_hash(passphrase, stored["salt"]), stored["hash"])
            if not good:
                self.failures.append(now)
                raise OwnerError("That passphrase is not right.")
            token = secrets.token_urlsafe(32)
            self.unlocks = {k: v for k, v in self.unlocks.items() if v > now}
            self.unlocks[hashlib.sha256(token.encode()).hexdigest()] = now + FRESH_SECONDS
            return token

    def unlocked(self, token):
        if not token:
            return False
        return self.unlocks.get(hashlib.sha256(str(token).encode()).hexdigest(), 0) > time.time()

    def relock(self, token=None):
        with self.lock:
            if token:
                self.unlocks.pop(hashlib.sha256(str(token).encode()).hexdigest(), None)
            else:
                self.unlocks.clear()
