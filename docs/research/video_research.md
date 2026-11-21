# Video notes (Wan 2.2, native ComfyUI)

- **Image-to-video:** the WanImageToVideo node uses high-noise and low-noise 14B experts. KSamplerAdvanced is split at the halfway step.
  - Fast: the 4-step LightX2V LoRAs, cfg 1, shift 5.
  - Quality: 20 steps, cfg 3.5.
  - From template `video_wan2_2_14B_i2v.json`.
- **First+last frame (FLF2V):** the `WanFirstLastFrameToVideo(positive, negative, vae, width, height, length, start_image, end_image, clip_vision_*)` node, with the same model files.
  - Template `video_wan2_2_14B_flf2v.json` uses 640×640×81. Its 4-step LoRA branch uses shift 5; its 20-step branch uses shift 8 and cfg 4.
- **Frame rules:** frames must be 4n+1. 81 frames = 5 s at 16 fps.
- **What Easy Studio does with FLF2V:**
  1. **"Go from this picture to that picture":** for example, the same character standing, then sitting. Make both stills with the Edit tab.
  2. **Seamless loop:** start = end = the same picture, for idle animations or game backgrounds.
  3. **Smoother extend:** when extending a clip, you can give a target end picture, so the story goes somewhere instead of drifting.
- **Extend (from v1, improved):**
  - The app takes the last frame (ffmpeg, lossless PNG) and makes the next clip from it.
  - It drops the duplicate first frame when stitching.
  - The prompt can change per clip ("then she turns and walks away").
  - New: an optional end-picture per extension (uses FLF2V) and a "loop back to start" option for the final clip.
- **Drift:** colour and identity drift slowly over many extensions. The mitigations are:
  - Keep each clip 5 s.
  - Re-anchor with an end picture made from the character's hero portrait.
  - Prefer 3-4 extensions over 10.
- **Sprites from video:** the app samples N frames with ffmpeg, optionally removes the background with BiRefNet, and packs them into a sprite sheet PNG plus a JSON atlas.
