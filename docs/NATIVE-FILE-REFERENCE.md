# Native Candy file reference

**Local source pin:** `e8c391f8c29ab75e16aed6e0a5e8385868272eee`, version `0.2.0rc1`. Paths in the inventory below are relative to the native checkout and are intentionally plain text. This guide lets a public-only contributor trace a change without access to the Mac, its media or its private evidence. The [contributor handoff](CONTRIBUTOR-HANDOFF.md) covers the separate public browser studio.

## Data flow and contracts

| User action | Input → output | What has to remain true |
| --- | --- | --- |
| Create or reopen a project | Picker selection → FFprobe metadata and source identity → SQLite project → optional working copy | A different file can occupy the same path. Recheck the selected identity, hash source bytes and verify a complete copy before reporting success. Opening a missing project must fail without creating a database. |
| Index selected media | Explicit file selections → durable SQLite queue → SHA-256 assets and path aliases → paged results | Hash-identical files can have multiple locations. Interrupted work can resume. Recheck the index identity before writing and the selected file hash before sending it to Scenes. |
| Build and reopen a scene | Detected stills, clips and paired motion → asset catalog → ordered shots → saved scene document | A shot carries an asset ID, duration and framing. Multiple shots can refer to the same asset. Weak visual matches need review. Reopen restores edits and detects stale saves or moved originals. |
| Render a montage | Ordered scene and verified assets → new 1280 × 720, 30 fps BT.709 SDR H.264/AAC MP4 | Validate source hashes, frame order, timing, fit/crop and audio. Reject unqualified HDR conversions. A montage can scale, crop or hold frames. |
| Join whole camera clips | Compatible whole clips in a user-reviewed order → stream-copied MP4 or Matroska | Compare packet clocks, decoded pictures and eligible audio against inputs. Edits that require rendering go through the montage path. Publish only a verified, new output. |
| Export one exact frame | Original, presentation-order ordinal and destination → single FFV1 frame in Matroska | Preserve supported native samples, dimensions and color tags. Record source SHA-256, rational PTS and sample digest. Unsupported transforms and side metadata get an explicit error. |
| Load a capability pack | Selected directory with one JSON manifest → validated catalog + native controls → typed request envelope | Accept supported declarations only. Match model, adapter, worker and adaptation versions exactly. The pack supplies data. An installed engine, training or a generated artifact requires separate proof. |

### Small interfaces worth knowing

- Foundation exposes `inspect_source(source)`, `create_project(root, source, *, expected_probe=None)`, `ensure_working_copy(root)` and `open_project(root)`. Paths are `pathlib.Path`. Inspection returns dimensions, duration, codec and an opaque source identity. Project state returns root, source path and SHA-256, probe and optional working-copy path. Handle `InspectionError` and `ProjectError` under `CandyError`.
- Storage separates the Foundation project database (`project.sqlite3`), copy receipt (`copy-receipt.sqlite3`), standalone library index and editable scene document. A Foundation schema migration writes a fresh project folder and preserves the v1 snapshot for rollback. The separate Library tracks asset digests, locations and queue items. Never open a library database inside a Foundation project.
- The scene document contains assets, scenes and reported issues. Assets carry original location, content digest, kind, size in pixels, timing, color, source order, aliases and optional paired-motion identity. Each scene has a name, a representative asset and an ordered list of shots with asset IDs, durations and fit choices. The saved revision is checked before publishing another edit. A thumbnail is regenerable.
- Capability references have the form `kind:id@version`. `load_pack(directory)` validates the JSON. `validate_values(form, values)` applies field types, bounds, conditional visibility and defaults. `prepare_request(pack, target, parameters)` binds the exact records and active values to a request digest. `validate_result(request, result)` checks correlation and the result shape. Output digests still require byte verification by the caller.

## Continuation experiment

The two inputs are generated 1280 × 720 SDR clips at 24 fps, each with 121 pictures. They end on the same decoded picture and contain identical PCM audio. Their preceding motion travels in opposite directions. Apply the same two-second forward-extension request, prompt, seed 42 and settings to each. A credible result must respond to the preceding motion; a held tail or a visually plausible animation of the shared last frame cannot establish temporal conditioning.

Measure the original checksum before and after, source and output timestamps, final-picture display duration, boundary frame order, color, source/audio changes, seeking and playback. Compare the outputs blind for motion direction, discontinuity, flicker, texture and audio. A passed media evaluator means an output met measured conditions. Human quality review is separate. Stock Extend can regenerate audio. Keep the untouched source audio available for comparison.

