# Return handoff — Candy integration line (milestone 1, 2026-11-06)

PRIVATE BUILD — NOT FOR DISTRIBUTION. Owner: Andrew Klein. Updated by the Candy team lead at each milestone; the
server kit builder adds its part. The M0–M2 handoff below is kept as history.

## 1. Where things are
- Integration branch: `candy-main`, started at PR #41's head `367e4c39`. Nothing goes to `main` until Ak says.
- Server kit, master USB, first boot and Mac link: `server-kit/` on `server-kit` (kit builder), reading the one
  model lock below.

| PR | What | Head | State |
|---|---|---|---|
| #42 | Merge #40 (`84a324c0`); take #39's features 12/14/18/19 (`dab854bd`); Mac test run green | `4fe666f` | reviewer look (rails) |
| #44 | Ak's exact (version, SHA256) allowlist, 12 entries: the eight audited LoRAs (D-C-18) and four Wan 2.2 14B sibling halves (D-C-20); whole description read, every piece (D-C-19) | `e917ea0` | reviewer look (rails); merges after #42 |
| #43 | One model lock `config/server_model_lock.json` + `config/llm_models.json`, every LoRA checked live by the app's own `civitai_check`; all 11 Wan 14B pairs complete | `5b58dc3` | reviewer look (lists); contains #44, merges after it |
| #45 | Every person a create adds needs a declared 21+ record (P-11 N02) | `e943ab2` | reviewer OK at `3caa278`; small follow-up commit |
| #46 | Every template on the right GPU lane; `app/placement.json` | `1422611` | merged (`518e526`) |
| #47 | Flux.1 dev as a photoreal look | `cfb490b` | CI |
| #48 | Server kit, master USB, first boot, Mac link (`server-kit/`, kit builder) | `f5741cf` | reviewer look (disk, SSH/sudo/firewall) |
| #49 | CI-only draft from `candy-main` into #41's branch | — | never merged |

## 2a. Server kit (from the kit builder)
Server kit: `server-kit/`, branch `server-kit`, PR #48 into `candy-main`, head `f5741cf`; waits for the
reviewer on disk and SSH/sudo/firewall.

