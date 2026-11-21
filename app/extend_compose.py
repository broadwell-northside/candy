# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Extend and build video: the instruction composer, the realism lock, the colour match, LoRAs and the engine choice.

Everything here is deterministic and runs on the machine. Nothing in this file touches a rail:
the raw words are checked by pipelines._txt before they are used, the composed prompt is checked again,
and the negative terms go through pipelines._safe_neg like every other negative.
"""
import os
import re

from PIL import Image, ImageStat

import comfy_client as cc
import photoreal
import safety
import video_tools as V

# ---- the realism lock ------------------------------------------------------------------------------------------
LOCK_POSITIVE = "photographic, live-action footage, natural motion, realistic skin and lighting, shot on a real camera"
LOCK_NEGATIVE = "anime, cartoon, animated, 3D render, illustration"
DEFAULT_LOOK = "realistic"
NOT_OFFERED = {"anime", "cartoon", "animated", "animation", "manga", "3d", "render3d", "3d render", "painted",
               "illustration", "drawing", "cel"}
CAMERA_WORDS = re.compile(r"\b(camera|pan|pans|panning|zoom|tracking|follow|follows|dolly|shot|angle|close-up)\b", re.I)
CAP_PREV = 160
CAP_INSTRUCTION = 500

# ---- hooks the tests (and the provider lane) set -----------------------------------------------------------------
PROVIDER_LOOKUP = None       # name -> Provider; default: providers.get when that package exists
TEXT_PROVIDERS = None        # () -> list of configured text Providers; default: providers.list_providers()
HOSTED_MEDIA = None          # () -> bool; default: providers.hosted_media_enabled() when it exists, else False
SLEEP = None                 # seconds -> None; the tests make polling instant
MAX_POLLS = 600
POLL_SECONDS = 5


class ExtendError(ValueError):
    """A plain-English refusal. pipelines turns it into a UserError."""


def _providers_module():
    try:
        import providers  # type: ignore
        return providers
    except Exception:
        return None


def get_provider(name):
    if PROVIDER_LOOKUP is not None:
        return PROVIDER_LOOKUP(name)
    mod = _providers_module()
    if mod is None:
        return None
    try:
        return mod.get(name)
    except Exception:
        return None


def hosted_media_on():
    if HOSTED_MEDIA is not None:
        return bool(HOSTED_MEDIA())
    mod = _providers_module()
    fn = getattr(mod, "hosted_media_enabled", None) if mod else None
    try:
        return bool(fn()) if fn else False
    except Exception:
        return False


# ---- look -------------------------------------------------------------------------------------------------------
def resolve_look(p):
    """The request's look, default realistic. Anime and every other drawn or rendered look are not offered for video."""
    look = str((p or {}).get("look") or DEFAULT_LOOK).strip().lower()
    if look in NOT_OFFERED or look not in {r["id"] for r in photoreal.LOOKS}:
        raise ExtendError("Video is always photographic and live-action. Anime, cartoon and 3D looks aren't offered; "
                          "leave the look as Realistic.")
    return look


def lock(prompt):
    """The prompt with the positive realism lock at its end (once, even when it is applied twice)."""
    return f"{strip_lock(prompt)}, {LOCK_POSITIVE}" if strip_lock(prompt) else LOCK_POSITIVE


def strip_lock(text):
    t = str(text or "").strip()
    i = t.find(LOCK_POSITIVE)
    if i >= 0:
        t = t[:i]
    return t.strip().rstrip(",.;| ").strip()


