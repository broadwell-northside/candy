# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The owner's own likeness, slice 2: the trainer self-test and likeness training.

Nothing trains here. The trainer is the stand-in the other training tests use
(tests/fake_trainer_run.py), and the pictures are the drawn frames of owner_tests.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import owner as O  # noqa: E402
from owner_tests import PASSPHRASE  # noqa: E402


def unit(check):
    print("\n[owner] The likeness registry and where the trainer runs")
    import machine_profiles
    import trainer as T
    old = os.environ.get("EASY_STUDIO_MACHINE")
    try:
        for profile, device in (("m5_max", "mps"), ("rtx_pro_6000", "cuda:0"), ("rtx_4090", "cuda:0")):
            os.environ["EASY_STUDIO_MACHINE"] = profile
            job_dir = tempfile.mkdtemp(prefix="es_cfg_")
            cfg = json.load(open(T.write_config(job_dir, "n", "fast", "trig", os.path.join(job_dir, "ds"))))
            check("the trainer's device on %s is %s" % (profile, device),
                  machine_profiles.active()["id"] == profile and cfg["config"]["process"][0]["device"] == device,
                  cfg["config"]["process"][0]["device"])
    finally:
        if old is None:
            os.environ.pop("EASY_STUDIO_MACHINE", None)
        else:
            os.environ["EASY_STUDIO_MACHINE"] = old

    out = tempfile.mkdtemp(prefix="es_owner_reg_")
    check("an empty registry knows no likeness", O.registry(out) == [] and not O.is_likeness_hash(out, "ab" * 32))
    entry = O.registry_add(out, "ab" * 32, "owner1", "likeness_fast.safetensors", "fast", "sess1")
    rows = O.registry(out)
    check("a registered LoRA is found by its SHA-256, with a signature that verifies",
          len(rows) == 1 and rows[0]["valid"] is True and rows[0]["owner_likeness"] is True and O.is_likeness_hash(out, "ab" * 32)
          and entry["mac"] == rows[0]["mac"])
    check("another hash is not a likeness", not O.is_likeness_hash(out, "cd" * 32))
    path = os.path.join(O.owner_dir(out), "likeness_registry.json")
    data = json.load(open(path))
    data[0]["owner_id"] = "someone-else"
    json.dump(data, open(path, "w"))
    rows = O.registry(out)
    check("an edited entry no longer verifies, and still counts as a likeness (the lock fails closed)",
          rows[0]["valid"] is False and O.is_likeness_hash(out, "ab" * 32))
    import routes_owner
    check("the owner job kinds are the trainer and the picture job", routes_owner.OWNER_JOB_KINDS == ("owner_train", "owner_picture"))
    import age_guard
    check("both new job kinds refuse while the appearance checker is off",
          {"owner_train", "owner_train_selftest"} <= age_guard.CHECKER_REQUIRED_KINDS)


def _owner_files(out, sub):
    folder = os.path.join(O.owner_dir(out), sub)
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


