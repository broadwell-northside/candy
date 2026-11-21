"""Style presets, aspect ratios and video sizes. Edit freely -- it's just text."""

IMAGE_MODELS = {
    "Realistic / painterly (Chroma1-HD)": {
        "workflow": "image_chroma1hd_api.json",
        "negative": "low quality, blurry, deformed hands, extra fingers, bad anatomy, watermark, text, jpeg artifacts",
        "base": 1024,
    },
    "Anime / illustrated (NoobAI-XL)": {
        "workflow": "image_noobai_xl_api.json",
        "negative": "worst quality, low quality, bad anatomy, extra fingers, watermark, signature, text",
        "base": 1024,
        "prefix": "masterpiece, best quality, newest, absurdres, ",
    },
}

STYLE_PRESETS = {
    "None (just my words)": "",
    "Cinematic photo": "cinematic film still, dramatic lighting, shallow depth of field, 35mm photo, rich color grading",
    "Game character art": "video game character concept art, full body, detailed costume, clean background, sharp focus",
    "Fantasy painting": "epic fantasy oil painting, painterly brushwork, glowing magical light, highly detailed",
    "Dark & moody": "low-key lighting, deep shadows, moody atmosphere, neon rim light, film grain",
    "Soft glamour": "soft glamour photography, warm golden-hour light, smooth skin, elegant pose, bokeh",
    "Anime key art": "anime key visual, vibrant colors, clean line art, cel shading, detailed eyes",
    "Comic / graphic novel": "graphic novel panel, bold ink lines, halftone shading, dynamic composition",
    "3D render": "high-end 3D render, subsurface scattering, octane render, studio lighting",
    "Sci-fi": "sci-fi setting, sleek futuristic armor, holographic lights, spaceship interior",
}

# label -> (width_ratio, height_ratio)
ASPECTS = {
    "Square 1:1": (1, 1),
    "Portrait 2:3": (2, 3),
    "Tall 9:16": (9, 16),
    "Landscape 3:2": (3, 2),
    "Wide 16:9": (16, 9),
}

VIDEO_QUALITY = {
    "Fast (4 steps, ~1-2 min per clip on RTX PRO 6000)": "video_wan22_i2v_fast_api.json",
    "Best quality (20 steps, ~5-10x slower)": "video_wan22_i2v_quality_api.json",
}

# label -> target pixel area
VIDEO_SIZES = {
    "480p (fast drafts)": 832 * 480,
    "720p (final)": 1280 * 720,
}

VIDEO_NEGATIVE = ("static, still image, blurry, low quality, jpeg artifacts, deformed, extra limbs, "
                  "bad hands, watermark, subtitles, flicker, anime, cartoon, animated, 3D render, illustration")
WAN_FPS = 16


def size_for_aspect(ratio_w, ratio_h, area, multiple=16):
    """Width/height with about `area` pixels, the given aspect ratio, divisible by `multiple`."""
    import math
    w = math.sqrt(area * ratio_w / ratio_h)
    h = w * ratio_h / ratio_w
    w = max(multiple, int(round(w / multiple)) * multiple)
    h = max(multiple, int(round(h / multiple)) * multiple)
    return w, h


def frames_for_seconds(seconds, fps=WAN_FPS):
    """Wan needs a frame count of the form 4n+1 (e.g. 81 = 5 s at 16 fps)."""
    n = int(round(seconds * fps))
    return max(5, (n // 4) * 4 + 1)
