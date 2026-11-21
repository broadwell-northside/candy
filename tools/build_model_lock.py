#!/usr/bin/env python3
# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Build the one model lock: config/server_model_lock.json (+ config/llm_models.json).

    python3 tools/build_model_lock.py --grok-lock PATH --grok-loras PATH --grok-llm PATH [--write]

Sources, in order of trust:
  1. The app itself: install/download_models.py (what each group downloads) and app/workflows/*.json (what the
     templates load). Every template file must end up locked or listed in "not_on_server" with a reason.
  2. Grok Bot's server lock (46 Hugging Face rows pinned to 40-hex revisions with SHA256; checked live by the
     reviewer on 2026-11-06). Used for the Director GGUFs, the VLM scorer, Flux.1 dev and its CLIP-L.
  3. Grok Bot's LoRA manifest, by numeric ID only: version id, SHA256, size, family, role, base. Catalog names,
     file names and trigger words are never copied, printed or written: LoRA files get ID-based ASCII names.

Network: the Hugging Face API (repo head, file sizes, LFS SHA256) at pinned revisions. No token, no weights.
Output rows follow Grok's `turin.server_model_lock/1` row format (wave, url, dest, size, sha256, comfy_link,
requires_token, profile, priority), plus id, family, roles, tier, license and source for the app and the reviewer.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
HF = "https://huggingface.co"
UA = {"User-Agent": "easy-studio-lock-builder/1"}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MODEL_EXT = re.compile(r"\.(safetensors|gguf|pth|pt|ckpt|bin|onnx|task)$")

# download_models.py group -> (family, wave, tier). Waves: 1 fast to useful, 2 image/edit/video core,
# 3 LoRAs + bake-off candidates, 4 heavy Director contenders (opt-in). Waves 1-3 go on the stick.
GROUPS = {
    "safety": ("safety", 1, "core"),
    "face": ("face", 1, "core"),
    "fast": ("zimage", 1, "core"),
    "tools": ("tools", 1, "core"),
    "image": ("chroma", 2, "core"),
    "edit": ("qwen_edit", 2, "core"),
    "video": ("wan22", 2, "core"),
    "video-wan5b": ("wan22", 2, "core"),
    "3d": ("trellis2", 2, "core"),
    "anime": ("sdxl", 3, "optional"),
    "video-t2v": ("wan22", 3, "candidate"),
    "video-ltx": ("ltx25", 3, "candidate"),
    "video-hunyuan": ("hunyuan15", 3, "candidate"),
    "video-kandinsky": ("kandinsky5", 3, "candidate"),
    "photoreal": ("photoreal", 3, "candidate"),
    "3d-shape": ("hunyuan3d", 3, "candidate"),
}
# Removed: identity copy (2027766) and an archive, not .safetensors (1822984) by Ak's order (C-LORA-01); a real-person
# tag (2268008, D-C-16); an identity-copy word at character 4082 of the description (1959747, D-C-19).
REMOVED_LORAS = {2027766: "identity_copy", 1822984: "archive_not_safetensors", 2268008: "real_person_tag_d_c_16",
                 1959747: "identity_copy_in_description_d_c_19"}
HELD_LORAS = {}
WAN_BASES = {"Wan Video 2.2 I2V-A14B": "wan22_i2v_a14b", "Wan Video 2.2 T2V-A14B": "wan22_t2v_a14b",
             "Wan Video 2.2 TI2V-5B": "wan22_ti2v_5b", "Flux.1 D": "flux1_dev", "Chroma": "chroma1",
             "Qwen": "qwen_image", "ZImageTurbo": "zimage_turbo"}


def http_json(url, data=None, tries=7):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=dict(UA, **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})))
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise
            wait = e.headers.get("Retry-After") if e.headers else None
            time.sleep(float(wait) if wait and str(wait).isdigit() else min(60, 3 * 2 ** attempt))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(min(60, 3 * 2 ** attempt))
    raise RuntimeError("network failed: " + url)


def http_bytes(url, limit=4 * 1024 * 1024):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("file too large to hash inline: " + url)
    return data


_heads, _info = {}, {}
PENDING = []  # rows that could not be locked yet (gated metadata); listed in not_on_server with the reason


def repo_head(repo):
    if repo not in _heads:
        meta = http_json(f"{HF}/api/models/{repo}")
        lic = (meta.get("cardData") or {}).get("license")
        if not lic:
            lic = next((t.split(":", 1)[1] for t in meta.get("tags") or [] if t.startswith("license:")), "unknown")
        if lic == "unknown":  # cards with no licence tag: the licence read from the repository's LICENSE file
            lic = LICENSE_FROM_FILE.get(meta.get("id") or repo, lic)
        _heads[repo] = {"sha": meta["sha"], "license": lic, "gated": bool(meta.get("gated")), "id": meta.get("id") or repo}
    return _heads[repo]


def file_info(repo, rev, path):
    key = (repo, rev, path)
    if key not in _info:
        rows = http_json(f"{HF}/api/models/{repo}/paths-info/{rev}",
                         data=urllib.parse.urlencode({"paths": path, "expand": "false"}).encode())
        row = next((r for r in rows if r.get("path") == path), None)
        if not row:
            raise FileNotFoundError(f"{repo}@{rev[:8]}:{path}")
        size, sha = int(row["size"]), (row.get("lfs") or {}).get("oid")
        if not sha:  # small git-stored file (configs): hash its bytes at the pinned revision
            sha = hashlib.sha256(http_bytes(f"{HF}/{repo}/resolve/{rev}/{urllib.parse.quote(path)}")).hexdigest()
        _info[key] = (size, sha)
    return _info[key]


def parse_hf(url):
    m = re.match(r"^https://huggingface\.co/([^/]+/[^/]+)/resolve/([^/]+)/(.+)$", url)
    if not m:
        raise ValueError("not a Hugging Face resolve URL: " + url)
    return m.group(1), m.group(2), urllib.parse.unquote(m.group(3))


def license_class(lic):
    lic = (lic or "").lower()
    if lic in ("apache-2.0", "mit", "bsd-3-clause", "openrail", "openrail++", "cc-by-4.0", "llama3.3", "gemma"):
        return "open"
    if "non-commercial" in lic or lic in ("flux-1-dev-non-commercial-license", "cc-by-nc-4.0", "cc-by-nc-sa-4.0"):
        return "noncommercial"
    if lic in ("other", "unknown", ""):
        return "custom"
    return "custom"


def load_download_table():
    spec = importlib.util.spec_from_file_location("download_models", ROOT / "install" / "download_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MODELS


def template_refs():
    keys = ("unet_name", "ckpt_name", "clip_name", "clip_name1", "clip_name2", "vae_name", "lora_name",
            "model_name", "control_net_name", "name", "upscale_model", "model")
    refs = {}
    for path in sorted((ROOT / "app" / "workflows").glob("*.json")):
        wf = json.loads(path.read_text())
        nodes = wf.values() if isinstance(wf, dict) else wf
        for node in nodes:
            ins = (node or {}).get("inputs") if isinstance(node, dict) else None
            if not isinstance(ins, dict):
                continue
            for k in keys:
                v = ins.get(k)
                if isinstance(v, str) and MODEL_EXT.search(v):
                    refs.setdefault(os.path.basename(v), set()).add(path.name)
    return refs


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def base_rows():
    rows, by_comfy = [], {}
    table = load_download_table()
    prio = {}
    for group, items in table.items():
        if group not in GROUPS:
            raise SystemExit(f"download group {group!r} has no lock mapping; add it to GROUPS")
        family, wave, tier = GROUPS[group]
        for comfy_dir, fname, url, _size in items:
            repo, ref, path = parse_hf(url)
            head = repo_head(repo)
            repo = head["id"]  # canonical name (renamed repos answer 307 on the old one)
            rev = head["sha"] if not HEX40.match(ref) else ref
            try:
                size, sha = file_info(repo, rev, path)
            except urllib.error.HTTPError as exc:
                if exc.code not in (401, 403):
                    raise
                PENDING.append({"comfy_file": fname, "comfy_dir": comfy_dir, "repo": repo, "rev": rev, "path": path,
                                "group": group, "reason": "gated: file metadata needs Ak's Hugging Face token at lock time"})
                continue
            key = (comfy_dir, fname)
            if key in by_comfy:
                prev = by_comfy[key]
                if prev["sha256"] != sha:
                    raise SystemExit(f"two different files share ComfyUI path {comfy_dir}/{fname}: "
                                     f"{prev['sha256'][:12]} vs {sha[:12]}")
                if wave < prev["wave"]:
                    prev["wave"], prev["tier"] = wave, tier
                prev.setdefault("also_groups", []).append(group)
                continue
            prio[wave] = prio.get(wave, 0) + 10
            family_dir = family if comfy_dir in ("diffusion_models", "checkpoints", "text_encoders", "vae",
                                                 "model_patches", "latent_upscale_models", "clip_vision") else "shared"
            row = {
                "id": f"{family}.{slug(os.path.splitext(fname)[0])}",
                "wave": wave, "priority": prio[wave], "tier": tier, "group": f"media:{family}" if family not in ("safety", "tools", "face") else family,
                "family": family, "roles": [group],
                "label": f"{family} {comfy_dir} {fname}",
                "url": f"{HF}/{repo}/resolve/{rev}/{urllib.parse.quote(path)}",
                "dest": f"comfy/{family_dir}/{fname}",
                "size": size, "sha256": sha,
                "comfy_link": {"type": comfy_dir, "name": fname},
                "repo": repo, "rev": rev, "path": path,
                "source": {"type": "hf", "repo": repo, "rev": rev, "path": path},
                "license": {"id": head["license"], "class": license_class(head["license"]), "gated": head["gated"]},
            }
            if head["gated"]:
                row["requires_token"] = "HF_TOKEN"
            by_comfy[key] = row
            rows.append(row)
    return rows, by_comfy


def grok_rows(grok_lock, by_comfy):
    """Director GGUFs, the VLM scorer, Flux.1 dev (+ CLIP-L): Grok's verified pins, Me-path liveness dropped."""
    rows = []
    for r in json.loads(pathlib.Path(grok_lock).read_text())["rows"]:
        if r["group"] == "liveness":
            continue  # Me path, parked (brief section 6)
        if r["group"].startswith("media:") and r["group"] != "media:flux":
            continue  # the app's own table is the source for these (Grok's pins differ from the templates)
        link = r.get("comfy_link")
        if link and (link["type"], link["name"]) in by_comfy:
            existing = by_comfy[(link["type"], link["name"])]
            if existing["sha256"] != r["sha256"]:
                raise SystemExit(f"Grok row {r['dest']} conflicts with the app's {link['type']}/{link['name']}")
            continue
        assert HEX40.match(r["rev"]) and HEX64.match(r["sha256"]), r["dest"]
        fam = {"media:flux": "flux1", "llm": "director", "vlm": "scorer"}[r["group"]]
        row = dict(r)
        row.update({
            "id": f"{fam}.{slug(os.path.basename(r['dest']).rsplit('.', 1)[0])}" if fam != "scorer" else f"scorer.{slug(r['path'])}",
            "family": fam, "tier": "heavy" if r["wave"] == 4 else "core",
            "roles": [{"flux1": "still_realistic", "director": "director", "scorer": "plate_qa"}[fam]],
            "source": {"type": "hf", "repo": r["repo"], "rev": r["rev"], "path": r["path"]},
        })
        if fam == "flux1":
            row["wave"] = 2
        if fam == "scorer":
            row["wave"] = 2
        row.setdefault("license", {"id": "see_registry", "class": "custom", "gated": bool(r.get("requires_token"))})
        rows.append(row)
    return rows


CIVITAI = "https://civitai.com/api/v1"
_civ = {}


def civitai_model(mid):
    """The live model record from civitai.com (metadata only, no token)."""
    if mid not in _civ:
        time.sleep(0.5)  # be gentle with the public API
        _civ[mid] = http_json(f"{CIVITAI}/models/{mid}")
    return _civ[mid]


def civitai_version(model, vid):
    found = next((v for v in model.get("modelVersions") or [] if v.get("id") == vid), None)
    return found or http_json(f"{CIVITAI}/model-versions/{vid}")


def app_check(model, version, pinned_sha):
    """The app's own importer decision on the live record, plus the pinned hash and format.

    Returns (ok, code). Codes only, never the check's message (it can quote catalog text)."""
    sys.path.insert(0, str(ROOT / "app"))
    import loras  # noqa: E402 - the repo's own refusal code (civitai_check, the D-C-18 allowlist)
    ok, _why = loras.civitai_check(model, version)
    if not ok:
        return False, "refused_by_civitai_check"
    live_sha = loras._primary_safetensors_sha(version)
    if not live_sha:
        return False, "no_safetensors_file"
    if live_sha != pinned_sha:
        return False, "sha256_differs_from_civitai"
    if version.get("status") not in (None, "Published"):
        return False, "not_published"
    return True, "allowlisted_exact_sha256_d_c_18" if loras.allowlisted(version) else "pass"


def lora_rows(grok_loras):
    """Grok's 42 kept LoRAs by ID only. Removals and holds per Ak; ID-based ASCII file names."""
    data = json.loads(pathlib.Path(grok_loras).read_text())
    rows, held, removed, prio = [], [], [], 0
    for e in data["kept"]:
        mid, vid = int(e["civitai_model_id"]), int(e["civitai_version_id"])
        if mid in REMOVED_LORAS:
            removed.append({"model_id": mid, "version_id": vid, "reason": REMOVED_LORAS[mid]})
            continue
        if not e["file_name"].lower().endswith(".safetensors"):
            removed.append({"model_id": mid, "version_id": vid, "reason": "not_safetensors"})
            continue
        sha = str(e["sha256"]).lower()
        assert HEX64.match(sha), (mid, vid)
        model = civitai_model(mid)
        ok, code = app_check(model, civitai_version(model, vid), sha)
        print(f"lora {mid}/{vid}: {code}")
        if not ok:
            removed.append({"model_id": mid, "version_id": vid, "reason": code})
            continue
        size = int(round(float(e["size_kb"]) * 1024))
        family, role = e["family"], e["role"]
        if mid in HELD_LORAS:
            held.append({"model_id": mid, "version_id": vid, "sha256": sha, "family": family, "reason": HELD_LORAS[mid]})
            continue
        trained_on = WAN_BASES.get(e.get("base_model") or "", slug(e.get("base_model") or "unknown"))
        lowered = e["file_name"].lower()  # read for the half hint only; never stored or printed
        half = "high" if "high" in lowered else ("low" if "low" in lowered else None)
        prio += 10
        row = {
            "id": f"lora.{family}.{mid}.{vid}",
            "wave": 3, "priority": prio, "tier": "core", "group": f"lora:{family}",
            "family": family, "roles": [role], "label": f"lora.{family}.{mid}.{vid}",
            "url": f"https://civitai.com/api/download/models/{vid}",
            "dest": f"comfy/loras/{family}/{role}/{mid}_{vid}.safetensors",
            "size": size, "sha256": sha, "requires_token": "CIVITAI_API_TOKEN",
            "civitai": {"model_id": mid, "version_id": vid},
            "source": {"type": "civitai", "model_id": mid, "version_id": vid},
            "trained_on": trained_on,
            "license": {"id": "civitai-per-version", "class": "custom", "gated": False, "verified": False},
            "import_check": code,
        }
        if family == "wan22_a14b":
            row["half"] = half
            row["pair_id"] = None
            row["pairing"] = "missing_half"  # route_lora refuses an unpaired 14B LoRA until its sibling half is locked
        rows.append(row)
    return rows, held, removed


def apply_pairs(rows, pairs_path):
    """Add each Wan 14B LoRA's sibling half (config/lora_pairs.json) when it passed the app's own checks."""
    pairs = json.loads(pathlib.Path(pairs_path).read_text())["pairs"]
    by_vid = {r["civitai"]["version_id"]: r for r in rows if r.get("civitai")}
    added = []
    for p in pairs:
        row, sib = by_vid.get(p["version_id"]), p.get("sibling")
        if not row or not sib:
            continue
        lo, hi = sorted((p["version_id"], sib["version_id"]))
        model = civitai_model(p["model_id"])
        ok, code = app_check(model, civitai_version(model, sib["version_id"]), str(sib.get("sha256", "")).lower())
        print(f"lora sibling {p['model_id']}/{sib['version_id']}: {code}")
        if not ok or not HEX64.match(sib.get("sha256", "")):
            row["pairing"] = "sibling_refused_at_import"
            row["sibling_version_id"] = sib["version_id"]
            continue
        pair_id = f"wan14b.{p['model_id']}.{lo}-{hi}"
        twin = dict(row)
        twin.update({
            "id": f"lora.{row['family']}.{p['model_id']}.{sib['version_id']}",
            "label": f"lora.{row['family']}.{p['model_id']}.{sib['version_id']}",
            "priority": row["priority"] + 1,
            "url": f"https://civitai.com/api/download/models/{sib['version_id']}",
            "dest": row["dest"].rsplit("/", 1)[0] + f"/{p['model_id']}_{sib['version_id']}.safetensors",
            "size": int(sib["size"]), "sha256": sib["sha256"],
            "civitai": {"model_id": p["model_id"], "version_id": sib["version_id"]},
            "source": {"type": "civitai", "model_id": p["model_id"], "version_id": sib["version_id"]},
            "half": sib["half"], "import_check": code,
        })
        row["half"] = p.get("half") or row.get("half")  # from version name + file name, read in the pairing step
        for r in (row, twin):
            r["pair_id"], r["pairing"] = pair_id, "paired"
        added.append(twin)
    return rows + added


# Files the templates or the Director registry need that neither the app's table nor Grok's lock carries.
EXTRA_HF = [
    # (repo, path, comfy_dir or None, family, wave, tier, role, profile)
    ("Comfy-Org/Z-Image", "split_files/diffusion_models/z_image_bf16.safetensors", "diffusion_models",
     "zimage", 2, "core", "still_identity", None),
    ("mradermacher/gpt-oss-120b-abliterated-GGUF", "gpt-oss-120b-abliterated.MXFP4_MOE.gguf", None,
     "director", 4, "heavy", "director", "gptoss_120b_abliterated_mxfp4"),
    ("stable-diffusion-v1-5/stable-diffusion-v1-5", "v1-5-pruned-emaonly.safetensors", "checkpoints",
     "sd15", 2, "core", "photo", None),
]
# Runtimes the lock pins for first boot (Ak, AK-CANDY-DEEPSEEK-BOTH-20261106: keep both DeepSeek builds;
# Strata is set up on first boot as hardware_pending and dropped only if its source fails verification).
LICENSE_FROM_FILE = {"opencv/face_detection_yunet": "mit", "opencv/face_recognition_sface": "apache-2.0"}
RUNTIMES = {
    "strata": {"repo": "https://github.com/Niko1221/Strata", "tag": "v0.2.11",
               "commit": "c3b3f5035506f3e966f1b4b7b188aeaabae92f1d", "license": "MIT",
               "for_profiles": ["deepseek_v41_flash_1017_uncensored_gsq_iq2xxs"],
               "verify": "fetch by git at the pinned commit (the tag is not signed); never run the release install.sh unread",
               "status": "hardware_pending"},
    "opencv_python_headless": {'project': 'https://pypi.org/project/opencv-python-headless/',
     'version': '4.14.0.94',
     'license': 'Apache-2.0',
     'filename': 'opencv_python_headless-4.14.0.94-cp37-abi3-macosx_13_0_arm64.whl',
     'size': 46491231,
     'url': 'https://files.pythonhosted.org/packages/9a/56/12f9b05628cf4ab6aad54479b9124f7c1f2f92b6a4e47c071beb63d926a2/opencv_python_headless-4.14.0.94-cp37-abi3-macosx_13_0_arm64.whl',
     'sha256': 'bc7db37dc234f7bb3190a158fd9dd750357246fc7d8adb23698843ef721a993b',
     'install': '--no-deps --require-hashes',
     'into': "the picture engine's Python (<runtime>/venv)",
     'requires': 'numpy 2 or newer (numpy 2.5.4 is already there)',
     'for': 'the face check: app/workers/face_worker.py',
     'fallback': {'version': '4.13.0.92',
                  'filename': 'opencv_python_headless-4.13.0.92-cp37-abi3-macosx_13_0_arm64.whl',
                  'size': 46247192,
                  'url': 'https://files.pythonhosted.org/packages/79/42/2310883be3b8826ac58c3f2787b9358a2d46923d61f88fedf930bc59c60c/opencv_python_headless-4.13.0.92-cp37-abi3-macosx_13_0_arm64.whl',
                  'sha256': '1a7d040ac656c11b8c38677cc8cccdc149f98535089dbe5b081e80a4e5903209',
                  'when': "only if 4.14.0.94 does not import with the installed numpy on the owner's Mac"},
     'status': "metadata only: not downloaded and not yet imported on the owner's Mac"},
}


def extra_rows(by_comfy):
    rows = []
    for repo, path, comfy_dir, family, wave, tier, role, profile in EXTRA_HF:
        head = repo_head(repo)
        repo = head["id"]
        rev = head["sha"]
        size, sha = file_info(repo, rev, path)
        fname = os.path.basename(path)
        if comfy_dir and (comfy_dir, fname) in by_comfy:
            continue
        row = {
            "id": f"{family}.{slug(os.path.splitext(fname)[0])}", "wave": wave, "priority": 900 + len(rows),
            "tier": tier, "group": "llm" if family == "director" else f"media:{family}", "family": family,
            "roles": [role], "label": f"{family} {fname}",
            "url": f"{HF}/{repo}/resolve/{rev}/{urllib.parse.quote(path)}",
            "dest": (f"comfy/{family}/{fname}" if comfy_dir else f"llm/{slug(profile or family)}/{fname}"),
            "size": size, "sha256": sha, "repo": repo, "rev": rev, "path": path,
            "source": {"type": "hf", "repo": repo, "rev": rev, "path": path},
            "license": {"id": head["license"], "class": license_class(head["license"]), "gated": head["gated"]},
        }
        if comfy_dir:
            row["comfy_link"] = {"type": comfy_dir, "name": fname}
            by_comfy[(comfy_dir, fname)] = row
        if profile:
            row["profile"] = profile
        if head["gated"]:
            row["requires_token"] = "HF_TOKEN"
        rows.append(row)
    return rows


def llm_registry(grok_llm, rows):
    reg = json.loads(pathlib.Path(grok_llm).read_text())
    files = {r["profile"]: [] for r in rows if r.get("profile")}
    for r in rows:
        if r.get("profile"):
            files[r["profile"]].append(r["id"])
    out = []
    for p in reg["profiles"]:
        if p.get("remote"):
            continue  # paid remote profile: off by Ak's rule, not in the registry (P-09)
        q = dict(p)
        q["lock_ids"] = sorted(files.get(p["id"], []))
        if "strata" in str(p.get("runtime", "")).lower():
            q["runtime_status"] = "hardware_pending: Strata runtime set up on first boot; dropped only if its source fails verification"
            q["enabled"] = True if p["id"] != "deepseek_v41_flash_1017_uncensored_tp2_burst" else p.get("enabled", False)
        if not q["lock_ids"] and q.get("enabled") and p["id"] != "deepseek_v41_flash_1017_uncensored_tp2_burst":
            q["enabled"] = False
            q["disabled_reason"] = "no SHA256-locked files yet"
        out.append(q)
    reg["profiles"] = out
    scorer_repo = next((r["repo"] for r in rows if r.get("family") == "scorer"), None)
    if scorer_repo:
        reg["scorer"] = dict(reg.get("scorer") or {}, hf_repo=scorer_repo, lock_family="scorer")
        reg["scorer"].pop("alt_hf_repo", None)
    reg["generated_from"] = "Grok Bot llm_models.json, remote profile removed, files tied to config/server_model_lock.json"
    return reg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--grok-lock", required=True)
    ap.add_argument("--grok-loras", required=True)
    ap.add_argument("--grok-llm", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    rows, by_comfy = base_rows()
    rows += grok_rows(a.grok_lock, by_comfy)
    rows += extra_rows(by_comfy)
    loras, held, removed = lora_rows(a.grok_loras)
    rows += apply_pairs(loras, ROOT / "config" / "lora_pairs.json")
    refs = template_refs()
    have = {r["comfy_link"]["name"] for r in rows if r.get("comfy_link")}
    pending_files = {x["comfy_file"]: x for x in PENDING}
    not_on_server = [dict(pending_files[f], templates=sorted(t)) if f in pending_files else
                     {"comfy_file": f, "templates": sorted(t), "reason": "no source in the app's download table yet"}
                     for f, t in sorted(refs.items()) if f not in have]
    not_on_server += [x for x in PENDING if x["comfy_file"] not in refs]
    lock = {
        "schema": "turin.server_model_lock/1",
        "generated_by": "tools/build_model_lock.py",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "models_root": "/srv/ai/models",
        "waves": {"1": "fast to useful: age check, Z-Image Turbo, tools, default Director",
                  "2": "image, edit, video and 3D core; Flux.1 dev; plate scorer",
                  "3": "LoRAs and bake-off candidates", "4": "heavy Director contenders (opt-in)"},
        "rows": sorted(rows, key=lambda r: (r["wave"], r["priority"], r["id"])),
        "held": held, "removed": removed, "not_on_server": not_on_server, "runtimes": RUNTIMES,
    }
    ids = [r["id"] for r in lock["rows"]]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"duplicate lock ids: {sorted(dup)}")
    reg = llm_registry(a.grok_llm, lock["rows"])
    total = {}
    for r in lock["rows"]:
        total.setdefault((r["wave"], r["tier"]), [0, 0])
        total[(r["wave"], r["tier"])][0] += 1
        total[(r["wave"], r["tier"])][1] += r["size"]
    for (w, t), (n, s) in sorted(total.items()):
        print(f"wave {w} {t:9s} files {n:3d} {s / 1e9:8.1f} GB")
    print("held:", [(h["model_id"], h["version_id"]) for h in held], "| removed:", [(x["model_id"], x["version_id"]) for x in removed])
    print("not_on_server:", [x["comfy_file"] for x in not_on_server])
    if a.write:
        (ROOT / "config").mkdir(exist_ok=True)
        (ROOT / "config" / "server_model_lock.json").write_text(json.dumps(lock, indent=1, ensure_ascii=True) + "\n")
        (ROOT / "config" / "llm_models.json").write_text(json.dumps(reg, indent=1, ensure_ascii=True) + "\n")
        print("wrote config/server_model_lock.json and config/llm_models.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
