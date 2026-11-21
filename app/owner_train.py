# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Training the owner's likeness, and the trainer self-test that has to pass first.

The likeness trainer takes one source only: the pictures of the enrolment that committed. It never
takes an upload, a gallery item or a list from the request. The trained LoRA stays in outputs/owner
and is registered by its SHA-256. Nothing here runs a model in tests: the test trainer is a stand-in.
"""
import json
import os
import re
import shutil
import time

from PIL import Image, ImageDraw

import lora_workshop as W
import owner as O
import owner_photos
import pipelines as P
import safety
import trainer as T

IMAGE_BASES = ("fast", "photo")
CAPTION = "[trigger], portrait photo"
SELFTEST_FILE = "trainer_selftest.json"
SELFTEST_STEPS = 20
NEED_SELFTEST = ("Run the trainer self-test first. Likeness training starts only after the trainer has passed "
                 "on this machine.")


def _out(ctx):
    return getattr(ctx.lib, "lib", ctx.lib).root


def _root():
    import pipelines_v3 as P3
    return P3.ROOT or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def selftest_record(out):
    try:
        with open(os.path.join(out, SELFTEST_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def selftest_passed(out):
    rec = selftest_record(out)
    return bool(isinstance(rec, dict) and rec.get("ok") is True and rec.get("device") == T.training_device())


def status(out):
    rec = selftest_record(out) or {}
    return {"trainer_installed": T.installed(_root()), "device": T.training_device(), "selftest_passed": selftest_passed(out),
            "selftest": {k: rec.get(k) for k in ("ok", "device", "base", "seconds", "steps", "at", "reason")} if rec else None,
            "likeness_loras": len(O.registry(out)), "bases": list(IMAGE_BASES)}


def _run(ctx, config_path, job_dir):
    done = T.run_training(_root(), config_path, lambda frac, msg: ctx.progress(frac, msg),
                          lambda: bool(ctx.job.get("cancel")), os.path.join(job_dir, "training_log.txt"))
    if not done:
        raise P.Cancelled()


def job_selftest(ctx, p):
    """The first go/no-go: does the trainer run on this machine at all? Ten drawn shapes, a few steps.

    No person and no likeness is involved. The result is numbers: pass or fail, seconds, device.
    If it fails, likeness training waits. It is never moved to another machine."""
    out = _out(ctx)
    base = p.get("base") or "fast"
    if base not in IMAGE_BASES:
        raise P.UserError("Pick a base for the self-test: fast or photo.")
    if not T.installed(_root()):
        raise P.UserError("The trainer isn't installed yet.")
    name = "selftest_%s" % time.strftime("%Y%m%d_%H%M%S")
    job_dir = os.path.join(out, "tmp", name)
    dataset = os.path.join(job_dir, "dataset")
    os.makedirs(dataset, exist_ok=True)
    record = {"ok": False, "device": T.training_device(), "base": base, "steps": SELFTEST_STEPS, "at": time.time()}
    started = time.time()
    try:
        for n in range(T.MIN_PICTURES):
            im = Image.new("RGB", (512, 512), (30 + n * 20, 90, 200 - n * 15))
            ImageDraw.Draw(im).rectangle([100 + n * 10, 120, 380, 400 - n * 10], fill=(240, 220 - n * 12, 60 + n * 15))
            im.save(os.path.join(dataset, "%03d.png" % n))
            with open(os.path.join(dataset, "%03d.txt" % n), "w", encoding="utf-8") as f:
                f.write("[trigger], a coloured rectangle")
        cfg = T.write_config(job_dir, name, base, "selftestshape", dataset, steps=SELFTEST_STEPS, rank=4)
        try:
            ctx.comfy.free_memory()
        except Exception:
            pass
        _run(ctx, cfg, job_dir)
        made = T.find_outputs(job_dir, name)
        record.update(ok=bool(made), seconds=round(time.time() - started, 1))
        if not made:
            record["reason"] = "the trainer finished but wrote no LoRA file"
    except P.Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001
        record.update(seconds=round(time.time() - started, 1), reason=str(exc)[-300:])
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
        with open(os.path.join(out, SELFTEST_FILE), "w", encoding="utf-8") as f:
            json.dump(record, f, indent=1)
    if not record["ok"]:
        raise P.UserError("The trainer self-test did not pass on this machine (%s), so likeness training waits: %s"
                          % (record["device"], record.get("reason") or "no reason given"))
    ctx.job["message"] = "The trainer self-test passed on %s in %s seconds." % (record["device"], record["seconds"])


def capture_set(out, record):
    """The enrolment pictures (each checked against the hash written at enrolment) plus the owner's kept photos."""
    items = _enrolment_set(out, record)
    try:
        return items + owner_photos.photo_items(out, record)
    except ValueError as exc:
        raise P.UserError(str(exc))


