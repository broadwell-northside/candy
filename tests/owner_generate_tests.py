# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The owner's own likeness, slice 3: pictures, the gates, the private gallery, the kill switch.

Mock engine, drawn pictures, stand-in face worker. The 18+ branches are checked at unit level,
because the test device has the 18+ section locked when these run.
"""
import inspect
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import owner as O  # noqa: E402
from owner_tests import OTHER_FACE, OWNER_FACE, PASSPHRASE, _owner, _refused, _run_plan, _save, frame  # noqa: E402

INJECT = os.environ["FAKE_FACE_INJECT"]


def _sees(person=None, faces=1):
    """Tell the stand-in face worker what it sees in a generated picture. None: read the picture's own code."""
    if person is None:
        if os.path.exists(INJECT):
            os.remove(INJECT)
        return
    with open(INJECT, "w", encoding="utf-8") as f:
        json.dump({"person": person, "faces": faces}, f)


def unit(check):
    # The main run enrols with a face check that declares a real presentation-attack check (a stand-in, "pad"),
    # so the 18+ branches below can run. The pose-only case is tested after it.
    os.environ["FAKE_FACE_LIVENESS"] = "pad"
    try:
        _unit(check)
    finally:
        os.environ.pop("FAKE_FACE_LIVENESS", None)
    _pose_only_unit(check)


def _pose_only_unit(check):
    import owner_generate as G
    import pipelines as P
    out = tempfile.mkdtemp(prefix="es_owner_poses_")
    o = _owner(out)
    got = o.start(32, PASSPHRASE)
    _run_plan(o, got)
    o.commit(got["session"])
    check("an enrolment made with the pose-only live check records its kind", O.match_set(out)["liveness"] == "poses_only" and not o.adult_live_ok())
    check("with a pose-only enrolment the 18+ consent cannot be given",
          O.ADULT_NEEDS == _refused(o.consent_give), _refused(o.consent_give))
    check("with a pose-only enrolment an 18+ likeness job is refused at the gate, whatever else is true",
          _gate(G, P, "adult", o) == O.ADULT_NEEDS and G.gates("default", o) is None, _gate(G, P, "adult", o))
    # a consent record or an open window cannot stand in for it
    o.window = {"owner_id": O.load(out)["owner_id"], "until": 2 ** 40}
    check("... even with the window open", _gate(G, P, "adult", o) == O.ADULT_NEEDS)
    o.faces.stop()
    older = O.match_set(out)
    older.pop("liveness")
    import json as _json
    _json.dump(older, open(os.path.join(O.owner_dir(out), "match_set.json"), "w"))
    check("an enrolment from before the kind was recorded is treated as pose-only", not o.adult_live_ok() and _gate(G, P, "adult", o) == O.ADULT_NEEDS)


