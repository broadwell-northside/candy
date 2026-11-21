# The policy gate

Candy's rails have three layers (D-C-50).

1. **The hard floor**, fixed in `SAFETY.md` and in code, with tests. Minors and anything that makes an adult read as a child; real people and anyone's likeness but the owner's; identity-copy tools and real-person LoRAs; blood, violence, gore and hurtful depictions; non-consensual, abusive or degrading acts against people; cruelty to animals; other grave harm. The output age check: in the 18+ section a flag on a result is final (D-C-49a).
2. **Everything else is leeway.** Beyond the floor and the refusals already in code, the app adds none by default; the policy file can add more.
3. **The gray zone.** An optional gate on the owner's own machine reads a plain text file the owner writes ("what I don't want"), decides, and logs the reason.

## The file

- Location: `outputs/policy/my_policy.txt`, or, in a test run only (`EASY_STUDIO_TEST_RUN=1`), the path in `EASY_STUDIO_POLICY_FILE`. No file is shipped and none is created by the app.
- Plain UTF-8 text, at most 64 KB. Blank lines and lines starting with `#` are ignored. A file with nothing else in it asks nothing of the gate.
- **No file means the gate is off** and every job runs exactly as before.
- The file is handed to the gate as text and nothing more. No line is read as a command, so no line can switch a rail off. The gate can only add a refusal; it cannot lift one. Widening the leeway zone means taking a line out; narrowing it means putting one in.

## What runs, in order, for a job's text

1. The fixed rails (`safety.check_prompt`, `safety.check_area`, the age rules, the workflow and LoRA checks). A refusal here is final. The gate is not asked.
2. Only if a policy file is in use: the gate, through `app/policy_gate.py` (`enforce`), called once in `server.create_job` after the other gates and before the job is queued.
3. The output age check on every result, later, in the pipelines. It reads no policy and no setting: a flagged result is deleted in every section.

## Fail closed

With a policy file in place, a job is refused with a plain message when: the file cannot be read or is too large or not text; the gate raises, times out, is not set up, or answers in a shape the app does not know; the gate would have to leave this computer; or the decision cannot be logged.

## The log

`outputs/policy/gate_log.jsonl`, one line per decision: time, job kind, area, SHA-256 of the job's text and of the policy, allow or refuse, the gate's reason (shortened to 200 characters), and the error type if the gate failed. The text itself and the policy itself are never logged.

## What is built and what is not

Built: the interface (`Gate.decide(texts, area, kind, policy) -> (allow, reason)`), a stand-in (`StubGate`) the tests use, `LocalModelGate` (loopback only, no transport set up, so with a file in place it refuses: fail closed), the file reader, the log, the wiring, and tests of the mechanism on placeholder text. Not built: the transport to the owner's local model, a Setup control for the file, and any policy content. Sessions never write, read or test the owner's policy.
