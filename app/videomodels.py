"""The Video studio's model list. Every entry is a workflow file; the controls are found by
wfdetect.py (the same code that reads "bring your own" workflows), so all models get the same
simple screen: prompt, start / end picture, seconds, size, seed, fast mode.

Licences (checked Nov 2026): Wan 2.2 Apache-2.0; Kandinsky 5 MIT; LTX-2.x community licence (free
under $10M yearly revenue, files gated behind a Hugging Face login); HunyuanVideo 1.5 Tencent
licence -- NOT valid in the EU, UK or South Korea. MiniMax-H3 / FastH3 are left out on purpose:
their licence excludes the USA, EU, UK and South Korea.
"""
import json
import os
import re

import wfdetect as D

HERE = os.path.dirname(os.path.abspath(__file__))

# id, label, family, mode, workflow, fps, frame rule (4n+1 or 8n+1), sizes {quality: (w,h) for 16:9},
# max seconds, group, note
MODELS = [
    dict(id="wan22_i2v", label="Wan 2.2 14B -- picture to video", family="Wan 2.2", mode="i2v",
         wf={"fast": "video_wan22_i2v_fast_api.json", "best": "video_wan22_i2v_quality_api.json"},
         fps=16, rule=4, base=(832, 480), hi=(1280, 720), max_s=10, group="video",
         note="The default. Best motion and faces. 'Fast' uses a 4-step speed-up LoRA."),
    dict(id="wan22_flf2v", label="Wan 2.2 14B -- A to B (start + end picture)", family="Wan 2.2", mode="flf2v",
         wf={"fast": "video_wan22_flf2v_fast_api.json", "best": "video_wan22_flf2v_quality_api.json"},
         fps=16, rule=4, base=(832, 480), hi=(1280, 720), max_s=10, group="video",
         note="Moves from your first picture to your last picture."),
    dict(id="wan22_t2v", label="Wan 2.2 14B -- text to video", family="Wan 2.2", mode="t2v",
         wf={"any": "vm_wan22_t2v_api.json"}, fps=16, rule=4, base=(832, 480), hi=(1280, 720), max_s=10,
         group="video-t2v", note="No picture needed. 'Fast' switches on the 4-step Lightning LoRA."),
    dict(id="wan22_5b_t2v", label="Wan 2.2 5B -- text to video (small, 24 fps)", family="Wan 2.2 5B", mode="t2v",
         wf={"any": "vm_wan22_5b_t2v_api.json"}, fps=24, rule=4, base=(1280, 704), hi=(1280, 704), max_s=5,
         group="video-wan5b", note="Smaller and quicker than 14B; good for drafts."),
    dict(id="wan22_5b_i2v", label="Wan 2.2 5B -- picture to video (small, 24 fps)", family="Wan 2.2 5B", mode="i2v",
         wf={"any": "vm_wan22_5b_i2v_api.json"}, fps=24, rule=4, base=(1280, 704), hi=(1280, 704), max_s=5,
         group="video-wan5b", note="Smaller and quicker than 14B."),
    dict(id="ltx25_t2v", label="LTX-2.5 -- text to video WITH sound", family="LTX-2.5", mode="t2v",
         wf={"any": "vm_ltx25_t2v_api.json"}, fps=24, rule=8, base=(1280, 704), hi=(1920, 1088), max_s=10,
         group="video-ltx", note="Makes matching sound. Files need a free Hugging Face login."),
    dict(id="ltx25_i2v", label="LTX-2.5 -- picture to video WITH sound", family="LTX-2.5", mode="i2v",
         wf={"any": "vm_ltx25_i2v_api.json"}, fps=24, rule=8, base=(1280, 704), hi=(1920, 1088), max_s=10,
         group="video-ltx", note="Makes matching sound."),
    dict(id="ltx25_flf2v", label="LTX-2.5 -- A to B WITH sound", family="LTX-2.5", mode="flf2v",
         wf={"any": "vm_ltx25_flf2v_api.json"}, fps=24, rule=8, base=(1280, 704), hi=(1920, 1088), max_s=10,
         group="video-ltx", note="Start + end picture, with sound."),
    dict(id="hunyuan15_t2v", label="HunyuanVideo 1.5 -- text to video (720p)", family="HunyuanVideo 1.5", mode="t2v",
         wf={"any": "vm_hunyuan15_t2v_api.json"}, fps=24, rule=4, base=(1280, 720), hi=(1280, 720), max_s=5,
         group="video-hunyuan", note="Strong realism. Licence not valid in the EU, UK or South Korea."),
    dict(id="hunyuan15_i2v", label="HunyuanVideo 1.5 -- picture to video (720p)", family="HunyuanVideo 1.5", mode="i2v",
         wf={"any": "vm_hunyuan15_i2v_api.json"}, fps=24, rule=4, base=(1280, 720), hi=(1280, 720), max_s=5,
         group="video-hunyuan", note="Licence not valid in the EU, UK or South Korea."),
    dict(id="kandinsky5_t2v", label="Kandinsky 5 Lite -- text to video", family="Kandinsky 5", mode="t2v",
         wf={"any": "vm_kandinsky5_t2v_api.json"}, fps=24, rule=4, base=(768, 512), hi=(768, 512), max_s=5,
         group="video-kandinsky", note="Small (2B), MIT licence."),
    dict(id="kandinsky5_i2v", label="Kandinsky 5 Lite -- picture to video", family="Kandinsky 5", mode="i2v",
         wf={"any": "vm_kandinsky5_i2v_api.json"}, fps=24, rule=4, base=(768, 512), hi=(768, 512), max_s=5,
         group="video-kandinsky", note="Small (2B), MIT licence."),
]
BY_ID = {m["id"]: m for m in MODELS}


