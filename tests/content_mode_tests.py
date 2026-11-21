"""The one content switch, sfw_mode (PRD §7). Mock engine only.

The game runs the same cases (game/tests/fixtures/content_mode_vectors.json) in GDScript.
"""
import json
import os
import tempfile

import catalog
import content_mode as CM
import stills
from library import Library


def _refused(fn):
    try:
        fn()
    except (PermissionError, ValueError, stills.StillError) as exc:
        return str(exc)
    return ""


def unit(check):
    print("\n[M0] sfw_mode: one switch, mapped in one place")
    vectors = CM.load_vectors()
    for row in vectors["game_settings"]:
        check(f"game mapping: {row['name']}", CM.map_game_settings(row["file"]) is row["sfw_mode"], row)
    for row in vectors["studio"]:
        sfw = CM.effective_sfw_mode(row["settings"], row["attested"])
        check(f"studio mapping: {row['name']}", sfw is row["sfw_mode"] and CM.area_for(sfw) == row["area"], (sfw, row))

    check("fresh install is SFW", CM.effective_sfw_mode({}, False) is True and CM.area_for(True) == "default")
    flipped = CM.on_attestation({"age_check": True})
    check("the 21+ attestation stores sfw_mode = false once", flipped == {"age_check": True, "sfw_mode": False})
    check("area 21+ is exactly sfw_mode off", CM.area_for(False) == "adult" and CM.sfw_mode_for_area("adult") is False
          and CM.sfw_mode_for_area("default") is True)
    check("SFW cannot be switched off without the attestation",
          CM.NEEDS_ATTESTATION in _refused(lambda: CM.set_sfw_mode({}, False, False)))
    check("SFW can always be switched on", CM.set_sfw_mode({"sfw_mode": False}, True, False)["sfw_mode"] is True)
    check("a text 'false' is not a switch", "on or off" in _refused(lambda: CM.set_sfw_mode({}, "false", True)))
    check("21+ is refused on a device without the attestation",
          "locked" in _refused(lambda: CM.check_area_request("adult", {"sfw_mode": False}, False)))
    check("21+ is refused while SFW mode is on, not quietly changed",
          CM.SFW_ON_REASON == _refused(lambda: CM.check_area_request("adult", {"sfw_mode": True}, True)))
    check("21+ opens when attested and SFW is off", CM.check_area_request("adult", {}, True) == "adult")
    check("the game writes the old field from the flag", CM.game_fields(True) == {"sfw_mode": True, "adult_content": False})

    # sfw_mode = true filters on content that exists today
    sfw_area = CM.area_for(True)
    character = {"id": "c1", "name": "Mara", "age": 32, "stated_age": 32, "gender": "woman", "style": "photo"}
    get = lambda _cid: character  # noqa: E731
    check("SFW: the nude wardrobe is unreachable in the still step",
          "21+" in _refused(lambda: stills.gate("workshop_still", {"character": "c1", "wardrobe": catalog.WORKSHOP_NUDE},
                                                sfw_area, get)))
    check("full 21+ mode: the same step accepts it",
          stills.gate("workshop_still", {"character": "c1", "wardrobe": catalog.WORKSHOP_NUDE}, CM.area_for(False), get)
          is character)
    check("SFW: wardrobe_allowed follows the flag", not CM.wardrobe_allowed(catalog.WORKSHOP_NUDE, True)
          and CM.wardrobe_allowed(catalog.WORKSHOP_NUDE, False) and CM.wardrobe_allowed("jeans_tee", True))
    root = tempfile.mkdtemp(prefix="sfw_lib_")
    lib = Library(root)
    for name, area in (("covered.png", "default"), ("full.png", "adult")):
        path = os.path.join(root, name)
        open(path, "wb").write(b"\x89PNG\r\n\x1a\n")
        lib.add(path, "still", area=area)
    shown = lib.list(area=sfw_area)
    check("SFW: 21+ gallery items are not listed", len(shown) == 1 and all((i.get("area") or "default") == "default" for i in shown))
    check("SFW: full_21 items and 21+ LoRA thumbnails are masked",
          CM.item_masked({"area": "adult"}, True) and CM.item_masked({"content_rating": "full_21"}, True)
          and CM.item_masked({"thumb_adult": True}, True) and not CM.item_masked({"area": "adult"}, False))

    # Rules for content that arrives in M3 (garments, sockets, Holiday tiers), tested now.
    layers = [{"layer": "unclothed_base"}, {"layer": "underlayer"}, {"layer": "swimwear"}, {"layer": "resort_wear"}]
    shown = CM.visible_garments(layers, True)
    check("SFW: exactly one covered garment layer is drawn", [row["layer"] for row in shown] == ["resort_wear"], shown)
    check("SFW: the base and underlayer are never drawn",
          CM.visible_garments([{"layer": "unclothed_base"}, {"layer": "underlayer"}], True) is None)
    check("full 21+ mode draws the visible stack", len(CM.visible_garments(layers, False)) == 4)
    check("SFW: a node needing full 21+ mode is unreachable",
          not CM.node_reachable({"sfw_safe": True, "requires_full_21_mode": True}, True)
          and not CM.node_reachable({"sfw_safe": False, "requires_full_21_mode": False}, True)
          and CM.node_reachable({"sfw_safe": True, "requires_full_21_mode": False}, True))
    check("a node missing either flag is unreachable in every mode",
          not CM.node_reachable({"sfw_safe": True}, False) and not CM.node_reachable({"requires_full_21_mode": False}, False))
    check("SFW: intimate-contact sockets are off", not CM.socket_enabled({"kind": "intimate_contact"}, True)
          and CM.socket_enabled({"kind": "intimate_contact"}, False) and CM.socket_enabled({"kind": "hand"}, True))
    check("SFW: the Holiday ceiling is Tier 1", CM.holiday_ceiling(4, True) == 1 and CM.holiday_ceiling(3, False) == 3
          and CM.holiday_ceiling(9, False) == 4)
    held = CM.resolve_variant({"adult": {"still": "full.png"}}, True)
    check("SFW: a missing covered variant is a hold card, never the full image",
          held["variant"] == "hold" and held["still"] == "" and "no covered version" in held["caption"], held)
    check("full 21+ mode uses the full variant", CM.resolve_variant({"adult": {"still": "full.png"}}, False)["variant"] == "adult")


