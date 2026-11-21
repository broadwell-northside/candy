"""Character stills: model choice, license cards, and keeping a face. Mock ComfyUI only."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import catalog  # noqa: E402
import comfy_client as cc  # noqa: E402
import loras as L  # noqa: E402
import model_cards  # noqa: E402
import safety  # noqa: E402
import stills  # noqa: E402

ZIMAGE = "https://github.com/Tongyi-MAI/Z-Image"
CHROMA = "https://huggingface.co/lodestones/Chroma1-HD"


def _character(age=32, cid="abc123def0"):
    return {"id": cid, "name": "Mara", "gender": "woman", "style": "photo", "age": age, "stated_age": age,
            "traits": {}, "fictional": True, "real_person": False}


def _get(cid, character):
    def fetch(wanted):
        if wanted == character["id"]:
            return character
        raise KeyError(wanted)
    return fetch


def _graph(which, lora=""):
    wf, _spec = stills.load_graph(which)
    if lora:
        wf["99"] = {"class_type": "LoraLoaderModelOnly",
                    "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 0.8}}
    return wf


def unit(check):
    print("\n[31] Still license cards and model choice")
    cards = {row["id"]: row for row in model_cards.load()["cards"]}
    for cid, url, adult in (
            ("z_image", ZIMAGE, False),
            ("z_image_turbo", ZIMAGE, False),
            ("chroma1hd", CHROMA, True)):
        row = cards[cid]
        check(f"{cid} card is Apache-2.0 private use yes",
              row.get("license_name") == "Apache-2.0" and row.get("license") == "Apache-2.0"
              and row.get("private_use") == "yes" and row.get("license_url") == url
              and row.get("license_checked") == "2026-11-05" and bool(row.get("adult_only")) is adult
              and row.get("weights"), row)
    pack = catalog.workshop_choices()
    check("workshop wardrobe is clothed presets only",
          [c["id"] for c in pack["wardrobe"]] == ["jeans_tee", "sundress", "suit", "yoga"]
          and "nude" not in json.dumps(pack["wardrobe"]))
    check("the page states the realism tradeoff", pack["tradeoff"] == catalog.WORKSHOP_TRADEOFF
          and "fast model does not keep the face" in pack["tradeoff"])
    check("everyday still is Turbo", stills.choice(False, False, False) == "everyday")
    check("a saved face uses the foundation model", stills.choice(False, True, False) == "identity")
    try:
        stills.choice(True, True, False)
        check("explicit stills are refused while the 21+ switch is off", False)
    except stills.StillError as exc:
        check("explicit stills are refused while the 21+ switch is off", "21+" in str(exc))
    check("explicit stills use Chroma when the switch is on", stills.choice(True, True, True) == "explicit")
    turbo = _graph("everyday")
    stills.assert_graph(turbo, "everyday")
    stills.require_licensed(turbo, "default")
    check("Turbo workflow is licensed for everyday stills", True)
    try:
        stills.assert_graph(_graph("everyday", "easy_studio/id_abc123def0_identity.safetensors"), "everyday")
        check("Turbo does not take the face LoRA", False)
    except stills.StillError as exc:
        check("Turbo does not take the face LoRA", "identity" in str(exc).lower() or "does not load" in str(exc))
    lora = "easy_studio/id_abc123def0_identity.safetensors"
    face = _graph("identity", lora)
    stills.assert_graph(face, "identity", lora)
    try:
        stills.require_licensed(face, "default")
        check("a face LoRA with no card does not run", False)
    except stills.StillError as exc:
        check("a face LoRA with no card does not run", "private use yes" in str(exc))
    extra = {"id": lora, "private_use": "yes", "adult_only": False, "weights": [lora],
             "license_name": "Apache-2.0", "license_url": ZIMAGE, "license_checked": "2026-11-05"}
    stills.require_licensed(face, "default", [extra])
    check("a face LoRA with private use yes can run on the foundation model", "turbo" not in stills.unet_of(face))
    no = dict(extra, private_use="no")
    try:
        stills.require_licensed(face, "default", [no])
        check("private use no does not let the LoRA run", False)
    except stills.StillError:
        check("private use no does not let the LoRA run", True)
    mystery = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "mystery.safetensors"}}}
    try:
        stills.require_licensed(mystery, "default")
        check("a weight with no card does not run", False)
    except stills.StillError as exc:
        check("a weight with no card does not run", "mystery.safetensors" in str(exc) and "private use yes" in str(exc))
    chroma = _graph("explicit")
    try:
        stills.require_licensed(chroma, "default")
        check("Chroma does not run while the 21+ switch is off", False)
    except stills.StillError as exc:
        check("Chroma does not run while the 21+ switch is off", "21+" in str(exc))
    stills.require_licensed(chroma, "adult")
    check("Chroma is licensed inside the 21+ area", True)
    try:
        stills.assert_graph(_graph("identity", lora), "everyday")
        check("the foundation graph is not accepted as the fast model", False)
    except stills.StillError:
        check("the foundation graph is not accepted as the fast model", True)

    print("\n[32] Still gate: age, wording, photos")
    character = _character()
    fetch = _get(character["id"], character)
    stills.gate("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "look": "olive skin", "body": "athletic"},
                "default", fetch, lambda _i: None)
    check("a clothed still of a saved adult passes the gate", True)
    for age, needle in ((18, "age=18"), (20, "age=20"), ("21", "saved"), (21.5, "21.5"), (True, "True"), (None, "Missing")):
        try:
            stills.gate("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "age": age},
                        "default", fetch, lambda _i: None)
            check(f"age {age!r} does not reach a still", False)
        except stills.StillError as exc:
            text = str(exc)
            clamped = needle in ("age=18", "age=20") and "not raised" not in text.lower()
            check(f"age {age!r} does not reach a still", needle in text and "25" not in text and not clamped, text)
    try:
        stills.gate("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "age": 40},
                    "default", fetch, lambda _i: None)
        check("a different adult age is not written over the saved age", False)
    except stills.StillError as exc:
        check("a different adult age is not written over the saved age", "saved" in str(exc).lower(), str(exc))
    for look in ("a youthful-looking woman", "childlike face", "face swap from a photo", "remove her clothes from this photo"):
        try:
            stills.gate("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "look": look},
                        "default", fetch, lambda _i: None)
            check(f"refuses {look!r} before a still", False)
        except stills.StillError:
            check(f"refuses {look!r} before a still", True)
    try:
        stills.gate("workshop_still", {"character": character["id"], "wardrobe": "nude", "look": "short dark hair"},
                    "default", fetch, lambda _i: None)
        check("nude is refused while the switch is off", False)
    except stills.StillError as exc:
        check("nude is refused while the switch is off", "21+" in str(exc))
    stills.gate("workshop_still", {"character": character["id"], "wardrobe": "nude"}, "adult", fetch, lambda _i: None)
    check("nude is allowed only in the 21+ area", True)
    try:
        stills.gate("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "image": "photo.png"},
                    "default", fetch, lambda _i: None)
        check("an uploaded photo is not a still input", False)
    except stills.StillError as exc:
        check("an uploaded photo is not a still input", "photo" in str(exc).lower() or "face-swap" in str(exc).lower())
    try:
        stills.gate("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "lora": "celebrity.safetensors"},
                    "default", fetch, lambda _i: None)
        check("a named likeness LoRA is refused", False)
    except stills.StillError:
        check("a named likeness LoRA is refused", True)
    photo = {"id": "photo1", "role": "background", "kind": "upload", "type": "image", "character": character["id"]}
    try:
        stills.gate("keep_face", {"character": character["id"], "items": ["photo1"]}, "default", fetch,
                    lambda iid: photo if iid == "photo1" else None)
        check("a real-person photo is refused as training input", False)
    except stills.StillError as exc:
        check("a real-person photo is refused as training input", "real-person photo" in str(exc), str(exc))
    young = {"id": "stillbad", "role": "made", "kind": "still", "type": "image", "character": character["id"],
             "stated_age": 20, "age_check": "ok"}
    try:
        stills.select_stills([young], character, ["stillbad"], "default", lambda iid: young)
        check("an under-21 still never trains a face", False)
    except stills.StillError as exc:
        check("an under-21 still never trains a face", "under 21" in str(exc) and "20" in str(exc), str(exc))
    missing = dict(young, id="stillmiss", stated_age=None)
    del missing["stated_age"]
    try:
        stills.select_stills([missing], character, ["stillmiss"], "default", lambda iid: missing)
        check("a missing age never trains a face", False)
    except stills.StillError as exc:
        check("a missing age never trains a face", "missing" in str(exc).lower(), str(exc))
    check("youthful-looking is still refused by the word check", not safety.check_prompt("a youthful-looking woman")[0])
    bad_look = {"lora_id": "reactor_faceswap.safetensors", "private_use": "yes", "weights_downloaded": False}
    check("a face-swap file is not a saved face", stills.kept_look(bad_look) is False)
    check("a downloaded weight is not a saved face",
          stills.kept_look({"lora_id": lora, "private_use": "yes", "weights_downloaded": True}) is False)
    refine_unit(check)
    _hold_job(check)


def _source(character, **extra):
    item = {"id": extra.pop("id", "stillok"), "role": "made", "kind": "still", "type": "image",
            "character": character["id"], "stated_age": character["stated_age"], "age_check": "ok",
            "prompt": "olive skin, a linen shirt", "area": "default",
            "appearance_check": {"status": "ok", "held": False}}
    item.update(extra)
    return item


def refine_unit(check):
    print("\n[35] Skin and anatomy gates")
    character = _character()
    fetch = _get(character["id"], character)
    good = _source(character)
    items = {"stillok": good}

    def get_item(iid):
        return items.get(iid)

    stills.gate("refine_skin", {"character": character["id"], "source": "stillok"}, "default", fetch, get_item)
    check("a cleared still can be refined", True)
    check("no extra detailer card is stored", stills.detailer_card() is None)
    try:
        stills.require_model_card("skin_detailer", "default")
        check("a missing detailer card refuses the weight", False)
    except stills.StillError as exc:
        check("a missing detailer card refuses the weight", "license card" in str(exc) and "private use" in str(exc), str(exc))
    mystery = {"1": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "skindetail_krea2_loraholic.safetensors"}}}
    try:
        stills.refuse_uncleared(mystery)
        check("an uncleared detailer file is refused", False)
    except stills.StillError as exc:
        check("an uncleared detailer file is refused", "skindetail_krea2_loraholic.safetensors" in str(exc), str(exc))
    for age, needle in ((18, "under 21"), (None, "Missing"), ("", "Missing"), (21.5, "21.5")):
        try:
            stills.gate("refine_skin", {"character": character["id"], "source": "stillok", "age": age},
                        "default", fetch, get_item)
            check(f"refine age {age!r} does not reach a job", False)
        except stills.StillError as exc:
            check(f"refine age {age!r} does not reach a job", needle in str(exc), str(exc))
    try:
        stills.gate("refine_skin", {"character": character["id"], "source": "stillok", "look": "a youthful-looking woman"},
                    "default", fetch, get_item)
        check("youthful wording is refused before a refine job", False)
    except stills.StillError as exc:
        check("youthful wording is refused before a refine job", "youthful" in str(exc).lower(), str(exc))
    young = _source(character, id="young", prompt="a youthful-looking woman")
    items["young"] = young
    try:
        stills.gate("refine_skin", {"character": character["id"], "source": "young"}, "default", fetch, get_item)
        check("a youthful still is refused before refine", False)
    except stills.StillError as exc:
        check("a youthful still is refused before refine", "youthful" in str(exc).lower(), str(exc))
    for status, faces in (("unchecked", 0), ("timeout", 1), ("error", 1), ("flag", 1)):
        bad = _source(character, id=status, age_check=status, age_flag=(status == "flag"),
                      appearance_check={"status": status, "held": True, "faces": faces})
        items[status] = bad
        try:
            stills.accept_source(bad, character, "default", "refine_skin")
            check(f"a {status} check cannot be refined", False)
        except stills.StillError as exc:
            check(f"a {status} check cannot be refined", "held" in str(exc).lower(), str(exc))
    upload = {"id": "up1", "role": "my_character", "kind": "upload", "type": "image", "character": character["id"],
              "stated_age": 32, "age_check": "ok", "prompt": "olive skin"}
    try:
        stills.accept_source(upload, character, "default", "refine_skin")
        check("an uploaded photo is not a refine source", False)
    except stills.StillError as exc:
        check("an uploaded photo is not a refine source", "uploaded photo" in str(exc), str(exc))
    clothes = _source(character, id="clothes", prompt="remove her clothes")
    try:
        stills.accept_source(clothes, character, "adult", "refine_anatomy")
        check("clothing removal is refused", False)
    except stills.StillError as exc:
        check("clothing removal is refused", "clothing removal" in str(exc).lower() or "refused" in str(exc).lower(), str(exc))
    try:
        stills.gate("refine_anatomy", {"character": character["id"], "source": "stillok"}, "default", fetch, get_item)
        check("anatomy is refused while the 21+ switch is off", False)
    except stills.StillError as exc:
        check("anatomy is refused while the 21+ switch is off", "21+" in str(exc), str(exc))
    nude = _source(character, id="nude", prompt="fully nude, short dark hair", area="adult")
    items["nude"] = nude
    try:
        stills.accept_source(nude, character, "adult", "refine_skin")
        check("a nude still is not refined on the everyday model", False)
    except stills.StillError as exc:
        check("a nude still is not refined on the everyday model", "Chroma" in str(exc) and "21+" in str(exc), str(exc))
    stills.accept_source(nude, character, "adult", "refine_anatomy")
    check("anatomy of an app-made still is allowed only in 21+", True)
    skin_wf, skin_spec = stills._prepare_refine("refine_skin", character, "default", None)
    stills._assert_refine(skin_wf, "refine_skin", skin_spec)
    stills.require_licensed(skin_wf, "default")
    check("skin refine is a light pass on Z-Image-Turbo with no detailer",
          stills.unet_of(skin_wf) == "z_image_turbo_bf16.safetensors" and stills.lora_names(skin_wf) == []
          and skin_spec["denoise"] == stills.SKIN_DENOISE and skin_spec["detailer"] == "")
    try:
        stills._prepare_refine("refine_anatomy", character, "default", None)
        check("anatomy graph is not built while 21+ is off", False)
    except stills.StillError as exc:
        check("anatomy graph is not built while 21+ is off", "21+" in str(exc), str(exc))
    anatomy_wf, anatomy_spec = stills._prepare_refine("refine_anatomy", character, "adult", {"lora_id": "ignored"})
    stills._assert_refine(anatomy_wf, "refine_anatomy", anatomy_spec)
    stills.require_licensed(anatomy_wf, "adult")
    check("anatomy refine is Chroma with no add-on",
          stills.unet_of(anatomy_wf) == "Chroma1-HD.safetensors" and stills.lora_names(anatomy_wf) == []
          and anatomy_spec["denoise"] == stills.ANATOMY_DENOISE and anatomy_spec["identity"] is None)
    page = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "v3.js"), encoding="utf-8").read()
    check("the workshop page says the check can miss a youthful result",
          "The check can miss a youthful result and can flag a young-looking adult. It is not a guarantee." in page)
    check("the workshop page says the extra detailer stays off",
          "No extra detailer is loaded" in page and "workshopAnatomy" in page)


def _hold_job(check):
    print("\n[36] A failed appearance check holds the refine result")
    import shutil
    import tempfile

    import age_guard
    import character as charmod
    import library
    import pipelines
    from PIL import Image

    root = tempfile.mkdtemp(prefix="es_refine_")
    os.makedirs(os.path.join(root, "tmp"))
    cid = "abc123def0"
    character = _character(cid=cid)
    character["traits"] = {}
    charmod.Store(root).save(character)
    lib = library.Library(root)
    src = os.path.join(root, "src.png")
    Image.new("RGB", (64, 96), (40, 90, 140)).save(src)
    item = lib.add(src, "still", role="made", character=cid, stated_age=32, age_check="ok",
                   prompt="olive skin, a linen shirt", appearance_check={"status": "ok", "held": False})

    class Comfy:
        def upload_image(self, path):
            return os.path.basename(path)

        def run(self, wf, out_dir, on_progress=None, by_node=True):
            path = os.path.join(out_dir, "refined.png")
            Image.new("RGB", (64, 96), (50, 100, 160)).save(path)
            return {"12": [path]}

    class Guard:
        enabled = True

        def __init__(self, status, reason, faces=0):
            self.status, self.reason, self.faces = status, reason, faces

        def check(self, path):
            return age_guard.gate({"status": self.status, "reason": self.reason, "faces": self.faces, "p_under21": 0.9})

    old_guard = pipelines.AGE_GUARD
    old_area = pipelines.area()
    try:
        pipelines.set_area("default")
        for status, reason in (("unchecked", "no face"), ("timeout", "age checker timed out"), ("error", "age checker failed")):
            pipelines.AGE_GUARD = Guard(status, reason, 0 if status == "unchecked" else 1)
            ctx = pipelines.JobContext({"id": "job" + status[:4], "params": {}}, Comfy(), lib, charmod.Store(root))
            before = set(lib.items)
            try:
                stills.job_refine_skin(ctx, {"character": cid, "source": item["id"]})
                check(f"a {status} refine is not saved for use", False, "it finished")
            except age_guard.AgeCheckBlocked as exc:
                check(f"a {status} refine is held", reason in str(exc) and set(lib.items) == before, str(exc))
        pipelines.AGE_GUARD = Guard("flag", "may look under 21", 1)
        ctx = pipelines.JobContext({"id": "jobflag", "params": {}}, Comfy(), lib, charmod.Store(root))
        before = set(lib.items)
        try:
            stills.job_refine_skin(ctx, {"character": cid, "source": item["id"]})
            check("a flagged refine is deleted, not saved", False, "it finished")
        except age_guard.AgeCheckDiscarded as exc:
            check("a flagged refine is deleted, not saved or blurred, and says so",
                  set(lib.items) == before and "deleted" in str(exc) and "new seed" in str(exc) and ctx.job.get("can_retry") is True, str(exc))
        # an older item that still carries the flag (made before the discard) stays blocked everywhere
        old_png = os.path.join(root, "older.png")
        Image.new("RGB", (64, 96), (60, 60, 60)).save(old_png)
        flagged = [lib.add(old_png, "still", role="made", character=cid, stated_age=32, age_flag=True, age_check="flag",
                           appearance_check={"status": "flag", "held": True, "faces": 1})]
        check("an older flagged item is not reusable", age_guard.saved_blocked(flagged[0]), flagged)
        try:
            lib.person_image(flagged[0]["id"])
            check("an older flagged item cannot be reused", False)
        except PermissionError as exc:
            check("an older flagged item cannot be reused", "can't be used" in str(exc), str(exc))
        try:
            stills.accept_source(flagged[0], character, "default", "refine_skin")
            check("an older flagged item cannot be refined again", False)
        except stills.StillError as exc:
            check("an older flagged item cannot be refined again", "held" in str(exc).lower(), str(exc))
        import pipelines_v3
        try:
            pipelines_v3._check_training_source(ctx, flagged[0], character)
            check("an older flagged item cannot be trained on", False)
        except pipelines.UserError as exc:
            check("an older flagged item cannot be trained on", "training" in str(exc).lower(), str(exc))
        flagged[0]["favourite"] = True
        lib._write(flagged[0])
        exported = [row["id"] for row in lib.list(character=cid, limit=5000)
                    if (row.get("favourite") or row["id"] == character.get("hero"))
                    and not age_guard.saved_blocked(row)]
        check("an older flagged item is left out of an export", flagged[0]["id"] not in exported and flagged[0].get("favourite") is True)
    finally:
        pipelines.AGE_GUARD = old_guard
        pipelines.set_area(old_area)
        shutil.rmtree(root, ignore_errors=True)


def _wf(a, job):
    return a.get(f"/api/jobs/{job['id']}/workflow").json()["workflows"][-1]


def _parts(wf):
    unets = [n["inputs"].get("unet_name") for n in wf.values() if n.get("class_type") == "UNETLoader"]
    loras = [n["inputs"].get("lora_name") for n in wf.values() if n.get("class_type") == "LoraLoaderModelOnly"]
    return unets, loras


def _refused(a, mock_url, requests, kind, params, needle, area=None):
    before_log = requests.get(mock_url + "/mock/log").json()
    before_jobs = len(a.get("/api/jobs").json())
    body = {"kind": kind, "params": params}
    if area:
        body["area"] = area
    response = a.post("/api/jobs", json=body)
    after_log = requests.get(mock_url + "/mock/log").json()
    text = response.text
    return (response.status_code == 400 and needle in text and after_log == before_log
            and len(a.get("/api/jobs").json()) == before_jobs, text)


def e2e(a, mock_url, comfy_dir):
    import requests
    check = a.check
    print("\n[33] Workshop stills through the mock engine")
    person = {"name": "Mara", "gender": "woman", "style": "photo", "age": 32, "traits": {}}
    character = a.post("/api/characters", json=person).json()
    check("saved person is 32, not a filled-in 25", character.get("age") == 32 and character.get("stated_age") == 32
          and character.get("age") != 25, character)
    refused, text = _refused(a, mock_url, requests, "workshop_still",
                             {"character": character["id"], "wardrobe": "jeans_tee", "age": 18}, "under 21")
    check("age 18 never reaches a still job", refused, text)
    refused, text = _refused(a, mock_url, requests, "workshop_still",
                             {"character": character["id"], "wardrobe": "jeans_tee", "look": "a youthful-looking woman"},
                             "youthful")
    check("youthful wording never reaches a still job", refused, text)
    refused, text = _refused(a, mock_url, requests, "workshop_still",
                             {"character": character["id"], "wardrobe": "nude", "look": "short dark hair"}, "21+")
    check("nude is refused while the adult switch is off", refused, text)
    refused, text = _refused(a, mock_url, requests, "workshop_still",
                             {"character": character["id"], "wardrobe": "jeans_tee", "image": "photo.png"}, "photo")
    check("the still step refuses an uploaded photo", refused, text)
    job = a.job("workshop_still", {"character": character["id"], "wardrobe": "jeans_tee", "body": "athletic",
                                   "look": "olive skin, long dark hair"})
    check("everyday still finishes", job.get("status") == "done" and job.get("results"), job.get("error"))
    unets, loras = _parts(_wf(a, job))
    result = (job.get("results") or [{}])[0]
    check("everyday still is Z-Image-Turbo with the saved age",
          unets == ["z_image_turbo_bf16.safetensors"] and loras == [] and result.get("stated_age") == 32
          and result.get("kind") == "still" and (result.get("provenance") or {}).get("model") == "z_image_turbo",
          (unets, loras, result.get("stated_age"), result.get("provenance")))
    positive = json.dumps(_wf(a, job))
    check("the prompt uses the typed look and body, and age 32",
          "athletic" in positive and "olive skin" in positive and "32-year-old" in positive)
    photo = a.upload(__import__("v3_tests").person(), "background", name="street.png")
    check("a scenery photo can be uploaded for the refusal test", photo.status_code == 200, photo.text[:200])
    photo_id = photo.json()["id"]
    refused, text = _refused(a, mock_url, requests, "keep_face",
                             {"character": character["id"], "items": [photo_id]}, "real-person photo")
    check("keep this face refuses a real-person photo before the job starts", refused, text)
    other = a.post("/api/characters", json={"name": "Leo", "gender": "man", "style": "photo", "age": 41, "traits": {}}).json()
    other_still = a.job("workshop_still", {"character": other["id"], "wardrobe": "suit", "look": "grey hair"})
    refused, text = _refused(a, mock_url, requests, "keep_face",
                             {"character": character["id"], "items": [other_still["results"][0]["id"]]}, "belong")
    check("keep this face refuses another person's still", refused, text)
    kept = a.job("keep_face", {"character": character["id"]})
    check("keep this face records a LoRA id", kept.get("status") == "done" and kept.get("lora"), kept.get("error"))
    fresh = a.get(f"/api/characters/{character['id']}").json()
    look = fresh.get("look") or {}
    path = os.path.join(comfy_dir, "models", "loras", look.get("lora_id") or "missing")
    meta = {}
    if os.path.isfile(path):
        meta, _shapes = L.read_header(path)
    check("the mock trainer does not download weights",
          look.get("private_use") == "yes" and look.get("weights_downloaded") is False
          and look.get("license_url") == ZIMAGE and look.get("license_checked") == "2026-11-05"
          and os.path.isfile(path) and os.path.getsize(path) < 20000
          and meta.get("es_source") == "app-stills" and meta.get("weights_downloaded") == "false"
          and photo_id not in (look.get("stills") or []) and result["id"] in (look.get("stills") or []),
          (look, meta, os.path.getsize(path) if os.path.isfile(path) else None))
    again = a.job("workshop_still", {"character": character["id"], "wardrobe": "sundress", "look": "long dark hair"})
    unets, loras = _parts(_wf(a, again))
    check("the next still uses foundation Z-Image and that LoRA, not Turbo",
          again.get("status") == "done" and unets == ["z_image_bf16.safetensors"]
          and loras == [look.get("lora_id")] and "turbo" not in "".join(unets),
          (again.get("error"), unets, loras))
    skin = a.job("refine_skin", {"character": character["id"], "source": result["id"]})
    unets, loras = _parts(_wf(a, skin)) if skin.get("id") else ([], [])
    denoises = []
    if skin.get("id"):
        denoises = [n["inputs"].get("denoise") for n in _wf(a, skin).values() if "denoise" in n.get("inputs", {})]
    check("refine skin after a saved face uses the foundation model and that LoRA",
          skin.get("status") == "done" and unets == ["z_image_bf16.safetensors"] and loras == [look.get("lora_id")]
          and denoises == [stills.SKIN_DENOISE] and (skin.get("results") or [{}])[0].get("stated_age") == 32
          and ((skin.get("results") or [{}])[0].get("provenance") or {}).get("detailer") == "",
          (skin.get("error"), unets, loras, denoises))
    flagged = a.job("workshop_still", {"character": character["id"], "wardrobe": "yoga", "look": "magentatest"})
    check("a flagged still is deleted: no result, a plain message, a retry offered",
          flagged.get("status") == "error" and not flagged.get("results") and flagged.get("can_retry") is True
          and "deleted" in (flagged.get("error") or ""), flagged.get("error") or flagged.get("warning"))
    import discard_tests
    first_seeds = discard_tests._seeds(a, flagged["id"])
    again = a.post("/api/jobs/%s/retry" % flagged["id"])
    if again.status_code == 200:
        discard_tests._wait(a, again.json()["id"])
        new_seeds = discard_tests._seeds(a, again.json()["id"])
    else:
        new_seeds = []
    check("a retried workshop still runs with a new seed (the saved character's seed is not reused)",
          again.status_code == 200 and first_seeds and new_seeds and not set(new_seeds) & set(first_seeds), (again.text[:120], first_seeds, new_seeds))
    refused, text = _refused(a, mock_url, requests, "refine_anatomy",
                             {"character": character["id"], "source": result["id"]}, "21+")
    check("anatomy is refused while the switch is off and does not start a job", refused, text)


def explicit_case(a, mock_url):
    import requests
    check = a.check
    print("\n[34] Explicit stills use Chroma only while 21+ is open")
    character = a.post("/api/characters", json={"name": "Nia", "gender": "woman", "style": "photo", "age": 36, "traits": {}}).json()
    clothed = a.job("workshop_still", {"character": character["id"], "wardrobe": "yoga", "look": "short dark hair"}, area="adult")
    check("a clothed still inside 21+ still uses the fast model",
          clothed.get("status") == "done" and _parts(_wf(a, clothed))[0] == ["z_image_turbo_bf16.safetensors"],
          clothed.get("error"))
    kept = a.job("keep_face", {"character": character["id"]}, area="adult")
    check("a face can be kept from a 21+ still", kept.get("status") == "done" and kept.get("lora"), kept.get("error"))
    nude = a.job("workshop_still", {"character": character["id"], "wardrobe": "nude", "look": "short dark hair"}, area="adult")
    unets, loras = _parts(_wf(a, nude)) if nude.get("id") else ([], [])
    check("a nude still uses Chroma and does not load the face LoRA",
          nude.get("status") == "done" and unets == ["Chroma1-HD.safetensors"] and loras == []
          and (nude.get("results") or [{}])[0].get("stated_age") == 36,
          (nude.get("error"), unets, loras))
    refused, text = _refused(a, mock_url, requests, "workshop_still",
                             {"character": character["id"], "wardrobe": "nude"}, "21+")
    check("nude is still refused when the request is outside the 21+ area", refused, text)
    clothed_id = (clothed.get("results") or [{}])[0].get("id")
    skin = a.job("refine_skin", {"character": character["id"], "source": clothed_id}, area="adult")
    unets, loras = _parts(_wf(a, skin)) if skin.get("id") else ([], [])
    check("a clothed skin pass inside 21+ uses the saved face on the foundation model",
          skin.get("status") == "done" and unets == ["z_image_bf16.safetensors"] and loras
          and "turbo" not in "".join(unets) and "Chroma" not in "".join(unets),
          (skin.get("error"), unets, loras))
    anatomy = a.job("refine_anatomy", {"character": character["id"], "source": clothed_id}, area="adult")
    unets, loras = _parts(_wf(a, anatomy)) if anatomy.get("id") else ([], [])
    weights = " ".join(stills.workflow_weights(_wf(a, anatomy))) if anatomy.get("id") else ""
    check("anatomy uses Chroma and no extra add-on",
          anatomy.get("status") == "done" and unets == ["Chroma1-HD.safetensors"] and loras == []
          and "krea" not in weights.lower() and "klein" not in weights.lower() and "civitai" not in weights.lower(),
          (anatomy.get("error"), unets, loras, weights))
    nude_id = (nude.get("results") or [{}])[0].get("id")
    refused, text = _refused(a, mock_url, requests, "refine_skin",
                             {"character": character["id"], "source": nude_id}, "Chroma", area="adult")
    check("a nude still is not refined on the everyday model", refused, text)
