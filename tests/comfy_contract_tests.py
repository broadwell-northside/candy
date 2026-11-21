"""Mock tests for the ComfyUI 0.43 client contract.

A job is done only when history says success and completed and a saved file is
present. SaveVideo is an images entry with the animated flag and a video
container. Cancel is POST /api/jobs/{prompt_id}/cancel with no /interrupt
fallback. A timeout reads that prompt's history and does not submit again.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
import comfy_client as cc  # noqa: E402


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _still(prefix):
    return {"1": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": prefix}}}


def _video(prefix):
    fmt = "mp4"
    for ext in ("mkv", "webm", "mov", "mp4"):
        if prefix.endswith(ext):
            fmt = ext
            break
    return {"1": {"class_type": "SaveVideo",
                  "inputs": {"video": ["1", 0], "filename_prefix": prefix, "format": fmt}}}


def _hist(filename, animated=False, status="success", completed=True, key="images"):
    node = {key: [{"filename": filename, "subfolder": "easy_studio", "type": "output"}]}
    if animated is True:
        node["animated"] = [True]
    elif animated == "bool":
        node["animated"] = True
    return {"outputs": {"9": node}, "status": {"status_str": status, "completed": completed, "messages": []}}


def _unit(check):
    still = _hist("still.png")
    check("a still is done only with success, completed, and a saved file", cc.job_succeeded(still))
    check("success without completed is not done", not cc.job_succeeded(_hist("still.png", completed=False)))
    check("completed without success is not done",
          not cc.job_succeeded({"outputs": still["outputs"], "status": {"completed": True, "messages": []}}))
    check("a history record that only has executing.node null is not done",
          not cc.job_succeeded({"status": {"executing": {"node": None}}, "outputs": still["outputs"]}))
    for ext in (".mp4", ".mkv", ".webm", ".mov"):
        hist = _hist("clip" + ext, animated=True)
        saved = cc.saved_output_files(hist["outputs"]["9"])
        check(f"SaveVideo {ext} is an animated images entry",
              cc.job_succeeded(hist) and saved and saved[0]["filename"].endswith(ext))
    png = _hist("clip.png", animated=True)
    check("an animated PNG is not a saved video",
          cc.saved_output_files(png["outputs"]["9"]) == [] and not cc.job_succeeded(png))
    check("animated PNG is named in the failure", "Animated PNG" in cc.job_failure_message(png))
    bool_flag = _hist("clip.webm", animated="bool")
    check("animated true (not a list) still counts", cc.job_succeeded(bool_flag))
    preview = {"outputs": {"1": {"images": [{"filename": "preview.png", "type": "temp"}]}},
               "status": {"status_str": "success", "completed": True}}
    check("a temp still preview is not a saved file", not cc.job_succeeded(preview))
    glb = _hist("model.glb", key="3d")
    check("a saved 3D file can complete a job", cc.job_succeeded(glb))
    failed = _hist("clip.mp4", animated=True, status="error", completed=False)
    failed["status"]["messages"] = [["execution_error", {"node_type": "SaveVideo", "exception_message": "disk full"}]]
    check("an error history is not success, even with a video file", not cc.job_succeeded(failed))
    check("an error history keeps the engine message", "disk full" in cc.job_failure_message(failed))


class _Mock:
    def __init__(self, extra_env=None):
        self.port = _free_port()
        env = dict(os.environ)
        env.pop("MOCK_NO_CANCEL", None)
        if extra_env:
            env.update(extra_env)
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "mock_comfy.py"), str(self.port)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        self.url = f"http://127.0.0.1:{self.port}"
        self.client = cc.ComfyClient(self.url)
        for _ in range(50):
            try:
                if requests.get(self.url + "/system_stats", timeout=0.5).ok:
                    return
            except requests.RequestException:
                time.sleep(0.05)
        raise RuntimeError("mock ComfyUI did not start: " + self._log())

    def _log(self):
        try:
            return (self.proc.stdout.read() if self.proc.stdout else "")[:500]
        except Exception:
            return ""

    def control(self):
        return requests.get(self.url + "/mock/control", timeout=5).json()

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _raises(check, name, fn, contains):
    try:
        fn()
    except cc.ComfyError as e:
        check(name, all(part in str(e) for part in contains), str(e))
        return str(e)
    check(name, False, "no error")
    return ""


def _live(check):
    mock = _Mock()
    try:
        before = mock.control()["prompts"]
        dest = tempfile.mkdtemp(prefix="es_contract_")
        paths = mock.client.run(_still("easy-studio/still"), dest)
        hist_prompts = mock.control()["prompts"]
        check("mock still is done with a saved png",
              paths and os.path.exists(paths[0]) and paths[0].endswith(".png") and hist_prompts == before + 1,
              paths)

        before = mock.control()["prompts"]
        dest = tempfile.mkdtemp(prefix="es_contract_")
        paths = mock.client.run(_still("es_contract_early_null"), dest, )
        check("executing.node null before history is not treated as done",
              paths and paths[0].endswith(".png") and mock.control()["prompts"] == before + 1, paths)

        for ext in (".mp4", ".mkv", ".webm", ".mov"):
            before = mock.control()["prompts"]
            dest = tempfile.mkdtemp(prefix="es_contract_")
            paths = mock.client.run(_video("es_contract_" + ext[1:]), dest)
            check(f"mock SaveVideo downloads {ext}",
                  paths and paths[0].lower().endswith(ext) and os.path.getsize(paths[0]) > 0
                  and mock.control()["prompts"] == before + 1, paths)

        before = mock.control()["prompts"]
        _raises(check, "mock animated PNG is rejected",
                lambda: mock.client.run(_video("es_contract_png"), tempfile.mkdtemp(prefix="es_contract_")),
                ["Animated PNG", ".png"])
        check("rejecting an animated PNG does not submit again", mock.control()["prompts"] == before + 1)

        before = mock.control()["prompts"]
        _raises(check, "success without a saved file is not done",
                lambda: mock.client.wait(mock.client.queue(_still("es_contract_nofile")), max_wait=3),
                ["no saved output file"])
        check("a no-file result does not submit again", mock.control()["prompts"] == before + 1)

        before = mock.control()["prompts"]
        pid = mock.client.queue(_still("es_contract_not_completed"))
        _raises(check, "success that is not completed is not done, even if node is null",
                lambda: mock.client.wait(pid, max_wait=0.6),
                ["not submitted again"])
        check("an unfinished prompt is not submitted again", mock.control()["prompts"] == before + 1)

        before = mock.control()["prompts"]
        _raises(check, "node null plus an error history is not success",
                lambda: mock.client.wait(mock.client.queue(_still("es_contract_error")), max_wait=3),
                ["disk full"])
        check("an error result does not submit again", mock.control()["prompts"] == before + 1)

        before = mock.control()["prompts"]
        reads = len(mock.control()["history_reads"])
        pid = mock.client.queue(_still("es_contract_null_only"))
        _raises(check, "node null with no history is a timeout, not success",
                lambda: mock.client.wait(pid, max_wait=0.6),
                ["Timed out", "not submitted again", pid])
        ctrl = mock.control()
        check("that timeout read the prompt history and did not submit again",
              ctrl["prompts"] == before + 1 and pid in ctrl["history_reads"][reads:], ctrl)

        before = mock.control()["prompts"]
        pid = mock.client.queue(_still("es_contract_slow"))
        _raises(check, "a timeout reads history and does not resubmit",
                lambda: mock.client.wait(pid, max_wait=0.4),
                ["Timed out", "not submitted again", pid])
        ctrl = mock.control()
        check("the slow prompt was read and left as one submission",
              ctrl["prompts"] == before + 1 and pid in ctrl["history_reads"], ctrl)

        pid = mock.client.queue(_still("easy-studio/recover"))
        late = {}
        for _ in range(80):
            body = requests.get(mock.url + "/history/" + pid, timeout=2).json()
            if body.get(pid, {}).get("status", {}).get("completed") is True:
                late = body[pid]
                break
            time.sleep(0.05)
        prompts = mock.control()["prompts"]
        got = mock.client.wait(pid, max_wait=0)
        check("when the timeout read finds a finished prompt, it is returned and not submitted again",
              cc.job_succeeded(got) and got.get("outputs") == late.get("outputs") and mock.control()["prompts"] == prompts,
              got.get("status"))

        before = mock.control()
        pid = mock.client.queue(_still("es_contract_slow_cancel"))
        body = mock.client.cancel(pid)
        ctrl = mock.control()
        check("cancel posts /api/jobs/{prompt_id}/cancel",
              ctrl["cancels"] and ctrl["cancels"][-1] == f"/api/jobs/{pid}/cancel" and body.get("cancelled") is True,
              ctrl["cancels"])
        check("cancel does not fall back to /interrupt or resubmit",
              ctrl["interrupts"] == before["interrupts"] == [] and ctrl["prompts"] == before["prompts"] + 1, ctrl)
        mock.client.interrupt()
        ctrl = mock.control()
        check("the old interrupt name still uses the per-job route",
              ctrl["cancels"][-1] == f"/api/jobs/{pid}/cancel" and ctrl["interrupts"] == [])
    finally:
        mock.close()

    missing = _Mock({"MOCK_NO_CANCEL": "1"})
    try:
        before = missing.control()
        pid = missing.client.queue(_still("es_contract_slow_missing"))
        _raises(check, "a missing cancel route is reported",
                lambda: missing.client.cancel(pid),
                ["no per-job cancel route", "404", "No global /interrupt"])
        ctrl = missing.control()
        check("a missing cancel route does not call /interrupt or resubmit",
              ctrl["interrupts"] == [] and ctrl["cancels"] == before["cancels"] and ctrl["prompts"] == before["prompts"] + 1,
              ctrl)
    finally:
        missing.close()


def run(check):
    print("\n[2b] ComfyUI 0.43 client contract")
    _unit(check)
    _live(check)


if __name__ == "__main__":
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"   <-- {detail}"))
        return cond

    run(check)
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} contract checks passed")
    sys.exit(1 if bad else 0)
