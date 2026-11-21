# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Pictures of the owner, made with the owner's own likeness LoRA. Stills only in this first version.

Every result is checked before it is kept: the age check, exactly one face, and that face is the
owner's. A result that fails is deleted, never blurred. In the 18+ section an age flag is final.
Kept pictures go to the private gallery only. Every plain copy made on the way (the engine's own
output file, the download, the link to the LoRA) is removed when the job ends.
"""
import os
import secrets
import shutil

import comfy_client as cc
import face_check
import owner as O
import owner_policy
import pipelines as P
import presets
import safety

WORKFLOWS = {"fast": "image_zimage_turbo_api.json", "photo": "image_chroma1hd_api.json"}
ENGINE_FOLDER = "owner_jobs"     # under the engine's output folder; excluded from backups and emptied per job
RETRY = "Nothing was kept. You can try again with a new seed."
FLAG_FINAL = ("The age check flagged this result, so it was deleted. In the 18+ section that is final: "
              "nothing overrules it. " + RETRY)
NOT_LOCAL = ("The engine that answered does not read this computer's folders, so nothing was sent to it. "
             "A likeness picture is made only by the engine on this computer.")
NOT_LOCAL_RESULT = "A result did not come from this computer's engine folder, so it was deleted."
OWNER = None      # the Owner object (consent, the live-match window); set by the owner routes
COMFY_DIR = None  # where the engine's folders are on this computer; set by the owner routes


def _out(ctx):
    return getattr(ctx.lib, "lib", ctx.lib).root


def judge(section, age, face, match_set):
    """What happens to one result. Returns ("keep", provenance) or ("discard", plain reason).

    It takes no setting and no policy: the 18+ flag case cannot be configured away (D-C-49a)."""
    if not isinstance(age, dict) or age.get("status") not in ("ok", "flag"):
        return "discard", "The age check could not clear this result, so it was deleted. " + RETRY
    if age.get("faces") != 1 or not isinstance(face, dict) or face.get("faces") != 1:
        return "discard", "The result did not show exactly one face, so it was deleted. " + RETRY
    same, score = face_check.matches(face.get("embedding") or [], match_set, face.get("model"))
    if not same:
        return "discard", "The face in the result is not the enrolled one, so it was deleted. " + RETRY
    if age["status"] == "flag":
        if section != "default":
            return "discard", FLAG_FINAL
        return "keep", {"age_check": "flag", "age_override": "owner_match", "match_score": score,
                        "p_under21": age.get("p_under21")}
    return "keep", {"age_check": "ok", "match_score": score}


def one_person(text, record):
    """The prompt rail of the one-face rule. The picture is of the owner, who is not named in the text,
    so any person the text introduces is a second person. Group words are refused the same way."""
    if safety.people_mentioned(text) > 0:
        raise P.UserError("A likeness picture shows one person: you. Describe the place, the light and what you "
                          "wear, and leave other people out.")
    ok, msg = safety.check_group_prompt(text, [{"age": record["stated_age"]}])
    if not ok:
        raise P.UserError("A likeness picture shows one person: you. " + msg)


def gates(section, owner):
    """The gates of an 18+ likeness job, checked when it is queued and again when it runs."""
    if section == "default":
        return
    if not owner.adult_live_ok():
        raise P.UserError(O.ADULT_NEEDS)
    if not owner.consent_valid():
        raise P.UserError("The 18+ consent for your likeness is not given, so this will not run.")
    if not owner.window_open():
        raise P.UserError("Do the live match first. An 18+ likeness job starts only for a short time after it.")


def engine_folder():
    """The engine's own output folder for likeness jobs, kept out of backups. Raises when it is not on this computer."""
    base = os.path.join(COMFY_DIR or "", "output")
    if not COMFY_DIR or not os.path.isdir(base):
        raise P.UserError("The engine's folders are not on this computer, so a likeness picture will not be made.")
    folder = os.path.join(base, ENGINE_FOLDER)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    if not O.backup_excluded(folder):
        O._tool("addexclusion", folder)
        if not O.backup_excluded(folder):
            raise P.UserError(O.NOT_EXCLUDED)
    return base, folder


def sweep(out, lora_dir):
    """At startup and after every job: no link to the LoRA, no engine output and no download is left."""
    O.sweep_engine_links(lora_dir)
    shutil.rmtree(os.path.join(O.owner_dir(out), "tmp"), ignore_errors=True)
    shutil.rmtree(os.path.join(O.owner_dir(out), "live"), ignore_errors=True)
    base = os.path.join(COMFY_DIR or "", "output")
    if COMFY_DIR and os.path.isdir(base):
        shutil.rmtree(os.path.join(base, ENGINE_FOLDER), ignore_errors=True)
        for name in os.listdir(base):
            if name.startswith("ownerimg"):
                try:
                    os.remove(os.path.join(base, name))
                except OSError:
                    pass


