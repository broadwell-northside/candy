# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Ak's importer rule (D-C-18, 2026-11-06): description rules stay hard refusals for every LoRA. Only Ak's exact
allowlist passes: the eight audited LoRAs, plus the four Wan 2.2 14B sibling halves of four of them
(D-C-20, AK-CANDY-WAN-SIBLINGS-20261106). Each passes only by exact (version id, SHA256 of the .safetensors file),
and only after flags, type, title, tags and trigger words pass. Synthetic, neutral records; IDs and hashes only.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import loras as L  # noqa: E402
import safety  # noqa: E402

ALLOWED_VID = 2299345
ALLOWED_SHA = "df934b1a366206daa3b5dcfef7c84efd9e75ca19d00867d7fe24fa2bb233fdc9"
OTHER_SHA = "0" * 64
RELATION_DESC = "Inspired by my sister's watercolour lessons."
# One of the four Wan 2.2 14B sibling halves (Ak, AK-CANDY-WAN-SIBLINGS-20261106) and its allowlisted partner.
SIBLING_VID, SIBLING_SHA = 2098396, "7adf32374c7b04724638155a274d38924bbab9386a134d466f034cb4af638540"
PARTNER_VID, PARTNER_SHA = 2098405, "58cb4a22b10c5dfcb43d631b97d36d6f9162f2fe6b1f5db141c7931e828527a4"
EIGHT = {(1662740, 2299345), (2247663, 2536215), (1836104, 2077824), (1331682, 2091870), (1331682, 2098405),
         (1874811, 2325788), (1922973, 2178869), (2004155, 3061098)}
WAN_SIBLINGS = {(1331682, 2091879), (1331682, 2098396), (1874811, 2191446), (1922973, 2176450)}
KEPT_OUT = {2027766, 1822984, 2268008, 1959747}


def _record(description="", name="Soft Window Light", tags=("photorealistic", "lighting"), words=("softlight",),
            vid=12345, sha=OTHER_SHA, poi=False, minor=False, mode=None, mtype="LORA", fname="soft_light.safetensors",
            fmt="SafeTensor"):
    model = {"id": 1, "name": name, "type": mtype, "tags": [{"name": t} for t in tags], "description": description,
             "poi": poi, "minor": minor, "nsfw": False}
    if mode:
        model["mode"] = mode
    version = {"id": vid, "trainedWords": list(words), "baseModel": "Flux.1 D",
               "files": [{"name": fname, "primary": True, "hashes": {"SHA256": sha}, "metadata": {"format": fmt}}]}
    return model, version


def _ok(**kw):
    return L.civitai_check(*_record(**kw))[0]


