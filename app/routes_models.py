# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Setup > Models: one Download button per model group from install/download_models.py.

Ak clicks; nothing here starts by itself. Rules, all enforced here and not in the page:
  * only files named *.safetensors, *.gguf or *.onnx are fetched (a .pth is a pickle; a .json is not a model);
  * a file is fetched only from the pinned URL in config/server_model_lock.json (a commit, not "main"),
    over https, from huggingface.co; the redirect to its file host is followed by hand and the login
    token is never sent past the first host;
  * the file is hashed as it arrives and must match the pinned SHA256 and size, or it is deleted;
  * a group with any weight file that is not pinned yet cannot be downloaded from the page;
  * at the click the free space is read, and the click is refused if less than 50 GiB would be left;
  * the download goes to a .part file next to its place and resumes after an interruption;
  * nothing downloaded is opened, imported, unpacked or made executable.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from urllib.parse import urlsplit, urljoin

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOCK_FILE = os.path.join(ROOT, "config", "server_model_lock.json")
MAC_PINS = os.path.join(ROOT, "config", "model_pins_mac.json")  # hash-pinned rows (no commit recorded yet)
FLOOR = 50 * 1024 ** 3
# The age check cannot start without two small config files and one checkpoint, so for that group alone the page also
# fetches .json and .pth, each pinned to a revision and checked against its hash like every other file. Nothing here
# opens, imports or runs a download; the age check's own worker loads them, as it did when the install script fetched them.
# The trainer's two base models are Hugging Face "diffusers" folders: weight shards (.safetensors, always allowed) and small
# config, tokenizer and index files. For those two groups alone the page also fetches .json, .txt and (sentencepiece) .model files,
# pinned to a revision and checked like every other file: a .json or .txt is read as text, and a .model is a plain tokenizer table.
EXTRA_EXT = {"safety": (".json", ".pth"), "trainer-fast": (".json", ".txt"), "trainer-photo": (".json", ".txt", ".model")}
ALLOWED_EXT = (".safetensors", ".gguf", ".onnx")  # weights only; .onnx is a plain graph file, not a pickle (the face check)
HOSTS = ("huggingface.co", "hf.co")  # first host; its file host is any subdomain of these
CHUNK = 4 * 1024 * 1024
_URL = re.compile(r"^https://huggingface\.co/([^/]+/[^/]+)/resolve/[^/]+/(.+)$")  # "main" or a pinned revision: the lock decides what is fetched
LOOPBACK = {"localhost", "127.0.0.1", "[::1]", "::1"}

S = None
_lock = threading.Lock()  # one group at a time
STATE = {}  # group -> {"status", "file", "done", "total", "error", "files": {name: status}}


def _dm():
    d = os.path.join(ROOT, "install")
    if d not in sys.path:
        sys.path.insert(0, d)
    import download_models
    return download_models


TRAINER_LOCK = os.path.join(ROOT, "config", "trainer_bases_lock.json")


def _trainer_pins():
    """The trainer's base-model files: pinned by revision, size and either SHA-256 (large files) or the git blob SHA-1 of the revision."""
    try:
        with open(TRAINER_LOCK, encoding="utf-8") as f:
            rows = json.load(f)["rows"]
    except Exception:
        return {}
    return {(r["repo"], r["path"]): r for r in rows
            if r.get("repo") and r.get("path") and r.get("rev") and r.get("size") and r.get("url") and (r.get("sha256") or r.get("git_blob_sha1"))}


def _pins(lock_file=None):
    try:
        with open(lock_file or LOCK_FILE, encoding="utf-8") as f:
            rows = json.load(f)["rows"]
    except Exception:
        return {}
    out = {}
    for r in rows:
        if r.get("repo") and r.get("path") and r.get("rev") and r.get("sha256") and r.get("size") and r.get("url"):
            out[(r["repo"], r["path"])] = r
    if lock_file is None:
        for key, r in _trainer_pins().items():
            out.setdefault(key, r)
    if lock_file is None:  # hash-only rows: same checks, link is the downloader's own
        try:
            with open(MAC_PINS, encoding="utf-8") as f:
                for r in json.load(f)["rows"]:
                    if r.get("repo") and r.get("path") and r.get("sha256") and r.get("size") and r.get("url"):
                        out.setdefault((r["repo"], r["path"]), r)
        except Exception:
            pass
    return out


