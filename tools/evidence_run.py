#!/usr/bin/env python3
"""Evidence run for the Easy Studio chain: text -> image -> video -> longer video -> 3D.

Drives a running Easy Studio app through the same HTTP API the web page uses (POST /api/jobs, then
GET /api/jobs/<id> until it ends), keeps a copy of every output and writes
<evidence root>/<run id>/manifest.json with, per step: the app job id, the workflow template, the
machine profile, the model files with SHA256, the prompt, the seed, timings, the output file with
SHA256, size, dimensions, frame count, fps, duration, mesh vertex and face counts and bounding box,
numeric sanity figures, app and ComfyUI log excerpts, plus the git heads and the ComfyUI commit.
A Playwright walk of the UI saves screenshots to disk.

Nothing here opens or shows generated media. Sanity is numeric only: pixel standard deviation,
mean frame-to-frame difference, durations, mesh counts. Screenshots are written, never viewed.

The chain (job kinds and parameters per step) lives in a JSON spec, tools/evidence_chain.json by
default, so the chain can follow the app without code changes. Strings in the spec such as
"{E1.id}", "{prompt}", "{seed}" or "{profile.video_proof}" are filled in at run time.

  Real run (app and ComfyUI already running on loopback):
    python tools/evidence_run.py --base http://127.0.0.1:7860 --comfy-dir <ComfyUI checkout> \
        --app-repo <app checkout> --outputs <EASY_STUDIO_OUTPUTS> --app-log <file> --comfy-log <file>
  Mock run (Tier 1: starts its own mock ComfyUI and app on free loopback ports, temporary outputs):
    python tools/evidence_run.py --mock
  Re-run the steps that did not finish in an earlier run:
    python tools/evidence_run.py --resume <run id> [same options as the first run]

Exit code 0 when every required check passes (and, outside Tier 1, every media check), else 1.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
SCHEMA = "candy-evidence/1"
DEFAULT_CHAIN = os.path.join(HERE, "evidence_chain.json")
DEFAULT_ROOT = os.environ.get("CANDY_EVIDENCE_ROOT") or os.path.expanduser("~/candy/evidence")
MODEL_EXT = (".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin", ".sft", ".onnx")
DONE = ("done", "error", "cancelled", "blocked_age_check_unavailable")
# The chain says what it shows ("subject"). A place chain may not name a person in its free text. A chain
# with one fictional adult must give every person record a stated age of 21 or more, and its free text
# stays clothed and non-sexual. Either problem stops the run before any job is posted.
PERSON_WORDS = re.compile(
    r"\b(person|persons|people|man|men|woman|women|girl|girls|boy|boys|child|children|kid|kids|baby|babies|"
    r"teen\w*|face|faces|portrait|selfie|he|she|her|hers|his|him|lady|ladies|guy|guys|human|humans|crowd|"
    r"body|bodies|nude|naked|figure|figures|character|characters|actor|actress|someone|somebody)\b", re.I)
NOT_SFW_WORDS = re.compile(
    r"\b(nude|nudity|naked|nsfw|explicit|erotic\w*|sexy|sexual\w*|sensual\w*|seductive|lingerie|underwear|bikini|"
    r"topless|bottomless|undress\w*|strip\w*|lewd|porn\w*|fetish\w*|kiss\w*|bed|bedroom|shower|bath\w*|"
    r"teen\w*|young|youthful|girl|girls|boy|boys|child\w*|kid|kids|minor|school\w*|petite)\b", re.I)
TEXT_KEYS = ("prompt", "text", "motion", "extra_scene", "scene_text", "description", "caption")
SUBJECTS = ("place", "fictional_adult")
SECRET_LINE = re.compile(r"password|passwd|token|secret|authorization|api[_-]?key|bearer|cookie|op://|hf_[A-Za-z0-9]{8,}",
                         re.I)
LOG_LINES = 400        # lines kept per excerpt file
LOG_INLINE = 40        # lines repeated inside manifest.json


class Stop(Exception):
    """A clear reason to stop the whole run."""


def now():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def file_row(path, root):
    return {"path": os.path.relpath(path, root), "sha256": sha256_file(path), "size": os.path.getsize(path)}


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, path)


def run(cmd, timeout=600, ok_codes=(0,)):
    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if res.returncode not in ok_codes:
        raise RuntimeError(f"{os.path.basename(cmd[0])} failed ({res.returncode}): "
                           + res.stderr.decode("utf-8", "replace")[-400:])
    return res.stdout


def git_info(path):
    """Head, branch and dirty-file count of the git checkout at path (None when it is not one)."""
    if not path or not os.path.isdir(path):
        return None
    def g(*args):
        res = subprocess.run(["git", "-C", path, *args], capture_output=True, timeout=30)
        return res.stdout.decode().strip() if res.returncode == 0 else None
    head = g("rev-parse", "HEAD")
    if not head:
        return {"path": path, "git": False}
    dirty = g("status", "--porcelain", "--untracked-files=no")
    return {"path": path, "head": head, "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
            "describe": g("describe", "--tags", "--always"), "dirty_files": len(dirty.splitlines()) if dirty else 0}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---------------------------------------------------------------------------------------------------- app client
class App:
    """The Easy Studio HTTP API. The password, if any, comes from EASY_STUDIO_PASSWORD and is never written."""

    def __init__(self, base, timeout=60):
        self.base = base.rstrip("/")
        self.timeout = timeout
        pw = os.environ.get("EASY_STUDIO_PASSWORD", "")
        self._auth = "Basic " + base64.b64encode(b"evidence:" + pw.encode()).decode() if pw and pw != "off" else None

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("X-Easy-Studio", "1")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self._auth:
            req.add_header("Authorization", self._auth)
        return req

    def call(self, method, path, body=None):
        try:
            with urllib.request.urlopen(self._req(method, path, body), timeout=self.timeout) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": raw.decode("utf-8", "replace")[:300]}

    def get(self, path):
        code, data = self.call("GET", path)
        if code != 200:
            raise RuntimeError(f"GET {path}: HTTP {code} {data}")
        return data

    def download(self, url, dest):
        with urllib.request.urlopen(self._req("GET", url), timeout=self.timeout) as r, open(dest, "wb") as fh:
            shutil.copyfileobj(r, fh, 1 << 22)
        return dest

    def up(self):
        try:
            self.get("/api/status")
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------------------------------- media
def ffbin(name):
    return shutil.which(name) or (f"/opt/homebrew/bin/{name}" if os.path.exists(f"/opt/homebrew/bin/{name}") else name)


def probe_image(path):
    from PIL import Image, ImageStat
    with Image.open(path) as im:
        im.load()
        gray = im.convert("L")
        rgb = im.convert("RGB")
        return {"width": im.size[0], "height": im.size[1], "mode": im.mode, "format": im.format,
                "pixel_std": round(ImageStat.Stat(gray).stddev[0], 3),
                "channel_std": [round(x, 3) for x in ImageStat.Stat(rgb).stddev],
                "pixel_mean": round(ImageStat.Stat(gray).mean[0], 3)}


def _ratio(text):
    try:
        num, den = str(text).split("/")
        return round(float(num) / float(den), 4) if float(den) else None
    except (ValueError, ZeroDivisionError):
        return None


def probe_video(path):
    out = run([ffbin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
               "stream=codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration"
               ":format=duration,bit_rate,format_name", "-of", "json", path])
    d = json.loads(out)
    s = (d.get("streams") or [{}])[0]
    f = d.get("format") or {}
    frames = int(s.get("nb_read_frames") or s.get("nb_frames") or 0)
    fps = _ratio(s.get("avg_frame_rate")) or _ratio(s.get("r_frame_rate"))
    duration = float(f.get("duration") or s.get("duration") or 0)
    return {"codec": s.get("codec_name"), "pix_fmt": s.get("pix_fmt"), "width": int(s.get("width") or 0),
            "height": int(s.get("height") or 0), "fps": fps, "r_frame_rate": s.get("r_frame_rate"),
            "frames": frames, "duration_s": round(duration, 4), "container": f.get("format_name"),
            "bit_rate": int(f["bit_rate"]) if str(f.get("bit_rate") or "").isdigit() else None}


def gray_frames(path, size=64):
    """Every frame scaled to size x size grey, as bytes objects (decoded by ffmpeg, never displayed)."""
    raw = run([ffbin("ffmpeg"), "-v", "error", "-i", path, "-vf", f"scale={size}:{size}:flags=area,format=gray",
               "-f", "rawvideo", "-pix_fmt", "gray", "-"], timeout=1800)
    n = size * size
    return [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]


def _std(frame):
    return statistics.pstdev(frame) if frame else 0.0


def frame_stats(path, join_frame=None):
    frames = gray_frames(path)
    diffs = []
    try:
        import numpy as np
        arr = np.frombuffer(b"".join(frames), dtype=np.uint8).reshape(len(frames), -1).astype(np.int16)
        if len(frames) > 1:
            diffs = np.abs(np.diff(arr, axis=0)).mean(axis=1).round(4).tolist()
    except ImportError:  # pragma: no cover - the app's requirements include numpy
        for a, b in zip(frames, frames[1:]):
            diffs.append(round(sum(abs(x - y) for x, y in zip(a, b)) / len(a), 4))
    out = {"decoded_frames": len(frames), "mean_frame_diff": round(statistics.fmean(diffs), 4) if diffs else 0.0,
           "median_frame_diff": round(statistics.median(diffs), 4) if diffs else 0.0,
           "max_frame_diff": max(diffs) if diffs else 0.0,
           "first_frame_std": round(_std(frames[0]), 3) if frames else 0.0,
           "last_frame_std": round(_std(frames[-1]), 3) if frames else 0.0,
           "still_pairs": sum(1 for x in diffs if x < 0.05)}
    if join_frame and 0 < join_frame < len(frames):
        at = diffs[join_frame - 1]
        out["join"] = {"frame": join_frame, "diff_at_join": at,
                       "ratio_to_median": round(at / out["median_frame_diff"], 3) if out["median_frame_diff"] else None}
    return out


# glTF component types -> struct code
_COMP = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _accessor_floats(gltf, binchunk, idx):
    acc = gltf["accessors"][idx]
    view = gltf["bufferViews"][acc["bufferView"]]
    n = _NCOMP[acc["type"]]
    code = _COMP[acc["componentType"]]
    size = struct.calcsize(code)
    stride = view.get("byteStride") or size * n
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    rows = []
    for i in range(acc["count"]):
        rows.append(struct.unpack_from("<" + code * n, binchunk, start + i * stride))
    return rows


def probe_glb(path):
    """Vertex and face counts and the bounding box of a binary glTF, read without any 3D library."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("not a binary glTF file (no glTF magic)")
    version, length = struct.unpack_from("<II", data, 4)
    pos, chunks = 12, {}
    while pos + 8 <= min(length, len(data)):
        clen, ctype = struct.unpack_from("<II", data, pos)
        chunks[ctype] = data[pos + 8:pos + 8 + clen]
        pos += 8 + clen
    gltf = json.loads(chunks[0x4E4F534A].decode("utf-8"))
    binchunk = chunks.get(0x004E4942, b"")
    verts = faces = prims = 0
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            prims += 1
            pidx = prim.get("attributes", {}).get("POSITION")
            if pidx is None:
                continue
            acc = gltf["accessors"][pidx]
            verts += acc["count"]
            mode = prim.get("mode", 4)
            count = gltf["accessors"][prim["indices"]]["count"] if "indices" in prim else acc["count"]
            faces += count // 3 if mode == 4 else max(0, count - 2) if mode in (5, 6) else 0
            mn, mx = acc.get("min"), acc.get("max")
            if not (mn and mx) and "bufferView" in acc:
                rows = _accessor_floats(gltf, binchunk, pidx)
                mn = [min(r[k] for r in rows) for k in range(3)] if rows else None
                mx = [max(r[k] for r in rows) for k in range(3)] if rows else None
            if mn and mx:
                lo = [min(a, b) for a, b in zip(lo, mn)]
                hi = [max(a, b) for a, b in zip(hi, mx)]
    bbox = None if lo[0] == float("inf") else {
        "min": [round(x, 6) for x in lo], "max": [round(x, 6) for x in hi],
        "size": [round(b - a, 6) for a, b in zip(lo, hi)], "space": "mesh-local (node transforms not applied)"}
    return {"format": "glb", "gltf_version": version, "declared_length": length, "file_length": len(data),
            "meshes": len(gltf.get("meshes", [])), "primitives": prims, "vertices": verts, "faces": faces,
            "materials": len(gltf.get("materials", [])), "textures": len(gltf.get("textures", [])),
            "generator": (gltf.get("asset") or {}).get("generator"), "bbox": bbox}


