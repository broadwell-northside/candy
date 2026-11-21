# Easy Studio widget inventory

This is the pass-1 inventory of every screen a person can open in the browser.
The page is one window. Tabs are drawn by `app/static/app.js` and `app/static/v3.js`.
Chips, outfits, places, and motions come from `app/catalog.py`. Counts below are from that catalog.

A full Cartesian product of every chip on Create is not feasible. Body, hair, outfit, place, light, and framing alone are already tens of millions of combinations, and that ignores text fields. The browser suite covers every option of each control on its own, then an all-pairs set across the controls that change a job. The matrix is written to `docs/E2E_PAIRWISE.md` when `python tests/e2e_browser.py` runs.

## Screens (19)

| # | Screen | How you open it | What it is for |
|---|---|---|---|
| 1 | First launch / Create | Tab **Create**, also the first screen | Build a fictional adult and make pictures |
| 2 | My characters | Tab **My characters** | Saved cast, notes, sister, export |
| 3 | Wardrobe | Tab **Wardrobe** | Change clothes, try on a photo, or paint |
| 4 | Pose | Tab **Pose** | Re-pose a picture or draw a saved character |
| 5 | Scene & background | Tab **Scene & background** | New place, quick cut-out, or transparent PNG |
| 6 | Add objects | Tab **Add objects** | Put a prop in the picture |
| 7 | Photoshoot | Tab **Photoshoot** | One set of matching pictures |
| 8 | Video | Tab **Video** | Make a short silent film from a kept still |
| 9 | Video studio | Tab **Video studio** | Pick a video model or your own workflow |
| 10 | 3D model | Tab **3D model** | Picture to a `.glb` |
| 11 | Game assets | Tab **Game assets** | Sheets, upscale, cut-out, export |
| 12 | LoRA library | Tab **LoRA library** | Install and edit LoRA cards |
| 13 | Train my character | Tab **Train my character** | Make training pictures, then train |
| 14 | Gallery | Tab **Gallery** | Everything made, filters, reuse |
| 15 | Advanced | Tab **Advanced** | Raw workflow, safety still on |
| 16 | Setup | Tab **Setup** | What is installed, age check, PIN |
| 17 | Jobs and queue | Clock button in the top bar | See the queue and stop a job |
| 18 | 18+ section | **18+ section** in the top bar | Separate gallery, same age rules |
| 19 | Dialogs | Upload, gallery picker, picture details, workflow JSON | Short tasks on top of a screen |

Top bar on every screen: brand, **Fictional adults only**, 18+ section, Jobs, engine status.

## Create

| Widget | Kind | Options / value classes |
|---|---|---|
| Saved-character strip | buttons | New, plus each saved character |
| Style | 4 tiles | Realistic photo, Anime, 3D render, Painted |
| Gender | 2 segments | Woman, Man |
| Age | text + slider | Empty, not a number, under 21, 21, 70, over 70 typed, very long. Nothing is filled in until you type or drag. |
| Look tabs | 5 tabs | Body, Skin, Face, Hair, Fantasy & more. Back and Next. |
| Look chips | chips | 95 chips in 15 groups (see table). Click again to clear a single-choice group. |
| Surprise me | button | Fills a random adult look and states an age because you pressed it |
| Anything else | text + prompt helper | Empty, valid phrase, blocked words, group-without-age, very long (500) |
| Prompt helper | chips + Check wording | Who / Where / Mood phrases |
| Outfit categories | 8 chips | Casual, Dressy, Lingerie, Swim, Costumes, Cover-ups, Shoes, Accessories |
| Outfit items | 39 chips | Every item in the open category |
| Look preset | 4 chips | Realistic, Film, Glam, Draft |
| Lens | 5 chips | Phone, 35 mm, 50 mm, 85 mm, Shallow focus. Optional. |
| Framing | 7 chips | Portrait through From behind |
| Place | 12 chips | First 12 scenes |
| Light | 12 chips | Catalog lights plus the extra studio lights |
| Speed | 2 segments | Best, Fast draft. Hidden for anime (one engine). |
| How many | 3 segments | 1, 2, 4 |
| Shape | 3 segments | Portrait, Square, Wide |
| Name | text | Empty, valid, 60 characters, longer text is stopped at 60 |
| Create pictures | button | Off until age is stated. Estimate shown. |
| Advanced | drawer | Seed, steps, CFG, denoise, sampler, scheduler, 3 LoRA rows, show workflow, reset |

Look groups: body 6, height 3, bust 4 (woman only), hips 3, skin 8, skin details 5 (multi), face 5, eyes 8, eye shape 5, lips 3, makeup 4, hair style 15, hair colour 14, hair length 4, fantasy 8 (multi).

## My characters

New character. Each card: portrait, Edit look, Again, Outfit only, Shoot, Pictures, Sister, Export, Delete, notes, Save notes.

