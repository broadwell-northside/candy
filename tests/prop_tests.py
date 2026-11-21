"""Guided 3D prop. Mock engine only: no GPU, no weight download, no RunPod."""
import json
import os
import tempfile

from PIL import Image, ImageDraw

import comfy_client as cc
import model_cards
import props
import stills

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _still(age=32, **extra):
    item = {
        "id": "still1", "type": "image", "role": "made", "kind": "create",
        "dna": {"age": age, "stated_age": age},
        "age_check": "ok", "appearance_check": {"status": "ok", "held": False},
    }
    item.update(extra)
    return item


def _lookup(item):
    def get_item(iid):
        return item if iid == item.get("id") else None
    return get_item


def _raises(fn, needle):
    try:
        fn()
    except props.PropError as exc:
        return needle in str(exc), str(exc)
    except Exception as exc:
        return False, repr(exc)
    return False, "no error"


def unit(check):
    print("\n[35] 3D prop license cards and gates")
    cards = {row.get("id"): row for row in model_cards.load().get("cards") or []}
    trellis, encoder = cards.get("trellis2") or {}, cards.get("dinov3") or {}
    check("TRELLIS.2 card is MIT on 2026-11-05",
          trellis.get("license_name") == "MIT" and trellis.get("private_use") == "yes"
          and trellis.get("license_checked") == "2026-11-05"
          and trellis.get("license_url") == "https://huggingface.co/microsoft/TRELLIS.2-4B")
    check("DINOv3 card is dinov3-license for a machine you do not distribute",
          encoder.get("license_name") == "dinov3-license" and encoder.get("private_use") == "yes"
          and encoder.get("license_checked") == "2026-11-05"
          and encoder.get("download") == "gated"
          and "do not distribute" in str(encoder.get("private_use_scope") or "")
          and encoder.get("license_url") == "https://ai.meta.com/resources/models-and-libraries/dinov3-license/")
    raw = open(os.path.join(ROOT, "app", "model_cards.json"), encoding="utf-8").read()
    check("the gated download is stored as a secret reference",
          '"token_ref": "op://Easy-Studio/DINOv3/token"' in raw)
    shown = json.dumps(props.public_licenses())
    check("a result license list does not print the secret reference", "op://" not in shown, shown)
    try:
        raise props.PropError("do not print op://Easy-Studio/DINOv3/token")
    except props.PropError as exc:
        leaked = str(exc)
    check("an error does not print the secret reference", "op://" not in leaked, leaked)
    wf = cc.load_workflow(props.WORKFLOW)
    names = stills.workflow_weights(wf)
    for name in names:
        ok, msg = stills.weight_allowed(name, "default")
        check(f"prop weight {name} has a private-use card", ok, msg)
    extra = json.loads(json.dumps(wf))
    extra["99"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "no_card_weight.safetensors"}}
    try:
        stills.require_licensed(extra, "default")
        blocked = False
        detail = "ran"
    except stills.StillError as exc:
        blocked = "no license card" in str(exc)
        detail = str(exc)
    check("a weight with no card does not run", blocked, detail)

    item = _still()
    source, found, age = props.gate({"source": "still", "image": item["id"]}, "default", lambda _cid: None, _lookup(item))
    check("a fictional adult still is accepted", source == "still" and age == 32 and found["id"] == item["id"])

    def boom(_iid):
        raise AssertionError("the picture was read")

    ok, detail = _raises(lambda: props.gate({"source": "still", "image": "x", "age": 18}, "default", lambda _c: None, boom), "under 21")
    check("age 18 never reaches a prop lookup", ok, detail)
    ok, detail = _raises(lambda: props.gate({"source": "still", "image": "x", "stated_age": ""}, "default", lambda _c: None, boom), "Missing stated age")
    check("a blank age never reaches a prop lookup", ok, detail)
    missing = _still()
    missing.pop("dna")
    ok, detail = _raises(lambda: props.gate({"source": "still", "image": missing["id"]}, "default", lambda _c: None, _lookup(missing)), "Missing stated age")
    check("a still with no age is refused", ok, detail)
    young = _still(20)
    ok, detail = _raises(lambda: props.gate({"source": "still", "image": young["id"]}, "default", lambda _c: None, _lookup(young)), "under 21")
    check("a still aged 20 is refused and not raised", ok, detail)
    upload = _still()
    upload["role"] = "my_character"
    upload["kind"] = "upload"
    ok, detail = _raises(lambda: props.gate({"source": "still", "image": upload["id"]}, "default", lambda _c: None, _lookup(upload)), "real person")
    check("an uploaded character photo is not a still", ok, detail)
    place = {"id": "place1", "type": "image", "role": "scenery", "kind": "upload", "place": True, "person": False, "face_check": "clear"}
    ok, detail = _raises(lambda: props.gate({"source": "still", "image": place["id"]}, "default", lambda _c: None, _lookup(place)), "place")
    check("a scenery photo is not used as a person", ok, detail)
    ok, detail = _raises(lambda: props.gate({"source": "scenery", "image": place["id"], "text": "face swap"}, "default", lambda _c: None, _lookup(place)), "face swap")
    check("a face swap never starts a prop", ok, detail)
    ok, detail = _raises(lambda: props.gate({"source": "scenery", "image": place["id"], "text": "remove her clothes"}, "default", lambda _c: None, _lookup(place)), "clothing-removal")
    check("a clothing-removal edit never starts a prop", ok, detail)
    ok, detail = _raises(lambda: props.gate({"source": "still", "image": item["id"], "engine": "gaussian"}, "default", lambda _c: None, _lookup(item)), "Gaussian splat")
    check("a Gaussian splat is not a prop engine", ok, detail)
    source, _found, age = props.gate({"source": "scenery", "image": place["id"]}, "default", lambda _c: None, _lookup(place))
    check("a confirmed place photo is accepted without a character age", source == "scenery" and age is None)

    path = os.path.join(tempfile.mkdtemp(prefix="es_prop_"), "place.png")
    im = Image.new("RGB", (40, 40), (10, 20, 30))
    draw = ImageDraw.Draw(im)
    for y in range(8, 24):
        for x in range(8, 24):
            draw.point((x, y), fill=(255, 0, 0) if (x + y) % 2 else (0, 255, 0))
    im.save(path)
    outside = im.getpixel((1, 1))
    inside = im.getpixel((12, 12))
    calls = {"n": 0}

    def checker(_path):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "ok", "faces": 1, "boxes": [[8, 8, 24, 24]]}
        return {"status": "unchecked", "faces": 0}

    meta = props.screen_scenery(path, checker)
    after = Image.open(path).convert("RGB")
    check("a found face is blurred and the place around it stays",
          meta.get("face_blurred") is True and meta.get("person") is False and calls["n"] == 2
          and after.getpixel((1, 1)) == outside and after.getpixel((12, 12)) != inside)
    ok, detail = _raises(lambda: props.screen_scenery(path, lambda _p: {"status": "ok", "faces": 1}), "could not be confirmed")
    check("a face with no confirmed blur is refused", ok, detail)
    clear = props.screen_scenery(path, lambda _p: {"status": "unchecked", "faces": 0, "held": True})
    check("a place photo with no face is accepted", clear.get("face_check") == "clear" and clear.get("face_blurred") is False)
    ok, detail = _raises(lambda: props.screen_scenery(path, lambda _p: {"status": "unavailable", "faces": 0}), "could not confirm")
    check("a photo is refused when the face check cannot run", ok, detail)
    def still_there(_path):
        return {"status": "ok", "faces": 1, "boxes": [[8, 8, 24, 24]]}

    ok, detail = _raises(lambda: props.screen_scenery(path, still_there), "could not be confirmed")
    check("a blur that still leaves a face is refused", ok, detail)


