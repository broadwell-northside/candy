> **Historical and superseded (Nov 5, 2026).** `docs/EASY_STUDIO_FINAL_PRD.md` is the product source of truth. Do not implement this file or quote it into new docs.


# Easy Studio 4.1 — Product Requirements Document

**Owner:** Andrew Klein. **Version:** 4.1. **Date:** 3 Nov 2026.
**Status:** v4.1 is the plan. The app now records the Still → Motion → Fix → Finish model choices, sends explicit keyframes to Chroma, keeps ordinary stills on Z-Image, uses fixed clip lengths, and can send a picture to video, save a still from a video, regenerate a character, and change clothes without changing the body. The Scene page, the repair brush, the saved LoRA-stack editor, SCAIL-2, SVI, and the real SeedVR2 and GIMM graphs are still later. They are named in the registry and are not claimed as running.

How this document is laid out:
- **Part V.1** is new in version 4.1: adult video first, then video → 3D. Where it disagrees with Part V, **Part V.1 wins**.
- **Part V** covers version 4.
- **Part A** covers version 3.
- **Part B** is the version 2 baseline.
- The full research behind Part V.1 (tables, links, licences, VRAM, recipes) is in `docs/research/adult_animation_research.md`.

**Decision record, 3 Nov 2026 (after this document was written):**

