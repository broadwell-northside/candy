"""Hosted providers (lane n-providers): the Keychain, the one send function, every refusal before a request,
the Video (API) job, and the key panel's routes. Stub HTTP and a stand-in `security` only: no network, no real key."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)

# The stand-in must be in place before anything can start `security`; the spawned server inherits it.
_STATE = os.path.join(tempfile.mkdtemp(prefix="es_security_"), "keys.json")
os.environ["EASY_STUDIO_TEST_RUN"] = "1"  # the stand-in tool below is honoured in a test run only
os.environ["EASY_STUDIO_SECURITY_TOOL"] = os.path.join(HERE, "fake_security.py")
os.environ["FAKE_SECURITY_STATE"] = _STATE

SENTINEL = "sk-SENTINEL-0123456789abcdefghij"
ENDPOINT = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
CLIP = open(os.path.join(HERE, "fixtures", "tiny.mp4"), "rb").read()


def _refused(fn):
    import pipelines as P
    from providers import ProviderError, Refused
    from providers.keychain import KeychainError
    try:
        fn()
    except (P.UserError, ProviderError, Refused, KeychainError) as exc:
        return str(exc)
    return ""


class _Checker:
    enabled = True
    mode = "ok"

    def check(self, path, *a, **k):
        if self.mode == "flag":
            return {"status": "flag", "faces": 1, "p_under21": 0.9}
        return {"status": "ok", "faces": 1, "p_under21": 0.02}


def _world():
    """A library with a made picture, a job context, and a stub HTTP session."""
    import pipelines as P
    from fake_provider import FakeSession
    from library import AreaView, Library
    from providers import base, guard
    guard.SETTINGS = {}
    root = tempfile.mkdtemp(prefix="es_prov_lib_")
    os.makedirs(os.path.join(root, "tmp"))
    lib = Library(root)
    session = FakeSession(clip=CLIP)
    base.SESSION = session
    P.AGE_GUARD = _Checker()
    P.set_area("default")
    job = {"id": "job1", "params": {}, "results": []}
    ctx = P.JobContext(job, None, AreaView(lib, "default"), None)
    return lib, ctx, session


def _pic(lib, name="pic.png", **meta):
    path = os.path.join(lib.root, name)
    Image.new("RGB", (64, 64), (90, 120, 60)).save(path)
    base = {"age_check": "ok", "appearance_check": {"status": "ok", "held": False}, "people": [{"age": 32}],
            "area": "default", "character": "c1"}
    base.update(meta)
    return lib.add(path, "create", role="made", **base)


def unit(check):
    print("\n[providers] The Keychain, the one send function, the refusals before a request, the Video (API) job")
    import age_guard  # noqa: F401
    import pipelines as P
    import pipelines_v3 as V3
    import provider_jobs as PJ
    import providers
    import safety
    from fake_provider import FakeSession
    from providers import base, guard, keychain
    PJ.POLL_SECONDS = 0

    # --- the Keychain -------------------------------------------------------------------------
    check("nothing is stored at first", keychain.configured("dashscope") is False)
    check("a key with spaces or quotes is refused without echoing it",
          "does not look like" in _refused(lambda: keychain.set_key("dashscope", 'sk bad"key;')) and
          "bad" not in _refused(lambda: keychain.set_key("dashscope", 'sk bad"key;')))
    check("an unknown key name is refused", "Unknown" in _refused(lambda: keychain.set_key("../etc", SENTINEL)))
    keychain.set_key("dashscope", SENTINEL)
    check("the key is stored and read back for the sender", keychain.configured("dashscope") and keychain.get_key("dashscope") == SENTINEL)
    check("the key never was a command-line argument of `security`",
          SENTINEL not in open(_STATE + ".argv", encoding="utf-8").read())
    open(_STATE + ".fail", "w").close()
    try:
        said = _refused(lambda: keychain.set_key("openrouter", SENTINEL))
    finally:
        os.remove(_STATE + ".fail")
    check("a Keychain failure says so without the key", "did not save" in said and SENTINEL not in said and not keychain.configured("openrouter"), said)
    check("listing providers shows yes or no per key and no key",
          SENTINEL not in json.dumps(providers.list_providers()) and
          next(p for p in providers.list_providers() if p["name"] == "dashscope_video")["configured"] is True)

    # --- what counts as an image or video part -----------------------------------------------------
    check("plain text is not media", not guard.has_media([{"role": "user", "content": "hello"}]))
    check("a text part is not media", not guard.has_media([{"role": "user", "content": [{"type": "text", "text": "hi"}]}]))
    check("an image part is media", guard.has_media([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]))
    check("a video part is media", guard.has_media({"input": {"media": [{"type": "first_clip", "url": "x"}]}}))
    check("a data URI is media", guard.has_media({"note": "data:image/png;base64,AAAA"}))

    # --- chat: the fixed address, the header, the refusals -------------------------------------------
    lib, ctx, s = _world()
    keychain.set_key("openrouter", SENTINEL)
    out = providers.get("openrouter").chat([{"role": "user", "content": "Say hi in French."}], None)
    c = s.calls[0]
    check("chat reaches only the fixed host and path", c["url"] == "https://openrouter.ai/api/v1/chat/completions" and out == "hello from the stub", c["url"])
    check("the key is only in the Authorization header, and redirects are not followed",
          c["headers"]["Authorization"] == "Bearer " + SENTINEL and c["allow_redirects"] is False and SENTINEL not in json.dumps(c["json"]))
    s.calls.clear()
    said = _refused(lambda: providers.get("openrouter").chat([{"role": "user", "content": [
        {"type": "text", "text": "what is this"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}], None))
    check("an image part is refused while the hosted-media switch is off, with no request", "switched off" in said and not s.calls, said)
    guard.SETTINGS["hosted_media"] = True
    providers.get("openrouter").chat([{"role": "user", "content": [
        {"type": "text", "text": "what is this"}, {"type": "image_url", "image_url": {"url": "x"}}]}], None)
    check("with the switch on the same request goes out", len(s.calls) == 1)
    guard.SETTINGS["hosted_media"] = False
    s.calls.clear()
    P.set_area("adult")
    said = _refused(lambda: providers.get("openrouter").chat([{"role": "user", "content": "hello"}], None))
    P.set_area("default")
    check("the 18+ area refuses chat, with no request", "18+" in said and not s.calls, said)
    said = _refused(lambda: providers.get("openrouter").chat([{"role": "user", "content": "a 16 year old girl"}], None))
    check("the prompt rails run on chat text, with no request", said != "" and not s.calls, said)
    s.fail_with = (401, {"code": "InvalidApiKey", "message": "Invalid key " + SENTINEL})
    said = _refused(lambda: providers.get("deepseek").chat([{"role": "user", "content": "hi"}], None))
    check("a deepseek call with no key says so; no request", "No DeepSeek key" in said and len(s.calls) == 0, said)
    keychain.set_key("deepseek", SENTINEL)
    said = _refused(lambda: providers.get("deepseek").chat([{"role": "user", "content": "hi"}], None))
    check("a service error keeps its short code and drops its own text (which echoed the key)",
          "HTTP 401" in said and "InvalidApiKey" in said and SENTINEL not in said, said)
    import requests
    s.fail_with, s.raise_error = None, requests.ConnectionError("boom " + SENTINEL)
    said = _refused(lambda: providers.get("deepseek").chat([{"role": "user", "content": "hi"}], None))
    check("a network error is reported without its text", "Could not reach" in said and SENTINEL not in said, said)

    # --- the Wan video provider ----------------------------------------------------------------------
    lib, ctx, s = _world()
    dv = providers.get("dashscope_video")
    handle = dv.video("a woman walks along a quiet beach", None, 6, None)
    body = s.calls[0]["json"]
    check("video goes to the fixed submit address with the async header",
          s.calls[0]["url"] == ENDPOINT and s.calls[0]["headers"]["X-DashScope-Async"] == "enable", s.calls[0]["url"])
    neg = body["input"]["negative_prompt"]
    check("the request asks for no prompt rewriting and no watermark, and carries the always-avoid words first",
          body["parameters"]["prompt_extend"] is False and body["parameters"]["watermark"] is False
          and len(neg) <= 500 and neg.startswith(safety.ALWAYS_NEGATIVE[:20]), neg[:60])
    check("words only: the words model, no picture part", body["model"] == "wan2.7-t2v" and "media" not in body["input"])
    check("seconds are held inside the service's range", dv.video("a quiet beach", None, 99, None)["seconds"] == 15 and dv.video("a quiet beach", None, 1, None)["seconds"] == 2)
    s.calls.clear()
    check("a running task says running", dv.poll(handle)["status"] == "running" and s.calls[-1]["url"].endswith("/api/v1/tasks/" + handle["task"]))
    folder = tempfile.mkdtemp()
    done = dv.poll(dict(handle, dir=folder))
    check("a finished task downloads the clip", done["status"] == "done" and open(done["file"], "rb").read() == CLIP)
    dl = s.calls[-1]
    check("the download carries no key and follows no redirect", dl.get("download") and "Authorization" not in dl["headers"] and dl["allow_redirects"] is False)
    s.calls.clear()
    s.task_polls, s.result_url = 1, "https://evil.example/clip.mp4"
    said = _refused(lambda: dv.poll(dict(handle, dir=folder)))
    check("a clip address off the service's domain is not opened", "will not open" in said and not [c for c in s.calls if c.get("download")], said)
    s.task_status = ["FAILED"]
    s.task_polls = 0
    check("a failed task reports failed with its short code", dv.poll(handle) == {"status": "failed", "file": None, "code": "DataInspectionFailed"})
    check("a task number is checked before it reaches a path", "not a task" in _refused(lambda: dv.poll({"task": "../../x"})))

    # --- the Video (API) job: every refusal first, no request on any of them ------------------------------
    def attempt(world, params):
        lib, ctx, s = world
        before = len(s.calls)
        said = _refused(lambda: PJ.job_video_api(ctx, params))
        return said, len(s.calls) - before

    words = {"text": "she smiles and turns to the camera", "seconds": 4, "stated_age": "30"}  # words that carry a person need a stated age
    w = _world()
    lib, ctx, s = w
    pic = _pic(lib)
    said, n = attempt(w, {"text": "she smiles", "image": pic["id"]})
    check("a picture with the hosted-media switch off is refused before any request", "switched off" in said and n == 0, (said, n))
    guard.SETTINGS["hosted_media"] = True
    P.set_area("adult")
    said, n = attempt(w, words)
    P.set_area("default")
    check("the 18+ area is refused before any request", "18+" in said and n == 0, (said, n))
    said, n = attempt(w, dict(words, owner_likeness=True))
    check("a likeness mark on the request is refused before any request", "likeness" in said and n == 0, (said, n))
    said, n = attempt(w, dict(words, advanced={"loras": [{"name": "my_style_lora.safetensors", "strength": 1}]}))
    check("any LoRA is refused before any request", "LoRA" in said and n == 0, (said, n))
    mark = _pic(lib, "own.png", owner_likeness=True)
    said, n = attempt(w, dict(words, image=mark["id"]))
    check("a picture carrying the likeness mark is refused before any request", "likeness" in said and n == 0, (said, n))
    child = _pic(lib, "child.png", parent=mark["id"])
    said, n = attempt(w, dict(words, image=child["id"]))
    check("a picture whose ancestor carries the mark is refused before any request", "likeness" in said and n == 0, (said, n))
    for label, meta in (("flagged", {"age_flag": True, "age_check": "flag"}), ("unchecked", {"age_check": "unchecked"}),
                        ("held", {"held": True}), ("no age check recorded", {"age_check": None})):
        bad = _pic(lib, f"bad_{label.split()[0]}.png", **meta)
        said, n = attempt(w, dict(words, image=bad["id"]))
        check(f"a picture whose age check is {label} is refused before any request", said != "" and n == 0, (said, n))
    lost = _pic(lib, "lost.png", parent="gone000000ab")
    said, n = attempt(w, dict(words, image=lost["id"]))
    check("a picture with a missing ancestor is refused before any request", said != "" and n == 0, (said, n))
    said, n = attempt(w, {"text": "a teen at school", "seconds": 4})
    check("the prompt rails run before any request", said != "" and n == 0, (said, n))
    keychain.delete_key("dashscope")
    said, n = attempt(w, words)
    check("no key saved: told to add one, before any request", "API keys" in said and n == 0, (said, n))
    keychain.set_key("dashscope", SENTINEL)

    # --- a good job end to end (stub HTTP), then the sentinel sweep ---------------------------------------------
    guard.SETTINGS["hosted_media"] = True
    ok_pic = _pic(lib, "ok.png")
    s.calls.clear()
    err, sout = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(sout), contextlib.redirect_stderr(err):
        said = _refused(lambda: PJ.job_video_api(ctx, {"text": "she smiles and turns to the camera", "seconds": 4, "image": ok_pic["id"],
                                                       "host": "evil.example", "base_url": "https://evil.example/"}))
    check("a good job with a cleared picture runs", said == "" and len(ctx.job["results"]) == 1, said)
    item = lib.get(ctx.job["results"][0]) if ctx.job["results"] else {}
    check("the clip is kept with remote: true, its age check recorded and its parent set",
          item.get("remote") is True and item.get("age_check") == "ok" and item.get("parent") == ok_pic["id"] and item.get("type") == "video", item)
    submit = [c for c in s.calls if c["method"] == "POST"]
    check("the request address is the constant, whatever the params say", [c["url"] for c in submit] == [ENDPOINT] and all(
        c["url"].startswith("https://dashscope-intl.aliyuncs.com/") for c in s.calls if not c.get("download")), [c["url"] for c in s.calls])
    check("the picture went as a first-frame part", submit[0]["json"]["input"]["media"][0]["type"] == "first_frame" and submit[0]["json"]["model"].startswith("wan2.7-i2v"))
    check("the clip's own mark follows a still taken from it", P._meta_from(item).get("remote") is True and P._meta_from(item).get("parent") == item["id"])
    guard.SETTINGS["hosted_media"] = False
    blobs = [json.dumps(ctx.job), json.dumps(guard.SETTINGS), sout.getvalue(), err.getvalue(),
             json.dumps({k: v for k, v in lib.items.items()})]
    for d, _s, fs in os.walk(lib.root):
        for f in fs:
            blobs.append(open(os.path.join(d, f), "rb").read().decode("latin-1"))
    check("the key is in no job record, library item, file, setting or output", not any(SENTINEL in b for b in blobs))
    check("nothing but the header ever held the key: not the request bodies", not any(SENTINEL in json.dumps(c["json"]) for c in s.calls))

    # --- a clip that fails the output check is deleted, not kept --------------------------------------------------------
    w2 = _world()
    lib2, ctx2, s2 = w2
    P.AGE_GUARD.mode = "flag"
    said, n = attempt(w2, words)
    check("a clip the age check flags is deleted and nothing is kept", "deleted" in said and ctx2.job["results"] == [] and not lib2.items and not [
        f for d, _s, fs in os.walk(ctx2.tmp) for f in fs if f.endswith(".mp4")], said)
    P.AGE_GUARD.mode = "ok"

    # --- extend: the last frame of a clip plus the instruction (the first priority) -----------------------------------------
    w4 = _world()
    lib4, ctx4, s4 = w4
    guard.SETTINGS["hosted_media"] = True
    tiny = os.path.join(HERE, "fixtures", "tiny.mp4")

    def _clip(**meta):
        base_meta = {"people": [{"age": 32}], "character": "c1", "age_check": "ok", "area": "default"}
        base_meta.update(meta)
        return lib4.add(tiny, "video:api", role="made", move=False, **base_meta)

    src = _clip()
    said, n = attempt(w4, {"text": "she turns and walks into the forest", "seconds": 5, "extend_from": src["id"]})
    sub = [c for c in s4.calls if c["method"] == "POST"]
    new_items = [i for i in lib4.items.values() if i.get("kind") == "video:api" and i.get("parent") == src["id"]]
    check("extend: the last frame and the instruction go out as one first-frame request, and the next clip comes back",
          said == "" and len(sub) == 1 and sub[0]["json"]["input"]["media"][0]["type"] == "first_frame"
          and sub[0]["json"]["model"].startswith("wan2.7-i2v") and len(new_items) == 1 and new_items[0].get("remote") is True, (said, len(sub)))
    body = sub[0]["json"]
    check("the prompt composer puts photographic, live-action wording first and the checked words after it",
          body["input"]["prompt"].startswith("Photographic, live-action footage") and "she turns and walks into the forest" in body["input"]["prompt"])
    neg = body["input"]["negative_prompt"]
    check("the negative carries the anime, cartoon, animated and 3D-render terms, after the always-avoid words, within 500 characters",
          all(t in neg for t in ("anime", "cartoon", "animated", "3D render")) and len(neg) <= 500 and neg.startswith(safety.ALWAYS_NEGATIVE[:20]), neg[:80])
    guard.SETTINGS["hosted_media"] = False
    n0 = len(s4.calls)
    said = _refused(lambda: PJ.job_video_api(ctx4, {"text": "she walks on", "extend_from": src["id"]}))
    check("extend: with the media switch off the last frame is not sent", "switched off" in said and len(s4.calls) == n0, said)
    guard.SETTINGS["hosted_media"] = True
    for label, meta in (("flagged", {"age_flag": True, "age_check": "flag"}), ("held", {"age_check": "unchecked"}),
                        ("carrying the likeness mark", {"owner_likeness": True}), ("with no age record", {"people": None})):
        bad = _clip(**meta)
        said, n = attempt(w4, {"text": "she walks on", "extend_from": bad["id"]})
        check(f"extend: a clip {label} is refused before any request", said != "" and n == 0, (said, n))
    kid = _clip(parent=_clip(owner_likeness=True)["id"])
    said, n = attempt(w4, {"text": "she walks on", "extend_from": kid["id"]})
    check("extend: a clip whose ancestor carries the mark is refused before any request", "likeness" in said and n == 0, (said, n))
    pic_not_clip = _pic(lib4, "notclip.png")
    said, n = attempt(w4, {"text": "she walks on", "extend_from": pic_not_clip["id"]})
    check("extend: a picture is not a clip to continue", said != "" and n == 0, (said, n))
    guard.SETTINGS["hosted_media"] = False

    # --- the choke point holds for any caller: another lane calling the provider or the helper directly ----------------------
    w5 = _world()
    lib5, ctx5, s5 = w5
    guard.SETTINGS["hosted_media"] = True
    raw = _pic(lib5, "raw.png")
    dv5 = providers.get("dashscope_video")
    said = _refused(lambda: dv5.video("she walks on", lib5.path(raw), 5, None))
    check("the provider sends no picture that was not cleared, switch on or not, and makes no request",
          "not cleared" in said and not s5.calls, said)
    mark5 = _pic(lib5, "mark5.png", owner_likeness=True)
    said = _refused(lambda: guard.clear_frame(mark5, P._lineage_get(ctx5), lib5.root, lib5.path(mark5)))
    check("a picture with the likeness mark cannot be cleared", "likeness" in said, said)
    guard.clear_frame(raw, P._lineage_get(ctx5), lib5.root, lib5.path(raw))
    dv5.video("she walks on", lib5.path(raw), 5, None)
    said = _refused(lambda: dv5.video("she walks on", lib5.path(raw), 5, None))
    check("a clearance is good for one send", len([c for c in s5.calls if c["method"] == "POST"]) == 1 and "not cleared" in said, said)
    s5.calls.clear()
    made = PJ.hosted_clip(ctx5, raw, "she walks on", 4)
    check("the helper other lanes call makes the clip with remote: true and the parent set",
          made.get("remote") is True and made.get("parent") == raw["id"] and made.get("type") == "video", made)
    guard.SETTINGS["hosted_media"] = False
    s5.calls.clear()
    P._LOCAL.area = None
    said = _refused(lambda: providers.get("openrouter").chat([{"role": "user", "content": "hello"}], None))
    P.set_area("default")
    check("a thread that never set its area is refused, with no request", "area" in said and not s5.calls, said)

    # --- never trained on ------------------------------------------------------------------------------------------------
    w3 = _world()
    lib3, ctx3, _ = w3
    clip_it = lib3.add(os.path.join(HERE, "fixtures", "tiny.mp4"), "video:api", role="made", remote=True, move=False,
                       people=[{"age": 32}], character="c1", age_check="ok")
    still = _pic(lib3, "still.png", parent=clip_it["id"])
    said = _refused(lambda: V3._check_training_source(ctx3, still, {"id": "c1"}))
    check("a picture made from a hosted clip is never a training picture", "never trained on" in said, said)
    plain = _pic(lib3, "plain.png")
    import lora_workshop
    check("the workshop trainer refuses a still carrying the remote mark too",
          lora_workshop.still_source_ok(dict(plain)) is True and lora_workshop.still_source_ok(dict(plain, remote=True)) is False)
    deep = _pic(lib3, "deep.png", parent=_pic(lib3, "mid.png", parent=clip_it["id"])["id"])
    check("the lineage walk finds a hosted clip several steps back",
          P.has_remote_ancestor(deep, P._lineage_get(ctx3)) is True and P.has_remote_ancestor(plain, P._lineage_get(ctx3)) is False)
    check("an ordinary picture still is one", _refused(lambda: V3._check_training_source(ctx3, plain, {"id": "c1"})) == "")
    check("the job kind is on the checker-required list", "video_api" in age_guard.CHECKER_REQUIRED_KINDS and "video_api" in P.JOBS)
    base.SESSION = None
    for k in ("dashscope", "openrouter", "deepseek"):
        keychain.delete_key(k)  # the server started next must see an empty Keychain


def e2e(a, out):
    print("\n[providers] The key panel's routes (stand-in Keychain; no job is run while a key is stored)")
    r = a.get("/api/providers")
    st = r.json()
    check = a.check
    check("the providers list answers, shows no key and the media switch off",
          r.status_code == 200 and st["hosted_media"] is False and all(k["configured"] is False for k in st["keys"]), st)
    j = a.job("video_api", {"text": "she smiles and turns to the camera", "seconds": 3, "stated_age": "30"})
    check("a Video (API) job with no key stored is refused plainly, with no request",
          j["status"] == "error" and "API keys" in (j.get("error") or ""), j)
    r = a.post("/api/providers/key", json={"name": "dashscope", "key": "short"})
    check("a bad key is refused with a fixed message", r.status_code == 400 and "short" not in r.text and "does not look like" in r.text, r.text)
    r = a.post("/api/providers/key", data="not json", headers={"Content-Type": "application/json"})
    check("an unreadable body is refused with a fixed message", r.status_code == 400 and "could not be read" in r.text, r.text)
    r = a.post("/api/providers/key", json={"name": "somewhere_else", "key": SENTINEL})
    check("an unknown key name is refused and the key is not echoed", r.status_code == 400 and SENTINEL not in r.text, r.text)
    r = a.post("/api/providers/key", json={"name": "dashscope", "key": SENTINEL})
    check("a good key is saved and the answer is yes or no only",
          r.status_code == 200 and SENTINEL not in r.text and [k for k in r.json()["keys"] if k["name"] == "dashscope"][0]["configured"] is True, r.text)
    check("reading the list again shows no key", SENTINEL not in a.get("/api/providers").text and SENTINEL not in a.get("/api/settings").text)
    r = a.post("/api/providers/hosted-media", json={"on": True})
    check("turning the media switch on needs the confirmation words", r.status_code == 400, r.text)
    r = a.post("/api/providers/hosted-media", json={"on": True, "confirm": "I understand"})
    check("with them it turns on, and can be turned off", r.json()["hosted_media"] is True and
          a.post("/api/providers/hosted-media", json={"on": False}).json()["hosted_media"] is False)
    a.s.delete(a.base + "/api/providers/key/dashscope", timeout=30)
    check("the key can be removed", a.get("/api/providers").json()["keys"][0]["configured"] is False)
    a.post("/api/providers/key", json={"name": "openrouter", "key": SENTINEL})
    leaked = []
    for d, _s, fs in os.walk(out):
        for f in fs:
            try:
                if SENTINEL.encode() in open(os.path.join(d, f), "rb").read():
                    leaked.append(f)
            except OSError:
                pass
    check("the key is in no file the app wrote, its log included", not leaked, leaked)
    check("the key was never an argument of `security`", SENTINEL not in open(_STATE + ".argv", encoding="utf-8").read())
    a.s.delete(a.base + "/api/providers/key/openrouter", timeout=30)
    check("the panel script is served", a.get("/static/providers.js").status_code == 200 and 'type: "password"' in a.get("/static/providers.js").text)


def tool_override_unit(check):
    """The Keychain tool can be swapped for a stand-in in a test run only."""
    from providers import keychain
    saved = {k: os.environ.get(k) for k in ("EASY_STUDIO_TEST_RUN", "EASY_STUDIO_SECURITY_TOOL")}
    try:
        os.environ["EASY_STUDIO_SECURITY_TOOL"] = "/tmp/stand-in-security"
        os.environ["EASY_STUDIO_TEST_RUN"] = "1"
        in_test = keychain._tool()
        os.environ.pop("EASY_STUDIO_TEST_RUN")
        alone = keychain._tool()
        os.environ["EASY_STUDIO_TEST_RUN"] = "0"
        off = keychain._tool()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("providers: the Keychain stand-in can be named in a test run only",
          in_test == "/tmp/stand-in-security" and alone == "/usr/bin/security" and off == "/usr/bin/security", (in_test, alone, off))
