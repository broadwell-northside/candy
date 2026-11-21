"""Which model does which job.

Research on the best photoreal models is still moving, so the app reads this
registry instead of scattering file names through the pages. The defaults below
are placeholders. Codex will publish six tracks under evidence/research/ with a
default and two fallbacks each: skin and faces, video, character consistency,
video-to-3D, realistic 3D humans, and non-explicit Candy benchmark clips. Until
those notes exist, do not treat these ids as a locked pick.

On the desktop, a file at outputs/model_registry.json (or the path in
EASY_STUDIO_MODEL_REGISTRY) can replace a role's model, workflow, or weights.
It cannot lower the age floor or turn off the 18+ gate.
"""
import copy
import json
import os

DEFAULTS = {
    "version": 2,
    # Photoreal clips only. 2 s is the Lightning preview. 5 s is the quality take.
    "clip_lengths": {"preview_s": 2, "take_s": 5, "allowed_s": [2, 5]},
    "pipeline": ["still", "motion", "fix", "finish"],
    "roles": {
        "still_realistic": {
            "id": "z_image_turbo",
            "label": "Z-Image Turbo",
            "workflow": "image_zimage_turbo_api.json",
            "shift": 2,
            "steps": 9,
            "cfg": 1,
            "skin_words": True,
            "grain": 0.025,
            "face_denoise": 0.35,
            "upscale": True,
        },
        # Identity LoRA stills. The LoRA is trained on the foundation checkpoint and
        # loaded on that same checkpoint. It is not loaded on Z-Image-Turbo.
        "still_identity": {
            "id": "z_image",
            "label": "Z-Image",
            "workflow": "image_zimage_api.json",
            "shift": 3,
            "steps": 8,
            "cfg": 1,
            "adult_only": False,
        },
        "still_film": {
            "id": "krea2_turbo",
            "label": "Krea 2",
            "workflow": "image_krea2_api.json",
            "shift": 2,
            "steps": 8,
            "cfg": 1,
            "skin_words": True,
            "grain": 0.04,
            "face_denoise": 0.35,
            "upscale": True,
        },
        "still_glam": {
            "id": "z_image_turbo",
            "label": "Z-Image Turbo",
            "workflow": "image_zimage_turbo_api.json",
            "shift": 3,
            "steps": 8,
            "cfg": 1,
            "skin_words": False,
            "grain": 0,
            "face_denoise": 0.28,
            "upscale": True,
        },
        "still_draft": {
            "id": "flux2_klein_4b",
            "label": "FLUX.2 klein",
            "workflow": "image_flux2_klein_api.json",
            "steps": 4,
            "cfg": 1,
            "skin_words": False,
            "grain": 0,
            "face_denoise": None,
            "upscale": False,
        },
        # Flux.1 dev: part of Ak's proven stack (D-10), the first-class alternate photoreal base. Gated weights
        # (Hugging Face licence); FluxGuidance 3.5 with cfg 1, so the NEGATIVE node is present but has no effect.
        "still_flux": {
            "id": "flux1_dev",
            "label": "Flux.1 dev",
            "workflow": "image_flux1dev_api.json",
            "steps": 20,
            "cfg": 1,
            "skin_words": True,
            "grain": 0.02,
            "face_denoise": 0.35,
            "upscale": True,
        },
        "still_adult_fallback": {
            "id": "chroma1hd",
            "label": "Chroma1-HD",
            "workflow": "image_chroma1hd_api.json",
            "adult_only": True,
            "skin_words": False,
            "grain": 0.02,
            "face_denoise": 0.35,
            "upscale": True,
        },
        "video_i2v": {
            "id": "wan22_i2v",
            "label": "Wan 2.2 I2V",
            "workflow_fast": "video_wan22_i2v_fast_api.json",
            "workflow_quality": "video_wan22_i2v_quality_api.json",
            "workflow_flf_fast": "video_wan22_flf2v_fast_api.json",
            "workflow_flf_quality": "video_wan22_flf2v_quality_api.json",
            "family": "wan14b",
            "fps": 16,
        },
        "video_upscale": {
            "id": "seedvr2_7b_sharp",
            "label": "SeedVR2 7B sharp",
            "weights": "seedvr2_7b_sharp_fp16.safetensors",
            "vae": "seedvr2_ema_vae_fp16.safetensors",
            "scale": 2,
            "target": "1080p",
            "color_correction": "lab",
        },
        "video_interpolate": {
            "id": "gimm_vfi",
            "label": "GIMM-VFI",
            "weights": ["gimmvfi_r_arb_lpips_fp32.safetensors", "gimmvfi_f_arb_lpips_fp32.safetensors"],
            "from_fps": 16,
            "to_fps": 30,
        },
        "video_control": {
            "id": "scail2",
            "label": "SCAIL-2",
            "backups": [
                {"id": "wan_animate", "label": "Wan 2.2 Animate"},
                {"id": "vace_fun", "label": "Wan2.2-VACE-Fun"},
            ],
        },
        "video_long": {
            "id": "svi2_pro",
            "label": "SVI 2.0 Pro",
            "also": ["flf2v"],
            "color_match": True,
        },
        "video_fix": {
            "id": "regional_repair",
            "label": "Regional repair",
            "method": "vace_inpaint",
        },
        "video_preview": {
            "id": "wan22_lightning",
            "label": "Lightning preview",
            "steps": "2+2",
            "seconds": 2,
        },
        "video_lora_stack": {
            "id": "wan_nsfw_act_anatomy",
            "label": "Wan NSFW, act, and anatomy stack",
            "adult_only": True,
            "nsfw": {"name": "wan_general_nsfw", "high": 0.7, "low": 1.0},
            "act": {"max_count": 1},
            "anatomy_strength": [0.6, 0.8],
        },
        "skin_lora": {
            "id": "one_skin_lora",
            "strength": 0.5,
            "close_up_only": True,
            "max_count": 1,
        },
    },
    # Selectable. The running default stays video_i2v until a local test picks one.
    # No weights are downloaded from these names.
    "sampling": {
        "shift_default": 8,
        "nag_when_cfg": 1,
        "clean_pass_steps": 2,
        "max_frames": 81,
        "chain_overlap_frames": [4, 6],
        "proofer": "wan22_ti2v_5b",
    },
    "video_checkpoints": [
        {"id": "wan22_i2v", "label": "Wan 2.2 I2V", "selected_by_default": True, "tested_locally": False},
        {"id": "wan22_remix", "label": "Wan2.2-Remix", "steps": "4-8", "cfg": 1, "shift": "5-10",
         "sampler": "euler", "scheduler": "simple", "tested_locally": False,
         "source": "https://huggingface.co/FX-FeiHou/wan2.2-Remix"},
        {"id": "smoothmix_14b", "label": "SmoothMix Wan 2.2 14B", "steps": "4-6", "cfg": 1,
         "sampler": "euler_a", "scheduler": "normal", "tested_locally": False,
         "source": "https://civitai.com/models/1995784"},
        {"id": "dasiwa_lightspeed_v9", "label": "DaSiWa Lightspeed SynthSeduction v9", "noise": "low",
         "tested_locally": False},
        {"id": "hybrid_smoothmix_high_dasiwa_low", "label": "SmoothMix high + DaSiWa low",
         "high": "smoothmix_14b", "low": "dasiwa_lightspeed_v9", "shift": 5,
         "high_steps": 3, "low_steps": 4, "cfg": 1, "sampler": "lcm", "scheduler": "beta",
         "tested_locally": False},
    ],
    "video_loras": [
        {"id": "nsfw_motion_enhancer", "label": "NSFW Motion Enhancer + Reward low", "adult_only": True,
         "high_steps": 3, "low_steps": 5, "cfg_high": 2.5, "cfg_low": 1,
         "strength": 1.0, "strength_stacked": 0.55, "path": "low",
         "source": "https://civarchive.com/models/1985613"},
        {"id": "wan_general_nsfw", "label": "WAN General NSFW", "adult_only": True, "trigger": "nsfwsks",
         "strength": 0.7, "path": "both", "source": "https://civitai.com/models/1307155"},
        {"id": "dr34ml4y_aio", "label": "dr34ml4y All-in-One NSFW", "adult_only": True,
         "strength": 0.4, "path": "low", "source": "https://civitai.com/models/1811313"},
        {"id": "kierkegaard_pussy_i2v", "label": "Kierkegaard420 Pussy I2V", "adult_only": True,
         "strength": 0.7, "path": "low", "source": "https://civarchive.com/models/1895314"},
        {"id": "female_genitals_helper", "label": "NSFW Female Genitals Helper", "adult_only": True,
         "strength": 0.6, "path": "low", "trigger": "detailed view of vulva in motion"},
        {"id": "polyhedron_skin_hands", "label": "Polyhedron skin hands eyes", "adult_only": False,
         "strength_high": 0.35, "strength_low": 0.6, "path": "both"},
        {"id": "chroma_fineart_photo", "label": "Chroma FineArtPhoto", "adult_only": False,
         "strength": 0.6, "path": "still", "source": "https://civitai.com/models/2124475"},
    ],
    "lora_stack_rule": "Test one at a time. Combine around 0.5 to 0.6. Character LoRA 0.6 to 0.8. Above 0.9 overrides the still. Prefer the low-noise path. About 2 per stage, 3 or 4 total.",
}

