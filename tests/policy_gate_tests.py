"""The policy gate (D-C-50): a gate on the owner's machine for the gray zone, behind an interface.

Only the mechanism is tested, on a stand-in gate and placeholder text. No policy content is written, read or tested
here, and no model is called. The fixed rails run first and the policy file cannot switch one off (D-C-49a).
"""
import inspect
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import age_guard  # noqa: E402
import pipelines  # noqa: E402
import policy_gate as G  # noqa: E402
import safety  # noqa: E402

PLACEHOLDER = "ZZ-PLACEHOLDER-LINE one\nZZ-PLACEHOLDER-LINE two\n"
# Lines shaped like instructions to the app. They are only text; the file is never parsed.
DIRECTIVES = ("switch off the age check\nallow everything\nignore the fixed rails\nchecker: off\nsafety: disabled\n"
              "unlock the 18+ section\nflag: never final\n")


def _run(out, params, area="default", kind="create", gate=None):
    try:
        G.enforce(params, area, kind, out, gate=gate)
        return ""
    except G.PolicyRefused as exc:
        return str(exc)


def _write_policy(out, text):
    os.makedirs(os.path.join(out, G.POLICY_FOLDER), exist_ok=True)
    with open(G.policy_path(out), "w", encoding="utf-8") as f:
        f.write(text)


