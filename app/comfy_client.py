"""Tiny client for a running ComfyUI server (its normal HTTP + websocket API).

Target line: ComfyUI 0.43.0.

Endpoints used: POST /prompt, GET /history/{id}, GET /view, POST /upload/image,
GET /system_stats, GET /object_info, POST /api/jobs/{prompt_id}/cancel,
websocket /ws (for live progress only; falls back to polling).

A job is done only when that prompt's history reports success and completed and
a saved output file is present. The websocket executing event with node null is
not success. Cancel uses the per-job route and does not fall back to POST
/interrupt. On timeout the client reads that prompt's history and does not
submit the job again.
"""
import copy
import json
import os
import time
import uuid
from urllib.parse import urlencode, urlparse

import requests

try:
    import websocket  # websocket-client
except Exception:  # pragma: no cover
    websocket = None


GRAPH_GUARD = None  # set by the owner routes: guard(workflow) -> why this graph may not be sent, or ""


class ComfyError(RuntimeError):
    pass


# SaveVideo writes the file on the images list and sets animated. The container
# is part of the filename, not a separate videos property. ComfyUI 0.43 accepts
# these containers from SaveVideo; an animated PNG is not one of them.
# An animated WebP is an animated image, not a video and not a failure.
VIDEO_CONTAINERS = (".mp4", ".mkv", ".webm", ".mov")
ANIMATED_IMAGE_EXTS = (".webp",)
STILL_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
_OUTPUT_KEYS = ("images", "videos", "gifs", "video", "files", "3d", "audio")
STATUS_DONE = "done"
STATUS_PENDING = "pending"
STATUS_MISSING = "missing"
STATUS_CORRUPT = "corrupt"
STATUS_MISMATCH = "requirement mismatch"
STATUS_BACKEND_FAILURE = "backend_failure"


def _ext(filename):
    return os.path.splitext(str(filename or ""))[1].lower()


def _animated(node_out):
    """True when this node's UI payload is marked animated.

    ComfyUI sends the flag beside the images list, either as true or as a
    one-item list. A still image has no flag.
    """
    flag = (node_out or {}).get("animated")
    if flag is True:
        return True
    if isinstance(flag, (list, tuple)):
        return True in flag
    return False


def saved_output_files(node_out):
    """Files this node actually saved.

    A SaveVideo result is an images entry plus the animated flag and a video
    container. An animated WebP is kept: it is an animated image, not a video.
    Animated PNG is rejected. Temp still previews are skipped.
    """
    node_out = node_out or {}
    if not isinstance(node_out, dict):
        return []
    animated = _animated(node_out)
    found = []
    for key in _OUTPUT_KEYS:
        for item in node_out.get(key) or []:
            if not isinstance(item, dict) or not item.get("filename"):
                continue
            ext = _ext(item["filename"])
            if key == "images" and animated:
                if ext not in VIDEO_CONTAINERS and ext not in ANIMATED_IMAGE_EXTS:
                    continue
            elif item.get("type") == "temp" and key == "images":
                continue
            found.append(item)
    return found


def artifact_kind(filename, animated=False):
    """still, animated_image, video, model, or file. None when the name is not a result."""
    ext = _ext(filename)
    if animated and ext in ANIMATED_IMAGE_EXTS:
        return "animated_image"
    if ext in VIDEO_CONTAINERS or (animated and ext in VIDEO_CONTAINERS):
        return "video"
    if ext in STILL_IMAGE_EXTS:
        return "still"
    if ext in (".glb", ".gltf", ".obj", ".fbx", ".stl"):
        return "model"
    if filename:
        return "file"
    return None


_CHECKED_EXTS = ("png", "jpg", "jpeg", "webp", "mp4", "mov", "webm", "mkv")


def container_of(data):
    """Sniff a container from magic bytes only. This is not a structural check."""
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if len(data) >= 4 and data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"qt  ", b"mqt "):
            return "mov"
        return "mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "matroska"
    return None


def _compatible(ext, sniffed):
    if ext in ("jpg", "jpeg"):
        return sniffed == "jpeg"
    if ext == "mp4":
        return sniffed in ("mp4", "mov")
    if ext == "mov":
        return sniffed in ("mov", "mp4")
    if ext in ("webm", "mkv"):
        return sniffed == "matroska"
    return sniffed == ext


