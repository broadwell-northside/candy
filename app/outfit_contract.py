"""Outfit edits keep the approved source and the pixels outside the mask.

Identity, the garment text, and the untouched region are recorded separately.
A later edit starts from the approved source, not from the previous edit.
"""
from PIL import Image


def approved_source_id(item):
    prov = (item or {}).get("provenance") or {}
    return prov.get("approved_source") or (item or {}).get("id")


def composite_unmasked(original_path, edited_path, mask, out_path):
    """White mask pixels may change. Every other pixel stays the original."""
    with Image.open(original_path) as im:
        original = im.convert("RGB")
    with Image.open(edited_path) as im:
        edited = im.convert("RGB")
    resized = edited.size != original.size
    if resized:
        edited = edited.resize(original.size, Image.Resampling.NEAREST)
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.Resampling.NEAREST)
    out = original.copy()
    op = out.load()
    ep = edited.load()
    mp = mask.convert("L").load()
    outside = edited_n = 0
    for y in range(original.height):
        for x in range(original.width):
            if mp[x, y] >= 128:
                op[x, y] = ep[x, y]
                edited_n += 1
            else:
                outside += 1
    out.save(out_path, "PNG")
    return {
        "identity": "outside_mask",
        "unchanged_region": "exact",
        "outside_pixels": outside,
        "edited_pixels": edited_n,
        "resized_edit": resized,
    }
