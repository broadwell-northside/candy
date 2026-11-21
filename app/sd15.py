# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Stable Diffusion 1.5 as a Create engine: "Photo (SD 1.5)".

It rides the normal Create job (job_create), so the stated age, the prompt rails and the age check on every
output apply exactly as they do for the other engines. This file holds only what is different: the template,
the negative words and the picture sizes, which are about 512 pixels because the model was trained there.
The card for it is in machine_profiles.json ("engines" -> "sd15").
"""
import machine_profiles

WORKFLOW = "image_sd15_api.json"
LABEL = "Stable Diffusion 1.5"
NEGATIVE = ("low quality, blurry, deformed hands, extra fingers, bad anatomy, watermark, text, jpeg artifacts, "
            "cropped, out of frame")
_SIDES = {"portrait": (512, 768), "square": (512, 512), "wide": (768, 512), "tall": (512, 768)}


def card():
    return (machine_profiles.load().get("engines") or {}).get("sd15") or {}


def size_for(aspect):
    return _SIDES.get(aspect, _SIDES["portrait"])


def wants(params):
    return str((params or {}).get("engine") or "") == "sd15"
