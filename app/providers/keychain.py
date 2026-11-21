# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""API keys live in the macOS login Keychain and nowhere else.

The key is written through `security -i` on its standard input, so it never appears in a process
list, an argument list or an error text. Nothing here returns a key except `get_key`, and the only
caller of that is the provider base class's `_send`, which puts it in one request header.
The `security` program can be swapped for a stand-in with EASY_STUDIO_SECURITY_TOOL, in a test run only:
the variable is read only when EASY_STUDIO_TEST_RUN is 1 as well, so a stray variable alone changes nothing.
"""
import os
import re
import subprocess
import sys

SERVICE = "candy-easy-studio"
KEY_RE = re.compile(r"[A-Za-z0-9._\-]{16,256}")
ACCOUNT_RE = re.compile(r"[a-z][a-z0-9_]{1,30}")


class KeychainError(Exception):
    """A plain, key-free message."""


def _tool():
    if os.environ.get("EASY_STUDIO_TEST_RUN") == "1" and os.environ.get("EASY_STUDIO_SECURITY_TOOL"):
        return os.environ["EASY_STUDIO_SECURITY_TOOL"]
    return "/usr/bin/security"


def _cmd(*args):
    tool = _tool()
    return ([sys.executable, tool] if tool.endswith(".py") else [tool]) + list(args)


def _account(provider):
    if not isinstance(provider, str) or not ACCOUNT_RE.fullmatch(provider):
        raise KeychainError("Unknown key name.")
    return provider


def _run(args, stdin=None):
    try:
        return subprocess.run(_cmd(*args), input=stdin, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


def configured(provider):
    """True when a key is stored. Reads the item's attributes only, never the secret."""
    done = _run(["find-generic-password", "-s", SERVICE, "-a", _account(provider)])
    return bool(done and done.returncode == 0)


def get_key(provider):
    """The stored key, or None. For the provider base class's `_send` only."""
    done = _run(["find-generic-password", "-s", SERVICE, "-a", _account(provider), "-w"])
    if not done or done.returncode != 0:
        return None
    key = (done.stdout or "").strip()
    return key if KEY_RE.fullmatch(key) else None


def set_key(provider, value):
    """Store (or replace) the key. Raises KeychainError with a message that never contains the key."""
    account = _account(provider)
    if not isinstance(value, str) or not KEY_RE.fullmatch(value.strip()):
        raise KeychainError("That does not look like an API key. Paste it again without spaces or quotes.")
    line = f"add-generic-password -U -s {SERVICE} -a {account} -w {value.strip()}\n"
    done = _run(["-i"], stdin=line)  # stdout and stderr of this call are never looked at
    del line
    if done is None or not configured(account):
        raise KeychainError("The Keychain did not save the key. Unlock the Mac's login Keychain and try again.")


def delete_key(provider):
    _run(["delete-generic-password", "-s", SERVICE, "-a", _account(provider)])
    return not configured(provider)
