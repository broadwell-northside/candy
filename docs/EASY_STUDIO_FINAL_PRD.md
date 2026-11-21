# Easy Studio + Stillwater — Final Product Requirements Document (PRD)
PRIVATE BUILD — NOT FOR DISTRIBUTION. Owner and sole user: Andrew Klein. Version 2.0 (final, post-audit), Nov 5, 2026. Repo: `https://github.com/broadwell-northside/easy-studio` (private).

## 0. Precedence and how to use this file
- **If two instructions disagree, this PRD wins.** The master prompt is how to implement it, and the prompt's **Session Box** wins over any milestone here for what gets built in a given session. `GAMEPLAY_PUZZLES_SCENE_STUDIO_3D_SPEC.md` and `STILLWATER_DESIGN.md` are reference: they add detail, never deliverables.
- **`docs/PRD.md` in the repo is historical and superseded.** Ignore its engine choice, its club milestone, and its production recipes. Do not quote it into new docs. Do not implement it.
- This PRD describes the whole product (M0–M4). Each build session implements only the milestone its Session Box names.

---
## 1. Vision
One private, local-first creative suite with **two co-equal products on one shared render backend and one shared asset library**:
- **Pillar A — Easy Studio Graphic Workflow Editor.** Make ComfyUI-grade stills, short films, and scene renders without wiring nodes: recipes and plain-English stage forms, with the real ComfyUI graph available as a read-only drawer.
- **Pillar B — Stillwater.** A private 21+ single-player island game whose characters, plates, and props come from Pillar A.

Quality bar: start with a fast MVP; finish at a genuine **"4-star" (AA-grade) look**. In the MVP, 4-star pixels come from offline renders (ComfyUI plates, later Blender Cycles stills) shown inside a real 3D Godot scene; real-time 4-star rendering comes with the production engine (M4).

## 2. Goals and non-goals
**Goals**
1. Andrew makes a still or a short film from a recipe in five clicks or fewer, without seeing nodes.
2. Andrew plays and edits puzzle places on the island without code.
3. Five game modes eventually ship (§6), built in a fixed order on shared plate-and-hotspot code.
4. Assets follow one canonical character contract (§11.4) so MVP work carries forward.
5. Everything runs locally; nothing is distributed.
**Non-goals:** see §15.

## 3. Persona
**Andrew — solo creator, owner, only player.** Non-coder day to day; wants calm, obvious screens; never wants features removed, only simplified; plays on a Mac; owns a home Linux box with two RTX PRO 6000 Blackwell cards (96 GB each; profile `rtx_pro_6000` is `confirmed: false` in `machine_profiles.json`). AI coding agents write almost all of the code.

## 4. Shared architecture
```
Easy Studio (local web)            Render backend                 Stillwater (Godot 4, Mac)
 Make · Play · Library  ── jobs ─▶ existing job kinds ─▶ ComfyUI   ◀── packs (export_godot → importer)
 (Pillar A recipes)                (checker, rails)    8188/8189   asset library (sha256, lineage)
```
- **One runner.** The editor compiles a recipe into one of the existing job kinds — `workshop_still`, `keep_face`, `refine_skin`, `refine_anatomy`, `film`, `prop`, `export_godot` — and submits that kind. No parallel runner. `raw` stays the opaque importer path and is not the recipe runner.
- **ComfyUI client:** the 0.43 contract from #23 (completion, cancel via `POST /api/jobs/{id}/cancel`, no global `/interrupt`, temp outputs are not saved). Do not change `classify_job`, `cancel`, or the temp-preview rule.
- **Hardware map (when the owner turns hardware on; build/CI uses the mock engine only, no weight downloads, no GPU calls):** process `8188` pinned to GPU0 (Z-Image family); process `8189` pinned to GPU1 (Wan 2.2 14B high + low). Qwen-Image-Edit-2511 and Chroma1-HD require a family change; a family change calls ComfyUI memory-free on that process before the next submit. Two processes never share a GPU. The Mac runs the game, voice, and UI; it is not the 14B film machine (its profile is Wan 5B).
- **Asset library:** content-addressed (sha256) items with `content_rating` (`sfw` | `full_21`), license card (`private_use: yes` required to run), and lineage (`parent` chain).

