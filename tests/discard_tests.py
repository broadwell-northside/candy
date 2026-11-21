"""Discard, never blur (D-C-51, with D-C-49a: in the 18+ section a flag is final).

A result the age check flags is deleted. The job says so plainly and offers a retry with a new seed. Nothing is saved,
nothing is shown blurred. The tests use a stand-in checker and tiny pictures; no engine and no model run.
"""
import inspect
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

from PIL import Image  # noqa: E402

import age_guard  # noqa: E402
import library  # noqa: E402
import owner_generate  # noqa: E402
import pipelines  # noqa: E402
import routes_retry  # noqa: E402

PLAIN = ("deleted", "new seed")


class _Guard:
    enabled = True

    def __init__(self, status="flag"):
        self.status = status

    def check(self, path):
        return age_guard.gate({"status": self.status, "faces": 1, "p_under21": 0.93, "reason": "A face may look under 21."})


def _ctx(root, status, area="default", params=None, kind=None):
    os.makedirs(os.path.join(root, "tmp"), exist_ok=True)
    lib = library.Library(root)
    pipelines.AGE_GUARD = _Guard(status)
    pipelines.set_area(area)
    job = {"id": "disc" + status[:3] + area[:2], "params": params or {}}
    if kind:
        job["kind"] = kind
    ctx = pipelines.JobContext(job, None, lib, None)
    return lib, ctx


def _picture(ctx, name="made.png"):
    path = os.path.join(ctx.tmp, name)
    Image.new("RGB", (64, 64), (255, 0, 255)).save(path)
    return path


def _add(ctx, path):
    try:
        ctx.add(path, "create")
    except age_guard.AgeCheckDiscarded as exc:
        return str(exc)
    return ""