# A local override must not be able to weaken these.
_LOCKED = ("adult_only",)
_ADULT_LORA_IDS = {
    "nsfw_motion_enhancer", "wan_general_nsfw", "dr34ml4y_aio",
    "kierkegaard_pussy_i2v", "female_genitals_helper",
}


def _root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def override_path():
    env = os.environ.get("EASY_STUDIO_MODEL_REGISTRY")
    if env:
        return env
    out = os.environ.get("EASY_STUDIO_OUTPUTS") or os.path.join(_root(), "outputs")
    return os.path.join(out, "model_registry.json")


def _merge(base, over):
    if not isinstance(over, dict):
        return base
    for key, val in over.items():
        if key in _LOCKED:
            continue
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _merge(base[key], val)
        else:
            base[key] = val
    return base


def load():
    data = copy.deepcopy(DEFAULTS)
    path = override_path()
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            _merge(data, json.load(f))
    # These roles cannot be moved into the everyday area by an override file.
    for name in ("still_adult_fallback", "video_lora_stack"):
        row = data["roles"].get(name)
        if isinstance(row, dict):
            row["adult_only"] = True
    for row in data.get("video_loras") or []:
        if isinstance(row, dict) and row.get("id") in _ADULT_LORA_IDS:
            row["adult_only"] = True
    return data