def e2e(a, out):
    check = a.check
    print("\n[owner] The trainer self-test, then likeness training from the enrolment pictures only")
    train = {"base": "fast", "trigger": "ownershore"}
    a.post("/api/owner/lock")
    job = a.job("owner_train", train)
    check("likeness training is refused without an unlock", job["status"] == "refused" and "Unlock" in (job.get("error") or ""), job.get("error"))
    check("the unlock works", a.post("/api/owner/unlock", json={"passphrase": PASSPHRASE}).status_code == 200)
    job = a.job("owner_train", train)
    check("likeness training is refused before the trainer self-test has passed",
          job["status"] in ("error", "refused") and "self-test" in (job.get("error") or ""), job.get("error"))
    st = a.get("/api/owner/trainer").json()
    check("the trainer status says: installed, the Mac's device, no self-test yet",
          st["trainer_installed"] is True and st["device"] == "mps" and st["selftest_passed"] is False and st["likeness_loras"] == 0, st)
    test = a.job("owner_train_selftest", {"base": "fast"}, timeout=180)
    rec = json.load(open(os.path.join(out, "trainer_selftest.json")))
    check("the trainer self-test runs on drawn shapes and records pass, device and seconds",
          test["status"] == "done" and rec["ok"] is True and rec["device"] == "mps" and isinstance(rec["seconds"], (int, float)), (test.get("error"), rec))
    check("the self-test leaves no trained file behind", not [f for f in os.listdir(os.path.join(out, "tmp")) if f.startswith("selftest_")])
    check("the status now says the self-test passed", a.get("/api/owner/trainer").json()["selftest_passed"] is True)

    for bad, words in (({"base": "video", "trigger": "ownershore"}, "base"), ({"base": "fast", "trigger": "x"}, "trigger"),
                       ({"base": "fast", "trigger": "teen"}, "minor")):
        job = a.job("owner_train", bad)
        check("likeness training refuses a bad request (%s)" % words, job["status"] in ("error", "refused") and words in (job.get("error") or "").lower(), job.get("error"))

    record = O.load(out)
    folder = os.path.join(O.owner_dir(out), "captures", record["capture_session"])
    victim = os.path.join(folder, "03.png")
    original = open(victim, "rb").read()
    with open(victim, "ab") as f:
        f.write(b"changed")
    try:
        job = a.job("owner_train", train)
    finally:
        with open(victim, "wb") as f:
            f.write(original)
    check("a changed enrolment picture stops training", job["status"] in ("error", "refused") and "changed or removed" in (job.get("error") or ""), job.get("error"))

    inject = os.environ.get("MOCK_AGE_INJECT")
    if inject:
        try:
            with open(inject, "w", encoding="utf-8") as f:
                json.dump({"apply": "still", "result": {"status": "flag", "faces": 1, "p_under21": 0.93}}, f)
            job = a.job("owner_train", train)
        finally:
            if os.path.exists(inject):
                os.remove(inject)
        check("a flag at the age re-check right before training stops the run",
              job["status"] in ("error", "refused") and "flagged by the age check" in (job.get("error") or ""), job.get("error"))
    check("no refused run left a LoRA or a training folder", _owner_files(out, "loras") == [] and _owner_files(out, "training") == [],
          (_owner_files(out, "loras"), _owner_files(out, "training")))

    shared_before = sorted(row["name"] for row in a.get("/api/loras").json()["loras"])
    items_before = len(a.get("/api/gallery", params={"limit": 2000}).json()["items"])
    job = a.job("owner_train", dict(train, items=["made-up-id"], caption="ignored"), timeout=180)
    check("likeness training runs from the enrolment pictures", job["status"] == "done", job.get("error"))
    loras = [f for f in _owner_files(out, "loras") if f.endswith(".safetensors")]
    check("the LoRA is saved in the private folder, readable by this account only",
          len(loras) == 1 and (os.stat(os.path.join(O.owner_dir(out), "loras", loras[0])).st_mode & 0o777) == 0o600, loras)
    if loras:
        sha = O.file_sha256(os.path.join(O.owner_dir(out), "loras", loras[0]))
        rows = O.registry(out)
        check("the registry holds it by SHA-256, signed, tagged as the owner's likeness",
              len(rows) == 1 and rows[0]["sha256"] == sha and rows[0]["valid"] and rows[0]["owner_likeness"] is True
              and rows[0]["owner_id"] == record["owner_id"] and rows[0]["capture_session"] == record["capture_session"], rows)
    check("it is not in the shared LoRA library", sorted(row["name"] for row in a.get("/api/loras").json()["loras"]) == shared_before)
    check("it made no gallery item", len(a.get("/api/gallery", params={"limit": 2000}).json()["items"]) == items_before)
    check("the copies of the pictures and the trainer's folder are gone", _owner_files(out, "training") == [], _owner_files(out, "training"))
    shared_training = os.path.join(out, "training")
    check("nothing of the likeness was written to the shared training folder",
          not os.path.isdir(shared_training) or not [d for d in os.listdir(shared_training) if d.startswith("likeness_")])
    check("the trainer status counts one likeness LoRA", a.get("/api/owner/trainer").json()["likeness_loras"] == 1)
    a.post("/api/owner/lock")
    job = a.job("owner_train", train)
    check("after Lock, likeness training is refused again", job["status"] == "refused" and "Unlock" in (job.get("error") or ""))
