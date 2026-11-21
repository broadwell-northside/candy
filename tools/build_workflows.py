"""Writes every API-format workflow Easy Studio uses into app/workflows/.

Node names and settings come from ComfyUI's own official templates (ComfyUI 0.43,
comfyui-workflow-templates), re-wired into the simple 'API format' that ComfyUI's
/prompt endpoint accepts. Nodes the app fills in are found by their TITLE
(POSITIVE, NEGATIVE, SEED, SIZE, IMAGE 1, IMAGE 2, MASK, START IMAGE, END IMAGE, ...).

Run:  python tools/build_workflows.py   (only needed if you change something here)
"""
import json, os, copy
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "workflows")

def N(cls, title=None, **inputs):
    d = {"class_type": cls, "inputs": inputs}
    if title: d["_meta"] = {"title": title}
    return d

W = {}

# ---------- Z-Image Turbo: fast realistic text-to-image (Apache-2.0, 8 steps) ----------
W["image_zimage_turbo_api.json"] = {
 "1": N("UNETLoader", "Image model (Z-Image Turbo)", unet_name="z_image_turbo_bf16.safetensors", weight_dtype="default"),
 "2": N("CLIPLoader", "Text encoder (Qwen3 4B)", clip_name="qwen_3_4b.safetensors", type="lumina2", device="default"),
 "3": N("VAELoader", None, vae_name="ae.safetensors"),
 "4": N("ModelSamplingAuraFlow", None, model=["1", 0], shift=3.0),
 "5": N("CLIPTextEncode", "POSITIVE", text="", clip=["2", 0]),
 "6": N("ConditioningZeroOut", None, conditioning=["5", 0]),
 "7": N("EmptySD3LatentImage", "SIZE", width=1024, height=1024, batch_size=1),
 "8": N("KSampler", "SEED", model=["4", 0], positive=["5", 0], negative=["6", 0], latent_image=["7", 0],
        seed=0, steps=8, cfg=1.0, sampler_name="res_multistep", scheduler="simple", denoise=1.0),
 "9": N("VAEDecode", None, samples=["8", 0], vae=["3", 0]),
 "10": N("SaveImage", None, images=["9", 0], filename_prefix="easy-studio/img"),
}

# ---------- Z-Image Turbo + Fun Union ControlNet: generate in a chosen POSE ----------
W["pose_zimage_api.json"] = copy.deepcopy(W["image_zimage_turbo_api.json"])
W["pose_zimage_api.json"].update({
 "11": N("LoadImage", "POSE IMAGE", image="pose.png"),
 "12": N("ModelPatchLoader", "Pose control (Z-Image Fun Union ControlNet)", name="Z-Image-Turbo-Fun-Controlnet-Union.safetensors"),
 "13": N("QwenImageDiffsynthControlnet", "POSE STRENGTH", model=["1", 0], model_patch=["12", 0], vae=["3", 0],
         image=["11", 0], strength=0.8),
})
W["pose_zimage_api.json"]["4"]["inputs"]["model"] = ["13", 0]

