"""A fake ComfyUI server for testing Easy Studio without a GPU.

Speaks the same API (/prompt, /history, /view, /upload/image, /ws, /system_stats, /object_info,
/interrupt, /api/jobs/{id}/cancel). Every job is CHECKED against a snapshot of the real ComfyUI 0.43 node list
(tests/comfy_nodes_0.43.json): node types must exist, required inputs must be present, unknown
inputs are rejected, links must point at real nodes/outputs, and loaded pictures must have been
uploaded. Then it fakes the outputs: pictures of the right size (RGBA for cut-outs), ffmpeg
test-pattern MP4s with the right size/frame count, and a small textured-colour cube .glb for 3D.
"""
import asyncio
import gzip
import json
import math
import os
import struct
import sys
import tempfile
import uuid
import re

from aiohttp import web
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import video_tools as V  # noqa: E402

SNAP = json.load(open(os.path.join(HERE, "comfy_nodes_0.43.json")))
NODES = SNAP["nodes"]
ROOT = tempfile.mkdtemp(prefix="mockcomfy_")
INPUT = os.path.join(ROOT, "input")
OUTPUT = os.environ.get("MOCK_OUTPUT_DIR") or os.path.join(ROOT, "output")  # tests can put it where the app looks
os.makedirs(INPUT, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)
HISTORY, SOCKETS, LOG = {}, {}, []
PENDING = set()
CANCELS, INTERRUPTS, HISTORY_HITS = [], [], []
HOLD_CANCELS = set()
SLOW = float(os.environ.get("MOCK_DELAY", "0.05"))


def model_files():
    """Every model file named in Easy Studio's workflows (the mock pretends they're all installed)."""
    files = set()
    wdir = os.path.join(HERE, "..", "app", "workflows")
    for n in os.listdir(wdir):
        for node in json.load(open(os.path.join(wdir, n))).values():
            for v in node["inputs"].values():
                if isinstance(v, str) and v.endswith((".safetensors", ".pth", ".ckpt")):
                    files.add(v)
    if os.environ.get("MOCK_MISSING"):
        files -= set(os.environ["MOCK_MISSING"].split(","))
    return sorted(files)


LORAS = ["my_style_lora.safetensors", "detail_tweaker.safetensors"]


async def system_stats(_):
    return web.json_response({"system": {"comfyui_version": "0.43.0 (mock)"},
                              "devices": [{"name": "MOCK GPU (no real model)", "type": "cuda", "vram_total": 96 * 1024**3}]})


def _info():
    files = model_files()
    combo = lambda lst: [lst, {}]  # noqa: E731
    out = {}
    for cls, key in {"UNETLoader": "unet_name", "CLIPLoader": "clip_name", "VAELoader": "vae_name",
                     "CheckpointLoaderSimple": "ckpt_name", "UpscaleModelLoader": "model_name",
                     "ModelPatchLoader": "name", "CLIPVisionLoader": "clip_name",
                     "LoadBackgroundRemovalModel": "bg_removal_name", "ImageOnlyCheckpointLoader": "ckpt_name"}.items():
        out[cls] = {"input": {"required": {key: combo(files)}}}
    out["LoraLoaderModelOnly"] = {"input": {"required": {"lora_name": combo(list(dict.fromkeys([f for f in files if re.search(r"lora|lightning|lightx2v", f, re.I)] + LORAS + _lora_dir())))}}}
    out["KSampler"] = {"input": {"required": {"sampler_name": combo(SNAP["lists"]["samplers"]),
                                              "scheduler": combo(SNAP["lists"]["schedulers"])}}}
    return out


_FULL = None


def _lora_dir():
    """Like ComfyUI: every .safetensors in the LoRA folder (MOCK_LORA_DIR), read fresh each time."""
    d = os.environ.get("MOCK_LORA_DIR")
    out = []
    if d and os.path.isdir(d):
        for r, ds, fs in os.walk(d):
            for f in fs:
                if f.endswith(".safetensors"):
                    out.append(os.path.relpath(os.path.join(r, f), d).replace(os.sep, "/"))
    return sorted(out)


