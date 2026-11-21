"""Keeps a test run's temporary folders from piling up in the user's temp folder.

A full run used to leave hundreds of megabytes behind (every test world, comfy folder and trainer folder), and a few
runs a day filled tens of gigabytes. Now:
  * a run puts everything it and its child programs create under one folder of its own (es_run_*), by pointing TMPDIR
    and tempfile at it, and removes that folder when the run passes. A failing run keeps it, and says where, for the logs;
  * at the start, folders named es_* that are older than 90 minutes are removed. A younger one may belong to a run in
    progress, perhaps another session's, so it is never touched.
"""
import os
import shutil
import sys
import tempfile
import time

PREFIX = "es_run_"
STALE_MINUTES = 90


def sweep_stale(base=None, minutes=STALE_MINUTES, now=None):
    """Remove es_* folders directly under base that were last changed more than `minutes` ago. Returns how many."""
    base = base or tempfile.gettempdir()
    cutoff = (now or time.time()) - minutes * 60
    gone = 0
    try:
        names = os.listdir(base)
    except OSError:
        return 0
    for name in names:
        path = os.path.join(base, name)
        if name.startswith("es_") and os.path.isdir(path) and not os.path.islink(path):
            try:
                if os.stat(path).st_mtime < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
                    gone += 1
            except OSError:
                pass
    return gone


def begin(base=None):
    """Sweep the old ones, then make this run's own folder and make it the temp folder. Returns (root, old tempdir)."""
    old = base or tempfile.gettempdir()
    sweep_stale(old)
    root = tempfile.mkdtemp(prefix=PREFIX, dir=old)
    os.environ["TMPDIR"] = root
    tempfile.tempdir = root
    return root, old


def end(root, old, keep=False):
    """Remove this run's folder unless keep. Always point the temp folder back."""
    os.environ["TMPDIR"] = old
    tempfile.tempdir = old
    if keep:
        print("temporary folders kept for the logs: " + root)
    else:
        shutil.rmtree(root, ignore_errors=True)


def run(main):
    """Run main() with its own temp folder; keep that folder only when the run fails."""
    root, old = begin()
    code = 0
    try:
        main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        raise
    except BaseException:
        code = 1
        raise
    finally:
        end(root, old, keep=bool(code))