def unit(check):
    print("\n[discard] A flagged result is deleted, never blurred")
    root = tempfile.mkdtemp(prefix="es_discard_")
    old_guard, old_area = pipelines.AGE_GUARD, pipelines.area()
    try:
        for section in ("default", "adult"):
            tag = "the 18+ section" if section == "adult" else "the everyday section"
            lib, ctx = _ctx(os.path.join(root, section), "flag", section)
            path = _picture(ctx)
            said = _add(ctx, path)
            check("a flagged picture is deleted in %s" % tag, said and not os.path.exists(path), said)
            check("a flagged picture is not saved in %s" % tag, not lib.items)
            check("the message says deleted and offers a new seed in %s" % tag, all(w in said for w in PLAIN), said)
            check("the job offers the retry in %s" % tag, ctx.job.get("can_retry") is True and ctx.job.get("results", []) == [])
            check("nothing blurred is left anywhere under the library in %s" % tag,
                  not [f for _r, _d, fs in os.walk(os.path.join(root, section)) for f in fs if f.endswith((".png", ".mp4")) and
                       "tmp" not in _r and "trash" not in _r])
            ctx.cleanup()
        # a later result is discarded after earlier ones were kept: the message says how many were kept
        lib, ctx = _ctx(os.path.join(root, "later"), "flag", "default")
        ctx.job["results"] = ["earlier-1", "earlier-2"]
        said = _add(ctx, _picture(ctx))
        check("a discard after earlier results says how many were kept, and still offers the retry",
              "The 2 earlier results of this job were kept." in said and ctx.job.get("can_retry") is True, said)
        ctx.job["results"] = ["earlier-1"]
        said = _add(ctx, _picture(ctx, "made2.png"))
        check("... in the singular for one", "The 1 earlier result of this job was kept." in said, said)
        ctx.job["results"] = []
        check("... and says nothing of earlier results when there are none", "earlier" not in _add(ctx, _picture(ctx, "made3.png")))
        ctx.cleanup()
        # a pass is kept as before, an unclear result is still held (not the discard path)
        lib, ctx = _ctx(os.path.join(root, "ok"), "ok")
        item = ctx.add(_picture(ctx), "create")
        check("a cleared picture is still kept", item["id"] in lib.items and item.get("age_check") == "ok" and not item.get("age_flag"))
        ctx.cleanup()
        lib, ctx = _ctx(os.path.join(root, "unc"), "unchecked")
        try:
            ctx.add(_picture(ctx), "create")
            held = False
        except age_guard.AgeCheckBlocked:
            held = True
        except age_guard.AgeCheckDiscarded:
            held = False
        check("an unchecked picture is still held by the checker rule, not saved", held and not lib.items)
        ctx.cleanup()
        # more than one result: the flagged one is deleted and the job stops; an earlier cleared one stays saved
        lib, ctx = _ctx(os.path.join(root, "two"), "ok")
        first = ctx.add(_picture(ctx, "a.png"), "create")
        pipelines.AGE_GUARD = _Guard("flag")
        said = _add(ctx, _picture(ctx, "b.png"))
        check("a later flagged result is deleted and the earlier cleared one stays",
              said and list(lib.items) == [first["id"]] and ctx.job["results"] == [first["id"]], said)
        ctx.cleanup()
    finally:
        pipelines.AGE_GUARD = old_guard
        pipelines.set_area(old_area)
        shutil.rmtree(root, ignore_errors=True)

    # the blur code is gone: nothing can produce a blurred copy of a flagged result
    check("age_guard has no blur function left", not [n for n in dir(age_guard) if "blur" in n.lower()])
    source = open(os.path.join(HERE, "..", "app", "age_guard.py"), encoding="utf-8").read()
    check("age_guard does not import an image filter", "ImageFilter" not in source and "GaussianBlur" not in source and "boxblur" not in source)
    check("the pipelines do not call a blur", "blur_in_place" not in open(os.path.join(HERE, "..", "app", "pipelines.py"), encoding="utf-8").read())

    # an older item that still carries the flag (made before the discard) stays blocked and unlisted-for-use
    legacy_root = tempfile.mkdtemp(prefix="es_legacy_")
    try:
        lib = library.Library(legacy_root)
        src = os.path.join(legacy_root, "old.png")
        Image.new("RGB", (32, 32), (20, 20, 20)).save(src)
        old_item = lib.add(src, "create", role="made", age_flag=True, age_check="flag", appearance_check={"status": "flag", "held": True})
        refused = []
        for fn in (lib.person_image, lib.ref_image):
            try:
                fn(old_item["id"])
            except PermissionError:
                refused.append(fn.__name__)
        check("an older flagged item can still not be used as a person or a reference", refused == ["person_image", "ref_image"], refused)
        check("an older flagged item is still blocked for reuse, training and export", age_guard.saved_blocked(old_item))
    finally:
        shutil.rmtree(legacy_root, ignore_errors=True)

    # D-C-49a: no setting or policy reaches the 18+ flag case
    names = list(inspect.signature(owner_generate.judge).parameters)
    check("the owner picture judge takes no setting and no policy", names == ["section", "age", "face", "match_set"], names)
    check("the discard path reads no setting", "SETTINGS" not in inspect.getsource(pipelines.JobContext.add))

    # the retry: the same job again, with a new seed in every place a job reads one
    print("\n[discard] The retry offers a new seed and goes through the normal queue")
    params = {"dna": {"seed": 5}, "count": 1, "seed": 7, "advanced": {"seed": 9, "steps": 12}}
    again = routes_retry.fresh_params(params)
    check("the retry's seeds are new", again["advanced"]["seed"] != 9 and again["seed"] != 7 and again["seed"] == again["advanced"]["seed"],
          (again["seed"], again["advanced"]))
    check("the retry keeps the rest and leaves the original alone",
          again["advanced"]["steps"] == 12 and again["dna"] == {"seed": 5} and params["advanced"]["seed"] == 9 and params["seed"] == 7)
    bare = routes_retry.fresh_params({"text": "x"})
    check("a job with no saved seed gets one", isinstance(bare["advanced"]["seed"], int) and "seed" not in bare)

    # every kind gets its seed in the place it reads it from, and no field it would refuse
    print("\n[discard] The new seed lands where each kind of job reads its seed")
    ws = routes_retry.fresh_params({"character": "c", "look": "x", "seed": 4}, "workshop_still")
    check("a workshop still gets a new top-level seed and no field it would refuse",
          set(ws) == {"character", "look", "seed"} and ws["seed"] != 4, ws)
    blank = routes_retry.fresh_params({"image": "i", "seconds": 5}, "film")
    check("a film with no typed seed gets one, and still only its own fields",
          set(blank) == {"image", "seconds", "seed"} and isinstance(blank["seed"], int), blank)
    graph = {"1": {"class_type": "KSampler", "inputs": {"seed": 5, "noise_seed": 6, "steps": 20, "text": "x", "model": ["9", 0]}},
             "2": {"class_type": "Other", "inputs": {"seed": ["1", 0], "flag": True}}}
    import json
    for label, wf in (("a dict", graph), ("a JSON string", json.dumps(graph))):
        out = routes_retry.fresh_params({"workflow": wf, "area": "x"}, "raw")
        got = json.loads(out["workflow"]) if isinstance(out["workflow"], str) else out["workflow"]
        seeds = {got["1"]["inputs"]["seed"], got["1"]["inputs"]["noise_seed"]}
        check("a raw workflow given as %s has every whole-number seed in its graph changed, nothing else" % label,
              len(seeds) == 1 and seeds != {5} and seeds != {6} and got["1"]["inputs"]["steps"] == 20 and got["1"]["inputs"]["text"] == "x"
              and got["1"]["inputs"]["model"] == ["9", 0] and got["2"]["inputs"]["seed"] == ["1", 0] and got["2"]["inputs"]["flag"] is True
              and type(out["workflow"]) is type(wf), got)
    check("a raw workflow that is not JSON is left as it was", routes_retry.fresh_params({"workflow": "not json"}, "raw")["workflow"] == "not json")
    check("the original raw workflow is left alone", graph["1"]["inputs"]["seed"] == 5)
    for kind in sorted(pipelines.RETRY_NO_SEED):
        lib, ctx = _ctx(os.path.join(root, "noseed" + kind), "flag", kind=kind)
        pipelines.AGE_GUARD = _Guard("flag")
        try:
            ctx.add(_picture(ctx), "create")
            said, can = "", None
        except age_guard.AgeCheckDiscarded as exc:
            said, can = str(exc), exc.can_retry
        check("%s: deleted, and it does not promise a new seed it cannot give" % kind,
              said and "deleted" in said and "new seed" not in said and can is False and ctx.job.get("can_retry") is False and not lib.items, said)
        ctx.cleanup()

    class Boom(Exception):
        pass

    class Server:
        class _App:
            def __init__(self):
                self.routes = {}

            def post(self, path):
                def deco(fn):
                    self.routes[path] = fn
                    return fn
                return deco

        def __init__(self):
            self.app = self._App()
            self.JOBS = {}
            self.sent = []
            self.unlocked = False

        def err(self, msg, code=400):
            raise Boom("%s %s" % (code, msg))

        def adult_unlocked(self, request):
            return self.unlocked

        def create_job(self, request, body):
            self.sent.append(body)
            return {"id": "new", "status": "queued"}

    server = Server()
    routes_retry.register(server)
    route = server.app.routes["/api/jobs/{jid}/retry"]

    def call(jid):
        try:
            return route(object(), jid)
        except Boom as exc:
            return str(exc)

    server.JOBS["a"] = {"id": "a", "kind": "create", "params": {"dna": {}, "advanced": {"seed": 1}}, "area": "default", "can_retry": True}
    server.JOBS["b"] = {"id": "b", "kind": "create", "params": {}, "area": "default"}
    server.JOBS["c"] = {"id": "c", "kind": "create", "params": {}, "area": "adult", "can_retry": True}
    check("a discarded job can be retried and goes to the normal job route with its area and kind",
          call("a") == {"id": "new", "status": "queued"} and server.sent[-1]["kind"] == "create" and server.sent[-1]["area"] == "default"
          and server.sent[-1]["params"]["advanced"]["seed"] != 1 and server.sent[-1]["request_id"])
    check("each retry carries its own request id (an old job is never handed back)",
          (call("a") and server.sent[-1]["request_id"]) != server.sent[-2]["request_id"])
    before = len(server.sent)
    server.JOBS["d"] = {"id": "d", "kind": "refine_skin", "params": {}, "area": "default", "can_retry": True}
    check("a tool with no seed to change cannot be retried this way, even if a job says so",
          "400" in str(call("d")) and len(server.sent) == before)
    server.JOBS["e"] = {"id": "e", "kind": "workshop_still", "params": {"character": "c", "look": "x"}, "area": "default", "can_retry": True}
    check("a retried workshop still goes through with a top-level seed only", call("e") and set(server.sent[-1]["params"]) == {"character", "look", "seed"})
    before = len(server.sent)
    check("a job that was not discarded cannot be retried this way", "400" in str(call("b")) and len(server.sent) == before)
    check("an unknown job is not found", "404" in str(call("zzz")))
    check("an 18+ job cannot be retried from a device that has not unlocked 18+", "404" in str(call("c")) and len(server.sent) == before)
    server.unlocked = True
    check("an unlocked device may retry an 18+ job, in the 18+ area", call("c") and server.sent[-1]["area"] == "adult")