Empty state: no characters yet.

## Wardrobe

Working picture (gallery or upload). Mode: Pick an outfit, Try on a clothing picture, Paint an area.

Pick: outfit picker, 12 colours, 8 materials, details text, how many (1/2/4), Change outfit, Keep the body, Advanced.

Try on: upload clothing, from gallery, what is it, reference strength slider (shows the number), Try it on.

Paint: brush size, Paint / Erase, Clear, Invert, describe, strength slider, Paint it.

## Pose

Working picture. Mode: Re-pose this picture, New picture of a saved character. Pose strictness slider on the new-picture mode. 19 stick figures plus copied poses. Copy a pose from a picture (upload). Apply pose. Advanced.

## Scene & background

Mode: Smart, Quick cut and paste, Transparent. Smart: 18 places, 12 lights, details, optional background upload. Quick: background or colour. Transparent: one button.

## Add objects

14 object tiles, describe text, upload object, Where: choose a spot (6 placements) or paint the spot. Add it. Advanced.

## Photoshoot

Character strip. 5 shoots (Beach day, Boudoir, Fantasy hero, Night out, Game portraits). Start the shoot stays off until a character is picked. Estimate shown.

## Video

Make a short film. Choose a still this app kept. A rejected, held, or missing still cannot start. Length chips are 2 seconds and 5 seconds. One motion chip. The film model is Wan 2.2, and the page says Wan has no sound. The page says two people touching is still the weak spot and is not solved. Explicit films stay behind the 21+ switch, which is off until you open it. Make a short film stays off until a still is chosen. The node graph stays hidden.

## Video studio

Model cards (ready and not installed). Not-installed cards leave Make video off, with a reason. Shape for text-to-video. Motion chips. Describe box with the prompt helper. Length slider. Fast / Best. Start, end, and continue-a-video pickers depending on the model. Import a workflow file or paste JSON. Remove on your own cards.

## 3D model

Working picture. Quality: Game-ready, Standard, Max detail. Optional clay-shape backup when that model is installed. Make 3D model. Recent models. How to open the file.

## Game assets

Turnaround, expression chips (8, multi), upscale ×2, ×4, transparent PNG, video picker, sprite frames (8/12/16/24/32/48), columns (4/6/8/12), transparent background toggle, character pack, Godot export.

## LoRA library

Confirm tick, drop zone, file picker, Civitai URL, API key (not saved), Look it up, Add to my library. Each card: works-with menu, trigger words, strength slider, remove. Locked cards explain why they cannot be edited. Empty state.

## Train my character

Character strip. How many training pictures (12/16/20/24). Make training pictures. Tick boxes on pictures. What the LoRA is for. Train. Warnings when the trainer, age check, or LoRA folder is missing.

## Gallery

Type filter (All, Pictures, Videos, 3D, Exports). Character menu. Project menu. Favourites only. Upload. Each picture: favourite, open, next-step buttons, download. Flagged pictures have no download and no reuse. Empty state.

Picture details: time, model, seed, prompt, project name, use as working picture, save project, download, delete.

## Advanced

Workflow text box. Insert gallery picture. Load last workflow. Run workflow. Same safety rules, including no face-swap nodes.

## Setup

Engine status. Download command when something is missing. Tool list. Age-check toggle (turning it off asks you to confirm). 18+ PIN. Trainer status.

## Jobs

Count on the clock. Panel: plain job name, status, percent, message, Stop. Empty state explains where to start.

## 18+ gate

Two confirmations (both say 21+). Optional PIN. Open, Leave, Lock.

## Upload dialog

File, role text, confirm tick, and for **My fictional character** a typed age. Empty, invalid, under 21, and 21+ are sent to the server. The server decides. Nothing is guessed from the picture.

## Value classes used everywhere

| Class | What we try |
|---|---|
| Valid | A normal choice the screen is built for |
| Empty | Blank text, no file, no character, no picture |
| Boundary | Age 21 and 70, slider ends, 60-character name, 500-character extra, score 0 and 10, strength ends |
| Invalid | Age 18, the word eighteen, a minor in the words, a real-person likeness, a face-swap workflow, clothes taken off an upload |
| Very long | A huge age, a huge prompt, a long name |

## What a full Cartesian product would be

Create alone, if every independent choice were crossed, is roughly:

4 styles × 2 genders × 50 ages × 6 bodies × 3 heights × 4 busts × 3 hips × 8 skins × 5 faces × 8 eye colours × 5 eye shapes × 3 lips × 4 makeups × 15 hair styles × 14 hair colours × 4 lengths × 39 outfits × 4 looks × 7 framings × 12 places × 12 lights × 2 speeds × 3 counts × 3 shapes.

That is billions of jobs. The suite does not do that. It selects every option once, then runs the all-pairs rows in `docs/E2E_PAIRWISE.md`.