## 5. Pillar A — Graphic Workflow Editor (co-equal pillar, milestone M1)
### 5.1 How it works
- **Make opens Recipes.** A recipe is a short form for a result: portrait still, keep-face still, skin refine, film from a still, 3D prop, send to island, LoRA strength test, and more over time.
- **Stage blocks = the opened form, in a fixed order:** `Subject → Look → Pose → Scene → Camera → Quality → Output`. Each stage can be turned on or off and its values saved as a preset. **Stages cannot be reordered.**
- **Model-family handoff is pixels, never latents.** A stage output is a decoded picture plus a sidecar (`width`, `height`, `seed`, `model_family`, `workflow_id`, `sha256`). The compiler inserts it as the next template's `LoadImage`. It never wires a latent from one family (Z-Image `KSampler`+`EmptySD3LatentImage`; Chroma1-HD `SamplerCustomAdvanced`+`CFGGuider`; Qwen-Image-Edit-2511 `VAEEncode`+`FluxKontext`; Wan 2.2 dual `KSamplerAdvanced`) into another.
- **Quality stage never writes `steps` on a template with two `KSamplerAdvanced` nodes** (Wan's shared high/low split; `apply_advanced()` already refuses this).
- **Node graph drawer:** read-only view of the compiled ComfyUI API JSON, off by default, not a tab. (Editing graphs is a later, separate decision.)
### 5.2 Required behaviour
- **Node titles preserved:** compiled templates keep `POSITIVE`, `NEGATIVE`, `SEED`, `START IMAGE`, `SIZE` so `fill()`/`set_in()`/`set_seed()` keep working.
- **Canonical hash (own recipes only):** API JSON after `finalize()`, keys sorted, no `_meta`, no UI layout. Round-trip hash applies only to recipes this app compiled.
- **One-way import:** ComfyUI UI JSON, PNG/WebP metadata, or any graph this app did not compile is stored as bytes, shows missing models and node types, and can run as an opaque `raw` graph. It is not decompiled into stages and its re-export hash is not claimed. No custom-node installs, even after a confirm.
- **Wan 2.2 14B LoRA router:** one function, `route_lora(file, unet_filename)`, is the only attach path for `inject_loras` and the workshop benchmark. A character LoRA on 14B must be a high/low pair; a 14B stack with an unpaired LoRA is a hard error. The fast template's `lightx2v` LoRAs stay in the template and are not a stage field (no double stacking). `wan_expert` on the usage card must match the pair keys or the card is incomplete.
- **Cache key:** sha256 of canonical inputs — template id, seed, every LoRA filename with model and clip strength, garment state, `sfw_mode`, camera id, source image sha256. A missing field is a cache miss.
- **Latent previews are ephemeral** pixels in the job tray: never library items, thumbnails, or `LoadImage` sources.
- **Recipe files are local** (`.esrecipe.json`): export strips every string containing `op://`; the editor never displays, logs, or writes a secret; no RunPod client, no token field, no model download.
- **Click rule:** a click is a pointer press that changes the result; typed ages and seeds count. Defaults are allowed only for camera and size. Age never has a default.
### 5.3 M1 acceptance (mock engine)
From Recipes: (a) a portrait still of one fictional adult with a typed stated age, and (b) a film job that calls the existing `film` job on that still — each in five clicks or fewer, without the node drawer. Export of that recipe re-imports to the same canonical hash. One measured mock-job latency is recorded; no GPU timing is claimed. Two-actor stills come later and are not the M1 gate; two-person contact stays a known limit and the existing warning stays on screen.

## 6. Pillar B — Stillwater
### 6.1 Five game modes (the full vision) and the only legal build order
1. **Door-unlock co-op puzzle** — pressure pads, prop passing, light beams; plates + hitboxes; loaded from one validated JSON file. *(First: M2.)*
2. **Mat & Balance Hotspot game** (Twister-style) — spinner, held poses, balance meters, props on hotspots; same plate-and-hotspot code. *(M3.)*
3. **Spin the Bottle / Truth or Dare / Wager-Forfeit** — a state machine (`idle → spin|draw → target_select → card_reveal → accept|swap → perform → resolve → score`) over cards that point at already-rendered plates; not a new renderer. *(M3.)*
4. **Read the Person: solo → opposite-sex partner → vs. 1–3 rival couples** (headline social loop) — hidden Person Cards read via visual tells, no-text partner signal wheel, utility-AI rival couples. *(M3.)*
5. **Direct Scene Studio** — open any authored scene and play/render it. *(M3.)*
Gameplay logic (utility AI, bottle physics, comfort meters, round timers) is code; JSON holds content and tuning, not behaviour.
### 6.2 Research basis
No French game literally titled "Blue Lagoon" was verifiable. Closest verified match: *Emmanuelle* (Coktel Vision, 1989; Amiga/Atari ST/MS-DOS; Muriel Tramis) — hidden per-character personality chosen through text menus. We keep the hidden-personality puzzle and replace text with body-language tells and physical interaction. Sources: https://en.wikipedia.org/wiki/Emmanuelle_(video_game) · https://www.mobygames.com/game/3838/emmanuelle-a-game-of-eroticism/ · https://www.atarimania.com/st/files/emmanuelle_tomahawk_uk_manual.pdf
### 6.3 Presentation stages
- **Stage 1 (M2–M3):** photoreal plates in the 3D Godot scene (PR #38 adds a walkable 3D beach with a plate at eye level). Plate sockets are `{u, v, depth}`. Cinematic shot lists use cached plates.
- **Stage 2 (M4+):** rigged characters on the canonical armature; bone sockets; IK; playable control. No IK on plates.
### 6.4 Existing game content stays
`chat_brain.gd` (Ollama seam), `dialogue_runner.gd`, and `scenes.json` beach scenes stay in place and off the new modes' critical path. Nothing is deleted.
### 6.5 Level editing
M2: "Edit this place" is a mode of Play for the one puzzle JSON. The full Level & Scene Builder (pose/socket graph, wardrobe track, dare deck authoring) is M3. Python writes level JSON plus its sha256; Godot loads and checks the hash. **One schema implementation (Python)**; Godot does not re-validate with a second schema (Godot 4 reads JSON numbers as floats — use the island's `whole_number()` helper).

## 7. Content mode model (one flag)
- One flag, `sfw_mode`, stored in studio settings and `user://settings.json`. Old fields map in one place: studio `area == "adult"` ⇔ `sfw_mode == false`; game `adult_content` ⇔ `sfw_mode == false`. No third meaning.
- **Fresh install: `sfw_mode = true`** until the existing 21+ attestation is stored (studio 21+ checkbox; game `age_gate_version = 21`). **On passing that attestation, `sfw_mode` becomes `false` (full 21+ mode)** — the owner's chosen default for an attested adult — and the SFW toggle stays one click away.
- `sfw_mode = true`: visible garment is exactly one of `swimwear`, `resort_wear`, `outerwear`; `unclothed_base` and `underlayer` are not drawn; nodes with `requires_full_21_mode: true` or `sfw_safe: false` are unreachable; `intimate_contact` sockets off; `full_21` gallery items masked; Holiday ceiling Tier 1 only. If a covered variant was never rendered, show a calm hold card — never the full image and never a silent regen.
- `sfw_mode = false`: all creator-authored content for fictional 21+ actors, up to Tier 4.
- The player gate is an **attestation**, not proof of age. Fail-closed applies to fictional actor records, checker-off, and missing stated ages. No numeric player age is added.
- Validators: `sfw_safe` and `requires_full_21_mode` are both required on every node/card; a card with `consent` other than `mutual`, or an actor without a consent entry, does not load.

## 8. Always-on rails (cannot be disabled; tests define done)
1. **Fictional actor age:** typed integer ≥ 21 stored only when a person types it into that character's field; missing/invalid/under-21 rejected at every entry point; never defaulted, inferred, or clamped. Do not change the age-checker threshold, worker, or `clamp_age`. The checker is a helper (stated recall about 0.70), not a guarantee; authoring rules and refusals are the primary control. Surprise-me age writing is out until its own session.
2. **`Me`:** the owner's player avatar, trained only from photos he attested are his and of an adult. Keep `me_gate`, `policy_reason`'s player block, `still_source_ok`, `export_age`'s real-person refusal, and `ME_SEX` compiling and tested. A later session (M3) may add one flag, `player_in_scene`, allowing a synthesized `Me` avatar in scenes for job kinds named in its tests (allowed and refused lists), with owner sign-off on scope. Until then, no images of `Me` in new modes.
3. **Uploaded photos:** clothing-removal edits of an uploaded photo stay blocked, **including any image whose ancestor was an upload**: `_refuse_uploaded_undress` walks `parent` to the root, and `job_raw` applies that walk to every loaded image.
4. **Checker-off fails closed:** any new job kind is refused while the appearance checker is off unless added to `CHECKER_REQUIRED_KINDS` in the same change. Recipe runs use kinds already on that list.
5. **Identity:** no likeness LoRAs, face-swap, or real people other than `Me`; keep `NODE_DENY_RE`; do not weaken it to import third-party graphs; no face-recognition service; keep the attestation checkbox.
6. **Consent:** every multi-actor scene requires `consent: "mutual"` per actor; no coercion/incapacitation states.
7. **Resources:** refuse `poi`, `minor`, `TakenDown`; verify sha256; `private_use: yes` to run.
8. **Secrets & spend:** `op://` references only, stripped from exports; never printed or logged; no paid GPU/RunPod without explicit approval.
9. **Repo hygiene:** do not commit generated images, LoRA weights, or `Me` photos; the island keeps placeholder art; imported packs live in a gitignored directory (CI uploads `stillwater-linux`/`stillwater-macos` artifacts).
10. **Disk:** on the Mac, check `df -h ~` before large writes; stop if under 50 GB would remain.
11. `PRIVATE BUILD — NOT FOR DISTRIBUTION` notices; keep separate from Village & Vines and BlueNord.
12. Third-party licenses: MetaHuman content may not be used to train or test AI models (MetaHuman Creator EULA §1.3).
A session that deletes `ME_SEX`, `_refuse_uploaded_undress`, or any rail above to make a test pass has failed.

## 9. UX — three calm doors
- **Home: `Make` · `Play` · `Library`; Settings is a gear.**
- **Make** opens Recipes (Pillar A). Stage blocks are the opened form. The node drawer is read-only and off by default.
- **Classic tools:** the existing 12 tabs (Create, My characters, Wardrobe, Pose, Scene & background, Add objects, Photoshoot, Video, 3D model, Game assets, Gallery, Advanced, Setup) stay available under one "Classic tools" link at the bottom of Make. Nothing is deleted; nothing is added to the home screen. No Classic redesign beyond #27.
- **Workshop features live inside the cards they belong to,** never as nav items. 19 features: 1 LoRA import (file/Civitai/catalogue, sha256, gates) · 2 Make LoRAs (ai-toolkit) · 3 author notes + one-press triggers · 4 conflict detector · 5 strength benchmark (= LoRA strength recipe) · 6 checkpoint resume · 7 `Me` twin · 8 one-press sample prompt · 9 my tested presets · 10 Stack Coach · 11 drag-to-next-step (= "send to next recipe") · 12 outfit try-on · 13 beach-day preset · 14 face-consistency check · 15 shot board (= strip on the film recipe) · 16 tooltips + phase estimates · 17 before/after (= compare control on a finished job) · 18 pre-export hold · 19 Surprise me. PR #37 ships 1–5, 7, 8, 10 and a training practice run. Light inline helpers (11, 15, 16, 17) fit M1; heavy ones (6, 12, 14, 18, 19) are staged to their own sessions.
- **Play** opens the island; "Edit this place" is a Play mode. **Library** is the asset library.
- Calm sand/sea/clay, light + dark, plain-English tooltips.

## 10. Level & Scene Builder (M3)
Level graph (zones, spawns, cameras, lighting, puzzle objects, routines, win/lose rules); pose, socket & contact graph (creator-authored nodes, Stage 1 `{u,v,depth}` sockets or Stage 2 bone sockets, prop slots, tags, transitions, reaction states; required `sfw_safe`, `requires_full_21_mode`, `actors[]`, `consent`); wardrobe track over the garment layers; Dare & Forfeit Deck (empty schema until M3 authoring); render bindings = a Pillar A recipe + LoRA stack + seed + camera. Content is open-ended for fictional 21+ actors within §7–§8.

## 11. Engine strategy — MVP to 4-star
### 11.1 Staged path
| Stage | Engine | Purpose |
|---|---|---|
| M0–M2 | Web studio + **Godot 4** (`game/`) | Prove fun fast. CI renderer stays **GL Compatibility**; do not switch `project.godot` to Forward+. PR #38's 3D shore may use Forward+ on desktop. 4-star pixels = offline ComfyUI plates (later Blender Cycles stills) inside the 3D scene. |
| M3 look test | Godot 4 Forward+ vs **Unity 6 LTS (C# + URP + custom shaders)** (UE5 only if a human will own binary scenes) | Same beach/pool scene and one Blender `.glb` character; timed stills and a 60 s camera move on the Linux box and Mac. A benchmark, not a port. |
| M4 production | **Unity 6 LTS, C# + URP** (recommended) | Port to the winner of the look test; custom subsurface skin, water, and hair-card shaders. Godot remains the fallback and stays playable. |
### 11.2 Why the audit overturned Unreal Engine 5
AI agents write almost all of this code and Andrew plays on a Mac. UE5 `.uasset`/`.umap`/Blueprint files are binary and opaque to an agent; the editor plus Derived Data Cache threatens the Mac's 50 GB floor; Lumen, Nanite, Substrate, and Groom are weakest on macOS and in headless Linux CI; MetaHuman's autorig is a cloud service (conflicts with local-only `Me`), its bodies are the wrong body for this game, and its content cannot be used for AI training. `app/g9_adapter.py` already records `not_adopted: metahuman_unreal`; it stays parked (no Daz import, no Genesis 9 purchase).
### 11.3 Why Unity 6 LTS + URP is the production recommendation
- C# code and YAML-text `.unity`/`.prefab` scenes are diffable and writable by an agent.
- Mac editor and Mac builds are first-class.
- Andrew prefers Unity.
- **URP, not HDRP:** Unity marks HDRP deprecated in Unity 7 (supported to end of 2029) and puts new features into URP.
- Licensing for a private, non-distributed build: Unity's current Terms of Service restrict obscene or illegal material in use of its Offerings; the "sexually explicit images" clause present in Dec 2024 was removed by Aug 2025; Unity Ads/IAP and the Asset Store forbid sexual content, and this project uses none of them. Re-check the terms at M3.
- Honest limits: URP does not give strand hair, Lumen-class skin, caustic water, or cloth at the 4-star bar out of the box — those are custom shaders/hair cards built in M4; Shader Graph/VFX Graph assets are awkward for agents, so prefer hand-written HLSL.
- Sources: https://unity.com/topics/the-path-to-a-single-render-pipeline-in-unity-7 · https://unity.com/topics/render-pipelines-strategy-for-2026 · https://unity.com/legal/terms-of-service · https://unity.com/legal/asset-store-content-transparency · https://www.unrealengine.com/eula/unreal · https://legal.epicgames.com/epicgames/content-guidelines · https://www.metahuman.com/license · https://www.unrealengine.com/en-US/eula/mhc
### 11.4 Blender and the canonical character asset contract (`schemas/character_asset.json`)
- **One runtime file per character: `.glb`.** One armature, meters, facing `+Z`, A-pose rest; all garment meshes skinned to that one armature; eight skin influences; Apply Modifiers off; shape keys on; no second armature copy.
- **Garment layers:** `unclothed_base → underlayer → swimwear/bikini → resort_wear → outerwear`. Each garment has `body_mask` (vertex group `MASK_<garment_id>`); the runtime hides those body vertices instead of z-fighting cloth against skin. SFW draws exactly one of `swimwear`, `resort_wear`, `outerwear`.
- **Texture sidecar** (not implied by glTF): `base_color`, `normal`, `roughness`, `metallic`, `occlusion`, `sss_mask`, `thickness`. ORM packing is an engine concern.
- **Sockets:** Stage 1 plate sockets `{u, v, depth}`; Stage 2 bone-name sockets on the canonical armature (with snap offsets in meters).
- **Deferred to engine-specific M4 work:** cloth sim, strand hair, ARKit-style face shapes (MPFB2 does not ship them). Hair cards may be a mesh. No Alembic groom deliverable. No FBX/USD multi-export.
- **Blender role:** DCC hub (MPFB2 CC0 base body, rigging, shape keys, garments, bakes including LoRA-derived skin maps, Cycles look-dev stills). Headless Blender Python exporters arrive at M4; until then only the schema and a fixture exist. `app/g9_adapter.py` is not the exporter or the skeleton.

## 12. Non-functional requirements
- Local-first and private; no telemetry; nothing distributed.
- Mock engine in build and CI; no weight downloads in build sessions.
- Performance: record measured mock-job latency in M1; no GPU timing claims until hardware is confirmed; frame rate is not an M2 gate, but the Mac export must launch to the title screen.
- Jobs survive refresh; cancel always works; atomic writes; content-addressed library.
- CI: keep the job name `test` (45-minute timeout on #37); Godot 4.7.2 headless on GL Compatibility; Linux and macOS exports.
- Calm UI (§9); five-click recipe results.

## 13. Milestones
| M | Name | Exit criteria |
|---|---|---|
| M0 | Integration | One branch from #37 (`4988cd75`) with #36 (`b5357c3f`) merged (and #38 `a809ecfe` if green); passing exporter-to-importer dry-run test (island `project.godot` byte-identical afterwards); rails tests green; `sfw_mode` one-place mapping. |
| M1 | **Graphic Workflow Editor MVP** | Make/Play/Library home; Recipes for portrait still, one-actor film, send-to-island; fixed-order stages; read-only node drawer; Classic tools link; §5.2 behaviours; §5.3 acceptance. |
| M2 | Game core vertical slice | Door-unlock puzzle playable on the existing beach (PR #38 3D shore if merged), plates + hitboxes, one validated JSON + sha256, "Edit this place"; no renderer change in CI. |
| M3 | Party pack + builder + look test | Mat game → spin-the-bottle/dare/wager → Read-the-Person vs 1–3 couples → Direct Scene Studio; Level & Scene Builder; `player_in_scene` flag with tests; engine look test (§11.1). |
| M4 | Production pipeline + port | Blender `.glb` exporters per §11.4; Unity 6 LTS URP port (or the look-test winner) with custom skin/water/hair-card shaders, cloth and hair per engine; 4-star checklist. |

## 14. Acceptance criteria (release level)
1. M0–M2 exit criteria pass on CI with the mock engine.
2. Every rail in §8 has an automated test that fails closed.
3. `sfw_mode` behaves as §7 in studio and game, including the hold card.
4. 4-star checklist (M4): subsurface skin with `sss_mask`/`thickness`; hair cards or strands; dynamic GI and reflections; water with foam and caustics; cloth on garment layers; facial animation; cinematic camera with depth of field; stable frame rate on target hardware (measured, not assumed).
5. `GROK_BOT_RETURN_HANDOFF.md` lists branches, PRs, SHAs, check counts, screenshots, and the next session's box.

## 15. Out of scope
Distribution or public hosting; multiplayer; companion/chat-relationship features as a product goal; real people other than `Me`; minors or youthful depictions; non-consensual scenarios; paid cloud GPU without approval; buying Genesis 9 or Daz content; installing Unreal; custom-node auto-install; mobile/console; monetization.

## 16. Six-axis pessimistic audit (distilled; 42 findings, all applied)
| Axis | Key findings | Applied fix |
|---|---|---|
| 1 Workflow Editor | Free block reorder = second ComfyUI; model latents are incompatible; third-party imports cannot round-trip hashes; Wan LoRA pairs attach two ways; no VRAM scheduler; previews could bypass the checker; cache keys missing seed/LoRA/`sfw_mode`; two-actor 5 s film gate contradicts code; a new runner would skip safety | Fixed-order stages with pixel handoff; own-recipe hash only, one-way import; `route_lora`; GPU pin + memory-free; ephemeral previews; full cache key; one-actor M1 gate; compile to existing job kinds |
| 2 Engine | UE5 binary scenes, Mac weakness, DDC disk use, MetaHuman cloud/body/training limits; Unity HDRP sunset; Godot Forward+ in CI is fragile; mixed-machine performance claims; `docs/PRD.md` outvotes new docs | Godot MVP on GL Compatibility; offline 4-star plates; M3 look test; Unity 6 LTS URP production target; measured numbers only; `docs/PRD.md` marked historical |
| 3 Blender/formats | glTF/FBX/USD/Alembic are different characters; no canonical skeleton; SSS/ORM outside glTF core; garment clipping; cloth/ARKit don't cross formats; plate vs bone sockets | One `.glb` contract; one armature; body masks; texture sidecar; separate socket schemas; cloth/hair/faces deferred |
| 4 Scope & git | Three divergent lines, not one stack; clean merge ≠ tested pipeline; exhaustion test matrix; current game is chat + dialogue; JSON doesn't make behaviour; double validators drift | Exact topology + merge map; exporter→importer test; one vertical slice per session; keep existing game content off the critical path; logic in code; one schema implementation |
| 5 UX | 12-tab cockpit; features as pages; five apps; click budget hides required fields | Make/Play/Library; Classic tools link; features inside cards; strict click rule, no age defaults |
| 6 Guardrails | `Me` through dare/wardrobe in one pass is a refusal hazard and contradicts shipped checks; undress block one hop deep and skipped by `raw`; checker allow-list fails open; three content switches with opposite defaults; `op://` leak via recipe export; CI artifact upload; age checker treated as a guarantee; keyword rails mistaken for identity understanding; loose group-age wording | Keep `Me` checks, later `player_in_scene` flag; ancestry walk; new kinds must join `CHECKER_REQUIRED_KINDS`; one `sfw_mode` mapping, fresh install safe; strip `op://`; no generated assets in git; don't touch checker thresholds; keep `NODE_DENY_RE` and attestation; one-actor M1 |
