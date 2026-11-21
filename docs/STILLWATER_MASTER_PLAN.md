# Easy Studio + Stillwater — Master Plan (M0–M4)

PRIVATE BUILD — NOT FOR DISTRIBUTION. Owner and only user: Andrew Klein.

Revision r2 (Nov 5, 2026): r1 revised after the pessimistic review; the change log is §12. Written from `docs/EASY_STUDIO_FINAL_PRD.md` (the product source of truth, copied
into this repo unchanged). `docs/PRD.md` is historical and superseded; nothing here comes from it.

How to read this file:
- The PRD says *what*. This plan says *how*, in the order it gets built.
- Each build session builds only what its Session Box names. This session's box is M0 + M1 + M2 (core slice).
  M3 and M4 are planned here so the early work does not paint them into a corner. They are not built yet.
- A pessimistic review of this plan is in `docs/STILLWATER_PLAN_REVIEW.md`.

---

## 1. Where we start (checked on Nov 5, 2026)

| Line | Branch | Tip | What it holds |
|---|---|---|---|
| Studio | `cursor/lora-workshop-wave-ae2e` (#37) | `4988cd75` | Studio, ComfyUI 0.43 client (#23), calm screens (#27), guided steps (#31–#35), LoRA workshop (#37). No `game/`. CI `test` green. |
| Island | `cursor/workshop-pack-import-5b8f` (#36) | `b5357c3f` | Godot island shell (#24), calm island screens (#28), 21+ gate (#30), pack importer (#36). CI `test` + `stillwater` green. |
| Island | `cursor/stillwater-beach-3d-f8cc` (#38, on #36) | `acf2204d` | Walkable 3D beach, Stage 1 plate, glTF level, headless on GL Compatibility. CI green. The PRD snapshot names `a809ecfe`; the branch moved one commit since. |
| Design | `cursor/stillwater-design-c384` (#26) | `3507373` | `docs/STILLWATER_DESIGN.md` only. Not merged (reference only). |

- #36/#37 merge base is `main` (`873baa4`). Only `.gitignore` overlaps.
- #29's tip `d3ba42d` (90-minute CI timeout) is not in #31–#37. It is cherry-picked only if the `test` job times out.
- #17, #18, #19, #22 and Dependabot #10–#16 are left alone.
- Baseline on this Mac: `tests/run_tests.py` passes 931 of 932. The one failure ("sprite sheet from video") is local
  only: Homebrew ffmpeg 9 removed the `-vsync` option. CI's Ubuntu ffmpeg still has it.

## 2. Shared architecture

```
Easy Studio (local web)               Render backend                     Stillwater (Godot 4, Mac)
 Home: Make · Play · Library ─ jobs ─▶ existing job kinds ─▶ ComfyUI      ◀── packs (export_godot → importer)
 Make → Recipes → stage form           (rails, checker)       8188 / 8189     asset library (sha256, lineage)
```

- **One runner.** A recipe compiles into one existing job kind and is submitted to the same `/api/jobs` queue:
  portrait still → `workshop_still`, one-actor film → `film`, send to island → `export_godot`.
  `raw` stays the opaque importer path and is never the recipe runner.
- **ComfyUI client:** the 0.43 contract from #23 is not changed (`classify_job`, cancel via
  `POST /api/jobs/{id}/cancel`, no global interrupt, temp outputs not saved).
- **Hardware map** (owner switches hardware on later; this session uses the mock engine only):
  process `8188` → GPU0 → Z-Image family (Z-Image, Chroma1-HD, Qwen-Image-Edit-2511 when the family changes);
  process `8189` → GPU1 → Wan 2.2 14B (high + low). A family change on one process calls ComfyUI memory-free
  on that process before the next submit. Two processes never share a GPU. The Mac's own profile is Wan 5B.
  Lives in `app/hardware_map.py`; a JSON file in the outputs folder can override it.
- **Asset library:** every item is a file plus a JSON record with `parent` lineage. Recipe results add a
  `sha256` and the recipe cache key.

## 3. Rails mapped to code and tests

| # | Rail | Where it lives | Test that fails closed |
|---|---|---|---|
| 1 | Typed actor age ≥ 21, never defaulted/clamped | `safety.require_stated_age`, `stills.gate`, `films.gate`, `export_age`, recipe compiler | recipe without a typed age refused; age 20/"21.5"/blank refused; `clamp_age` untouched |
| 2 | `Me` checks | `lora_workshop.me_gate`, `policy_reason`, `still_source_ok`, `ME_SEX`, `pipelines_v3.export_age` | existing tests kept; recipe Subject refuses the player record |
| 3 | Upload ancestry | `pipelines._refuse_uploaded_undress` (walks `parent` to the root), `job_raw` | two-hop edit refused; `raw` load of a grandchild refused |
| 4 | Checker-off fails closed | `age_guard.CHECKER_REQUIRED_KINDS` (now also holding the three kinds `server.py` hard-coded) + a frozen `CHECKER_FREE_KINDS` list of today's other kinds; anything in neither is refused | every registered kind is in exactly one list; an unlisted kind is refused with the checker off |
| 5 | Identity | `safety.NODE_DENY_RE` (unchanged), attestation checkbox | third-party import with a face-swap node is refused, not weakened |
| 6 | Consent | puzzle validator | an actor without `consent: "mutual"` does not load; a node missing `sfw_safe` or `requires_full_21_mode` does not load |
| 7 | Resources | `loras` gates (`poi`, `minor`, `TakenDown`, sha256, `private_use`) | existing workshop tests kept |
| 8 | Secrets | recipe export | nested `op://` strings removed from every depth; nothing printed |
| 9 | Repo hygiene | `.gitignore` | imported packs and local level drafts ignored |
| 10 | Notices, disk | headers, `df -h ~` before big writes | notice tests kept |

## 4. Content mode: one flag

Studio (`app/content_mode.py`, the only place the mapping is written):
- `sfw_mode` is stored in `outputs/settings.json`. A fresh install has no value, which reads as `true`.
- The 21+ attestation is the existing device unlock (`/api/adult/unlock` with both boxes ticked). Passing it
  stores `sfw_mode = false` once.
- Effective `sfw_mode` is `true` whenever the device is not attested (locked, PIN session expired, other device).
- `area == "adult"` ⇔ effective `sfw_mode == false`. `want_area()` asks this module.
- `GET /api/settings` reports `sfw_mode`; `POST /api/settings {"sfw_mode": ...}` switches it (off needs the attestation).

Game (`game/scripts/settings.gd`, the only place the mapping is written in GDScript):
- `sfw_mode` stored in `user://settings.json`. Fresh install `true`.
- `confirm_age()` stores `age_gate_version = 21` and sets `sfw_mode = false`.
- `adult_content` becomes a derived read-only view: `not sfw_mode`, and always `false` without the gate.
- An old file with `adult_content` but no `sfw_mode` maps once: gate passed → `sfw_mode = not adult_content`;
  no gate → `sfw_mode = true`.

Filters when `sfw_mode = true` that apply to content that exists today:
- Studio: nude wardrobe and explicit stills unreachable; 21+ gallery items hidden; 21+-only LoRAs and their
  thumbnails masked; recipe stage options marked `requires_full_21_mode` hidden.
- Game: scene catalog never picks the adult variant; when a scene has no covered variant the game shows a calm
  hold card (never the adult picture, never a silent re-render).
- Not yet present (garment layer stacks, intimate-contact sockets, Holiday tiers): the resolver functions and
  their tests land with M0 so M3 content inherits them.

## 5. M0 — Integration

1. Branch `stillwater-m0-m2-integration` from `origin/cursor/lora-workshop-wave-ae2e` (`4988cd75`).
2. Merge `origin/cursor/workshop-pack-import-5b8f` (`b5357c3f`). Expected conflict: `.gitignore` only.
3. Merge `origin/cursor/stillwater-beach-3d-f8cc` at its green tip (`acf2204d`) if it merges cleanly.
4. No rebase. No #17/#18/#19/#22/#26. CI job name stays `test`.
5. Exporter-to-importer test: build a pack with `job_export_godot` on mock data, run
   `game/tools/import_easy_studio.py` in dry-run against the real island folder, assert `game/project.godot`
   is byte-identical and nothing was written.
6. `sfw_mode` mapping with tests for fresh install, attestation flip, and each `true` filter above.

Exit: one branch, both merges recorded, the dry-run test and every rail test green.

## 6. M1 — Graphic Workflow Editor MVP

### 6.1 Screens
- **Home** (new first screen): three large doors, `Make` · `Play` · `Library`, and a Settings gear. It is shown
  first once after this version even if the browser remembers an old tab (UX-1).
- **Make:** the recipe cards (Portrait still, Film from a still, Send to the island). At the bottom, one link:
  "Classic tools". It opens the existing 12 tabs exactly as they are (no redesign beyond #27). Every Classic
  screen gets a "⌂ Home" button at the top of the sidebar; tab ids stay the same (UX-1).
- **Recipe page:** the stage form. Stages in a fixed order: Subject → Look → Pose → Scene → Camera → Quality →
  Output. Each has an on/off switch and a "Save as preset" button. No drag, no reorder. Subject is always on.
  Stages a recipe does not use are greyed with a plain reason (UX-2, UX-3). Server refusals show under the
  stage they belong to (UX-6).
- **Node drawer:** a read-only view of the compiled ComfyUI API graph, closed by default, inside the recipe page.
- **Play:** how to open the island, the door puzzle status, and "Edit this place" notes.
- **Library:** the existing gallery.

### 6.2 Compiler (`app/recipes.py`)
- `compile(recipe) → {kind, params, graph, canonical_hash, cache_key, sidecar}`. The still and film jobs are
  split into `build_*_graph()` + run; the compiler calls the same builders, and a mock-engine test checks the
  executed graph hashes the same as the compiled one (PIPE-1).
- Pose, Scene and Camera choices become plain phrases inside the job's existing text field (`look` for the
  still, `motion` for the film). Size and camera have defaults; nothing else does. Age never does.
- Seeds: `workshop_still` and `film` take one new optional input, a whole-number `seed`; nothing else is added
  to their gates (PIPE-2). A typed seed is used as typed. A blank seed is drawn once at compile time, shown as
  "Seed used: N" and written back into the recipe, so the export reproduces the same graph (UX-4).
- Quality never writes `steps` on a template with two `KSamplerAdvanced` nodes.
- Cross-family handoff is pixels: the still's PNG plus a sidecar (`width`, `height`, `seed`, `model_family`,
  `workflow_id`, `sha256`) feeds the film's `START IMAGE` `LoadImage`. The compiler checks the sidecar sha256
  against the library file. No latent crosses families.
- Canonical hash: sha256 of `json.dumps(finalize(graph), sort_keys=True, separators=(",", ":"))`.
- Cache key: sha256 over template id, seed, every LoRA (file, model strength, clip strength), garment state,
  `sfw_mode`, camera id, source sha256. A model-only loader records clip strength as `"model_only"`. Any
  missing field means no key, which is a cache miss (PIPE-6).
- `route_lora(file, unet_filename)` in `comfy_client` is the only attach path (used by `inject_loras` and the
  LoRA benchmark, which loses its private `_attach_lora` path). On a Wan 2.2 14B half, a LoRA without the
  matching pair half is a hard error. The fast template's `lightx2v` LoRAs stay inside that template
  (PIPE-3, PIPE-4).
- Export: `.esrecipe.json`, built locally in the browser download; every string containing `op://` is removed
  at any depth. Import of our own format recompiles and must match the stored hash. ComfyUI UI/API JSON or PNG
  metadata is one-way: stored as bytes, shows missing models and node types, may run as `raw`, never decompiled.
  `NODE_DENY_RE` is not weakened for imports (PIPE-7, PIPE-12, SAFE-10).
- Subject: a saved fictional adult by id, or a new one whose age is typed into the stage and saved with the
  character. Exports never carry an age. The player record (`Me`) and `real_person` records are refused
  (SAFE-4, SAFE-5).
- Family switches: the worker remembers the last model family per ComfyUI process and calls `/free` before a
  job of another family on that process (PIPE-8). Latent previews are never items (PIPE-9).

### 6.3 Inline helpers (light features)
- 11 send-to-next: a finished, kept portrait still offers "Make a film from this" (PIPE-11).
- 15 shot strip: the film recipe shows the source still and the clips made from it in a strip.
- 16 tooltips + phase labels: each stage has a plain tooltip; the job tray shows "Step 1 of 1 · Making a still".
- 17 compare: a finished film or still can be compared with its source side by side.
- Heavy features 6, 12, 14, 18, 19 stay staged (see §10).

### 6.4 Acceptance (mock engine)
- Portrait still of one fictional adult with a typed age: ≤ 5 clicks from Make without the drawer.
- Film job on that still: ≤ 5 clicks.
- Export → import of that recipe gives the same canonical hash.
- One measured mock-job latency is recorded in `docs/M1_MOCK_LATENCY.json`.

## 7. M2 — Game core vertical slice: the door-unlock co-op puzzle

### 7.1 Content (one file)
- `game/data/puzzles/beach_door.json` + `beach_door.json.sha256`, written only by
  `game/tools/puzzle_level.py` (the one schema implementation).
- Holds: the door, two pressure pads, one prop (a brass key), the companion actor (an existing fictional adult
  from `game/data/characters`), plate hitboxes with Stage 1 sockets `{u, v, depth}`, labels, tuning.
- The validator also checks it can be solved: everything inside the beach bounds, pads at least 2 m apart,
  door not on a pad (FUN-4). Each actor's age comes from that actor's character record: a whole number ≥ 21
  or the file is refused (SAFE-8).
- Every node/card carries `sfw_safe`, `requires_full_21_mode`, `actors[]`, `consent: "mutual"` per actor.
- An empty dare-deck schema ships next to it (`schemas/dare_deck.json`); the validator refuses any card.

### 7.2 Rules (code, not JSON)
- `game/scripts/door_puzzle.gd`: load, check the sha256, then a small state machine: pads held, prop holder,
  door state. The door opens when both pads are held at once and the key has been passed to the companion and
  set in the door socket. The two goals can be done in either order (FUN-1).
- Feedback: pads glow when held, the door has two lamps, and the status line names the next missing step
  (FUN-3). The puzzle never calls `chat_brain.gd`, `dialogue_runner.gd` or `scenes.json` (FUN-6).

### 7.3 On the beach
- After #38 the beach the player sees is `beach_3d.tscn`. The puzzle builds its pads, door and prop there.
- The companion is a Stage 1 plate. Its hitboxes take two plain actions: "Stand on the far pad" and "Take the
  key" (FUN-2).

### 7.4 Edit this place
- A mode of Play inside the game (UX-8): move pads, door and prop on the sand, clamped to the beach bounds;
  save a draft to `user://levels/`; the draft carries its own sha256 and only positions change. A draft loads
  only when its hash matches. `python3 game/tools/puzzle_level.py promote` validates the draft with the one
  Python schema and writes the real file and its hash.

### 7.5 Tests
- Python: validator refusals, byte-stable writer, promote.
- Godot headless: the existing scene suite, plus loading the puzzle, refusing a bad hash, solving it, and
  failing it.

## 8. M3 — Party pack, builder, look test (queued)
Order: mat & balance → spin the bottle / truth or dare / wagers → Read the Person → Direct Scene Studio; Level &
Scene Builder; `player_in_scene` with allowed/refused job-kind tests and owner sign-off; 60 s look test
(Godot 4 Forward+ vs Unity 6 LTS URP). All reuse the plate, hitbox and socket code from M2.

## 9. M4 — Production (queued)
`schemas/character_asset.json` exporters in headless Blender, Unity 6 LTS URP port (or the look-test winner)
with custom skin, water and hair-card shaders, cloth and hair per engine, the 4-star checklist.

## 10. Staged features (not removed)
6 checkpoint resume · 12 outfit try-on · 14 face-consistency check · 18 pre-export hold · 19 Surprise me.

## 11. Checks
`ruff check .`, `tests/run_tests.py`, `tests/ui_smoke.py`, `tests/e2e_browser.py` (plus one new light-mode
Playwright path: Make → portrait still recipe → island import dry-run), `game/tools/test_import.py`, Godot
headless `res://scenes/tests.tscn`, Linux and macOS exports in CI.

## 12. Change log r1 → r2 (from `docs/STILLWATER_PLAN_REVIEW.md`)
- UX-1..UX-8: home shown first once, "⌂ Home" in Classic, Subject always on, greyed unused stages with reasons,
  "Seed used", plain drawer label, errors under their stage, edit inside the game.
- PIPE-1..PIPE-12: shared graph builders with an executed-hash test, `seed` as the one new job input,
  `route_lora` hard error and single path, no steps on dual Wan samplers, `"model_only"` clip strength in the
  cache key, one-way imports, memory-free on family switch, previews never items, sidecar sha256 check,
  send-to-next only on kept stills, recursive `op://` strip.
- FUN-1..FUN-6: two linked goals in any order, two verbs, lamps and a next-step line, solvability validation,
  feel left to an owner playtest, no chat/dialogue dependency.
- SAFE-1..SAFE-12: ancestry walk in edits and `raw`, fail-closed checker list, no ages in exports, no `Me` in
  Subject, attested-only `sfw_mode = false`, legacy game settings fail closed, puzzle actor age/consent from
  their own records, empty dare deck, `NODE_DENY_RE` unchanged, no hidden helpers. SAFE-12 (one stale
  "18 or older" message) is left for the next session.

## 13. Session checklist (this session's stable ids)
State as of the end of the Nov 5, 2026 session. Evidence is in `GROK_BOT_RETURN_HANDOFF.md`. "Done" means
source and tests on the branch; review, merge and owner playtest are separate gates and are not claimed.

| Id | Item | State |
|---|---|---|
| SW-P1 | Master plan r1, review, plan r2 | done (`6acad6e`, `a149ed4`) |
| SW-M0-1 | Merge #36 (`b5357c3f`) | done (`604191e`) |
| SW-M0-2 | Merge #38 (`acf2204d`) if green and clean | done (`f30ad5f`) |
| SW-M0-3 | Exporter → importer dry-run test | done (`fd5fec9`) |
| SW-M0-4 | `sfw_mode` one-place mapping + tests | done (`8247a41`) |
| SW-R-1 | Upload ancestry walk (edits + `raw`) | done (`cbb2c09`) |
| SW-R-2 | Checker-off fail-closed list | done (`cbb2c09`) |
| SW-M1-1 | `route_lora`, shared graph builders, `seed` input | done (`cbb2c09`) |
| SW-M1-2 | `app/recipes.py` compiler, hash, cache key, export/import, hardware map | done (`cbb2c09`) |
| SW-M1-3 | Home, Make, recipe page, drawer, Classic tools, helpers 11/15/16/17 | done (`6362dcb`) |
| SW-M2-1 | Puzzle schema/writer + committed level + hash | done (`3a13a44`) |
| SW-M2-2 | Godot puzzle rules, 3D beach pieces, Edit this place | done (`3a13a44`) |
| SW-Q-1 | All checks green; Playwright path; latency; Mac export launch | done; see the handoff for counts and NOT_RUN items |
| SW-H-1 | Push, one PR, `GROK_BOT_RETURN_HANDOFF.md` | done (PR #41) |
| SW-X-1 | Export ships the beach glTF/PNG files (pre-existing #38 gap found by the Mac launch check) | done (`08c24ab`, `86f93fc`) |
