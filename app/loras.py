"""LoRA library: the add-on style / character files in ComfyUI/models/loras.

For every .safetensors file it reads the small text header (no need to load the weights) to find:
  * which base model it was made for (SDXL/NoobAI, Chroma/Flux, Z-Image, Qwen-Image, Wan 2.2 14B/5B, LTX-2,
    HunyuanVideo) -- from the metadata the trainer wrote, or else from the layer names inside;
  * trigger words (kohya tag list, ai-toolkit / modelspec trigger, Civitai "trained words");
  * a preview picture next to the file (name.png / name.preview.png / .jpg / .webp).
Easy Studio's own notes live in a sidecar  name.es.json  (trigger, default strength, source, area).

Safety: a LoRA whose file name, metadata or trigger words point at a child / minor, a real named person
(celebrity, "lookalike", Civitai "person of interest") or face-swap is listed as BLOCKED and can't be used.
Only .safetensors files are accepted (the older .pt/.ckpt formats can run hidden code).
"""
import hashlib
import json
import os
import re
import struct
import threading
import time

import requests

import safety

FAMILIES = {
    "sdxl": "SDXL / NoobAI / Illustrious / Pony (anime pictures)",
    "flux": "Chroma / Flux (realistic pictures)",
    "zimage": "Z-Image (fast pictures)",
    "qwen_image": "Qwen-Image (edits)",
    "wan14b": "Wan 2.1 / 2.2 14B (video)",
    "wan5b": "Wan 2.2 5B (video)",
    "ltx2": "LTX-2 / 2.5 (video)",
    "hunyuan_video": "HunyuanVideo (video)",
    "kandinsky5": "Kandinsky 5 (video)",
    "unknown": "Unknown base model",
}
# which family each Easy Studio model file belongs to (by its main model file name)
MODEL_FAMILY_RULES = [
    (r"noobai|illustrious|sdxl|pony", "sdxl"), (r"chroma|flux", "flux"), (r"z_image|zimage", "zimage"),
    (r"qwen_image|qwen-image", "qwen_image"), (r"wan2\.2_ti2v_5b|wan2\.2_5b", "wan5b"), (r"wan2\.[12].*14b|wan2\.[12]_(i2v|t2v)", "wan14b"),
    (r"ltx", "ltx2"), (r"hunyuanvideo|hunyuan_video", "hunyuan_video"), (r"kandinsky5", "kandinsky5"),
]
CIVITAI_BASE = [
    (r"sdxl|illustrious|noob|pony", "sdxl"), (r"flux|chroma", "flux"), (r"z\s*-?image", "zimage"), (r"qwen", "qwen_image"),
    (r"wan.*(5b)", "wan5b"), (r"wan", "wan14b"), (r"ltx", "ltx2"), (r"hunyuan\s*video", "hunyuan_video"), (r"kandinsky", "kandinsky5"),
]
PREVIEW_EXT = (".preview.png", ".png", ".preview.jpg", ".jpg", ".jpeg", ".webp", ".preview.webp")
MAX_HEADER = 100 * 1024 * 1024


def read_header(path):
    """The JSON header of a .safetensors file: (metadata dict, {tensor name: shape})."""
    with open(path, "rb") as f:
        raw = f.read(8)
        if len(raw) < 8:
            raise ValueError("Not a .safetensors file (too short).")
        n = struct.unpack("<Q", raw)[0]
        if n <= 1 or n > MAX_HEADER:
            raise ValueError("Not a .safetensors file.")
        try:
            h = json.loads(f.read(n).decode("utf-8"))
        except Exception:
            raise ValueError("Not a .safetensors file (bad header).")
    if not isinstance(h, dict):
        raise ValueError("Not a .safetensors file.")
    meta = h.pop("__metadata__", {}) or {}
    shapes = {k: v.get("shape") for k, v in h.items() if isinstance(v, dict)}
    return {str(k): str(v) for k, v in meta.items()}, shapes


def family_of_model_file(name):
    n = (name or "").lower()
    for rx, fam in MODEL_FAMILY_RULES:
        if re.search(rx, n):
            return fam
    return "unknown"


