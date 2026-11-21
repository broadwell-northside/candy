# Easy Studio 3: make, dress, animate and train your own fictional characters

PRIVATE BUILD — NOT FOR DISTRIBUTION

Easy Studio is a private web app that runs on your RTX PRO 6000 PC. You open it in the browser on
your MacBook. Everything works by clicking pictures and chips, the same way character-creator
sites do. You never see nodes. Behind the scenes it drives **ComfyUI** (the engine). Everything
stays on your own machines. Explicit adult content of fictional adults goes in the separate
🔞 **18+ section**, which has its own gallery. Easy Studio is for **personal use** (the game won't be sold).

> ## ⚠️ The rules (built in; they cannot be switched off)
> * **Adults only.** Every character is a fictional adult. The age slider starts at 21, and the
>   server raises any lower number. Words or numbers that describe minors or child-like
>   characters are refused everywhere you can type: prompts, names, notes, file names, and the
>   texts inside raw workflows. "child, teen, underage…" is always added to the avoid list.
> * **Fictional characters only, no real people.** There is no face-swap, no "make it look like
>   this person", and no identity-copy model (ReActor, InstantID, PuLID, IP-Adapter FaceID and
>   similar are refused, even in Advanced mode). Requests for celebrities, deepfakes or
>   someone's likeness are refused. Uploaded pictures are only used as an outfit, object,
>   background or stick-figure pose reference. The only exception is a picture of **your own
>   fictional character**, and you must tick a box confirming it.
> * **No real people without their consent, ever.** LoRAs of real people or celebrities, and LoRAs
>   of minors, are refused. Don't load models made to copy a real person.
> * **Training only uses fictional characters.** *Train my character* learns only from characters
>   made in Easy Studio, or from your own drawn / 3D-rendered fictional art (uploaded with the
>   "My fictional character" tick). **It never trains on photos of real people, including
>   yourself.** This is a deliberate choice: a LoRA of a real person would let anyone make nude
>   pictures of them, and the app can't check who is in a photo or whether they agreed.
> * **The 18+ section follows the same rules.** Characters there are fictional adults (21+). On
>   top of that, themes that make an adult look like a child are blocked (school uniform,
>   classroom, step-family…).
> * **Automatic age check (on by default).** Every new picture and video is checked. Anything that
>   may look under 21 is deleted (never shown, never blurred); the job says so and offers a retry with a new seed.
>
> These checks are a guard rail, not a guarantee. You are responsible for what you make and share.

---

## What's inside (one tab per job)

| Tab | What you do | Engine underneath |
|---|---|---|
| ✨ **Create** | Pick style (photo / anime / 3D render / painted), gender and age (21+). Then pick the look on five small pages (Body, Skin, Face, Hair, Fantasy), or press 🎲 *Surprise me*. Then choose outfit (lingerie, bikinis, swimwear and yoga clothes included), framing, place and light, and press **Create**. Press **👤 Save as character** on the one you like. | Chroma1-HD, Z-Image Turbo, NoobAI-XL |
| 👥 **My characters** | Your saved cast: *Edit look, Dress, Shoot, Pictures, Sister, Export*, plus notes. | – |
| 👗 **Wardrobe** | Change outfit with chips, **try on** a clothing photo, or **paint** an area. | Qwen-Image-Edit-2511, Chroma / NoobAI inpaint |
| 🧍 **Pose** | 14 stick figures (more in 18+), copy a pose from any picture, or re-draw in a pose. | Qwen edit, SDPose, Z-Image + ControlNet |
| 🏞️ **Scene & background** | Smart new place with matching light, quick cut-out, or transparent PNG. | Qwen edit, BiRefNet |
| 🪄 **Add objects** | Put a prop, pet or furniture in the scene. | Qwen edit / inpaint |
| 📸 **Photoshoot** | One click makes a consistent set (extra 18+ sets inside the 18+ section). | Qwen edit + pose figures |
| 🎬 **Video** | The quick way: animate a picture, A → B, **Extend** and **loop**. | Wan 2.2 14B |
| 🎞️ **Video studio** *(new)* | **Any video model**: pick a model card (ready / not installed), then text → video, picture → video, A → B, or extend. **Import your own ComfyUI video workflow** and Easy Studio finds its prompt, picture, length and seed boxes by itself. | Wan 2.2 14B + 5B, LTX-2.5 (with sound), HunyuanVideo 1.5, Kandinsky 5, your workflows |
| 🧊 **3D model** | Picture → textured **.glb** to spin in the page. | TRELLIS.2 |
| 🎮 **Game assets** | Turnaround / expression / sprite sheets, upscale, cut-out, character pack, and **Export to Godot 4** *(new)*. | Qwen, RealESRGAN, ffmpeg |
| 🧩 **LoRA library** *(new)* | Drag-and-drop LoRA files or paste a Civitai link. Cards show a thumbnail, what it works with (detected automatically), trigger words and strength. LoRAs of real people or minors are refused. | ComfyUI's `models/loras` folder |
| 🎓 **Train my character** *(new)* | Pick a saved character → **Make training pictures** (12–24 varied shots with captions) → untick bad ones → **Train**. The LoRA then appears in every Advanced drawer, with its trigger word added for you. | ai-toolkit (Chroma, Z-Image, NoobAI, Wan 2.2 video) |
| 🖼️ **Gallery** | Everything you made (the 18+ section has its own). | – |
| 🛠️ **Advanced** | Every tool's *Advanced* drawer: seed, steps, CFG, sampler, **up to 4 LoRAs** (by name, with trigger hints), "show the workflow". This tab also runs your own API workflow, with the same safety rules. | any built-in ComfyUI node |
| ⚙️ **Setup** | What's installed, what's missing, plus the age-check switch, 18+ PIN and trainer status. | – |
| 🔞 **18+ section** *(top bar)* | A separate area for explicit content of fictional adults (21+), with its own gallery, outfits, photoshoots, poses and motions. You confirm once on this device (optional PIN), and 🔒 Lock closes it. | same tools |