def _full_info():
    """The real ComfyUI 0.43 /object_info (gzipped snapshot), with the loader lists swapped for the mock's files."""
    global _FULL
    if _FULL is None:
        p = os.path.join(HERE, "comfy_object_info_0.43.json.gz")
        _FULL = json.load(gzip.open(p)) if os.path.exists(p) else {}
    out = dict(_FULL)
    for cls, v in _info().items():
        base = json.loads(json.dumps(out.get(cls, {"input": {"required": {}}})))
        base.setdefault("input", {}).setdefault("required", {}).update(v["input"]["required"])
        out[cls] = base
    return out


async def object_info(req):
    info = _full_info()
    n = req.match_info.get("n")
    return web.json_response({n: info[n]} if n else info) if (not n or n in info) else web.json_response({})


async def upload(req):
    data = await req.post()
    f = data["image"]
    with open(os.path.join(INPUT, os.path.basename(f.filename)), "wb") as out:
        out.write(f.file.read())
    return web.json_response({"name": os.path.basename(f.filename), "subfolder": "", "type": "input"})


# ---------------------------------------------------------------- validation
def validate(wf):
    errors = {}
    if not isinstance(wf, dict) or not wf:
        return {"error": {"message": "empty prompt"}}
    for nid, node in wf.items():
        ct = node.get("class_type")
        spec = NODES.get(ct)
        errs = []
        if spec is None:
            errs.append({"message": "unknown node type", "details": ct})
        else:
            inputs = node.get("inputs", {})
            base = {k.split(".")[0] for k in inputs}
            for r in spec["r"]:
                if r not in base:
                    errs.append({"message": "Required input is missing", "details": r})
            for k in base:
                if k not in spec["r"] and k not in spec["o"]:
                    errs.append({"message": "unknown input", "details": k})
            for k, v in inputs.items():
                if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                    src = wf.get(v[0])
                    if src is None:
                        errs.append({"message": "link to missing node", "details": f"{k} -> {v[0]}"})
                    elif NODES.get(src["class_type"]) and v[1] >= max(1, NODES[src["class_type"]]["out"]):
                        errs.append({"message": "bad output index", "details": f"{k} -> {v}"})
            if ct == "UNETLoader" and inputs.get("weight_dtype") not in UNET_WEIGHT_DTYPES:  # as ComfyUI 0.43.0 refuses it
                errs.append({"message": "Value not in list", "type": "value_not_in_list",
                             "details": f"weight_dtype: '{inputs.get('weight_dtype')}' not in {list(UNET_WEIGHT_DTYPES)}"})
            if ct in ("LoadImage", "LoadImageMask"):
                img = inputs.get("image")
                if not isinstance(img, str) or not os.path.exists(os.path.join(INPUT, img)):
                    errs.append({"message": "Invalid image file", "details": str(img)})
            for k, v in inputs.items():
                if isinstance(v, str) and v.endswith((".safetensors", ".pth", ".ckpt")) and v not in model_files() + LORAS + _lora_dir():
                    errs.append({"message": "Value not in list", "details": f"{k}: '{v}' not in (list of length {len(model_files())})", "type": "value_not_in_list"})
        if errs:
            errors[nid] = {"errors": errs, "class_type": ct}
    return errors


# ---------------------------------------------------------------- fake outputs
def ancestors(wf, nid, seen=None):
    seen = seen if seen is not None else set()
    for v in wf[nid]["inputs"].values():
        if isinstance(v, list) and len(v) == 2 and v[0] in wf and v[0] not in seen:
            seen.add(v[0])
            ancestors(wf, v[0], seen)
    return seen


def find(wf, ids, cls):
    return [wf[i] for i in ids if wf[i]["class_type"] == cls]


def load_input(node):
    return Image.open(os.path.join(INPUT, node["inputs"]["image"]))


def _font(s):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    except Exception:
        return ImageFont.load_default()


def figure(size, seed, label):
    """A friendly placeholder 'character' (gradient + silhouette + label)."""
    w, h = size
    hue = seed % 360
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    import colorsys
    for y in range(h):
        r, g, b = colorsys.hsv_to_rgb(((hue + y * 40 / h) % 360) / 360, .45, .35 + .35 * y / h)
        d.line([(0, y), (w, y)], fill=(int(r * 255), int(g * 255), int(b * 255)))
    cx = w // 2
    s = min(w, h) / 1024
    skin = (236, 200, 180)
    d.ellipse([cx - 90 * s, h * .16, cx + 90 * s, h * .16 + 200 * s], fill=skin)
    d.polygon([(cx - 170 * s, h), (cx - 120 * s, h * .16 + 260 * s), (cx + 120 * s, h * .16 + 260 * s), (cx + 170 * s, h)],
              fill=((hue * 3) % 255, 60, 140))
    d.rectangle([cx - 30 * s, h * .16 + 190 * s, cx + 30 * s, h * .16 + 270 * s], fill=skin)
    f = _font(max(14, int(34 * s)))
    d.rounded_rectangle([20, 20, 20 + d.textlength("MOCK · " + label, font=f) + 24, 20 + 52 * s + 10], 12, fill=(0, 0, 0))
    d.text((32, 26), "MOCK · " + label, fill=(255, 255, 255), font=f)
    return im


