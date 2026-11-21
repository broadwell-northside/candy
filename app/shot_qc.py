"""Still-first gate, shot planner, and the 100-point rubric.

Image-to-video copies the still. A clip starts only after two or more keyframes
are scored and the one being animated passes. Settings and checkpoints stay in
the model registry. This module does not download weights.
"""
import csv
import os

import model_registry as reg

AXES = ("hands", "anatomy", "contact", "skin", "lighting")
# Hands, anatomy, and contact are the hard still checks. Skin and light can be a point lower.
PASS_AT = {"hands": 7, "anatomy": 7, "contact": 7, "skin": 6, "lighting": 6}
HARD_FLAGS = ("detached", "phantom", "fused")
RUBRIC_WEIGHTS = {
    "genitals": 3, "hands": 2, "limbs": 2, "contact": 3, "skin": 2,
    "motion": 3, "identity": 3, "cross_angle": 2, "lighting": 1, "artifacts": 1,
}
CONTACT_PRESET = {
    "id": "contact_explicit",
    "adult_only": True,
    "lighting": "flat softbox, even frontal light",
    "aperture": "f/8, deep focus, the join stays sharp",
    "skin": "unretouched skin, visible pores, no makeup",
    "background": "mid-grey seamless background",
}
ARTIFACTS = (
    {"id": "face_drift", "see": "Face drifts or the head grows", "fix": "Use a frontal still and a character LoRA around 0.7. Try the DaSiWa low path.", "adult": False},
    {"id": "squat", "see": "The body squats when it should stand", "fix": "Use Remix v2 or later. Say standing straight, legs extended.", "adult": False},
    {"id": "loop", "see": "The clip jumps back to the first frame", "fix": "Stay at 81 frames or fewer, then chain the next clip.", "adult": False},
    {"id": "wrong_surface", "see": "Male anatomy lands on the wrong surface", "fix": "Put the man fully in the still and use a male anatomy LoRA.", "adult": True},
    {"id": "gloop", "see": "Contact turns into one shape", "fix": "Repair the still until the two bodies stay separate. DaSiWa on the low path.", "adult": True},
    {"id": "breast_inflate", "see": "Breasts inflate during the clip", "fix": "Put that in the NAG negative.", "adult": True},
    {"id": "brightness", "see": "The clip gets brighter as it plays", "fix": "Lower the high-noise CFG or the lightning strength.", "adult": False},
    {"id": "blur", "see": "SmoothMix goes soft after two frames", "fix": "Add the lightx2v LoRA on SmoothMix v2.", "adult": False},
    {"id": "limbs", "see": "Hands or arms melt together", "fix": "Name both hands in the still. Run the 2-step clean pass.", "adult": False},
    {"id": "jitter", "see": "The motion jitters", "fix": "Fewer LoRAs and a lower CFG.", "adult": False},
    {"id": "leg_count", "see": "An extra leg in a two-person shot", "fix": "Count the legs in the still before animating.", "adult": False},
    {"id": "duplicate", "see": "Duplicate genitals in a point-of-view still", "fix": "Regenerate the still. Do not animate it.", "adult": True},
    {"id": "banding", "see": "Dark bands in neon light", "fix": "Use 8 steps and an fp16 VAE decode.", "adult": False},
)
LOG_FIELDS = (
    "shot_id", "character_id", "still_model", "still_seed", "lora_stack", "wan_variant",
    "steps", "cfg", "shift", "frames", "i2v_prompt", "negatives", "score_total",
    "worst_axis", "notes",
)


class ShotQCError(ValueError):
    pass


def _score(raw):
    try:
        n = float(raw)
    except (TypeError, ValueError):
        raise ShotQCError("Each still score must be a number from 0 to 10.")
    if not 0 <= n <= 10:
        raise ShotQCError("Each still score must be a number from 0 to 10.")
    return n


def variant_passes(variant):
    """One keyframe. Returns (ok, reason, scores)."""
    scores = variant.get("scores") or {}
    flags = " ".join(str(x) for x in (variant.get("flags") or [])).lower()
    if any(word in flags for word in HARD_FLAGS):
        return False, "Hard gate: detached, phantom, or fused anatomy. Repair the still.", {}
    out = {}
    for axis in AXES:
        if axis not in scores:
            raise ShotQCError(f"Score {axis} before animating.")
        out[axis] = _score(scores[axis])
    failed = [axis for axis, need in PASS_AT.items() if out[axis] < need]
    if failed:
        return False, "Still needs a higher score for: " + ", ".join(failed) + ".", out
    return True, "", out


def require_variants(qc, image_id):
    """Two or more scored stills, and the one being animated has to pass."""
    variants = (qc or {}).get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        raise ShotQCError("Generate at least two keyframes and score each one before animating.")
    if len({v.get("image") for v in variants if isinstance(v, dict)}) < 2:
        raise ShotQCError("The two keyframes have to be different pictures.")
    seen = []
    chosen = None
    for variant in variants:
        if not isinstance(variant, dict) or not variant.get("image"):
            raise ShotQCError("Each keyframe needs an image id and scores.")
        ok, reason, scores = variant_passes(variant)
        seen.append({"image": variant["image"], "ok": ok, "reason": reason, "scores": scores})
        if variant["image"] == image_id:
            chosen = seen[-1]
    if chosen is None:
        raise ShotQCError("The picture you animate has to be one of the scored keyframes.")
    if not chosen["ok"]:
        raise ShotQCError(chosen["reason"] or "That still did not pass. Inpaint the contact or regenerate it.")
    return {"use": image_id, "variants": seen, "worst_axis": _worst(chosen["scores"])}


