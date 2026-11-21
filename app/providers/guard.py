# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Every refusal that must happen BEFORE anything is sent to a hosted service.

`check_call` runs inside the provider base class's single send function, so no caller can skip it.
The job-level checks (`check_picture`, `check_loras`) run before a job encodes a picture at all.
Nothing here reads a rail's word list; it calls the safety module's functions.
"""
import os
import re
import threading

import owner as O
import owner_policy as OP
import safety

SETTINGS = {}   # the server's settings dict, set by routes_providers.register; the switch is "hosted_media"

AREA_REFUSAL = "Hosted services are never used from the 18+ area. Nothing was sent."
MEDIA_REFUSAL = ("Sending a picture or video to a hosted service is switched off. Turn on the hosted-media switch in "
                 "Setup → API keys if you want that. Nothing was sent.")
LIKENESS_REFUSAL = "Your likeness never leaves this computer, so nothing was sent to a hosted service."
PICTURE_REFUSAL = "The age check has not cleared this picture, so it will not be sent to a hosted service."
_TEXT_PART = "text"
_MEDIA_KEYS = ("media", "image_url", "image", "images", "input_image", "video_url", "video", "audio")
_DATA_URI = re.compile(r"^\s*data:(image|video|audio)/", re.I)


class Refused(Exception):
    """A refusal. The message is plain and safe to show."""


def hosted_media_on():
    return SETTINGS.get("hosted_media") is True


def has_media(value, _depth=0):
    """True when a request body carries anything that is not plain text: an image, video or audio part,
    a data URI, or one of the media fields."""
    if _depth > 12:
        return True  # too deep to read: treat as media
    if isinstance(value, str):
        return bool(_DATA_URI.match(value))
    if isinstance(value, dict):
        kind = value.get("type")
        if isinstance(kind, str) and kind not in (_TEXT_PART, "function", "json_object", "json_schema", "object"):
            return True
        return any((k in _MEDIA_KEYS and v) or has_media(v, _depth + 1) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_media(v, _depth + 1) for v in value)
    return False


NO_AREA_REFUSAL = ("This thread did not say which area it works for, so nothing was sent. A caller outside a job "
                   "must set the area from the server-side check first.")
_CLEARED = threading.local()   # picture files this thread cleared for sending, each good for one send


def current_area():
    import pipelines as P
    if getattr(P._LOCAL, "area", None) is None:
        raise Refused(NO_AREA_REFUSAL)   # fail closed: an unset area is not "everyday"
    return P.area()


def check_call(body=None, media=False):
    """Refuse before any HTTP: the 18+ area, and media while the switch is off."""
    if current_area() != "default":
        raise Refused(AREA_REFUSAL)
    if (media or has_media(body)) and not hosted_media_on():
        raise Refused(MEDIA_REFUSAL)


def message_texts(messages):
    out = []
    for m in messages or []:
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            out += [p.get("text") for p in c if isinstance(p, dict) and isinstance(p.get("text"), str)]
    return out


def check_text(texts):
    """The ordinary prompt rails, run on everything about to be sent."""
    ok, msg = safety.check_all(*[t for t in texts if t])
    if not ok:
        raise Refused(msg)


def check_loras(adv):
    """A hosted service takes no LoRA at all, so a likeness LoRA (by hash or by any other way of naming it)
    can never go: any LoRA on the request refuses it."""
    if (adv or {}).get("loras"):
        raise Refused("A hosted service does not use LoRAs, so this request was not sent. Remove the LoRA and try again.")


def _ancestors(item, get_item):
    seen = set()
    cur = item
    while isinstance(cur, dict):
        yield cur
        parent = cur.get("parent")
        if not parent or parent in seen or len(seen) >= 64:
            return
        seen.add(parent)
        try:
            cur = get_item(parent)
        except Exception:
            return


def check_picture(item, get_item, out=None):
    """An input picture for a hosted service: its age check must be exactly ok, and neither it nor any
    ancestor may carry the likeness mark. A parent that cannot be found counts against the picture."""
    appearance = item.get("appearance_check") or {}
    if (item.get("age_check") != "ok" or item.get("age_flag") or item.get("held") or appearance.get("held")
            or appearance.get("status") in ("flag", "blocked_age_check_unavailable", "unchecked", "off")):
        raise Refused(PICTURE_REFUSAL)
    for rec in _ancestors(item, get_item):
        if not OP.may_leave(rec, "hosted_api"):
            raise Refused(LIKENESS_REFUSAL)
        sha = rec.get("sha256") or rec.get("lora_sha256")
        if out and isinstance(sha, str) and O.is_likeness_hash(out, sha):
            raise Refused(LIKENESS_REFUSAL)
    parent = item.get("parent")
    if parent:
        try:
            get_item(parent)
        except Exception:
            raise Refused(PICTURE_REFUSAL)


def check_params_marks(params):
    """A request that itself carries the likeness mark or names a likeness LoRA."""
    if OP.is_likeness(params) or OP.is_likeness(params.get("advanced") if isinstance(params, dict) else None):
        raise Refused(LIKENESS_REFUSAL)


def clear_frame(item, get_item, out, path):
    """Clear one picture file for one send: check_picture on the item it came from, then remember the file.
    The provider's video() sends no picture that was not cleared here."""
    check_picture(item, get_item, out)
    if not isinstance(path, str) or not os.path.isfile(path):
        raise Refused(PICTURE_REFUSAL)
    cleared = getattr(_CLEARED, "paths", None)
    if cleared is None:
        cleared = _CLEARED.paths = set()
    cleared.add(os.path.realpath(path))


def consume_frame(path):
    """Used by the provider before it reads a picture: refuse unless the file was cleared, and spend the clearance."""
    cleared = getattr(_CLEARED, "paths", None) or set()
    real = os.path.realpath(path) if isinstance(path, str) else None
    if real not in cleared:
        raise Refused("This picture was not cleared for a hosted service, so nothing was sent.")
    cleared.discard(real)
