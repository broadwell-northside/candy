"""Always-on rails that this session touched (PRD §8). Mock engine only.

- Upload ancestry: the clothing-removal refusal walks `parent` to the root, in edits and in raw graphs.
- Checker-off fails closed: a job kind in neither list is refused while the appearance checker is off.
- NODE_DENY_RE is not weakened.
"""
import io
import os
import tempfile

from PIL import Image, ImageDraw

import age_guard
import pipelines
import pipelines_v3  # noqa: F401  (registers the v3 job kinds)
import safety
from library import AreaView, Library

NODE_DENY_PATTERN = (r"(face|swap|reactor|instantid|pulid|ipadapter|ip_adapter|faceid|roop|insightface|photomaker|"
                     r"ecomid|infiniteyou|lora_?train|trainlora)")


class _Stop(Exception):
    pass


class _RawCtx:
    def __init__(self, lib):
        self.lib = AreaView(lib, "adult")
        self.chars = None
        self.tmp = tempfile.mkdtemp(prefix="rails_raw_")
        self.job = {"id": "rails", "params": {}}
        self.ran = False

    def upload_item(self, item):
        return f"es_{item['id']}.png"

    def run(self, wf, label):
        self.ran = True
        raise _Stop()


def _png(root, name):
    path = os.path.join(root, name)
    Image.new("RGB", (16, 16), (200, 180, 160)).save(path)
    return path


def _lineage():
    root = tempfile.mkdtemp(prefix="rails_lib_")
    lib = Library(root)
    upload = lib.add(_png(root, "oc.png"), "upload", role="my_character", stated_age=34, age_check="ok")
    child = lib.add(_png(root, "child.png"), "edit:outfit", role="made", parent=upload["id"], stated_age=34, age_check="ok")
    grandchild = lib.add(_png(root, "grand.png"), "edit:outfit", role="made", parent=child["id"], stated_age=34,
                         age_check="ok")
    clean = lib.add(_png(root, "made.png"), "create", role="made", stated_age=30, age_check="ok")
    clean_child = lib.add(_png(root, "made2.png"), "edit:outfit", role="made", parent=clean["id"], stated_age=30,
                          age_check="ok")
    return lib, upload, child, grandchild, clean, clean_child


def _refusal(fn):
    try:
        fn()
    except pipelines.UserError as exc:
        return str(exc)
    except _Stop:
        return "RAN"
    return ""


