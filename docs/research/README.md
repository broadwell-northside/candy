# Research notes (Nov 2026)

| File | What's in it |
|---|---|
| `competitors.csv` | 111 rows. Each is a site/app we tried to open, with its load status. 74 loaded with real content. |
| `comfyui_feature_guide.md` | How each Easy Studio feature works in ComfyUI: native nodes, settings, and the template each came from. |
| `models_and_licenses.md` | Every model file: link (checked), size, licence, VRAM, and notes. |
| `three_d_research.md` | Image-to-3D in late 2026, TRELLIS.2 vs Hunyuan3D 2.1, GLB export, viewer and Blender. |
| `video_research.md` | Wan 2.2 image-to-video, first+last frame, extend, and loop tricks. |
| `critic_passes.md` | The honest no-other-models note, the four reviewer-persona passes, and the pessimistic adversarial review (fixed vs still open). |
| `improvement_loops.md` | What each of the five test → critique → fix loops changed. |

How it was gathered:
- **Websites:** a scraper (Chrome user-agent), with WebFetch as a fallback.
- **ComfyUI:** a real ComfyUI 0.43.0 (commit 6b904b5, 2 Nov 2026) installed on the build machine, CPU-only.
  - `/object_info` gave the list of 1034 native nodes and their exact inputs.
  - The official `comfyui-workflow-templates` package (669 templates) supplied the reference settings and model links.
- **Model links:** each download link was checked with a ranged HTTP request (status 206, size recorded).
