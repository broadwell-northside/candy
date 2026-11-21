# Stillwater LoRA workshop

PRIVATE BUILD — NOT FOR DISTRIBUTION

This is the first LoRA workshop for Stillwater. It lives in the private creator studio. The island game is separate. This is not a girlfriend, boyfriend, or companion product.

You use it to bring in a small add-on file, called a LoRA, read what the author actually wrote, and try it on the mock engine. A LoRA can change a style, a concept, or the face of a fictional adult. It does not make a real photograph.

## What you can do in this version

1. Add a LoRA from your own computer, from a Civitai link, or from the metadata catalogue.
2. Read a usage card and put the listed trigger words, or one sample prompt, into the prompt you are writing.
3. See a conflict when a stack does not fit, and read the stack coach.
4. Run a prompt benchmark on the mock engine and save the cell you like as your tested preset.
5. Start a guided training run with ai-toolkit, for a fictional character or a concept, using stills this app made.
6. Keep a Me portrait for Andrew, the player. The path is photos, curated stills, a Me LoRA, then the player avatar.

Two extras are built here: the one-tap sample prompt, and the stack coach. The other ideas at the end of this note are specified and not built.

The practice screens use the mock engine. They do not use a GPU. They do not call RunPod. They do not spend money. In the test build they do not call the network. Mock pictures are not photographs.

## Who this is for

Adult NPCs are fictional adults. Each one needs a stated age of 21 or older. A missing age, an invalid age, or an age under 21 is rejected. The app does not guess an age and it does not raise a younger age to 21.

The only real person in this private build is Andrew, and only as the player. Me is a consented self portrait. Me is not an NPC. Me is not a sexual partner. Adult sexual content stays with fictional adults who are 21 or older.

Do not remove clothing from a photo of a real person. Do not make a face-swap. Do not make a likeness LoRA of anyone except this Me path. Do not import a Civitai model marked as a real person, a minor, or taken down.

## Adding a LoRA

You can drop a local `.safetensors` file, paste a Civitai link, or pick a row in the catalogue. The catalogue in tests is metadata only. The app reads these fields when a fixture or a Civitai answer has them:

- `baseModel`
- `trainedWords`
- `files[].hashes.SHA256`
- scans
- the real-person (poi) and minor gates
- mode `Archived` or `TakenDown`

The file is not downloaded until you confirm. After a download, the app checks the SHA256. If the hash does not match, the file is refused and not kept. If no hash was published, the card says the hash is UNKNOWN. That is not a claim that the file was verified.

These are refused:

- a real person, including a Civitai person-of-interest flag
- a face-swap or a likeness of someone other than the Me path
- a minor flag, an under-21 trigger, or a scan that flags a minor
- mode Archived
- mode TakenDown

The same gates already in `app/loras.py` still apply. A future Civitai token is an `op://` reference. This page does not ask for a token and it does not print one.

## The usage card

The card shows the author notes and the trained words.

Three labels are used, and they are not interchangeable:

- **Author recipe.** Shown only when authorship is verified.
- **App suggestion.** The app tells you to put listed trigger words at the start of the prompt. It does not suggest a strength.
- **My tested preset.** Stored only when you save a benchmark cell.

If `trainedWords` is empty, the card says that no trigger words were listed. That is not proof the LoRA has no trigger.

If model strength or clip strength was not given, the card says UNKNOWN. The app does not invent a recommended strength. Model strength and clip strength stay separate. A tested preset can set the model strength. Clip strength stays UNKNOWN until a real clip value exists.

Putting trigger words into the prompt does not load a different weight file. The one-tap sample prompt does not either. It copies that sample into the active prompt and keeps the sample's source id on the card.

Call a sample an **Author example** only when authorship is verified. Otherwise call it **Resource example (authorship unverified)**.

## Conflicts

The strip looks at the stack on the active engine. It warns, and it blocks where the existing rules already block.

| What you see | What the app does |
|---|---|
| Wrong base model for the active engine | Hard block. The library already refuses this. |
| A Wan 2.1 LoRA in Wan 2.2 High Noise | Soft warning. |
| Two character or face LoRAs | Soft warning. |
| Known model strengths adding up to more than 1.5, or one known model strength over 1 | Soft warning. This is not a recommended strength. |
| Two style LoRAs | Soft warning. Style can fight style. |
| A blocked file, a real person, a face-swap, or Me used as an NPC | Hard block. |

