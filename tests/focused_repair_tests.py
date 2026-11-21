"""Focused checks for output classification and the 21+ age rules.

    python tests/focused_repair_tests.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))

import age_guard  # noqa: E402
import character as charmod  # noqa: E402
import comfy_client as cc  # noqa: E402
import photoreal  # noqa: E402
import safety  # noqa: E402

WEBP = b"RIFF\x18\x00\x00\x00WEBPVP8 \x0c\x00\x00\x00" + b"\x00" * 12
SIGNATURE_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom"
FIX = os.path.join(HERE, "fixtures")


def _fix(name):
    with open(os.path.join(FIX, name), "rb") as handle:
        return handle.read()


def _box(typ, payload):
    return (8 + len(payload)).to_bytes(4, "big") + typ + payload


STRUCT_MP4 = _box(b"ftyp", b"isom\x00\x00\x00\x00") + _box(b"mdat", b"\x00\x00\x00\x00")


def _hist(filename, animated=False, status="success", completed=True):
    node = {"images": [{"filename": filename, "subfolder": "", "type": "output"}]}
    if animated:
        node["animated"] = [True]
    return {"outputs": {"9": node}, "status": {"status_str": status, "completed": completed, "messages": []}}


def _output(check):
    animated = cc.classify_job(_hist("clip.webp", animated=True), payloads={"clip.webp": _fix("tiny_anim.webp")})
    check("animated WebP is an animated image, not a failure",
          animated["status"] == "done" and animated["kind"] == "animated_image" and animated["status"] != "backend_failure",
          animated)
    still = cc.classify_job(_hist("still.webp"), payloads={"still.webp": _fix("tiny.webp")})
    check("still WebP is a still image", still["status"] == "done" and still["kind"] == "still", still)
    video = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": _fix("tiny.mp4")})
    check("SaveVideo MP4 is a video result", video["status"] == "done" and video["kind"] == "video", video)
    import os
    import tempfile
    import video_tools as V
    real_path = os.path.join(tempfile.mkdtemp(prefix="es_fix_"), "real.mp4")
    V.make_test_video(real_path, 32, 32, 2, 8)
    real_mp4 = open(real_path, "rb").read()
    real = cc.classify_job(_hist("real.mp4", animated=True), payloads={"real.mp4": real_mp4})
    check("a real ffprobe-readable MP4 is a video result", real["status"] == "done" and real["kind"] == "video", real)
    signature = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": SIGNATURE_MP4})
    check("a signature-only MP4 is corrupt", signature["status"] == "corrupt", signature)
    empty = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": b""})
    check("an empty MP4 is corrupt", empty["status"] == "corrupt", empty)
    truncated = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": real_mp4[:24]})
    check("a truncated MP4 is corrupt", truncated["status"] == "corrupt", truncated)
    wrong = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": WEBP})
    check("WebP bytes named .mp4 are corrupt without an MP4 expectation", wrong["status"] == "corrupt", wrong)
    missing_dl = cc.classify_job(_hist("clip.mp4", animated=True), payloads={})
    check("a missing download is not done", missing_dl["status"] == "missing" and "missing download" in missing_dl["message"], missing_dl)
    missing = cc.classify_job({"outputs": {}, "status": {"status_str": "success", "completed": True}})
    check("missing output is not a backend failure",
          missing["status"] == "missing" and "no saved output file" in missing["message"] and missing["status"] != "backend_failure",
          missing)
    corrupt = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": b"not-a-real-mp4"})
    check("corrupt output is not a backend failure",
          corrupt["status"] == "corrupt" and corrupt["status"] != "backend_failure", corrupt)
    mismatch = cc.classify_job(_hist("clip.webp", animated=True), expected="mp4", payloads={"clip.webp": _fix("tiny.webp")})
    check("expected MP4 but got WebP is a requirement mismatch",
          mismatch["status"] == "requirement mismatch" and "WebP" in mismatch["message"] and "backend_failure" not in mismatch["message"],
          mismatch)
    failed = _hist("clip.mp4", animated=True, status="error", completed=False)
    failed["status"]["messages"] = [["execution_error", {"node_type": "SaveVideo", "exception_message": "disk full"}]]
    backend = cc.classify_job(failed)
    check("a ComfyUI error stays a backend failure",
          backend["status"] == "backend_failure" and "disk full" in backend["message"], backend)
    two = {
        "outputs": {
            "4": {"images": [{"filename": "a.mp4", "type": "output"}], "animated": [True]},
            "7": {"images": [{"filename": "b.mp4", "type": "output"}], "animated": [True]},
        },
        "status": {"status_str": "success", "completed": True, "messages": []},
    }
    savers = [{"node_id": "4", "format": "mp4"}, {"node_id": "7", "format": "mp4"}]
    both = cc.classify_job(two, expected=savers, payloads={"a.mp4": _fix("tiny.mp4"), "b.mp4": _fix("tiny.mp4")})
    check("two MP4 savers both have to succeed", both["status"] == "done" and both["kind"] == "video", both)
    mixed = {
        "outputs": {
            "4": {"images": [{"filename": "need.webp", "type": "output"}], "animated": [True]},
            "9": {"images": [{"filename": "other.mp4", "type": "output"}], "animated": [True]},
        },
        "status": {"status_str": "success", "completed": True, "messages": []},
    }
    bad = cc.classify_job(mixed, expected=[{"node_id": "4", "format": "mp4"}],
                          payloads={"need.webp": _fix("tiny.webp"), "other.mp4": _fix("tiny.mp4")})
    check("an unrelated MP4 does not satisfy another saver",
          bad["status"] == "requirement mismatch" and "node 4" in bad["message"], bad)
    still_only = {
        "outputs": {
            "4": {},
            "2": {"images": [{"filename": "still.png", "type": "output"}]},
        },
        "status": {"status_str": "success", "completed": True, "messages": []},
    }
    # node 4 expected a video and saved nothing; node 2 saved a still
    gap = cc.classify_job(still_only, expected=[{"node_id": "4", "format": "mp4"}])
    check("a still does not satisfy a missing required video",
          gap["status"] == "missing" and gap["status"] != "done" and "node 4" in gap["message"], gap)


def _ages(check):
    ok, age, msg = safety.require_stated_age({"age": 21})
    check("stated age 21 is accepted", ok and age == 21 and msg == "", msg)
    ok, age, msg = safety.require_stated_age({"age": "34"})
    check("a numeric string age is accepted", ok and age == 34, msg)
    ok, age, msg = safety.require_stated_age({"name": "A"})
    check("a missing age is rejected and not defaulted", not ok and age is None and "age is missing" in msg and "25" not in msg, msg)
    import catalog
    blank, err = charmod.normalise({"name": "No Age", "gender": "woman", "style": "photo"})
    check("catalog default 25 is not written onto a character with no age",
          err and blank.get("age") is None and blank.get("stated_age") is None
          and catalog.AGE_DEFAULT == 25 and catalog.everything()["age"]["default"] == 25 and "25" not in err,
          (blank.get("age"), err))
    ok, age, msg = safety.require_stated_age({"age": 21.5})
    check("age 21.5 is rejected and not clamped", not ok and age is None and "21.5" in msg, msg)
    js = open(os.path.join(ROOT, "app", "static", "app.js"), encoding="utf-8").read()
    page_js = open(os.path.join(ROOT, "app", "static", "v3.js"), encoding="utf-8").read()
    check("the page does not copy catalog age.default", "age.default" not in js and "age.default" not in page_js)
    check("Surprise me stores 21 through 40 only from the press", js.count("21 + Math.floor(Math.random() * 20)") == 1)
    check("the confirm sentence does not say unchecked results are still produced",
          "won't be checked" not in page_js and "will not run" in page_js)
    html = open(os.path.join(ROOT, "app", "static", "index.html"), encoding="utf-8").read()
    server = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    check("the private build notice stays",
          "PRIVATE BUILD — NOT FOR DISTRIBUTION" in html and html.count("PRIVATE BUILD — NOT FOR DISTRIBUTION") >= 1
          and "PRIVATE BUILD — NOT FOR DISTRIBUTION" in server)
    ok, age, msg = safety.require_stated_age({"age": "eighteen"})
    check("an invalid age keeps the original value", not ok and "age='eighteen'" in msg, msg)
    ok, age, msg = safety.require_stated_age({"age": 18})
    check("age 18 is rejected and not raised", not ok and "age=18" in msg and "not raised" in msg, msg)
    ok, age, msg = safety.require_stated_age({"age": 25, "stated_age": 30})
    check("conflicting ages keep both original values", not ok and "age=25" in msg and "stated_age=30" in msg, msg)
    ok, age, msg = safety.require_stated_age({"appearance": "looks 40", "looks": "mature"})
    check("age is not inferred from appearance", not ok and age is None and "appearance" in msg.lower(), msg)
    record, err = charmod.normalise({"age": 18, "name": "Ada"})
    check("normalise rejects 18 before rewriting it", err and record.get("age") == 18 and "age=18" in err, (record.get("age"), err))
    record, err = charmod.normalise({"age": None, "name": "Ada"})
    check("normalise keeps a missing age value", err and record.get("age") is None and "age=None" in err, (record.get("age"), err))
    record, err = charmod.normalise({"age": 21, "name": "Ada"})
    check("a valid character keeps the stated age apart from any appearance check",
          err is None and record["age"] == 21 and record["stated_age"] == 21 and "appearance_check" not in record, record)
    ok, ages, msg = safety.require_group_ages({"people": [{"age": 22}, {"age": 40}]})
    check("a group of stated 21+ ages is accepted", ok and ages == [22, 40], msg)
    ok, ages, msg = safety.require_group_ages({"people": [{"age": 30}, {"name": "Bea"}]})
    check("a group is rejected when any person has no age", not ok and "age is missing" in msg, msg)
    ok, ages, msg = safety.require_group_ages({"people": [{"age": 30}, {"age": 19}]})
    check("a group is rejected when any person is under 21", not ok and "age=19" in msg, msg)
    ok, msg = safety.check_group_prompt("a 25-year-old woman and a 32-year-old man")
    check("a group prompt with an age for each person is accepted", ok, msg)
    ok, msg = safety.check_group_prompt("a 40-year-old man and a woman who looks 30")
    check("a group prompt does not infer age from appearance", not ok and "woman" in msg.lower(), msg)
    try:
        card = photoreal.body_card({"gender": "woman", "age": 12})
        check("photoreal does not clamp age 12", False, card)
    except photoreal.PhotorealError as e:
        check("photoreal does not clamp age 12", "age=12" in str(e), str(e))
    card = photoreal.body_card({"gender": "woman", "age": 28})
    check("body card age is the stated age, not an appearance result",
          card["age"] == 28 and card["stated_age"] == 28 and card["age_source"] == "stated" and "appearance_check" not in card)


def _install_dir():
    folder = tempfile.mkdtemp(prefix="es_age_")
    for name in ("model.safetensors", "config.json", "preprocessor_config.json"):
        open(os.path.join(folder, name), "w", encoding="utf-8").write("{}")
    nested = os.path.join(folder, "torch", "hub", "checkpoints")
    os.makedirs(nested)
    open(os.path.join(nested, "yunet_final.pth"), "w", encoding="utf-8").write("x")
    return folder


def _worker(body):
    path = tempfile.NamedTemporaryFile(prefix="es_age_worker_", suffix=".py", delete=False, mode="w", encoding="utf-8")
    path.write(body)
    path.close()
    return path.name


def _checker(check):
    off_guard = age_guard.AgeGuard(_install_dir(), enabled=False)
    off = off_guard.check("x.png")
    check("a switched-off checker refuses to run",
          off["status"] == "off" and off.get("held") is True and age_guard.held_unusable(off)
          and age_guard.held_unusable({"status": "off", "held": False})
          and off_guard.proc is None and "age" not in off and "age" not in off["appearance_check"], off)
    mixed_off = age_guard.aggregate_frame_checks([
        {"status": "ok", "faces": 1, "p_under21": 0.01},
        {"status": "off"},
    ])
    check("one passing frame does not hide a checker that is off",
          mixed_off["status"] == "off" and mixed_off.get("held") is True and age_guard.held_unusable(mixed_off), mixed_off)
    import pipelines
    import pipelines_v3
    old_guard = pipelines.AGE_GUARD
    try:
        pipelines.AGE_GUARD = age_guard.AgeGuard(_install_dir(), enabled=False)
        calls = (
            ("create", pipelines.job_create, {"dna": {"age": 32, "gender": "woman", "style": "photo"}}),
            ("video", pipelines.job_video, {"image": "x"}),
            ("export", pipelines.job_export, {"character": "x"}),
            ("video studio", pipelines_v3.job_video_any, {"model": "wan22_t2v", "text": "she waves"}),
            ("train", pipelines_v3.job_train_lora, {"character": "x", "base": "photo"}),
            ("train pictures", pipelines_v3.job_train_dataset, {"character": "x", "count": 12}),
            ("godot export", pipelines_v3.job_export_godot, {"character": "x"}),
            ("workshop still", __import__("stills").job_workshop_still, {"character": "x", "wardrobe": "jeans_tee"}),
            ("keep face", __import__("stills").job_keep_face, {"character": "x"}),
            ("refine skin", __import__("stills").job_refine_skin, {"character": "x"}),
            ("refine anatomy", __import__("stills").job_refine_anatomy, {"character": "x"}),
            ("short film", __import__("films").job_film, {"image": "x", "seconds": 5}),
        )
        for name, fn, params in calls:
            try:
                fn(None, params)
                check(f"{name} refuses to run while the checker is off", False, "it ran")
            except pipelines.UserError as exc:
                check(f"{name} refuses to run while the checker is off", "will not run" in str(exc).lower(), str(exc))
    finally:
        pipelines.AGE_GUARD = old_guard

    missing = age_guard.AgeGuard("/no/such/age/model", enabled=True).check("x.png")
    check("a missing age-checker dependency is held",
          missing["status"] == "blocked_age_check_unavailable" and missing.get("cause") == "missing_dependency"
          and missing.get("held") is True and "age" not in missing["appearance_check"], missing)

    error_py = _worker(
        "import json,sys\n"
        "print(json.dumps({'ready': True, 'device': 'cpu'}), flush=True)\n"
        "for line in sys.stdin:\n"
        "    print(json.dumps({'status': 'error', 'reason': 'classifier exploded'}), flush=True)\n"
    )
    timeout_py = _worker(
        "import json,sys,time\n"
        "print(json.dumps({'ready': True, 'device': 'cpu'}), flush=True)\n"
        "for line in sys.stdin:\n"
        "    time.sleep(5)\n"
        "    print(json.dumps({'status': 'ok'}), flush=True)\n"
    )
    old = age_guard.WORKER
    try:
        age_guard.WORKER = error_py
        guard = age_guard.AgeGuard(_install_dir(), enabled=True)
        try:
            failed = guard.check(os.path.join(tempfile.gettempdir(), "x.png"), timeout=5)
        finally:
            guard.stop()
        check("a checker error is held and is not a declared age",
              failed["status"] == "blocked_age_check_unavailable" and failed.get("cause") == "error"
              and failed.get("held") is True and "classifier exploded" in failed.get("reason", "")
              and "age" not in failed["appearance_check"], failed)

        age_guard.WORKER = timeout_py
        guard = age_guard.AgeGuard(_install_dir(), enabled=True)
        try:
            timed = guard.check(os.path.join(tempfile.gettempdir(), "x.png"), timeout=0.4)
        finally:
            guard.stop()
        check("a checker timeout is held",
              timed["status"] == "blocked_age_check_unavailable" and timed.get("cause") == "timeout" and timed.get("held") is True,
              timed)
    finally:
        age_guard.WORKER = old

    import video_tools as V
    clip = os.path.join(tempfile.mkdtemp(prefix="es_frames_"), "clip.mp4")
    V.make_test_video(clip, 64, 64, 4, 8)
    extracted = age_guard.check_video(type("G", (), {"check": lambda self, path: {"status": "error", "reason": "boom", "cause": "error"}})(),
                                      "/no/such/clip.mp4", tempfile.mkdtemp(prefix="es_fx_"), "ffmpeg")
    check("frame extraction failure is held and kept",
          extracted["status"] == "blocked_age_check_unavailable" and extracted.get("held") is True
          and extracted.get("failures") and "frame extraction failed" in extracted.get("reason", ""), extracted)

    class Mixed:
        def __init__(self):
            self.n = 0

        def check(self, path):
            self.n += 1
            if self.n == 2:
                return {"status": "unavailable", "reason": "checker down", "cause": "unavailable"}
            return {"status": "ok", "faces": 1, "p_under21": 0.02}

    mixed = age_guard.check_video(Mixed(), clip, tempfile.mkdtemp(prefix="es_mix_"), "ffmpeg")
    statuses = [frame.get("status") for frame in mixed.get("frames") or []]
    check("one passing frame does not hide a failed frame",
          mixed["status"] == "blocked_age_check_unavailable" and mixed.get("held") is True
          and "ok" in statuses and "blocked_age_check_unavailable" in statuses
          and len(mixed.get("failures") or []) >= 1 and "age" not in mixed["appearance_check"], mixed)


def _groups(check):
    """Plural and adjective scenes are cleared only by declared records."""
    one = [{"age": 29, "gender": "woman", "style": "photo"}]
    pair = [{"age": 30, "gender": "woman", "style": "photo"}, {"age": 30, "gender": "woman", "style": "photo"}]
    try:
        ok, msg = safety.check_group_prompt("two women playing volleyball", one)
    except TypeError as exc:
        ok, msg = True, f"no record argument: {exc}"
    check("plural wording is not cleared just because no phrase matched",
          ok is False and msg == "Unbound group: 'two women' asks for 2 people but 1 declared record was given.",
          msg)
    try:
        ok, msg = safety.check_group_prompt("athletic women playing volleyball", pair)
    except TypeError as exc:
        ok, msg = True, f"no record argument: {exc}"
    check("adjective plural wording without a count is unsupported",
          ok is False and msg == "Unsupported group wording: 'athletic women' is not a supported group. "
          "Every person needs their own declared record with a stated age of 21 or older.",
          msg)
    try:
        ok, msg = safety.check_group_prompt("two athletic women playing volleyball", pair)
    except TypeError as exc:
        ok, msg = True, f"no record argument: {exc}"
    check("an exact count with adjectives is cleared by matching records",
          ok is True and msg == "", msg)


def _bytes_of_saver(check):
    """Duplicate basenames and non-MP4 savers."""
    import video_tools as V
    real_path = os.path.join(tempfile.mkdtemp(prefix="es_saver_"), "real.mp4")
    V.make_test_video(real_path, 32, 32, 2, 8)
    real_mp4 = open(real_path, "rb").read()
    hist = {
        "outputs": {
            "4": {"images": [{"filename": "clip.mp4", "subfolder": "a", "type": "output"}], "animated": [True]},
            "7": {"images": [{"filename": "clip.mp4", "subfolder": "b", "type": "output"}], "animated": [True]},
        },
        "status": {"status_str": "success", "completed": True, "messages": []},
    }
    client = cc.ComfyClient("http://127.0.0.1:9")
    original = cc.requests.get

    def fake_get(url, timeout=None):
        from urllib.parse import parse_qs, urlparse
        sub = (parse_qs(urlparse(url).query).get("subfolder") or [""])[0]
        body = WEBP if sub == "b" else real_mp4

        class Response:
            content = body

            def raise_for_status(self):
                return None

        return Response()

    cc.requests.get = fake_get
    try:
        paths = client.download_outputs(hist, tempfile.mkdtemp(prefix="es_dl_"))
        report = cc.classify_job(hist, expected=[{"node_id": "4", "format": "mp4"}, {"node_id": "7", "format": "mp4"}],
                                  payloads=client._payloads(paths))
    finally:
        cc.requests.get = original
    check("a corrupt twin basename does not validate as the other saver's bytes",
          report["status"] == "corrupt" and report["status"] != "done"
          and "node 7" in report["message"] and "subfolder b" in report["message"],
          report)
    still = {"images": [{"filename": "still.png", "subfolder": "", "type": "output"}]}
    for fmt in ("webm", "mkv", "mov", "png", "webp", "jpeg"):
        masked = {
            "outputs": {"4": {}, "2": still},
            "status": {"status_str": "success", "completed": True, "messages": []},
        }
        gap = cc.classify_job(masked, expected=[{"node_id": "4", "format": fmt}])
        check(f"a missing required {fmt} saver is not masked by an unrelated still",
              gap["status"] == "missing" and gap["status"] != "done" and "node 4" in gap["message"] and fmt in gap["message"],
              gap)
    names = {"mp4": "tiny.mp4", "webm": "tiny.webm", "mkv": "tiny.mkv", "mov": "tiny.mov",
             "png": "tiny.png", "webp": "tiny.webp", "jpeg": "tiny.jpg"}
    for fmt, name in names.items():
        data = _fix(name)
        animated = fmt in ("mp4", "webm", "mkv", "mov", "webp")
        hist = _hist(name, animated=animated)
        report = cc.classify_job(hist, expected=[{"node_id": "9", "format": fmt}], payloads={name: data})
        check(f"a real {fmt} saver is accepted on its own bytes",
              report["status"] == "done" and cc.media_problem(name, data) is None, report)


def _content(check):
    """Synthetic containers are not media. A missing validator fails closed."""
    box = cc.classify_job(_hist("clip.mp4", animated=True), payloads={"clip.mp4": STRUCT_MP4})
    check("a box-only MP4 with no moov is corrupt",
          box["status"] == "corrupt" and "no video track" in box["message"], box)
    marker = cc.classify_job(_hist("still.jpg"), payloads={"still.jpg": b"\xff\xd8\xff\xd9"})
    check("a marker-only JPEG is corrupt",
          marker["status"] == "corrupt" and "image did not decode" in marker["message"], marker)
    chunks = cc.classify_job(_hist("still.webp"), payloads={"still.webp": WEBP})
    check("a WebP with only chunk lengths is corrupt",
          chunks["status"] == "corrupt" and "image did not decode" in chunks["message"], chunks)
    accepted = cc._ffprobe_accepts(STRUCT_MP4, "mp4")
    check("ffprobe does not accept a box-only MP4", accepted is False, accepted)
    import shutil
    import video_tools as V
    real_path = os.path.join(tempfile.mkdtemp(prefix="es_probe_"), "real.mp4")
    V.make_test_video(real_path, 32, 32, 2, 8)
    real_mp4 = open(real_path, "rb").read()
    original = shutil.which

    def no_ffprobe(name, *args, **kwargs):
        if name == "ffprobe":
            return None
        return original(name, *args, **kwargs)

    shutil.which = no_ffprobe
    try:
        problem = cc.media_problem("real.mp4", real_mp4)
    finally:
        shutil.which = original
    check("a missing video validator fails closed", problem == "corrupt", problem)


def _upload_form(check, app):
    """The real Upload-my-character dialog, not the Python helper."""
    from playwright.sync_api import sync_playwright
    from PIL import Image, ImageDraw
    picture = os.path.join(tempfile.mkdtemp(prefix="es_form_"), "character.png")
    img = Image.new("RGB", (80, 80), (90, 40, 40))
    ImageDraw.Draw(img).ellipse([10, 10, 70, 70], fill=(220, 180, 150))
    img.save(picture)
    posts = []
    with sync_playwright() as pw:
        exe = "/usr/local/bin/google-chrome" if os.path.exists("/usr/local/bin/google-chrome") else None
        browser = pw.chromium.launch(executable_path=exe, headless=True)
        page = browser.new_page()
        page.on("request", lambda req: posts.append(req) if req.method == "POST" and req.url.endswith("/api/upload") else None)
        page.goto(app.base + "/", wait_until="domcontentloaded")
        page.wait_for_selector("#door-make", timeout=15000)  # first screen is Make · Play · Library
        page.evaluate("go('gallery')")
        page.locator("#main button", has_text="Upload").click()
        page.locator("#modal h2", has_text="My fictional character").wait_for(timeout=5000)
        age = page.locator("#modal input.stated-age")
        check("the upload dialog collects a typed stated age", age.count() == 1, f"stated-age inputs: {age.count()}")
        if age.count() != 1:
            browser.close()
            check("a missing typed age is rejected with the exact error", False, "NOT_RUN: the dialog has no stated-age field")
            check("an invalid typed age is rejected with the exact error", False, "NOT_RUN: the dialog has no stated-age field")
            check("an under-21 typed age is rejected with the exact error", False, "NOT_RUN: the dialog has no stated-age field")
            check("a valid typed age is sent and the upload succeeds", False, "NOT_RUN: the dialog has no stated-age field")
            return
        page.locator("#modal input[type=file]").set_input_files(picture)
        page.locator("#modal input[type=checkbox]").check()

        captured = {}

        def remember(route):
            raw = route.request.post_data
            if raw is None and route.request.post_data_buffer is not None:
                raw = route.request.post_data_buffer.decode("latin1", "replace")
            captured["body"] = raw or ""
            route.continue_()

        page.route("**/api/upload", remember)

        def posted_age():
            raw = captured.get("body") or ""
            marker = 'name="age"'
            start = raw.find(marker)
            if start < 0:
                return None
            rest = raw[start + len(marker):]
            sep = "\r\n\r\n" if "\r\n\r\n" in rest else "\n\n"
            if sep not in rest:
                return None
            return rest.split(sep, 1)[1].split("\r\n", 1)[0].split("\n", 1)[0]

        def submit(value):
            import json as _json
            seen = page.locator(".toast.bad").count()
            captured.clear()
            age.fill(value)
            with page.expect_response("**/api/upload") as caught:
                page.locator("#modal button.btn.primary", has_text="Upload").click()
            response = caught.value
            text = response.text()
            try:
                payload = _json.loads(text)
            except ValueError:
                payload = {}
            detail = payload.get("error") if isinstance(payload, dict) else None
            if response.status != 200:
                page.wait_for_function(
                    "(n) => document.querySelectorAll('.toast.bad').length > n", arg=seen, timeout=10000)
                shown = page.locator(".toast.bad").last.inner_text()
            else:
                shown = ""
            return response.status, detail, shown, posted_age(), (captured.get("body") or "")[:160]

        status, detail, shown, posted, snippet = submit("")
        check("a missing typed age is rejected with the exact error",
              status == 400 and detail == "Missing stated age: age=''. Age is not inferred from appearance."
              and shown == detail and posted == "",
              (status, detail, shown, posted, snippet))
        status, detail, shown, posted, snippet = submit("eighteen")
        check("an invalid typed age is rejected with the exact error",
              status == 400 and detail == "Invalid stated age: age='eighteen'." and shown == detail and posted == "eighteen",
              (status, detail, shown, posted, snippet))
        status, detail, shown, posted, snippet = submit("18")
        check("an under-21 typed age is rejected with the exact error",
              status == 400 and detail == "Stated age is under 21: age='18'. It is not raised."
              and shown == detail and posted == "18",
              (status, detail, shown, posted, snippet))
        before = {item["id"] for item in app.get("/api/gallery").json()["items"]}
        status, detail, shown, posted, snippet = submit("34")
        try:
            page.wait_for_function("() => document.getElementById('modal').classList.contains('hidden')", timeout=5000)
            hidden = True
        except Exception:
            hidden = False
        added = [item for item in app.get("/api/gallery").json()["items"] if item["id"] not in before]
        check("a valid typed age is sent and the upload succeeds",
              status == 200 and hidden and len(added) == 1 and added[0].get("stated_age") == 34
              and added[0].get("age_check") == "ok" and posted == "34",
              (status, detail, hidden, posted, snippet, added))
        browser.close()


def _api(check):
    """API to worker: held results, group records, and the upload form."""
    import shutil
    import subprocess
    import tempfile
    import time
    import requests
    from run_tests import App, free_port
    from v3_tests import fake_lora
    out = tempfile.mkdtemp(prefix="es_hold_")
    comfy_dir = tempfile.mkdtemp(prefix="es_hold_comfy_")
    os.makedirs(os.path.join(comfy_dir, "models", "loras"))
    agedir = os.path.join(comfy_dir, "models", "easy_studio", "age_check")
    os.makedirs(os.path.join(agedir, "torch", "hub", "checkpoints"))
    for name in ("model.safetensors", "config.json", "preprocessor_config.json",
                 os.path.join("torch", "hub", "checkpoints", "yunet_final.pth")):
        open(os.path.join(agedir, name), "w", encoding="utf-8").write("{}")
    for name in ("my_style_lora.safetensors", "detail_tweaker.safetensors"):
        fake_lora(os.path.join(comfy_dir, "models", "loras", name), ["lora_x.lora_down.weight", "lora_x.lora_up.weight"], {})
    mp, port = free_port(), free_port()
    py = sys.executable
    mock = subprocess.Popen([py, os.path.join(HERE, "mock_comfy.py"), str(mp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=dict(os.environ, MOCK_LORA_DIR=os.path.join(comfy_dir, "models", "loras")))
    tdir = tempfile.mkdtemp(prefix="es_hold_trainer_")
    shutil.copy(os.path.join(HERE, "fake_trainer_run.py"), os.path.join(tdir, "run.py"))
    import json
    log_path = os.path.join(out, "age_checker.log")
    inject_path = os.path.join(out, "age_inject.json")
    with open(inject_path, "w", encoding="utf-8") as fh:
        json.dump({"apply": "off"}, fh)
    env = dict(os.environ, EASY_STUDIO_OUTPUTS=out, COMFY_URL=f"http://127.0.0.1:{mp}", EASY_STUDIO_PORT=str(port),
               COMFY_DIR=comfy_dir, COMFY_PYTHON=py, EASY_STUDIO_TEST_RUN="1", EASY_STUDIO_AGE_WORKER=os.path.join(HERE, "fake_age_worker.py"),
               EASY_STUDIO_TRAINER_DIR=tdir, EASY_STUDIO_TRAINER_PYTHON=py, MOCK_HOLD_MIDDLE_FRAME="1",
               MOCK_AGE_LOG=log_path, MOCK_AGE_INJECT=inject_path)
    srv = subprocess.Popen([py, os.path.join(ROOT, "app", "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        app = None
        for _ in range(80):
            try:
                requests.get(f"http://127.0.0.1:{port}/api/status", timeout=2)
                app = App(f"http://127.0.0.1:{port}")
                break
            except Exception:
                time.sleep(0.25)
        check("hold server started", app is not None)
        if app is None:
            return
        dna = {"gender": "woman", "age": 29, "style": "photo", "name": "Nia"}
        still = app.job("create", {"dna": dna, "count": 1})
        other = app.job("create", {"dna": {**dna, "name": "Noa"}, "count": 1})
        keep = (still.get("results") or [{}])[0]
        alt = (other.get("results") or [{}])[0]
        check("prerequisite create succeeded",
              still.get("status") == "done" and keep.get("id") and keep.get("age_check") == "ok"
              and other.get("status") == "done" and alt.get("id"),
              (still.get("status"), still.get("error"), keep.get("age_check"), other.get("status")))
        import shot_qc
        qc = shot_qc.passing_qc(keep.get("id"), alt.get("id")) if keep.get("id") and alt.get("id") else None
        before = {i["id"] for i in app.get("/api/gallery").json()["items"]}
        vid = app.job("video", {"image": keep.get("id"), "motion": "wind", "seconds": 2, "mode": "fast", "qc": qc}) if keep.get("id") else {"status": "error", "error": "create produced no still"}
        after = app.get("/api/gallery").json()["items"]
        new_videos = [i for i in after if i["id"] not in before and i.get("type") == "video"]
        log_text = open(log_path, encoding="utf-8").read() if os.path.exists(log_path) else ""
        middle = [line for line in log_text.splitlines() if "\tunchecked\t" in line and "agecheck_" in line and line.endswith("middle frame was not checked")]
        check("the final video checker was invoked on the middle frame", len(middle) == 1, log_text or "no checker log")
        check("mixed ok and unchecked frames are not published as a usable video",
              vid.get("status") == "blocked_age_check_unavailable" and vid.get("error") == "middle frame was not checked"
              and not vid.get("results") and new_videos == [],
              (vid.get("status"), vid.get("error"), new_videos))
        with open(inject_path, "w", encoding="utf-8") as fh:
            json.dump({"apply": "still", "result": {"status": "unchecked", "faces": 0, "reason": "injected unchecked disposition"}}, fh)
        before_images = {i["id"] for i in app.get("/api/gallery").json()["items"] if i.get("type") == "image"}
        held = app.job("create", {"dna": dna, "count": 1, "extra_scene": "standing in a studio"})
        after_images = [i for i in app.get("/api/gallery").json()["items"] if i.get("type") == "image" and i["id"] not in before_images]
        check("an injected unchecked disposition blocks the final still",
              held.get("status") == "blocked_age_check_unavailable" and held.get("error") == "injected unchecked disposition"
              and not held.get("results") and after_images == [],
              (held.get("status"), held.get("error"), [i.get("id") for i in after_images]))
        with open(inject_path, "w", encoding="utf-8") as fh:
            json.dump({"apply": "off"}, fh)
        r = app.post("/api/jobs", json={"kind": "create", "params": {"dna": dna, "extra_scene": "two women playing volleyball", "count": 1}})
        check("one record plus 'two women playing volleyball' is refused",
              r.status_code == 400 and "Unbound group: 'two women' asks for 2 people but 1 declared record was given." in r.text,
              r.text)
        r = app.post("/api/jobs", json={"kind": "create", "params": {
            "people": [{"age": 30, "gender": "woman", "style": "photo"}, {"age": 30, "gender": "woman", "style": "photo"}],
            "extra_scene": "athletic women playing volleyball", "count": 1}})
        check("adjective plural wording is refused when it is not a supported count",
              r.status_code == 400 and "Unsupported group wording: 'athletic women'" in r.text, r.text)
        group = app.job("create", {"people": [{"age": 30, "gender": "woman", "style": "photo"},
                                               {"age": 30, "gender": "woman", "style": "photo"}],
                                    "extra_scene": "two athletic women playing volleyball", "count": 1})
        made = (group.get("results") or [{}])[0]
        ages = [person.get("age") for person in made.get("people") or []]
        check("repeated equal ages are all saved on the group picture",
              group.get("status") == "done" and ages == [30, 30], (group.get("status"), group.get("error"), ages))
        reused = app.job("edit", {"image": made.get("id"), "op": "custom", "text": "warm the light"}) if made.get("id") else {"status": "error", "error": "no group picture"}
        reused_ages = [person.get("age") for person in ((reused.get("results") or [{}])[0].get("people") or [])]
        check("reuse of a multi-person picture keeps every record",
              reused.get("status") == "done" and reused_ages == [30, 30],
              (reused.get("status"), reused.get("error"), reused_ages))
        nested = app.job("create", {"dna": {"people": [{"age": 29, "gender": "woman", "style": "photo"},
                                                        {"age": 34, "gender": "man", "style": "photo"}]}, "count": 1})
        nested_ages = [person.get("age") for person in ((nested.get("results") or [{}])[0].get("people") or [])]
        check("a nested dna.people group runs through the worker",
              nested.get("status") == "done" and nested_ages == [29, 34],
              (nested.get("status"), nested.get("error"), nested_ages))
        _upload_form(check, app)
    finally:
        srv.terminate()
        mock.terminate()


def run(check):
    print("\n[2c] Output classification and 21+ age rules")
    _output(check)
    _ages(check)
    _groups(check)
    _bytes_of_saver(check)
    _content(check)
    _checker(check)
    _api(check)


if __name__ == "__main__":
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"   <-- {detail}"))
        return bool(cond)

    run(check)
    bad = [row for row in results if not row[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} focused checks passed")
    sys.exit(1 if bad else 0)