# ---------- Qwen-Image-Edit-2511 (+ Lightning 4-step): change outfit / pose / scene / add object ----------
def qwen_edit(extra_lora=None):
    w = {
     "1": N("UNETLoader", "Edit model (Qwen-Image-Edit-2511)", unet_name="qwen_image_edit_2511_fp8mixed.safetensors", weight_dtype="default"),
     "2": N("CLIPLoader", "Text encoder (Qwen2.5-VL 7B)", clip_name="qwen_2.5_vl_7b_fp8_scaled.safetensors", type="qwen_image", device="default"),
     "3": N("VAELoader", None, vae_name="qwen_image_vae.safetensors"),
     "4": N("LoraLoaderModelOnly", "4-step speed LoRA", model=["1", 0], lora_name="Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", strength_model=1.0),
     "5": N("ModelSamplingAuraFlow", None, model=["4", 0], shift=3.1),
     "6": N("CFGNorm", None, model=["5", 0], strength=1.0),
     "10": N("LoadImage", "IMAGE 1", image="image1.png"),
     "11": N("FluxKontextImageScale", None, image=["10", 0]),
     "12": N("LoadImage", "IMAGE 2", image="image2.png"),
     "13": N("LoadImage", "IMAGE 3", image="image3.png"),
     "20": N("TextEncodeQwenImageEditPlus", "POSITIVE", clip=["2", 0], prompt="", vae=["3", 0], image1=["11", 0], image2=["12", 0], image3=["13", 0]),
     "21": N("TextEncodeQwenImageEditPlus", "NEGATIVE", clip=["2", 0], prompt="", vae=["3", 0], image1=["11", 0], image2=["12", 0], image3=["13", 0]),
     "22": N("FluxKontextMultiReferenceLatentMethod", None, conditioning=["20", 0], reference_latents_method="index_timestep_zero"),
     "23": N("FluxKontextMultiReferenceLatentMethod", None, conditioning=["21", 0], reference_latents_method="index_timestep_zero"),
     "30": N("VAEEncode", None, pixels=["11", 0], vae=["3", 0]),
     "31": N("KSampler", "SEED", model=["6", 0], positive=["22", 0], negative=["23", 0], latent_image=["30", 0],
             seed=0, steps=4, cfg=1.0, sampler_name="euler", scheduler="simple", denoise=1.0),
     "32": N("VAEDecode", None, samples=["31", 0], vae=["3", 0]),
     "33": N("SaveImage", None, images=["32", 0], filename_prefix="easy-studio/edit"),
    }
    if extra_lora:
        w["7"] = N("LoraLoaderModelOnly", "Camera-angle LoRA", model=["4", 0], lora_name=extra_lora, strength_model=1.0)
        w["5"]["inputs"]["model"] = ["7", 0]
    return w
W["edit_qwen2511_api.json"] = qwen_edit()
W["angles_qwen2511_api.json"] = qwen_edit("qwen-image-edit-2511-multiple-angles-lora.safetensors")

# ---------- Masked repaint ("paint where to change"), works for nude/outfit detail ----------
W["inpaint_chroma1hd_api.json"] = {
 "1": N("UNETLoader", "Image model (Chroma1-HD)", unet_name="Chroma1-HD.safetensors", weight_dtype="default"),
 "2": N("CLIPLoader", "Text encoder (T5-XXL)", clip_name="t5xxl_fp16.safetensors", type="chroma", device="default"),
 "3": N("T5TokenizerOptions", None, clip=["2", 0], min_padding=0, min_length=0),
 "4": N("VAELoader", None, vae_name="ae.safetensors"),
 "5": N("ModelSamplingAuraFlow", None, model=["1", 0], shift=1.0),
 "6": N("DifferentialDiffusion", None, model=["5", 0], strength=1.0),
 "7": N("CLIPTextEncode", "POSITIVE", text="", clip=["3", 0]),
 "8": N("CLIPTextEncode", "NEGATIVE", text="", clip=["3", 0]),
 "9": N("LoadImage", "IMAGE 1", image="image1.png"),
 "10": N("LoadImageMask", "MASK", image="mask.png", channel="red"),
 "11": N("GrowMask", "MASK GROW", mask=["10", 0], expand=8, tapered_corners=True),
 "12": N("InpaintModelConditioning", None, positive=["7", 0], negative=["8", 0], vae=["4", 0], pixels=["9", 0], mask=["11", 0], noise_mask=True),
 "13": N("CFGGuider", None, model=["6", 0], positive=["12", 0], negative=["12", 1], cfg=3.5),
 "14": N("KSamplerSelect", None, sampler_name="euler"),
 "15": N("BasicScheduler", "STRENGTH", model=["6", 0], scheduler="beta", steps=26, denoise=0.9),
 "16": N("RandomNoise", "SEED", noise_seed=0),
 "17": N("SamplerCustomAdvanced", None, noise=["16", 0], guider=["13", 0], sampler=["14", 0], sigmas=["15", 0], latent_image=["12", 2]),
 "18": N("VAEDecode", None, samples=["17", 0], vae=["4", 0]),
 "19": N("ImageCompositeMasked", None, destination=["9", 0], source=["18", 0], x=0, y=0, resize_source=False, mask=["11", 0]),
 "20": N("SaveImage", None, images=["19", 0], filename_prefix="easy-studio/edit"),
}
W["inpaint_noobai_xl_api.json"] = {
 "1": N("CheckpointLoaderSimple", "Image model (NoobAI-XL)", ckpt_name="NoobAI-XL-v1.1.safetensors"),
 "2": N("CLIPSetLastLayer", None, clip=["1", 1], stop_at_clip_layer=-2),
 "3": N("DifferentialDiffusion", None, model=["1", 0], strength=1.0),
 "7": N("CLIPTextEncode", "POSITIVE", text="", clip=["2", 0]),
 "8": N("CLIPTextEncode", "NEGATIVE", text="", clip=["2", 0]),
 "9": N("LoadImage", "IMAGE 1", image="image1.png"),
 "10": N("LoadImageMask", "MASK", image="mask.png", channel="red"),
 "11": N("GrowMask", "MASK GROW", mask=["10", 0], expand=8, tapered_corners=True),
 "12": N("InpaintModelConditioning", None, positive=["7", 0], negative=["8", 0], vae=["1", 2], pixels=["9", 0], mask=["11", 0], noise_mask=True),
 "13": N("KSampler", "SEED", model=["3", 0], positive=["12", 0], negative=["12", 1], latent_image=["12", 2],
         seed=0, steps=28, cfg=5.5, sampler_name="euler_ancestral", scheduler="normal", denoise=0.9),
 "14": N("VAEDecode", None, samples=["13", 0], vae=["1", 2]),
 "15": N("ImageCompositeMasked", None, destination=["9", 0], source=["14", 0], x=0, y=0, resize_source=False, mask=["11", 0]),
 "16": N("SaveImage", None, images=["15", 0], filename_prefix="easy-studio/edit"),
}

