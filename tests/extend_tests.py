# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Extend and build video, on mocks: the composer, the realism lock, chaining with a colour match, LoRAs, the engine choice.

`unit(check)`    -- the composer, the lock, the colour match, the polish rules, the hosted-engine refusals, LoRA names.
`inproc(check)`  -- job_extend run in this process against a fake model run (no ComfyUI, no network, no model):
                    the 5B template's graph is captured, the clips are tiny ffmpeg test patterns, the hosted engine is a stub.
`e2e(...)`       -- the same job through POST /api/jobs on the mock ComfyUI.
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import types
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)

LOCK = "photographic, live-action footage, natural motion"
WALK = "she turns around and walks into the forest and sees trees"


# ---------------------------------------------------------------------------------------------------------- helpers
def _clip(path, colour="0x808080", frames=24, fps=24, size="64x64"):
    import video_tools as V
    V._run([V.ffmpeg_bin(), "-y", "-v", "error", "-f", "lavfi", "-i",
            f"color=c={colour}:s={size}:r={fps}:d={frames / fps}", "-c:v", "libx264", "-pix_fmt", "yuv420p", path])
    return path


def _mean(path):
    import video_tools as V
    import extend_compose as EC
    tmp = tempfile.mkdtemp(prefix="ext_mean_")
    try:
        return EC._mean_rgb(V.last_frame(path, os.path.join(tmp, "f.png")))[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class FakeGuard:
    enabled = True

    def check(self, path):
        return {"status": "ok", "appearance_check": {}}


class StubText:
    """A text provider stand-in (tests/fake_provider.py belongs to the providers lane)."""
    name, kind = "stubtext", "text"

    def __init__(self, reply="She turns and walks slowly into the forest, looking up at the trees.", configured=True):
        self.reply, self._configured, self.calls = reply, configured, []

    def configured(self):
        return self._configured

    def chat(self, messages, model=None):
        self.calls.append(messages)
        return self.reply


class StubVideo:
    name, kind = "stubvid", "video"

    def __init__(self, clip_path, configured=True):
        self.clip, self._configured, self.calls, self.polls = clip_path, configured, [], 0

    def configured(self):
        return self._configured

    def video(self, prompt, image_path, seconds, model=None):
        self.calls.append({"prompt": prompt, "image": image_path, "seconds": seconds, "model": model})
        return {"id": "h1"}

    def poll(self, handle):
        self.polls += 1
        if self.polls == 1:
            return {"status": "running", "file": None}
        return {"status": "done", "file": self.clip}


class Rig:
    """A library with one source video and a job context whose model run is faked."""

    def __init__(self, colour="0x808080", prompt="adult, a woman walks down a beach, " + LOCK, extra=None, prov=None):
        import pipelines as P
        from library import Library
        self.P = P
        self.root = tempfile.mkdtemp(prefix="ext_rig_")
        os.makedirs(os.path.join(self.root, "tmp"), exist_ok=True)
        self.lib = Library(self.root)
        src = _clip(os.path.join(self.root, "src.mp4"), colour)
        self.source = self.lib.add(src, "video", role="made", prompt=prompt, age_check="ok", stated_age=30, style="photo",
                                   provenance=prov or {"seed": 777, "look": "realistic"}, **(extra or {}))
        self.graphs, self.new_colour = [], "0x808080"

    def run(self, params, area="default", clip_colour=None):
        P = self.P
        P.set_area(area)
        P.AGE_GUARD = FakeGuard()
        job = {"id": uuid.uuid4().hex[:8], "params": params}
        ctx = P.JobContext(job, None, self.lib, None)
        self.graphs = graphs = []
        colour = clip_colour or self.new_colour

        def fake_run(wf, label):
            graphs.append(copy.deepcopy(wf))
            return {"9": [_clip(os.path.join(ctx.tmp, f"gen{len(graphs)}.mp4"), colour)]}

        ctx.upload_path = lambda path, name: name
        ctx.run = fake_run
        try:
            P.job_extend(ctx, dict(params))
            return {"status": "done", "results": [self.lib.get(i) for i in job.get("results", [])]}
        except P.UserError as e:
            return {"status": "error", "error": str(e), "results": []}
        finally:
            P.set_area("default")


def _prompts(graph):
    pos = neg = ""
    for n in graph.values():
        title = (n.get("_meta") or {}).get("title") or ""
        if n.get("class_type") == "CLIPTextEncode":
            if "Positive" in title:
                pos = n["inputs"].get("text") or ""
            if "Negative" in title:
                neg = n["inputs"].get("text") or ""
    return pos, neg


def _lora_nodes(graph):
    return [n["inputs"]["lora_name"] for n in graph.values() if n.get("class_type") == "LoraLoaderModelOnly"
            and "Extra LoRA" in ((n.get("_meta") or {}).get("title") or "")]


# ------------------------------------------------------------------------------------------------------------- unit
def unit(check):
    import extend_compose as EC
    import safety
    print("\n[extend] The composer, the realism lock, the colour match, the polish rules, the hosted engine, LoRA names")
    import pipelines as _P
    import providers as _providers
    _old = (_providers.list_providers, _providers.get, EC.TEXT_PROVIDERS)
    try:
        stub = StubText()
        _providers.list_providers = lambda: [{"name": "stubtext", "kind": "text", "configured": True}]
        _providers.get = lambda name: stub if name == "stubtext" else None
        EC.TEXT_PROVIDERS = None
        check("with the real providers package, the text provider is found from its list of rows", EC._text_provider() is stub)
    finally:
        _providers.list_providers, _providers.get, EC.TEXT_PROVIDERS = _old
    _P.set_area("default")  # the providers' guard refuses a thread that has not said which area it works for

    out = EC.compose(WALK, "a woman walks down a beach")
    check("composer keeps every word of the instruction", WALK[0].upper() + WALK[1:] in out, out)
    check("composer keeps the subject and scene from the clip before", "just before: a woman walks down a beach" in out
          and "same person" in out and "same place" in out, out)
    check("composer ends with the realism lock", out.endswith(EC.LOCK_POSITIVE) and "live-action" in out)
    check("composer adds a camera follow when none is named, and not when one is",
          "camera follows" in out and "camera follows" not in EC.compose("the camera pans left as she walks", None))
    check("the lock is applied once, however often", EC.lock(EC.lock("a walk")).count(EC.LOCK_POSITIVE) == 1)
    check("a composed prompt passes the same word check every prompt passes",
          safety.check_all(out)[0] and safety.check_area(out, "default")[0], safety.check_all(out))
    prev = EC.clean_previous("adult, a woman walks down a beach | " + EC.lock("she waves"))
    check("the carried-forward text drops the lock, the hint and the older pieces", prev == "she waves", prev)
    check("the negative lock names anime, cartoon, animated, 3D render, illustration",
          all(w in EC.LOCK_NEGATIVE for w in ("anime", "cartoon", "animated", "3D render", "illustration")))
    import presets
    check("every video's negative carries the lock terms", all(w in presets.VIDEO_NEGATIVE for w in ("anime", "cartoon", "animated")))

    check("look defaults to realistic", EC.resolve_look({}) == "realistic")
    for bad in ("anime", "cartoon", "3d", "painted", "nonsense"):
        try:
            EC.resolve_look({"look": bad})
            ok = False
        except EC.ExtendError as e:
            ok = "photographic" in str(e)
        check(f"look {bad!r} is not offered for video", ok)

    # polish: only when a text provider is configured, never 18+ or likeness, reply re-checked
    seen = []
    ok_check = lambda t: seen.append(t)  # noqa: E731
    old = EC.TEXT_PROVIDERS
    try:
        stub = StubText()
        EC.TEXT_PROVIDERS = lambda: [stub]
        got = EC.polish(WALK, "default", False, {}, ok_check)
        check("a configured text provider polishes the instruction", got and "forest" in got and len(stub.calls) == 1, got)
        sent = json.dumps(stub.calls)
        check("only the instruction is sent, never an id or a description", WALK in sent and "dna" not in sent.lower())
        check("the polished reply goes through the prompt check", seen == [got], seen)
        n = len(stub.calls)
        check("a request with an image part is never polished off this machine",
              EC.polish(WALK, "default", False, {}, ok_check, has_image=True) is None and len(stub.calls) == n)
        check("polish: 'false' or 0 also turns it off", all(EC.polish(WALK, "default", False, {"polish": v}, ok_check) is None
                                                          for v in ("false", 0, "off")) and len(stub.calls) == n)
        old_mod = EC._providers_module

        def refusing(_body=None, media=False):
            raise RuntimeError("refused")
        EC._providers_module = lambda: types.SimpleNamespace(guard=types.SimpleNamespace(check_call=refusing))
        check("the providers guard, when present, can stop a polish: it stays local",
              EC.polish(WALK, "default", False, {}, ok_check) is None and len(stub.calls) == n)
        EC._providers_module = lambda: types.SimpleNamespace(guard=types.SimpleNamespace(check_call=lambda b=None, media=False: None))
        check("and when the guard passes, the polish goes ahead", EC.polish(WALK, "default", False, {}, ok_check) is not None)
        EC._providers_module = old_mod
        n = len(stub.calls)
        check("18+ is never polished off this machine", EC.polish(WALK, "adult", False, {}, ok_check) is None and len(stub.calls) == n)
        check("a likeness mark is never polished off this machine", EC.polish(WALK, "default", True, {}, ok_check) is None and len(stub.calls) == n)
        check("polish: false turns it off", EC.polish(WALK, "default", False, {"polish": False}, ok_check) is None and len(stub.calls) == n)

        def refuse(_t):
            raise ValueError("no")
        check("a refused reply falls back to the plain words", EC.polish(WALK, "default", False, {}, refuse) is None)
        EC.TEXT_PROVIDERS = lambda: [StubText(configured=False)]
        check("no configured provider means no polish", EC.polish(WALK, "default", False, {}, ok_check) is None)
    finally:
        EC.TEXT_PROVIDERS = old

    # colour match
    tmp = tempfile.mkdtemp(prefix="ext_cm_")
    try:
        import video_tools as V
        a, b = _clip(os.path.join(tmp, "a.mp4"), "0x808080"), _clip(os.path.join(tmp, "b.mp4"), "0xA0A0A0")
        path, rec = EC.match_colour(a, b, tmp, 1)
        check("a brighter clip is pulled down, within 15%", rec["applied"] and all(abs(g - 0.85) < 0.01 for g in rec["gain_rgb"]), rec)
        check("the matched clip is closer to the one before", abs(_mean(path) - _mean(a)) < abs(_mean(b) - _mean(a)))
        check("the matched clip keeps its frame count and frame rate",
              V.probe(path)["frames"] == V.probe(b)["frames"] and abs(V.probe(path)["fps"] - V.probe(b)["fps"]) < 0.01)
        same = _clip(os.path.join(tmp, "c.mp4"), "0x808080")
        path2, rec2 = EC.match_colour(a, same, tmp, 2)
        check("a clip that already matches is left alone", not rec2["applied"] and path2 == same, rec2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # hosted engine refusals (fail closed)
    src = {"age_check": "ok"}
    old_hm = EC.HOSTED_MEDIA
    try:
        EC.HOSTED_MEDIA = None
        check("hosted media is off by default, so a hosted extend is refused",
              "hosted media" in (EC.provider_refusal({}, "default", src, False, []) or ""))
        EC.HOSTED_MEDIA = lambda: True
        check("with the switch on and nothing marked, a hosted extend may go", EC.provider_refusal({}, "default", src, False, []) is None)
        check("18+ never goes to a hosted model", "18+" in (EC.provider_refusal({}, "adult", src, False, []) or ""))
        check("a likeness mark never goes to a hosted model", "likeness" in (EC.provider_refusal({}, "default", src, True, []) or ""))
        check("a LoRA can't go to a hosted model", "LoRA" in (EC.provider_refusal({}, "default", src, False, [("a.safetensors", 1)]) or ""))
        check("a video the age check has not passed can't go", "age check" in (EC.provider_refusal({}, "default", {}, False, []) or ""))
    finally:
        EC.HOSTED_MEDIA = old_hm

    # likeness mark through the parent chain
    items = {"p": {"id": "p", "owner_likeness": True}, "r": {"id": "r", "role": "owner_capture"}, "ok": {"id": "ok"},
             "loop": {"id": "loop", "parent": "loop"}}
    marked = EC.likeness_marked
    check("a likeness mark in the history is found, by the owner registry's own test",
          marked({"id": "c", "parent": "p"}, items.get) and marked({"id": "c", "parent": "r"}, items.get))
    check("a clean history is clean", not marked({"id": "c", "parent": "ok"}, items.get) and not marked({"id": "c"}, items.get))
    check("an unknown parent, a loop, or no way to look up counts as marked (fails closed)",
          marked({"id": "c", "parent": "gone"}, items.get) and marked({"id": "c", "parent": "loop"}, items.get)
          and marked({"id": "c", "parent": "ok"}, None))

    _loras_unit(check)


def _loras_unit(check):
    import extend_compose as EC
    import loras as L
    from v3_tests import fake_lora, WAN_KEYS
    root = tempfile.mkdtemp(prefix="ext_lib_")
    try:
        os.makedirs(os.path.join(root, "models", "loras"))
        lib = L.LoraLibrary(root)
        fake_lora(os.path.join(lib.dir, "walk5b.safetensors"), WAN_KEYS)
        lib.write_sidecar("walk5b.safetensors", base="wan5b", strength=0.7, civitai={"model": 1, "version": 4242, "base": "Wan 2.2 5B"})
        rows = EC.resolve_loras(["walk5b.safetensors", {"id": "4242"}, {"name": "walk5b.safetensors", "strength": 0.4}], lib)
        check("LoRAs resolve by name, by version id, and keep a stated strength",
              [r["name"] for r in rows] == ["walk5b.safetensors"] * 3 and [r["strength"] for r in rows] == [0.7, 0.7, 0.4], rows)
        try:
            EC.resolve_loras([{"version": "999999"}], lib)
            ok = False
        except EC.ExtendError as e:
            ok = "not in the library" in str(e)
        check("an unknown version id is refused in plain words", ok)
        try:
            EC.with_loras({"loras": ["a.safetensors"] * 3, "advanced": {"loras": [{"name": "b.safetensors"}] * 2}}, lib)
            ok = False
        except EC.ExtendError as e:
            ok = "four" in str(e)
        check("more than four LoRAs is refused, not cut", ok)
        merged = EC.with_loras({"loras": ["walk5b.safetensors"], "advanced": {"seed": 5, "loras": [{"name": "old.safetensors"}]}}, lib)
        check("the old Advanced path keeps working beside the new one",
              [r["name"] for r in merged["advanced"]["loras"]] == ["old.safetensors", "walk5b.safetensors"] and merged["advanced"]["seed"] == 5)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------------- in-process
def inproc(check):
    import extend_compose as EC
    import pipelines as P
    import loras as L
    from v3_tests import fake_lora, WAN_KEYS, SDXL_KEYS
    print("\n[extend] job_extend against a fake model run: chaining, continuity, colour match, LoRAs, engines")
    saved = (P.AGE_GUARD, P.LORA_LIB, EC.TEXT_PROVIDERS, EC.PROVIDER_LOOKUP, EC.HOSTED_MEDIA, EC.SLEEP)
    comfy = tempfile.mkdtemp(prefix="ext_comfy_")
    try:
        os.makedirs(os.path.join(comfy, "models", "loras"))
        lib = L.LoraLibrary(comfy)
        for name, keys, base in (("walk5b.safetensors", WAN_KEYS, "wan5b"), ("look14b.safetensors", WAN_KEYS, "wan14b"),
                                 ("inkstyle.safetensors", SDXL_KEYS, "sdxl")):
            fake_lora(os.path.join(lib.dir, name), keys)
            lib.write_sidecar(name, base=base, **({"civitai": {"model": 1, "version": 4242, "base": "Wan 2.2 5B"}} if base == "wan5b" else {}))
        P.LORA_LIB = lib
        EC.SLEEP = lambda _s: None
        _chain(check, EC, P)
        _rails(check, EC, P)
        _loras(check, EC, P)
        _engines(check, EC, P)
    finally:
        P.AGE_GUARD, P.LORA_LIB, EC.TEXT_PROVIDERS, EC.PROVIDER_LOOKUP, EC.HOSTED_MEDIA, EC.SLEEP = saved
        shutil.rmtree(comfy, ignore_errors=True)


def _chain(check, EC, P):
    import video_tools as V
    rig = Rig()
    segs = [{"text": WALK, "seconds": 2}, {"text": "she stops and looks up at the tall trees", "seconds": 2},
            {"text": "she kneels down and touches the moss", "seconds": 2}]
    r = rig.run({"video": rig.source["id"], "segments": segs}, clip_colour="0xA0A0A0")
    check("three instructions make three segments and one joined video", r["status"] == "done" and len(rig.graphs) == 3
          and len(r["results"]) == 1, r.get("error"))
    if r["status"] != "done":
        return
    it = r["results"][0]
    prov = it["provenance"]
    n = V.probe(rig.lib.path(it))["frames"]
    check("the joined video is the source plus three clips, repeated frames dropped", n == 24 + 23 * 3, n)
    starts = [[x["inputs"]["image"] for x in g.values() if x.get("class_type") == "LoadImage"][0] for g in rig.graphs]
    check("each part starts from its own picture: the last frame of the clip before it", len(set(starts)) == 3, starts)
    pos0, neg0 = _prompts(rig.graphs[0])
    check("the first prompt carries the instruction, the continuity and the realism lock",
          "walks into the forest" in pos0 and "just before: a woman walks down a beach" in pos0 and LOCK in pos0, pos0)
    check("the negative names anime, cartoon, animated, 3D render, illustration",
          all(w in neg0 for w in ("anime", "cartoon", "animated", "3D render", "illustration")), neg0)
    pos1 = _prompts(rig.graphs[1])[0]
    check("the second prompt remembers what the first part did", "just before: she turns around and walks into the forest" in pos1, pos1)
    segs_rec = prov["segments"]
    check("provenance records each part's words, composed prompt and seed",
          len(segs_rec) == 3 and all(s["instruction"] and LOCK in s["prompt"] and s["seed"] for s in segs_rec), segs_rec)
    check("the source's recorded seed carries to every part", {s["seed"] for s in segs_rec} == {777}, segs_rec)
    check("provenance names the look, the engine and the continuity",
          prov["look"] == "realistic" and prov["engine"] == "local" and prov["continuity"]["from"] == rig.source["id"]
          and prov["continuity"]["seed"] == 777, prov)
    joins = prov["join_points"]
    check("the join points are recorded: three of them, at 24, 47 and 70 frames",
          [j["frame"] for j in joins] == [24, 47, 70], joins)
    check("a colour match is recorded at every join and pulled a brighter clip down",
          all(j.get("colour_matched") and j["colour_gain"][0] < 1 for j in joins), joins)
    check("the prompt on the video is the instructions in order", it["prompt"].count(" | ") == 2 and it["prompt"].startswith("she turns"), it["prompt"])
    check("a chained extend's next prompt does not grow the lock", EC.clean_previous(it["prompt"]) == "she kneels down and touches the moss")

    # an extension of an extension continues from the last part
    r2 = rig.run({"video": it["id"], "segments": [{"text": "she walks on", "seconds": 2}]})
    pos = _prompts(rig.graphs[0])[0] if rig.graphs else ""
    check("extending the extension continues from its last part and its seed",
          r2["status"] == "done" and "just before: she kneels down and touches the moss" in pos
          and r2["results"][0]["provenance"]["segments"][0]["seed"] == 777, r2.get("error") or pos)
    check("a request that sets a seed overrides the recorded one",
          rig.run({"video": it["id"], "segments": [{"text": "she walks on"}], "advanced": {"seed": 5}})["results"][0]
          ["provenance"]["segments"][0]["seed"] == 5)
    check("more than six parts is refused, not cut", "at most 6" in (rig.run(
        {"video": it["id"], "segments": [{"text": "x"}] * 7}).get("error") or ""))
    check("an anime look is refused on extend", "photographic" in (rig.run(
        {"video": it["id"], "segments": [{"text": "she walks on"}], "look": "anime"}).get("error") or ""))


def _rails(check, EC, P):
    rig = Rig()
    r = rig.run({"video": rig.source["id"], "segments": [{"text": "she turns into a little girl", "seconds": 2}]})
    check("the prompt check still refuses the raw words, and no model runs", r["status"] == "error" and not rig.graphs, r)
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}, {"text": "she turns into a little girl"}]})
    check("one refused part refuses the whole request before any part runs", r["status"] == "error" and not rig.graphs, r)
    # the composer cannot launder a word: a polished reply that fails the check is dropped for the raw words
    stub = StubText(reply="she becomes a teenager and walks away")
    EC.TEXT_PROVIDERS = lambda: [stub]
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}]})
    pos = _prompts(rig.graphs[0])[0] if rig.graphs else ""
    check("a polished reply the prompt check refuses is dropped; the raw words are used",
          r["status"] == "done" and len(stub.calls) == 1 and "teenager" not in pos and "walks into the forest" in pos, r.get("error") or pos)
    stub.reply = "She turns and walks slowly into the forest, looking up at the trees."
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}]})
    pos = _prompts(rig.graphs[0])[0] if rig.graphs else ""
    check("a good polished reply is what gets composed, with the continuity and the lock",
          r["status"] == "done" and "walks slowly into the forest" in pos and LOCK in pos and "same person" in pos, r.get("error") or pos)
    n = len(stub.calls)
    rig.run({"video": rig.source["id"], "segments": [{"text": WALK}]}, area="adult")
    check("in the 18+ section the text provider is never called", len(stub.calls) == n)
    marked = Rig(extra={"owner_likeness": True})
    marked.run({"video": marked.source["id"], "segments": [{"text": WALK}]})
    check("a likeness-marked video is never sent to the text provider", len(stub.calls) == n)
    EC.TEXT_PROVIDERS = None
    check("a video that is not in the gallery can't be extended", rig.run({"video": "nope", "segments": [{"text": WALK}]})["status"] == "error")
    flagged = Rig(extra={"age_flag": True})
    check("a video the age check flagged can't be extended", flagged.run(
        {"video": flagged.source["id"], "segments": [{"text": WALK}]})["status"] == "error")
    upload = Rig()
    upload.lib.items[upload.source["id"]]["role"] = "upload"
    check("an uploaded video is still refused", upload.run({"video": upload.source["id"], "segments": [{"text": WALK}]})["status"] == "error")


