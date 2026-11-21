#!/usr/bin/env python3
"""Draw the placeholder pictures and the wave and wind sounds.

These are simple shapes, not real people and not photos. Run this again any
time you want to rebuild them. The game ships with the results already made.
"""

import math
import os
import random
import struct
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 1280, 720


def font(size, bold=False):
    path = FONT_BOLD if bold and os.path.exists(FONT_BOLD) else FONT_PATH
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = lerp(top, bottom, t)
        for x in range(w):
            px[x, y] = c
    return img


def vertical_bands(img, stops):
    """stops: list of (y_fraction, color)."""
    w, h = img.size
    px = img.load()
    stops = sorted(stops)
    for y in range(h):
        fy = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            y0, c0 = stops[i]
            y1, c1 = stops[i + 1]
            if y0 <= fy <= y1:
                t = 0 if y1 == y0 else (fy - y0) / (y1 - y0)
                c = lerp(c0, c1, t)
                for x in range(w):
                    px[x, y] = c
                break
    return img


def ellipse(draw, box, fill):
    draw.ellipse(box, fill=fill)


def person(draw, cx, foot, scale, skin, cloth, hair, covered, extra=None):
    """A geometric adult silhouette. No face detail and no bare body."""
    s = scale
    head_r = 46 * s
    head_cy = foot - 400 * s
    # Hair sits behind the head.
    ellipse(draw, [cx - head_r * 1.2, head_cy - head_r * 1.45, cx + head_r * 1.2, head_cy + head_r * 0.15], hair)
    ellipse(draw, [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], skin)
    top = head_cy + head_r + 6 * s
    if covered:
        bot = foot - 18 * s
        half = 92 * s
    else:
        # Shorter tunic. Still a solid shape, not a body study.
        bot = foot - 70 * s
        half = 74 * s
    draw.rounded_rectangle([cx - half, top, cx + half, bot], radius=int(36 * s), fill=cloth)
    leg_w = 26 * s
    gap = 14 * s
    leg_top = bot - 8 * s
    draw.rounded_rectangle([cx - gap - leg_w, leg_top, cx - gap, foot], radius=int(10 * s), fill=skin)
    draw.rounded_rectangle([cx + gap, leg_top, cx + gap + leg_w, foot], radius=int(10 * s), fill=skin)
    arm_w = 22 * s
    arm_bot = top + 160 * s
    draw.rounded_rectangle([cx - half - arm_w + 6 * s, top + 18 * s, cx - half + 10 * s, arm_bot], radius=int(10 * s), fill=skin)
    draw.rounded_rectangle([cx + half - 10 * s, top + 18 * s, cx + half + arm_w - 6 * s, arm_bot], radius=int(10 * s), fill=skin)
    if extra == "hat":
        ellipse(draw, [cx - head_r * 1.7, head_cy - head_r * 0.2, cx + head_r * 1.7, head_cy + head_r * 0.35], (212, 168, 74))
        draw.rectangle([cx - head_r * 0.55, head_cy - head_r * 1.7, cx + head_r * 0.55, head_cy - head_r * 0.1], fill=(196, 148, 62))
    elif extra == "book":
        draw.rounded_rectangle([cx + half * 0.15, top + 70 * s, cx + half + 36 * s, top + 110 * s], radius=4, fill=(92, 58, 42))
    elif extra == "scarf":
        ellipse(draw, [cx - 34 * s, head_cy + head_r - 4 * s, cx + 34 * s, head_cy + head_r + 28 * s], (242, 193, 78))


PEOPLE = {
    "mira": {"skin": (198, 140, 102), "cloth": (196, 107, 74), "cloth_adult": (42, 122, 132), "hair": (42, 28, 24), "extra": {"smile": "scarf", "thoughtful": "book", "neutral": None}},
    "leo": {"skin": (176, 122, 86), "cloth": (36, 78, 112), "cloth_adult": (24, 92, 104), "hair": (88, 86, 84), "extra": {"smile": None, "thoughtful": "book", "neutral": None}},
    "nia": {"skin": (94, 58, 40), "cloth": (110, 140, 104), "cloth_adult": (196, 120, 72), "hair": (54, 36, 28), "extra": {"smile": "hat", "thoughtful": "hat", "neutral": "hat"}},
}