def e2e(a, App, out=None):
    print("\n[M0] sfw_mode through the server")
    check = a.check
    fresh = App(a.base)
    st = fresh.get("/api/settings").json()
    check("a device without the attestation reads as SFW", st.get("sfw_mode") is True and st.get("area") == "default", st)
    r = fresh.post("/api/settings", json={"sfw_mode": False})
    check("SFW cannot be switched off without the attestation", r.status_code == 403, r.text[:200])
    r = fresh.post("/api/jobs", json={"kind": "workshop_still", "params": {}, "area": "adult"})
    check("21+ jobs are refused before the attestation", r.status_code == 403 and "locked" in r.text, r.text[:200])
    r = fresh.post("/api/adult/unlock", json={"confirm_age": True, "confirm_rules": True})
    check("the 21+ attestation is accepted", r.status_code == 200, r.text[:200])
    st = fresh.get("/api/settings").json()
    check("after the attestation the studio is in full 21+ mode", st.get("sfw_mode") is False and st.get("area") == "adult", st)
    r = fresh.post("/api/settings", json={"sfw_mode": True})
    check("SFW switches back on in one request", r.status_code == 200 and r.json().get("sfw_mode") is True, r.text[:200])
    r = fresh.get("/api/gallery?area=adult")
    check("21+ is refused while SFW mode is on", r.status_code == 403 and "SFW mode is on" in r.text, r.text[:200])
    r = fresh.post("/api/settings", json={"sfw_mode": False})
    check("SFW switches off again on the attested device", r.status_code == 200 and r.json().get("sfw_mode") is False)
    check("the 21+ gallery opens again", fresh.get("/api/gallery?area=adult").status_code == 200)
    other = App(a.base)
    check("another device still reads as SFW", other.get("/api/settings").json().get("sfw_mode") is True)
    if out:
        saved = json.load(open(os.path.join(out, "settings.json")))
        check("settings.json stores sfw_mode", saved.get("sfw_mode") is False, saved)