# ---------- Background removal (BiRefNet, MIT) -> transparent PNG + mask ----------
W["remove_bg_api.json"] = {
 "1": N("LoadImage", "IMAGE 1", image="image1.png"),
 "2": N("LoadBackgroundRemovalModel", None, bg_removal_name="birefnet.safetensors"),
 "3": N("RemoveBackground", None, bg_removal_model=["2", 0], image=["1", 0]),
 "4": N("InvertMask", None, mask=["3", 0]),
 "5": N("JoinImageWithAlpha", None, image=["1", 0], alpha=["4", 0]),
 "6": N("SaveImage", "CUTOUT", images=["5", 0], filename_prefix="easy-studio/cutout"),
 "7": N("MaskToImage", None, mask=["3", 0]),
 "8": N("SaveImage", "MASK OUT", images=["7", 0], filename_prefix="easy-studio/mask"),
}

# ---------- Upscale (Real-ESRGAN x4plus, BSD-3) ----------
W["upscale_api.json"] = {
 "1": N("LoadImage", "IMAGE 1", image="image1.png"),
 "2": N("UpscaleModelLoader", None, model_name="RealESRGAN_x4plus.safetensors"),
 "3": N("ImageUpscaleWithModel", None, upscale_model=["2", 0], image=["1", 0]),
 "4": N("ImageScaleBy", "SCALE", image=["3", 0], upscale_method="lanczos", scale_by=0.5),
 "5": N("SaveImage", None, images=["4", 0], filename_prefix="easy-studio/upscaled"),
}

# ---------- Copy a pose from any picture (SDPose -> stick figure only) ----------
W["pose_extract_api.json"] = {
 "1": N("LoadImage", "IMAGE 1", image="image1.png"),
 "2": N("CheckpointLoaderSimple", None, ckpt_name="sdpose_wholebody_fp16.safetensors"),
 "3": N("ResizeImageMaskNode", None, input=["1", 0], resize_type="scale longer dimension",
        **{"resize_type.longer_size": 1024}, scale_method="area"),
 "4": N("SDPoseKeypointExtractor", None, model=["2", 0], vae=["2", 2], image=["3", 0], batch_size=1),
 "5": N("SDPoseDrawKeypoints", None, keypoints=["4", 0], draw_body=True, draw_hands=True, draw_face=False,
        draw_feet=True, stick_width=4, face_point_size=2, score_threshold=0.5, draw_head=True),
 "6": N("SaveImage", None, images=["5", 0], filename_prefix="easy-studio/pose"),
}