def catalog(models=None, pins=None):
    """Every group with its files, each marked ok / blocked (wrong type) / unpinned, from committed data only."""
    models = models if models is not None else _dm().MODELS
    help_ = _dm().GROUP_HELP if models is _dm().MODELS else {}
    pins = pins if pins is not None else _pins()
    groups = {}
    for g, files in models.items():
        items = []
        for folder, name, url, size_text in files:
            m = _URL.match(url)
            pin = pins.get((m.group(1), m.group(2))) if m else None
            if not name.lower().endswith(ALLOWED_EXT + EXTRA_EXT.get(g, ())):
                kind = "blocked"
            elif pin is None:
                kind = "unpinned"
            else:
                kind = "ok"
            items.append({"folder": folder, "name": name, "kind": kind, "size_text": size_text,
                          "url": pin["url"] if pin else None, "sha256": pin.get("sha256") if pin else None,
                          "git_blob_sha1": pin.get("git_blob_sha1") if pin else None,
                          "size": int(pin["size"]) if pin else None})
        groups[g] = {"id": g, "help": help_.get(g, g), "files": items}
    return groups


def _dest(models_dir, item):
    real = os.path.realpath(models_dir)
    dest = os.path.realpath(os.path.join(real, item["folder"], item["name"]))
    if not dest.startswith(real + os.sep):
        raise ValueError("That file would land outside the models folder.")
    return dest


def _have(item, models_dir):
    d = _dest(models_dir, item)
    return os.path.isfile(d) and os.path.getsize(d) == item["size"]


def _part_size(item, models_dir):
    p = _dest(models_dir, item) + ".part"
    return os.path.getsize(p) if os.path.isfile(p) else 0


def summarize(group, models_dir, state=None):
    files = group["files"]
    weights = [f for f in files if f["kind"] != "blocked"]
    unpinned = [f for f in weights if f["kind"] == "unpinned"]
    blocked = [f for f in files if f["kind"] == "blocked"]
    out = {"id": group["id"], "help": group["help"], "unpinned": len(unpinned), "blocked": len(blocked),
           "files": [{"name": f["name"], "kind": f["kind"]} for f in files]}
    if unpinned or not weights:
        out.update(can_download=False, reason="Not pinned yet: " + ", ".join(f["name"] for f in unpinned) if unpinned
                   else "Nothing here the page may download.")
        out["size_bytes"] = None
        out["installed"] = False
        return out
    todo = [f for f in weights if not _have(f, models_dir)]
    out["size_bytes"] = sum(f["size"] for f in weights)
    out["need_bytes"] = sum(f["size"] - min(_part_size(f, models_dir), f["size"]) for f in todo)
    out["installed"] = not todo
    out["can_download"] = bool(todo)
    out["reason"] = "" if todo else "Already installed."
    if blocked:
        out["note"] = "Partly here: " + ", ".join(f["name"] for f in blocked) + " come from the install script."
    return out


def refusal(group, models_dir, free_fn=shutil.disk_usage, state=None):
    """None if this group may start now, else a plain sentence. Also returns the df reading read just now."""
    if not os.path.isdir(models_dir):
        return "ComfyUI's models folder isn't on this computer (set COMFY_DIR). Nothing was created.", None
    free = free_fn(models_dir).free
    s = summarize(group, models_dir)
    if not s["can_download"]:
        return s["reason"], free
    if state and state.get("status") == "running":
        return "That group is already downloading.", free
    left = free - s["need_bytes"]
    if left < FLOOR:
        return ("Not enough room: %.1f GB free, this needs %.1f GB, and 50 GB must stay free "
                "(it would leave %.1f GB)." % (free / 1e9, s["need_bytes"] / 1e9, left / 1e9)), free
    return None, free


def http_fetch(url, headers):
    """The only network call. https only; redirects are followed by hand to huggingface.co / hf.co hosts."""
    import requests
    token = os.environ.get("HF_TOKEN")
    for hop in range(6):
        sp = urlsplit(url)
        host = (sp.hostname or "").lower()
        if sp.scheme != "https" or not any(host == h or host.endswith("." + h) for h in HOSTS):
            raise RuntimeError("Refused a link that leaves Hugging Face.")
        h = dict(headers)
        if token and hop == 0 and host in HOSTS:
            h["Authorization"] = "Bearer " + token
        r = requests.get(url, headers=h, stream=True, timeout=60, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, r.headers.get("location", ""))
            r.close()
            continue
        return r
    raise RuntimeError("Too many redirects.")


def _hasher(item):
    """SHA-256 for a file pinned by SHA-256. For a small file pinned by the git blob hash of its revision, the same SHA-1 git uses:
    the header "blob <size>" and a zero byte, then the file."""
    if item.get("sha256"):
        return hashlib.sha256()
    h = hashlib.sha1()  # noqa: S324  (git's own object id, used only as the revision's check of a small file)
    h.update(b"blob %d\0" % int(item["size"]))
    return h


