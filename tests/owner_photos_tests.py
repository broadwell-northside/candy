"""Add photos (D-C-54): the owner's own photos from disk, kept only if they show the enrolled person.

unit(check)  -- run from run_tests.py: the rules, on the stand-in face check and age check (no model, no real photo).
python tests/owner_photos_tests.py -- the page's whole-folder add against canned answers.
The pictures are drawn stand-ins (tests/owner_tests.py frame()); no photo of anyone is read anywhere in these tests."""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))

import owner_tests as OT  # noqa: E402  (sets the stand-in face worker and backup tool for a test run)
from owner_tests import OTHER_FACE, OWNER_FACE, PASSPHRASE, _age, _files, _owner, _run_plan, frame  # noqa: E402


def _enrolled(out):
    o = _owner(out)
    got = o.start(32, PASSPHRASE)
    _run_plan(o, got)
    o.commit(got["session"])
    return o


def unit(check):
    print("\n[photos] Add photos: kept only if exactly one face, the enrolled face, and a clear age check")
    import owner as O
    import owner_photos as P
    import owner_train as OTR
    import pipelines
    out = tempfile.mkdtemp(prefix="es_photos_")
    try:
        o = _owner(out)
        try:
            P.add_photo(o, frame("face_camera", 1))
            said = ""
        except O.OwnerError as exc:
            said = str(exc)
        check("before anyone is enrolled a photo is refused with a plain message", "Nobody is enrolled" in said and not P.count(out), said)
        o = _enrolled(out)
        off = _owner(out, checker_on=False)
        try:
            P.add_photo(off, frame("face_camera", 2))
            said = ""
        except O.OwnerError as exc:
            said = str(exc)
        check("with the appearance checker off a photo is refused", "checker is off" in said and not P.count(out), said)

        mine = P.add_photo(o, frame("face_camera", 3, OWNER_FACE))
        check("a photo of the enrolled face, one face, a clear age check: kept", mine["kept"] is True and mine["reason"] == "" and P.count(out) == 1, mine)
        row = P.records(out)[0]
        path = os.path.join(P.photos_dir(out), row["file"])
        check("it is a private file under outputs/owner, with the same mark as the captures, and no embedding is stored",
              os.path.isfile(path) and oct(os.stat(path).st_mode & 0o777) == "0o600" and row["owner_likeness"] is True
              and row["owner_id"] == O.load(out)["owner_id"] and row["age_check"] == "ok" and "embedding" not in json.dumps(row)
              and path.startswith(O.owner_dir(out)), row)
        check("a kept photo is not a library item, so no picture job can take it as an input",
              not os.path.exists(os.path.join(out, "items")) or not any(row["file"] in f for _d, _s, fs in os.walk(os.path.join(out, "items")) for f in fs))

        cases = [
            ("another person's face", frame("face_camera", 4, OTHER_FACE), "no_match", "doesn't show the enrolled person"),
            ("two faces (the face check counts them)", frame("face_camera", 5, OWNER_FACE, faces=2), "two_faces", "more than one face"),
            ("two faces (the age check counts them)", frame("face_camera", 6, OWNER_FACE, corner=(9, 9, 9)), "two_faces", "more than one face"),
            ("no face", frame("face_camera", 7, OWNER_FACE, faces=0), "no_face", "no single clear face"),
            ("a flagged photo", frame("face_camera", 8, OWNER_FACE, corner=(255, 0, 255)), "flagged", "flagged"),
            ("an age check that cannot clear it", frame("face_camera", 9, OWNER_FACE, corner=(1, 2, 3)), "age_not_cleared", "could not clear"),
            ("something that is not a picture", b"not a picture at all", "not_a_picture", "not a picture"),
        ]
        before = _files(O.owner_dir(out))
        for label, data, reason, words in cases:
            got = P.add_photo(o, data)
            check("%s: dropped (%s), with a plain reason" % (label, reason), got["kept"] is False and got["reason"] == reason and words in got["message"], got)
        check("none of them left a file, a record or an embedding behind", _files(O.owner_dir(out)) == before and P.count(out) == 1, _files(O.owner_dir(out)))
        other = P.add_photo(o, frame("face_camera", 10, OTHER_FACE))
        check("a photo that did not match carries its match score, a number only, so the threshold can be tuned",
              isinstance(other.get("score"), float) and 0 <= other["score"] < 1 and "embedding" not in json.dumps(other), other)
        again = P.add_photo(o, frame("face_camera", 3, OWNER_FACE))
        check("the same photo twice is dropped as already added", again["kept"] is False and again["reason"] == "duplicate" and P.count(out) == 1, again)
        check("every reason code the module can give has plain words", all(P.REASON_WORDS.get(r) for r in ("no_match", "no_face", "two_faces", "flagged", "age_not_cleared", "duplicate", "not_a_picture")))

        # the limit, and the order of the checks: a flagged photo is final whatever else is true
        old_max, P.MAX_PHOTOS = P.MAX_PHOTOS, 2
        try:
            P.add_photo(o, frame("turn_left", 11, OWNER_FACE))
            try:
                P.add_photo(o, frame("turn_right", 12, OWNER_FACE))
                said = ""
            except O.OwnerError as exc:
                said = str(exc)
        finally:
            P.MAX_PHOTOS = old_max
        check("past the limit a photo is refused with a plain message", "already" in said and P.count(out) == 2, said)

        # training takes the enrolment pictures plus the kept photos, each checked against its record
        rec = O.load(out)
        items = OTR.capture_set(out, rec)
        check("training takes the enrolment pictures plus the kept photos", len(items) == O.PLAN_STEPS + 2, len(items))
        victim = os.path.join(P.photos_dir(out), P.records(out)[0]["file"])
        open(victim, "ab").write(b"changed")
        try:
            OTR.capture_set(out, rec)
            said = ""
        except pipelines.UserError as exc:
            said = str(exc)
        check("a kept photo that was changed afterwards stops training with a plain message", "changed or removed" in said, said)
        removed = P.remove_all(out)
        check("Remove my added photos deletes every kept photo and its record", removed == 2 and P.count(out) == 0 and not P.records(out), removed)
        P.add_photo(o, frame("face_camera", 20, OWNER_FACE))
        done = o.remove_everything(None)
        check("the kill switch deletes the kept photos with everything else, and counts them with the captures",
              not os.path.exists(P.photos_dir(out)) and done["removed"]["captures"] == O.PLAN_STEPS + 1 and done["left"] == 0, done)
        o.faces.stop()
    finally:
        shutil.rmtree(out, ignore_errors=True)
    src = open(os.path.join(os.path.dirname(HERE), "app", "static", "owner_photos.js"), encoding="utf-8").read()
    check("the page has a folder picker and a file picker, a per-photo list, a Stop button, and shows no picture",
          "webkitdirectory" in src and "ownerPhotosList" in src and "ownerPhotosStop" in src and "createElement(\"img\")" not in src
          and 'h("img"' not in src and "URL.createObjectURL" not in src)
    routes = open(os.path.join(os.path.dirname(HERE), "app", "routes_owner_photos.py"), encoding="utf-8").read()
    check("every Add photos route needs the passphrase unlock", routes.count("need_unlock(request)") >= 3)