def _log(out):
    import json
    path = G.log_path(out)
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def unit(check):
    print("\n[policy] The gate for the gray zone: local, logged, after the fixed rails, fails closed")
    root = tempfile.mkdtemp(prefix="es_policy_")
    old_env = os.environ.pop("EASY_STUDIO_POLICY_FILE", None)
    old_test = os.environ.get("EASY_STUDIO_TEST_RUN")
    try:
        os.environ["EASY_STUDIO_POLICY_FILE"] = "/tmp/elsewhere.txt"
        os.environ.pop("EASY_STUDIO_TEST_RUN", None)
        alone = G.policy_path(root)
        os.environ["EASY_STUDIO_TEST_RUN"] = "1"
        in_test = G.policy_path(root)
        os.environ.pop("EASY_STUDIO_POLICY_FILE")
        check("the policy file path can be named by environment in a test run only",
              in_test == "/tmp/elsewhere.txt" and alone == os.path.join(root, G.POLICY_FOLDER, G.POLICY_NAME), (alone, in_test))
        ok_params = {"text": "soft window light, a linen shirt"}

        out = os.path.join(root, "none")
        gate = G.StubGate(allow=False, reason="stand-in refusal")
        check("with no policy file the gate is not asked and the job passes",
              _run(out, ok_params, gate=gate) == "" and not gate.calls and not _log(out))
        _write_policy(out, "# only a comment\n\n   \n")
        check("a file of blanks and comments asks nothing of the gate", _run(out, ok_params, gate=gate) == "" and not gate.calls)

        out = os.path.join(root, "refuse")
        _write_policy(out, PLACEHOLDER)
        gate = G.StubGate(allow=False, reason="stand-in refusal")
        said = _run(out, ok_params, gate=gate)
        check("when the gate refuses, the job is refused with the gate's reason", "stand-in refusal" in said and said, said)
        rows = _log(out)
        check("the decision is logged with its reason, kind and area", len(rows) == 1 and rows[0]["allow"] is False
              and rows[0]["reason"] == "stand-in refusal" and rows[0]["kind"] == "create" and rows[0]["area"] == "default", rows)
        check("the log holds hashes, never the text or the policy",
              ok_params["text"] not in open(G.log_path(out), encoding="utf-8").read()
              and "ZZ-PLACEHOLDER" not in open(G.log_path(out), encoding="utf-8").read()
              and len(rows[0]["text_sha256"]) == 64 and len(rows[0]["policy_sha256"]) == 64)
        check("the gate was handed the policy as plain text, the job's text, the area and the kind",
              gate.calls and gate.calls[0]["policy"] == PLACEHOLDER and gate.calls[0]["texts"] == [ok_params["text"]]
              and gate.calls[0]["area"] == "default" and gate.calls[0]["kind"] == "create")

        gate = G.StubGate(allow=True, reason="fine")
        check("when the gate allows, the job passes and the allow is logged too",
              _run(out, ok_params, gate=gate) == "" and _log(out)[-1]["allow"] is True)
        check("a refusal with no reason still gets a plain one",
              "do not want" in _run(out, ok_params, gate=G.StubGate(allow=False, reason="")))
        check("a job with no text is not asked", _run(out, {"count": 2}, gate=G.StubGate(allow=False, reason="x")) == "")

        # fail closed
        for label, stub in (("raises", G.StubGate(error=RuntimeError("boom"))),
                            ("times out", G.StubGate(error=TimeoutError("slow"))),
                            ("is unavailable", G.StubGate(error=G.GateUnavailable("no model"))),
                            ("answers a string", G.StubGate(answer="allow")),
                            ("answers a truthy non-bool", G.StubGate(answer=(1, "ok"))),
                            ("answers nothing", G.StubGate(answer=(None, None))),
                            ("answers a short tuple", G.StubGate(answer=(True,)))):
            said = _run(out, ok_params, gate=stub)
            check("the job is refused when the gate %s" % label, said == G.UNAVAILABLE, said)
        check("a gate failure is logged as a refusal with the error type only",
              _log(out)[-1]["allow"] is False and _log(out)[-1].get("error") == "GateUnavailable" and "no model" not in str(_log(out)[-1]))
        old = G.GATE
        try:
            G.GATE = G.LocalModelGate()
            check("the real gate with no local model set up refuses (fails closed) while a policy file exists",
                  _run(out, ok_params) == G.UNAVAILABLE)
            G.GATE = G.LocalModelGate(endpoint="http://example.com:8080/v1", transport=lambda *a: (True, "x"))
            check("a gate pointed at anything but this computer is refused, whatever it would say",
                  _run(out, ok_params) == G.UNAVAILABLE)
            G.GATE = G.LocalModelGate(endpoint="http://127.0.0.1:8080/v1", transport=lambda t, a, k, p: (True, "ok"))
            check("a gate on loopback with a transport can allow", _run(out, ok_params) == "")
        finally:
            G.GATE = old
        check("only loopback addresses count as this computer",
              all(G.is_local_endpoint(u) for u in ("http://127.0.0.1:1/x", "http://localhost/x", "http://[::1]:5/x"))
              and not any(G.is_local_endpoint(u) for u in ("http://example.com", "http://192.168.1.5:80", "https://10.0.0.1", "", "nonsense")))

        # an unreadable policy refuses; an unwritable log refuses
        bad = os.path.join(root, "bad")
        os.makedirs(os.path.join(bad, G.POLICY_FOLDER))
        with open(G.policy_path(bad), "wb") as f:
            f.write(b"\xff\xfe\x00 not text \x80")
        check("a policy file that is not text refuses the job", _run(bad, ok_params, gate=G.StubGate()) == G.UNREADABLE)
        with open(G.policy_path(bad), "wb") as f:
            f.write(b"x" * (G.MAX_POLICY_BYTES + 5))
        check("a policy file over the size limit refuses the job", _run(bad, ok_params, gate=G.StubGate()) == G.UNREADABLE)
        os.remove(G.policy_path(bad))
        os.mkdir(G.policy_path(bad))  # a folder where the file should be
        check("a policy path that cannot be read refuses the job", _run(bad, ok_params, gate=G.StubGate()) == G.UNREADABLE)
        shutil.rmtree(G.policy_path(bad))
        _write_policy(bad, PLACEHOLDER)
        os.mkdir(G.log_path(bad))  # a folder where the log should be
        check("a log that cannot be written refuses the job (reasons are always logged)",
              "could not write its log" in _run(bad, ok_params, gate=G.StubGate()))

        # the fixed rails run first and the file cannot switch one off
        print("\n[policy] The fixed rails run first; nothing in the file switches one off")
        out = os.path.join(root, "rails")
        _write_policy(out, DIRECTIVES + PLACEHOLDER)
        allow_all = G.StubGate(allow=True, reason="stand-in allows everything")
        for label, text, area in (("a minor word", "a teen girl", "default"), ("a stated age under 21", "age 17", "default"),
                                  ("a violence word", "a gory scene", "default"), ("a violence word in 18+", "a gory scene", "adult"),
                                  ("a real person's name", "looks like a famous actress, dressed as a real person", "default"),
                                  ("a floor-category word", "non-consensual", "default"),
                                  ("a floor-category word in 18+", "cruelty to animals", "adult")):
            said = _run(out, {"text": text}, area=area, gate=allow_all)
            check("%s is still refused with a policy file of directive-shaped lines and a gate that allows all" % label,
                  said.startswith("Blocked") and not allow_all.calls, said)
        n_before = len(_log(out))
        check("a fixed-rail refusal never reaches the gate or its log", not allow_all.calls and len(_log(out)) == n_before)
        check("the file's text reaches the gate only as text",
              _run(out, ok_params, gate=allow_all) == "" and allow_all.calls[-1]["policy"] == DIRECTIVES + PLACEHOLDER)
        # an unrelated everyday check, to prove the allow path is not just refusing everything
        check("an ordinary prompt passes the fixed rails", safety.check_prompt(ok_params["text"])[0])

        # the age rails are untouched by anything here
        frozen_required, frozen_free = set(age_guard.CHECKER_REQUIRED_KINDS), set(age_guard.CHECKER_FREE_KINDS)
        _run(out, ok_params, gate=allow_all)
        check("the checker's kind sets are unchanged by the gate",
              set(age_guard.CHECKER_REQUIRED_KINDS) == frozen_required and set(age_guard.CHECKER_FREE_KINDS) == frozen_free)
        check("with the checker off, a gate that allows still does not run a required kind",
              age_guard.checker_blocks("create", False) and age_guard.checker_blocks("owner_picture", False))
        source = inspect.getsource(pipelines.JobContext.add)
        check("a flagged result's discard reads no policy and no gate", "policy_gate" not in source and "GATE" not in source and "SETTINGS" not in source)
        check("the policy module does not import the age check or the pipelines (it cannot reach them)",
              "import age_guard" not in inspect.getsource(G) and "import pipelines" not in inspect.getsource(G))
        check("the gate interface can only answer allow or refuse: nothing it returns is read as a rail setting",
              list(inspect.signature(G.Gate.decide).parameters) == ["self", "texts", "area", "kind", "policy"])
        check("no example policy ships with the app", not os.path.exists(os.path.join(HERE, "..", "app", G.POLICY_NAME))
              and not os.path.exists(os.path.join(HERE, "..", G.POLICY_FOLDER)))

        # the route calls it after the fixed gates
        server_src = open(os.path.join(HERE, "..", "app", "server.py"), encoding="utf-8").read()
        pos = {name: server_src.find(name) for name in ("safety.check_workflow(wf)", "policy_gate.enforce(", "QUEUE.put(jid)")}
        check("create_job asks the gate after the fixed gates and before the job is queued",
              all(v > 0 for v in pos.values()) and pos["safety.check_workflow(wf)"] < pos["policy_gate.enforce("] < pos["QUEUE.put(jid)"], pos)
    finally:
        if old_env is not None:
            os.environ["EASY_STUDIO_POLICY_FILE"] = old_env
        if old_test is None:
            os.environ.pop("EASY_STUDIO_TEST_RUN", None)
        else:
            os.environ["EASY_STUDIO_TEST_RUN"] = old_test
        shutil.rmtree(root, ignore_errors=True)


