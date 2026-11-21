# Upgrade the live check: design (not built)

Status: a design for review. Nothing here is built, and the pad rail is not touched by writing it down.

## What is true today

- Enrolment records the kind of live check it was made with (`liveness_kind`): `poses_only` with the shipped worker, `pad` only for a worker with a real presentation-attack check. The app accepts only the kinds in `ACCEPTED_LIVENESS`.
- The 18+ consent and every 18+ likeness job need an enrolment of kind `pad` (`ADULT_LIVE_KIND` in `app/owner.py`). With a pose-only enrolment they are refused with a plain message. Everyday pictures are not affected.
- The app holds one enrolled person. A second enrolment is refused; only the kill switch deletes the enrolment so that it can be redone.
- Nothing ships that can produce `pad`. That is intended: the rail stays shut until a real check exists and the reviewer accepts it.

## What "Upgrade the live check" would be

One new step on the owner card, shown only when the enrolment is kind `poses_only` and a `pad` worker is installed: **Upgrade the live check**.

1. The owner presses it and the page asks for a new live capture, with its own nonce, exactly like an enrolment step sequence.
2. The `pad` worker runs on that capture and must say two things: the capture is a live face (its presentation-attack score clears the worker's fixed threshold), and the face matches the already enrolled face under the same match rule and the same model name as every other check.
3. Only if both hold does the recorded kind change from `poses_only` to `pad`. The change is written once, under the same registry lock as other owner changes.
4. If either fails, nothing changes and no picture from the attempt is kept. The message says which one failed in plain words, without showing the picture.

What does not change: the enrolled face and its embeddings, the registry and hash lock, the private folder and its modes, the kill switch, the output check for 18+, the Add photos rules, and the rule that a second enrolment is refused. The upgrade adds no second person and replaces no embedding.

## Why not just enrol again

A second enrolment is refused by design, and the kill switch deletes everything the owner made. The upgrade has to prove "the same person, live" against the face already enrolled, so it cannot be a way to swap in a different face.

## The worker

- It follows the same worker contract as the face worker (`worker names its kind in its first line`), with kind `pad`.
- Candidate: Silent-Face-Anti-Spoofing (Apache-2.0). It would need an ONNX export whose weights are pinned by hash and downloaded from the Models page like any other group (size, 50 GB floor, SHA-256). Nothing is downloaded by the app on its own and nothing runs offline-unsafe.
- Whether a given worker earns the name `pad` is the reviewer's decision, on the worker's published error rates and on a test with real printed and screen attacks. Until then the name is not accepted.
- A worker that names no kind, or an unknown one, is refused, as today.

## What the page must say plainly

A camera-only check does not stop a virtual camera or a replay injected into the browser. It makes a printed photo or a phone screen held up to the lens fail. The upgrade page and `docs/FACE_CHECK.md` say this in a sentence, and the 18+ rail wording stays as strict as it is now. Whether that is enough for 18+ is the reviewer's decision, not the page's.

## Tests (when built)

- Stand-in `pad` worker: pass, spoof (fail), wrong face (fail), no kind, unknown kind.
- A failed attempt leaves no file, no record, no embedding and the kind unchanged.
- A pass changes the kind exactly once; a second pass is a no-op.
- 18+ consent is refused before and allowed after, with the stand-in only.
- A second enrolment is still refused after an upgrade.
- No real model runs and no photo is read in tests.

## Open for the reviewer

1. Is a camera-only `pad` check enough for the 18+ rail, given the virtual-camera limit?
2. Which worker earns the name `pad`, and on what evidence?
3. Should the upgrade also be offered when the enrolment is already `pad`, to refresh it? Proposed: no.