def _loras(check, EC, P):
    rig = Rig()
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}], "loras": ["walk5b.safetensors"]})
    check("a LoRA by name runs on the 5B model", r["status"] == "done" and _lora_nodes(rig.graphs[0]) == ["walk5b.safetensors"], r.get("error"))
    check("provenance lists the LoRA", r["results"] and r["results"][0]["provenance"]["loras"] == [
        {"name": "walk5b.safetensors", "strength": 1.0}], r["results"][0]["provenance"]["loras"] if r["results"] else r)
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}, {"text": "she waves"}], "loras": [{"id": "4242", "strength": 0.6}]})
    check("a LoRA by Civitai version id runs on every part", r["status"] == "done" and all(
        _lora_nodes(g) == ["walk5b.safetensors"] for g in rig.graphs) and len(rig.graphs) == 2, r.get("error"))
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}], "loras": ["look14b.safetensors"]})
    check("a 14B LoRA on the 5B model is refused with a plain reason, before any model runs",
          r["status"] == "error" and "won't work" in r["error"] and not rig.graphs, r)
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}], "loras": ["inkstyle.safetensors"]})
    check("a picture-model LoRA on video is refused", r["status"] == "error" and "won't work" in r["error"] and not rig.graphs, r)
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}], "loras": [{"version": "31337"}]})
    check("a version id that is not in the library is refused", r["status"] == "error" and "not in the library" in r["error"], r)
    r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK}], "advanced": {"loras": [{"name": "walk5b.safetensors"}]}})
    check("the old Advanced LoRA path still works", r["status"] == "done" and _lora_nodes(rig.graphs[0]) == ["walk5b.safetensors"], r.get("error"))