The approved local reference is the official arm64 Desktop 1.3.2 installer and five pinned BF16 files: transformer, text encoder, video VAE, audio VAE and spatial upscaler. The total is 71,955,233,680 bytes. The budget requires 155 GiB free at start and 50 GiB free throughout. Generation requires verified local assets, disabled analytics, updates and pairing, and offline execution. The two runs each have a 25-minute limit. At the last recorded check the installer returned HTTP 200, the machine lacked local Hugging Face authentication, and the selected files had not been acquired. No model inference or generated-output verdict exists for this pilot. Q8 quality and adaptation compatibility remain open.

## File inventory

Each row identifies one tracked file at the source pin, its responsibility, and a useful integration or verification detail. Examples of test names identify actual regression cases in the corresponding file.

### Package and setup

| Local file | Responsibility and behavior |
| --- | --- |
| `.gitignore` | Local build and interpreter exclusions. Consult this when diagnosing why generated project artifacts do not appear in a source checkout. |
| `README.md` | User tutorial and development entry point. Covers new/open/copy, scene import and SDR export, the example pack, source-frame export, library indexing and ordering camera fragments. |
| `pyproject.toml` | Defines the candy package, Python 3.12+ and PySide6 6.x dependency, pytest extra, src layout and Swift resource. The local release-candidate version comes from this file. |
| `src/candy/__init__.py` | Package root and identity. Launch through the module entry point so the application owns its Qt event loop. |
| `src/candy/__main__.py` | Creates QApplication and MainWindow. In a frozen Finder launch it supplements PATH with standard local FFmpeg locations before showing the window. |

### Source inspection, projects and derived files

| Local file | Responsibility and behavior |
| --- | --- |
| `src/candy/core/__init__.py` | Exports the supported Foundation interface, exception types and explicit migration functions. UI and integration callers should import from this boundary. |
| `src/candy/core/model.py` | Defines immutable ProbeResult and ProjectState and the CandyError hierarchy. A missing working copy is represented by None. |
| `src/candy/core/inspection.py` | Opens and pins a regular source, reads it through FFprobe’s seekable descriptor protocol and checks identity. Digest and probe operate against the selected file. |
| `src/candy/core/storage.py` | Pins the project directory, coordinates locks and publishes anonymous staged files to new names. Filesystem capability checks are part of the operation. |
| `src/candy/core/project.py` | Implements create_project, open_project and ensure_working_copy. Reads SQLite snapshots, checks expected probe and source hash, verifies a copy or existing receipt, and refuses conflicting destinations. |
| `src/candy/core/migration.py` | Implements the explicit v1-to-v2 migration and rollback into fresh destinations. Both operations verify their source project and reconstruct a complete project independently of the original folder. |
| `src/candy/frames/__init__.py` | Package boundary for verified native-resolution frame exports. The callable lives in export.py. |
| `src/candy/frames/export.py` | export_frame accepts the source, zero-based ordinal, destination, progress and cancellation callbacks. Decodes the selected frame and verifies output samples, timing and supported metadata before publication. |
| `src/candy/captions/__init__.py` | Defines the caption interchange package and its integer-millisecond time convention. |
| `src/candy/captions/interchange.py` | Cue, parse and serialize handle plain SRT/WebVTT, exact millisecond clocks, multiline text and permitted overlap. Unsupported formatting must produce a readable error. |
| `src/candy/captions/files.py` | load_document pins and bounds a selected text file. save_as publishes a verified new caption file while keeping source identity available to the editor. |

### Capability packs and indexing

| Local file | Responsibility and behavior |
| --- | --- |
| `src/candy/contracts/__init__.py` | Marks the declarative pack namespace. The catalog, pack reader and exchange modules define independent version checks. |
| `src/candy/contracts/catalog.py` | Validates the complete reference graph and exact adapter/model/adaptation relationships. verify_artifact streams an explicitly supplied file to check its SHA-256. |
| `src/candy/contracts/packs.py` | Reads candy-pack.json from the selected folder and validates the form schema. Computes active fields in declaration order, applies defaults and rejects unknown parameter names. |
| `src/candy/contracts/exchange.py` | Constructs a local or remote request using a resolved model, worker and parameters. Validates result IDs, status and output digests. Transport and execution are separate concerns. |
| `src/candy/library/__init__.py` | Exports Library and the result and error types shared by its UI and callers. |
| `src/candy/library/model.py` | Defines Resource, ImportItem, Page, ImportReport and LibraryError. Use these for paginated lookup and per-item results without coupling widgets to SQLite rows. |
| `src/candy/library/fingerprint.py` | Reads one selected regular file through a read-only descriptor. Produces an outcome for indexing and detects changes while hashing. |
| `src/candy/library/store.py` | Owns the independent SQLite database, pending and paused queue items, digest deduplication, aliases and bounded queries. Verifies the bound index before taking a writer lock after directory replacement. |

