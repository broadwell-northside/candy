# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Recipes: the Graphic Workflow Editor (PRD §5). A recipe is a short form that compiles into ONE existing
job kind and is submitted to the normal job queue. There is no second runner.

    portrait_still  -> workshop_still
    one_actor_film  -> film            (on a kept still)
    send_to_island  -> export_godot

Stages always run in this order and cannot be reordered: Subject, Look, Pose, Scene, Camera, Quality, Output.
Each stage can be switched on or off (Subject cannot) and saved as a preset. Stages a recipe does not use
are listed with a plain reason.

The compiler calls the same graph builders as the jobs (stills.build_still_graph, films.build_film_graph),
so the read-only node drawer shows the graph that runs, and the canonical hash of the executed graph equals
the compiled one. Defaults exist only for camera and size. Age never has a default: a recipe points at a
saved fictional adult whose age was typed into that character's field.
"""
import copy
import hashlib
import json
import os
import random

import catalog
import content_mode as CM
import safety

FORMAT = "easy-studio-recipe/1"
PRIVATE_NOTICE = "PRIVATE BUILD — NOT FOR DISTRIBUTION"
STAGES = ("subject", "look", "pose", "scene", "camera", "quality", "output")
STAGE_LABELS = {
    "subject": "Subject", "look": "Look", "pose": "Pose", "scene": "Scene",
    "camera": "Camera", "quality": "Quality", "output": "Output",
}
STAGE_TIPS = {
    "subject": "Who is in it: one saved fictional adult. Their age is the one typed when they were saved.",
    "look": "Clothes, body and a few words about the look.",
    "pose": "How the person stands, or how they move in a film.",
    "scene": "Where it happens.",
    "camera": "The lens and framing, or the camera move in a film. This one has a default.",
    "quality": "Which model and template make it. Fixed for these recipes.",
    "output": "What comes out, its size, and the seed.",
}
LOOK_LIMIT = 300

POSES = [
    {"id": "standing", "label": "Standing, relaxed", "phrase": "standing relaxed, weight on one leg"},
    {"id": "seated", "label": "Seated", "phrase": "seated, hands resting in the lap"},
    {"id": "leaning", "label": "Leaning on a rail", "phrase": "leaning on a wooden rail, relaxed"},
    {"id": "walking", "label": "Mid-step", "phrase": "walking, caught mid-step"},
]
SCENES = [
    {"id": "beach_golden", "label": "Beach at golden hour", "phrase": "on a quiet beach at golden hour"},
    {"id": "villa_terrace", "label": "Villa terrace", "phrase": "on a white villa terrace above the sea"},
    {"id": "pool_evening", "label": "Pool in the evening", "phrase": "beside a pool in the warm evening light"},
    {"id": "studio_grey", "label": "Plain studio", "phrase": "in a plain grey photo studio"},
]
CAMERAS = [
    {"id": "portrait_85", "label": "85 mm portrait, eye level", "phrase": "85mm portrait lens, eye level", "default": True},
    {"id": "waist_50", "label": "50 mm, waist up", "phrase": "50mm lens, framed from the waist up"},
    {"id": "full_35", "label": "35 mm, full length", "phrase": "35mm lens, full-length framing"},
]
CAMERA_MOVES = [
    {"id": "static", "label": "Camera still", "phrase": "camera still", "default": True},
    {"id": "push_in", "label": "Slow push-in", "phrase": "slow camera push-in"},
    {"id": "pan", "label": "Gentle pan", "phrase": "gentle camera pan"},
]
FILM_SECONDS = (2, 5)
# Every option is a node: both flags are required (content_mode.node_reachable).
for _row in POSES + SCENES + CAMERAS + CAMERA_MOVES:
    _row.setdefault("sfw_safe", True)
    _row.setdefault("requires_full_21_mode", False)

RECIPES = {
    "portrait_still": {
        "label": "Portrait still", "kind": "workshop_still", "icon": "📷",
        "blurb": "One fictional adult, one photo-style still.",
        "uses": ("subject", "look", "pose", "scene", "camera", "quality", "output"),
        "required": {"subject": ("character",), "look": ("wardrobe",)},
        "fixed": {"quality": "Z-Image (Turbo, or the base model when a saved face is used). This recipe has one quality.",
                  "output": "One still, 1024 × 1536, portrait."},
        "unused": {},
        "phase": "Step 1 of 1 · Making a still",
    },
    "one_actor_film": {
        "label": "Film from a still", "kind": "film", "icon": "🎬",
        "blurb": "A 2 or 5 second clip of one person, made from a still you kept.",
        "uses": ("subject", "pose", "camera", "quality", "output"),
        "required": {"subject": ("still",), "output": ("seconds",)},
        "fixed": {"quality": "Wan 2.2 I2V-A14B quality template, 720p, no sound. Steps stay with the template's own "
                             "high/low split; the fast lightx2v template is not used here."},
        "unused": {"look": "A film keeps the look of its still.", "scene": "A film keeps the scene of its still."},
        "tips": {"subject": "The kept still this film starts from. The person and their stated age come with it.",
                 "pose": "How the person moves. Off means a small, slow movement.",
                 "camera": "The camera move. This one has a default: camera still."},
        "phase": "Step 1 of 1 · Making a short film",
    },
    "send_to_island": {
        "label": "Send to the island", "kind": "export_godot", "icon": "🏝️",
        "blurb": "Pack one character for Stillwater. Check it against the island first; nothing is copied.",
        "uses": ("subject", "output"),
        "required": {"subject": ("character",)},
        "fixed": {"output": "A Godot pack (.zip): portraits, kept clips and character.json, covered pictures unless 21+ is on."},
        "unused": {"look": "The pack uses pictures you already kept.", "pose": "The pack uses pictures you already kept.",
                   "scene": "The island has its own places.", "camera": "The island has its own cameras.",
                   "quality": "Nothing is rendered for a pack."},
        "phase": "Step 1 of 1 · Making the island pack",
    },
}

STAGE_KEYS = {
    "subject": {"character", "still", "sidecar_sha256"},
    "look": {"wardrobe", "body", "look"},
    "pose": {"pose", "motion"},
    "scene": {"scene"},
    "camera": {"camera"},
    "quality": set(),
    "output": {"seconds"},
}


class RecipeError(ValueError):
    """A plain-English problem with the recipe. `stage` names the stage it belongs to."""

    def __init__(self, message, stage=""):
        super().__init__(message)
        self.stage = stage


# --------------------------------------------------------------------------- catalogue for the page
def catalogue(sfw_mode):
    """Everything the recipe page shows. Options that need full 21+ mode are not listed in SFW mode."""
    def keep(rows):
        return [{k: v for k, v in row.items()} for row in rows if CM.node_reachable(row, sfw_mode)]

    motions = [dict(row, sfw_safe=True, requires_full_21_mode=False) for row in catalog.MOTIONS]
    if sfw_mode is False:
        motions += [dict(row, sfw_safe=False, requires_full_21_mode=True) for row in catalog.ADULT_MOTIONS]
    wardrobe = [{"id": wid, "label": (catalog.outfit_item(wid) or {}).get("label", wid)} for wid in catalog.WORKSHOP_CLOTHED]
    if CM.wardrobe_allowed(catalog.WORKSHOP_NUDE, sfw_mode):
        wardrobe.append({"id": catalog.WORKSHOP_NUDE, "label": "Nude (21+)", "requires_full_21_mode": True})
    import stills
    return {
        "format": FORMAT, "notice": PRIVATE_NOTICE, "stages": [
            {"id": sid, "label": STAGE_LABELS[sid], "tip": STAGE_TIPS[sid]} for sid in STAGES],
        "recipes": [{"id": rid, **{k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()
                                   if k != "required"},
                     "required": {k: list(v) for k, v in r["required"].items()}} for rid, r in RECIPES.items()],
        "poses": keep(POSES), "scenes": keep(SCENES), "cameras": keep(CAMERAS), "camera_moves": keep(CAMERA_MOVES),
        "motions": keep(motions), "wardrobe": wardrobe, "bodies": stills.body_ids(), "seconds": list(FILM_SECONDS),
        "sfw_mode": sfw_mode, "look_limit": LOOK_LIMIT,
    }


# --------------------------------------------------------------------------- shape
def _find(rows, oid, stage, sfw_mode):
    for row in rows:
        if row["id"] == oid:
            if not CM.node_reachable(row, sfw_mode):
                raise RecipeError("That choice needs full 21+ mode. SFW mode is on.", stage)
            return row
    raise RecipeError("Pick one of the choices this page offers.", stage)


def _default(rows):
    return next(row for row in rows if row.get("default"))


def normalize(doc):
    """Check the recipe's shape. Returns a clean copy. Stage order is fixed; reordering is refused."""
    if not isinstance(doc, dict):
        raise RecipeError("That is not a recipe.")
    rid = doc.get("recipe")
    if rid not in RECIPES:
        raise RecipeError("Pick one of the recipes on the Make page.")
    order = doc.get("order")
    if order is not None and list(order) != list(STAGES):
        raise RecipeError("Stages run in a fixed order (Subject, Look, Pose, Scene, Camera, Quality, Output). "
                          "They cannot be reordered.")
    stages_in = doc.get("stages") or {}
    if not isinstance(stages_in, dict):
        raise RecipeError("That recipe's stages are not readable.")
    unknown = set(stages_in) - set(STAGES)
    if unknown:
        raise RecipeError("This app has no stage called " + ", ".join(sorted(unknown)) + ".")
    spec = RECIPES[rid]
    stages = {}
    for sid in STAGES:
        row = stages_in.get(sid) or {}
        if not isinstance(row, dict):
            raise RecipeError("That stage is not readable.", sid)
        values = row.get("values") or {}
        if not isinstance(values, dict):
            raise RecipeError("That stage is not readable.", sid)
        extra = set(values) - STAGE_KEYS[sid]
        if extra:
            raise RecipeError("This stage does not take " + ", ".join(sorted(extra)) + ".", sid)
        on = row.get("on", sid in spec["uses"])
        if not isinstance(on, bool):
            raise RecipeError("A stage is on or off.", sid)
        if sid == "subject":
            on = True  # Subject is always on.
        if sid not in spec["uses"]:
            on = False
        clean = {}
        for key, value in values.items():
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            if isinstance(value, str):
                value = value.strip()
                if "op://" in value:
                    raise RecipeError("A recipe never holds a secret reference.", sid)
            clean[key] = value
        stages[sid] = {"on": on, "values": clean}
    seed = doc.get("seed")
    if seed is not None and (seed == "" or (isinstance(seed, str) and not seed.strip())):
        seed = None
    if seed is not None:
        if isinstance(seed, bool) or (isinstance(seed, float) and not float(seed).is_integer()):
            raise RecipeError("The seed has to be a whole number.", "output")
        try:
            seed = int(str(seed).strip()) if isinstance(seed, str) else int(seed)
        except (TypeError, ValueError):
            raise RecipeError("The seed has to be a whole number.", "output")
        if seed < 0 or seed >= 2**53:
            raise RecipeError("The seed has to be a whole number from 0 up.", "output")
    name = str(doc.get("name") or spec["label"])[:80]
    return {"format": FORMAT, "recipe": rid, "name": name, "order": list(STAGES), "stages": stages, "seed": seed}


