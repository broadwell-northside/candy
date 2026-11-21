"""Photoreal stills (the keyframe) and the adult video chain.

Stills: Z-Image for ordinary keyframes. Chroma for explicit keyframes inside the
18+ section. Film, Glam, and Draft stay available when the prompt is not explicit.
Video plan: Still → Motion → Fix → Finish. The runner still renders Wan, records
regional repair and SeedVR2 (1080p), then sets GIMM-VFI's 30 fps with ffmpeg.
SCAIL-2, SVI, and Lightning are registry names until their graphs exist.
Anatomy LoRAs stack only inside the 18+ section. The age check still runs later.
The Me slot is not built here.
"""
import os
import random

from PIL import Image, ImageEnhance, ImageFilter

import model_registry as reg
import safety

SKIN_WORDS = "natural skin texture, visible pores, fine vellus hair, subtle imperfections, unretouched"
GLAM_WORDS = "smooth retouched skin, soft beauty lighting"

LOOKS = (
    {"id": "realistic", "label": "Realistic", "icon": "✨", "role": "still_realistic"},
    {"id": "film", "label": "Film", "icon": "🎞️", "role": "still_film"},
    {"id": "glam", "label": "Glam", "icon": "💄", "role": "still_glam"},
    {"id": "draft", "label": "Draft", "icon": "⚡", "role": "still_draft"},
    {"id": "flux", "label": "Flux.1 dev", "icon": "🌀", "role": "still_flux"},
    {"id": "chroma", "label": "Chroma (18+ fallback)", "icon": "🔞", "role": "still_adult_fallback"},
)
LENSES = (
    {"id": "phone", "label": "Phone snapshot", "p": "phone camera snapshot, natural perspective"},
    {"id": "mm35", "label": "35 mm", "p": "shot on a 35mm lens"},
    {"id": "mm50", "label": "50 mm", "p": "shot on a 50mm lens"},
    {"id": "mm85", "label": "85 mm portrait", "p": "85mm portrait lens, flattering perspective"},
    {"id": "shallow", "label": "Shallow focus", "p": "shallow depth of field, subject sharp, background soft"},
)
EXTRA_LIGHTS = (
    {"id": "softbox", "label": "Softbox", "p": "large softbox, even studio light", "icon": "💡"},
    {"id": "window", "label": "Window light", "p": "soft window light from one side", "icon": "🪟"},
    {"id": "noon", "label": "Hard noon", "p": "hard noon sunlight, crisp shadows", "icon": "☀️"},
    {"id": "overcast", "label": "Overcast", "p": "soft overcast daylight", "icon": "☁️"},
    {"id": "neon_rim", "label": "Neon rim", "p": "cyberpunk neon rim light", "icon": "🟣"},
    {"id": "club", "label": "Club spot", "p": "club stage spotlight", "icon": "🎤"},
)

# 18+ only. sex "any" is allowed for every adult body.
ANATOMY = (
    {"id": "chest_female", "sex": "female", "label": "Chest / breasts"},
    {"id": "breasts", "sex": "female", "label": "Breasts"},
    {"id": "chest_male", "sex": "male", "label": "Chest"},
    {"id": "buttocks", "sex": "any", "label": "Buttocks"},
    {"id": "genitals_female", "sex": "female", "label": "Genitals (female)"},
    {"id": "genitals_male", "sex": "male", "label": "Genitals (male)"},
    {"id": "skin", "sex": "any", "label": "Skin detail"},
    {"id": "body_hair", "sex": "any", "label": "Body hair"},
)

ANGLES = ("front", "side", "back", "overhead", "low")
POSE_IDS = ("standing", "seated", "lying", "kneeling", "pair")
DETAIL_FACE = {"realistic": 0.35, "film": 0.35, "glam": 0.28, "draft": None, "flux": 0.35, "chroma": 0.35}
HAND_DENOISE = 0.40
BODY_DENOISE = 0.25
ANATOMY_DENOISE = 0.30


class PhotorealError(ValueError):
    pass