### Scene ingest, edit, render and join

| Local file | Responsibility and behavior |
| --- | --- |
| `src/candy/scenes/__init__.py` | Package boundary for local scenes assembled from selected stills and clips. |
| `src/candy/scenes/model.py` | Asset, Shot, Scene and SceneProject represent the source catalog and editable sequence. A scene save token is in memory; a shot references an asset by ID. |
| `src/candy/scenes/ingest.py` | Classifies selected resources from their content, extracts metadata and builds regenerable thumbnails. Handles input problems per item and flags inputs requiring unqualified HDR conversion. |
| `src/candy/scenes/apple_media.swift` | Trusted macOS helper for Apple still decoding, metadata and Vision analysis. It lets the app inspect Apple media locally and is compiled into the packaged app. |
| `src/candy/scenes/_media_tools.py` | Wraps bounded FFmpeg/FFprobe and Apple-helper invocations, structured output parsing and cancellation. Use this layer when a background media operation needs to terminate cleanly. |
| `src/candy/scenes/_visual.py` | Computes compact image features from local pixels, including appearance and background cues. Grouping consumes these features without identifying a person. |
| `src/candy/scenes/_live_pairs.py` | Reconciles identifier-backed still and motion resources across imports. Ambiguous collisions retain their original asset information for review. |
| `src/candy/scenes/grouping.py` | Builds conservative scene suggestions from visual evidence and emits review reasons. Burst hints preserve members so the user can undo a grouping choice. |
| `src/candy/scenes/_fragment_evidence.py` | Reads bounded head/tail windows from verified movie descriptors and compares boundary evidence. The output feeds clip ordering independently of filenames. |
| `src/candy/scenes/fragments.py` | propose_fragments considers 2–10 selected clips, evaluates candidate sequences and reports ambiguity. A proposal stays editable before rendering or joining. |
| `src/candy/scenes/store.py` | Validates and persists versioned scene documents. Optimistic save checks and recoverable prior saves protect edits against stale windows and interrupted writes. |
| `src/candy/scenes/render.py` | export_scene renders an edited sequence from verified media to a new SDR movie. Decode checks cover output order, timing, source provenance and audio policy. |
| `src/candy/scenes/_join_media.py` | Describes stream layouts, packet records, decoded pictures and audio samples. inspect_streams and verify_join check that a proposed stream-copy output matches eligible inputs. |
| `src/candy/scenes/join.py` | join_originals takes ordered whole assets and a new output path. Uses anonymous staging, checks eligibility and output proof, and avoids leaving a named media copy on abrupt termination. |

### Native user interface

| Local file | Responsibility and behavior |
| --- | --- |
| `src/candy/ui/__init__.py` | Package boundary for PySide6 desktop windows and widgets. |
| `src/candy/ui/main_window.py` | Owns project creation, reopening, inspection results and the current primary action. File and Tools menus are integration points for the other native workspaces. |
| `src/candy/ui/project_widgets.py` | Shared system-palette widgets, stage headings, action buttons and file readouts. Changes here affect path presentation and keyboard/accessibility behavior across project states. |
| `src/candy/ui/capabilities.py` | CapabilityDialog opens a selected pack directory and builds native typed controls, presets, advanced fields and conditional visibility. Validation errors stay with the form. |
| `src/candy/ui/library_window.py` | LibraryWindow manages file selection, background indexing, search, import reports and scene transfer. Reopening must bind the current index before resuming a job. |
| `src/candy/ui/frame_export.py` | FrameExportDialog collects the source, frame ordinal and destination, exposes progress/cancel and reports verified output to the user. |
| `src/candy/ui/captions.py` | CaptionWindow, CueTable and CueEdit support native cue selection, timing edits, undo/redo, new-file save and dirty-state recovery on close. |
| `src/candy/ui/scene_workspace.py` | SceneWindow joins import, contact sheets, shot editing, save/reopen, preview and export. Resolves the user’s selection before proposing clip order or joining whole clips. |
| `src/candy/ui/scene_edits.py` | Implements edits to the scene model including split, representative, add/import reconciliation and explicit Live Photo pairing. Keeps widget code separate from model changes. |
| `src/candy/ui/scene_history.py` | Stores changed scene ranges, selection and shot settings for undo/redo. New edits clear the redo branch and saved revisions establish a clean-state boundary. |
| `src/candy/ui/scene_media.py` | SceneJob runs background media work. Thumbnail repair and PreviewDialog support playback of the rendered sequence and bounded worker lifetime. |

