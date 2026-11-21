# Pessimistic review of the Stillwater master plan (r1)

PRIVATE BUILD — NOT FOR DISTRIBUTION.

Reviewed: `docs/STILLWATER_MASTER_PLAN.md` r1, against `docs/EASY_STUDIO_FINAL_PRD.md` and the code on the
integration branch (Nov 5, 2026). The question for every line was "how does this fail?". Each finding has an
id, a severity (High / Medium / Low), and what r2 of the plan does about it. Nothing is waved through because
it is inconvenient.

## A. A non-coder using it every day

| Id | Sev | Finding | r2 decision |
|---|---|---|---|
| UX-1 | High | Hiding the 12-tab sidebar behind "Classic tools" loses the owner's muscle memory, and a stale saved tab (`create`) in the browser would skip the new home entirely. | Home is the first screen after this version once (a version key in browser storage). Every Classic screen shows a "⌂ Home" button at the top of the sidebar. The tabs and their ids are unchanged. |
| UX-2 | High | Five clicks is easy to blow when required fields sit inside closed stages. | Subject is always open and cannot be switched off. Required fields say "needed" next to them. The browser test counts presses. |
| UX-3 | Medium | A Pose switch on a recipe that has no pose input is a lie. | Every recipe lists which stages it uses. Stages it does not use are shown greyed with a plain reason ("Films keep the pose of the still"). |
| UX-4 | Medium | A blank seed that silently becomes a number confuses later re-runs. | Blank means "pick one for me". After compiling, the form shows "Seed used: N", and exports carry N. |
| UX-5 | Medium | The node drawer is jargon. | Closed by default, labelled "For experts: the graph this sends (read only)". No editing. |
| UX-6 | Medium | Gate errors arrive as toasts far from the field ("Missing stated age"). | The recipe page shows the server's message under the stage it belongs to. |
| UX-7 | Low | The "21+" button now means "SFW off". | Keep the button label; its tooltip and the Settings line say "SFW mode is on/off" plainly. |
| UX-8 | Medium | "Edit this place" only in the web studio would mean editing somewhere other than where you play. | Edit happens inside the game (a Play mode). Promotion to the real file is one Python command (and the Play door shows it). |

## B. ComfyUI and LoRA pipeline

