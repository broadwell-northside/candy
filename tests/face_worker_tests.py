"""The real face worker (app/workers/face_worker.py) and its rules (app/workers/face_logic.py).

No model is run. The rules are tested on made-up landmarks. The worker file is run as a program, through the
real FaceCheck, with a stand-in for the few OpenCV calls it makes (tests/stubs/cv2) and tiny made-up model files."""
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "app", "workers"))

import face_check  # noqa: E402
import face_logic as L  # noqa: E402

WORKER = os.path.join(ROOT, "app", "workers", "face_worker.py")
LOCK = os.path.join(ROOT, "config", "server_model_lock.json")


def landmarks(yaw=0.0, roll=0.0, pitch=0.62, scale=100.0, at=(320.0, 240.0)):
    """Five landmarks for a face of the given pose, built the way face_logic reads them."""
    base = [(-0.5, 0.0), (0.5, 0.0), (yaw, pitch), (-0.35, 1.0), (0.35, 1.0)]
    c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    return [(at[0] + scale * (x * c - y * s), at[1] + scale * (x * s + y * c)) for x, y in base]


def vector(person, rng):
    return [(1.0 if i == person else 0.0) + rng.random() * 0.05 for i in range(8)]


def row(step, pose, person=0, rng=None):
    rng = rng or random.Random(1)
    lm = landmarks(**pose)
    return {"step": step, "pose": L.pose(lm), "shape": L.shape(lm), "embedding": vector(person, rng)}


def good_capture(rng, steps=None):
    """A 12-picture capture of one person: every step at least once, each picture a little different."""
    plan = list(steps or (list(L.STEPS) * 3)[:12])
    poses = {"face_camera": dict(yaw=0.02, roll=1.0, pitch=0.62), "turn_left": dict(yaw=0.42, roll=2.0, pitch=0.62),
             "turn_right": dict(yaw=-0.40, roll=-1.0, pitch=0.62), "tilt": dict(yaw=0.03, roll=17.0, pitch=0.62),
             "look_up": dict(yaw=0.04, roll=0.0, pitch=0.40)}
    rows = []
    for i, step in enumerate(plan):
        pose = dict(poses[step])
        pose["yaw"] += (i % 4) * 0.012 - 0.018  # each picture a little different from the others
        pose["at"] = (320 + rng.uniform(-20, 20), 240 + rng.uniform(-20, 20))
        rows.append(row(step, pose, 0, rng))
    return rows


def _verdict(rows):
    return L.verdict(rows, L.THRESHOLD)


def _write_pictures(folder, items):
    """Make picture files and their stand-in sidecars. items: [(name, faces, embedding)] with faces as flat rows."""
    paths = []
    for name, faces, emb in items:
        path = os.path.join(folder, name)
        open(path, "wb").write(b"not a picture, the stand-in reads the sidecar")
        json.dump({"faces": faces, "embedding": emb}, open(path + ".lm.json", "w"))
        paths.append(path)
    return paths


def _face_row(**pose):
    lm = landmarks(**pose)
    return [270, 190, 100, 120] + [v for p in lm for v in p] + [0.95]


def _model_dir(content=True):
    """A folder with two tiny made-up files under the pinned names, and the hashes they have."""
    folder = tempfile.mkdtemp(prefix="es_face_models_")
    hashes = {}
    for key, want in L.MODEL_FILES.items():
        data = (key + " model stand-in").encode() if content else b"wrong"
        open(os.path.join(folder, want["file"]), "wb").write(data)
        hashes[key] = hashlib.sha256((key + " model stand-in").encode()).hexdigest()
    return folder, hashes