def save(img, *parts):
    path = os.path.join(ASSETS, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG")
    print("wrote", os.path.relpath(path, ROOT))
    return path


def draw_sky_sea_sand(stops, sand, foam_y):
    img = Image.new("RGB", (W, H))
    vertical_bands(img, stops)
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, foam_y + 18, W, H], fill=sand)
    # A soft foam line.
    for i, x in enumerate(range(0, W, 8)):
        y = foam_y + int(6 * math.sin(i * 0.35))
        dr.ellipse([x, y, x + 22, y + 10], fill=(244, 239, 228))
    return img


def clouds(dr, specs, color):
    for cx, cy, rw, rh in specs:
        ellipse(dr, [cx - rw, cy - rh, cx + rw, cy + rh], color)
        ellipse(dr, [cx - rw * 0.7, cy - rh * 1.3, cx + rw * 0.2, cy + rh * 0.2], color)


def beach(kind):
    if kind == "morning":
        img = draw_sky_sea_sand(
            [(0, (248, 220, 176)), (0.34, (156, 206, 214)), (0.52, (232, 244, 236)), (0.62, (30, 124, 142)), (0.78, (14, 76, 92))],
            (230, 199, 138),
            470,
        )
        dr = ImageDraw.Draw(img)
        ellipse(dr, [900, 90, 1010, 200], (246, 196, 83))
        clouds(dr, [(180, 120, 70, 24), (260, 110, 46, 18), (520, 80, 80, 22)], (255, 248, 236))
    elif kind == "midday":
        img = draw_sky_sea_sand(
            [(0, (120, 196, 228)), (0.28, (232, 246, 252)), (0.48, (186, 226, 232)), (0.60, (20, 128, 154)), (0.78, (12, 86, 112))],
            (240, 215, 162),
            455,
        )
        dr = ImageDraw.Draw(img)
        ellipse(dr, [590, 36, 690, 136], (255, 236, 170))
        clouds(dr, [(240, 150, 90, 26), (980, 120, 76, 22)], (255, 255, 255))
    elif kind == "sunset":
        img = draw_sky_sea_sand(
            [(0, (92, 48, 92)), (0.28, (232, 112, 74)), (0.46, (246, 186, 110)), (0.58, (26, 62, 86)), (0.78, (16, 40, 58))],
            (201, 132, 90),
            468,
        )
        dr = ImageDraw.Draw(img)
        ellipse(dr, [120, 300, 280, 460], (246, 170, 90))
        clouds(dr, [(700, 160, 100, 20), (860, 190, 60, 16)], (244, 140, 110))
    else:
        img = draw_sky_sea_sand(
            [(0, (8, 18, 36)), (0.40, (18, 42, 68)), (0.55, (10, 36, 52)), (0.70, (8, 28, 40))],
            (58, 70, 80),
            480,
        )
        dr = ImageDraw.Draw(img)
        ellipse(dr, [980, 70, 1060, 150], (232, 228, 210))
        ellipse(dr, [1000, 78, 1072, 150], (12, 24, 42))
        rnd = random.Random(kind)
        for _ in range(40):
            x, y = rnd.randrange(0, W), rnd.randrange(20, 300)
            r = rnd.choice([1, 1, 2])
            dr.ellipse([x, y, x + r, y + r], fill=(240, 236, 220))
    # Distant headland, so the beach reads as an island.
    dr = ImageDraw.Draw(img)
    dr.polygon([(0, 430), (180, 360), (320, 420), (0, 450)], fill=(20, 70, 78))
    return img


def title_image():
    img = beach("morning").convert("RGBA")
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(veil).rectangle([0, 0, 620, H], fill=(10, 40, 48, 90))
    return Image.alpha_composite(img, veil).convert("RGB")


