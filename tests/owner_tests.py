# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The owner's own likeness, slice 1: enrolment by the app's camera, the one-person lock, the Host check.

No camera, no face model and no real person: the pictures are drawn here, the face check and the
backup tool are stand-ins under tests/, and the passphrase is an obviously made-up test value.
"""
import io
import json
import os
import stat
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

# Stand-ins for the whole test run, set before the test server starts so it inherits them.
_STATE = os.path.join(tempfile.mkdtemp(prefix="es_owner_"), "excluded.json")
os.environ["FAKE_TMUTIL_STATE"] = _STATE
os.environ["EASY_STUDIO_TEST_RUN"] = "1"  # the overrides below are honoured in a test run only
os.environ["EASY_STUDIO_BACKUP_TOOL"] = os.path.join(HERE, "fake_tmutil.py")
os.environ["EASY_STUDIO_FACE_WORKER"] = os.path.join(HERE, "fake_face_worker.py")
os.environ["FAKE_FACE_INJECT"] = _STATE + ".face"

import face_check  # noqa: E402
import owner as O  # noqa: E402
import safety  # noqa: E402

PASSPHRASE = "test-passphrase-not-a-secret"
OWNER_FACE, OTHER_FACE = 100, 200


def frame(step, n=0, person=OWNER_FACE, faces=1, corner=None, replay=False):
    """A drawn stand-in for one camera frame. The codes are read by the two test workers."""
    im = Image.new("RGB", (96, 120), (40 + n * 7 % 200, 90, 140))
    draw = ImageDraw.Draw(im)
    draw.ellipse([28, 20, 68, 70], fill=(230, 190, 170))
    if corner:
        draw.rectangle([0, 0, 15, 15], fill=corner)  # the age stand-in reads this corner
    code = (person, (face_check.STEPS.index(step) + 1) * 40 if step in face_check.STEPS else 0, faces * 60)
    draw.rectangle([80, 104, 95, 119], fill=code)   # the face stand-in reads this one
    if replay:
        draw.rectangle([0, 104, 15, 119], fill=(7, 7, 7))  # the face stand-in's "this is a replay" code
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _age(path):
    """The age check's answer, as the fake age worker gives it, plus one code for 'two faces'."""
    with Image.open(path) as im:
        c = im.convert("RGB").getpixel((4, 4))
    if c == (255, 0, 255):
        return {"status": "flag", "faces": 1, "p_under21": 0.93}
    if c == (1, 2, 3):
        return {"status": "unchecked", "faces": 0}
    if c == (9, 9, 9):
        return {"status": "ok", "faces": 2, "p_under21": 0.04}
    return {"status": "ok", "faces": 1, "p_under21": 0.04}


def _owner(out, checker_on=True):
    import assets
    return O.Owner(out, face_check.FaceCheck(), _age, lambda: checker_on, safety.require_stated_age, assets.to_png)


def _refused(fn):
    try:
        fn()
    except O.OwnerError as exc:
        return str(exc)
    return ""


def _files(folder):
    return sorted(os.path.relpath(os.path.join(d, f), folder) for d, _s, fs in os.walk(folder) for f in fs)


def _run_plan(o, got, person=OWNER_FACE, upto=None):
    nonce = got["nonce"]
    for row in got["plan"][:upto]:
        back = o.frame(got["session"], row["index"], nonce, frame(row["step"], row["index"], person))
        nonce = back["nonce"]
    return nonce


