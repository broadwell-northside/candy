# Codex evidence → Easy Studio requirements map (PRD v4)

**Source:** Codex's Candy.ai Premium audit and competitor notes.
- Repo copy: branch `codex/evidence-candy-premium-20261103`, commit `a68fc39`, `evidence/INDEX.md`.
- Local copy: `/workspace/evidence/EasyStudio-Evidence/`.
- Sanitized copy, used for this map: `/workspace/evidence/sanitized/EasyStudio-Evidence/`. See its `REDACTIONS.md`.
- Feature ids F01–F24 are Codex's.
- Codex marked its packet **work in progress**. Nothing here proves Candy's output quality, because no paid generation was completed in the audit.

**How to read the "Decision" column**
- **Adopt**: we take the idea, in a local form.
- **Already have**: Easy Studio v3 already does it.
- **Adapt**: we take a local version of a cloud feature.
- **Not copied (deliberate)**: we leave it out on purpose, for a safety or legal reason.
- **Not applicable**: it only makes sense for a paid cloud or social service.
- **Low priority**: this is the chat area. Andrew ranked chat last on 3 Nov 2026.

| # | Candy evidence (Codex id, screenshot) | What it shows | Easy Studio requirement | Decision |
|---|---|---|---|---|
| 1 | F01 shell and navigation (019, 020) | Left rail of icons, one top search, token counter | §6 tab bar; "one job, one tab" | **Already have.** Keep tabs, no token counter |
| 2 | F02 discovery and profile preview (020, 021) | Big portrait cards, hover preview, filter chips | Saved characters (§6.2) | **Adopt:** add a hover preview (short loop video if one exists) to character cards |
| 3 | F03 collection / My AI / media (025, 026, 027) | Per-character media library, separate from the catalogue | Gallery + projects (§6.10) | **Already have**. **Adopt** a per-character media filter in Gallery |
| 4 | F04 exclusive / creator-owned characters | Paid unlocks of other creators' characters | n/a | **Not applicable** (marketplace) |
| 5 | F05–F06 chat lifecycle, regenerate, branch, delete (028–031) | Composer, regenerate, edit, rewind | Companion chat proposal (PRD v4 §V9) | **Low priority**. If built, copy regenerate, edit and rewind only |
| 6 | F07 chat model and response style (032) | Model picker, reply length and style | Companion chat | **Low priority**. Local LLM picker on the Mac |
| 7 | F08 memory entries (help + client code) | Editable memory list with limited slots | Companion chat | **Low priority**. Editable memory file per character, no slot limit |
| 8 | F09 user personas (043, 022) | "Your persona": name, age, gender, location, job | Companion chat | **Low priority**. Persona only matters for chat. Never ask for real location |
| 9 | F10 group chat (046) | Group chat entry with an **"18-21" age filter chip** | Companion chat | **Not copied (deliberate):** no age filter under 21. All characters are 21+ |
| 10 | F11 versioned character creation (019, 023, 024) | Guided step-by-step picks, style first, draft saved | Character Creator (§6.1) | **Already have** (pick-first chips). **Adopt:** auto-save draft and a "versions" list per character |
| 11 | F12 preview, validation, voice pick | Live summary, voice picked at creation | §6.1, companion voice | **Adopt** live summary (already partly there). Voice: **low priority** |
| 12 | F13 Image Studio with references (035–040) | Reference library, scene, lighting and composition chips | Wardrobe, scenes, photoshoot (§6.3–6.7) and the **photorealism workstream** (PRD v4 §V2) | **Adopt:** add lighting and lens chips (golden hour, softbox, neon rim, 35mm/85mm) as part of the realism presets |
| 13 | F14 Video Studio: model cards, modes, keyframes, duration (S02, 033, 041) | Capability-driven form: each model card shows its modes and limits | Video studio (§A5) | **Already have** (model picker driven by capabilities). **Adopt** model "cards" showing max seconds and resolution |
| 14 | F15 preset video and montage projects (034, 042) | Preset scenes, multi-clip montage | Photoshoot packs, Video extend | **Adapt:** "Montage" = join clips from Gallery into one MP4 (ffmpeg, local) |
| 15 | F15 "Scenes 18+" explicit presets (034) | Explicit preset categories | 🔞 18+ section (§A7) | **Already have** (own presets inside the gated area). No age-play or non-consent presets |
| 16 | F16 revision jobs and recoverable uncertainty | Request keys, "still working?" states, stale-update guards | §4 progress and errors | **Adopt:** idempotent job ids, safe "retry", honest "unknown — check gallery" when the browser lost contact |
| 17 | Studio model labels (Seedream / Seedance) | Candy uses hosted ByteDance models | §7 model list | **Not applicable:** cloud only. Local equivalents are in the photorealism workstream |
| 18 | F17 Premium entitlements | Paid tiers gate features | n/a | **Not applicable** |
| 19 | F18 wallet, tokens, auto top-up (045, 022) | Token prices per action | n/a | **Not applicable.** **Adapt** as an honest "GPU time" estimate per job (already shown) |
| 20 | F19 shop, gifts, items (045) | Sex-toy and gift shop for characters | n/a | **Not applicable** (economy). Wardrobe already covers outfits |
| 21 | F20 relationship level, achievements, streaks (044) | 131 achievements, points, streaks | n/a | **Adapt (optional):** local "milestones" (first trained LoRA, first 10 s video, first Godot export). These teach features; no streaks, no nagging |
| 22 | F21 dictation, voice messages, calls | ElevenLabs-style calls | Companion chat | **Low priority.** Local TTS/STT on the M5 Max |
| 23 | F22 Live Action, Cam, Roulette | Simulated live streams with tips | n/a | **Not applicable** (simulated audience and tipping) |
| 24 | F23 shorts, branching stories, campaigns | Choice-based stories, social shorts | Godot export, **game phase** (PRD v4 §V6) | **Adapt:** branching scenes belong in the Godot game, not in a social feed |
| 25 | F24 responsive / PWA | Phone-friendly web app | §6 mobile layout | **Already have** (responsive). PWA install: not needed |
| 26 | Real-performer / "clone" characters (external research) | Some rivals sell lookalikes of real people | §10 safety | **Not copied (deliberate):** no real-person likeness, no face-swap, no photo training |
| 27 | Age range 18–20 on rivals (046 chip; 019 shows "21yo" floor in Candy's builder) | Rivals allow 18+; Candy's builder shows 21 as an option | §A2 hard limits | **Not copied (deliberate):** the Easy Studio floor stays at **21** |

## Conflicts between the evidence and PRD v3

1. **Chat is a non-goal in v3.** Most of Candy's depth is in chat (F05–F10, F21). PRD v4 resolves this by keeping chat as a **small, low-priority, optional** proposal. It goes after photorealism, 3D and the game.
2. **Hosted versus local models.** Candy's best visuals come from hosted Seedream and Seedance models. Easy Studio is local only. To close the gap we need the **photorealism workstream**, not a cloud API.
3. **Stacked LoRAs: four (Part A §A6) versus three (Part B §6.12).** Part A wins: the limit is **four**. PRD v4 fixes the Part B text.
4. **"Any model" video.** Codex rightly warns that a generic card is not proof that every workflow works. PRD v4 keeps the honest auto-detect report: it lists unsupported nodes, unclear inputs and missing models.
5. **Estimated progress.** Candy shows a fake progress bar. Easy Studio keeps the honest per-stage progress from the engine.

## Privacy note
The repo branch `codex/evidence-candy-premium-20261103` still holds the **unredacted** files. Easy Studio docs only cite the sanitized copy. See `REDACTIONS.md` for what to fix in the repo, which needs Andrew's OK.
