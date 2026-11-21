"""M0: a pack from job_export_godot goes through the island importer.

Mock data and the mock engine only. No GPU, no weight download, no network.
The real island folder is read in dry-run mode and must not change at all.
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

import island_export_tests as ex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "game")
IMPORTER = os.path.join(GAME, "tools", "import_easy_studio.py")


def _importer():
    spec = importlib.util.spec_from_file_location("import_easy_studio_m0", IMPORTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _tree(root):
    """Every file under the island folder with its hash. Godot's own cache folder is skipped."""
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in (".godot", "build", "__pycache__"))
        for name in sorted(files):
            path = os.path.join(base, name)
            out[os.path.relpath(path, root)] = _sha(path)
    return out


def _zip_from_export(specs):
    z = ex._pack(ex._person(), specs)
    path = os.path.join(tempfile.mkdtemp(prefix="m0_pack_"), "mara_pack.zip")
    with open(path, "wb") as fh:
        fh.write(z.fp.getvalue())
    return path, z


def unit(check):
    print("\n[M0] Export to Godot, then the island importer in dry-run")
    project = os.path.join(GAME, "project.godot")
    check("the island folder is on this branch", os.path.isfile(project) and os.path.isfile(IMPORTER))
    if not (os.path.isfile(project) and os.path.isfile(IMPORTER)):
        return
    imp = _importer()
    zip_path, z = _zip_from_export([{"name": "smile.png"}, {"name": "shore.mp4", "kind": "video:film"}])
    check("the export zip carries its own preview project.godot",
          "project.godot" in z.namelist(), z.namelist()[:10])

    before_bytes = open(project, "rb").read()
    before_tree = _tree(GAME)
    summary = imp.import_export(zip_path, "mara", root=GAME, dry_run=True)
    after_bytes = open(project, "rb").read()
    check("dry-run reports the pack", summary.get("dry_run") is True and summary.get("stated_age") == 32
          and summary.get("portraits", 0) >= 1 and summary.get("videos", 0) >= 1, summary)
    check("island project.godot is byte-identical after the dry-run", before_bytes == after_bytes)
    check("dry-run writes nothing anywhere in the island folder", _tree(GAME) == before_tree)
    check("dry-run does not create game/assets/imports",
          not os.path.isdir(os.path.join(GAME, "assets", "imports")))

    run = subprocess.run([sys.executable, IMPORTER, zip_path, "--character", "mara", "--dry-run"],
                         capture_output=True, text=True, timeout=120)
    check("the command-line dry-run succeeds", run.returncode == 0, (run.returncode, run.stdout[-300:], run.stderr[-300:]))
    check("island project.godot is byte-identical after the command-line dry-run",
          open(project, "rb").read() == before_bytes)
    check("the command-line dry-run writes nothing", _tree(GAME) == before_tree)

    # A real import (stills only, so no video encoder is needed) into a copy of the island.
    copy_root = os.path.join(tempfile.mkdtemp(prefix="m0_island_"), "game")
    shutil.copytree(GAME, copy_root, ignore=shutil.ignore_patterns(".godot", "build"))
    stills_zip, _ = _zip_from_export([{"name": "smile.png"}])
    copy_before = open(os.path.join(copy_root, "project.godot"), "rb").read()
    done = imp.import_export(stills_zip, "mara", root=copy_root)
    check("a real import into a copy of the island succeeds", done.get("dry_run") is False, done)
    check("a real import keeps the island's project.godot byte-identical",
          open(os.path.join(copy_root, "project.godot"), "rb").read() == copy_before)
    check("a real import never copies the pack's preview project.godot",
          not os.path.exists(os.path.join(copy_root, "assets", "imports", "mara", "project.godot")))
    check("the real island folder is still untouched", _tree(GAME) == before_tree)
