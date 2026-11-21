# The five improvement loops (test → critique → fix)

Each loop: run the self-test and screenshot run, critique from one viewpoint, fix, re-test.

| Loop | Viewpoint | Changes |
|---|---|---|
| **1** | Visual UX (19 screenshots, desktop + phone) | Image aspect ratio kept while loading. Look card split into Body / Skin / Face / Hair / Fantasy sub-tabs with counters and Next/Back. 🎲 Surprise me. Compact gallery cards with hover actions. Nested-card styling. Phone top bar. "item(s)" plural. Async errors inside a tab are caught and shown instead of a blank page. |
| **2** | Novice install and failure modes | Yellow "not installed yet" banner per tab. Plain-English "model file missing" error. Status loaded before the first screen. Fake-engine test with a deleted model. `download_models.py --check` (all 28 links OK, 139 GB measured). Start/install scripts point to the new server. Free-disk-space print. Corrected sizes and times. |
| **3** | Security | Automatic LAN password (`outputs/password.txt`, local bypass, `EASY_STUDIO_PASSWORD=off` or own value). CSRF header check. LoRA name validation. New wording patterns (looks/passes for an under-18 age, barely/only + age, face replace, face from photo, youngling, pre-adult). A→B video default motion. |
| **4** | ComfyUI expert | Checked Wan 4n+1 frame counts, extend stitching (drop duplicate first frame), loop trim, Qwen auto-scaling. **Fixed:** paint/inpaint on very large (upscaled) pictures now shrinks them to about 1.6 MP first, with a new test. Re-ran every workflow shape against real ComfyUI 0.43. |
| **5** | Docs and wording | README rewritten for v2 (tabs table, start flow, password, model groups with measured sizes and licences, troubleshooting, honest limits; rules box kept). Plain-English network, password and server errors in the browser. 422 errors no longer show "[object Object]". Advanced "Denoise" label explained. PRD roadmap, safety and open questions updated. These research notes. |

## Easy Studio 3 loops (6, 7, 8)

Each loop followed the same steps as before: run the full self-test (`tests/run_tests.py`, about 350 checks) and the
browser smoke run (`tests/ui_smoke.py`, which now covers the new Video studio, LoRA library, Train and 18+ screens),
critique the result, fix it, then run again.

| Loop | Viewpoint | Changes |
|---|---|---|
| **6** | Does every v3 feature actually work end-to-end? (test failures) | The fake ComfyUI didn't know about LoRA files on disk, so LoRA and training tests failed with "isn't installed yet". It now lists the LoRA folder like real ComfyUI does. **A full model was accepted as a LoRA** ("diff" matched "diffusion_model"), so the layer-name test was tightened. **LoRA thumbnails didn't show** (stale cache), so the cache now notices new preview files. **Deleted LoRAs were still listed** (stale ComfyUI list), so the list refreshes on delete. The final job message ("Done. 12 pictures…") was overwritten by "Done", and is now kept. LoRAs that ComfyUI finds in other folders now show up in the library and the Advanced drawers too. Trigger words are added to the prompt on the server, so they work from every tool. |
| **7** | Andrew's brief, item by item | **The Godot export had no export preset**, so `export_presets.cfg` was added (Windows, Linux and macOS desktop), with a test and a README line. 18+ outfits, packs, poses and motions only appear inside the 18+ section, through one helper, so nothing leaks into the normal area. The "My fictional character" upload text now says clearly that it is not a photo of a real person, "not even of me". PRD v3 (Part A) and README v3 were written, and Appendix A was regenerated from the CSV (174 rows). |
| **8** | UX on the screenshots | **Video studio's A → B mode didn't show the "End picture" box.** The server calls that mode `flf2v` and the page expected `ab`; it is now mapped, and the card reads "Start → end (A to B)". The word **"null"** appeared on the LoRA and Train pages where an optional part was left out. That's fixed for every page, and the smoke run now fails if any page shows "null", "undefined" or "NaN". **Built-in speed-up LoRAs** (Lightning / lightx2v) were listed in the LoRA library as if they were yours; they are now hidden. In the 18+ gate, long tick-box texts wrapped under the box instead of beside it. The training screenshot was taken mid-run, so the smoke run now waits for the pictures. The lightbox couldn't be closed with Esc, and a window left open blocked the next tab's buttons (found by the smoke run). Now Esc closes any window, and switching tabs closes it too. The smoke run now clicks *Make training pictures*, opens the 18+ gate, ticks both boxes, enters, and screenshots the 18+ Create, Photoshoot and Gallery. |

Adversarial safety pass for v3: see `critic_passes.md`, section "Easy Studio 3 adversarial pass".