def stamp(im, label, tint):
    im = im.convert("RGB")
    over = Image.new("RGB", im.size, tint)
    im = Image.blend(im, over, 0.22)
    d = ImageDraw.Draw(im)
    f = _font(max(14, im.width // 28))
    d.rounded_rectangle([16, im.height - 70, 26 + d.textlength(label, font=f) + 16, im.height - 16], 10, fill=(0, 0, 0))
    d.text((28, im.height - 64), label, fill=(255, 255, 255), font=f)
    return im


BAD_GLB_SEED = 4040404  # tests: this seed makes SaveGLB write a broken file
UNET_WEIGHT_DTYPES = ("default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2")  # ComfyUI 0.43.0 UNETLoader


def seed_of(wf):
    for n in wf.values():
        for k in ("seed", "noise_seed"):
            if isinstance(n["inputs"].get(k), int):
                return n["inputs"][k]
    return 7


def render_image(wf, nid):
    anc = ancestors(wf, nid)
    loads = [wf[i] for i in sorted(anc, key=lambda x: int(x) if x.isdigit() else 0) if wf[i]["class_type"] == "LoadImage"]
    first = load_input(loads[0]) if loads else None
    seed = seed_of(wf)
    if find(wf, anc, "JoinImageWithAlpha"):
        im = first.convert("RGBA")
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).ellipse([im.width * .18, im.height * .05, im.width * .82, im.height * 1.1], fill=255)
        im.putalpha(m)
        return im
    if find(wf, anc, "MaskToImage"):
        m = Image.new("L", first.size, 0)
        ImageDraw.Draw(m).ellipse([first.width * .18, first.height * .05, first.width * .82, first.height * 1.1], fill=255)
        return m.convert("RGB")
    if find(wf, anc, "ImageUpscaleWithModel"):
        sc = 4 * find(wf, anc, "ImageScaleBy")[0]["inputs"]["scale_by"]
        return first.convert("RGB").resize((int(first.width * sc), int(first.height * sc)))
    if find(wf, anc, "SDPoseDrawKeypoints"):
        im = Image.new("RGB", first.size, 0)
        d = ImageDraw.Draw(im)
        w, h = im.size
        for a, b, c in [((.5, .2), (.5, .5), (0, 255, 0)), ((.5, .25), (.3, .45), (255, 170, 0)), ((.5, .25), (.7, .3), (255, 85, 0)),
                        ((.5, .5), (.4, .9), (0, 170, 255)), ((.5, .5), (.62, .88), (0, 85, 255))]:
            d.line([(a[0] * w, a[1] * h), (b[0] * w, b[1] * h)], fill=c, width=10)
        d.ellipse([w * .46, h * .1, w * .54, h * .18], fill=(255, 0, 255))
        return im
    if find(wf, anc, "ImageCompositeMasked"):
        mk = find(wf, anc, "LoadImageMask")[0]
        mask = Image.open(os.path.join(INPUT, mk["inputs"]["image"])).convert("L").resize(first.size)
        assert mask.getbbox(), "inpaint mask is empty"
        fill = Image.new("RGB", first.size, ((seed * 5) % 255, 40, 160))
        return Image.composite(fill, first.convert("RGB"), mask)
    if find(wf, anc, "TextEncodeQwenImageEditPlus"):
        enc = find(wf, anc, "TextEncodeQwenImageEditPlus")
        label = "edit"
        prompt = [n for n in enc if "prompt" in n["inputs"]][0]["inputs"]["prompt"].lower()
        for word in ("pose", "clothing", "background", "add ", "expression", "view", "photograph"):
            if word in prompt:
                label = {"add ": "object", "clothing": "outfit", "view": "angle", "photograph": "photoshoot"}.get(word, word)
                break
        if "image2" in enc[0]["inputs"]:
            label += " +ref"
        return stamp(first, f"MOCK {label}", ((seed * 37) % 255, (seed * 11) % 255, 200))
    lat = find(wf, anc, "EmptySD3LatentImage") + find(wf, anc, "EmptyLatentImage") + find(wf, anc, "EmptyFlux2LatentImage")
    size = (lat[0]["inputs"]["width"], lat[0]["inputs"]["height"]) if lat else (1024, 1024)
    lbl = "pose" if find(wf, anc, "QwenImageDiffsynthControlnet") else "picture"
    return figure(size, seed, lbl)


def cube_glb(path, color=(0.9, 0.5, 0.7)):
    """A tiny valid glTF-binary cube (8 verts, 12 tris) with a coloured material."""
    v = [(-.5, 0, -.3), (.5, 0, -.3), (.5, 1.7, -.3), (-.5, 1.7, -.3), (-.5, 0, .3), (.5, 0, .3), (.5, 1.7, .3), (-.5, 1.7, .3)]
    idx = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5]
    vb = b"".join(struct.pack("<3f", *p) for p in v)
    ib = b"".join(struct.pack("<H", i) for i in idx)
    ib += b"\x00" * ((4 - len(ib) % 4) % 4)
    binb = vb + ib
    gltf = {"asset": {"version": "2.0", "generator": "Easy Studio mock"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
            "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [*color, 1], "metallicFactor": 0, "roughnessFactor": .6}}],
            "buffers": [{"byteLength": len(binb)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vb), "target": 34962},
                            {"buffer": 0, "byteOffset": len(vb), "byteLength": len(idx) * 2, "target": 34963}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [-.5, 0, -.3], "max": [.5, 1.7, .3]},
                          {"bufferView": 1, "componentType": 5123, "count": len(idx), "type": "SCALAR"}]}
    js = json.dumps(gltf).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binb)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(struct.pack("<I4s", len(binb), b"BIN\x00") + binb)