def probe_obj(path):
    verts = faces = 0
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                verts += 1
                xyz = [float(x) for x in line.split()[1:4]]
                lo = [min(a, b) for a, b in zip(lo, xyz)]
                hi = [max(a, b) for a, b in zip(hi, xyz)]
            elif line.startswith("f "):
                faces += max(1, len(line.split()) - 3)
    bbox = None if not verts else {"min": lo, "max": hi, "size": [b - a for a, b in zip(lo, hi)], "space": "file"}
    return {"format": "obj", "vertices": verts, "faces": faces, "bbox": bbox}


def probe_output(path, kind_type, join_frame=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".glb" or kind_type == "model" and ext != ".obj":
        return {"mesh": probe_glb(path)}
    if ext == ".obj":
        return {"mesh": probe_obj(path)}
    if ext in (".mp4", ".webm", ".mov", ".mkv", ".gif") or kind_type == "video":
        return {"video": probe_video(path), "motion": frame_stats(path, join_frame)}
    return {"image": probe_image(path)}


# ---------------------------------------------------------------------------------------------------- chain spec
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)(\?)?\}")
OMIT = object()  # an optional placeholder ("{chain.qc?}") with no value: the key is left out


def lookup(ctx, dotted):
    cur = ctx
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(dotted)
    return cur


def _lookup_opt(ctx, m):
    try:
        return lookup(ctx, m.group(1))
    except KeyError:
        if m.group(2):
            return OMIT
        raise


def resolve(obj, ctx):
    """Fill "{name}" placeholders. A string that is exactly one placeholder keeps the value's type;
    "{name?}" is optional: with no value its key (or list entry) is left out."""
    if isinstance(obj, dict):
        out = {k: resolve(v, ctx) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v is not OMIT}
    if isinstance(obj, list):
        return [v for v in (resolve(v, ctx) for v in obj) if v is not OMIT]
    if isinstance(obj, str):
        whole = PLACEHOLDER.fullmatch(obj)
        if whole:
            value = _lookup_opt(ctx, whole)
            if whole.group(1).startswith("chain.") and isinstance(value, (dict, list)):
                value = resolve(value, {**ctx, "chain": {}})  # a --var file may name "{E1.results.0}"; one level only
            return value
        return PLACEHOLDER.sub(lambda m: "" if (v := _lookup_opt(ctx, m)) is OMIT else str(v), obj)
    return obj


def step_needs(step):
    """The earlier steps a step reads from (by "{E1.…}" placeholders)."""
    found = set()
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            for m in PLACEHOLDER.finditer(o):
                found.add(m.group(1).split(".")[0])
    walk(step.get("params"))
    walk(step.get("expect"))
    return found


