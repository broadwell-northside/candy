# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The provider contract, and the one function that talks to a hosted service.

`Provider._send` is the only code in the app that reads an API key. It refuses first (guard), builds
the address from the provider's host constant and a fixed path, puts the key in the Authorization header,
never follows a redirect, and turns every failure into a message that holds a status and a short error
code at most: never the key, never the service's own text.
"""
import re

import requests

from . import guard, keychain

TIMEOUT = 60
_CODE_RE = re.compile(r"[A-Za-z0-9_.\-]{1,64}")
_PATH_RE = re.compile(r"/[A-Za-z0-9_.\-/]{0,200}")  # a fixed path; no host, query, userinfo or backslash
SESSION = None   # tests put a stand-in HTTP session here; None means `requests`


class ProviderError(Exception):
    """A failure whose message is safe to show and to store on a job."""


Refused = guard.Refused


def http():
    return SESSION or requests


class Provider:
    name = ""        # registry name
    label = ""
    kind = ""        # "text" or "video"
    host = ""        # fixed in code, bare host name, https only
    key_name = ""    # Keychain account; providers of one company share a key
    default_model = None

    def __init__(self):
        self.key_name = self.key_name or self.name

    # contract ----------------------------------------------------------------
    def configured(self):
        return keychain.configured(self.key_name)

    def chat(self, messages, model=None):
        raise ProviderError(f"{self.label} does not do chat.")

    def video(self, prompt, image_path=None, seconds=5, model=None):
        raise ProviderError(f"{self.label} does not make video.")

    def poll(self, handle):
        raise ProviderError(f"{self.label} does not make video.")

    # the one way out ------------------------------------------------------------
    def _send(self, method, path, body=None, media=False, headers=None):
        """Send one request. Returns the parsed JSON object."""
        guard.check_call(body, media)
        if not (self.host and re.fullmatch(r"[a-z0-9.\-]+", self.host) and _PATH_RE.fullmatch(path) and "//" not in path
                and ".." not in path):
            raise ProviderError("This provider's address is not valid.")  # a bug, not input
        key = keychain.get_key(self.key_name)
        if not key:
            raise ProviderError(f"No {self.label} key is saved yet. Add it in Setup → API keys.")
        head = {"Authorization": "Bearer " + key, "Accept": "application/json"}
        head.update(headers or {})
        try:
            resp = http().request(method, "https://" + self.host + path, json=body, headers=head, timeout=TIMEOUT,
                                  allow_redirects=False)
        except requests.RequestException:
            raise ProviderError(f"Could not reach {self.label}. Nothing was lost; try again.") from None
        finally:
            key = head = None
        status = getattr(resp, "status_code", 0)
        try:
            data = resp.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            data = {}
        if not 200 <= status < 300:
            err = data.get("error")
            code = data.get("code") or (err.get("code") if isinstance(err, dict) else None)
            code = code if isinstance(code, str) and _CODE_RE.fullmatch(code) else ""
            raise ProviderError(f"{self.label} refused the request (HTTP {status}{', ' + code if code else ''}).")
        return data