def render(pid, wf):
    outputs = {}
    marked = "magentatest" in json.dumps(wf).lower()
    for nid, node in wf.items():
        ct = node["class_type"]
        sub = os.path.dirname(node["inputs"].get("filename_prefix", "easy-studio/x"))
        if ct == "SaveImage":
            im = render_image(wf, nid)
            if "uncheckedtest" in json.dumps(wf).lower():
                im = Image.new("RGB", im.size, (30, 30, 30))
                ImageDraw.Draw(im).rectangle([0, 0, 15, 15], fill=(1, 2, 3))
            elif marked:  # tests: the fake age checker flags pictures with a magenta corner
                im = im.convert("RGB")
                ImageDraw.Draw(im).rectangle([0, 0, 15, 15], fill=(255, 0, 255))
            fn = f"{os.path.basename(node['inputs']['filename_prefix'])}_{pid[:8]}_{nid}.png"
            im.save(os.path.join(OUTPUT, fn))
            outputs[nid] = {"images": [{"filename": fn, "subfolder": sub, "type": "output"}]}
        elif ct in ("SaveVideo", "VHS_VideoCombine"):
            anc = ancestors(wf, nid)
            size = [wf[i]["inputs"] for i in anc if all(isinstance(wf[i]["inputs"].get(k), int) for k in ("width", "height"))
                    and isinstance(wf[i]["inputs"].get("length", wf[i]["inputs"].get("num_frames")), int)]
            size = size[0] if size else {"width": 640, "height": 384, "length": 49}
            fps = [wf[i]["inputs"]["fps"] for i in anc if isinstance(wf[i]["inputs"].get("fps"), (int, float))]
            fps = fps[0] if fps else 16
            prefix = str(node["inputs"].get("filename_prefix", ""))
            fn = f"video_{pid[:8]}.mp4"
            for ext in (".png", ".mkv", ".webm", ".mov", ".mp4", ".webp"):
                if f"es_contract_{ext[1:]}" in prefix:
                    fn = f"clip_{pid[:8]}{ext}"
                    break
            if "es_contract_corrupt" in prefix:
                fn = f"clip_{pid[:8]}.mp4"
            path = os.path.join(OUTPUT, fn)
            if "es_contract_corrupt" in prefix:
                with open(path, "wb") as f:
                    f.write(b"not-a-real-mp4-file")
            elif fn.endswith(".mp4"):
                V.make_test_video(path, size["width"], size["height"], size.get("length", size.get("num_frames")),
                                  fps, color_shift=seed_of(wf) % 360)
            elif fn.endswith(".png"):
                Image.new("RGB", (8, 8), (255, 0, 0)).save(path)
            elif fn.endswith(".webp"):
                with open(path, "wb") as f:
                    f.write(open(os.path.join(HERE, "fixtures", "tiny.webp"), "rb").read())
            elif fn.endswith(".mov"):
                with open(path, "wb") as f:
                    f.write(open(os.path.join(HERE, "fixtures", "tiny.mov"), "rb").read())
            elif fn.endswith(".webm"):
                with open(path, "wb") as f:
                    f.write(open(os.path.join(HERE, "fixtures", "tiny.webm"), "rb").read())
            elif fn.endswith(".mkv"):
                with open(path, "wb") as f:
                    f.write(open(os.path.join(HERE, "fixtures", "tiny.mkv"), "rb").read())
            else:
                with open(path, "wb") as f:
                    f.write(b"fake-video-container")
            outputs[nid] = {"images": [{"filename": fn, "subfolder": sub, "type": "output"}], "animated": [True]}
        elif ct == "SaveGLB":
            fn = f"model_{pid[:8]}_00001_.glb"
            if seed_of(wf) == BAD_GLB_SEED:  # tests: a .glb that has the right header and nothing valid behind it
                with open(os.path.join(OUTPUT, fn), "wb") as f:
                    f.write(struct.pack("<4sII", b"glTF", 2, 64) + b"\x00" * 8)
            else:
                cube_glb(os.path.join(OUTPUT, fn), color=((seed_of(wf) % 7) / 7, .45, .75))
            outputs[nid] = {"3d": [{"filename": fn, "subfolder": sub, "type": "output"}]}
    return outputs


