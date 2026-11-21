"""Download the model files Easy Studio uses into the right ComfyUI folders.

  python install/download_models.py --comfy PATH_TO_ComfyUI [--what all|image,anime,fast,edit,tools,video,3d,3d-shape]

All files below are public on Hugging Face (no login needed). Downloads resume if interrupted.
Total for --what all: about 150 GB. Optional extras (--what video-t2v,video-ltx,...) are listed with --list. Set HF_TOKEN if you have one (faster, fewer rate limits).
"""
import argparse
import os
import sys
import time

import requests

HF = "https://huggingface.co"
# group -> list of (ComfyUI models sub-folder, file name, download URL, size).  All links checked Nov 2026.
MODELS = {
    "image": [  # Chroma1-HD -- realistic / painterly, Apache-2.0
        ("diffusion_models", "Chroma1-HD.safetensors",
         f"{HF}/lodestones/Chroma1-HD/resolve/main/Chroma1-HD.safetensors", "17.8 GB"),
        ("text_encoders", "t5xxl_fp16.safetensors",
         f"{HF}/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors", "9.8 GB"),
        ("vae", "ae.safetensors",
         f"{HF}/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors", "0.3 GB"),
    ],
    "anime": [  # NoobAI-XL 1.1 -- anime / illustration, Fair AI Public License 1.0-SD
        ("checkpoints", "NoobAI-XL-v1.1.safetensors",
         f"{HF}/Laxhar/noobai-XL-1.1/resolve/main/NoobAI-XL-v1.1.safetensors", "7.1 GB"),
    ],
    "fast": [  # Z-Image Turbo -- fast realistic drafts (8 steps) + pose control, Apache-2.0
        ("diffusion_models", "z_image_turbo_bf16.safetensors",
         f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors", "12.3 GB"),
        ("text_encoders", "qwen_3_4b.safetensors",
         f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors", "8.0 GB"),
        ("vae", "ae.safetensors",
         f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors", "0.3 GB"),
        ("model_patches", "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
         f"{HF}/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors", "3.1 GB"),
    ],
    "edit": [  # Qwen-Image-Edit-2511 + 4-step Lightning LoRA -- outfit / pose / scene / object edits, Apache-2.0
        ("diffusion_models", "qwen_image_edit_2511_fp8mixed.safetensors",
         f"{HF}/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors", "20.5 GB"),
        ("text_encoders", "qwen_2.5_vl_7b_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "9.4 GB"),
        ("vae", "qwen_image_vae.safetensors",
         f"{HF}/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "0.25 GB"),
        ("loras", "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
         f"{HF}/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "0.85 GB"),
        ("loras", "qwen-image-edit-2511-multiple-angles-lora.safetensors",
         f"{HF}/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA/resolve/main/qwen-image-edit-2511-multiple-angles-lora.safetensors", "0.3 GB"),
    ],
    "tools": [  # small helpers: background removal (MIT), upscaler (BSD-3), pose reader (SDPose)
        ("background_removal", "birefnet.safetensors",
         f"{HF}/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors", "0.44 GB"),
        ("upscale_models", "RealESRGAN_x4plus.safetensors",
         f"{HF}/Comfy-Org/Real-ESRGAN_repackaged/resolve/main/RealESRGAN_x4plus.safetensors", "0.07 GB"),
        ("checkpoints", "sdpose_wholebody_fp16.safetensors",
         f"{HF}/Comfy-Org/SDPose/resolve/main/checkpoints/sdpose_wholebody_fp16.safetensors", "1.9 GB"),
    ],
    "video": [  # Wan 2.2 image-to-video 14B -- Apache-2.0
        ("diffusion_models", "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "14.3 GB"),
        ("diffusion_models", "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "14.3 GB"),
        ("loras", "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "1.2 GB"),
        ("loras", "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "1.2 GB"),
        ("vae", "wan_2.1_vae.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "0.25 GB"),
        ("text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "6.7 GB"),
    ],
    "video-t2v": [  # Wan 2.2 14B text-to-video -- Apache-2.0
        ("diffusion_models", "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors", "14.3 GB"),
        ("diffusion_models", "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors", "14.3 GB"),
        ("loras", "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors", "1.2 GB"),
        ("loras", "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors", "1.2 GB"),
        ("text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "6.7 GB"),
        ("vae", "wan_2.1_vae.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "0.2 GB"),
    ],
    "video-wan5b": [  # Wan 2.2 5B text/image-to-video (smaller, 24 fps) -- Apache-2.0
        ("diffusion_models", "wan2.2_ti2v_5B_fp16.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors", "10.0 GB"),
        ("vae", "wan2.2_vae.safetensors",
         f"{HF}/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors", "1.4 GB"),
        ("text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
         f"{HF}/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "6.7 GB"),
    ],
    "video-ltx": [  # LTX-2.5 22B (video WITH sound) -- LTX-2 community licence, free under $10M revenue. GATED: accept the licence on huggingface.co/Lightricks/LTX-2.5 and set HF_TOKEN
        ("diffusion_models", "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
         f"{HF}/Lightricks/LTX-2.5/resolve/main/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors", "21.5 GB (login needed)"),
        ("text_encoders", "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
         f"{HF}/Lightricks/LTX-2.5/resolve/main/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors", "15.4 GB (login needed)"),
        ("vae", "ltx-2.5-video-vae-bf16.safetensors",
         f"{HF}/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-bf16.safetensors", "1.5 GB (login needed)"),
        ("vae", "ltx-2.5-audio-vae-bf16.safetensors",
         f"{HF}/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-audio-vae-bf16.safetensors", "0.4 GB (login needed)"),
        ("latent_upscale_models", "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
         f"{HF}/Lightricks/LTX-2.5/resolve/main/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors", "1.0 GB (login needed)"),
    ],
    "video-hunyuan": [  # HunyuanVideo 1.5 720p -- Tencent licence: NOT valid in the EU, UK or South Korea
        ("diffusion_models", "hunyuanvideo1.5_720p_t2v_fp16.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/diffusion_models/hunyuanvideo1.5_720p_t2v_fp16.safetensors", "16.6 GB"),
        ("diffusion_models", "hunyuanvideo1.5_720p_i2v_fp16.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/diffusion_models/hunyuanvideo1.5_720p_i2v_fp16.safetensors", "16.6 GB"),
        ("text_encoders", "qwen_2.5_vl_7b_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "9.4 GB"),
        ("text_encoders", "byt5_small_glyphxl_fp16.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/byt5_small_glyphxl_fp16.safetensors", "0.4 GB"),
        ("vae", "hunyuanvideo15_vae_fp16.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/vae/hunyuanvideo15_vae_fp16.safetensors", "2.5 GB"),
        ("clip_vision", "sigclip_vision_patch14_384.safetensors",
         f"{HF}/Comfy-Org/sigclip_vision_384/resolve/main/sigclip_vision_patch14_384.safetensors", "0.9 GB"),
    ],
    "video-kandinsky": [  # Kandinsky 5.0 Lite 5 s -- MIT
        ("diffusion_models", "kandinsky5lite_t2v_sft_5s.safetensors",
         f"{HF}/kandinskylab/Kandinsky-5.0-T2V-Lite-sft-5s/resolve/main/model/kandinsky5lite_t2v_sft_5s.safetensors", "4.6 GB"),
        ("diffusion_models", "kandinsky5lite_i2v_5s.safetensors",
         f"{HF}/kandinskylab/Kandinsky-5.0-I2V-Lite-5s/resolve/main/model/kandinsky5lite_i2v_5s.safetensors", "4.6 GB"),
        ("text_encoders", "qwen_2.5_vl_7b_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "9.4 GB"),
        ("text_encoders", "clip_l.safetensors",
         f"{HF}/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors", "0.2 GB"),
        ("vae", "hunyuan_video_vae_bf16.safetensors",
         f"{HF}/Kijai/HunyuanVideo_comfy/resolve/main/hunyuan_video_vae_bf16.safetensors", "0.5 GB"),
    ],
    "3d": [  # TRELLIS.2 (Microsoft, MIT) textured 3D, run natively by ComfyUI
        ("diffusion_models", "trellis_2_int8_convrot.safetensors",
         f"{HF}/Comfy-Org/TRELLIS.2/resolve/main/diffusion_models/trellis_2_int8_convrot.safetensors", "5.3 GB"),
        ("vae", "trellis_2_shape_vae_bf16.safetensors",
         f"{HF}/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_shape_vae_bf16.safetensors", "1.1 GB"),
        ("vae", "trellis_2_texture_vae_bf16.safetensors",
         f"{HF}/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_texture_vae_bf16.safetensors", "0.95 GB"),
        ("clip_vision", "dino_v3_vit_l.safetensors",
         f"{HF}/Comfy-Org/TRELLIS.2/resolve/main/clip_vision/dino_v3_vit_l.safetensors", "1.2 GB"),
        ("background_removal", "birefnet.safetensors",
         f"{HF}/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors", "0.44 GB"),
    ],
    "safety": [  # automatic age check (on by default): face finder + age classifier, both Apache-2.0
        ("easy_studio/age_check", "model.safetensors",
         f"{HF}/prithivMLmods/Age-Classification-SigLIP2/resolve/main/model.safetensors", "0.4 GB"),
        ("easy_studio/age_check", "config.json",
         f"{HF}/prithivMLmods/Age-Classification-SigLIP2/resolve/main/config.json", "0.0 GB"),
        ("easy_studio/age_check", "preprocessor_config.json",
         f"{HF}/prithivMLmods/Age-Classification-SigLIP2/resolve/main/preprocessor_config.json", "0.0 GB"),
        ("easy_studio/age_check/torch/hub/checkpoints", "yunet_final.pth",
         f"{HF}/kornia/yunet/resolve/main/yunet_final.pth", "0.0 GB"),
    ],
    "face": [  # the face check behind enrolment (Phase two): YuNet MIT, SFace Apache-2.0. Not in the default set; pinned to a revision, and its worker checks the hash.
        ("easy_studio/face_check", "face_detection_yunet_2023mar.onnx",
         f"{HF}/opencv/face_detection_yunet/resolve/3cc26e7f1014a5ee5d74a42acee58bafc9d0a310/face_detection_yunet_2023mar.onnx", "0.0 GB"),
        ("easy_studio/face_check", "face_recognition_sface_2021dec.onnx",
         f"{HF}/opencv/face_recognition_sface/resolve/3d7082438a6e4551e840c9b2bb60b71e8da4b524/face_recognition_sface_2021dec.onnx", "0.04 GB"),
    ],
    "photoreal": [  # optional. Not in the default "all" set. Sizes measured 3 Nov 2026.
        ("diffusion_models", "krea2_turbo_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/Krea-2/resolve/main/diffusion_models/krea2_turbo_fp8_scaled.safetensors", "13.1 GB"),
        ("text_encoders", "qwen3vl_4b_fp8_scaled.safetensors",
         f"{HF}/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors", "5.2 GB"),
        ("diffusion_models", "flux-2-klein-4b.safetensors",
         f"{HF}/Comfy-Org/Flux-2-Klein-4B/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors", "7.8 GB"),
        ("vae", "flux2-vae.safetensors",
         f"{HF}/Comfy-Org/Flux-2-Klein-4B/resolve/main/split_files/vae/flux2-vae.safetensors", "0.3 GB"),
        ("diffusion_models", "seedvr2_7b_sharp_fp16.safetensors",
         f"{HF}/Comfy-Org/SeedVR2/resolve/main/diffusion_models/seedvr2_7b_sharp_fp16.safetensors", "16.5 GB"),
        ("vae", "seedvr2_ema_vae_fp16.safetensors",
         f"{HF}/Comfy-Org/SeedVR2/resolve/main/vae/seedvr2_ema_vae_fp16.safetensors", "0.5 GB"),
        ("upscale_models", "gimmvfi_r_arb_lpips_fp32.safetensors",
         f"{HF}/Kijai/GIMM-VFI_safetensors/resolve/main/gimmvfi_r_arb_lpips_fp32.safetensors", "0.1 GB"),
        ("upscale_models", "gimmvfi_f_arb_lpips_fp32.safetensors",
         f"{HF}/Kijai/GIMM-VFI_safetensors/resolve/main/gimmvfi_f_arb_lpips_fp32.safetensors", "0.1 GB"),
    ],
    "sd15": [  # Stable Diffusion 1.5 -- "Photo (SD 1.5)" in Create. The VAE is inside the checkpoint. CreativeML OpenRAIL-M
        ("checkpoints", "v1-5-pruned-emaonly.safetensors",
         f"{HF}/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors", "4.3 GB"),
    ],
    "3d-shape": [  # Hunyuan3D 2.1 shape-only backup. Tencent licence: NOT valid in the EU, UK or South Korea.
        ("checkpoints", "hunyuan_3d_v2.1.safetensors",
         f"{HF}/Comfy-Org/hunyuan3D_2.1_repackaged/resolve/main/hunyuan_3d_v2.1.safetensors", "7.4 GB"),
    ],
}
GROUP_HELP = {
    "image": "Realistic pictures (Chroma1-HD)", "anime": "Anime pictures (NoobAI-XL)",
    "fast": "Fast drafts + poses (Z-Image Turbo)", "edit": "Outfit / pose / scene / object edits (Qwen-Image-Edit)",
    "tools": "Background remover, upscaler, pose reader", "video": "Video (Wan 2.2)",
    "3d": "3D models (TRELLIS.2)", "3d-shape": "Fast 3D shape backup (Hunyuan3D 2.1)",
    "safety": "Automatic age check (flags pictures that may look under 21)",
    "face": "Face check for the My likeness card (Phase two, off by default)",
    "video-t2v": "Video from text (Wan 2.2 14B), 38 GB", "video-wan5b": "Small video model (Wan 2.2 5B), 18 GB",
    "video-ltx": "Video with sound (LTX-2.5), 40 GB, needs a free Hugging Face login",
    "video-hunyuan": "HunyuanVideo 1.5 720p, 46 GB (not licensed in the EU/UK/South Korea)",
    "video-kandinsky": "Kandinsky 5 Lite, 19 GB",
    "sd15": "Photo (SD 1.5), 4.3 GB, VAE included",
    "photoreal": "Film look, draft model, SeedVR2 7B sharp, GIMM-VFI (about 44 GB, optional)",
}
OPTIONAL_GROUPS = ["video-t2v", "video-wan5b", "video-ltx", "video-hunyuan", "video-kandinsky", "3d-shape", "photoreal", "sd15"]
def _trainer_group(base):
    """The files one trainer base needs, from config/trainer_bases_lock.json (pinned to a revision, built from public metadata)."""
    import json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "trainer_bases_lock.json")
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)["rows"]
    except (OSError, ValueError):
        return []
    return [(r["folder"], r["name"], r["url"], "%.2f GB" % (r["size"] / 1e9)) for r in rows if r["base"] == base]


MODELS["trainer-fast"] = _trainer_group("fast")
MODELS["trainer-photo"] = _trainer_group("photo")
GROUP_HELP["trainer-fast"] = "Trainer base for Fast pictures (Z-Image Turbo), about 33 GB. Needed to train a likeness. Not part of the default set."
GROUP_HELP["trainer-photo"] = "Trainer base for Realistic pictures (Chroma1-HD), about 28 GB. Needed to train a likeness. Not part of the default set."

DEFAULT_GROUPS = ["image", "anime", "fast", "edit", "tools", "video", "3d", "safety"]  # big extra video models + 3d-shape are opt-in

MANUAL_NOTE = """
Optional extras you download by hand (not needed for Easy Studio to work):
  * Civitai fine-tunes / LoRAs (e.g. Chroma or Illustrious/NoobAI merges): you need a free
    Civitai account. Put checkpoints in ComfyUI/models/checkpoints (SDXL-type) or
    ComfyUI/models/diffusion_models (Chroma-type), LoRAs in ComfyUI/models/loras.
    Only use models of adult characters; skip anything built to imitate a real person.
  * LTX-2.5 (video with sound) is in the Video studio, but its files are gated: log in at
    https://huggingface.co/Lightricks/LTX-2.5, accept the licence, make a read token at
    https://huggingface.co/settings/tokens, then run with HF_TOKEN=... --what video-ltx
  * MiniMax-H3 / FastVideo FastH3 are NOT built in: their licence excludes the USA, EU, UK and
    South Korea. (You could still import such a workflow yourself where it is licensed.)
"""


def download(url, dest, token=None):
    tmp = dest + ".part"
    headers = {"User-Agent": "easy-studio/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    if have:
        headers["Range"] = f"bytes={have}-"
    with requests.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True) as r:
        if r.status_code in (401, 403):
            raise RuntimeError("This file needs a Hugging Face login / licence acceptance. "
                               "Accept it on the website, create a token, then: set HF_TOKEN=... and retry.")
        if r.status_code == 416:  # already complete
            os.replace(tmp, dest)
            return
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"
        if mode == "wb":
            have = 0
        total = have + int(r.headers.get("content-length", 0))
        t0, done = time.time(), have
        with open(tmp, mode) as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
                done += len(chunk)
                if total:
                    speed = (done - have) / max(1e-6, time.time() - t0) / 1e6
                    sys.stdout.write(f"\r    {done/1e9:6.2f} / {total/1e9:.2f} GB  ({speed:5.1f} MB/s)")
                    sys.stdout.flush()
    print()
    os.replace(tmp, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comfy", required=True, help="path to the ComfyUI folder")
    ap.add_argument("--what", default="all", help="all, or a comma list of: " + ", ".join(MODELS))
    ap.add_argument("--list", action="store_true", help="only print what would be downloaded")
    ap.add_argument("--check", action="store_true", help="only check every download link works (no download)")
    a = ap.parse_args()
    models_dir = os.path.join(a.comfy, "models")
    if a.check:
        groups = list(MODELS) if a.what == "all" else [g.strip() for g in a.what.split(",")]
        bad, total = [], 0
        token = os.environ.get("HF_TOKEN")
        for g in groups:
            for folder, name, url, size in MODELS[g]:
                h = {"User-Agent": "easy-studio/1.0", **({"Authorization": f"Bearer {token}"} if token else {})}
                try:
                    r = requests.head(url, headers=h, allow_redirects=True, timeout=90)
                    n = int(r.headers.get("x-linked-size") or r.headers.get("content-length") or 0)
                    ok = r.status_code == 200
                except requests.RequestException as e:
                    ok, n = False, 0
                    r = type("R", (), {"status_code": str(e)[:60]})
                total += n
                gated = (not ok) and r.status_code in (401, 403) and "login" in size
                print(f"  {'OK ' if ok else ('LOGIN' if gated else 'BAD')} {r.status_code}  {n/1e9:6.2f} GB  [{g}] {name}")
                if not ok and not gated:
                    bad.append(name)
        print(f"\nTotal of working links: {total/1e9:.1f} GB. Broken: {len(bad)}")
        sys.exit(1 if bad else 0)
    if not a.list and not os.path.isdir(models_dir):
        sys.exit(f"Can't find {models_dir} -- is --comfy pointing at the ComfyUI folder?")
    groups = DEFAULT_GROUPS if a.what == "all" else [g.strip() for g in a.what.split(",") if g.strip()]
    bad = [g for g in groups if g not in MODELS]
    if bad:
        sys.exit(f"Unknown group(s): {bad}. Choose from: {', '.join(MODELS)}")
    if a.list:
        if a.what == "all":
            groups = list(MODELS)
        for g in groups:
            print(f"== {g}: {GROUP_HELP[g]}")
            for folder, name, url, size in MODELS[g]:
                print(f"  {size:>8}  {folder}/{name}")
        return
    token = os.environ.get("HF_TOKEN")
    failed = []
    for g in groups:
        print(f"\n== {g}: {GROUP_HELP[g]} ==")
        for folder, name, url, size in MODELS[g]:
            dest_dir = os.path.join(models_dir, folder)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, name)
            if os.path.exists(dest) and os.path.getsize(dest) > (0 if size.startswith("0.0") else 1_000_000):
                print(f"  ok (already there)  {folder}/{name}")
                continue
            print(f"  downloading {folder}/{name}  ({size})")
            try:
                download(url, dest, token)
            except Exception as e:  # keep going, report at the end
                print(f"\n  !! failed: {e}")
                failed.append(name)
    print(MANUAL_NOTE)
    if failed:
        print("Some downloads failed (run this again to resume):", ", ".join(failed))
        sys.exit(1)
    print("All model files are in place.")


if __name__ == "__main__":
    main()