def browser():
    from playwright.sync_api import sync_playwright
    from e2e_browser import World
    results = []

    def check(name, cond, detail=""):
        results.append(bool(cond))
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else "  -- %s" % str(detail)[:300]))

    world = World()
    folder = tempfile.mkdtemp(prefix="es_photos_dir_")
    try:
        for name in ("a.jpg", "b.png", "c.jpg", "d.HEIC", ".DS_Store", "notes.txt"):
            open(os.path.join(folder, name), "wb").write(b"x" * 20)
        with sync_playwright() as p:
            exe = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            try:
                b = p.chromium.launch(headless=True)
            except Exception:
                b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None, headless=True)
            page = b.new_page(viewport={"width": 1200, "height": 1000})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            sent = []
            answers = {"a.jpg": {"kept": True, "message": "Photo added.", "reason": "", "score": 0.71},
                       "b.png": {"kept": False, "message": "that photo doesn't show the enrolled person", "reason": "no_match", "score": 0.31},
                       "c.jpg": {"kept": False, "message": "more than one face is in it", "reason": "two_faces", "score": None}}

            def ans(route, body, status=200):
                route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

            def owner_routes(route, request):
                path = request.url.split("/api/owner/")[1].split("?")[0]
                if path == "status":
                    return ans(route, {"enrolled": True, "checker_on": True, "face_check": True, "face_check_message": "", "steps": 12, "min_passphrase": 10,
                                       "unlocked": True, "consent_18": False, "window_open": False, "how": "By camera."})
                if path == "trainer":
                    return ans(route, {"trainer_installed": True, "device": "mps", "selftest_passed": True, "likeness_loras": 0})
                if path == "photos" and request.method == "POST":
                    body = request.post_data_buffer or b""
                    name = next((n for n in answers if n.encode() in body), "")
                    sent.append(name)
                    return ans(route, dict(answers[name], count=len(sent)))
                return route.continue_()

            page.route("**/api/owner/**", owner_routes)
            page.route("**/api/phase_two", lambda r, q: ans(r, {"hidden": False}))
            page.goto(world.base + "/#/setup", wait_until="domcontentloaded")
            page.reload()
            page.wait_for_selector("#ownerPhotosBtn", timeout=20000)
            check("an enrolled owner sees an Add photos step between Enrol and Train", page.locator("#ownerSteps button").all_inner_texts()[:3] == ["1 Enrol ✓", "Add photos", "2 Train"],
                  page.locator("#ownerSteps button").all_inner_texts())
            page.click("#ownerPhotosBtn")
            check("it says in plain words what is kept and that photos stay on this Mac",
                  "exactly one face" in page.inner_text("#ownerPhotosWords") and "stay on this Mac" in page.inner_text("#ownerPhotosWords"))
            page.set_input_files("#ownerPhotoFolder", folder)
            page.click("#ownerPhotoAdd")
            page.wait_for_function("() => document.querySelector('#ownerSay').innerText.includes('kept')", timeout=20000)
            rows = page.locator("#ownerPhotosList li").all_inner_texts()
            check("a folder is added as a whole: only the JPEG and PNG files are sent, one at a time", sorted(sent) == ["a.jpg", "b.png", "c.jpg"], sent)
            check("each photo gets a plain result: kept, or dropped with its reason and match score",
                  any(r.endswith("a.jpg — kept") or "a.jpg — kept" in r for r in rows) and any("b.png — dropped: that photo doesn't show the enrolled person (match 0.31)" in r for r in rows)
                  and any("c.jpg — dropped: more than one face is in it" in r for r in rows), rows)
            check("a HEIC file is listed as not read, with the way out, and is never sent", any("d.HEIC — not read" in r and "JPEG" in r for r in rows) and "d.HEIC" not in sent, rows)
            check("the totals line counts kept, dropped and not read, and says other files were left alone",
                  "1 kept, 2 dropped, 1 not read" in page.inner_text("#ownerSay") and "2 other files" in page.inner_text("#ownerPhotosTotals"),
                  (page.inner_text("#ownerSay"), page.inner_text("#ownerPhotosTotals")))
            check("no picture is shown on the page", page.locator("#ownerPhotosList img, #ownerPanel img").count() == 0)
            b.close()
        check("no JavaScript errors", not errors, errors[:3])
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        world.close()
    bad = results.count(False)
    print("\n%d/%d Add photos page checks passed" % (len(results) - bad, len(results)))
    return bad == 0


if __name__ == "__main__":
    ok = True
    n, fails = [0], []

    def check(name, cond, detail=""):
        n[0] += 1
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else "  -- %s" % str(detail)[:300]))
        if not cond:
            fails.append(name)

    unit(check)
    ok = not fails and browser()
    sys.exit(0 if ok else 1)