def _runner(hashes, with_stub=True):
    """A program that runs the real worker file with test hashes pinned, and the stand-in OpenCV on the path."""
    fd, path = tempfile.mkstemp(prefix="es_face_run_", suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write("import runpy, sys\n")
        if with_stub:
            f.write("sys.path.insert(0, %r)\n" % os.path.join(HERE, "stubs"))
        f.write("sys.path.insert(0, %r)\nimport face_logic as L\n" % os.path.join(ROOT, "app", "workers"))
        for key, h in hashes.items():
            f.write("L.MODEL_FILES[%r] = dict(L.MODEL_FILES[%r], sha256=%r)\n" % (key, key, h))
        f.write("runpy.run_path(%r, run_name='__main__')\n" % WORKER)
    return path


def _check(model_dir, runner=None):
    """A FaceCheck on the worker file (or a runner around it), in a test run."""
    if runner:
        os.environ["EASY_STUDIO_FACE_WORKER"] = runner
    else:
        os.environ.pop("EASY_STUDIO_FACE_WORKER", None)
    return face_check.FaceCheck(python=sys.executable, model_dir=model_dir, timeout=20)


def unit(check):
    print("\n[face] The face worker's rules, and the worker file on a stand-in")
    rng = random.Random(7)

    # --- pose from five landmarks
    ok = True
    for yaw, roll, pitch in ((0, 0, 0.5), (0.3, 10, 0.6), (-0.4, -20, 0.45), (0.05, 35, 0.7)):  # all five kinds of pose
        for scale, at in ((40, (50, 60)), (250, (800, 500))):
            p = L.pose(landmarks(yaw, roll, pitch, scale, at))
            ok = ok and abs(p["yaw"] - yaw) < 1e-6 and abs(p["roll"] - roll) < 1e-6 and abs(p["pitch"] - pitch) < 1e-6
    check("pose is read back from landmarks at any size, place and tilt", ok)
    check("nonsense landmarks give no pose",
          L.pose([(0, 0)] * 5) is None and L.pose([(1, 1)] * 4) is None and L.pose(None) is None
          and L.pose([(float("nan"), 0)] * 5) is None and L.pose("abcde") is None)

    # --- one picture, one step
    front, left, tilted, up = (L.pose(landmarks(**k)) for k in (dict(), dict(yaw=0.4), dict(roll=15), dict(pitch=0.4)))
    check("a straight picture shows face_camera and nothing else",
          L.step_ok("face_camera", front) and not any(L.step_ok(s, front) for s in ("turn_left", "turn_right", "tilt", "look_up")))
    check("a turned picture shows either turn, and not face_camera", L.step_ok("turn_left", left) and L.step_ok("turn_right", left) and not L.step_ok("face_camera", left))
    check("a tilted picture shows tilt only", L.step_ok("tilt", tilted) and not L.step_ok("face_camera", tilted) and not L.step_ok("look_up", tilted))
    check("a raised face shows look_up", L.step_ok("look_up", up) and not L.step_ok("look_up", front))
    check("an unknown step, or no pose, shows nothing", not L.step_ok("blink", front) and not L.step_ok("face_camera", None))
    check("the step list is the five poses, with tilt where blink was", L.STEPS == face_check.STEPS and "blink" not in L.STEPS and "tilt" in L.STEPS)

    # --- the verdict on a whole capture
    rows = good_capture(rng)
    live, why = _verdict(rows)
    check("a good 12-picture capture of one person passes", live is True and why == "", why)
    check("... also when every yaw is mirrored (the camera may show the picture either way)",
          _verdict([dict(r, pose=dict(r["pose"], yaw=-r["pose"]["yaw"])) for r in rows])[0] is True)
    check("a 3-picture live match with no straight picture passes on the poses alone",
          _verdict(good_capture(rng, ["turn_left", "tilt", "look_up"]))[0] is True)
    check("an empty capture is not live", _verdict([])[0] is False)
    bad = list(rows)
    bad[1] = dict(rows[1], pose=L.pose(landmarks(yaw=0.0)))
    check("a picture that does not show the pose that was asked fails the whole capture", _verdict(bad)[0] is False)
    check("a picture with no clear face fails it", _verdict(rows[:3] + [dict(rows[3], embedding=[])] + rows[4:])[0] is False
          and _verdict(rows[:3] + [dict(rows[3], pose=None)] + rows[4:])[0] is False)
    same = list(rows)
    same[5] = dict(rows[5], shape=rows[0]["shape"], pose=rows[0]["pose"], step="face_camera")
    same[0] = dict(rows[0], step="face_camera")
    check("the same picture twice fails: each step needs a new one", _verdict(same)[0] is False and "same picture" in _verdict(same)[1], _verdict(same))
    swapped = [dict(r, pose=dict(r["pose"], yaw=abs(r["pose"]["yaw"]) if r["step"] == "turn_right" else r["pose"]["yaw"])) for r in rows]
    check("left and right turns that go the same way fail", _verdict(swapped)[0] is False, _verdict(swapped))
    mixed = [dict(r, pose=dict(r["pose"], yaw=-r["pose"]["yaw"])) if r["step"] == "turn_left" and i == next(j for j, q in enumerate(rows) if q["step"] == "turn_left") else r
             for i, r in enumerate(rows)]
    check("turns for one side that do not all go the same way fail", _verdict(mixed)[0] is False, _verdict(mixed))
    slight = [dict(r, pose=dict(r["pose"], yaw=0.24 + r["pose"]["yaw"] * 0)) if r["step"] == "turn_left" else r for r in rows]
    front_turned = [dict(r, pose=dict(r["pose"], yaw=0.12)) if r["step"] == "face_camera" else r for r in slight]
    check("a turn that is barely beyond the straight pictures fails", _verdict(front_turned)[0] is False, _verdict(front_turned))
    weak_tilt = [dict(r, pose=dict(r["pose"], roll=6.0)) if r["step"] == "face_camera" else dict(r, pose=dict(r["pose"], roll=13.0)) if r["step"] == "tilt" else r for r in rows]
    check("a tilt that is barely beyond the straight pictures fails", _verdict(weak_tilt)[0] is False, _verdict(weak_tilt))
    weak_up = [dict(r, pose=dict(r["pose"], pitch=0.46)) if r["step"] == "face_camera" else dict(r, pose=dict(r["pose"], pitch=0.48)) if r["step"] == "look_up" else r for r in rows]
    check("a look-up that is barely beyond the straight pictures fails", _verdict(weak_up)[0] is False, _verdict(weak_up))
    other = [dict(r, embedding=vector(3, rng)) if i == 4 else r for i, r in enumerate(rows)]
    check("a different face among the pictures fails", _verdict(other)[0] is False and "same face" in _verdict(other)[1], _verdict(other))
    check("the match threshold is never under the published floor", _verdict(rows)[0] is True
          and L.verdict(other, 0.0)[0] is False and L.FLOOR <= L.THRESHOLD and face_check.MIN_MATCH == L.FLOOR)
    src = open(os.path.join(ROOT, "app", "workers", "face_logic.py"), encoding="utf-8").read()
    check("the rules say in plain words what the live verdict cannot see", "does NOT check" in src and "recording" in src and "series of pictures" in src and "LIVENESS_KIND" in src)

    # --- the worker file, as a program
    for variable in ("EASY_STUDIO_FACE_WORKER",):
        kept = os.environ.get(variable)
    try:
        empty = tempfile.mkdtemp(prefix="es_face_empty_")
        fc = _check(empty)
        check("no model files: the worker says so in the fixed words, and enrolment cannot start",
              fc.available() is False and fc.last_error == face_check.REASONS["files_missing"] and "not installed" in fc.last_error, fc.last_error)
        wrong, _ = _model_dir(content=False)
        fc = _check(wrong)
        check("model files with another hash are never loaded", fc.available() is False and fc.last_error == face_check.REASONS["hash_mismatch"], fc.last_error)
        folder, hashes = _model_dir()
        fc = _check(folder, _runner(hashes, with_stub=False))
        check("files that are right but a library that will not start: the fixed words, naming the older version",
              fc.available() is False and fc.last_error == face_check.REASONS["library_failed"] and "older version" in fc.last_error, fc.last_error)
        liar = tempfile.mktemp(prefix="es_face_liar_", suffix=".py")
        open(liar, "w").write('import json\nprint(json.dumps({"ready": False, "code": "see /etc/passwd", "error": "free text"}), flush=True)\n')
        fc = _check(folder, liar)
        check("a reason outside the fixed set is shown as 'not installed', never as the worker wrote it",
              fc.available() is False and fc.last_error == face_check.NOT_INSTALLED, fc.last_error)

        fc = _check(folder, _runner(hashes))
        check("with the files and the library the worker is ready", fc.available() is True, fc.last_error)
        check("it names its model by both files' short hashes",
              fc.model == "yunet-2023mar:%s+sface-2021dec:%s" % (hashes["detector"][:8], hashes["embedder"][:8]), fc.model)
        check("it names the kind of live verdict it gives: poses only, which the app accepts and records",
              fc.liveness_kind == "poses_only" == L.LIVENESS_KIND and fc.liveness_kind in face_check.ACCEPTED_LIVENESS, fc.liveness_kind)
        check("it reports its own threshold, which the app keeps", fc.threshold == L.THRESHOLD and fc.threshold >= face_check.MIN_MATCH, fc.threshold)
        pics = tempfile.mkdtemp(prefix="es_face_pics_")
        emb = vector(0, random.Random(3))
        straight, turned, two, none, big = _write_pictures(pics, [
            ("a.png", [_face_row()], emb), ("b.png", [_face_row(yaw=0.4)], emb),
            ("c.png", [_face_row(), _face_row(yaw=0.4)], emb), ("d.png", [], emb), ("e.png", [_face_row()], emb)])
        json.dump({"faces": [_face_row()], "embedding": emb, "side": 6000}, open(big + ".lm.json", "w"))
        got = fc.inspect(straight, "face_camera")
        check("one straight face: one face, the step shown, its embedding, and the model it came from",
              got["faces"] == 1 and got["step_ok"] is True and len(got["embedding"]) == 8 and got["model"] == fc.model, got)
        got = fc.inspect(turned, "face_camera")
        check("a turned face does not show face_camera", got["faces"] == 1 and got["step_ok"] is False, got)
        check("... and does show a turn", fc.inspect(turned, "turn_left")["step_ok"] is True)
        got = fc.inspect(two, "face_camera")
        check("two faces: two counted, no embedding, no step", got["faces"] == 2 and got["embedding"] == [] and got["step_ok"] is False, got)
        got = fc.inspect(none, "face_camera")
        check("no face: none counted", got["faces"] == 0 and got["embedding"] == [] and got["step_ok"] is False, got)
        got = fc.inspect(os.path.join(pics, "missing.png"), "face_camera")
        check("a picture that cannot be read counts as no face, and the worker goes on", got["faces"] == 0 and fc.available() is True)
        check("a very large picture is looked at in a smaller copy and still answered", fc.inspect(big, "face_camera")["faces"] == 1)
        fc.proc.stdin.write("{not json\n")
        fc.proc.stdin.flush()
        bad = fc._read()
        check("a request the worker cannot read gets an error answer, not a stopped worker",
              bad.get("faces") == 0 and bad.get("step_ok") is False and fc.inspect(straight, "face_camera")["faces"] == 1, bad)

        # liveness, through the whole path: pictures -> worker -> verdict
        def capture(items):
            return [{"path": p, "step": s} for p, s in items]
        steps = (list(L.STEPS) * 3)[:12]
        pose_of = {"face_camera": dict(yaw=0.02, roll=1.0, pitch=0.62), "turn_left": dict(yaw=0.42, pitch=0.62),
                   "turn_right": dict(yaw=-0.40, pitch=0.62), "tilt": dict(roll=17.0, pitch=0.62), "look_up": dict(pitch=0.40)}
        made = _write_pictures(pics, [("p%02d.png" % i, [_face_row(**dict(pose_of[s], at=(320 + i, 240 - i),
                                                                        yaw=pose_of[s].get("yaw", 0.0) + (i % 4) * 0.012 - 0.018))], emb)
                                     for i, s in enumerate(steps)])
        live, why = fc.liveness(capture(zip(made, steps)))
        check("a capture of twelve different pictures, each showing its step, is judged live", live is True and why == "", why)
        live, why = fc.liveness(capture(zip([made[0]] * 12, steps)))
        check("the same picture twelve times is not", live is False, why)
        wrong_steps = list(steps)
        wrong_steps[1], wrong_steps[2] = wrong_steps[2], wrong_steps[1]
        wrong_steps[1] = "face_camera"
        live, why = fc.liveness(capture(zip(made, wrong_steps)))
        check("pictures that do not match the order the plan asked for are not live", live is False, why)
        check("the worker's whole answer to a verdict is a plain true or false with a reason", isinstance(live, bool) and isinstance(why, str))
        fc.stop()
    finally:
        if kept is not None:
            os.environ["EASY_STUDIO_FACE_WORKER"] = kept
        else:
            os.environ.pop("EASY_STUDIO_FACE_WORKER", None)

    # --- the worker file's own limits
    text = open(WORKER, encoding="utf-8").read()
    check("the worker opens no network connection and reads nothing but the pictures it is asked about",
          not re.search(r"\b(import|from)\s+(socket|urllib|requests|http|ftplib|smtplib|subprocess|ssl)\b", text)
          and "open(" not in text.replace("with open(path", ""), [m for m in re.findall(r"open\([^)]*\)", text)])
    check("it names the older library version it can fall back to", "4.13.0.92" in text)

    # --- environment overrides, only in a test run (reviewer F1 on the enrolment PR)
    import owner as O
    saved = {k: os.environ.get(k) for k in ("EASY_STUDIO_TEST_RUN", "EASY_STUDIO_FACE_WORKER", "EASY_STUDIO_BACKUP_TOOL")}
    try:
        os.environ["EASY_STUDIO_FACE_WORKER"] = "/tmp/stand-in.py"
        os.environ["EASY_STUDIO_BACKUP_TOOL"] = "/tmp/stand-in-tool"
        os.environ["EASY_STUDIO_TEST_RUN"] = "1"
        in_test = (face_check.worker_path(), O._backup_tool())
        os.environ.pop("EASY_STUDIO_TEST_RUN")
        alone = (face_check.worker_path(), O._backup_tool())
        os.environ["EASY_STUDIO_TEST_RUN"] = "0"
        off = (face_check.worker_path(), O._backup_tool())
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("in a test run the stand-in worker and backup tool can be named", in_test == ("/tmp/stand-in.py", "/tmp/stand-in-tool"), in_test)
    import age_guard
    kept_env = {k: os.environ.get(k) for k in ("EASY_STUDIO_TEST_RUN", "EASY_STUDIO_AGE_WORKER")}
    try:
        os.environ["EASY_STUDIO_AGE_WORKER"] = "/tmp/stand-in-age.py"
        os.environ["EASY_STUDIO_TEST_RUN"] = "1"
        age_in_test = age_guard.worker_path()
        os.environ.pop("EASY_STUDIO_TEST_RUN")
        age_alone = age_guard.worker_path()
    finally:
        for k, v in kept_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("the age-check worker can be swapped for a stand-in in a test run only, like the other overrides",
          age_in_test == "/tmp/stand-in-age.py" and age_alone == os.path.join(ROOT, "app", "workers", "age_check_worker.py"), (age_in_test, age_alone))
    check("without the test-run flag the same variables change nothing",
          alone == (WORKER, "/usr/bin/tmutil") and off == (WORKER, "/usr/bin/tmutil"), (alone, off))

    # --- the lock: the two files, the library and the cards
    lock = json.load(open(LOCK, encoding="utf-8"))
    rows = {r["id"]: r for r in lock["rows"]}
    for key, rid, repo in (("detector", "face.face_detection_yunet_2023mar", "opencv/face_detection_yunet"),
                           ("embedder", "face.face_recognition_sface_2021dec", "opencv/face_recognition_sface")):
        r = rows.get(rid) or {}
        want = L.MODEL_FILES[key]
        check("the lock has a row for the %s, with the hash the worker is pinned to, a full revision and a licence" % key,
              r.get("sha256") == want["sha256"] and r.get("repo") == repo and re.fullmatch(r"[0-9a-f]{40}", r.get("rev", ""))
              and ("/resolve/" + r.get("rev", "x") + "/") in r.get("url", "") and r.get("url", "").endswith(want["file"])
              and r.get("license", {}).get("class") == "open" and r.get("size", 0) > 0 and r.get("group") == "face"
              and r.get("comfy_link", {}).get("type") == "easy_studio/face_check" and r.get("comfy_link", {}).get("name") == want["file"], r)
    wheel = (lock.get("runtimes") or {}).get("opencv_python_headless") or {}
    check("the lock pins the library's wheel by hash, with the older wheel as the documented fallback",
          re.fullmatch(r"[0-9a-f]{64}", wheel.get("sha256", "")) and wheel.get("url", "").startswith("https://files.pythonhosted.org/")
          and wheel.get("version") == "4.14.0.94" and wheel.get("license") == "Apache-2.0" and wheel.get("install") == "--no-deps --require-hashes"
          and re.fullmatch(r"[0-9a-f]{64}", (wheel.get("fallback") or {}).get("sha256", "")) and (wheel.get("fallback") or {}).get("version") == "4.13.0.92", wheel)
    cards = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "app", "model_cards.json"), encoding="utf-8"))["cards"]}
    check("the licence cards for the two models and the library are there, private use, no adult use",
          all(cards.get(i, {}).get("license") in ("MIT", "Apache-2.0") and cards[i].get("private_use") == "yes" and cards[i].get("commercial") == "allowed"
              for i in ("face_yunet_2023mar", "face_sface_2021dec", "opencv_python_headless")), sorted(cards)[-4:])
