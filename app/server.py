# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Easy Studio 3 -- the app server. Run:  python app/server.py

Serves the web page (app/static) and a small JSON API. All heavy work goes to ComfyUI
(COMFY_URL, default http://127.0.0.1:8188) one job at a time, in a background worker.
"""
import base64
import collections
import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import sys
import threading
import time
import traceback
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import assets  # noqa: E402
import catalog  # noqa: E402
import character as charmod  # noqa: E402
import comfy_client as cc  # noqa: E402
import age_guard  # noqa: E402
import loras as loramod  # noqa: E402
import pipelines  # noqa: E402
import pipelines_v3  # noqa: E402
import policy_gate  # noqa: E402
import props  # noqa: E402
import films  # noqa: E402
import stills  # noqa: E402
import creator_tools  # noqa: E402
import safety  # noqa: E402
import trainer  # noqa: E402
import videomodels  # noqa: E402
import wfdetect  # noqa: E402
from library import AreaView, Library, UPLOAD_ROLES, PERSON_ROLES  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.abspath(os.environ.get("EASY_STUDIO_OUTPUTS", os.path.join(ROOT, "outputs")))
creator_tools.set_root(OUT)
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
PASSWORD = os.environ.get("EASY_STUDIO_PASSWORD", "")


AUTO_PW = False  # True = password made up automatically; then this PC itself (127.0.0.1) doesn't need it


def _auto_password():
    """Open to the home network (HOST 0.0.0.0) with no password set? Make one up and keep it in
    outputs/password.txt, so nobody else on the Wi-Fi can browse the gallery. EASY_STUDIO_PASSWORD=off disables."""
    global PASSWORD, AUTO_PW
    if PASSWORD.lower() == "off":
        PASSWORD = ""
        return
    if PASSWORD or os.environ.get("EASY_STUDIO_HOST", "127.0.0.1") in ("127.0.0.1", "localhost"):
        return
    f = os.path.join(os.environ.get("EASY_STUDIO_OUTPUTS", os.path.join(ROOT, "outputs")), "password.txt")
    if os.path.exists(f):
        PASSWORD = open(f).read().strip()
    AUTO_PW = True
    if not PASSWORD:
        words = ["apple", "river", "candle", "tiger", "maple", "comet", "velvet", "harbor", "ember", "lotus", "pixel", "orbit"]
        PASSWORD = "-".join(secrets.choice(words) for _ in range(3)) + "-" + str(secrets.randbelow(90) + 10)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh:
            fh.write(PASSWORD + "\n")
    print(f"\n  Password for other devices: {PASSWORD}   (user name: anything)\n  (saved in {f})\n", flush=True)


_auto_password()

VERSION = "3.0.0"
MAX_UPLOAD = 50 * 1024 * 1024
MAX_LORA_UPLOAD = 4 * 1024 ** 3

# Where ComfyUI lives on this PC (for the LoRA folder, the age checker and the trainer). The installers put it
# next to the app; set COMFY_DIR if yours is elsewhere. If ComfyUI runs on another PC, LoRA files / training
# can't be managed from here (the rest still works).
COMFY_DIR = os.path.abspath(os.environ.get("COMFY_DIR", os.path.join(ROOT, "ComfyUI")))
_cp = [os.path.join(COMFY_DIR, "venv", "bin", "python"), os.path.join(COMFY_DIR, "venv", "Scripts", "python.exe"),
       os.path.join(ROOT, "python_embeded", "python.exe")]
COMFY_PYTHON = os.environ.get("COMFY_PYTHON") or next((p for p in _cp if os.path.exists(p)), sys.executable)
AGE_MODEL_DIR = os.environ.get("EASY_STUDIO_AGE_MODEL", os.path.join(COMFY_DIR, "models", "easy_studio", "age_check"))

os.makedirs(os.path.join(OUT, "tmp"), exist_ok=True)
LIB = Library(OUT)
CHARS = charmod.Store(OUT)
COMFY = cc.ComfyClient(COMFY_URL)
SETTINGS_FILE = os.path.join(OUT, "settings.json")


def load_settings():
    try:
        return {"age_check": True, **json.load(open(SETTINGS_FILE))}
    except Exception:
        return {"age_check": True}


SETTINGS = load_settings()
LORAS = loramod.LoraLibrary(COMFY_DIR if os.path.isdir(COMFY_DIR) else None)
AGE = age_guard.AgeGuard(AGE_MODEL_DIR, python=COMFY_PYTHON, enabled=bool(SETTINGS.get("age_check", True)))
pipelines.LORA_LIB = LORAS
pipelines.AGE_GUARD = AGE
import hardware_map  # noqa: E402
HARDWARE = hardware_map.HardwareMap.load(OUT, COMFY_URL)
pipelines.HARDWARE = HARDWARE
pipelines_v3.BYO_DIR = os.path.join(OUT, "byo")
pipelines_v3.COMFY_DIR = COMFY_DIR
pipelines_v3.ROOT = ROOT
os.makedirs(pipelines_v3.BYO_DIR, exist_ok=True)

app = FastAPI(title="Easy Studio", version=VERSION, docs_url=None, redoc_url=None, openapi_url=None)


# ---------------------------------------------------------------------------
# optional password (HTTP basic auth: any user name, the password from EASY_STUDIO_PASSWORD)
# ---------------------------------------------------------------------------
_LOOPBACK_NAMES = ("127.0.0.1", "localhost", "::1")
BIND_HOST = os.environ.get("EASY_STUDIO_HOST", "127.0.0.1")


def _host_name(value):
    """The name part of a Host header, without the port. "" when there is none."""
    value = str(value or "").strip().lower()
    if value.startswith("["):
        return value[1:].split("]", 1)[0]
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def host_refusal(request):
    """Why this request is not answered, or "".

    A web page can point its own name at this computer's loopback port and read the answers. So when the
    app is bound to this computer only (the default), every request has to name this computer. The owner's
    routes always do, and also have to come from this computer, even when the app is opened to the network.
    """
    name = _host_name(request.headers.get("host"))
    owner_route = request.url.path.startswith("/api/owner")
    if (owner_route or BIND_HOST in _LOOPBACK_NAMES) and name not in _LOOPBACK_NAMES:
        return "Request blocked (this app answers only on this computer's own address)."
    if owner_route and not (request.client is not None and request.client.host in ("127.0.0.1", "::1")):
        return "Request blocked (this part of the app answers only on this computer)."
    return ""


@app.middleware("http")
async def guard(request: Request, call_next):
    blocked = host_refusal(request)
    if blocked:
        return JSONResponse({"error": blocked}, status_code=403)
    # Other websites open in the same browser must not be able to start jobs or delete things:
    # every change needs a custom header, which browsers never let another site add (no CORS here).
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-easy-studio") != "1":
        return JSONResponse({"error": "Request blocked (missing app header)."}, status_code=403)
    local = request.client is not None and request.client.host in ("127.0.0.1", "::1")
    if PASSWORD and not (AUTO_PW and local):
        ok = False
        h = request.headers.get("authorization", "")
        if h.lower().startswith("basic "):
            try:
                _, pw = base64.b64decode(h[6:]).decode("utf-8", "replace").split(":", 1)
                ok = secrets.compare_digest(pw, PASSWORD)
            except Exception:
                ok = False
        if not ok:
            return Response("Password needed", status_code=401, headers={"WWW-Authenticate": 'Basic realm="Easy Studio"'})
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def err(msg, code=400):
    raise HTTPException(status_code=code, detail=msg)


_IMAGE_AGE_JOBS = {"edit", "inpaint", "outfit_locked", "contact_repair", "video", "remove_bg", "bg_quick",
                     "upscale", "turnaround", "expressions", "model3d", "creator_outfit"}
_VIDEO_AGE_JOBS = {"extend", "video_still", "sprites"}
_CHAR_AGE_JOBS = {"pose_new", "photoshoot", "regenerate", "export", "workshop_still", "keep_face", "refine_skin", "refine_anatomy"}


def _record_for_item(it, depth=0):
    """Declared age record hanging off a gallery item. Does not invent one."""
    if not isinstance(it, dict) or depth > 5:
        return None
    dna = it.get("dna")
    if isinstance(dna, dict) and safety.explicit_age_fields(dna):
        return dna
    if it.get("stated_age") is not None:
        return {"age": it.get("stated_age")}
    if it.get("character"):
        try:
            ch = CHARS.get(it["character"])
            if isinstance(ch, dict) and safety.explicit_age_fields(ch):
                return ch
        except Exception:
            pass
    parent = LIB.items.get(it.get("parent") or "")
    if parent:
        return _record_for_item(parent, depth + 1)
    return None


def _gate_create_ages(params):
    """One admitted shape: a list of person records, top-level or nested, each 21+."""
    raw = params.get("dna") if isinstance(params.get("dna"), dict) else None
    if raw and safety.people_in(raw) and safety.explicit_age_fields(raw) and not isinstance(params.get("people"), list):
        err("Unsupported group shape: a group container cannot also carry its own age.")
    records = safety.scene_records(params)
    if not records:
        err("Missing stated age: age is missing.")
    if len(records) > 1 or isinstance(params.get("people"), list) or (raw and safety.people_in(raw)):
        ok, _, msg = safety.require_group_ages({"people": records})
    else:
        ok, _, msg = safety.require_stated_age(records[0])
    if not ok:
        err(msg)
    ok, msg = safety.check_group_prompt(str(params.get("extra_scene") or ""), records)
    if not ok:
        err(msg)


def _refuse_scenery_as_person(params):
    """A scenery photo is a place. It is not a person input for any other tool."""
    if not isinstance(params, dict):
        return
    messages = {
        "image": "This photo is a place, not a person. It cannot be a character, a face swap, or a clothing-removal edit.",
        "video": "This photo is a place, not a person. It cannot be a character, a face swap, or a clothing-removal edit.",
        "end_image": "This photo is a place, not a person. It cannot be a character, a face swap, or a clothing-removal edit.",
        "ref": "This photo is a place, not a person. It cannot be a character reference, a face swap, or a clothing-removal edit.",
        "background": "This photo is a place, not a person. It cannot be a character reference, a face swap, or a clothing-removal edit.",
    }
    for key, message in messages.items():
        iid = params.get(key)
        if not isinstance(iid, str):
            continue
        it = LIB.items.get(iid)
        if isinstance(it, dict) and (it.get("role") == "scenery" or it.get("place") is True):
            err(message)


def _gate_stated_ages(params, kind=""):
    """Refuse a person-producing job before it is queued unless every person has a stated age."""
    if not isinstance(params, dict):
        err("Missing stated age: age is missing.")
    if kind == "create":
        _gate_create_ages(params)
        return
    people = params.get("people") if isinstance(params.get("people"), list) else None
    dna = params.get("dna") if isinstance(params.get("dna"), dict) else None
    if people is not None:
        ok, _, msg = safety.require_group_ages({"people": people})
        if not ok:
            err(msg)
        if isinstance(dna, dict) and safety.explicit_age_fields(dna):
            ok, _, msg = safety.require_stated_age(dna)
            if not ok:
                err(msg)
        return
    if isinstance(dna, dict):
        if safety.people_in(dna) and not safety.explicit_age_fields(dna):
            ok, _, msg = safety.require_group_ages(dna)
            if not ok:
                err(msg)
            return
        ok, _, msg = safety.require_stated_age(dna)
        if not ok:
            err(msg)
        return
    if kind == "create":
        err("Missing stated age: age is missing.")
    if kind == "raw":
        _gate_raw_ages(params.get("workflow"))
        return
    if kind in _CHAR_AGE_JOBS:
        try:
            ch = CHARS.get(params.get("character") or "")
        except Exception:
            ch = None
        if not isinstance(ch, dict):
            err("Missing stated age: age is missing.")
        ok, _, msg = safety.require_stated_age(ch)
        if not ok:
            err(msg)
        return
    if kind in _IMAGE_AGE_JOBS or kind in _VIDEO_AGE_JOBS:
        iid = params.get("image") or params.get("video")
        it = LIB.items.get(iid or "")
        if not it:
            err("Missing stated age: age is missing. This picture has no per-person age record.")
        rec = _record_for_item(it)
        if not rec:
            err("Missing stated age: age is missing. This picture has no per-person age record.")
        ok, _, msg = safety.require_stated_age(rec)
        if not ok:
            err(msg)


def _gate_raw_ages(workflow):
    """A raw person workflow is unavailable until an explicit age record is bound."""
    wf = workflow
    if isinstance(wf, str):
        try:
            wf = json.loads(wf)
        except ValueError:
            return
    if not isinstance(wf, dict):
        err("This raw workflow is unavailable without an explicit per-person age record.")
    bound = False
    for node in wf.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") not in ("LoadImage", "LoadImageOutput", "LoadVideo"):
            continue
        img = (node.get("inputs") or {}).get("image") or (node.get("inputs") or {}).get("file")
        if not isinstance(img, str) or not img.startswith("es_"):
            err("This raw workflow is unavailable without an explicit per-person age record.")
        iid = img[3:].split(".")[0]
        it = LIB.items.get(iid)
        rec = _record_for_item(it) if it else None
        if not rec:
            err("Missing stated age: age is missing. This picture has no per-person age record.")
        ok, _, msg = safety.require_stated_age(rec)
        if not ok:
            err(msg)
        bound = True
    if not bound:
        err("This raw workflow is unavailable without an explicit per-person age record.")


# ---------------------------------------------------------------------------
# jobs: one worker thread, one ComfyUI job at a time
# ---------------------------------------------------------------------------
JOBS = collections.OrderedDict()
QUEUE = queue.Queue()
JOB_LOCK = threading.Lock()


def public_job(j):
    return {k: j.get(k) for k in ("id", "kind", "status", "progress", "message", "error", "created", "started",
                                  "finished", "position", "area", "warning", "lora", "recipe", "can_retry")} | {
        "results": [item_json(LIB.items[i]) for i in j.get("results", []) if i in LIB.items],
        "has_workflow": bool(j.get("workflows")), "request_id": j.get("request_id")}


def worker():
    while True:
        jid = QUEUE.get()
        j = JOBS.get(jid)
        if not j or j.get("cancel"):
            if j:
                j.update(status="cancelled", finished=time.time())
            continue
        j.update(status="running", started=time.time(), message="Starting ...", progress=0.0)
        pipelines.set_area(j.get("area"))
        ctx = pipelines.JobContext(j, COMFY, AreaView(LIB, j.get("area")), CHARS)
        try:
            pipelines.JOBS[j["kind"]](ctx, j["params"])
            j.update(status="done", progress=1.0, message=j["message"] if str(j.get("message") or "").startswith("Done.") else "Done")
        except pipelines.Cancelled:
            j.update(status="cancelled", message="Stopped")
        except age_guard.AgeCheckBlocked as e:
            j.update(status=age_guard.BLOCKED_AGE_CHECK, error=str(e))
        except age_guard.AgeCheckDiscarded as e:  # a flagged result was deleted (D-C-51); the page offers a new seed
            j.update(status="error", error=str(e), can_retry=e.can_retry)
        except pipelines.UserError as e:
            j.update(status="error", error=str(e))
        except cc.ComfyError as e:
            j.update(status="error", error=str(e))
        except trainer.TrainerBaseMissing as e:  # a trainer base that is not on this computer: the message says what to press
            j.update(status="error", error=str(e))
        except Exception as e:  # pragma: no cover
            traceback.print_exc()
            j.update(status="error", error=f"Something went wrong: {e}")
        finally:
            j["finished"] = time.time()
            ctx.cleanup()
            _tag_results(j)
            _refresh_positions()


def _refresh_positions():
    n = 0
    for j in JOBS.values():
        if j["status"] == "queued":
            n += 1
            j["position"] = n
        else:
            j["position"] = 0


threading.Thread(target=worker, daemon=True).start()


def _recipe_tag(raw):
    """Recipe bookkeeping a page may attach to a job: the cache key and canonical hash it compiled.
    Only short hex strings and a short name are kept; nothing here changes what the job does."""
    if not isinstance(raw, dict):
        return None
    out = {}
    for key in ("cache_key", "canonical_hash"):
        value = raw.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            out[key] = value
    name = raw.get("name")
    if isinstance(name, str) and name.strip() and safety.check_prompt(name)[0]:
        out["name"] = name.strip()[:80]
    return out or None


def _tag_results(j):
    recipe = j.get("recipe")
    if not recipe or j.get("status") != "done":
        return
    for iid in j.get("results", []):
        try:
            LIB.tag(iid, recipe_cache_key=recipe.get("cache_key"), recipe_hash=recipe.get("canonical_hash"),
                    recipe=recipe.get("name"), sha256=_file_sha(LIB.path(LIB.items[iid])))
        except (KeyError, OSError):
            pass


def _file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@app.post("/api/jobs")
def create_job(request: Request, body: dict = Body(...)):
    area = want_area(request, body.get("area"))
    kind = body.get("kind")
    if kind not in pipelines.JOBS:
        err("Unknown tool.")
    params = body.get("params") or {}
    if not isinstance(params, dict):
        err("Bad request.")
    blob = json.dumps(params)
    if len(blob) > 8 * 1024 * 1024:
        err("Request too large.")
    # quick up-front text check so obvious refusals come back instantly (the pipelines check again)
    for k in ("text", "extra_scene", "name", "notes", "look"):
        if isinstance(params.get(k), str):
            ok, msg = safety.check_prompt(params[k])
            if ok:
                ok, msg = safety.check_area(params[k], area)
            if not ok:
                err(msg)
    if kind in ("train_lora", "train_dataset") and any(j["kind"] == "train_lora" and j["status"] in ("queued", "running")
                                                      for j in JOBS.values()):
        err("A training run is already waiting or running. Wait for it to finish first.")
    request_id = str(body.get("request_id") or "")[:80]
    if request_id:
        for old in JOBS.values():
            if old.get("request_id") == request_id and old.get("kind") == kind:
                return public_job(old)
    if kind != "prop":
        _refuse_scenery_as_person(params)
    _gate_stated_ages(params, kind)
    if kind in ("workshop_still", "keep_face", "refine_skin", "refine_anatomy"):
        try:
            stills.gate(kind, params, area, CHARS.get, LIB.items.get)
        except stills.StillError as exc:
            err(str(exc))
    if kind == "prop":
        try:
            props.gate(params, area, CHARS.get, LIB.items.get)
        except props.PropError as exc:
            err(str(exc))
    if kind == "film":
        try:
            films.gate(params, area, CHARS.get, LIB.items.get)
        except films.FilmError as exc:
            err(str(exc))
    if kind == "export_godot":
        try:
            export_character = CHARS.get(params.get("character") or "")
        except Exception:
            export_character = None
        if not isinstance(export_character, dict):
            err("Pick a saved character first.")
        try:
            pipelines_v3.export_age(export_character)
        except pipelines.UserError as exc:
            err(str(exc))
        if params.get("creator_pack"):
            # Feature 18 (pre-export hold), from PR #39: a held pack is not sent.
            creator_tools.set_root(OUT)
            pack_state = creator_tools.load_state(OUT)
            pack_item = LIB.items.get(params.get("pack_item") or "")
            pack = creator_tools.pack_status(
                export_character, pack_item if isinstance(pack_item, dict) else None,
                pack_state.get("face"), pack_state.get("reviews") or [])
            if pack["held"]:
                err(pack["message"])
    if kind == "creator_outfit":
        # Feature 12 (outfit try-on), from PR #39.
        try:
            outfit_item = LIB.get(str(params.get("image") or ""))
            outfit_ref = LIB.get(str(params.get("ref") or ""))
        except KeyError:
            err("Pick a still and a clothing reference.")
        outfit_character = None
        if outfit_item.get("character"):
            try:
                outfit_character = CHARS.get(outfit_item["character"])
            except Exception:
                outfit_character = None
        try:
            creator_tools.outfit_source_ok(
                outfit_item, outfit_character if isinstance(outfit_character, dict) else None,
                params.get("text") or "", params.get("confirm"))
            creator_tools.clothing_ref_ok(outfit_ref)
        except ValueError as exc:
            err(str(exc))
    if kind == "lora_benchmark":
        ok, _, msg = safety.require_stated_age({"age": params.get("stated_age")})
        if not ok:
            err(msg)
        bench_prompt = str(params.get("prompt") or "")
        if bench_prompt:
            ok, msg = safety.check_prompt(bench_prompt)
            if ok:
                ok, msg = safety.check_area(bench_prompt, area)
            if not ok:
                err(msg)
            ok, msg = safety.reconcile_prompt_ages(bench_prompt, [{"age": params.get("stated_age")}])
            if not ok:
                err(msg)
    if age_guard.checker_blocks(kind, AGE.enabled):
        err(age_guard.CHECKER_OFF_REASON)
    if kind == "raw":
        wf = params.get("workflow")
        if isinstance(wf, str):
            try:
                wf = json.loads(wf)
            except ValueError:
                err("That text isn't valid JSON.")
        ok, msg = safety.check_workflow(wf)
        if not ok:
            err(msg)
    try:  # the owner's own policy, only after every fixed gate above; it can add a refusal and never lift one (D-C-50)
        policy_gate.enforce(params, area, kind, OUT)
    except policy_gate.PolicyRefused as exc:
        err(str(exc))
    owner_id = routes_owner.gate_job(request, kind, area)  # None for a job that is not the owner's
    with JOB_LOCK:
        jid = uuid.uuid4().hex[:10]
        JOBS[jid] = {"id": jid, "kind": kind, "params": params, "status": "queued", "progress": 0.0, "area": area,
                     "message": "Waiting in line", "created": time.time(), "results": [], "request_id": request_id or None}
        if owner_id:
            JOBS[jid]["owner"] = owner_id
        recipe = _recipe_tag(body.get("recipe"))
        if recipe:
            JOBS[jid]["recipe"] = recipe
        while len(JOBS) > 200:
            old = next(iter(JOBS))
            if JOBS[old]["status"] in ("queued", "running"):
                break
            JOBS.pop(old)
        _refresh_positions()
    QUEUE.put(jid)
    return public_job(JOBS[jid])


@app.get("/api/jobs")
def list_jobs(request: Request, area: str = ""):
    a = want_area(request, area)
    return [public_job(j) for j in reversed(JOBS.values()) if (j.get("area") or "default") == a][:50]


@app.get("/api/jobs/{jid}")
def get_job(request: Request, jid: str):
    if jid not in JOBS or (JOBS[jid].get("area") == "adult" and not adult_unlocked(request)):
        err("No such job", 404)
    return public_job(JOBS[jid])


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    j = JOBS.get(jid) or err("No such job", 404)
    j["cancel"] = True
    if j["status"] == "running":
        try:
            COMFY.cancel(COMFY.active_prompt_id)
        except cc.ComfyError as e:
            j["warning"] = str(e)
    elif j["status"] == "queued":
        j.update(status="cancelled", message="Stopped")
    _refresh_positions()
    return public_job(j)


@app.get("/api/jobs/{jid}/workflow")
def job_workflow(jid: str):
    j = JOBS.get(jid) or err("No such job", 404)
    return {"workflows": j.get("workflows", [])}


# ---------------------------------------------------------------------------
# gallery + uploads + files
# ---------------------------------------------------------------------------
def item_json(it):
    d = {k: v for k, v in it.items() if k != "dna"}
    d["url"] = LIB.url(it)
    return d


@app.get("/api/gallery")
def gallery(request: Request, character: str = "", project: str = "", type: str = "", favourites: bool = False,
            role: str = "", limit: int = 300, area: str = ""):
    a = want_area(request, area)
    items = LIB.list(character=character or None, project=project or None, type=type or None,
                     favourites=favourites, role=role or None, limit=max(1, min(2000, limit)), area=a)
    items = [i for i in items if not i.get("age_flag")]  # nothing flagged is shown, blurred or otherwise (D-C-51)
    return {"items": [item_json(i) for i in items], "projects": LIB.projects(a), "area": a}


def _item_for(request, iid):
    """An item, but 18+ items only for a device that unlocked the 18+ section."""
    try:
        it = LIB.get(iid)
    except KeyError as e:
        err(str(e), 404)
    if (it.get("area") or "default") == "adult" and not adult_unlocked(request):
        err("No such item", 404)
    return it


@app.get("/api/items/{iid}")
def get_item(request: Request, iid: str):
    return item_json(_item_for(request, iid))


@app.patch("/api/items/{iid}")
def patch_item(request: Request, iid: str, body: dict = Body(...)):
    _item_for(request, iid)
    if "title" in body:
        ok, msg = safety.check_prompt(str(body["title"]))
        if not ok:
            err(msg)
    if "project" in body and body["project"]:
        body["project"] = str(body["project"])[:80]
        ok, msg = safety.check_prompt(body["project"])
        if not ok:
            err(msg)
    try:
        return item_json(LIB.update(iid, **body))
    except KeyError as e:
        err(str(e), 404)


@app.delete("/api/items/{iid}")
def delete_item(request: Request, iid: str):
    _item_for(request, iid)
    try:
        LIB.delete(iid)
    except KeyError as e:
        err(str(e), 404)
    return {"ok": True}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...), role: str = Form(...), confirm: str = Form(""),
                 area: str = Form(""), age: str = Form("")):
    a = want_area(request, area)
    if role not in UPLOAD_ROLES:
        err("Pick what this picture is.")
    if confirm != "yes":
        err("Please tick the box to confirm the picture is allowed (see the text next to it).")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        err("That file is bigger than 50 MB.")
    ok, msg = safety.check_prompt(re.sub(r"[_\-.]+", " ", file.filename or ""))
    if not ok:
        err(msg)
    tmp_in = os.path.join(OUT, "tmp", "up_" + uuid.uuid4().hex)
    with open(tmp_in, "wb") as f:
        f.write(data)
    out = tmp_in + ".png"
    try:
        assets.to_png(tmp_in, out)
    except Exception:
        err("That doesn't look like a picture (PNG, JPG or WebP please).")
    finally:
        if os.path.exists(tmp_in):
            os.remove(tmp_in)
    base = re.sub(r"\.[A-Za-z0-9]+$", "", os.path.basename(file.filename or "upload"))[:40]
    final = os.path.join(OUT, "tmp", f"upload_{role}_{base}.png")
    os.replace(out, final)
    meta = {"area": a}
    if role == "my_character":  # declared age first; the appearance check never supplies it
        ok, stated, msg = safety.require_stated_age({"age": age})
        if not ok:
            os.remove(final)
            err(msg)
        meta["stated_age"] = stated
        meta["dna"] = {"age": stated, "stated_age": stated, "age_source": "stated"}
        res = AGE.check(final)
        appearance = dict(res.get("appearance_check") or {})
        appearance.pop("age", None)
        appearance.pop("stated_age", None)
        meta["age_check"] = res.get("status")
        meta["appearance_check"] = appearance
        if age_guard.held_unusable(res):
            os.remove(final)
            err("Held by the age check (" + str(res.get("status")) + "); this picture was not saved for use. "
                + str(res.get("reason") or ""))
        if res.get("status") == "flag":
            os.remove(final)
            err("The automatic age check thinks this character may look under 21, so it can't be used. "
                "Easy Studio only works with clearly adult (21+) characters.")
    if role == "scenery":
        try:
            meta.update(props.screen_scenery(final, AGE.check))
        except props.PropError as exc:
            if os.path.exists(final):
                os.remove(final)
            err(str(exc))
    it = LIB.add(final, "upload", role=role, title=base, confirmed=True, **meta)
    return item_json(it)


_FILE_AREA = {}


def _file_area(rel):
    a = _FILE_AREA.get(rel)
    if a is None:
        for it in list(LIB.items.values()):
            _FILE_AREA[it["file"].replace(os.sep, "/")] = it.get("area") or "default"
        a = _FILE_AREA.get(rel, "adult")  # unknown file: treat as private
    return a


@app.get("/files/{path:path}")
def files(request: Request, path: str):
    full = os.path.abspath(os.path.join(OUT, path))
    if not full.startswith(os.path.join(OUT, "files") + os.sep) or not os.path.isfile(full):
        err("Not found", 404)
    if _file_area(os.path.relpath(full, OUT).replace(os.sep, "/")) == "adult" and not adult_unlocked(request):
        err("Not found", 404)
    media = None
    if full.endswith(".glb"):
        media = "model/gltf-binary"
    return FileResponse(full, media_type=media)


# ---------------------------------------------------------------------------
# characters
# ---------------------------------------------------------------------------
def _check_hero(dna):
    if dna.get("hero"):
        try:
            it = LIB.person_image(dna["hero"])
        except (KeyError, PermissionError, ValueError) as e:
            err(str(e))
        if pipelines.is_proof(it, LIB.get):  # D-C-28: a proof is never promoted to a character's portrait
            err("A picture from an unscored motion proof can't be a character's portrait.")


@app.get("/api/characters")
def characters(request: Request):
    out = []
    unlocked = adult_unlocked(request)
    for c in CHARS.list():
        c = dict(c)
        if c.get("hero") in LIB.items and (LIB.items[c["hero"]].get("area") != "adult" or unlocked):
            c["hero_url"] = LIB.url(LIB.items[c["hero"]])
        c["count"] = sum(1 for i in LIB.items.values() if i.get("character") == c["id"])
        out.append(c)
    return out


@app.post("/api/characters")
def save_character(body: dict = Body(...)):
    _gate_stated_ages({"dna": body if isinstance(body, dict) else {}})
    dna, msg = charmod.normalise(body)
    if msg:
        err(msg)
    import photoreal
    try:
        old = CHARS.get(dna["id"])
    except Exception:
        old = None
    dna["spec_version"] = 4
    dna["body_card"] = photoreal.body_card(dna)
    if old:
        hist = list(old.get("versions") or [])
        hist.append({"spec_version": old.get("spec_version") or 3, "updated": old.get("updated")})
        dna["versions"] = hist[-12:]
    _check_hero(dna)
    try:
        old = CHARS.get(dna["id"])
        dna["created"] = old.get("created", dna["created"])
    except Exception:
        pass
    kept = stills.kept_look(old.get("look") if isinstance(old, dict) else None)
    if kept:
        dna["look"] = kept
    CHARS.save(dna)
    if dna.get("hero") in LIB.items:  # tag the portrait with this character
        LIB.update(dna["hero"], character=dna["id"])
    return dna


@app.get("/api/characters/{cid}")
def get_character(cid: str):
    try:
        return CHARS.get(cid)
    except Exception:
        err("No such character", 404)


@app.post("/api/characters/{cid}/duplicate")
def duplicate_character(cid: str):
    try:
        c = dict(CHARS.get(cid))
    except Exception:
        err("No such character", 404)
    c.update(id=uuid.uuid4().hex[:10], name=(c["name"] + " (sister)")[:60], hero="", seed=pipelines._rand_seed(),
             created=time.time())
    _gate_stated_ages({"dna": c})
    dna, msg = charmod.normalise(c)
    if msg:
        err(msg)
    return CHARS.save(dna)


@app.delete("/api/characters/{cid}")
def delete_character(cid: str):
    try:
        CHARS.delete(cid)
    except Exception:
        err("No such character", 404)
    return {"ok": True}


# ---------------------------------------------------------------------------
# status, catalog, advanced options
# ---------------------------------------------------------------------------
FEATURES = [
    ("create_photo", "Create: realistic still", ["image_zimage_turbo_api.json"]),
    ("create_film", "Create: film look", ["image_krea2_api.json"]),
    ("create_draft", "Create: draft", ["image_flux2_klein_api.json"]),
    ("create_flux", "Create: Flux.1 dev (needs a Hugging Face login for the weights)", ["image_flux1dev_api.json"]),
    ("create_chroma", "Create: 18+ fallback", ["image_chroma1hd_api.json"]),
    ("create_fast", "Create: fast drafts", ["image_zimage_turbo_api.json"]),
    ("create_anime", "Create: anime", ["image_noobai_xl_api.json"]),
    ("edit", "Outfit / pose / scene / object edits", ["edit_qwen2511_api.json"]),
    ("turnaround", "Turnaround sheet", ["angles_qwen2511_api.json"]),
    ("paint", "Paint-to-change", ["inpaint_chroma1hd_api.json", "inpaint_noobai_xl_api.json"]),
    ("remove_bg", "Background remover", ["remove_bg_api.json"]),
    ("upscale", "Upscaler", ["upscale_api.json"]),
    ("pose_read", "Copy a pose", ["pose_extract_api.json"]),
    ("pose_new", "New picture in a pose", ["pose_zimage_api.json"]),
    ("video", "Video (fast + best)", ["video_wan22_i2v_fast_api.json", "video_wan22_flf2v_fast_api.json"]),
    ("video_t2v", "Video studio: Wan 2.2 text to video (optional)", ["vm_wan22_t2v_api.json"]),
    ("video_wan5b", "Video studio: Wan 2.2 5B (optional)", ["vm_wan22_5b_t2v_api.json", "vm_wan22_5b_i2v_api.json"]),
    ("video_ltx", "Video studio: LTX-2.5 with sound (optional, needs HF login)", ["vm_ltx25_t2v_api.json"]),
    ("video_hunyuan", "Video studio: HunyuanVideo 1.5 (optional)", ["vm_hunyuan15_t2v_api.json", "vm_hunyuan15_i2v_api.json"]),
    ("video_kandinsky", "Video studio: Kandinsky 5 Lite (optional)", ["vm_kandinsky5_t2v_api.json", "vm_kandinsky5_i2v_api.json"]),
    ("model3d", "3D models (TRELLIS.2)", ["3d_trellis2_api.json"]),
    ("model3d_shape", "3D clay shape (Hunyuan3D, optional)", ["3d_hunyuan21_shape_api.json"]),
]
LOADERS = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name", "VAELoader": "vae_name",
           "CheckpointLoaderSimple": "ckpt_name", "LoraLoaderModelOnly": "lora_name",
           "UpscaleModelLoader": "model_name", "ModelPatchLoader": "name", "CLIPVisionLoader": "clip_name",
           "LoadBackgroundRemovalModel": "bg_removal_name", "ImageOnlyCheckpointLoader": "ckpt_name"}
_cache = {"t": 0, "files": None, "info": {}}


def _group_of(filename):
    try:
        sys.path.insert(0, os.path.join(ROOT, "install"))
        import download_models as dm
        for g, lst in dm.MODELS.items():
            for _folder, name, _url, _size in lst:
                if os.path.basename(name) == filename:
                    return g
    except Exception:
        pass
    return None


def comfy_files():
    if time.time() - _cache["t"] < 20 and _cache["files"] is not None:
        return _cache["files"], _cache["info"]
    files, info = set(), {}
    try:
        allinfo = COMFY.object_info()
        for cls, key in LOADERS.items():
            spec = (allinfo.get(cls, {}).get("input", {}).get("required", {}) or {}).get(key)
            if spec:
                opts = spec[0] if isinstance(spec[0], list) else spec[1].get("options", [])
                files.update(os.path.basename(o) for o in opts)
        info = allinfo
    except Exception:
        files = None
    _cache.update(t=time.time(), files=files, info=info)
    return files, info


def workflow_models(names):
    need = []
    for n in names:
        wf = cc.load_workflow(n)
        for node in wf.values():
            k = LOADERS.get(node["class_type"])
            if k and isinstance(node["inputs"].get(k), str):
                need.append(os.path.basename(node["inputs"][k]))
    return sorted(set(need))


@app.get("/api/status")
def status(request: Request):
    up = COMFY.is_up()
    gpu, version = None, None
    if up:
        try:
            st = COMFY.system_stats()
            dev = (st.get("devices") or [{}])[0]
            gpu = {"name": dev.get("name"), "vram_gb": round((dev.get("vram_total") or 0) / 1024**3, 1)}
            version = st.get("system", {}).get("comfyui_version")
        except Exception:
            pass
    # An unavailable inventory yields no known missing files. Keep readiness false
    # until the engine has actually reported which model files it can see.
    files = comfy_files()[0] if up else None
    feats = []
    for fid, label, wfs in FEATURES:
        need = workflow_models(wfs)
        missing = [m for m in need if files is not None and m not in files]
        groups = sorted({g for g in (_group_of(m) for m in missing) if g})
        feats.append({"id": fid, "label": label, "ready": up and files is not None and not missing,
                      "missing": missing, "groups": groups})
    busy = sum(1 for j in JOBS.values() if j["status"] in ("queued", "running"))
    return {"app": VERSION, "comfy_up": up, "comfy_url": COMFY_URL, "comfy_version": version, "gpu": gpu,
            "features": feats, "busy": busy, "password": bool(PASSWORD), "age_check": AGE.status(),
            "trainer": trainer.installed(ROOT), "lora_folder": LORAS.available(),
            "adult": {"unlocked": adult_unlocked(request), "pin": pin_set()},
            "machine": __import__("machine_profiles").active()}


@app.get("/api/catalog")
def get_catalog(request: Request):
    c = catalog.everything()
    if adult_unlocked(request):
        c["adult"] = catalog.adult_extras()
    return c


@app.get("/api/advanced/options")
def advanced_options(request: Request, area: str = ""):
    files, info = comfy_files()
    ks = (info.get("KSampler", {}).get("input", {}).get("required", {}) if info else {})
    def opts(spec):
        if not spec:
            return []
        return spec[0] if isinstance(spec[0], list) else spec[1].get("options", [])
    loras = opts((info.get("LoraLoaderModelOnly", {}).get("input", {}).get("required", {}) or {}).get("lora_name")) if info else []
    builtin = set()
    for n in os.listdir(cc.WORKFLOW_DIR):
        for node in cc.load_workflow(n).values():
            if node["class_type"] == "LoraLoaderModelOnly":
                builtin.add(node["inputs"]["lora_name"])
    a = want_area(request, area)
    if LORAS.available():
        mine = LORAS.scan()
        known = {r["name"] for r in mine}
        loras = [r["name"] for r in mine if not r["blocked"] and not r.get("player_only")
                 and not (r.get("area") == "adult" and a != "adult")
                 and r["name"] not in builtin and not LORAS._sidecar(LORAS.path_of(r["name"])).get("hidden")] + \
                [x for x in loras if x not in known]
    loras = [l for l in loras if l not in builtin and safety.check_lora(l)[0]]
    return {"samplers": opts(ks.get("sampler_name")) or ["euler", "euler_ancestral", "dpmpp_2m", "res_multistep"],
            "schedulers": opts(ks.get("scheduler")) or ["simple", "normal", "karras", "beta"],
            "loras": loras}


# routes_v3.register() replaces these with the real functions before the server accepts
# a request. Naming them here lets a checker see them; it does not change behaviour.
want_area = None
adult_unlocked = None
pin_set = None
import routes_v3  # noqa: E402  (18+ section, LoRA library, video studio, training, settings)
routes_v3.register(sys.modules[__name__])
import routes_recipes  # noqa: E402  (Make -> Recipes, the Play door's island check)
routes_recipes.register(sys.modules[__name__])
import routes_owner  # noqa: E402  (the owner's own likeness: enrolment by camera)
routes_owner.register(sys.modules[__name__])
import routes_owner_photos  # noqa: E402  (Add photos: his own photos, kept only if they show the enrolled face)
routes_owner_photos.register(sys.modules[__name__])
import routes_models  # noqa: E402  (Setup > Models: pinned, hash-checked downloads)
routes_models.register(sys.modules[__name__])
import routes_providers  # noqa: E402  (hosted providers: API keys panel, Video (API) job)
routes_providers.register(sys.modules[__name__])
import routes_firstrun  # noqa: E402  (PHASE_TWO switch, SD 1.5 feature)
routes_firstrun.register(sys.modules[__name__])
import routes_retry  # noqa: E402  (retry a job whose flagged result was deleted, with a new seed)
routes_retry.register(sys.modules[__name__])

# ---------------------------------------------------------------------------
# web page
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


@app.post("/api/check-text")
def check_text(request: Request, body: dict = Body(...)):
    """Plain wording check for the prompt helper. It does not start a job."""
    text = str((body or {}).get("text") or "")
    if len(text) > 8000:
        err("That text is too long to check. Shorten it and try again.")
    area = want_area(request, (body or {}).get("area"))
    ok, msg = safety.check_prompt(text)
    if ok:
        ok, msg = safety.check_area(text, area)
    if ok:
        ok, msg = safety.check_group_prompt(text)
    return {"ok": bool(ok), "error": "" if ok else msg}


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"), headers={"Cache-Control": "no-cache"})


@app.exception_handler(HTTPException)
async def http_err(_req, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


def main():
    import uvicorn
    host = os.environ.get("EASY_STUDIO_HOST", "127.0.0.1")
    port = int(os.environ.get("EASY_STUDIO_PORT", "7860"))
    print(f"Easy Studio {VERSION} on http://{host}:{port}  (ComfyUI: {COMFY_URL})")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
