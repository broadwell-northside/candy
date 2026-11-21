# Safety rules

These rules are part of the product. They apply in every tab, including the 18+ section.
They cannot be switched off from the app. A pull request that weakens them must say so
in the pull request description, in plain language, and the owner has to agree.
"Weakens" means a prompt, upload, workflow, LoRA, or training picture that these rules
refuse today would be accepted after the change.

The checks are a guard rail, not a guarantee. The owner is responsible for what they make
and what they share.

## Fictional adults only

- Every character is a fictional adult.
- The youngest age is **21**. The age slider starts at 21. The server raises any lower number.
- Anything about minors is refused. That includes words, numbers, look-alike letters,
  spaced-out letters, and the same words hidden inside a name, a note, a file name, or a
  raw workflow.
- Words such as "child" and "teen" are always added to the avoid list on the picture.
- The automatic age check is **on by default**. Every new picture, and frames from every
  new video, are checked. If a face may look under 21, the result is deleted: it is not
  saved, not shown and never blurred. The job says so plainly and offers a retry with a new
  seed. In the 18+ section that is final: no face match, setting or policy file overrules it.
  Switching the check off needs a typed confirmation. Training refuses to run while the
  check is off.
- The age check is a helper. It can miss a face it cannot find, and it can flag a
  young-looking adult.

## No real people

- No face-swap, no deepfake, and no real-person likeness.
- Requests for celebrities, or for a picture that looks like a named real person, are refused.
- Identity-copy tools are refused, even in Advanced mode. That includes ReActor, InstantID,
  PuLID, IP-Adapter FaceID, and the same idea under another node name that the denylist catches.
- LoRAs of real people or celebrities are refused. A LoRA whose file name is only an unknown
  person's name cannot be detected from the file. The confirmation tick exists for that gap.
  Do not load a model made to copy a real person.

## Training

- Character training uses only pictures made in Easy Studio, or the owner's own drawn or
  3D-rendered fictional art, uploaded with the "My fictional character" tick.
- Training never uses photos of real people, with one exception: the one person enrolled at this computer's camera
  (the owner). A likeness is trained only on that person's enrolment pictures and on photos the app has matched to
  the enrolled face (exactly one face, the enrolled face, and a clear age check). A photo of anyone else is dropped
  and is never a training picture. Nothing with that likeness leaves this computer.
- Clothing, object, background, and pose uploads cannot be used as training pictures.
- Every training picture is age-checked again right before training. One flag stops the run.

## The 18+ section

- Explicit adult content of fictional adults belongs in the separate 18+ section.
- Body-part LoRAs (chest, breasts, buttocks, genitals, skin, body hair), for both adult sexes, load only from a job inside this section. The server checks that. The age check still runs on every output. These categories are not a way around the 21+ rule.
- A still saved from a video is age-checked again. A clip the check already flagged cannot be turned into a still.
- Token packs and paywalls from other products do not unlock this section. They are not part of Easy Studio.
- Candy.ai is a picture-quality reference only. Chat, tokens, shop, community, memory, and notifications from that evidence are out of scope.
- The section is gated. The first time on a device, the owner confirms they are an adult
  and that the rules still apply. An optional PIN can be set. Lock closes the section.
- The 18+ gallery, files, jobs, thumbnails, and LoRAs stay in that section. The server
  hides them from the normal area, including direct file links.
- The same adult-only and no-real-people rules apply inside the section.
- Extra blocks apply inside the section for themes that make an adult look like a child,
  including school uniforms, classrooms, and step-family roleplay.

## Hosted services (API keys)

- A hosted video or text service is optional. Its key lives in the Mac's Keychain only, and the app never shows it again.
- The server refuses before any request is sent: anything from the 18+ area; anything that carries the owner-likeness mark,
  by mark, by ancestry or by a likeness LoRA (any LoRA at all is refused); any input picture whose age check is not ok;
  and any picture or video part at all unless the hosted-media switch in Setup is on (it is off by default).
- Addresses are fixed in the code. A key can only be sent to the provider's own host, never to an address typed in a field.
- A clip that comes back is age-checked like any other, is deleted if the check does not clear it, is marked `remote: true`,
  and is never trained on (nor is anything made from one of its frames).
## The hard floor

These categories are refused in every section, including the 18+ section, by words in
the text of a prompt, a note, a name, a raw workflow, or a LoRA's name, triggers and
description. They are named here by category only, and the tests use plain category words.

- Blood, violence, gore and hurtful depictions.
- Non-consensual, abusive or degrading acts against people.
- Cruelty to animals.
- Other grave harm to people, such as kidnapping, trafficking, slavery, terror, genocide
  and hate crimes.

Together with the fictional-adults rule and the no-real-people rule above, this is the
floor: it lives in code (`app/safety.py`), the same in every section, and no setting and
no policy file switches it off. The refusals that already exist in code stay exactly as they are; this section removes none.
Beyond the floor and those refusals the app adds no refusal of its own.
Everyday words that only share a stem with a floor word stay allowed.

## The owner's own policy (the gray zone)

Beyond the floor and the refusals already in code, the app adds none by default. An owner who wants more can keep a
plain text file ("what I don't want") in his own data folder. A gate on his own machine
reads it and the job's text, decides, and logs the reason (`docs/POLICY_GATE.md`).

- The file can only narrow or widen that leeway. It is read as text, never as a command,
  so it cannot switch off a floor rule, the age rules or the output age check. The fixed
  rails run first, in code, and a flagged result is deleted whatever the file says.
- No file means no gate. A file that cannot be read, or a gate that is missing, fails,
  times out or would have to leave the computer, means the job is refused.
- The gate runs only on the owner's machine. Nothing in 18+ text is sent anywhere.

## What is allowed

Lingerie, bikinis, swimwear, and yoga clothes are allowed. They are normal outfit choices.
They are not blocked by the safety rules.

## Where the rules live in code

- `app/safety.py` — word checks, age floor, workflow node denylist, 18+ area checks
- `app/age_guard.py` — automatic age check
- `app/policy_gate.py` — the owner's optional policy gate (after the fixed rails, fails closed)
- `app/server.py` and `app/routes_v3.py` — uploads, the 18+ gate, jobs
- `app/providers/guard.py` and `app/provider_jobs.py` — what may be sent to a hosted service
- `app/loras.py` — LoRA blocking, including Civitai "person of interest"
- `app/trainer.py` — which pictures training is allowed to use
- `writing/game_writer_system_prompt.txt` — the writing rules given to the local story model

`tests/run_tests.py` checks these rules against a fake ComfyUI. A change to the rules
needs a test that shows the new behaviour, and the pull request must say whether any
previous refusal is now allowed.
