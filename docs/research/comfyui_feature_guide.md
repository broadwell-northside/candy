# ComfyUI feature guide (native nodes only, ComfyUI 0.43.0)

Everything below uses nodes that ship inside ComfyUI itself, so Easy Studio needs **no custom nodes**.

Sources:
- Node inputs and outputs: from `/object_info` of a real ComfyUI 0.43.0 (1034 nodes).
- Settings: from the official templates named in each section.
- Validation: `tests/run_tests.py --real-comfy URL --real-dir DIR` sends every Easy Studio workflow to that real ComfyUI. All 17 were accepted.

## ComfyUI API basics (what Easy Studio calls)
- **`POST /prompt {prompt: <API-format graph>, client_id}`** queues a job. It returns `prompt_id`, or `node_errors` if validation fails. ComfyUI checks every class name, input name, link type and dropdown value before it accepts a job.
- **`GET /history/{prompt_id}`** gives the outputs. Each output lists `images[]` and, for SaveGLB/SaveVideo, `3d[]`/`videos[]`, as `{filename, subfolder, type}`.
- **`GET /view?filename=&subfolder=&type=output`** downloads a file.
- **`POST /upload/image`** (multipart `image`, `type=input`, `overwrite`) puts pictures and masks into `ComfyUI/input/`.
- **`WS /ws?clientId=`** streams messages: `progress` (value/max), `executing` (node; `node == null` means done) and `execution_error`.
- **`GET /object_info/<Node>`** returns the dropdown choices, which tells you which model files ComfyUI can see.
- **`POST /interrupt`** stops the current job. **`POST /queue {clear:true}`** clears waiting jobs.
- **API format:** `{ "<id>": {"class_type": "...", "inputs": {name: value | [src_id, out_index]}, "_meta": {"title": "..."}} }`.
- **Dynamic-combo inputs** (new V3 nodes) use dotted keys. For example, `RemeshMesh`'s `sign_mode="solid"` comes with `"sign_mode.fill": 20` and `"sign_mode.qef": false`. Easy Studio's converter (`tools/ui2api.py`) handles this.

## Character pictures (text to image)
- **Chroma1-HD** (`image_chroma1hd_api.json`):
  - UNETLoader → ModelSamplingAuraFlow(shift 1) → CFGGuider(cfg 3.5).
  - CLIPLoader(type `chroma`) → T5TokenizerOptions(0,0).
  - Sampling: KSamplerSelect(euler), BasicScheduler(beta, 26), RandomNoise, EmptySD3LatentImage, then SamplerCustomAdvanced.
- **NoobAI-XL** (`image_noobai_xl_api.json`): CheckpointLoaderSimple → CLIPSetLastLayer(-2) → KSampler(28 steps, cfg 5.5, euler_ancestral).
- **Z-Image Turbo** (`image_zimage_turbo_api.json`): from template `image_z_image_turbo.json`.
  - UNETLoader → ModelSamplingAuraFlow(3). CLIPLoader(type `lumina2`).
  - The negative is `ConditioningZeroOut(positive)`.
  - KSampler: 8 steps, cfg 1, `res_multistep`/`simple`.

## Consistent character (fictional, made in the app)
1. **Character DNA:** a saved JSON with the trait chips and sliders, a fixed seed, and the "hero" portrait.
   - Every new prompt is built from the DNA, so the description never drifts.
2. **New pictures of the same character** are made by editing the hero portrait with Qwen-Image-Edit-2511.
   - Pass it as `image1` and say what changes, e.g. "Same woman, now on a beach at sunset, wearing...".
   - 2511 is specifically tuned for keeping identity across edits.
3. **Later phase:** train a character LoRA on 20-40 app-made images of the character. This is optional, for the strongest consistency.
4. **Safety:** reference images must be app-generated characters. There is no face-swap, no InstantID/PuLID and no IP-Adapter on uploaded photos.

## Wardrobe / outfit swap / try-on
- **Route A, describe-to-change** (`edit_qwen2511_api.json`): from template `image_qwen_image_edit_2511.json`.
  - Loaders: UNETLoader `qwen_image_edit_2511_fp8mixed` → LoraLoaderModelOnly (Lightning 4-step) → ModelSamplingAuraFlow(3.1) → CFGNorm(1).
  - Encoding: CLIPLoader(type `qwen_image`). Each `TextEncodeQwenImageEditPlus(clip, prompt, vae, image1..3)` → FluxKontextMultiReferenceLatentMethod(`index_timestep_zero`), once for positive and once for negative.
  - Latent: `FluxKontextImageScale(image1)` → VAEEncode.
  - Sampling: KSampler 4 steps, cfg 1, euler/simple. Without Lightning it is 40 steps, cfg 3.
  - **Try-on:** image1 = character, image2 = garment picture, prompt "Dress the woman in image 1 in the outfit from image 2, keep her face, hair, body and pose".