def detect_family(meta, shapes):
    m = {k.lower(): str(v).lower() for k, v in (meta or {}).items()}
    hint = " ".join(m.get(k, "") for k in ("es_base", "ss_base_model_version", "modelspec.architecture", "ss_sd_model_name",
                                             "base_model", "ss_network_module", "modelspec.implementation"))
    if m.get("es_base") in FAMILIES:
        return m["es_base"]
    for rx, fam in [(r"sdxl|stable-diffusion-xl|illustrious|noob|pony", "sdxl"), (r"chroma|flux", "flux"),
                    (r"z[-_]?image|zimage|lumina", "zimage"), (r"qwen[-_]?image", "qwen_image"),
                    (r"wan.?2\.2.*5b|wan22_5b", "wan5b"), (r"wan", "wan14b"), (r"ltx", "ltx2"),
                    (r"hunyuan.?video", "hunyuan_video"), (r"kandinsky", "kandinsky5")]:
        if re.search(rx, hint):
            return fam
    keys = list(shapes or {})
    ks = " ".join(keys[:4000]).lower()
    if "lora_te2_" in ks or ("input_blocks" in ks and "lora_unet" in ks) or "down_blocks" in ks and "add_embedding" in ks:
        return "sdxl"
    if re.search(r"img_attn_qkv|txt_attn_qkv|byt5|individual_token_refiner", ks):
        return "hunyuan_video"
    if re.search(r"double_blocks|single_blocks|single_transformer_blocks", ks):
        return "flux"
    if re.search(r"context_refiner|noise_refiner", ks):
        return "zimage"
    if re.search(r"img_mod|txt_mlp|img_mlp", ks):
        return "qwen_image"
    if re.search(r"audio_attn|audio_ff|av_ca|scale_shift_table", ks) or ("transformer_blocks" in ks and "attn2" in ks):
        return "ltx2"
    if re.search(r"blocks\.\d+\.(cross_attn|self_attn|ffn)", ks):
        dim = 0
        for k, s in shapes.items():
            if re.search(r"self_attn\.q.*(lora_down|lora_a|lora\.down)", k.lower()) and s and len(s) == 2:
                dim = s[1]
                break
        return "wan5b" if dim == 3072 else "wan14b"
    return "unknown"


def triggers_from(meta):
    m = meta or {}
    out = []
    for k in ("es_trigger", "modelspec.trigger_phrase", "trigger_word", "ss_trigger", "trained_words"):
        if m.get(k):
            out += [t.strip() for t in re.split(r"[,;\n]", str(m[k])) if t.strip()]
    tf = m.get("ss_tag_frequency")
    if tf and len(out) < 3:
        try:
            d = json.loads(tf)
            counts = {}
            for sub in d.values():
                for t, c in sub.items():
                    counts[t.strip()] = counts.get(t.strip(), 0) + int(c)
            out += [t for t, _ in sorted(counts.items(), key=lambda x: -x[1])[:3]]
        except Exception:
            pass
    return list(dict.fromkeys(t for t in out if 0 < len(t) < 80))[:6]


LIKENESS_GUARD = None    # set by the owner routes: path -> why this LoRA may not load now, or ""
LIKENESS_ALLOWED = None  # path -> True when it is the running likeness job's own LoRA


