"""Automatic age check (on by default; Settings can switch it off -- not recommended).

While the checker is off, this check refuses to run. Create, video, train, and export
will not run either. A switched-off check does not produce a usable result.

Every new picture (and 3 frames of every new video) is looked at by a small local face finder + age
classifier running in ComfyUI's Python (see workers/age_check_worker.py). If any face looks under 21
(P(child) + P(teenager) >= threshold), the result is DELETED: nothing is saved, nothing is shown (never blurred),
and the job says so and offers a retry with a new seed (D-C-51). In the 18+ section that is final (D-C-49a).

Honest limits: it is a helper, not a guarantee. The age model's teen recall is about 0.70 on its own
test set (so it misses some), it can wrongly flag young-looking adults, and faces it can't find (back
views, many anime styles, tiny faces) come back "unchecked". The text rules in safety.py still apply.
"""
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
def worker_path():
    """The age-check worker. A stand-in can be named by EASY_STUDIO_AGE_WORKER in a test run only (EASY_STUDIO_TEST_RUN=1)."""
    if os.environ.get("EASY_STUDIO_TEST_RUN") == "1" and os.environ.get("EASY_STUDIO_AGE_WORKER"):
        return os.environ["EASY_STUDIO_AGE_WORKER"]
    return os.path.join(HERE, "workers", "age_check_worker.py")


WORKER = worker_path()

# Appearance-checker outcome. This is not a declared age.
BLOCKED_AGE_CHECK = "blocked_age_check_unavailable"
_CHECKER_FAILURES = {"unavailable", "error", "timeout", BLOCKED_AGE_CHECK}
CHECKER_OFF_REASON = "The appearance checker is off, so this will not run."
CHECKER_REQUIRED_KINDS = frozenset({
    "create", "video", "video_any", "extend", "video_still",
    "train_dataset", "train_lora", "export", "export_godot",
    "workshop_still", "keep_face", "refine_skin", "refine_anatomy", "film",
    "lora_benchmark", "workshop_train", "workshop_me_train",
    "creator_outfit",
    "owner_train", "owner_train_selftest", "owner_picture", "video_api",
})
# Fail closed: these are the only kinds that run while the checker is off, frozen as they were on
# Nov 5, 2026. A job kind in neither set is refused while the checker is off. A new kind joins
# CHECKER_REQUIRED_KINDS in the same change that adds it (tests/rails_tests.py checks every kind).
CHECKER_FREE_KINDS = frozenset({
    "edit", "inpaint", "outfit_locked", "contact_repair", "regenerate", "remove_bg", "bg_quick",
    "upscale", "pose_extract", "pose_new", "model3d", "photoshoot", "turnaround", "expressions",
    "sprites", "raw", "prop",
})


def checker_blocks(kind, checker_enabled):
    """True when this kind must not run because the appearance checker is off."""
    if checker_enabled:
        return False
    return kind in CHECKER_REQUIRED_KINDS or kind not in CHECKER_FREE_KINDS


class AgeCheckBlocked(Exception):
    """The appearance checker could not clear a result, so it is held."""

    status = BLOCKED_AGE_CHECK


DISCARDED = ("The age check flagged a result as possibly under 21, so it was deleted. Nothing was saved and nothing "
             "was shown. You can try again with a new seed.")
DISCARDED_NO_SEED = ("The age check flagged a result as possibly under 21, so it was deleted. Nothing was saved and "
                     "nothing was shown. This tool has no seed to change, so change the wording or the picture you "
                     "started from before you try again.")


class AgeCheckDiscarded(Exception):
    """The age check flagged a result and it was deleted (D-C-51). Not the checker-unavailable case: the job ends as an
    ordinary error with this plain message. can_retry says the page may offer a retry with a new seed (False for a
    tool that has no seed to change)."""

    def __init__(self, message=DISCARDED, can_retry=True):
        super().__init__(message)
        self.can_retry = bool(can_retry)


def held_unusable(result):
    """True when a required check held the result and it must not be saved or reused.

    A flagged result is deleted before it is saved. An older item that still carries the flag (made before D-C-51)
    stays blocked here.
    off, unchecked, unavailable, error, and timeout holds are not usable publications.
    """
    if not isinstance(result, dict):
        return True
    status = result.get("status")
    appearance = result.get("appearance_check") if isinstance(result.get("appearance_check"), dict) else {}
    if status == "off" or appearance.get("status") == "off":
        return True
    if status in ("ok", "flag"):
        return False
    if result.get("held") or appearance.get("held"):
        return True
    return status in ("unchecked", "unavailable", "error", "timeout", BLOCKED_AGE_CHECK)


def saved_blocked(item):
    """True when a saved item must not be reused, trained on, or exported."""
    if not isinstance(item, dict):
        return True
    appearance = item.get("appearance_check") if isinstance(item.get("appearance_check"), dict) else {}
    if item.get("age_flag"):
        return True
    return held_unusable({
        "status": item.get("age_check") or appearance.get("status"),
        "held": item.get("held"),
        "appearance_check": appearance,
    })