| Id | Sev | Finding | r2 decision |
|---|---|---|---|
| PIPE-1 | High | A compiler with its own copy of the graph logic will drift from the job, so the drawer and the hash would describe a graph that never runs. | The still and film jobs are split into `build_*_graph()` + run. The compiler calls the same builder. A test runs the job on the mock engine and checks the executed graph's canonical hash equals the compiled one. |
| PIPE-2 | High | `workshop_still` takes the seed from the character or a random number, so no recipe hash is stable. | `workshop_still` and `film` accept one more optional input, a whole-number `seed` (validated, no other new inputs). The gates still refuse every other extra key. |
| PIPE-3 | High | `_lora_hook` quietly attaches an unpaired file to both Wan 14B halves. | `route_lora()` raises a plain error for an unpaired LoRA on a 14B high/low loader. 5B and image loaders are unaffected. |
| PIPE-4 | High | The benchmark has its own `_attach_lora` that bypasses the hook. | The benchmark calls `route_lora()` too. A test monkeypatches `route_lora` and sees both paths use it. |
| PIPE-5 | High | A Quality stage that writes `steps` breaks Wan's shared high/low split. | The compiler refuses `steps` on any template with two `KSamplerAdvanced` nodes; the film recipe has no step control. Tested. |
| PIPE-6 | Medium | "Both strengths" on `LoraLoaderModelOnly` has no clip strength. | A model-only loader records clip strength as the literal `"model_only"`. A `None` anywhere in the key means no key. Both cases are tested. |
| PIPE-7 | High | Decompiling third-party graphs into stages would create a second ComfyUI. | One-way: third-party JSON/PNG is reported (missing models, missing node types, refused nodes) and can only run as `raw`. No custom-node installs. |
| PIPE-8 | Medium | Switching model family on one GPU process without freeing memory risks out-of-memory on real hardware. | The worker remembers the last family per process and calls `/free` on a change. On the mock it is visible in the mock log; tested. |
| PIPE-9 | Medium | Latent previews could leak into the library. | The client already skips temp previews (#23); the existing check "a temp still preview is not a saved file" in `tests/comfy_contract_tests.py` covers it. Recipes never read previews. |
| PIPE-10 | High | Cross-family latent wiring. | The film reads the still's pixels by `LoadImage`; the compiler verifies the sidecar sha256 against the file and refuses a mismatch. |
| PIPE-11 | Medium | A film recipe pointed at a still that is still rendering. | Send-to-next appears only on a finished, kept still. The film compile refuses an item that is not in the library. |
| PIPE-12 | High | `op://` strings in notes or preset names would leave in an export. | Recursive strip of every string containing `op://` (keys too). Tested at nested depths and in lists. |

## C. Is the game any fun?

| Id | Sev | Finding | r2 decision |
|---|---|---|---|
| FUN-1 | High | A door with one obvious switch is a chore, not a puzzle. | Two linked goals: both pads must be held at once (you and the companion), and the key must pass to the companion, who sets it in the door. Steps can be done in either order. |
| FUN-2 | Medium | Directing the companion through menus is text-heavy. | Click her plate: two short verbs only ("Stand on the far pad", "Take the key"). No dialogue tree. |
| FUN-3 | Medium | No feedback means confusion. | Pads glow when held; the door has two lamps (pads, key). The status line names the next missing step in five words or fewer. |
| FUN-4 | High | Editing can make the puzzle unsolvable (pads on top of each other, door in the sea). | The Python validator checks solvability: positions inside the beach bounds, pads at least 2 m apart, door not on a pad, prop reachable. Godot's editor clamps moves to the same bounds before saving a draft. |
| FUN-5 | Medium | Headless tests cannot judge feel or frame rate. | Feel is an owner playtest item in the handoff. Frame rate is not a gate. |
| FUN-6 | Medium | Wiring the puzzle into chat or dialogue would make it depend on the Ollama seam. | The puzzle never calls `chat_brain.gd`, `dialogue_runner.gd` or `scenes.json`. |

## D. Age, identity, consent, secrets

| Id | Sev | Finding | r2 decision |
|---|---|---|---|
| SAFE-1 | High | `_refuse_uploaded_undress` checks one hop, and `derived_role` relabels an upload's child as `made`. | Walk `parent` to the root; any upload role refuses; an unresolvable parent is treated as an upload. Two-hop test. |
| SAFE-2 | High | `job_raw` never runs the walk. | `job_raw` walks every loaded image against all workflow text. Test with a grandchild of an upload. |
| SAFE-3 | High | Checker-off is an allow-list for refusal, so any new kind runs with the checker off. | Fail closed: a kind runs with the checker off only if it is in a frozen list of today's checker-free kinds. The three kinds hard-coded in `server.py` move into `CHECKER_REQUIRED_KINDS`. Snapshot test over `pipelines.JOBS`. |
| SAFE-4 | High | A recipe export that carries a typed age would store an age nobody typed on import. | Recipes point at a saved character by id. A new character's age is typed into the Subject stage and saved with that character; exports never carry an age, and import leaves it blank. |
| SAFE-5 | High | The Subject picker could offer the player (`Me`). | The compiler refuses `real_person` and player records; the picker never lists them. Tested. |
| SAFE-6 | High | `sfw_mode = false` could be set by a request from an unattested device. | Setting it off needs the device attestation; effective `sfw_mode` is `true` whenever the device is not attested (including an expired PIN session). |
| SAFE-7 | Medium | Game: `adult_content: true` in an old settings file without the 21+ gate. | Maps to `sfw_mode = true`. Tested. |
| SAFE-8 | High | Puzzle actors could be loaded without a valid age or consent. | The validator reads each actor's character record: whole-number age ≥ 21 or refuse; `consent: "mutual"` per actor or refuse. |
| SAFE-9 | Medium | The dare deck could be filled early. | The schema ships empty; the validator refuses any card this milestone. |
| SAFE-10 | High | Third-party imports tempt weakening `NODE_DENY_RE`. | Unchanged. A face-swap node in an import is reported as refused. |
| SAFE-11 | Medium | Hidden helpers break the owner's visibility rule. | This session runs no subagents or background workers beyond plain test runs. |
| SAFE-12 | Low | The 21+ unlock still says "18 or older" in one server message. | Left as is this session (copy change outside the box); listed for the next session. |

## Summary
38 findings (8 UX, 12 pipeline, 6 gameplay, 12 safety). Every High finding changes r2. Two items are honest limits rather than fixes: feel/frame rate
(FUN-5) and the stale "18 or older" copy (SAFE-12).