class LoraLibrary:
    def __init__(self, comfy_dir):
        self.dir = os.path.join(comfy_dir, "models", "loras") if comfy_dir else None
        self.lock = threading.Lock()
        self.cache = {}  # path -> (mtime, record)
        self.downloads = {}

    def available(self):
        return bool(self.dir) and os.path.isdir(self.dir)

    def _sidecar(self, path):
        p = os.path.splitext(path)[0] + ".es.json"
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}

    def write_sidecar(self, name, **changes):
        path = self.path_of(name)
        side = self._sidecar(path)
        side.update({k: v for k, v in changes.items() if v is not None})
        with open(os.path.splitext(path)[0] + ".es.json", "w", encoding="utf-8") as f:
            json.dump(side, f, indent=1)
        self.cache.pop(path, None)
        return side

    def path_of(self, name):
        if not self.available():
            raise ValueError("The LoRA folder isn't on this PC (set COMFY_DIR).")
        name = str(name).replace("\\", "/")
        if ".." in name.split("/") or name.startswith("/") or not name.lower().endswith(".safetensors"):
            raise ValueError("Not a LoRA file name.")
        p = os.path.abspath(os.path.join(self.dir, name))
        if not p.startswith(os.path.abspath(self.dir) + os.sep):
            raise ValueError("Not a LoRA file name.")
        return p

    def record(self, path):
        st = os.stat(path)
        c = self.cache.get(path)
        side = self._sidecar(path)
        side_key = json.dumps(side, sort_keys=True) + "|" + ",".join(e for e in PREVIEW_EXT if os.path.exists(os.path.splitext(path)[0] + e))
        if c and c[0] == (st.st_mtime, side_key):
            return c[1]
        name = os.path.relpath(path, self.dir).replace(os.sep, "/")
        rec = {"name": name, "title": side.get("title") or os.path.splitext(os.path.basename(name))[0].replace("_", " "),
               "size_mb": round(st.st_size / 1e6, 1), "added": st.st_mtime}
        try:
            meta, shapes = read_header(path)
        except Exception as e:
            meta, shapes = {}, {}
            rec["error"] = str(e)
        fam = side.get("base") if side.get("base") in FAMILIES else detect_family(meta, shapes)
        if "trigger_words" in side:
            trig = [str(t).strip() for t in (side.get("trigger_words") or []) if str(t).strip()]
        else:
            trig = triggers_from(meta)
        ok, why = safety.check_lora(name, {**meta, **({"poi": side["poi"]} if "poi" in side else {})}, trig)
        if ok and side.get("title"):
            ok, why = safety.check_lora(side["title"])
        known_strength = "strength" in side and side.get("strength") is not None
        rec.update(family=fam, family_label=FAMILIES[fam], trigger_words=trig,
                   strength=float(side["strength"]) if known_strength else None, strength_known=known_strength,
                   source=side.get("source") or ("Easy Studio" if meta.get("es_trigger") else "file"),
                   character=side.get("character"), area=side.get("area") or "default", pair=side.get("pair"),
                   civitai=side.get("civitai"), blocked=not ok, blocked_reason=why if not ok else "",
                   identity=side.get("identity") or "",
                   player_only=bool(side.get("player_only") or side.get("identity") == "player_me"),
                   usage=side.get("usage") if isinstance(side.get("usage"), dict) else {},
                   thumb=None)
        base = os.path.splitext(path)[0]
        for ext in PREVIEW_EXT:
            if os.path.exists(base + ext):
                rec["thumb"] = os.path.relpath(base + ext, self.dir).replace(os.sep, "/")
                break
        self.cache[path] = ((st.st_mtime, side_key), rec)
        return rec

    def scan(self):
        if not self.available():
            return []
        out = []
        for root, dirs, files in os.walk(self.dir):
            dirs[:] = [d for d in dirs if d != "_trash" and not d.startswith(".")]
            for f in files:
                if f.lower().endswith(".safetensors"):
                    try:
                        out.append(self.record(os.path.join(root, f)))
                    except OSError:
                        pass
        return sorted(out, key=lambda r: -r["added"])

    def get(self, name):
        return self.record(self.path_of(name))

    def check_usable(self, name, model_family=None, area="default"):
        """Raise ValueError with a plain message if this LoRA can't be used here."""
        if not self.available():
            ok, why = safety.check_lora(name)
            if not ok:
                raise ValueError(why)
            return None
        p = self.path_of(name)
        if LIKENESS_GUARD is not None and os.path.exists(p):
            # The owner's likeness is locked by the file's SHA-256, whatever its name, folder or sidecar says.
            why = LIKENESS_GUARD(p)
            if why:
                raise ValueError(why)
            if LIKENESS_ALLOWED is not None and LIKENESS_ALLOWED(p):
                return {"pair": None, "owner_likeness": True}  # the likeness job's own LoRA; the registry holds its base
        if not os.path.exists(p):  # e.g. in a folder ComfyUI reads via extra_model_paths: name rules only
            ok, why = safety.check_lora(name)
            if not ok:
                raise ValueError(why)
            return None
        r = self.record(p)
        if r["blocked"]:
            raise ValueError(r["blocked_reason"])
        if r.get("player_only") or r.get("identity") == "player_me":
            raise ValueError("This LoRA is the player, Andrew. It is not an NPC, and it is not used to make pictures of anyone else.")
        if r["area"] == "adult" and area != "adult":
            raise ValueError(f"LoRA '{r['title']}' is kept in the 18+ section; use it there.")
        if model_family and r["family"] not in ("unknown", model_family) and not (
                {r["family"], model_family} <= {"wan14b"}):
            raise ValueError(f"LoRA '{r['title']}' was made for {FAMILIES[r['family']]}, so it won't work with "
                             f"{FAMILIES.get(model_family, model_family)}. Pick a matching LoRA or another model.")
        return r

    # ---- adding files ----
    def add_file(self, tmp_path, filename, **side):
        if not self.available():
            raise ValueError("The LoRA folder isn't on this PC (set COMFY_DIR).")
        if not filename.lower().endswith(".safetensors"):
            raise ValueError("Only .safetensors LoRA files can be added (other formats can hide code).")
        meta, shapes = read_header(tmp_path)
        if not shapes or not any(re.search(r"lora|lokr|loha|\.alpha$|\.diff(_b)?$", k, re.I) for k in list(shapes)[:2000]):
            raise ValueError("That .safetensors file doesn't look like a LoRA (no LoRA layers inside).")
        trig = side.get("trigger_words") or triggers_from(meta)
        ok, why = safety.check_lora(filename, {**meta, **({"poi": side.get("poi")} if side.get("poi") else {})}, trig)
        if not ok:
            raise ValueError(why)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(filename))[-120:]
        d = os.path.join(self.dir, "easy_studio")
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, safe)
        root, ext = os.path.splitext(dst)
        i = 2
        while os.path.exists(dst):
            dst = f"{root}_{i}{ext}"
            i += 1
        os.replace(tmp_path, dst) if os.path.dirname(os.path.abspath(tmp_path)) == d else _move(tmp_path, dst)
        name = os.path.relpath(dst, self.dir).replace(os.sep, "/")
        if side:
            self.write_sidecar(name, **side)
        return self.get(name)

    def delete(self, name):
        p = self.path_of(name)
        trash = os.path.join(self.dir, "_trash")
        os.makedirs(trash, exist_ok=True)
        base = os.path.splitext(p)[0]
        for ext in (".safetensors", ".es.json") + PREVIEW_EXT:
            if os.path.exists(base + ext):
                _move(base + ext, os.path.join(trash, os.path.basename(base + ext)))
        self.cache.pop(p, None)