**Built:** one master USB (FAT32 `TURINBOOT` = the official Ubuntu 24.04.5 ISO files + autoinstall; exFAT `TURINDATA` =
the models from the lock, a 665-package apt mirror pinned to snapshot `20261105T000000Z`, hash-locked wheels, ComfyUI
v0.43.0 / llama.cpp / Strata sources). The installer copies and checks the store onto the NVMe and powers off; first
boot is offline with a pinned online fallback. Mac link: SSH tunnels with their own `ssh -F` config and Tailscale
scripts with `--accept-dns=false`, all dry-run by default with an undo. The lock loads as 130 rows, 116 in waves 1–3
(388.2 GB on the USB); held and removed rows are skipped; all 11 `comfy_link` types become ComfyUI folders or links;
the Director reads each profile's `lock_ids`; the dashboard shows lock ids only. ComfyUI is pinned to tag v0.43.0
(`426f5eea`), matching the app's contract snapshot. Units: GPU0 :8188 image, GPU1 :8189 video; Director placement
from `app/placement.json` (merged in #46).
*(Lead note after D-C-20: the lock on #43 `5b58dc3` now has 134 rows, 120 of them in waves 1–3 at about 389.5 GB;
the kit loads whatever the lock holds.)*

**Differs from Grok's kit, and why:** the writer picks the USB by serial plus a confirmed volume UUID with no size rule
(the 128 GiB rule made a model-carrying USB impossible and could not protect 1–2 TB data drives); no `dd`, no `sudo`;
models, drivers and software come from the USB, not downloads after boot; Ubuntu's NVIDIA 580 driver with signed
prebuilt modules instead of a floating `nvidia-open` + DKMS (Secure Boot is no longer a blocker); CUDA 12.8.2 pinned;
Docker and the container toolkit dropped (unused); no tokens on the server (`turin-set-tokens` removed); dashboard on
127.0.0.1 with ids only; no open 41641/udp; a sudo allowlist plus a first-login password instead of `NOPASSWD: ALL`; the
kit never creates SSH keys (Ak's key lives in 1Password); Grok's VM key and self-test ISO removed; Grok's blank-NVMe
disk guard kept and tightened (no USB, removable or master-USB disks).

**hardware_pending:** `server-kit/HARDWARE_PENDING.md` HP-01…HP-17 (UEFI boot from the copied files, exFAT import in
the installer, the driver on the real cards, CUDA builds, cooling under burn-in, a VM autoinstall run, the Mac scripts
run by Ak).

## 2. What differs from Grok Bot's pack and kit, and why
- **Not taken (Ak parked it):** the Me path — `me_provenance.py`, `me_liveness.py`, `routes_me_capture.py`,
  `migrate_m3a.py`, `me_provenance.sql`, their tests and patches, Me slot rows, `render_gate`, the liveness model.
  Fictional 21+ characters and a fictional player avatar instead.
- **Not taken:** OD-002's install default `sfw_mode = false` (PR #41's one-time 21+ attestation stays, Ak's answer);
  literal slot labels in git (slot and act labels load from local data); `apply_pack.py` (files were read and taken one
  at a time); the paid remote Director profile; Grok's own LoRA regex gates (the app's `loras.civitai_check` decides).
- **Model lock (#43):** Grok's lock lacked the app's age-check model (the checker would fail closed on every checked
  job), Qwen-Image-Edit-2511, `t5xxl_fp16`, the `lightx2v` Wan pairs, Z-Image base and ControlNet, the tools and every
  candidate family, and shipped files no template loads (Qwen-Image-Edit-2509, `t5xxl_fp8`). The new lock is built from
  the app's own templates: 85 base rows plus 49 LoRA rows by ID only (134 rows); waves 1–3 about 389.5 GB (120 rows),
  wave 4 about 621 GB.
- **LoRAs:** removed `2027766` (identity copy), `1822984` (`.zip`), `2268008` (real-person tag, D-C-16) and `1959747`
  (identity-copy word at character 4082 of its description, which the app's old 4000-character cut missed, D-C-19):
  38 of 42 stay; eight description-only refusals pass by exact version + SHA256 (Ak, D-C-18);
  every Wan 2.2 14B LoRA was missing its other half (route_lora refuses a half) — all 11 pairs are now complete: 7
  sibling halves pass the importer as they are, and Ak added the other 4 to the same exact allowlist (D-C-20), which now
  has 12 entries; descriptions are read in full, every comma piece included (D-C-19); LoRA files get ID-based names and
  no catalog names or trigger words are stored in git.
- **Director models:** both DeepSeek V4.1 Flash 1017 builds kept for the bake-off (Ak); the Strata runtime is pinned
  (v0.2.11, commit `c3b3f503`) and set up on first boot as hardware_pending.
- **GPU lanes:** the app's split is kept (GPU0 image/edit/3D, GPU1 video) instead of Grok's OD-013 split, which put Wan,
  Chroma and Flux on one card and forced a model swap on every still → clip; the Director runs hybrid on GPU0 (experts in
  RAM). HunyuanVideo, LTX and Kandinsky were landing on the image GPU; fixed (#46).
- **#39 Surprise me** fills the look only; #39 rolled a random 21–40 age, which the app's rail forbids.

- **Not yet wired:** the LoRA files the stick pre-caches carry IDs only; the app's LoRA library does not know them yet
  (family, role, trigger words, Wan half). The next step imports each locked LoRA into the library on first run (a
  metadata-only lookup by version id; names and trigger words stay in local files), so route_lora can pair the Wan
  halves and the router can pick by role.

- **For Ak, one line (optional):** to run the full local suite on the Mac, `brew install ffmpeg-full` (keg-only; gives
  the game importer libtheora). Nothing was installed on this Mac; CI runs those checks.

## 3. hardware_pending (never reported as passed)
Every VRAM, speed and quality number; the lane plan and Director placement; LoRA/base compatibility marked unverified;
Flux.1 dev and every candidate family on real weights; the Strata runtime; everything in the server kit's list (boot,
driver, GPUs, cooling, Tailscale).

---

# Return handoff — Stillwater M0 + M1 + M2 core slice

PRIVATE BUILD — NOT FOR DISTRIBUTION. Owner: Andrew Klein. Written Nov 5, 2026
(working copy `/Users/dfuuu/candy/easy-studio`).

Source of truth: `docs/EASY_STUDIO_FINAL_PRD.md` (copied in unchanged). Plan: `docs/STILLWATER_MASTER_PLAN.md`
(r2). Review: `docs/STILLWATER_PLAN_REVIEW.md` (38 findings, four angles). `docs/PRD.md` is marked historical.

## 1. Branch, PR, SHAs

| What | Value |
|---|---|
| Branch | `stillwater-m0-m2-integration` |
| PR | https://github.com/broadwell-northside/easy-studio/pull/41 (base `main`) |
| Branch point | #37 `cursor/lora-workshop-wave-ae2e` at `4988cd752b80ebf2b644a10cb25944f787bf066c` |
| Merged | #36 `cursor/workshop-pack-import-5b8f` at `b5357c3fa31cc9ece37cf9cba15fbc62167dc048` (merge `604191e`) |
| Merged | #38 `cursor/stillwater-beach-3d-f8cc` at `acf2204d5139079760423ffac96c3b1b1d94a136` (merge `f30ad5f`) |
| CI-verified head | `86f93fc` (all checks green); this file lands in the next commit, docs only |

- #38 drift: the PRD and prompt snapshot named `a809ecfe`. The branch had moved one commit
  (`acf2204` "Read the beach plate from the committed files"), CI `test` + `stillwater` were green on it,
  and it merged with no conflicts, so its tip was merged.
- #36 merged without a conflict; git auto-merged `.gitignore`, and the duplicated importer line was dropped.
- Not merged, by instruction: #17, #18, #19, #22, #26, Dependabot #10–#16. No rebase. `d3ba42d` (#29's
  90-minute timeout) was not needed: the `test` job took about 12 minutes of its 45.
- CI job names unchanged: `test` (CI) and `stillwater` (Game).

## 2. What changed, by Session Box item

1. **Plans:** master plan r1 → pessimistic review (UX, ComfyUI/LoRA pipeline, gameplay fun,
   age/identity/consent/secrets) → plan r2 with a change log and a stable-id checklist.
2. **M0 integration:** #36 and #38 merged onto #37 (above).
3. **M0 test:** `tests/m0_integration_tests.py` builds a pack with `job_export_godot` on mock data and runs
   `game/tools/import_easy_studio.py` in dry-run against the real island folder, from Python and from the
   command line. `game/project.godot` and every other island file stay byte-identical; a real import into a
   copy keeps that copy's `project.godot` unchanged too.
4. **M0 flag:** `app/content_mode.py` (studio) and `game/scripts/settings.gd` (game) are the only mappings.
   Fresh install SFW; the 21+ attestation stores `sfw_mode = false` once; an unattested device is always SFW.
   Both sides run `game/tests/fixtures/content_mode_vectors.json`. The #38 plate file had its own `sfw_mode`
   (a third meaning); it now follows Settings, and a full-21 slot with no covered file shows a hold.
5. **M1 Graphic Workflow Editor:** Home is Make · Play · Library with a Settings gear; Classic tools is one
   link at the bottom of Make. Recipes compile to `workshop_still`, `film`, `export_godot` and go through the
   normal `/api/jobs` queue (`app/recipes.py`, `app/routes_recipes.py`, `app/static/make.js`).
6. **M2 slice:** the door-unlock co-op puzzle on the #38 3D shore (`game/tools/puzzle_level.py`,
   `game/data/puzzles/beach_door.json` + `.sha256`, `game/scripts/door_puzzle.gd`,
   `game/scripts/door_puzzle_view.gd`), with Edit this place as a mode of Play.