def workflow_file(m, quality="fast"):
    return m["wf"].get("any") or m["wf"].get("best" if quality == "best" else "fast")


def size_for(m, img_size=None, quality="fast", aspect=None):
    """Width/height for this model: keep the picture's shape (or the chosen aspect), the model's pixel budget,
    multiples of 32 (16 for Wan)."""
    bw, bh = m["hi"] if quality == "best" else m["base"]
    budget = bw * bh
    if img_size:
        w, h = img_size
    else:
        w, h = {"wide": (16, 9), "tall": (9, 16), "square": (1, 1), "portrait": (2, 3)}.get(aspect or "wide", (16, 9))
    r = w / float(h)
    W = (budget * r) ** 0.5
    H = W / r
    mult = 16 if m["family"].startswith("Wan 2.2") and "5B" not in m["family"] else 32
    return max(mult * 8, int(W // mult * mult)), max(mult * 8, int(H // mult * mult))


def model_files(wf):
    """Model file names a workflow loads (for readiness)."""
    keys = ("unet_name", "clip_name", "clip_name1", "clip_name2", "vae_name", "ckpt_name", "lora_name", "model_name", "name")
    out = []
    for n in wf.values():
        if re.search(r"Loader", n["class_type"]):
            for k in keys:
                v = n.get("inputs", {}).get(k)
                if isinstance(v, str) and v.endswith((".safetensors", ".pt", ".pth", ".ckpt", ".bin", ".gguf")):
                    out.append(os.path.basename(v))
    return sorted(set(out))


def load(name):
    with open(os.path.join(HERE, "workflows", name), encoding="utf-8") as f:
        return json.load(f)


def public(files=None):
    """The list the web page shows (with installed / not installed)."""
    out = []
    for m in MODELS:
        need = sorted({x for q in m["wf"].values() for x in model_files(load(q))})
        missing = [x for x in need if files is not None and x not in files]
        out.append({k: m[k] for k in ("id", "label", "family", "mode", "fps", "max_s", "group", "note")} |
                   {"ready": files is not None and not missing, "missing": missing,
                    "fast_switch": bool(D.analyse(load(workflow_file(m)))["fast"]) or len(m["wf"]) > 1})
    return out