def _move(a, b):
    import shutil
    shutil.move(a, b)


# ---------------------------------------------------------------------------
# Civitai import (public REST API: https://github.com/civitai/civitai/wiki/REST-API-Reference)
# ---------------------------------------------------------------------------
CIVITAI_BAD_TAGS = re.compile(r"\b(celebrit\w*|real\s*person|real\s*people|actress|actor|influencer|politician|singer|"
                              r"youtuber|streamer|cosplayer|lookalike|look-alike|deepfake|face\s*swap|person\s*of\s*interest|"
                              r"child\w*|kids?|loli\w*|shota\w*|teen\w*|minor|young\s*girl|toddler|baby)\b", re.I)
_SCAN_BAD = re.compile(r"minor|under\s*-?\s*21|underage|child|poi|real\s*person|face\s*swap|faceswap", re.I)
_SCAN_CLEAR = re.compile(r"\b(false|clean|pass|success|ok|none|not detected)\b", re.I)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_status(path, expected):
    """verified, mismatch, or UNKNOWN when the publisher did not list a SHA256."""
    token = str(expected or "").strip()
    if not token:
        return "UNKNOWN"
    if file_sha256(path).lower() != token.lower():
        return "mismatch"
    return "verified"


def wan_parts(base_model):
    """(version, expert) read from a base-model string. Empty strings mean the field was not there."""
    text = str(base_model or "").lower()
    if re.search(r"2\s*\.\s*2", text):
        version = "2.2"
    elif re.search(r"2\s*\.\s*1", text):
        version = "2.1"
    else:
        version = ""
    if re.search(r"high[\s_\-]*noise", text):
        expert = "high_noise"
    elif re.search(r"low[\s_\-]*noise", text):
        expert = "low_noise"
    else:
        expert = ""
    return version, expert


def _truthy(value):
    return value in (True, "true", "True", 1, "1")


def civitai_mode(model, version):
    """Archived or TakenDown when a fixture or response says so. Otherwise empty."""
    sources = (version or {}, model or {}, (version or {}).get("model") or {})
    for src in sources:
        if not isinstance(src, dict) or not src.get("mode"):
            continue
        key = re.sub(r"[\s_\-]+", "", str(src.get("mode"))).lower()
        if key == "takendown":
            return "TakenDown"
        if key == "archived":
            return "Archived"
    return ""