def appearance_result(status, **fields):
    """Checker status only. Declared ages are not stored here."""
    kept = {key: value for key, value in fields.items() if key not in ("age", "stated_age", "stated_ages")}
    kept["status"] = status
    return kept


def gate(result):
    """Map one checker answer. Unavailable, error, and timeout are held, never passed."""
    if not isinstance(result, dict):
        reason = "age checker returned no result"
        return {
            "status": BLOCKED_AGE_CHECK, "held": True, "cause": "error", "reason": reason,
            "appearance_check": appearance_result(BLOCKED_AGE_CHECK, held=True, cause="error", reason=reason),
        }
    status = result.get("status")
    if status == "off":
        reason = result.get("reason") or CHECKER_OFF_REASON
        cause = result.get("cause") or "checker_off"
        appearance = appearance_result("off", held=True, reason=reason, cause=cause)
        return {"status": "off", "held": True, "cause": cause, "reason": reason, "appearance_check": appearance}
    if status == "ok":
        appearance = appearance_result("ok", held=False, faces=result.get("faces"), p_under21=result.get("p_under21"))
        return {**result, "held": False, "appearance_check": appearance}
    if status == "flag":
        appearance = appearance_result("flag", held=True, faces=result.get("faces"), p_under21=result.get("p_under21"),
                                       reason=result.get("reason") or "")
        return {**result, "held": True, "appearance_check": appearance}
    if status == "unchecked":
        appearance = appearance_result("unchecked", held=True, faces=result.get("faces"), reason=result.get("reason") or "")
        return {**result, "held": True, "appearance_check": appearance}
    cause = result.get("cause") or ("timeout" if status == "timeout" else "error" if status == "error" else "unavailable")
    reason = result.get("reason") or "age checker unavailable"
    appearance = appearance_result(BLOCKED_AGE_CHECK, held=True, cause=cause, reason=reason)
    return {"status": BLOCKED_AGE_CHECK, "held": True, "cause": cause, "reason": reason, "appearance_check": appearance}


def aggregate_frame_checks(frames):
    """Keep every frame. One passing frame does not hide a failed or unchecked one.

    The result is held when any required frame failed or could not be checked.
    """
    kept = []
    for index, frame in enumerate(frames or []):
        if not isinstance(frame, dict):
            row = gate({"status": "error", "reason": "frame check missing", "cause": "frame_extraction"})
        else:
            row = gate(frame)
        row = dict(row)
        row["index"] = frame.get("index", index) if isinstance(frame, dict) else index
        kept.append(row)
    if not kept:
        blocked = gate({"status": "error", "reason": "no frames were checked", "cause": "frame_extraction"})
        blocked["frames"] = []
        blocked["failures"] = [blocked["appearance_check"]]
        return blocked
    off = [row for row in kept if row.get("status") == "off"]
    if off:
        reason = off[0].get("reason") or CHECKER_OFF_REASON
        appearance = appearance_result("off", held=True, frames=kept, failures=off, reason=reason, cause="checker_off")
        return {"status": "off", "held": True, "cause": "checker_off", "reason": reason,
                "frames": kept, "failures": off, "appearance_check": appearance}
    failures = [row for row in kept if row.get("status") in _CHECKER_FAILURES or row.get("cause") == "frame_extraction"
                or row.get("status") == "unchecked" or row.get("status") == "flag"]
    hard = [row for row in kept if row.get("status") == BLOCKED_AGE_CHECK or row.get("cause") == "frame_extraction"]
    if hard:
        reasons = [row.get("reason") or row.get("status") for row in hard]
        appearance = appearance_result(BLOCKED_AGE_CHECK, held=True, frames=kept, failures=hard, reason="; ".join(reasons))
        return {"status": BLOCKED_AGE_CHECK, "held": True, "cause": hard[0].get("cause") or "unavailable",
                "reason": "; ".join(reasons), "frames": kept, "failures": hard, "appearance_check": appearance}
    flagged = [row for row in kept if row.get("status") == "flag"]
    if flagged:
        appearance = appearance_result("flag", held=True, frames=kept, failures=flagged,
                                       p_under21=max((row.get("p_under21") or 0) for row in flagged))
        return {"status": "flag", "held": True, "frames": kept, "failures": flagged, "appearance_check": appearance,
                "p_under21": appearance.get("p_under21")}
    unchecked = [row for row in kept if row.get("status") == "unchecked"]
    if unchecked:
        reasons = []
        for row in unchecked:
            reasons.append(row.get("reason") or "A required frame could not be checked.")
        reason = "; ".join(dict.fromkeys(reasons))
        appearance = appearance_result("unchecked", held=True, frames=kept, failures=unchecked, reason=reason)
        return {"status": "unchecked", "held": True, "frames": kept, "failures": unchecked, "appearance_check": appearance,
                "reason": reason}
    appearance = appearance_result("ok", held=False, frames=kept, failures=[])
    return {"status": "ok", "held": False, "frames": kept, "failures": [], "appearance_check": appearance}