### Setup, verification tools and synthetic fixtures

| Local file | Responsibility and behavior |
| --- | --- |
| `tools/build_macos_app.py` | Compiles the Swift helper and freezes PySide6 into a new arm64 Candy.app. Checks the local ad-hoc signature; the resulting bundle still needs a native workflow check. |
| `tools/check_native_workflow.py` | Exercises new project, working-copy creation and project reopening using generated source media, temporary project paths and picker selections. Suitable for local Foundation smoke testing. |
| `tools/check_scene_workflow.py` | Exercises the Cocoa scene window with an ordered synthetic selection and waits for background work before inspecting state and capturing evidence. |
| `tools/qualify_scene_groups.py` | Creates a labeled synthetic shoot. Measures grouping behavior and resource use on the host so proposals can be evaluated against known groups. |
| `tools/qualify_continuation.py` | prepare creates matched synthetic sources, controls creates known positive and negative derivatives, and evaluate measures a supplied full derivative. None of these commands runs a generation model. |
| `tools/verify_continuation_assets.py` | Offline verifier for the pinned installer and five selected model files. Checks size and SHA-256 of supplied files before engine loading. |
| `tests/fixtures/README.md` | Documents the synthetic-fixture convention and retains the directory in clean checkouts. Generated media belongs in temporary test locations. |
| `tests/fixtures/c0-pack/candy-pack.json` | Version-one data-only pack with adapter, model, worker and related records plus Color study and Training trial forms. It exercises presets, conditional fields and request construction. |

### Foundation, contracts and integration tests

| Local file | Responsibility and behavior |
| --- | --- |
| `tests/core/test_core.py` | Exercises inspect/create/copy/reopen, malformed probe output, changed inputs, conflicts and interrupted operations on generated media. |
| `tests/core/test_migration.py` | Compares v1, migrated v2 and restored v1 state; challenges overlapping or occupied destinations, malformed backups and changed original media. |
| `tests/contracts/test_catalog.py` | Exercises forward references, distinct versions, invalid records, catalog bounds and artifact identity against synthetic records. |
| `tests/contracts/test_packs.py` | Exercises fixture loading, defaults, nested conditional visibility, bounded input, redirected manifests and unsupported declarations. |
| `tests/contracts/test_exchange.py` | Exercises a local recipe, a remote training declaration and result correlation against the prepared request. |
| `tests/integration/conftest.py` | Builds temporary synthetic video sources, controlled probe executables and independent checksums for filesystem and process tests. |
| `tests/integration/test_project.py` | Uses public Foundation APIs to verify working-copy reuse, project reopening, unowned files, missing sources and published file effects. |
| `tests/integration/test_processes.py` | Coordinates separate processes at a filesystem barrier and exercises concurrent access, abrupt creation interruption and failure during a copy. |
| `tests/integration/test_source.py` | Exercises actual filesystem and FFprobe boundaries, including unreadable or missing inputs, malformed results and changes during inspection. |
| `tests/integration/test_continuation_pilot.py` | Decodes the matched histories and challenges the evaluator with held motion, wrong source history and wrong end timing. These tests use media controls. |

### Media and UI regression tests

