"""Auto-detect the simple controls of ANY ComfyUI video (or image) workflow.

Used for the built-in video models AND for "Bring your own workflow". Given an API-format
workflow it finds: the positive / negative prompt, the start / end pictures, seed, length
(seconds or frames), frames-per-second, width / height, a "fast mode" switch, and the outputs.
Then fill() writes the user's simple choices into a copy of the workflow.

Rules (in order): node titles ("Prompt", "Width", "Duration", "START IMAGE" ...), then input names
traced through the graph (a text encoder whose output reaches an input called "negative" is the
negative prompt), then node order. Values that come from a Primitive node are set on the primitive.
"""
import copy
import re

PRIMITIVES = {"PrimitiveInt", "PrimitiveFloat", "PrimitiveString", "PrimitiveStringMultiline", "PrimitiveBoolean",
              "Int", "Float", "String", "Primitive int [Crystools]", "easy int", "easy float", "easy string"}
TEXT_KEYS = ("text", "prompt", "positive_prompt", "text_g", "text_l", "caption")
IMAGE_LOADERS = {"LoadImage"}
OTHER_FILE_LOADERS = {"LoadImageMask", "LoadImageOutput", "LoadVideo", "VHS_LoadVideo", "VHS_LoadVideoPath", "LoadAudio",
                      "VHS_LoadAudio", "VHS_LoadImagePath", "LoadImageFromUrl", "LoadImagesFromFolder", "LoadImageSetFromFolderNode",
                      "LoadImageTextSetFromFolderNode", "LoadImageDataSetFromFolder", "Load3D", "LoadImageFromPath"}
VIDEO_OUTPUTS = {"SaveVideo", "SaveWEBM", "SaveAnimatedWEBP", "SaveAnimatedPNG", "VHS_VideoCombine"}
IMAGE_OUTPUTS = {"SaveImage"}
FRAME_KEYS = ("length", "num_frames", "video_length", "frames", "frame_count", "num_frame")
FPS_KEYS = ("fps", "frame_rate")
SEED_KEYS = ("seed", "noise_seed")


def _title(n):
    return str((n.get("_meta") or {}).get("title") or "")


def _is_link(v):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def consumers(wf):
    out = {}
    for nid, n in wf.items():
        for k, v in (n.get("inputs") or {}).items():
            if _is_link(v):
                out.setdefault(v[0], []).append((nid, k))
    return out


def _resolve(wf, nid, key):
    """Where the value of wf[nid].inputs[key] really lives: (node, key, how).
    how = 'const' (plain value), 'primitive' (set the primitive), 'computed' (comes from another node)."""
    v = wf[nid]["inputs"].get(key)
    if _is_link(v):
        src = wf.get(v[0])
        if src and src["class_type"] in PRIMITIVES:
            sv = src["inputs"].get("value")
            if _is_link(sv):
                return v[0], "value", "computed"
            return v[0], "value", "primitive"
        return nid, key, "computed"
    return nid, key, "const"


def _downstream_role(wf, cons, nid, depth=0, seen=None):
    """'positive' / 'negative' / None for a conditioning node, by the input names it reaches."""
    seen = seen or set()
    if depth > 8 or nid in seen:
        return None
    seen.add(nid)
    for c, k in cons.get(nid, []):
        kl = k.lower()
        if "negative" in kl or kl in ("uncond", "unconditional"):
            return "negative"
        if "positive" in kl or kl in ("conditioning", "cond"):
            if kl in ("conditioning", "cond") and wf[c]["class_type"] in ("BasicGuider",):
                return "positive"
            if "positive" in kl:
                return "positive"
        r = _downstream_role(wf, cons, c, depth + 1, seen)
        if r:
            return r
    return None


