# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Setup > Models: pinned, hash-checked, resumable downloads. The network is a stand-in; real requests raise."""
import hashlib
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import routes_models as R  # noqa: E402

DATA = (b"not a model, only test bytes " * 4000)
SHA = hashlib.sha256(DATA).hexdigest()
GB = 1024 ** 3


class Resp:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.body), 5000):
            yield self.body[i:i + 5000]

    def close(self):
        pass


def server(data=DATA, honour_range=True, log=None):
    def fetch(url, headers):
        if log is not None:
            log.append((url, dict(headers)))
        rng = headers.get("Range")
        if rng and honour_range:
            return Resp(206, data[int(rng.split("=")[1].rstrip("-")):])
        return Resp(200, data)
    return fetch


def item(name="m.safetensors", sha=SHA, size=len(DATA)):
    return {"folder": "loras", "name": name, "kind": "ok", "url": "https://huggingface.co/o/r/resolve/" + "a" * 40 + "/" + name,
            "sha256": sha, "size": size}


def group(files, gid="g"):
    return {"id": gid, "help": "t", "files": files}


def free(n):
    return lambda p: types.SimpleNamespace(free=n)


def unit(check):
    print("\n[models] Pinned, hash-checked downloads (stand-in network)")

    def no_net(*a, **k):
        raise AssertionError("real network call")
    import requests
    real_get, requests.get = requests.get, no_net
    try:
        md = os.path.join(tempfile.mkdtemp(prefix="es_models_"), "models")
        os.makedirs(md)
        # catalog: every group is pinned/blocked/unpinned from committed data; ext rule and pins
        cat = R.catalog()
        kinds = {f["kind"] for g in cat.values() for f in g["files"]}
        check("models: the catalog covers every download group", {"image", "safety", "video"} <= set(cat))
        check("models: an unpinned weight is marked unpinned, and a .pth or .json file in any group but the age check's is blocked",
              "unpinned" in kinds and not any(f["kind"] == "blocked" for f in cat["safety"]["files"])
              and not any(f["kind"] != "blocked" for g, grp in cat.items() if g != "safety" for f in grp["files"] if f["name"].endswith((".pth", ".json", ".pt", ".ckpt", ".bin"))
                      and not (g in ("trainer-fast", "trainer-photo") and f["name"].endswith(".json"))))
        mini = {"x": [("f", "a.pth", "https://huggingface.co/o/r/resolve/main/a.pth", "0 GB"), ("f", "c.json", "https://huggingface.co/o/r/resolve/main/c.json", "0 GB")],
                "safety": [("f", "a.pth", "https://huggingface.co/o/r/resolve/main/a.pth", "0 GB")]}
        pins_ = {("o/r", "a.pth"): {"url": "https://huggingface.co/o/r/resolve/" + "a" * 40 + "/a.pth", "sha256": "0" * 64, "size": 5},
                 ("o/r", "c.json"): {"url": "https://huggingface.co/o/r/resolve/" + "a" * 40 + "/c.json", "sha256": "0" * 64, "size": 5}}
        small = R.catalog(models=mini, pins=pins_)
        check("models: the same .pth is blocked in an ordinary group and fetched, pinned, in the age check's group",
              [f["kind"] for f in small["x"]["files"]] == ["blocked", "blocked"] and [f["kind"] for f in small["safety"]["files"]] == ["ok"], small)
        check("models: the age check's group can be downloaded from the page, with every file it needs pinned",
              all(f["kind"] == "ok" for f in cat["safety"]["files"]) and {f["name"] for f in cat["safety"]["files"]} >=
              {"model.safetensors", "config.json", "preprocessor_config.json", "yunet_final.pth"}, [(f["name"], f["kind"]) for f in cat["safety"]["files"]])
        faces = [f for f in cat["face"]["files"] if f["name"].endswith(".onnx")]
        check("models: the face check's two files are in their own face group (not safety), pinned to a revision (not main), with a size and hash",
              len(faces) == 2 and not [f for f in cat["safety"]["files"] if f["name"].endswith(".onnx")] and all(f["kind"] == "ok" and f["sha256"] and f["size"] and "/resolve/main/" not in f["url"] for f in faces), faces)
        check("models: every pinned url is a commit-pinned https huggingface.co link with a sha256 (or, for a small trainer file, a git blob hash)",
              all(f["url"].startswith("https://huggingface.co/") and len(f["sha256"] or f["git_blob_sha1"]) in (64, 40) and f["size"] > 0
                  and ("/resolve/main/" not in f["url"] or R._URL.match(f["url"]))
                  for g in cat.values() for f in g["files"] if f["kind"] == "ok"))
        full = {g for g, v in cat.items() if all(f["kind"] != "unpinned" for f in v["files"])}
        check("models: Chroma1-HD, Z-Image Turbo and Wan 5B (with VAE and text encoder) are pinned", {"image", "fast", "video-wan5b", "sd15"} <= full, sorted(full))
        # unpinned / blocked groups cannot start
        ok, msg, _ = R.start("image", md, fetch=server(), free_fn=free(500 * GB), groups={"image": group([dict(item(), kind="unpinned", url=None, sha256=None, size=None)])})
        check("models: a group with an unpinned file is refused", not ok and "Not pinned" in msg, msg)
        # floor refusal, with the df reading
        ok, msg, fr = R.start("g", md, fetch=server(), free_fn=free(50 * GB + 10), groups={"g": group([item(size=1000)])})
        check("models: the click is refused when the 50 GB floor would break", not ok and "50 GB" in msg and fr == 50 * GB + 10, msg)
        # a good download, hash and size checked, file lands
        log = []
        ok, msg, fr = R.start("g", md, fetch=server(log=log), free_fn=free(200 * GB), groups={"g": group([item()])}, background=False)
        dest = os.path.join(md, "loras", "m.safetensors")
        check("models: a pinned download lands only after its SHA256 matches",
              ok and R.STATE["g"]["status"] == "done" and open(dest, "rb").read() == DATA and not os.path.exists(dest + ".part"), R.STATE.get("g"))
        check("models: the live df reading comes back at the click", fr == 200 * GB)
        # nothing executable
        check("models: the downloaded file is not made executable", not os.access(dest, os.X_OK))
        # already installed -> nothing to do
        ok, msg, _ = R.start("g", md, fetch=server(), free_fn=free(200 * GB), groups={"g": group([item()])})
        check("models: an installed group has nothing to download", not ok and "Already" in msg, msg)
        # mismatch: no final file, no .part
        it = item("bad.safetensors", sha="0" * 64)
        ok, _m, _f = R.start("b", md, fetch=server(), free_fn=free(200 * GB), groups={"b": group([it])}, background=False)
        d2 = os.path.join(md, "loras", "bad.safetensors")
        check("models: a SHA256 mismatch deletes the file and its .part", R.STATE["b"]["status"] == "error" and not os.path.exists(d2) and not os.path.exists(d2 + ".part"), R.STATE.get("b"))
        # resume from a .part via 206
        it = item("res.safetensors")
        d3 = os.path.join(md, "loras", "res.safetensors")
        open(d3 + ".part", "wb").write(DATA[:30000])
        log = []
        R.fetch_file(it, md, server(log=log))
        check("models: a partial file resumes with a Range request and ends with the right hash",
              open(d3, "rb").read() == DATA and log and log[0][1].get("Range") == "bytes=30000-", log)
        # 200 to a range request restarts
        it = item("rst.safetensors")
        d4 = os.path.join(md, "loras", "rst.safetensors")
        open(d4 + ".part", "wb").write(b"junk-prefix")
        R.fetch_file(it, md, server(honour_range=False))
        check("models: a server that ignores the range restarts the file cleanly", open(d4, "rb").read() == DATA)
        # path escape
        try:
            R._dest(md, dict(item(), folder="../../etc"))
            esc = False
        except ValueError:
            esc = True
        check("models: a file can't land outside the models folder", esc)
        # missing models dir: refuse, create nothing
        gone = os.path.join(tempfile.mkdtemp(prefix="es_models_"), "nomodels")
        ok, msg, _ = R.start("g", gone, fetch=server(), free_fn=free(500 * GB), groups={"g": group([item()])})
        check("models: no models folder means refuse and create nothing", not ok and not os.path.exists(gone), msg)
        # local only
        check("models: only this computer may start a download",
              R.is_local("localhost:8000", "127.0.0.1") and R.is_local("[::1]:8000", "::1") and not R.is_local("studio.lan:8000", "127.0.0.1")
              and not R.is_local("localhost", "192.168.1.5") and not R.is_local(None, "127.0.0.1"))
        # the default fetch refuses a link that leaves Hugging Face (no request is sent)
        try:
            R.http_fetch("https://evil.example/x.safetensors", {})
            leaves = False
        except RuntimeError:
            leaves = True
        check("models: the default fetch refuses a host that is not Hugging Face", leaves)
    finally:
        requests.get = real_get
        R.STATE.clear()