- **Route B, paint-to-change** (`inpaint_chroma1hd_api.json` / `inpaint_noobai_xl_api.json`):
  - The user paints the area in the browser. It is uploaded as a mask PNG and loaded with LoadImageMask(red).
  - GrowMask(8) → `InpaintModelConditioning(noise_mask=True)` + `DifferentialDiffusion` → sampler.
  - Then `ImageCompositeMasked`, so pixels outside the mask are untouched.
  - Use this route for adult detail or nudity, where Qwen-Image-Edit is weaker. It also gives exact control of where things change.

## Poses
- **Pose presets:** bundled OpenPose-style stick figures (`app/static/poses/*.png`, drawn by `tools/make_poses.py`).
- **Generate in a pose** (`pose_zimage_api.json`): from template `image_z_image_turbo_fun_union_controlnet.json`.
  - `ModelPatchLoader(Z-Image-Turbo-Fun-Controlnet-Union)` + `QwenImageDiffsynthControlnet(model, model_patch, vae, image, strength)` feeds ModelSamplingAuraFlow.
  - The template feeds Canny; the Union model also accepts pose skeletons.
- **Re-pose an existing character** (edit): image1 = character, image2 = pose stick figure, prompt "Make the woman in image 1 take the exact pose shown in image 2". Qwen-Image-Edit 2509+ understands keypoint images.
- **Copy a pose from any picture** (`pose_extract_api.json`): from template `utility_sdpose_ood_image_to_pose.json`.
  - CheckpointLoaderSimple(`sdpose_wholebody_fp16`) → ResizeImageMaskNode(scale longer dimension 1024) → SDPoseKeypointExtractor → SDPoseDrawKeypoints.
  - Only the stick figure is kept; the source picture is not used to make art.

## Insert an object
- **Describe** (Qwen edit): "Add a red leather armchair to the left of the woman, matching the room's lighting".
- **With a reference** (Qwen edit, image2 = object picture): "Place the sword from image 2 in the woman's right hand".
- **Paint where** (inpaint route): mask the spot and prompt the object. This gives the most control over placement.

## Background remove / swap
- **Remove** (`remove_bg_api.json`): from template `utility_birefnet_remove_background.json`.
  - LoadBackgroundRemovalModel(`birefnet`) → RemoveBackground → InvertMask → JoinImageWithAlpha, saved as a transparent PNG.
  - The app also saves the mask (MaskToImage).
- **Quick swap:** the app composites the cut-out over a picked or generated background with Pillow. Pixels stay identical.
- **Smart swap** (Qwen edit): "Replace the background with a neon-lit Tokyo street at night; keep the woman exactly the same and match lighting".

## Upscale
- `upscale_api.json`: from template `utility-gan_upscaler.json`.
  - UpscaleModelLoader(`RealESRGAN_x4plus`) → ImageUpscaleWithModel (x4) → ImageScaleBy(0.5) for x2.
- "Detail upscale" (diffusion re-detailing, e.g. `utility_z_image_turbo_2k_upscaler.app.json` / SeedVR2) is a Phase 3 item.

## Video
- See `video_research.md`. The nodes used are WanImageToVideo, WanFirstLastFrameToVideo, KSamplerAdvanced (high/low split), CreateVideo and SaveVideo.

## 3D
- See `three_d_research.md`. The nodes used are Trellis2Conditioning, Trellis2ShapeStage/UpsampleStage/TextureStage, VaeDecode*Trellis, RemeshMesh, DecimateMesh, UnwrapMesh, BakeTextureFromVoxel, ApplyTextureToMesh, MeshToFile3D and SaveGLB.

## Turnaround / character sheet
- `angles_qwen2511_api.json`: the Qwen edit workflow plus the fal Multiple-Angles LoRA, from template `template_qwen_multiangle.app.json`.
- **Prompt words** are the exact phrases ComfyUI's own `CameraAngle` node produces:
  - Horizontal: `front view`, `front-right quarter view`, `right side view`, `back view`, and so on.
  - Vertical: `low-angle shot`, `eye-level shot`, `elevated shot`, `high-angle shot`.
  - Distance: `wide shot`, `medium shot`, `close-up`.
- The app runs 4 angles (front, right side, back, left side) and stitches them into one sheet with Pillow. ComfyUI's `ImageStitch` node does the same.

## Not native in ComfyUI 0.43 (deliberately avoided)
- **IP-Adapter, InstantID, PuLID, ReActor/face-swap:** these are custom nodes. The face tools are also real-person likeness tools, so they are excluded by design.