def unit(check):
    print("\n[owner] Enrolment by camera: one person, age-checked frames, nothing saved on a failed try")
    # With nothing installed, the default worker says so and enrolment refuses.
    kept = os.environ.pop("EASY_STUDIO_FACE_WORKER")
    try:
        bare = face_check.FaceCheck()
        check("with no face model installed, the face check is not available", bare.available() is False)
        out0 = tempfile.mkdtemp(prefix="es_owner_out_")
        import assets
        o0 = O.Owner(out0, bare, _age, lambda: True, safety.require_stated_age, assets.to_png)
        said = _refused(lambda: o0.start(32, PASSPHRASE))
        check("then enrolment refuses to start, and writes nothing", "not installed" in said and not os.path.exists(O.owner_dir(out0)), said)
    finally:
        os.environ["EASY_STUDIO_FACE_WORKER"] = kept

    out = tempfile.mkdtemp(prefix="es_owner_out_")
    o = _owner(out)
    check("the appearance checker off refuses the start", "checker is off" in _refused(lambda: _owner(out, False).start(32, PASSPHRASE)))
    check("a stated age of 20 refuses the start", "under 21" in _refused(lambda: o.start(20, PASSPHRASE)).lower())
    check("no stated age refuses the start", "missing" in _refused(lambda: o.start(None, PASSPHRASE)).lower())
    check("a short passphrase refuses the start", "passphrase" in _refused(lambda: o.start(32, "short")))
    open(_STATE + ".fail", "w").close()
    try:
        said = _refused(lambda: o.start(32, PASSPHRASE))
        check("when the folder cannot be kept out of backups, the start refuses and nothing is saved",
              "out of backups" in said and _files(O.owner_dir(out)) == [], (said, _files(O.owner_dir(out))))
    finally:
        os.remove(_STATE + ".fail")

    got = o.start(32, PASSPHRASE)
    steps = [row["step"] for row in got["plan"]]
    check("the plan has twelve steps in a mixed order with every pose in it",
          len(steps) == O.PLAN_STEPS and set(steps) == set(face_check.STEPS), steps)
    check("the folder was kept out of backups before any picture was saved",
          os.path.abspath(O.owner_dir(out)) in json.load(open(_STATE)) and _files(O.owner_dir(out)) == [])
    check("a second capture session cannot start while one is open", "already under way" in _refused(lambda: o.start(32, PASSPHRASE)))
    first = got["plan"][0]
    wrong = next(s for s in face_check.STEPS if s != first["step"])
    check("a picture with the wrong nonce is refused", "does not belong" in _refused(lambda: o.frame(got["session"], 0, "0" * 16, frame(first["step"]))))
    check("a picture for a later step is refused", "does not belong" in _refused(lambda: o.frame(got["session"], 3, got["nonce"], frame(first["step"]))))
    check("a file that is not a picture is refused", "not a picture" in _refused(lambda: o.frame(got["session"], 0, got["nonce"], b"not an image")))
    check("a picture that shows another step is refused", "step that was asked" in _refused(lambda: o.frame(got["session"], 0, got["nonce"], frame(wrong))))
    check("a picture the age check flags is refused", "age check" in _refused(
        lambda: o.frame(got["session"], 0, got["nonce"], frame(first["step"], corner=(255, 0, 255)))))
    check("a picture the age check cannot read is refused", "age check" in _refused(
        lambda: o.frame(got["session"], 0, got["nonce"], frame(first["step"], corner=(1, 2, 3)))))
    check("a picture with no face is refused", "No single clear face" in _refused(
        lambda: o.frame(got["session"], 0, got["nonce"], frame(first["step"], faces=0))))
    check("none of the refused pictures was kept", _files(O.owner_dir(out)) == [], _files(O.owner_dir(out)))
    back = o.frame(got["session"], 0, got["nonce"], frame(first["step"], 0))
    check("the right picture for the step is kept, and the next step opens", back["done"] is False and back["next"] == 1)
    check("the same picture twice is refused", "already sent" in _refused(
        lambda: o.frame(got["session"], 1, back["nonce"], frame(first["step"], 0))))
    check("finishing early is refused", "not finished" in _refused(lambda: o.commit(got["session"])))
    said = _refused(lambda: o.frame(got["session"], 1, back["nonce"], frame(got["plan"][1]["step"], 1, faces=2)))
    check("two faces in a picture stop the whole capture", "More than one face" in said, said)
    check("after that the session is gone, its pictures are deleted, and nobody is enrolled",
          "not open" in _refused(lambda: o.commit(got["session"])) and _files(O.owner_dir(out)) == [] and not O.enrolled(out))

    got = o.start(32, PASSPHRASE)
    said = _refused(lambda: o.frame(got["session"], 0, got["nonce"], frame(got["plan"][0]["step"], corner=(9, 9, 9))))
    check("two faces seen by the age check stop the capture too", "More than one face" in said and got["session"] not in o.sessions, said)

    got = o.start(32, PASSPHRASE)
    nonce = _run_plan(o, got, upto=6)
    for row in got["plan"][6:]:
        nonce = o.frame(got["session"], row["index"], nonce, frame(row["step"], row["index"], OTHER_FACE))["nonce"]
    said = _refused(lambda: o.commit(got["session"]))
    check("pictures of two different faces are not enrolled, and nothing is saved",
          "same face" in said and not O.enrolled(out) and _files(O.owner_dir(out)) == [], (said, _files(O.owner_dir(out))))

    # Posted pictures with the right nonces and steps are not enough: the capture needs the live verdict.
    got = o.start(32, PASSPHRASE)
    nonce = _run_plan(o, got, upto=O.PLAN_STEPS - 1)
    last = got["plan"][-1]
    o.frame(got["session"], last["index"], nonce, frame(last["step"], last["index"], replay=True))
    said = _refused(lambda: o.commit(got["session"]))
    check("a capture the face check does not call live enrols nobody and saves nothing",
          "live check did not pass" in said and not O.enrolled(out) and _files(O.owner_dir(out)) == [], (said, _files(O.owner_dir(out))))
    got = o.start(32, PASSPHRASE)
    _run_plan(o, got)
    os.environ["FAKE_FACE_NO_VERDICT"] = _STATE + ".noverdict"
    o.faces.stop()  # the worker reads the setting when it starts
    open(_STATE + ".noverdict", "w").close()
    try:
        said = _refused(lambda: o.commit(got["session"]))
    finally:
        os.remove(_STATE + ".noverdict")
    check("a face check that gives no live verdict enrols nobody and saves nothing",
          "Nothing was saved" in said and not O.enrolled(out) and _files(O.owner_dir(out)) == [], (said, _files(O.owner_dir(out))))
    for kind in ("none", "liveness-magic", ""):
        os.environ["FAKE_FACE_LIVENESS"] = kind
        try:
            fresh = _owner(out)
            got = fresh.start(32, PASSPHRASE)
            _run_plan(fresh, got)
            said = _refused(lambda: fresh.commit(got["session"]))
        finally:
            os.environ.pop("FAKE_FACE_LIVENESS", None)
        check("a live verdict of a kind the app does not accept ('%s') enrols nobody and saves nothing" % (kind or "empty"),
              "not one the app accepts" in said and "Nothing was saved" in said and not O.enrolled(out) and _files(O.owner_dir(out)) == [], (said, _files(O.owner_dir(out))))
        fresh.faces.stop()
    check("the accepted kinds are the pose-only verdict and a real presentation-attack check, nothing else",
          face_check.ACCEPTED_LIVENESS == ("poses_only", "pad"))

    got = o.start(32, PASSPHRASE)
    o.sessions[got["session"]]["opened"] -= O.STEP_SECONDS + 1
    said = _refused(lambda: o.frame(got["session"], 0, got["nonce"], frame(got["plan"][0]["step"])))
    check("a step that ran out of time ends the session", "ran out of time" in said and got["session"] not in o.sessions, said)
    check("a failed try never locks the app: nobody is enrolled", not O.enrolled(out) and O.load(out) is None)

    got = o.start(32, PASSPHRASE)
    _run_plan(o, got)
    done = o.commit(got["session"])
    record = O.load(out)
    text = open(os.path.join(O.owner_dir(out), "owner.json"), encoding="utf-8").read()
    check("a full plan of one face enrols the owner", done == {"enrolled": True, "frames": O.PLAN_STEPS} and O.enrolled(out))
    check("the record holds the stated age and a salted hash, never the passphrase",
          record["stated_age"] == 32 and record["passphrase"]["kind"] == "scrypt" and PASSPHRASE not in text
          and len(record["passphrase"]["hash"]) == 64)
    check("the 18+ consent is off in a new record", record.get("consent_18") is False)
    kept = _files(O.owner_dir(out))
    check("twelve pictures, their record, the match set and the owner record are the only files",
          len([f for f in kept if f.endswith(".png")]) == O.PLAN_STEPS and "owner.json" in kept and "match_set.json" in kept
          and len(kept) == O.PLAN_STEPS + 3, kept)
    modes = {stat.S_IMODE(os.stat(os.path.join(O.owner_dir(out), f)).st_mode) for f in kept}
    check("the folder and every file in it are readable by this account only",
          modes == {0o600} and stat.S_IMODE(os.stat(O.owner_dir(out)).st_mode) == 0o700, modes)
    check("the one-person lock: a second enrolment is refused", O.ONE_PERSON == _refused(lambda: o.start(40, PASSPHRASE)))
    check("a new app object still sees the lock", O.ONE_PERSON == _refused(lambda: _owner(out).start(40, PASSPHRASE)))

    ms = O.match_set(out)
    same = o.faces.inspect(_save(frame("face_camera", 77)), "face_camera")["embedding"]
    other = o.faces.inspect(_save(frame("face_camera", 78, OTHER_FACE)), "face_camera")["embedding"]
    model = o.faces.model
    check("the match set matches the enrolled face", face_check.matches(same, ms, model)[0] is True)
    check("the match set does not match another face", face_check.matches(other, ms, model)[0] is False)
    check("no match set is never a match", face_check.matches(same, None, model)[0] is False and face_check.matches([], ms, model)[0] is False)
    check("another model, or no model name, is never a match: the numbers mean nothing for it",
          face_check.matches(same, ms, "another-model")[0] is False and face_check.matches(same, ms, None)[0] is False
          and face_check.matches(same, ms, "")[0] is False)
    check("the match set names the worker's threshold (never under the floor) and keeps numeric scores only",
          ms["threshold"] == max(o.faces.threshold, face_check.MIN_MATCH) and set(ms["scores"]) == {"min", "mean"}
          and all(isinstance(v, float) for v in ms["scores"].values()), ms)
    score = face_check.matches(other, dict(ms, threshold=0.0001), model)[1]
    check("a stored threshold under the published floor is raised to it (the other face scores between the two)",
          0.0001 < score < face_check.MIN_MATCH and face_check.matches(other, dict(ms, threshold=0.0001), model)[0] is False, score)

    check("a wrong passphrase does not unlock", "not right" in _refused(lambda: o.unlock("wrong-test-value")))
    token = o.unlock(PASSPHRASE)
    check("the right passphrase unlocks for a short time", o.unlocked(token) and not o.unlocked("made-up") and not o.unlocked(None))
    o.unlocks = {k: 0 for k in o.unlocks}
    check("an unlock runs out", not o.unlocked(token))
    token = o.unlock(PASSPHRASE)
    o.relock(token)
    check("locking ends the unlock", not o.unlocked(token))
    for _ in range(5):
        _refused(lambda: o.unlock("wrong-test-value"))
    check("five wrong tries stop further tries for a while, the right passphrase included",
          "Too many" in _refused(lambda: o.unlock(PASSPHRASE)))
    o.faces.stop()


