"""The test harness's temporary-folder hygiene (tests/tmp_hygiene.py)."""
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tmp_hygiene as H  # noqa: E402


def unit(check):
    print("\n[hygiene] A test run cleans up its own temporary folders, and only old ones of others")
    base = tempfile.mkdtemp(prefix="hyg_base_")
    old_dir, young_dir, other_dir, file_ = (os.path.join(base, n) for n in ("es_old", "es_young", "keep_me", "es_file"))
    for d in (old_dir, young_dir, other_dir):
        os.makedirs(os.path.join(d, "inner"))
    open(file_, "w").write("x")
    long_ago = time.time() - 3 * 3600
    os.utime(old_dir, (long_ago, long_ago))
    os.utime(other_dir, (long_ago, long_ago))
    gone = H.sweep_stale(base)
    check("the sweep removes an es_ folder older than 90 minutes, and nothing else",
          gone == 1 and not os.path.exists(old_dir) and os.path.isdir(young_dir) and os.path.isdir(other_dir) and os.path.isfile(file_), gone)
    check("a younger es_ folder, which may belong to a run in progress, is left alone", os.path.isdir(os.path.join(young_dir, "inner")))
    check("a folder that does not start with es_ is left alone however old", os.path.isdir(other_dir))

    saved = (tempfile.tempdir, os.environ.get("TMPDIR"))
    try:
        tempfile.tempdir = base
        root, old = H.begin(base)
        inside = tempfile.mkdtemp(prefix="es_world_")
        check("a run's folders are made inside its own folder, and its child programs get the same one",
              os.path.dirname(inside) == root and os.environ["TMPDIR"] == root and os.path.basename(root).startswith(H.PREFIX), (inside, root))
        H.end(root, old, keep=False)
        check("when the run passes, its folder is gone and the temp folder is pointed back",
              not os.path.exists(root) and tempfile.tempdir == base and os.environ["TMPDIR"] == base)
        root, old = H.begin(base)
        open(os.path.join(root, "server.log"), "w").write("log")
        H.end(root, old, keep=True)
        check("when the run fails, its folder is kept for the logs", os.path.isfile(os.path.join(root, "server.log")))
    finally:
        tempfile.tempdir = saved[0]
        if saved[1] is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = saved[1]
        shutil.rmtree(base, ignore_errors=True)