def analyse(wf):
    if not isinstance(wf, dict):
        raise ValueError("Not a workflow.")
    cons = consumers(wf)
    a = {"prompt": [], "negative": [], "images": [], "seed": [], "frames": [], "seconds": [], "fps": [],
         "width": [], "height": [], "fast": None, "enhancer": [], "outputs": [], "other_loaders": [], "warnings": []}
    ids = sorted(wf, key=lambda x: (len(x), x))
    # -- outputs
    for nid in ids:
        ct = wf[nid]["class_type"]
        if ct in VIDEO_OUTPUTS or ct in IMAGE_OUTPUTS:
            a["outputs"].append(nid)
        if ct in OTHER_FILE_LOADERS:
            a["other_loaders"].append(nid)
    a["output_type"] = "video" if any(wf[o]["class_type"] in VIDEO_OUTPUTS for o in a["outputs"]) else (
        "image" if a["outputs"] else "none")
    # -- prompts: text-encoder style nodes (have a text-ish input and their output is conditioning)
    for nid in ids:
        n = wf[nid]
        ct, ins = n["class_type"], n.get("inputs") or {}
        if ct in PRIMITIVES or ct.startswith("TextGenerate"):
            continue
        tk = next((k for k in TEXT_KEYS if k in ins), None)
        if not tk:
            continue
        if not re.search(r"(TextEncode|Conditioning|Encode|Prompt)", ct, re.I) and not cons.get(nid):
            continue
        tn, tkey, how = _resolve(wf, nid, tk)
        if how == "computed":
            src = wf[ins[tk][0]]
            if src["class_type"] == "ComfySwitchNode":  # prompt-enhancer switch: always use the user's own words
                a["enhancer"].append(ins[tk][0])
                raw = src["inputs"].get("on_false")
                if _is_link(raw) and wf.get(raw[0], {}).get("class_type") in PRIMITIVES:
                    tn, tkey, how = raw[0], "value", "primitive"
        if how == "computed":
            a["warnings"].append(f"Prompt of node {nid} is computed by another node; left as is.")
            continue
        t = (_title(n) + " " + _title(wf[tn])).lower()
        role = "negative" if "negative" in t else ("positive" if re.search(r"positive|\bprompt\b", t) else None)
        role = role or _downstream_role(wf, cons, nid) or "positive"
        a["prompt" if role == "positive" else "negative"].append((tn, tkey))
    for k in ("prompt", "negative"):
        a[k] = list(dict.fromkeys(a[k]))
    # -- pictures
    loads = [nid for nid in ids if wf[nid]["class_type"] in IMAGE_LOADERS]
    def img_role(nid):
        t = _title(wf[nid]).lower()
        if re.search(r"\b(end|last|final)\b", t):
            return "end"
        if re.search(r"\b(start|first|begin)", t):
            return "start"
        for c, k in cons.get(nid, []):
            kl = k.lower()
            if "end" in kl or "last" in kl:
                return "end"
            if "start" in kl or "first" in kl:
                return "start"
        return None
    roles = {nid: img_role(nid) for nid in loads}
    for nid in loads:
        if roles[nid] is None:
            roles[nid] = "start" if "start" not in roles.values() else ("end" if "end" not in roles.values() else "extra")
    a["images"] = [{"node": nid, "role": roles[nid]} for nid in loads]
    # -- numbers
    seen = set()
    def add(kind, nid, key):
        r = _resolve(wf, nid, key)
        if wf[nid]["class_type"] in PRIMITIVES and r[2] == "computed":
            r = (nid, key, "override")  # a titled primitive fed by a helper: we can replace it with a number
        if r[2] == "computed" and kind in ("seed", "width", "height"):
            return
        sig = (kind, r[0], r[1])
        if sig not in seen:
            seen.add(sig)
            a[kind].append({"node": r[0], "key": r[1], "how": r[2], "via": nid})
    for nid in ids:
        n = wf[nid]
        ct, ins, t = n["class_type"], n.get("inputs") or {}, _title(n).lower()
        if ct in PRIMITIVES:
            if re.search(r"duration|seconds|\blength \(s\)", t):
                add("seconds", nid, "value")
            elif re.search(r"frame ?rate|\bfps\b", t):
                add("fps", nid, "value")
            elif ct == "PrimitiveBoolean" and re.search(r"lightning|turbo|fast|distill", t):
                a["fast"] = {"node": nid, "key": "value"}
            elif ct == "PrimitiveBoolean" and re.search(r"enhanc", t):
                a["enhancer"].append(nid)
            elif re.fullmatch(r"\s*width\s*", t):
                add("width", nid, "value")
            elif re.fullmatch(r"\s*height\s*", t):
                add("height", nid, "value")
            continue
        for k in SEED_KEYS:
            if k in ins and not isinstance(ins[k], (str, bool)):
                add("seed", nid, k)
        if ct.startswith(("TextGenerate",)):
            continue
        for k in FRAME_KEYS:
            if k in ins and not isinstance(ins[k], (str, bool, float)):
                add("frames", nid, k)
        for k in FPS_KEYS:
            if k in ins and not isinstance(ins[k], str):
                add("fps", nid, k)
        if ct in ("ResolutionSelector", "GetImageSize"):
            continue
        for k in ("width", "height"):
            if k in ins and not isinstance(ins[k], (str, bool)):
                add(k, nid, k)
    # frames that are computed from a duration primitive are covered by "seconds"
    if a["seconds"]:
        a["frames"] = [f for f in a["frames"] if f["how"] != "computed"]
    imgs = [i for i in a["images"] if i["role"] in ("start", "end")]
    a["mode"] = ("flf2v" if any(i["role"] == "end" for i in imgs) and len(imgs) >= 2 else
                 "i2v" if imgs else "t2v")
    if any(i["role"] == "extra" for i in a["images"]):
        a["warnings"].append("This workflow loads more than two pictures; Easy Studio fills only the first two.")
    return a