def neutral_text_problems(obj, subject="place", where=""):
    """Free-text fields (prompt, text, motion ...) that do not fit the chain's subject, and person records
    whose stated age is missing or under 21."""
    probs = []
    words = PERSON_WORDS if subject == "place" else NOT_SFW_WORDS
    why = ("names a person; this chain shows places or objects" if subject == "place"
           else "is not clothed, neutral and adult; this chain shows one fictional adult")
    if isinstance(obj, dict):
        if subject == "fictional_adult" and "age" in obj:
            age = obj.get("age")
            if not isinstance(age, int) or isinstance(age, bool) or age < 21:
                probs.append(f"{where}age: a person record needs a stated age of 21 or more, not {age!r}")
        for k, v in obj.items():
            if isinstance(v, str) and k in TEXT_KEYS:
                m = words.search(v)
                if m:
                    probs.append(f"{where}{k}: the word {m.group(0)!r} {why}")
            else:
                probs += neutral_text_problems(v, subject, f"{where}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            probs += neutral_text_problems(v, subject, f"{where}{i}.")
    return probs


def load_chain(path):
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise Stop(f"{path}: no steps")
    ids = [s.get("id") for s in steps]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", i) for i in ids):
        raise Stop(f"{path}: every step needs a unique id such as E1")
    if spec.get("subject") not in SUBJECTS:
        raise Stop(f"{path}: subject must be one of {SUBJECTS}")
    known = set()
    for s in steps:
        if not isinstance(s.get("kind"), str) or not isinstance(s.get("params", {}), dict):
            raise Stop(f"{path}: step {s['id']} needs a kind and a params object")
        if "area" in s or "area" in s.get("params", {}):
            raise Stop(f"{path}: step {s['id']} sets an area; evidence runs stay in the default area")
        unknown = step_needs(s) - known - {"prompt", "seed", "motion", "profile", "run_id", "chain"}
        if unknown:
            raise Stop(f"{path}: step {s['id']} reads {sorted(unknown)} before they exist")
        known.add(s["id"])
    probs = neutral_text_problems({k: spec.get(k) for k in ("prompt", "motion") if spec.get(k)}, spec["subject"])
    probs += neutral_text_problems([s.get("params") for s in steps], spec["subject"])
    probs += neutral_text_problems(spec.get("vars") or {}, spec["subject"], "vars.")
    if probs:
        raise Stop("chain text is not neutral: " + "; ".join(probs))
    return spec


RULES = {
    "place": "places and objects only, no people; sessions never open the media; checks are numbers only",
    "fictional_adult": "one fictional adult with a stated age of 21 or more, fully clothed, non-sexual, everyday "
                       "section, no real person, no likeness; sessions never open the media; checks are numbers only",
}
QC_META = ("source", "scored_by", "scored_at", "note")


def qc_declaration(given, tier):
    """Who scored the keyframes in a --var qc file. Tier 1 takes only scores labelled "source": "mock";
    T2 and T3 take only Ak's own ("source": "ak_scores" with "scored_by"). Returns (scores to send without
    the label fields, the label) or (None, None) when no scores were given."""
    if "qc" not in given:
        return None, None
    qc = given["qc"]
    if not isinstance(qc, dict):
        raise Stop("--var qc must be a JSON object holding the scored variants")
    decl = {k: qc[k] for k in QC_META if k in qc}
    src = decl.get("source")
    if tier == "T1":
        if src != "mock":
            raise Stop('Tier 1 takes only scores labelled "source": "mock" in the --var qc file')
    elif src != "ak_scores" or not str(decl.get("scored_by") or "").strip():
        raise Stop(f'{tier} takes only Ak\'s own scores: the --var qc file needs "source": "ak_scores" and '
                   '"scored_by"; mock scores never reach a real run')
    return {k: v for k, v in qc.items() if k not in QC_META}, decl


def parse_vars(pairs):
    """--var NAME=VALUE (a JSON value or plain text) or NAME=@file.json; returned with the files' SHA256."""
    out, files = {}, {}
    for pair in pairs or []:
        name, sep, value = pair.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise Stop(f"--var {pair!r}: use NAME=VALUE or NAME=@file.json")
        if value.startswith("@"):
            path = os.path.abspath(value[1:])
            with open(path, encoding="utf-8") as fh:
                out[name] = json.load(fh)
            files[name] = {"path": path, "sha256": sha256_file(path)}
        else:
            try:
                out[name] = json.loads(value)
            except ValueError:
                out[name] = value
    return out, files


# ---------------------------------------------------------------------------------------------------- models + workflows
class HashCache:
    """SHA256 of model files, kept by (path, size, mtime) so a re-run does not hash 20 GB again."""

    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8") as fh:
                self.rows = json.load(fh)
        except (OSError, ValueError):
            self.rows = {}

    def sha(self, path):
        st = os.stat(path)
        key = f"{os.path.realpath(path)}|{st.st_size}|{st.st_mtime_ns}"
        if key not in self.rows:
            self.rows[key] = sha256_file(path)
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            write_json(self.path, self.rows)
        return self.rows[key]


class ModelIndex:
    def __init__(self, dirs, cache):
        self.dirs = [d for d in dirs if d and os.path.isdir(d)]
        self.cache = cache
        self._by_name = None

    def find(self, name):
        for d in self.dirs:  # a name with a sub folder ("wan/x.safetensors") first, as written
            for sub in ("", *sorted(os.listdir(d))):
                cand = os.path.join(d, sub, name)
                if os.path.isfile(cand):
                    return cand
        if self._by_name is None:
            self._by_name = {}
            for d in self.dirs:
                for root, _dirs, files in os.walk(d, followlinks=True):
                    for f in files:
                        if f.lower().endswith(MODEL_EXT):
                            self._by_name.setdefault(f, []).append(os.path.join(root, f))
        hits = self._by_name.get(os.path.basename(name)) or []
        return hits[0] if hits else None

    def row(self, name):
        path = self.find(name)
        if not path:
            return {"name": name, "path": None, "sha256": None,
                    "note": "not found under the model folders given" if self.dirs else "no model folder given"}
        return {"name": name, "path": path, "size": os.path.getsize(path), "sha256": self.cache.sha(path)}


def workflow_models(wf):
    rows = []
    for nid, node in sorted((wf or {}).items(), key=lambda kv: str(kv[0])):
        if not isinstance(node, dict):
            continue
        for key, val in (node.get("inputs") or {}).items():
            if isinstance(val, str) and val.lower().endswith(MODEL_EXT):
                rows.append({"node": str(nid), "class_type": node.get("class_type"), "input": key, "name": val})
    return rows


def workflow_seeds(wf):
    return sorted({v for node in (wf or {}).values() if isinstance(node, dict)
                   for k, v in (node.get("inputs") or {}).items() if k in ("seed", "noise_seed") and isinstance(v, int)})


def load_templates(app_repo):
    out = {}
    wdir = os.path.join(app_repo or "", "app", "workflows")
    if os.path.isdir(wdir):
        for name in sorted(os.listdir(wdir)):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(wdir, name), encoding="utf-8") as fh:
                        out[name] = json.load(fh)
                except (OSError, ValueError):
                    pass
    return out


def _values(wf):
    return {f"{k}.{i}={v}" for k, n in (wf or {}).items() if isinstance(n, dict)
            for i, v in (n.get("inputs") or {}).items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}


def match_template(wf, templates):
    """The app workflow file a submitted graph came from: best overlap of (node id, node type) pairs, then the
    model files it loads, then other unchanged input values (two templates can share one graph shape)."""
    sig = {f"{k}:{v.get('class_type')}" for k, v in (wf or {}).items() if isinstance(v, dict)}
    files = {r["name"] for r in workflow_models(wf)}
    vals = _values(wf)
    best, key = None, (0.0, 0, 0)
    for name, tpl in templates.items():
        tsig = {f"{k}:{v.get('class_type')}" for k, v in tpl.items() if isinstance(v, dict)}
        if not (sig or tsig):
            continue
        cand = (round(len(sig & tsig) / len(sig | tsig), 3), len(files & {r["name"] for r in workflow_models(tpl)}),
                len(vals & _values(tpl)))
        if cand > key:
            best, key = name, cand
    return {"name": best, "score": key[0], "model_files_matched": key[1]}


# ---------------------------------------------------------------------------------------------------- logs
class LogTap:
    """What a log file gained while one step ran."""

    def __init__(self, path):
        self.path = path if path and os.path.isfile(path) else None
        self.offset = None

    def mark(self):
        if self.path:
            self.offset = os.path.getsize(self.path)

    def excerpt(self):
        if not self.path or self.offset is None:
            return None
        with open(self.path, "rb") as fh:
            fh.seek(self.offset)
            text = fh.read(8 << 20).decode("utf-8", "replace")
        return text.splitlines()


def redact(lines):
    return ["[line withheld: looks like a credential]" if SECRET_LINE.search(x) else x for x in lines]


def comfy_internal_logs(comfy_url, t0, t1):
    """ComfyUI's own log buffer (GET /internal/logs/raw), entries inside the step's time window."""
    try:
        with urllib.request.urlopen(comfy_url.rstrip("/") + "/internal/logs/raw", timeout=10) as r:
            data = json.loads(r.read())
    except Exception:
        return None
    lines = []
    for e in data.get("entries") or []:
        t = e.get("t")
        try:
            ts = dt.datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
            if not (t0 - 5 <= ts <= t1 + 5):
                continue
        except ValueError:
            pass
        lines += str(e.get("m") or "").rstrip("\n").splitlines()
    return lines


def save_excerpt(lines, dest, root):
    if lines is None:
        return {"available": False}
    lines = redact(lines)
    kept = lines[-LOG_LINES:]
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + ("\n" if kept else ""))
    return {"available": True, "file": os.path.relpath(dest, root), "lines_total": len(lines), "lines_kept": len(kept),
            "tail": kept[-LOG_INLINE:]}


