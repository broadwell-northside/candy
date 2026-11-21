# Models, links, licences, VRAM

All links were checked on 3 Nov 2026 with a ranged HTTP request (HTTP 206). Sizes are the real file sizes.

VRAM figures are rough peaks for ComfyUI's native loaders. They come from the model cards and the Comfy blog, and were NOT measured by us (no GPU here). ComfyUI offloads between steps, so on the 96 GB RTX PRO 6000, every row fits on its own.

| Feature | Model (file) | Size | Licence | Approx. VRAM | Link |
|---|---|---|---|---|---|
| Realistic pictures | Chroma1-HD (`Chroma1-HD.safetensors`) + T5-XXL fp16 + FLUX `ae` VAE | 17.8 + 9.8 + 0.3 GB | Apache-2.0 | ~24-30 GB | huggingface.co/lodestones/Chroma1-HD |
| Anime pictures | NoobAI-XL 1.1 | 7.1 GB | Fair AI Public License 1.0-SD (derivatives must stay open; check before selling) | ~8-10 GB | huggingface.co/Laxhar/noobai-XL-1.1 |
| Fast drafts | Z-Image Turbo bf16 + Qwen3-4B + `ae` | 12.3 + 8.0 + 0.3 GB | Apache-2.0 | ~16-20 GB | huggingface.co/Comfy-Org/z_image_turbo |
| Pose control | Z-Image-Turbo-Fun-Controlnet-Union (model patch) | 3.1 GB | Apache-2.0 | +3-4 GB | huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union |
| Edits (outfit, pose, scene, object, angle) | Qwen-Image-Edit-2511 fp8mixed + Qwen2.5-VL-7B fp8 + Qwen VAE | 20.5 + 9.4 + 0.25 GB | Apache-2.0 | ~30-40 GB | huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI |
| Edits, 4-step speed | Qwen-Image-Edit-2511-Lightning 4-step LoRA | 0.85 GB | Apache-2.0 | +1 GB | huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning |
| Turnaround angles | Qwen-Image-Edit-2511 Multiple-Angles LoRA (fal) | 0.3 GB | Apache-2.0 (HF card) | +0.5 GB | huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA |
| Background removal | BiRefNet | 0.44 GB | MIT | ~2-4 GB | huggingface.co/Comfy-Org/BiRefNet |
| Upscale x2/x4 | Real-ESRGAN x4plus | 0.07 GB | BSD-3-Clause | ~2-6 GB (tiles) | huggingface.co/Comfy-Org/Real-ESRGAN_repackaged |
| Read a pose from a picture | SDPose whole-body fp16 | 1.9 GB | MIT (Comfy-Org/SDPose card) | ~4 GB | huggingface.co/Comfy-Org/SDPose |
| Video | Wan 2.2 I2V 14B high/low-noise fp8 + 4-step LoRAs + umt5 + Wan 2.1 VAE | 14.3x2 + 1.2x2 + 6.7 + 0.25 GB | Apache-2.0 | ~40-60 GB at 720p | huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged |
| Video first+last frame | same Wan 2.2 I2V files (WanFirstLastFrameToVideo node) | -- | Apache-2.0 | same | -- |
| 3D (textured) | TRELLIS.2 int8 + shape VAE + texture VAE + DINOv3 ViT-L | 5.3 + 1.1 + 0.95 + 1.2 GB | MIT (Microsoft). DINOv3 weights carry Meta's DINOv3 licence -- **flag** | ~12 GB native (upstream needs 24 GB) | huggingface.co/Comfy-Org/TRELLIS.2 |
| 3D (fast shape, optional) | Hunyuan3D 2.1 | 7.4 GB | Tencent Hunyuan 3D Community Licence: **not valid in the EU, UK or South Korea**; extra terms above 1M monthly users | ~10 GB (shape only) | huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged |

Exact download URLs are in `install/download_models.py`. One link was dead: `Real-ESRGAN_repackaged/.../RealESRGAN_x4plus_anime_6B.safetensors` returns 404, so it is not used.

## Total disk
- Default install (everything except Hunyuan3D): about 150 GB.
- Hunyuan3D shape adds 7.4 GB.
- The installer lets you pick groups, e.g. `--what image,edit,tools`.

## Licence notes (Easy Studio 3: personal, non-commercial use)
Andrew confirmed the game is **for personal use only and will not be sold**. That relaxes most licence worries:
non-commercial and "community" licences are fine for private use. What still matters:

- **Territory limits still apply even for private use.** Tencent's Hunyuan licences (HunyuanVideo 1.5, Hunyuan3D 2.1)
  say they are *not valid* in the EU, the UK or South Korea. Both are optional, off by default, and the installer and
  Video studio say so. If you live in one of those places, don't install them.
- **MiniMax-H3** is excluded: its licence excludes use in the USA.
- **LTX-2 / LTX-2.5** (LTX-2 Community Licence): free for individuals and companies under $10M revenue; the files are
  gated on Hugging Face, so you need a free account and to accept the terms once.
- **Apache-2.0 / MIT** (Chroma, Z-Image, Qwen-Image-Edit, Wan 2.2 14B and 5B, Kandinsky 5 (MIT), TRELLIS.2, BiRefNet,
  Real-ESRGAN, ai-toolkit (MIT), age check: SigLIP2 age classifier + YuNet face finder): no limits for this use.
- **NoobAI-XL** (FAIPL-1.0-SD): fine for private use; only matters if you redistribute the model or a merge.
- **DINOv3** (inside TRELLIS.2): gated Meta licence; fine for private use, re-check if plans ever change.
- If you ever decide to sell or publish the game, re-read this file first: that would change several answers.

| v3 addition | Licence | Note |
|---|---|---|
| Wan 2.2 14B text-to-video, Wan 2.2 5B | Apache-2.0 | optional groups video-t2v, video-wan5b |
| LTX-2.5 (with sound) | LTX-2 Community Licence | gated on HF; free under $10M revenue |
| HunyuanVideo 1.5 | Tencent Hunyuan Community | **not valid in EU / UK / South Korea**; optional |
| Kandinsky 5 Lite | MIT | optional |
| ai-toolkit (trainer) | MIT | installed by install_trainer.sh |
| Age-Classification-SigLIP2 + YuNet | Apache-2.0 | the automatic age check ("safety" group, on by default) |
| MiniMax-H3 | excludes the USA | **not included** |

Licence fields came from the Hugging Face API (`cardData.license`) on 3 Nov 2026:
- Apache-2.0: Chroma1-HD, Z-Image-Turbo, Qwen-Image-Edit-2511, Fun-ControlNet-Union, Lightning, Multiple-Angles LoRA.
- MIT: TRELLIS.2-4B, Comfy-Org/TRELLIS.2, BiRefNet, SDPose.
- "other": NoobAI-XL (FAIPL), Hunyuan3D-2.1 (Tencent), DINOv3 (Meta, gated).