# ---------- Wan 2.2 first+last frame (smooth "go from A to B", seamless loops) ----------
def flf2v(fast=True):
    w = json.load(open(os.path.join(OUT, "video_wan22_i2v_fast_api.json" if fast else "video_wan22_i2v_quality_api.json")))
    w["18"] = N("LoadImage", "END IMAGE", image="end.png")
    w["12"] = N("WanFirstLastFrameToVideo", "SIZE", positive=["9", 0], negative=["10", 0], vae=["8", 0],
                start_image=["11", 0], end_image=["18", 0], width=832, height=480, length=81, batch_size=1)
    return w
W["video_wan22_flf2v_fast_api.json"] = flf2v(True)
W["video_wan22_flf2v_quality_api.json"] = flf2v(False)

# ---------- 3D: TRELLIS.2 (MIT) textured GLB; from template 3d_pixal3d_trellis2_image_to_model ----------
T = {
 "1": N("LoadImage", "IMAGE 1", image="image1.png"),
 "2": N("LoadBackgroundRemovalModel", None, bg_removal_name="birefnet.safetensors"),
 "3": N("RemoveBackground", None, bg_removal_model=["2", 0], image=["1", 0]),
 "4": N("ImageCropToMask", None, images=["1", 0], masks=["3", 0], width=1024, height=1024, pad_factor=1.0, grow_mask=0, background="#000000"),
 "5": N("CLIPVisionLoader", None, clip_name="dino_v3_vit_l.safetensors"),
 "6": N("Trellis2Conditioning", None, clip_vision_model=["5", 0], image=["4", 0]),
 "7": N("UNETLoader", "3D model (TRELLIS.2)", unet_name="trellis_2_int8_convrot.safetensors", weight_dtype="default"),
 "8": N("VAELoader", None, vae_name="trellis_2_shape_vae_bf16.safetensors"),
 "9": N("VAELoader", None, vae_name="trellis_2_texture_vae_bf16.safetensors"),
 "10": N("CFGOverride", None, model=["7", 0], cfg=1.0, start_percent=0.667, end_percent=1.0),
 "11": N("RescaleCFG", None, model=["10", 0], multiplier=0.7),
 "12": N("ModelSamplingSD3", None, model=["11", 0], shift=5.0),
 "13": N("CFGOverride", None, model=["7", 0], cfg=1.0, start_percent=0.769, end_percent=1.0),
 "14": N("RescaleCFG", None, model=["13", 0], multiplier=0.5),
 "15": N("EmptyTrellis2LatentStructure", None, batch_size=1),
 "16": N("KSampler", "SEED", model=["12", 0], positive=["6", 0], negative=["6", 1], latent_image=["15", 0],
         seed=0, steps=12, cfg=7.5, sampler_name="euler", scheduler="normal", denoise=1.0),
 "17": N("VaeDecodeStructureTrellis2", None, samples=["16", 0], vae=["8", 0], resolution="32"),
 "18": N("Trellis2ShapeStage", None, positive=["6", 0], negative=["6", 1], voxel=["17", 0]),
 "19": N("KSampler", None, model=["14", 0], positive=["18", 0], negative=["18", 1], latent_image=["18", 2],
         seed=42, steps=20, cfg=7.5, sampler_name="euler", scheduler="normal", denoise=1.0),
 "20": N("Trellis2UpsampleStage", "DETAIL", positive=["18", 0], negative=["18", 1], shape_latent=["19", 0], vae=["8", 0], target_resolution=1024),
 "21": N("KSampler", None, model=["14", 0], positive=["20", 0], negative=["20", 1], latent_image=["20", 2],
         seed=42, steps=12, cfg=7.5, sampler_name="euler", scheduler="simple", denoise=1.0),
 "22": N("VaeDecodeShapeTrellis", None, samples=["21", 0], vae=["8", 0]),
 "23": N("Trellis2TextureStage", None, positive=["20", 0], negative=["20", 1], shape_latent=["21", 0]),
 "24": N("KSampler", None, model=["7", 0], positive=["23", 0], negative=["23", 1], latent_image=["23", 2],
         seed=43, steps=12, cfg=1.0, sampler_name="euler", scheduler="normal", denoise=1.0),
 "25": N("VaeDecodeTextureTrellis", None, samples=["24", 0], vae=["9", 0], shape_subdivides=["22", 1]),
 "26": N("RemeshMesh", "REMESH", mesh=["22", 0], resolution=768, sign_mode="solid", **{"sign_mode.fill": 20.0, "sign_mode.qef": False},
         band=1.0, project_back=0.0, fix_poles=False, smooth_iters=20, drop_small_components=0.01, precluster_max_verts=20000000),
 "27": N("DecimateMesh", "FACES", mesh=["26", 0], target_face_count=200000, placement_mode="midpoint"),
 "28": N("MeshSmoothNormals", None, mesh=["27", 0], crease_angle=180.0),
 "29": N("UnwrapMesh", None, mesh=["28", 0], segmenter="pec", resolution=2048, padding=1, weld_distance=0.0002),
 "30": N("BakeTextureFromVoxel", "TEXTURE SIZE", mesh=["29", 0], voxel_colors=["25", 0], reference_mesh=["22", 0], texture_size=2048),
 "31": N("BakeNormalMapFromMesh", None, low_poly=["29", 0], high_poly=["26", 0], resolution=2048, cage_distance=0.05, ignore_backfaces=True),
 "32": N("ApplyTextureToMesh", None, mesh=["29", 0], base_color=["30", 0], metallic=["30", 1], roughness=["30", 2], normal_map=["31", 0]),
 "33": N("MeshSmoothNormals", None, mesh=["32", 0], crease_angle=180.0),
 "34": N("MeshToFile3D", None, mesh=["33", 0]),
 "35": N("SaveGLB", "SAVE 3D", mesh=["34", 0], filename_prefix="easy-studio/3d"),
}
W["3d_trellis2_api.json"] = T

