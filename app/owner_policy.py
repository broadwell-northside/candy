# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The rules that keep the owner's likeness where it belongs.

One definition, used by every gate: a likeness job is a job that loads a LoRA whose hash is a
likeness hash. In this first version likeness pictures never enter the shared library, so no
ordinary job can have one as an input; the only likeness job kind is `owner_picture`.

The lock follows the file's SHA-256, not its name or folder.
"""
import os
import threading

import owner as O

OWNER_PICTURE = "owner_picture"
NOT_HERE = ("This LoRA is the owner's own likeness. It is used only by the likeness picture job, "
            "for the enrolled owner, and by nothing else.")
REVOKED = "This LoRA was the owner's likeness and has been deleted. It is refused for good."
# Where a likeness file or picture may never go. One refusal for all of them.
DESTINATIONS = ("hosted_api", "rented_machine", "server", "website", "evidence_bundle", "game_export", "pack", "zip")

_LOCAL = threading.local()


def enter(sha256, kind):
    """The running job says which likeness LoRA it may load. Set by the likeness job only."""
    _LOCAL.allow = {"sha256": sha256, "kind": kind}


def leave():
    _LOCAL.allow = None


def current():
    return getattr(_LOCAL, "allow", None)


def _sha(path):
    return O.cached_sha256(path)


def lora_refusal(out, path):
    """Why this LoRA file may not load in the job that is running now, or "".

    Asked for every LoRA, before its sidecar or its name is looked at."""
    private = os.path.join(O.owner_dir(out), "loras") + os.sep
    inside = os.path.realpath(path).startswith(os.path.realpath(private))
    sha = _sha(path)
    if sha is None:
        return NOT_HERE if inside else ""
    if sha in O.revoked_hashes(out):
        return REVOKED
    if not inside and sha not in O.likeness_hashes(out):
        return ""
    allow = current()
    if allow and allow.get("kind") == OWNER_PICTURE and allow.get("sha256") == sha:
        return ""
    return NOT_HERE


def graph_refusal(out, lora_dir, workflow):
    """Why this graph may not be sent to the engine, or "". Asked for every graph, whatever made it: a raw
    workflow that names a LoRA file itself is checked like one picked in the app."""
    if not lora_dir or not isinstance(workflow, dict):
        return ""
    root = os.path.normpath(lora_dir) + os.sep  # by name, not by where a link leads: the engine follows links too
    for node in workflow.values():
        inputs = node.get("inputs") if isinstance(node, dict) else None
        for value in (inputs or {}).values() if isinstance(inputs, dict) else ():
            if not isinstance(value, str) or not value or len(value) > 512 or "\x00" in value:
                continue
            path = os.path.normpath(os.path.join(lora_dir, value))
            if not path.startswith(root) or not os.path.isfile(path):
                continue
            why = lora_refusal(out, path)
            if why:
                return why
    return ""


def is_likeness(record):
    """True for anything that carries the likeness mark, or sits in the owner's folder."""
    if not isinstance(record, dict):
        return False
    return bool(record.get("owner_likeness") or record.get("identity") == "owner"
                or str(record.get("role") or "").startswith("owner_"))


def may_leave(record, destination):
    """False for every likeness record and every destination in DESTINATIONS. Callers refuse on False.

    A likeness picture stays on the owner's machines. A destination this function does not know is
    treated as off the machine."""
    return not is_likeness(record)