def summary(a):
    """Plain-language list of what was found (shown under an imported workflow)."""
    out = []
    out.append("Prompt box: found" if a["prompt"] else "Prompt box: NOT found")
    out.append("Negative prompt: found" if a["negative"] else "Negative prompt: none")
    roles = [i["role"] for i in a["images"]]
    out.append({"t2v": "Pictures: none (text to video)", "i2v": "Pictures: 1 (start picture)",
                "flf2v": "Pictures: 2 (start and end)"}[a["mode"]])
    out.append("Length: seconds" if a["seconds"] else ("Length: frames" if a["frames"] else "Length: fixed"))
    out.append("Size: adjustable" if any(r["how"] != "computed" for r in a["width"]) else "Size: fixed by the workflow")
    out.append("Seed: found" if a["seed"] else "Seed: none")
    if a["fast"]:
        out.append("Fast mode switch: found")
    out.append(f"Result: {a['output_type']}")
    return out + [w for w in a["warnings"]]


def _set(wf, ref, value):
    wf[ref["node"]]["inputs"][ref["key"]] = value


def frames_for(seconds, fps, rule=4):
    """Most video models want 4n+1 (Wan, Hunyuan) or 8n+1 (LTX) frames."""
    n = max(1, int(round(seconds * fps / rule)))
    return n * rule + 1


def fill(wf, a, prompt=None, negative=None, images=None, seed=None, seconds=None, fps=None, width=None, height=None,
         fast=None, frame_rule=4):
    wf = copy.deepcopy(wf)
    if prompt is not None:
        for nid, k in a["prompt"]:
            wf[nid]["inputs"][k] = prompt
    if negative is not None:
        for nid, k in a["negative"]:
            wf[nid]["inputs"][k] = negative
    for nid in a["enhancer"]:  # prompt enhancers rewrite the user's words: always off
        n = wf.get(nid)
        if n and n["class_type"] == "PrimitiveBoolean":
            n["inputs"]["value"] = False
        elif n and n["class_type"] == "ComfySwitchNode":
            n["inputs"]["switch"] = False
    for im in a["images"]:
        name = (images or {}).get(im["role"])
        if name:
            wf[im["node"]]["inputs"]["image"] = name
    if seed is not None:
        for r in a["seed"]:
            _set(wf, r, int(seed) % (2**53))
    eff_fps = fps
    if eff_fps is None:
        for r in a["fps"]:
            if r["how"] in ("const", "primitive"):
                v = wf[r["node"]]["inputs"].get(r["key"])
                if isinstance(v, (int, float)):
                    eff_fps = v
                    break
    if fps is not None:
        for r in a["fps"]:
            if r["how"] != "computed":
                cur = wf[r["node"]]["inputs"].get(r["key"])
                _set(wf, r, int(fps) if isinstance(cur, int) and not isinstance(cur, bool) else float(fps))
    if seconds is not None:
        if a["seconds"]:
            for r in [x for x in a["seconds"] if x["how"] != "computed"]:
                cur = wf[r["node"]]["inputs"].get(r["key"])
                _set(wf, r, int(round(seconds)) if isinstance(cur, int) else float(seconds))
        elif a["frames"]:
            n = frames_for(seconds, eff_fps or 16, frame_rule)
            for r in a["frames"]:
                if r["how"] != "computed":
                    _set(wf, r, n)
    for key, val in (("width", width), ("height", height)):
        if val is not None:
            for r in a[key]:
                if r["how"] != "computed":
                    _set(wf, r, int(val))
    if fast is not None and a["fast"]:
        _set(wf, a["fast"], bool(fast))
    return prune(wf, a["outputs"])


def prune(wf, keep):
    """Drop nodes no output needs (preview nodes, unused helpers) and strip _meta."""
    if not keep:
        return wf
    need, stack = set(), list(keep)
    while stack:
        i = stack.pop()
        if i in need or i not in wf:
            continue
        need.add(i)
        for v in (wf[i].get("inputs") or {}).values():
            if _is_link(v):
                stack.append(v[0])
    return {k: v for k, v in wf.items() if k in need}