| Local file | Responsibility and behavior |
| --- | --- |
| `tests/frames/test_export.py` | Independent decoded-pixel and timestamp checks for VFR frame selection and color tags; refusal and cancellation cover unsupported inputs and occupied destinations. |
| `tests/captions/test_interchange.py` | Checks UTF-8, multiline cues, timing precision, overlap and round trips. Malformed or unsupported syntax must report an actionable error. |
| `tests/library/test_library.py` | Checks byte-level deduplication with distinct aliases, read-time replacement, cancellation, restart and durable per-file progress. |
| `tests/scenes/conftest.py` | Injects a move or replacement during the final filesystem sync to test publication races without touching real media. |
| `tests/scenes/test_camera_join.py` | Independently decodes qualified MP4/Matroska joins in requested order, compares pictures and PCM, and exercises rejected layouts and abrupt exits. |
| `tests/scenes/test_fragments.py` | Uses generated pictures and audio to test clip-order proposals, misleading names, ambiguous boundaries and preservation of selected IDs. |
| `tests/scenes/test_grouping_visual.py` | Draws movable synthetic subjects, changes outfit/setting, and checks both useful matches and rejection of transitive chains. Checks reversible burst hints. |
| `tests/scenes/test_ingest_apple.py` | Creates Apple-container fixtures for orientation, HEIC/HEIF decoding, actual pairing metadata and Live Photo motion in export. |
| `tests/scenes/test_ingest_reconciliation.py` | Checks pairing across imports and save/reopen, collisions, aliases and retention of assets when a proposed automatic pair becomes ambiguous. |
| `tests/scenes/test_scene_documents.py` | Checks saved edits, existing destinations, stale-window conflicts, interruption recovery and integrity of the previously saved revision. |
| `tests/scenes/test_scene_render.py` | Decodes the finished montage and checks ordered pictures, timing, audio offsets, preservation of originals and cancellation before publication. |
| `tests/ui/test_main_window.py` | Exercises normal project operations, error recovery and reopened states via native widgets, including long-path geometry, focus and action visibility. |
| `tests/ui/test_capabilities.py` | Opens the pack dialog via the actual menu and exercises native form fields, visibility, validation and the synthetic preset. |
| `tests/ui/test_library_window.py` | Exercises import, search, keyboard controls, pagination, cancellation and reopening/resuming through the Library window. |
| `tests/ui/test_library_scenes.py` | Transfers selected indexed files through the UI, detects changed sources and verifies that reopening a replaced library rebinds the target. |
| `tests/ui/test_captions.py` | Exercises native cue editing, keyboard controls, exact timing, saved data, cancellation and recovery of pending edits. |
| `tests/ui/test_neutral_tools.py` | Checks native Captions menu reuse and the Scene menu’s whole-clip join behavior, including refusal of edited timing. |
| `tests/ui/test_scene_history.py` | Exercises undo/redo, selection, clean/dirty transitions and navigation across saved revisions in the actual editor. |
| `tests/ui/test_scenes_workspace.py` | Exercises import reports, editing, burst controls, manual pairing, preview/export and lifecycle of background operations through the scene window. |

### Design documents and supporting files