def _value(doc, sid, key):
    stage = doc["stages"][sid]
    return stage["values"].get(key) if stage["on"] else None


def _require(doc):
    spec = RECIPES[doc["recipe"]]
    for sid, keys in spec["required"].items():
        for key in keys:
            if _value(doc, sid, key) in (None, ""):
                words = {"character": "Pick a saved fictional adult, or save a new one with a typed age.",
                         "still": "Pick a still you kept.", "wardrobe": "Pick clothes.", "seconds": "Choose 2 or 5 seconds."}
                raise RecipeError(words.get(key, "This stage needs a choice."), sid)


# --------------------------------------------------------------------------- hashing and keys
def canonical_json(graph):
    """API JSON after finalize(): keys sorted, no _meta, no layout."""
    import comfy_client as cc
    return json.dumps(cc.finalize(graph), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(graph):
    return hashlib.sha256(canonical_json(graph).encode("utf-8")).hexdigest()


def params_hash(kind, params):
    """A job with no ComfyUI graph (export_godot) is hashed by its kind and params, keys sorted."""
    blob = json.dumps({"kind": kind, "params": params}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def graph_loras(graph):
    """(file, model strength, clip strength) for every LoRA loader in the graph. Model-only loaders have no
    clip input, so their clip strength is the literal "model_only"."""
    out = []
    for nid in sorted(graph, key=lambda k: (len(str(k)), str(k))):
        node = graph[nid]
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        if node.get("class_type") == "LoraLoaderModelOnly":
            out.append([inputs.get("lora_name"), inputs.get("strength_model"), "model_only"])
        elif node.get("class_type") == "LoraLoader":
            out.append([inputs.get("lora_name"), inputs.get("strength_model"), inputs.get("strength_clip")])
    return out


CACHE_FIELDS = ("template", "seed", "loras", "garment_state", "sfw_mode", "camera", "source_sha256")


def cache_key(fields):
    """sha256 over the canonical inputs. Any missing field (None) means there is no key: a cache miss."""
    if not isinstance(fields, dict):
        return None
    for name in CACHE_FIELDS:
        if fields.get(name) is None:
            return None
    for row in fields["loras"]:
        if not isinstance(row, (list, tuple)) or len(row) != 3 or any(part is None for part in row):
            return None
    if not isinstance(fields["sfw_mode"], bool):
        return None
    blob = json.dumps({name: fields[name] for name in CACHE_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def model_family(item):
    prov = (item or {}).get("provenance") or {}
    text = " ".join(str(prov.get(k) or "") for k in ("model", "unet", "workflow")).lower() + " " + str(
        (item or {}).get("model") or "").lower()
    for token, fam in (("chroma", "chroma"), ("qwen", "qwen_edit"), ("wan", "wan14b"), ("z_image", "zimage"),
                       ("z-image", "zimage"), ("zimage", "zimage"), ("flux", "flux"), ("noob", "sdxl")):
        if token in text:
            return fam
    return "unknown"


def sidecar_for(item, path):
    """The pixel handoff between model families: a decoded picture plus this sidecar, never a latent."""
    prov = (item or {}).get("provenance") or {}
    return {
        "item": item.get("id"),
        "width": item.get("w"), "height": item.get("h"),
        "seed": item.get("seed") if item.get("seed") is not None else prov.get("seed"),
        "model_family": model_family(item),
        "workflow_id": prov.get("workflow") or "",
        "sha256": file_sha256(path),
    }


def apply_quality(graph, quality):
    """Quality may set steps only on a single-sampler template. A template with two KSamplerAdvanced nodes
    (Wan's shared high/low split) is refused, never edited."""
    quality = quality or {}
    if not quality:
        return graph
    if "steps" in quality:
        advanced = [n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "KSamplerAdvanced"]
        if len(advanced) >= 2:
            raise RecipeError("This template shares its steps between two samplers. Quality does not change them.",
                              "quality")
        import comfy_client as cc
        cc.apply_advanced(graph, {"steps": quality["steps"]})
    return graph


def assert_pixel_handoff(graph, start_name):
    """The film reads the still as pixels: START IMAGE is a LoadImage of that file, and nothing else in the
    graph comes from another model family's latent."""
    loads = [n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "LoadImage"]
    if not any((n.get("inputs") or {}).get("image") == start_name for n in loads):
        raise RecipeError("The film must start from the still's picture.", "subject")
    for node in graph.values():
        if isinstance(node, dict) and node.get("class_type") in ("LoadLatent", "LatentFromBatch", "SaveLatent"):
            raise RecipeError("A recipe never wires a latent between model families.", "quality")


# --------------------------------------------------------------------------- compile
class Context:
    """What the compiler may look at: the request's area and sfw_mode, characters and kept items."""

    def __init__(self, area, sfw_mode, get_character, get_item, item_path):
        self.area = area
        self.sfw_mode = sfw_mode
        self.get_character = get_character
        self.get_item = get_item
        self.item_path = item_path


def _subject_character(ctx, cid):
    try:
        character = ctx.get_character(cid)
    except Exception:
        character = None
    if not isinstance(character, dict):
        raise RecipeError("That saved character no longer exists.", "subject")
    if (character.get("real_person") is True or character.get("player_only") or character.get("player")
            or character.get("identity") == "player_me"):
        raise RecipeError("Me is the player, Andrew. Recipes make fictional adults only.", "subject")
    ok, _age, msg = safety.require_stated_age(character)
    if not ok:
        raise RecipeError(msg, "subject")
    return character


def _with_area(area, fn):
    import pipelines
    old = pipelines.area()
    pipelines.set_area(area)
    try:
        return fn()
    finally:
        pipelines.set_area(old)


def _gate_error(exc, stage="subject"):
    return RecipeError(str(exc), stage)


def compile_recipe(doc, ctx, rng=None):
    """Recipe -> {kind, params, graph, canonical_hash, cache_key, sidecar, recipe}. Nothing is submitted here."""
    doc = normalize(doc)
    _require(doc)
    if doc["seed"] is None:
        doc["seed"] = (rng or random.SystemRandom()).randint(1, 2**31 - 1)  # drawn once, written back
    rid = doc["recipe"]
    return {"portrait_still": _compile_still, "one_actor_film": _compile_film,
            "send_to_island": _compile_island}[rid](doc, ctx)


def _compile_still(doc, ctx):
    import pipelines
    import stills
    character = _subject_character(ctx, _value(doc, "subject", "character"))
    wardrobe = _value(doc, "look", "wardrobe")
    if not CM.wardrobe_allowed(wardrobe, ctx.sfw_mode):
        raise RecipeError("That wardrobe needs full 21+ mode. SFW mode is on." if wardrobe == catalog.WORKSHOP_NUDE
                          else "Pick a wardrobe this page offers.", "look")
    parts = [str(_value(doc, "look", "look") or "")]
    pose = _value(doc, "pose", "pose")
    if pose:
        parts.append(_find(POSES, pose, "pose", ctx.sfw_mode)["phrase"])
    scene = _value(doc, "scene", "scene")
    if scene:
        parts.append(_find(SCENES, scene, "scene", ctx.sfw_mode)["phrase"])
    camera = None
    if doc["stages"]["camera"]["on"]:
        camera = _find(CAMERAS, _value(doc, "camera", "camera") or _default(CAMERAS)["id"], "camera", ctx.sfw_mode)
        parts.append(camera["phrase"])
    look = ", ".join(part for part in parts if part)
    if len(look) > LOOK_LIMIT:
        raise RecipeError(f"The look words and stage words are too long together ({len(look)} of {LOOK_LIMIT} letters).",
                          "look")
    params = {"character": character["id"], "wardrobe": wardrobe, "seed": doc["seed"]}
    if look:
        params["look"] = look
    body = _value(doc, "look", "body")
    if body:
        params["body"] = body
    try:
        stills.gate("workshop_still", params, ctx.area, ctx.get_character, ctx.get_item)
        built = _with_area(ctx.area, lambda: stills.build_still_graph(character, params, ctx.area))
    except (stills.StillError, pipelines.UserError) as exc:
        raise _gate_error(exc, "look") from exc
    import comfy_client as cc
    graph = cc.finalize(built["wf"])
    fields = {"template": built["template"], "seed": built["seed"], "loras": graph_loras(graph),
              "garment_state": wardrobe, "sfw_mode": ctx.sfw_mode, "camera": camera["id"] if camera else "none",
              "source_sha256": "text_only"}
    return {"recipe": doc, "kind": "workshop_still", "params": params, "graph": graph,
            "canonical_hash": canonical_hash(graph), "cache_key": cache_key(fields), "cache_fields": fields,
            "sidecar": None, "phase": RECIPES["portrait_still"]["phase"]}


def _compile_film(doc, ctx):
    import films
    import pipelines
    import stills
    still_id = _value(doc, "subject", "still")
    try:
        item = ctx.get_item(still_id)
    except Exception:
        item = None
    if not isinstance(item, dict) or item.get("type") != "image":
        raise RecipeError("Pick a still you kept. A still that is still rendering cannot be used yet.", "subject")
    path = ctx.item_path(item)
    sidecar = sidecar_for(item, path)
    given = doc["stages"]["subject"]["values"].get("sidecar_sha256")
    if given and given != sidecar["sha256"]:
        raise RecipeError("That still's picture changed since it was picked. Pick it again.", "subject")
    parts = []
    if doc["stages"]["pose"]["on"] and _value(doc, "pose", "motion"):
        motions = catalogue(ctx.sfw_mode)["motions"]
        parts.append(str(_find(motions, _value(doc, "pose", "motion"), "pose", ctx.sfw_mode).get("p") or ""))
    camera = None
    if doc["stages"]["camera"]["on"]:
        camera = _find(CAMERA_MOVES, _value(doc, "camera", "camera") or _default(CAMERA_MOVES)["id"], "camera",
                       ctx.sfw_mode)
        parts.append(camera["phrase"])
    text = ", ".join(part for part in parts if part)
    params = {"image": item["id"], "seconds": _value(doc, "output", "seconds"), "seed": doc["seed"]}
    if text:
        params["text"] = text
    start_name = f"es_{item['id']}.png"
    try:
        _it, _ages, seconds, phrase = films.gate(params, ctx.area, ctx.get_character, ctx.get_item)
        built = _with_area(ctx.area, lambda: films.build_film_graph(phrase, seconds, ctx.area, path, start_name,
                                                                     doc["seed"]))
    except (films.FilmError, stills.StillError, pipelines.UserError) as exc:
        raise _gate_error(exc, "output" if "second" in str(exc) else "subject") from exc
    import comfy_client as cc
    graph = cc.finalize(built["wf"])
    assert_pixel_handoff(graph, start_name)
    fields = {"template": built["template"], "seed": built["seed"], "loras": graph_loras(graph),
              "garment_state": "as_still", "sfw_mode": ctx.sfw_mode, "camera": camera["id"] if camera else "none",
              "source_sha256": sidecar["sha256"]}
    return {"recipe": doc, "kind": "film", "params": params, "graph": graph,
            "canonical_hash": canonical_hash(graph), "cache_key": cache_key(fields), "cache_fields": fields,
            "sidecar": sidecar, "phase": RECIPES["one_actor_film"]["phase"]}


def _compile_island(doc, ctx):
    import pipelines
    import pipelines_v3
    character = _subject_character(ctx, _value(doc, "subject", "character"))
    try:
        pipelines_v3.export_age(character)
    except pipelines.UserError as exc:
        raise _gate_error(exc) from exc
    params = {"character": character["id"]}
    fields = {"template": "export_godot", "seed": doc["seed"], "loras": [], "garment_state": "kept_pictures",
              "sfw_mode": ctx.sfw_mode, "camera": "none", "source_sha256": "kept_pictures"}
    return {"recipe": doc, "kind": "export_godot", "params": params, "graph": None,
            "canonical_hash": params_hash("export_godot", params), "cache_key": None, "cache_fields": fields,
            "sidecar": None, "phase": RECIPES["send_to_island"]["phase"],
            "note": "A pack has no ComfyUI graph and is always made fresh from the pictures you kept."}


# --------------------------------------------------------------------------- export / import
def strip_secrets(value):
    """Remove every string containing op:// at any depth (dict keys too). Returns a new value."""
    if isinstance(value, dict):
        return {k: strip_secrets(v) for k, v in value.items()
                if not (isinstance(k, str) and "op://" in k) and not (isinstance(v, str) and "op://" in v)}
    if isinstance(value, list):
        return [strip_secrets(v) for v in value if not (isinstance(v, str) and "op://" in v)]
    if isinstance(value, tuple):
        return [strip_secrets(v) for v in value if not (isinstance(v, str) and "op://" in v)]
    return value


def export_recipe(doc, compiled=None):
    """The .esrecipe.json text. It never carries an age or a secret reference; it points at a saved
    character or a kept still by id, and carries the seed so the graph can be rebuilt exactly."""
    out = copy.deepcopy(doc if isinstance(doc, dict) else {})
    out["format"] = FORMAT
    out["notice"] = PRIVATE_NOTICE
    if compiled:
        out["compiled"] = {"kind": compiled.get("kind"), "canonical_hash": compiled.get("canonical_hash"),
                           "cache_key": compiled.get("cache_key"), "seed": (compiled.get("recipe") or {}).get("seed")}
        out["seed"] = (compiled.get("recipe") or {}).get("seed", out.get("seed"))
    for sid in list((out.get("stages") or {}).keys()):
        values = (out["stages"][sid] or {}).get("values") or {}
        for key in list(values):
            if key in safety.STATED_AGE_FIELDS:
                values.pop(key)
    out = strip_secrets(out)
    return json.dumps(out, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def _png_text_chunks(blob):
    import struct
    import zlib
    out = {}
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return out
    pos = 8
    while pos + 8 <= len(blob):
        length, ctype = struct.unpack(">I4s", blob[pos:pos + 8])
        data = blob[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"tEXt" and b"\x00" in data:
            key, val = data.split(b"\x00", 1)
            out[key.decode("latin-1")] = val.decode("latin-1", "replace")
        elif ctype == b"iTXt" and b"\x00" in data:
            key, rest = data.split(b"\x00", 1)
            flag = rest[:1]
            rest = rest[2:]
            _lang, rest = rest.split(b"\x00", 1)
            _tkey, text = rest.split(b"\x00", 1)
            if flag == b"\x01":
                try:
                    text = zlib.decompress(text)
                except zlib.error:
                    continue
            out[key.decode("latin-1")] = text.decode("utf-8", "replace")
        if ctype == b"IEND":
            break
    return out


def _graph_report(graph, fmt, known_nodes=None):
    """One-way: list node types, models and refusals. Never decompiled into stages."""
    types, models = set(), set()
    nodes = graph.get("nodes") if fmt == "ui" else list(graph.values())
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        ctype = node.get("type") if fmt == "ui" else node.get("class_type")
        if ctype:
            types.add(str(ctype))
        values = node.get("widgets_values") if fmt == "ui" else list((node.get("inputs") or {}).values())
        for v in values or []:
            if isinstance(v, str) and v.lower().endswith((".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".bin")):
                models.add(v)
    refused = [t for t in sorted(types) if safety.NODE_DENY_RE.search(t)]
    ok, why = (True, "")
    if fmt == "api":
        ok, why = safety.check_workflow(graph)
    missing = sorted(t for t in types if known_nodes is not None and t not in known_nodes)
    return {"node_types": sorted(types), "models": sorted(models), "refused_nodes": refused,
            "missing_node_types": missing if known_nodes is not None else None,
            "check": "ok" if ok and not refused else (why or "This graph has nodes Easy Studio refuses."),
            "can_run_as_raw": fmt == "api" and ok and not refused}


def import_recipe(blob, known_nodes=None):
    """Our own .esrecipe.json is read back as a recipe (to be recompiled and compared by hash).
    Anything else (ComfyUI UI JSON, API JSON, PNG metadata) is one-way: a report only. No decompiling,
    no custom-node installs."""
    if isinstance(blob, str):
        blob = blob.encode("utf-8")
    meta = _png_text_chunks(blob)
    if meta:
        for key, fmt in (("prompt", "api"), ("workflow", "ui")):
            if key in meta:
                try:
                    graph = json.loads(meta[key])
                except ValueError:
                    continue
                return {"kind": "third_party", "format": "png_" + fmt, "decompiled": False,
                        "report": _graph_report(graph, fmt, known_nodes)}
        raise RecipeError("That picture has no ComfyUI graph inside.")
    try:
        data = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise RecipeError("That file is not a recipe or a ComfyUI graph.")
    if isinstance(data, dict) and data.get("format") == FORMAT:
        data = strip_secrets(data)
        expected = (data.get("compiled") or {}).get("canonical_hash")
        return {"kind": "own", "recipe": normalize(data), "expected_hash": expected}
    if isinstance(data, dict) and isinstance(data.get("nodes"), list):
        return {"kind": "third_party", "format": "ui", "decompiled": False,
                "report": _graph_report(data, "ui", known_nodes)}
    if isinstance(data, dict) and data and all(isinstance(v, dict) and "class_type" in v for v in data.values()):
        return {"kind": "third_party", "format": "api", "decompiled": False,
                "report": _graph_report(data, "api", known_nodes)}
    raise RecipeError("That file is not a recipe or a ComfyUI graph.")


def store_import(blob, root):
    """Third-party files are kept as bytes, content-addressed, in outputs/recipes/imports."""
    if isinstance(blob, str):
        blob = blob.encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    folder = os.path.join(root, "recipes", "imports")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, digest + (".png" if blob.startswith(b"\x89PNG") else ".json"))
    if not os.path.exists(path):
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(blob)
        os.replace(tmp, path)
    return digest


# --------------------------------------------------------------------------- presets
def save_preset(root, recipe_id, stage_id, values, name):
    """A stage preset: one stage's values, saved under a name. Ages and secrets are never saved."""
    if recipe_id not in RECIPES or stage_id not in STAGES:
        raise RecipeError("Pick a recipe and a stage.")
    if not isinstance(values, dict) or set(values) - STAGE_KEYS[stage_id]:
        raise RecipeError("This stage does not take those values.", stage_id)
    name = str(name or "").strip()[:60]
    if not name:
        raise RecipeError("Give the preset a name.", stage_id)
    ok, msg = safety.check_prompt(name)
    if not ok:
        raise RecipeError(msg, stage_id)
    clean = strip_secrets({k: v for k, v in values.items() if k not in safety.STATED_AGE_FIELDS})
    path = os.path.join(root, "recipes", "presets.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault(recipe_id, {}).setdefault(stage_id, {})[name] = clean
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return data


def load_presets(root):
    try:
        return json.load(open(os.path.join(root, "recipes", "presets.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
