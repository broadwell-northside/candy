# Adult animation research (ES5) — photoreal adult video first, then video → 3D

**Owner:** Andrew Klein · **Written:** 3 Nov 2026 (EST) · **Status:** research only. No app code changed, no weights downloaded, no sites logged into.
**Scope rules:** fictional adults 21+ only (plus Andrew's own PIN-locked "Me" under the existing v4 rules in PRD §V10). Nothing youthful-looking. No real-person or celebrity LoRAs. Everything here is for private, local, personal use.

**Priority (Andrew, 3 Nov 2026, 7:40 AM EST):** hyper-realistic adult **video** is #1. After that comes pulling the characters out of those videos into 3D (Track D). The game work (Track B) and the "game drives the video" hybrid (Track C) are now secondary.

How sure each claim is: **[S]** = stated by a primary source (model card, repo, paper). **[C]** = community report (Reddit/X/blog), not tested by us. **[E]** = our estimate. Nothing here has been run on Andrew's PC yet.

---

## 1. Plain-language summary

1. **The best open adult video model today is still Wan 2.2 (14B, Apache-2.0).** [C] Newer Wan versions (2.5–2.7) are hosted only, so they can't be used for adult content. Out of the box, Wan 2.2 is bad at genital interaction. It becomes good with NSFW LoRAs or an NSFW fine-tune. [C]
2. **The method that works is "picture first, then animate":**
   - make a near-perfect still frame (photoreal model + anatomy LoRAs);
   - animate it with Wan 2.2 image-to-video plus a small stack of NSFW LoRAs;
   - make several takes and keep the best one;
   - repair bad frames with masked inpainting;
   - upscale and smooth the frame rate.

   Commercial adult AI studios, such as the Chinese "Huang Guo" short-drama producers, use this same chain plus human QC. [C]
3. **Hard limits that remain:**
   - Clips are about 5 s per take; longer needs extension tricks.
   - Two bodies in close contact still warp.
   - Anatomy can't be guaranteed from every angle, because a single picture doesn't define the hidden sides.
   - Wan has no sound.
4. **Video → 3D works for motion, not for anatomy.** We can reliably pull a body's movement (a skeleton animation) out of a video. Genitals, soft tissue and close two-person contact can't be recovered as accurate 3D shapes from video, by anyone, today. In 3D, the anatomy has to come from a pre-made adult game body (Daz Genesis 9 with adult add-ons, or the free MPFB fallback). The video supplies the motion and a reference for the look. [S]/[E]
5. **Pure 3D won't look like the video.** The only route to "photoreal" for a 3D scene is to render it, then run it back through the video model offline ("replay render"). Real-time photoreal at a playable resolution isn't possible on one PRO 6000. [S]/[E]

---

## 2. Master table (models, LoRAs, tools, assets)

VRAM is approximate weights-only size unless a source says otherwise (est. = our estimate). 96 GB fits everything below at full precision, though not all of it at once.

### 2.1 Video base models

| Item | Type | Source | Licence | Quality notes | VRAM |
|---|---|---|---|---|---|
| **Wan 2.2 I2V/T2V A14B** | Video model (2 experts: high-noise = motion, low-noise = detail) | https://github.com/Wan-Video/Wan2.2 | Apache-2.0 [S] | Still the default local adult model in Oct 2026 [C]. It has the largest NSFW LoRA ecosystem. Base model is weak at genital interaction [C]. About 5 s / 81 frames at 16 fps per take | ~28 GB per expert bf16; ~14 GB fp8 (est.) |
| Wan 2.2 TI2V 5B | Small video model | same | Apache-2.0 | Fast drafts and low VRAM; lower quality | ~10 GB (est.) |
| HunyuanVideo 1.5 (8.3B) | Video model | https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5 | Tencent community licence | Better text-to-video and object physics; failures show up as isolated bad frames [C]. Very few adult LoRAs | ~17 GB bf16 (est.) |
| LTX-2.5 (22B) / LTX-2.3 | Video + audio model | https://github.com/Lightricks/LTX-2 | LTX-2 community (free under $10M revenue) | Native audio and longer clips. Adult anatomy is hit-or-miss; faces distort [C] | ~44 GB bf16; fp8 ~27 GB (Sulphur 2) [S] |
| Sulphur 2 Base / 10Eros | Uncensored LTX-2.3 checkpoints | https://civitai.com/models/2601098 · https://huggingface.co/TenStrip/LTX2.3-10Eros | follows LTX | Places anatomy correctly in an X side-by-side test [C]. The best use is adding sound to a Wan clip | 27 GB fp8 [S] |
| MiniMax H3 (open weights) | Video + audio | https://huggingface.co/MiniMaxAI/MiniMax-H3 | **Licence excludes users in US/EU/UK/South Korea** [S] | Highest blind-test score: 68.7 vs Wan 58.5. That test gives audio 15% of the score, and Wan has no audio [S]. Raw model misplaces anatomy [C]. 480p 10 s took ~22 min on an RTX 3090 (INT8) [C] | ran on 24 GB INT8 [C] |
| Kandinsky 6.0 Video (29B Pro / 3B Lite) | Video + audio | https://github.com/kandinskylab (Kandinsky 5 repo is MIT; check 6.0 card) | MIT (per release reports) | New (Oct 2026); almost no adult LoRAs yet | ~58 GB bf16 Pro (est.) |
| SkyReels V3 (14B) | Reference-to-video, extension | https://github.com/SkyworkAI/SkyReels-V3 | custom | Keeps several subjects consistent; few adult LoRAs | ~28 GB (est.) |

### 2.2 Adult LoRAs and fine-tunes for Wan 2.2

Note: Civitai removed most hardcore content in 2026. These now live on civarchive mirrors, TensorArt, SeaArt and Hugging Face. [C] Check that every LoRA's sample images show only clearly adult people before using it.

| Item | What it does | Source | Settings people report | Notes |
|---|---|---|---|---|
| **WAN General NSFW** (CubeyAI) | General adult acts and anatomy, high + low pair | https://civarchive.com/models/1307155 | high 0.6–0.8, low 1.0; trigger `nsfwsks` [C] | The most downloaded (403K, 585 MB). Trained with diffusion-pipe on a 4090 |
| SmoothMix Animations | Smoother adult motion | via SpicyAPI list https://spicyapi.ai/lora/wan-2-2-nsfw | 0.5–0.8 [C] | 111K downloads |
| PENIS LoRA by CoachBate v2 (HIGH+LOW) | Male anatomy | https://civarchive.com/models/2314356 | 0.6–0.9 (est.) | Male anatomy is the weaker side of most models |
| NSFW / Female Genitals helper | Female anatomy | https://civarchive.com/models/1434650 | 0.6–0.8 [C] | T2V and I2V |
| GodPussy v1.0 (low) | Female anatomy detail, low-noise expert | https://civarchive.com/models/1955914 | low only | T2V A14B |
| **WAN 2.2 Enhanced NSFW (SVI / camera / Lightning)** merge | All-in-one adult merge | https://civarchive.com/models/2053259 | 2+2 or 2+3 steps, Euler simple, CFG 1 [C] | Praised for speed. "Needs almost no LoRA" [C]. Good for **drafts** |
| Wan2.2-Remix | Adult merge (lightx2v + Fun MPS/HPS + Pusa + NSFW LoRAs) | https://huggingface.co/FX-FeiHou/wan2.2-Remix | fp8/fp16, LightX2V-friendly [C] | r/StableDiffusion consensus: merges hurt character-LoRA likeness, so **base + LoRAs is better for finals** [C] |
| Lightx2v / Lightning (speed LoRAs) | 4–8 step speed-up | Kijai / lightx2v on HF | see recipe R1 | They cause slow motion and lower quality. Use them for drafts, or only after the first steps [C] |

### 2.3 Keyframe (still image) models

| Item | Source | Licence | Notes |
|---|---|---|---|
| **Chroma** (8.9B, Flux-derived, uncensored) | https://huggingface.co/lodestones/Chroma | Apache-2.0 | Better than Z-Image Turbo for explicit male anatomy [C]. Use it for explicit keyframes |
| Z-Image Turbo / base (6B) | https://github.com/Tongyi-MAI/Z-Image | Apache-2.0 | Best skin realism (PRD §V2), but its NSFW LoRAs are weaker [C]. Use it for non-explicit and SFW frames |
| Qwen-Image-Edit (2509+) | https://github.com/QwenLM/Qwen-Image | Apache-2.0 | Builds a two-person starting frame from separate characters [C] |
| SeedVR2 (image and video upscaler) | https://github.com/ByteDance-Seed/SeedVR | Apache-2.0 | Upscaling the start image improves identity hold in video [C] |

### 2.4 Control, multi-person and motion transfer

| Item | Source | Licence | Quality notes | VRAM |
|---|---|---|---|---|
| **SCAIL-2** (zai-org, Jun 2026) | https://github.com/zai-org/SCAIL-2 · ComfyUI native nodes `WanSCAILToVideo`, `SCAIL2ColoredMask` (SAM3 tracking) https://docs.comfy.org/tutorials/video/zai/scail2 | Apache-2.0 | Built for **multi-character** animation and replacement. The ComfyUI-SCAIL2-Easy plugin handles up to 6 subjects. In the SCAIL paper's cross-driven motion accuracy test, SCAIL scored 53% vs Wan-Animate 35% and VACE 9% [S] | Wan-14B class |
| Wan 2.2 Animate (Move / Replace) | https://docs.comfy.org/tutorials/video/wan/wan2-2-animate | Apache-2.0 | Scored 7.1/10 in an r/SD test, the best balance. Handles 2 characters at about 80% likeness. Stack reference images vertically [C]. Multi-person isn't official (issue #150), and occlusion breaks pose extraction | Wan-14B class |
| Wan2.2-VACE-Fun-A14B | https://huggingface.co/alibaba-pai/Wan2.2-VACE-Fun-A14B | Apache-2.0 | Takes depth, pose, canny, MLSD, trajectory or a reference image; 512–1024 px, 81 frames. The tool for **object contact** guided by a blocked-out 3D scene. Weakness: "mushy", identity drifts [C] | Wan-14B class |
| WAN I2V Conditioning Mask Pro | https://github.com/shootthesound/comfyui-wan-i2v-control | no licence file (ask author; private use) | Locks parts of the start frame (face, background) while the rest moves. "Closest to MAGREF-level face consistency" [C] | — |
| ComfyUI-Wan-VACE-Prep / VACE masked inpaint | https://github.com/stuttlepress/Comfyui-Wan-VACE-Prep | open | Repairs **only** a masked region across frames (white = regenerate, grey 127 = keep), with feathered edges | Wan-14B class |
| ComfyUI-Forbidden-Vision | GitHub (search the name) | open | Adult-aware detection and segmentation, used to make the repair masks | small |
| SVI 2.0 Pro (Stable-Video-Infinity) | https://github.com/vita-epfl/Stable-Video-Infinity | MIT | Long continuous takes (30 s+) with an anchor image. There's no colour shift if set up correctly (see issue #51) [C] | Wan-14B class |

### 2.5 Finishing

| Item | Source | Licence | Notes |
|---|---|---|---|
| SeedVR2 (video) | above | Apache-2.0 | Upscales to 1080p while adding real detail |
| GIMM-VFI | https://github.com/GSeanCDAT/GIMM-VFI | see repo (non-standard) | Interpolates 16 fps → 30 or 60 fps |
| Image Color Match node | ComfyUI core / KJNodes | open | Matches every frame to frame 1, which fixes colour drift in extended clips [C] |
| LTX-2.x audio pass | above | LTX-2 community | Community workaround: "generate with Wan, add sound with LTX" [C] |

### 2.6 Training our own video LoRAs

| Item | Source | Licence | Recipe people report |
|---|---|---|---|
| **musubi-tuner** (kohya) | https://github.com/kohya-ss/musubi-tuner/blob/main/docs/wan.md | Apache-2.0 | Clips at 16 fps, length 4n+1 frames (81 = 5 s), one `.txt` caption per clip. Train both experts (`--dit` low + `--dit_high_noise`); boundary 900 for I2V. On 96 GB, bf16 runs with no block swap (est.) |
| diffusion-pipe | https://github.com/tdrussell/diffusion-pipe | MIT | Motion LoRA: 10–30 short clips (3–4 for one narrow concept), 256–512 px, 25–81 frames. "Motion matters more than resolution" [C] |
| Character LoRA for Wan | r/SD May 2026 https://www.reddit.com/r/StableDiffusion/comments/1tn3d8v/ | — | 30–50 clips of 2–5 s: ⅓ front, ⅓ three-quarter, ⅓ profile; rank 32–64; lr 1e-4. Bootstrap by animating your own image-LoRA stills, then keep the cleanest ~30 [C] |
| ai-toolkit (ostris) | https://github.com/ostris/ai-toolkit | MIT | Easier interface; supports Wan 2.2 |

### 2.7 Video → 3D / 4D (Track D)

| Item | What it gives | Source | Licence | Quality (honest) |
|---|---|---|---|---|
| **PromptHMR** (video, world coordinates) | Multi-person SMPL-X bodies and motion in world space | https://github.com/yufu-wang/PromptHMR | research (SMPL-X licence applies) | Among the best on EMDB-2 (WA-MPJPE 71 mm, RTE 1.3) [S]. Drifts badly under very fast camera moves [S] |
| GVHMR | Single-person world-grounded motion | https://github.com/zju3dv/gvhmr · ComfyUI → FBX https://github.com/AKASubaz/ComfyUI-Video2MotionCapture | research | Fast and simple: 111 mm WA-MPJPE [S]. Single person only |
| WHAM | Single-person motion | https://github.com/yohanshin/WHAM | MIT code (+SMPL licence) | Weaker: 135.6 mm [S] |
| WildHSR / Human3R / GUSH3R (2026) | Feed-forward people + scene; GUSH3R outputs people as moving Gaussians | https://arxiv.org/html/2609.29106 · https://arxiv.org/html/2607.05243v1 | papers (code varies) | State of the art in research; not production tools yet [E] |
| **SAM 3D Body** (Meta) | Rigged full-body mesh from one image (MHR rig) | https://github.com/facebookresearch/sam-3d-body · ComfyUI node exporting rigged FBX https://github.com/danielvw/ComfyUI-SAM3DBody | SAM licence (commercial OK); MHR Apache-2.0 | Good body *shape*. No genitals and no clothing separation [E] |
| SAM3DBody-cpp | Real-time multi-person → BVH | https://github.com/AmmarkoV/SAM3DBody-cpp | open | Live mocap from webcam or video |
| Close two-person contact (Harmony4D benchmark; CloseInt, BUDDI, SocialMirror) | Two bodies touching | https://arxiv.org/html/2410.20294v1 · https://arxiv.org/html/2604.13581v1 | research | **Weak.** Best methods are still 9–13 cm off, with 5–10 cm of body interpenetration [S]. Unusable for intimate contact without hand fixing |
| **ExAvatar** | Drivable whole-body Gaussian avatar (body, hands, face) from a ~10 s video | https://github.com/mks0601/ExAvatar_RELEASE | MIT (+SMPL-X licence) | Photoreal when driven by new poses. Gaussians follow an SMPL-X mesh, which has no genitals, so adult detail is only "painted on" and won't deform [E] |
| GaussianAvatar | Avatar from a single video | https://github.com/aipixel/GaussianAvatar | MIT | Older (2024); same limits |
| LHM++ (2026) | Animatable Gaussian avatar from 1+ images in under 1 s | https://github.com/aigc3d/LHM-plusplus | Apache-2.0 (NVIDIA parts non-commercial) | Quick previews; same anatomy limit |
| 4DGT / MoVieS / Shape of Motion / MonST3R | General moving-scene reconstruction | https://4dgt.github.io/ | research | Lets you view a recorded moment from new angles. Not rigged, so it can't be animated in a game [S]/[E] |
| godotGS (Gaussian splats in Godot) | Splat viewer with per-splat keyframes | https://klausi3d.github.io/godotGS/latest/features/animation/ | open | **No skinned (skeleton-driven) splats.** Advice from KIRI: use splats for looks plus a skinned mesh for animation [S] |
| BVH Motion Retargeter (Blender) | SMPL-X / BVH motion → Genesis 9 or MPFB skeleton | https://github.com/BacteriaJun/BVH-Motion-Retargeter | open | Standard retargeting; needs fixes at the hands and feet |
| R3DS Wrap / Faceform | Transfers scanned or generated shape and texture onto a G9 mesh | https://www.russian3dscanner.com/ | paid | The professional way to put a "look from the video" onto the game body |

### 2.8 Game-side assets (Track B, secondary — details in PRD §V3/§V6)

| Item | Source | Licence / cost | Notes |
|---|---|---|---|
| Daz Genesis 9 + Golden Palace (female) / Dicktator (male) | https://www.renderotica.com/store/sku/67582_Golden-Palace-For-Genesis-9 · https://www.renderotica.com/store/sku/67091_Dicktator-for-Genesis-9 | Each product needs a **Daz Interactive License** for game use (G9 Starter Essentials IL ≈ $50) [S]; check Renderotica's own terms | The most realistic adult anatomy available for game bodies |
| MPFB2 + CC0 "adult male genitalia" proxy | http://makehumancommunity.org/proxy/adult_male_genitalia_breast_fix.html | CC0, free | Free fallback; a female equivalent isn't verified |
| naelstrof DynamicPenetrationForGames (Unity) | https://deepwiki.com/naelstrof/DynamicPenetrationForGames | MIT | The method to port to Godot: GPU bending along a spline plus bulge |
| WiggleBone / JiggleBones (Godot) | https://github.com/detomon/wigglebone | MIT | Soft-tissue jiggle |
| Paired animation packs | phantasiagame ($10+, 28 paired FBX) · Truebones Kama-Sutra ($149, 350 moves) | paid | Hand-authored contact poses, which beat video-extracted motion for contact |

### 2.9 Real-time hybrid (Track C, secondary)

| Item | Source | Licence | Verdict |
|---|---|---|---|
| Krea Realtime 14B | https://huggingface.co/krea/krea-realtime-video | weights Apache-2.0; inference code CC BY-NC-SA | ~11 fps at 320×576 fp8 on an RTX 5090. Higher resolution needs 40 GB+ [S]. **Low-res preview only** |
| StreamDiffusionV2 | https://github.com/chenfengxu714/StreamDiffusionV2 | Apache-2.0 | 58 fps for 14B needs **4×H100** [S]. Not possible on one card |
| Blender/Godot passes → Wan VACE / Fun Control / SCAIL-2 | https://docs.comfy.org/tutorials/video/wan/wan2-2-fun-control | Apache-2.0 | **Offline "replay render" works today** [C] |

---

## 3. Recipes (ComfyUI, reported settings — to verify on Andrew's PC)

**R1 — Wan 2.2 I2V "quality" (finals)**
- Model: base Wan 2.2 I2V A14B, high + low experts. Use bf16 on 96 GB; fp8 if speed matters.
- Text encoder: umT5. CLIP Vision encode of the start frame goes into `WanImageToVideo`. [C]
- Resolution: 480×832 or 720×1280. Many community LoRAs **stop working above 720p**, so upscale afterwards instead. [C]
- Frames: 81 at 16 fps (5 s). Shift 5–8; sampler Euler; scheduler simple / beta / beta57.
- **Three KSamplers** [C], e.g. for 14 total steps:
  1. High expert, **no speed LoRA**, CFG 3–3.5, steps 0–2.
  2. High expert + Lightx2v 1.0, CFG 1, steps 2–8.
  3. Low expert + Lightx2v 1.0, CFG 1, steps 8–14.
- 14 steps looks "much better" than 8. Halving the speed LoRA strength and using 21 steps looks better still. [C]
- Without any speed LoRA: 20–30 steps, CFG ~3.5 high / 1–3 low. [C]
- Note: some users find 3 samplers drift away from the start face, and 2 samplers (4 high + 6 low, LCM / sgm_uniform) hold the face better. **Try both.** [C]
- LoRA stack (high / low):
  - WAN General NSFW 0.7 / 1.0;
  - one act or motion LoRA 0.6–0.8;
  - one anatomy helper 0.6–0.8;
  - our own character LoRA ~0.8 / 1.0.

  Never use LoRAs trained only on still images: "image-trained LoRAs kill movement". [C]
- Prompt: one or two plain sentences about the motion. Punctuation creates pauses. Describe any body part hidden in the start frame. [C]
- Takes: make 4–8 seeds per shot and keep the best one. Even experts "pick the best of N". [C]

**R2 — Wan 2.2 "draft"**
- Model: the Enhanced NSFW Lightning merge (civarchive 2053259) or Wan2.2-Remix.
- 2+2 steps, Euler simple, CFG 1. [C]
- Use it to preview the action and timing, then re-run the chosen take with R1.

**R3 — Starting frame that holds identity**
- Keyframe from Chroma (explicit) or Z-Image (non-explicit), with character LoRAs plus face, hand and body detailers.
- **Upscale the keyframe with SeedVR2** before animating. [C]
- Build a reference sheet per character (front, ¾, profile, full body) to feed animate/reference nodes.
- Use **Conditioning Mask Pro** to lock the face and background while the body moves. [C]

**R4 — Two people in contact**
- Build **one start frame that already shows both people** in the starting pose. Assemble it with Qwen-Image-Edit, or let Wan bring each character in using their own LoRA. Don't load two character LoRAs globally, because they bleed into each other. [C]
- Then use R1, or SCAIL-2 with `SCAIL2ColoredMask` (one colour per person) driven by a pose video when the motion must be exact.
- Wan 2.2 Animate is the fallback; stack references vertically. [C]

**R5 — Precise motion or object contact**
- Block out the scene in Blender or Godot (bed, chair, toy, hands) with simple mannequins.
- Export depth, pose (DWPose) and canny passes.
- Feed them to Wan2.2-VACE-Fun or SCAIL-2 together with the photoreal start frame.
- Known issue: front/back confusion with mocap rigs. Add a depth pass and a clear prompt. [C]

**R6 — Longer scenes (10–60 s)**
- Edit like a film: 3–8 s shots, with cuts covering the joins. This is what commercial studios do. [C]
- For one continuous take: **SVI 2.0 Pro**. It uses an anchor image plus previous frames, and segments can have different lengths. [C]
- To land on a planned pose: generate the segment, fix the face on its last frame, then **re-run that segment with first-last-frame (FLF2V)**. This is called "double processing". [C]
- Always add **Image Color Match to frame 1**. Avoid tiled VAE across time, which is a known cause of colour shift. [C]

**R7 — Repair**
- Detect bad regions (Forbidden-Vision or a manual mask).
- Run a VACE masked inpaint over just those frames and that region: feathered mask, grey 127 elsewhere, paste only the masked area back.
- Faces: fix with the face detailer on keyframes, then FLF2V.

**R8 — Finish**
- SeedVR2 video upscale to 1080p.
- GIMM-VFI to 30 fps, or 60 fps for slow motion.
- Colour match, film grain (PRD §V2).
- Optional: LTX-2.x audio pass, later.

**R9 — Train our own LoRAs (after the first month)**
- Data: in-app clips of fictional adults, curated by hand, plus 3D-rendered motion clips from the game.
- Real adult footage: no by default. If Andrew ever chooses it, it must be legally obtained and adult-verified, with faces masked or cropped, so that no real person's identity is learned.
- Use musubi-tuner as in §2.6.

---

## 4. Track D detail: what "video → 3D" can and can't do (honest)

| Goal | Today | Our path |
|---|---|---|
| Body motion of one person | **Good.** GVHMR / PromptHMR / SAM 3D Body give a usable skeleton animation. Expect small foot slides | Extract to BVH/FBX → retarget in Blender → Godot |
| Two people moving near each other | **OK** (PromptHMR multi-person) | Same, then align them |
| Two people **touching / intimate contact** | **Poor.** 5–13 cm errors and interpenetration [S] | Use the extracted motion as a *guide*, then fix contact with Godot IK, paired animation packs and contact blend shapes |
| Genitals, breasts, soft-tissue shape | **Not recoverable from video** (SMPL-X has no genitals; generated video isn't consistent across angles) | From the asset body: Daz G9 + Golden Palace/Dicktator, or MPFB. Jiggle via WiggleBone; deformation via a port of the MIT shader method |
| Body proportions | **Good** (SMPL-X shape / SAM 3D Body) | Fit the asset body's morphs to the recovered shape |
| Skin and face look | **Fair.** Projecting from AI video gives patchy textures because angles disagree | Use the character's image LoRA to make a clean front/back/side texture set, then project with R3DS Wrap or Blender. Game skin: Godot SSS skin (PRD §V5) |
| Photoreal moving 3D person you can view from any angle | **Research only** (ExAvatar, GUSH3R, 4DGT). Not rigged for games, and Godot can't skin splats | Optional viewer for replays only; revisit in 6–12 months |
| Photoreal look in the game | Not in real time | **Replay render:** record game motion → pose/depth → SCAIL-2/VACE → photoreal clip (offline, minutes per clip) |

**Expected quality:** the 3D characters will look like a good adult game (Virt-A-Mate class). They won't look like the photoreal video. Motion pulled from good videos will look natural for solo movement. Intimate contact will need hand-tuning or purchased paired animations.

---

## 5. Community findings (where the consensus comes from)

- **r/StableDiffusion / r/comfyui** (2025–2026): base Wan + LoRAs beats merges; the 3-sampler method; SVI for long takes; colour matching; one shared start frame for couples; Animate and SCAIL rankings. Links in §3 and the notes. Reddit's direct JSON is blocked for our fetcher, so all of this came from search results. [C]
- **X (searched 3 Nov 2026):**
  - @NamekoKing777 (11.8K followers): same-image test. Wan 2.2 NSFW merge and LTX-2.3 NSFW fine-tune place anatomy correctly; raw MiniMax H3 doesn't. "Best workflow: video with Wan, sound with LTX." https://x.com/NamekoKing777/status/2085354752758714823
  - @jmo_jean: official Wan 2.2 is "very bad for genital interaction" until NSFW-trained. https://x.com/jmo_jean/status/2086340605198622854
  - Huang Guo adult short-drama pipeline (several posts, Sep–Nov 2026): LLM script → character LoRA → keyframes → manual polish → Wan 2.2 (NSFW-tuned) or self-hosted MiniMax H3 → lip-sync → 30 fps → audio → edit. https://x.com/grok/status/2094942526029348891 · https://x.com/lbolbo123456/status/2115421383647985923
  - Video → 4D: GVHMR is what people use to extract motion for 4D Gaussian work. https://x.com/21CenturyBoomer/status/2111281964367929635
- **Commercial sites:**
  - Candy.ai: companion clips with strong continuity but little control.
  - Promptchan: 3–5 s clips, Pro tier.
  - SugarLab and Pornify: cheap and tag-driven.
  - Reviews agree a **self-hosted Wan 2.2 gives the most control and quality** (720p, 5 s clips). https://reviewai.net/best/best-nsfw-ai-video-generators/ · https://renderreport.com/blog/best-nsfw-ai-video-generators [C]
  - Which model each site uses isn't public. Codex question Q1 asks for direct evidence.
- **Civitai and mirrors:** see §2.2. Expect links to move; keep local copies of the LoRA cards' sample settings (text only).

---

## 6. Safety and data rules for this phase

- Adults only. All characters are fictional 21+, kept under the existing automatic age check (PRD §A8). Any LoRA whose samples look youthful is rejected.
- No real-person or celebrity LoRAs. The only real person is Andrew's own PIN-locked Me, under PRD §V10.
- Training data: our own generated or rendered clips first. If real adult footage is ever used: legally obtained, adult-verified, faces masked, and never used to learn a real person's identity.
- Third-party LoRAs are checked by hash and stored offline. Read their licences and cards before use.

Sources: the full URL list is in this file and in the ES5 notes (`/tmp/es5/notes.md`, copied into §2–§5).
