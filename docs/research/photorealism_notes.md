# Photorealism research notes (raw, 3 Nov 2026)
- Z-Image Turbo (6B, Apache-2.0, 8 steps, <16 GB): best skin per step; shift 2 brings pores back (robertcreative.com/blog/z-image-turbo-realistic-skin); realism LoRAs often smooth skin. Z-Image base = LoRA training base. https://modeltrends.ai/ai-model-guides/best-ai-models-for-photorealism
- Krea 2 (Turbo/Raw, Jun 22 2026): most "shot not rendered" look, pores/freckles, filmic; Krea 2 Community License (free under $1M revenue). https://www.criticatv.com/z-image-vs-flux-klein-vs-qwen-image-krea-2-comfyui/
- FLUX.2 klein 4B (Apache) fastest previews + multi-ref edit; FLUX.2 dev non-commercial, 32 GB class; Qwen-Image 2512 (Apache, 20B) best prompt-following but plastic skin unless res_2s/bong_tangent + skin LoRAs; Qwen-Image-2.1 research licence. https://iimagined.ai/blog/best-comfyui-models-2026 ; https://diffusiondoodles.substack.com/p/model-rundown-z-image-turbo-qwen
- SDXL realism: RealVisXL V5, Juggernaut XL Ragnarok (huge LoRA/ControlNet ecosystem). Local measurements: https://github.com/N3V3MORE/comfyui-local/blob/main/MODEL_COMPARISON.md
- Upscale: SeedVR2 (ByteDance, v2.5 ComfyUI nodes, one-step DiT, image+video); 7B "sharp" keeps pores, 3B beautifies; SUPIR slower, airbrushed, broke on ComfyUI update. Two-stage SeedVR2 -> SRPO refine. https://myaiforce.com/seedvr2-srpo-upscaling/ ; reddit r/comfyui 1s295yc
- Hybrid: compose with Qwen 2512, refine with Z-Image second pass (low denoise).
## Video
- Instareal Wan 2.2 realism LoRA (high/low noise, trigger Instareal, 0.8-1.2) https://civitai.com/models/1877171/instareal-wan-22
- SeedVR2 video upscale: uniform batch, temporal overlap, color correction to avoid flicker https://note.com/ripe_cedum5672/n/n5354f2467474
- Interpolation: GIMM-VFI (better, slower) vs RIFE (fast); SVI v2 PRO LoRAs for long extend; Wan FaceDetailer pass (Wan low-noise T2V + face seg YOLO) https://fastsdmodel.com/models/2232205 ; pipeline SeedVR2+RIFE https://joshsymonds.com/workflows/
## Godot skin
- StandardMaterial3D SSS skin mode + transmittance (Forward+); sss_mode_skin render mode https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/spatial_shader.html
- MatMADNESS HumanShaders (skin, eye, eye wetness) Godot 4.5+ https://github.com/matmadness/HumanShaders ; RoboPoets digital_human (SSS/transmission maps) https://github.com/RoboPoets/digital_human
## Identity (Me avatar)
- PuLID-Flux2 (Klein 4B/9B/Dev) community node v0.6.2 https://github.com/iFayens/ComfyUI-PuLID-Flux2 ; PuLID-Flux v0.9.1 (start step 4 for realism) https://iimagined.ai/blog/pulid-flux ; InstantID SDXL-only, research-only checkpoints; InsightFace antelopev2 non-commercial (ok: personal)
- Sticker look comes from high denoise + no color match: use 0.5-0.65 + color match; head swap best w/ Qwen-Image-2.1 + BFS LoRA https://tingyudeco.com/blog/comfyui-face-swap-vs-head-swap-comparison
- aiofm ladder: adapter -> adapter + LoRA -> LoRA https://aiofm.info/en/guides/consistent-ai-character
## 3D head
- GTAvatar (single video, FLAME, relightable textured Gaussians, 1-3 h train; FLAME + 3DGS renderer non-commercial research) https://github.com/KelianB/GTAvatar
- PBR-GAvatar (monocular video, relightable, Jan 2026) https://github.com/liguohao96/PBR-GAvatar ; LAM one-image (MeshLAM CVPR 2026) https://github.com/aigc3d/LAM ; GAGAvatar MIT https://github.com/xg-chu/GAGAvatar
- MetaHuman: usable in any engine since 5.6, free < $1M; Mesh to MetaHuman from video/iPhone depth (Live Link Face); needs internet for autorig cloud backend https://www.metahuman.com/license https://dev.epicgames.com/documentation/metahuman/mesh-to-metahuman
- GoDNA Godot importer (UE5.6 -> Godot 4.5, 103-bone humanoid, 51 ARKit shapes, beta, $7.50) https://danikakes.itch.io/godna ; MetaHumanGodot viewer https://github.com/ibrews/MetaHumanGodot
## Liveness
- Open-source: open-face-liveness (MiniFASNet passive + pose/expression + screen-light) https://github.com/abhigyaan-jha/open-face-liveness ; face-liveness-check randomized challenges https://pypi.org/project/face-liveness-check/ ; arXiv 2610.16417: interactive challenges vs real-time face swaps - not fully solved
## Body realism
- VTON 2026 table (licences, VRAM, ComfyUI): IDM-VTON/CatVTON/OOTDiffusion/FitDiT CC BY-NC-SA; FASHN VTON v1.5 Apache-2.0 ~8 GB mask-free; Leffa MIT https://fashiolabs.com/blog/open-source-virtual-try-on-compared
- FitVTON (FLUX.1 Kontext, fit-aware, body-shape) best fit scores 3.08 vs CatVTON 2.30 https://zenoning.github.io/FitVTON/
- SAM 3D Body (Meta, MHR 45 shape params, MHR<->SMPL-X conversion) https://github.com/facebookresearch/sam-3d-body https://github.com/facebookresearch/MHR ; Multi-HMR SMPL-X
## Skin LoRAs
- Z-Image: base at shift 2 beats checkpoints; ProSkin (0.5-0.75, trigger refineface) https://civitai.com/models/2848683/proskin-z-image ; Skin Detail Slider (Krea2+ZIT, refiner pass) ; PhotorealTouch (Z-Image/SDXL/Pony/Illustrious/Flux) https://civitai.com/models/1464286/photorealtouch ; Flux "Detailed Skin&Textures" v3 0.5-0.8 https://civitai.com/models/1173967
## Training
- Z-Image character LoRA 20-30 imgs (ai-toolkit) https://neurocanvas.net/blog/zimage-lora-training-guide/ ; Wan 2.2 identity LoRA 15-30 imgs, low-noise expert https://github.com/DavidJBarnes/wan22-character-lora/blob/main/GUIDELINES.md
## Capture
- iPhone TrueDepth apps Heges/ViewScan export mesh; photogrammetry KIRI/RealityScan 100+ photos https://www.kiriengine.app/blog/Best_Free_3D_Scanner_Apps_2026
- MetaHuman autorig/texture synthesis uses Epic cloud (privacy) https://www.metahuman.com/ai-info
## Game
- Godot 4.6 volumetric fog, SDFGI tips https://docs.godotengine.org/en/4.6/tutorials/3d/volumetric_fog.html ; MPFB2 Mixamo rig + Godot BoneMap retarget https://static.makehumancommunity.org/mpfb/docs/rigging_posing/mixamo.html https://docs.godotengine.org/en/latest/tutorials/assets_pipeline/retargeting_3d_skeletons.html
- VaM 2 v1.2 beta Aug 2026 ; traffic: AlphaMoat Sep 2026 https://www.alphamoat.ai/en/ai/c/fun