- **D2 is chosen.** Game bodies are Daz Genesis 9 with Golden Palace (female) and Dicktator (male), plus a Daz Interactive License for each product that ships in the game. MPFB2 is the free fallback only. Nothing has been purchased. No Daz files belong in this repository.
- **Export path:** Daz Studio, then Blender with Diffeomorphic or Daz to Blender, then glTF, then Godot. Each product needs its own Interactive License. The Genesis 9 Starter Essentials Interactive License is about $50. Check Renderotica's game-use terms before buying. A personal-use license is not the game license.
- **Hardware is unconfirmed** until the desktop install hold ends. Do not treat a 96 GB RTX PRO 6000 as a measured fact.
- **Token packs and paywalls** seen in the Candy evidence stay research only. They are not a feature.
- **Candy parity is dropped** (issue #1, `ES-RESEARCH-20261103-004`). Candy is a visual-quality benchmark only. Chat, tokens, shop, community, memory, and notifications from that evidence are out of scope, including `evidence/BUILD-PROMPT.md` and earlier parity notes on the evidence branch.
- **Six research tracks are the active research index** (`evidence/research/INDEX.md` at `fe3525a`). Order: photoreal skin and faces, photoreal video, consistent characters, video-to-3D, realistic 3D humans, and three non-explicit Candy quality-baseline clips. Track 1 published SeedVR2 7B int8, SUPIR, and Z-Image Turbo template settings. They are selectable configs in `app/pipeline_candidates.json`, not the default, and they have not been run locally. Track 2 at that commit is a queue with no settings yet.
- **3D import stays format-agnostic.** D2 still names Genesis 9 as the body. FBX and glTF are both acceptable into Godot 4. Do not lock the importer to one format while Codex checks rigging.
- **The first real test machine is Andrew's M5 Max MacBook Pro** (Apple Silicon, 128 GB unified memory, macOS), even if it is slow. Its profile is the default: Z-Image Turbo for fast stills, Chroma1-HD keyframes in fp16 or bf16 with no fp8-only Chroma file, and Wan 2.2 TI2V-5B for short motion proofs, without memory offload. The RTX 4090 profile stays for upscales, keyframes, and previews. The RTX PRO 6000 profile stays for main video and is still not confirmed. Do not treat a source paper's 80 GB example as this machine's spec.
- **Video evaluation recipes** (issue #1, `ES-RESEARCH-20261103-006`, commit `f5b74ad`) are candidates, not the running default. First recipe: Wan 2.2 A14B native image-to-video, high/low fp8, 20 steps split 10, CFG 3.5, Euler/simple, shift 5, 640×640, 81 frames, 16 fps. Second: Wan 2.2 14B first/last frame, 20 steps split 10, CFG 4, shift 8. Fallbacks: HunyuanVideo 1.5 720p, then LTX-2.5 distilled two-stage, with Wan 5B TI2V if memory is tight. The 4-step LightX2V branch and Endless Wan / SVI2Pro wait until native motion passes, one change at a time. Finish native frames first, then compare SeedVR2 3B and 7B and color match separately, then RIFE only on approved motion, then encode. Keep the native frame count and frame rate. Stills still go through Andrew's still-first score before any of this runs. Chroma1-HD and Z-Image Turbo remain the still candidates.
- **Character order is unchanged** (`ES-RESEARCH-20261103-007`): FLUX.2 Klein 4B reference edit, then Qwen-Image-Edit-2511, then a character LoRA on approved fictional stills. CatVTON, IDM-VTON, and FitDiT are optional garment comparisons. FLUX 3 Klein stays unused until its license is read.
- **Video-to-3D** (`ES-RESEARCH-20261103-008`, commit `85a91d3`): evaluation order stays PromptHMR video to GLB, then WHAM, then GVHMR. All of that is not run. The first 3D milestone is owned code in `app/g9_adapter.py`: PromptHMR output, an explicit rest-pose and bone map onto Genesis 9, then glTF, then Godot 4. The map is empty until a local file is inspected, and the adapter has its own test. PromptHMR's default leaves hand pose off and writes 22 body rotations, so fingers are a separate plan: try hand pose if the tool supports it, otherwise a SAM 3D Body or MHR hand pass, otherwise a held default hand pose. That choice waits for the first local run. Two-person scenes get a contact-cleanup step on the retargeted rig. The paper reports bodies still passing through each other in close pairs. Hug and dance identity swaps are unknown. WHAM's pair contact is unknown because its contact reasoning is feet only. SAM 3D Body stays a separate body and hand experiment. GaussianAvatar and HUGS stay appearance only. FBX remains acceptable.
- **Genesis 9 export evaluation** (`ES-RESEARCH-20261103-009`, commit `b611551`): the order to test is Genesis 9, then Diffeomorphic 5.2.0 and Blender 5.2, then glTF 2.0, then Godot 4.7.2 Forward+. The official Daz to Blender bridge is the fallback, used to separate bridge problems from the default path. MetaHuman and Unreal are not adopted. The game stays on Godot. This round trip has not been run. Morph names are not guaranteed to survive: Diffeomorphic slices at 57 characters, Blender shape-key names hold at most 63 bytes, the glTF exporter writes `extras.targetNames` and skips basis, muted, and self-relative keys, and Godot turns colons into underscores, suffixes duplicates, and can drop blend shapes if meshes are merged. Keep a morph-name manifest at every stage. Names are colon-free, unique, and under 57 characters. After import, compare count, order, and names with that manifest. Leave mesh-merge off until that check passes. glTF export keeps Apply Modifiers off, Shape Keys on, Shape Key Normals on, Shape Key Tangents off, Animations on, Shape Key Animations on, Always Sample Animations on, sampling at 1 frame, and Reset Shape Keys Between Actions on. Daz ERC and JCM correctives and Blender drivers are not carried by glTF. Bake them or rebuild them in Godot. The first round-trip test scores static shape, runtime morph control, and pose-driven correctives separately, together with the PromptHMR to Genesis 9 rest-pose map. Materials, collision proxies, cloth pins, and spring chains are authored in Godot. Each Daz product still needs its own interactive license before any purchase. Nothing has been purchased.
- **Candy benchmark clips** (`ES-RESEARCH-20261103-010`, commit `3fb51b7`) are a reference, not a spec and not a quality ceiling. Three non-explicit, fully clothed clips: a skin close-up, a full-body turn, and a two-person hand-hold dance. Each is 496×864, 24 fps, 97 frames, about 4 seconds, H.264, and silent. Only two stills were reviewed per case, so blink, identity drift, foot slide, finger count, and flicker are still unknown. The local video test uses these same three scenes and reviews the full clip beside those files. Our clips must beat that resolution and the fine skin and iris detail. No further spending on that site. Do not copy its features. All six research tracks are complete. The entry point is `evidence/research/INDEX.md` on the evidence branch.
- **Finish target** in the registry is SeedVR2 to 1080p, then GIMM-VFI to 30 fps. Where an older sentence in Part V still says 32 fps, Part V.1 wins. That finish target is a placeholder until the photoreal-video track publishes exact settings.

---

# Part V.1 — Easy Studio 4.1: photoreal adult video first

## V.1-0. New priority (Andrew, 3 Nov 2026, 7:40 AM EST)

**1.** **Hyper-realistic, photoreal adult video scenes are #1.**

**2.** **Then bring those characters into 3D:** pull their motion (and as much of their look as possible) out of the videos into game bodies.

**3.** Everything else comes after, in the v4 order (Me avatar, 3D realism, the game, chat, live scan).

All the same rules apply: fictional adults 21+ only (plus Andrew's own PIN-locked Me under §V10), no youthful look, no real-person or celebrity LoRAs, and local and private use only.

## V.1-1. The ONE recommended video pipeline: "Still → Motion → Fix → Finish"

**In plain words:** make one perfect photo of the scene's first moment, animate it with Wan 2.2 plus adult add-ons, make several takes and keep the best one, repair any bad spots, then sharpen and smooth it. Long scenes are edited from short shots, like a film.

| Step | What happens | Starting models / tools | Why |
|---|---|---|---|
| 1. Cast | Each fictional character gets an image LoRA and a reference sheet (front, ¾, side, full body) | Z-Image base for the LoRA (§V2), Chroma for explicit stills | Keeps the same face and body across shots |
| 2. Still | Create the first frame of the shot. For couples, **both people go in one frame**. Run detailers, then upscale with SeedVR2 | **Chroma** (explicit) or **Z-Image Turbo** (non-explicit) + anatomy LoRAs; Qwen-Image-Edit to assemble couples | Wan copies what it sees. A clean, sharp first frame is half the quality |
| 3. Motion | Image-to-video, 5 s per take, 480p–720p, 4–8 takes per shot | **Wan 2.2 I2V A14B base (bf16)**, using the 3-sampler recipe (research doc R1) and a high/low LoRA stack: **WAN General NSFW** (0.7/1.0) + one act LoRA + anatomy helper (CoachBate penis v2 or the female genitals helper, 0.6–0.8) + our Wan character LoRA. Lock the face with **Conditioning Mask Pro** | The community's best open adult setup today. Base model + LoRAs keeps character likeness better than merges |
| 3b. Exact motion (optional) | Drive the shot from a pose/depth video, made from a game mock-up, a paired animation, or our own reference clip | **SCAIL-2** (multi-person, colour masks), Wan 2.2 Animate as a fallback, **Wan2.2-VACE-Fun** for object contact | When the act, position or contact with furniture and objects must be exact |
| 4. Length | Short shots plus cuts. For one continuous take, use SVI 2.0 Pro; use first-last-frame to land on a planned pose | SVI 2.0 Pro, Wan FLF2V, Image Color Match | Wan drifts after about 5 s; these are the fixes the community trusts |
| 5. Fix | Mask the bad area (anatomy, hands, face) over the bad frames and regenerate only that area | VACE masked inpaint, Forbidden-Vision masks, face detailer + FLF re-run | Bad frames are usually local, so they can be fixed without redoing the shot |
| 6. Finish | Upscale to 1080p, 16 → 30 fps (60 for slow motion), colour match, grain | **SeedVR2** video, **GIMM-VFI** | The finished photoreal look |
| 7. Sound (later) | Add audio after the picture is locked | LTX-2.x audio pass (community workaround) | Wan is silent |
| 8. Own LoRAs (month 2+) | Train Wan character and motion LoRAs on our own generated or rendered clips | **musubi-tuner** (bf16, no block swap on 96 GB) | The public adult LoRA catalogue is small and keeps disappearing |

**Fast draft mode:** the Enhanced NSFW Lightning merge (2+2 steps) to preview the action, then re-render the chosen version with the quality recipe.

**What the app needs (to build later, not now):**

- A "Scene" page: shot list, per-shot still, takes grid, "keep / fix / extend" buttons.
- Saved LoRA stacks per act.
- A repair brush that makes the mask.
- A finish button for the upscale + interpolate chain.
- The ComfyUI graphs (R1–R8) shipped as fixed, tested workflow files.

**Expected speed on the PRO 6000 (estimate, to measure):** several minutes per 5 s take at 720p with the quality recipe, and well under a minute per draft. A finished 60 s scene with 4–8 takes per shot is an evening, not minutes.

## V.1-2. The ONE recommended video → 3D path: "Motion from video, body from assets, look by replay"

**In plain words:** we copy how the characters **move** from the finished videos onto ready-made adult 3D bodies in Godot. We can't copy their bodies' 3D shape from video, and nobody can yet. If Andrew wants a 3D scene to look photoreal again, we record it and run it back through the video pipeline offline.

**1.** **Track each person** in the finished clip (SAM3 masks, the same ones SCAIL-2 uses).

**2.** **Pull the motion:**

- **PromptHMR** for two or more people (world-space SMPL-X);
- **GVHMR** for one person (ComfyUI → FBX node already exists);
- **SAM 3D Body** for body shape.

**3.** **Pick the game body:**

- **Daz Genesis 9 + Golden Palace / Dicktator** for the most realistic anatomy (needs Interactive Licences);
- **MPFB2** + CC0 adult proxy as the free fallback.

Fit its morphs to the recovered body shape.

**4.** **Retarget:** SMPL-X/BVH → Blender → G9/MPFB skeleton → glTF → Godot 4.6.

**5.** **Fix contact by hand or with the game's systems:**

- Godot IK (TwoBoneIK3D/FABRIK3D);
- paired animation packs as a base;
- contact blend shapes;
- WiggleBone jiggle;
- a Godot port of the MIT penetration-deformation method.

**6.** **Look:**

- generate a clean texture set from the character's image LoRA (front/back/side), project it onto the body (R3DS Wrap or Blender);
- Godot SSS skin shader (§V5).

**7.** **Photoreal replay (optional):** record the 3D scene's pose and depth → SCAIL-2 / VACE-Fun with the character's still → a photoreal clip. Offline only.

**Honest quality assessment:**

- **Solo motion:** good, natural movement with small foot-slides to clean up.
- **Two people touching:** poor straight out of video. Research methods are still 5–13 cm off, with bodies passing through each other, so every intimate contact needs fixing.
- **Anatomy and soft tissue in 3D:** comes **only** from the asset bodies and our deformation systems, not from the video.
- **Overall look in-game:** good adult-game level (Virt-A-Mate class), **not** photoreal.
- **Photoreal in real time:** not possible on one PRO 6000. Krea Realtime manages about 11 fps at 320×576 on a 5090-class card, so preview quality only. Photoreal is offline replay only.
- **Photoreal 3D people (Gaussian avatars: ExAvatar, LHM++, GUSH3R):** real research, but there are no genitals in their body model, nothing can be skinned in Godot, and they're not game-ready. Watch these; revisit in 6–12 months.

## V.1-3. Phased plan (replaces the top of the §V1 roadmap)

| Phase | What | Depends on | Exit test |
|---|---|---|---|
| **P4V-1 — Video core** | The parts of P4a that feed video: Chroma + Z-Image stills, detailers, SeedVR2. Wan 2.2 I2V base in bf16 with recipes R1/R2, saved LoRA stacks, the takes grid | v3 app | 10 test shots (solo, both sexes, 5 acts) rated "keep" in at least 1 of 4 takes |
| **P4V-2 — Couples, control, objects** | One-frame couples (Qwen-Image-Edit), SCAIL-2 multi-person, VACE-Fun with simple Blender/Godot blockouts, Conditioning Mask Pro | P4V-1 | 10 couple and object shots, each with a "keep" take within 8 tries |
| **P4V-3 — Long scenes + fixing + finish** | Scene page (shot list), SVI 2.0 Pro, FLF2V, colour match, repair brush (VACE inpaint), SeedVR2 video + GIMM-VFI. Audio is a later extra | P4V-2 | One 60 s, 1080p/30 fps scene with no visible joins or colour shift |
| **P4V-4 — Our own LoRAs** | musubi-tuner workflow for Wan character LoRAs (30–50 clips) and motion LoRAs (10–30 clips), built from our own generated or rendered clips | P4V-1 | Character likeness holds through a 5-shot scene |
| **P4D — Video → 3D motion** | Motion extraction (GVHMR / PromptHMR / SAM 3D Body) → retarget to G9 or MPFB in Godot; contact fix tools; replay render | P4V-3, plus the §V6 base bodies | A 20 s solo clip and a 20 s couple clip play on game bodies with no visible passing-through after fixes |
| Then | P4 (rest of photoreal images), P5 Me, P6 3D realism, P7 game, P8 chat, P9 live scan, as in §V1 | | |

## V.1-4. Pessimistic review from three viewpoints

**A. ComfyUI video power user**

- "Your Wan LoRA list will be half dead in three months. Civitai already removed the hardcore models." *Response:* store LoRAs locally by hash with their cards (text). From P4V-4, rely on our own trained LoRAs.
- "Three samplers lose the start face." *Response:* P4V-1 tests the 2-sampler and 3-sampler setups side by side on the 10-shot set and picks one per act.
- "Most LoRAs break above 720p." *Response:* generate at 480–720p and get 1080p from SeedVR2. Don't render higher.
- "Two-person contact will warp no matter what." *Response:* true. We use one-frame couples, SCAIL-2 masks, the repair brush and best-of-N. The P4V-2 exit test is about whether we can *get* a keeper, not whether every take works.
- "Wan has no sound." *Response:* audio is a later extra (LTX pass). MiniMax H3 has sound, but its licence may exclude Andrew; see decision D1.

**B. 3D / game tech artist**

- "Video-to-3D of sex scenes is mostly a myth today." *Response:* agreed. We take motion only, and contact is re-authored. The plan never promises photoreal 3D anatomy from video.
- "Retargeting SMPL-X onto G9 breaks hands, feet and spine twist." *Response:* expected cleanup. Use paired animation packs as the base for contact poses and video-extracted motion for everything else.
- "Daz adult add-ons plus Interactive Licences add up, and Renderotica terms may differ." *Response:* decision D2. MPFB is the free fallback, and the Godot-vs-Unity gate from §V6 stays.
- "Gaussian avatars look amazing in papers." *Response:* they can't be skinned in Godot, and their body model has no genitals. They're viewer-only, and we'll revisit later.

**C. Skeptical reviewer**

- "Nothing here has been run on Andrew's PC." *Response:* correct. Every number is a source or community claim, and each phase has an exit test.
- "Community claims are cherry-picked." *Response:* yes, and that's why best-of-N and exit tests are built in. The Codex questions ask for direct evidence.
- "Safety drift: adult LoRAs from mirrors may have been trained on bad data or youthful looks." *Response:* check every LoRA card and sample before use, keep the automatic age check on all outputs (§A8), and prefer our own LoRAs.
- "Real-footage training is tempting." *Response:* it's off by default. If it's ever used, it must be legal, adult-verified, with faces masked, and never used to learn a real identity.

## V.1-5. Questions for Codex (drafts only — the parent posts them to issue #1 after Andrew agrees)

**1.** **Commercial quality bar (Candy.ai premium).** Using the existing evidence account, make 3 adult video clips with fictional adult characters. For each, report in text only:

- resolution, fps, length, audio yes/no;
- generation time;
- visible problems at contact points (warping, extra limbs, flicker).

Attach at most 2 still frames per clip with **no account, payment or personal details visible**. Store them only in a private location, not on the public evidence branch. Also note any model name the site discloses (page text, FAQ or file metadata).

**2.** **Community workflow evidence.** Find the 5 most-used public ComfyUI workflows from the last 90 days for Wan 2.2 image-to-video adult content (Civitai, civarchive, TensorArt or SeaArt pages; links only, no downloads, no log-ins). For each, report:

- page link and date;
- required base model, LoRAs and strengths;
- sampler, steps, CFG and shift;
- resolution and frames;
- whether it uses SVI, FLF2V, SeedVR2 or interpolation.

**3.** **Video-to-3D proof.** Find 3 public demos (repo, video or write-up) where someone took an AI-generated or ordinary video through GVHMR, PromptHMR or SAM 3D Body onto a rigged character in Blender, Unity, Unreal or Godot, ideally with two people touching. For each, report:

- the link and steps used;
- the export format;
- the failures they show, especially hand/foot contact and bodies passing through each other.

## V.1-6. Decisions and purchases for Andrew

- **D1 — Your country.** MiniMax H3's licence excludes users in the US, EU, UK and South Korea. If you live there, we don't use it (still open: Part A §A10 Q5).
- **D2 — Daz route. Chosen 3 Nov 2026.** Golden Palace (female) and Dicktator (male) for Genesis 9, plus Daz Interactive Licences (G9 Starter Essentials IL is about $50; each product needs its own). MPFB2 is the free fallback only, not the path we build first. Nothing has been purchased. Check Renderotica's game-use terms before buying. Do not commit Daz assets.
- **D3 — Optional purchases:**

  - paired animation packs (phantasiagame $10+, Truebones Kama-Sutra $149) to base contact scenes on;
  - R3DS Wrap (paid) for texturing game bodies.

- **D4 — Disk.** Plan 2–4 TB of free SSD space for video models, LoRAs and takes.
- **D5 — Real footage for training.** Default is **no**. Only if you decide otherwise, under the rules in V.1-4 C.
- Unchanged: the game engine gate (Godot first; Unity 6 if the deformation port fails), from §V6.

---

# Part V — Easy Studio 4

## V0. Priority order (Andrew, 3 Nov 2026)

> **Superseded in v4.1:** adult video is now #1, followed by video → 3D (see Part V.1). The list below is the order for everything after that.

1. **Stunning visuals: photorealistic people** with realistic skin (§V2). Under it, **body realism** (§V3) has high priority.
2. **"Me" avatar, phase 1.** A photoreal version of Andrew, built from a video he uploads (§V4).
3. **3D rendering.** Realistic 3D skin, the 3D Me head and game-ready bodies (§V5).
4. **The game:** a Cyberpunk-style strip club scene in Godot 4 (§V6).
5. **Companion chat.** The **lowest priority**, kept small (§V9).
6. **Guided live scan with liveness checks.** This is the **very last phase**. It re-checks the Me identity against a live scan (§V4.10).

## V1. Roadmap v4

| Phase | What | Depends on | Status |
|---|---|---|---|
| **P4 — Photoreal studio** (P4a realism stack + Realism-60, must pass before P5; P4b body realism, may finish alongside P5) | New default realism model (Z-Image), "Realistic skin" preset stack, face/hand/body detailers, SeedVR2 upscaler, grain and lighting presets, realistic video chain (realism LoRA, SeedVR2 video, GIMM-VFI), Realism-60 test set and score page. **Includes body realism (§V3):** body-shape lock, masked outfit change, 18+ anatomy LoRA categories | v3 app | Planned (next) |
| **P5 — Me avatar, phase 1 (2D, upload)** | One owner slot behind the PIN. Upload a face video plus hair and body photos. Frame scoring, coverage report, **face identity LoRA** and **body LoRA** on the photoreal model, plus a Wan 2.2 video LoRA. Fast preview adapter. Outfit changes on Me | P4 | Planned |
| **P6 — 3D realism + Me 3D head + game avatar** | Godot skin and eye shaders (SSS), MPFB2 base bodies with shape morphs, a 3D head from the uploaded video (FLAME/Gaussian route, see §V4.8), head-on-body with facial blendshapes, clothing as separate meshes, nude base under the 18+ gate | P5 | Planned |
| **P7 — Game: strip club vertical slice** | One room in Godot 4: neon club, stage and pole, 3 to 6 NPC dancers from saved characters, the player walking, interaction prompts, in-game screens playing Easy Studio videos | P6 | Planned |
| **P8 — Companion chat (low priority, optional)** | Small local chat with a character's persona and memory, "send me a picture", and optional local voice | P5 (persona) | Low priority; may be skipped |
| **P9 — Guided live scan + liveness (final)** | Face ID-style guided capture with random prompts. Re-checks the existing Me identity, can add a better 3D head scan (iPhone TrueDepth), and locks the slot to the live-verified face | P7 | Planned, last |

The order follows Andrew's list: photoreal studio, then Me in 2D, then the 3D head and game avatar, then the strip club game, and finally the live scan. Chat is optional and sits after everything else except the live-scan check.

## V2. Photorealism workstream (top priority)

**Goal:** pictures of fictional adults (and later, Andrew's Me avatar) that look like photos, not renders. That means real skin texture, believable light, correct hands, and no waxy "AI look".

### V2.1 What we found (late 2026)

**Base models for realistic people**

| Model | Licence | Realism verdict from sources | Role in Easy Studio |
|---|---|---|---|
| **Z-Image Turbo** (6B, Alibaba Tongyi) | Apache-2.0 | Best skin detail per step (pores, freckles, hair), 8 steps, under 16 GB. Testers rate its skin above FLUX.2 dev and Qwen-Image 2512. Weak spots: less variety between seeds, occasional anatomy errors | **New default** for realistic pictures |
| **Z-Image (base, undistilled)** | Apache-2.0 | "A good base for LoRA training"; supports CFG and negative prompts | **Training base** for the Me LoRAs and character LoRAs |
| **Krea 2** (Turbo / Raw, June 2026) | Krea 2 Community Licence: free under $1M yearly revenue, so fine for personal use | The most "shot, not rendered" look, with filmic tone and natural imperfections. Needs 16 GB+ | **Second look:** a "Film" style choice |
| **FLUX.2 klein 4B** | Apache-2.0 | Fastest (4 steps), convincing photo texture, multi-reference edits | **Drafts and previews**, plus the base for the PuLID-Flux2 Me preview |
| **Qwen-Image 2512** (20B) | Apache-2.0 | Best at following prompts and composition, but skin looks plastic without special samplers and skin LoRAs | Optional "compose with Qwen, refine with Z-Image" for complex scenes |
| **Chroma1-HD** (v3 default) | Apache-2.0 | Uncensored; strong but softer skin | **Kept** as the 18+ fallback when Z-Image anatomy isn't good enough (to be tested) |
| SDXL realism fine-tunes (RealVisXL V5, Juggernaut Ragnarok) | OpenRAIL variants | Older but have the largest LoRA/ControlNet ecosystem | Not default. Only for specific LoRAs |

Sources:
- modeltrends.ai photorealism guide
- iimagined.ai "Best ComfyUI models 2026"
- criticatv.com four-model comparison
- diffusiondoodles model rundown
- SpicyAPI Qwen 2512 vs Z-Image test
- N3V3MORE local measurements

Links are in `docs/research/photorealism_notes.md`.

**Upscalers**
- **SeedVR2** (ByteDance, v2.5 ComfyUI nodes) does images and video in one step. It has GGUF, BlockSwap and tiling.
- Testers prefer the **7B "sharp"** model for skin, because the 3B model "has a beauty filter on" and removes pores and freckles.
- **SUPIR** is slower, looks airbrushed, and a ComfyUI update broke it for at least one tester.
- **Decision: SeedVR2 7B sharp is the default upscaler.** The best skin comes from a two-stage chain: SeedVR2 first, then a light detail refine.

**Detailers.** ADetailer-style passes come from the ComfyUI Impact Pack's FaceDetailer. It finds the face or hands, crops, re-draws at higher resolution and pastes back. The "sticker face" look comes from re-drawing too hard without matching colour. Keep the re-draw strength at **0.30–0.45** and always colour-match.

**Skin LoRAs.** A controlled test on Z-Image found:
- Lowering **shift to 2** brings pores back at no cost.
- No checkpoint beat the base model on skin.
- Most "realism" LoRAs change the framing more than the skin, and some *smooth* it.

Dedicated texture LoRAs exist: ProSkin (Z-Image, 0.5–0.75), Skin Detail Slider (Z-Image and Krea 2, refiner pass), PhotorealTouch (versions for Z-Image, SDXL, Pony, Illustrious and Flux) and Flux "Detailed Skin & Textures" v3 (0.5–0.8). The shared advice: **use one at a time, never stack two strong detail LoRAs.**

**Realistic video**
1. Start from a photoreal still: realism mostly comes from the first frame.
2. Wan 2.2 I2V 14B.
3. Optionally a Wan 2.2 realism LoRA (for example "Instareal", high- and low-noise parts, strength 0.8–1.2; check Civitai gating).
4. Use speed LoRAs (Lightx2v) only for drafts, because they flatten texture.
5. Optionally a Wan face-detailer pass.
6. **SeedVR2 video upscale** with uniform batches, temporal overlap and colour correction, which stops flicker between batches.
7. **GIMM-VFI** frame interpolation, 16 → 32 fps. It is better than RIFE but slower, so use RIFE for previews.
8. Grain added last, the same on every frame.

### V2.2 The "Realistic skin" preset stack (new default for realistic pictures)

| Step | Node(s) | Settings (starting point, to tune on Realism-60) |
|---|---|---|
| 1. Base picture | Z-Image Turbo + ModelSamplingAuraFlow | 8–9 steps, **shift 2**, CFG 1. 1024×1536 portrait or 1536×1024 landscape |
| 1a. Skin words (automatic) | Prompt builder | Adds "natural skin texture, visible pores, fine vellus hair, subtle imperfections, unretouched" unless the user picks "Glam / retouched" |
| 2. Optional skin LoRA | LoRA loader | **Off by default.** "Close-up" adds one Z-Image skin LoRA at 0.5. At most **one** skin LoRA |
| 3. Face pass | FaceDetailer (YOLO face + SAM mask) | Crop 1024, re-draw **0.35**, same model and LoRAs, colour match on |
| 4. Hands pass | FaceDetailer with a hand detector | Re-draw 0.40. Runs only if hands are found |
| 5. Body skin pass (full-body only) | Person-segment detailer | Re-draw 0.25 at 1.5× crop. Evens out skin texture between face and body |
| 6. Upscale | SeedVR2 7B sharp | 2× (short side 2048), colour correction on |
| 7. Finish | Easy Studio "Film finish" (pixel step, no model) | Luminance grain 2–3 %, very light vignette, optional halation for neon. Off for "Clean" |

**Presets the user sees:** ✨ Realistic (default), 🎞️ Film (Krea 2 base, more grain), 💄 Glam (no imperfections words, gentler detailers), ⚡ Draft (FLUX.2 klein, no upscale).
**Light chips:** softbox studio, window light, golden hour, hard noon sun, overcast, neon rim (cyberpunk), club stage spot, candlelight.
**Lens chips:** phone snapshot, 35 mm, 50 mm, 85 mm portrait, shallow depth of field.

### V2.3 ComfyUI workflow outline (realistic still)

```
Z-Image Turbo loader ─ ModelSamplingAuraFlow(shift=2) ─ [optional skin LoRA] ─ KSampler(8–9 steps) ─ VAE decode
  └─ FaceDetailer(face, denoise .35) ─ FaceDetailer(hands, .40) ─ [full-body: person detailer .25]
     └─ SeedVR2 (7B sharp, 2×, colour fix) ─ Film finish (grain, vignette) ─ Age check ─ Save + sidecar
```

**Realistic video**

```
Realistic still ─ Wan 2.2 I2V (high + low noise, optional realism LoRA, optional character/Me LoRA)
  └─ [optional Wan face detailer] ─ SeedVR2 video (2×, temporal overlap) ─ GIMM-VFI (16→32 fps) ─ grain ─ age check ─ MP4
```

### V2.4 Quality targets and the Realism-60 test set

**Realism-60** is a fixed list of 60 prompts, each run on 2 fixed seeds, all fictional adults aged 21–55. Planned file: `tests/realism/realism60.json`.
- 24 portraits: 8 skin tones × 3 lights (hard sun, softbox, neon).
- 12 half-body clothed: casual, lingerie, swimwear, yoga, club outfit.
- 8 full-body: standing, walking, sitting, pole pose.
- 8 hand shots: glass, hand on face, phone, folded hands.
- 4 groups of two or three people.
- 4 gated 18+ prompts, kept in a separate folder.

| Target | How it's measured | Pass mark (P4) |
|---|---|---|
| **Looks real** | Blind "photo or AI?" test. Andrew sees 30 Realism-60 pictures mixed with 30 licensed stock photos of adults (a yardstick only, kept in `tests/realism/reference/`, never used for training, the galleries or the Me slot), in random order | ≥ **35 %** of generated pictures judged "photo". 50 % would mean he can't tell at all |
| **Rated realism** | Andrew scores each of the 120 pictures 1–5 | Median ≥ **4**, no category median below 3 |
| **Skin is textured, not plastic or crunchy** | High-frequency energy on a cheek patch at 100 % crop (Laplacian variance inside a skin mask), compared with the stock photos | Inside the stock photos' middle range (25th–75th percentile) for ≥ 80 % of portraits |
| **Image quality score** | No-reference IQA (CLIP-IQA+ and MUSIQ via `pyiqa`) | ≥ 10 % better than the v3 Chroma baseline on the same prompts |
| **Hands** | Finger count and shape, checked by hand on the 8 hand prompts × 2 seeds | ≤ 2 bad hands out of 16 |
| **No sticker faces** | Visible seam or colour step around the face at 100 % zoom | 0 in 60 |
| **Safety intact** | Age check on all outputs. Adult prompts must not be blurred as "under 21" (false alarms) | 0 missed blocks; false alarms ≤ 2 in 120 |
| **Video realism** | 10 Realism-60 stills turned into 5 s clips: ArcFace similarity, first vs last frame; flicker (mean frame-to-frame warp error) | Similarity ≥ 0.60; flicker no worse than plain Wan 2.2 output; Andrew rates ≥ 4 on 7 of 10 |
| **Speed** (estimates, to be measured on the RTX PRO 6000) | Wall clock | Realistic still with the full stack ≤ 45 s; 5 s 720p clip with upscale and interpolation ≤ 6 min |

**Score page:** a planned "Realism report" in Advanced runs Realism-60 and shows the numbers above next to the last run, so changes to models or settings can be judged by numbers, not by feel.

## V3. Body realism workstream (high priority, part of P4/P5)

**Problem:** when the Me avatar (or a saved character) changes shirts, the waist, arms, chest and skin must stay *the same body* and look real. Most "change outfit" tools re-draw the body each time, so the body drifts: arms get thinner, the chest changes, skin tone shifts.

### V3.1 The one recommendation: **body card + body LoRA + masked outfit edit**

Three parts that always work together:

1. **Body card (shape numbers).**
   - For Me, **SAM 3D Body** (Meta, open source) reads each body photo and estimates a 3D body.
   - Its shape numbers (45 MHR shape values, convertible to SMPL-X "betas") are averaged over all photos and saved as the *body card*.
   - For fictional characters, the body card comes from the creator's body sliders, or is estimated from the hero full-body picture.
   - The same numbers later drive the 3D body (§V3.4). That is how image and 3D stay matched.
2. **Body LoRA (skin and look).**
   - A small LoRA trained on Andrew's body photos and video frames, **kept separate from the face LoRA**.
   - Faces in those photos are greyed out or loss-masked, so the body LoRA learns skin tone, body hair, moles, tattoos and build, not the face.
   - Both LoRAs live in the PIN-locked Me slot.
   - For fictional characters, their normal character LoRA plays this role.
3. **Masked outfit edit (the change itself).** To change clothes on an existing picture:
   - **Segment** the old clothing and any skin the new outfit will show. Face, hands and background are **never** in the mask.
   - **Pose and depth:** SAM 3D Body estimates the pose in *this* picture. Easy Studio poses the stored body card that way and renders a **depth map and pose skeleton**. Those guide the re-draw (Z-Image Fun Union ControlNet: depth + pose), so the new outfit is drawn **on the stored body shape**, not a guessed one. (*Verify in P4:* the SAM 3D Body licence and Z-Image base support for this ControlNet. Fallback: SMPL-X from Multi-HMR plus an SDXL or FLUX depth ControlNet.)
   - **Re-draw only the mask** with the photoreal model plus the Me face LoRA and body LoRA, then a body-skin detailer pass and SeedVR2.
   - Result: the outfit changes, but the shoulders, waist and arms keep the stored shape, and skin texture comes from the body LoRA. A "shape check" compares the new picture's estimated body with the body card and warns when it drifts (target below).

**Why this and not try-on alone:**
- Try-on models (IDM-VTON, CatVTON, Leffa, FitDiT, OOTDiffusion) keep whatever body is in the picture. But they **don't know Andrew's real body** when skin that was covered becomes visible: short sleeves, crop tops, open shirts.
- Most are licensed CC BY-NC-SA. That is fine for personal use, but they are SDXL-era quality.
- The body card + body LoRA route keeps identity *and* shape across many outfits and poses, and reuses the LoRAs we train anyway for video.

### V3.2 Fallbacks (in order)

| When | Use | Notes |
|---|---|---|
| A **specific garment photo** must be copied exactly (logo, print) | **Virtual try-on**, then a body-skin pass with the body LoRA at low re-draw (0.25) | FASHN VTON v1.5 (Apache-2.0, about 8 GB, no mask needed) first; CatVTON or Leffa as alternatives (non-commercial or unclear terms, fine for personal use). FitVTON (FLUX.1 Kontext) scores best on body-shape fit in its own benchmark (3.08 vs CatVTON 2.30 out of 5), but check its weights and licence first |
| A quick text change ("make the shirt red linen") | **Qwen-Image-Edit-2511** (v3's editor), then a Z-Image low re-draw pass (0.25) with the Me LoRAs on skin areas | Qwen keeps the layout well; the second pass puts Andrew's real skin texture back |
| Several references at once (garment + pose + Me) | **FLUX.2 klein** multi-reference edit, plus a PuLID-Flux2 face preview | Draft quality; for previews |
| Body LoRA not trained yet | Body card only (depth + pose guidance) | Shape holds; skin is generic |

### V3.3 Video, 3D and Godot: keeping the same body everywhere

- **Video:** always start Wan 2.2 from a still that already has the right outfit and body. A Wan 2.2 Me LoRA (low-noise expert, trained on face and body frames) keeps the person consistent while moving. Body shape is checked on 3 frames per clip with SAM 3D Body against the body card.
- **3D:** the body card numbers are fitted to **MPFB2** (MakeHuman for Blender, CC0 bodies) shape sliders (§V3.4). Outfits are separate meshes on the same skeleton.
- **Godot:** the same MPFB body and skeleton are exported. Godot swaps outfit meshes on the one body, so the strip club NPCs and the Me avatar can change clothes at runtime.

### V3.4 3D side: morphs, clothes and nude bodies

- **One base body for everyone:**
  - MPFB2 gives one topology with shape sliders, a game rig compatible with Mixamo, and a CC0 clothes library.
  - A planned fitting script finds the MPFB slider values that best match each body card. Characters made in Easy Studio get a body card from their creator sliders.
- **Skin:**
  - Use the HumanShaders skin shader (SSS, plus eye and eye-wetness shaders) with a tiled pore detail normal map.
  - Albedo comes from MPFB skin presets, tinted to the character's skin tone sampled from the hero picture.
  - For Me, add a texture projected from the body photos (planned, experimental).
- **Clothes:**
  - Use separate skinned meshes from the MPFB library, or modelled in Blender. The body's hidden faces are deleted under tight clothes to stop poke-through.
  - Loose parts (skirts, hair) move with Godot's bone-based spring physics (SpringBoneSimulator3D, Godot 4.4+). Soft-body cloth is too slow for several dancers and is avoided.
- **Nudity (18+ build only):**
  - The base body *is* the unclothed mesh.
  - Optional anatomy detail meshes and textures sit in an 18+ asset folder, used only in the gated area and in the **18+ export preset**.
  - The licences of community anatomy assets must be checked before use (open question V-Q9).

### V3.5 Adult anatomy in the 18+ section and game

**Approach.**
- Rely first on base models that already draw adult anatomy well: **Chroma1-HD** (uncensored) and Z-Image (to be tested in the 18+ part of Realism-60).
- Add **optional anatomy LoRAs** only where a base model is weak.
- They are organised in the LoRA library **under the 18+ gate** with body-part categories:
  - upper body / chest;
  - breasts;
  - buttocks;
  - genitals (female);
  - genitals (male);
  - body hair;
  - skin detail (adult).

**Rules for these LoRAs**
- Each LoRA is tagged with its base model. The library hides LoRAs that don't match the chosen model (v3 base detection).
- Each LoRA has a **strength slider**, default 0.6, maximum 1.0. **At most one LoRA per category.**
- These categories can **only be loaded in a job that comes from the 18+ area**. The server checks this, not just the page.
- Every existing v3 LoRA rule still applies: blocks on minors, real people, celebrities and age sliders, plus Civitai gating.
- New block: anatomy LoRAs whose name, tags or trigger words include youthful terms.
- An 18+ **body-part detailer** uses a nudity part detector (a NudeNet-style detector) to place a low re-draw (0.30) detail pass on those areas. It runs before the age check, and **every output is still age-checked**.
- **Me avatar:** Andrew's own body LoRA is his own likeness. He may use it in the 18+ area for himself. It can never be applied to an NPC (§V4.6).

### V3.6 Body quality targets and test (Body-20)

**Body-20:** 5 outfits × 4 poses for one fictional test character and, later, for Me.

| Target | Measure | Pass mark |
|---|---|---|
| Shape stays the same | SAM 3D Body shape values of each output vs the body card (normalised distance) | ≤ 0.15 on ≥ 18 of 20 |
| Skin tone stays the same | Mean Lab colour of a forearm patch vs the reference | ΔE ≤ 5 on ≥ 18 of 20 |
| No seam where clothes were changed | Manual check at 100 % zoom | 0 visible seams |
| Andrew's "same body?" rating | 1–5 | Median ≥ 4 |

## V4. "Me" avatar: a photoreal Andrew (P5, then P6 and P9)

### V4.1 Rule change (narrow exception)

v3 rule: *never train on photos of real people, including yourself.*

v4 rule: the same, with **one exception: the owner's own "Me" slot.**
- Andrew is the only real person who can appear in Easy Studio, and only through that slot.
- Everything else stays as it was:
  - all NPCs and characters are generated fictional adults aged 21+;
  - no other real faces;
  - no celebrity or performer look-alikes;
  - the age check stays on.

> **Honest note:** until the live scan (P9) exists, Easy Studio **cannot prove** an uploaded video shows the owner. Phase 1 relies on Andrew's attestation, the PIN and the one-slot limit (§V4.6, §V4.11).

### V4.2 Phase 1 flow (upload-based)

1. **Open Me.** This needs the PIN. Read and tick the attestation: *"This video shows me, the owner of this Easy Studio. I am 21 or older. I won't upload anyone else."*
2. **Upload one face video:** a close-up, turning slowly, 60–90 s. Optionally add hair photos (any angle, including other hairstyles) and body photos (front, side, back).
3. **Easy Studio checks and scores** the upload (§V4.4) and shows a **coverage report**, for example:
   - "Left profile: only 3 good frames, need 8. Turn further left, slowly."
   - "Too dark under the chin."
   - "No smiling frames."
4. **Build the dataset:** 30–40 best face frames, 15–30 body images and the hair photos, with automatic captions. Andrew can untick any frame.
5. **Train** (runs overnight-style, with honest progress, as in v3):
   - face identity LoRA;
   - body LoRA;
   - Wan 2.2 video LoRA.
6. **Fast preview while training:** an identity adapter (PuLID-Flux2 on FLUX.2 klein) shows "rough Me" pictures within minutes. They are labelled *Preview, not trained*.
7. **Use Me** in Pictures, Video, Outfit change and the 18+ area: pick "Me" as the person. Hairstyle and body sliders are editable (§V4.5).

### V4.3 Capture guidance (shown in the app before upload)

**Camera**
- iPhone **rear 1× camera**, 4K at 30 fps. Front camera is fine if a helper isn't available.
- Lock focus and exposure (long press, "AE/AF lock").
- Hold the camera at eye level, 50–70 cm from the face.

**Light**
- Soft and even: daylight from a window in front, or two lamps at 45°.
- No hard overhead light, no mixed coloured light, no backlight.

**Look**
- No glasses, hat or heavy make-up. Hair off the face for one pass, then natural.
- Neutral background.

**Motion (about 75 s)**
1. Face the camera.
2. Turn slowly to the left until your ear faces the camera, back, then the same to the right (about 90°).
3. Look up and down (about 30°).
4. Repeat while talking, smiling, then serious.
5. Blink normally.
6. Finish with a slow 360° turn showing the back of the head.

**Body photos (optional, for the body LoRA)**
- Front, side and back standing, arms relaxed and arms out; 10–20 photos.
- Fitted clothes, underwear or swimwear, or unclothed (Andrew's choice; all stays encrypted in the Me slot).
- Same soft light, full body in frame.

**Hair photos (optional):** any angle. They teach the hairstyle separately, so the hairstyle can be changed later.

### V4.4 Frame scoring and dataset selection

| Check | How | Used for |
|---|---|---|
| Sharpness | Laplacian variance on the face crop; motion-blur rejection | Drop blurry frames |
| Head angle | Head-pose estimate (yaw/pitch/roll) into bins: front, ¾ left/right, profile left/right, up, down, back | Coverage report; balanced pick |
| Exposure and light | Face histogram (clipped highlights/shadows), left–right brightness balance | Drop bad frames; tips |
| Expression | Facial landmark clusters: neutral, smile, talking, eyes closed | Make sure 3+ expressions are present |
| Same person | ArcFace embedding of every frame vs the median of the clip | Drop frames of anyone else; flag the upload if the clip contains two people |
| Near duplicates | ArcFace and picture similarity | Keep variety |
| Age | v3 age check | Must read as 21+ |

**Selection:**
- Extract at 2–4 fps.
- Pick **30–40 frames balanced across angle bins**, roughly:
  - 30 % front;
  - 40 % ¾;
  - 20 % profile;
  - 10 % up/down.
- Expressions are mixed.
- Crops are **full head plus neck and top of shoulders**. That helps the model put the head on a body naturally (§V4.7).

**Hair and body photos:**
- Every face found in them is compared with the owner's face embedding.
- Faces that **don't match are blurred or masked** before training. That keeps other real people out.
- The owner's own face in body photos is greyed out for the *body* LoRA only.

### V4.5 Training and the identity "ladder"

**Identity ladder (what Andrew sees, from fastest to best)**

| Rung | Method | Time (estimate) | Quality |
|---|---|---|---|
| 1. Preview | PuLID-Flux2 adapter on FLUX.2 klein, using 3–5 best frames | Instant | "Looks like a cousin". Good for checking the upload |
| 2. Adapter + LoRA | Trained face LoRA plus a light adapter on the face pass | After training | Best for difficult angles |
| 3. LoRA only | Face LoRA on Z-Image (and Krea 2 if trained), with body LoRA | After training | Most natural; the default |

**What gets trained**

| LoRA | Base | Data | Notes |
|---|---|---|---|
| Me face | Z-Image (base) via ai-toolkit | 30–40 head crops | Guides suggest 20–30 images for a Z-Image character LoRA. Rank 16–32. Caption the trigger "ohwx man" + clothing/background words (not face words) |
| Me body | Z-Image (base) | 15–30 body images, face greyed out | Separate file so outfits and hair can change without breaking the face |
| Me video | Wan 2.2 **low-noise** expert (optionally high-noise too) | 20–30 frames from the video, plus a few short clips | Guides recommend the low-noise expert for identity |

**Hairstyle and body editing**
- Hairstyle is a prompt and hair-photo option ("my usual hair" vs "buzz cut", "long", and so on), with a hair-only inpaint for changes.
- Body edits ("more muscular", "slimmer") change the body card numbers and re-render through the outfit/body path (§V3.1).
- The face LoRA is never retrained for these.

**Licences:** InsightFace models used by face adapters (antelopev2) are non-commercial. That is fine for Andrew's personal use, and stated in the README. InstantID is SDXL-only and not planned.

### V4.6 Safeguards

**Slot rules**
- **One owner identity per install.** Re-enrolling replaces it: the old LoRAs are securely deleted.
- **PIN-locked.** The Me area, its files and every Me job need the PIN to be unlocked in this session.
- **Attestation** is ticked on each enrolment and saved with a date in the local log.

**Storage**
- **Encrypted at rest.** Me LoRAs, frames and embeddings are encrypted with a key derived from the PIN (Argon2id, AES-GCM).
- They are decrypted into memory (`/dev/shm`) only while a Me job runs, then removed.

**Hidden and not exportable**
- The Me LoRAs don't appear in the LoRA library, the zip export or the Godot export.
- They can't be downloaded or shared, and there is no "export Me" button.
- The Godot game can only use Me baked into a character the owner plays (P6 decision; see V-Q4).

**NPCs can never be Me**
- The server rejects the Me LoRAs and the Me embedding in any job not started from the PIN-unlocked Me area.
- Every NPC and character output is also checked with ArcFace against the owner embedding. At similarity ≥ 0.5 the output is blurred and flagged ("This looks like you — NPCs must be fictional").

**Other people kept out**
- Faces in hair and body photos that don't match the owner are masked.
- Uploads where the main face changes partway through are rejected.

**Age and content checks**
- The age check applies to all Me outputs.
- All v3 word and LoRA rules still apply, including the celebrity and real-person blocks for everything else.

**Honest limit:** this protects against mistakes and casual misuse. It is **not** DRM. Someone with admin access to the PC and the PIN can always copy files. That is acceptable for a single-owner personal install, and it is said plainly in the README.

### V4.7 Avoiding the "face-swap look"

The face-swap look happens when a face is pasted onto a body drawn without it. Typical signs:
- a colour or grain step at the jaw;
- a face that is sharper than the neck;
- wrong head size;
- a different light direction.

How Easy Studio avoids it:
1. **Draw the whole person with identity from the start:** the Me LoRAs are in the first picture pass, never pasted in later.
2. Training crops include the **neck and shoulders**, so the model learns how the head sits on the body.
3. The face detailer runs at **low re-draw (0.30–0.40) with the same LoRAs**. The 0.5–0.65 range from face-swap guides applies only to adapter swaps onto a face drawn without identity, which here means only the preview rung, and its colour is matched to the surroundings.
4. **SeedVR2** then unifies the texture over the whole picture, and **grain is added once to the whole image**.
5. A "light check" compares face and neck brightness direction (planned, simple).
6. **Head swap** (Qwen-Image-2.1 + a head-swap LoRA) is kept only as a last-resort tool for fixing a single picture. It is never the main path, and its research licence is noted.

### V4.8 3D head: what works from a casual video vs what needs a guided capture

| Method | Input | Output | Licence / notes | Fits which phase |
|---|---|---|---|---|
| **GTAvatar** (2025–26) | **One normal phone video** | FLAME-rigged head with relightable textured Gaussians; editable textures | Code is research; FLAME and the 3DGS renderer are non-commercial (fine for personal use). Training takes about 1–3 h on one GPU | **P6, from the P5 upload** |
| **PBR-GAvatar** | One normal video | Relightable Gaussian head with PBR materials | Research licence | P6 alternative |
| VHAP / FLAME tracking | One video | FLAME parameters plus a mesh (expressions) | Research | P6: drives blendshapes |
| **LAM** (Large Avatar Model) | **One photo** | Animatable Gaussian head in seconds | Apache-2.0 | P6 quick preview |
| GAGAvatar | One photo | Gaussian head | MIT | P6 quick preview |
| Photogrammetry (RealityScan, KIRI) | **Guided**: 100+ sharp photos all around, still subject | Textured mesh | Needs a helper and a still subject | P9 |
| iPhone TrueDepth scan (Heges, ViewScan) | **Guided** front-camera scan | Mesh plus texture | Short range, good geometry | P9 |
| MetaHuman (Mesh to MetaHuman / Live Link Face depth) | **Guided** iPhone depth capture, or a mesh | Fully rigged, high-quality face and body | Usable in any engine since UE 5.6; free under $1M. **Autorig and texture synthesis run in Epic's cloud, so Andrew's face would leave the PC** (privacy, V-Q6) | P6 experiment only if Andrew agrees; otherwise P9 |

**Getting into Godot**
- **Gaussian heads** look the most real, but Godot 4 has no built-in Gaussian splat renderer. Community plugins exist but are unverified for animated heads. So the plan is to **bake** the result into a normal mesh (FLAME mesh plus textures, albedo/normal/roughness) with **51–52 ARKit-style blendshapes** for expressions.
- That mesh is attached to the MPFB body with a neck blend (shared seam, matched skin tone).
- The MetaHuman route uses the **GoDNA** importer (UE 5.6 MetaHuman to Godot 4.5; 103-bone humanoid, 51 ARKit shapes; beta, paid) or **MetaHumanGodot**.
- P6 includes a **side-by-side test**: GTAvatar-baked mesh vs MetaHuman (only if allowed) vs MPFB head + projected texture. The best one is picked by Me-40 numbers.

### V4.9 Quality targets and the Me-40 test protocol

**Me-40:**
- 40 prompts × 1 fixed seed.
- Angles: 10 front, 10 ¾, 8 profile, 4 up/down, 4 back-of-head/over-shoulder, 4 full-body.
- Lighting: 4 kinds.
- Expressions: 3.
- Includes 8 outfit changes and 4 hairstyle changes.
- Measured against **held-out frames** (frames never used for training).

| Target | Measure | P5 pass mark |
|---|---|---|
| Looks like Andrew | ArcFace similarity vs held-out frames | Median ≥ **0.60**; profiles ≥ **0.50** |
| Andrew's own verdict | Blind "Is it me?" 1–5, mixed with 10 real held-out frames | Median ≥ **4**; real frames picked out as real in fewer than 70 % of cases |
| No face-swap look | Checklist: jaw seam, sharpness step, grain step, light direction, head size | ≤ 2 of 40 fail any item |
| Same body | Body-20 (§V3.6) on Me | As §V3.6 |
| Video identity | Wan 2.2 Me clips: ArcFace similarity per second | No second below 0.50; Andrew ≥ 4 on 4 of 5 clips |
| 3D head (P6) | Renders from 8 angles vs held-out frames (ArcFace), plus Andrew's rating | Median ≥ 0.50 and rated ≥ 3.5. 3D is expected to be weaker than 2D at first |
| NPC lock | 100 NPC pictures checked against the owner embedding | 0 above 0.5 that weren't blurred |

### V4.10 Final phase (P9): guided live scan and liveness re-verify

**What the scan does**
- Guided capture in the browser on the Mac or iPhone. The app asks for **random** moves: "turn left", "blink twice", "smile", "look up".
- Passive anti-spoof checks look for screens and printed photos (for example MiniFASNet in open-face-liveness), plus a depth check where an iPhone TrueDepth capture is available.
- The live scan face is compared with the stored Me identity. If they match, the slot is marked **"Live-verified (date)"**. If not, Me is **locked** until re-enrolment with a live scan.
- The same capture can give a better 3D head (guided TrueDepth/photogrammetry route).

**Honest limits**
- Research from 2026 shows **interactive challenges don't fully stop real-time face-swap or virtual-camera injection**. The scan raises the bar a lot, but it isn't proof.
- On a single-owner personal PC this is a sensible level.

### V4.11 Risks (Me)

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Someone uploads another real person's video as "Me"** (the main misuse scenario) | Possible: anyone with the PIN | Attestation; one slot; PIN; same-face continuity check; NPC lock; P9 live re-verify; README warning that creating sexual images of a real person without consent is illegal in many places |
| PIN shared or guessed | Low | Rate-limited PIN; Me needs a re-entered PIN after 15 min idle |
| Files copied off the PC | Low | Encrypted at rest; but not DRM (stated) |
| Identity looks "almost" right (uncanny) | Medium | Ladder; Me-40 targets; more coverage tips |
| Likeness drifts toward a celebrity look-alike | Low | Celebrity block on prompts and LoRAs; Me outputs are not checked against celebrities (no celebrity face database is kept, by design) |
| Liveness fooled by a virtual camera | Possible for an expert | Stated limit; local-only use |
| Non-commercial model licences (InsightFace, FLAME, 3DGS) | Certain | Personal use only; listed in README |

## V5. 3D realism (P6)

| Area | Plan |
|---|---|
| Renderer | Godot 4.6 **Forward+** (needed for subsurface scattering, volumetric fog and SDFGI) |
| Skin | StandardMaterial3D with **SSS skin mode + transmittance** (ears and fingers glow red against light) as the simple path. The **HumanShaders** add-on (skin, eye, eye wetness; Godot 4.5+) is the quality path. RoboPoets *digital_human* is a reference |
| Skin maps per character | Albedo, normal (+ tiled pore detail normal), roughness, SSS/thickness. Made by tinting MPFB skin sets to the character's tone and adding AI-generated detail (moles, freckles) as a decal layer. TRELLIS.2 PBR output is too low-detail for skin |
| Eyes and hair | HumanShaders eye shader with wetness. Hair as card meshes from the MPFB library, coloured to match the 2D character |
| Lighting | ACES/AgX tonemap, SDFGI or baked lightmaps for the club, volumetric fog for neon haze, glow (bloom) on neon only |
| Me head | Baked GTAvatar mesh (or the V4.8 winner) on the MPFB body, ARKit-style blendshapes, matched skin tone at the neck |
| Measure | **Godot-10:** the same 10 characters as stills vs 3D renders, rated 1–5 by Andrew. Target median ≥ 3.5 at P6 (3D realism is behind 2D; we say so) |

## V6. The game: Cyberpunk-style strip club (P7)

**What it is:**
- A single explorable neon club in Godot 4.
- The player walks around, watches dancers on a stage with a pole, talks to dancers and the bartender, and sees Easy Studio pictures and videos on screens and posters.
- **Every NPC is a fictional adult (21+) made from a saved Easy Studio character.** The Me avatar can be the player's body (P6) and is never an NPC.

### V6.1 Pipeline (character to game)

```
Saved character (look, body card, persona)  →  MPFB2 body (fitted shape) + head (MPFB head tinted, or 3D head route)
   → skin maps + hair + outfits (separate meshes)  →  rig (MPFB game rig, Mixamo-compatible)
   → animations retargeted in Godot (BoneMap + SkeletonProfileHumanoid)  →  .glb into the Godot project
```

| Part | Choice | Why / alternatives |
|---|---|---|
| Base body | **MPFB2** (CC0) for all NPCs | One topology, sliders, game rig, clothes library. Alternatives: generated meshes (TRELLIS.2 / Hunyuan3D) look uneven and are hard to rig, so they're used only for props |
| Rigging | MPFB's built-in rig; **UniRig** / **AccuRIG** / Mixamo auto-rig for odd meshes | Mixamo needs an Adobe login (Andrew's choice) |
| Clothing | Separate skinned meshes; hidden-body masking; spring bones for skirts and hair | §V3.4 |
| Animation sources | (1) Mixamo walk/idle/talk/dance clips. (2) **Video to motion:** a pose-tracking model turns a Wan 2.2 dance clip of a fictional dancer into a 3D motion, then retargets it (experimental, tool to be chosen, e.g. GVHMR-class). (3) Hand-keyed pole moves in Blender. (4) Paid mocap packs | Pole dancing needs specific motion; nothing free covers it well (risk) |
| Faces | 52 ARKit-style blendshapes; idle blinks; talk animation from audio (if voice is used) | |

### V6.2 Scene design (vertical slice)

- **Club:** one room about 20 × 15 m. Entrance, bar, main stage with one pole, two side podiums, booths and a VIP curtain (closed in the slice).
- **Look:** wet dark floor reflections (SSR), neon signs (emissive + glow), volumetric haze, moving stage spotlights, a few big screens.
- **NPCs:** 3–6 dancers chosen from saved characters, plus 1 bartender and a few background patrons with simple idles.
- **Player:**
  - third-person camera by default (V-Q1), WASD/controller, walk/sit;
  - **interaction prompts** ("E: talk", "E: tip", "E: sit") when near;
  - stage dances loop with crossfades.
- **Dialogue:**
  - short conversations using the character's persona, through the small local LLM (§V9), with a hard 21+ fictional rule in the system prompt and the v3 word gates on both input and output;
  - preset lines are the fallback if no LLM is running.
- **18+:** nudity and explicit content appear only in the **18+ build** (export preset), behind the same age and PIN rules. The standard build keeps lingerie and swimwear only.

### V6.3 AI 2D and video content inside the game

- Easy Studio exports a **"Club media pack"**: posters (stills), screen loops (Wan 2.2 clips, upscaled and looped) and neon sign art.
- All are age-checked and from fictional characters, plus Me only if the owner places them.
- In Godot they play as video textures (Theora/OGV) or image textures on screens. A JSON manifest lets the club pick up new media without code changes.

### V6.4 Performance (estimates; to be measured)

| Target | Budget |
|---|---|
| 1440p **60 fps** on RTX PRO 6000 with 6 dancers + 6 patrons | Characters ≤ 60k triangles each with LODs; 4K skin maps for dancers, 2K for patrons; ≤ 8 shadow-casting lights; SDFGI or baked GI; volumetric fog at medium |
| 4K 60 fps | Stretch goal with FSR 2 / temporal upscaling |
| Mac (M5 Max) | Not a target for the game in P7 (Godot Forward+ on Metal works, but untested) |

### V6.5 Phases

1. **P7.1 Vertical slice:** the club room, 3 dancers from saved characters, the player walking, one interaction (talk with preset lines), screens playing club media, 60 fps measured.
2. **P7.2 Content:** 6+ dancers, more dances (video-to-motion test), bar and booth interactions, LLM dialogue.
3. **P7.3 18+ build:** nude bodies and anatomy assets, gated export, all safety tests.
4. **P7.4 Polish:** Me as the player avatar, a photo mode that sends a frame to Easy Studio for a photoreal re-render, sound and music.

### V6.6 Comparables (what to learn)

| Game | Lesson |
|---|---|
| **Cyberpunk 2077** (Lizzie's Bar, Jig-Jig Street) | The look: rain, neon, haze and dense signage sell the setting more than polygons. Short scripted interactions |
| **Virt-A-Mate / VaM 2** (v1.2 beta Aug 2026) | Users value realistic skin, physics and customisation, but complex tools scare people off. Keep Easy Studio's "one big button" ethos |
| **Koikatsu / Honey Select 2** (Illusion) | A character creator with many sliders drives retention; stylized can be more appealing than almost-real |
| **Wild Life** (Unreal) | Realistic adult 3D is very expensive to reach; a narrow scope (one club) is right |

### V6.7 Game risks

- **Uncanny valley.** 3D realism lags far behind 2D, so the photo mode re-render (P7.4) is the escape hatch.
- **Pole dance animation quality** (no good free source).
- Godot has no MetaHuman-class character pipeline; community importers are beta.
- Gaussian splats are unverified in Godot.
- **Scope creep:** keep to one club.
- **LLM dialogue may say unsafe things:** gates on both sides, plus preset fallback lines.

## V7. Codex evidence: map and privacy (summary)

**The full map is in `docs/research/evidence_map.md`.** It has 27 rows covering Codex features F01–F24 plus extras. Each row is marked Adopt, Already have, Adapt, Not copied (deliberate), Not applicable, or Low priority.

**Adopted (small, local):**
- hover previews on character cards
- a per-character Gallery filter
- auto-saved creator drafts and a versions list
- lighting and lens chips (now part of §V2.2)
- model "cards" in the video studio
- ffmpeg montage of clips
- idempotent jobs with an honest "unknown, check the gallery" state
- optional local milestones (no streaks)

**Not copied, on purpose:**
- an "18–21" age chip (the Easy Studio floor stays at 21)
- real-performer or "clone" characters (the only exception is the owner's Me slot, §V4)
- non-consent or age-play presets

**Not applicable (cloud or economy features):** premium tiers, wallet and tokens, shop and gifts, live cams and tipping, hosted Seedream and Seedance models. The local equivalents are §V2 and §V3.

**Conflicts resolved:**
- Chat becomes small and last.
- Local models stay; we close the gap through the photoreal workstream.
- The LoRA stack limit is 4 (Part B corrected).
- "Any model" keeps its honest auto-detect report.
- Progress stays honest; no fake progress bars.

**Privacy:**
- A sanitized copy of the evidence is at `/workspace/evidence/sanitized/EasyStudio-Evidence/` (with `REDACTIONS.md`), plus `EasyStudio-Evidence-sanitized.tgz`. It has:
  - the username path removed
  - account and chat IDs removed
  - nickname, gender, persona name, avatar initial and location fields blacked out
  - browser bookmarks and the password-manager icon blacked out
  - macOS `._` files removed
- **The repo branch `codex/evidence-candy-premium-20261103` still holds the unredacted originals.** Fixing that needs a history rewrite or a branch delete, which needs **Andrew's OK**. Nothing in the repo was changed.

## V8. New research lessons (Nov 2026)

There are **39 new products** in `docs/research/competitors.csv` (212 rows in total), marked "[v4]". The new column `usage_or_traffic` holds traffic figures where they could be found.

**Traffic (Sep 2026; third-party estimates, approximate):**
- **Semrush:** Character.AI 176.5M visits per month, SpicyChat 96.6M, Candy.ai 53.9M, Kindroid 2.8M, Nomi 1.4M, Replika 428K.
- **AlphaMoat:** Janitor AI 132.3M, Candy 62.7M, JOI 27.2M, CrushOn 21.2M, GirlfriendGPT 14.0M, Secrets 6.8M, Muah 862K, DreamGF 315K.
- The two sources disagree on Candy (53.9M vs 62.7M), so treat all figures as rough.

**Lessons:**
1. **Most traffic goes to chat-first products, but our edge is visuals.** The biggest sites are chat sites with weak images. Local photoreal pictures, video, a Me avatar and a game are things none of them offer offline. This supports Andrew's order: photoreal first, chat last.
2. **Local chat is already a solved, popular stack.** SillyTavern, KoboldCpp, LM Studio, Ollama, Open WebUI, oobabooga, Backyard AI and RisuAI exist. If we ever build chat, **reuse** one of these runtimes and don't build a new one (§V9).
3. **Photorealism moved to new, small, open models in 2026.** Z-Image, Krea 2 and FLUX.2 klein beat older large models on skin. Most of the realism gain comes from **settings, detailers and the upscaler**, not more LoRAs.
4. **Identity is a ladder, not one switch.** Adapters (PuLID-Flux2) are instant but approximate; a trained LoRA is better; both together handle hard angles.
5. **3D heads from a phone video are now realistic,** for example GTAvatar and PBR-GAvatar (relightable). Getting them into a game engine still means baking them to a mesh.
6. **MetaHuman is free in any engine but cloud-dependent.** This is a privacy trade-off for a real face.
7. **Liveness can be fooled by real-time face swaps.** Be honest about what the P9 scan proves.
8. **Adult 3D games win on character creators and customization** (Koikatsu, VaM). Raw polygon realism matters less, and the scope should stay small.
9. **Some sites block automated checks:** Chub 403, and SSL failures on two game sites. Their facts come from search results and are marked as such in the CSV.

## V9. Companion chat (lowest priority, optional, P8)

Kept deliberately small:

- **Runtime:** a local LLM through **LM Studio or Ollama**, on the M5 Max or the RTX PC. Easy Studio only talks to its OpenAI-compatible endpoint. There is no cloud and no account.
- **Persona:** the persona comes from the saved character: name, personality and backstory, all fictional and 21+.
- **Memory:** one editable memory file per character.
- **Editing:** regenerate, edit and rewind messages.
- **Pictures:** "Send me a picture" turns the chat context into an Easy Studio picture job with that character's LoRA. The age check and word gates apply.
- **Voice (optional):** **Kokoro** or **Chatterbox** for speech, and **whisper.cpp** for dictation. Andrew's own voice is **not** cloned (V-Q8).
- **Safety:** v3 word gates run on both the user's input and the model's output. The system prompt sets a hard fictional-21+ rule. NPC chats can never use the Me identity.
- **Not included:** relationship levels, streaks, tokens and group chats with age chips.

## V10. Safety changes in v4

| Rule | v3 | v4 |
|---|---|---|
| Training on real photos | Never, including yourself | Never, **except the owner's own PIN-locked Me slot** (§V4.1) |
| Real-person likeness | Blocked | Blocked, except Me used by the owner. **NPCs are checked against the owner embedding** |
| Celebrities and performers | Blocked | Blocked (unchanged) |
| Age floor | 21+ | 21+ (unchanged). The age check also applies to Me, 3D renders and game media |
| 18+ content | Gated area | Gated area **plus** the 18+ anatomy LoRA categories (server-checked) and a separate 18+ Godot export preset |
| Liveness | n/a | Final phase P9. Limits stated |

**The current app (v3 code) still blocks all self-training.** The Me exception applies only once P5 is built.

## V11. Risks (overall)

| Risk | Impact | Mitigation |
|---|---|---|
| Z-Image anatomy or 18+ quality is weaker than Chroma | 18+ realism drops | Keep Chroma as the 18+ fallback; test the 18+ part of Realism-60 first |
| Licences: Krea 2 Community, FLUX.2 dev non-commercial, InsightFace, FLAME and 3DGS non-commercial, VTON CC BY-NC-SA | Fine for personal use, blocks any future sale | List all licences in the README; Apache defaults where possible (Z-Image, klein, FASHN, LAM) |
| Civitai realism and anatomy LoRAs vanish or are gated | Missing presets | The v3 import flow plus local copies; never auto-download gated files |
| Pipeline chains get long and slow | Waiting | Draft preset; honest time estimates; batch at night |
| Uncanny Me (almost but not quite) | Andrew dislikes it | The ladder, coverage tips and Me-40 numbers decide, not opinion |
| Misuse of the Me slot with another person's video | Legal and ethical harm | §V4.6 and §V4.11; P9 live re-verify |
| 3D realism far behind 2D | Disappointing game | Stylized option (V-Q3); photo-mode re-render |
| Too much scope (studio + Me + 3D + game) | Nothing finishes | Strict phase gates: each phase ships with its test set passed before the next starts |
| Repo still holds unsanitized evidence | Privacy leak if the repo is shared | Needs Andrew's OK to rewrite history or delete the branch |

## V12. Open questions for Andrew

1. **V-Q1 Camera:** third person (default proposal, so you see the dancers and your avatar) or first person (more immersive, like Cyberpunk)?
2. **V-Q2 Art style in 3D:** go for full realism (uncanny risk), or "stylized realistic" (slightly painted, like Cyberpunk's characters)?
3. **V-Q3 Realistic vs stylized NPC faces in the game:** if 3D faces fall short of target, may we switch to stylized?
4. **V-Q4 Me in the game:** only as the player avatar, or also in photo-mode stills? (NPC use is never allowed.)
5. **V-Q5 Hair and body photos:** may they include unclothed body photos for the body LoRA? They stay encrypted, and it is your choice.
6. **V-Q6 MetaHuman:** OK to send your face scan to Epic's cloud for auto-rigging, or local-only routes only?
7. **V-Q7 Film look:** use Krea 2 (Community Licence, free under $1M) as the "Film" style?
8. **V-Q8 Voice:** clone your own voice for Me? We propose **no** for now.
9. **V-Q9 Anatomy meshes for the 3D 18+ build:** OK to use community assets after a licence check, or only what we model ourselves?
10. **V-Q10 Paid tools:** OK to buy GoDNA ($7.50) and possibly mocap packs for pole dances?
11. **V-Q11 Repo:** OK to rewrite the history of `codex/evidence-candy-premium-20261103` (or delete it) to remove the unredacted evidence?
12. **V-Q12 Chat:** build P8 at all, or skip it?

The v3 open question Q2 ("train my own clone") is **answered by v4**: allowed only as the owner Me slot (§V4), built in P5.

## V13. Two improvement loops and a pessimistic review

### Loop 1: consistency check of the draft

| Found | Fix made |
|---|---|
| The research notes say face-swap passes need **0.5–0.65** re-draw, but §V2 uses **0.30–0.45**, which looks like a contradiction | Clarified. 0.5–0.65 applies to *adapter face swaps* onto a face drawn without identity. Our main path puts identity in the first pass, so the detailer only refines (0.30–0.45). The higher range is kept only for the preview ladder rung |
| The "photo or AI?" test uses stock photos of real people | Stated that they are a **yardstick only**: kept in `tests/realism/reference/`, never added to training, galleries or the Me slot |
| SAM 3D Body and the Z-Image ControlNet ("Fun Union") were treated as certain | Both are now marked **"verify licence and Z-Image base support in P4"**. The fallback is SMPL-X from Multi-HMR plus an SDXL or FLUX depth ControlNet |
| Body realism was not clearly placed in a phase | Body card and masked outfit edit go in **P4**. The Me body LoRA goes in **P5** with the face LoRA |
| The v3 open question Q2 ("clone") conflicted with v4 | Answered in V12 and §V4.1; the v3 text is marked superseded |
| Part B said 3 stacked LoRAs, Part A said 4 | Part B corrected to 4 |

### Loop 2: simplify for a non-developer owner

| Found | Fix made |
|---|---|
| Too many knobs (light, lens, grain, skin LoRA, detailers) | Four visible presets (Realistic, Film, Glam, Draft). Everything else lives under "More options" |
| Me enrolment could feel like a lab procedure | One upload screen, a coverage report written in sentences ("turn further left"), and a preview within minutes |
| P4 blocked P5 entirely | P4 is split. **P4a** (realism stack + Realism-60) must pass before P5. **P4b** (body realism) can finish alongside P5, because the Me body LoRA needs the outfit path anyway |
| Game phase lists were long | P7.1 vertical slice defined in one line: one room, three dancers, walk, talk, screens, 60 fps |

### Pessimistic review (what will probably go wrong)

1. **A 75-second video in one room means Me will look best in that room's light.** Different lighting (neon, hard sun) may lose likeness. *Response:* coverage tips ask for two lighting setups; Me-40 tests 4 lighting setups; the adapter rung helps; and we're honest if neon Me scores lower.
2. **Andrew judging his own face is biased.** People are oddly critical of their own likeness. *Response:* ArcFace numbers sit next to his rating, and held-out real frames are mixed in to calibrate.
3. **Community ComfyUI nodes break on updates.** One tester's SUPIR broke this way. *Response:* pin node versions per preset, add a "known good" snapshot, and include the Realism-60 smoke run after updates.
4. **The 3D head will look gamier than the 2D pictures.** Baking Gaussians into a mesh loses much of their realism. *Response:* say so up front (target 3.5 vs 4), add the photo-mode re-render, and keep a stylized option.
5. **The pole dance has no good animation source.** *Response:* video-to-motion is an experiment; paid mocap is a question for Andrew (V-Q10); simple podium dances from Mixamo serve the slice.
6. **Z-Image may be weaker than Chroma for 18+ anatomy.** *Response:* Chroma stays, and anatomy LoRAs are per base model.
7. **The Realism-60 "35 % judged photo" target may be too easy or too hard.** *Response:* it's a first guess, re-set after the first baseline run, and recorded with the date.
8. **Scope.** Five phases before chat is a lot of work for a personal project. *Response:* strict phase gates; each phase is usable on its own.
9. **Safety drift.** New features (Me, anatomy LoRAs, game dialogue) add new ways around the rules. *Response:* server-side checks rather than UI-only, the NPC-vs-owner face check, gates on LLM output, and a safety test list per phase (extending v3's tests).
10. **The liveness scan won't stop a determined expert.** *Response:* this is stated plainly, and it's acceptable for a single-owner home install.

**Outcome:** v4 is a plan. Nothing here is proven until each phase's test set passes on Andrew's PC.

## V14. Sources

Full links are in `docs/research/photorealism_notes.md` and in `docs/research/competitors.csv` (the url and source columns). The main sources:
- **Models and settings:** model and photorealism guides on modeltrends.ai, iimagined.ai, criticatv.com and diffusiondoodles; the SpicyAPI Qwen-vs-Z-Image test; the N3V3MORE Z-Image skin test.
- **Upscaling and video:** the SeedVR2 nodes (numz/ComfyUI-SeedVR2_VideoUpscaler), GIMM-VFI nodes and Impact Pack.
- **Identity and 3D heads:** PuLID-Flux2 node, GTAvatar (arXiv), PBR-GAvatar, LAM (aigc3d), GAGAvatar.
- **MetaHuman and Godot:** MetaHuman licence and Mesh-to-MetaHuman docs; GoDNA; MetaHumanGodot; HumanShaders; RoboPoets digital_human; Godot 4.6 docs (spatial shader SSS, volumetric fog, skeleton retargeting); the MPFB2 Mixamo docs.
- **Body:** SAM 3D Body (Meta), FASHN VTON 1.5, Leffa, CatVTON, IDM-VTON, FitDiT, OOTDiffusion, FitVTON.
- **Liveness:** open-face-liveness, face-liveness-check, arXiv 2610.16417.
- **Traffic:** Semrush and AlphaMoat (Sep 2026).

---

# Part A — Easy Studio 3

## A1. What Andrew asked for (v3 brief)
- The youngest age is **21**. Lingerie, bikinis, swimwear and yoga clothes are allowed. Cut false blocks without weakening the real ones.
- **Personal use only**, no selling. Licence notes are relaxed to non-commercial; territory limits are still listed.
- **Pick a game engine.**
- **Train my character**, so one character looks the same in every picture and video.
- A **video tool that works with any model**.
- **Intuitive LoRA support.**
- A separate **18+ section** for adult content.
- More site research, with Candy.ai as the main reference.

## A2. Hard limits (unchanged, and they apply inside the 18+ section too)
1. Fictional **adults only (21+)**. Anything describing minors is refused.
2. **No real people.** No face-swap, deepfake, celebrity or "looks like <name>", and no LoRAs of real people.
3. **Training never uses photos of real people, and that includes Andrew himself.** See A4.
4. The adult-only README note stays.

## A3. Game engine pick: **Godot 4**
**Decision: Godot 4** (4.3 or newer). The runner-up is Ren'Py.

| Need | Godot 4 | Ren'Py | Unity | Unreal |
|---|---|---|---|---|
| Licence for a private adult game | **MIT, no fees, no content rules, no account** | MIT-style | Proprietary, needs an account | Proprietary, royalty rules |
| Uses Easy Studio's assets as they are | **.glb 3D, PNG sprite frames → SpriteFrames, .ogv video in VideoStreamPlayer** | PNG and video only, no 3D | Yes, needs importers | Yes, heavy |
| 2D visual-novel style *and* 3D scenes | **Both** | 2D/VN only | Both | 3D-first |
| Runs on the RTX PC and the M5 Max Mac | **Yes (native Apple Silicon)** | Yes | Yes | Heavy on Mac |
| Size and learning curve for a non-developer | **About 100 MB, one app, GDScript is beginner-friendly** | Easiest (script-like) | Large | Very large |
| Works offline and stays private | **Yes** | Yes | Account login | Account login |

**Why Godot over Ren'Py:**
- Ren'Py is easier for a pure visual novel, but it can't use the 3D models Easy Studio makes.
- Godot handles both a VN-style game and a 3D game, so you don't have to switch engines later.

**Why not Unity or Unreal:** both are proprietary, need an account, are heavy, and have adult-content and store rules
that are irrelevant to a private game but still friction.

**What Easy Studio does for it:**
- An **"Export to Godot 4"** card in Game assets builds a ready Godot project folder (a zip). It contains:
  - `project.godot`;
  - portraits and ⭐ favourites;
  - sprite sheets cut into frames, each with a SpriteFrames `.tres` for AnimatedSprite2D;
  - `.glb` models;
  - videos converted to `.ogv` (Theora), which Godot plays natively;
  - a README for the folder.
- There is an `export_presets.cfg` with desktop presets (Linux, Windows, macOS). Godot's export templates are a
  one-time download inside Godot.
- Items flagged by the age check are never exported.

## A4. Train my character (the next phase, now built)
**What it does:** teaches the image models (and optionally Wan 2.2 video) one saved character, so her face and body
stay the same in new outfits, places and poses.

**Flow:**
1. **Pick a saved character.**
2. **Make training pictures.** Easy Studio uses Qwen-Image-Edit to make 12–24 varied shots from her portrait (angles,
   close-ups, full body, expressions, outfits, places, light). Each shot gets an automatic caption that names only
   what changes, plus a unique trigger word built from her name.
3. **Untick any shots that drift.**
4. **Choose what the LoRA is for:**
   - realistic (Chroma1-HD);
   - fast (Z-Image Turbo);
   - anime (NoobAI-XL);
   - video (Wan 2.2 14B; training produces a high-noise and low-noise pair).
5. **Train.** It runs on the RTX PRO 6000 with **ai-toolkit (MIT)**, installed once with `install_trainer.sh/.bat`.
   ComfyUI frees its VRAM while training. Progress shows in the job panel, and you can stop it at any time.

**The result:**
- The LoRA lands in ComfyUI's LoRA folder (`loras/easy_studio/`), with her portrait as the thumbnail, the trigger word
  and the base model already filled in.
- It can be picked in **every** Advanced drawer: pictures, edits, video and the Video studio.
- The trigger word is added to the prompt automatically.
- For video, the right half of the pair goes onto the matching Wan model.

**The deliberate limit:**
- Training sources are limited to:
  - characters created in the app;
  - Andrew's **own drawn or 3D-rendered fictional art**, uploaded as "My fictional character" with its confirmation tick.
- **Training never uses photos of real people, including Andrew himself.**
- Andrew asked to be able to "train your own clone". **We chose not to build that.** A LoRA of a real person can make
  nude pictures of that person, and the app can't verify who is in a photo or whether they agreed.
- The README states the same.

**How the limit is enforced (server side, not just the UI):**
- Every training picture must:
  - be an image of *this* character, either made by Easy Studio or a confirmed own-art upload;
  - pass the age check.
- Training requires the age check to be installed and switched on.
- Every picture is age-checked **again** right before training. One flag stops the run.
- Only one training job runs at a time.
- Clothing, object, background and pose uploads are refused.

## A5. Video studio (any model)
- **Model picker cards:** ready / not installed (with the missing file names), mode, frame rate and maximum length.
- **Modes:**
  - text → video;
  - picture → video;
  - **A → B** (start + end picture);
  - **extend** a video (continues from its last frame).
- **Built-in models:**

| Model | Modes | fps | Max | Group (download) | Licence |
|---|---|---|---|---|---|
| Wan 2.2 14B | picture→video, A→B | 16 | 10 s | `video` (default) | Apache-2.0 |
| Wan 2.2 14B | text→video | 16 | 10 s | `video-t2v` (optional, 38 GB) | Apache-2.0 |
| Wan 2.2 5B | text→video, picture→video | 24 | 5 s | `video-wan5b` (optional, 18 GB) | Apache-2.0 |
| LTX-2.5 (with sound) | text→video, picture→video, A→B | 24 | 10 s | `video-ltx` (optional, 40 GB, HF login) | LTX-2 Community |
| HunyuanVideo 1.5 720p | text→video, picture→video | 24 | 5 s | `video-hunyuan` (optional, 46 GB) | Tencent (not EU/UK/KR) |
| Kandinsky 5 Lite | text→video, picture→video | 24 | 5 s | `video-kandinsky` (optional, 19 GB) | MIT |

- **Bring your own workflow:**
  - Import any ComfyUI video workflow (normal UI format or API format; it's converted using ComfyUI's live node list).
  - Easy Studio **auto-detects** the prompt, negative, start/end image, length, size, seed, fps and "fast" switch
    nodes, and works out the mode.
  - The workflow is safety-scanned: no face-swap / IP-Adapter-FaceID / ReActor nodes, and every text is checked.
  - It then appears as a model card.
- **Frame rules are handled for you.** Wan needs 4n+1 frames and LTX needs 8n+1. Sizes are snapped to multiples of 16.
- **All six video models run through the same Video studio form.** LoRAs work there too, and the right Wan half is
  picked automatically.
- The **motion chips** add 18+ motions inside the 18+ section.

## A6. LoRA library
- **Add LoRAs** by drag-and-drop (.safetensors only, up to 4 GB) or by **pasting a Civitai link**. Both need a tick:
  "not a real person, not a child".
- **Civitai import** shows the name, base model, size, trigger words and preview. It **respects gating**:
  - early-access and gated files need your own Civitai API key, which is used for that one request and **never
    stored**;
  - LoRAs that Civitai marks NSFW can only be added from inside the 18+ section, and their previews are hidden
    outside it.
- **Each LoRA card** shows:
  - a thumbnail (`<name>.preview.png`, the same convention as Civitai Helper);
  - the base model, **detected from the file's layers**: SDXL/Pony/Illustrious, Flux/Chroma, Z-Image, Qwen-Image, Wan
    14B/5B, LTX-2, HunyuanVideo or Kandinsky 5;
  - the trigger words (read from the file, editable);
  - the default strength (−1 to 2);
  - remove (it goes to `_trash`).
- **Using LoRAs:**
  - stack up to 4 in any Advanced drawer, in the image *and* video tabs;
  - names show as titles with their base model;
  - trigger words are added to the prompt automatically;
  - a LoRA for the wrong base model is refused with a plain message, instead of failing silently.
- **Blocked:**
  - LoRAs whose name, title, trigger words or embedded metadata point to minors ("loli", "teen", "schoolgirl"…);
  - **real people or celebrities** (likeness words, "celeb", a list of about 120 famous names in
    `app/celebrity_names.txt`, and Civitai's *person of interest* flag);
  - LoRAs of yourself ("my_face", "myself"…) and **age sliders**;
  - full models disguised as LoRAs.
  - Blocked LoRAs show a 🚫 reason and can't be used.
- **Known gap:** a real-person LoRA named *only* with the person's name (for example "jane_doe_v2") can't be recognised
  from the file. The tick box and this note are the mitigation (open question Q3).

## A7. 🔞 18+ section
- **Gate:**
  - **once per device**: two ticks, "I'm 18+ and adult content is legal for me" and "I understand the rules still
    apply";
  - this is remembered with a 1-year HttpOnly cookie, and the server stores only its hash;
  - an **optional PIN** (4–8 digits, PBKDF2-hashed) is then asked every 12 hours;
  - 5 wrong PINs lock it for 5 minutes;
  - **Lock** ends the session.
- **A separate area:**
  - it has **its own gallery**;
  - 18+ items, jobs, files, thumbnails and LoRAs are invisible (404) to anything outside the section, enforced by the
    server, and that includes direct file links;
  - the normal gallery never shows them;
  - inside the 18+ section you can still use normal-area pictures and characters as starting points.
- **Allowed:** explicit nudity and sex between **fictional adult characters (21+)**.
- **Own presets:**
  - 18+ outfit categories (lingerie, nude…);
  - 18+ photoshoot packs;
  - 18+ poses;
  - 18+ video motions.
- **Normal area:**
  - explicit words are refused with "use the 18+ section";
  - a nudity negative is added, so normal-area results stay non-explicit.
- **Every safety rule still applies:**
  - the minor and real-person word rules (including look-alike letters and named celebrities);
  - extra 18+-only blocks for themes that code an adult as a child (school uniforms, classroom, step-family,
    "innocent"…);
  - the age check;
  - the no-face-swap rule.

## A8. Automatic age check (on by default)
- **Every new picture and video is checked:**
  - YuNet finds the faces;
  - a SigLIP2 age classifier scores each face;
  - videos are checked on 3 frames.
- **If any face may look under 21:**
  - the result is **blurred in place**;
  - it gets a "⚠️ Hidden: may look under 21" badge;
  - it can't be used as a source, exported or trained on;
  - flagged uploads are refused.
- **Switching it off:** possible in ⚙️ Setup, with a typed confirmation. Training stops working while it is off.
- **It's a helper, not a guarantee:**
  - it misses faces it can't find (back views, masks, some anime styles);
  - it can flag young-looking adults;
  - it is less reliable on stylised art.
- It is listed as open question Q1.

## A9. Tested vs not tested (honest)
**Tested here** with `tests/run_tests.py`: the real server, plus a fake ComfyUI that serves the **real ComfyUI 0.43 node
list**, a fake age checker and a fake trainer. Covered:
- the word rules (21+, lingerie/bikini/yoga allowed, school/teen blocked, the 18+-only blocks);
- the 18+ gate, PIN, lock-out and area isolation;
- the age-check flag → blur → can't reuse;
- all 12 video-studio model/mode combinations (frame-count and size rules);
- BYO workflow import;
- LoRA upload, family detection, triggers, blocking, stacking, Wan pairs and the Civitai flow (with a fake Civitai);
- the training dataset, refusals and the fake training run;
- Godot export;
- UI smoke tests and screenshots.

Separately, every built-in workflow (now including the v3 video models) was accepted by a **real** ComfyUI 0.43
running on CPU.

**Not tested** (no GPU and no model files here):
- real picture/video quality;
- real training quality and time;
- the real age-classifier accuracy;
- real Civitai downloads;
- opening the export in a real Godot editor;
- Windows scripts.

## A10. Open questions (v3)
1. **Q1 Age check:**
   - Keep it on by default, and keep requiring it for training?
   - Should flagged originals be deleted, as now, or kept blurred-only?
   - It can't be perfect (see A8).
2. **Q2 "Train my own clone":** *Answered in v4: allowed only as the owner's PIN-locked "Me" slot (Part V §V4), planned for P5.* v3 text: not built, for the reason in A4. If what you want is a *fictional* character that
   resembles your style, use Create plus Train. Is that enough?
3. **Q3 Real-person LoRAs named only by a name** can't be detected. Keep the tick box, or allow only LoRAs trained in
   Easy Studio?
4. **Q4 18+ PIN:** optional now. Make it required?
5. **Q5 Where do you live?** We did not ask, as you requested. The Hunyuan models are not licensed in the EU, UK or
   South Korea. They are optional and off by default.
6. **Q6 Godot 2D or 3D first?** The export supports both. Which comes first decides what we polish next (VN dialogue
   template vs 3D character controller).
7. **Q7 Video LoRA training** takes hours (Wan 2.2 14B pair). Keep it, or offer only picture LoRAs by default?

## A11. Improvement loops and adversarial pass
See `docs/research/improvement_loops.md` (v3 loops 6–8) and `docs/research/critic_passes.md` (v3 adversarial safety pass).

---

# Part B — Easy Studio 2 baseline (still true unless Part A says otherwise)

## 1. Summary

Easy Studio is a private, local "character studio" for Andrew's adult video game.

- **The idea.** It feels like the best "create your virtual girlfriend" sites (Candy.ai, Lovescape, Promptchan), crossed with a dress-up doll maker (Picrew, VRoid).
  - You pick looks with picture chips and sliders, not prompts or nodes.
  - Then you dress, pose, photograph, animate and 3D-print-preview the same character.
  - Results are exported as game assets.
- **How it runs.** Everything runs on Andrew's RTX PRO 6000 (96 GB) desktop. ComfyUI is the hidden engine, and Andrew uses it from a browser on his M5 Max MacBook.
- **Advanced controls.** Seeds, samplers, steps, LoRAs and the raw ComfyUI workflow sit behind an "Advanced" drawer.

**Hard limits (cannot be switched off in the app):**
1. Fictional **adults only**. Anything describing minors is refused.
2. **No real people.** No face-swap, deepfake, "looks like <name>", or celebrity likeness.
3. The adult-only README note stays.

Otherwise there is **no NSFW filter** on fictional adult content.

## 2. Goals and non-goals

**Goals**
- G1. A non-technical user goes from "open app" to the first picture of a new character in **under 2 minutes**, without typing a prompt.
- G2. The **same character** stays recognisable across outfits, poses, scenes, video and 3D.
- G3. One-click actions on every result: **Change outfit / Pose / Background / Add object / Upscale / Animate / Make 3D / Save to game**.
- G4. Game-ready exports: transparent PNG sprites, turnaround sheets, sprite sheets from video, and GLB 3D models.
- G5. Install stays one script plus one start script. No custom ComfyUI nodes.
- G6. Advanced users can reach every knob without leaving the app.

**Non-goals (for now)**
- Chat/companion features (personality, voice, memory). The game itself does this; Easy Studio only stores "writing notes".
- Cloud hosting, accounts, payments, sharing or a community feed.
- Rigging and animation of 3D models (Phase 3 idea).
- Any feature built to copy a real person.

## 3. Target user and personas

| Persona | Who | Needs | Pain today |
|---|---|---|---|
| **Andrew (primary)** | Game designer, not a developer. Visual thinker. | Make a cast of consistent adult characters, dress them, pose them, animate them, get assets into the game. | ComfyUI node graphs are confusing. Web sites are filtered or cloud-only and keep his content. |
| **"Power Andrew"** | Same person, a month later | Fine control: seeds, LoRAs from Civitai, exact sampler settings, the raw workflow. | Wants control without the default screen getting cluttered. |
| **Collaborator artist** (future) | A 2D/3D artist helping with the game | Clean exports: transparent PNGs, GLB into Blender, sprite sheets. | Gets messy JPGs with backgrounds. |
| **Novice tester** (critic persona) | Someone who has never used AI tools | Big obvious buttons, no jargon, an undo, a clear progress bar. | "What's a sampler? Why is it stuck?" |

## 4. Product principles

1. **Simple by default, advanced in a drawer** (Fooocus, SwarmUI). The Advanced drawer is closed on every tab and remembers its state.
2. **Pick, don't type** (Picrew, Candy.ai, VRoid). Every trait is a chip with an icon or swatch. There is always a free-text "anything else?" box, which is optional.
3. **One tool per job** (Mage.space "apps"). Each tab does one thing, with at most 3 steps: pick the input, choose the change, click the big button.
4. **Every result is a starting point** (Leonardo, Promptchan). The action bar under each picture covers outfit, pose, background, object, upscale, animate, 3D, sheet and save.
5. **The character is the unit** (Lovescape, Nomi). Saved characters carry their look and seed into every tool.
6. **Show before/after** (Promptchan Tweak). Edits are shown with a drag-to-compare slider.
7. **Honest progress.** A real progress bar, a "Stop" button, and plain-language errors with a fix.
8. **Safety is quiet but firm.** No nagging pop-ups. Hard refusals with a one-line reason. Unsafe chips simply don't exist.

## 5. Competitor study (summary)

**What we looked at.** We opened 111 sites and apps; 74 loaded with usable content. The rest were blocked (Cloudflare/SSL), parked, or wrong sites, and are marked in `docs/research/competitors.csv`. The full table is in **Appendix A**.

**Top 10 UX lessons we copied**
1. **Picture-card trait pickers, one decision at a time** (Candy.ai, DreamGF). → Character Creator chips with swatches and a step bar.
2. **Presets first, sliders second, live preview** (VRoid Studio, MetaHuman). → Body/face sliders under the chips; a live "character card" summary.
3. **Category icon row + swatch grid** (Picrew, Doll Divine). → The Wardrobe has category tabs (tops, bottoms, dresses, lingerie, swim, costumes, shoes, accessories) and colour swatches.
4. **Reusable character profile; change only outfit/scene/camera** (Lovescape, Nomi). → Saved Characters with a hero portrait and a seed; every tool starts from "Pick a character".
5. **One small app per task** (Mage.space: Outfit Swap, Angles, Character Sheet, Relight). → One tab per job.
6. **Before/after compare slider for edits** (Promptchan). → A compare slider on every edit result.
7. **Animate + Extend directly under each result** (Promptchan, HeraHaven, Leonardo). → The action bar on every result.
8. **Three-step "photoshoot"** (Fotor: upload, pick background/size, generate). **"Series" presets** (Seduced.ai) give a consistent set of shots in one click. → Photoshoot packs.
9. **Drop picture → 3D → spin → Export** (Meshy, Tripo). → The 3D tab with a built-in viewer and a GLB download.
10. **"Advanced" checkbox that hides the scary stuff** (Fooocus). **Simple front over ComfyUI, with raw-workflow access** (SwarmUI). → The Advanced drawer.

**Anti-patterns we refuse** (seen on real sites):
- "Teen" tags (OurDream, Kupid).
- Family-role bots such as "daughter" (Sakura.fm).
- "Age Play" and "Teen camp" tags (SpicyChat).
- A "Celebrities" category (JOI).
- Face Swap apps (Mage.space).
- Lookalike-from-photo (SoulGen) and selfie-to-avatar (Avaturn).

## 6. Feature list

Each feature has user stories (US), acceptance criteria (AC) and the model used. Phase: **P1** = must have now, **P2** = next, **P3** = later.

### 6.1 Character Creator (P1)
- **US1.** As Andrew, I click chips for body, face, hair, skin and style and get 4 candidate portraits without typing.
- **US2.** I can lock the look I like (its seed) and try small changes ("same, but red hair").
- **AC — chip groups:**
  - **Style:** realistic photo, anime, 3D render, painted.
  - **Gender presentation:** woman, man.
  - **Age:** slider, **minimum 21, maximum 70**, default 25. It is shown as "Adult · 25".
  - **Body type:** slim, athletic, average, curvy, plus-size, muscular.
  - **Height:** petite-adult, average, tall.
  - **Bust:** small, medium, large. **Hips:** narrow, medium, wide. Shown only for women; worded for adults.
  - **Skin tone:** 8 swatches. **Skin details:** freckles, tan lines, tattoos, piercings, beauty mark.
  - **Face:** face shape, eye shape, eye colour (swatches), lips, makeup level.
  - **Hair:** style chips (15), colour swatches (14), length.
  - **Fantasy:** elf ears, horns, tail, wings, demon, vampire, android, catgirl/kemonomimi (adult).
  - **Extra description:** a free-text field that passes the safety check.
- **AC — results and safety:**
  - Shows 4 results in a grid. Clicking one opens it big with the action bar.
  - Server side: the age is clamped to at least 21, and "adult, mature" is always in the prompt, with minor terms in the negative.
  - There is no "teen", "young", "petite child" or similar chip, and free text with such words is refused.
- **Model:**
  - Realistic → Chroma1-HD. Draft speed → Z-Image Turbo.
  - Anime → NoobAI-XL.
  - "3D render" and "painted" are style words used with Chroma.

### 6.2 Saved characters (P1)
- **US3.** I save a character with a name and notes ("writing notes" for the game). It appears as a card with its hero portrait.
- **US4.** In any tab I pick the character from a strip of cards instead of uploading.
- **AC — saved data:**
  - A character is a JSON "DNA" (all chips and sliders, style, seed, hero image, notes, created/updated dates).
  - It lives in `outputs/characters/<id>.json`.
  - You can rename, duplicate ("make a sister": same DNA, new seed), delete (moves to trash) and export/import as a JSON file.
- **AC — use in tools:**
  - Every tool that needs a character picture uses the hero portrait (or a chosen gallery picture of that character).
  - Everything made from a character is tagged with its id. The gallery filters by character.

### 6.3 Wardrobe / outfit swap / try-on (P1)
- **US5.** I pick a character, click "Outfit" chips (category, item, colour, material), and get the same character in the new outfit.
- **US6.** I upload a picture of a garment (no person needed) and the character wears it ("try-on").
- **US7.** I paint over an area and describe what goes there. This is the precise mode, and it's better for adult detail.
- **AC:**
  - **Describe mode** keeps the face, hair, body and pose, judged by eye; a before/after slider is shown.
  - **Try-on mode** accepts a garment picture. Upload role "clothing" is required, and the prompt tells the model to keep the character's face.
  - **Paint mode** has a brush with size, eraser, clear, and an "invert" option. Pixels outside the painted area stay identical (ImageCompositeMasked).
  - There's an "Undress/nude" outfit chip for adult characters. No filter is applied beyond the hard limits.
- **Model:**
  - Describe and try-on use Qwen-Image-Edit-2511 with the Lightning 4-step LoRA.
  - Paint mode uses Chroma1-HD inpaint (realistic) or NoobAI-XL inpaint (anime).

### 6.4 Poses (P1)
- **US8.** I pick a pose from a picture grid of stick figures (standing, hands on hips, sitting, kneeling, lying, walking, over-the-shoulder, arms up, leaning, crouching, and more), and my character takes that pose.
- **US9.** I copy a pose from any picture. Only the stick figure is extracted; the picture itself is not used.
- **AC:**
  - There are at least 12 bundled pose presets.
  - Re-posing keeps identity (edit route). "New picture in pose" uses pose control.
  - A pose extracted from an upload can be saved as a custom preset.
- **Model:**
  - Re-pose: Qwen-Image-Edit-2511, with image2 = the pose skeleton.
  - New picture in pose: Z-Image Turbo + Fun Union ControlNet.
  - Extract: SDPose.

### 6.5 Scenes and backgrounds (P1)
- **US10.** I pick a scene card (bedroom, beach, neon city, forest, castle hall, spaceship, studio white, office, bar, onsen, and so on) and lighting (golden hour, studio softbox, neon, candle, moonlight).
- **AC — three modes:**
  - **Smart swap:** the model re-lights the character to match (Qwen edit).
  - **Quick swap:** the character is cut out with BiRefNet and composited, so pixels are identical.
  - **Remove background:** produces a transparent PNG.

### 6.6 Insert objects (P1)
- **US11.** I add a prop to the picture: a chosen chip (sword, wine glass, flowers, guitar, umbrella, cat, sofa, motorbike, and so on), my own description, or an uploaded object picture.
- **AC:** a placement chip (in her hand, next to her, on the table, in the background, left, right) and an optional paint-where mask.
- **Model:**
  - Qwen edit, with image2 = the object picture when one is uploaded.
  - Inpaint when the user paints where it goes.

### 6.7 Photoshoot mode (P1)
- **US12.** I pick a character and a "shoot pack" (e.g. "Beach day: 6 shots", "Boudoir: 6 shots", "Fantasy armour: 4 shots", "Game portrait set: 4 expressions") and get a consistent set in one click.
- **AC:**
  - Each pack is a list of (scene, pose, camera, outfit) shots run as one job queue, with a progress bar per shot.
  - Results land in a project folder named after the pack.
- **Model:** Qwen edit from the hero portrait. This keeps identity across shots.

### 6.8 Image-to-video and extend (P1, improved in P2)
- **US13.** I click "Animate" on any picture, describe the motion with motion chips (turn around, walk toward camera, hair in wind, wink and smile, dance, sit down) and get a 5 s clip.
- **US14.** I extend a clip several times, changing the instruction each time, and get one stitched video.
- **US15.** I make "from picture A to picture B" and **seamless loops**.
- **AC:**
  - Fast (4-step) and Quality (20-step) modes; 480p and 720p; 2-10 s per clip.
  - Extend has an optional end picture per extension and a "loop back to start" option.
  - Duplicate frames are dropped when stitching.
- **Model:** Wan 2.2 I2V 14B, using WanImageToVideo and WanFirstLastFrameToVideo.

### 6.9 Image-to-3D with viewer and export (P1)
- **US16.** I click "Make 3D" on a picture (best: full body, plain background) and get a spinning textured 3D model I can download as GLB for Blender, Unity or Godot.
- **AC:**
  - Quality presets: Game-ready (50k faces), Standard (200k), Max detail (700k).
  - The built-in viewer (orbit, zoom, auto-rotate, lighting) works offline in Safari and Chrome.
  - There is a "Download .glb" button, and a help line on how to import into Blender.
  - An optional "Fast clay shape" mode uses Hunyuan3D 2.1. It is off by default because of its licence.
- **Model:** TRELLIS.2 (native ComfyUI). Hunyuan3D 2.1 is the opt-in backup.

### 6.10 Gallery and projects (P1)
- **US17.** I see everything I made, newest first, filter by character, project or type (picture, cut-out, video, 3D), star favourites, and open any item to continue working.
- **AC:**
  - Each item has a sidecar JSON: what made it, the prompt, seed, model, parent item and character.
  - A "Use these settings again" button.
  - Delete moves the item to `outputs/_trash`.
  - Projects are simple named folders/tags.

### 6.11 Game-asset export (P1 basic, P2 more)
- **US18.** I get assets my engine can use directly.
- **AC:**
  - Transparent PNG cut-outs.
  - A **turnaround sheet** (front, right, back, left) as one PNG plus the separate views.
  - A **sprite sheet** from a video (N frames, optional background removal) as PNG plus a JSON atlas.
  - **Expression sheet:** neutral, smile, laugh, angry, sad, surprised, flirty, sleepy.
  - **"Export pack"** zips a character's DNA, hero image, favourites, sheets and GLB.
- **Model:**
  - Turnaround: Qwen edit + the Multiple-Angles LoRA.
  - Expressions: Qwen edit.
  - Sprites: ffmpeg + BiRefNet.

### 6.12 Advanced mode (P1)
- **US19.** As Power Andrew I can set the seed, steps, CFG, sampler, scheduler and denoise, add up to 4 LoRAs with strengths (corrected in v4 to match Part A §A6), see the exact prompt sent, and paste or edit the raw ComfyUI workflow JSON.
- **AC:**
  - The drawer appears on every generating tab. Sampler and scheduler lists come live from ComfyUI; the LoRA list comes from `ComfyUI/models/loras`.
  - "Copy workflow" gives the exact API JSON for the last job, which can be pasted into ComfyUI.
  - "Run raw workflow" accepts API-format JSON. The **safety check still runs on every text field**, and node types linked to face-swap/likeness are refused.

### 6.13 Setup & health screen (P1)
- **AC:**
  - Shows whether ComfyUI is reachable, the GPU name and VRAM, and **which features are ready**. Each feature has a ✓ or ✗ with the exact missing file and the command to fetch it.

## 7. Model per feature

| Feature | Primary | Fallback / alternative | Why |
|---|---|---|---|
| New realistic character | Chroma1-HD (26 steps) | Z-Image Turbo (8 steps, drafts) | Apache-2.0, uncensored, strong realism |
| New anime character | NoobAI-XL 1.1 | -- | Best open anime model with adult knowledge |
| Outfit / scene / object / re-pose / expression | Qwen-Image-Edit-2511 + Lightning | Inpaint (Chroma / NoobAI) | Best open identity-keeping editor. Weaker on nudity, so paint mode covers that |
| Pose-guided new picture | Z-Image Turbo + Fun Union ControlNet | Qwen edit with skeleton | Native, Apache |
| Copy a pose | SDPose | -- | Native, MIT |
| Background remove | BiRefNet | -- | Native, MIT |
| Upscale | Real-ESRGAN x4plus | Diffusion detail upscale (P3) | Tiny, fast |
| Turnaround | Qwen edit + Multiple-Angles LoRA | -- | Uses ComfyUI CameraAngle vocabulary |
| Video | Wan 2.2 I2V 14B (fast/quality) | Wan FLF2V for A→B / loops | Apache, best open I2V |
| 3D | TRELLIS.2 (native) | Hunyuan3D 2.1 shape (opt-in) | MIT, textured PBR GLB |

## 8. Performance budgets

### RTX PRO 6000 Blackwell, 96 GB
These are **estimates** from model cards and community reports. They were **not measured**, because the build machine has no GPU. They are to be confirmed in Phase 1 acceptance.

| Job | Target time | VRAM peak |
|---|---|---|
| Chroma1-HD 1024² | ≤ 20 s per picture | ~30 GB |
| Z-Image Turbo 1024² | ≤ 4 s | ~20 GB |
| NoobAI-XL 1024² | ≤ 6 s | ~10 GB |
| Qwen edit (4-step) 1 MP | ≤ 8 s | ~40 GB |
| Inpaint Chroma | ≤ 20 s | ~30 GB |
| BiRefNet / Real-ESRGAN x2 | ≤ 2 s / ≤ 3 s | < 6 GB |
| Wan 2.2 fast, 5 s at 480p | ≤ 90 s | ~45 GB |
| Wan 2.2 fast, 5 s at 720p | ≤ 4 min | ~60 GB |
| TRELLIS.2 Standard | ≤ 60 s | ~12-24 GB |
| Photoshoot pack of 6 | ≤ 1 min | -- |

**Model switching:** the first job after switching model families loads from disk, which takes 10-40 s on NVMe. The app shows "Loading model…" so it doesn't look stuck.

### M5 Max MacBook (browser only)
- First page load is under 1 s on the LAN, with no external CDNs.
- Gallery thumbnails are lazy-loaded.
- The 3D viewer handles a 200k-face GLB at 60 fps. Max-detail models may be 50-100 MB; the viewer warns before loading anything over 60 MB.
- Uploads of up to 50 MB per picture.

### Other machines
- A 24 GB GPU can run everything except 720p video comfortably. Qwen edit needs fp8 and offloading there.
- A 12-16 GB GPU should use Z-Image, NoobAI, BiRefNet, Real-ESRGAN and TRELLIS.2 only. That's documented, not optimised.

## 9. Roadmap

| Phase | Contents | Status |
|---|---|---|
| **P1 — Studio core** | Character Creator, Saved characters, Wardrobe (describe/try-on/paint), Poses (presets, re-pose, copy pose), Scenes and backgrounds (smart/quick/remove), Insert object, Upscale, Animate + Extend, 3D (TRELLIS.2) with viewer and GLB, Gallery/projects, Advanced drawer, Setup screen, safety layer, new installer | **Built** (tested without GPU) |
| **P2 — Game pipeline** | Photoshoot packs, turnaround sheet, expression sheet, sprite sheet from video, FLF2V A→B and loop, export pack zip, Hunyuan3D opt-in, custom pose save | **Built**, except "custom pose save" (manual: copy the PNG into `app/static/poses/`) |
| **P3 — Pro (v3)** | Train my character (ai-toolkit; picture + Wan 2.2 video LoRAs), Video studio for any model + BYO workflows, LoRA library + Civitai import, 18+ section, automatic age check, Godot 4 export | **Built in v3** (tested with fakes; see Part A §A9). Still open: detail upscale, multi-view 3D, auto-rig, relight, region prompts |
| **P4–P9 (v4 plan)** | Photoreal studio + body realism → Me avatar 2D (upload) → 3D realism + Me head + game avatar → strip club game → companion chat (optional) → live scan + liveness | **Planned**; see Part V §V1 |

## 10. Safety design

1. **Text gate** (`app/safety.py`) runs on every text that reaches a model: free text, custom chips, character names and notes, video motion text, and **every string inside a raw workflow**.
   - It blocks minor terms (and leetspeak/spaced variants such as "t33n" and "t e e n"), ages under 18 (digits and words), school/family-role terms, and real-person / likeness / face-swap / celebrity terms.
2. **No unsafe UI.** There are no chips for youthful or child-coded traits. The age slider's floor is 21, and the server clamps it too, so tampered requests can't go lower.
3. **Adult anchoring.** Every positive prompt gets "adult" and mature cues. Every negative prompt gets the minor and real-person terms (`ALWAYS_NEGATIVE`). The anime model gets "mature female/male".
4. **Uploads have a role and a confirmation.**
   - **My fictional character** may be edited. The user must confirm it's a fictional adult they created.
   - **Clothing**, **object** and **background** can only be used as references (image2), never as the person being edited.
   - **Pose reference** can only be used to extract a stick figure.
   - The server enforces these roles.
5. **No likeness tools.** There is no face-swap, IP-Adapter-FaceID, InstantID, PuLID or ReActor. The raw-workflow runner refuses node types matching `face|swap|reactor|instantid|pulid|ipadapter|faceid|roop`.
6. **Local only by default.** ComfyUI listens on 127.0.0.1. The app listens on the LAN so the MacBook can reach it. When it listens on the LAN with no password set, it **creates one automatically** (`outputs/password.txt`, HTTP basic). Requests from the PC itself skip it. `EASY_STUDIO_PASSWORD=<value>` sets your own; `off` disables it. Every request that changes something must carry an `X-Easy-Studio` header, so another website open in your browser can't trigger jobs (CSRF). Nothing is uploaded anywhere.
7. **Limits we are honest about.**
   - Word lists can be dodged by a determined user.
   - Image models can still draw a youthful-looking face from neutral words. The negative prompt, age anchoring and the 21+ floor reduce this but don't guarantee it.
   - Andrew remains responsible for review. **v3:** an automatic image-level age check (YuNet + SigLIP2) now flags and blurs results that may look under 21 (Part A §A8); it is a helper, not a guarantee.
8. **v3 additions:** the 18+ section is isolated server-side; LoRAs of minors/real people are blocked; training only uses in-app characters or own fictional art, never photos (Part A §A4, §A6, §A7).

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Qwen edit weak on nudity / explicit detail | Wardrobe results "censored-looking" | Paint mode with Chroma / NoobAI inpaint; NoobAI for anime |
| Identity drift across edits and video | Character looks different | Always edit from the hero portrait (not chains of edits); P3 LoRA training |
| VRAM thrash switching models | Slow first job | Group work by tool; ComfyUI caches; "loading model" message |
| 3D quality (holes, soft hair) | Not game-ready without cleanup | Remesh (solid) + decimate; recommend full-body A-pose input; Blender cleanup tips |
| Licences (NoobAI, Hunyuan3D, DINOv3) | Commercial release issues | Opt-in Hunyuan; documented; open questions |
| ComfyUI updates rename nodes | Workflows break | Pinned ComfyUI commit in installer (optional); `tests/run_tests.py --real-comfy URL --real-dir DIR` re-checks every workflow shape against a running ComfyUI |
| Safety bypass via raw workflow / wording | Policy violation | Full-string scanning; node denylist; honest limits section |
| LAN exposure | Someone on the Wi-Fi uses it | Automatic password on LAN; CSRF header; README warns |
| 150 GB of downloads | Install takes hours | Resumable; groups; progress per file |

## 12. Open questions from v2 (status after v3)

| v2 question | Status |
|---|---|
| Q1 Uploads of people | Unchanged: role + tick. In v3, "My fictional character" uploads are also age-checked, and are the only uploads that can be used for training (own drawn / 3D art only). |
| Q2 Age floor | **Resolved: 21** (Andrew). |
| Q3 Body chips (petite / small bust) | Kept as "petite adult" / "small bust (adult)". The age check now backs this up. |
| Q4 Image-level age check | **Resolved: built, on by default** (Part A §A8). Its settings are open question A-Q1. |
| Q5 Commercial release | **Resolved: personal use only.** Territory notes are kept (Part A §A10 Q5). |
| Q6 Genders | Unchanged (woman / man + custom text). |
| Q7 Game engine | **Resolved: Godot 4** (Part A §A3). |
| Q8 LoRA training | **Resolved: built** (Part A §A4). |
| Q9 LAN password | Unchanged (on by default on the LAN). |
| Q10 UI tech | Unchanged (custom web page). |

---

## Appendix A — Competitor table

Source: `docs/research/competitors.csv`, 212 rows (v2: 111, v3 added 62, v4 added 39 marked "[v4]"). The load-status column says what loaded and what failed. Failed sites are listed, but nothing from them was used. "Traffic" comes from third-party estimates (Semrush / AlphaMoat, Sep 2026) and is approximate.

| # | Site | Category | Create flow | Standout UI | Pricing | Copy / avoid | Load status | Traffic |
|---|---|---|---|---|---|---|---|---|
| 1 | [Candy.ai](https://candy.ai/create-girlfriend) | AI companion | Step-by-step builder: style (realistic/anime) > ethnicity > age range > eyes > hair style & colour > body > personality > voice > hobbies > done | Big picture cards for every choice; one choice per screen; live summary; image gen offers outfit/background/pose pickers | Free trial + subscription + tokens | Picture-card choices per trait; outfit/pose/background pickers in the photo generator | loaded | 53.89M web visits Sep 2026 (Semrush); 62.7M (AlphaMoat); '50M users' is a company claim |
| 2 | [Nomi.ai](https://nomi.ai) | AI companion | Create a Nomi > pick look > chat; ask for selfies in chat | Memory of the character; selfies that respect current outfit/background; group chats | Free + subscription | Character keeps its look across every new picture ('character memory') | loaded | 1.43M web visits Sep 2026 (Semrush, via Codex ledger) |
| 3 | [Kindroid](https://kindroid.ai) | AI companion | Build a character > chat/voice/video call | Selfies, voice, live video (marketing page only) | not shown on the page we loaded | Short, confident feature labels | loaded (very little content) | 2.84M web visits Sep 2026 (Semrush, via Codex ledger) |
| 4 | [OurDream.ai](https://ourdream.ai) | AI companion / generator | 18+ gate > realistic or anime > face, body, hair, clothing, accessories > generate | Tag chips for traits; style toggle at top | $9.99-$19.99/mo + coins | Realistic/Anime toggle and trait chips. AVOID: it lists a 'Teen' tag despite banning minors | loaded | No Semrush figure; '70M registered' is an unaudited company claim |
| 5 | [DreamGF](https://dreamgf.ai) | AI companion | 6-step wizard: account > mix & match appearance > personality > extra content > chat > upgrade | Progress bar wizard; daily streak rewards | $12.99-$25.98/mo | A numbered wizard with a visible progress bar for first-time users | loaded | 315.1K web visits Sep 2026 (AlphaMoat) |
| 6 | [Promptchan](https://promptchan.com) | Adult image/video generator | Create (prompt + presets) > Tweak (describe a change) > Animate > Extend | Before/after drag slider for edits; Subject/Setting/Mood prompt helper; 'clone' community settings | Free + Gems / subscription | Before/after compare slider; Subject-Setting-Mood helper; Animate + Extend buttons right under a result | loaded | - |
| 7 | [SoulGen](https://soulgen.net) | Adult image generator | Describe or pick tags > generate > inpaint/outpaint > lip-sync video | Edit-by-brush, expand canvas | Subscription | Brush-to-edit and expand canvas. AVOID: 'make someone look like a photo' (real-person likeness) | loaded | - |
| 8 | [Replika](https://replika.com) | AI companion | Create avatar > customise look > chat | 3D avatar customisation, room, outfits shop | Free + Pro subscription | Outfit 'shop' style wardrobe browsing | loaded | 428.34K web visits Sep 2026 (Semrush; app-led, so understated) |
| 9 | [DarLink AI](https://www.darlink.ai) | AI companion | Customise look and personality > chat > photos/video | not shown on the page we loaded | Tokens | Look + personality in one builder | loaded (very little content) | - |
| 10 | [SpicyChat](https://spicychat.ai) | AI character chat | Browse community cards by tag > chat > create your own card | Tag chips, community cards, filters | Free + subscription | Tag filtering. AVOID: tags such as 'Age Play' / 'Teen camp' -- never offer such chips | loaded | 96.64M web visits Sep 2026 (Semrush, via Codex ledger) |
| 11 | [Janitor AI](https://janitorai.com) | AI character chat | Browse/create character cards > chat | Card grid, tags, creator profiles | Free (own API key) / tokens | Character card grid with tags | loaded | 132.3M web visits Sep 2026 (AlphaMoat); 189.5M own-domain (Semrush) |
| 12 | [Muah AI](https://muah.ai) | AI companion | Customise character > chat, voice, photos | Single long page of options | Subscription | Customise in one place | loaded | 862.4K web visits Sep 2026 (AlphaMoat) |
| 13 | [Lovescape](https://lovescape.com) | Adult image/video/story generator | Create a character profile > reuse it: change outfit, setting, camera, pose, lighting | Visual controls for appearance, clothing, body type, pose, background, lighting and composition; reusable character profiles | Subscription | REUSABLE CHARACTER PROFILE: keep traits, change only outfit/scene/camera -- the core of our Saved Characters | loaded | - |
| 14 | [GirlfriendGPT](https://www.girlfriendgpt.com (redirects to gptgirlfriend.online)) | AI companion | Browse characters with tag filters > chat > create | Tag filter bar | Free + premium | Filter bar of tags | loaded | 14.0M web visits Sep 2026 (AlphaMoat) |
| 15 | [JOI AI](https://www.joi.com) | AI companion | Browse > customise > chat | Age-range filters. AVOID: a 'celebrities' category | not shown on the page we loaded | Nothing on safety; shows why we ban real-person likeness | loaded | 27.2M web visits Sep 2026 (AlphaMoat) |
| 16 | [Secrets AI](https://secrets.ai) | AI companion | Pick a 'fantasy' > chat | 100+ fantasy scenario cards | not shown on the page we loaded | Scenario cards as starting points (our Photoshoot 'scenes') | loaded | 6.8M web visits Sep 2026 (AlphaMoat) |
| 17 | [Seduced.ai](https://seduced.com) | Adult image/video generator | Pick model (30+) > pick 'Series' preset of curated scenes > mix 'extensions' (LoRAs) > generate longer scenes | Presets that bundle scene+variables; mixable extensions at a default 80% strength | Subscription | 'Series' = one click gives a consistent set of shots; extensions with sensible default strength (our LoRA drawer) | loaded | - |
| 18 | [HeraHaven](https://herahaven.com) | AI companion | Create girlfriend > chat > pictures > turn picture into video | Picture-to-video button on every image | not shown on the page we loaded | 'Animate this' on every picture | loaded | - |
| 19 | [FantasyGF](https://fantasygf.ai) | AI companion | Filter by age, hair, body > pick or create > chat/pics/voice/video | Filter chips; duos | Free + premium | Chip filters for browsing your saved characters | loaded | - |
| 20 | [Kupid AI](https://kupid.ai) | AI companion | Realistic/Anime toggle > pick > chat | Style toggle; categories. AVOID: 'Teen' category | not shown on the page we loaded | Style toggle at the very top | loaded | - |
| 21 | [SoulFun](https://soulfun.ai) | AI companion | Pick personality tags > chat with text/images/voice/video | Personality tag chips | Subscription | Personality chips (for game writing notes) | loaded | - |
| 22 | [Sakura.fm](https://www.sakura.fm) | AI character chat | Browse/create characters > chat | Tags. AVOID: family-role bots (e.g. 'daughter') | Free + premium | Shows why role words like 'daughter' are blocked in our safety list | loaded | - |
| 23 | [FreeGF](https://freegf.ai) | AI companion / generator | Generator + chat, no sign-up | Minimal | Free | No sign-up wall (we're local, so zero sign-up) | loaded | - |
| 24 | [CrushOn AI](https://crushon.ai) | AI character chat | (title/description only) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (title/description only) | 21.2M web visits Sep 2026 (AlphaMoat) |
| 25 | [Anima (myanima)](https://myanima.ai) | AI companion | (minimal content) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (very little content) | - |
| 26 | [EVA AI](https://www.evaapp.ai) | AI companion | (minimal content) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (very little content) | - |
| 27 | [Virtual Girlfriend AI](https://www.virtualgirlfriend.ai) | AI companion | (minimal content) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (very little content) | - |
| 28 | [PepHop](https://pephop.ai) | AI character chat | (minimal content) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (very little content) | - |
| 29 | [Glambase](https://glambase.app) | AI influencer creator | Create persona > generate content > monetise | Persona profile page | Revenue share | A character 'profile card' with name, bio and portfolio | loaded | - |
| 30 | [VRoid Studio](https://vroid.com/en/studio) | 3D anime avatar maker | Pick preset items > adjust 10+ sliders > combine outfit templates > texture pen > export VRM | Real-time 3D preview; presets first, sliders second; one-click accessories | Free | PRESETS FIRST, SLIDERS SECOND, LIVE PREVIEW -- our Character Creator layout | loaded | - |
| 31 | [inZOI](https://playinzoi.com) | Life-sim character creator | (minimal marketing content) | not shown on the page we loaded | Paid game | -- | loaded (very little content) | - |
| 32 | [Avaturn](https://avaturn.me) | 3D avatar maker | Pick body type > hair > clothes > accessories > export (Blender/Unity), rigged with ARKit blendshapes | 10k looks; export buttons | Free + paid SDK | Export to Blender/Unity. AVOID: selfie-to-avatar (real person) | loaded | - |
| 33 | [MetaHuman](https://www.metahuman.com) | 3D digital human creator | Blend presets > sculpt face/body > hair & clothing > rigged export to Unreal | Blend between presets; region sculpting | Free with Unreal | Blend-between-presets idea for face shapes | loaded | - |
| 34 | [Daz 3D](https://www.daz3d.com) | 3D figure software + store | Load base figure > morph dials > add outfits/hair from store > pose > render | Morph dials; huge outfit library | Free app + paid assets | Pose presets library | loaded | - |
| 35 | [Reallusion Character Creator](https://www.reallusion.com/character-creator/) | 3D character design | Base > morph sliders > skin > hair > outfits > AccuRIG auto-rig > export | HD morph sliders; auto-rig | Paid + free trial | Auto-rig mention (future); grouped sliders | loaded | - |
| 36 | [Meshy](https://www.meshy.ai) | AI 3D generator | Upload image or text > 3D in 20-30 s > PBR textures > rig > export GLB/FBX/OBJ/STL | Big drop-zone; 3D viewer; export menu | Free tier + credits | Drop picture > get 3D > spin it > Export button | loaded | - |
| 37 | [Tripo AI](https://www.tripo3d.ai) | AI 3D generator | Text/image to 3D > rig & animate > PBR up to 8K > quad mesh | Viewer with lighting presets | Free tier + subscription | Low-poly / quad options for games | loaded | - |
| 38 | [Hyper3D Rodin](https://hyper3d.ai) | AI 3D generator | Image to 3D, near production-ready | Quality presets | Credits, free to start | Quality presets (Fast / Detailed) | loaded | - |
| 39 | [Kaedim](https://www.kaedim3d.com) | AI + artist 3D service | Send image > studio returns game-ready asset | Studio pipeline | $470-$600 (plans) | 'Game-ready' polygon budgets | loaded | - |
| 40 | [Artbreeder](https://www.artbreeder.com) | AI image mixer | (title only) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (title/description only) | - |
| 41 | [Tencent Hunyuan 3D (web)](https://3d.hunyuan.tencent.com) | AI 3D generator | (JavaScript-only page, no readable content) | not shown on the page we loaded | not shown on the page we loaded | -- | could not load (JavaScript only) | - |
| 42 | [Leonardo.ai](https://leonardo.ai) | AI image/video suite | Generate > Motion > Edit keeping the character > Upscale | Tool rail on the left, canvas in the middle | Free + subscription | Post-result action bar: Animate / Edit / Upscale | loaded | - |
| 43 | [Tensor.Art](https://tensor.art) | Model hub + generator | Pick model/LoRA > generate; 'design original character' | Model cards | Free + Pro | Model cards with sample images in the advanced drawer | loaded | - |
| 44 | [Civitai](https://civitai.com) | Model hub + generator | Browse models/LoRAs > generate | Model cards, filters | Free + Buzz currency | Where Andrew can find extra LoRAs (advanced) | loaded | - |
| 45 | [getimg.ai](https://getimg.ai) | AI creative suite | Character creator, relight, background cleanup, upscale, product orbit | Workspace with tool tabs | From $15/mo (credits) | Relight + background cleanup as one-click tools | loaded | - |
| 46 | [Krea](https://www.krea.ai) | AI creative suite | Generate / edit / enhance images and video in real time | Real-time canvas | Tokens / subscription | Live preview while dragging (future, needs fast model) | loaded | - |
| 47 | [Playground](https://playground.com) | AI design tool | Pick template > edit with words; swap style; remove object; smart layers | Template gallery | Free to start | Remove-object and swap-style buttons | loaded | - |
| 48 | [Mage.space](https://www.mage.space) | AI image/video | 'Apps': Character Builder, Outfit Swap, Scene Builder, Angles, Character Sheet, Relight, Inpaint, Skin Enhancer | One app per task, each a small form | Free + $10/mo | ONE SMALL TOOL PER TASK (Outfit Swap, Angles, Character Sheet) -- our tab design. AVOID: their Face Swap app | loaded | - |
| 49 | [PixAI](https://pixai.art) | Anime generator | Prompt or pick model/LoRA > generate | 1.8M models; daily credits | Free + credits | Anime model presets | loaded | - |
| 50 | [NovelAI](https://novelai.net) | Anime image + story | Prompt with tags > generate; story writer | Tag autocomplete | $10/mo+ | Tag autocomplete for the anime model (future) | loaded | - |
| 51 | [SeaArt](https://www.seaart.ai) | AI creative community | Remix someone's image settings > generate | 'Remix' button | Free + subscription | 'Use these settings again' on every gallery item | loaded | - |
| 52 | [Yodayo](https://yodayo.com) | Anime generator | Prompt > generate > share | Prompt gallery | not shown on the page we loaded | Prompt gallery as inspiration | loaded | - |
| 53 | [Moescape](https://moescape.ai) | Anime generator | Prompt > generate > share | Prompt gallery | not shown on the page we loaded | -- | loaded | - |
| 54 | [Higgsfield](https://higgsfield.ai) | AI image/video suite | Text or reference > image/video > edit > upscale | Camera-move presets | not shown on the page we loaded | Camera-move presets for video (future) | loaded | - |
| 55 | [Dzine](https://www.dzine.ai) | AI creative suite | Consistent character, image-to-3D, generative fill | Layers + tool rail | Credits | Consistent character + image-to-3D in one app (same idea as ours) | loaded | - |
| 56 | [Recraft](https://www.recraft.ai) | AI design platform | Generate, vector, custom styles | Style library | not shown on the page we loaded | Saved custom styles | loaded | - |
| 57 | [Unstable Diffusion (unstability.ai)](https://www.unstability.ai) | Unfiltered image generator | Prompt > generate | Model picker | $30/mo | -- | loaded | - |
| 58 | [Stable Diffusion Online](https://stablediffusionweb.com) | Web generator | Prompt > generate | Single prompt box | Free + paid | Single prompt box first screen | loaded | - |
| 59 | [Lalaland (now Browzwear)](https://lalaland.ai) | Fashion AI models | Redirects to Browzwear 3D virtual showrooms | 3D showroom | not shown on the page we loaded | -- | loaded | - |
| 60 | [Botika](https://botika.io) | Fashion AI models | Upload flat lay > pick AI model > on-model photos; one model across a whole collection | Model picker, batch | not shown on the page we loaded | Same model across many outfits = our Wardrobe batch | loaded | - |
| 61 | [Photoroom](https://www.photoroom.com) | Product photo editor | Upload > remove background > pick scene template > export | Instant cut-out; template scenes | Free trial + subscription | Instant background removal then scene templates | loaded | - |
| 62 | [Claid](https://claid.ai) | Product/fashion photo AI | Upload > background/lifestyle scene/on-model > download | Before/after | Free trial + credits | Clean cut-outs + lifestyle scenes | loaded | - |
| 63 | [Pebblely](https://pebblely.com) | Product photo AI | Upload > remove bg > pick from 100+ themes > bulk generate | Theme thumbnails | Free + paid | Theme thumbnails for backgrounds | loaded | - |
| 64 | [Aragon](https://www.aragon.ai) | AI headshots | Upload selfies > pick styles > get headshots | Style packs | $250-$500 (team plans) | --  (selfie-based; not applicable) | loaded | - |
| 65 | [FASHN](https://fashn.ai) | Fashion AI / try-on | Consistent AI models > virtual try-on > product visuals | Model library | Credits | Try-on: 'put this garment on this model' | loaded | - |
| 66 | [Fotor AI Photoshoot](https://www.fotor.com/features/ai-photoshoot/) | AI photoshoot | 3 steps: upload > choose background and size > generate | Three numbered steps | Free + Pro | 3-step Photoshoot flow | loaded | - |
| 67 | [Pixelcut Virtual Try-On](https://www.pixelcut.ai/virtual-try-on) | Virtual try-on | Upload clothing > pick a library model > fit | Two drop-zones side by side | not shown on the page we loaded | Two drop-zones: 'the character' + 'the outfit' | loaded | - |
| 68 | [Kolors Virtual Try-On (HF Space)](https://huggingface.co/spaces/Kwai-Kolors/Kolors-Virtual-Try-On) | Virtual try-on demo | Upload person + garment > seed > run | Two images in, one out | Free | Same two-input layout | loaded (title/description only) | - |
| 69 | [Vmake](https://vmake.ai) | Product video | Product > social video | Templates | Credits | -- | loaded | - |
| 70 | [Kling AI](https://klingai.com) | AI video | Text/image/reference to video | Multi-reference video | not shown on the page we loaded | First+last frame video (we use Wan FLF2V) | loaded | - |
| 71 | [HeyGen](https://www.heygen.com) | Avatar video | Personal avatar from your face/voice | Avatar picker | Free plan + paid | --  (real-person avatar; not applicable) | loaded | - |
| 72 | [Genmo](https://www.genmo.ai) | Video model lab | Research + video generation | not shown on the page we loaded | not shown on the page we loaded | -- | loaded | - |
| 73 | [Digen AI](https://digen.ai) | AI video | Image to video | Templates | $11.99 | Image-to-video templates | loaded | - |
| 74 | [Nastia](https://www.nastia.ai) | AI companion | Chat/roleplay companion | not shown on the page we loaded | Free tier + paid | -- | loaded | - |
| 75 | [Picrew](https://picrew.me) | Dress-up image maker | Open a maker > click part categories > pick items/colours > save | CATEGORY ICON ROW + SWATCH GRID + LIVE PREVIEW; colour swatches per part | Free | Category icons + swatch grid + instant preview -- the 'dress-up doll' feel Andrew wants | loaded | - |
| 76 | [Doll Divine](https://www.dolldivine.com) | Dress-up games | Pick a game > category tabs > click items | Category tabs | Free (gems) | Category tabs for Wardrobe | loaded | - |
| 77 | [Azalea's Dolls](https://www.azaleasdolls.com) | Dress-up games | Pick a doll > click clothes | Click-to-wear | Free | Click-to-wear simplicity | loaded | - |
| 78 | [Fooocus](https://github.com/lllyasviel/Fooocus) | Local image UI | Type prompt > Generate; 'Advanced' checkbox reveals styles, seeds, inpaint, image prompt | SIMPLE BY DEFAULT, ADVANCED CHECKBOX; Upscale/Vary buttons; offline | Free (open source) | Advanced drawer hidden by default | loaded | - |
| 79 | [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI) | Local image UI on ComfyUI | Simple Generate tab; full ComfyUI tab for experts | Generate tab + Comfy workflow tab | Free (open source) | Simple front-end on top of ComfyUI, with raw workflow access | loaded | - |
| 80 | [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion) | Local painting + AI (ComfyUI) | Select area > type > generate fill; live mode; pose vectors; upscale | Selection-based inpaint; live painting; region prompts | Free (open source) | Select-area-then-describe for object insertion | loaded | - |
| 81 | [Krita AI Handbook](https://docs.interstice.cloud) | Docs | Guides for the Krita plugin | Docs | not shown on the page we loaded | -- | loaded | - |
| 82 | [Stable Diffusion WebUI Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge) | Local image UI | Tabs: txt2img, img2img, extras | Tabbed layout | Free (open source) | -- | loaded | - |
| 83 | [InvokeAI](https://invoke.ai (docs)) | Local image UI (canvas) | Unified canvas: layers, inpaint, control layers, upscale | Canvas + layers; control layers | Free (open source); hosted $15-$50/mo | Control layers for pose/reference | loaded | - |
| 84 | [InvokeAI GitHub](https://github.com/invoke-ai/InvokeAI) | Local image UI (repo) | See above | -- | -- | -- | loaded | - |
| 85 | [Comfy (comfy.org)](https://comfy.org) | Node-based engine (our backend) | Node graph; templates; 'apps' mode | Templates gallery | Free local / paid cloud | Templates-first; Easy Studio hides the nodes | loaded | - |
| 86 | [Loras.dev](https://loras.dev) | LoRA generator | (thin page) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (very little content) | - |
| 87 | [getsona.ai](https://getsona.ai) | Persona AI | (thin page) | not shown on the page we loaded | not shown on the page we loaded | -- | loaded (very little content) | - |
| 88 | [SDXL Unstable / instantid.org](https://instantid.org) | (parked domain) | -- | -- | -- | -- | loaded but irrelevant (parked domain) | - |
| 89 | [Character.AI](https://character.ai) | AI character chat | -- | -- | -- | -- | could not load (403 Cloudflare) | 176.48M web visits Sep 2026 (Semrush, via Codex ledger) |
| 90 | [Talkie](https://www.talkie-ai.com) | AI character chat | -- | -- | -- | -- | could not load (403) | - |
| 91 | [PornPen](https://www.pornpen.ai) | Adult generator | -- | -- | -- | -- | could not load (SSL error) | - |
| 92 | [Perchance](https://perchance.org/ai-character-generator) | Generator | -- | -- | -- | -- | could not load (Cloudflare) | - |
| 93 | [NightCafe](https://creator.nightcafe.studio) | Generator | -- | -- | -- | -- | could not load (Cloudflare) | - |
| 94 | [Ideogram](https://www.ideogram.ai) | Generator | -- | -- | -- | -- | could not load (Cloudflare) | - |
| 95 | [ZMO.ai](https://www.zmo.ai) | Generator | -- | -- | -- | -- | could not load (SSL error) | - |
| 96 | [Everskies](https://everskies.com) | Dress-up community | -- | -- | -- | -- | could not load (521 server down) | - |
| 97 | [Ready Player Me](https://readyplayer.me) | 3D avatars | -- | -- | -- | -- | could not load (SSL; service reportedly ended) | - |
| 98 | [Illusion](https://www.illusion.jp) | 3D character games | -- | -- | -- | -- | could not load (SSL error) | - |
| 99 | [AI-Girlfriend.ai](https://ai-girlfriend.ai) | AI companion | -- | -- | -- | -- | could not load (Cloudflare) | - |
| 100 | [Dollmaker games](https://www.dollmaker.games) | Dress-up | -- | -- | -- | -- | could not load (SSL error) | - |
| 101 | [CSM.ai](https://www.csm.ai) | AI 3D | -- | -- | -- | -- | could not load (SSL error) | - |
| 102 | [Hi-Anime](https://www.hi-anime.ai) | Anime generator | -- | -- | -- | -- | could not load (SSL error) | - |
| 103 | [DreamPal](https://www.dreampal.ai) | AI companion | -- | -- | -- | -- | could not load (503) | - |
| 104 | [Dittin](https://www.dittin.ai) | AI character chat | -- | -- | -- | -- | could not load (SSL error) | - |
| 105 | [Fliki](https://www.fliki.ai) | AI video | -- | -- | -- | -- | could not load (SSL error) | - |
| 106 | [Anytopia](https://www.anytopia.ai) | AI companion | -- | -- | -- | -- | could not load (SSL error) | - |
| 107 | [OpenArt](https://www.openart.ai) | Generator | -- | -- | -- | -- | could not load (404 on the page tried) | - |
| 108 | [Invoke.com](https://www.invoke.com) | (domain for sale) | -- | -- | -- | -- | wrong site (domain for sale) | - |
| 109 | [Chai (chai.com)](https://www.chai.com) | (tea company, not the AI app) | -- | -- | -- | -- | wrong site (tea company) | - |
| 110 | [mua.ai](https://www.mua.ai) | (domain for sale) | -- | -- | -- | -- | wrong site (domain for sale) | - |
| 111 | [Pykaso](https://www.pykaso.ai) | (page now shows Pyksel, an ad generator) | -- | -- | -- | -- | loaded but irrelevant (now an ad generator) | - |
| 112 | [Candy.ai video builder (v3 visit)](https://candy.ai/ai-video-generator) | AI companion video | Home > 'Build your video': pick a girl from a photo grid > build scenes > video; sign-up wall before the scene step | Hero banner with sample clip lengths (1:12, 1:47, 2:00); character grid with category tabs; sticky bottom bar 'Pick a character -> Create Video' | Subscription + tokens | Copy: pick-a-character-first then scenes; sticky action bar; long videos made of scenes. Avoid: '18-21' category and 19-year-old characters (our youngest is 21); licensed real-performer clones (we allow no real people); account wall | loaded (home, create, video grid screenshots); create-character/shorts/my-ai = 404; collection/private = sign-in wall (not passed) | - |
| 113 | [Candy.ai create flow (v3 visit)](https://candy.ai/create-girlfriend) | AI companion | Girls/Trans toggle > two big cards REALISTIC vs ANIME > Start > (later steps need an account) | Two huge picture cards with a check badge; one decision per screen; pink primary button | Subscription | Copy: style choice as two big picture cards as the very first step (Easy Studio Create already starts with style; made cards bigger in plan) | loaded (step 1 only; rest behind sign-up, not attempted) | - |
| 114 | [Nectar AI](https://nectar.ai) | AI companion | Create > HD creator > character; 'Fantasies' = same characters in different scenarios | 'Fantasies': unique storylines with the same characters; per-companion model/memory settings | Free + subscription | Copy: scenario packs that reuse one saved character (our Photoshoot packs + 18+ packs) | loaded | - |
| 115 | [ComfyUI-Lora-Manager](https://github.com/willmiao/ComfyUI-Lora-Manager) | LoRA manager (open source) | Scans LoRA folder > cards with previews, trigger words, base model > send to workflow | Preview cards, Civitai metadata fetch, trigger words copied in, recipes | Free (open source) | Copy: card grid with thumbnail, base model and trigger words; auto-insert triggers. We add a real-person/minor block | loaded | - |
| 116 | [Stable-Diffusion-Webui-Civitai-Helper](https://github.com/butaixianran/Stable-Diffusion-Webui-Civitai-Helper) | LoRA manager (Forge/A1111 extension) | Scan models > fetch Civitai info + preview by file hash > download by URL | One-click 'download by Civitai URL'; preview images saved next to the file | Free (open source) | Copy: paste a Civitai link to install; preview saved as <name>.preview.png (we use the same convention) | loaded | - |
| 117 | [Civitai content levels](https://education.civitai.com/civitais-guide-to-content-levels/) | Content policy | Five-level rating system for models and images (PG to XXX) | Browsing levels the user opts into; adult levels hidden by default | n/a | Copy: adult content hidden unless opted in; we route Civitai NSFW LoRAs to the 18+ section only | loaded | - |
| 118 | [Civitai LoRA trainer guide](https://education.civitai.com/using-civitai-the-on-site-lora-trainer/) | LoRA training (web) | Choose model type > add + caption training data > review settings > submit > wait > test | Wizard with auto-captioning and sensible defaults; sample images per epoch | Buzz credits | Copy: 4-step wizard with auto-captions and defaults. Our dataset is generated from the saved character instead of uploaded photos | loaded | - |
| 119 | [Civitai REST API wiki](https://github.com/civitai/civitai/wiki/REST-API-Reference) | API docs | /api/v1/models/{id}, /model-versions/{id}, download URLs with token | Public JSON incl. nsfw flag, baseModel, trainedWords, poi (person of interest) flag | Free | Used for the Civitai import: name, base model, trigger words, nsfw and poi flags | loaded | - |
| 120 | [Civitai developer docs](https://developer.civitai.com/docs/api/public-rest) | API docs | - | - | - | Used the GitHub wiki instead | failed (404) | - |
| 121 | [ai-toolkit (ostris)](https://github.com/ostris/ai-toolkit) | LoRA trainer (open source, MIT) | YAML/JSON config > run.py > LoRA; UI optional | Supports Chroma, Z-Image, SDXL, Wan 2.2 (incl. high/low split), LTX; low-VRAM options | Free | Picked as Easy Studio's trainer (one tool for picture and video LoRAs) | loaded (README rate-limited once, main page loaded) | - |
| 122 | [musubi-tuner](https://github.com/kohya-ss/musubi-tuner) | LoRA trainer (open source) | Cache latents/text > train video LoRAs (Wan, HunyuanVideo) | Strong for video LoRAs; command-line only | Free | Runner-up trainer for video; not picked to keep one trainer | loaded | - |
| 123 | [diffusion-pipe](https://github.com/tdrussell/diffusion-pipe) | LoRA trainer (open source) | TOML config > deepspeed pipeline training | Multi-GPU; many video models | Free | Not picked (Linux/deepspeed only, harder setup) | loaded | - |
| 124 | [OneTrainer](https://github.com/Nerogar/OneTrainer) | LoRA trainer (open source) | Desktop GUI > presets > train | Presets per model; built-in captioning; sample previews | Free | Copy: presets per base model (our 'What is the LoRA for?' choice) | loaded | - |
| 125 | [FluxGym](https://github.com/cocktailpeanut/fluxgym) | LoRA trainer UI (open source) | Name + trigger > drop images > auto-caption > train | 3-step single page; low-VRAM | Free | Copy: one page, trigger word up front, auto captions | loaded | - |
| 126 | [kohya_ss](https://github.com/bmaltais/kohya_ss) | LoRA trainer GUI (open source) | Many tabs of settings > train | Very powerful, very many knobs | Free | Avoid: settings overload for a non-developer | failed first try, loaded on retry | - |
| 127 | [fal.ai FLUX LoRA training](https://fal.ai/models/fal-ai/flux-lora-fast-training) | LoRA training (cloud API) | Upload zip > trigger word > train in minutes | Minimal form; style/character/object modes | Pay per run | Copy: few inputs. Not used (cloud upload; we stay local) | loaded | - |
| 128 | [Replicate FLUX fine-tune](https://replicate.com/blog/fine-tune-flux) | LoRA training (cloud) | Upload images > trigger word > train > run | One-line training; trigger word naming tips | Pay per run | Copy: unique trigger word made from the name (our make_trigger) | loaded | - |
| 129 | [Astria](https://www.astria.ai/) | Fine-tune / photoshoots (web) | Upload > tune > templates (headshots, ecommerce) | Keyboard-driven composer; template packs | Subscription | Avoid: photo-of-real-person tuning (we deliberately don't train on photos) | loaded (app shell) | - |
| 130 | [SwarmUI video model docs](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/Video%20Model%20Support.md) | Local UI docs | Per-model notes: frames, fps, resolutions for Wan, LTX, Hunyuan, Kandinsky | Model-specific frame rules (4n+1, 8n+1) documented | Free | Used to check frame-count rules per video model | loaded | - |
| 131 | [SwarmUI prompt syntax (LoRAs)](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/Features/Prompt%20Syntax.md) | Local UI docs | <lora:name:weight> in prompt | LoRAs by name in the prompt | Free | Avoid for non-developers: we use pickers + auto trigger words instead of syntax | loaded | - |
| 132 | [Wan2GP (WanGP)](https://github.com/deepbeepmeep/Wan2GP) | Local video app (open source) | Pick model > prompt/picture > generate; sliding-window long videos | One app, many video models (Wan, LTX, Hunyuan, MiniMax H3), LoRA folder per model | Free | Copy: model picker for every video model with per-model LoRA lists; we add BYO ComfyUI workflows | loaded | - |
| 133 | [ComfyUI workflow templates](https://github.com/Comfy-Org/workflow_templates) | Workflows | Official template workflows per model | Reference graphs for Wan 2.2, LTX-2, HunyuanVideo 1.5, Kandinsky 5 | Free | Used as the base for the built-in video workflows | loaded | - |
| 134 | [HunyuanVideo 1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5) | Video model | t2v / i2v, 480p/720p, step-distilled | Lightweight (8.3B) | Tencent Hunyuan Community licence (not valid in EU/UK/South Korea) | Included as optional; licence territory note in README | loaded | - |
| 135 | [LTX-2](https://github.com/Lightricks/LTX-2) | Video model | Audio+video model; LoRA trainer included | Fast distilled variants; built-in trainer | LTX-2 Community licence (free under $10M revenue; HF gated) | Included as optional download; gated: needs your own HF login | loaded | - |
| 136 | [LTX Studio](https://ltx.studio/) | Video (web) | Story > storyboard > shots > video | Storyboard of shots with consistent characters | Subscription | Copy: scene-by-scene thinking (our Extend parts) | loaded | - |
| 137 | [Krea Video](https://www.krea.ai/video) | Video (web, multi-model) | Pick a model from a list (Seedance, Veo, Kling, Wan, Runway...) > prompt/picture | Model picker as the first choice, same form for all | Subscription | Copy: one form for every model; model picker first (our Video studio) | loaded | - |
| 138 | [Pollo AI](https://pollo.ai/) | Video (web, multi-model) | Tool list (image-to-video, extender, ...) + model list | Separate 'Video Extender' tool; dozens of models | Credits | Copy: Extend as its own mode. Avoid: face-swap tools (we never add them) | loaded | - |
| 139 | [Higgsfield](https://higgsfield.ai/) | Video/image suite (web) | Apps per task (Genjutsu, Mangaka, Cinema Studio) | Camera-move presets | Subscription | Copy: camera-move presets (our motion chips) | loaded | - |
| 140 | [OpenArt Characters](https://openart.ai/characters) | Character consistency (web) | Create a character from presets/prompt (or photo) > reuse the same face in every image and video | Saved character used everywhere | Credits | Copy: saved character reused everywhere. Avoid: 'from a photo' (real people) | loaded | - |
| 141 | [OpenArt video](https://openart.ai/video) | Video (web) | Model list + Director mode (long video) | Director mode for full films | Credits | Copy: long-video mode idea | loaded (partial) | - |
| 142 | [OpenArt training](https://openart.ai/training) | LoRA training (web) | - | - | - | - | failed (404) | - |
| 143 | [Lovescape (v3 visit)](https://lovescape.com/) | Adult AI studio | Fictional adult profile > style > images, chat, story, video in one workspace | 'One consistent profile, several tools' (image > story > video) | Subscription | Copy: one character drives every tool. Avoid: 'Teen 18+' category (our youngest is 21) | loaded | - |
| 144 | [Seduced.ai (v3 visit)](https://seduced.ai/) | Adult AI image/video | Pick model style (realistic/semi/hentai) > layer fetish presets > images > videos > extend into longer scenes | 30+ models; extend scenes instead of one short clip | Subscription | Copy: extend scenes, style first; separate adult area | loaded | - |
| 145 | [Promptchan (v3 visit)](https://promptchan.com/) | Adult AI image/video | Create > prompt > Tweak > video; community 'Clone' and 'Extend' buttons | Extend button on every video; Clone settings from a post | Freemium | Copy: Extend button on results (we have it), 'reuse settings' | loaded | - |
| 146 | [HeraHaven (v3 visit)](https://herahaven.com/) | AI companion | Age gate (enter) > create girlfriend > chat/pictures/videos | Simple one-click age-confirm gate | Subscription | Copy: one-time confirm gate. Avoid: 18- and 19-year-old characters | loaded | - |
| 147 | [OurDream.ai (v3 visit)](https://www.ourdream.ai/) | AI roleplay | Age verification + interest pick > explore/create/generate | Interest picker in the age gate | Subscription + coins | Copy: separate adult area behind a gate | loaded | - |
| 148 | [Kupid AI (v3 visit)](https://kupid.ai/) | AI companion | Style realistic/anime > category > model | Category chips | Subscription | Avoid: 'Teen' category; we refuse teen words entirely | loaded | - |
| 149 | [Mage.space (v3 visit)](https://www.mage.space/) | Image/video (web) | Apps: Character Builder, Inpaint, Refine, Face Swap... | 'Private by default' | Freemium | Copy: private-by-default. Avoid: face swap / video face swap | loaded | - |
| 150 | [SeaArt training](https://www.seaart.ai/train) | LoRA training (web) | - | Page loaded only the generic shell | - | - | loaded (empty shell, no training details) | - |
| 151 | [Pinokio](https://pinokio.co/) | 1-click local AI app launcher | Browse apps > 1-click install > run | 1-click installers for local AI apps (incl. trainers) | Free | Copy: one-command installers (our install_trainer scripts) | loaded | - |
| 152 | [MiVOLO](https://github.com/WildChlamydia/MiVOLO) | Age estimation model | Face+body age/gender estimation | Good accuracy | Research licence (non-commercial) | Considered for the age check; not picked (licence, heavier) | loaded | - |
| 153 | [vit-age-classifier](https://huggingface.co/nateraw/vit-age-classifier) | Age classifier | ViT trained on FairFace age buckets | Small, simple pipeline | Model card: no licence stated clearly | Considered; we used a SigLIP2 age classifier + YuNet face finder instead (see PRD) | loaded | - |
| 154 | [Bluesky stackable moderation](https://bsky.social/about/blog/03-12-2024-stackable-moderation) | Content policy | Labelers add labels; users choose to hide/warn/show per label | Blur-with-warning instead of delete | n/a | Copy: blur + warning badge for flagged items (our age check) | loaded | - |
| 155 | [Tumblr content labels](https://help.tumblr.com/community-labels/) | Content policy | Creators label posts (mature, sexual themes...); viewers choose show/blur/hide | Blurred labelled content behind a tap | n/a | Copy: separate adult content, blurred by default where needed | loaded | - |
| 156 | [Steam adult content FAQ](https://help.steampowered.com/en/faqs/view/2E99-6E80-0C2E-6E13) | Content policy (games) | - | Page shell only | n/a | Godot export stays private; no store publishing planned | loaded (page shell only, no FAQ text) | - |
| 157 | [Spicychat (v3 visit)](https://spicychat.ai/) | AI companion | - | - | - | - | failed (JS app, only 'Loading...') | - |
| 158 | [Joyland](https://www.joyland.ai/) | AI companion | - | - | - | - | failed (JS app, empty page) | - |
| 159 | [Kindroid (v3 visit)](https://kindroid.ai/) | AI companion | - | Only title/meta loaded | - | - | loaded (title only) | - |
| 160 | [Leonardo.ai (v3 visit)](https://leonardo.ai/) | Image/video (web) | - | - | - | - | failed (403 bot check) | - |
| 161 | [Tensor.Art (v3 visit)](https://tensor.art/lora-training) | LoRA training (web) | - | - | - | - | failed (403 bot check) | - |
| 162 | [NightCafe (v3 visit)](https://creator.nightcafe.studio/) | Image (web) | - | - | - | - | failed (403 bot check) | - |
| 163 | [Freepik video](https://www.freepik.com/ai/video-generator) | Video (web) | - | - | - | - | failed (403 security filter) | - |
| 164 | [PornPen (v3 visit)](https://pornpen.ai/) | Adult image | - | - | - | - | failed (no response) | - |
| 165 | [getimg.ai DreamBooth](https://getimg.ai/features/dreambooth) | LoRA training (web) | - | - | - | - | failed (404); home page loaded | - |
| 166 | [InvokeAI model docs](https://invoke-ai.github.io/InvokeAI/concepts/models/) | Docs | - | - | - | - | failed (500) | - |
| 167 | [itch.io content rating docs](https://itch.io/docs/creators/content-rating) | Content policy (games) | - | - | - | - | failed (404) | - |
| 168 | [Discord age-restricted help](https://support.discord.com/hc/en-us/articles/115000084051) | Content policy | - | - | - | - | failed (403 bot check) | - |
| 169 | [Patreon adult content help](https://support.patreon.com/hc/en-us/articles/203950825) | Content policy | - | - | - | - | failed (403 bot check) | - |
| 170 | [Reddit NSFW help](https://support.reddithelp.com/hc/en-us/articles/360060418952) | Content policy | - | - | - | - | failed (403 bot check) | - |
| 171 | [X sensitive media help](https://help.x.com/en/safety-and-security/sensitive-media) | Content policy | - | - | - | - | failed (403 bot check) | - |
| 172 | [DeviantArt mature filter](https://www.deviantart.com/team/journal/Mature-Content-Filter-Update-817495578) | Content policy | - | - | - | - | failed (no response) | - |
| 173 | [pixiv R-18 help](https://www.pixiv.help/hc/en-us/articles/235646387) | Content policy | - | - | - | - | failed (no response) | - |
| 174 | [SillyTavern](https://github.com/SillyTavern/SillyTavern) | Local open-source companion chat frontend [v4] | Install > connect a local or API LLM > import character card (PNG/JSON) > chat | Character cards, lorebooks/world info, per-chat author's note, swipes (regenerate alternatives), group chats, image-gen and TTS extensions | Free, AGPL-3.0 | Copy: character card format and 'swipes'. Too many knobs for Andrew; keep a 3-control version (low-priority chat) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 175 | [KoboldCpp](https://github.com/LostRuins/koboldcpp) | Local LLM runner [v4] | Download one exe > pick GGUF model > web UI | Single file, built-in story/chat UI, image + TTS + Whisper bundled | Free, AGPL-3.0 | Proof a single-binary local chat stack is possible; we would use LM Studio/Ollama on the Mac instead | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 176 | [LM Studio](https://lmstudio.ai) | Local LLM runner (Mac/Windows) [v4] | Install > download model from catalogue > chat or local OpenAI-style server | MLX models on Apple Silicon; OpenAI-compatible local server | Free for personal use | Best fit for the M5 Max side of the (low-priority) chat; Easy Studio just calls its local server | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 177 | [Ollama](https://ollama.com) | Local LLM runner [v4] | Install > `ollama run <model>` > local API | One-line model pulls; local REST API | Free, MIT | Alternative to LM Studio; simple API | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 178 | [Open WebUI](https://github.com/open-webui/open-webui) | Local chat web UI [v4] | Docker/pip install > connect Ollama > chat | Voice mode (STT/TTS), memory, image generation via ComfyUI | Free, BSD-3 with branding clause | Copy: talk-mode button; ComfyUI hook for pictures in chat | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 179 | [text-generation-webui (oobabooga)](https://github.com/oobabooga/text-generation-webui) | Local LLM UI [v4] | Install > load model > chat/notebook | Character tab, extensions | Free, AGPL-3.0 | Reference only; developer-oriented | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 180 | [Backyard AI (ex-Faraday)](https://backyard.ai) | Local + cloud companion chat app [v4] | Install desktop app > download a character > chat offline | Runs models on-device; character hub; simple model picker | Free local; paid cloud tiers | Copy: 'it just runs offline' framing for the chat | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 181 | [RisuAI](https://github.com/kwaroran/RisuAI) | Open-source chat frontend [v4] | Web/desktop > add API or local model > chat | Emotion images per character, lorebooks, TTS | Free, GPL-3.0 | Copy: expression-picture swap during chat (we already make expression sheets) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 182 | [Chub.ai](https://chub.ai) | Character card hub [v4] | Browse > download card > use in SillyTavern etc. | Huge shared card library, tags | Free + paid chat | Not applicable (sharing/community); card format is the useful part | failed (HTTP Error 403: Forbidden); info from search results | - |
| 183 | [Kokoro TTS](https://huggingface.co/hexgrad/Kokoro-82M) | Local text-to-speech model [v4] | Load 82M model > text > speech | Very small, fast, good quality | Apache-2.0 | Local TTS candidate for the (low-priority) voice | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 184 | [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) | Local TTS with emotion control [v4] | Install > text (+ optional voice prompt) > speech | Emotion exaggeration slider; watermarking | MIT | Use built-in/fictional voices only; no cloning of real voices except the owner's own (open question) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 185 | [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | Local speech-to-text [v4] | Build/download > model > transcribe | Fast on Apple Silicon (Metal) | MIT | Local STT for talk mode on the Mac | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 186 | [OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat) | Open-source talking 3D avatar chat [v4] | Install > LLM + ASR + TTS + LAM avatar | Real-time 3D Gaussian head in the browser | Apache-2.0 | Reference for a later talking head; heavy | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 187 | [LAM (Large Avatar Model)](https://github.com/aigc3d/LAM) | One-image 3D Gaussian head avatar [v4] | Upload one image > animatable head in seconds | WebGL renderer; Audio2Expression; MeshLAM (CVPR 2026) | Apache-2.0 (FLAME parts separate) | Fast 3D-head preview from one frame; lower fidelity than video methods | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 188 | [GTAvatar](https://github.com/KelianB/GTAvatar) | Research: relightable head avatar from one video [v4] | Monocular video > FLAME tracking > 1-3 h training > relightable textured Gaussians | Relighting with HDR maps, texture editing | Apache-2.0 code; FLAME and 3DGS renderer non-commercial | Best match for 'Me' 3D head from the uploaded video (personal use OK) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 189 | [PBR-GAvatar](https://github.com/liguohao96/PBR-GAvatar) | Research: relightable Gaussian head from monocular video [v4] | Video > FLAME > blendshape Gaussians with PBR materials | Storage-efficient; material split (albedo/roughness) | Research code; FLAME licence | Alternative to GTAvatar | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 190 | [GAGAvatar](https://github.com/xg-chu/GAGAvatar) | Research: one-shot head avatar [v4] | One image > real-time reenactment | Real-time | MIT (FLAME separate) | Quick preview only | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 191 | [MetaHumanGodot](https://github.com/ibrews/MetaHumanGodot) | MetaHuman viewer/shaders for Godot [v4] | Export MetaHuman > Blender > Godot 4.6 | Skin/eye/hair shaders, ARKit morph targets | Free (repo licence) | Route to a rigged realistic body + face in Godot | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 192 | [GoDNA](https://danikakes.itch.io/godna) | Godot importer for MetaHuman [v4] | UE 5.6 one-click export > Godot 4.5 import | 103-bone humanoid, 51 ARKit shapes, hair cards, live face capture (Pro) | Paid $7.50+ (beta) | Cheapest path from MetaHuman to Godot; beta | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 193 | [HumanShaders (MatMADNESS)](https://github.com/matmadness/HumanShaders) | Godot skin/eye shaders [v4] | Drop shaders onto a head | Skin SSS, eye, eye wetness | Free (CC0/MIT per repo) | Use as the Godot skin baseline | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 194 | [MPFB2 (MakeHuman for Blender)](https://static.makehumancommunity.org/mpfb) | Open-source base-body generator [v4] | Blender add-on > sliders > rig > export | CC0 bodies, game rigs, Mixamo-compatible rig, clothes library | Free, CC0 assets/GPL code | Default base body for NPCs and the Me body | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 195 | [Mixamo](https://www.mixamo.com) | Auto-rig + animation library [v4] | Upload mesh > auto-rig > pick animations | Large free mocap library | Free with Adobe account | Animation source (dance, idle, walk); needs an account (Andrew signs in) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 196 | [UniRig](https://github.com/VAST-AI-Research/UniRig) | Research auto-rigging [v4] | Mesh > predicted skeleton + skin weights | Works on varied meshes | MIT | Local auto-rig for generated (TRELLIS) meshes | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 197 | [AccuRIG / ActorCore](https://actorcore.reallusion.com/auto-rig) | Free auto-rigger + paid mocap [v4] | Load mesh > place markers > rig | Hands/fingers rigging; mocap store incl. dances | Free rigger; paid motions | Alternative to Mixamo | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 198 | [KIRI Engine](https://www.kiriengine.app) | Phone photogrammetry / 3DGS scanning [v4] | Phone photos or video > cloud reconstruct > mesh/3DGS | Quad retopology, many export formats | Free tier + paid | Cloud: not for the face. OK for props/clothes | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 199 | [Heges 3D Scanner](https://apps.apple.com/us/app/heges-3d-scanner/id1382310112) | iPhone TrueDepth/LiDAR scanner [v4] | Scan with front TrueDepth > export mesh | On-device; STL/OBJ/PLY/GLB | Paid app | On-device face depth scan option for the later guided capture | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 200 | [Live Link Face](https://apps.apple.com/us/app/live-link-face/id1495370836) | iPhone face capture (Epic) [v4] | Record with TrueDepth > MetaHuman Animator | Depth + video takes; ARKit blendshapes | Free | Best iPhone tool for MetaHuman identity + facial animation | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 201 | [ComfyUI-Impact-Pack (FaceDetailer)](https://github.com/ltdrdata/ComfyUI-Impact-Pack) | ComfyUI detailer nodes [v4] | Detect face/hands > crop > re-sample > paste back | ADetailer-style; SAM/YOLO detectors | GPL-3.0 | Use for face/hand detail passes | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 202 | [SeedVR2 ComfyUI nodes](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler) | Image/video upscaler [v4] | Image or video > one-step DiT upscale | 3B/7B, GGUF, BlockSwap, tiling | Apache-2.0 | Default upscaler (7B sharp for skin) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 203 | [ComfyUI-Frame-Interpolation / GIMM-VFI](https://github.com/kijai/ComfyUI-GIMM-VFI) | Video frame interpolation [v4] | 16 fps video > 32/48 fps | GIMM-VFI high quality; RIFE fast | Varies (MIT/Apache) | Use GIMM-VFI for finals, RIFE for previews | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 204 | [Instareal Wan 2.2](https://civitai.com/models/1877171/instareal-wan-22) | Wan 2.2 realism LoRA [v4] | Load high + low noise LoRA > trigger 'Instareal' | Skin/lighting realism | Civitai model licence | Candidate realism LoRA for video (check gating) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 205 | [PuLID-Flux2](https://github.com/iFayens/ComfyUI-PuLID-Flux2) | Identity adapter for FLUX.2 [v4] | Reference face > Apply PuLID > generate | Works with Klein 4B/9B and Dev | Community code; InsightFace non-commercial | Fast 'Me' preview before the LoRA is trained (owner identity only) | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 206 | [Z-Image (Turbo / base)](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) | Open photoreal image model [v4] | Prompt > 8 steps | Best skin detail per step; shift 2 trick | Apache-2.0 | Main photoreal model candidate | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | 879 Z-Image-Turbo LoRAs on Hugging Face, 17 Oct 2026 (SpicyAPI) |
| 207 | [Krea 2](https://www.krea.ai) | Open photoreal image model (Jun 2026) [v4] | Prompt > Turbo 8 steps / Raw for LoRA training | Most 'shot not rendered' look | Krea 2 Community Licence (free < $1M revenue) | Second photoreal model; fine for personal use | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 208 | [FLUX.2 klein 4B](https://huggingface.co/black-forest-labs) | Fast open image + multi-reference edit [v4] | Prompt/refs > 4 steps | Fastest previews | Apache-2.0 | Draft/preview model and PuLID-Flux2 base | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |
| 209 | [Virt-A-Mate (VaM 2)](https://www.patreon.com/meshedvr) | Adult 3D sandbox (VR) [v4] | Pick figure > morph sliders > scene > animate | Photoreal skin, physics, huge morph library; v1.2 beta Aug 2026 | Patreon | Benchmark for realistic adult 3D; learning curve is the lesson to avoid | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | v1.2 beta 11 Aug 2026 (Patreon); no audited usage figure |
| 210 | [Koikatsu Sunshine / Honey Select 2](https://www.illusion.jp) | Adult 3D character creator games (Illusion) [v4] | Slider creator > studio scenes | Deep sliders, Studio Neo posing | Paid (studio closed) | Copy: creator-to-scene flow; avoid youthful anime proportions | failed (<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate ); info from search results | - |
| 211 | [Wild Life](https://www.wildlifegame.com) | Adult 3D game (Unreal) [v4] | Sandbox + story | Realistic UE characters, scene editor | Patreon / Steam | Shows UE-level realism bar; Godot will look less realistic | failed (<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occur); info from search results | - |
| 212 | [Cyberpunk 2077 (Lizzie's Bar, Jig-Jig Street)](https://www.cyberpunk.net) | AAA reference for neon club scenes [v4] | Walk in > NPC dancers > interact | Neon volumetrics, crowd density, diegetic screens | Paid | Mood reference only; no assets or likenesses copied | loaded (HTTP 200, 3 Nov 2026) — reachability check only; facts from the project page/search | - |

## Appendix B — Research notes

See `docs/research/`:
- v4: `evidence_map.md` (Codex evidence map) and `photorealism_notes.md` (photoreal, body, Me, 3D and game research with links)
- v3 site lessons (`v3_sites.md`, Candy.ai first)
- the ComfyUI feature guide
- models and licences
- 3D research
- video research
- the critic passes and adversarial review