# ---------------------------------------------------------------------------------------------------- checks
def check(checks, step, cid, ok, value=None, want=None, level="required"):
    checks.append({"step": step, "id": cid, "ok": bool(ok), "value": value, "want": want, "level": level})


def step_checks(rec, steps_by_id, expect, checks):
    sid = rec["id"]
    out = rec.get("output") or {}
    check(checks, sid, "job_done", rec["job"].get("status") == "done", rec["job"].get("status"), "done")
    check(checks, sid, "output_saved", bool(out.get("sha256")), out.get("file"))
    if out.get("app_sha256"):
        check(checks, sid, "output_matches_app_copy", out["app_sha256"] == out.get("sha256"),
              out["app_sha256"][:12], (out.get("sha256") or "")[:12])
    if rec.get("status") == "held" or out.get("age"):
        held = rec.get("status") == "held" or not out.get("publishable")
        why = "; ".join(f"{a.get('age_check')} p_under21={a.get('p_under21')}" for a in rec.get("results_age") or []
                        if a.get("held")) or (out.get("age") or {}).get("age_check")
        check(checks, sid, "age_check_publishable", not held, why, "ok, not flagged")
    want_type = expect.get("type")
    if want_type:
        check(checks, sid, "output_type", out.get("type") == want_type, out.get("type"), want_type)
    img, vid, mot, mesh = out.get("image"), out.get("video"), out.get("motion"), out.get("mesh")
    if img:
        if expect.get("min_width"):
            check(checks, sid, "min_width", img["width"] >= expect["min_width"], img["width"], expect["min_width"], "media")
        if expect.get("min_height"):
            check(checks, sid, "min_height", img["height"] >= expect["min_height"], img["height"], expect["min_height"],
                  "media")
        if expect.get("min_pixel_std") is not None:
            check(checks, sid, "pixel_std", img["pixel_std"] >= expect["min_pixel_std"], img["pixel_std"],
                  f">= {expect['min_pixel_std']}", "media")
    if vid:
        if expect.get("min_duration_s") is not None:
            check(checks, sid, "min_duration", vid["duration_s"] >= expect["min_duration_s"], vid["duration_s"],
                  f">= {expect['min_duration_s']}", "media")
        if expect.get("fps"):
            tol = expect.get("fps_tolerance", 0.5)
            check(checks, sid, "fps", vid["fps"] is not None and abs(vid["fps"] - expect["fps"]) <= tol, vid["fps"],
                  expect["fps"], "media")
        if expect.get("min_frames"):
            check(checks, sid, "min_frames", vid["frames"] >= expect["min_frames"], vid["frames"], expect["min_frames"],
                  "media")
        ratio = expect.get("min_duration_ratio")
        if isinstance(ratio, dict):
            base = ((steps_by_id.get(ratio.get("of")) or {}).get("output") or {}).get("video")
            if base:
                need = round(base["duration_s"] * float(ratio.get("ratio", 1.8)), 4)
                check(checks, sid, f"duration_vs_{ratio.get('of')}", vid["duration_s"] >= need, vid["duration_s"],
                      f">= {need} ({ratio.get('ratio', 1.8)} x {base['duration_s']})", "required")
            else:
                check(checks, sid, f"duration_vs_{ratio.get('of')}", False, None, f"{ratio.get('of')} has no video")
        same = expect.get("same_size_as")
        if same:
            base = ((steps_by_id.get(same) or {}).get("output") or {}).get("video")
            check(checks, sid, f"same_size_as_{same}", bool(base) and (vid["width"], vid["height"]) ==
                  (base["width"], base["height"]), [vid["width"], vid["height"]],
                  [base["width"], base["height"]] if base else None, "media")
    if mot:
        if expect.get("min_mean_frame_diff") is not None:
            check(checks, sid, "moves", mot["mean_frame_diff"] >= expect["min_mean_frame_diff"], mot["mean_frame_diff"],
                  f">= {expect['min_mean_frame_diff']}", "media")
        if expect.get("max_mean_frame_diff") is not None:
            check(checks, sid, "not_noise", mot["mean_frame_diff"] <= expect["max_mean_frame_diff"],
                  mot["mean_frame_diff"], f"<= {expect['max_mean_frame_diff']}", "media")
        if expect.get("min_pixel_std") is not None:
            check(checks, sid, "first_frame_std", mot["first_frame_std"] >= expect["min_pixel_std"],
                  mot["first_frame_std"], f">= {expect['min_pixel_std']}", "media")
    if mesh:
        if expect.get("min_vertices"):
            check(checks, sid, "min_vertices", mesh["vertices"] >= expect["min_vertices"], mesh["vertices"],
                  expect["min_vertices"], "media")
        if expect.get("min_faces"):
            check(checks, sid, "min_faces", mesh["faces"] >= expect["min_faces"], mesh["faces"], expect["min_faces"],
                  "media")
        if expect.get("bbox_nonzero"):
            size = (mesh.get("bbox") or {}).get("size")
            check(checks, sid, "bbox_nonzero", bool(size) and all(x > 0 for x in size), size, "all > 0", "media")
    allowed = expect.get("templates")
    if allowed:
        used = [w["template"]["name"] for w in rec.get("workflows") or []]
        check(checks, sid, "workflow_templates", bool(used) and all(u in allowed for u in used), used, allowed)
    if expect.get("models_hashed"):
        rows = rec.get("models") or []
        check(checks, sid, "models_hashed", bool(rows) and all(r.get("sha256") for r in rows),
              sum(1 for r in rows if r.get("sha256")), len(rows), "media")


# ---------------------------------------------------------------------------------------------------- age check
def age_of(app, item, depth=0):
    """The app's output age check on a gallery item. A picture or clip is publishable only when its own
    check is "ok" with no flag; a mesh is not checked itself and takes the check of the picture it came from."""
    row = {"age_check": item.get("age_check"), "age_flag": bool(item.get("age_flag")),
           "p_under21": item.get("p_under21"), "appearance_check": item.get("appearance_check")}
    if item.get("type") in ("image", "video"):
        row["held"] = row["age_flag"] or row["age_check"] != "ok"
        row["basis"] = "this file"
    else:
        parent = None
        if item.get("parent") and depth < 3:
            try:
                parent = app.get(f"/api/items/{item['parent']}")
            except RuntimeError:
                parent = None
        if parent:
            src = age_of(app, parent, depth + 1)
            row.update(held=src["held"], basis=f"source picture {parent['id']}", source_age_check=src["age_check"],
                       source_age_flag=src["age_flag"])
        else:
            row.update(held=True, basis="no source picture to take an age check from")
    row["publishable"] = not row["held"]
    return row


def attempt_summary(rec):
    """An earlier try at a step, kept in attempts[] with no file reference."""
    out = rec.get("output") or {}
    return {"status": rec.get("status"), "reason": rec.get("reason"), "job": rec.get("job"),
            "timings": rec.get("timings"), "seed": rec.get("seed"), "qc_source": rec.get("qc_source"),
            "results_age": rec.get("results_age"),
            "output": {k: out.get(k) for k in ("item_id", "type", "sha256", "size", "age", "held")} if out else None,
            "held_file_moved_to": rec.get("held_file_moved_to")}