def map_image():
    img = vertical_bands(Image.new("RGB", (W, H)), [
        (0, (14, 90, 112)),
        (1, (10, 58, 78)),
    ])
    dr = ImageDraw.Draw(img)
    # Soft shallows.
    ellipse(dr, [180, 80, 1100, 660], (32, 140, 150))
    ellipse(dr, [260, 140, 1020, 600], (214, 186, 120))
    # Green interior.
    ellipse(dr, [340, 180, 940, 520], (90, 140, 96))
    # Lagoon pool.
    ellipse(dr, [700, 280, 900, 420], (64, 168, 176))
    # Cliffs to the north.
    dr.polygon([(560, 150), (700, 120), (820, 190), (760, 250), (600, 240)], fill=(120, 116, 112))
    # Village squares.
    for x, y in ((360, 320), (400, 340), (380, 370)):
        dr.rectangle([x, y, x + 28, y + 22], fill=(232, 220, 196))
        dr.polygon([(x - 4, y), (x + 14, y - 16), (x + 32, y)], fill=(168, 84, 62))
    # Hut.
    dr.rectangle([980, 250, 1040, 310], fill=(196, 140, 90))
    dr.polygon([(968, 250), (1010, 214), (1052, 250)], fill=(120, 64, 48))
    # Beach sand along the south shore.
    ellipse(dr, [430, 470, 860, 600], (230, 196, 130))
    return img


def portrait(person_id, mood, variant):
    spec = PEOPLE[person_id]
    img = Image.new("RGBA", (480, 720), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    # A soft ground shadow so the figure sits somewhere.
    ellipse(dr, [120, 640, 360, 690], (20, 30, 34, 50))
    covered = variant == "covered"
    cloth = spec["cloth"] if covered else spec["cloth_adult"]
    extra = spec["extra"].get(mood)
    person(dr, 240, 660, 1.15, spec["skin"], cloth, spec["hair"], covered, extra)
    # Corner tab so the two variants are easy to tell apart before real art arrives.
    tab = (232, 214, 180) if covered else (196, 107, 74)
    dr.rounded_rectangle([248, 430, 456, 478], radius=12, fill=tab)
    label = "covered" if covered else "adult variant"
    dr.text((268, 442), label, font=font(18, True), fill=(27, 42, 48))
    return img


def walker(person_id):
    spec = PEOPLE[person_id]
    img = Image.new("RGBA", (200, 360), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    person(dr, 100, 340, 0.55, spec["skin"], spec["cloth"], spec["hair"], True, spec["extra"].get("neutral"))
    return img


def scene_card(bg_kind, person_id, caption, variant, badge):
    img = beach(bg_kind).convert("RGBA")
    fig = portrait(person_id, "neutral", variant).resize((280, 420), Image.Resampling.LANCZOS)
    img.alpha_composite(fig, (900, 150))
    veil = Image.new("RGBA", (W, 110), (8, 28, 34, 150))
    img.alpha_composite(veil, (0, H - 110))
    dr = ImageDraw.Draw(img)
    dr.text((48, H - 78), caption, font=font(28, True), fill=(251, 246, 238))
    dr.text((48, H - 40), badge, font=font(18), fill=(230, 214, 186))
    return img.convert("RGB")


def icon():
    img = Image.new("RGB", (128, 128), (14, 60, 72))
    dr = ImageDraw.Draw(img)
    dr.ellipse([16, 18, 112, 112], fill=(30, 130, 146))
    dr.ellipse([28, 70, 100, 120], fill=(230, 196, 130))
    dr.ellipse([78, 22, 108, 52], fill=(246, 196, 83))
    return img


def write_wav(path, samples, rate=22050):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples)
        handle.writeframes(frames)
    print("wrote", os.path.relpath(path, ROOT))


def sound_waves():
    rate = 22050
    n = rate * 4
    rnd = random.Random(7)
    low = 0.0
    out = []
    for i in range(n):
        swell = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * i / (rate * 2.4)))
        # A second slower swell so the loop feels like sets of waves.
        swell *= 0.7 + 0.3 * math.sin(2 * math.pi * i / (rate * 4.0))
        noise = rnd.uniform(-1, 1)
        low = low * 0.94 + noise * 0.06
        out.append(low * swell * 0.55)
    # Ease the join so the loop does not click.
    fade = rate // 20
    for i in range(fade):
        t = i / fade
        out[i] *= t
        out[-1 - i] *= t
    return out