def civitai_minor(model, version):
    sources = (model or {}, version or {}, (version or {}).get("model") or {})
    for src in sources:
        if isinstance(src, dict) and (_truthy(src.get("minor")) or _truthy(src.get("underage"))):
            return True
    return False


def civitai_scans(model, version):
    found = []
    for src in (model or {}, version or {}):
        if isinstance(src, dict) and isinstance(src.get("scans"), list):
            found.extend(src["scans"])
    for one in (version or {}).get("files") or []:
        if isinstance(one, dict) and isinstance(one.get("scans"), list):
            found.extend(one["scans"])
    return found


def civitai_scan_block(model, version):
    for item in civitai_scans(model, version):
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = " ".join(str(item.get(key) or "") for key in ("name", "type", "result", "status"))
        else:
            continue
        if _SCAN_BAD.search(text) and not _SCAN_CLEAR.search(text):
            return "Blocked: a scan flags this LoRA (%s)." % text.strip()
    return ""


def civitai_sha256(version):
    for one in (version or {}).get("files") or []:
        if not isinstance(one, dict):
            continue
        token = str(((one.get("hashes") or {}).get("SHA256")) or "").strip()
        if token:
            return token
    return ""


def parse_civitai_url(url):
    """-> (model_id or None, version_id or None)"""
    u = str(url or "").strip()
    m = re.search(r"civitai\.(com|green|red)/api/download/models/(\d+)", u)
    if m:
        return None, int(m.group(2))
    mid = re.search(r"civitai\.(com|green|red)/models/(\d+)", u)
    vid = re.search(r"modelVersionId=(\d+)", u)
    if not mid and not vid:
        raise ValueError("That isn't a Civitai model link (it should look like civitai.com/models/12345).")
    return (int(mid.group(2)) if mid else None), (int(vid.group(1)) if vid else None)


def civitai_check(model, version):
    """Refuse real people, minors, face-swap, archived, and taken-down; refuse non-LoRA types. Returns (ok, message)."""
    mode = civitai_mode(model, version)
    if mode:
        return False, "Blocked: Civitai marks this version %s." % mode
    if civitai_minor(model, version):
        return False, "Blocked: Civitai marks this as a minor. Under 21 is refused."
    scan_why = civitai_scan_block(model, version)
    if scan_why:
        return False, scan_why
    if model.get("poi") or (version.get("model") or {}).get("poi"):
        return False, "Blocked: Civitai marks this as a real person ('person of interest')."
    mtype = str(model.get("type") or (version.get("model") or {}).get("type") or "").lower()
    if mtype and mtype not in ("lora", "locon", "dora", "lycoris"):
        return False, f"This is a '{mtype}', not a LoRA. Only LoRAs can be added here."
    tags = [str(t.get("name") if isinstance(t, dict) else t) for t in (model.get("tags") or [])]
    for t in tags:
        if CIVITAI_BAD_TAGS.search(t):
            return False, f"Blocked: this LoRA is tagged '{t}'."
    words = list(version.get("trainedWords") or [])
    name = str(model.get("name") or (version.get("model") or {}).get("name") or "")
    desc = re.sub(r"<[^>]+>", " ", str(model.get("description") or ""))  # the whole description (D-C-19)
    # Title, tags and trigger words first, with every rule.
    ok, why = safety.check_lora(name, {"tags": ", ".join(tags)}, words)
    if not ok:
        return False, why
    # Then the description, with every rule (D-C-18: description rules stay hard refusals for every LoRA).
    ok, why = safety.check_lora(name, {"description": desc, "tags": ", ".join(tags)}, words)
    if ok:
        return True, ""
    # The one exception: Ak's exact allowlist (the eight audited LoRAs and the four Wan 2.2 14B sibling halves of
    # four of them), by exact version id and SHA256 of their .safetensors file.
    # Even for those, a minor-coded word or an age under 21 in the description still refuses.
    if allowlisted(version):
        ok, minor_why = safety.check_minor_and_age(desc)
        if not ok:
            return False, "This LoRA can't be used. " + minor_why
        return True, ""
    return False, why


ALLOWLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora_allowlist.json")