Under every result you get buttons for the next step: *Outfit, Pose, Scene, Object, Animate, 3D,
Sheets, Upscale, Cut out*. You never have to re-upload anything.

---

## How your machines fit together

| Machine | Job |
|---|---|
| **RTX PRO 6000 (96 GB) PC** | Runs ComfyUI + Easy Studio: all pictures, video and 3D. |
| **MacBook Pro M5 Max** | The screen you use (Safari/Chrome over your home Wi-Fi), plus story writing in LM Studio. |

---

## Step-by-step setup (RTX PRO 6000 PC)

**What you need:** Windows 11 or Ubuntu 24.04, the latest NVIDIA RTX PRO driver, about **150 GB
of free SSD space**, and ideally 64–128 GB of RAM.

1. **Unzip** `easy-studio.zip` somewhere simple, such as `C:\easy-studio` or `~/easy-studio`.
2. **Install (one time, 1–3 hours, mostly downloading about 139 GB):**
   * Windows: double-click **`install_windows.bat`** and say *Yes* if asked.
   * Linux: `bash install_linux.sh`.

   It installs Git, Python, ffmpeg, ComfyUI and PyTorch for your card, then all model files.
   If a download stops, run it again and it resumes. It finishes with a self-test (no GPU
   needed). To install without models, use `install_windows.bat -NoModels` or
   `bash install_linux.sh nomodels`.
3. **Start:** double-click **`start_windows.bat`** (allow *Private networks* at the firewall
   prompt), or run `./start_linux.sh`. The window shows the address for your MacBook and a
   **password**.
4. **Open it on the MacBook** at the address shown (for example `http://192.168.1.50:7860`).
   Type any user name and the password, and let the browser remember it. The PC itself never
   asks for it.
5. Open **⚙️ Setup** once: every tool should have a ✅. Any ✗ shows the exact command to fix it.

**About the password:** because the app is open to your home network, it makes up a password the
first time it starts and saves it in `outputs/password.txt`. To choose your own, set
`EASY_STUDIO_PASSWORD` (Windows: `setx EASY_STUDIO_PASSWORD yourpassword`, then reopen the
window). Setting it to `off` turns the password off, which isn't recommended.

### Model groups (pick and choose)

`install/download_models.py --comfy ComfyUI --what <groups>` downloads only what you name.
`--list` shows the files and `--check` tests every link without downloading. All 28 links were
checked working on 3 Nov 2026.