def _refused(a, mock_url, requests, params, needle):
    before_log = requests.get(mock_url + "/mock/log", timeout=30).json()
    before_jobs = len(a.get("/api/jobs").json())
    response = a.post("/api/jobs", json={"kind": "prop", "params": params})
    after_log = requests.get(mock_url + "/mock/log", timeout=30).json()
    text = response.text
    return (response.status_code == 400 and needle in text and after_log == before_log
            and len(a.get("/api/jobs").json()) == before_jobs, text)


def e2e(a, mock_url):
    import requests
    check = a.check
    print("\n[36] 3D prop through the mock engine")
    made = a.job("create", {"dna": {"age": 32, "gender": "woman", "style": "photo", "name": "Ada"}, "count": 1})
    still = (made.get("results") or [None])[0]
    check("a still of a fictional adult exists for the prop", made.get("status") == "done" and still and still.get("id"), made.get("error"))
    if not still:
        return
    refused, text = _refused(a, mock_url, requests, {"source": "still", "image": still["id"], "age": 18}, "under 21")
    check("an under-21 age never reaches the prop job", refused, text)
    refused, text = _refused(a, mock_url, requests, {"source": "still", "image": still["id"], "stated_age": ""}, "Missing stated age")
    check("a missing age never reaches the prop job", refused, text)
    refused, text = _refused(a, mock_url, requests, {"source": "still", "image": still["id"], "engine": "hunyuan"}, "only takes a still")
    check("the prop step does not take the clay-shape engine", refused, text)
    job = a.job("prop", {"source": "still", "image": still["id"]})
    result = (job.get("results") or [None])[0]
    blob = a.file(result) if result else b""
    served = a.get(result["url"]) if result else None
    check("a still becomes a glTF prop",
          job.get("status") == "done" and result and result.get("kind") == "model3d:prop"
          and result.get("stated_age") == 32 and blob[:4] == b"glTF"
          and served is not None and served.headers.get("content-type", "").startswith("model/gltf-binary")
          and (result.get("provenance") or {}).get("rigged") is False
          and (result.get("provenance") or {}).get("format") == "gltf"
          and (result.get("provenance") or {}).get("importer") == "godot",
          job.get("error") or result)
    wf = {}
    if job.get("id"):
        wf = a.get(f"/api/jobs/{job['id']}/workflow").json()["workflows"][-1]
    names = stills.workflow_weights(wf)
    dumped = json.dumps({"job": job, "workflow": wf})
    check("the prop uses the TRELLIS path and does not print the secret reference",
          "dino_v3_vit_l.safetensors" in names and "trellis_2_int8_convrot.safetensors" in names
          and "birefnet.safetensors" in names and not any("hunyuan" in name.lower() for name in names)
          and "op://" not in dumped, names)
    meadow = Image.new("RGB", (48, 48), (20, 90, 40))
    place = a.upload(meadow, "scenery", name="meadow.png")
    check("a place photo with no face is kept as scenery",
          place.status_code == 200 and place.json().get("role") == "scenery"
          and place.json().get("place") is True and place.json().get("person") is False
          and place.json().get("face_check") == "clear" and place.json().get("stated_age") is None,
          place.text[:300])
    if place.status_code != 200:
        return
    place_id = place.json()["id"]
    prop = a.job("prop", {"source": "scenery", "image": place_id})
    place_result = (prop.get("results") or [None])[0]
    check("a place photo becomes a prop and not a person",
          prop.get("status") == "done" and place_result and place_result.get("kind") == "model3d:prop"
          and place_result.get("stated_age") is None and not place_result.get("character")
          and (place_result.get("provenance") or {}).get("source") == "scenery"
          and (place_result.get("provenance") or {}).get("rigged") is False,
          prop.get("error"))
    face = Image.new("RGB", (48, 48), (20, 90, 40))
    ImageDraw.Draw(face).ellipse([8, 8, 36, 36], fill=(220, 180, 160))
    refused_photo = a.upload(face, "scenery", name="visitors.png")
    check("a place photo with a face is refused when the blur cannot be confirmed",
          refused_photo.status_code == 400 and "refused" in refused_photo.text.lower(), refused_photo.text[:300])
    gallery = a.get("/api/gallery?role=scenery").json()
    check("the refused photo is not saved", all(item.get("title") != "visitors" for item in gallery.get("items") or []))
    refused, text = _refused(a, mock_url, requests, {"source": "still", "image": place_id}, "place")
    check("a scenery photo cannot be the body of a prop", refused, text)
    before = requests.get(mock_url + "/mock/log", timeout=30).json()
    edited = a.job("edit", {"image": place_id, "op": "outfit", "text": "remove her clothes"})
    referenced = a.job("edit", {"image": still["id"], "op": "outfit", "item": "jeans_tee", "ref": place_id})
    after = requests.get(mock_url + "/mock/log", timeout=30).json()
    check("a scenery photo is not a clothing-removal edit",
          edited.get("status") in ("error", "refused") and "place" in (edited.get("error") or "").lower() and after == before,
          edited.get("error"))
    check("a scenery photo is not a character reference",
          referenced.get("status") in ("error", "refused")
          and "character reference" in (referenced.get("error") or "").lower()
          and after == before, referenced.get("error"))
    person = a.post("/api/characters", json={"name": "Ada", "gender": "woman", "style": "photo", "age": 32, "traits": {}}).json()
    kept = a.post("/api/jobs", json={"kind": "keep_face", "params": {"character": person.get("id"), "items": [place_id]}})
    check("keep this face does not take a scenery photo", kept.status_code == 400 and "photo" in kept.text.lower(), kept.text[:300])
    mine = a.upload(face, "my_character", name="my_drawing.png", age="34")
    if mine.status_code == 200:
        refused, text = _refused(a, mock_url, requests, {"source": "still", "image": mine.json()["id"]}, "real person")
        check("a real-person upload is not built into a body", refused, text)
    else:
        check("a real-person upload is not built into a body", False, mine.text[:300])