def unit(check):
    import violence_rail_tests
    violence_rail_tests.unit(check)
    print("\n[Rails] Upload ancestry, checker-off, identity")
    lib, upload, child, grandchild, clean, clean_child = _lineage()
    get = lib.get
    check("an upload is its own upload ancestor", pipelines.has_upload_ancestor(upload, get))
    check("one hop: an edit of an upload has an upload ancestor", pipelines.has_upload_ancestor(child, get))
    check("two hops: an edit of an edit of an upload has an upload ancestor", pipelines.has_upload_ancestor(grandchild, get))
    check("a picture made from text has no upload ancestor", not pipelines.has_upload_ancestor(clean_child, get))
    check("a parent that cannot be found counts as an upload",
          pipelines.has_upload_ancestor({"role": "made", "parent": "gone000000"}, get))
    check("a lineage loop counts as an upload", pipelines.has_upload_ancestor({"id": "a", "role": "made", "parent": "a"},
                                                                              lambda _i: {"id": "a", "role": "made", "parent": "a"}))
    check("no lookup means the walk fails closed", pipelines.has_upload_ancestor({"role": "made", "parent": "x"}, None))
    msg = _refusal(lambda: pipelines._refuse_uploaded_undress(grandchild, "remove her clothes", get_item=get))
    check("two-hop clothing removal is refused", "won't remove" in msg, msg)
    check("two-hop dressing is allowed", _refusal(lambda: pipelines._refuse_uploaded_undress(
        grandchild, "a blue linen dress", get_item=get)) == "")
    check("a picture made from text is unchanged by the walk", _refusal(lambda: pipelines._refuse_uploaded_undress(
        clean_child, "remove her clothes", get_item=get)) == "")
    ctx = _RawCtx(lib)
    check("the walk reads the whole library from a job context", pipelines._lineage_get(ctx) is not None)

    pipelines.set_area("adult")
    try:
        wf = {"1": {"class_type": "LoadImage", "inputs": {"image": f"es_{grandchild['id']}.png"}},
              "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fictional adult woman, 34, remove her clothes"}}}
        msg = _refusal(lambda: pipelines.job_raw(ctx, {"workflow": wf}))
        check("raw: a graph that loads a grandchild of an upload cannot remove clothes", "won't remove" in msg and not ctx.ran,
              msg)
        mask_wf = {"1": {"class_type": "LoadImage", "inputs": {"image": f"es_{clean['id']}.png"}},
                   "3": {"class_type": "LoadImageMask", "inputs": {"image": f"es_{child['id']}.png"}},
                   "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fictional adult woman, 30, undressed"}}}
        msg = _refusal(lambda: pipelines.job_raw(_RawCtx(lib), {"workflow": mask_wf}))
        check("raw: the walk covers every loaded image, masks too", "won't remove" in msg, msg)
        clean_wf = {"1": {"class_type": "LoadImage", "inputs": {"image": f"es_{clean_child['id']}.png"}},
                    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fictional adult woman, 30, undressed"}}}
        msg = _refusal(lambda: pipelines.job_raw(_RawCtx(lib), {"workflow": clean_wf}))
        check("raw: a lineage made from text is not refused by the walk", msg == "RAN", msg)
    finally:
        pipelines.set_area("default")

    kinds = set(pipelines.JOBS)
    required, free = set(age_guard.CHECKER_REQUIRED_KINDS), set(age_guard.CHECKER_FREE_KINDS)
    check("every job kind is in exactly one checker list", kinds == required | free and not (required & free),
          {"unlisted": sorted(kinds - required - free), "both": sorted(required & free), "stale": sorted((required | free) - kinds)})
    check("a new, unlisted kind is refused while the checker is off", age_guard.checker_blocks("made_up_kind", False))
    pipelines.JOBS["made_up_kind"] = lambda ctx, p: None
    try:
        check("registering a kind does not let it run with the checker off", age_guard.checker_blocks("made_up_kind", False))
    finally:
        pipelines.JOBS.pop("made_up_kind", None)
    check("required kinds are refused with the checker off", all(age_guard.checker_blocks(k, False) for k in required))
    check("nothing is refused for the checker while it is on", not any(age_guard.checker_blocks(k, True) for k in kinds | {"x"}))
    check("the recipe kinds are all checker-required",
          {"workshop_still", "film", "export_godot"} <= required)
    check("the benchmark and training kinds moved into the required list",
          {"lora_benchmark", "workshop_train", "workshop_me_train"} <= required)
    check("NODE_DENY_RE is unchanged", safety.NODE_DENY_RE.pattern == NODE_DENY_PATTERN, safety.NODE_DENY_RE.pattern)
    check("a face-swap node is still refused", not safety.check_workflow({"1": {"class_type": "ReActorFaceSwap", "inputs": {}}})[0])


def e2e(a, mock_url):
    import violence_rail_tests
    violence_rail_tests.e2e(a, mock_url)
    print("\n[Rails] Two-hop and raw ancestry through the server")
    check = a.check
    b = io.BytesIO()
    art = Image.new("RGB", (64, 96), (190, 150, 120))
    ImageDraw.Draw(art).ellipse((16, 10, 48, 50), fill=(220, 180, 150))  # not flat, so the fake checker sees a face
    art.save(b, "PNG")
    up = a.post("/api/upload", files={"file": ("my_oc.png", b.getvalue(), "image/png")},
                data={"role": "my_character", "confirm": "yes", "age": "34"})
    check("upload of fictional character art works", up.status_code == 200, up.text[:200])
    if up.status_code != 200:
        return
    first = a.job("edit", {"image": up.json()["id"], "op": "outfit", "text": "a blue linen dress"})
    check("one edit of the upload is made", first["status"] == "done" and first["results"], first.get("error"))
    if not first.get("results"):
        return
    second = a.job("edit", {"image": first["results"][0]["id"], "op": "outfit", "text": "a straw sun hat"})
    check("a second edit (two hops from the upload) is made", second["status"] == "done" and second["results"],
          second.get("error"))
    if not second.get("results"):
        return
    grand = second["results"][0]
    check("the two-hop picture is relabelled as made", grand.get("role") == "made" and grand.get("parent") == first["results"][0]["id"])
    a.post("/api/adult/unlock", json={"confirm_age": True, "confirm_rules": True})
    undress = a.job("edit", {"image": grand["id"], "op": "outfit", "text": "remove her clothes"}, area="adult")
    check("two-hop clothing removal is refused by the server", undress["status"] in ("error", "refused")
          and "won't remove" in (undress.get("error") or ""), undress.get("error"))
    wf = {"1": {"class_type": "LoadImage", "inputs": {"image": f"es_{grand['id']}.png"}},
          "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fictional adult woman, 34, remove her clothes"}},
          "3": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "x"}}}
    raw = a.job("raw", {"workflow": wf}, area="adult")
    check("a raw load of the two-hop picture cannot remove clothes", raw["status"] in ("error", "refused")
          and "won't remove" in (raw.get("error") or ""), raw.get("error"))
