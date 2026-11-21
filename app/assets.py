"""Picture helpers done on the Easy Studio side (no GPU): compositing, sheets, sprite sheets, zips."""
import base64
import io
import json
import math
import re
import os
import zipfile

import numpy as np

from PIL import Image, ImageDraw, ImageFont


def decode_data_url(data_url):
    if not data_url or "," not in data_url:
        raise ValueError("No mask was painted.")
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1])))


def prepare_mask(data_url, size, out_path):
    """The brush mask from the web page -> a white-on-black PNG the size of the picture.
    Anything painted (any alpha or bright pixel) counts as 'change this'."""
    m = decode_data_url(data_url).convert("RGBA")
    a = np.array(m.split()[3])
    lum = np.array(m.convert("RGB").convert("L"))
    # opaque mask (white strokes on black) -> use brightness; transparent canvas -> use painted alpha
    arr = lum if a.min() == 255 else a
    mask = Image.fromarray(arr.astype("uint8"))
    mask = mask.point(lambda v: 255 if v > 32 else 0).resize(size, Image.NEAREST)
    if mask.getbbox() is None:
        raise ValueError("The mask is empty -- paint over the area you want to change first.")
    mask.convert("RGB").save(out_path)
    return out_path


def composite(cutout_path, background_path, out_path, scale=0.9, anchor="bottom"):
    """Put a transparent cut-out on top of a background picture."""
    bg = Image.open(background_path).convert("RGBA")
    fg = Image.open(cutout_path).convert("RGBA")
    box = fg.getbbox() or (0, 0, fg.width, fg.height)
    fg = fg.crop(box)
    s = min(bg.width * scale / fg.width, bg.height * scale / fg.height)
    fg = fg.resize((max(1, int(fg.width * s)), max(1, int(fg.height * s))), Image.LANCZOS)
    x = (bg.width - fg.width) // 2
    y = bg.height - fg.height if anchor == "bottom" else (bg.height - fg.height) // 2
    bg.alpha_composite(fg, (x, max(0, y)))
    bg.convert("RGB").save(out_path)
    return out_path


def solid_background(size, color, out_path):
    Image.new("RGB", size, color).save(out_path)
    return out_path


def _font(size):
    for f in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def sheet(paths, labels, out_path, cols=None, cell_h=768, bg=(255, 255, 255), label_h=48):
    """Lay pictures out in a grid with a label under each (turnaround / expression sheet)."""
    ims = [Image.open(p).convert("RGBA") for p in paths]
    cols = cols or len(ims)
    rows = math.ceil(len(ims) / cols)
    cells = []
    for im in ims:
        s = cell_h / im.height
        cells.append(im.resize((max(1, int(im.width * s)), cell_h), Image.LANCZOS))
    cell_w = max(c.width for c in cells)
    W, H = cols * cell_w, rows * (cell_h + label_h)
    out = Image.new("RGBA", (W, H), bg + (255,))
    d = ImageDraw.Draw(out)
    f = _font(28)
    for i, c in enumerate(cells):
        x0 = (i % cols) * cell_w + (cell_w - c.width) // 2
        y0 = (i // cols) * (cell_h + label_h)
        out.alpha_composite(c, (x0, y0))
        if labels:
            t = labels[i]
            tw = d.textlength(t, font=f)
            d.text(((i % cols) * cell_w + (cell_w - tw) / 2, y0 + cell_h + 8), t, fill=(40, 40, 40), font=f)
    out.convert("RGB").save(out_path)
    return out_path


def sprite_sheet(frame_paths, out_png, out_json, cols=8, max_cell=512):
    """Frames -> one PNG (transparent if frames are) + a JSON atlas (TexturePacker-style 'frames' hash)."""
    ims = [Image.open(p).convert("RGBA") for p in frame_paths]
    w, h = ims[0].size
    s = min(1.0, max_cell / max(w, h))
    cw, ch = max(1, int(w * s)), max(1, int(h * s))
    cols = max(1, min(cols, len(ims)))
    rows = math.ceil(len(ims) / cols)
    out = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    frames = {}
    for i, im in enumerate(ims):
        x, y = (i % cols) * cw, (i // cols) * ch
        out.alpha_composite(im.resize((cw, ch), Image.LANCZOS), (x, y))
        frames[f"frame_{i:03d}"] = {"frame": {"x": x, "y": y, "w": cw, "h": ch}, "rotated": False, "trimmed": False,
                                    "spriteSourceSize": {"x": 0, "y": 0, "w": cw, "h": ch}, "sourceSize": {"w": cw, "h": ch}}
    out.save(out_png)
    meta = {"frames": frames, "meta": {"app": "Easy Studio", "image": os.path.basename(out_png),
                                       "size": {"w": out.width, "h": out.height}, "scale": "1",
                                       "columns": cols, "rows": rows, "frame_count": len(ims)}}
    with open(out_json, "w") as f:
        json.dump(meta, f, indent=1)
    return out_png, out_json


def zip_files(pairs, out_path):
    """pairs = [(path_on_disk, name_in_zip)]"""
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p, name in pairs:
            if os.path.exists(p):
                z.write(p, name)
    return out_path


def to_png(src, out_path, max_side=4096):
    """Normalise an upload to PNG (strips metadata), limits size."""
    im = Image.open(src)
    im.load()
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    im.save(out_path, "PNG")
    return out_path


def split_sprite_sheet(sheet_png, atlas_json, out_dir):
    """Cut a sprite sheet back into one PNG per frame (Godot SpriteFrames uses single textures)."""
    os.makedirs(out_dir, exist_ok=True)
    meta = json.load(open(atlas_json))
    names = []
    with Image.open(sheet_png) as sheet:
        for name, fr in sorted(meta["frames"].items()):
            f = fr["frame"]
            fn = re.sub(r"[^A-Za-z0-9_]+", "_", name) + ".png"
            sheet.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"])).save(os.path.join(out_dir, fn))
            names.append(fn)
    return names
