# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The "Video (API)" job: a short clip from a hosted Wan model. Three calls, in this order of priority: extend
(the last frame of a clip plus an instruction), picture to video, words to video. Joining clips is the extend lane's job.

Everything that can refuse does so before the first request: the area, the likeness mark, any LoRA, the
hosted-media switch, the picture's age check and ancestry. A clip that comes back is age-checked like any
other, kept with remote: true, and never trained on.
"""
import os
import time

import age_guard
import pipelines as P
import pipelines_v3 as V3
import safety
import video_tools as V
from library import PERSON_ROLES
from pipelines import UserError
from providers import ProviderError, Refused, get, guard

POLL_SECONDS = 5.0
LIMIT_SECONDS = 25 * 60
PROVIDER = "dashscope_video"
NOT_KEPT = "The age check did not clear the clip that came back, so it was deleted and nothing was kept. You can try again."


def _lib_root(ctx):
    return getattr(ctx.lib, "lib", ctx.lib).root


def job_video_api(ctx, p):
    P.require_checker_on()
    try:
        _run(ctx, p)
    except (Refused, ProviderError) as e:
        raise UserError(str(e)) from None


def hosted_clip(ctx, item, prompt, seconds, stated_age=None):
    """The one way a hosted clip is made, for this job and for any other lane (extend, chain): checks, submit,
    poll, the output age check, and the result kept with remote: true. `item` is None (words only), a picture
    item (its picture is the first frame) or a video item (its last frame is). The caller has already run the
    checks that belong to its own job (stated age, the prompt rails); everything about leaving the machine is
    here. Returns the new library item. Raises UserError with a plain message."""
    try:
        return _hosted_clip(ctx, item, prompt, seconds, stated_age)
    except (Refused, ProviderError) as e:
        raise UserError(str(e)) from None


def _hosted_clip(ctx, item, prompt, seconds, stated_age=None):
    guard.check_call(media=item is not None)          # area, and the hosted-media switch, before any picture is opened
    provider = get(PROVIDER)
    if not provider.configured():
        raise UserError("Add your Alibaba Model Studio key in Setup \u2192 API keys first.")
    image_path = None
    if item is not None:
        image_path = ctx.lib.path(item)
        if item.get("type") == "video":
            image_path = V.last_frame(image_path, os.path.join(ctx.tmp, "last.png"))
        guard.clear_frame(item, P._lineage_get(ctx), _lib_root(ctx), image_path)
    ctx.steps(1)
    handle = provider.video(prompt, image_path, float(seconds or 5), None)
    handle["dir"] = ctx.tmp
    started = time.time()
    clip = None
    while clip is None:
        ctx.progress(min(0.9, (time.time() - started) / 240.0), "The hosted service is making the clip ...")
        if time.time() - started > LIMIT_SECONDS:
            raise UserError("The hosted service took too long. Nothing was kept.")
        res = provider.poll(handle)
        if res["status"] == "failed":
            raise UserError("The hosted service could not make this clip" + (f" ({res['code']})." if res.get("code") else "."))
        if res["status"] == "done":
            clip = res["file"]
        else:
            time.sleep(POLL_SECONDS)
    check = age_guard.check_video(P.AGE_GUARD, clip, ctx.tmp, V.ffmpeg_bin())
    if check.get("status") != "ok":
        os.remove(clip)
        raise UserError(NOT_KEPT)
    meta = {"prompt": prompt, "model": "Wan 2.7 (hosted)", "remote": True}
    if stated_age is not None:
        meta["stated_age"] = stated_age  # a clip made from words alone keeps the age it was made with
    if item is not None:
        meta.update(parent=item["id"], character=item.get("character"), style=item.get("style"),
                    **P.proof_mark(item, P._lineage_get(ctx)))
    return ctx.add(clip, "video:api", **meta)


def _run(ctx, p):
    guard.check_call()                                   # area, before anything else
    guard.check_params_marks(p)
    adv = p.get("advanced")
    guard.check_loras(adv if isinstance(adv, dict) else {})
    prompt = V3._motion(p)
    item = None
    if p.get("extend_from"):                             # the last frame of a clip you made, plus the instruction
        try:
            item = ctx.lib.get(p["extend_from"])
        except (KeyError, PermissionError) as e:
            raise UserError(str(e))
        if item["type"] != "video" or item.get("role") not in PERSON_ROLES or item.get("age_flag"):
            raise UserError("Pick a video Easy Studio made (and that passed the age check) to continue.")
        records = P._bound_people(ctx, item)
        if not records:
            raise UserError("Missing stated age: age is missing. This clip has no per-person age record.")
        for record in records:
            ok, _age, msg = safety.require_stated_age(record)
            if not ok:
                raise UserError(msg)
    elif p.get("image"):
        guard.check_call(media=True)
        item = P._person(ctx, p, "image")
    if item is not None:
        P._refuse_uploaded_undress(item, prompt, p.get("text"), p.get("motion"), ctx=ctx)
    stated = V3.words_only_age(p, prompt, item) if item is None else None
    hosted_clip(ctx, item, prompt, p.get("seconds") or 5, stated)


P.JOBS["video_api"] = job_video_api