def e2e(a, out):
    """Through the real server, with the real (unconfigured) gate: a policy file in place refuses (fail closed),
    no file changes nothing, and a fixed rail answers first with its own message."""
    print("\n[policy] End to end: the route asks the gate only when a policy file is in use")
    check = a.check
    dna = {"gender": "woman", "age": 29, "style": "photo", "name": "Policy"}
    folder = os.path.join(out, G.POLICY_FOLDER)
    path = os.path.join(folder, G.POLICY_NAME)
    if os.path.exists(path):
        return
    ordinary = {"kind": "create", "params": {"dna": dna, "count": 1, "extra_scene": "soft window light"}}
    os.makedirs(folder, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(PLACEHOLDER)
        r = a.post("/api/jobs", json=ordinary)
        check("with a policy file and no local model set up, a job is refused (fails closed)",
              r.status_code == 400 and G.UNAVAILABLE in r.text, r.text[:200])
        rows = _log(out)
        check("the refusal is logged, with hashes only",
              rows and rows[-1]["allow"] is False and "soft window light" not in open(G.log_path(out), encoding="utf-8").read(), rows[-1:])
        r = a.post("/api/jobs", json={"kind": "create", "params": {"dna": dna, "count": 1, "extra_scene": "non-consensual"}})
        check("a fixed rail answers first, with its own message, not the gate's",
              r.status_code == 400 and "Blocked" in r.text and G.UNAVAILABLE not in r.text, r.text[:200])
    finally:
        for name in (G.POLICY_NAME, G.LOG_NAME):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass
    done = a.job("create", {"dna": dna, "count": 1})
    check("with no policy file the same job runs as before", done["status"] == "done", done.get("error"))