def _enrolment_set(out, record):
    folder = os.path.join(O.owner_dir(out), "captures", str(record.get("capture_session") or ""))
    try:
        with open(os.path.join(folder, "session.json"), encoding="utf-8") as f:
            session = json.load(f)
    except (OSError, ValueError):
        raise P.UserError("The enrolment pictures are missing, so training will not start.")
    if session.get("owner_id") != record.get("owner_id"):
        raise P.UserError("The enrolment pictures belong to another enrolment, so training will not start.")
    items = []
    for row in session.get("frames") or []:
        path = os.path.join(folder, os.path.basename(str(row.get("file") or "")))
        if not os.path.isfile(path) or O.file_sha256(path) != row.get("sha256"):
            raise P.UserError("An enrolment picture was changed or removed since enrolment, so training will not start.")
        items.append({"id": row["file"], "path": path, "age_check": row.get("age_check") or "ok"})
    return items


class _Paths:
    """What the shared age re-check needs: where each picture is."""

    @staticmethod
    def path(item):
        return item["path"]


def job_owner_train(ctx, p):
    P.require_checker_on()
    out = _out(ctx)
    if P.area() != "default":
        raise P.UserError("Training the likeness happens in the everyday section only.")
    record = O.load(out)
    if not record:
        raise P.UserError("Nobody is enrolled yet. Enrol with the camera first.")
    if not ctx.job.get("owner") or ctx.job.get("owner") != record["owner_id"]:
        raise P.UserError("Unlock with your passphrase first. An unlock lasts five minutes.")
    base = p.get("base") or "fast"
    if base not in IMAGE_BASES:
        raise P.UserError("Pick a base for the likeness: fast or photo.")
    trigger = str(p.get("trigger") or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9]{3,23}", trigger):
        raise P.UserError("Type a trigger word: 4 to 24 small letters or digits, starting with a letter.")
    ok, msg = safety.check_prompt(trigger)
    if not ok:
        raise P.UserError(msg)
    if W.SEXUAL_ME.search(trigger):
        raise P.UserError(W.ME_SEX)
    if not T.installed(_root()):
        raise P.UserError("The trainer isn't installed yet.")
    if not selftest_passed(out):
        raise P.UserError(NEED_SELFTEST)
    items = capture_set(out, record)
    if len(items) < T.MIN_PICTURES:
        raise P.UserError("Training needs at least %d enrolment pictures (there are %d)." % (T.MIN_PICTURES, len(items)))
    paths = type("Ctx", (), {"lib": _Paths})()
    W.recheck_training_pictures(paths, items)  # SAFETY.md: every training picture is age-checked again right before
    folder = O.ensure_private_folder(out)
    name = "likeness_%s_%s" % (base, time.strftime("%Y%m%d_%H%M%S"))
    job_dir = os.path.join(folder, "training", name)
    dataset = os.path.join(job_dir, "dataset")
    try:
        os.makedirs(dataset, mode=0o700)
        for n, item in enumerate(items):
            shutil.copyfile(item["path"], os.path.join(dataset, "%03d.png" % n))
            with open(os.path.join(dataset, "%03d.txt" % n), "w", encoding="utf-8") as f:
                f.write(CAPTION)
        cfg = T.write_config(job_dir, name, base, trigger, dataset)
        try:
            ctx.comfy.free_memory()
        except Exception:
            pass
        _run(ctx, cfg, job_dir)
        try:
            made = T.find_outputs(job_dir, name)
        except ValueError as exc:
            raise P.UserError(str(exc))
        if set(made) != {"single"}:
            raise P.UserError("The trainer did not write one LoRA file, so nothing was kept.")
        loras = os.path.join(folder, "loras")
        os.makedirs(loras, mode=0o700, exist_ok=True)
        final = os.path.join(loras, name + ".safetensors")
        shutil.move(made["single"], final)
        os.chmod(final, 0o600)
        entry = O.registry_add(out, O.file_sha256(final), record["owner_id"], os.path.basename(final), base,
                               record.get("capture_session"))
        _sidecar(final, trigger, base)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)  # the copies of the pictures and the trainer's caches
    ctx.job["message"] = "Done. Your likeness LoRA is saved privately on this machine."
    ctx.job["owner_lora"] = entry["sha256"][:12]


def _sidecar(lora_path, trigger, base):
    side = {"title": "My likeness", "identity": "player_me", "player_only": True, "owner_likeness": True,
            "area": "default", "trigger_words": [trigger], "base": T.BASES[base]["family"], "source": "Owner enrolment"}
    path = os.path.splitext(lora_path)[0] + ".es.json"
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(side, f, indent=1)