def _png_structure_ok(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    saw_ihdr = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        ctype = data[offset + 4:offset + 8]
        if length < 0 or offset + 12 + length > len(data):
            return False
        if ctype == b"IHDR":
            saw_ihdr = True
        if ctype == b"IEND":
            return saw_ihdr and offset + 12 + length == len(data)
        offset += 12 + length
    return False


def _jpeg_structure_ok(data):
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return False
    return data.endswith(b"\xff\xd9") and len(data) >= 4


def _riff_structure_ok(data, kind):
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != kind:
        return False
    declared = int.from_bytes(data[4:8], "little")
    if declared < 4 or declared + 8 != len(data):
        return False
    offset = 12
    saw = False
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        padded = size + (size & 1)
        if size < 0 or offset + 8 + padded > len(data):
            return False
        saw = True
        offset += 8 + padded
    return saw and offset == len(data)


def _mp4_structure_ok(data):
    """Walk ISO BMFF boxes. A box that claims more bytes than remain is corrupt."""
    if len(data) < 16:
        return False
    offset = 0
    saw_ftyp = saw_media = False
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        typ = data[offset + 4:offset + 8]
        header = 8
        if size == 1:
            if offset + 16 > len(data):
                return False
            size = int.from_bytes(data[offset + 8:offset + 16], "big")
            header = 16
        if size < header or offset + size > len(data):
            return False
        if typ == b"ftyp":
            saw_ftyp = True
        if typ in (b"mdat", b"moov"):
            saw_media = True
        offset += size
    return offset == len(data) and saw_ftyp and saw_media


def _ebml_vint(data, offset):
    if offset >= len(data) or data[offset] == 0:
        return None
    first = data[offset]
    width = 1
    mask = 0x80
    while width <= 8 and not (first & mask):
        width += 1
        mask >>= 1
    if width > 8 or offset + width > len(data):
        return None
    raw = int.from_bytes(data[offset:offset + width], "big")
    return width, raw & ((1 << (7 * width)) - 1)


def _matroska_structure_ok(data):
    if len(data) < 5 or data[:4] != b"\x1a\x45\xdf\xa3":
        return False
    parsed = _ebml_vint(data, 4)
    if not parsed:
        return False
    width, size = parsed
    end = 4 + width + size
    return 0 <= size and end <= len(data)


def _structure_ok(sniffed, data):
    if sniffed == "png":
        return _png_structure_ok(data)
    if sniffed == "jpeg":
        return _jpeg_structure_ok(data)
    if sniffed == "webp":
        return _riff_structure_ok(data, b"WEBP")
    if sniffed in ("mp4", "mov"):
        return _mp4_structure_ok(data)
    if sniffed == "matroska":
        return _matroska_structure_ok(data)
    return False


def _image_content_ok(data):
    """True only when the bytes decode to a real picture. A missing decoder fails closed."""
    try:
        import io
        from PIL import Image
    except Exception:
        return False
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            width, height = im.size
            return width > 0 and height > 0
    except Exception:
        return False


def _ffprobe_accepts(data, ext):
    """True only when ffprobe sees a video stream. No moov, or no ffprobe, is not acceptance."""
    if ext not in ("mp4", "mov", "webm", "mkv"):
        return False
    if ext in ("mp4", "mov") and b"moov" not in data:
        return False
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffprobe"):
        return False
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix="." + ext)
        os.write(fd, data)
        os.close(fd)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, timeout=20)
        text = (probe.stdout or b"").decode("utf-8", "replace")
        return probe.returncode == 0 and "video" in text
    except Exception:
        return False
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass


# ComfyUI 0.43.0 UNETLoader weight_dtype choices. A value outside this list is refused by ComfyUI before it runs.
UNET_WEIGHT_DTYPES = ("default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2")


def _glb_problem(data):
    """N05: a .glb must be a whole binary glTF with a real mesh in it, not only the right extension."""
    import mesh_check
    try:
        mesh_check.glb_stats_bytes(data)
    except ValueError:
        return "corrupt"
    return None


def media_problem(filename, data):
    """None when the bytes are a whole file of the named type. Sniffing is not enough."""
    if data is None:
        return "missing_download"
    if len(data) == 0:
        return "empty"
    ext = _ext(filename).lstrip(".")
    if ext == "glb":
        return _glb_problem(data)
    if ext not in _CHECKED_EXTS:
        return None
    sniffed = container_of(data)
    if sniffed is None:
        return "corrupt"
    if not _compatible(ext, sniffed):
        return "wrong_extension"
    if not _structure_ok(sniffed, data):
        return "corrupt"
    if sniffed in ("png", "jpeg", "webp") and not _image_content_ok(data):
        return "undecodable"
    if sniffed in ("mp4", "mov") or (sniffed == "matroska" and ext in ("webm", "mkv")):
        probe_ext = ext if ext in ("mp4", "mov", "webm", "mkv") else ("mov" if sniffed == "mov" else "mp4")
        if probe_ext in ("mp4", "mov") and b"moov" not in data:
            return "no_video"
        import shutil
        if not shutil.which("ffprobe"):
            return "corrupt"
        if not _ffprobe_accepts(data, probe_ext):
            return "no_video"
    return None


def file_is_corrupt(filename, data):
    """True when provided bytes are empty, truncated, signature-only, or the wrong type."""
    if data is None:
        return False
    return media_problem(filename, data) not in (None, "missing_download")


def artifact_key(art):
    """Identity of one saved file: saver node, folder, view type, and filename."""
    if isinstance(art, str):
        return os.path.basename(art)
    return "|".join([
        str(art.get("node_id") or ""),
        str(art.get("subfolder") or ""),
        str(art.get("type") or "output"),
        os.path.basename(str(art.get("filename") or "")),
    ])