A missing strength is UNKNOWN. It is not treated as zero, so it is not added into the total. The stack coach tells you what to take off the stack. It does not load a different weight file by itself.

## The prompt benchmark

The grid uses one seed. It has two rows, with the trigger words and without them, and four model strengths: 0.4, 0.6, 0.8, and 1.0. Those numbers are the test, not a recommendation. Clip strength is not copied from model strength.

Saving a cell stores My tested preset on that same weight file. The tests run this on the mock engine. No GPU. No weight download. Each cell is labeled: Mock picture. Not a photograph.

You type the stated age. A missing or under-21 age does not run. The benchmark also stays off while the appearance checker is off.

## Guided training

ai-toolkit is the trainer in this version. Other trainers are not here.

You pick approved stills this app made, write a caption and a trigger, and train either a character LoRA or a concept LoRA. The stills have to belong to a fictional adult with a stated age of 21 or older. Uploads of real people, Me photos, and held pictures are not used for a character or concept LoRA.

The mock trainer does not download weights and does not spend money. A full merge, or a publish to Civitai, is not in this version.

If a recipe says training can resume, the screen says this: an inference LoRA is not a resumable training checkpoint. Resume only from a durable checkpoint you have acknowledged. This version has no resume button. The file added to the library is the inference LoRA. Numbered checkpoint files are left in the training folder and are not loaded as that LoRA.

This version does not check that the face matches before you accept a character LoRA or a Me LoRA. Accepting one does not mean the face was verified.

This version does not estimate how long a real training run takes.

## Me

Me is the player, Andrew. Me is not an NPC.

The upload is labeled for Andrew's own photos only. You confirm that the photos are yours and that Me is not an NPC. You type a stated age. A missing, invalid, or under-21 age is rejected. The appearance check still has to clear the picture. The check does not invent the age.

The path is:

1. Photos
2. Curated stills
3. Me LoRA
4. Player avatar

Curating keeps a photo you already checked. It does not redraw it and it does not remove clothing. Sexual content is not offered for Me. There is no nude control on this page, and the Me LoRA cannot be used as someone else's character LoRA.

## Built in this version

- **One-tap sample prompt.** One press copies a sample into the active prompt, keeps the source id, and does not change the weight file.
- **Stack coach.** Next to the conflict strip, it says what to take off the stack. The button removes a LoRA from the stack only.

## Specified, not built

These are not in this version. The rules below are what a later version has to follow.

**Drag to the next step.** You can drag a still onto the next workshop step. The drop does not skip the age gate. A missing or under-21 age still does not start a job.

**Outfit try-on.** For fictional adults with a stated age of 21 or older. It is not offered for Me. It does not remove clothing from an uploaded photo of a real person.

**Beach-day preset.** A saved place and light for the lagoon. The Blue Lagoon title is not used. The people in it are fictional adults.

**Face-consistency check.** Before you accept a character LoRA or a Me LoRA, compare the training stills with a new still. A miss, or an unsure result, holds the LoRA. Until that check exists, accepting a LoRA does not mean the face matched.

**Short-film shot board.** An ordered list of shots made from a still. The film limits stay visible, including that two people touching is not solved and that Wan has no sound.

**Phase time estimates.** Any number has to be labeled as an estimate, and only after it has been measured. This version shows none.

**Before/after slider.** The same seed, with the LoRA and without it. Mock frames are labeled as not photographs.

**Defect hold before export.** A failed check holds the file out of export. This version does not export a LoRA.

**Surprise me.** A press may store a whole number from 21 through 40. That is not a silent default. If you do not press it, a missing age is still rejected. It is not on the Me page, because Me is Andrew and the age is typed.

## Limits

- Private build. Not for distribution.
- Not a girlfriend, boyfriend, or companion product.
- Me is the player only.
- An empty trigger list is not proof that there is no trigger.
- Strength is UNKNOWN when it was not given.
- Mock images are not photographs.