def _save(data):
    fd, path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def e2e(a, out):
    import requests
    check = a.check
    print("\n[owner] Enrolment through the app, the Host check, and no way in by upload")
    head = {"X-Easy-Studio": "1"}
    for host, want in (("evil.example", 403), ("127.0.0.1.evil.example:80", 403), ("localhost:9", 200), ("127.0.0.1", 200), ("[::1]:7860", 200)):
        got = requests.get(a.base + "/api/status", headers={**head, "Host": host}, timeout=30)
        check("a request that names '%s' as the host gets %d" % (host, want), got.status_code == want, got.status_code)
    blocked = requests.get(a.base + "/api/owner/status", headers={**head, "Host": "evil.example"}, timeout=30)
    check("the owner routes refuse another host name too", blocked.status_code == 403 and "own address" in blocked.text, blocked.text[:200])
    page = requests.get(a.base + "/", headers={"Host": "evil.example"}, timeout=30)
    check("the page itself is not served under another host name", page.status_code == 403)

    st = a.get("/api/owner/status").json()
    check("the owner status says: nobody enrolled, a capture session with a live check",
          st["enrolled"] is False and "live check" in st["how"] and st["face_check"] is True and st["unlocked"] is False, st)
    minted = a.upload(Image.open(io.BytesIO(frame("face_camera"))), "owner_capture", age=32)
    check("the general upload route cannot make an owner capture", minted.status_code == 400, minted.text[:200])
    loose = a.post("/api/owner/enrol/frame", files={"file": ("me.png", frame("face_camera"), "image/png")},
                   data={"session": "", "index": "0", "nonce": ""})
    check("a picture sent outside a capture session is refused", loose.status_code == 400 and "not open" in loose.text, loose.text[:200])
    made_up = a.post("/api/owner/enrol/frame", files={"file": ("me.png", frame("face_camera"), "image/png")},
                     data={"session": "ab" * 16, "index": "0", "nonce": "cd" * 8})
    check("a picture for a made-up session is refused", made_up.status_code == 400)
    check("a stated age of 20 is refused at the start", a.post("/api/owner/enrol/start", json={"age": 20, "passphrase": PASSPHRASE}).status_code == 400)
    check("nothing is saved by the refused tries", _files(O.owner_dir(out)) == [], _files(O.owner_dir(out)))

    got = a.post("/api/owner/enrol/start", json={"age": 32, "passphrase": PASSPHRASE})
    check("enrolment starts with a stated age and a passphrase", got.status_code == 200 and len(got.json()["plan"]) == O.PLAN_STEPS, got.text[:300])
    plan, nonce, sid = got.json()["plan"], got.json()["nonce"], got.json()["session"]
    flagged = a.post("/api/owner/enrol/frame", files={"file": ("f.png", frame(plan[0]["step"], corner=(255, 0, 255)), "image/png")},
                     data={"session": sid, "index": "0", "nonce": nonce})
    check("a frame the age check flags is refused through the app", flagged.status_code == 400 and "age check" in flagged.text, flagged.text[:200])
    ok = True
    for row in plan:
        back = a.post("/api/owner/enrol/frame", files={"file": ("f.png", frame(row["step"], row["index"]), "image/png")},
                      data={"session": sid, "index": str(row["index"]), "nonce": nonce})
        ok = ok and back.status_code == 200
        nonce = back.json().get("nonce") if back.status_code == 200 else nonce
    done = a.post("/api/owner/enrol/commit", json={"session": sid})
    check("twelve camera frames of one face enrol the owner", ok and done.status_code == 200 and done.json().get("enrolled") is True, done.text[:300])
    again = a.post("/api/owner/enrol/start", json={"age": 40, "passphrase": PASSPHRASE})
    check("a second enrolment is refused by the server", again.status_code == 400 and "one enrolled person" in again.text, again.text[:200])
    check("the likeness folder is marked as kept out of backups", os.path.abspath(O.owner_dir(out)) in json.load(open(_STATE)))

    for path in ("/files/owner/owner.json", "/files/..%2Fowner%2Fowner.json", "/files/%2e%2e/owner/owner.json",
                 "/files/../owner/match_set.json", "/static/..%2F..%2Foutputs%2Fowner%2Fowner.json"):
        got = requests.get(a.base + path, headers=head, timeout=30)
        check("no file link serves the likeness folder (%s)" % path, got.status_code in (403, 404) and "passphrase" not in got.text, got.status_code)
    items = a.get("/api/gallery", params={"limit": 2000}).json()["items"]
    check("no capture is a gallery item", not [row["id"] for row in items if "owner" in str(row.get("file") or "") or row.get("role") == "owner_capture"])

    bad = a.post("/api/owner/unlock", json={"passphrase": "wrong-test-value"})
    check("a wrong passphrase does not unlock through the app", bad.status_code == 400 and PASSPHRASE not in bad.text)
    good = a.post("/api/owner/unlock", json={"passphrase": PASSPHRASE})
    cookie = good.headers.get("set-cookie", "")
    check("the right passphrase unlocks, with a cookie scripts cannot read",
          good.status_code == 200 and "es_owner=" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie.replace("Strict", "strict"), cookie[:120])
    check("the status then says unlocked", a.get("/api/owner/status").json()["unlocked"] is True)
    a.post("/api/owner/lock")
    check("and locked again after Lock", a.get("/api/owner/status").json()["unlocked"] is False)
    log = open(os.path.join(out, "server.log"), encoding="utf-8", errors="replace").read()
    saved = open(os.path.join(O.owner_dir(out), "owner.json"), encoding="utf-8").read()
    check("the passphrase is in no log and no saved file", PASSPHRASE not in log and PASSPHRASE not in saved)
