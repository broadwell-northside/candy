"""Local quality-test record. Nothing here has been run.

A row is a blank form until a desktop test fills GPU, hashes, seeds, time, and
the blind scores. File size is not memory.
"""

BLIND_AXES = (
    "identity",
    "skin_waxiness",
    "invented_pores",
    "hands",
    "seams",
    "color_shift",
)
RECORD_FIELDS = (
    "gpu_name",
    "vram_mib",
    "model_hashes",
    "seeds",
    "latency_s",
    "peak_memory_mib",
    "blind",
    "status",
)
VIDEO_CLIPS = (
    "face_turn_blink",
    "full_body_walk_feet",
    "two_clothed_adults_hug_dance",
)
VIDEO_SCORE_AXES = (
    "face_continuity",
    "body_continuity",
    "fingers",
    "foot_slide",
    "contact_separation",
    "hair_fabric",
    "background_drift",
    "camera_drift",
)
# Budget-tier reference clips. Not a spec and not a quality ceiling.
BENCHMARK_CASES = (
    {"id": "C06-01", "scene": "skin_closeup"},
    {"id": "C06-02", "scene": "full_body_turn"},
    {"id": "C06-03", "scene": "two_person_hand_hold"},
)
BENCHMARK_REVIEW = (
    "blink",
    "identity_consistency",
    "foot_sliding",
    "hands_fingers",
    "flicker",
)
BENCHMARK_FLOOR = {
    "width": 496,
    "height": 864,
    "fps": 24,
    "frames": 97,
    "audio": False,
    "role": "beat this resolution and fine skin and iris detail",
}


def blank_record(candidate_id):
    return {
        "candidate": candidate_id,
        "gpu_name": "",
        "vram_mib": None,
        "model_hashes": {},
        "seeds": [],
        "latency_s": None,
        "peak_memory_mib": None,
        "blind": {axis: None for axis in BLIND_AXES},
        "status": "NOT_RUN",
    }


def blank_video_record(candidate_id):
    """Still-first scoring stays separate. This row is the motion test."""
    row = blank_record(candidate_id)
    row.update({
        "clips": list(VIDEO_CLIPS),
        "video_scores": {axis: None for axis in VIDEO_SCORE_AXES},
        "keep_native_frames": True,
        "keep_native_fps": True,
        "seed_behavior": "",
        "precision": "",
        "cold_s": None,
        "warm_s": None,
        "failures": [],
        "long_clip_boundaries": "inspect every join plus first, middle, and last identity",
        "benchmark_cases": [row["id"] for row in BENCHMARK_CASES],
        "benchmark_review": {axis: None for axis in BENCHMARK_REVIEW},
        "benchmark_floor": dict(BENCHMARK_FLOOR),
        "benchmark_unknown_from_stills": (
            "continuous_motion", "blink", "identity_drift", "foot_sliding", "finger_counts", "flicker",
        ),
    })
    return row


def missing_fields(row):
    row = row or {}
    missing = [name for name in RECORD_FIELDS if name not in row]
    blind = row.get("blind") if isinstance(row.get("blind"), dict) else {}
    for axis in BLIND_AXES:
        if axis not in blind:
            missing.append("blind." + axis)
    return missing