# ---------------------------------------------------------------------------------------------------- one step
def run_step(app, step, ctx, run_dir, opts, templates, models, steps_by_id, attempt=1):
    sid = step["id"]
    try:
        params = resolve(step.get("params") or {}, ctx)
    except KeyError as e:
        name = e.args[0]
        hint = f" (pass --var {name.split('.', 1)[1]}=@file.json)" if name.startswith("chain.") else ""
        return {"id": sid, "title": step.get("title"), "kind": step["kind"], "status": "failed",
                "reason": f"needs {{{name}}}, which this run does not have{hint}"}
    probs = neutral_text_problems(params, ctx["subject"])
    if probs:
        raise Stop(f"{sid}: " + "; ".join(probs))
    base_rid = f"evidence-{ctx['run_id']}-{sid}"
    request_id = base_rid if attempt <= 1 else f"{base_rid}-a{attempt}"
    rec = {"id": sid, "title": step.get("title"), "kind": step["kind"], "params_sent": params,
           "request_id": request_id, "machine_profile": (ctx.get("profile") or {}).get("id"), "status": "running",
           # mock / ak_scores (from the --var qc label), unscored_proof (a gated step sent with no scores),
           # or not_applicable (a step with no keyframe gate)
           "qc_source": (ctx.get("qc_source") if "qc" in params else "unscored_proof") if step.get("qc_gate")
           else "not_applicable"}
    taps = {"app": LogTap(opts.app_log), "comfyui": LogTap(opts.comfy_log)}
    for t in taps.values():
        t.mark()
    t_submit = time.time()
    # The app answers a repeated request_id + kind with the job it already has (by design). A re-run is a new
    # attempt with its own id ("-a2", "-a3" ...); should the app still hand back a job created before this post
    # (an attempt the manifest lost), the next number is tried instead of accepting the old job.
    reused = []
    for _ in range(50):
        code, job = app.call("POST", "/api/jobs", {"kind": step["kind"], "params": params, "request_id": request_id})
        if code != 200 or not isinstance(job, dict) or float(job.get("created") or t_submit) >= t_submit - 1:
            break
        reused.append({"request_id": request_id, "job": job.get("id"), "status": job.get("status")})
        attempt += 1
        request_id = f"{base_rid}-a{attempt}"
    else:
        raise RuntimeError(f"the app returned an earlier job for 50 request ids in a row ({reused[-1]})")
    rec["request_id"], rec["attempt"] = request_id, attempt
    if reused:
        rec["request_ids_already_used"] = reused
    if code != 200:
        rec.update(status="failed", reason=f"app refused the job (HTTP {code}): {(job or {}).get('error') or job}",
                   job={"status": "refused", "error": (job or {}).get("error")})
        return rec
    jid = job["id"]
    last = None
    while job["status"] not in DONE:
        if time.time() - t_submit > opts.step_timeout:
            app.call("POST", f"/api/jobs/{jid}/cancel")
            rec.update(status="failed", reason=f"timed out after {opts.step_timeout} s; cancel sent")
            break
        time.sleep(opts.poll)
        job = app.get(f"/api/jobs/{jid}")
        line = f"{job.get('status')} {round(100 * (job.get('progress') or 0))}% {job.get('message') or ''}"
        if line != last and not opts.quiet:
            print(f"  {sid} {time.strftime('%H:%M:%S')} {line}", flush=True)
            last = line
    t_done = time.time()
    rec["job"] = {k: job.get(k) for k in ("id", "kind", "status", "error", "message", "created", "started", "finished",
                                         "warning")}
    rec["timings"] = {"submitted": t_submit, "done": t_done, "wall_s": round(t_done - t_submit, 3),
                      "queue_s": round((job.get("started") or t_done) - (job.get("created") or t_submit), 3),
                      "run_s": round((job.get("finished") or t_done) - (job.get("started") or t_done), 3)}
    # what the app sent to ComfyUI
    wfs = []
    try:
        sent = app.get(f"/api/jobs/{jid}/workflow").get("workflows") or []
    except RuntimeError:
        sent = []
    os.makedirs(os.path.join(run_dir, "workflows"), exist_ok=True)
    seen_models = {}
    for i, wf in enumerate(sent, 1):
        dest = os.path.join(run_dir, "workflows", f"{sid}_{i}.json")
        write_json(dest, wf)
        rows = workflow_models(wf)
        for r in rows:
            seen_models.setdefault(r["name"], []).append(f"{r['class_type']}.{r['input']}")
        wfs.append({**file_row(dest, run_dir), "template": match_template(wf, templates), "seeds": workflow_seeds(wf),
                    "model_inputs": rows})
    rec["workflows"] = wfs
    rec["workflow_template"] = wfs[-1]["template"]["name"] if wfs else None
    rec["models"] = [{**models.row(name), "used_by": sorted(set(used))} for name, used in sorted(seen_models.items())]
    # logs
    logs = {}
    os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
    logs["app"] = save_excerpt(taps["app"].excerpt(), os.path.join(run_dir, "logs", f"{sid}_app.log"), run_dir)
    comfy_lines = taps["comfyui"].excerpt()
    source = "file"
    if comfy_lines is None and ctx.get("comfy_url") and not opts.mock:
        comfy_lines, source = comfy_internal_logs(ctx["comfy_url"], t_submit, t_done), "/internal/logs/raw"
    logs["comfyui"] = save_excerpt(comfy_lines, os.path.join(run_dir, "logs", f"{sid}_comfyui.log"), run_dir)
    if logs["comfyui"].get("available"):
        logs["comfyui"]["source"] = source
    rec["logs"] = logs
    if rec.get("status") == "failed":
        return rec
    if job.get("can_retry"):
        # the app's output age check flagged the result and deleted it (D-C-51): held, nothing to write to the bundle
        rec["results_age"] = [{"age_check": "flag", "age_flag": True, "held": True, "deleted": True, "p_under21": None}]
        rec.update(status="held", output=None,
                   reason="held by the app's output age check (age_check=flag); the app deleted the result; "
                          "nothing written to the bundle")
        return rec
    if job["status"] != "done":
        rec.update(status="failed", reason=f"job ended {job['status']}: {job.get('error') or job.get('message')}")
        return rec
    # the output: every result's age check first; a held result is never downloaded
    pick = step.get("pick") or {}
    results = job.get("results") or []
    items = [app.get(f"/api/items/{r['id']}") for r in results if r.get("id")]
    ages = [age_of(app, it) for it in items]
    rec["results_age"] = [{"id": it["id"], "type": it.get("type"), **a} for it, a in zip(items, ages)]
    rec["result_ids_all"] = [it["id"] for it in items]
    usable = [it for it, a in zip(items, ages) if not a["held"]]
    def matches(r):
        return (not pick.get("type") or r.get("type") == pick["type"]) and \
            (not pick.get("kind_prefix") or str(r.get("kind") or "").startswith(pick["kind_prefix"]))
    item = next((it for it in usable if matches(it)), None)
    if item is None:
        held = [a for it, a in zip(items, ages) if a["held"] and matches(it)]
        if held:
            rec.update(status="held", reason="held by the app's output age check (" + "; ".join(
                f"age_check={a['age_check']} p_under21={a['p_under21']}" for a in held)
                + "); nothing written to the bundle", output=None)
        else:
            rec.update(status="failed", reason=f"no result matches {pick} among {[r.get('type') for r in results]}")
        return rec
    ext = os.path.splitext(item.get("file") or item.get("url") or "")[1] or ".bin"
    dest = os.path.join(run_dir, f"{sid}_{step['kind']}{ext}")
    app.download(item["url"], dest)
    out = {"item_id": item["id"], "item_kind": item.get("kind"), "type": item.get("type"), "url": item.get("url"),
           "app_file": item.get("file"), **file_row(dest, run_dir), "file": os.path.basename(dest)}
    out.pop("path", None)
    age = ages[items.index(item)]
    out["age"] = age
    out["held"], out["publishable"] = age["held"], age["publishable"]
    if opts.outputs and item.get("file"):
        on_disk = os.path.join(opts.outputs, item["file"])
        out["app_sha256"] = sha256_file(on_disk) if os.path.isfile(on_disk) else None
    join_from = (step.get("expect") or {}).get("join_after")
    join_frame = (((steps_by_id.get(join_from) or {}).get("output") or {}).get("video") or {}).get("frames") \
        if join_from else None
    out.update(probe_output(dest, item.get("type"), join_frame))
    rec["output"] = out
    rec["item"] = {k: item.get(k) for k in ("id", "kind", "type", "role", "model", "prompt", "seed", "w", "h",
                                           "parent", "created", "quality", "loop")}
    rec["result_ids"] = [it["id"] for it in usable]  # {E1.results.N} names usable results only
    prov = item.get("provenance") or {}
    rec["provenance"] = prov
    if prov.get("workflow"):
        rec["workflow_template_app_reported"] = prov["workflow"]
        if rec.get("workflow_template") != prov["workflow"]:
            rec["workflow_template_note"] = "the app's provenance names a different template than the graph match"
    if out.get("type") == "video" or "qc" in params:
        # which quality gate the clip went through: Ak's scores (--var qc) or the unscored proof path
        rec["qc_route"] = {"scores_given": "qc" in params,
                           "provenance": {k: v for k, v in prov.items() if "qc" in k.lower() or "proof" in k.lower()}}
    rec["prompt"] = item.get("prompt")
    rec["seed"] = item.get("seed") if item.get("seed") is not None else prov.get("seed")
    rec["model_label"] = item.get("model")
    rec["status"] = "done"
    return rec


