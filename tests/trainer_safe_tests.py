"""The trainer made safe to run: a pinned install, its bases as groups on the Models page, and a run with nothing reaching the network.

Stand-ins only: sparse files stand in for the base models, a tiny script stands in for ai-toolkit. Nothing is installed or downloaded
and no model runs."""
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "install"))
sys.path.insert(0, HERE)

PIN = os.path.join(ROOT, "config", "trainer_pin.json")


def _base_files(base):
    return [r for r in json.load(open(os.path.join(ROOT, "config", "trainer_bases_lock.json"), encoding="utf-8"))["rows"] if r["base"] == base]


def _make_base(models, base, skip=None):
    """The base's files as sparse files of the right size: no disk is used."""
    for r in _base_files(base):
        if r["name"] == skip:
            continue
        path = os.path.join(models, r["folder"], r["name"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.truncate(r["size"])


def unit(check):
    print("\n[trainer] The trainer made safe to run: pinned install, bases on the Models page, offline")
    import download_models as D
    import routes_models as R
    import trainer as T
    lock = json.load(open(os.path.join(ROOT, "config", "trainer_bases_lock.json"), encoding="utf-8"))
    rows = lock["rows"]

    # --- the lock of the two bases
    check("the lock covers both bases, with the files a diffusers folder needs (shards, index, config, tokenizer, scheduler, vae)",
          {r["base"] for r in rows} == {"fast", "photo"} and all(any(r["base"] == b and r["name"] == "model_index.json" for r in rows) for b in ("fast", "photo"))
          and sum(r["name"].endswith(".safetensors") for r in rows) >= 12)
    check("every file is pinned to a full 40-character revision, has a size, and one hash (SHA-256 for a large file, git blob SHA-1 for a small one)",
          all(re.fullmatch(r"[0-9a-f]{40}", r["rev"]) and r["size"] > 0 and ("/resolve/%s/" % r["rev"]) in r["url"] and r["url"].startswith("https://huggingface.co/")
              and (bool(re.fullmatch(r"[0-9a-f]{64}", r.get("sha256", ""))) != bool(re.fullmatch(r"[0-9a-f]{40}", r.get("git_blob_sha1", "")))) for r in rows))
    check("every large file has a SHA-256, and only small files rely on the git hash",
          all("sha256" in r for r in rows if r["size"] > 50 * 1024 * 1024) and all(r["size"] < 50 * 1024 * 1024 for r in rows if "git_blob_sha1" in r))
    check("the sample pictures, the readme and the single-file checkpoint are not in the lock", not any(
        r["path"].startswith(("assets/", "images/")) or r["path"] in ("README.md", "Chroma1-HD.safetensors") or r["path"].endswith(".png") for r in rows))
    check("the licences are Apache-2.0 and nothing is gated", set(lock["licences"].values()) == {"apache-2.0"})
    check("sizes: about 33 GB for the fast base and about 27.5 GB for the photo base",
          32.5e9 < lock["bases"]["fast"]["total_bytes"] < 34e9 and 27e9 < lock["bases"]["photo"]["total_bytes"] < 28e9)

    # --- the Models page
    cat = R.catalog()
    check("the Models page has both trainer groups, every file pinned and none blocked or unpinned, and neither is in the default set",
          all(g in cat and all(f["kind"] == "ok" for f in cat[g]["files"]) for g in ("trainer-fast", "trainer-photo"))
          and not ({"trainer-fast", "trainer-photo"} & set(D.DEFAULT_GROUPS)))
    check("the groups' help text says what they are for and that they are not part of the default set",
          all("Not part of the default set" in D.GROUP_HELP[g] and "train" in D.GROUP_HELP[g].lower() for g in ("trainer-fast", "trainer-photo")))
    from models_tests import Resp
    import models_tests as MT
    data = b"{ \"a small config file\": true }\n" * 40
    item = {"folder": "easy_studio/trainer/fast", "name": "model_index.json", "size": len(data), "url": "https://huggingface.co/o/r/resolve/" + "a" * 40 + "/model_index.json",
            "git_blob_sha1": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()}
    md = os.path.join(tempfile.mkdtemp(prefix="es_trsafe_"), "models")
    os.makedirs(md)
    try:
        dest = R.fetch_file(item, md, MT.server(data=data), lambda n: None)
        check("a small file pinned by its git blob hash is fetched, checked and put in place", os.path.isfile(dest) and open(dest, "rb").read() == data)
        bad = dict(item, name="other.json", git_blob_sha1="0" * 40)
        try:
            R.fetch_file(bad, md, MT.server(data=data), lambda n: None)
            said = ""
        except RuntimeError as exc:
            said = str(exc)
        check("a file that does not match its hash is deleted and refused", "did not match" in said and not os.path.exists(os.path.join(md, item["folder"], "other.json"))
              and not os.path.exists(os.path.join(md, item["folder"], "other.json.part")), said)
    finally:
        shutil.rmtree(os.path.dirname(md), ignore_errors=True)
    check("the Models page fetches .json, .txt and tokenizer .model files for the two trainer groups only",
          R.EXTRA_EXT.get("trainer-fast") == (".json", ".txt") and R.EXTRA_EXT.get("trainer-photo") == (".json", ".txt", ".model")
          and set(R.EXTRA_EXT) == {"safety", "trainer-fast", "trainer-photo"})

    # --- the trainer reads its bases from this computer
    saved = {k: os.environ.get(k) for k in ("COMFY_DIR", "EASY_STUDIO_TEST_RUN")}
    comfy = tempfile.mkdtemp(prefix="es_trsafe_comfy_")
    try:
        os.environ["COMFY_DIR"] = comfy
        models = os.path.join(comfy, "models")
        for base, name in (("fast", "Fast pictures"), ("photo", "Realistic pictures")):
            os.environ.pop("EASY_STUDIO_TEST_RUN", None)
            ready, missing = T.base_status(base)
            check("%s: with nothing downloaded the base is not ready" % base, ready is False and len(missing) == len(_base_files(base)))
            try:
                T.write_config(tempfile.mkdtemp(prefix="es_trcfg_"), "n", base, "trig", "/tmp/ds")
                said = ""
            except T.TrainerBaseMissing as exc:
                said = str(exc)
            check("%s: a run without the base is refused in plain words that name the button, and nothing is fetched" % base,
                  "not on this computer" in said and "Setup, then Models" in said and T.GROUP_LABEL[base] in said and "never fetches" in said, said)
            _make_base(models, base, skip=_base_files(base)[0]["name"])
            ready, missing = T.base_status(base)
            try:
                T.write_config(tempfile.mkdtemp(prefix="es_trcfg_"), "n", base, "trig", "/tmp/ds")
                said = ""
            except T.TrainerBaseMissing as exc:
                said = str(exc)
            check("%s: with one file missing it is still refused, and says how many" % base, ready is False and "1 of its files are missing" in said, said)
            _make_base(models, base)
            cfg_path = T.write_config(tempfile.mkdtemp(prefix="es_trcfg_"), "n", base, "trig", "/tmp/ds")
            model = json.load(open(cfg_path))["config"]["process"][0]["model"]
            blob = json.dumps(model)
            check("%s: with the base downloaded the config names this computer's folder, and no Hugging Face name is left" % base,
                  model["name_or_path"] == T.base_dir(base) and os.path.isdir(model["name_or_path"]) and not re.search(r"\b(lodestones|Tongyi-MAI|ostris)/", blob), blob[:200])
        fast_model = json.load(open(T.write_config(tempfile.mkdtemp(prefix="es_trcfg_"), "n", "fast", "trig", "/tmp/ds")))["config"]["process"][0]["model"]
        check("the Z-Image training adapter is read from the base's own adapter folder",
              fast_model["assistant_lora_path"] == os.path.join(T.base_dir("fast"), "adapter", "zimage_turbo_training_adapter_v2.safetensors")
              and os.path.isfile(fast_model["assistant_lora_path"]))
        try:
            T.write_config(tempfile.mkdtemp(prefix="es_trcfg_"), "n", "anime", "trig", "/tmp/ds")
            said = ""
        except T.TrainerBaseMissing as exc:
            said = str(exc)
        check("a base with no download here (anime, video) is refused instead of fetching its model by itself", "never fetches" in said, said)
        os.environ["EASY_STUDIO_TEST_RUN"] = "1"
        shutil.rmtree(models)
        check("in a test run the stand-in trainer still gets a config without any base on disk",
              json.load(open(T.write_config(tempfile.mkdtemp(prefix="es_trcfg_"), "n", "fast", "trig", "/tmp/ds")))["config"]["process"][0]["model"]["name_or_path"])
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(comfy, ignore_errors=True)

    # --- the run itself: offline, no key, no network
    tdir = tempfile.mkdtemp(prefix="es_trsafe_tr_")
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]
    try:
        with open(os.path.join(tdir, "run.py"), "w", encoding="utf-8") as f:
            f.write("import json, os, socket, sys\nenv = {k: os.environ.get(k) for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_DATASETS_OFFLINE','DIFFUSERS_OFFLINE',"
                    "'HF_HOME','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','WANDB_API_KEY','DASHSCOPE_API_KEY','HF_HUB_DISABLE_TELEMETRY','WANDB_MODE')}\n"
                    "s = socket.socket(); s.settimeout(3)\ntry:\n    s.connect(('127.0.0.1', %d)); env['network'] = 'connected'\n"
                    "except Exception as e:\n    env['network'] = 'blocked'\n"
                    "def tryit(f):\n    try:\n        f(); return 'allowed'\n    except Exception:\n        return 'blocked'\n"
                    "env['udp'] = tryit(lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('127.0.0.1', 9)))\n"
                    "env['dns'] = tryit(lambda: socket.getaddrinfo('example.invalid', 443))\n"
                    "import tempfile, multiprocessing as mp\n"
                    "d = tempfile.mkdtemp(prefix='es_sbx_', dir='/tmp')\n"
                    "def unix(where):\n    a = socket.socket(socket.AF_UNIX); a.bind(where + '/s'); a.listen(1); b = socket.socket(socket.AF_UNIX); b.connect(where + '/s')\n"
                    "env['unix'] = tryit(lambda: unix(os.environ['TMPDIR']))\n"
                    "env['unix_elsewhere'] = tryit(lambda: unix(d))\n"
                    "env['unix_agent'] = tryit(lambda: socket.socket(socket.AF_UNIX).connect(os.environ.get('SSH_AUTH_SOCK_TEST', '/private/var/run/mDNSResponder')))\n"
                    "env['pair'] = tryit(lambda: socket.socketpair())\n"
                    "def kid(q): q.put('ok')\n"
                    "q = mp.get_context('fork').Queue(); pr = mp.get_context('fork').Process(target=kid, args=(q,)); pr.start()\n"
                    "env['worker'] = q.get(timeout=20); pr.join()\n"
                    "import shutil; shutil.rmtree(d, ignore_errors=True)\n"
                    "json.dump(env, open(sys.argv[1] + '.seen', 'w'))\nprint('1/1 [00:00]')\n" % port)
        cfg = os.path.join(tdir, "cfg.json")
        open(cfg, "w").write("{}")
        keep = {k: os.environ.get(k) for k in ("EASY_STUDIO_TRAINER_DIR", "EASY_STUDIO_TRAINER_PYTHON", "HF_TOKEN", "WANDB_API_KEY", "DASHSCOPE_API_KEY")}
        os.environ.update(EASY_STUDIO_TRAINER_DIR=tdir, EASY_STUDIO_TRAINER_PYTHON=sys.executable, HF_TOKEN="hf_not_a_real_token_0000000000000000",
                          WANDB_API_KEY="not-a-real-key", DASHSCOPE_API_KEY="not-a-real-key")
        try:
            T.run_training(ROOT, cfg, lambda f, m: None, lambda: False, os.path.join(tdir, "log.txt"))
        finally:
            for k, v in keep.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        seen = json.load(open(cfg + ".seen"))
        check("the trainer runs with every offline switch on and a private empty Hugging Face home",
              all(seen[k] == "1" for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "DIFFUSERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"))
              and seen["HF_HOME"] == os.path.join(tdir, "hf_home") and os.path.isdir(os.path.join(tdir, "hf_home")) and seen["WANDB_MODE"] == "disabled", seen)
        check("any variable named like a key, token or secret is dropped, whatever the vendor", T.offline_env(tdir, {"SOME_VENDOR_API_KEY": "x", "MY_SERVICE_TOKEN": "x", "DB_PASSWORD": "x", "PATH": "/usr/bin"}).get("SOME_VENDOR_API_KEY") is None
              and "MY_SERVICE_TOKEN" not in T.offline_env(tdir, {"MY_SERVICE_TOKEN": "x"}) and "DB_PASSWORD" not in T.offline_env(tdir, {"DB_PASSWORD": "x"})
              and T.offline_env(tdir, {"PATH": "/usr/bin"})["PATH"] == "/usr/bin")
        check("no login or key reaches the trainer", seen["HF_TOKEN"] is None and seen["HUGGING_FACE_HUB_TOKEN"] is None
              and seen["WANDB_API_KEY"] is None and seen["DASHSCOPE_API_KEY"] is None, seen)
        if sys.platform == "darwin" and os.path.exists(T.SANDBOX_EXEC):
            check("on a Mac the system denies the trainer the network: no connection to a program on this computer, no UDP, no name lookup",
                  seen["network"] == "blocked" and seen["udp"] == "blocked" and seen["dns"] == "blocked", seen)
            check("on a Mac the trainer's own processes can still talk (a socket in its private temp folder, a socket pair, a data-loader style worker), but it cannot "
                  "reach any other program's local socket, such as an agent or the system's name service",
                  seen["unix"] == "allowed" and seen["pair"] == "allowed" and seen["worker"] == "ok" and seen["unix_elsewhere"] == "blocked" and seen["unix_agent"] == "blocked", seen)
        else:
            check("no system network block on this platform (the offline switches still apply)", True)
        check("the command is the sandboxed one on a Mac, with a profile that denies the network and allows sockets only in the private temp folder, and the plain one elsewhere",
              T.network_off(tdir) == ([T.SANDBOX_EXEC, "-p", T.no_network_profile(T.private_tmp(tdir))] if sys.platform == "darwin" and os.path.exists(T.SANDBOX_EXEC) else [])
              and "(deny network*)" in T.no_network_profile(tdir) and T.no_network_profile(tdir).count("(allow network*") == 2
              and os.path.realpath(tdir) in T.no_network_profile(tdir) and "(allow network* (remote ip" not in T.no_network_profile(tdir))
        check("a socket-pointer variable (agent, container, password manager) never reaches the trainer",
              not {"SSH_AUTH_SOCK", "DOCKER_HOST"} & set(T.offline_env(tdir, {"SSH_AUTH_SOCK": "/x", "DOCKER_HOST": "unix:///y", "PATH": "/usr/bin"})))
    finally:
        srv.close()
        shutil.rmtree(tdir, ignore_errors=True)

    # --- the install scripts
    pin = json.load(open(PIN, encoding="utf-8"))
    for name in ("install_trainer_mac.sh", "install_trainer.sh"):
        text = open(os.path.join(ROOT, "install", name), encoding="utf-8").read()
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        check("%s takes the pinned commit and the pinned requirement hashes, which match config/trainer_pin.json" % name,
              'COMMIT="%s"' % pin["commit"] in text and 'REQ_SHA="%s"' % pin["requirements_txt_sha256"] in text
              and 'REQ_BASE_SHA="%s"' % pin["requirements_base_txt_sha256"] in text and re.fullmatch(r"[0-9a-f]{40}", pin["commit"]))
        check("%s never pulls 'latest', checks the commit and both hashes before installing, and downloads no model" % name,
              "git -C \"$T\" pull" not in code and "rev-parse HEAD" in code and code.count("Stopped:") >= 3
              and code.index("rev-parse HEAD") < code.index("pip install") and code.index("shasum -a 256" if "shasum" in code else "sha256sum") < code.index("pip install")
              and "huggingface-cli" not in code and "download_models" not in code and "snapshot_download" not in code)
        check("%s has valid shell syntax and can be run" % name,
              subprocess.run(["bash", "-n", os.path.join(ROOT, "install", name)]).returncode == 0 and os.access(os.path.join(ROOT, "install", name), os.X_OK))
    mac = open(os.path.join(ROOT, "install", "install_trainer_mac.sh"), encoding="utf-8").read()
    check("the Mac script installs torch at the pinned versions from the pin file",
          all("%s==%s" % (k, v) in mac for k, v in pin["torch"].items() if k in ("torch", "torchvision", "torchaudio")))
    check("the pin says honestly what is and is not pinned", "limits" in pin and "never run on this Mac" in pin["limits"])
    start = open(os.path.join(ROOT, "start_mac.sh"), encoding="utf-8").read()
    check("the start script points the app at the same trainer folder the Mac install script uses",
          'EASY_STUDIO_TRAINER_DIR="${EASY_STUDIO_TRAINER_DIR:-$RT/trainer/ai-toolkit}"' in start
          and 'T="${EASY_STUDIO_TRAINER_DIR:-$RT/trainer/ai-toolkit}"' in mac)
