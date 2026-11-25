# Developing Candy for one person

Candy runs on one user's devices. Start with a concrete task someone wants to finish, such as reopening a project or exporting the frame on screen. Use the laptop and the local server in the example only when that workflow needs both.

## From request to working feature

1. **One owner writes the outcome.** Describe the starting screen, the action, what the user should see, and one way the operation could fail. Choose one synthetic fixture. The owner can make an ordinary fix directly.
2. **Build a complete, small change.** Reuse the existing UI, storage and engine entry points. Split out a second writer only for genuinely independent work with separate files and checks. Keep the public browser and local Mac test baselines distinct.
3. **Check the result at the screen.** Run the focused regression, use the normal launch path, try the failure and recover. For a UI change, use the keyboard, the smallest supported window and both system appearances. Use a reviewer for source preservation, migrations, credentials, access rules, destructive device operations or a model-quality claim. Retain the repository's required CI.
4. **Hand back once.** Give the revision, what now works, tests, a screenshot or synthetic output where useful, and the remaining limitation. Update the affected tutorial when its steps change. A read-only contributor can return the reproduction and proposed test directly.

## Effort by task

| Task | Starting assignment | When to change |
| --- | --- | --- |
| Checklist, status, naming or a known documentation edit | A deterministic command when possible, otherwise Sol Low | Move to Medium when evidence conflicts or several modules must be reconciled. |
| Coordination, ordinary features, browser UI and a short research decision | GPT-6.1 Sol Medium | Use High for a reproducible failure involving multiple layers or meaningful risk to saved work. |
| Persistence, media clocks, credential boundaries or difficult engine integration | GPT-6.1 Sol High with a bounded fixture | Escalate with the failed check and a specific question. Preserve authorized security-review procedures when applicable. |
| Visual review and native computer use | GPT-6.1 Terra Medium for a normal user journey | Use a stronger model when a real interaction, accessibility or visual defect remains unexplained after reproduction. |
| Exceptional engineering problem | Astra Extra High on the bounded problem | Consider Max only for an exceptionally hard unresolved case where the extra reasoning could change a concrete decision. Return to the ordinary setting after the check. |

The [Codex project configuration](../.codex/config.toml) sets the ordinary default for a trusted checkout. Existing chats can retain explicit session choices. These assignments are starting points. Current model guidance recommends testing lighter configurations against representative tasks. Reasoning effort, retries and time to an accepted result all matter. Subscription usage is shared and cannot be attributed to one project from its percentage alone. [Model selection](https://developers.openai.com/api/docs/guides/model-selection) · [Reasoning effort and evaluation](https://developers.openai.com/api/docs/guides/deployment-checklist) · [Project configuration](https://developers.openai.com/codex/config-basic/)

## What “easy to use” means here

| Journey | Observable acceptance check |
| --- | --- |
| First launch with the engine offline | The screen names the unavailable component in plain language, offers the next recovery action and lets the user recheck readiness. No prior knowledge of ports, weights or ComfyUI is required. |
| Reopen a project with a missing original | The UI identifies the missing source and explains how to recover. A relink-capable workflow accepts a replacement only after identity verification. A wrong file leaves the saved project intact. |
| Export a frame | A first-time user can tell which original and frame will be exported, choose a destination, see that export completed, and find the new file. Unsupported input explains what can be done next. |

These are acceptance criteria for changes. Record which were actually exercised. For a routing comparison, use the same fixture, instructions and pass criteria at two feasible effort levels. Count wrong results, retries, elapsed time and token usage where available. Keep the lighter setting when it meets the same quality bar. Do not spend a premium turn merely to generate a status update.