def fetch_file(item, models_dir, fetch, progress=lambda n: None):
    """Fetch one pinned file into <dest>.part, hash it, and move it into place only if it matches."""
    dest = _dest(models_dir, item)
    part = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    want, size = (item.get("sha256") or item["git_blob_sha1"]).lower(), item["size"]
    for attempt in range(2):
        h, have = _hasher(item), 0
        if os.path.isfile(part):
            with open(part, "rb") as f:
                while True:
                    b = f.read(CHUNK)
                    if not b:
                        break
                    h.update(b)
                    have += len(b)
            if have > size:
                os.remove(part)
                h, have = _hasher(item), 0
        if have < size:
            headers = {"User-Agent": "easy-studio/1.0"}
            if have:
                headers["Range"] = "bytes=%d-" % have
            r = fetch(item["url"], headers)
            try:
                if r.status_code in (401, 403):
                    raise RuntimeError("Hugging Face asked for a login for this file.")
                if r.status_code == 416 and attempt == 0:
                    os.remove(part)  # our partial no longer lines up: start the file again
                    continue
                if r.status_code not in (200, 206):
                    raise RuntimeError("Hugging Face answered %s." % r.status_code)
                if r.status_code == 200 and have:
                    h, have = _hasher(item), 0  # it ignored the range: start over
                with open(part, "ab" if have else "wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK):
                        if not chunk:
                            continue
                        f.write(chunk)
                        h.update(chunk)
                        have += len(chunk)
                        progress(have)
                        if have > size:
                            break
            finally:
                r.close()
        if have != size or h.hexdigest() != want:
            try:
                os.remove(part)
            except OSError:
                pass
            raise RuntimeError("%s did not match its pinned check (size/SHA256); it was deleted." % item["name"])
        os.replace(part, dest)
        return dest
    raise RuntimeError("Could not resume %s." % item["name"])


def run_group(group, models_dir, fetch, free_fn, st):
    """The worker body: file by file, re-reading the free space between files."""
    try:
        todo = [f for f in group["files"] if f["kind"] == "ok" and not _have(f, models_dir)]
        st["total"] = sum(f["size"] for f in todo)
        base = 0
        for f in todo:
            free = free_fn(models_dir).free
            if free - (f["size"] - _part_size(f, models_dir)) < FLOOR:
                raise RuntimeError("Stopped: 50 GB must stay free. Free up space and press Download again to resume.")
            st["file"] = f["name"]
            fetch_file(f, models_dir, fetch, lambda n, b=base: st.__setitem__("done", b + n))
            base += f["size"]
            st["done"] = base
        st.update(status="done", file=None)
    except Exception as exc:
        st.update(status="error", error=str(exc)[:300])


def start(group_id, models_dir, fetch=None, free_fn=shutil.disk_usage, groups=None, background=True):
    """Check, then start. Returns (ok, message, df_reading_bytes)."""
    groups = groups if groups is not None else catalog()
    g = groups.get(group_id)
    if not g:
        return False, "Unknown group.", None
    with _lock:
        msg, free = refusal(g, models_dir, free_fn, STATE.get(group_id))
        if msg:
            return False, msg, free
        for s in STATE.values():
            if s.get("status") == "running":
                return False, "Another group is downloading. One at a time.", free
        st = STATE[group_id] = {"status": "running", "file": None, "done": 0, "total": 0, "error": None, "started": time.time()}
    fn = fetch or http_fetch
    if background:
        threading.Thread(target=run_group, args=(g, models_dir, fn, free_fn, st), daemon=True).start()
    else:
        run_group(g, models_dir, fn, free_fn, st)
    return True, "Started.", free


def is_local(host_header, client_host):
    name = (host_header or "").rsplit(":", 1)[0] if not (host_header or "").endswith("]") else host_header
    name = (name or "").lower()
    return (name in LOOPBACK or name.endswith(".localhost")) and client_host in ("127.0.0.1", "::1")


def register(server):
    global S
    from fastapi import Body, Request

    S = server
    app = server.app

    def models_dir():
        return os.path.join(server.COMFY_DIR, "models")

    @app.get("/api/models/groups")
    def models_groups():
        md = models_dir()
        free = shutil.disk_usage(md).free if os.path.isdir(md) else None
        cat = catalog()
        import phase_two
        if phase_two.hidden(server.OUT):  # the face check belongs to Phase two: no button for it while that is hidden
            cat = {gid: g for gid, g in cat.items() if gid != "face"}
        return {"floor_bytes": FLOOR, "free_bytes": free, "models_dir_ok": os.path.isdir(md),
                "groups": [dict(summarize(g, md), state=STATE.get(gid)) for gid, g in cat.items()]}

    @app.get("/api/models/status")
    def models_status():
        return {"state": STATE}

    @app.post("/api/models/download")
    def models_download(request: Request, body: dict = Body(...)):
        host = request.headers.get("host")
        if not is_local(host, request.client.host if request.client else None):
            S.err("Downloads start only from this computer.", 403)
        ok, msg, free = start(str(body.get("group", "")), models_dir())
        if not ok:
            S.err(msg + (" (free now: %.1f GB)" % (free / 1e9) if free is not None else ""))
        return {"ok": True, "free_bytes": free, "message": msg}
