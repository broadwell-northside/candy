"""Owned rest-pose adapter from a source rig onto Genesis 9.

The first 3D test is this map. It is empty until a local PromptHMR GLB is
inspected. Nothing here has been run. The Genesis 9 export path stays unlocked
until the materials and morph-name research is folded in.
"""

FINGER_PLAN = ("prompt_hmr_hand_pose", "sam3d_body_mhr", "held_default_hand")
HAND_POSE_DEFAULT = False
BODY_ROTATIONS = 22
# The evaluation order is chosen. The round trip has not been run, so it is not closed.
EXPORT_PATH_LOCKED = False
EXPORT_EVALUATION = {
    "default": ["genesis9", "diffeomorphic_5.2.0", "blender_5.2", "gltf_2.0", "godot_4.7.2_forward_plus"],
    "fallback": "daz_to_blender",
    "not_adopted": "metahuman_unreal",
    "tested": False,
}
MORPH_MAX_CHARS = 56  # under the 57-character Diffeomorphic slice
GLTF_EXPORT = {
    "apply_modifiers": False,
    "shape_keys": True,
    "shape_key_normals": True,
    "shape_key_tangents": False,
    "animations": True,
    "shape_key_animations": True,
    "always_sample_animations": True,
    "sampling_rate_frames": 1,
    "reset_shape_keys_between_actions": True,
}
ROUND_TRIP_CHECKS = (
    "static_shape",
    "runtime_morph_control",
    "pose_driven_correctives",
    "rest_pose_bonemap",
)


class AdapterError(ValueError):
    pass


def bone_map():
    """Source bone name to Genesis 9 bone name. Empty means the test is not written."""
    return {}


def retarget(source_rotations, mapping=None):
    """Apply an explicit map. Refuses to invent bones."""
    mapping = bone_map() if mapping is None else mapping
    if not mapping:
        raise AdapterError("The Genesis 9 rest-pose map is not written yet.")
    missing = [name for name in source_rotations or {} if name not in mapping]
    if missing:
        raise AdapterError("No Genesis 9 bone for: " + ", ".join(missing))
    return {mapping[name]: value for name, value in source_rotations.items()}


def finger_plan():
    """Try a hand pose, then a separate hand pass, then a held pose. Choose after a local run."""
    return {
        "order": list(FINGER_PLAN),
        "hand_pose_default": HAND_POSE_DEFAULT,
        "body_rotations": BODY_ROTATIONS,
        "animated_fingers": False,
        "chosen": None,
    }


def morph_name_problems(names):
    """Names must be colon-free, unique, and under 57 characters."""
    problems = []
    seen = set()
    for name in names or []:
        if not isinstance(name, str) or not name:
            problems.append("empty name")
            continue
        if ":" in name:
            problems.append(name + " has a colon")
        if len(name) > MORPH_MAX_CHARS:
            problems.append(name + " is not under 57 characters")
        if name in seen:
            problems.append(name + " is duplicated")
        seen.add(name)
    return problems


def compare_imported_morphs(manifest, imported):
    """Post-import check: count, order, and names. Godot colons become underscores."""
    expected = [name.replace(":", "_") for name in (manifest or [])]
    got = list(imported or [])
    return {
        "count": len(expected) == len(got),
        "order": expected == got,
        "names": set(expected) == set(got),
        "mesh_merge": "off until this check passes",
    }


def round_trip_record():
    """Separate pass/fail rows. None means not run."""
    return {
        "status": "NOT_RUN",
        "checks": {name: None for name in ROUND_TRIP_CHECKS},
        "correctives": "bake or reimplement; glTF does not carry Daz ERC or Blender drivers",
        "materials": "author in Godot",
        "collision": "author in Godot",
        "cloth_and_springs": "author in Godot",
        "license_check": "each Daz product needs its own interactive license before purchase",
        "purchased": False,
    }


def contact_cleanup(people):
    """Two-person clips need an offset pass. Contact from the source is not assumed clean."""
    count = len(people or [])
    return {
        "required": count >= 2,
        "method": "collision_offset",
        "assumed_clean": False,
        "people": count,
        "note": "PromptHMR reports residual interpenetration in close pairs. WHAM contact reasoning is feet only.",
    }
