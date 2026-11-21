# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Hosted Wan video through Alibaba Model Studio (DashScope).

Docs read 2026-11-20 (help.aliyun.com / alibabacloud.com, Model Studio "text-to-video API reference" and
"image-to-video general API reference"): POST /api/v1/services/aigc/video-generation/video-synthesis with
`X-DashScope-Async: enable`, then GET /api/v1/tasks/{task_id}. Models: wan2.7-t2v (words) and
wan2.7-i2v-2026-04-25 (first frame). The host is the Singapore legacy domain, which the docs say stays
available; the newer per-workspace host would need a typed name in the address, so it is not used.
Not run against the real service yet (no key, no request in the build).
"""
import base64
import io
import os
import re
import tempfile

from PIL import Image

import presets
import safety

from . import guard
from .base import Provider, ProviderError, http

HOST = "dashscope-intl.aliyuncs.com"
SUBMIT = "/api/v1/services/aigc/video-generation/video-synthesis"
TASKS = "/api/v1/tasks/"
MODELS = {"t2v": "wan2.7-t2v", "i2v": "wan2.7-i2v-2026-04-25"}
MIN_S, MAX_S = 2, 15
MAX_IMAGE = 19 * 1024 * 1024
MAX_CLIP = 400 * 1024 * 1024
_TASK_RE = re.compile(r"[A-Za-z0-9\-]{8,64}")
_RESULT_HOST = re.compile(r"https://([a-z0-9.\-]+)/")


REALISM_PREFIX = "Photographic, live-action footage, realistic people, natural light and natural motion. "
REALISM_NEGATIVE = "anime, cartoon, animated, 3D render, CGI, illustration, painting, drawing"


def negative():
    """The always-avoid words first, then the realism words, then the video words, within the 500 characters."""
    always = f"{safety.ALWAYS_NEGATIVE}, {safety.VIOLENCE_NEGATIVE}"
    return (always + ", " + REALISM_NEGATIVE + ", " + presets.VIDEO_NEGATIVE)[:500]


def compose(prompt):
    """The words sent: photographic, live-action wording first (a realism default), then the checked prompt."""
    return (REALISM_PREFIX + prompt.strip())[:2000]


def _image_part(path):
    try:
        with Image.open(path) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "PNG")
    except (OSError, ValueError):
        raise ProviderError("That picture could not be read.") from None
    data = buf.getvalue()
    if len(data) > MAX_IMAGE:
        raise ProviderError("That picture is too large to send. Use a smaller one.")
    return {"type": "first_frame", "url": "data:image/png;base64," + base64.b64encode(data).decode("ascii")}


class DashScopeVideo(Provider):
    name, label, kind, host, key_name = "dashscope_video", "Alibaba Model Studio (Wan video)", "video", HOST, "dashscope"

    def video(self, prompt, image_path=None, seconds=5, model=None):
        """One call for all three jobs. With image_path: the picture is the first frame, so an extend is the
        last frame of a clip plus the instruction, and a picture-to-video is the picture plus the words. With
        none: words only. Returns a handle for poll()."""
        guard.check_call(media=bool(image_path))      # before the picture is even read
        if image_path:
            guard.consume_frame(image_path)           # only a picture the caller cleared (age check, likeness, ancestry)
        guard.check_text([prompt])
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderError("Describe what happens in the video.")
        n = max(MIN_S, min(MAX_S, int(round(float(seconds or 5)))))
        mode = "i2v" if image_path else "t2v"
        model = model or MODELS[mode]
        if model != MODELS[mode]:
            raise ProviderError("Pick the Wan model that fits this request.")
        body = {"model": model, "input": {"prompt": compose(prompt[:1900]), "negative_prompt": negative()},
                "parameters": {"resolution": "720P", "duration": n, "prompt_extend": False, "watermark": False}}
        if image_path:
            body["input"]["media"] = [_image_part(image_path)]
        else:
            body["parameters"]["ratio"] = "16:9"
        data = self._send("POST", SUBMIT, body, media=bool(image_path), headers={"X-DashScope-Async": "enable"})
        task = ((data.get("output") or {}).get("task_id"))
        if not isinstance(task, str) or not _TASK_RE.fullmatch(task):
            raise ProviderError(f"{self.label} did not return a task number.")
        return {"provider": self.name, "task": task, "model": model, "seconds": n}

    def poll(self, handle):
        task = (handle or {}).get("task")
        if not isinstance(task, str) or not _TASK_RE.fullmatch(task):
            raise ProviderError("That is not a task from this provider.")
        out = (self._send("GET", TASKS + task).get("output") or {})
        status = out.get("task_status")
        if status in ("PENDING", "RUNNING"):
            return {"status": "running", "file": None}
        if status != "SUCCEEDED":
            code = out.get("code")
            return {"status": "failed", "file": None, "code": code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", code) else ""}
        return {"status": "done", "file": self._fetch(out.get("video_url"), handle.get("dir"))}

    def _fetch(self, url, folder):
        """Download the finished clip. No key goes with this request, and only an https address on the
        service's own domain is followed."""
        m = _RESULT_HOST.match(url) if isinstance(url, str) else None
        if not m or not m.group(1).endswith(".aliyuncs.com"):
            raise ProviderError(f"{self.label} returned a clip address this app will not open.")
        folder = folder or tempfile.mkdtemp(prefix="es_remote_")
        dest = os.path.join(folder, "remote_clip.mp4")
        try:
            resp = http().get(url, stream=True, timeout=120, allow_redirects=False)
            if getattr(resp, "status_code", 0) != 200:
                raise ProviderError(f"{self.label}'s clip could not be downloaded (HTTP {getattr(resp, 'status_code', 0)}).")
            size = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    size += len(chunk)
                    if size > MAX_CLIP:
                        raise ProviderError("The clip is larger than this app accepts.")
                    f.write(chunk)
        except ProviderError:
            if os.path.exists(dest):
                os.remove(dest)
            raise
        except Exception:
            if os.path.exists(dest):
                os.remove(dest)
            raise ProviderError(f"The clip from {self.label} could not be downloaded.") from None
        return dest