### Rails touched (all with fail-closed tests)
- Upload ancestry: `_refuse_uploaded_undress` walks `parent` to the root (any upload role refuses; a missing
  parent or a loop counts as an upload). `job_raw` runs the walk on every image it loads. Tests: two-hop edit,
  raw grandchild, raw mask, unit and server.
- Checker-off: `CHECKER_FREE_KINDS` is a frozen list; any kind in neither list is refused while the checker
  is off; the three kinds `server.py` hard-coded moved into `CHECKER_REQUIRED_KINDS`. Snapshot test over
  every registered kind.
- `NODE_DENY_RE` pinned by a test. `ME_SEX`, `me_gate`, `policy_reason`, `still_source_ok`, `export_age`
  untouched and still tested. Age checker threshold, worker and `clamp_age` untouched.
- `op://`: recipe export strips every string containing it at any depth, keys too.

### Bugs found and fixed on the way
- **Wan 2.2 pairs from training kept one half.** `trainer.find_outputs` read the run name's time stamp
  (`_194116`) as a step number and dropped the high-noise file. The old hook then attached the *low* half to
  the high-noise model, and the old test passed only because the template's own lightx2v LoRA names contain
  `high_noise`. Fixed the picker, refuse a half pair, and the test now follows each half to its loader.
- `route_lora(file, unet_filename)` is now the only attach path (inject_loras and the benchmark). An unpaired
  LoRA on a 14B half is a hard error with a plain message. Two older tests that attached one file to both
  14B halves now expect that refusal.