async def prompt(req):
    body = await req.json()
    wf = body.get("prompt")
    errs = validate(wf)
    if errs:
        if "error" in errs:
            return web.json_response(errs, status=400)
        return web.json_response({"error": {"message": "Prompt outputs failed validation", "details": ""}, "node_errors": errs}, status=400)
    pid = str(uuid.uuid4())
    LOG.append(wf)
    PENDING.add(pid)
    cid = body.get("client_id")
    blob = json.dumps(wf)

    async def job():
        try:
            await _contract_job(pid, cid, wf, blob)
        finally:
            PENDING.discard(pid)
    asyncio.ensure_future(job())
    return web.json_response({"prompt_id": pid, "number": len(LOG), "node_errors": {}})


async def _wait_ws(cid, tries=40):
    for _ in range(tries):
        ws = SOCKETS.get(cid)
        if ws is not None and not ws.closed:
            return ws
        await asyncio.sleep(0.05)
    return SOCKETS.get(cid)


async def _send_node_null(cid, pid):
    ws = await _wait_ws(cid)
    if ws is not None and not ws.closed:
        await ws.send_json({"type": "executing", "data": {"node": None, "prompt_id": pid}})


async def _contract_job(pid, cid, wf, blob):
    """Normal fake execution, plus a few prefixes the client-contract tests use.

    e2e_hold_job pauses the fake engine so the browser can refresh or cancel
    mid-job. It is not one of the client-contract cases below.

    es_contract_early_null sends executing.node=null before history exists.
    es_contract_null_only sends that event and never writes history.
    es_contract_nofile / es_contract_error / es_contract_not_completed write a
    terminal-looking history that is not a successful saved file.
    es_contract_slow does not finish within a short client timeout.
    """
    if "es_contract_early_null" in blob:
        await _send_node_null(cid, pid)
        await asyncio.sleep(0.6)
    if "es_contract_null_only" in blob:
        await _send_node_null(cid, pid)
        await asyncio.sleep(30)
        return
    if "es_contract_nofile" in blob:
        HISTORY[pid] = {"outputs": {}, "status": {"status_str": "success", "completed": True, "messages": []}}
        await _send_node_null(cid, pid)
        return
    if "es_contract_not_completed" in blob:
        HISTORY[pid] = {"outputs": {"1": {"images": [{"filename": "still.png", "subfolder": "", "type": "output"}]}},
                        "status": {"status_str": "success", "completed": False, "messages": []}}
        await _send_node_null(cid, pid)
        await asyncio.sleep(30)
        return
    if "es_contract_error" in blob:
        HISTORY[pid] = {"outputs": {"1": {"images": [{"filename": "clip.mp4", "subfolder": "", "type": "output"}],
                                          "animated": [True]}},
                        "status": {"status_str": "error", "completed": False,
                                   "messages": [["execution_error", {"node_type": "SaveVideo", "exception_message": "disk full"}]]}}
        await _send_node_null(cid, pid)
        return
    if "e2e_hold_job" in blob:
        for _ in range(80):
            if pid in HOLD_CANCELS:
                break
            await asyncio.sleep(0.1)
    if "es_contract_slow" in blob:
        await asyncio.sleep(30)
    ws = SOCKETS.get(cid)
    for i in range(1, 5):
        await asyncio.sleep(SLOW)
        if ws is not None and not ws.closed:
            await ws.send_json({"type": "progress", "data": {"value": i, "max": 4, "prompt_id": pid}})
    try:
        outputs = await asyncio.get_event_loop().run_in_executor(None, render, pid, wf)
        HISTORY[pid] = {"prompt": [0, pid, wf, {}, []], "outputs": outputs,
                        "status": {"status_str": "success", "completed": True, "messages": []}}
    except Exception as e:  # pragma: no cover
        HISTORY[pid] = {"outputs": {}, "status": {"status_str": "error", "completed": False,
                                                  "messages": [["execution_error", {"exception_message": repr(e)}]]}}
    ws = SOCKETS.get(cid)
    if ws is not None and not ws.closed:
        await ws.send_json({"type": "executing", "data": {"node": None, "prompt_id": pid}})


