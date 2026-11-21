# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Web API for the Graphic Workflow Editor (Make -> Recipes) and the Play door's island check.

Recipes compile here; the page then submits the compiled kind and params to the normal /api/jobs queue,
so every gate in server.create_job still applies. register(server_module) adds the routes.
"""
import hashlib
import importlib.util
import os

from fastapi import Body, File, Request, UploadFile
from fastapi.responses import JSONResponse

import content_mode as CM
import recipes as R

S = None  # the server module


def _sfw(request):
    return CM.effective_sfw_mode(S.SETTINGS, S.adult_unlocked(request))


def _bad(exc, code=400):
    return JSONResponse({"error": str(exc), "stage": getattr(exc, "stage", "")}, status_code=code)


def _ctx(request, area):
    view = S.AreaView(S.LIB, area)

    def get_item(iid):
        it = view.get(iid)
        S.LIB._not_flagged(it)
        return it

    return R.Context(area, CM.sfw_mode_for_area(area), S.CHARS.get, get_item, S.LIB.path)


def _cached(area, key):
    if not key:
        return None
    view = S.AreaView(S.LIB, area)
    for it in view.list_usable(limit=5000):
        if it.get("recipe_cache_key") != key:
            continue
        try:
            S.LIB._not_flagged(it)
        except PermissionError:
            continue
        return S.item_json(it)
    return None


def _importer():
    path = os.path.join(S.ROOT, "game", "tools", "import_easy_studio.py")
    if not os.path.isfile(path):
        return None, path
    spec = importlib.util.spec_from_file_location("es_island_importer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def register(server):
    global S
    S = server
    app = server.app
    err = server.err

    @app.get("/api/recipes")
    def recipes_catalogue(request: Request):
        sfw = _sfw(request)
        out = R.catalogue(sfw)
        out["presets"] = R.load_presets(S.OUT)
        out["hardware"] = S.HARDWARE.summary()
        out["area"] = CM.area_for(sfw)
        return out

    @app.post("/api/recipes/compile")
    def recipes_compile(request: Request, body: dict = Body(...)):
        area = S.want_area(request, body.get("area"))
        try:
            compiled = R.compile_recipe(body.get("recipe"), _ctx(request, area))
        except R.RecipeError as exc:
            return _bad(exc)
        compiled["cached"] = _cached(area, compiled.get("cache_key"))
        fam = None
        if compiled.get("graph"):
            import hardware_map
            fam = hardware_map.family_of_graph(compiled["graph"])
        proc = S.HARDWARE.process_for(fam) if fam else None
        compiled["process"] = {"port": proc["port"], "gpu": proc["gpu"], "label": proc.get("label")} if proc else None
        compiled.pop("cache_fields", None)
        return compiled

    @app.post("/api/recipes/export")
    def recipes_export(request: Request, body: dict = Body(...)):
        area = S.want_area(request, body.get("area"))
        try:
            compiled = R.compile_recipe(body.get("recipe"), _ctx(request, area))
        except R.RecipeError as exc:
            return _bad(exc)
        text = R.export_recipe(compiled["recipe"], compiled)
        name = "".join(ch if ch.isalnum() else "_" for ch in compiled["recipe"]["name"].lower()).strip("_") or "recipe"
        return {"filename": name[:40] + ".esrecipe.json", "text": text, "canonical_hash": compiled["canonical_hash"]}

    @app.post("/api/recipes/import")
    async def recipes_import(request: Request, file: UploadFile = File(...)):
        blob = await file.read()
        if len(blob) > 20 * 1024 * 1024:
            err("That file is too big for a recipe.")
        try:
            info = S.COMFY.object_info() if S.COMFY else None
            known = set(info) if isinstance(info, dict) else None
        except Exception:
            known = None
        try:
            found = R.import_recipe(blob, known)
        except R.RecipeError as exc:
            return _bad(exc)
        if found["kind"] == "third_party":
            found["stored"] = R.store_import(blob, S.OUT)
            found["note"] = ("This graph was not made by Easy Studio, so it is kept as it is and never turned into "
                             "stages. Missing nodes are not installed. A graph in API format can run as a raw graph "
                             "from Classic tools → Advanced.")
            return found
        area = S.want_area(request, request.query_params.get("area"))
        try:
            compiled = R.compile_recipe(found["recipe"], _ctx(request, area))
        except R.RecipeError as exc:
            return _bad(exc)
        compiled.pop("cache_fields", None)
        return {"kind": "own", "recipe": compiled["recipe"], "canonical_hash": compiled["canonical_hash"],
                "expected_hash": found["expected_hash"],
                "matches": bool(found["expected_hash"]) and found["expected_hash"] == compiled["canonical_hash"],
                "compiled": compiled}

    @app.post("/api/recipes/preset")
    def recipes_preset(body: dict = Body(...)):
        try:
            return R.save_preset(S.OUT, body.get("recipe"), body.get("stage"), body.get("values") or {}, body.get("name"))
        except R.RecipeError as exc:
            return _bad(exc)

    @app.get("/api/hardware")
    def hardware():
        return S.HARDWARE.summary()

    @app.get("/api/island/status")
    def island_status():
        module, path = _importer()
        game = os.path.join(S.ROOT, "game")
        return {"game_here": module is not None, "importer": os.path.relpath(path, S.ROOT),
                "project": os.path.isfile(os.path.join(game, "project.godot")),
                "puzzle": os.path.isfile(os.path.join(game, "data", "puzzles", "beach_door.json"))}

    @app.post("/api/island/dry-run")
    def island_dry_run(request: Request, body: dict = Body(...)):
        """Check a pack against the island on this computer. Nothing is copied: the importer runs in dry-run
        mode, and project.godot is hashed before and after to prove it."""
        module, _path = _importer()
        if module is None:
            err("The island folder (game/) is not on this computer.")
        area = S.want_area(request, body.get("area"))
        try:
            item = S.AreaView(S.LIB, area).get(str(body.get("item") or ""))
        except (KeyError, PermissionError) as exc:
            err(str(exc), 404)
        if item.get("type") != "zip" or not str(item.get("kind") or "").startswith("export"):
            err("Pick an island pack made by Send to the island.")
        slug = "".join(ch for ch in str(body.get("character") or "").lower() if ch.isalnum() or ch == "_")[:32]
        if not slug or not slug[0].isalpha():
            slug = "guest"
        game = os.path.join(S.ROOT, "game")
        project = os.path.join(game, "project.godot")
        before = _sha(project)
        try:
            summary = module.import_export(S.LIB.path(item), slug, root=game, dry_run=True)
        except module.GameImportError as exc:
            err(str(exc))
        after = _sha(project)
        return {"ok": True, "summary": summary, "character": slug, "project_godot_unchanged": before == after,
                "project_godot_sha256": after,
                "message": "The island would accept this pack. Nothing was copied, and project.godot is unchanged."
                if before == after else "project.godot changed during the check. Stop and look."}