def _payload_for(payloads, art):
    """Bytes for this artifact. A shared basename is not another saver's file."""
    if not payloads:
        return None
    if isinstance(art, str):
        base = os.path.basename(art)
        if art in payloads:
            return payloads[art]
        if base in payloads:
            return payloads[base]
        return None
    key = artifact_key(art)
    if key in payloads:
        return payloads[key]
    name = os.path.basename(str(art.get("filename") or ""))
    sub = str(art.get("subfolder") or "")
    qualified = f"{sub}/{name}" if sub else name
    if qualified in payloads:
        return payloads[qualified]
    if name in payloads:
        owners = [item for item in payloads if os.path.basename(str(item).split("|")[-1]) == name]
        if len(owners) == 1:
            return payloads[name]
    return None


def _norm_expected(expected):
    if not expected:
        return None
    text = str(expected).strip().lower().lstrip(".")
    if text in ("mp4", "video/mp4"):
        return "mp4"
    return text


def expected_savers(workflow):
    """Each SaveVideo node keeps its own id and format. Two savers are not collapsed."""
    found = []
    if not isinstance(workflow, dict):
        return found
    for nid, node in workflow.items():
        if not isinstance(node, dict) or node.get("class_type") != "SaveVideo":
            continue
        fmt = (node.get("inputs") or {}).get("format")
        found.append({
            "node_id": str(nid),
            "format": _norm_expected(fmt) if isinstance(fmt, str) and fmt.strip() else None,
        })
    return found


def expected_video_format(workflow):
    """Single SaveVideo format. Several savers are returned by expected_savers instead."""
    savers = expected_savers(workflow)
    if len(savers) == 1:
        return savers[0]["format"]
    return None


def _artifacts(hist):
    found = []
    for node_id, node_out in ((hist or {}).get("outputs") or {}).items():
        if not isinstance(node_out, dict):
            continue
        animated = _animated(node_out)
        for item in saved_output_files(node_out):
            ext = _ext(item["filename"])
            found.append({
                "node_id": str(node_id),
                "filename": item["filename"],
                "subfolder": item.get("subfolder") or "",
                "type": item.get("type") or "output",
                "kind": artifact_kind(item["filename"], animated and ext in ANIMATED_IMAGE_EXTS + VIDEO_CONTAINERS),
                "ext": ext,
            })
    return found


def _history_saved_files(hist):
    files = []
    for node_out in ((hist or {}).get("outputs") or {}).values():
        files.extend(saved_output_files(node_out))
    return files


def _rejected_animated_names(hist):
    names = []
    for node_out in ((hist or {}).get("outputs") or {}).values():
        if not isinstance(node_out, dict) or not _animated(node_out):
            continue
        for item in node_out.get("images") or []:
            if not isinstance(item, dict) or not item.get("filename"):
                continue
            ext = _ext(item["filename"])
            if ext not in VIDEO_CONTAINERS and ext not in ANIMATED_IMAGE_EXTS:
                names.append(str(item["filename"]))
    return names


def _backend_failure_text(hist):
    st = (hist or {}).get("status") or {}
    detail = ""
    for entry in st.get("messages") or []:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2 and entry[0] == "execution_error":
            data = entry[1] if isinstance(entry[1], dict) else {}
            detail = f"{data.get('node_type')}: {data.get('exception_message')}"
    return "backend_failure: ComfyUI failed while running the job. " + detail[:800]


def _missing_message(hist):
    rejected = _rejected_animated_names(hist)
    if not rejected:
        return "missing: ComfyUI reported success and completed, but no saved output file was present."
    text = (
        "missing: ComfyUI reported success, but the saved file is not an accepted result. "
        "SaveVideo is an images entry with the animated flag and a "
        ".mp4, .mkv, .webm, or .mov file. An animated WebP is an animated image."
    )
    if any(name.lower().endswith(".png") for name in rejected):
        text += " Animated PNG is not accepted."
    return text + " Rejected: " + ", ".join(rejected)


def classify_job(hist, expected=None, payloads=None):
    """Classify a ComfyUI history record.

    done, pending, missing, corrupt, requirement mismatch, or backend_failure.
    Expected MP4 with a WebP result is requirement mismatch, not a backend failure.
    An animated WebP is kind animated_image. A still WebP is kind still.
    executing.node == null does not decide this.
    """
    st = (hist or {}).get("status") or {}
    if st.get("status_str") == "error":
        return {"status": STATUS_BACKEND_FAILURE, "kind": None, "files": [], "message": _backend_failure_text(hist)}
    if st.get("status_str") != "success" or st.get("completed") is not True:
        return {"status": STATUS_PENDING, "kind": None, "files": [], "message": ""}
    files = _artifacts(hist)
    if payloads is not None:
        for art in files:
            data = _payload_for(payloads, art)
            where = f"node {art.get('node_id')}"
            if art.get("subfolder"):
                where += f" subfolder {art['subfolder']}"
            if data is None:
                return {
                    "status": STATUS_MISSING, "kind": art["kind"], "files": files,
                    "message": f"missing download: {art['filename']} ({where}) was not saved",
                }
            problem = media_problem(art["filename"], data)
            if problem == "wrong_extension" and _norm_expected(expected if isinstance(expected, str) else None) != "mp4":
                return {
                    "status": STATUS_CORRUPT, "kind": art["kind"], "files": files,
                    "message": f"corrupt: {art['filename']} ({where}) does not match its extension",
                }
            if problem in ("corrupt", "empty", "undecodable", "no_video"):
                detail = { "undecodable": " (image did not decode)", "no_video": " (no video track)" }.get(problem, "")
                return {
                    "status": STATUS_CORRUPT, "kind": art["kind"], "files": files,
                    "message": f"corrupt: saved output {art['filename']} is not a valid {art['ext'] or 'file'}{detail}",
                }
    if not files:
        return {"status": STATUS_MISSING, "kind": None, "files": [], "message": _missing_message(hist)}
    if isinstance(expected, (list, tuple)):
        return _classify_savers(files, expected, payloads)
    expected_fmt = _norm_expected(expected)
    if expected_fmt == "mp4":
        report = _mp4_requirement(files, payloads, "mp4")
        if report:
            return report
    kind = files[0]["kind"]
    if any(a["kind"] == "video" for a in files):
        kind = "video"
    elif any(a["kind"] == "animated_image" for a in files):
        kind = "animated_image"
    return {"status": STATUS_DONE, "kind": kind, "files": files, "message": ""}