| Group | Size | Unlocks | Licence note |
|---|---|---|---|
| `image` | 27.9 GB | Realistic Create (Chroma1-HD) | Apache-2.0 |
| `anime` | 7.1 GB | Anime Create + anime paint | **FAIPL-1.0-SD**: no paid generation service; check before selling |
| `fast` | 23.8 GB | Fast drafts, *new picture in a pose* (Z-Image Turbo + ControlNet) | Apache-2.0 |
| `edit` | 31.3 GB | Wardrobe, Pose, Scene, Objects, Photoshoot, sheets (Qwen-Image-Edit-2511) | Apache-2.0 |
| `tools` | 2.4 GB | Background remover, upscaler, pose reader | MIT / BSD-3 / check SDPose |
| `video` | 38.0 GB | Video + Extend (Wan 2.2 14B) | Apache-2.0 |
| `3d` | 9.0 GB | 3D models (TRELLIS.2) | MIT, but the DINOv3 image encoder has Meta's own licence |
| `3d-shape` | 7.4 GB | Optional clay-shape backup (Hunyuan3D 2.1). **Not in the default install.** | Tencent licence **does not apply in the EU, UK or South Korea** |
| `safety` | < 1 GB | Automatic age check (YuNet face finder + SigLIP2 age classifier). **In the default install.** | Apache-2.0 |
| `video-t2v` | 38 GB | Video studio: Wan 2.2 14B text → video. Optional | Apache-2.0 |
| `video-wan5b` | 18 GB | Video studio: Wan 2.2 5B (small, 24 fps). Optional | Apache-2.0 |
| `video-ltx` | 40 GB | Video studio: LTX-2.5 with sound. Optional, **needs a free Hugging Face login** (gated) | LTX-2 Community Licence (free under $10M revenue) |
| `video-hunyuan` | 46 GB | Video studio: HunyuanVideo 1.5 720p. Optional | Tencent licence **does not apply in the EU, UK or South Korea** |
| `video-kandinsky` | 19 GB | Video studio: Kandinsky 5 Lite. Optional | MIT |

The default install is everything except `3d-shape` and the `video-…` extras. Add an extra later with,
for example, `--what video-ltx`. Sizes are measured from the download
servers; files shared between groups are only downloaded once.

### Character trainer (one time, optional)

`install_trainer.bat` (Windows) or `bash install_trainer.sh` (Linux) puts **ai-toolkit** (MIT) in
`trainer/ai-toolkit` with its own Python (about 10 GB). The base models it trains on download the
first time you train. A picture LoRA takes about 30–60 minutes on the RTX PRO 6000, and a Wan 2.2
video LoRA a few hours (estimates, not measured). ComfyUI frees the GPU while training runs.

### Game engine: Godot 4

Easy Studio's pick for your game is **Godot 4** (free, MIT licence, no account, runs on the PC and
the Mac). It imports `.glb` 3D models directly, and plays `.ogv` videos and sprite frames. In
🎮 Game assets, **Export to Godot 4** builds a ready project folder (a zip) with
`project.godot`, desktop **export presets** (Windows, Linux, macOS), portraits, sprite frames +
SpriteFrames `.tres`, `.glb` models and `.ogv` videos. Open it with Godot → Import. Why Godot: see
`docs/PRD.md` §A3.

## Writing setup (MacBook Pro M5 Max)

1. Install **LM Studio** from <https://lmstudio.ai>.
2. In LM Studio, go to the search tab and paste
   **`huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated-MTP-GGUF`**. Download the **Q8_0** file
   (37.8 GB). If that version doesn't load, use the MLX version
   `leonsarmiento/Huihui-Qwen3.6-35B-A3B-abliterated-6bit-XL-mlx` (about 28 GB) instead.
3. Load it, open the **System prompt** box and paste in the text from
   `writing/game_writer_system_prompt.txt`. That file keeps the adults-only and no-real-people
   rules.
4. For more "romance novel" style character roleplay, try the backup model:
   `llmfan46/MS3.2-PaintedFantasy-v4.1-24B-ultra-uncensored-heretic-v2-GGUF` (Q8_0, about 25 GB).

---

## Adding your own models / LoRAs

* **LoRAs:** open 🧩 **LoRA library**, tick "not a real person, not a child", and drop the
  `.safetensors` files in (or paste a Civitai link). Easy Studio works out what each LoRA is for
  (SDXL/Pony/Illustrious, Chroma/Flux, Z-Image, Qwen, Wan, LTX, Hunyuan, Kandinsky), reads its
  trigger words, and puts it in ComfyUI's `models/loras/easy_studio/`. Files you copy into
  `ComfyUI/models/loras/` yourself show up too.
* **Civitai:** public LoRAs download directly. Early-access or gated ones need your own Civitai API
  key, which is used for that one download and never saved. LoRAs that Civitai marks adult can only
  be added from inside the 18+ section. Easy Studio refuses Civitai's "person of interest" (real
  person) LoRAs.
