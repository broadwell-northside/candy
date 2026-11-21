#!/usr/bin/env python3
"""Writes config/trainer_bases_lock.json: the files the character trainer needs for each base, pinned to a revision.

Reads PUBLIC METADATA only (Hugging Face's model and tree API: file names, sizes, hashes). It downloads no model.
Each file carries its size and one hash: the SHA-256 for a large (LFS) file, and for a small file the git blob hash (SHA-1)
that the revision itself is built from. The Models page checks the download against it.

  python tools/build_trainer_bases_lock.py
"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF = "https://huggingface.co"
UA = {"User-Agent": "easy-studio-lock-builder/1"}

# base id -> (label, [(repo, subfolder under the base's folder, [paths of that repo to take])], what it is for)
SKIP_PREFIXES = ("assets/", "images/")
BASES = {
    "fast": {"label": "Trainer base: Fast pictures (Z-Image Turbo)",
             "repos": [("Tongyi-MAI/Z-Image-Turbo", "", None), ("ostris/zimage_turbo_training_adapter", "adapter/", ["zimage_turbo_training_adapter_v2.safetensors"])]},
    "photo": {"label": "Trainer base: Realistic pictures (Chroma1-HD)",
              "repos": [("lodestones/Chroma1-HD", "", None)]},
}
DROP = {"README.md", ".gitattributes", "Chroma1-HD.safetensors", "ComfyUI_Chroma1-HD_T2I-overview.png", "ComfyUI_Chroma1-HD_T2I-sample.png",
        "ComfyUI_Chroma1-HD_T2I-workflow.json"}   # the single-file checkpoint and the sample pictures are not part of the diffusers folder


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def main():
    rows, totals, licences = [], {}, {}
    for base_id, spec in BASES.items():
        for repo, sub, only in spec["repos"]:
            meta = get("%s/api/models/%s" % (HF, repo))
            rev, lic = meta["sha"], (meta.get("cardData") or {}).get("license")
            if meta.get("gated") or lic not in ("apache-2.0", "mit"):
                raise SystemExit("%s: gated or not Apache-2.0/MIT (%s); stopped" % (repo, lic))
            licences[repo] = lic
            for e in get("%s/api/models/%s/tree/%s?recursive=true" % (HF, repo, rev)):
                path = e["path"]
                if e.get("type") != "file" or path in DROP or path.startswith(SKIP_PREFIXES):
                    continue
                if only is not None and path not in only:
                    continue
                row = {"base": base_id, "repo": repo, "rev": rev, "path": path, "size": int(e["size"]),
                       "folder": "/".join(x for x in ("easy_studio/trainer/%s" % base_id, sub.strip("/"), os.path.dirname(path)) if x),
                       "name": os.path.basename(path), "url": "%s/%s/resolve/%s/%s" % (HF, repo, rev, path)}
                lfs = e.get("lfs") or {}
                if lfs.get("oid"):
                    row["sha256"] = lfs["oid"]
                else:
                    row["git_blob_sha1"] = e["oid"]
                rows.append(row)
                totals[base_id] = totals.get(base_id, 0) + row["size"]
    rows.sort(key=lambda r: (r["base"], r["repo"], r["path"]))
    doc = {"schema": 1, "note": "Pinned by revision. Large files by SHA-256, small files by git blob SHA-1. Built from public metadata by "
           "tools/build_trainer_bases_lock.py; nothing was downloaded.",
           "licences": licences, "bases": {b: {"label": BASES[b]["label"], "total_bytes": totals[b]} for b in BASES}, "rows": rows}
    path = os.path.join(ROOT, "config", "trainer_bases_lock.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=True)
        f.write("\n")
    print("wrote", path, len(rows), "files;", {b: "%.1f GB" % (t / 1e9) for b, t in totals.items()})


if __name__ == "__main__":
    main()