def _engines(check, EC, P):
    import video_tools as V
    work = tempfile.mkdtemp(prefix="ext_eng_")
    try:
        remote = StubVideo(_clip(os.path.join(work, "remote.mp4"), "0xA0A0A0"))
        EC.PROVIDER_LOOKUP = lambda name: remote if name == "stubvid" else None
        EC.HOSTED_MEDIA = None
        rig = Rig()
        params = {"video": rig.source["id"], "segments": [{"text": WALK, "seconds": 2}], "engine": "stubvid"}
        r = rig.run(params)
        check("a hosted engine is refused while hosted media is off, before any call", r["status"] == "error"
              and "hosted media" in r["error"] and not remote.calls, r)
        EC.HOSTED_MEDIA = lambda: True
        from providers import guard as PG
        saved_settings = dict(PG.SETTINGS)
        PG.SETTINGS["hosted_media"] = False
        r = rig.run(params)
        check("the providers' own switch is checked too: with it off the hosted engine is refused before any call",
              r["status"] == "error" and "switched off" in r["error"] and not remote.calls, r)
        PG.SETTINGS["hosted_media"] = True
        r = rig.run(params)
        it = (r["results"] or [{}])[0]
        check("a hosted engine runs through the provider interface and the clip joins", r["status"] == "done" and len(remote.calls) == 1
              and not rig.graphs and V.probe(rig.lib.path(it))["frames"] == 24 + 23, r.get("error"))
        call = remote.calls[0] if remote.calls else {}
        check("the provider got the composed prompt and the last frame",
              "walks into the forest" in call.get("prompt", "") and LOCK in call.get("prompt", "") and str(call.get("image", "")).endswith(".png")
              and call.get("seconds") == 2, call)
        check("the result is marked remote, with the engine named and the join recorded",
              it.get("remote") is True and it["provenance"]["engine"] == "stubvid" and it["provenance"]["video_proof"] == "hosted"
              and it["provenance"]["join_points"][0]["frame"] == 24, it.get("provenance"))
        check("the age check ran on the joined output", it.get("age_check") == "ok")
        check("a colour match ran on a hosted clip too", it["provenance"]["join_points"][0].get("colour_matched") is True)
        n = len(remote.calls)
        r = rig.run(params, area="adult")
        check("18+ never uses a hosted engine", r["status"] == "error" and "18+" in r["error"] and len(remote.calls) == n, r)
        r = rig.run(dict(params, loras=["walk5b.safetensors"]))
        check("LoRAs are refused on a hosted engine", r["status"] == "error" and "LoRA" in r["error"] and len(remote.calls) == n, r)
        marked = Rig(extra={"owner_likeness": True})
        r = marked.run(dict(params, video=marked.source["id"]))
        check("a likeness mark is refused on a hosted engine", r["status"] == "error" and "likeness" in r["error"] and len(remote.calls) == n, r)
        r = rig.run(dict(params, engine="nobody"))
        check("an unknown engine is refused", r["status"] == "error" and "not a video provider" in r["error"], r)
        remote._configured = False
        r = rig.run(params)
        check("a hosted engine with no key is refused in plain words", r["status"] == "error" and "no key" in r["error"] and len(remote.calls) == n, r)
        remote._configured = True
        r = rig.run(dict(params, provider="stubvid", loop=True))
        check("a loop is refused on a hosted engine", r["status"] == "error", r)
        r = rig.run({"video": rig.source["id"], "segments": [{"text": WALK, "seconds": 2}], "engine": "local"})
        check("engine 'local' is the 5B model on this machine", r["status"] == "done" and len(rig.graphs) == 1
              and "wan2.2_ti2v_5B_fp16.safetensors" in json.dumps(rig.graphs[0]), r.get("error"))
    finally:
        from providers import guard as PG
        PG.SETTINGS.clear()
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------------------------------------------- e2e
def e2e(a, mock_url, comfy_dir, ffprobe_frames, requests, check):
    print("\n[extend] The same through POST /api/jobs on the mock ComfyUI")
    from v3_tests import fake_lora, WAN_KEYS
    import loras as L
    loras_dir = os.path.join(comfy_dir, "models", "loras")
    fake_lora(os.path.join(loras_dir, "es_ext_walk5b.safetensors"), WAN_KEYS)
    fake_lora(os.path.join(loras_dir, "es_ext_look14b.safetensors"), WAN_KEYS)
    lib = L.LoraLibrary(comfy_dir)
    lib.write_sidecar("es_ext_walk5b.safetensors", base="wan5b", civitai={"model": 9, "version": 6161, "base": "Wan 2.2 5B"})
    lib.write_sidecar("es_ext_look14b.safetensors", base="wan14b")

    j = a.job("create", {"dna": {"name": "Beach", "gender": "woman", "age": 31, "style": "photo"},
                         "extra_scene": "fully clothed in a linen shirt, walking on a quiet beach", "count": 1, "aspect": "wide",
                         "look": "realistic", "advanced": {"seed": 20261120}})
    still = (j.get("results") or [None])[0]
    check("X1: a still of one fictional adult", j["status"] == "done" and still, j.get("error"))
    if not still:
        return

    def graphs_since(n):
        return requests.get(mock_url + "/mock/log").json()[n:]

    def texts(g):  # the sent graph has no titles: follow the sampler's positive and negative links
        ks = [n for n in g.values() if n.get("class_type") == "KSampler"]
        if not ks:
            return "", ""
        return tuple(g[str(ks[0]["inputs"][k][0])]["inputs"].get("text", "") for k in ("positive", "negative"))

    start = len(requests.get(mock_url + "/mock/log").json())
    j = a.job("video", {"image": still["id"], "text": "a woman walks down the beach", "seconds": 2, "mode": "fast", "quality": "480"})
    vid = (j.get("results") or [None])[0]
    check("X2: a first-run video is built and carries the realism lock", j["status"] == "done" and vid
          and LOCK in (vid.get("prompt") or "") and (vid.get("provenance") or {}).get("look") == "realistic", j.get("error"))
    sent = graphs_since(start)
    pos, neg = texts(sent[-1]) if sent else ("", "")
    check("X2 sent the lock in the prompt and the anime terms in the negative", LOCK in pos and "anime" in neg and "cartoon" in neg, (pos, neg))
    j = a.job("video", {"image": still["id"], "text": "a woman walks down the beach", "seconds": 2, "look": "anime"})
    check("X3: an anime look is refused with a plain reason", j["status"] in ("error", "refused") and "photographic" in (j.get("error") or ""), j.get("error"))
    if not vid:
        return

    start = len(requests.get(mock_url + "/mock/log").json())
    j = a.job("extend", {"video": vid["id"], "segments": [{"text": WALK, "seconds": 2},
                                                          {"text": "she stops and looks up at the tall trees", "seconds": 2}],
                         "loras": ["es_ext_walk5b.safetensors"], "engine": "local"})
    ext = (j.get("results") or [None])[0]
    check("X4: two instructions extend the video into one", j["status"] == "done" and ext, j.get("error"))
    if not ext:
        return
    prov = ext.get("provenance") or {}
    n0, _, _ = ffprobe_frames(a.file(vid))
    n1, _, _ = ffprobe_frames(a.file(ext))
    check("X4 is the source plus two clips, repeated frames dropped", n1 == n0 + 48 * 2, (n0, n1))
    check("X4 provenance: look, engine, loras, two join points with a colour record, per-part prompts",
          prov.get("look") == "realistic" and prov.get("engine") == "local" and len(prov.get("join_points") or []) == 2
          and all("colour_gain" in jp for jp in prov["join_points"]) and len(prov.get("segments") or []) == 2
          and (prov.get("loras") or [{}])[0].get("name") == "es_ext_walk5b.safetensors", prov)
    sent = graphs_since(start)
    pos, neg = texts(sent[0]) if sent else ("", "")
    check("X4 sent the composed prompt, the lock, the negative terms and the LoRA to the 5B template",
          len(sent) == 2 and "forest" in pos and LOCK in pos and "anime" in neg
          and any(n.get("class_type") == "LoraLoaderModelOnly" and n["inputs"]["lora_name"] == "es_ext_walk5b.safetensors" for n in sent[0].values()), (pos, neg))

    start = len(requests.get(mock_url + "/mock/log").json())
    j = a.job("extend", {"video": vid["id"], "segments": [{"text": WALK, "seconds": 2}], "loras": ["es_ext_look14b.safetensors"]})
    check("X5: a LoRA made for another model is refused plainly, and nothing ran",
          j["status"] in ("error", "refused") and "won't work" in (j.get("error") or "") and not graphs_since(start), j.get("error"))
    j = a.job("extend", {"video": vid["id"], "segments": [{"text": WALK, "seconds": 2}], "loras": [{"id": "6161", "strength": 0.5}]})
    check("X6: a LoRA by Civitai version id resolves on extend", j["status"] == "done", j.get("error"))
    j = a.job("extend", {"video": vid["id"], "segments": [{"text": "she turns into a little girl", "seconds": 2}]})
    check("X7: the prompt check still refuses the words, and the composer does not touch the rail", j["status"] in ("error", "refused"), j.get("error"))
    j = a.job("video_any", {"model": "wan22_5b_i2v", "extend_from": vid["id"], "text": "the camera slowly pans", "seconds": 2,
                            "loras": ["es_ext_look14b.safetensors"]})
    check("X8: video_any refuses the same misfit", j["status"] in ("error", "refused") and "won't work" in (j.get("error") or ""), j.get("error"))
    j = a.job("video_any", {"model": "wan22_5b_i2v", "extend_from": vid["id"], "text": "the camera slowly pans", "seconds": 2,
                            "loras": ["es_ext_walk5b.safetensors"]})
    more = (j.get("results") or [{}])[0]
    check("X9: video_any takes `loras` and records the look and the lock", j["status"] == "done" and LOCK in (more.get("prompt") or "")
          and (more.get("provenance") or {}).get("look") == "realistic"
          and (more.get("provenance") or {}).get("loras") == [{"name": "es_ext_walk5b.safetensors", "strength": 1.0}], j.get("error") or more)