def _is_real_mp4(art, payloads):
    data = _payload_for(payloads, art) if payloads is not None else None
    if art["ext"] != ".mp4":
        return False
    if data is None:
        return payloads is None
    return media_problem(art["filename"], data) is None and container_of(data) in ("mp4", "mov")


def _is_webp_art(art, payloads):
    if art["ext"] == ".webp" or art["kind"] == "animated_image":
        return True
    data = _payload_for(payloads, art) if payloads is not None else None
    return bool(data) and container_of(data) == "webp"


def _mp4_requirement(arts, payloads, label):
    mp4s = [art for art in arts if _is_real_mp4(art, payloads)]
    webps = [art for art in arts if _is_webp_art(art, payloads)]
    if mp4s:
        return None
    if webps:
        return {
            "status": STATUS_MISMATCH, "kind": webps[0]["kind"], "files": arts,
            "message": f"requirement mismatch: expected MP4 but got WebP ({label})",
        }
    return {
        "status": STATUS_MISSING, "kind": None, "files": arts,
        "message": f"missing: required video was not saved ({label})",
    }


_FORMAT_EXTS = {
    "mp4": (".mp4",),
    "mkv": (".mkv",),
    "webm": (".webm",),
    "mov": (".mov",),
    "webp": (".webp",),
    "png": (".png",),
    "jpg": (".jpg", ".jpeg"),
    "jpeg": (".jpg", ".jpeg"),
}


def _saver_bytes_ok(art, payloads):
    if payloads is None:
        return True
    data = _payload_for(payloads, art)
    return data is not None and media_problem(art["filename"], data) is None


def _classify_savers(files, savers, payloads):
    """Each required saver is judged on its own node and format. Another node's file does not count."""
    for saver in savers:
        node_id = str(saver.get("node_id"))
        fmt = _norm_expected(saver.get("format"))
        if not fmt:
            continue
        own = [art for art in files if art.get("node_id") == node_id]
        if fmt == "auto":
            if not any(art.get("ext") in (".mp4", ".mkv", ".webm", ".mov", ".webp") and _saver_bytes_ok(art, payloads) for art in own):
                return {
                    "status": STATUS_MISSING, "kind": None, "files": files,
                    "message": f"missing: required video was not saved (node {node_id})",
                }
            continue
        exts = _FORMAT_EXTS.get(fmt)
        if exts is None:
            return {
                "status": STATUS_MISSING, "kind": None, "files": files,
                "message": f"missing: required {fmt} was not saved (node {node_id})",
            }
        if fmt == "mp4":
            if not own:
                return {
                    "status": STATUS_MISSING, "kind": None, "files": files,
                    "message": f"missing: required mp4 was not saved (node {node_id})",
                }
            report = _mp4_requirement(own, payloads, f"node {node_id}")
            if report:
                report["files"] = files
                return report
            continue
        good = [art for art in own if art.get("ext") in exts and _saver_bytes_ok(art, payloads)]
        if not good:
            return {
                "status": STATUS_MISSING, "kind": None, "files": files,
                "message": f"missing: required {fmt} was not saved (node {node_id})",
            }
    if not files and not savers:
        return {"status": STATUS_MISSING, "kind": None, "files": [], "message": _missing_message({})}
    kind = None
    if any(a["kind"] == "video" for a in files):
        kind = "video"
    elif any(a["kind"] == "animated_image" for a in files):
        kind = "animated_image"
    elif files:
        kind = files[0]["kind"]
    return {"status": STATUS_DONE, "kind": kind, "files": files, "message": ""}


def job_succeeded(hist, expected=None, payloads=None):
    """True only when classification is done: success, completed, and a real saved file.

    executing.node == null is not success. A requirement mismatch is not success.
    """
    return classify_job(hist, expected=expected, payloads=payloads)["status"] == STATUS_DONE


