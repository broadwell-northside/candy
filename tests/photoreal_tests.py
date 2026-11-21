"""Photoreal stills, the video chain, body cards and the 18+ anatomy gate."""
import json
import os
import tempfile

import safety
import photoreal
import pipeline_candidates as pc
import shot_qc
import model_cards
import quality_harness
import outfit_contract
import g9_adapter
import machine_profiles
import model_registry as reg

HERE = os.path.dirname(os.path.abspath(__file__))


def unit(check):
    print("\n[31] Photoreal registry, stills, body, benchmark")
    chain = reg.video_chain()
    check("video chain order is i2v, upscale, interpolate",
          [s["id"] for s in chain] == ["wan22_i2v", "seedvr2_7b_sharp", "gimm_vfi"], [s["id"] for s in chain])
    path = tempfile.mktemp(suffix=".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"roles": {"video_i2v": {"id": "wan_custom", "label": "Custom Wan"},
                             "still_adult_fallback": {"adult_only": False},
                             "video_lora_stack": {"adult_only": False}}}, f)
    old = os.environ.get("EASY_STUDIO_MODEL_REGISTRY")
    os.environ["EASY_STUDIO_MODEL_REGISTRY"] = path
    try:
        swapped = reg.role("video_i2v")
        check("registry override replaces the video model id", swapped["id"] == "wan_custom" and swapped["label"] == "Custom Wan")
        check("registry override cannot clear the 18+ fallback", reg.role("still_adult_fallback")["adult_only"] is True)
        check("registry override cannot clear the adult video stack", reg.role("video_lora_stack")["adult_only"] is True)
    finally:
        if old is None:
            os.environ.pop("EASY_STUDIO_MODEL_REGISTRY", None)
        else:
            os.environ["EASY_STUDIO_MODEL_REGISTRY"] = old
        os.remove(path)
    plan = reg.pipeline()
    check("pipeline is still, motion, fix, finish", plan["order"] == ["still", "motion", "fix", "finish"])
    check("explicit still is Chroma and other stills are Z-Image", plan["still_explicit"] == "chroma1hd" and plan["still_other"] == "z_image_turbo")
    check("motion is Wan, control is SCAIL-2, long is SVI", plan["motion"] == "wan22_i2v" and plan["control"] == "scail2" and plan["long"] == "svi2_pro")
    check("control backups are Wan Animate and VACE-Fun", plan["control_backups"] == ["wan_animate", "vace_fun"])
    check("finish is 1080p then 30 fps", plan["finish_size"] == "1080p" and plan["finish_fps"] == 30 and plan["preview"] == "wan22_lightning")
    check("photoreal lengths are the 2s preview and the 5s take", reg.clip_lengths() == [2, 5])
    check("4 seconds snaps to the 5 second take", photoreal.snap_seconds(4, True) == 5)
    check("2 seconds stays the preview length", photoreal.snap_seconds(2, True) == 2 and photoreal.snap_seconds(9, True, preview=True) == 2)
    check("a non-photoreal 3 second clip is not snapped", photoreal.snap_seconds(3, False) == 3)
    check("explicit adult still uses Chroma", photoreal.choose_still({"look": "realistic"}, "photo", "adult", ["nude on silk"])["id"] == "chroma")
    check("clothed still stays Realistic", photoreal.choose_still({}, "photo", "adult", ["standing on the beach"])["id"] == "realistic")
    check("anime is not switched to Chroma", photoreal.choose_still({}, "anime", "adult", ["nude"]) is None)
    check("a close reference is named", "closely" in photoreal.reference_clause(0.9))
    check("a weak reference is a loose guide", "loose guide" in photoreal.reference_clause(0.25))
    check("default still is Z-Image", reg.role("still_realistic")["id"] == "z_image_turbo")
    mac = machine_profiles.active()
    check("the M5 Max is the first test machine", mac["id"] == "m5_max" and mac["device"] == "mps" and mac["first_test"] is True)
    names = set(machine_profiles.load()["profiles"])
    check("the 4090 and PRO 6000 profiles stay available", {"rtx_4090", "rtx_pro_6000"} <= names)
    check("the Mac Chroma weight is fp16 and not fp8", mac["chroma_dtype"] == "fp16" and mac["forbid_fp8_chroma"] is True)
    try:
        machine_profiles.check_chroma_file("Chroma1-HD-fp8.safetensors")
        check("an fp8-only Chroma file is refused on the Mac", False)
    except ValueError:
        check("an fp8-only Chroma file is refused on the Mac", True)
    check("short motion proofs use the fp16 5B model", mac["video_proof"] == "wan22_ti2v_5b" and "fp16" in mac["unet"])
    ids = {c["id"] for c in pc.candidates()}
    check("track 1 candidates are selectable and not selected",
          {"seedvr2_7b_int8_image", "supir_upscale", "z_image_turbo_template"} <= ids
          and pc.load()["selected"] is None and pc.active("still") is None and pc.active("upscale") is None)
    z = pc.candidate("z_image_turbo_template")
    seedvr = pc.candidate("seedvr2_7b_int8_image")
    supir = pc.candidate("supir_upscale")
    check("published Z-Image settings stay in the config",
          pc.widgets(z, "KSampler")[2:6] == [8, 1, "res_multistep", "simple"] and pc.widgets(z, "ModelSamplingAuraFlow") == [3])
    check("published SeedVR2 int8 and SUPIR settings stay in the config",
          pc.widgets(seedvr, "UNETLoader")[0] == "seedvr2_7b_int8_convrot.safetensors"
          and pc.widgets(supir, "BasicScheduler")[:3] == ["sgm_uniform", 10, 1])
    check("untested candidates are not the default", all(c["tested_locally"] is False and c["status"] == "NOT_RUN" for c in pc.candidates()))
    over = tempfile.mktemp(suffix=".json")
    with open(over, "w", encoding="utf-8") as f:
        json.dump({"selected": "supir_upscale"}, f)
    old_pc = os.environ.get("EASY_STUDIO_PIPELINE_CANDIDATES")
    os.environ["EASY_STUDIO_PIPELINE_CANDIDATES"] = over
    try:
        check("selecting an untested upscaler does not turn it on", pc.active("upscale") is None)
    finally:
        if old_pc is None:
            os.environ.pop("EASY_STUDIO_PIPELINE_CANDIDATES", None)
        else:
            os.environ["EASY_STUDIO_PIPELINE_CANDIDATES"] = old_pc
        os.remove(over)
    try:
        shot_qc.require_variants({"variants": [{"image": "a", "scores": {"hands": 8, "anatomy": 8, "contact": 8, "skin": 7, "lighting": 7}}]}, "a")
        check("one keyframe cannot be animated", False)
    except shot_qc.ShotQCError:
        check("one keyframe cannot be animated", True)
    bad = shot_qc.passing_qc("keep", "other")
    bad["variants"][0]["scores"]["contact"] = 2
    try:
        shot_qc.require_variants(bad, "keep")
        check("a failing still cannot be animated", False)
    except shot_qc.ShotQCError:
        check("a failing still cannot be animated", True)
    check("two scored stills can pass", shot_qc.require_variants(shot_qc.passing_qc("keep", "other"), "keep")["use"] == "keep")
    check("profile contact is blocked without a depth guide", shot_qc.plan_shot("profile", True, False)["blocked"] is True)
    check("profile contact is allowed with a depth guide", shot_qc.plan_shot("profile", True, True)["blocked"] is False)
    check("motion prompt is action, camera, and pace", shot_qc.i2v_prompt("pushes in", "static camera", "slowly") == "pushes in, static camera, slowly")
    try:
        shot_qc.i2v_prompt("word " * 61, "static", "slowly")
        check("motion prompt stays under 60 words", False)
    except shot_qc.ShotQCError:
        check("motion prompt stays under 60 words", True)
    perfect = {axis: 10 for axis in shot_qc.RUBRIC_WEIGHTS}
    check("rubric of tens is 100 and a keep", shot_qc.rubric_total(perfect) == {"total": 100.0, "band": "keep"})
    check("detached anatomy caps the rubric", shot_qc.rubric_total(perfect, ["detached"])["total"] == 40)
    check("frame cap is 81 and longer clips chain", shot_qc.cap_frames(49) == (49, False) and shot_qc.cap_frames(161) == (81, True))
    check("remix, smoothmix, and dasiwa are selectable checkpoints",
          {c["id"] for c in reg.video_checkpoints()} >= {"wan22_remix", "smoothmix_14b", "dasiwa_lightspeed_v9", "hybrid_smoothmix_high_dasiwa_low"})
    check("the running default checkpoint stays Wan 2.2", reg.role("video_i2v")["id"] == "wan22_i2v")
    check("sampling keeps NAG, the clean pass, and the 5B proofer",
          reg.sampling()["nag_when_cfg"] == 1 and reg.sampling()["clean_pass_steps"] == 2 and reg.sampling()["proofer"] == "wan22_ti2v_5b")
    check("contact preset asks for softbox, f/8, and mid-grey",
          "softbox" in shot_qc.contact_clause() and "f/8" in shot_qc.contact_clause() and "mid-grey" in shot_qc.contact_clause())
    check("fail-fast at 0:02 needs every check", shot_qc.fail_fast_ok({"hands": True, "genitals": True, "contact": True, "face": False}) is False)
    order = pc.finishing_order()
    check("finishing candidates stay in research order and off",
          order == ["seedvr2_7b_int8_image", "realesrgan_x4plus", "z_image_refine_h2logs", "no_enhancement"]
          and pc.active("finish") is None)
    fast = pc.candidate("z_image_turbo_fast_still")
    klein = pc.candidate("flux2_klein_4b_edit")
    qwen = pc.candidate("qwen_image_edit_2511")
    check("fast still and outfit fallbacks keep the published settings",
          fast["settings"]["steps"] == 8 and fast["settings"]["shift"] == 3
          and klein["settings"]["steps"] == 4 and klein["settings"]["cfg"] == 1
          and qwen["settings"]["steps"] == 40 and qwen["settings"]["cfg"] == 4 and qwen["settings"]["turbo"] is False)
    check("Wan templates come before Hunyuan and LTX",
          pc.candidate("wan22_14b_i2v_template")["rank"] == 1
          and pc.candidate("hunyuan_video_15_720p_i2v")["rank"] == 2
          and pc.candidate("ltx25_i2v_template")["rank"] == 3)
    native = pc.candidate("wan22_14b_i2v_template")["settings"]
    flf = pc.candidate("wan22_14b_flf2v_template")["settings"]
    check("native Wan recipe is 20 steps, CFG 3.5, shift 5, 81 frames",
          native["steps"] == 20 and native["cfg"] == 3.5 and native["shift"] == 5 and native["frames"] == 81 and native["fps"] == 16)
    check("first-last recipe is CFG 4 and shift 8", flf["cfg"] == 4 and flf["shift"] == 8 and flf["four_step_branch"] == "bypassed")
    check("acceleration waits until native motion passes",
          pc.candidate("wan22_lightx2v_4step")["after"] == "native_motion_passes"
          and pc.candidate("endless_wan_svi2pro")["one_change_at_a_time"] is True
          and pc.candidate("wan22_5b_ti2v")["rank"] == 4)
    check("video finish keeps native frames before RIFE",
          pc.video_finishing_order() == ["native_frames", "seedvr2_3b_video", "seedvr2_7b_video", "color_match", "rife", "encode"])
    check("3D motion order is PromptHMR, WHAM, then GVHMR",
          pc.motion_3d_order() == ["prompthmr_glb", "wham", "gvhmr"] and pc.active("motion_3d") is None)
    check("the Genesis 9 map is empty owned code", g9_adapter.bone_map() == {} and g9_adapter.EXPORT_PATH_LOCKED is False)
    try:
        g9_adapter.retarget({"hips": [0, 0, 0]})
        check("retarget refuses an unwritten map", False)
    except g9_adapter.AdapterError:
        check("retarget refuses an unwritten map", True)
    fingers = g9_adapter.finger_plan()
    check("fingers are a later choice and are not animated yet",
          fingers["order"] == ["prompt_hmr_hand_pose", "sam3d_body_mhr", "held_default_hand"]
          and fingers["hand_pose_default"] is False and fingers["body_rotations"] == 22 and fingers["animated_fingers"] is False)
    pair = g9_adapter.contact_cleanup(["a", "b"])
    check("two people require contact cleanup", pair["required"] is True and pair["assumed_clean"] is False)
    check("one person does not pretend a pair contact pass", g9_adapter.contact_cleanup(["a"])["required"] is False)
    check("export test order is Diffeomorphic then glTF then Godot",
          g9_adapter.EXPORT_EVALUATION["default"] == ["genesis9", "diffeomorphic_5.2.0", "blender_5.2", "gltf_2.0", "godot_4.7.2_forward_plus"]
          and g9_adapter.EXPORT_EVALUATION["not_adopted"] == "metahuman_unreal"
          and g9_adapter.EXPORT_EVALUATION["tested"] is False)
    check("morph names must be short, unique, and colon-free",
          g9_adapter.morph_name_problems(["SmileBody"]) == []
          and g9_adapter.morph_name_problems(["Smile:Body"]) 
          and g9_adapter.morph_name_problems(["a" * 57]))
    imported = g9_adapter.compare_imported_morphs(["SmileBody", "JawOpen"], ["SmileBody", "JawOpen"])
    check("import check compares count, order, and names", imported["count"] and imported["order"] and imported["names"])
    drifted = g9_adapter.compare_imported_morphs(["SmileBody"], ["SmileBody 2"])
    check("a renamed Godot target fails the manifest", drifted["names"] is False)
    trip = g9_adapter.round_trip_record()
    check("round trip scores shape, morphs, and correctives separately",
          trip["status"] == "NOT_RUN" and set(trip["checks"]) == set(g9_adapter.ROUND_TRIP_CHECKS)
          and trip["purchased"] is False and g9_adapter.GLTF_EXPORT["apply_modifiers"] is False)
    check("FLUX 3 stays behind an unread license",
          pc.candidate("flux3_klein")["blocked_until"] == "license_read" and model_cards.card("flux3_klein")["license"] == "unread")
    video_row = quality_harness.blank_video_record("wan22_14b_i2v_template")
    check("video test names the three clips and keeps native frames",
          video_row["clips"] == list(quality_harness.VIDEO_CLIPS) and video_row["keep_native_fps"] is True
          and "foot_slide" in video_row["video_scores"] and video_row["status"] == "NOT_RUN")
    check("benchmark clips are a floor, not the whole review",
          video_row["benchmark_cases"] == ["C06-01", "C06-02", "C06-03"]
          and video_row["benchmark_floor"]["width"] == 496
          and "flicker" in video_row["benchmark_review"]
          and "blink" in video_row["benchmark_unknown_from_stills"])
    check("non-commercial cards stay marked",
          model_cards.noncommercial("supir") and model_cards.noncommercial("catvton")
          and model_cards.card("seedvr2_7b_int8")["license"] == "Apache-2.0")
    blank = quality_harness.blank_record("seedvr2_7b_int8_image")
    check("quality record starts unrun and names the blind axes",
          blank["status"] == "NOT_RUN" and quality_harness.missing_fields(blank) == []
          and set(quality_harness.BLIND_AXES) <= set(blank["blind"]))
    from PIL import Image as _Image
    base = tempfile.mktemp(suffix=".png")
    edit = tempfile.mktemp(suffix=".png")
    out = tempfile.mktemp(suffix=".png")
    _Image.new("RGB", (20, 20), (10, 20, 30)).save(base)
    _Image.new("RGB", (20, 20), (200, 0, 0)).save(edit)
    mask = _Image.new("L", (20, 20), 0)
    mask.putpixel((10, 10), 255)
    info = outfit_contract.composite_unmasked(base, edit, mask, out)
    with _Image.open(out) as got, _Image.open(base) as src:
        check("outfit composite keeps pixels outside the mask", got.getpixel((0, 0)) == src.getpixel((0, 0)) and got.getpixel((10, 10)) == (200, 0, 0) and info["unchanged_region"] == "exact")
    os.remove(base)
    os.remove(edit)
    os.remove(out)
    row = photoreal.look("realistic")
    check("realistic look keeps its preset id", row["id"] == "realistic" and row["shift"] == 2)
    check("skin words on realistic", "pores" in photoreal.skin_clause(row))
    check("glam does not ask for pores", "pores" not in photoreal.skin_clause(photoreal.look("glam")))
    try:
        photoreal.resolve_look({"look": "chroma"}, "photo", "default")
        check("chroma refused outside 18+", False)
    except photoreal.PhotorealError:
        check("chroma refused outside 18+", True)
    check("chroma allowed inside 18+", photoreal.resolve_look({"look": "chroma"}, "photo", "adult")["id"] == "chroma")
    try:
        photoreal.skin_lora_slot({"skin_lora": "skin.safetensors", "camera": "full"}, row)
        check("skin LoRA refused off a close-up", False)
    except photoreal.PhotorealError:
        check("skin LoRA refused off a close-up", True)
    check("one skin LoRA on a close-up", photoreal.skin_lora_slot({"skin_lora": "skin.safetensors", "camera": "closeup"}, row)[1] == 0.5)
    try:
        photoreal.body_card({"gender": "woman", "age": 12, "traits": {"bust": "b_large"}})
        check("body card refuses age 12 instead of raising it", False)
    except photoreal.PhotorealError as e:
        check("body card refuses age 12 instead of raising it", "age=12" in str(e), str(e))
    female = photoreal.body_card({"gender": "woman", "age": 21, "traits": {"bust": "b_large"}})
    male = photoreal.body_card({"gender": "man", "age": 40, "traits": {"body": "muscular"}})
    check("body card keeps a stated age of 21", female["age"] == 21 and female["stated_age"] == 21 and female["sex"] == "female" and "bust" in female["sliders"] and "appearance_check" not in female)
    check("male body card has a chest slider", male["sex"] == "male" and "chest" in male["sliders"] and "bust" not in male["sliders"])
    check("body card is not a real person", female["real_person"] is False and male["fictional"] is True)
    face = photoreal.detailer_plan("realistic", "female", True, "default")
    check("face fix is not automatic", [p["part"] for p in face] == ["hands", "body"])
    asked = photoreal.detailer_plan("realistic", "female", True, "default", face_fix=True)
    check("face fix is opt-in at 0.35", asked[0]["part"] == "face" and asked[0]["denoise"] == 0.35)
    adult_f = photoreal.detailer_plan("realistic", "female", False, "adult")
    adult_m = photoreal.detailer_plan("realistic", "male", False, "adult")
    check("18+ detailer names female regions", "genitals_female" in adult_f[-1]["regions"] and "genitals_male" not in adult_f[-1]["regions"])
    check("18+ detailer names male regions", "genitals_male" in adult_m[-1]["regions"] and "breasts" not in adult_m[-1]["regions"])
    mask = photoreal.clothing_mask(100, 100)
    check("mask protects the face", mask.getpixel((50, 5)) == 0)
    check("mask protects a hand", mask.getpixel((5, 60)) == 0)
    check("mask repaints the torso", mask.getpixel((50, 50)) == 255)
    try:
        photoreal.anatomy_loras([{"category": "breasts", "name": "a.safetensors", "strength": 0.6}], "default", "female")
        check("anatomy LoRA refused outside 18+", False)
    except photoreal.PhotorealError:
        check("anatomy LoRA refused outside 18+", True)
    try:
        photoreal.anatomy_loras([{"category": "genitals_male", "name": "a.safetensors"}], "adult", "female")
        check("male anatomy refused on a woman", False)
    except photoreal.PhotorealError:
        check("male anatomy refused on a woman", True)
    try:
        photoreal.anatomy_loras([{"category": "breasts", "name": "teen_body.safetensors"}], "adult", "female")
        check("youthful anatomy name refused", False)
    except photoreal.PhotorealError:
        check("youthful anatomy name refused", True)
    stacked = photoreal.anatomy_loras(
        [{"category": "breasts", "name": "breasts_v1.safetensors", "strength": 0.6},
         {"category": "skin", "name": "skin_v1.safetensors", "strength": 1}], "adult", "female")
    check("two categories can stack", len(stacked) == 2 and stacked[0][1] == 0.6)
    rows = photoreal.build_realism60()
    check("realism-60 has 60 prompts and two seeds", len(rows) == 60 and all(r["seeds"] == [101, 202] for r in rows))
    check("realism-60 ages are 21 or older", all(21 <= r["age"] <= 55 for r in rows))
    check("realism-60 buckets", {r["bucket"] for r in rows} >= {"portrait", "half", "full", "hands", "group", "adult"})
    adult = photoreal.build_adult_benchmark()
    sexes = {r["sex"] for r in adult}
    angles = {r["angle"] for r in adult}
    poses = {r["pose"] for r in adult}
    check("18+ benchmark covers both sexes and every angle and pose",
          sexes == {"female", "male"} and angles == set(photoreal.ANGLES) and poses == set(photoreal.POSE_IDS))
    blocked = [r["id"] for r in rows + adult if not safety.check_prompt(r["prompt"])[0]]
    check("benchmark prompts pass the word check", not blocked, blocked[:3])
    explicit = [r["id"] for r in rows if r["adult"] and safety.check_area(r["prompt"], "default")[0]]
    check("gated benchmark prompts are refused in the normal area", not explicit, explicit)
    check("targets include anatomy and video", photoreal.TARGETS["adult_anatomy_median"] == 4 and photoreal.TARGETS["video_arcface_min"] == 0.60)