def _plain(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clean_previous(text):
    """The part of a recorded prompt worth carrying forward: its last piece, without the lock or the 'adult' hint."""
    t = _plain(strip_lock(text))
    if " | " in t:
        t = t.split(" | ")[-1]
    t = re.sub(r"^" + re.escape(safety.ADULT_HINT) + r",\s*", "", t, flags=re.I)
    t = re.sub(r"^Continuing the same shot[^.]*\.\s*", "", t)  # a composed prompt: keep only the action
    return t[:CAP_PREV].rstrip(",. ")


def previous_of(item):
    """What the source video's record says about its last clip: (prompt text, seed, look)."""
    prov = (item or {}).get("provenance") or {}
    segs = prov.get("segments") or []
    last = segs[-1] if segs and isinstance(segs[-1], dict) else {}
    text = last.get("instruction") or (item or {}).get("prompt") or ""
    seed = last.get("seed") or prov.get("seed")
    look = prov.get("look") if prov.get("look") in {r["id"] for r in photoreal.LOOKS} else None
    return clean_previous(text), seed, look


def instruction_sentence(text):
    t = _plain(text)[:CAP_INSTRUCTION].strip().rstrip(".!, ")
    return (t[:1].upper() + t[1:]) if t else ""


def compose(instruction, previous=None):
    """Plain words -> the video model's prompt. Same person, place and light as the clip before; the instruction;
    a steady camera unless the words name one; then the realism lock. No word of the instruction is changed or dropped."""
    action = instruction_sentence(instruction)
    parts = []
    cont = "Continuing the same shot, same person, same clothing, same place and light"
    if previous:
        cont += f" (just before: {previous})"
    parts.append(cont + ".")
    if action:
        parts.append(action + ".")
    if not CAMERA_WORDS.search(str(instruction or "")):
        parts.append("The camera follows the subject smoothly.")
    parts.append(LOCK_POSITIVE)
    return " ".join(parts)


# ---- the optional text provider ---------------------------------------------------------------------------------------
POLISH_SYSTEM = ("Rewrite the instruction as one short plain sentence about what is visible in a live-action video clip "
                 "of one adult. Keep the same subject and meaning. Add no new people and no new places. "
                 "Reply with the sentence only.")


def _text_provider(name=None):
    if TEXT_PROVIDERS is not None:
        rows = list(TEXT_PROVIDERS())
    else:
        mod = _providers_module()
        rows = []
        if mod is not None:
            try:
                rows = [mod.get(n["name"] if isinstance(n, dict) else n) for n in mod.list_providers()]  # list_providers gives rows
            except Exception:
                rows = []
    for prov in rows:
        try:
            if prov is not None and getattr(prov, "kind", "") == "text" and prov.configured() and (
                    not name or getattr(prov, "name", "") == name):
                return prov
        except Exception:
            continue
    return None


def _off(value):
    return value is False or str(value).strip().lower() in ("false", "0", "no", "off")


def polish(instruction, area_name, likeness, p, check, has_image=False):
    """The instruction polished by a configured text provider, or None (the caller then composes the raw words).

    It silently stays local for the 18+ section, for anything with a likeness mark or ancestry, and for a request
    with an image part. Only the instruction text is sent. When the providers package has its guard, the same
    server-side refusals that apply to any remote call run first. The reply goes through `check` (the prompt check);
    a refusal or an error means the plain composition of the raw words is used instead.
    """
    if _off((p or {}).get("polish")) or area_name == "adult" or likeness or has_image:
        return None
    prov = _text_provider((p or {}).get("text_provider"))
    if prov is None:
        return None
    messages = [{"role": "system", "content": POLISH_SYSTEM},
                {"role": "user", "content": _plain(instruction)[:CAP_INSTRUCTION]}]
    mod = _providers_module()
    guard = getattr(mod, "guard", None) if mod else None
    if guard is not None:
        try:
            guard.check_call(messages)
        except Exception:
            return None
    try:
        reply = prov.chat(messages, (p or {}).get("text_model"))
    except Exception:
        return None
    reply = _plain(reply)[:CAP_INSTRUCTION]
    if not reply:
        return None
    try:
        check(reply)
    except Exception:
        return None
    return reply


def likeness_marked(item, get_item=None):
    """True if the video, or anything it came from, carries a likeness mark. Fails closed.

    Each item is judged by owner_policy.is_likeness (the registry the other rails use), plus the older
    `likeness` and `ancestry` marks. A parent that can't be looked up, a loop in the parent links, or a chain
    past 64 steps counts as marked: this answer decides what may leave the machine, so "unknown" is "yes"."""
    import owner_policy
    seen, cur = set(), item
    for _ in range(64):
        if not isinstance(cur, dict):
            return True
        if owner_policy.is_likeness(cur) or cur.get("likeness") or cur.get("ancestry"):
            return True
        pid = cur.get("parent")
        if not pid:
            return False
        if get_item is None or pid in seen:
            return True
        seen.add(pid)
        try:
            cur = get_item(pid)
        except Exception:
            return True
    return True


# ---- LoRAs ------------------------------------------------------------------------------------------------------------
def _one_lora(row):
    if isinstance(row, str):
        return row, None
    if isinstance(row, dict):
        ref = row.get("name") or row.get("file") or row.get("id") or row.get("version") or row.get("version_id")
        return (str(ref) if ref not in (None, "") else None), row.get("strength")
    return None, None


def resolve_loras(rows, lib):
    """`loras` from the request (names, or Civitai version ids) -> [{"name", "strength"}] of files in the library."""
    out = []
    for row in rows or []:
        ref, strength = _one_lora(row)
        if not ref:
            raise ExtendError("A LoRA in the list has no name. Pick LoRAs from the library.")
        rec = None
        if lib is not None and lib.available():
            for r in lib.scan():
                civ = r.get("civitai") or {}
                if r["name"] == ref or str(civ.get("version") or "") == ref or r.get("title") == ref:
                    rec = r
                    break
        if rec is None:
            if ref.isdigit():
                raise ExtendError(f"LoRA version {ref} is not in the library. Add it first, or pick one from the list.")
            name = ref
        else:
            name = rec["name"]
            if strength in (None, "") and rec.get("strength_known"):
                strength = rec.get("strength")
        out.append({"name": name, "strength": 1.0 if strength in (None, "") else strength})
    return out


def with_loras(p, lib):
    """A copy of the request whose Advanced LoRAs also hold the top-level `loras`. The old path keeps working."""
    rows = (p or {}).get("loras")
    if not rows:
        return p
    if not isinstance(rows, list):
        raise ExtendError("`loras` must be a list.")
    adv = dict(p.get("advanced") or {}) if isinstance(p.get("advanced"), dict) else {}
    merged = list(adv.get("loras") or []) + resolve_loras(rows, lib)
    if len(merged) > 4:
        raise ExtendError("At most four LoRAs can run on one video.")
    adv["loras"] = merged
    return dict(p, advanced=adv)


def preflight_loras(wf, loras, error_cls):
    """Run every LoRA through the same attach rule the job will use, on this model's loaders, before any work starts.

    A LoRA made for another model, a single file where Wan 2.2 14B needs a high/low pair, a blocked or 18+ LoRA:
    each says why in plain words and nothing runs."""
    if not loras:
        return
    for node in (wf or {}).values():
        if node.get("class_type") in ("UNETLoader", "CheckpointLoaderSimple"):
            main = node["inputs"].get("unet_name") or node["inputs"].get("ckpt_name") or ""
            for f, _s in loras:
                try:
                    cc.route_lora(f, main)
                except cc.LoraRouteError as e:
                    raise error_cls(str(e))


# ---- colour / exposure match at a join ---------------------------------------------------------------------------------
GAIN_LIMIT = 0.15
GAIN_QUIET = 0.02


def _mean_rgb(png):
    with Image.open(png) as im:
        return ImageStat.Stat(im.convert("RGB")).mean


def first_frame(video, out_png):
    V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", video, "-frames:v", "1", out_png])
    return out_png


def match_colour(prev_clip, clip, tmp, idx):
    """Pull the new clip's colour and brightness toward the last frame of the clip before it.

    One gain per channel, from the frame mean at the join, kept within +-15%. Inside 2% nothing is changed.
    Returns (path of the clip to use, record). The frame count and frame rate do not change."""
    a = _mean_rgb(V.last_frame(prev_clip, os.path.join(tmp, f"cm_prev_{idx}.png")))
    b = _mean_rgb(first_frame(clip, os.path.join(tmp, f"cm_next_{idx}.png")))
    gains = [max(1 - GAIN_LIMIT, min(1 + GAIN_LIMIT, (x / y) if y > 1 else 1.0)) for x, y in zip(a, b)]
    rec = {"clip": idx, "gain_rgb": [round(g, 3) for g in gains], "applied": False}
    if all(abs(g - 1) <= GAIN_QUIET for g in gains):
        return clip, rec
    out = os.path.join(tmp, f"matched_{idx}.mp4")
    mixer = f"colorchannelmixer=rr={gains[0]:.4f}:gg={gains[1]:.4f}:bb={gains[2]:.4f}"
    V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-i", clip, "-vf", mixer, "-c:v", "libx264", "-crf", "16",
            "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", out])
    rec["applied"] = True
    return out, rec