def _allowlist():
    try:
        rows = json.load(open(ALLOWLIST_PATH, encoding="utf-8")).get("entries") or []
    except (OSError, ValueError):
        return frozenset()
    return frozenset((int(r["version_id"]), str(r["sha256"]).lower()) for r in rows
                     if isinstance(r, dict) and re.fullmatch(r"[0-9a-fA-F]{64}", str(r.get("sha256") or "")))


def _primary_safetensors_sha(version):
    files = [f for f in (version or {}).get("files") or [] if isinstance(f, dict)
             and str(f.get("name") or "").lower().endswith(".safetensors")
             and str((f.get("metadata") or {}).get("format", "SafeTensor")).lower().startswith("safetensor")]
    f = next((x for x in files if x.get("primary")), files[0] if files else None)
    return str(((f or {}).get("hashes") or {}).get("SHA256") or "").lower()


def allowlisted(version):
    """True only for an exact (version id, SHA256 of its .safetensors file) pair in app/lora_allowlist.json.

    Ak approved these on 2026-11-06: the eight after the reviewer's audit (D-C-18, AK-CANDY-IMPORTER-ALLOWLIST-20261106),
    then the four Wan 2.2 14B sibling halves of four of them after a live check (D-C-20, AK-CANDY-WAN-SIBLINGS-20261106)."""
    try:
        vid = int((version or {}).get("id"))
    except (TypeError, ValueError):
        return False
    sha = _primary_safetensors_sha(version)
    return bool(sha) and (vid, sha) in _allowlist()


def civitai_family(base_model):
    b = str(base_model or "").lower()
    for rx, fam in CIVITAI_BASE:
        if re.search(rx, b):
            return fam
    return "unknown"


def civitai_lookup(url, api_key=None, session=None):
    s = session or requests
    mid, vid = parse_civitai_url(url)
    h = {"User-Agent": "easy-studio/3", **({"Authorization": f"Bearer {api_key}"} if api_key else {})}
    if vid:
        r = s.get(f"https://civitai.com/api/v1/model-versions/{vid}", headers=h, timeout=30)
        if r.status_code in (401, 403):
            raise ValueError("Civitai says this needs you to be logged in. Paste your Civitai API key (Civitai > Account settings > API keys).")
        r.raise_for_status()
        version = r.json()
        mid = mid or version.get("modelId")
    r = s.get(f"https://civitai.com/api/v1/models/{mid}", headers=h, timeout=30)
    if r.status_code in (401, 403):
        raise ValueError("Civitai says this needs you to be logged in. Paste your Civitai API key.")
    if r.status_code == 404:
        raise ValueError("Civitai can't find that model (it may have been removed).")
    r.raise_for_status()
    model = r.json()
    versions = model.get("modelVersions") or []
    if not vid:
        if not versions:
            raise ValueError("That model has no downloadable versions.")
        version = versions[0]
    else:
        version = next((v for v in versions if v.get("id") == vid), None) or version
    ok, why = civitai_check(model, version)
    files = [f for f in (version.get("files") or []) if str((f.get("metadata") or {}).get("format", "SafeTensor")).lower().startswith("safetensor")]
    f = next((x for x in files if x.get("primary")), files[0] if files else None)
    if not f:
        ok, why = (False, why or "This version has no .safetensors file.")
    thumb = next((i.get("url") for i in (version.get("images") or []) if i.get("type", "image") == "image"), None)
    nsfw_thumb = any((i.get("nsfwLevel") or 0) > 1 for i in (version.get("images") or [])[:1])
    sha = civitai_sha256(version)
    version_name, expert = wan_parts(version.get("baseModel"))
    creator = str((model.get("creator") or {}).get("username") or "")
    examples = []
    for image in (version.get("images") or [])[:4]:
        if not isinstance(image, dict):
            continue
        prompt = str(((image.get("meta") or {}).get("prompt")) or "").strip()
        if not prompt:
            continue
        username = str(image.get("username") or "")
        verified = bool(creator and username and username == creator)
        examples.append({
            "prompt": prompt[:500],
            "source_id": "civitai:%s:%s:image:%s" % (model.get("id"), version.get("id"), image.get("id") or len(examples) + 1),
            "author_id": username,
            "source_author": creator,
            "authorship": "verified" if verified else "unverified",
        })
    notes = re.sub(r"<[^>]+>", " ", str(model.get("description") or ""))
    notes = re.sub(r"\s+", " ", notes).strip()[:500]
    return {"ok": ok, "reason": why, "model_id": model.get("id"), "version_id": version.get("id"),
            "name": model.get("name"), "version": version.get("name"), "base": version.get("baseModel"),
            "family": civitai_family(version.get("baseModel")), "trigger_words": list(version.get("trainedWords") or [])[:8],
            "file": f.get("name") if f else None, "size_mb": round((f.get("sizeKB") or 0) / 1024, 1) if f else 0,
            "download_url": f.get("downloadUrl") if f else None, "thumb_url": thumb, "thumb_adult": nsfw_thumb,
            "nsfw": bool(model.get("nsfw")), "early_access": bool(version.get("earlyAccessEndsAt") or version.get("availability") == "EarlyAccess"),
            "sha256": sha, "hash_status": "listed" if sha else "UNKNOWN", "scans": civitai_scans(model, version),
            "mode": civitai_mode(model, version), "minor": civitai_minor(model, version),
            "poi": bool(model.get("poi") or (version.get("model") or {}).get("poi")),
            "wan_version": version_name, "wan_expert": expert, "author_notes": notes, "examples": examples,
            "authorship": "verified" if any(row["authorship"] == "verified" for row in examples) else "unverified"}


