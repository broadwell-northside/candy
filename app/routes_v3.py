"""Easy Studio 3 web API: the 18+ section gate, LoRA library, Video studio models and imported workflows,
Train my character, settings. register(server_module) adds the routes to the app."""
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid

from fastapi import Body, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import content_mode as CM
import creator_tools as C
import lora_workshop as W
import loras as L
import pipelines
import pipelines_v3 as P3
import safety
import trainer as T
import ui2api
import videomodels as VM
import wfdetect as D

ADULT_DEVICE_COOKIE = "es_adult_device"   # "this device confirmed 18+ once" (1 year)
ADULT_SESSION_COOKIE = "es_adult_session"  # only when a PIN is set: unlocked for 12 hours
SESSION_HOURS = 12
_SESSIONS = {}
_FAILS = {"n": 0, "until": 0.0}
_LOCK = threading.Lock()
S = None  # the server module


def _h(x):
    return hashlib.sha256(str(x).encode()).hexdigest()


def _adult_file():
    return os.path.join(S.OUT, "adult.json")


def _adult_state():
    try:
        return json.load(open(_adult_file()))
    except Exception:
        return {"devices": [], "pin": None}


def _save_adult(st):
    tmp = _adult_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, _adult_file())


def pin_set():
    return bool(_adult_state().get("pin"))


def _pin_hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", str(pin).encode(), bytes.fromhex(salt), 200_000).hex()


def adult_unlocked(request):
    if request is None:
        return False
    st = _adult_state()
    dev = request.cookies.get(ADULT_DEVICE_COOKIE)
    if not dev or _h(dev) not in st.get("devices", []):
        return False
    if st.get("pin"):
        tok = request.cookies.get(ADULT_SESSION_COOKIE)
        exp = _SESSIONS.get(_h(tok)) if tok else None
        return bool(exp and exp > time.time())
    return True


def want_area(request, area):
    """The area a request asks for. 21+ only when this device holds the attestation and SFW mode is off.

    content_mode is the one place the mapping lives: area == "adult" <=> sfw_mode is False.
    """
    try:
        return CM.check_area_request(area, S.SETTINGS, adult_unlocked(request) if area == "adult" else False)
    except PermissionError as exc:
        S.err(str(exc), 403)


def _save_settings():
    tmp = S.SETTINGS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(S.SETTINGS, f, indent=1)
    os.replace(tmp, S.SETTINGS_FILE)


def _cookie(resp, name, value, max_age):
    resp.set_cookie(name, value, max_age=max_age, httponly=True, samesite="strict", path="/")