async def history(req):
    pid = req.match_info["pid"]
    HISTORY_HITS.append(pid)
    return web.json_response({pid: HISTORY[pid]} if pid in HISTORY else {})


async def view(req):
    fn = os.path.basename(req.query["filename"])
    folder = OUTPUT if req.query.get("type", "output") == "output" else INPUT
    p = os.path.join(folder, fn)
    if not os.path.exists(p):
        return web.Response(status=404)
    return web.FileResponse(p)


async def ws_handler(req):
    ws = web.WebSocketResponse()
    await ws.prepare(req)
    SOCKETS[req.query.get("clientId")] = ws
    await ws.send_json({"type": "status", "data": {"status": {"exec_info": {"queue_remaining": 0}}}})
    async for _ in ws:
        pass
    return ws


async def interrupt(req):
    """Global interrupt. The Easy Studio client must not call this to cancel one job."""
    INTERRUPTS.append(req.path)
    return web.json_response({})


async def cancel_job(req):
    """POST /api/jobs/{job_id}/cancel, as on ComfyUI 0.43.0.

    A finished or unknown id is a no-op ({"cancelled": false}). This route does
    not call the global interrupt handler.
    """
    pid = req.match_info["job_id"]
    CANCELS.append(f"/api/jobs/{pid}/cancel")
    HOLD_CANCELS.add(pid)
    row = HISTORY.get(pid) or {}
    st = row.get("status") or {}
    if pid not in PENDING and pid not in HISTORY:
        return web.json_response({"cancelled": False})
    if st.get("completed") is True or st.get("status_str") in ("success", "error"):
        return web.json_response({"cancelled": False})
    return web.json_response({"cancelled": True})


FREED = []


async def free(req):
    FREED.append(await req.json())
    return web.json_response({})


async def log(_):
    return web.json_response(LOG)


async def control(_):
    return web.json_response({"cancels": list(CANCELS), "interrupts": list(INTERRUPTS),
                              "prompts": len(LOG), "history_reads": list(HISTORY_HITS), "frees": len(FREED)})


def make_app():
    app = web.Application(client_max_size=1024 ** 3)
    routes = [web.get("/system_stats", system_stats), web.get("/object_info", object_info),
              web.get("/object_info/{n}", object_info), web.post("/upload/image", upload),
              web.post("/prompt", prompt), web.get("/history/{pid}", history), web.get("/view", view),
              web.get("/ws", ws_handler), web.post("/interrupt", interrupt), web.post("/free", free),
              web.get("/mock/log", log), web.get("/mock/control", control)]
    if os.environ.get("MOCK_NO_CANCEL") != "1":
        routes.append(web.post("/api/jobs/{job_id}/cancel", cancel_job))
    app.add_routes(routes)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8191, print=None)