def _unit(check):
    print("\n[owner] The output check, the 18+ gates, the lock by hash, the kill switch")
    import face_check
    import loras
    import owner_generate as G
    import owner_policy as OP
    import pipelines as P
    _sees(None)
    out = tempfile.mkdtemp(prefix="es_owner_gen_")
    o = _owner(out)
    got = o.start(32, PASSPHRASE)
    _run_plan(o, got)
    o.commit(got["session"])
    ms = O.match_set(out)
    me = {"faces": 1, "model": o.faces.model, "embedding": o.faces.inspect(_save(frame("face_camera", 5)), "face_camera")["embedding"]}
    other = {"faces": 1, "model": o.faces.model, "embedding": o.faces.inspect(_save(frame("face_camera", 6, OTHER_FACE)), "face_camera")["embedding"]}
    ok, flag = {"status": "ok", "faces": 1, "p_under21": 0.03}, {"status": "flag", "faces": 1, "p_under21": 0.9}

    # D-C-49a, one check per case.
    check("everyday, clear, the owner's face: kept", G.judge("default", ok, me, ms)[0] == "keep")
    verdict, detail = G.judge("default", flag, me, ms)
    check("everyday, flagged, the owner's face: kept, with the override recorded",
          verdict == "keep" and detail["age_override"] == "owner_match" and detail["age_check"] == "flag", detail)
    check("everyday, flagged, another face: deleted", G.judge("default", flag, other, ms)[0] == "discard")
    verdict, said = G.judge("adult", flag, me, ms)
    check("18+, flagged, even with the owner's face: deleted, final, with a retry offered",
          verdict == "discard" and "final" in said and "new seed" in said, said)
    check("18+, clear, the owner's face: kept", G.judge("adult", ok, me, ms)[0] == "keep")
    check("a result the face check judged with another model, or with no model named, is deleted",
          G.judge("default", ok, dict(me, model="another-model"), ms)[0] == "discard"
          and G.judge("default", ok, {k: v for k, v in me.items() if k != "model"}, ms)[0] == "discard")
    check("the 18+ flag case takes no setting and no policy: it cannot be configured away",
          list(inspect.signature(G.judge).parameters) == ["section", "age", "face", "match_set"]
          and "SETTINGS" not in inspect.getsource(G.judge) and "policy_gate" not in inspect.getsource(G))
    for section in ("default", "adult"):
        check("another face is deleted in the %s section" % section, G.judge(section, ok, other, ms)[0] == "discard")
        check("two faces are deleted in the %s section" % section,
              G.judge(section, {"status": "ok", "faces": 2}, me, ms)[0] == "discard"
              and G.judge(section, ok, dict(me, faces=2), ms)[0] == "discard")
        check("no face is deleted in the %s section" % section, G.judge(section, ok, {"faces": 0, "embedding": []}, ms)[0] == "discard")
        for status in ("unchecked", "unavailable", "error", "timeout", "off", "blocked_age_check_unavailable"):
            if G.judge(section, {"status": status, "faces": 1}, me, ms)[0] != "discard":
                check("a result the age check answers '%s' for is deleted (%s)" % (status, section), False)
        check("a result with no age answer, or no match set, is deleted in the %s section" % section,
              G.judge(section, None, me, ms)[0] == "discard" and G.judge(section, ok, me, None)[0] == "discard")

    # The prompt rail of the one-face rule: the owner is implied, so any person in the text is a second one.
    rec = {"stated_age": 32}
    for text in ("on a pier and a tall man beside", "with her husband", "a woman, a man", "kissing a man", "a couple dancing",
                 "two women on a beach", "twins", "a man on a pier"):
        try:
            G.one_person(text, rec)
            said = ""
        except P.UserError as exc:
            said = str(exc)
        check("a likeness prompt that brings in a person is refused: %s" % text, "one person: you" in said, said)
    for text in ("standing on a pier at sunset, linen shirt", "yoga on the beach, morning light", "reading in a cafe"):
        try:
            G.one_person(text, rec)
            said = ""
        except P.UserError as exc:
            said = str(exc)
        check("a scene with nobody else in it passes: %s" % text, said == "", said)

    # The 18+ gates: the consent record and the live-match window.
    check("the everyday section needs neither consent nor a window", G.gates("default", o) is None)
    check("18+ without the consent record is refused", "consent" in _gate(G, P, "adult", o))
    check("consent cannot be given without a live match in the same sitting", "live match" in _refused(o.consent_give))
    live = o.live_start()
    check("a live match is a short plan", len(live["plan"]) == O.LIVE_STEPS)
    nonce = live["nonce"]
    for row in live["plan"]:
        nonce = o.frame(live["session"], row["index"], nonce, frame(row["step"], 40 + row["index"], OTHER_FACE))["nonce"]
    check("a live match with another face opens nothing", "not the enrolled one" in _refused(lambda: o.commit(live["session"])) and not o.window_open())
    live = o.live_start()
    nonce = live["nonce"]
    for row in live["plan"]:
        nonce = o.frame(live["session"], row["index"], nonce, frame(row["step"], 50 + row["index"], replay=row["index"] == 0))["nonce"]
    check("a live match the face check does not call live opens nothing", "did not pass" in _refused(lambda: o.commit(live["session"])) and not o.window_open())
    live = o.live_start()
    _run_plan(o, live)
    done = o.commit(live["session"])
    check("a live match with the enrolled face opens the window", done.get("window") is True and o.window_open())
    check("the live match keeps no picture", not os.path.isdir(os.path.join(O.owner_dir(out), "live"))
          or not [f for _d, _s, fs in os.walk(os.path.join(O.owner_dir(out), "live")) for f in fs])
    check("with the window open but no consent, 18+ is still refused", "consent" in _gate(G, P, "adult", o))
    check("consent is off until it is given", o.consent_valid() is False)
    o.consent_give()
    check("consent given live is a record that verifies", o.consent_valid() is True and _gate(G, P, "adult", o) == "")
    o.window["until"] = 0
    check("when the window runs out, 18+ is refused again", not o.window_open() and "live match" in _gate(G, P, "adult", o))
    path = os.path.join(O.owner_dir(out), "consent_18.json")
    row = json.load(open(path))
    json.dump(dict(row, owner_id="someone-else"), open(path, "w"))
    check("an edited consent record counts as no consent", o.consent_valid() is False)
    json.dump(row, open(path, "w"))
    kept_statement = O.CONSENT_STATEMENT
    O.CONSENT_STATEMENT = kept_statement + " (changed)"
    try:
        check("a changed statement needs consent again", o.consent_valid() is False)
    finally:
        O.CONSENT_STATEMENT = kept_statement
    check("the record verifies again unchanged", o.consent_valid() is True)

    # The private gallery, and withdrawing consent.
    everyday = O.gallery_add(out, _save(frame("face_camera", 60)), {"area": "default", "owner_id": "x"})
    adult = O.gallery_add(out, _save(frame("face_camera", 61)), {"area": "adult", "owner_id": "x"})
    broken = O.gallery_add(out, _save(frame("face_camera", 62)), {"area": "default", "owner_id": "x"})
    open(os.path.join(O.gallery_dir(out), broken["id"] + ".json"), "w").write("{not json")
    check("a gallery record that cannot be read counts as 18+",
          next(r for r in O.gallery_list(out) if r["id"] == broken["id"])["area"] == "adult")
    gone = o.consent_withdraw()
    left = [r["id"] for r in O.gallery_list(out)]
    check("withdrawing consent needs no live match, deletes the 18+ pictures and keeps the everyday ones",
          gone == {"consent_18": False, "removed": 2} and left == [everyday["id"]] and o.consent_valid() is False
          and not os.path.exists(os.path.join(O.gallery_dir(out), adult["file"])), (gone, left))
    check("every likeness record is refused for every destination",
          all(OP.may_leave(everyday, d) is False for d in OP.DESTINATIONS + ("somewhere-new",))
          and OP.may_leave({"id": "ordinary", "role": "made"}, "pack") is True)

    # The lock follows the file's SHA-256.
    loras_dir = os.path.join(O.owner_dir(out), "loras")
    os.makedirs(loras_dir, exist_ok=True)
    lora = os.path.join(loras_dir, "likeness_fast_test.safetensors")
    open(lora, "wb").write(b"likeness weights stand-in " + os.urandom(16))
    sha = O.file_sha256(lora)
    unregistered = OP.lora_refusal(out, lora)
    O.registry_add(out, sha, O.load(out)["owner_id"], os.path.basename(lora), "fast", "sess")
    elsewhere = tempfile.mkdtemp(prefix="es_loras_")
    renamed = os.path.join(elsewhere, "borrowed_style.safetensors")
    shutil.copyfile(lora, renamed)
    plain = os.path.join(elsewhere, "plain_style.safetensors")
    open(plain, "wb").write(b"an ordinary lora")
    OP.leave()
    check("a file in the private LoRA folder is locked even before it is registered", unregistered == OP.NOT_HERE)
    check("the likeness LoRA is refused when no likeness job is running", OP.lora_refusal(out, lora) == OP.NOT_HERE)
    check("a renamed copy in another folder is refused by its hash", OP.lora_refusal(out, renamed) == OP.NOT_HERE)
    check("an ordinary LoRA is not touched by the lock", OP.lora_refusal(out, plain) == "")
    OP.enter(sha, "create")
    check("another job kind cannot load it", OP.lora_refusal(out, renamed) == OP.NOT_HERE)
    OP.enter("00" * 32, OP.OWNER_PICTURE)
    check("a likeness job for another hash cannot load it", OP.lora_refusal(out, renamed) == OP.NOT_HERE)
    OP.enter(sha, OP.OWNER_PICTURE)
    check("the running likeness job can load its own LoRA", OP.lora_refusal(out, lora) == "" and OP.lora_refusal(out, renamed) == "")
    OP.leave()
    lib_dir = tempfile.mkdtemp(prefix="es_comfy_")
    os.makedirs(os.path.join(lib_dir, "models", "loras"))
    shutil.copyfile(lora, os.path.join(lib_dir, "models", "loras", "borrowed_style.safetensors"))
    old_guard = loras.LIKENESS_GUARD
    loras.LIKENESS_GUARD = lambda p: OP.lora_refusal(out, p)
    try:
        try:
            loras.LoraLibrary(lib_dir).check_usable("borrowed_style.safetensors", "zimage", "default")
            said = ""
        except ValueError as exc:
            said = str(exc)
        check("the LoRA library refuses the renamed copy before it reads a sidecar or a name", said == OP.NOT_HERE, said)
    finally:
        loras.LIKENESS_GUARD = old_guard
    # The job itself, on a stand-in engine: it runs only on the engine that reads this disk.
    import comfy_client as cc
    link_dir = os.path.join(lib_dir, "models", "loras")
    engine_out = os.path.join(lib_dir, "output")
    os.makedirs(engine_out)

    class _Engine:
        def __init__(self, lists=True, local=True):
            self.lists, self.local, self.sent, self.named = lists, local, [], []

        def available(self, node, name):
            return sorted(os.listdir(link_dir)) if self.lists else ["my_style_lora.safetensors"]

        def run(self, wf, dest, on_progress=None):
            self.sent.append(wf)
            self.named += [n["inputs"]["lora_name"] for n in wf.values() if "lora_name" in n.get("inputs", {})]
            prefix = next(n["inputs"]["filename_prefix"] for n in wf.values() if n.get("class_type") == "SaveImage")
            name = os.path.basename(prefix) + "_00001_.png"
            picture = _save(frame("face_camera", 70 + len(self.sent)))
            if self.local:
                os.makedirs(os.path.join(engine_out, os.path.dirname(prefix)), exist_ok=True)
                shutil.copyfile(picture, os.path.join(engine_out, os.path.dirname(prefix), name))
            shutil.copyfile(picture, os.path.join(dest, name))
            os.remove(picture)
            return [os.path.join(dest, name)]

    class _Age:
        enabled = True
        answer = ok

        def check(self, path):
            return self.answer

    class _Ctx:
        def __init__(self, engine):
            self.comfy, self.job, self.lib = engine, {"owner": O.load(out)["owner_id"]}, type("L", (), {"root": out})()

        def progress(self, fraction, message=""):
            pass

    def _job(engine, section="default", text="standing on a pier at sunset, linen shirt"):
        P.set_area(section)
        ctx = _Ctx(engine)
        try:
            G.job_owner_picture(ctx, {"text": text, "base": "fast"})
            return "", ctx
        except P.UserError as exc:
            return str(exc), ctx
        finally:
            P.set_area("default")

    def _pictures():
        return len(O.gallery_list(out))

    keep = (P.AGE_GUARD, P.LORA_LIB, P.HARDWARE, G.OWNER, G.COMFY_DIR, loras.LIKENESS_GUARD, loras.LIKENESS_ALLOWED, cc.GRAPH_GUARD)
    age = _Age()
    P.AGE_GUARD, P.LORA_LIB, P.HARDWARE, G.OWNER = age, loras.LoraLibrary(lib_dir), None, o
    loras.LIKENESS_GUARD = lambda path: OP.lora_refusal(out, path)
    loras.LIKENESS_ALLOWED = lambda path: bool(OP.current()) and OP._sha(path) == OP.current()["sha256"]
    try:
        G.COMFY_DIR = None
        check("no engine folders on this computer: refused", "not on this computer" in _job(_Engine())[0])
        G.COMFY_DIR = os.path.join(lib_dir, "nowhere")
        check("an engine folder that is not there: refused", "not on this computer" in _job(_Engine())[0])
        G.COMFY_DIR = lib_dir
        before = _pictures()
        remote = _Engine(lists=False)
        said, _ctx = _job(remote)
        check("an engine that does not read this disk is refused before any prompt is sent to it",
              said == G.NOT_LOCAL and remote.sent == [] and _strays(out, lib_dir) == [] and _pictures() == before, (said, remote.sent))
        far = _Engine(local=False)
        said, _ctx = _job(far)
        check("a result that was not in this computer's engine folder is deleted",
              said == G.NOT_LOCAL_RESULT and _pictures() == before and _strays(out, lib_dir) == [], said)
        here = _Engine()
        said, ctx = _job(here)
        check("on this computer's engine an everyday picture of the owner is kept in the private gallery",
              said == "" and _pictures() == before + 1 and len(ctx.job["owner_results"]) == 1, said)
        check("the engine was given a link under a random name, and no link, download or engine output is left",
              len(here.named) == 1 and here.named[0].startswith("owner_") and _strays(out, lib_dir) == [], here.named)
        check("the excluded engine folder for likeness jobs exists and is out of backups",
              O.backup_excluded(os.path.join(engine_out, G.ENGINE_FOLDER)))
        import safety

        def _violent(section):
            if not hasattr(safety, "check_violence"):  # the no-violence rail, once it is in the same base
                return
            bloody = _Engine()
            said, _ctx = _job(bloody, section, "standing on a pier, covered in blood")
            check("a violent likeness prompt is refused in the %s section, and nothing is sent" % section,
                  "violence" in said and "blood" in said and bloody.sent == [], said)
        _violent("default")
        gated = _Engine()
        said, _ctx = _job(gated, "adult")
        check("18+ without consent and a live match: the job itself refuses, and nothing is sent", "consent" in said and gated.sent == [], said)
        live = o.live_start()
        _run_plan(o, live)
        o.commit(live["session"])
        o.consent_give()
        before = _pictures()
        age.answer = flag
        flagged = _Engine()
        said, _ctx = _job(flagged, "adult")
        check("18+, the whole job: a flagged result is deleted, final, and nothing is kept anywhere",
              said == G.FLAG_FINAL and len(flagged.sent) == 1 and _pictures() == before and _strays(out, lib_dir) == [], said)
        said, _ctx = _job(_Engine(), "default")
        check("everyday, the whole job: the same flag with the owner's face is kept, with the override recorded",
              said == "" and _pictures() == before + 1
              and any((r.get("provenance") or {}).get("age_override") == "owner_match" for r in O.gallery_list(out)), said)
        age.answer = ok
        said, ctx = _job(_Engine(), "adult")
        check("18+, clear, consent and a live match: kept, marked 18+",
              said == "" and [r["area"] for r in O.gallery_list(out) if r["id"] in ctx.job["owner_results"]] == ["adult"], said)
        _violent("adult")  # with the consent given and the window open, so the rail is what refuses
        _sees(OTHER_FACE)
        said, _ctx = _job(_Engine(), "adult")
        _sees(None)
        check("18+, another face in the result: deleted", said != "" and _strays(out, lib_dir) == [], said)

        # A graph that names a LoRA file itself (a raw workflow) meets the same lock, before it is posted.
        def graph(name):
            return {"3": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": name, "strength_model": 1.0}},
                    "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "a pier at sunset"}}}
        open(os.path.join(link_dir, "plain_style.safetensors"), "wb").write(b"an ordinary lora")
        os.symlink(elsewhere, os.path.join(link_dir, "sub"))
        check("a raw graph that names the renamed copy is refused", OP.graph_refusal(out, link_dir, graph("borrowed_style.safetensors")) == OP.NOT_HERE)
        check("... also through a linked folder", OP.graph_refusal(out, link_dir, graph("sub/borrowed_style.safetensors")) == OP.NOT_HERE)
        check("a raw graph with an ordinary LoRA, or none, is not refused",
              OP.graph_refusal(out, link_dir, graph("plain_style.safetensors")) == ""
              and OP.graph_refusal(out, link_dir, graph("not_there.safetensors")) == ""
              and OP.graph_refusal(out, link_dir, {"4": graph("x")["4"]}) == "" and OP.graph_refusal(out, None, graph("x")) == "")
        os.symlink(lora, os.path.join(link_dir, "owner_test_link.safetensors"))
        check("another job that names the likeness job's link is refused",
              OP.graph_refusal(out, link_dir, graph("owner_test_link.safetensors")) == OP.NOT_HERE)
        cc.GRAPH_GUARD = lambda wf: OP.graph_refusal(out, link_dir, wf)
        try:
            cc.ComfyClient("http://127.0.0.1:9").queue(graph("borrowed_style.safetensors"))
            said = ""
        except cc.ComfyError as exc:
            said = str(exc)
        check("the engine client asks the lock before it posts a graph", said == OP.NOT_HERE, said)

        # The sweep at startup and after a job.
        mine = os.path.join(link_dir, "owner_my_own_style.safetensors")
        open(mine, "wb").write(b"a file somebody put there")
        for folder in (os.path.join(O.owner_dir(out), "tmp", "t1"), os.path.join(O.owner_dir(out), "live", "l1"),
                       os.path.join(engine_out, G.ENGINE_FOLDER, "j1")):
            os.makedirs(folder, exist_ok=True)
            open(os.path.join(folder, "left.png"), "wb").write(b"x")
        open(os.path.join(engine_out, "ownerimgabc_00001_.png"), "wb").write(b"x")
        G.sweep(out, link_dir)
        check("the sweep leaves no link, download, live frame or engine output", _strays(out, lib_dir) == ["owner_my_own_style.safetensors"]
              and not os.path.exists(os.path.join(O.owner_dir(out), "live")), _strays(out, lib_dir))
        check("the sweep removes links only: a plain file with a like name is not deleted", os.path.isfile(mine))
        os.remove(mine)
        os.remove(os.path.join(link_dir, "sub"))
    finally:
        P.AGE_GUARD, P.LORA_LIB, P.HARDWARE, G.OWNER, G.COMFY_DIR, loras.LIKENESS_GUARD, loras.LIKENESS_ALLOWED, cc.GRAPH_GUARD = keep
        P.set_area("default")
        OP.leave()


    lora2 = O.usable_lora(out, O.load(out)["owner_id"], "fast")
    open(lora, "ab").write(b"tampered")
    check("a registered LoRA is usable only while the file still has its hash",
          lora2 is not None and O.usable_lora(out, O.load(out)["owner_id"], "fast") is None)

    # The kill switch.
    os.symlink(lora, os.path.join(link_dir, "owner_leftover.safetensors"))
    current = O.file_sha256(lora)  # the file as it is now, after the change above
    os.makedirs(os.path.join(link_dir, "styles"))
    stray = os.path.join(link_dir, "styles", "summer_look.safetensors")
    shutil.copyfile(lora, stray)
    ordinary = os.path.join(link_dir, "plain_style.safetensors")
    os.symlink(link_dir, os.path.join(link_dir, "styles", "back_to_the_top"))  # a link that loops
    done = o.remove_everything(link_dir)
    check("the kill switch leaves no file in the likeness folder and nobody enrolled",
          done["left"] == 0 and not os.path.exists(O.owner_dir(out)) and not O.enrolled(out) and done["removed"]["captures"] == O.PLAN_STEPS, done)
    check("it removes a leftover link in the engine's LoRA folder", not os.path.lexists(os.path.join(link_dir, "owner_leftover.safetensors")))
    check("it deletes a plain copy of the LoRA in the engine's LoRA folder, whatever its name, and no other file",
          not os.path.exists(stray) and os.path.isfile(ordinary) and done["removed"]["copies"] >= 1, done)
    check("that copy's hash is revoked too", current in O.revoked_hashes(out))
    check("it ends the window, the unlocks and the consent", not o.window_open() and not o.consent_valid() and o.unlocks == {})
    check("the deleted LoRA's hash is revoked: a stray copy is refused for good, likeness job or not", _revoked(OP, out, renamed, sha))
    tomb = json.load(open(os.path.join(out, O.REMOVED_FILE)))
    check("the tombstone holds counts and no file names", tomb["left"] == 0 and set(tomb["removed"]) == {"loras", "pictures", "captures", "copies"})
    again = o.start(41, PASSPHRASE)
    _run_plan(o, again)
    check("after the kill switch a fresh enrolment starts from zero", o.commit(again["session"])["enrolled"] is True and O.load(out)["stated_age"] == 41)
    o.faces.stop()
    del face_check


def _gate(G, P, section, o):
    try:
        G.gates(section, o)
    except P.UserError as exc:
        return str(exc)
    return ""


def _revoked(OP, out, path, sha):
    OP.leave()
    first = OP.lora_refusal(out, path) == OP.REVOKED
    OP.enter(sha, OP.OWNER_PICTURE)
    second = OP.lora_refusal(out, path) == OP.REVOKED
    OP.leave()
    return first and second


def _strays(out, comfy_dir):
    """Every plain copy a likeness job could leave behind, outside the private gallery."""
    found = [f for f in os.listdir(os.path.join(comfy_dir, "models", "loras")) if f.startswith("owner_")]
    eng = os.path.join(comfy_dir, "output")
    found += [f for f in os.listdir(eng) if f.startswith("ownerimg")]
    found += [os.path.join(d, f) for d, _s, fs in os.walk(os.path.join(eng, "owner_jobs")) for f in fs]
    found += [os.path.join(d, f) for d, _s, fs in os.walk(os.path.join(O.owner_dir(out), "tmp")) for f in fs]
    return found


def e2e(a, out, comfy_dir, mock_url):
    import requests
    check = a.check
    print("\n[owner] Pictures of the owner through the app: gates, the output check, no stray copy, the kill switch")
    pic = {"text": "standing on a pier at sunset, linen shirt", "base": "fast", "seed": 77}
    shared_before = len(a.get("/api/gallery", params={"limit": 2000}).json()["items"])
    a.post("/api/owner/lock")
    job = a.job("owner_picture", pic)
    check("a likeness picture is refused without an unlock", job["status"] == "refused" and "Unlock" in (job.get("error") or ""), job.get("error"))
    check("the private gallery is closed without an unlock", a.get("/api/owner/gallery").status_code == 400)
    a.post("/api/owner/unlock", json={"passphrase": PASSPHRASE})
    _sees(OWNER_FACE)
    for text, words in (("on a pier and a tall man beside", "one person"), ("a teen on a pier", "minor")):
        job = a.job("owner_picture", dict(pic, text=text))
        check("a likeness prompt is refused: %s" % words, job["status"] in ("error", "refused") and words in (job.get("error") or "").lower(), job.get("error"))
    job = a.job("owner_picture", dict(pic, area_note="everyday"), area="adult")
    check("an 18+ likeness job is refused on this device (the 18+ section is locked; the gates are unit-tested)", job["status"] in ("error", "refused"))

    job = a.job("owner_picture", pic, timeout=180)
    check("a picture of the owner is made in the everyday section", job["status"] == "done" and not job.get("results"), job.get("error"))
    graph = requests.get(mock_url + "/mock/log").json()[-1]
    used = [n["inputs"].get("lora_name") for n in graph.values() if n.get("class_type") == "LoraLoaderModelOnly"]
    text = json.dumps(graph)
    check("the engine got the likeness LoRA under a job-scoped name, and the child and teen avoid-words",
          len(used) == 1 and used[0].startswith("owner_") and "child" in text and "teen" in text and "nudity" in text, used)
    check("the job record keeps no graph: the prompt and the LoRA name cannot be read back from it",
          job.get("has_workflow") is False and a.get("/api/jobs/%s/workflow" % job["id"]).json() == {"workflows": []})
    items = a.get("/api/owner/gallery").json()["items"]
    check("the picture is in the private gallery, marked everyday", len(items) == 1 and items[0]["area"] == "default", items)
    got = a.get(items[0]["url"])
    check("the owner can open it, and the answer may not be cached",
          got.status_code == 200 and got.content[:4] == b"\x89PNG" and got.headers.get("cache-control") == "no-store", got.headers.get("cache-control"))
    check("it is not in the shared gallery, so no ordinary job or export can reach it",
          len(a.get("/api/gallery", params={"limit": 2000}).json()["items"]) == shared_before)
    check("no link, download or engine output is left after the job", _strays(out, comfy_dir) == [], _strays(out, comfy_dir))

    for person, faces, words in ((OTHER_FACE, 1, "not the enrolled one"), (OWNER_FACE, 2, "exactly one face"), (OWNER_FACE, 0, "exactly one face")):
        _sees(person, faces)
        job = a.job("owner_picture", dict(pic, seed=78), timeout=180)
        check("a result is deleted when it shows %s" % ("another face" if person == OTHER_FACE else "%d faces" % faces),
              job["status"] == "error" and words in (job.get("error") or "") and "new seed" in (job.get("error") or ""), job.get("error"))
    _sees(OWNER_FACE)
    job = a.job("owner_picture", dict(pic, text="uncheckedtest on a pier", seed=79), timeout=180)
    check("a result the age check cannot read is deleted", job["status"] == "error" and "could not clear" in (job.get("error") or ""), job.get("error"))
    check("the refused results left nothing: one picture in the gallery, no stray copy",
          len(a.get("/api/owner/gallery").json()["items"]) == 1 and _strays(out, comfy_dir) == [], _strays(out, comfy_dir))
    job = a.job("owner_picture", dict(pic, text="magentatest on a pier", seed=80), timeout=180)
    items = a.get("/api/owner/gallery").json()["items"]
    check("everyday: a flagged result that is the owner's face is kept unblurred, with the override recorded",
          job["status"] == "done" and len(items) == 2 and items[0]["age_override"] == "owner_match", (job.get("error"), items))
    _sees(OTHER_FACE)
    job = a.job("owner_picture", dict(pic, text="magentatest on a pier", seed=81), timeout=180)
    check("everyday: a flagged result with another face is deleted", job["status"] == "error" and len(a.get("/api/owner/gallery").json()["items"]) == 2)
    _sees(OWNER_FACE)

    # The lock by hash, through the app: a renamed copy in the shared LoRA folder.
    private = O.private_lora_files(out)[0]
    borrowed = os.path.join(comfy_dir, "models", "loras", "borrowed_style.safetensors")
    shutil.copyfile(private, borrowed)
    dna = {"gender": "woman", "age": 32, "style": "photo", "name": "Mara"}
    used = a.job("create", {"dna": dna, "count": 1, "advanced": {"loras": [{"name": "borrowed_style.safetensors", "strength": 0.6}]}})
    check("an ordinary job cannot load a renamed copy of the likeness LoRA", used["status"] in ("error", "refused")
          and "own likeness" in (used.get("error") or ""), used.get("error"))
    made = a.job("create", {"dna": dna, "count": 1})
    wf = json.load(open(os.path.join(HERE, "..", "app", "workflows", "remove_bg_api.json")))
    for node in wf.values():
        if node["class_type"] == "LoadImage":
            node["inputs"]["image"] = "es_%s.png" % (made["results"][0]["id"] if made.get("results") else "none")
    ran = a.job("raw", {"workflow": wf})
    wf["9001"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "borrowed_style.safetensors", "strength_model": 0.6}}
    sent = len(requests.get(mock_url + "/mock/log").json())
    used = a.job("raw", {"workflow": wf})
    check("the same raw workflow without that LoRA runs", ran["status"] == "done", ran.get("error"))
    check("a raw workflow that names the renamed copy is refused, and the engine is sent nothing",
          used["status"] in ("error", "refused") and "own likeness" in (used.get("error") or "")
          and len(requests.get(mock_url + "/mock/log").json()) == sent, used.get("error"))

    # The live match and the consent routes.
    check("consent cannot be given without the 18+ section open on this device",
          a.post("/api/owner/consent", json={"give": True}).status_code == 400)
    check("the consent route takes a plain yes or no: anything else changes nothing",
          a.post("/api/owner/consent", json={}).status_code == 400 and a.post("/api/owner/consent", json={"give": "no"}).status_code == 400)
    _sees(None)
    live = a.post("/api/owner/live/start").json()
    nonce, good = live["nonce"], True
    for row in live["plan"]:
        back = a.post("/api/owner/enrol/frame", files={"file": ("f.png", frame(row["step"], 90 + row["index"]), "image/png")},
                      data={"session": live["session"], "index": str(row["index"]), "nonce": nonce})
        good = good and back.status_code == 200
        nonce = back.json().get("nonce") if back.status_code == 200 else nonce
    done = a.post("/api/owner/enrol/commit", json={"session": live["session"]})
    st = a.get("/api/owner/status").json()
    check("a live match through the app opens the window, and consent stays off",
          good and done.status_code == 200 and done.json().get("window") is True and st["window_open"] is True and st["consent_18"] is False, done.text[:200])
    a.post("/api/owner/lock")
    check("after Lock the gallery and its files are closed again",
          a.get("/api/owner/gallery").status_code == 400 and a.get(items[0]["url"]).status_code == 404)

    # The kill switch, last: then a fresh enrolment from zero.
    sha = O.file_sha256(private)
    spare = os.path.join(tempfile.mkdtemp(prefix="es_spare_"), "kept_elsewhere.safetensors")
    shutil.copyfile(private, spare)
    wrong = a.s.request("DELETE", a.base + "/api/owner/likeness", json={"confirm": "please"}, timeout=60)
    check("the kill switch needs an unlock or the typed words", wrong.status_code == 400 and O.enrolled(out))
    gone = a.s.request("DELETE", a.base + "/api/owner/likeness", json={"confirm": "delete my likeness"}, timeout=60)
    check("the typed words delete everything without the passphrase",
          gone.status_code == 200 and gone.json()["left"] == 0 and gone.json()["removed"]["pictures"] == 2
          and not os.path.exists(O.owner_dir(out)), gone.text[:300])
    st = a.get("/api/owner/status").json()
    check("nobody is enrolled afterwards", st["enrolled"] is False and st["consent_18"] is False and st["window_open"] is False, st)
    check("the LoRA's hash is revoked", sha in O.revoked_hashes(out))
    check("the kill switch deleted the plain copy in the engine's LoRA folder", not os.path.exists(borrowed) and gone.json()["removed"]["copies"] == 1, gone.text[:200])
    shutil.copyfile(spare, borrowed)  # a copy kept somewhere else and brought back
    used = a.job("create", {"dna": dna, "count": 1, "advanced": {"loras": [{"name": "borrowed_style.safetensors", "strength": 0.6}]}})
    check("a copy brought back later is refused for good", used["status"] in ("error", "refused")
          and "deleted" in (used.get("error") or ""), used.get("error"))
    os.remove(borrowed)
    check("no stray copy is left after the kill switch", _strays(out, comfy_dir) == [])
    got = a.post("/api/owner/enrol/start", json={"age": 33, "passphrase": PASSPHRASE})
    plan, nonce, sid, good = got.json().get("plan") or [], got.json().get("nonce"), got.json().get("session"), got.status_code == 200
    for row in plan:
        back = a.post("/api/owner/enrol/frame", files={"file": ("f.png", frame(row["step"], 120 + row["index"]), "image/png")},
                      data={"session": sid, "index": str(row["index"]), "nonce": nonce})
        good = good and back.status_code == 200
        nonce = back.json().get("nonce") if back.status_code == 200 else nonce
    done = a.post("/api/owner/enrol/commit", json={"session": sid})
    check("a fresh enrolment from zero works after the kill switch", good and done.status_code == 200 and done.json().get("enrolled") is True, done.text[:200])
