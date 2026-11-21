# Roadmap

This is the short version of the phases in `docs/PRD.md`. Personal use only. The
safety rules in `SAFETY.md` apply to every phase. Research is still moving, so model
names live in `app/model_registry.py`. A desktop file `outputs/model_registry.json`
can replace a role. It cannot turn off the 18+ gate.

Candy.ai is a visual-quality benchmark only. Feature parity is dropped. Do not add
chat, tokens, shop, community, memory, or notification features from the Candy
evidence. `evidence/BUILD-PROMPT.md` on the evidence branch, and earlier parity
notes there, are out of scope. Companion chat in this product, if it is ever
built, stays last and is not a Candy copy.

Codex is publishing six research tracks as `evidence/research/<track>.md`:
photoreal skin and faces, photoreal video, character consistency, video-to-3D,
realistic 3D humans, and three non-explicit Candy benchmark clips (480p, 4 seconds,
a low-tier baseline). Each track will name a default and two fallbacks with exact
settings. Until those files exist, the model ids in `app/model_registry.py` are
placeholders. Change them with `outputs/model_registry.json`. Do not treat today's
ids as a locked pick, and do not hard-code a new workflow for those tracks.

Track 1 settings from evidence commit `fe3525a` are in
`app/pipeline_candidates.json`: SeedVR2 7B int8 image upscale, SUPIR upscale,
the Z-Image Turbo template, and the H2logs Z-Image refine pass. All are
`NOT_RUN`. None is selected. They become active only after a local test sets
`tested_locally` and `selected` in `outputs/pipeline_candidates.json`. The 4090-class
cards are the intended place for upscales, keyframes, and previews. Main video
stays on the desktop GPU. Neither machine is assumed reachable, and this repo
does not download weights.

Track 2 at that same commit is a queue only: Wan 2.2 image-to-video, HunyuanVideo,
LTX, continuation, first/last frame, and upscale, interpolation, and color match.
No track 2 settings are published in that commit.

Research commit `3773d4f` (message `ES-RESEARCH-20261103-005`) added candidates only.
Image finishing order is SeedVR2 7B INT8, then Real-ESRGAN x4plus, then a Z-Image
refine at denoise 0.33, then a no-enhancement control. FLUX.2 Klein 4B is the
first outfit-edit candidate, then Qwen-Image-Edit-2511, then a character LoRA
trained on approved fictional stills. Wan 2.2 14B image-to-video and first/last
frame are the first video templates. HunyuanVideo 1.5 and LTX 2.5 are alternates.
None of these is selected until a local test. Non-commercial models stay behind
a license card. The outfit edit pastes the original pixels back outside the mask
and a second edit starts from the approved source.

Messages `ES-RESEARCH-20261103-006` and `007`, commit `f5b74ad`, add the video
recipes and the video-to-3D order as candidates. Native Wan 2.2 A14B settings
are recorded and not selected. LightX2V and long SVI clips wait until native
motion passes.

Message `ES-RESEARCH-20261103-008`, commit `85a91d3`, finishes the video-to-3D
packet. The first 3D milestone is an owned rest-pose adapter from PromptHMR to
Genesis 9, then glTF, then Godot 4. The map is empty. Fingers are a later
choice. Two-person contact gets an explicit cleanup step.

Message `ES-RESEARCH-20261103-009`, commit `b611551`, sets the export test
order: Genesis 9, Diffeomorphic 5.2.0, Blender 5.2, glTF 2.0, Godot 4.7.2
Forward+. The official Daz to Blender bridge is only the fallback. MetaHuman
and Unreal are not used. Morph names are kept in a manifest, colon-free,
unique, and under 57 characters. Mesh merge stays off until the Godot name
check passes. Correctives are baked or rebuilt in Godot. Nothing has been
purchased. The desktop card is still unconfirmed.

The first live test machine is the M5 Max. Fast stills use Z-Image Turbo. Explicit
keyframes use Chroma1-HD in fp16 or bf16. Short motion proofs use Wan 2.2
TI2V-5B. The 4090 and the unconfirmed PRO 6000 stay as later profiles.

Message `ES-RESEARCH-20261103-010`, commit `3fb51b7`, closes the research
packet. The three reference clips are a floor for resolution and skin detail,
not a ceiling. The video test includes a skin close-up, a full-body turn, and
a two-person hand-hold, reviewed beside those files for blink, identity, feet,
fingers, and flicker. No further spending on the reference site.