# ---- the hosted engine ------------------------------------------------------------------------------------------------
def provider_refusal(p, area_name, source, likeness, loras):
    """Why a hosted model may not run this request, or None. Fails closed; every check runs before any remote call.

    SWAP AT INTEGRATION (once candy/n-providers is merged): this guard and run_provider_clip are replaced by
    provider_jobs.hosted_clip(ctx, item, prompt, seconds), which does the guard, the submit, the poll, the output
    age check and keeps the clip as a library item with remote: true. In pipelines.job_extend, the `if remote:`
    branches call it with item = the source video for part one and the item it returned for each later part,
    and take the clip file from ctx.lib.path(that item)."""
    if area_name == "adult":
        return "The 18+ section never leaves this machine, so it can't use a hosted video model."
    if likeness:
        return "Anything with a likeness mark never leaves this machine, so it can't use a hosted video model."
    if loras:
        return "LoRAs only run on this machine's own model. Remove them, or use the local engine."
    if (source or {}).get("age_check") != "ok":
        return "The automatic age check has not passed on that video, so it can't be sent to a hosted model."
    if not hosted_media_on():
        return ("Extending sends the last picture of your video to the hosted model. That is off: switch on "
                "'hosted media' in Setup first, or use the local engine.")
    return None


def run_provider_clip(prov, prompt, start_png, seconds, model=None, folder=None):
    """One clip from a hosted provider: start the job, wait for it, return the downloaded file's path."""
    import time
    handle = prov.video(prompt, start_png, max(1, int(round(float(seconds)))), model)
    if folder and isinstance(handle, dict):
        handle["dir"] = folder  # where the finished clip is saved
    sleep = SLEEP or time.sleep
    for _ in range(MAX_POLLS):
        res = prov.poll(handle) or {}
        status = str(res.get("status") or "").lower()
        if status in ("done", "succeeded", "completed", "success") and res.get("file"):
            return res["file"]
        if status in ("failed", "error", "cancelled", "canceled", "refused"):
            raise ExtendError(str(res.get("error") or res.get("message") or "The hosted model could not make that clip."))
        sleep(POLL_SECONDS)
    raise ExtendError("The hosted model took too long. Nothing was added.")