def job_owner_picture(ctx, p):
    P.require_checker_on()
    out = _out(ctx)
    section = P.area()
    record = O.load(out)
    if not record:
        raise P.UserError("Nobody is enrolled yet. Enrol with the camera first.")
    if not ctx.job.get("owner") or ctx.job.get("owner") != record["owner_id"]:
        raise P.UserError("Unlock with your passphrase first. An unlock lasts five minutes.")
    gates(section, OWNER)
    text = str(p.get("text") or "").strip()[:500]
    if not text:
        raise P.UserError("Describe the picture.")
    one_person(text, record)
    P._txt(text)
    base = p.get("base") or "fast"
    if base not in WORKFLOWS:
        raise P.UserError("Pick a base for the picture: fast or photo.")
    lora = O.usable_lora(out, record["owner_id"], base)
    if not lora:
        raise P.UserError("There is no likeness LoRA for that base yet. Train your likeness first.")
    matcher = O.match_set(out)
    lib = P.LORA_LIB
    if lib is None or not lib.available():
        raise P.UserError("The engine's folders are not on this computer, so a likeness picture will not be made.")
    engine_out, _folder = engine_folder()
    private = O.ensure_private_folder(out)
    tag = secrets.token_hex(6)
    link_name = "owner_%s.safetensors" % secrets.token_hex(8)
    link = os.path.join(lib.dir, link_name)
    dest = os.path.join(private, "tmp", tag)
    kept, last_reason = [], RETRY
    try:
        os.makedirs(dest, mode=0o700)
        os.symlink(lora["path"], link)  # a link, not a copy: the LoRA's only plain file stays in the private folder
        owner_policy.enter(lora["sha256"], owner_policy.OWNER_PICTURE)
        # Only an engine that reads this disk can list a random name made a moment ago. Asked before any prompt.
        if link_name not in ctx.comfy.available("LoraLoaderModelOnly", "lora_name"):
            raise P.UserError(NOT_LOCAL)
        sidecar = {}
        try:
            import json
            with open(os.path.splitext(lora["path"])[0] + ".es.json", encoding="utf-8") as f:
                sidecar = json.load(f)
        except (OSError, ValueError):
            pass
        trigger = " ".join(str(w) for w in (sidecar.get("trigger_words") or [])[:1])
        prompt = safety.add_adult_hint(", ".join(x for x in (trigger, text) if x))
        P._txt(prompt)
        wf = cc.load_workflow(WORKFLOWS[base])
        cc.set_in(wf, "POSITIVE", text=prompt)
        if cc.has_title(wf, "NEGATIVE"):
            cc.set_in(wf, "NEGATIVE", text=P.safe_neg_for("low quality, blurry, deformed, extra people", section))
        w, h = presets.size_for_aspect(2, 3, 1024 * 1024)
        cc.set_in(wf, "SIZE", width=w, height=h)
        seed = int(p.get("seed") or 0) or P._rand_seed()
        cc.set_seed(wf, seed)
        for node in wf.values():
            if node.get("class_type") == "SaveImage":
                node["inputs"]["filename_prefix"] = "%s/%s/ownerimg%s" % (ENGINE_FOLDER, tag, tag)
        cc.inject_loras(wf, [(link_name, max(0.1, min(1.5, float(p.get("strength") or 0.9))))])
        ctx.progress(0, "Making the picture ...")
        if P.HARDWARE is not None:
            import hardware_map
            P.HARDWARE.before_run(hardware_map.family_of_graph(wf), ctx.comfy)
        # Not ctx.run: the download goes into the private folder, and the graph is not kept on the job record.
        paths = ctx.comfy.run(cc.finalize(wf), dest, on_progress=lambda f, m: ctx.progress(f, "Making the picture"))
        for path in paths if isinstance(paths, list) else [x for v in paths.values() for x in v]:
            name = os.path.basename(path)  # the name carries this job's random tag; an engine may save it flat
            if not name.startswith("ownerimg" + tag) or not any(os.path.isfile(os.path.join(folder, name)) for folder in (
                    os.path.join(engine_out, ENGINE_FOLDER, tag), engine_out)):
                last_reason = NOT_LOCAL_RESULT
                os.remove(path)
                continue
            try:
                age = P.AGE_GUARD.check(path)
                face = OWNER.faces.inspect(path, "")
            except face_check.FaceUnavailable as exc:
                age, face, last_reason = None, None, str(exc) + " " + RETRY
            verdict, detail = judge(section, age, face, matcher)
            if verdict != "keep":
                last_reason = detail if isinstance(detail, str) else last_reason
                os.remove(path)
                continue
            kept.append(O.gallery_add(out, path, {
                "area": section, "owner_id": record["owner_id"], "seed": seed, "base": base, "model": WORKFLOWS[base],
                "provenance": {"likeness_loras": [lora["sha256"]], "workflow": WORKFLOWS[base], **detail}}))
    except cc.ComfyError as exc:
        raise P.UserError(str(exc))
    finally:
        owner_policy.leave()
        for path in (link,):
            try:
                os.remove(path)
            except OSError:
                pass
        shutil.rmtree(dest, ignore_errors=True)
        shutil.rmtree(os.path.join(engine_out, ENGINE_FOLDER, tag), ignore_errors=True)
        for name in os.listdir(engine_out):
            if name.startswith("ownerimg" + tag):
                try:
                    os.remove(os.path.join(engine_out, name))
                except OSError:
                    pass
    if not kept:
        raise P.UserError(last_reason)
    ctx.job["message"] = "Saved to your private gallery (%d)." % len(kept)
    ctx.job["owner_results"] = [row["id"] for row in kept]