def sound_wind():
    rate = 22050
    n = rate * 4
    rnd = random.Random(11)
    band = 0.0
    out = []
    for i in range(n):
        gust = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(2 * math.pi * i / (rate * 3.1) + 0.6))
        noise = rnd.uniform(-1, 1)
        band = band * 0.8 + noise * 0.2
        out.append(band * gust * 0.22)
    fade = rate // 20
    for i in range(fade):
        t = i / fade
        out[i] *= t
        out[-1 - i] *= t
    return out


def maybe_video(still_path, dest):
    if shutil_which("ffmpeg") is None:
        print("ffmpeg not found, skipped", dest)
        return
    subprocess.check_call([
        "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", still_path,
        "-t", "2", "-r", "12", "-c:v", "libtheora", "-q:v", "6", "-pix_fmt", "yuv420p", "-an", dest,
    ])
    print("wrote", os.path.relpath(dest, ROOT))


def shutil_which(name):
    from shutil import which
    return which(name)


def main():
    for kind in ("morning", "midday", "sunset", "night"):
        save(beach(kind), "backgrounds", f"beach_{kind}.png")
    save(title_image(), "backgrounds", "title.png")
    save(map_image(), "backgrounds", "map.png")
    icon().save(os.path.join(ROOT, "icon.png"), "PNG")
    print("wrote icon.png")
    for pid in PEOPLE:
        os.makedirs(os.path.join(ASSETS, "characters", pid), exist_ok=True)
        for mood in ("neutral", "smile", "thoughtful"):
            for variant in ("covered", "adult"):
                save(portrait(pid, mood, variant), "characters", pid, f"{mood}_{variant}.png")
        save(walker(pid), "characters", pid, "walker.png")
    stems = {
        "swim": ("midday", "mira", "You swim until the sand lets go"),
        "sun": ("midday", "leo", "You lie in the sun"),
        "walk": ("morning", "nia", "You walk the shoreline"),
        "sun_mira_close": ("sunset", "mira", "The place Mira kept for you"),
    }
    for stem, (bg, pid, caption) in stems.items():
        for variant in ("covered", "adult"):
            badge = "Placeholder  ·  covered" if variant == "covered" else "Placeholder  ·  adult variant"
            path = save(scene_card(bg, pid, caption, variant, badge), "scenes", f"{stem}_{variant}.png")
            if stem == "swim" and variant == "covered":
                maybe_video(path, os.path.join(ASSETS, "scenes", "swim_covered.ogv"))
    write_wav(os.path.join(ASSETS, "audio", "waves.wav"), sound_waves())
    write_wav(os.path.join(ASSETS, "audio", "wind.wav"), sound_wind())
    write_plate_stand_in()


