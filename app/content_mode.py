# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""One content switch: sfw_mode. This is the only place older fields map to it (PRD §7).

- Studio: area == "adult"  <=>  sfw_mode is False.
- Game:   adult_content    <=>  sfw_mode is False (game/scripts/settings.gd mirrors map_game_settings()).
- A fresh install reads as sfw_mode = True. Passing the existing 21+ attestation (the studio's two
  checkboxes, the game's age_gate_version = 21) stores sfw_mode = False once. The SFW switch stays one
  click away after that.
- Without the attestation on this device (never confirmed, locked, or an expired PIN session) the
  effective value is always True, whatever is stored.

The gate is an attestation by the owner, not proof of age. No numeric player age is stored.

The filters below are the sfw_mode = True rules. Some of them (garment layers, contact sockets, Holiday
tiers) describe content that arrives in M3; they live here now so that content inherits them.
"""
import json
import os

GATE_VERSION = 21

GARMENT_ORDER = ("unclothed_base", "underlayer", "swimwear", "resort_wear", "outerwear")
SFW_GARMENTS = ("swimwear", "resort_wear", "outerwear")
NEVER_IN_SFW = ("unclothed_base", "underlayer")
SFW_HOLIDAY_CEILING = 1
MAX_HOLIDAY_TIER = 4

HOLD_MESSAGE = ("This moment has no covered version yet, so it stays on hold while SFW mode is on. "
                "Nothing was re-rendered.")
SFW_ON_REASON = "SFW mode is on. Switch it off in Settings to open 21+."
NEEDS_ATTESTATION = "Confirm 21+ on this device first. Then SFW mode can be switched off."


# --------------------------------------------------------------------------- the flag
def stored_sfw_mode(settings):
    """The stored value, or None when nothing (or something that is not a true/false) was stored."""
    value = (settings or {}).get("sfw_mode") if isinstance(settings, dict) else None
    return value if isinstance(value, bool) else None


def effective_sfw_mode(settings, attested):
    """True unless this device holds the 21+ attestation and SFW was not switched back on."""
    if attested is not True:
        return True
    stored = stored_sfw_mode(settings)
    if stored is None:
        return False  # attested with nothing stored: full 21+ mode, the owner's chosen default
    return stored


def area_for(sfw_mode):
    return "default" if sfw_mode is not False else "adult"


def sfw_mode_for_area(area):
    return area != "adult"


def on_attestation(settings):
    """The 21+ attestation was just stored: full 21+ mode from now on."""
    out = dict(settings or {})
    out["sfw_mode"] = False
    return out


def set_sfw_mode(settings, value, attested):
    """Switch it. Turning SFW off needs the attestation on this device."""
    if not isinstance(value, bool):
        raise ValueError("SFW mode is on or off.")
    if value is False and attested is not True:
        raise PermissionError(NEEDS_ATTESTATION)
    out = dict(settings or {})
    out["sfw_mode"] = value
    return out


def check_area_request(requested, settings, attested):
    """The area a request may use. Asking for 21+ while SFW mode is on is refused, not quietly changed."""
    if requested != "adult":
        return "default"
    if attested is not True:
        raise PermissionError("The 18+ section is locked on this device. Open it with the 18+ button first.")
    if effective_sfw_mode(settings, True):
        raise PermissionError(SFW_ON_REASON)
    return "adult"


def map_game_settings(data):
    """The game's user://settings.json mapping (settings.gd does the same in GDScript).

    No gate stored: always True. Gate stored: sfw_mode if it is a true/false, else the old
    adult_content flag inverted, else False (full 21+ after the attestation).
    """
    data = data if isinstance(data, dict) else {}
    gate = data.get("age_gate_version")
    passed = (isinstance(gate, int) and not isinstance(gate, bool) and gate == GATE_VERSION) or (
        isinstance(gate, float) and gate.is_integer() and int(gate) == GATE_VERSION)
    if not passed:
        return True
    if isinstance(data.get("sfw_mode"), bool):
        return data["sfw_mode"]
    if isinstance(data.get("adult_content"), bool):
        return not data["adult_content"]
    return False


def game_fields(sfw_mode):
    """What the game writes back: the flag, plus the old field derived from it for older readers."""
    return {"sfw_mode": bool(sfw_mode), "adult_content": not bool(sfw_mode)}


# --------------------------------------------------------------------------- sfw_mode = True filters
def wardrobe_allowed(wardrobe, sfw_mode):
    import catalog
    if wardrobe == catalog.WORKSHOP_NUDE:
        return sfw_mode is False
    return wardrobe in catalog.WORKSHOP_CLOTHED


def visible_garments(layers, sfw_mode):
    """The garment layers to draw. In SFW mode exactly one of swimwear / resort_wear / outerwear is drawn
    (the outermost one that exists) and the base and underlayer never are. None means hold: no covered
    layer exists, so nothing is drawn and the caller shows the hold card."""
    rows = [dict(row) for row in (layers or []) if isinstance(row, dict) and row.get("layer") in GARMENT_ORDER]
    if sfw_mode is False:
        return [row for row in rows if row.get("visible", True)]
    covered = [row for row in rows if row.get("layer") in SFW_GARMENTS and row.get("content_rating", "sfw") == "sfw"]
    if not covered:
        return None
    covered.sort(key=lambda row: GARMENT_ORDER.index(row["layer"]))
    return [covered[-1]]


def node_reachable(node, sfw_mode):
    """Builder nodes/cards. Both flags are required on every node; a node missing either is unreachable."""
    if not isinstance(node, dict):
        return False
    if not isinstance(node.get("sfw_safe"), bool) or not isinstance(node.get("requires_full_21_mode"), bool):
        return False
    if sfw_mode is False:
        return True
    return node["sfw_safe"] is True and node["requires_full_21_mode"] is False


def socket_enabled(socket, sfw_mode):
    if not isinstance(socket, dict):
        return False
    if sfw_mode is not False and (socket.get("kind") == "intimate_contact" or socket.get("intimate_contact") is True):
        return False
    return True


def item_masked(item, sfw_mode):
    """True when a library item or thumbnail must be masked: full_21 content (or the 21+ area) in SFW mode."""
    if sfw_mode is False:
        return False
    item = item if isinstance(item, dict) else {}
    return item.get("content_rating") == "full_21" or item.get("area") == "adult" or item.get("thumb_adult") is True


def holiday_ceiling(level_ceiling, sfw_mode):
    """Holiday tiers 1-4. SFW is Tier 1. A level may lower its ceiling, never raise it."""
    try:
        tier = int(level_ceiling)
    except (TypeError, ValueError):
        tier = SFW_HOLIDAY_CEILING
    tier = max(SFW_HOLIDAY_CEILING, min(MAX_HOLIDAY_TIER, tier))
    return SFW_HOLIDAY_CEILING if sfw_mode is not False else tier


def resolve_variant(variants, sfw_mode):
    """Pick a rendered variant. SFW never falls through to the full image and never re-renders:
    no covered file means a hold card."""
    variants = variants if isinstance(variants, dict) else {}

    def has(name):
        media = variants.get(name)
        return isinstance(media, dict) and bool(media.get("still") or media.get("video"))

    if sfw_mode is False and has("adult"):
        return {"variant": "adult", **variants["adult"]}
    if has("covered"):
        return {"variant": "covered", **variants["covered"]}
    if sfw_mode is not False and has("adult"):
        return {"variant": "hold", "still": "", "video": "", "caption": HOLD_MESSAGE}
    return {"variant": "none", "still": "", "video": ""}


# --------------------------------------------------------------------------- shared test vectors
VECTORS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "game", "tests", "fixtures", "content_mode_vectors.json")


def load_vectors():
    with open(VECTORS, encoding="utf-8") as fh:
        return json.load(fh)