# ---------------------------------------------------------------------------------------------------- UI walk
def ui_walk(base, run_dir, steps_by_id, tabs, timeout_ms=30000):
    """Screenshots of the app's pages written to ui/ (never opened), and whether <model-viewer> loads the mesh."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ran": False, "reason": "playwright is not installed in this Python"}
    out_dir = os.path.join(run_dir, "ui")
    os.makedirs(out_dir, exist_ok=True)
    shots, errors, mesh_view = [], [], None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                      extra_http_headers={"X-Easy-Studio": "1"})
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)[:300]))
            for i, tab in enumerate(tabs, 1):
                url = base + "/#/" + tab
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    page.wait_for_function("() => document.body && document.body.innerText.length > 40",
                                           timeout=timeout_ms)
                except Exception:
                    pass
                page.wait_for_timeout(800)
                dest = os.path.join(out_dir, f"{i:02d}_{tab}.png")
                page.screenshot(path=dest, full_page=True)
                shots.append({"tab": tab, "url": url, **file_row(dest, run_dir)})
            mesh_url = next((((s.get("output") or {}).get("url")) for s in steps_by_id.values()
                             if (s.get("output") or {}).get("mesh")), None)
            if mesh_url:
                # a same-origin page with no app script (the status JSON), then the app's own vendored viewer
                page = ctx.new_page()
                page.goto(base + "/api/status", wait_until="domcontentloaded", timeout=timeout_ms)
                t0 = time.time()
                result = page.evaluate("""async (src) => {
                    document.body.innerHTML = '';
                    const s = document.createElement('script');
                    s.type = 'module'; s.src = '/static/vendor/model-viewer.min.js';
                    document.head.append(s);
                    const defined = await Promise.race([customElements.whenDefined('model-viewer').then(() => true),
                                                        new Promise(r => setTimeout(() => r(false), 30000))]);
                    if (!defined) return {loaded: false, reason: 'model-viewer did not load'};
                    const mv = document.createElement('model-viewer');
                    mv.id = 'evidenceMesh'; mv.style.width = '800px'; mv.style.height = '600px';
                    mv.setAttribute('camera-controls', '');
                    const done = new Promise(res => {
                      mv.addEventListener('load', () => res({loaded: true}), {once: true});
                      mv.addEventListener('error', e => res({loaded: false, reason: String(e.detail && e.detail.type || 'error')}), {once: true});
                      setTimeout(() => res({loaded: false, reason: 'timeout'}), 60000);
                    });
                    mv.src = src; document.body.append(mv);
                    return await done;
                }""", mesh_url)
                mesh_view = {"src": mesh_url, **(result or {}), "ms": round((time.time() - t0) * 1000)}
                if mesh_view.get("loaded"):
                    page.wait_for_timeout(1500)
                    dest = os.path.join(out_dir, f"{len(tabs) + 1:02d}_model_viewer.png")
                    page.locator("#evidenceMesh").screenshot(path=dest)
                    mesh_view["screenshot"] = file_row(dest, run_dir)
            browser.close()
    except Exception as e:
        return {"ran": False, "reason": f"{type(e).__name__}: {str(e)[:300]}", "screenshots": shots}
    return {"ran": True, "viewed_by_session": False, "screenshots": shots, "page_errors": errors[:20],
            "model_viewer": mesh_view}


# ---------------------------------------------------------------------------------------------------- mock backend
class MockStack:
    """Mock ComfyUI plus the real app, both on free loopback ports (Tier 1). The app's outputs and both logs
    stay in state_dir, so a --resume finds the items the first run made."""

    def __init__(self, app_repo, state_dir, machine="m5_max"):
        self.app_repo = app_repo
        self.state_dir = state_dir
        self.tmp = tempfile.mkdtemp(prefix="evidence_mock_")
        self.out = os.path.join(state_dir, "outputs")
        log_dir = os.path.join(state_dir, "logs")
        self.comfy = os.path.join(self.tmp, "comfy")
        os.makedirs(self.out, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        agedir = os.path.join(self.comfy, "models", "easy_studio", "age_check")
        os.makedirs(os.path.join(agedir, "torch", "hub", "checkpoints"))
        os.makedirs(os.path.join(self.comfy, "models", "loras"))
        for n in ("model.safetensors", "config.json", "preprocessor_config.json",
                  os.path.join("torch", "hub", "checkpoints", "yunet_final.pth")):
            with open(os.path.join(agedir, n), "w") as fh:
                fh.write("{}")
        self.mp, self.ap = free_port(), free_port()
        self.app_log = os.path.join(log_dir, "mock_app_server.log")
        self.comfy_log = os.path.join(log_dir, "mock_comfyui.log")
        tests = os.path.join(app_repo, "tests")
        py = sys.executable
        env_mock = dict(os.environ, MOCK_LORA_DIR=os.path.join(self.comfy, "models", "loras"))
        self.mock = subprocess.Popen([py, os.path.join(tests, "mock_comfy.py"), str(self.mp)], env=env_mock,
                                     stdout=open(self.comfy_log, "a"), stderr=subprocess.STDOUT)
        env = dict(os.environ, EASY_STUDIO_OUTPUTS=self.out, COMFY_URL=f"http://127.0.0.1:{self.mp}",
                   EASY_STUDIO_PORT=str(self.ap), EASY_STUDIO_HOST="127.0.0.1", COMFY_DIR=self.comfy,
                   COMFY_PYTHON=py, EASY_STUDIO_TEST_RUN="1",  # this is the mock app: the stand-in age worker is honoured in a test run only
                   EASY_STUDIO_AGE_WORKER=os.path.join(tests, "fake_age_worker.py"),
                   EASY_STUDIO_MACHINE=machine, EASY_STUDIO_LORA_OFFLINE="1", EASY_STUDIO_PASSWORD="off")
        self.srv = subprocess.Popen([py, os.path.join(app_repo, "app", "server.py")], env=env,
                                    stdout=open(self.app_log, "a"), stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.ap}"
        self.comfy_url = f"http://127.0.0.1:{self.mp}"
        app = App(self.base)
        for _ in range(120):
            if app.up():
                break
            if self.srv.poll() is not None:
                break
            time.sleep(0.25)
        else:
            self.close()
            raise Stop("mock app did not start; see " + self.app_log)
        if self.srv.poll() is not None:
            self.close()
            raise Stop("mock app exited at start; see " + self.app_log)

    def close(self):
        for proc in (getattr(self, "srv", None), getattr(self, "mock", None)):
            if proc and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------- environment
def host_facts():
    facts = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()}
    if sys.platform == "darwin":
        for key, cmd in (("cpu", ["sysctl", "-n", "machdep.cpu.brand_string"]), ("memory_bytes", ["sysctl", "-n", "hw.memsize"]),
                         ("macos", ["sw_vers", "-productVersion"])):
            try:
                facts[key] = subprocess.run(cmd, capture_output=True, timeout=10).stdout.decode().strip()
            except Exception:
                pass
        if str(facts.get("memory_bytes", "")).isdigit():
            facts["memory_gb"] = round(int(facts.pop("memory_bytes")) / 1024 ** 3)
    return facts


def kit_pin(repo):
    try:
        with open(os.path.join(repo, "server-kit", "config", "kit.json"), encoding="utf-8") as fh:
            pins = json.load(fh)["software"]["git_pins"]
        row = next(p for p in pins if p.get("id") == "comfyui")
        return {"commit": row["commit"], "tag": row.get("tag"), "source": "server-kit/config/kit.json"}
    except Exception:
        return None


def comfy_stats(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=10) as r:
            st = json.loads(r.read())
    except Exception:
        return None
    sysd = st.get("system") or {}
    return {"comfyui_version": sysd.get("comfyui_version"), "python_version": sysd.get("python_version"),
            "pytorch_version": sysd.get("pytorch_version"), "os": sysd.get("os"),
            "ram_total_gb": round((sysd.get("ram_total") or 0) / 1024 ** 3, 1),
            "devices": [{"name": d.get("name"), "type": d.get("type"),
                         "vram_total_gb": round((d.get("vram_total") or 0) / 1024 ** 3, 1)} for d in st.get("devices") or []]}


def decide_tier(mock, status):
    version = str((status or {}).get("comfy_version") or "")
    device = str(((status or {}).get("machine") or {}).get("device") or "")
    if mock or "mock" in version.lower():
        return "T1", "mock ComfyUI: plumbing only; the media are test patterns, not renders"
    if device == "cuda":
        return "T3", "the server stack"
    return "T2", f"real render on this machine ({((status or {}).get('machine') or {}).get('id')})"


# ---------------------------------------------------------------------------------------------------- main
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=os.environ.get("EASY_STUDIO_URL", "http://127.0.0.1:7860"),
                    help="the running app (loopback)")
    ap.add_argument("--mock", action="store_true", help="Tier 1: start a mock ComfyUI and the app from --app-repo")
    ap.add_argument("--chain", default=DEFAULT_CHAIN, help="chain spec JSON (default tools/evidence_chain.json)")
    ap.add_argument("--evidence-root", default=DEFAULT_ROOT)
    ap.add_argument("--run-id", help="name of the run folder (default: time stamp + tier)")
    ap.add_argument("--resume", metavar="RUN_ID", help="keep the finished steps of this run and run the rest")
    ap.add_argument("--only", help="comma-separated step ids to run (others are kept from --resume or skipped)")
    ap.add_argument("--var", action="append", default=[], metavar="NAME=VALUE",
                    help="a chain variable, read as {chain.NAME}; NAME=@file.json reads a JSON file (repeatable)")
    ap.add_argument("--note", action="append", default=[], help="a line kept in the manifest's notes (repeatable; "
                    "earlier notes stay on --resume)")
    ap.add_argument("--prompt", help="override the chain's prompt")
    ap.add_argument("--seed", type=int, help="override the chain's seed")
    ap.add_argument("--app-repo", default=REPO, help="the app checkout the running app comes from (git head, workflows)")
    ap.add_argument("--comfy-dir", help="the ComfyUI checkout (git commit, model files)")
    ap.add_argument("--models-dir", action="append", default=[], help="extra model folder (repeatable)")
    ap.add_argument("--outputs", help="the app's EASY_STUDIO_OUTPUTS folder, to compare its copy of each output")
    ap.add_argument("--app-log", help="file the app's stdout/stderr goes to")
    ap.add_argument("--comfy-log", help="file ComfyUI's stdout/stderr goes to")
    ap.add_argument("--comfy-url", help="ComfyUI URL (default: the one the app reports)")
    ap.add_argument("--no-ui", action="store_true", help="skip the Playwright walk")
    ap.add_argument("--ui-tabs", default="create,video,3d,gallery,setup")
    ap.add_argument("--step-timeout", type=float, default=4 * 3600)
    ap.add_argument("--poll", type=float, default=3.0)
    ap.add_argument("--quiet", action="store_true")
    return ap.parse_args(argv)


def main(argv=None):
    opts = parse_args(argv)
    chain_path = os.path.abspath(opts.chain)
    spec = load_chain(chain_path)
    opts.app_repo = os.path.abspath(opts.app_repo)
    os.makedirs(opts.evidence_root, exist_ok=True)
    stack = drop_state = None
    try:
        if opts.resume:
            run_id = opts.resume
            run_dir = os.path.join(opts.evidence_root, run_id)
            with open(os.path.join(run_dir, "manifest.json"), encoding="utf-8") as fh:
                old = json.load(fh)
        else:
            old = None
        if opts.mock:
            if not old:
                run_id = opts.run_id or time.strftime("%Y%m%dT%H%M%S") + "-T1"
            stack = MockStack(opts.app_repo, os.path.join(opts.evidence_root, ".mock_state", run_id))
            opts.base, opts.app_log, opts.comfy_log, opts.outputs = stack.base, stack.app_log, stack.comfy_log, stack.out
        app = App(opts.base)
        status = app.get("/api/status")
        tier, tier_note = decide_tier(opts.mock, status)
        if old and old.get("tier") != tier:
            raise Stop(f"--resume: run {run_id} is {old.get('tier')}, this backend is {tier}")
        if not old:
            if not opts.mock:
                run_id = opts.run_id or time.strftime("%Y%m%dT%H%M%S") + "-" + tier
            run_dir = os.path.join(opts.evidence_root, run_id)
            if os.path.exists(run_dir):
                raise Stop(f"{run_dir} already exists")
            os.makedirs(run_dir)
        comfy_url = opts.comfy_url or status.get("comfy_url")
        machine = status.get("machine") or {}
        models_dirs = list(opts.models_dir)
        if opts.comfy_dir:
            models_dirs.insert(0, os.path.join(opts.comfy_dir, "models"))
        models = ModelIndex(models_dirs, HashCache(os.path.join(opts.evidence_root, ".model_sha256_cache.json")))
        templates = load_templates(opts.app_repo)
        comfy_git = git_info(opts.comfy_dir) if opts.comfy_dir else None
        pin = kit_pin(REPO)
        manifest = {
            "schema": SCHEMA, "run_id": run_id, "tier": tier, "tier_note": tier_note,
            "started": (old or {}).get("started") or now(), "finished": None, "status": "running",
            "viewed_by_session": False,
            "rules": spec.get("rules") or RULES[spec["subject"]],
            "tool": {"path": os.path.relpath(os.path.abspath(__file__), REPO), "sha256": sha256_file(os.path.abspath(__file__)),
                     "git": git_info(REPO)},
            "chain": {"path": chain_path, "sha256": sha256_file(chain_path), "spec": spec},
            "app": {"base": opts.base, "version": status.get("app"), "git": git_info(opts.app_repo),
                    "comfy_up": status.get("comfy_up"), "busy_at_start": status.get("busy"),
                    "features_ready": sorted(f["id"] for f in status.get("features") or [] if f.get("ready")),
                    "age_check": status.get("age_check"),
                    "mock_stack": {"app_log": opts.app_log, "comfy_log": opts.comfy_log} if opts.mock else None},
            "machine_profile": machine,
            "host": host_facts(),
            "comfyui": {"url": comfy_url, "version": status.get("comfy_version"), "gpu": status.get("gpu"),
                        "system_stats": None if opts.mock else comfy_stats(comfy_url or ""),
                        "git": comfy_git, "server_kit_pin": pin,
                        "matches_server_kit_pin": (comfy_git or {}).get("head") == (pin or {}).get("commit")
                        if comfy_git and pin else None},
            "steps": [], "checks": [], "ui_walk": None, "files": []}
        manifest["notes"] = list((old or {}).get("notes") or []) + [{"at": now(), "text": n} for n in opts.note]
        if old:
            manifest["resumed_from"] = {"started": old.get("started"), "status": old.get("status"), "at": now()}
        manifest_path = os.path.join(run_dir, "manifest.json")
        if tier != "T1" and not status.get("comfy_up"):
            raise Stop("the app reports ComfyUI is not up")
        given, var_files = parse_vars(opts.var)
        scores, qc_label = qc_declaration(given, tier)
        manifest["chain"]["qc_label"] = qc_label
        sendable = dict(given, **({"qc": scores} if scores is not None else {}))
        ctx = {"run_id": run_id, "subject": spec["subject"], "prompt": opts.prompt or spec.get("prompt"),
               "qc_source": (qc_label or {}).get("source"),
               "seed": opts.seed if opts.seed is not None else spec.get("seed"),
               "motion": spec.get("motion"), "profile": machine, "chain": {**(spec.get("vars") or {}), **sendable},
               "comfy_url": comfy_url}
        probs = neutral_text_problems({"prompt": ctx["prompt"] or "", "motion": ctx["motion"] or ""}, spec["subject"])
        probs += neutral_text_problems(given, spec["subject"], "--var ")
        if probs:
            raise Stop("; ".join(probs))
        manifest["chain"]["subject"] = spec["subject"]
        manifest["chain"]["vars_given"] = {k: {"value": v, **({"file": var_files[k]} if k in var_files else {})}
                                           for k, v in given.items()}
        only = set(opts.only.split(",")) if opts.only else None
        olds = {s["id"]: s for s in (old or {}).get("steps") or []}
        steps_by_id = {}
        for step in spec["steps"]:
            sid = step["id"]
            prev = olds.get(sid)
            earlier = list((prev or {}).get("attempts") or [])
            if prev and prev.get("status") == "done" and (only is None or sid not in only) and _still_there(prev, run_dir):
                age = recheck_age(app, prev)
                if age is not None and not age["held"]:
                    prev = dict(prev, kept_from_earlier_run=True)
                    prev["output"] = dict(prev["output"], age=age, held=False, publishable=True)
                    steps_by_id[sid] = prev
                    ctx[sid] = {"id": prev["output"]["item_id"], "item": prev.get("item") or {},
                                "output": prev["output"], "results": prev.get("result_ids") or [prev["output"]["item_id"]]}
                    manifest["steps"].append(prev)
                    write_json(manifest_path, manifest)
                    continue
                # held by the app's age check (or no longer in the app): out of the bundle, kept as an attempt
                prev = dict(prev, status="held" if age else "failed",
                            reason="held by the app's output age check" if age else
                            "the app no longer has this item, so its age check cannot be confirmed")
                if age:
                    prev["output"] = dict(prev["output"], age=age, held=True, publishable=False)
            if prev and prev.get("status") != "skipped" and only is not None and sid not in only:
                prev = dict(prev, kept_from_earlier_run=True)  # not asked to run again: the record stays as it was
                prev["held_file_moved_to"] = move_out(prev, run_dir, opts.evidence_root, run_id) \
                    if prev.get("status") != "done" else None
                steps_by_id[sid] = prev
                manifest["steps"].append(prev)
                write_json(manifest_path, manifest)
                continue
            if prev and prev.get("status") != "skipped":
                prev["held_file_moved_to"] = move_out(prev, run_dir, opts.evidence_root, run_id)
                earlier.append(attempt_summary(prev))
            missing = [n for n in step_needs(step) if n in steps_by_id and steps_by_id[n].get("status") != "done"
                       or n in {s["id"] for s in spec["steps"]} and n not in steps_by_id]
            if only is not None and sid not in only:
                rec = {"id": sid, "title": step.get("title"), "kind": step["kind"], "status": "skipped",
                       "reason": "not in --only"}
            elif missing:
                rec = {"id": sid, "title": step.get("title"), "kind": step["kind"], "status": "skipped",
                       "reason": f"needs {', '.join(sorted(missing))}, which did not finish"}
            else:
                if not opts.quiet:
                    print(f"{sid} {step.get('title') or ''}: posting {step['kind']}", flush=True)
                try:
                    rec = run_step(app, step, ctx, run_dir, opts, templates, models, steps_by_id,
                                   attempt=len(earlier) + 1)
                except Stop:
                    raise
                except Exception as e:
                    rec = {"id": sid, "title": step.get("title"), "kind": step["kind"], "status": "failed",
                           "reason": f"{type(e).__name__}: {str(e)[:400]}"}
            if earlier:
                rec["attempts"] = earlier
            steps_by_id[sid] = rec
            if rec.get("status") == "done":
                ctx[sid] = {"id": rec["output"]["item_id"], "item": rec.get("item") or {}, "output": rec["output"],
                            "results": rec.get("result_ids") or [rec["output"]["item_id"]]}
            manifest["steps"].append(rec)
            write_json(manifest_path, manifest)
            if not opts.quiet:
                print(f"{sid}: {rec['status']}" + (f" ({rec.get('reason')})" if rec.get("reason") else ""), flush=True)
        # checks
        checks = []
        for step in spec["steps"]:
            rec = steps_by_id.get(step["id"]) or {}
            if rec.get("status") == "skipped" and only is not None and step["id"] not in only:
                continue
            if rec.get("status") in ("done", "failed", "held") and rec.get("job"):
                step_checks(rec, steps_by_id, step.get("expect") or {}, checks)
            else:
                check(checks, step["id"], "step_ran", False, rec.get("status"), "done")
        for c in checks:
            c["counts"] = c["ok"] or (c["level"] == "media" and tier == "T1")
            if not c["ok"] and c["level"] == "media" and tier == "T1":
                c["note"] = "Tier 1 placeholder media: recorded, does not fail the run"
        manifest["checks"] = checks
        # UI walk
        if opts.no_ui:
            manifest["ui_walk"] = {"ran": False, "reason": "--no-ui"}
        else:
            if not opts.quiet:
                print("UI walk (screenshots to disk only)", flush=True)
            tabs = [t for t in opts.ui_tabs.split(",") if t]
            try:
                gallery = app.get("/api/gallery?limit=2000").get("items") or []
            except RuntimeError:
                gallery = []
            # a flagged result is deleted and a flagged older item is not listed (D-C-51), so nothing blurred is ever here
            held_items = [g.get("id") for g in gallery if g.get("type") in ("image", "video")
                          and (g.get("age_flag") or g.get("age_check") not in (None, "ok"))]
            if held_items and "gallery" in tabs:
                tabs.remove("gallery")
            old_ui = os.path.join(run_dir, "ui")
            if os.path.isdir(old_ui):  # an earlier walk's screenshots leave the bundle (nothing is deleted)
                dest = os.path.join(opts.evidence_root, ".attempts", run_id, "ui_" + time.strftime("%Y%m%dT%H%M%S"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                os.replace(old_ui, dest)
                manifest.setdefault("notes", []).append({"at": now(), "text": f"earlier UI screenshots moved to {dest}"})
            manifest["ui_walk"] = ui_walk(opts.base, run_dir, steps_by_id, tabs)
            manifest["ui_walk"]["app_items_age_held"] = len(held_items)
            if held_items:
                manifest["ui_walk"]["gallery_skipped"] = (
                    f"the app's gallery holds {len(held_items)} age-held item(s), so no "
                    "gallery screenshot is taken")
            mv = (manifest["ui_walk"] or {}).get("model_viewer")
            if mv is not None:
                check(checks, "UI", "model_viewer_loads_mesh", mv.get("loaded"), mv.get("reason") or "loaded", "loaded")
                checks[-1]["counts"] = checks[-1]["ok"]
        failed = [c for c in checks if not c["counts"]]
        left_out = [s["id"] for s in manifest["steps"] if s.get("status") == "skipped"]
        manifest["status"] = "incomplete" if failed else "partial" if left_out else "complete"
        if stack:
            # the mock app's library holds mock QC in its provenance: kept only while a --resume may need it
            drop_state = stack.state_dir if manifest["status"] == "complete" else None
            manifest["app"]["mock_state"] = {
                "path": stack.state_dir, "removed": bool(drop_state),
                "note": "mock app data (mock QC in its provenance); removed when the run completes, else kept "
                        "for --resume; never used by a real run"}
        manifest["summary"] = {"steps": {s["id"]: s.get("status") for s in manifest["steps"]},
                               "checks_passed": sum(1 for c in checks if c["ok"]), "checks_total": len(checks),
                               "failing": [f"{c['step']}.{c['id']}" for c in failed]}
        manifest["finished"] = now()
        manifest["files"] = sorted((file_row(os.path.join(dp, f), run_dir) for dp, _d, fs in os.walk(run_dir) for f in fs
                                    if f not in ("manifest.json",) and not f.endswith(".tmp")), key=lambda r: r["path"])
        write_json(manifest_path, manifest)
        print(f"{manifest['status']}: {manifest_path} ({manifest['summary']['checks_passed']}/"
              f"{manifest['summary']['checks_total']} checks)", flush=True)
        for f in failed:
            print(f"  FAIL {f['step']}.{f['id']}: value={f['value']} want={f['want']}", flush=True)
        return 0 if not failed else 1
    except Stop as e:
        print(f"stopped: {e}", file=sys.stderr, flush=True)
        return 2
    finally:
        if stack:
            stack.close()
            if drop_state:
                shutil.rmtree(drop_state, ignore_errors=True)


def recheck_age(app, rec):
    """The app's age check on a kept step's output, read again (None when the app no longer has the item)."""
    try:
        return age_of(app, app.get(f"/api/items/{rec['output']['item_id']}"))
    except (RuntimeError, KeyError, TypeError):
        return None


def move_out(rec, run_dir, root, run_id):
    """Move an earlier try's file out of the bundle folder (held media to .held/, others to .attempts/), so the
    bundle only ever holds the current, publishable outputs. Nothing is deleted."""
    name = (rec.get("output") or {}).get("file")
    src = os.path.join(run_dir, name) if name else None
    if not src or not os.path.isfile(src):
        return None
    dest_dir = os.path.join(root, ".held" if rec.get("status") == "held" else ".attempts", run_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{time.strftime('%Y%m%dT%H%M%S')}_{name}")
    os.replace(src, dest)
    return dest


def _still_there(rec, run_dir):
    out = rec.get("output") or {}
    path = os.path.join(run_dir, out.get("file") or "")
    return bool(out.get("file")) and os.path.isfile(path) and sha256_file(path) == out.get("sha256")


if __name__ == "__main__":
    sys.exit(main())
