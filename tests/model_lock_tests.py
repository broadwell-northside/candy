# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Offline checks of the one model lock (config/server_model_lock.json) and the Director registry.

No network, no weights. Run by tests/run_tests.py; also: python tests/model_lock_tests.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
LOCK = os.path.join(ROOT, "config", "server_model_lock.json")
LLM = os.path.join(ROOT, "config", "llm_models.json")
ALLOWLIST = os.path.join(ROOT, "app", "lora_allowlist.json")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MODEL_EXT = re.compile(r"\.(safetensors|gguf|pth|pt|ckpt|bin|onnx|task)$")
SAFE_DEST = re.compile(r"^[A-Za-z0-9._/+-]+$")
NAME_FIELDS = ("file_name", "trigger_words", "trained_words", "title", "description", "name")


def template_files():
    refs = {}
    keys = ("unet_name", "ckpt_name", "clip_name", "clip_name1", "clip_name2", "vae_name", "lora_name",
            "model_name", "control_net_name", "name", "upscale_model", "model")
    folder = os.path.join(ROOT, "app", "workflows")
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".json"):
            continue
        wf = json.load(open(os.path.join(folder, fname), encoding="utf-8"))
        for node in (wf.values() if isinstance(wf, dict) else wf):
            ins = node.get("inputs") if isinstance(node, dict) else None
            if isinstance(ins, dict):
                for key in keys:
                    value = ins.get(key)
                    if isinstance(value, str) and MODEL_EXT.search(value):
                        refs.setdefault(os.path.basename(value), set()).add(fname)
    return refs


PAIRS = json.load(open(os.path.join(ROOT, "config", "lora_pairs.json"), encoding="utf-8"))["pairs"]