def e2e(a, mock_url, check, requests):
    print("\n[32] Photoreal video chain and keyframe")
    import requests as rq
    requests = requests or rq
    dna = {"gender": "woman", "age": 28, "style": "photo", "name": "Mara", "traits": {"body": "average"}}
    j = a.job("create", {"dna": dna, "count": 1, "look": "realistic", "camera": "closeup"})
    check("realistic still is made", j["status"] == "done" and j["results"], j.get("error"))
    if not j.get("results"):
        return
    still = j["results"][0]
    sent = requests.get(mock_url + "/mock/log").json()[-1]
    blob = json.dumps(sent)
    check("realistic still asks for pores and shift 2", "visible pores" in blob and '"shift": 2' in blob, blob[max(0, blob.find("shift") - 30):blob.find("shift") + 40])
    check("still provenance names the look", still.get("provenance", {}).get("look") == "realistic", still.get("provenance"))
    j = a.job("create", {"dna": dna, "count": 1, "look": "glam", "camera": "half"})
    blob = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("glam does not ask for pores", j["status"] == "done" and "visible pores" not in blob, j.get("error"))
    other = (j.get("results") or [{}])[0]
    j = a.job("create", {"dna": dna, "count": 1, "look": "chroma"})
    check("chroma still is refused in the normal area", j["status"] in ("error", "refused") and "18+" in (j.get("error") or ""), j.get("error"))
    j = a.job("video", {"image": still["id"], "motion": "wind", "seconds": 2, "photoreal": True})
    check("video without a still gate is refused", j["status"] in ("error", "refused") and "keyframe" in (j.get("error") or "").lower(), j.get("error"))
    qc = shot_qc.passing_qc(still["id"], other.get("id"))
    j = a.job("video", {"image": still["id"], "motion": "wind", "seconds": 2, "photoreal": True, "qc": qc,
                        "anatomy": [{"category": "breasts", "name": "breasts_v1.safetensors", "strength": 0.6}]})
    check("anatomy LoRA on video is refused outside 18+", j["status"] in ("error", "refused"), j.get("error"))
    # The 18+ success path runs from v3_tests while that device is unlocked.
    # Here the gate may already be locked out, so only the refusal is checked above.
    j = a.job("outfit_locked", {"image": still["id"], "item": "jeans_tee"})
    check("masked outfit edit runs", j["status"] == "done", j.get("error"))
    if j.get("results"):
        prov = j["results"][0].get("provenance") or {}
        check("outfit edit records protected regions", prov.get("protected") == ["face", "hands", "background"])
        check("outfit edit keeps the approved source", prov.get("approved_source") == still["id"] and prov.get("checks", {}).get("unchanged_region") == "exact")
        again = a.job("outfit_locked", {"image": j["results"][0]["id"], "item": "sundress"})
        check("a re-edit starts from the approved source", again["status"] == "done" and (again.get("results") or [{}])[0].get("provenance", {}).get("approved_source") == still["id"], again.get("error"))
    from PIL import Image
    cloth = a.upload(Image.new("RGB", (64, 96), (180, 20, 20)), "clothing", name="red_dress.png").json()
    j = a.job("edit", {"image": still["id"], "op": "outfit", "ref": cloth["id"], "text": "red dress", "reference_strength": 0.25})
    check("reference strength is kept on the try-on", j["status"] == "done" and "loose guide" in ((j.get("results") or [{}])[0].get("prompt") or ""), j.get("error"))
    j = a.job("contact_repair", {"image": still["id"], "text": "clear separation"})
    check("contact repair stays in the 18+ section", j["status"] in ("error", "refused") and "18+" in (j.get("error") or ""), j.get("error"))
    j = a.job("video", {"image": still["id"], "motion": "wind", "seconds": 4, "photoreal": True, "qc": qc,
                        "action": "hair moves", "camera_move": "static camera", "pace": "gently"})
    check("image goes straight to a fixed-length video", j["status"] == "done" and (j.get("results") or [{}])[0].get("provenance", {}).get("seconds") == 5, j.get("error"))
    sent_v = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("the first test machine proofs motion on Wan 5B fp16", "wan2.2_ti2v_5B_fp16.safetensors" in sent_v, sent_v[:240])
    if j.get("results"):
        vid = j["results"][0]
        check("finish records 1080p and 30 fps", [c.get("stage") for c in vid["provenance"]["chain"]][-2:] == ["upscale", "interpolate"] and vid["provenance"]["chain"][-1]["to_fps"] == 30)
        js = a.job("video_still", {"video": vid["id"], "frame": "last"})
        check("a still is saved from the video", js["status"] == "done" and (js.get("results") or [{}])[0].get("provenance", {}).get("source_video") == vid["id"], js.get("error"))
    saved = a.post("/api/characters", json={"gender": "woman", "age": 28, "style": "photo", "name": "Mara"}).json()
    j = a.job("regenerate", {"character": saved["id"], "seed": 4242})
    check("regenerate uses the saved character and the new seed", j["status"] == "done" and (j.get("results") or [{}])[0].get("seed") == 4242 and (j.get("results") or [{}])[0].get("provenance", {}).get("regenerated_from") == saved["id"], j.get("error"))
    r = a.post("/api/jobs", json={"kind": "create", "params": {"dna": dna, "count": 1}, "request_id": "same-still"})
    r2 = a.post("/api/jobs", json={"kind": "create", "params": {"dna": dna, "count": 1}, "request_id": "same-still"})
    check("same request id does not start a second job", r.status_code == 200 and r.json()["id"] == r2.json()["id"])