## 3. Checks (exact counts)

CI on `86f93fc` (GitHub Actions, PR #41): CI run `42143423324`, Game run `42143423291`.

| Check | Where | Result |
|---|---|---|
| `ruff check .` | CI `test` · Lint | All checks passed |
| Setup script self-tests | CI `test` | preflight and gpu_smoke self-tests passed |
| gitleaks secret scan | CI `test` | no leaks found |
| `tests/run_tests.py` (mock suite, includes M0, sfw_mode, rails, recipes, puzzle level) | CI `test` | **1164/1164** checks passed |
| `tests/ui_smoke.py` | CI `test` | 0 problems, 0 JS errors |
| `tests/e2e_browser.py` (includes the light-mode Playwright recipe path) | CI `test` | **223/223** browser cases passed |
| `ruff check game/tools` | CI `stillwater` | passed |
| `game/tools/test_import.py` | CI `stillwater` | all importer tests passed (91 PASS lines) |
| `game/tools/puzzle_level.py check` | CI `stillwater` | ok: level file and its sha256 |
| Godot 4.7.2 headless, GL Compatibility (`res://scenes/tests.tscn`, includes the door puzzle load) | CI `stillwater` | **314** checks, all passed |
| Linux and macOS exports | CI `stillwater` | built and uploaded (`stillwater-linux`, `stillwater-macos`) |
| Mac export launch | this Mac, the CI `stillwater-macos` artifact of run `42143423291` | launched to the title screen and the 3D beach with the door puzzle (`docs/screenshots/m2/mac_export_title.png`, `docs/screenshots/m2/mac_export_beach.png`); run with a throwaway HOME holding a confirmed 21+ setting, so the owner's own settings were not touched |

Local runs on this Mac (Python 3.15, Homebrew ffmpeg 9, Godot 4.7.2 from the official release):
`tests/run_tests.py` 1161/1162 (the one failure is the known ffmpeg 9 case below), `tests/ui_smoke.py` clean,
`tests/e2e_browser.py` 223/223, Godot headless 314/314.

Acceptance numbers (mock engine): portrait still of a new fictional adult with a typed age, 5 presses from
Recipes; a film on it, 3 presses via send-to-next (4 from Recipes); export → re-import gives the same
canonical hash; the executed graph hashes the same as the compiled graph for both the still and the film;
one measured mock latency, 0.423 s submit-to-done through `/api/jobs` (`docs/M1_MOCK_LATENCY.json`; about
1.3 s in the browser from Make it to the picture). No GPU timing is claimed.

Found by the Mac launch check and fixed here: the #38 beach read its `.gltf`, `.buffer` and stand-in PNG files
straight from the project, but exports only carried Godot's imported copies, so the exported Mac build showed
an empty beach. Those files are now marked "keep" and shipped as they are.

## 4. Before and after (UX)

| Before (#37) | After (this branch) |
|---|---|
| First screen: Create, with a 12-tab sidebar (`docs/screenshots/desktop_create.png`) | Home: Make · Play · Library + gear (`docs/screenshots/m1/mobile_home.png`) |
| Workshop features spread over tabs | Make → recipe cards (`docs/screenshots/m1/recipe_make_light.png`) |
| A still took a full Create form | Portrait still recipe: 5 presses for a new adult with a typed age (`docs/screenshots/m1/recipe_portrait_light.png`) |
| A film from a still on the Video page | Film recipe from send-to-next: 3 presses (`docs/screenshots/m1/recipe_film_light.png`) |
| Send to island, then run the importer by hand | Send to the island + "Check it against the island (dry run)" (`docs/screenshots/m1/recipe_island_dry_run_light.png`) |
| Walkable beach with one stand-in plate (empty in the Mac export) | Door puzzle on the beach: pads, key, Mira's plate, door with two lamps (`docs/screenshots/m2/beach_door_puzzle.png`, Mac export `docs/screenshots/m2/mac_export_beach.png`) |
| — | Desktop doors from the UI smoke run: `docs/screenshots/desktop_home.png`, `desktop_make.png`, `desktop_play.png`, `desktop_library.png` |

The island art is placeholder by design this session (no model downloads, no GPU, no generated images in
git). Photoreal plates come from the recipes on the owner's GPU box.

## 5. Staged, not removed
Heavy workshop features stay staged: 6 checkpoint resume · 12 outfit try-on · 14 face-consistency check ·
18 pre-export hold · 19 Surprise me (and no Surprise-me age writing). Light helpers 11, 15, 16, 17 are inline
in the recipe page. The node drawer is read-only; an editable canvas is a later decision.

## 6. Not run / limits (never reported as PASS)
- Real GPU, real weights, RunPod, Civitai downloads: not touched. Mock engine only.
- Local Mac only: `tests/run_tests.py` "sprite sheet from video" fails because Homebrew ffmpeg 9 removed
  `-vsync`; CI's Ubuntu ffmpeg passes it. `game/tools/test_import.py` cannot convert clips locally because
  Homebrew ffmpeg 9 has no libtheora; CI runs it. Worth knowing: the importer on this Mac will fail on clips
  until ffmpeg with libtheora is installed.
- Game feel and frame rate: not judged (not a gate). Owner playtest item.
- Editing in-game drafts writes positions only; keeping a draft is `python3 game/tools/puzzle_level.py promote`.
- `docs/M1_MOCK_LATENCY.json` is rewritten by every local `tests/run_tests.py` run (like `docs/e2e_last_run.json`),
  so expect a small diff after running the tests.
- `game/export_presets.cfg` now includes `*.png` raw files; the `keep` `.import` files are what fixed the empty
  Mac beach, so the next session can narrow that filter to the plate pictures if pack size matters.
- The #38 scripts' Godot `.uid` files are generated locally on first import and were not committed (as on #38).

## 7. Owner directions recorded this session (not built here)
- Nov 5, 2026, in chat: the owner (40) wants `Me` to have the same scope as other characters, including
  nudity, and says the game is private and only he uses it. This session kept the `Me` checks as the
  Session Box requires. The M3 `player_in_scene` session should take this up with owner sign-off. Open
  point for that session: the app cannot confirm that uploaded photos are of the owner (the main risk with
  explicit images of a real person); one option is training `Me` only from photos captured in the app.
- Nov 5, 2026, in chat: the owner wants a realistic adult look (Civitai LoRAs, full anatomy for fictional
  21+ actors), not cartoon placeholders. First item in M3 below.

## 8. Next Session Boxes (queued, not started)

**M3 — party pack, builder, look test.** In this order: (0) put real renders on the island: a kept still or
clip from the recipes, background removed, becomes Mira's plate (covered/full slots follow `sfw_mode`); mat
& balance game → spin the bottle / truth or dare / wagers (cards over cached plates) → Read the Person (solo →
opposite-sex partner → vs. 1–3 rival couples; Person Cards, signal wheel, utility AI) → Direct Scene Studio;
Level & Scene Builder (pose/socket graph, wardrobe track, dare deck authoring, all through
`game/tools/puzzle_level.py`-style single validators); `player_in_scene` flag for synthesized `Me` scenes with
allowed/refused job-kind tests and owner sign-off (see §7); 60 s engine look test (Godot 4 Forward+ vs Unity 6
LTS C# + URP; UE5 only if a human will own binary scenes; no HDRP).

**M4 — production.** `schemas/character_asset.json` exporters in headless Blender (one `.glb`, one armature,
meters, +Z, A-pose, garments skinned to it, 8 influences, shape keys, `MASK_<garment_id>` body masks, texture
sidecar `base_color`/`normal`/`roughness`/`metallic`/`occlusion`/`sss_mask`/`thickness`, hair cards); Unity 6
LTS C# + URP port (or the look-test winner) with custom skin, water and hair-card shaders; cloth and hair per
engine; 4-star checklist.