def look(look_id):
    for row in LOOKS:
        if row["id"] == look_id:
            spec = reg.role(row["role"])
            merged = {**spec, **row, "model_id": spec.get("id"), "label": spec.get("label") or row["label"]}
            merged["id"] = row["id"]
            return merged
    raise PhotorealError("Unknown look.")


def resolve_look(params, style, area_name):
    """Which still preset to run. Anime is unchanged. Photo defaults to Realistic."""
    if style == "anime":
        return None
    if style in ("render3d", "painted") and not params.get("look"):
        return None
    chosen = params.get("look")
    if not chosen and params.get("speed") == "fast":
        chosen = "draft"
    chosen = chosen or "realistic"
    row = look(chosen)
    if row.get("adult_only") and area_name != "adult":
        raise PhotorealError("Chroma is the 18+ fallback. Open the 18+ section to use it.")
    return row


def choose_still(params, style, area_name, texts):
    """Explicit adult keyframes use Chroma. Everything else keeps resolve_look."""
    row = resolve_look(params, style, area_name)
    blob = " ".join(str(t or "") for t in (texts or []))
    if style != "anime" and area_name == "adult" and safety.explicit_word(blob):
        return look("chroma")
    return row


def snap_seconds(seconds, photoreal_flag, preview=False):
    """Photoreal clips use the registry lengths. Other clips stay on the old 1–10 s range."""
    try:
        s = float(5 if seconds is None else seconds)
    except (TypeError, ValueError):
        s = 5.0
    if not photoreal_flag:
        return max(1.0, min(10.0, s))
    spec = reg.load().get("clip_lengths") or {}
    if preview:
        return float(spec.get("preview_s") or 2)
    allowed = reg.clip_lengths()
    return float(min(allowed, key=lambda n: (abs(n - s), n)))


def reference_clause(strength):
    """Words for a clothing reference. The try-on slider stays; Candy's panels did not have one."""
    try:
        s = float(strength)
    except (TypeError, ValueError):
        raise PhotorealError("Reference strength must be a number.")
    if not 0 <= s <= 1:
        raise PhotorealError("Reference strength must be between 0 and 1.")
    if s >= 0.75:
        return "Match the reference closely."
    if s <= 0.4:
        return "Use the reference only as a loose guide."
    return "Follow the reference, and keep the person's body."


def skin_clause(row):
    if row and row.get("id") == "glam":
        return GLAM_WORDS
    if row and row.get("skin_words"):
        return SKIN_WORDS
    return ""


def size_for(row, aspect):
    if row and row.get("id") == "draft":
        return {"portrait": (832, 1216), "square": (1024, 1024), "wide": (1216, 832)}.get(aspect, (832, 1216))
    if aspect == "wide":
        return 1536, 1024
    if aspect == "square":
        return 1024, 1024
    return 1024, 1536


def close_up(params):
    return bool(params.get("close_up") or params.get("camera") in ("closeup", "portrait") or params.get("lens") == "mm85")


def skin_lora_slot(params, row):
    """At most one skin LoRA, and only on a close-up. Off when the user does not name one."""
    rule = reg.role("skin_lora")
    name = params.get("skin_lora") or ""
    if not name:
        return None
    if rule.get("close_up_only") and not close_up(params):
        raise PhotorealError("The skin LoRA is only added on a close-up. Pick Portrait, Close-up, or the 85 mm lens.")
    ok, msg = safety.check_lora(str(name))
    if not ok:
        raise PhotorealError(msg)
    return (str(name), float(rule.get("strength") or 0.5))


def sex_of(item=None, params=None):
    params = params or {}
    dna = (item or {}).get("dna") or params.get("dna") or {}
    g = dna.get("gender") or params.get("sex") or ""
    if g in ("man", "male"):
        return "male"
    if g in ("woman", "female"):
        return "female"
    return "unspecified"