* **Using them:** any *Advanced settings* drawer, in picture and video tools, stacks up to 4
  LoRAs. A LoRA made for a different base model is refused, with an explanation.
* **Your own video workflow:** in ComfyUI, save or export the workflow, then use 🎞️ **Video
  studio → Use your own ComfyUI video workflow**. It works with the normal or API format.
* **Your own picture workflow:** *Workflow → Export (API)*, then paste it into 🛠️ **Advanced**.
* **Other checkpoints:** swap the file name in the matching JSON in `app/workflows/`.

No custom nodes are needed. All built-in workflows use nodes that ship with ComfyUI. They were
checked against a real ComfyUI 0.43.0.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| Yellow bar "Not installed yet…" | Open ⚙️ Setup, run the command it shows, and restart Easy Studio. |
| "A model file this tool needs isn't installed yet" | Same as above. |
| 🔴 "Engine offline" | Wait 30 s. If it stays red, look at the ComfyUI window (Windows) or `outputs/comfyui.log` (Linux). |
| MacBook can't open the page | Both machines must be on the same Wi-Fi. Allow the firewall prompt. Find the PC's address with `ipconfig` / `hostname -I`. |
| Forgot the password | It's in `outputs/password.txt` on the PC. |
| "Out of memory" | Use 480p + Fast, *Game-ready* 3D, and close other GPU apps. |
| "Use the 18+ section" | Explicit words only work inside the 🔞 18+ section. |
| "⚠️ Hidden: may look under 21" | The age check thought a face may look young. Make the character look clearly older (age 25+, adult face, adult body) and try again. |
| "LoRA … is for … not for this model" | That LoRA was made for a different base model. Pick one whose card says it works with this tool. |
| "The trainer isn't installed yet" | Run `install_trainer.bat` / `bash install_trainer.sh`, then restart. |
| "Blocked: …" | It matched the adults-only / no-real-people rules. Reword it to describe a clearly adult, fictional character. A few harmless phrases also trip it (for example "son of a gun"). |

**Self-test** (no GPU needed): `.venv/bin/python tests/run_tests.py` on Linux, or
`.venv\Scripts\python tests\run_tests.py` on Windows. It starts a fake engine and runs every
tool (about 360 checks). `tests/ui_smoke.py` opens every tab in a headless browser
(`pip install playwright` first).

---

## Honest limits

* **Not yet tested on a real GPU.** Every workflow, including the new video models, was accepted by
  a real ComfyUI 0.43, and the whole app was tested end-to-end against a fake engine, a fake age
  checker and a fake trainer. Real picture and video quality, training results, speed and memory
  use still need checking on your PC. All times are estimates.
* **Training** needs the character's training pictures to look like her. Untick the ones that
  drift. A LoRA can't fix a bad portrait.
* **The age check is a helper, not a guarantee.** It only judges faces it can find, so it can miss
  back views, masks and some anime styles. It can also wrongly flag young-looking adults.
* **LoRAs of real people named only with a name** (e.g. "jane_doe_v2") can't be recognised from
  the file. That's why the tick box exists. Only add LoRAs of fictional characters.
* **Faces drift a little** across long videos. Keep extended videos to about 4–6 parts, or use a
  trained LoRA.
* **3D from one picture guesses the back**, and models are not rigged.
* **Sound:** only LTX-2.5 makes sound. Wan, Hunyuan and Kandinsky are silent.
* **The word filter isn't perfect.** It can block harmless phrases, and a determined person could
  get around it. It is backed by the 21+ floor, the always-on negative prompt, the age check, the
  upload roles and the refusal of face/identity nodes.
* **Licences:** this is for personal use (no selling), so non-commercial and community licences
  are fine. **Territory limits still apply:** the HunyuanVideo 1.5 and Hunyuan3D licences are not
  valid in the EU, UK or South Korea, so skip those optional groups if you live there. MiniMax-H3
  is not included (its licence excludes the USA). Details: `docs/research/models_and_licenses.md`.

Docs: `docs/PRD.md` (v3 product spec, engine pick, competitor study, roadmap) and `docs/research/`
(competitor CSV, v3 site lessons, feature docs, critic passes, adversarial review).

## Working on the code

The rest of this file is the guide for using the app. If you are changing the code, read
`CONTRIBUTING.md`, `SAFETY.md`, and `ROADMAP.md`. The safety rules stay as they are.
Checks on every pull request are described in `CONTRIBUTING.md`.
