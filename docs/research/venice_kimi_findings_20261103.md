# Venice/Kimi research findings from Andrew (2026-11-03): condensed by the main assistant
Source: Andrew pasted several Venice.ai (Kimi) research outputs plus a live test log. Several docs overlap. Doc 4 ("Research & Prompt Engineering Dossier") invented LoRA names (Wan2.2_Fluid_Motion_XL, Dynamic_Contact_v2, Ultra_Real_Skin_Texture, Physiology_Correct_Genitalia) and implausible settings (30-50 steps, CFG 5-7.5, flow_shift 1.0). DISCARD doc 4. Another doc assumed a 24GB GPU; Andrew has a 96GB RTX PRO 6000 + 2x 4090.

## ANDREW'S #1 PRIORITY LEARNING: "Still-first QC gate" (from a live Chroma -> Wan test)
- Generate 2+ Chroma still variants per shot (832x1248, 2:3, which maps to Wan 640x960 / 832x1248), SCORE each against the rubric BEFORE animating. Never animate a still with wrong anatomy; I2V preserves topology, it doesn't fix it.
- Typical still faults: malformed hands/thumbs/extra nubs, duplicate genitals, glans cleft, tip fused into labia (no separation means the "gloopy contact" failure in video), feet malformed, makeup look despite prompt, hot lamp blowout.
- Fix contact in the still first (inpaint/regenerate until separation and insertion are legible), then animate.
- For explicit contact framings: close-up contact framing, flat softbox/bounce frontal lighting, deeper DOF (f/8) so the join stays sharp. Add an "unretouched skin" clause (flat light made skin waxy) and a mid-grey background (whites clipped). If still too hot: half-power key plus a second fill behind camera.
- Angle results: frontal and rear framings succeeded (rear doggy, reverse cowgirl best: 8/10). PROFILE/side-on fails structurally: Chroma loses which opening is involved and entry reads on the thigh. Fix = ControlNet depth pass from a reference pose/3D mock or a different model, not re-rolls.
- Extreme close-ups are poor I2V start frames (no body context means drift and invented geometry at the edges). Pattern: a wide establishing still per position, plus a close-up still for detail; animate each separately and CUT between them in the edit.
- Best motion start pose: tip-at-entrance, so the first action is a push in.
- Venice test used "Wan 3.0" 5s with audio (130 credits); the video endpoint was slow/unreturned.

## Checkpoints (I2V merges with NSFW baked in)
- Wan2.2-Remix (FX_FeiHou): 4-8 steps, CFG 1, shift 5-10, Euler/simple, 720p. Failures: face drift on non-European faces, comic squatting, loop-back to the first frame above 81 frames, wrong-surface male anatomy on unprompted males. https://huggingface.co/FX-FeiHou/wan2.2-Remix , civarchive 2003153
- SmoothMix Wan 2.2 14B (DigitalPastel): 4-6 steps, CFG 1, Euler a/Normal or UniPC/Simple; v2 lacks merged lightx2v (blurry without it). Cons: breast inflation, male "glooping", brightness creep, auto makeup. civitai 1995784
- DaSiWa Lightspeed SynthSeduction v9 (low noise). Hybrid trick (altoiddealer): SmoothMix high + DaSiWa low, shift 5, 3 high / 4 low, CFG 1, lcm/beta, up to 1280x720.

## LoRAs (verify each)
- NSFW Motion Enhancer + Reward_LoRA_low (airi_mizuki17), civarchive 1985613: 3 high / 5 low steps, CFG 2.5 high / 1 low; Reward >=1.0, 0.5-0.6 when stacking.
- WAN General NSFW (lopi999), trigger nsfwsks: civitai 1307155, HF lopi999/Wan2.2-I2V_General-NSFW-LoRA.
- dr34ml4y All-in-One NSFW (civitai 1811313): 0.25-0.6, preserves faces.
- Kierkegaard420 Pussy I2V (civarchive 1895314): 0.5-1.0; French Kiss (2171333).
- NSFW/Female Genitals Helper: "detailed view of vulva in motion".
- Polyhedron perfect skin/hands/eyes (civarchive 1947995): 0.35 high / 0.6 low (causes extra toes).
- playtime_ai LoRAs (Orgasm, HIGH+LOW at full strength); mql position LoRAs for insertion consistency.
- Jerking Off (civitai 2224862); SVI 2 PRO (Kijai/WanVideo_comfy LoRAs/Stable-Video-Infinity/v2.0); CineScale 4-step AIO (civitai 1915394, update to AIO V10).
- Chroma: FineArtPhoto LoRA (civitai 2124475) for skin; NSFW LoRA strengths UNKNOWN, start at 0.6.
- Stacking rule: test one at a time; combine at 0.5-0.6; character LoRA 0.6-0.8; >0.9 overrides the reference image; LoRAs mostly on the LOW-noise path (no Wan 2.1 LoRAs on high noise); cap about 2 per stage or 3-4 total.