def civitai_download(lib, info, api_key=None, dl=None, session=None, tmp_dir=None):
    """Download a looked-up Civitai LoRA into the library. dl: a dict updated with progress."""
    s = session or requests
    if not info.get("ok"):
        raise ValueError(info.get("reason") or "Blocked.")
    url = info["download_url"]
    h = {"User-Agent": "easy-studio/3", **({"Authorization": f"Bearer {api_key}"} if api_key else {})}
    tmp = os.path.join(tmp_dir or lib.dir, f".civitai_{info['version_id']}.part")
    with s.get(url, headers=h, stream=True, timeout=60, allow_redirects=True) as r:
        if r.status_code in (401, 403):
            raise ValueError("Civitai needs you to be logged in for this file (or it is early-access / gated). "
                             "Paste your Civitai API key, and make sure your account can download it on the website.")
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        got = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                if dl is not None and dl.get("cancel"):
                    raise ValueError("Stopped.")
                f.write(chunk)
                got += len(chunk)
                if dl is not None:
                    dl["progress"] = round(got / total, 3) if total else 0
                if got > 4 * 1024**3:
                    raise ValueError("That file is bigger than 4 GB -- not a normal LoRA.")
    listed_hash = str(info.get("sha256") or "").strip()
    status = hash_status(tmp, listed_hash)
    if status == "mismatch":
        if os.path.exists(tmp):
            os.remove(tmp)
        raise ValueError("Blocked: the downloaded file hash does not match the published SHA256.")
    rec = None
    try:
        words = list(info.get("trigger_words") or [])
        side = {"source": "Civitai", "civitai": {"model": info["model_id"], "version": info["version_id"], "base": info["base"]},
                "trigger_words": words, "title": info["name"],
                "usage": {"author_notes": info.get("author_notes") or "", "trained_words": words,
                          "trained_words_listed": bool(words), "strength_model": None, "strength_clip": None,
                          "hash_status": status, "sha256": listed_hash, "role": info.get("role") or "",
                          "base_model": info.get("base") or "", "wan_version": info.get("wan_version") or "",
                          "wan_expert": info.get("wan_expert") or "", "authorship": info.get("authorship") or "unverified",
                          "examples": info.get("examples") or [], "scans": info.get("scans") or [],
                          "mode": info.get("mode") or ""}}
        if info["family"] != "unknown":
            side["base"] = info["family"]
        if info.get("nsfw"):
            side["area"] = "adult"
        rec = lib.add_file(tmp, info["file"] or f"civitai_{info['version_id']}.safetensors", **side)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if info.get("thumb_url") and rec:
        try:
            r = s.get(info["thumb_url"], timeout=30, headers={"User-Agent": "easy-studio/3"})
            if r.ok and len(r.content) < 20 * 1024 * 1024:
                ext = ".jpg" if b"JFIF" in r.content[:20] or r.content[:2] == b"\xff\xd8" else ".png"
                p = os.path.splitext(lib.path_of(rec["name"]))[0] + ".preview" + ext
                open(p, "wb").write(r.content)
                if info.get("thumb_adult"):
                    lib.write_sidecar(rec["name"], thumb_adult=True)
        except Exception:
            pass
    return lib.get(rec["name"]) if rec else None