Andrew's still-first gate is mandatory. A clip does not start until two keyframes
are scored and the one being animated passes hands, anatomy, contact, skin, and
lighting. Profile contact asks for a depth guide. The contact preset, the motion
prompt limit, the 81-frame cap, and the Remix / SmoothMix / DaSiWa checkpoints
are configurable. They are not a claim that those weights have been run here.

The desktop is still not reachable. Andrew has deferred local setup. The runbook
records the GPU name and VRAM. It does not require a specific card, and it does
not assume an RTX PRO 6000 is online.

## What to work on next

Part V.1 of the PRD wins. The video pipeline is **Still → Motion → Fix → Finish**.

1. **P4V-1 — Video core.** The registry placeholder sends explicit keyframes through
   Chroma and other stills through Z-Image, then Wan 2.2 image-to-video. NSFW, act,
   and anatomy LoRAs are registry slots and stay inside the 18+ section. The age
   check still runs. Exact settings wait on the photoreal-video track.
2. **P4V-2 — Controlled and multi-person motion.** The placeholder names SCAIL-2, with
   Wan 2.2 Animate and VACE-Fun as backups. Their graphs are not built yet.
3. **P4V-3 — Longer takes, repair, and finish.** Placeholders: SVI 2.0 Pro and FLF2V,
   plus a color match. Regional repair is recorded, not yet a brush. The recorded
   finish is SeedVR2 to 1080p, then GIMM-VFI to 30 fps. A Lightning preview is the
   short clip (2 seconds). The quality take is 5 seconds. Until the SeedVR2 and GIMM
   nodes exist, the app records those stages and sets the frame rate with ffmpeg.
4. **P4V-4 — Our own LoRAs.** Train Wan character and motion LoRAs on clips this app
   made. Not started.
5. **P4D — Video to 3D.** Copy motion from a finished clip onto a rigged body.
   GVHMR, PromptHMR, and SAM 3D Body are the current placeholders. Anatomy comes
   from the body asset, not from the video. Not built. Codex is still checking
   whether those tool outputs can be rigged to Genesis 9 or exported as FBX or
   glTF for Godot 4. The import step stays format-agnostic until that note lands.
6. **The Godot game**, after P4D. The first scene is still a Cyberpunk-style walkable
   strip club. Adult interaction stays in a separate 18+ build. NPCs stay fictional
   and 21+.
7. **Everything else.** The Me slot is not built. Companion chat is last.

## Game bodies (chosen, nothing purchased)

Andrew chose **Daz Genesis 9** with **Golden Palace** (female) and **Dicktator** (male),
plus a **Daz Interactive License** for each product that ships in the game. MPFB2 is
the free fallback only.

One possible export, once licenses exist:

1. Build the body in Daz Studio.
2. Send it to Blender with **Diffeomorphic** or **Daz to Blender**.
3. Export **FBX or glTF**.
4. Import that file in Godot 4.

Godot already accepts both formats. The gallery file types already include `.fbx`,
`.glb`, and `.gltf`. Do not write an importer that accepts only one of them, and
do not require a Daz-specific file in the repo. Video-to-3D tools may deliver FBX
or glTF directly. That path stays open.

Licensing, before anyone buys:

- Each product needs its own Daz Interactive License. A personal-use license is not
  the game license.
- The Genesis 9 Starter Essentials Interactive License is about $50.
- Check Renderotica's game-use terms before buying Golden Palace or Dicktator.
- Do not commit Daz files, license keys, or store downloads. Nothing has been purchased.

## Already in the prototype

Phases 1–3 from the earlier plan are in the tree and were tested with a fake ComfyUI.
They are not the current priority. The list is in the previous roadmap sections of
`docs/PRD.md` (Part A). The photoreal stills, the masked outfit edit, and the video
chain runner are in the app. The Scene page, the repair brush, and the saved LoRA-stack
editor from Part V.1 are still later work.

## After this change

1. Keep the evidence pack on its own pull request. Do not merge it.
2. Run the local setup when the desktop card is known. Report the GPU name on
   GitHub issue #1. Do not commit model output.
3. Small pull requests. One subject each. Safety rules stay as they are.