## Settings consensus
- Shift 8 default (5-10). res_multistep/sgm_uniform = realism pick; euler a/normal = motion pick. 4 high / 8 low when using 2.1 LoRAs. Final 2-step "clean pass" on the low model with only the lightning LoRA (darkroast175696, Civitai article 23316).
- Negatives are inert at CFG 1: use ComfyUI-NAG (github ChenDarYen/ComfyUI-NAG; supports Wan + Chroma) or CFG >=1.5.
- Max 81 frames per clip; chain clips (last frame -> next init, overlap 4-6 frames, crossfade) or use SVI 2 Pro.
- Chroma1-HD: 40 steps, CFG 3 official; community CFG 3-4, Euler/UniPC, drop RescaledCFG, weights <=2. Generate stills at 2x for cropping.
- Fast motion proofing on Wan 2.2 TI2V-5B before A14B. Sage attention. Seeds fixed. Auto-queue off.
- Nodes: VideoHelperSuite, Frame-Interpolation (RIFE/FILM), Impact-Pack FaceDetailer, rgthree, Crystools, NAG.

## Prompting
- I2V prompt = MOTION ONLY (the still owns appearance). One action + one camera move + one pace word per 5s; <60 words. Clinical/mechanical verbs beat slang. Name the rhythm ("continuous rhythmic motion"). Anchor both hands and every contact point limb by limb. "no makeup". Add skin displacement / flesh compression for contact. One environmental mover (steam, fog, neon flicker). Wan camera control is weak: prefer a static camera and add moves in post.
- Still template slots: SHOT/lens/DOF, SUBJECTS (21+), CONTACT MAP, BODY DETAIL, SKIN (pores, sheen, flush), LIGHT, STYLE TAIL (photoreal, 35mm grain, no makeup). Cyberpunk modifier block: magenta rim, teal fill, wet reflective surfaces, volumetric fog, anamorphic flare.

## Artifact -> fix table (merge into PRD)
face drift (bigger head, frontal still, char LoRA 0.7, DaSiWa low); squatting (Remix v2+, "standing straight, legs extended"); loop-back (<=81 frames); male anatomy wrong surface (male LoRA, male fully in still); glooping (DaSiWa low, more literal still); breast inflation (NAG negative); brightness creep (lower high CFG / lightning strength); blur after 2 frames (add lightx2v to SmoothMix v2); limb merging (anchor hands, clean pass); jitter (fewer LoRAs, lower CFG); leg count in multi-person shots (count in the still); duplicate genitals in POV (regenerate still); dark neon banding (8-step, fp16 VAE decode).

## Rubric (merge the best of the versions)
Weighted 100-pt: genital accuracy x3, hands x2, limb/joint x2, contact x3, skin x2, motion x3, identity x3, cross-angle x2, lighting x1, artifacts x1. Bands: 85+ keep; 70-84 trim/fix; 55-69 re-roll; <55 rebuild the still. Hard gates: detached genitals or phantom limbs cap at 4/10; face morph cap 5. Fail-fast at 0:02: hands, genitals, contact and face all OK, or abort. Diagnostic: if anatomy, hands and contact are all low, the still is the problem. Shot-log CSV: shot_id, character_id, still_model, still_seed, lora_stack, wan_variant, steps, cfg, shift, frames, i2v_prompt, negatives, score_total, worst_axis, notes.