def unit(check):
    print("\n[lock] Model lock and Director registry")
    lock = json.load(open(LOCK, encoding="utf-8"))
    rows = lock["rows"]
    check("the lock uses the kit's row format", lock.get("schema") == "turin.server_model_lock/1" and rows)
    ids = [r["id"] for r in rows]
    check("lock ids are unique", len(ids) == len(set(ids)))
    for r in rows:
        ok = (isinstance(r.get("wave"), int) and 1 <= r["wave"] <= 4 and r["url"].startswith("https://")
              and isinstance(r.get("size"), int) and r["size"] > 0 and HEX64.match(r.get("sha256", "")))
        if "huggingface.co/" in r["url"]:
            m = re.search(r"/resolve/([^/]+)/", r["url"])
            ok = ok and bool(m and HEX40.match(m.group(1)))
        dest = r["dest"]
        ok = ok and SAFE_DEST.match(dest) and not dest.startswith("/") and ".." not in dest.split("/") and dest.isascii()
        if not ok:
            check("row is pinned, hashed, sized and has a safe ASCII destination: " + r["id"], False)
    check("every row is pinned, hashed, sized and has a safe ASCII destination", True)
    paths = {}
    for r in rows:
        link = r.get("comfy_link")
        if link:
            paths.setdefault((link["type"], link["name"]), set()).add(r["sha256"])
    check("one ComfyUI path never maps to two different files", all(len(v) == 1 for v in paths.values()))
    locked = {name for (_t, name) in paths}
    listed = {x["comfy_file"] for x in lock.get("not_on_server", []) if x.get("reason")}
    missing = sorted(f for f in template_files() if f not in locked and f not in listed)
    check("every file a template loads is locked or listed with a reason", not missing, missing[:5])
    loras = [r for r in rows if r["id"].startswith("lora.")]
    check("LoRA rows carry no catalog names, file names or trigger words",
          all(not any(k in r for k in NAME_FIELDS) and r["label"] == r["id"] for r in loras))
    check("LoRA files get ID-based names", all(re.fullmatch(r"comfy/loras/[a-z0-9_]+/[a-z_]+/\d+_\d+\.safetensors", r["dest"]) for r in loras))
    wan = [r for r in loras if r["family"] == "wan22_a14b"]
    pairs = {}
    for r in wan:
        if r.get("pairing") == "paired":
            pairs.setdefault(r["pair_id"], []).append(r)
    check("every paired Wan 14B LoRA has exactly one high and one low half under one pair id",
          all(sorted(x["half"] for x in v) == ["high", "low"] and len({x["civitai"]["model_id"] for x in v}) == 1
              for v in pairs.values()) and pairs)
    check("every Wan 14B LoRA is paired with its sibling half: 11 pairs, 22 rows (D-C-20)",
          all(r.get("pairing") == "paired" for r in wan) and len(pairs) == 11 and len(wan) == 22,
          [r["id"] for r in wan if r.get("pairing") != "paired"][:3])
    removed = {x["model_id"] for x in lock.get("removed", [])}
    lora_models = {r["civitai"]["model_id"] for r in loras}
    out = {2027766, 1822984, 2268008, 1959747}
    check("2027766, 1822984, 2268008 and 1959747 are removed (C-LORA-01, D-C-16, D-C-19)",
          out <= removed and not (out & lora_models))
    sibling_ids = {p["sibling"]["version_id"] for p in PAIRS if p.get("sibling")}
    listed = [r for r in loras if r["civitai"]["version_id"] not in sibling_ids]
    check("38 of Grok's 42 LoRAs stay, plus the Wan 14B sibling halves", len(listed) == 38, len(listed))
    check("49 LoRA rows: Grok's 38 kept plus all 11 Wan 14B sibling halves", len(loras) == 49, len(loras))
    allow = {(e["version_id"], e["sha256"]) for e in json.load(open(ALLOWLIST, encoding="utf-8"))["entries"]}
    waived = [r for r in loras if r.get("import_check") == "allowlisted_exact_sha256_d_c_18"]
    check("the 12 LoRAs that pass only by Ak's allowlist match it by exact version and SHA256 (D-C-18, D-C-20)",
          len(waived) == 12 and all((r["civitai"]["version_id"], r["sha256"]) in allow for r in waived), len(waived))
    allowed_vids = {v for v, _ in allow}
    check("a Wan 14B half is on the allowlist only together with its partner half",
          all((p["version_id"] in allowed_vids) == (p["sibling"]["version_id"] in allowed_vids) for p in PAIRS))
    check("no row comes from the parked Me path", not any("liveness" in r["dest"] or "face_landmarker" in r["dest"] for r in rows))
    check("the automatic age check model is on the server", any(r["family"] == "safety" for r in rows))
    blob = open(LOCK, encoding="utf-8").read()
    check("no token or secret reference in the lock",
          "op://" not in blob and "Bearer" not in blob and not re.search(r"\bhf_[A-Za-z0-9]{20,}", blob))
    reg = json.load(open(LLM, encoding="utf-8"))
    profiles = reg["profiles"]
    check("no remote or paid profile in the registry", not any(p.get("remote") for p in profiles) and "op://" not in json.dumps(reg))
    by_id = {r["id"]: r for r in rows}
    check("every enabled Director profile has its files in the lock",
          all(p.get("lock_ids") and all(i in by_id for i in p["lock_ids"]) for p in profiles if p.get("enabled")))
    check("the default Director profile is enabled", any(p["id"] == reg["default_profile"] and p.get("enabled") for p in profiles))
    deepseek = {p["id"]: p for p in profiles if p["id"].startswith("deepseek_v41_flash_1017_")}
    check("both DeepSeek V4.1 Flash 1017 builds stay enabled for the bake-off (Ak)",
          deepseek.get("deepseek_v41_flash_1017_uncensored_gsq_iq2xxs", {}).get("enabled") is True
          and deepseek.get("deepseek_v41_flash_1017_abliterated_iq1s_lora", {}).get("enabled") is True)
    strata = lock.get("runtimes", {}).get("strata", {})
    check("the Strata runtime is pinned to a commit and marked hardware_pending",
          HEX40.match(strata.get("commit", "")) and strata.get("status") == "hardware_pending")


if __name__ == "__main__":
    failed = []

    def _check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {extra}"))
        if not cond:
            failed.append(name)
    unit(_check)
    sys.exit(1 if failed else 0)
