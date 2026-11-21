"""The policy gate: the third layer of D-C-50, for the gray zone only.

The layers: (1) a hard floor fixed in SAFETY.md and in code (safety.py, age_guard.py, the pipelines): minors, real
people, identity-copy tools, violence and the floor categories, the output age check; (2) wide leeway for everything
else, where the app refuses nothing by default; (3) this gate. The owner keeps a plain text file ("what I don't want")
in his own data folder; a gate on his own machine reads it and the job's text, decides, and the reason is logged.

What the file can and cannot do (D-C-49a, D-C-50):
  * It is only ever handed to the gate as text. No line of it is parsed as a command, so no line can switch anything off.
  * The fixed rails run first, in `enforce` itself, before the gate is asked. A gate that says "allow" changes nothing
    about a refusal that already happened. The gate can only add a refusal; it cannot lift one.
  * The output age check is not reached from here at all: a flagged result is deleted in `pipelines.JobContext.add`,
    which reads no setting and no policy.
  * The file's absence means the gate is not asked. A file that cannot be read, a gate that fails, times out or
    answers in a shape this module does not know, or a log that cannot be written, means the job is refused.
    That is fail closed.

The gate is local only: its model runs on the owner's machine and nothing in 18+ text is sent anywhere. This module
holds the interface, a stand-in for tests and the seam for the real local model; it calls no model itself.
Sessions never write, read or test the content of the owner's policy; the tests here use neutral placeholder text.
"""
import hashlib
import json
import os
import time
import urllib.parse

import safety

POLICY_FOLDER = "policy"
POLICY_NAME = "my_policy.txt"
LOG_NAME = "gate_log.jsonl"
MAX_POLICY_BYTES = 64 * 1024
MAX_REASON = 200
# The text fields of a job that the gate reads. Same names the job route already checks, plus the other plain-text fields.
TEXT_KEYS = ("text", "extra_scene", "name", "notes", "look", "prompt", "motion", "scene", "instruction")

UNAVAILABLE = "The policy gate could not decide, so this was refused. Nothing was made."
UNREADABLE = "Your policy file could not be read, so this was refused. Fix or move the file and try again."
NOT_LOCAL = "The policy gate only runs on this computer, so it was not used and this was refused."


class PolicyRefused(Exception):
    """The job is refused; the message is plain and is shown to the owner."""


class GateUnavailable(Exception):
    """The gate cannot answer right now (no local model set up, not reachable, too slow)."""


class Gate:
    """The interface. decide() returns (allow: bool, reason: str). It may raise anything: that refuses the job."""

    def decide(self, texts, area, kind, policy):  # pragma: no cover - interface
        raise NotImplementedError


class StubGate(Gate):
    """The stand-in the tests use (and the one tools may use on fixtures). It never reads a model."""

    def __init__(self, allow=True, reason="", error=None, answer=None):
        self.allow, self.reason, self.error, self.answer = allow, reason, error, answer
        self.calls = []

    def decide(self, texts, area, kind, policy):
        self.calls.append({"texts": list(texts), "area": area, "kind": kind, "policy": policy})
        if self.error is not None:
            raise self.error
        if self.answer is not None:
            return self.answer
        return self.allow, self.reason


def is_local_endpoint(url):
    """True only for a loopback address. The gate never talks to anything but this computer."""
    try:
        host = urllib.parse.urlparse(str(url)).hostname or ""
    except ValueError:
        return False
    return host in ("localhost", "127.0.0.1", "::1")


class LocalModelGate(Gate):
    """The seam for the owner's local model. Until a loopback `transport` is given it cannot answer, so (with a policy
    file present) every job is refused: fail closed. The transport is `transport(texts, area, kind, policy) -> (allow, reason)`
    and is wired in when the local model is set up; this PR sets none up."""

    def __init__(self, endpoint=None, transport=None):
        self.endpoint, self.transport = endpoint, transport

    def decide(self, texts, area, kind, policy):
        if self.endpoint is not None and not is_local_endpoint(self.endpoint):
            raise GateUnavailable(NOT_LOCAL)
        if self.transport is None:
            raise GateUnavailable("no local model is set up for the policy gate")
        return self.transport(texts, area, kind, policy)


GATE = LocalModelGate()  # tests replace this with a StubGate


def policy_path(out_dir):
    if os.environ.get("EASY_STUDIO_TEST_RUN") == "1" and os.environ.get("EASY_STUDIO_POLICY_FILE"):
        return os.environ["EASY_STUDIO_POLICY_FILE"]  # a test run only: a stray variable alone changes nothing
    return os.path.join(out_dir, POLICY_FOLDER, POLICY_NAME)


def log_path(out_dir):
    return os.path.join(out_dir, POLICY_FOLDER, LOG_NAME)


def read_policy(path):
    """(policy_text or None, error or ''). None with no error means there is no policy: the gate is not asked."""
    try:
        with open(path, "rb") as f:
            raw = f.read(MAX_POLICY_BYTES + 1)
    except FileNotFoundError:
        return None, ""
    except OSError:
        return None, UNREADABLE
    if len(raw) > MAX_POLICY_BYTES:
        return None, UNREADABLE
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, UNREADABLE
    if not [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]:
        return None, ""  # only blanks and comments: nothing is asked of the gate
    return text, ""


def job_texts(params):
    """The plain-text fields of a job, in a fixed order."""
    out = []
    if isinstance(params, dict):
        for key in TEXT_KEYS:
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                out.append(value)
    return out


def _digest(parts):
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()


def _log(out_dir, row):
    path = log_path(out_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _clean_reason(reason):
    return " ".join(str(reason or "").split())[:MAX_REASON]


def enforce(params, area, kind, out_dir, gate=None):
    """Raises PolicyRefused when the job may not run. Returns None when it may.

    Order is the guarantee: when a policy file is in use, the fixed text rails run first (a refusal there is final and the
    gate is not asked), then the gate. The job route has already run the same rails; this repeats them so the guarantee
    does not depend on the caller."""
    texts = job_texts(params)
    if not texts:
        return
    policy, problem = read_policy(policy_path(out_dir))
    if problem:
        raise PolicyRefused(problem)
    if policy is None:
        return  # no policy file: the gate is not asked, and nothing changes for the job
    for text in texts:
        ok, msg = safety.check_prompt(text)
        if ok:
            ok, msg = safety.check_area(text, area)
        if not ok:
            raise PolicyRefused(msg)
    gate = gate or GATE
    row = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": str(kind), "area": str(area),
           "text_sha256": _digest(texts), "policy_sha256": _digest([policy])}
    failed = False
    try:
        answer = gate.decide(list(texts), area, kind, policy)
        if not (isinstance(answer, tuple) and len(answer) == 2 and isinstance(answer[0], bool) and isinstance(answer[1], str)):
            raise GateUnavailable("the gate answered in a shape this app does not know")
        allow, reason = answer
        reason = _clean_reason(reason)
        if not allow and not reason:
            reason = "that is something you said you do not want"
    except Exception as exc:  # any failure of the gate is a refusal
        allow, reason, failed = False, _clean_reason(UNAVAILABLE), True
        row["error"] = type(exc).__name__
    row.update(allow=allow, reason=reason)
    try:
        _log(out_dir, row)
    except OSError:
        raise PolicyRefused("The policy gate could not write its log, so this was refused. Nothing was made.")
    if not allow:
        raise PolicyRefused(UNAVAILABLE if failed else "Refused by your own policy: " + reason)