| Local file | Responsibility and behavior |
| --- | --- |
| `docs/BASELINE.md` | Records the greenfield Foundation intake, project root and initial verification. Use subsequent acceptance receipts for current readiness. |
| `docs/FOUNDATION_CONTRACT.md` | Defines project API signatures, values, errors, FFprobe behavior, path checks, copy publication and source-preservation guarantees. |
| `docs/CANDY-SCENES-001.md` | Defines the Apple-media scene workflow, supported resources, grouping and editing criteria, SDR export and fixture acceptance cases. |
| `docs/DOMAIN-MODEL.md` | Defines identities, parent relationships, rational media clocks, provenance and future domains. Individual evidence records determine which contracts have implementations. |
| `docs/MODULE-MAP.md` | Assigns responsibilities across core, contracts, scenes, UI and library, including the separate index and ownership of menu integration. |
| `docs/UI-ARCHITECTURE.md` | Describes native window responsibilities and presentation of workflows, background state, recovery and extension controls. |
| `docs/EXTENSION-MATRIX.md` | Maps contribution types to the proposed integration surface and evidence required for acceptance. Current C0 proof covers a subset. |
| `docs/INTEGRATION-PLAN.md` | Records integration dependencies and sequencing for independent slices, including combined testing against exact revisions. |
| `docs/REQUIREMENTS.md` | Registers workstation requirements and evidence expectations. A requirement listed here can still be unimplemented. |
| `docs/RESEARCH.md` | Records technology research and qualification gaps for media and model workflows. Check execution evidence before selecting an engine. |
| `docs/ACCEPTANCE-MATRIX.md` | Maps working and pending features to focused, integrated, independent and user evidence. Read the dated pilot receipt for later access status. |
| `docs/TEST-EVIDENCE.md` | Attributes suite results and correction receipts to their exact source revisions. Distinguishes the isolated C0 count from the integrated suite. |
| `docs/RELEASE_NOTES.md` | Documents the local 0.2.0rc1 scene candidate and user-visible edit/export behavior. This is a local candidate record. |
| `docs/PACKAGING.md` | Build procedure for a local arm64 Mac bundle and compiled Apple helper. Distinguishes ad-hoc verification from signing, notarization and clean-machine qualification. |
| `docs/CONTINUATION-DECISION.md` | Compares official Desktop and the community MLX path, temporal conditioning, hardware fit, model revisions and unverified adaptation or quantization behavior. |
| `docs/CONTINUATION-APPROVAL.md` | Specifies the six authorized reference files, designated storage, privacy controls, disk threshold, offline runs, individual time caps and rollback. |
| `docs/CONTINUATION-PILOT.md` | Defines the synthetic histories, expected clocks, paired comparison, required measurement and blind output review. |
| `docs/continuation-desktop-manifest.json` | Machine-readable upstream pins, file names, exact byte lengths and expected SHA-256 values for the installer and five BF16 files. |
| `docs/c0/ARCHITECTURE.md` | Overview of the first neutral contracts and their relationship to existing projects, declarative packs and native controls. |
| `docs/c0/CATALOG.md` | Version-one catalog keys, exact reference syntax, supported record classes and compatibility checks for model and adaptation artifacts. |
| `docs/c0/PACKS.md` | Manifest limits and schema for native controls, offered presets, numeric bounds, simple/advanced presentation and conditional visibility. |
| `docs/c0/EXCHANGE.md` | Versioned, transport-neutral request and result schemas, canonical JSON hashing, correlation and error representation. |
| `docs/c0/MIGRATION.md` | Documents explicit v1/v2 migration, backup and reversal to a fresh directory, supported filesystems and interrupted-operation recovery. |

## Evidence available only on the native machine

These record names let a read-only contributor request a specific verification result from a maintainer. They are descriptions of local artifacts. Public CI cannot run them against the native source.

| Local artifact | Contents and interpretation |
| --- | --- |
| `p0-handoff-suite.log` | Exact final native checkout, 418 passed in 111.31 seconds with zero skips or failures. This was an application and qualification-tool suite. |
| `p0-clean-review/final-suite.log` and `docs-identity.log` | Independent run, 418 passed in 111.17 seconds on parent `9b8b397`. Comparing all 109 entries found only six documentation lines added across two files. Executable, tests and package inputs matched the final revision. |
| `p0-clean-review/final-cleanup.log` and `final-playback.log` | Forced interruption left zero named staged media. A successful retry produced a joined artifact. Independent playback emitted all 18 pictures and 34,560 audio sample frames and reached 720 ms. |
| `p0-handoff-package/Candy.app` and `p0-handoff-native.json` | Local ad-hoc-signed arm64 bundle and native interaction receipt. The macOS picker selected the synthetic H.264 source, Scene Preview advanced to 2.880 seconds, and its original SHA-256 matched afterward. |
| `pilot-inputs-seed42/receipt.json` and `p0-queue-requests.json` | Source identities, media clocks and request bodies for the opposing histories. Both inputs have the same final decoded picture and 242,000 matching audio sample frames. These files prepare a comparison. |
| `ltx-desktop-pilot/receipts/pre-acquisition.json` and the dated pilot access record | Local disk and asset preflight followed by per-artifact access disposition. The last recorded check had 280 GiB free; only the public installer access check reached its host. The five model requests had no HTTP result. Recheck access and free space immediately before transfer. |
| Foundation acceptance, native integration handoff and feature ledger | Foundation records human acceptance of the five-step Mac project workflow at `7f8e9d3`. The integration record distinguishes independent engineering acceptance of `e8c391f` from later user acceptance. The ledger holds ideas such as shot-aware enhancement pending a qualified benchmark. |
| Runtime-created project, library, scene and output files | The Foundation database and receipt describe a selected original and verified working copy. The library stores digests, aliases and per-item import state. A scene file stores editable choices and local asset references. Derived exports carry provenance. Reproduce a case with synthetic data and share the behavior or hashes. |

Build caches, virtual environments, transient test files and local drafts have no role in the 109-file source pin. A maintainer reproducing a change should use a clean checkout of that pin and a separate destination for generated artifacts.
