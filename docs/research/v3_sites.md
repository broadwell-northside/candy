# Easy Studio 3 — site research (3 Nov 2026)

What we looked at for v3, and what we took from it. **Only sites we actually opened are listed.** Each one has a row
in `competitors.csv` with its load result. 62 v3 rows: 43 loaded (some only partly), and 19 failed (bot check, 404,
or an empty JavaScript page). No accounts were made, and nothing was posted.

## Candy.ai (the reference Andrew named)
Pages opened: home, the "create your AI girl" builder (step 1), the AI video builder grid, the sign-up wall, and help.
`/create-character`, `/shorts` and `/my-ai` returned *Page not found*. Collection and Private Content go to a sign-in
page, which we did not get past (no account was made). Screenshots: `docs/screenshots/research/candy_*.jpg`.

| What Candy does | What Easy Studio 3 does with it |
|---|---|
| Step 1 is two big picture cards, **Realistic** vs **Anime**, one choice per screen | Create already starts with style. Kept big picture cards and one decision per step |
| "Build your video": **pick a girl first**, then build it scene by scene; a sticky bottom bar ("Pick a character → Create video") | Video studio: pick model → picture/character → motion. Extend adds scenes one after another |
| Long videos (1–2 min) made of scenes | Extend (up to 6 parts, optional loop) in Video and Video studio |
| Shorts / Private Content / Collection as separate areas | The 🔞 18+ section is a separate area with its own gallery, which never mixes into the normal one |
| One sign-up wall that also confirms "18+" | A one-time 18+ confirm on this device (two ticks), with an optional PIN. No account, everything stays local |
| An "18-21" filter, featured characters aged **19**, and "Live Action" clones of **real adult performers** | **Not copied.** Youngest age is 21, and teen words are refused. No real people, not even licensed ones: Easy Studio can't check consent |
| Category tabs (Bae, MILF, Fit, Busty, Curvy…) | 18+ photoshoot packs, poses and motions are their own presets, for fictional 21+ characters only |

## Lessons from the other sites
- **One saved character drives every tool** (Lovescape, OpenArt Characters, Nectar "Fantasies"). Easy Studio already
  had saved characters; v3 adds *Train my character*, so the look holds even in new outfits and places.
- **Pick the model first, then use the same form for every model** (Krea Video, Wan2GP, Pollo). This became the Video
  studio: model cards (ready / not installed), then one form that changes with the mode (text→video, picture→video,
  A→B, extend).
- **Extend instead of one short clip** (Seduced, Promptchan "Extend"). There is an Extend mode for every model.
- **LoRA cards with thumbnail, base model and trigger words; trigger words added automatically** (ComfyUI-Lora-Manager,
  Civitai Helper). This became the LoRA library: drag-and-drop install, paste a Civitai link, and the Advanced drawer
  shows LoRA names and adds trigger words for you.
- **Civitai's content levels and nsfw/poi flags** (Civitai docs and REST wiki). Adult Civitai LoRAs only go into the
  18+ section, LoRAs flagged as a "person of interest" are refused, and gated files need your own key, which is used
  once and never saved.
- **Training wizards are 3–4 steps with auto-captions** (Civitai trainer, FluxGym, OneTrainer presets). Train my
  character has the same three steps: make pictures → check → train. The difference is that the pictures are
  *generated from the saved character*, never uploaded photos.
- **Blur with a warning label instead of a silent delete** (Bluesky labelers, Tumblr content labels). The age check
  blurs a flagged result and badges it "Hidden: may look under 21". A flagged upload is refused.
- **Avoid:** face swap and video face swap (Mage, Pollo), "from a photo" character creation (OpenArt, Astria),
  "Teen 18+" categories (Lovescape, Kupid), and settings overload (kohya_ss).

## Trainer choice
- **ai-toolkit (MIT)** was picked. One tool covers every base model Easy Studio uses (Chroma, Z-Image Turbo,
  NoobAI-XL/SDXL) **and** Wan 2.2 video LoRAs, including the high/low-noise pair. It is driven by a config file, so
  Easy Studio can write the settings for you.
- Runners-up: musubi-tuner (video only), OneTrainer (GUI first) and diffusion-pipe (deepspeed, Linux only).

## Age-check model choice
- **YuNet** (face finder, via kornia) plus **SigLIP2 age classifier** (prithivMLmods/Age-Classification-SigLIP2).
  Both are Apache-2.0 and small (~0.4 GB), and run on the GPU or the CPU in ComfyUI's Python.
- MiVOLO was more accurate but has a non-commercial research licence and is heavier.
- nateraw/vit-age-classifier has no clear licence.
- **Limits** (also listed in the README):
  - it only judges faces it can find;
  - it can miss back views, masks and some anime styles;
  - it can wrongly flag young-looking adults;
  - age estimators are less accurate on stylised art.
- It is a second line of defence. The word rules and the 21+ age slider are the first.