def register(server):
    global S
    S = server
    app = server.app
    server.want_area = want_area
    server.adult_unlocked = adult_unlocked
    server.pin_set = pin_set
    err = server.err

    # ------------------------------------------------------------------ 18+ gate
    @app.get("/api/adult/status")
    def adult_status(request: Request):
        st = _adult_state()
        dev = request.cookies.get(ADULT_DEVICE_COOKIE)
        return {"unlocked": adult_unlocked(request), "pin": bool(st.get("pin")),
                "device_confirmed": bool(dev and _h(dev) in st.get("devices", []))}

    @app.post("/api/adult/unlock")
    def adult_unlock(request: Request, body: dict = Body(...)):
        """First time on a device: confirm 18+ and the rules (optionally set a PIN). Later: PIN only (if set)."""
        st = _adult_state()
        dev = request.cookies.get(ADULT_DEVICE_COOKIE)
        known = bool(dev and _h(dev) in st.get("devices", []))
        if not known and not (body.get("confirm_age") is True and body.get("confirm_rules") is True):
            err("Please confirm you are 18 or older and accept the rules.")
        with _LOCK:
            if st.get("pin"):
                if _FAILS["until"] > time.time():
                    err(f"Too many wrong PINs. Try again in {int(_FAILS['until'] - time.time()) + 1} seconds.", 429)
                pin = str(body.get("pin") or "")
                if not secrets.compare_digest(_pin_hash(pin, st["pin"]["salt"]), st["pin"]["hash"]):
                    _FAILS["n"] += 1
                    if _FAILS["n"] >= 5:
                        _FAILS.update(n=0, until=time.time() + 300)
                    err("Wrong PIN.", 403)
                _FAILS["n"] = 0
            elif body.get("new_pin"):
                np = str(body["new_pin"])
                if not re.fullmatch(r"\d{4,8}", np):
                    err("A PIN is 4 to 8 digits.")
                salt = secrets.token_hex(16)
                st["pin"] = {"salt": salt, "hash": _pin_hash(np, salt)}
            resp = JSONResponse({"ok": True, "pin": bool(st.get("pin"))})
            if not known:
                dev = secrets.token_urlsafe(32)
                st.setdefault("devices", []).append(_h(dev))
                st["devices"] = st["devices"][-50:]
            _save_adult(st)
            if not known:
                # The 21+ attestation was just stored on this device: full 21+ mode (PRD §7).
                S.SETTINGS.update(CM.on_attestation(dict(S.SETTINGS)))
                _save_settings()
            _cookie(resp, ADULT_DEVICE_COOKIE, dev, 365 * 24 * 3600)
            if st.get("pin"):
                tok = secrets.token_urlsafe(32)
                _SESSIONS[_h(tok)] = time.time() + SESSION_HOURS * 3600
                _cookie(resp, ADULT_SESSION_COOKIE, tok, SESSION_HOURS * 3600)
            return resp

    @app.post("/api/adult/lock")
    def adult_lock(request: Request):
        tok = request.cookies.get(ADULT_SESSION_COOKIE)
        if tok:
            _SESSIONS.pop(_h(tok), None)
        resp = JSONResponse({"ok": True, "unlocked": False})
        if not pin_set():  # without a PIN, locking means forgetting this device
            st = _adult_state()
            dev = request.cookies.get(ADULT_DEVICE_COOKIE)
            if dev and _h(dev) in st.get("devices", []):
                st["devices"].remove(_h(dev))
                _save_adult(st)
            resp.delete_cookie(ADULT_DEVICE_COOKIE, path="/")
        resp.delete_cookie(ADULT_SESSION_COOKIE, path="/")
        return resp

    @app.post("/api/adult/pin")
    def adult_pin(request: Request, body: dict = Body(...)):
        """Set, change or remove the PIN (needs the 18+ section unlocked on this device)."""
        if not adult_unlocked(request):
            err("Open the 18+ section first.", 403)
        st = _adult_state()
        if st.get("pin") and not secrets.compare_digest(_pin_hash(str(body.get("old_pin") or ""), st["pin"]["salt"]),
                                                        st["pin"]["hash"]):
            err("The current PIN is wrong.", 403)
        np = str(body.get("new_pin") or "")
        if np:
            if not re.fullmatch(r"\d{4,8}", np):
                err("A PIN is 4 to 8 digits.")
            salt = secrets.token_hex(16)
            st["pin"] = {"salt": salt, "hash": _pin_hash(np, salt)}
        else:
            st["pin"] = None
        _SESSIONS.clear()
        _save_adult(st)
        resp = JSONResponse({"ok": True, "pin": bool(st["pin"])})
        if st["pin"]:
            tok = secrets.token_urlsafe(32)
            _SESSIONS[_h(tok)] = time.time() + SESSION_HOURS * 3600
            _cookie(resp, ADULT_SESSION_COOKIE, tok, SESSION_HOURS * 3600)
        return resp

    # ------------------------------------------------------------------ settings
    @app.get("/api/settings")
    def get_settings(request: Request):
        attested = adult_unlocked(request)
        sfw = CM.effective_sfw_mode(S.SETTINGS, attested)
        return {"age_check": S.AGE.enabled, "age_status": S.AGE.status(), "sfw_mode": sfw,
                "area": CM.area_for(sfw), "attested": attested}

    @app.post("/api/settings")
    def set_settings(request: Request, body: dict = Body(...)):
        if "sfw_mode" in body:
            try:
                S.SETTINGS.update(CM.set_sfw_mode(S.SETTINGS, body["sfw_mode"], adult_unlocked(request)))
            except PermissionError as exc:
                err(str(exc), 403)
            except ValueError as exc:
                err(str(exc))
            _save_settings()
        if "age_check" in body:
            on = bool(body["age_check"])
            if not on and body.get("confirm") != "I understand":
                err("Switching the age check off needs confirmation.")
            S.AGE.enabled = on
            S.SETTINGS["age_check"] = on
            if not on:
                S.AGE.stop()
            _save_settings()
        return get_settings(request)

    # ------------------------------------------------------------------ LoRA library
    def lora_json(r, request):
        d = dict(r)
        if d.get("thumb"):
            d["thumb_url"] = "/api/loras/thumb?name=" + __import__("urllib.parse").parse.quote(d["name"])
        return d

    @app.get("/api/loras")
    def list_loras(request: Request, area: str = "", model: str = ""):
        a = want_area(request, area)
        try:
            files, info = S.comfy_files() if S.COMFY.is_up() else ({}, {})
        except Exception:
            info = {}
        spec = (info.get("LoraLoaderModelOnly", {}).get("input", {}).get("required", {}) or {}).get("lora_name") if info else None
        names = (spec[0] if spec and isinstance(spec[0], list) else []) if spec else []

        def bare(n, where):
            return {"name": n, "title": n, "family": "unknown", "family_label": L.FAMILIES["unknown"], "trigger_words": [],
                    "strength": None, "strength_known": False, "blocked": not safety.check_lora(n)[0], "source": where,
                    "blocked_reason": safety.check_lora(n)[1]}
        if not S.LORAS.available():
            return {"folder": False, "loras": [bare(n, "ComfyUI") for n in names], "families": L.FAMILIES}
        out = []
        for r in S.LORAS.scan():
            if r.get("area") == "adult" and a != "adult":
                continue
            if r["name"].startswith("_trash/"):
                continue
            out.append(lora_json(r, request))
        known = {r["name"] for r in S.LORAS.scan()}
        out += [bare(n, "another ComfyUI folder") for n in names
                if n not in known and not n.startswith("_trash/") and n not in _builtin_loras()]
        return {"folder": True, "loras": out, "families": L.FAMILIES,
                "model_families": _model_families()}

    _BUILTIN = set()

    def _builtin_loras():
        """Speed-up / helper LoRAs the built-in workflows already use: not shown in the library."""
        if not _BUILTIN:
            for n in os.listdir(S.cc.WORKFLOW_DIR):
                try:
                    for node in S.cc.load_workflow(n).values():
                        if node.get("class_type") in ("LoraLoaderModelOnly", "LoraLoader"):
                            _BUILTIN.add(node["inputs"].get("lora_name"))
                except Exception:
                    pass
            _BUILTIN.add("")
        return _BUILTIN

    _MF = {}

    def _model_families():
        if not _MF:
            for m in VM.MODELS:
                try:
                    wf = VM.load(VM.workflow_file(m))
                    main = [n["inputs"].get("unet_name") or n["inputs"].get("ckpt_name") for n in wf.values()
                            if n["inputs"].get("unet_name") or n["inputs"].get("ckpt_name")]
                    _MF[m["id"]] = L.family_of_model_file(str(main[0]) if main else "")
                except Exception:
                    _MF[m["id"]] = "unknown"
            _MF.update({"photo": "flux", "fast": "zimage", "anime": "sdxl", "edit": "qwen_image"})
        return _MF

    @app.get("/api/loras/thumb")
    def lora_thumb(request: Request, name: str):
        try:
            r = S.LORAS.get(name)
        except (ValueError, OSError):
            err("Not found", 404)
        if not r.get("thumb") or (r.get("area") == "adult" and not adult_unlocked(request)):
            err("Not found", 404)
        side = S.LORAS._sidecar(S.LORAS.path_of(name))
        if side.get("thumb_adult") and not adult_unlocked(request):
            err("Not found", 404)
        return FileResponse(os.path.join(S.LORAS.dir, r["thumb"]))

    @app.post("/api/loras/upload")
    async def lora_upload(request: Request, file: UploadFile = File(...), confirm: str = Form(""), area: str = Form("")):
        a = want_area(request, area)
        if confirm != "yes":
            err("Please tick the box: this LoRA is a style, a concept or an original fictional adult character -- "
                "not a real person and not a child.")
        if not S.LORAS.available():
            err("Easy Studio can't see ComfyUI's LoRA folder on this PC (set COMFY_DIR).")
        name = os.path.basename(file.filename or "")
        if not name.lower().endswith(".safetensors"):
            err("Only .safetensors LoRA files can be added.")
        tmp = os.path.join(S.LORAS.dir, f".upload_{uuid.uuid4().hex}.part")
        size = 0
        try:
            with open(tmp, "wb") as f:
                while True:
                    chunk = await file.read(1 << 20)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > S.MAX_LORA_UPLOAD:
                        err("That file is bigger than 4 GB -- not a normal LoRA.")
                    f.write(chunk)
            try:
                rec = S.LORAS.add_file(tmp, name, source="upload", **({"area": "adult"} if a == "adult" else {}))
            except ValueError as e:
                err(str(e))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        S._cache["t"] = 0  # ComfyUI re-reads the folder; refresh our list soon
        return lora_json(rec, request)

    @app.patch("/api/loras")
    def lora_edit(request: Request, body: dict = Body(...)):
        try:
            r = S.LORAS.get(str(body.get("name")))
        except (ValueError, OSError) as e:
            err(str(e), 404)
        if r.get("area") == "adult" and not adult_unlocked(request):
            err("Not found", 404)
        ch = {}
        if "title" in body:
            t = str(body["title"])[:80]
            ok, msg = safety.check_lora(t)
            if not ok:
                err(msg)
            ch["title"] = t
        if "trigger_words" in body:
            tw = [str(x).strip()[:60] for x in (body["trigger_words"] or []) if str(x).strip()][:6]
            ok, msg = safety.check_lora(r["name"], None, tw)
            if not ok:
                err(msg)
            ch["trigger_words"] = tw
        if "strength" in body:
            ch["strength"] = max(-2.0, min(2.0, float(body["strength"])))
        if "base" in body and body["base"] in L.FAMILIES:
            ch["base"] = body["base"]
        if "area" in body and body["area"] in ("default", "adult"):
            want_area(request, "adult")  # only from inside the 18+ section
            ch["area"] = body["area"]
        S.LORAS.write_sidecar(r["name"], **ch)
        return lora_json(S.LORAS.get(r["name"]), request)

    @app.delete("/api/loras")
    def lora_delete(request: Request, name: str):
        try:
            r = S.LORAS.get(name)
        except (ValueError, OSError) as e:
            err(str(e), 404)
        if r.get("area") == "adult" and not adult_unlocked(request):
            err("Not found", 404)
        S.LORAS.delete(name)
        S._cache["t"] = 0
        return {"ok": True}

    DL = {}

    @app.post("/api/loras/civitai/lookup")
    def civitai_lookup(body: dict = Body(...)):
        secret = str(body.get("api_key") or "")
        try:
            info = W.lookup_url(body.get("url"))
        except W.UseNetwork:
            try:
                info = L.civitai_lookup(body.get("url"), secret or None)
            except ValueError as e:
                err(_hide_secret(str(e), secret))
            except Exception as e:
                err("Couldn't reach Civitai.")
        except ValueError as e:
            err(str(e))
        info.pop("download_url", None)
        info.pop("api_key", None)
        return info

    @app.post("/api/loras/civitai/download")
    def civitai_download(request: Request, body: dict = Body(...)):
        a = want_area(request, body.get("area"))
        if body.get("confirm") != "yes":
            err("Please tick the box: this LoRA is not a real person and not a child.")
        if not S.LORAS.available():
            err("Easy Studio can't see ComfyUI's LoRA folder on this PC (set COMFY_DIR).")
        key = body.get("api_key") or None
        try:
            info = W.lookup_url(body.get("url"))
        except W.UseNetwork:
            try:
                info = L.civitai_lookup(body.get("url"), key)
            except ValueError as e:
                err(_hide_secret(str(e), str(key or "")))
            except Exception:
                err("Couldn't reach Civitai.")
        except ValueError as e:
            err(str(e))
        if not info["ok"]:
            err(info["reason"])
        if info.get("id") and not info.get("download_url"):
            try:
                rec = W.import_entry(S.LORAS, info["id"], "yes")
            except ValueError as exc:
                err(str(exc))
            S._cache["t"] = 0
            return {"id": "fixture", "name": rec["title"], "progress": 1.0, "status": "done", "error": "", "lora": rec["name"]}
        if info.get("nsfw") and a != "adult":
            err("Civitai marks this LoRA as adult (NSFW). Add it from inside the 18+ section.")
        did = uuid.uuid4().hex[:8]
        DL[did] = {"id": did, "name": info["name"], "progress": 0.0, "status": "downloading", "error": ""}

        def run():
            try:
                rec = L.civitai_download(S.LORAS, info, key, dl=DL[did])
                DL[did].update(status="done", progress=1.0, lora=rec["name"] if rec else None)
                S._cache["t"] = 0
            except Exception as e:
                DL[did].update(status="error", error=str(e))
        threading.Thread(target=run, daemon=True).start()
        return DL[did]

    @app.get("/api/loras/downloads")
    def civitai_downloads():
        return list(DL.values())[-20:]

    # ------------------------------------------------------------------ Video studio
    @app.get("/api/video/models")
    def video_models():
        files = S.comfy_files()[0] if S.COMFY.is_up() else None
        return {"models": VM.public(files), "byo": P3.byo_list()}

    @app.post("/api/byo")
    def byo_import(body: dict = Body(...)):
        name = str(body.get("name") or "My workflow")[:60]
        ok, msg = safety.check_prompt(name)
        if not ok:
            err(msg)
        wf = body.get("workflow")
        if isinstance(wf, str):
            try:
                wf = json.loads(wf)
            except ValueError:
                err("That isn't valid JSON. In ComfyUI use Workflow > Export (API), or the normal Save.")
        if not isinstance(wf, dict) or len(json.dumps(wf)) > 4 * 1024 * 1024:
            err("That isn't a ComfyUI workflow.")
        oi = None
        try:
            oi = S.COMFY.object_info()
        except Exception:
            pass
        if "nodes" in wf and "links" in wf:  # the normal 'Save' format: convert using this ComfyUI's node list
            if oi is None:
                err("ComfyUI must be running to read a normal (non-API) workflow. Start it, or export in API format.")
            try:
                ui2api.set_object_info(oi)
                wf = ui2api.convert(wf)
            except Exception as e:
                err(f"Couldn't read that workflow: {e}")
        try:
            a = P3.check_byo(wf, oi)
        except pipelines.UserError as e:
            err(str(e))
        fps = next((wf[r["node"]]["inputs"].get(r["key"]) for r in a["fps"] if r["how"] != "computed"), None)
        text = json.dumps(wf).lower()
        rule = 8 if "ltxv" in text or "ltx2" in text else 4
        bid = uuid.uuid4().hex[:10]
        rec = {"id": bid, "name": name, "mode": a["mode"], "summary": D.summary(a), "created": time.time(),
               "fps": fps if isinstance(fps, (int, float)) else None, "rule": rule, "workflow": wf}
        with open(os.path.join(P3.BYO_DIR, bid + ".json"), "w") as f:
            json.dump(rec, f)
        return {k: v for k, v in rec.items() if k != "workflow"}

    @app.delete("/api/byo/{bid}")
    def byo_delete(bid: str):
        if not re.fullmatch(r"[a-f0-9]{6,32}", bid):
            err("Unknown workflow", 404)
        p = os.path.join(P3.BYO_DIR, bid + ".json")
        if os.path.exists(p):
            os.makedirs(os.path.join(S.OUT, "_trash"), exist_ok=True)
            os.replace(p, os.path.join(S.OUT, "_trash", f"byo_{bid}.json"))
        return {"ok": True}

    # ------------------------------------------------------------------ Train my character
    @app.get("/api/train/status")
    def train_status(request: Request, character: str = "", area: str = ""):
        a = want_area(request, area)
        out = {"installed": T.installed(S.ROOT), "age_check": S.AGE.status(), "lora_folder": S.LORAS.available(),
               "bases": {k: {"label": v["label"], "steps": v["steps"], "family": v["family"]} for k, v in T.BASES.items()},
               "min": T.MIN_PICTURES, "max": T.MAX_PICTURES}
        if character:
            items = [i for i in S.LIB.list(character=character, limit=5000, area="all")
                     if i["type"] == "image" and i.get("role") in S.PERSON_ROLES and not i.get("age_flag")
                     and (i.get("area") != "adult" or a == "adult")]
            out["pictures"] = [S.item_json(i) for i in items if i["kind"] == "train:shot"]
            out["other_pictures"] = [S.item_json(i) for i in items if i["kind"] != "train:shot"][:60]
            out["loras"] = [r for r in (S.LORAS.scan() if S.LORAS.available() else []) if r.get("character") == character]
            try:
                out["trigger"] = T.make_trigger(S.CHARS.get(character)["name"])
            except Exception:
                pass
        return out

    def _hide_secret(text, secret):
        if secret and secret in text:
            return text.replace(secret, "[redacted]")
        return text

    def _lora_or_404(name):
        try:
            return S.LORAS.get(str(name))
        except (ValueError, OSError) as exc:
            S.err(str(exc), 404)

    @app.get("/api/loras/workshop/limits")
    def workshop_limits():
        return W.limits()

    @app.get("/api/loras/workshop/catalogue")
    def workshop_catalogue():
        return W.catalogue_public()

    @app.post("/api/loras/workshop/lookup")
    def workshop_lookup(body: dict = Body(...)):
        try:
            if body.get("id"):
                return W.lookup_id(str(body.get("id")))
            return W.lookup_url(body.get("url"))
        except W.UseNetwork:
            S.err("That model is not in the workshop catalogue.")
        except ValueError as exc:
            S.err(str(exc))

    @app.post("/api/loras/workshop/import")
    def workshop_import(body: dict = Body(...)):
        if not S.LORAS.available():
            S.err("Easy Studio can't see the LoRA folder on this PC.")
        entry_id = str(body.get("id") or "")
        if not entry_id and body.get("url"):
            try:
                found = W.lookup_url(body.get("url"))
            except (W.UseNetwork, ValueError) as exc:
                S.err(str(exc) if isinstance(exc, ValueError) else "That model is not in the workshop catalogue.")
            entry_id = found["id"]
        try:
            rec = W.import_entry(S.LORAS, entry_id, body.get("confirm"))
        except ValueError as exc:
            S.err(str(exc))
        S._cache["t"] = 0
        return lora_json(rec, None)

    @app.post("/api/loras/workshop/upload")
    async def workshop_upload(request: Request, file: UploadFile = File(...), confirm: str = Form("")):
        if confirm != "yes":
            S.err("Download weights only after you confirm. Tick the box first.")
        if not S.LORAS.available():
            S.err("Easy Studio can't see the LoRA folder on this PC.")
        name = os.path.basename(file.filename or "")
        tmp = os.path.join(S.LORAS.dir, ".workshop_upload_%s.part" % uuid.uuid4().hex)
        try:
            data = await file.read()
            if len(data) > S.MAX_LORA_UPLOAD:
                S.err("That file is bigger than 4 GB -- not a normal LoRA.")
            with open(tmp, "wb") as handle:
                handle.write(data)
            try:
                rec = S.LORAS.add_file(tmp, name, source="upload",
                                       usage={"author_notes": "", "trained_words": [], "trained_words_listed": False,
                                              "strength_model": None, "strength_clip": None, "hash_status": "UNKNOWN",
                                              "sha256": "", "role": "", "authorship": "unverified", "examples": []},
                                       trigger_words=[])
            except ValueError as exc:
                S.err(str(exc))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        S._cache["t"] = 0
        return lora_json(rec, request)

    @app.get("/api/loras/workshop/card")
    def workshop_card(name: str = ""):
        return W.usage_card(_lora_or_404(name))

    @app.post("/api/loras/workshop/prompt")
    def workshop_prompt(body: dict = Body(...)):
        record = _lora_or_404(body.get("name"))
        card = W.usage_card(record)
        action = body.get("action") or "triggers"
        if action == "sample":
            examples = (record.get("usage") or {}).get("examples") or []
            try:
                example = examples[int(body.get("example") or 0)]
            except (IndexError, TypeError, ValueError):
                S.err("That sample is not on this card.")
            out = W.apply_sample(example, record["name"])
        else:
            out = W.insert_triggers(body.get("prompt") or "", card["trained_words"], record["name"])
        out["weight_changed"] = False
        return out

    @app.post("/api/loras/workshop/stack")
    def workshop_stack(request: Request, body: dict = Body(...)):
        area = want_area(request, body.get("area"))
        items = []
        for name in body.get("names") or []:
            items.append(W.stack_item(_lora_or_404(name)))
        try:
            report = W.stack_report(items, str(body.get("engine") or "zimage_turbo"), area)
        except ValueError as exc:
            S.err(str(exc))
        return report

    @app.post("/api/loras/workshop/preset")
    def workshop_preset(body: dict = Body(...)):
        record = _lora_or_404(body.get("name"))
        try:
            item = S.LIB.get(str(body.get("item") or ""))
        except KeyError as exc:
            S.err(str(exc), 404)
        try:
            usage = W.save_preset(record, item)
        except ValueError as exc:
            S.err(str(exc))
        S.LORAS.write_sidecar(record["name"], usage=usage)
        return W.usage_card(S.LORAS.get(record["name"]))

    @app.get("/api/loras/workshop/stills")
    def workshop_stills(request: Request, character: str = ""):
        area = want_area(request, "")
        rows = []
        for item in S.LIB.list(limit=500, area="all" if area == "adult" else "default"):
            if not W.still_source_ok(item):
                continue
            if character and item.get("character") != character:
                continue
            if (item.get("area") or "default") == "adult" and area != "adult":
                continue
            try:
                age = W.still_age(item, S.CHARS)
            except ValueError:
                continue
            rows.append({"id": item["id"], "title": item.get("title") or item.get("kind"), "kind": item.get("kind"),
                         "url": S.LIB.url(item), "stated_age": age, "character": item.get("character") or ""})
        return {"stills": rows[:80], "min": T.MIN_PICTURES}

    @app.get("/api/loras/workshop/me")
    def workshop_me(request: Request):
        photos, stills = [], []
        for item in S.LIB.list(limit=500, area="default"):
            if item.get("identity") != "player_me":
                continue
            row = {"id": item["id"], "title": item.get("title") or "", "url": S.LIB.url(item),
                   "stated_age": item.get("stated_age"), "role": item.get("role")}
            if item.get("role") == "player_me_photo":
                photos.append(row)
            elif item.get("role") == "player_me_still":
                stills.append(row)
        path = os.path.join(S.OUT, "player_me.json")
        avatar = None
        if os.path.exists(path):
            try:
                avatar = json.load(open(path, encoding="utf-8"))
            except Exception:
                avatar = None
        return {"notice": W.ME_TEXT, "sexual": W.ME_SEX, "photos": photos, "stills": stills, "avatar": avatar,
                "upload_closed": True, "capture_only": W.ME_CAPTURE_ONLY}

    @app.post("/api/loras/workshop/me/photo")
    async def workshop_me_photo(request: Request, file: UploadFile = File(...), age: str = Form(""),
                                confirm_player: str = Form(""), confirm_not_npc: str = Form(""),
                                caption: str = Form(""), area: str = Form("")):
        """Closed. Every upload is refused, and no photo is saved.

        Two tick boxes do not show who is in a photo, so enrolment waits for the in-app camera capture.
        The earlier refusals still answer first, so a bad request gets the same message as before."""
        if not S.AGE.enabled:
            S.err(S.age_guard.CHECKER_OFF_REASON)
        try:
            W.me_gate(file.filename or "", age, confirm_player, confirm_not_npc, caption, area)
        except ValueError as exc:
            S.err(str(exc))
        S.err(W.ME_CAPTURE_ONLY)

    @app.post("/api/loras/workshop/me/curate")
    def workshop_me_curate(body: dict = Body(...)):
        """Closed. Its only source was uploaded photos, so nothing is turned into a training still."""
        S.err(W.ME_CAPTURE_ONLY)

    @app.post("/api/loras/workshop/me/avatar")
    def workshop_me_avatar(body: dict = Body(...)):
        """Closed. It could only point at a Me LoRA and a curated still that came from uploaded photos.

        Nothing is written and nothing already on disk is removed."""
        S.err(W.ME_CAPTURE_ONLY)


    # PR #39 creator controls, taken in part (Ak's rule): features 12 (outfit try-on, job kind
    # creator_outfit in server.py), 14 (face check), 18 (pre-export hold) and 19 (Surprise me, which
    # fills the look only and never picks an age). Not taken: the Workflow page, carry/place, beach-day,
    # shot board, phase estimates, pipelines and checkpoint resume.
    def _creator_character(character_id):
        if not character_id:
            return None
        try:
            found = S.CHARS.get(str(character_id))
        except Exception:
            return None
        return found if isinstance(found, dict) else None

    def _creator_item(item_id):
        if not item_id:
            return None
        try:
            return S.LIB.get(str(item_id))
        except KeyError:
            S.err("That picture is no longer in the gallery.", 404)

    @app.get("/api/creator/state")
    def creator_state():
        C.set_root(S.OUT)
        state = C.load_state(S.OUT)
        tray = state.get("tray") if isinstance(state.get("tray"), dict) else None
        if tray and tray.get("item_id"):
            try:
                tray = dict(tray)
                tray["url"] = S.LIB.url(S.LIB.get(tray["item_id"]))
                state["tray"] = tray
            except KeyError:
                pass
        state["estimate"] = C.estimate_payload(state)
        state["sentence"] = C.STUDIO_SENTENCE
        state["phases"] = list(C.PHASES)
        state["film"] = C.FILM_LIMITS
        return state

    @app.post("/api/creator/surprise")
    def creator_surprise(body: dict = Body(...)):
        C.set_root(S.OUT)
        try:
            row = C.surprise(body.get("press"))
        except ValueError as exc:
            S.err(str(exc))

        def apply(state):
            state["surprise"] = {"source": "press", "look": row["look"]["label"]}
        C._mutate(S.OUT, apply)
        return row

    @app.post("/api/creator/pack")
    def creator_pack(body: dict = Body(...)):
        C.set_root(S.OUT)
        state = C.load_state(S.OUT)
        character = _creator_character(body.get("character"))
        item = _creator_item(body.get("item")) if body.get("item") else None
        return C.pack_status(character, item, state.get("face"), state.get("reviews") or [])

    @app.post("/api/creator/review")
    def creator_review(body: dict = Body(...)):
        C.set_root(S.OUT)
        state = C.load_state(S.OUT)
        character = _creator_character(body.get("character"))
        item = _creator_item(body.get("item")) if body.get("item") else None
        current = C.pack_status(character, item, state.get("face"), [])
        defect_id = body.get("defect") or ((current["defects"][0]["id"]) if current["defects"] else "")
        try:
            review = C.review_defect(current["defects"], defect_id, body.get("ack"),
                                     (character or {}).get("id"), (item or {}).get("id") if item else "")
        except ValueError as exc:
            S.err(str(exc))

        def apply(saved):
            reviews = list(saved.get("reviews") or [])
            reviews.append(review)
            saved["reviews"] = reviews[-40:]
        C._mutate(S.OUT, apply)
        state = C.load_state(S.OUT)
        return C.pack_status(character, item, state.get("face"), state.get("reviews") or [])

    @app.post("/api/loras/workshop/face-check")
    def workshop_face_check(body: dict = Body(...)):
        C.set_root(S.OUT)
        record = _lora_or_404(body.get("name"))
        try:
            reference = S.LIB.get(str(body.get("reference") or ""))
            result = S.LIB.get(str(body.get("result") or ""))
        except KeyError as exc:
            S.err(str(exc), 404)
        row = C.face_check(reference, result)
        row["lora"] = record["name"]
        row["reference_url"] = S.LIB.url(reference)
        row["result_url"] = S.LIB.url(result)

        def apply(state):
            state["face"] = row
        C._mutate(S.OUT, apply)
        return row

    @app.post("/api/loras/workshop/accept")
    def workshop_accept(body: dict = Body(...)):
        C.set_root(S.OUT)
        record = _lora_or_404(body.get("name"))
        state = C.load_state(S.OUT)
        check = state.get("face") if isinstance(state.get("face"), dict) else None
        if check and check.get("lora") != record["name"]:
            check = None
        try:
            usage = C.accept_lora(record, check)
        except ValueError as exc:
            S.err(str(exc))
        S.LORAS.write_sidecar(record["name"], usage=usage)
        return W.usage_card(S.LORAS.get(record["name"]))