# ---------- 3D: Hunyuan3D 2.1 shape only (fast, untextured clay; licence excludes EU/UK/South Korea) ----------
W["3d_hunyuan21_shape_api.json"] = {
 "1": N("LoadImage", "IMAGE 1", image="image1.png"),
 "2": N("LoadBackgroundRemovalModel", None, bg_removal_name="birefnet.safetensors"),
 "3": N("RemoveBackground", None, bg_removal_model=["2", 0], image=["1", 0]),
 "4": N("ImageCropToMask", None, images=["1", 0], masks=["3", 0], width=1024, height=1024, pad_factor=1.1, grow_mask=0, background="#FFFFFF"),
 "5": N("ImageOnlyCheckpointLoader", "3D model (Hunyuan3D 2.1)", ckpt_name="hunyuan_3d_v2.1.safetensors"),
 "6": N("ModelSamplingAuraFlow", None, model=["5", 0], shift=1.0),
 "7": N("CLIPVisionEncode", None, clip_vision=["5", 1], image=["4", 0], crop="center"),
 "8": N("Hunyuan3Dv2Conditioning", None, clip_vision_output=["7", 0]),
 "9": N("EmptyLatentHunyuan3Dv2", None, resolution=4096, batch_size=1),
 "10": N("KSampler", "SEED", model=["6", 0], positive=["8", 0], negative=["8", 1], latent_image=["9", 0],
         seed=0, steps=30, cfg=5.0, sampler_name="euler", scheduler="normal", denoise=1.0),
 "11": N("VAEDecodeHunyuan3D", None, samples=["10", 0], vae=["5", 2], num_chunks=8000, octree_resolution=256),
 "12": N("VoxelToMesh", None, voxel=["11", 0], algorithm="surface net", threshold=0.6),
 "13": N("SaveGLB", "SAVE 3D", mesh=["12", 0], filename_prefix="easy-studio/3d"),
}

if __name__ == "__main__":
    for name, wf in W.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=1)
        print("wrote", name, len(wf), "nodes")