def _worst(scores):
    if not scores:
        return ""
    return min(scores, key=lambda axis: (scores[axis], axis))


def plan_shot(framing, explicit_contact=False, depth_control=False):
    """Profile contact needs a depth guide. The default edit is wide, then close-up."""
    framing = str(framing or "front").lower()
    profile = framing in ("profile", "side", "side-on")
    warnings = []
    if profile and explicit_contact and not depth_control:
        warnings.append(
            "A profile contact shot needs a depth ControlNet from a pose or a 3D mock-up. "
            "Re-rolling the still will not fix which opening is which."
        )
    return {
        "framing": framing,
        "needs_depth": bool(profile and explicit_contact),
        "depth_control": bool(depth_control),
        "blocked": bool(warnings),
        "warnings": warnings,
        "pattern": [
            {"role": "establish", "shot": "wide"},
            {"role": "detail", "shot": "closeup"},
        ],
        "cut": "Animate the wide still and the close-up still separately, then cut between them.",
    }


def guard_plan(params):
    plan = plan_shot(params.get("framing"), bool(params.get("explicit_contact")), bool(params.get("depth_control")))
    if plan["blocked"]:
        raise ShotQCError(plan["warnings"][0])
    return plan


def contact_clause():
    row = CONTACT_PRESET
    return ", ".join(row[key] for key in ("lighting", "aperture", "skin", "background"))


def still_prompt(appearance, contact_map, use_contact_preset=False):
    appearance = str(appearance or "").strip()
    contact_map = str(contact_map or "").strip()
    if not appearance or not contact_map:
        raise ShotQCError("The still prompt needs the appearance and a contact map.")
    parts = [appearance, "Contact map: " + contact_map]
    if use_contact_preset:
        parts.append(contact_clause())
    return ". ".join(parts)


def i2v_prompt(action, camera, pace):
    parts = [str(action or "").strip(), str(camera or "").strip(), str(pace or "").strip()]
    if not all(parts):
        raise ShotQCError("The motion prompt needs one action, one camera move, and one pace word.")
    text = ", ".join(parts)
    if len(text.split()) > 60:
        raise ShotQCError("The motion prompt must stay under 60 words. Appearance stays in the still.")
    return text


def check_motion_words(text):
    if len(str(text or "").split()) > 60:
        raise ShotQCError("The motion prompt must stay under 60 words. Appearance stays in the still.")
    return text


def rubric_total(scores, hard_flags=()):
    """Weighted 100-point score. Missing axes are refused. Hard flags cap the total."""
    flags = " ".join(str(x) for x in (hard_flags or [])).lower()
    total_w = sum(RUBRIC_WEIGHTS.values())
    acc = 0.0
    for axis, weight in RUBRIC_WEIGHTS.items():
        if axis not in (scores or {}):
            raise ShotQCError(f"The rubric needs a score for {axis}.")
        acc += _score(scores[axis]) * weight
    total = round(acc / total_w * 10, 1)
    if "face" in flags or "morph" in flags:
        total = min(total, 50)
    if any(word in flags for word in ("detached", "phantom")):
        total = min(total, 40)
    if total >= 85:
        band = "keep"
    elif total >= 70:
        band = "trim"
    elif total >= 55:
        band = "reroll"
    else:
        band = "rebuild"
    return {"total": total, "band": band}


def fail_fast_ok(checks):
    """At 0:02, hands, genitals, contact, and face must all be OK."""
    checks = checks or {}
    needed = ("hands", "genitals", "contact", "face")
    if any(key not in checks for key in needed):
        return False
    return all(bool(checks[key]) for key in needed)


def max_frames():
    try:
        return int(reg.sampling().get("max_frames") or 81)
    except (TypeError, ValueError):
        return 81


def cap_frames(frames):
    """Returns (frames, chained). Over the cap, the rest is a later clip."""
    limit = max_frames()
    frames = int(frames)
    if frames <= limit:
        return frames, False
    return limit, True


def passing_qc(keep_id, other_id):
    """A test helper: one passing still and one weaker alternate."""
    return {
        "use": keep_id,
        "variants": [
            {"image": keep_id, "scores": {"hands": 8, "anatomy": 8, "contact": 8, "skin": 7, "lighting": 7}},
            {"image": other_id, "scores": {"hands": 5, "anatomy": 4, "contact": 4, "skin": 6, "lighting": 6}},
        ],
    }


def contact_mask_box(width, height):
    """White rectangle over the contact area. Face and the outer background stay black."""
    from PIL import Image
    im = Image.new("L", (width, height), 0)
    box = (int(width * 0.28), int(height * 0.42), int(width * 0.72), int(height * 0.78))
    px = im.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            px[x, y] = 255
    return im


def public_tips(adult_only):
    """adult_only=False is the everyday list. True is the extra 18+ rows."""
    return [dict(row) for row in ARTIFACTS if row["adult"] is adult_only]


def log_path():
    env = os.environ.get("EASY_STUDIO_SHOT_LOG")
    if env:
        return env
    out = os.environ.get("EASY_STUDIO_OUTPUTS") or os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "outputs")
    return os.path.join(out, "shot_log.csv")


def append_shot_log(row, path=None):
    path = path or log_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in LOG_FIELDS})
    return path