class AgeGuard:
    def __init__(self, model_dir, python=None, threshold=0.5, enabled=True):
        self.model_dir = model_dir
        self.python = python or sys.executable
        self.threshold = threshold
        self.enabled = enabled
        self.proc = None
        self.lock = threading.Lock()
        self.last_error = ""
        self.device = None

    def installed(self):
        need = ["model.safetensors", "config.json", "preprocessor_config.json",
                os.path.join("torch", "hub", "checkpoints", "yunet_final.pth")]
        return bool(self.model_dir) and all(os.path.exists(os.path.join(self.model_dir, n)) for n in need)

    def status(self):
        return {"enabled": self.enabled, "installed": self.installed(), "running": bool(self.proc and self.proc.poll() is None),
                "device": self.device, "error": self.last_error, "threshold": self.threshold}

    def _kill(self):
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None

    def _read_line(self, timeout):
        box = {}

        def read():
            try:
                box["line"] = self.proc.stdout.readline()
            except Exception as exc:
                box["err"] = exc

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError("age checker timed out")
        if box.get("err"):
            raise box["err"]
        line = box.get("line") or ""
        if not str(line).strip():
            raise RuntimeError("age checker returned nothing")
        return line

    def _start(self, timeout=60):
        env = dict(os.environ, TORCH_HOME=os.path.join(self.model_dir, "torch"), HF_HUB_OFFLINE="1",
                   TRANSFORMERS_OFFLINE="1", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen([self.python, WORKER, self.model_dir, str(self.threshold)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env, bufsize=1)
        line = self._read_line(timeout)
        try:
            hello = json.loads(line)
        except ValueError:
            hello = {}
        if not hello.get("ready"):
            self._kill()
            raise RuntimeError("The age checker didn't start (is ComfyUI's Python set up? see COMFY_PYTHON).")
        self.device = hello.get("device")

    def _ask(self, path, timeout):
        if not self.proc or self.proc.poll() is not None:
            self._start(timeout=timeout)
        self.proc.stdin.write(json.dumps({"path": os.path.abspath(path)}) + "\n")
        self.proc.stdin.flush()
        return json.loads(self._read_line(timeout))

    def check(self, path, timeout=60):
        """Appearance check. Unavailable, error, and timeout are held and never passed.

        The returned appearance_check object is only the checker status. It is not a declared age.
        """
        if not self.enabled:
            return gate({"status": "off", "reason": CHECKER_OFF_REASON, "cause": "checker_off"})
        if not self.installed():
            return gate({"status": "unavailable", "reason": "age checker not installed", "cause": "missing_dependency"})
        with self.lock:
            try:
                ans = self._ask(path, timeout)
                self.last_error = ""
                return gate(ans)
            except TimeoutError as e:
                self.last_error = str(e)
                self._kill()
                return gate({"status": "timeout", "reason": str(e), "cause": "timeout"})
            except Exception as e:
                self.last_error = str(e)
                self._kill()
                try:
                    ans = self._ask(path, timeout)
                    self.last_error = ""
                    return gate(ans)
                except TimeoutError as e2:
                    self.last_error = str(e2)
                    self._kill()
                    return gate({"status": "timeout", "reason": str(e2), "cause": "timeout"})
                except Exception as e2:
                    self.last_error = str(e2)
                    self._kill()
                    return gate({"status": "error", "reason": str(e2), "cause": "error"})

    def stop(self):
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass
            self.proc = None


def check_video(guard, video_path, tmp_dir, ffmpeg):
    """Check the first, middle, and last frame. Every failure is kept.

    One passing frame does not hide a later failure, and a failure is not
    rewritten as unchecked. If any required frame failed or could not be
    checked, the video is held.
    """
    import video_tools as V
    try:
        info = V.probe(video_path)
        n = max(1, int(info.get("frames") or 0))
    except Exception as e:
        return aggregate_frame_checks([{
            "status": "error", "cause": "frame_extraction",
            "reason": f"frame extraction failed: {e}",
        }])
    frames = []
    for i, idx in enumerate(sorted({0, n // 2, max(0, n - 1)})):
        fp = os.path.join(tmp_dir, f"agecheck_{os.getpid()}_{i}.png")
        try:
            subprocess.run([ffmpeg, "-y", "-v", "error", "-i", video_path, "-vf", f"select=eq(n\\,{idx})", "-frames:v", "1", fp],
                           check=True, capture_output=True, timeout=120)
            if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                raise RuntimeError(f"frame extraction produced no file for frame {idx}")
            try:
                answer = guard.check(fp)
            except TimeoutError as e:
                answer = {"status": "timeout", "cause": "timeout", "reason": str(e)}
            if not isinstance(answer, dict):
                answer = {"status": "error", "cause": "error", "reason": "age checker returned no result"}
        except subprocess.TimeoutExpired as e:
            answer = {"status": "timeout", "cause": "timeout", "reason": f"frame extraction timed out: {e}"}
        except Exception as e:
            answer = {"status": "error", "cause": "frame_extraction", "reason": f"frame extraction failed: {e}"}
        finally:
            if os.path.exists(fp):
                os.remove(fp)
        answer = dict(answer)
        answer["index"] = idx
        frames.append(answer)
    return aggregate_frame_checks(frames)