def job_failure_message(hist, expected=None, payloads=None):
    """Why a terminal history record is not a successful job. Empty if it is still running."""
    report = classify_job(hist, expected=expected, payloads=payloads)
    if report["status"] in (STATUS_DONE, STATUS_PENDING):
        return ""
    return report["message"]


def job_terminal_state(hist, expected=None, payloads=None):
    """'done', 'fail', or 'pending'. Pending means keep waiting. Node null is never 'done'."""
    status = classify_job(hist, expected=expected, payloads=payloads)["status"]
    if status == STATUS_DONE:
        return "done"
    if status == STATUS_PENDING:
        return "pending"
    return "fail"


class ComfyClient:
    def __init__(self, base_url="http://127.0.0.1:8188", timeout=10):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())
        # Prompt currently inside queue/wait. A socket id, not a job id, is client_id.
        self.active_prompt_id = None
        self.expected_format = None

    # ---------- basic calls ----------
    def is_up(self):
        try:
            r = requests.get(self.base + "/system_stats", timeout=3)
            return r.ok
        except requests.RequestException:
            return False

    def system_stats(self):
        return requests.get(self.base + "/system_stats", timeout=self.timeout).json()

    def available(self, node_class, input_name):
        """List of choices ComfyUI offers for a combo input (e.g. model files it can see)."""
        try:
            info = requests.get(f"{self.base}/object_info/{node_class}", timeout=self.timeout).json()
            spec = info[node_class]["input"]["required"][input_name]
            return list(spec[0]) if isinstance(spec[0], list) else list(spec[1].get("options", []))
        except Exception:
            return []

    def upload_image(self, path, overwrite=True):
        with open(path, "rb") as f:
            files = {"image": (os.path.basename(path), f, "image/png")}
            data = {"type": "input", "overwrite": "true" if overwrite else "false"}
            r = requests.post(self.base + "/upload/image", files=files, data=data, timeout=120)
        if not r.ok:
            raise ComfyError(f"Upload failed ({r.status_code}): {r.text[:300]}")
        j = r.json()
        return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]

    def queue(self, workflow):
        why = GRAPH_GUARD(workflow) if GRAPH_GUARD else ""
        if why:
            raise ComfyError(why)
        r = requests.post(self.base + "/prompt",
                          json={"prompt": workflow, "client_id": self.client_id}, timeout=60)
        try:
            j = r.json()
        except ValueError:
            raise ComfyError(f"ComfyUI answered {r.status_code}: {r.text[:300]}")
        if not r.ok or j.get("node_errors"):
            raise ComfyError(self._explain_error(j))
        self.active_prompt_id = j["prompt_id"]
        self.expected_format = expected_savers(workflow) or expected_video_format(workflow)
        return j["prompt_id"]

    @staticmethod
    def _explain_error(j):
        msgs = []
        err = j.get("error")
        if isinstance(err, dict):
            msgs.append(err.get("message", "") + " " + str(err.get("details", "")))
        for node_id, ne in (j.get("node_errors") or {}).items():
            for e in ne.get("errors", []):
                msgs.append(f"[{ne.get('class_type', node_id)}] {e.get('message')}: {e.get('details')}")
        text = "\n".join(m for m in msgs if m.strip()) or json.dumps(j)[:500]
        import re as _re
        missing = sorted(set(_re.findall(r"'([^']+\.(?:safetensors|pth|ckpt|pt|bin|gguf))' not in", text)))
        if missing:
            return ("A model file this tool needs isn't installed yet: " + ", ".join(missing) +
                    ".\nOpen ⚙️ Setup — it shows the one command that downloads it. Then restart Easy Studio.")
        if "not in" in text and ("safetensors" in text or "value_not_in_list" in text):
            text += ("\n\nTip: a model file is missing. Check the README section "
                     "'Which file goes in which folder' and restart ComfyUI.")
        return "ComfyUI rejected the job:\n" + text

    def history(self, prompt_id):
        r = requests.get(f"{self.base}/history/{prompt_id}", timeout=self.timeout)
        r.raise_for_status()
        return r.json().get(prompt_id)

    def cancel(self, prompt_id):
        """Cancel one prompt with POST /api/jobs/{prompt_id}/cancel.

        ComfyUI 0.43.0 exposes that route. A missing route is reported.
        This never posts the global /interrupt endpoint.
        """
        if not prompt_id:
            return {"cancelled": False, "reason": "no prompt id"}
        url = f"{self.base}/api/jobs/{prompt_id}/cancel"
        try:
            r = requests.post(url, timeout=5, allow_redirects=False)
        except requests.RequestException as e:
            raise ComfyError(f"Could not reach ComfyUI to cancel prompt {prompt_id}: {e}")
        if r.is_redirect or r.status_code in (404, 405):
            raise ComfyError(
                f"ComfyUI has no per-job cancel route (POST /api/jobs/{prompt_id}/cancel returned {r.status_code}). "
                "The missing route was reported. No global /interrupt was sent."
            )
        if not r.ok:
            raise ComfyError(f"ComfyUI refused to cancel prompt {prompt_id} ({r.status_code}).")
        try:
            return r.json()
        except ValueError:
            return {"cancelled": True, "prompt_id": prompt_id}

    def interrupt(self, prompt_id=None):
        """Old name for cancel. Cancels one prompt and does not call POST /interrupt."""
        return self.cancel(prompt_id or self.active_prompt_id)

    def _open_progress_socket(self):
        if websocket is None:
            return None
        try:
            u = urlparse(self.base)
            scheme = "wss" if u.scheme == "https" else "ws"
            return websocket.create_connection(f"{scheme}://{u.netloc}/ws?clientId={self.client_id}", timeout=2)
        except Exception:
            return None

    def _pump_progress(self, ws, prompt_id, on_progress, deadline):
        """Read one progress event. executing.node == null is ignored."""
        if ws is None:
            remaining = deadline - time.time()
            if remaining > 0:
                time.sleep(min(1.0, remaining))
            return
        remaining = deadline - time.time()
        if remaining <= 0:
            return
        try:
            ws.settimeout(min(2.0, max(0.05, remaining)))
            msg = ws.recv()
        except Exception:
            return
        if not isinstance(msg, str):
            return
        try:
            m = json.loads(msg)
        except ValueError:
            return
        d = m.get("data") or {}
        if m.get("type") == "progress" and on_progress and d.get("max"):
            on_progress(d["value"] / d["max"], f"step {d['value']}/{d['max']}")
        if m.get("type") == "execution_error" and d.get("prompt_id") == prompt_id:
            raise ComfyError("ComfyUI error: " + str(d.get("exception_message", d))[:800])
        # type == executing and node is None arrives for both success and failure.
        # It is not a reason to treat the job as done.

    def _read_history(self, prompt_id):
        try:
            return self.history(prompt_id)
        except requests.RequestException:
            return None

    # ---------- waiting ----------
    def wait(self, prompt_id, on_progress=None, max_wait=60 * 60):
        """Block until history reports success, completed, and a saved file.

        Does not treat executing.node == null as done. On timeout, reads
        GET /history/{prompt_id} once more and does not submit the job again.
        """
        start = time.time()
        deadline = start + max_wait
        ws = self._open_progress_socket()
        try:
            while time.time() < deadline:
                self._pump_progress(ws, prompt_id, on_progress, deadline)
                h = self._read_history(prompt_id)
                state = job_terminal_state(h, expected=self.expected_format)
                if state == "done":
                    return h
                if state == "fail":
                    raise ComfyError(job_failure_message(h, expected=self.expected_format))
            # Timed out. Re-read this prompt. Never call queue() from here.
            try:
                late = self.history(prompt_id)
            except requests.RequestException as e:
                raise ComfyError(
                    f"Timed out waiting for ComfyUI prompt {prompt_id}. "
                    f"The job was not submitted again. History could not be read: {e}"
                )
            late_state = job_terminal_state(late, expected=self.expected_format)
            if late_state == "done":
                return late
            if late_state == "fail":
                raise ComfyError(job_failure_message(late, expected=self.expected_format) + " The job was not submitted again.")
            raise ComfyError(
                f"Timed out waiting for ComfyUI prompt {prompt_id}. The job was not submitted again."
            )
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    # ---------- outputs ----------
    def download_outputs(self, hist, dest_dir, by_node=False):
        """Fetch every picture / video / 3D file the job produced.
        Returns a list of local paths, or {node_id: [paths]} when by_node=True."""
        os.makedirs(dest_dir, exist_ok=True)
        found = {}
        self.last_downloads = []
        for node_id, node_out in (hist.get("outputs") or {}).items():
            for item in saved_output_files(node_out):
                q = urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                               "type": item.get("type", "output")})
                r = requests.get(f"{self.base}/view?{q}", timeout=600)
                r.raise_for_status()
                name = os.path.basename(item["filename"])
                local = os.path.join(dest_dir, name)
                if os.path.exists(local):
                    root, ext = os.path.splitext(local)
                    local = f"{root}_{int(time.time()*1000)}{ext}"
                with open(local, "wb") as f:
                    f.write(r.content)
                self.last_downloads.append({
                    "node_id": str(node_id),
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder") or "",
                    "type": item.get("type") or "output",
                    "local": local,
                })
                found.setdefault(node_id, []).append(local)
        if by_node:
            return found
        return [p for k in sorted(found, key=lambda x: (len(x), x)) for p in found[k]]

    def _payloads(self, paths):
        rows = getattr(self, "last_downloads", None) or []
        if rows:
            out = {}
            for row in rows:
                try:
                    with open(row["local"], "rb") as f:
                        data = f.read()
                except OSError:
                    data = b""
                out[artifact_key(row)] = data
            return out
        groups = paths.values() if isinstance(paths, dict) else [paths or []]
        out = {}
        for group in groups:
            for path in group or []:
                try:
                    with open(path, "rb") as f:
                        out[os.path.basename(path)] = f.read()
                except OSError:
                    out[os.path.basename(path)] = b""
        return out

    def run(self, workflow, dest_dir, on_progress=None, by_node=False):
        pid = self.queue(workflow)
        try:
            hist = self.wait(pid, on_progress=on_progress)
            paths = self.download_outputs(hist, dest_dir, by_node=by_node)
            report = classify_job(hist, expected=self.expected_format, payloads=self._payloads(paths))
            if report["status"] != STATUS_DONE:
                raise ComfyError(report["message"])
            return paths
        finally:
            if self.active_prompt_id == pid:
                self.active_prompt_id = None

    def free_memory(self):
        """Ask ComfyUI to unload its models (used before training, which needs the whole GPU)."""
        requests.post(self.base + "/free", json={"unload_models": True, "free_memory": True}, timeout=30)

    def object_info(self, node_class=None):
        u = self.base + "/object_info" + (f"/{node_class}" if node_class else "")
        return requests.get(u, timeout=30).json()