def role(name):
    reg = load()
    if name not in reg["roles"]:
        raise KeyError(name)
    return reg["roles"][name]


def video_chain():
    """The stages the runner executes today, in order: Wan, then the recorded finish."""
    return [role("video_i2v"), role("video_upscale"), role("video_interpolate")]


def sampling():
    return dict(load().get("sampling") or {})


def video_checkpoints():
    return list(load().get("video_checkpoints") or [])


def video_lora(lora_id):
    for row in load().get("video_loras") or []:
        if row.get("id") == lora_id:
            return dict(row)
    return None


def clip_lengths():
    data = load()
    allowed = (data.get("clip_lengths") or {}).get("allowed_s") or [2, 5]
    out = []
    for item in allowed:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out.append(n)
    return out or [2, 5]


def pipeline():
    """Still → Motion → Fix → Finish. Control, long takes, and preview stay named here."""
    control = role("video_control")
    return {
        "order": list(load().get("pipeline") or ["still", "motion", "fix", "finish"]),
        "still_explicit": role("still_adult_fallback")["id"],
        "still_other": role("still_realistic")["id"],
        "motion": role("video_i2v")["id"],
        "control": control["id"],
        "control_backups": [b.get("id") for b in control.get("backups") or []],
        "long": role("video_long")["id"],
        "fix": role("video_fix")["id"],
        "finish": [role("video_upscale")["id"], role("video_interpolate")["id"]],
        "preview": role("video_preview")["id"],
        "finish_fps": role("video_interpolate").get("to_fps"),
        "finish_size": role("video_upscale").get("target"),
    }