def unit(check):
    print("\n[allow] Description rules stay hard; Ak's twelve pass by exact version and SHA256")
    data = json.load(open(L.ALLOWLIST_PATH, encoding="utf-8"))
    entries = data["entries"]
    pairs = {(e["model_id"], e["version_id"]) for e in entries}
    check("the allowlist has exactly Ak's twelve: the eight audited LoRAs and the four Wan 2.2 14B sibling halves",
          pairs == EIGHT | WAN_SIBLINGS and len(entries) == 12, sorted(pairs ^ (EIGHT | WAN_SIBLINGS)))
    check("every allowlist hash is a full SHA256", all(re.fullmatch(r"[0-9a-f]{64}", e["sha256"]) for e in entries))
    check("no version id is listed twice", len({e["version_id"] for e in entries}) == len(entries))
    check("2027766, 1822984, 2268008 and 1959747 stay out of the allowlist",
          not (KEPT_OUT & {e["model_id"] for e in entries}))
    by_vid = {e["version_id"]: e for e in entries}
    siblings = [e for e in entries if "sibling_of" in e]
    check("each sibling half names an allowlisted version of the same model and Ak's decision",
          {(e["model_id"], e["version_id"]) for e in siblings} == WAN_SIBLINGS
          and all(by_vid.get(e["sibling_of"], {}).get("model_id") == e["model_id"]
                  and (e["model_id"], e["sibling_of"]) in EIGHT
                  and e.get("decision") == "AK-CANDY-WAN-SIBLINGS-20261106" for e in siblings))
    # Description rules are hard for every LoRA that is not on the list.
    for text, label in (
        (RELATION_DESC, "a relation phrase"),
        ("Use the poses from this photo series.", "'from this photo'"),
        ("Keeps the same face as the reference.", "'same face as'"),
        ("A woman and a man walking on a beach.", "a person with no stated age"),
        ("Trained on a celebrity.", "a celebrity word"),
        ("A face swap helper.", "face swap"),
        ("Great for deepfakes.", "deepfake"),
        ("Gives a look-alike of anyone.", "look-alike"),
        ("Makes her look like Jane Example.", "a named person to copy"),
        ("Replace her face with yours.", "replacing a face"),
        ("Made for teen characters.", "a minor-coded word"),
        ("She is 17 years old in this set.", "an age under 21"),
    ):
        check(f"a description with {label} is refused for a LoRA not on the list", not _ok(description=text))
    # The exact pair passes; anything less exact does not.
    check("an allowlisted version and SHA256 pass the description check", _ok(description=RELATION_DESC, vid=ALLOWED_VID, sha=ALLOWED_SHA))
    check("the right version with another SHA256 is refused", not _ok(description=RELATION_DESC, vid=ALLOWED_VID, sha=OTHER_SHA))
    check("the right SHA256 under another version is refused", not _ok(description=RELATION_DESC, vid=999, sha=ALLOWED_SHA))
    check("an allowlisted hash on a non-.safetensors file is refused",
          not _ok(description=RELATION_DESC, vid=ALLOWED_VID, sha=ALLOWED_SHA, fname="pack.zip", fmt="Diffusers"))
    # The four Wan 14B sibling halves pass the same way, each by its own exact pair; a half never borrows its partner's.
    check("an added Wan 14B sibling half passes the description check by its exact version and SHA256",
          _ok(description=RELATION_DESC, vid=SIBLING_VID, sha=SIBLING_SHA))
    check("a sibling half's SHA256 under its partner's version id is refused",
          not _ok(description=RELATION_DESC, vid=PARTNER_VID, sha=SIBLING_SHA))
    check("the partner's SHA256 under the sibling half's version id is refused",
          not _ok(description=RELATION_DESC, vid=SIBLING_VID, sha=PARTNER_SHA))
    sib = dict(vid=SIBLING_VID, sha=SIBLING_SHA, description=RELATION_DESC)
    check("an added sibling half marked POI is refused", not _ok(poi=True, **sib))
    check("an added sibling half with a real-person tag is refused", not _ok(tags=("real person",), **sib))
    check("an added sibling half with a minor-coded trigger word is refused", not _ok(words=("teen",), **sib))
    check("an added sibling half with an age under 21 in its description is refused",
          not _ok(vid=SIBLING_VID, sha=SIBLING_SHA, description="She is 17 years old in this set."))
    # The allowlist never waives flags, type, title, tags or trigger words.
    allowed = dict(vid=ALLOWED_VID, sha=ALLOWED_SHA, description=RELATION_DESC)
    check("an allowlisted LoRA with a relation phrase in its title is refused", not _ok(name="Portrait of my wife", **allowed))
    check("an allowlisted LoRA with a real-person tag is refused", not _ok(tags=("real person",), **allowed))
    check("an allowlisted LoRA with a face-copy title is refused", not _ok(name="reactor face helper", **allowed))
    check("an allowlisted LoRA with a minor-coded trigger word is refused", not _ok(words=("teen",), **allowed))
    check("an allowlisted LoRA marked POI is refused", not _ok(poi=True, **allowed))
    check("an allowlisted LoRA marked minor is refused", not _ok(minor=True, **allowed))
    check("an allowlisted LoRA taken down is refused", not _ok(mode="TakenDown", **allowed))
    check("an allowlisted file that is not a LoRA is refused", not _ok(mtype="Checkpoint", **allowed))
    # Minors and ages under 21 refuse even in an allowlisted description.
    check("an allowlisted description with a minor-coded word is refused",
          not _ok(vid=ALLOWED_VID, sha=ALLOWED_SHA, description="Made for teen characters."))
    check("an allowlisted description with an age under 21 is refused",
          not _ok(vid=ALLOWED_VID, sha=ALLOWED_SHA, description="She is 17 years old in this set."))
    # The whole description is read (D-C-19): a word far past the old 4000/6000-character cuts still refuses.
    filler = "Soft window light for portraits. " * 400
    check("an identity-copy word after 13,000 characters of description is refused", not _ok(description=filler + "Gives a look-alike of anyone."))
    check("a long clean description still passes", _ok(description=filler))
    check("a minor-coded word deep in an allowlisted description is still refused",
          not _ok(vid=ALLOWED_VID, sha=ALLOWED_SHA, description=filler + "Made for teen characters."))
    # Every comma or newline piece is read: the old 2000-piece cap left the tail of a comma-heavy text unread.
    pieces = "soft window light, " * 2500
    check("an identity-copy word after 2,500 comma-separated pieces of description is refused",
          not _ok(description=pieces + "Gives a look-alike of anyone."))
    check("a celebrity word after 2,500 newline-separated pieces of description is refused",
          not _ok(description="soft window light\n" * 2500 + "Trained on a celebrity."))
    check("a long comma-heavy clean description still passes", _ok(description=pieces))
    sets = {f"set{i}": {f"lighting{i}x{j}": 1 for j in range(300)} for i in range(8)}
    sets["set7"]["celebrity"] = 1
    sets["set7"] = dict(list(sets["set7"].items())[-300:])  # the bad tag stays inside the 300 read per set
    check("a celebrity tag after 2,100 training tags in a LoRA file's metadata is refused",
          not safety.check_lora("soft_light.safetensors", {"ss_tag_frequency": sets})[0])
    # Prompts are judged exactly as before.
    for text in ("a portrait of my sister", "make her from this photo", "the same face as the reference",
                 "a teen at the beach", "a 17 year old"):
        check(f"a prompt is still refused: {text}", not safety.check_prompt(text)[0])
    check("the minor/age helper agrees with the prompt rule", not safety.check_minor_and_age("a teen")[0]
          and not safety.check_minor_and_age("17 years old")[0] and safety.check_minor_and_age("soft window light")[0])


if __name__ == "__main__":
    failed = []

    def _check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {extra}"))
        if not cond:
            failed.append(name)
    unit(_check)
    sys.exit(1 if failed else 0)