def _seeds(a, jid):
    out = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("seed", "noise_seed") and isinstance(v, int):
                    out.append(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(a.get("/api/jobs/%s/workflow" % jid).json())
    return out


def _wait(a, jid, timeout=120):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = a.get("/api/jobs/%s" % jid).json()
        if j["status"] in ("done", "error", "cancelled", "blocked_age_check_unavailable"):
            return j
        time.sleep(0.25)
    return {"status": "timeout"}


def e2e(a, mock_url):
    """Through the real server: the mock engine returns a picture its stand-in age checker flags."""
    print("\n[discard] End to end: a flagged result is deleted, the job offers a new seed")
    dna = {"gender": "woman", "age": 29, "style": "photo", "name": "Flag"}
    before = len(a.get("/api/gallery?area=all").json()["items"])
    first = a.job("create", {"dna": dna, "count": 1, "extra_scene": "magentatest", "advanced": {"seed": 123}})
    check = a.check
    check("the everyday section: no result, an error that says deleted and new seed, retry offered",
          first["status"] == "error" and not first.get("results") and first.get("can_retry") is True
          and "deleted" in first.get("error", "") and "new seed" in first.get("error", ""), first)
    check("the job record never carries the job's parameters", "params" not in first)
    adult = a.job("create", {"dna": dna, "count": 1, "extra_scene": "magentatest"}, area="adult")
    check("the 18+ section: the same, and final (no result, nothing kept)",
          adult["status"] == "error" and not adult.get("results") and adult.get("can_retry") is True, adult)
    seeds_first = _seeds(a, first["id"])
    check("the first job ran with the seed it was given", 123 in seeds_first, seeds_first)
    r = a.post("/api/jobs/%s/retry" % first["id"])
    check("the retry is accepted", r.status_code == 200 and r.json().get("id") not in (None, first["id"]), r.text)
    if r.status_code == 200:
        again = _wait(a, r.json()["id"])
        seeds_again = _seeds(a, r.json()["id"])
        check("the retry ran with a new seed", seeds_again and 123 not in seeds_again, (seeds_first, seeds_again))
        check("the retry goes through every gate again (same text, flagged again, deleted again)",
              again["status"] == "error" and not again.get("results") and again.get("can_retry") is True, again)
    after = a.get("/api/gallery?area=all").json()["items"]
    check("nothing was saved by any of these jobs, and nothing flagged is listed", len(after) == before
          and not [i for i in after if i.get("age_flag")], (before, len(after)))
    done = a.job("create", {"dna": dna, "count": 1})
    check("a job that finished cleanly cannot be retried this way",
          done["status"] == "done" and a.post("/api/jobs/%s/retry" % done["id"]).status_code == 400, done.get("error"))
    check("an unknown job cannot be retried", a.post("/api/jobs/nosuchjob/retry").status_code == 404)
