# Self-likeness v2: the owner's own likeness, in every section (design only, no code)

PRIVATE BUILD — NOT FOR DISTRIBUTION

**Scope in one line.** One person, the owner; one private app on his own machines; never for sale, never hosted for
anyone else.

**Status.** A design, for review before anything is built. No code, no SAFETY.md edit and no model run comes with
this document. It merges only on the owner's merge instruction, and every build that follows it is its own pull
request with its own review at an exact head.

**Decisions it implements.** D-C-31 (the owner trains a likeness of himself and makes an avatar for the game),
D-C-37 (the people rule: the "never 18+" floor of the first design is lifted for the owner's own likeness only, with
every control in section 3), D-C-46 (one person, one app; private for good; no blood, violence, gore or hurtful
depictions), D-C-48 (built thin first; the fixed rails stay hard), D-C-49a (the output check for a marked result,
section 3.13) and D-C-50 (a fixed floor, wide leeway, and a policy gate for the rest, section 5.4). The owner's words are in the team's decision log under AK-CANDY-SELF-AVATAR-20261106,
AK-CANDY-FINAL-LOOP-OBJECTIVES-20261119 and AK-CANDY-SCOPE-SINGLE-PERSON-NOT-FOR-SALE-20261119.

**What it replaces.** The first design (`docs/design/SELF-LIKENESS-20261106.md`, pull request #55, never merged) kept
the likeness out of the 18+ section and on one Mac. Its review does not carry over. This document stands on its own:
nothing in it depends on reading the first one.

**Code points.** Every file and line below is at commit 255807b of the development branch. A code point marked *(new)* does not
exist yet. One marked *(after #52)*, *(after #53)*, *(after #54)* or *(after R0)* lives in a pull request that is
open and not merged at that head.

**What nobody does.** Nobody building or testing this feature views a capture or a generated picture, reads
18+ text, or runs a model. Every check in this design is a number, a hash or a status. Tests use the mock engine and
made-up fixtures. The owner starts every real run himself, from the app.

---

## 1. Scope

**One person.** The app has exactly one enrolled person: the owner. A second enrolment is refused by the server
(section 3.2). The app is private and is never sold or hosted for others (D-C-46).

**What the likeness is for.** Pictures, and later clips, of the owner himself, in the everyday section and, after his
own separate consent step, in the 18+ section. A clothed 3D avatar of him goes to the game.

| Allowed | Refused |
|---|---|
| Enrolment by the app's camera, with a live check, on the owner's own passkey | Any uploaded or photo-library picture as a likeness or training source |
| One likeness LoRA trained from verified captures | A second enrolled person; any other real person, anywhere |
| Everyday-section jobs in the closed list (section 3.6), on a fresh passkey check | A second person in a likeness picture: in the prompt, in a reference picture, or in the result |
| 18+ jobs in the closed list, only with the consent record and inside the live-match window | Any 18+ likeness job without the consent record, or outside the window |
| A clothed, player-only 3D avatar for the game | The avatar unclothed, in an 18+ scene, or as a non-player character |
| A private, encrypted gallery that opens only for the owner | Likeness files or pictures on a hosted service, a rented machine, the server, the website, an evidence bundle, a pack |
| One switch that deletes everything, including every picture made with the likeness | Identity-copy tools, real-person LoRAs, raw workflows, and stacking the likeness with any other identity |
| | Blood, violence, gore and hurtful depictions, in every section (section 5) |

Clips come second. The clip job kinds are in the design (section 3.6), but they are switched on only after the
stills path has passed its build review, because every clip needs the many-frame face count of section 3.5.

## 2. The SAFETY.md change (proposed wording, not applied)

SAFETY.md line 5 says a pull request that weakens a rule must say so in plain language and the owner has to agree.
This section is that statement. The edit itself lands with the build, not with this document.

### 2.1 The three lines

| Line | Today | Proposed |
|---|---|---|
| 29 | "- No face-swap, no deepfake, and no real-person likeness." | "- No face-swap, no deepfake, and no real-person likeness. The one exception is the owner's own likeness, made and used only under "The owner's own likeness" below." |
| 41 | "- Training never uses photos of real people. That includes photos of the owner." | "- Training never uses photos of real people, with one exception: the owner's own likeness, trained only from pictures taken by the in-app camera as described below. An uploaded photo, and a photo of anyone else, is never a training picture." |
| 56 | "- The same adult-only and no-real-people rules apply inside the section." | "- The same adult-only and no-real-people rules apply inside the section. The owner's own likeness is used here only after his separate 18+ consent and a live face match, as described below. Nobody else's likeness is ever used here." |

### 2.2 A new section, after "No real people"

> ## The owner's own likeness
>
> - The app has one enrolled person: the owner. Nobody else can be enrolled, and nobody can enrol or unlock the
>   owner's likeness for him.
> - The likeness is made only from pictures taken in the app, with this machine's camera, on the owner's passkey,
>   with a live check. Uploads and the photo library are never used. A second face in the camera stops the capture.
> - Every capture and every result is age-checked. The stated age is 21 or older. The child and teen words stay on
>   the avoid list for every likeness picture, in every section.
> - A likeness result that the age check flags is never kept blurred. In the 18+ section it is deleted, always, and
>   nothing overrules that. In the everyday section it is kept only when the one face in it matches the owner;
>   otherwise it is deleted.
> - Use in the 18+ section needs a separate consent step, done live by the owner. It is off until he gives it, and he
>   can withdraw it at any time. Withdrawing it deletes the 18+ pictures made with the likeness.
> - An 18+ job with the likeness runs only for a short time after the owner has just passed a live face match. A
>   passkey alone is not enough.
> - A likeness picture shows one person. A prompt, a reference picture or a result with a second person is refused.
> - Everything made with the likeness is marked as the likeness, and so is everything made from that. The mark
>   follows the file's contents, not its name.
> - The likeness files and pictures stay on the owner's own machines, encrypted, in a private gallery that opens only
>   for him. They are never sent to a hosted service, a rented machine, the website, an evidence bundle or a pack.
> - The game gets a clothed 3D avatar and nothing else.
> - One switch deletes the captures, the trained model, the avatar and every picture made with the likeness.
> - The server refuses each of these. Hiding a button is not the control.

### 2.3 A new section for D-C-46

> ## No violence
>
> - Blood, violence, gore and hurtful depictions are refused in every section, including the 18+ section. That
>   covers prompts, notes, names, file names, LoRA text and raw workflows. The same words are on the avoid list of
>   every picture.

### 2.4 Which refusals change, why, and which test shows it

Today the app refuses each of these. After the build it accepts them, only for the owner's verified likeness, and
only behind the gates named.

| # | Refusal today (code point) | After the build | Gate |
|---|---|---|---|
| 1 | Training on photos of the owner: `lora_workshop.job_me_train` (lora_workshop.py:682) is closed *(after R0)*, and SAFETY.md line 41 forbids it | Training on verified in-app captures only | passkey; verified captures; section 3.1 |
| 2 | Any job with the player LoRA: `LoraLibrary.check_usable` (loras.py:231) and `lora_workshop.policy_reason` (lora_workshop.py:311) refuse a `player_only` LoRA everywhere | The likeness LoRA loads in the closed job list of the everyday section | passkey; section 3.6 |
| 3 | The same two code points, in the 18+ area; SAFETY.md line 56 | The likeness LoRA loads in the closed 18+ job list | 18+ consent record and live-match window; sections 3.3, 3.4 |
| 4 | `export_age` (pipelines_v3.py:435) refuses a real person in a game pack | One clothed avatar asset passes through its own branch | verified manifest; clothed lock; section 4.2 |
| 5 | `SEXUAL_ME` (lora_workshop.py:25) and `ME_SEX` (lora_workshop.py:32) refuse 18+ words for anything about the player | They keep applying to capture, training and the avatar. A render in the 18+ area follows the 18+ text rails (`safety.check_area`, safety.py:622) instead | 18+ consent record and live-match window |
| 6 | Section-bound LoRA families load only in the 18+ section (`photoreal.anatomy_loras`, photoreal.py:182), and the first design never stacked them with the likeness | They may stack with the likeness in the 18+ section | 18+ consent record and live-match window |
| 7 | A result the age check flags is blurred, held and cannot be reused (`JobContext.add`, pipelines.py:283) | In the everyday section only, a flagged likeness result whose one face matches the owner is kept unblurred. It can never be an input to an 18+ job. In the 18+ section a flag stays final, and stricter than today: the result is deleted | the likeness mark; the owner match; section 3.13 |

**Why:** the owner's decisions D-C-31, D-C-37 and D-C-46.

**Which tests show it:** `tests/owner_likeness_tests.py` *(new)*, listed per control in section 3. Each row above
has an "allowed with the gate" check and a "refused without it" check.

**Everything else refuses more than today.** Nothing else in SAFETY.md moves. In particular: the 21+ floor, the age
check, the celebrity and real-person refusals, the identity-copy denylist, the upload roles, the rule that an
uploaded picture never has its clothes removed (`pipelines._refuse_uploaded_undress`, pipelines.py:376), and the
extra 18+ blocks for themes that make an adult look like a child.

The README repeats today's rule (README.md lines 16 and 26–27). It gets the matching edit in the same build.

---

## 3. The controls

Each section has the same four parts: the control, the code points that enforce it, the tests that prove it, and
what breaks without it. All twelve rows of the people rule are here, in the same order.

### 3.0 What a likeness job is

One definition, used by every gate in this document.

**A likeness job is any job that loads a registered LoRA hash, or has a marked input, or has an input with a marked
ancestor.** A marked 18+ picture that is edited or upscaled loads no LoRA at all, and it is still a likeness job.

- One function answers it: `owner_policy.is_likeness_job(kind, params, loras)` *(new)*. It uses the registry
  (section 3.6) and the fail-closed walk `has_likeness_ancestor`.
- It is asked twice: at submit (`app/server.py:408` `create_job`) and again in the worker (`app/server.py:326`
  `worker`), and once more when a LoRA is attached (`app/pipelines.py:131` `_lora_hook`), because a workflow can
  name a LoRA the request did not.
- Every gate uses that one answer: the passkey check (3.2), the closed job lists (3.6), the 18+ consent record
  (3.3), the live-match window (3.4), the one-face rule (3.5), the marks on outputs (3.6), the private gallery
  (3.9), the refusals to leave the machine (3.10), and the engine handle (3.10).
- No gate keeps its own narrower test. A gate that asked only "is the likeness LoRA attached?" would miss an edit
  of a marked picture.

**Tests.** For each gate, the same three cases: a job that attaches the LoRA, a job with a marked input and no
LoRA, and a job whose input has a marked ancestor two steps back. In particular: an 18+ `edit` and an 18+ `upscale`
of a marked item, with consent and no live-match window, are refused.

**Without it.** A picture of the owner is edited, upscaled or sent somewhere by a job that no gate looked at.

### 3.1 Capture only in the app's camera, with a random live check

**Control.**
- Enrolment pictures come only from `getUserMedia` in the app, posted to the capture routes. There is no upload
  field and no photo-library path. The old upload route for `Me` is closed *(after R0)* and stays closed.
- `POST /api/owner/capture/start` needs a fresh passkey check. The server answers with a session id and a **random
  challenge plan**: six to eight steps in random order (turn left, turn right, blink twice, look up, smile, and a
  screen-light step where the page shows two server-chosen colours). Each step has its own time window and a
  one-time nonce.
- The server refuses a frame that arrives outside its step's window, repeats a hash, does not decode as an image,
  is held or flagged by the age check, or shows anything other than exactly one face.
- A second face in any frame ends the whole session. It cannot be committed.
- `POST /api/owner/capture/commit` needs a passkey check. It runs the live check, then the owner match (section
  3.2), then writes a signed provenance record.
- The live check runs on the machine's own processor with a local face-landmark model. It looks for a blink, head
  turns on both sides, a face shape that stays stable while the eyes close, real frame-to-frame motion, the order
  and timing of the plan, and the face area following the two screen colours. With no detector it fails closed.
- Each capture is a library item with `role: "owner_capture"`, `owner_likeness: true`, `owner_id`, `stated_age`,
  `area: "default"`. The role is not in `PERSON_ROLES` or `REF_ROLES`, so a capture is never an input to a picture
  job. It is an input to training only.

**Code points.**
- `app/routes_owner_capture.py` *(new)*: the three capture routes.
- `app/owner_liveness.py` *(new)*: the live check and the owner match.
- `app/owner_auth.py` *(new)*: the passkey check.
- `app/routes_v3.py` `workshop_me_photo`, `workshop_me_curate` *(after R0)*: closed, with tests.
- `app/server.py:633` `upload`, line 637: the general upload route takes only `UPLOAD_ROLES` (library.py:30), which
  has no likeness role.
- `app/library.py:28–30` `PERSON_ROLES`, `REF_ROLES`, `UPLOAD_ROLES`: `owner_capture` joins none of them.
- `app/library.py:178` `person_image`, `:193` `ref_image`: both refuse a role outside their lists.
- `app/age_guard.py:253` `AgeGuard.check`: runs on every frame, as it does on every output.
- `app/age_guard.py:30` `CHECKER_REQUIRED_KINDS`: the capture and training kinds join it, so they refuse while the
  checker is off.

**Tests.**
- A frame outside its window, a repeated hash, a non-image, a frame the age check holds or flags, and a frame with
  no face are each refused.
- Two faces in one frame end the session, and a commit after that is refused.
- A missing detector, a static frame set, an out-of-order plan and a failed screen-light step each fail.
- The upload route and the curate route refuse a fully valid request and save nothing *(after R0, already in
  `tests/lora_workshop_tests.py`)*.
- The general upload route refuses `owner_capture` and both `player_me_*` roles *(after R0)*.
- `person_image` and `ref_image` refuse a capture item.

**Without it.** Any photo of any person becomes "the enrolled person".

### 3.2 The owner enrols and unlocks only his own likeness

**Control.**
- **Passkey.** The owner registers one passkey with the machine's platform authenticator (Touch ID). The private key
  never leaves the Secure Enclave. The server stores the credential id and public key in `outputs/owner/owner.json`.
  `owner_id` is the SHA-256 of the credential id.
- **One owner.** When `owner.json` exists, a second passkey registration and a second enrolment are refused. Only the
  kill switch (section 3.11) clears it.
- **Every likeness action needs a fresh passkey check:** start and commit a capture, give or withdraw 18+ consent,
  train, render, open the private gallery, export the avatar, pair the Studio, and delete. The check needs user
  verification, is under five minutes old, and is bound to a one-time server nonce.
- **Secure context only.** Passkeys work on `localhost` or HTTPS. Over plain HTTP from another machine, every
  likeness action is refused.
- **Own match set.** The first verified capture session stores an enrolment set of face embeddings, encrypted. Every
  later capture session, and every live match (section 3.4), must match it or it stops. The embedding model is
  imported by `owner_liveness.py` and by nothing else. The app gains no face recognition anywhere else.
- **The check travels with the job.** At submit, the job record stores the verified check (`owner_id`, nonce, job
  kind, area, time; never a secret). The worker checks it again before it decrypts anything.
- **The key needs the owner present.** The secret that signs records and encrypts files is a Keychain item with a
  biometry access control (`kSecAccessControlBiometryCurrentSet`). The Keychain releases it only after Touch ID, and
  only to the app's small signed helper. Without the helper, every likeness action is refused.
- **Another person** is outside this app. Someone else who wants the same thing runs their own copy, under their own
  macOS account, with their own passkey and their own face. This app has no way to hold a second person.

**Code points.**
- `app/owner_auth.py` *(new)*: registration, the check, the secure-context gate, the one-owner refusal.
- `app/helpers/owner-key/` *(new, Swift)*: the Keychain item and its release.
- `app/server.py:408` `create_job`: binds the owner check into the job record.
- `app/server.py:326` `worker`: checks the record again before `pipelines.JOBS[kind]` runs.
- `app/owner_liveness.py` *(new)*: the only importer of the embedding model.

**Tests.**
- No passkey check, a stale check and a check bound to another nonce each refuse every likeness action.
- A second registration and a second enrolment are refused.
- Plain HTTP from a LAN address is refused.
- A capture session that does not match the enrolment set stops.
- A job whose record's owner, kind or area changed after submit is refused in the worker.
- Without the key helper, every likeness action is refused.
- No module other than `owner_liveness.py` imports the embedding model (an import scan).

**Without it.** One person makes pictures of another. A present for someone else is theirs to accept in their own
enrolment, on their own account.

### 3.3 A separate 18+ consent step, live, off by default, withdrawable

**Control.**
- Enrolling does not open the 18+ section for the likeness. That takes its own step.
- **Giving consent** needs, in one sitting: a fresh passkey check, a live face match (section 3.4), and the owner
  pressing one button under a fixed statement. Nothing is pre-ticked.
- **The record** is `outputs/owner/consent_18.json`: `owner_id`, the time, the SHA-256 of the statement shown, the id
  of the live-match record, the machine id, and a signature made with the Keychain secret. A record that does not
  verify counts as no consent. A changed statement needs consent again.
- **Off by default.** No record means every 18+ likeness job is refused.
- **Withdrawing** takes a passkey check and one button. It needs no live match: stopping is easier than starting.
  It removes the record, cancels queued 18+ likeness jobs, and deletes every marked 18+ item (section 3.11 walks
  them). Everyday likeness pictures and the avatar stay.
- The consent record never leaves the machine and is never shown in a log.

**Code points.**
- `app/owner_consent.py` *(new)*: give, verify, withdraw.
- `app/routes_v3.py:67` `adult_unlocked`, `:81` `want_area`: the device's 18+ unlock still applies first. Consent is
  a second lock on top of it, for the likeness only.
- `app/loras.py:231` `check_usable`: refuses the likeness LoRA in the `adult` area without a verified record.
- `app/server.py:408` `create_job` and `:326` `worker`: refuse any 18+ likeness job (section 3.0) without a verified
  record.

**Tests.**
- With no record, every 18+ job kind in the list is refused for the likeness.
- A record with a broken signature, another `owner_id` or an old statement hash counts as none.
- Giving consent without a live match in the same sitting is refused.
- Withdrawal needs no live match, cancels queued jobs, deletes the marked 18+ items, and leaves everyday items.
- After withdrawal, every 18+ job is refused again.

**Without it.** Enrolling for an avatar silently becomes consent to something else.

### 3.4 18+ likeness jobs run only inside a live-match window

**Control.**
- A **live match** is a short capture challenge (three random steps from the plan of section 3.1), with exactly one
  face, matched against the enrolment set, on the machine where the owner is sitting.
- A pass opens a **window** of ten minutes. The window record (`owner_id`, start, end, nonce, machine id) is signed
  and kept in memory only. Restarting the app closes it.
- An 18+ likeness job (section 3.0: a LoRA, a marked input or a marked ancestor) must be submitted inside the
  window and must start inside it. The worker checks the window again before it runs the job, whether or not the
  job decrypts a LoRA. A job that has not started when the window ends is cancelled with a plain
  message. A job that started in time may finish.
- A passkey check alone never opens the window, and the window never replaces the passkey check.
- Everyday-section likeness jobs need the passkey check and not the window.

**Code points.**
- `app/owner_liveness.py` *(new)*: `live_match`.
- `app/owner_policy.py` *(new)*: the window, and the thread-local owner context the job runs in (the pattern of
  `pipelines.set_area` and `area()`, pipelines.py:62–66).
- `app/server.py:408` `create_job` and `:326` `worker`: the two checks.
- `app/pipelines.py:131` `_lora_hook`: refuses the likeness LoRA in the `adult` area with no open window.
- `owner_policy.is_likeness_job` *(new)*: the one test all three use (section 3.0).

**Tests.**
- With consent and no window, an 18+ likeness job is refused: one that attaches the LoRA, an 18+ edit of a marked
  item, and an 18+ upscale of a marked item.
- A window from a failed match, a match with two faces, or a match against another face never opens.
- A job submitted in the window and started after it is cancelled.
- An app restart closes the window.
- An everyday likeness job runs with a passkey check and no window.

**Without it.** A shared Mac or a borrowed fingerprint makes 18+ pictures of someone who is not there.

### 3.5 One face only: the prompt rail and an output face count

**Control.**
- **Before the job.** A likeness job refuses text that introduces a second person, any `people` list, any group
  record, and any reference picture with a person role. Clothing, object and background references and stick-figure
  poses are allowed.
- **After the job.** Every likeness result is counted by the face finder the age check already runs:
  - a still must show exactly one face;
  - a clip is sampled at every twelfth frame, at least eight frames, and each sampled frame must show exactly one;
  - two or more faces in any picture or frame: the result is refused and not saved;
  - no face: the age check already answers "unchecked", and the app already refuses to save that.
- The count applies in every section.
- A 3D model is made from a likeness still that has already passed.

**Code points.**
- `app/safety.py:424` `people_mentioned`, `:457` `check_group_prompt`, `:438` `scene_records`: the prompt rail.
- `app/server.py:222` `_gate_stated_ages`, `:183` `_gate_create_ages`: refuse a `people` list for a likeness job.
- `app/workers/age_check_worker.py:51–76`: the face finder; its answer carries `faces`.
- `app/age_guard.py:100` `gate`: keeps `faces` in the answer.
- `app/pipelines.py:283` `JobContext.add`: where every output is checked before it is saved. The face-count rule for
  a marked job goes here.
- `app/age_guard.py:310` `check_video`: samples three frames today. A likeness clip uses the denser sampling
  *(new function beside it)*.

**Tests.**
- A likeness prompt that adds a second person is refused, with each form `tests/group_binding_tests.py` already lists.
- A `people` list and a person-role reference are refused.
- A mock result with two faces is refused and not saved; one face is saved; no face is held.
- A mock clip with two faces in one sampled frame is refused.
- The same checks pass in the everyday area and the `adult` area.

**Without it.** A second person appears in the picture. On Nov 6 a one-person prompt produced a still with two
faces; the prompt rail alone does not stop that.

### 3.6 The lock follows the file, the mark follows the picture, the walk fails closed

**Control.**
- **The lock is set from a signed manifest, not from an editable field.** The trainer writes a `likeness_manifest`
  (capture hashes, session ids, trainer config hash, base model, signature) beside the LoRA. No sidecar edit, LoRA
  override or `outputs/*` override file can add the lock or clear it.
- **The lock follows the file's SHA-256.** Every verified manifest adds its file's hash to a signed registry,
  `outputs/owner/likeness_registry.json`. Every LoRA a job names is resolved and hashed (cached by path, size and
  modification time) and looked up there. A match is locked whatever its name, folder or sidecar says. That covers a
  renamed copy, a copy outside the LoRA folder, and a name inside a raw workflow.
- **The closed job lists** (`OWNER_KINDS`):
  - everyday: `create`, `edit` (outfit, scene and expression operations), `turnaround`, `expressions`, `upscale`,
    `model3d`, `export_godot` (the avatar asset only);
  - 18+: `create`, `edit` (the same operations), `upscale`;
  - clips, switched on later: `video`, `extend`, `video_any`.
  A locked LoRA in any other job kind is refused. Adding a kind is one line and one test.
- **Stacks.** The likeness is never stacked with a LoRA whose role is character, player or face, or with another
  identity. Section-bound families follow their section's rule.
- **Every output is marked.** When a locked LoRA passes the hook, the running job records `{owner_id, sha256}`.
  Every output of that job is saved with `owner_likeness: true`, `owner_id`, and the hash list in
  `provenance.likeness_loras`. Every job also records the LoRAs it attached in `provenance.loras`.
- **The mark is inherited.** Anything made from a marked item is marked.
- **The walk fails closed.** `has_likeness_ancestor` is true when the item or any ancestor is marked, or when any
  recorded LoRA hash is in the registry. A missing parent or a loop counts as likeness.
- **A marked item is never** a fictional character's portrait, a training picture for any other LoRA, a keyframe
  for another character, or an input to a job outside the lists.
- **The decrypted copy** used for a render has a random name, sits in a private per-job model folder that only the
  app's own engine is given (section 3.10), is registered as locked for that job only, and is deleted in a `finally`
  when the job ends. At startup the app deletes every leftover.
- A revoked hash stays in the registry as revoked, so a stray copy is refused for good (section 3.11).

**Code points.**
- `app/loras.py:173` `LoraLibrary.record`, `:231` `check_usable`: the lock by hash.
- `app/loras.py:153` `write_sidecar`: cannot set or clear the lock.
- `app/pipelines.py:131` `_lora_hook`: every LoRA on every model loader goes through `check_usable`.
- `app/pipelines.py:194` `_adv`, `app/comfy_client.py` `inject_loras`: the stack rule.
- `app/pipelines.py:283` `JobContext.add`: marks outputs.
- `app/pipelines.py:454` `_meta_from`: carries the mark.
- `app/pipelines.py:341` `_lineage_get`, `:348` `has_upload_ancestor`: the pattern the new walk follows.
- `app/pipelines.py:1279` `job_raw`: not in the lists; a registered hash inside a raw workflow is refused.
- `app/server.py:722` `_check_hero`: refuses a marked item as a character's portrait.
- `app/pipelines_v3.py:227` `_check_training_source`, `app/lora_workshop.py:413` `still_source_ok`: refuse a marked
  item as training input for any other LoRA.
- `app/lora_workshop.py:466` `_finish_lora`: writes the manifest.
- `app/owner_registry.py` *(new)*: the registry, the hash cache, the startup cleanup.
- `app/owner_policy.py` *(new)*: `OWNER_KINDS`, `has_likeness_ancestor`.
- *(after #54)* the proof mark (`is_proof`, `proof_mark`) uses the same inheritance and the same walk.

**Tests.**
- A sidecar edit cannot clear the lock; a file with a broken manifest is blocked.
- A renamed copy with no sidecar, a copy outside the folder, and a copy named by a raw workflow are each refused
  outside the lists and in 18+ without the gates.
- Each job kind outside the lists refuses the likeness LoRA (one check per kind).
- A stack with another identity, character, player or face LoRA is refused.
- Every output of a likeness `create`, `edit`, `turnaround`, `expressions` and `upscale` is marked.
- An edit of a marked item is marked. An item with a registered hash in `provenance.loras` and no mark is caught.
- A missing parent and a parent loop each count as likeness.
- A marked item is refused as a character's portrait and as training input for another LoRA.
- The decrypted copy has a random name and is gone after the job; after a simulated crash it is gone at startup.

**Without it.** A renamed LoRA copy, or a picture made from a likeness picture, escapes every other rule here.

### 3.7 Identity-copy tools, real-person LoRAs and other people's photos stay refused

**Control.** Nothing in this design touches these refusals. The likeness path is one narrow door for one person.
- The node denylist and the workflow check refuse identity-copy tools in every section, Advanced mode included.
- The LoRA checks and the importer refuse real-person and celebrity LoRAs, with the exact allowlist unchanged.
- An upload is a clothing, object, background, pose or scenery reference, or the owner's own fictional art. It is
  never an identity, and never a likeness source.
- A likeness job cannot contain an identity-copy node at all: raw workflows are outside the lists.
- Celebrity and named-real-person text is refused in likeness jobs as in every job.

**Code points.**
- `app/safety.py:88` `NODE_DENY_RE`, `:217` `check_workflow`, `:143` `check_prompt`, `:646` `check_lora`.
- `app/loras.py:420` `civitai_check`, `:481` `allowlisted`, `app/lora_allowlist.json`.
- `app/server.py:633` `upload`, `:202` `_refuse_scenery_as_person`.
- `app/pipelines.py:376` `_refuse_uploaded_undress`.

**Tests.**
- The existing suites for these refusals pass unchanged with the feature on: `tests/rails_tests.py`,
  `tests/lora_allowlist_tests.py`, `tests/v3_tests.py`, and the importer checks in `tests/lora_workshop_tests.py`.
- A likeness job with a denylisted node, a real-person LoRA or a celebrity name is refused.
- A second real person cannot be enrolled by any route (section 3.2).

**Without it.** The likeness path becomes a general real-person tool.

### 3.8 The minors rails are untouched, in every section

**Control.**
- The stated age is 21 or older, for the enrolment and for every job.
- Every capture is age-checked. Every result is age-checked. Every training picture is age-checked again right
  before training *(after R0)*.
- The child and teen words are on the avoid list of every likeness picture, in every section.
- The minor-word, look-alike-letter and stated-age text checks run on every likeness prompt.
- The extra 18+ blocks for themes that make an adult look like a child apply to the likeness as to everything else.
- A likeness result that the age check flags is never kept blurred. What happens to it is section 3.13: deleted in
  the 18+ section, always; kept in the everyday section only on an owner match.
- With the checker off, every likeness action refuses.

**Code points.**
- `app/safety.py:304` `require_stated_age`, `:44` `MIN_AGE`, `:189` `check_minor_and_age`, `:581` `safe_negative`,
  `:622` `check_area`.
- `app/pipelines.py:122` `safe_neg_for`, `:283` `JobContext.add`.
- `app/age_guard.py:253` `AgeGuard.check`, `:310` `check_video`, `:60` `held_unusable`, `:30`
  `CHECKER_REQUIRED_KINDS`.
- `app/lora_workshop.py` `recheck_training_pictures` *(after R0)*.

**Tests.**
- A stated age of 20, or none, refuses enrolment and every likeness job.
- A flagged capture is refused. A flagged likeness result follows section 3.13.
- The avoid list of a likeness job in the `adult` area still carries the child and teen words (the mock log).
- Each extra 18+ block still refuses with the likeness LoRA attached.
- With the checker off, capture, training and every likeness job refuse.

**Without it.** The floor of the whole rule set goes.

### 3.9 An encrypted private gallery

**Control.**
- Every marked item is stored AES-GCM encrypted under `outputs/owner/gallery/`, thumbnails included. The key comes
  from the Keychain secret of section 3.2, so it needs Touch ID.
- A marked item is hidden from the ordinary gallery, lists and file links. The server answers for it only on a
  fresh owner passkey check. A marked 18+ item also needs the device's 18+ unlock.
- The server decrypts in memory and streams. It writes no decrypted picture to disk. The one exception is the input
  of a running job, which gets a random name in the job's temporary folder and is deleted when the job ends.
- The folder is readable by the owner's macOS account only.
- The gallery lives on the machine that captured. The Studio never holds it (section 4.1).

**Code points.**
- `app/library.py:88` `Library.add`, `:84` `url`, `:148` `list`, `:211` `AreaView`: marked items are stored and
  listed through the private store.
- `app/server.py:706` the `/files/{path}` route and `:697` `_file_area`: refuse a marked file without the owner
  check.
- `app/server.py:574` `item_json`, `:589` `_item_for`, `:600` the item route: the same.
- `app/owner_gallery.py` *(new)*: encrypt, decrypt to memory, stream.

**Tests.**
- A marked item is absent from `/api/gallery` and its file link answers "not found" without the owner check.
- A marked 18+ item also refuses without the 18+ unlock.
- The bytes on disk are not a readable image (the file does not decode).
- No decrypted file is left after a view, after a job, or after a simulated crash and restart.

**Without it.** On a shared machine, someone else browses the owner's pictures, and a copied folder leaks them.

### 3.10 Nothing of the likeness leaves the owner's machines

**Control.** Each destination below is refused by the server, for any marked item, any job that loads a registered
hash, and any 18+ item.

| Destination | Refusal | Code point |
|---|---|---|
| A hosted API | A request to a remote provider with a likeness mark, an 18+ area, or an image or video part is refused | the remote provider adapter *(new, with the chat work)* calls `owner_policy.may_leave` *(new)* |
| A rented machine | The backend adapter refuses a likeness or 18+ job for every backend. A likeness job reaches an engine only through an engine handle (below), and a rented machine can never hold one | the backend adapter *(new)*; `app/owner_engine.py` *(new)* |
| The server | The server has no pairing, so it can never hold an engine handle (below). It becomes a likeness host only through its own reviewed design | `app/owner_engine.py` *(new)* |
| Any engine the app cannot prove is local or paired | A likeness job never uses the configured engine address. It runs only on an **engine handle** (below) | `app/server.py:50` `COMFY_URL`, `:97` `COMFY`; `app/comfy_client.py:653` `ComfyClient`; `app/owner_engine.py` *(new)* |
| The website | A marked or 18+ item is never staged | the staging script *(after #52)* |
| The evidence bundle | The same | the evidence tool *(after #53)* |
| A game export | Only the clothed avatar asset of section 4.2 passes; every other marked item is refused | `app/pipelines_v3.py:593` `job_export_godot`, `:435` `export_age` |
| A pack or a zip | A pack that holds a marked item is refused | `app/pipelines.py:1234` `job_export`, `app/creator_tools.py:392` `pack_status` |

**The engine handle.** An address does not show where an engine is. The kit's link forwards this machine's
`127.0.0.1:8188` and `8189` to the server, so a loopback address can be another machine. A machine profile does
not show it either: the profile is picked by an environment variable or an override file, and section 3.6 says an
editable field never carries the lock. So a likeness job is tied to the engine itself:
- **Local engine.** For a likeness job the app starts its own engine process, bound to `127.0.0.1` on a port it
  picks, and keeps the process handle. Before each job it checks that the process listening on that port is the
  child it started. A port owned by anything else, an SSH forward included, is refused.
- **The child engine runs bare.** It starts with custom nodes off. The decrypted LoRA sits in a private per-job
  model folder that only the child engine is given. It is never put in the shared LoRA folder, which the ordinary
  engine also reads.
- **Paired Studio.** The only other handle comes from the pairing of section 4.1. The app opens its own channel over
  the link and the Studio worker answers a fresh challenge with the pairing secret. A forward that already exists is
  never used.
- `COMFY_URL`, the machine profile and the placement file choose the engine for every other job. They cannot give a
  likeness job an engine.
- Nothing else can make a handle. The server, a rented machine and a hosted service have no pairing.

The avatar row is the one place this design reads the people rule narrowly. The rule says the likeness never goes to
a game export. The owner's decision D-C-31 is that his avatar goes into the game. This design lets exactly one thing
through: the clothed avatar asset. The review accepted that reading, with two limits:
- the export target is the game folder on the owner's own machines. It is never a pack, a zip or an upload;
- the asset keeps its mark, so the kill switch finds it and removes it.

There is no cloud step anywhere in capture, training or rendering.

**Tests.** One refusal per row, each with a marked item, with an unmarked item that carries a registered LoRA hash,
and with an 18+ item. For the engine handle:
- with the kit's forward up (a listener on `127.0.0.1:8188` owned by another process), a likeness job is refused;
- `COMFY_URL` pointing anywhere, and each machine profile, cannot give a likeness job an engine;
- the app's own child engine is accepted, and the same port owned by another process after the child exits is refused;
- the child engine's start line has custom nodes off, and the decrypted LoRA is not in the shared LoRA folder;
- a Studio worker that cannot answer the pairing challenge gives no handle.

**Without it.** Pictures of a real person land on someone else's machines.

### 3.11 A kill switch that also removes every marked output

**Control.** `DELETE /api/owner/likeness`, on a passkey check, removes:
- the captures, the provenance records and the enrolment set;
- the 18+ consent record and any open window;
- the training folders and caches;
- the LoRA, encrypted and decrypted, and every leftover copy in the ComfyUI folders;
- the avatar assets, including the copy imported into the game folder;
- **every marked item**: the switch walks the library by mark, by ancestry and by recorded LoRA hash, and deletes
  each item's file, thumbnail and record. It bypasses the trash folder;
- the engine's input, output and temporary files for likeness jobs;
- the Studio's copies, by a wipe command over the link, confirmed by a listing (section 4.1).

Then it:
- keeps each LoRA hash as **revoked**, so a stray copy stays refused for good. The switch deletes the Touch ID
  secret, so the revoked list cannot depend on it. It is kept in a second Keychain item that has no biometry control
  and survives the switch, and mirrored in a file signed with that item. A list that is missing or does not verify
  while a tombstone exists stops every LoRA from loading until it is restored;
- writes a dated tombstone with counts and no names;
- lists what is left, which must be nothing;
- clears `owner.json`, so a new enrolment starts from zero.

If the Studio cannot be reached, the switch finishes locally, records "Studio wipe pending", and refuses any new
enrolment until the wipe is confirmed.

Withdrawing the 18+ consent (section 3.3) is the same walk, limited to marked 18+ items.

**Code points.**
- `app/routes_owner_capture.py` *(new)*: the route.
- `app/owner_registry.py` *(new)*: the revoked list.
- `app/library.py:137` `Library.delete`: moves to `_trash` today; the switch removes for good.
- `app/owner_policy.py` *(new)*: the walk.

**Tests.**
- After the switch, no capture, enrolment set, consent record, LoRA, decrypted copy, avatar file or marked item is
  left, and `_trash` holds none of them.
- An unmarked item with a registered hash in its provenance is removed too.
- A copy of the LoRA placed back in the folder is refused as revoked.
- With the revoked file deleted or edited, every LoRA load is refused until it matches the Keychain copy again.
- An unreachable Studio leaves "wipe pending" and blocks a new enrolment.
- The tombstone holds counts and no file names.

**Without it.** Withdrawing consent leaves the pictures behind.

### 3.12 Nobody building the app views the media

**Control.**
- Every check in this design is a number, a hash, a count or a status.
- The tests run on the mock engine and on fixtures drawn by the tests themselves.
- No test, log, fixture, pull request or bundle holds a capture, a likeness picture or 18+ text.
- The first real run of each step is the owner's, from the app. He reports numbers, not pictures.

**Code points.** `tests/mock_comfy.py`, `tests/fake_age_worker.py`, `tests/run_tests.py`; `.gitignore` keeps
`outputs/` out of the repository.

**Tests.** A repository check in CI refuses any tracked file under `outputs/`, any tracked model file
(`.safetensors`, `.gguf`, `.ckpt`), and any tracked file under an `owner/` folder. The tracked pictures in
`docs/screenshots/` are drawn by the mock engine in the UI smoke test and are not part of this check. gitleaks runs
as today.

**Without it.** The rule that keeps the owner's pictures private is broken by the work itself.

### 3.13 The output check for a marked result

This section is decision D-C-49a. A face match shows whose face it is. It does not show how old the person in the
picture looks. So a match never overrules the age check where pictures are explicit.

**Control.** Every result of a likeness job (section 3.0) is age-checked and face-counted before it is saved, as
every result is today. A flag on a marked result is then handled by section, and never by blurring:

| Case | What happens |
|---|---|
| 18+ section, the age check flags the result | **Final.** The result is deleted. It is not blurred, not kept and not shown. A face match, a setting and a policy file (section 5.4) cannot change this. The message says so plainly and offers a retry with a new seed |
| Everyday section, flagged, and the one face matches the owner's enrolment set | Kept, unblurred. The item records `age_override: "owner_match"`, the match score and the check's own answer in its provenance |
| Everyday section, flagged, and the face does not match, or the match cannot run | Deleted |
| Any section, the face does not match the owner, or there is more than one face | Refused and not kept (section 3.5) |
| Any section, the check cannot answer (unchecked, unavailable, error, timeout, off) | Held and not saved, as today |
| A result with no mark | Today's behaviour, unchanged: blurred, held, no reuse |

- An item kept by the override is never an input to an 18+ job, and neither is anything made from it.
- For a clip, one flagged sampled frame is a flag on the clip.
- The match runs only inside the gated path of section 3.2. It is the same match as the live match, on a picture
  in place of the camera.
- If false flags turn out to be common on the owner's real runs, the fix is in how the check samples and reports,
  with his numbers. It is never an identity override in the 18+ section.

**Code points.**
- `app/pipelines.py:283` `JobContext.add`: the age check on every output, the blur and the hold (lines 287–306).
  The marked-result cases go here.
- `app/age_guard.py:253` `AgeGuard.check`, `:310` `check_video`, `:60` `held_unusable`, `:79` `saved_blocked`,
  `:296` `blur_in_place`, `:353` `blur_video`.
- `app/library.py:170` `_not_flagged`, `:178` `person_image`: where a kept item is offered as an input. The
  refusal of an overridden item for an 18+ job goes with `owner_policy.is_likeness_job` *(new)*.
- `app/owner_liveness.py` *(new)*: the match against the enrolment set.
- The mark and the registry: section 3.6.

**Tests.** One per case:
- 18+, flagged: deleted, nothing saved, and the message offers a retry with a new seed;
- 18+, flagged, with a passing face match: still deleted;
- 18+, flagged, with every setting and a policy file that says to keep it: still deleted;
- everyday, flagged, match passes: saved unblurred, with the override in its provenance;
- everyday, flagged, match fails, and match unavailable: deleted;
- an overridden item, and an edit of it, are refused as inputs to an 18+ job;
- a clip with one flagged sampled frame in 18+: deleted;
- an unmarked flagged result in each section: blurred and held, exactly as today.

**Without it.** Either the owner's own pictures are blurred against his decision, or an identity check is allowed
to overrule an age check on explicit pictures, which it cannot answer.

---

## 4. Machines

### 4.1 The Mac Studio as a render and training host

**Until this section passes review and is built, the likeness stays on the machine that captured it.** Version 1 of
the build captures, trains and renders on the capturing machine only.

**Roles.**
- The **capturing machine** (the MacBook) holds the passkey, the Touch ID key, the enrolment set, the consent
  record, the registry and the private gallery. It makes every decision.
- The **Studio** (M3 Ultra, 256 GB) is a worker. It decides nothing and keeps nothing.

**The link.** Likeness data moves only over the kit's SSH link (`server-kit/mac/candy_link.py`): key-only SSH, its
own configuration under `~/.candy-server-kit/`, the key held by the owner's password manager, and tunnels to
services that listen on the Studio's loopback only. The link gets a Studio entry beside the server's. Nothing else
carries likeness data: no shared folder, no cloud drive, no AirDrop.

**Pairing.** Once, with both machines in front of the owner: the capturing machine makes a pairing secret and shows
a code; the owner types it on the Studio. The Studio keeps the pairing secret in its login Keychain. It is not a
decryption key. It only proves that a job came from this capturing machine.

**What moves, per job.**
1. On the capturing machine, after the passkey check (and inside the live-match window for an 18+ job), the app
   decrypts the LoRA in memory and encrypts it again under a fresh random **job key**.
2. It sends the ciphertext over the link, and the job key over the same SSH channel into the worker's memory. The
   job key is never written to the Studio's disk.
3. It sends a **job token**: `owner_id`, job id, kind, area, the LoRA's SHA-256, a start-by time and an end time,
   signed with the pairing secret. A token is used once.

**No long-lived key on the Studio.** The Studio may have no Touch ID, so it never holds the Keychain secret or
anything derived from it that outlives a job. A job key dies with its job. A token expires: the start-by time is
never later than the end of the live-match window, and the end time is the job's cap (30 minutes for stills, 2 hours
for a clip, 12 hours for training).

**How the live match gates a Studio job.** The capturing machine issues a token for an 18+ job only inside the
window. The Studio starts a job only before the token's start-by time. The capturing machine holds the SSH channel
open for the life of the job. If the channel drops, the worker stops the job and wipes its folder.

**Where the decrypted copy lives.** In a per-job folder in the Studio account's home, mode 0700, with a random file
name, registered with the engine for that job only. The worker deletes the folder when the job ends, when its token
expires, and at every worker start. The worker refuses to start when the Studio's disk encryption (FileVault) is
off. The engine listens on loopback, with previews off, and its history and temporary files for the job are cleared
with the folder.

**Where the results and the gallery live.** The worker encrypts each result under the job key as soon as it is
written, deletes the plain file, and sends the ciphertext back. The capturing machine runs the age check and the
face count, then stores the result in the private gallery or discards it. The Studio has no gallery and keeps no
result.

**Training on the Studio** follows the same steps, with the captures in place of the LoRA. It is enabled only after
the Studio's own MPS smoke test passes (section 4.3). The trained LoRA comes back encrypted; the Studio's copy, its
caches and its job folder are wiped.

**Who administers the Studio.** The owner. He is the only enrolled person (D-C-46), so the administrator and the
person in the pictures are the same. The worker refuses to start when the Studio's administrator group has a member
other than the paired account.

**Stated residual.** An administrator of the Studio, or anyone who can log in as the paired account, can read the
decrypted LoRA and the plain results while a job runs, and can read the job key from memory. Nothing in software
removes that. It is acceptable here only because the administrator is the owner himself. A second person's likeness
would not be acceptable on a machine someone else administers; this app has no second person.

**Unknown until the link exists.** The Studio's macOS version and free disk. It keeps its own 50 GB floor.

**Code points.**
- `server-kit/mac/candy_link.py`, `server-kit/config/kit.json`: a Studio host entry.
- `app/machine_profiles.json`: a new `m3_ultra` profile for ordinary jobs. It does not make the Studio a likeness
  host; only the pairing does (section 3.10, the engine handle).
- `app/owner_studio.py` *(new)*: pairing, job key, token, the channel watch, the remote wipe.
- The Studio worker *(new)*: token check, job folder, FileVault and administrator checks, wipe.

**Tests** (mock link, two temporary folders standing in for the two machines).
- A job with no token, a used token, an expired token, a token for another LoRA hash, and a token signed with
  another pairing secret are each refused by the worker.
- An 18+ token is not issued outside the window.
- The job key is never in a file on the Studio side (a scan of the worker's folder).
- A dropped channel stops the job and empties the folder.
- A worker start finds a leftover folder and removes it.
- FileVault "off" and a second administrator each stop the worker.
- A result is never left plain on the Studio side, and the gallery on the capturing machine receives it only after
  the age check and the face count.

**Without it.** A copy of the likeness sits unprotected on a second machine, usable by anyone who reaches it.

### 4.2 The game avatar stays clothed

**Control.**
- The avatar is built from a clothed, solo, plain-background hero sheet (`create`, `turnaround`), turned into a mesh
  (`model3d`), then prepared in Blender on the owner's machine.
- The asset carries `owner_likeness: true`, `owner_id`, `player_only: true`, `sfw_only: true`,
  `garment_lock: "clothed"`, the stated age and the manifest signature.
- The unclothed base layer is never textured with the likeness, and the game never hides every garment on this asset.
- The game refuses the asset in any 18+ scene or mode, in any step that changes clothing, and in any non-player slot.
- The lock follows where the pictures came from, not how close the face looks. A stylised avatar is still locked.
- The avatar asset is the only marked thing a game export carries (section 3.10). The export writes it into the
  game folder on the owner's machines, never into a pack, a zip or an upload. The game runs on the owner's machines.

**Code points.** `app/pipelines.py:1092` `job_model3d`, `:1159` `job_turnaround`; `app/pipelines_v3.py:593`
`job_export_godot`, `:435` `export_age`; `game/tools/import_easy_studio.py:109` `validate_pack`, `:73`
`validate_stated_age`; the asset contract `schemas/character_asset.json` *(new; planned with the Blender exporter)*.

**Tests.** The asset carries the lock; the importer refuses it in an 18+ scene, a clothing step and a non-player
slot; a pack with the avatar and any 18+ flag is refused; the kill switch removes the imported copy.

**Without it.** The game becomes a second place where the likeness can be undressed or handed to another character.

### 4.3 Training: the first go/no-go, and where it runs

**Control.**
- `trainer.write_config` writes `device: "cuda:0"` today, so the Mac cannot train as built. The build takes the
  device from the machine profile: `mps` on the Macs, `cuda:0` on the server.
- **The first go/no-go of the whole feature** is an MPS smoke test: a tiny LoRA trained on fictional test pictures,
  run by the owner, reporting time, memory and loss as numbers.
- If it fails, the feature waits. Likeness training never moves to a rented machine, and it does not move to the
  server under this design.
- **Training location, version 1: the capturing machine.** The Studio trains only after section 4.1 is built and its
  own smoke test passes.
- The likeness trainer takes only `owner_capture` items from verified sessions of the requesting owner, at least
  `trainer.MIN_PICTURES` and at most `MAX_PICTURES`, in the everyday section, on a fresh passkey check.
- Right before the run it verifies each capture's signature, hash and live-check record again, and runs the age
  check on every picture again *(after R0)*.
- The LoRA is written encrypted to `outputs/owner/loras/`, not into the shared LoRA folder.

**Code points.** `app/trainer.py:99` `write_config` (the device, line 111), `:39` `MIN_PICTURES` and `MAX_PICTURES`;
`app/lora_workshop.py:682` `job_me_train`, `:505` `_train_common`, `:394` `me_gate`, `:466` `_finish_lora`;
`app/machine_profiles.json`.

**Tests.** The config says `mps` on a Mac profile and `cuda:0` on the server profile; likeness training is refused
until the smoke-test record exists; fewer than the minimum of verified captures is refused; a tampered capture
record or a changed hash is refused; a flag at the re-check stops the run *(after R0, already tested)*.

**Without it.** The feature has no trainer on the machines it is allowed to run on, and the pressure is to move
real-person training somewhere it must never go.

### 4.4 The disk rule

The owner's MacBook cannot hold every model group at once and keep 50 GB free.

**Control.**
- **Set A**, resident: the fast still group, the Chroma group, the safety group, the SD 1.5 group, and the small
  describer model. About 57 GB plus 3 to 6 GB for the describer.
- **Set B**, swapped in when needed: the 5B video group and the 3D shape group. About 25 GB.
- **The rule.** Before any group is brought in, the app reads the free space at that moment
  (`shutil.disk_usage` on the data volume), adds what the swap frees, subtracts what it brings in, and refuses when
  the result is under 50 GB. No number is remembered from an earlier reading.
- The trainer's base model, its caches, its outputs and the private gallery are counted in the same sum.
- A reading taken while this was written: 131 GiB free. Set A would leave about 68 to 71; A and B together about 43
  to 46, under the floor. So bringing set B in means moving part of set A off first, and the app says which part.
- What moves off is model files only. A likeness file is never moved to make room.
- The Studio and the server each keep their own floor.

**Code points.** `install/download_models.py:17` `MODELS` (the groups and their sizes), `:191` `OPTIONAL_GROUPS`,
`:192` `DEFAULT_GROUPS`; `app/model_sets.py` *(new)*: the sets and the swap check.

**Tests** (a fake disk reading). A swap that would end under the floor is refused; the same swap passes after part
of set A is marked as moved off; the describer's size is in set A's sum; the sum includes the trainer's folders and
the gallery; a likeness path is never in the list of things to move.

**Without it.** The disk fills, as it did on Nov 3, in the middle of a job.

---

## 5. Four more rules

### 5.1 Tools that redraw real footage

Three tools planned from the other stack take a real video and redraw it: refine, follow-this-video, and together.

**Control.** Before anything else, such a tool samples the footage (every twelfth frame, at least eight), counts
the faces, and matches each one against the owner's enrolment set, inside the gated path of section 3.2. Footage
with any face that does not match is refused. Footage with no face passes as scenery. The result of a pass is a
likeness job, with every control of section 3.

**Code points.** None exist at this head; the tools arrive with the catalog work. The gate is
`owner_policy.footage_faces_ok` *(new)*, and each tool calls it first.

**Tests** (a stub face finder and stub embeddings). Footage with one matching face passes; with one face that does
not match, refused; with a matching face and a second face, refused; with no face, treated as scenery; a tool that
skips the gate fails a test that lists every footage tool.

**Without it.** A video of someone else becomes material for redrawn pictures of them.

### 5.2 No blood, violence, gore or hurtful depictions

**Control.** A fixed text rail, beside the minors and real-person rails, in every section. It runs on prompts, notes,
names, file names, LoRA text and the text inside raw workflows, through the same variant handling (spacing,
look-alike letters) as the minors rail. The same words join the avoid list of every picture. No setting turns it
off. The code is its own small pull request, a tightening that refuses more and loosens nothing; the SAFETY.md
wording of section 2.3 lands with the rest of section 2.

**Code points.** `app/safety.py:143` `check_prompt`, `:209` `check_all`, `:217` `check_workflow`, `:646`
`check_lora`, `:106` `_variants`, `:581` `safe_negative`; `app/pipelines.py:70` `_txt`. New in the rail's own pull
request: `safety.check_violence`, `safety.VIOLENCE_NEGATIVE`.

**Tests** (`tests/violence_rail_tests.py`, in that pull request). Each word family is refused in both sections, in
a prompt, a name, a workflow and LoRA text; the spaced and look-alike forms are refused; ordinary words that only
contain one of the patterns still pass (a fixed list of safe examples); none of the app's own catalog prompts is
refused; every prompt the existing suites accept is still accepted.

**Without it.** The owner's stated limit exists only on paper.

---

### 5.3 Nothing merges, and nothing else is touched, until the owner says so

**Control.**
- This document, and every build pull request after it, merges only when the owner's merge instruction names it.
- The work writes only to branches and worktrees it created. It never pushes to the development branch, to `main`,
  or to a branch created by other work, and it never writes in another checkout.
- Until that instruction, the SAFETY.md wording of section 2 stays a proposal inside this document.

**Code points.** None in the app. The pull requests' own history is the record: each is opened against the
development branch and left unmerged.

**Tests.** Before each push: the branch being pushed is one this work created; the commit touches only the files its
pull request names; no commit, title or description carries an author other than the owner.

**Without it.** A rule change reaches the main line before the owner has agreed to it, or two lines of work collide.

### 5.4 The policy gate for the leeway zone

This section is decision D-C-50. The rails have three layers.

1. **The fixed floor.** In code, with tests, the same in every section, and named by category: minors and anything
   that makes an adult read as a child; real people and anyone's likeness but the owner's; identity-copy tools and
   real-person LoRAs; blood, violence, gore and hurtful depictions; non-consensual, abusive or degrading acts
   against people; cruelty to animals. The floor grows by its own small pull requests, one category at a time.
2. **Wide leeway.** Outside the floor the app refuses nothing by default.
3. **The gray zone.** A local model on the owner's machine reads a plain policy file that the owner writes, decides,
   and logs its reason. This section designs that gate.

**Control.**
- **Order.** The fixed rails run first, in code. Only a job that passed every one of them reaches the gate.
- **What the gate can do.** Allow the job or refuse it. That is all. It widens or narrows the leeway zone only.
- **What the gate cannot do.** It cannot allow anything a fixed rail refused: a refusal by a fixed rail is never
  sent to the gate. It cannot change the section, lift a lock, open the consent or the window, change the output
  check of section 3.13, or pick an engine. No line in the policy file is read by a fixed rail.
- **The policy file** is plain text at `outputs/owner/policy.txt`, written and edited only by the owner in the app.
  With no file, the gate is off and only the fixed rails apply.
- **The model** is a small local model on the owner's machine, reached on loopback only. A hosted model is never
  the gate.
- **The answer** is a fixed shape: `allow` or `refuse`, and one sentence of reason. Anything else counts as no
  answer.
- **No answer.** When a policy file exists and the gate cannot answer (no model, a timeout, a malformed answer),
  the job is refused with a plain message. The gate never fails open.
- **The log** is local, under `outputs/owner/`: the time, the job id, the decision and the reason. It is never put
  in a bundle, a report or the repository.
- **Who sees the policy.** Only the owner. Nobody building the app writes, reads or tests the policy's content. The
  mechanism is built and tested with a made-up fixture policy about harmless words and a stub model.

**Code points.**
- `app/policy_gate.py` *(new)*: read the file, ask the model, parse the answer, log.
- `app/server.py:408` `create_job`: the gate is called after the last fixed check and before the job is queued.
- `app/safety.py:143` `check_prompt`, `:217` `check_workflow`, `:622` `check_area`, `:646` `check_lora`; `app/server.py:222`
  `_gate_stated_ages`: the fixed rails that run first and never read the policy file.

**Tests** (a stub model and a fixture policy; no real model, no real policy).
- With no policy file the gate is off and a job that passes the fixed rails runs.
- A stub "refuse" refuses the job with the stub's reason; a stub "allow" lets it run.
- A job a fixed rail refuses is refused with the gate set to "allow", and the gate is never called for it (one case
  per fixed rail: minors, a real person, an identity-copy node, a violence word).
- The 18+ flag of section 3.13 stays final with a policy file that says otherwise.
- No model, a timeout and a malformed answer each refuse the job.
- A hosted address for the gate model is refused.
- The log holds the decision and reason, and no test fixture, bundle or repository file holds a policy.

**Without it.** Either the gray zone is decided by fixed word lists nobody can tune, or by a file that can also
switch the floor off.

## 6. Residual risks

- **A trained likeness file is portable.** Encryption raises the bar. On a machine the owner controls, copying is
  never impossible. While a render runs, a decrypted copy exists under a random name.
- **The engine can read the decrypted copy during a render.** ComfyUI is a separate program. Anything that can
  reach its loopback port while a job runs can ask it to load that file. The build keeps the port on loopback and
  the copy job-scoped; it does not remove this.
- **A virtual camera can feed the capture** until protection L3 is built (section 7). The random plan and the
  screen-light step still have to be passed live.
- **Live checks are not solved against real-time face swaps.** The random plan and the screen-light step defeat a
  printed photo, a still on a screen and a recording. A live swap can still pass.
- **Touch ID protects the key from other programs**, not from the owner, and not from an administrator account.
- **The Studio's administrator can read a decrypted copy during a job** (section 4.1).
- **The revoked list can be removed by someone with the owner's account**, who can delete both the Keychain item
  and the file. A LoRA copy kept from before the switch then loads as an unknown file. That same copy already works
  in any other program, which is the portable-file risk above.
- **Backups and disk remnants are beyond the kill switch.** A Time Machine or NAS copy of `outputs/owner/`, and
  blocks an SSD has not yet erased, survive it. The files there are encrypted, and the key is gone after the switch.
  Keeping `outputs/owner/` out of backups is the owner's setting to make.
- **The age check and the face finder are helpers.** They can miss a face they cannot find and miscount in a hard
  picture. The face count refuses what it sees; it does not prove what it did not see.
- **Mock tests cannot prove the live check, the match or the count on a real camera and a real model.** That takes
  the owner's own run, reported as numbers.
- **Every new input path is a place for the word and age rails to be bypassed.** This design adds four routes, one
  trainer input and one worker. Each refuses in the server and each has a test.
- **MPS training may not work.** Then the feature waits (section 4.3).
- **Losing the passkey** means the kill switch and a new enrolment. Until protection L2 is built (section 7), the
  switch itself needs that passkey.

## 7. Later protections

The owner's decision D-C-48: the app is built quickly, for him alone, and protections are added over time. The fixed
rails are built first and stay hard: 21 or older, the age check on every capture and result, no minors, nobody
else's likeness, no identity-copy tools, no real-person LoRAs, no violence, one enrolled person, and nothing of the
likeness leaving his machines. Section 3.0's one definition is part of that, and is built from the first slice.

The four protections below are designed here and built later. Each says what it is, what it costs, and what is open
until it exists.

| # | Protection | What it is | What it costs | Open until then |
|---|---|---|---|---|
| L1 | Passkey checks bound to their action; origin checks | The signed passkey challenge includes the action and its parameters, so one check cannot be reused for another action inside its five minutes. Owner routes refuse a request whose `Origin` is not this app | One challenge format, a check in each owner route, tests for a replayed check and a cross-origin request. About a day | A page open in the same browser could call the local API inside the five-minute window |
| L2 | Deleting without the passkey | The kill switch also runs from the machine itself with a typed confirmation, with no passkey and no Touch ID | A second entry to the same delete walk, and a test for the lost-passkey path. Under a day | A lost passkey or a Touch ID reset leaves the switch unusable and `owner.json` blocking a new enrolment |
| L3 | Virtual cameras | Capture goes through the signed helper, which accepts only the built-in camera. The screen-light step stays the defence against a remote live person | A native capture path in the helper in place of `getUserMedia`. Several days | The browser accepts any camera it lists, a virtual one included. Until L3 this is a stated residual (section 6) |
| L4 | Decrypted pictures at rest | `Cache-Control: no-store` on every response that streams a marked picture; a named per-job, owner-only engine output folder, wiped after the job and at startup; and the encrypted gallery of section 3.9 | Headers and a folder rule are small. The encrypted gallery is the large part: storage, thumbnails and streaming. About a week | The first slice keeps likeness pictures as plain files in an owner-only folder |

Two small parts of L1 and L4 are **not** later. They are in the first build that saves or serves a likeness
picture, because they keep the likeness on the machine:
- **A Host check.** The app refuses any request whose `Host` header is not this app on loopback. Without it a web
  page can point its own name at this machine's loopback port and read the app's answers.
- **Backup exclusion.** Before the first picture is saved, the app itself marks `outputs/owner/` and the engine's
  job folders as excluded from backups (the Time Machine exclusion attribute), and does not leave that to a setting.

## 8. Defaults this design fixes

None of these is a question. Each is the choice made here, and changing one is a new decision with a new test.

| Topic | Default |
|---|---|
| Who can be enrolled | The owner only; one per app |
| Clips of the likeness | In the design; switched on after the stills path passes its build review |
| Captures after training | Kept, encrypted, until the kill switch |
| Live-match window | Ten minutes; in memory only |
| Passkey freshness | Five minutes |
| Withdrawing 18+ consent | Deletes the marked 18+ items; keeps everyday items and the avatar |
| A flagged likeness result | Deleted, not kept blurred |
| Training location | The capturing machine; the Studio only after section 4.1 |
| The server | Not a likeness host until its own design |
| The game avatar | Clothed, player-only |

## 9. Order

The twelve controls are the target shape. Under D-C-48 the first build is the simplest version of each that works:
a simple live check, a plain one-person lock, a delete-based kill switch. The encrypted gallery (3.9, L4) and the
Studio (4.1) follow later. Each step is one pull request, with tests on the main path and its follow-ups listed.

1. This design is reviewed.
2. The MPS smoke test is the first go/no-go (section 4.3).
3. The build lands as its own pull requests against the development branch, each with every test of its section, each
   reviewed at an exact head: the owner key and passkey; capture and live check; the lock, marks and walk; the
   private gallery; the trainer; consent and the window; the egress refusals; the kill switch; the avatar; then
   the Studio.
4. SAFETY.md and the README change in the pull request that first makes a refusal of section 2.4 reachable.
5. Section 5.3 holds throughout.