def write_plate_stand_in():
    """A person-shaped Stage 1 plate. Words stay off the body."""
    width, height = 480, 1080
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _plate_person(draw, width // 2, height)
    folder = os.path.join(ASSETS, "plates")
    os.makedirs(folder, exist_ok=True)
    image_path = os.path.join(folder, "stand_in.png")
    image.save(image_path, "PNG")
    print("wrote", os.path.relpath(image_path, ROOT))
    alpha = image.getchannel("A")
    depth = Image.new("L", (width, height), 0)
    alpha_px = alpha.load()
    depth_px = depth.load()
    center = width // 2
    for y in range(height):
        face = 1.0 - min(1.0, abs(y - 150) / 120.0)
        chest = 1.0 - min(1.0, abs(y - 420) / 180.0)
        for x in range(width):
            if alpha_px[x, y] < 128:
                continue
            side = min(1.0, abs(x - center) / 150.0)
            shade = (1.0 - side * 0.65) * (0.35 + 0.65 * max(face, chest * 0.85))
            depth_px[x, y] = int(max(0, min(255, shade * 255)))
    depth_path = os.path.join(folder, "stand_in_depth.png")
    depth.save(depth_path, "PNG")
    print("wrote", os.path.relpath(depth_path, ROOT))


def _plate_person(draw, cx, height):
    """Standing adult cutout. Eyes sit on the plate's eye line. Feet touch the bottom."""
    skin = (198, 148, 116, 255)
    skin_shadow = (168, 116, 88, 255)
    hair = (46, 30, 26, 255)
    shirt = (232, 214, 190, 255)
    shirt_fold = (206, 178, 150, 255)
    trousers = (58, 78, 92, 255)
    shoes = (48, 36, 32, 255)
    eye_y = int(round(height * (1.0 - 1.55 / 1.8)))
    # Crown sits just above the eyes. The card above the hair stays clear.
    crown = eye_y - 72
    chin = eye_y + 78
    shoulder = chin + 36
    hip = int(height * 0.58)
    foot = height - 1

    def leg(side):
        inner = 10
        outer = 46
        knee = hip + int((foot - hip) * 0.46)
        draw.polygon([
            (cx + side * inner, hip - 8),
            (cx + side * outer, hip + 10),
            (cx + side * (outer - 4), knee),
            (cx + side * (outer - 8), foot - 28),
            (cx + side * (inner + 6), foot - 28),
            (cx + side * (inner - 2), knee),
        ], fill=trousers)
        shoe_a = cx + side * (inner - 4)
        shoe_b = cx + side * (outer + 6)
        draw.ellipse([min(shoe_a, shoe_b), foot - 36, max(shoe_a, shoe_b), foot], fill=shoes)

    leg(-1)
    leg(1)
    draw.polygon([
        (cx - 108, shoulder + 8),
        (cx - 132, shoulder + 70),
        (cx - 118, hip - 30),
        (cx - 96, hip + 10),
        (cx - 78, shoulder + 24),
    ], fill=skin)
    draw.polygon([
        (cx + 108, shoulder + 8),
        (cx + 132, shoulder + 70),
        (cx + 118, hip - 30),
        (cx + 96, hip + 10),
        (cx + 78, shoulder + 24),
    ], fill=skin)
    draw.ellipse([cx - 128, hip - 48, cx - 96, hip - 16], fill=skin_shadow)
    draw.ellipse([cx + 96, hip - 48, cx + 128, hip - 16], fill=skin_shadow)
    draw.polygon([
        (cx - 102, shoulder),
        (cx + 102, shoulder),
        (cx + 78, shoulder + 150),
        (cx + 64, hip),
        (cx - 64, hip),
        (cx - 78, shoulder + 150),
    ], fill=shirt)
    draw.polygon([
        (cx - 18, shoulder + 8),
        (cx + 18, shoulder + 8),
        (cx + 8, shoulder + 70),
        (cx - 8, shoulder + 70),
    ], fill=shirt_fold)
    draw.polygon([
        (cx - 24, chin - 8),
        (cx + 24, chin - 8),
        (cx + 18, shoulder + 16),
        (cx - 18, shoulder + 16),
    ], fill=skin)
    draw.ellipse([cx - 84, crown - 16, cx + 84, eye_y - 4], fill=hair)
    draw.polygon([
        (cx - 72, crown + 24), (cx - 80, eye_y + 18), (cx - 52, chin - 8), (cx - 46, crown + 36),
    ], fill=hair)
    draw.polygon([
        (cx + 72, crown + 24), (cx + 80, eye_y + 18), (cx + 52, chin - 8), (cx + 46, crown + 36),
    ], fill=hair)
    draw.ellipse([cx - 68, crown + 6, cx + 68, chin], fill=skin)
    draw.ellipse([cx - 22, eye_y - 6, cx - 8, eye_y + 8], fill=(250, 244, 236, 255))
    draw.ellipse([cx + 8, eye_y - 6, cx + 22, eye_y + 8], fill=(250, 244, 236, 255))
    draw.ellipse([cx - 18, eye_y - 4, cx - 10, eye_y + 6], fill=(36, 24, 20, 255))
    draw.ellipse([cx + 10, eye_y - 4, cx + 18, eye_y + 6], fill=(36, 24, 20, 255))
    draw.arc([cx - 18, eye_y + 28, cx + 18, eye_y + 52], 15, 165, fill=(120, 72, 58, 255), width=3)


if __name__ == "__main__":
    main()
