# Candy contributor handoff

**Status checked November 25, 2026.** Candy has two implementations. Choose one by the task you need to solve.

| If the task involves… | Start here | Baseline |
| --- | --- | --- |
| Browser UI, generation jobs, model setup or a ComfyUI workflow | This public repository, called **Easy Studio** in its UI and README | Browser app version 3.0.0 at [`9042f09`](https://github.com/broadwell-northside/candy/commit/9042f0965053adf864530fa62693a273d85335f5) |
| macOS file picker, verified originals, media library, scene editing, captions, frame export or the local continuation pilot | The separate native **Candy** checkout. A public-only reader can use the [native file reference](NATIVE-FILE-REFERENCE.md) to trace a workflow and design a change | Native 0.2.0rc1 at local revision `e8c391f8c29ab75e16aed6e0a5e8385868272eee` |

The public Git history contains the browser studio. Native revision IDs below identify the local repository. The two implementations have separate entry points, dependencies, persistence and test results.

## Follow one browser job

1. A user chooses a task and parameters in the browser. The static client lives in [app/static](../app/static). Start with [the page](../app/static/index.html), [the first-run guide](FIRST_RUN.md) or [the video controls](../app/static/video_pages.js).
2. [app/server.py](../app/server.py) creates the FastAPI app, serves the UI and registers the route modules. Trace a feature from its browser request to the corresponding route. [Model routes](../app/routes_models.py) handle the model UI. [The registry](../app/model_registry.py) and [model cards](../app/model_cards.json) describe choices. A listed model still needs its files and a compatible engine.
3. [app/comfy_client.py](../app/comfy_client.py) checks the engine, submits the workflow and retrieves job history. [app/library.py](../app/library.py) is the starting point for saved library items. Preserve the existing safety and content-mode checks along these paths. [Safety rules](../SAFETY.md)
4. On a configured Mac, run `./start_mac.sh --check` for the launcher check. Then `./start_mac.sh` starts the app and engine on loopback and opens the browser. Defaults are port 7860 for the app and 8188 for the engine. The README also covers using a browser with a separate GPU host. [Launcher](../start_mac.sh) · [Setup](../README.md)

For development, follow the Python 3.12, FFmpeg and Playwright setup in [CONTRIBUTING.md](../CONTRIBUTING.md). From the public repository root run:

```sh
.venv/bin/python tests/run_tests.py
.venv/bin/python tests/ui_smoke.py
.venv/bin/python tests/e2e_browser.py
```

The first command uses a fake ComfyUI server. The browser checks exercise the interface. For a claim about real rendering, identify the model and engine versions, use a synthetic input, and inspect the resulting artifact. The public baseline passed its [CI](https://github.com/broadwell-northside/candy/actions/runs/44869270345), [Game](https://github.com/broadwell-northside/candy/actions/runs/44869270368) and [Server kit](https://github.com/broadwell-northside/candy/actions/runs/44869270324) workflows. Those dated runs cover the public browser repository.

## Browser files on the operator’s machine

The browser studio can be understood from a public clone without reading anyone’s library. These examples use logical paths, relative to the configured runtime or output directory.

| Local file or directory | Who creates and consumes it | How a read-only contributor can reproduce the behavior |
| --- | --- | --- |
| ComfyUI checkout, its Python environment, and model directories | The local engine loads workflows and model weights. The Mac launcher resolves its runtime using `CANDY_RUNTIME`. Workflows in the public repository name required models. | Use the mock server or a simulated inventory. In `GET /api/status`, engine reachability and each feature’s readiness are separate. An empty missing-file list with an unavailable engine leaves readiness false. |
| Output media and per-item JSON | [The library](../app/library.py) writes a record with an ID, file path relative to its root, type, kind, role, timestamp and optional metadata. Updates replace a temporary JSON file. The UI resolves a result from that record. `EASY_STUDIO_OUTPUTS` selects the Mac output root. | Create a temporary library and add a generated image as a fixture. Verify that lookup, listing and permitted metadata updates agree after reopening. |
| `outputs/model_registry.json` and `outputs/pipeline_candidates.json` | The registry can override role defaults on one machine. The candidate file records which proposed pipelines were tested and selected locally. Presence of a workflow in source alone does not prove either. | Use temporary config and a mock engine to test selection and validation. For quality claims, record a named model, hardware, settings and measured output in a separate synthetic run. |
| Runtime logs, process IDs and test outputs | The launcher records processes it started. Browser E2E tests regenerate screenshots and a run report. Operator logs can contain prompts or private locations. | Generate fresh evidence for the case under test and share a sanitized result. The public source of truth for the setup steps is the launcher and [contribution guide](../CONTRIBUTING.md). |

## Follow one native project

A user picks an original in the native PySide6 app. FFprobe inspects the open file. Candy records the source identity and SHA-256 in a SQLite project and creates a verified working copy on request. Reopening checks the saved original and copy. A separate SQLite library indexes selected files and resumes interrupted imports. In Scene Workspace the user groups stills and clips, reviews the group suggestions, edits a shot sequence, saves it and exports a new SDR movie. Captions and exact-frame extraction are separate tools.

In the native checkout, launch with `.venv/bin/python -m candy` and run synthetic tests with `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest`. Apple media import uses Swift and Apple frameworks. Native picker, playback and bundle checks require macOS. The local package uses host FFmpeg and FFprobe. The [file reference](NATIVE-FILE-REFERENCE.md) covers setup, data contracts, all 109 tracked files, test coverage and local evidence. [Developer notes](DEVELOPER-NOTES.md) explain when each capability landed and what its verification established.

## Current priorities and useful first contributions

| Task | A public-only contributor can deliver | A maintainer can verify |
| --- | --- | --- |
| Browser first run | Trace the launcher, engine status and Models UI. Reproduce a missing-engine or missing-model state with a mock. If the user cannot identify the failing prerequisite, propose the precise message, recovery action and test. | Exercise the same state with the native launcher and an installed or deliberately unavailable engine. |
| Library and model workshop | Read [PR #9](https://github.com/broadwell-northside/candy/pull/9) before proposing changes to shared library access. Identify a missing regression case or another non-overlapping task. | Run the fixture against both ordinary library items and workshop records under the existing access rules. |
| Native source-video continuation | Use the two-source experiment in the file reference to design a blind score sheet for boundary motion, flicker, color, detail and audio. Hand back criteria and expected failure examples. | Run the approved two-second reference extension and matched control when authenticated model access is available. Each job has its own 25-minute limit. |
| Native editing improvements | Specify one concrete workflow, its input state, the affected native files, the user-visible result and an acceptance fixture. An example is explaining an unsupported HDR export while keeping the source and edited sequence recoverable. | Implement in the native checkout, test the public API and the actual window, then compare original hashes before and after. |

**Read-only handback.** Include the implementation and baseline, reproduction steps using synthetic input, expected and observed behavior, suggested paths and tests, and what needs a maintainer with local access. A patch, a proposed test case or a precise finding is enough. Avoid claiming a model ran on the basis of a mock, an installed-file check or a roadmap entry.
