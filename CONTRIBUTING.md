# Contributing

Easy Studio is a private, personal-use app. The owner is the reviewer that matters.
Write pull requests in plain language.

## One small change per pull request

- One feature, one bug fix, or one docs change.
- Do not mix a behaviour change with a drive-by reformat or a rename of unrelated files.
- The first import of the prototype stays as it was written. Later pull requests may
  format the files they touch. Run `ruff format` on those files only.
- CI runs `ruff check`, which looks for syntax errors and undefined names. It does not
  enforce spacing or quote style.

## Tests are required

A code change needs a test, or a short note explaining why a test cannot be run here
(for example, it needs the real GPU).

On a machine that has Python 3.12, ffmpeg, and the packages below:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/playwright install chromium
.venv/bin/python tests/run_tests.py
.venv/bin/python tests/ui_smoke.py
```

Windows uses `.venv\Scripts\python` instead of `.venv/bin/python`.

`tests/run_tests.py` starts a fake ComfyUI and checks the app, including the safety rules.
`tests/ui_smoke.py` opens every tab in a headless browser. It writes screenshots into
`docs/screenshots/`. Do not commit those screenshots unless the pull request is about
the look of a screen and the description says so.

The UI smoke test uses Google Chrome if `CHROME` or `/usr/bin/google-chrome` exists.
Otherwise it uses Playwright's Chromium.

To re-check the workflow files against a real ComfyUI (this needs the engine running):

```bash
.venv/bin/python tests/run_tests.py --real-comfy http://127.0.0.1:8188 --real-dir /path/to/ComfyUI
```

## Safety rules

Read `SAFETY.md` before changing prompts, uploads, workflows, LoRAs, training, the age
check, or the 18+ section.

Do not weaken those rules. A change weakens them if something the app refuses today
would be accepted afterwards. If the owner has explicitly asked for a narrower block,
the pull request description must say, in plain language:

- which refusal changes
- why
- which test shows the new line

Lingerie, bikinis, swimwear, and yoga clothes stay allowed.

## What never gets committed

- Model weights, checkpoints, and LoRA files
- `outputs/`, including `outputs/password.txt`
- The ComfyUI checkout, the trainer checkout, and virtualenvs
- Hugging Face tokens, Civitai keys, cookies, or payment details
- Photos of real people
- `__pycache__/` and other generated files

`.gitignore` already covers the usual ones.

## Coordination

Codex keeps the evidence inbox. Do not start a second one.

- The conversation is GitHub issue #1:
  https://github.com/broadwell-northside/easy-studio/issues/1
- The files that go with it are on the evidence branch, in `coordination/inbox/`
  and `evidence/`. Read `coordination/inbox/README.md` there.
- Acknowledge the exact message id and the commit you actually read.
- Ask for missing evidence with one bounded question. Do not ask for a new full crawl.
- Never put passwords, cookies, session exports, payment details, or API tokens in
  the issue or the repository.
- Evidence stays on its own pull request. Do not mix it into an app pull request.
