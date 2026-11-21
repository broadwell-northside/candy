"""First real GPU check. Run on the desktop while Easy Studio and ComfyUI are up.

    python setup/gpu_smoke.py --out path/to/report.md

It makes one adult fictional portrait (jeans and a t-shirt, not an explicit picture),
a 2 second video, one extend, and one game-quality 3D model. It records time and the
highest VRAM it saw. It does not print or save the app password.

    python setup/gpu_smoke.py --self-test

Stop at the first failed step. Post the report on GitHub issue #1. Do not commit
pictures, videos, or the 3D file.
"""
import argparse
import os
import re
import subprocess
import sys
import time

import requests

APP = os.environ.get("EASY_STUDIO_URL", "http://127.0.0.1:7860")
SECRET_MARK = os.environ.get("EASY_STUDIO_PASSWORD", "")


def _headers():
    return {"X-Easy-Studio": "1"}


def _auth():
    pw = os.environ.get("EASY_STUDIO_PASSWORD") or ""
    if not pw or pw.lower() == "off":
        return None
    return ("owner", pw)


def _vram():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=20)
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


def _job(session, kind, params, timeout):
    t0 = time.time()
    peak = _vram()
    r = session.post(APP + "/api/jobs", json={"kind": kind, "params": params}, timeout=60)
    if r.status_code != 200:
        return {"status": "FAIL", "seconds": round(time.time() - t0, 1), "vram_mib": peak,
                "detail": r.text[:300]}
    jid = r.json()["id"]
    while time.time() - t0 < timeout:
        time.sleep(2)
        used = _vram()
        if used is not None:
            peak = used if peak is None else max(peak, used)
        j = session.get(APP + f"/api/jobs/{jid}", timeout=30).json()
        if j["status"] in ("done", "error", "cancelled", "blocked_age_check_unavailable"):
            return {"status": "PASS" if j["status"] == "done" else "FAIL",
                    "seconds": round(time.time() - t0, 1), "vram_mib": peak,
                    "detail": j.get("error") or j.get("message") or "",
                    "results": j.get("results") or []}
    return {"status": "FAIL", "seconds": timeout, "vram_mib": peak, "detail": "timed out"}


def _redact(text):
    text = text or ""
    if SECRET_MARK and SECRET_MARK.lower() != "off":
        text = text.replace(SECRET_MARK, "[redacted]")
    text = re.sub(r"(?i)(password|token|api[_-]?key|cookie)\s*[:=]\s*\S+", r"\1: [redacted]", text)
    return text


def report(steps):
    lines = [
        "ES-SETUP-GPU-SMOKE",
        "Sender: Codex",
        "Status: " + ("READY_FOR_INGEST" if all(s["status"] == "PASS" for s in steps) else "BLOCKED"),
        "Scope: first GPU smoke (one image, 2 second video, one extend, one 3D model)",
        "Evidence commit: n/a",
        "",
        "No pictures are attached. Password and tokens are not included.",
        "",
        "| Step | Result | Seconds | Peak VRAM MiB | Notes |",
        "|---|---|---|---|---|",
    ]
    for s in steps:
        lines.append("| {name} | {status} | {seconds} | {vram} | {detail} |".format(
            name=s["name"], status=s["status"], seconds=s.get("seconds", ""),
            vram=s.get("vram_mib") if s.get("vram_mib") is not None else "",
            detail=_redact(s.get("detail") or "").replace("|", "/")))
    lines.append("")
    lines.append("Completion: posted on issue #1. Generated files stay in outputs/ and are not committed.")
    return "\n".join(lines) + "\n"


def run():
    s = requests.Session()
    s.headers.update(_headers())
    s.auth = _auth()
    steps = []
    dna = {"gender": "woman", "age": 28, "style": "photo", "name": "Mara",
           "traits": {"hair_color": "brown", "body": "average"}}
    image = _job(s, "create", {"dna": dna, "count": 2, "outfit": "jeans_tee", "scene": "studio"}, 1200)
    image["name"] = "image"
    steps.append(image)
    if image["status"] != "PASS" or not image.get("results"):
        return steps
    iid = image["results"][0]["id"]
    other = image["results"][1]["id"]
    video = _job(s, "video", {"image": iid, "motion": "wind", "seconds": 2, "qc": {
        "variants": [
            {"image": iid, "scores": {"hands": 8, "anatomy": 8, "contact": 8, "skin": 7, "lighting": 7}},
            {"image": other, "scores": {"hands": 5, "anatomy": 4, "contact": 4, "skin": 6, "lighting": 6}},
        ]}}, 1800)
    video["name"] = "video"
    steps.append(video)
    if video["status"] != "PASS" or not video.get("results"):
        return steps
    vid = video["results"][0]["id"]
    ext = _job(s, "extend", {"video": vid, "motion": "look", "seconds": 2}, 1800)
    ext["name"] = "extend"
    steps.append(ext)
    if ext["status"] != "PASS":
        return steps
    model = _job(s, "model3d", {"image": iid, "quality": "game"}, 1800)
    model["name"] = "3d"
    steps.append(model)
    return steps


def self_test():
    os.environ["EASY_STUDIO_PASSWORD"] = "smoke-secret-value"
    global SECRET_MARK
    SECRET_MARK = "smoke-secret-value"
    text = report([
        {"name": "image", "status": "PASS", "seconds": 12, "vram_mib": 20000, "detail": "ok"},
        {"name": "video", "status": "FAIL", "seconds": 3, "vram_mib": 1000,
         "detail": "password: smoke-secret-value token=abc"},
    ])
    assert "smoke-secret-value" not in text
    assert "[redacted]" in text
    assert "ES-SETUP-GPU-SMOKE" in text
    assert "BLOCKED" in text
    print("gpu_smoke self-test passed")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    steps = run()
    text = report([{k: v for k, v in s.items() if k != "results"} for s in steps])
    print(text)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "w", encoding="utf-8").write(text)
    return 0 if steps and all(s["status"] == "PASS" for s in steps) else 1


if __name__ == "__main__":
    sys.exit(main())