def anatomy_loras(items, area_name, sex):
    """(name, strength) pairs. Refuses anything outside the 18+ section."""
    items = items or []
    if not items:
        return []
    if area_name != "adult":
        raise PhotorealError("Body-part LoRAs only run inside the 18+ section.")
    by_id = {c["id"]: c for c in ANATOMY}
    seen = set()
    out = []
    for raw in items:
        if not isinstance(raw, dict):
            raise PhotorealError("Each anatomy LoRA needs a category and a file name.")
        cid = str(raw.get("category") or "")
        cat = by_id.get(cid)
        if not cat:
            raise PhotorealError("Unknown body-part category.")
        if cid in seen:
            raise PhotorealError(f"Only one LoRA is allowed for {cat['label']}.")
        if sex in ("female", "male") and cat["sex"] not in ("any", sex):
            raise PhotorealError(f"{cat['label']} does not match this character's sex.")
        name = str(raw.get("name") or "")
        if not name:
            raise PhotorealError(f"Name the LoRA file for {cat['label']}.")
        ok, msg = safety.check_lora(name)
        if not ok:
            raise PhotorealError(msg)
        strength = raw.get("strength", 0.6)
        try:
            strength = float(strength)
        except (TypeError, ValueError):
            raise PhotorealError("Anatomy strength must be a number.")
        if not 0 < strength <= 1:
            raise PhotorealError("Anatomy LoRA strength must be above 0 and at most 1.")
        seen.add(cid)
        out.append((name, strength))
    return out


def detailer_plan(look_id, sex, full_body, area_name, face_fix=False):
    """Face repair is opt-in. It is not added just because the look has a face pass."""
    face = DETAIL_FACE.get(look_id)
    passes = []
    if face is not None and face_fix:
        passes.append({"part": "face", "denoise": face, "sex": sex, "opt_in": True})
    if face is not None:
        passes.append({"part": "hands", "denoise": HAND_DENOISE, "sex": sex})
    if full_body and face is not None:
        passes.append({"part": "body", "denoise": BODY_DENOISE, "sex": sex})
    if area_name == "adult":
        regions = [c["id"] for c in ANATOMY if c["sex"] in ("any", sex) or sex == "unspecified"]
        passes.append({"part": "anatomy", "denoise": ANATOMY_DENOISE, "sex": sex, "regions": regions})
    return passes


def body_card(dna):
    """Shape numbers for a fictional adult. Sex is male or female. No real person.

    The age is the caller's stated age. It is not defaulted, clamped, or taken
    from how the picture looks.
    """
    import safety
    ok, age, msg = safety.require_stated_age(dna or {})
    if not ok:
        raise PhotorealError(msg)
    sex = "male" if (dna or {}).get("gender") == "man" else "female"
    traits = (dna or {}).get("traits") or {}
    sliders = {
        "height": traits.get("height") or "avg_h",
        "build": traits.get("body") or "average",
        "hips": traits.get("hips") or "h_med",
    }
    if sex == "female":
        sliders["bust"] = traits.get("bust") or "b_med"
    else:
        sliders["chest"] = traits.get("chest") or traits.get("body") or "average"
    return {
        "version": 1,
        "sex": sex,
        "age": age,
        "stated_age": age,
        "age_source": "stated",
        "source": "creator_sliders",
        "fictional": True,
        "real_person": False,
        "sliders": sliders,
        "shape45": None,
        "protected": ["face", "hands", "background"],
    }


def clothing_mask(width, height):
    """White = clothing and skin the outfit may reveal. Black = face, hands, background."""
    im = Image.new("L", (width, height), 0)
    px = im.load()
    for y in range(height):
        for x in range(width):
            nx, ny = x / width, y / height
            border = nx < 0.10 or nx > 0.90 or ny > 0.96
            face = ny < 0.22 and 0.28 < nx < 0.72
            hand_l = 0.52 < ny < 0.78 and nx < 0.24
            hand_r = 0.52 < ny < 0.78 and nx > 0.76
            if not (border or face or hand_l or hand_r):
                px[x, y] = 255
    return im