# ---------- workflow helpers ----------
WORKFLOW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows")


def load_workflow(name):
    with open(os.path.join(WORKFLOW_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def node_by_title(wf, title):
    for nid, node in wf.items():
        if node.get("_meta", {}).get("title") == title:
            return node
    raise KeyError(f"Workflow has no node titled {title!r}")


def fill(wf, prompt=None, negative=None, seed=None, width=None, height=None, length=None,
         start_image=None, fps=None):
    """Return a copy of an API-format workflow with the user's settings filled in.
    Nodes are found by their titles: POSITIVE, NEGATIVE, SEED, SIZE, START IMAGE, FPS."""
    wf = copy.deepcopy(wf)
    if prompt is not None:
        node_by_title(wf, "POSITIVE")["inputs"]["text"] = prompt
    if negative is not None:
        node_by_title(wf, "NEGATIVE")["inputs"]["text"] = negative
    if seed is not None:
        n = node_by_title(wf, "SEED")["inputs"]
        n["noise_seed" if "noise_seed" in n else "seed"] = int(seed)
    if width is not None:
        node_by_title(wf, "SIZE")["inputs"]["width"] = int(width)
    if height is not None:
        node_by_title(wf, "SIZE")["inputs"]["height"] = int(height)
    if length is not None:
        node_by_title(wf, "SIZE")["inputs"]["length"] = int(length)
    if start_image is not None:
        node_by_title(wf, "START IMAGE")["inputs"]["image"] = start_image
    if fps is not None:
        try:
            node_by_title(wf, "FPS")["inputs"]["fps"] = float(fps)
        except KeyError:
            pass
    for node in wf.values():  # ComfyUI ignores _meta, but strip it anyway to keep payloads clean
        node.pop("_meta", None)
    return wf


# ---------- editing API-format workflows by node title ----------
def title_id(wf, title):
    for nid, node in wf.items():
        if node.get("_meta", {}).get("title") == title:
            return nid
    raise KeyError(f"Workflow has no node titled {title!r}")


def has_title(wf, title):
    try:
        title_id(wf, title)
        return True
    except KeyError:
        return False


def set_in(wf, title, **values):
    n = wf[title_id(wf, title)]["inputs"]
    for k, v in values.items():
        n[k] = v
    return wf


def drop_title(wf, title):
    """Remove a node and every (optional) input that pointed at it."""
    nid = title_id(wf, title)
    del wf[nid]
    for node in wf.values():
        for k in [k for k, v in node["inputs"].items() if isinstance(v, list) and len(v) == 2 and v[0] == nid]:
            del node["inputs"][k]
    return wf


def set_seed(wf, seed):
    n = wf[title_id(wf, "SEED")]["inputs"]
    n["noise_seed" if "noise_seed" in n else "seed"] = int(seed) % (2**53)


LORA_HOOK = None  # set by pipelines: hook(lora_file, main_model_file) -> file to use on that loader (None = skip)
PAIR_HOOK = None  # set by pipelines: hook(lora_file) -> {"high_noise": file, "low_noise": file} or None


class LoraRouteError(ComfyError):
    """A LoRA cannot be attached to this model loader. The message is plain English."""


def wan14b_expert(unet_filename):
    """'high_noise' or 'low_noise' for a Wan 2.2 14B half, else ''. 5B and image models are not halves."""
    name = str(unet_filename or "").lower()
    if "14b" not in name:
        return ""
    if "high_noise" in name:
        return "high_noise"
    if "low_noise" in name:
        return "low_noise"
    return ""


def route_lora(file, unet_filename):
    """The one attach path for an extra LoRA on one model loader (inject_loras and the LoRA benchmark).

    Returns the file to load on that loader, or None to skip it. On a Wan 2.2 14B high- or low-noise
    loader the LoRA must be a high/low pair, and the matching half is used. A single, unpaired file on a
    14B half is a hard error: it is never copied onto both halves. The fast template's own lightx2v LoRAs
    are part of that template and never pass through here.
    """
    if not file:
        return None
    expert = wan14b_expert(unet_filename)
    if expert:
        pair = PAIR_HOOK(file) if PAIR_HOOK else None
        if not isinstance(pair, dict) or not pair.get("high_noise") or not pair.get("low_noise"):
            raise LoraRouteError(
                f"'{os.path.basename(str(file))}' is a single LoRA file. Wan 2.2 14B needs a matching high-noise and "
                "low-noise pair, so this LoRA was not attached. Add both halves to the LoRA library, or use a model "
                "with one loader.")
    chosen = LORA_HOOK(file, unet_filename) if LORA_HOOK else file
    if expert and chosen not in (pair.get(expert), file):
        raise LoraRouteError("The LoRA library returned the wrong half for this Wan 2.2 14B loader.")
    if expert:
        chosen = pair[expert]
    return chosen or None


def inject_loras(wf, loras):
    """Chain LoraLoaderModelOnly nodes after every main model loader. loras=[(file, strength)].
    Every attach goes through route_lora(): on Wan 2.2 14B the matching half of a pair, never an unpaired file."""
    loras = [(f, float(s)) for f, s in (loras or []) if f]
    if not loras:
        return wf
    loaders = [nid for nid, n in wf.items() if n["class_type"] in ("UNETLoader", "CheckpointLoaderSimple")]
    nxt = max(int(k) for k in wf if str(k).isdigit()) + 1000
    for lid in loaders:
        src = [lid, 0]
        new_ids = []
        main = wf[lid]["inputs"].get("unet_name") or wf[lid]["inputs"].get("ckpt_name") or ""
        for f, s in loras:
            f = route_lora(f, main)
            if not f:
                continue
            nid = str(nxt); nxt += 1
            wf[nid] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": src, "lora_name": f, "strength_model": s},
                       "_meta": {"title": f"Extra LoRA {f}"}}
            new_ids.append(nid)
            src = [nid, 0]
        for nid, node in wf.items():
            if nid in new_ids:
                continue
            for k, v in node["inputs"].items():
                if isinstance(v, list) and len(v) == 2 and v[0] == lid and v[1] == 0:
                    node["inputs"][k] = src
    add_triggers(wf, [f for f, _ in loras])
    return wf


TRIGGER_HOOK = None  # set by pipelines: lora file -> its trigger words (from the LoRA library)


def add_triggers(wf, files):
    """Put the LoRAs' trigger words at the start of the prompt (so the user never has to remember them)."""
    words = []
    for f in files:
        for w in (TRIGGER_HOOK(f) if TRIGGER_HOOK else []) or []:
            if w and w not in words:
                words.append(w)
    if not words:
        return wf
    slots = [(nid, "text") for nid, n in wf.items() if (n.get("_meta") or {}).get("title") == "POSITIVE" and "text" in n["inputs"]]
    slots += [(nid, "prompt") for nid, n in wf.items() if n["class_type"] == "TextEncodeQwenImageEditPlus"
              and isinstance(n["inputs"].get("prompt"), str)]
    if not slots:
        import wfdetect
        try:
            slots = wfdetect.analyse(wf)["prompt"]
        except Exception:
            slots = []
    for nid, k in slots:
        t = wf[nid]["inputs"].get(k)
        if isinstance(t, str):
            missing = [w for w in words if w.lower() not in t.lower()]
            if missing:
                wf[nid]["inputs"][k] = ", ".join(missing) + ", " + t
    return wf


def apply_advanced(wf, adv):
    """Seed / steps / cfg / sampler / scheduler / denoise from the Advanced drawer.
    Only the main sampler (the node titled SEED and its helpers) is changed."""
    adv = adv or {}
    if not adv:
        return wf
    sid = title_id(wf, "SEED")
    s = wf[sid]
    ct = s["class_type"]
    def put(node, key, val, conv):
        if val not in (None, "") and key in node["inputs"]:
            node["inputs"][key] = conv(val)
    if adv.get("seed") not in (None, ""):
        set_seed(wf, adv["seed"])
    if ct == "KSampler":
        put(s, "steps", adv.get("steps"), int); put(s, "cfg", adv.get("cfg"), float)
        put(s, "sampler_name", adv.get("sampler"), str); put(s, "scheduler", adv.get("scheduler"), str)
        put(s, "denoise", adv.get("denoise"), float)
    elif ct == "RandomNoise":
        for n in wf.values():
            if n["class_type"] == "KSamplerSelect":
                put(n, "sampler_name", adv.get("sampler"), str)
            if n["class_type"] == "BasicScheduler":
                put(n, "steps", adv.get("steps"), int); put(n, "scheduler", adv.get("scheduler"), str)
                put(n, "denoise", adv.get("denoise"), float)
            if n["class_type"] == "CFGGuider":
                put(n, "cfg", adv.get("cfg"), float)
    elif ct == "KSamplerAdvanced":  # video: two samplers share one step split -- leave steps alone
        for n in wf.values():
            if n["class_type"] == "KSamplerAdvanced":
                put(n, "sampler_name", adv.get("sampler"), str); put(n, "scheduler", adv.get("scheduler"), str)
                put(n, "cfg", adv.get("cfg"), float)
                if adv.get("seed") not in (None, ""):
                    n["inputs"]["noise_seed"] = int(adv["seed"]) % (2**53)
    inject_loras(wf, adv.get("loras"))
    return wf


def finalize(wf):
    wf = copy.deepcopy(wf)
    for node in wf.values():
        node.pop("_meta", None)
    return wf