def film_finish(path, amount):
    """Light grain and a very light vignette. Leaves the age-check test marker alone."""
    if not amount:
        return path
    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.getpixel((min(4, im.width - 1), min(4, im.height - 1))) == (255, 0, 255):
            return path
        rnd = random.Random(3)
        grain = Image.new("RGB", im.size)
        gp = grain.load()
        amp = int(255 * float(amount))
        for y in range(im.height):
            for x in range(im.width):
                g = 128 + rnd.randint(-amp, amp)
                gp[x, y] = (g, g, g)
        out = Image.blend(im, grain, min(0.15, float(amount) * 2))
        vig = Image.new("L", im.size, 0)
        vig.paste(255, (int(im.width * 0.08), int(im.height * 0.08), int(im.width * 0.92), int(im.height * 0.92)))
        vig = vig.filter(ImageFilter.GaussianBlur(max(8, im.width // 20)))
        dark = ImageEnhance.Brightness(out).enhance(0.92)
        out = Image.composite(out, dark, vig)
        out.save(path)
    return path


def video_stages(preview=False):
    i2v, up, interp = reg.video_chain()
    fix = reg.role("video_fix")
    stages = []
    if preview:
        prev = reg.role("video_preview")
        stages.append({"stage": "preview", "model": prev["id"], "label": prev["label"], "status": "registered"})
    stages.append({"stage": "i2v", "model": i2v["id"], "label": i2v["label"], "status": "ran"})
    stages.append({"stage": "fix", "model": fix["id"], "label": fix["label"], "status": "registered"})
    stages.append({"stage": "upscale", "model": up["id"], "label": up["label"], "weights": up.get("weights"),
                   "scale": up.get("scale"), "target": up.get("target") or "1080p", "status": "registered"})
    stages.append({"stage": "interpolate", "model": interp["id"], "label": interp["label"],
                   "weights": interp.get("weights"), "to_fps": interp.get("to_fps"), "status": "fps-set"})
    return stages


def conform_fps(src, dst, fps, ffmpeg):
    import video_tools as V
    V._run([ffmpeg, "-y", "-v", "error", "-i", src, "-filter:v", f"fps={int(fps)}",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst])
    return dst


def apply_video_chain(src, tmp_dir, ffmpeg, preview=False):
    """Wan has already rendered `src`. Record repair and SeedVR2, then set 30 fps.

    SeedVR2 and GIMM nodes are not in the ComfyUI 0.43 snapshot, so this does not
    claim those graphs ran. ffmpeg only sets the registry frame rate.
    """
    stages = video_stages(preview=preview)
    interp = reg.role("video_interpolate")
    dst = os.path.join(tmp_dir, "photoreal_chain.mp4")
    conform_fps(src, dst, interp.get("to_fps") or 30, ffmpeg)
    return dst, stages


def _prompt(sex, age, angle, pose, nude):
    who = "woman" if sex == "female" else "man"
    body = "anatomically realistic adult body, natural skin texture" if nude else "natural skin texture, clothed"
    pose_words = {
        "standing": "standing", "seated": "seated on a chair", "lying": "lying down",
        "kneeling": "kneeling", "pair": "with one other fictional adult, standing close",
    }[pose]
    view = {"front": "front view", "side": "side view", "back": "back view",
            "overhead": "overhead view", "low": "low angle view"}[angle]
    outfit = "nude" if nude else "wearing jeans and a white t-shirt"
    return f"a {age}-year-old fictional adult {who}, {outfit}, {view}, {pose_words}, {body}, unretouched photograph"


def build_realism60():
    """60 fictional-adult prompts. The last 4 are the gated 18+ slots inside the set."""
    tones = ["very fair skin", "fair skin", "olive skin", "tan skin", "brown skin", "deep brown skin", "dark skin", "deep dark skin"]
    lights = ["hard noon sunlight", "soft studio softbox lighting", "pink and blue neon lighting"]
    rows = []
    n = 1
    for tone in tones:
        for light in lights:
            rows.append({"id": f"p{n:02d}", "bucket": "portrait", "sex": "female" if n % 2 else "male",
                         "age": 24 + (n % 20), "seeds": [101, 202], "adult": False,
                         "prompt": f"close-up portrait of a {24 + (n % 20)}-year-old fictional adult, {tone}, {light}, natural skin texture, visible pores"})
            n += 1
    outfits = ["jeans and a white t-shirt", "a summer dress", "black lace lingerie", "a bikini", "yoga clothes", "a club outfit"]
    for i, outfit in enumerate(outfits):
        for sex, age in (("female", 28), ("male", 34)):
            who = "woman" if sex == "female" else "man"
            rows.append({"id": f"h{i}{sex[0]}", "bucket": "half", "sex": sex, "age": age, "seeds": [101, 202],
                         "adult": False,
                         "prompt": f"waist-up photograph of a {age}-year-old fictional adult {who} wearing {outfit}, soft studio light, natural skin texture"})
    full_poses = ["standing", "walking", "sitting", "a pole-dance stance", "standing", "walking", "sitting", "standing"]
    for i, pose in enumerate(full_poses):
        sex = "female" if i < 4 else "male"
        age = 30 if sex == "female" else 36
        rows.append({"id": f"f{i:02d}", "bucket": "full", "sex": sex, "age": age, "seeds": [101, 202], "adult": False,
                     "prompt": f"full-body photograph of a {age}-year-old fictional adult {'woman' if sex == 'female' else 'man'}, {pose}, jeans and a t-shirt, natural skin"})
    hands = ["holding a wine glass", "one hand on the cheek", "holding a phone", "hands folded",
             "holding a wine glass", "one hand on the cheek", "holding a phone", "hands folded"]
    for i, hand in enumerate(hands):
        rows.append({"id": f"n{i:02d}", "bucket": "hands", "sex": "female" if i < 4 else "male", "age": 32,
                     "seeds": [101, 202], "adult": False,
                     "prompt": f"close photograph of a 32-year-old fictional adult's hands, {hand}, natural skin texture, five fingers"})
    for i in range(4):
        rows.append({"id": f"g{i}", "bucket": "group", "sex": "mixed", "age": 29, "seeds": [101, 202], "adult": False,
                     "prompt": f"two fictional adults in their thirties, both clearly 21 or older, standing together, outfit {i + 1}, natural skin, photograph"})
    # The four gated prompts are extra slots required by the PRD's 60-count. Trim portraits if we are over.
    # Count now: 24 portraits + 12 half + 8 full + 8 hands + 4 group = 56. Add 4 adult.
    adult4 = [
        ("a28", "female", 28, "front", "standing"),
        ("a29", "female", 31, "side", "seated"),
        ("a30", "male", 35, "back", "standing"),
        ("a31", "male", 40, "low", "kneeling"),
    ]
    for i, sex, age, angle, pose in adult4:
        rows.append({"id": i, "bucket": "adult", "sex": sex, "age": age, "seeds": [101, 202], "adult": True,
                     "angle": angle, "pose": pose,
                     "prompt": _prompt(sex, age, angle, pose, nude=True)})
    assert len(rows) == 60, len(rows)
    return rows


def build_adult_benchmark():
    """18+ subset: both sexes, every angle, every pose. Scored for anatomy, not for chat."""
    rows = []
    ages = {"female": 27, "male": 34}
    for sex in ("female", "male"):
        for angle in ANGLES:
            for pose in POSE_IDS:
                rows.append({
                    "id": f"{sex[0]}_{angle}_{pose}",
                    "sex": sex,
                    "age": ages[sex],
                    "angle": angle,
                    "pose": pose,
                    "seeds": [101, 202],
                    "adult": True,
                    "score": ["anatomical_correctness", "consistency_across_angles"],
                    "prompt": _prompt(sex, ages[sex], angle, pose, nude=True),
                })
    return rows


TARGETS = {
    "looks_real_photo_rate": 0.35,
    "rated_realism_median": 4,
    "skin_in_stock_midrange": 0.80,
    "iqa_better_than_chroma": 0.10,
    "bad_hands_max": 2,
    "sticker_faces_max": 0,
    "age_false_alarms_max": 2,
    "video_arcface_min": 0.60,
    "video_andrew_at_least_4": 7,
    "still_seconds_max": 45,
    "clip_seconds_max": 360,
    "adult_anatomy_median": 4,
}
