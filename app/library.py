"""The gallery: every file Easy Studio makes or receives is an "item" with a small JSON record.

outputs/files/<YYYY-MM-DD>/<name>   the file
outputs/items/<id>.json             what made it (kind, prompt, seed, model, parent, character, project, role...)
Deleted items move to outputs/_trash.

Roles (safety):
  made          made by Easy Studio from text / from other made items -> may be edited as the person
  my_character  an upload the user confirmed is a fictional adult they created -> may be edited as the person
  clothing / object / background   uploads usable ONLY as a reference picture (image 2)
  pose_ref      upload usable ONLY to extract a stick figure
  scenery       a place photo. Not a person, not a character reference, not a face swap,
                and not a clothing-removal edit. A found face is blurred or the photo is refused.
  skeleton      a stick-figure pose picture -> usable only as pose guidance

Areas (v3): items made in the 18+ section have area "adult"; they are hidden from the everyday gallery
and can't be used as a source outside the 18+ section. Items the automatic age check flagged
(age_flag), made before a flagged result was deleted outright (D-C-51), can't be used as a source anywhere
and are not listed in the gallery.
"""
import json
import os
import re
import shutil
import threading
import time
import uuid

PERSON_ROLES = ("made", "my_character")
REF_ROLES = ("clothing", "object", "background", "made", "my_character")
UPLOAD_ROLES = ("my_character", "clothing", "object", "pose_ref", "background", "scenery")

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
VIDEO_EXT = (".mp4", ".webm", ".mov")
MODEL_EXT = (".glb", ".gltf", ".obj", ".fbx", ".stl")


def file_type(path):
    e = os.path.splitext(path)[1].lower()
    if e in IMAGE_EXT:
        return "image"
    if e in VIDEO_EXT:
        return "video"
    if e in MODEL_EXT:
        return "model"
    if e == ".zip":
        return "zip"
    return "file"


class Library:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.items_dir = os.path.join(self.root, "items")
        self.files_dir = os.path.join(self.root, "files")
        self.trash = os.path.join(self.root, "_trash")
        for d in (self.items_dir, self.files_dir, self.trash):
            os.makedirs(d, exist_ok=True)
        self.lock = threading.Lock()
        self.items = {}
        for f in os.listdir(self.items_dir):
            if f.endswith(".json"):
                try:
                    it = json.load(open(os.path.join(self.items_dir, f), encoding="utf-8"))
                    if os.path.exists(self.path(it)):
                        self.items[it["id"]] = it
                except Exception:
                    pass

    # ---- paths ----
    def new_path(self, name):
        day = time.strftime("%Y-%m-%d")
        d = os.path.join(self.files_dir, day)
        os.makedirs(d, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(name))[-80:] or "file"
        p = os.path.join(d, name)
        root, ext = os.path.splitext(p)
        while os.path.exists(p):
            p = f"{root}_{uuid.uuid4().hex[:4]}{ext}"
        return p

    def path(self, item):
        return os.path.join(self.root, item["file"])

    def url(self, item):
        return "/files/" + item["file"].replace(os.sep, "/")

    # ---- items ----
    def add(self, src_path, kind, role="made", move=True, **meta):
        dst = self.new_path(os.path.basename(src_path))
        (shutil.move if move else shutil.copyfile)(src_path, dst)
        it = {"id": uuid.uuid4().hex[:12], "file": os.path.relpath(dst, self.root), "type": file_type(dst),
              "kind": kind, "role": role, "created": time.time(), "favourite": False}
        it.update({k: v for k, v in meta.items() if v is not None})
        if it["type"] == "image":
            try:
                from PIL import Image
                with Image.open(dst) as im:
                    it["w"], it["h"] = im.size
                    it["alpha"] = im.mode in ("RGBA", "LA")
            except Exception:
                pass
        self._write(it)
        return it

    def _write(self, it):
        with self.lock:
            self.items[it["id"]] = it
            tmp = os.path.join(self.items_dir, it["id"] + ".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(it, f, indent=1)
            os.replace(tmp, os.path.join(self.items_dir, it["id"] + ".json"))

    def get(self, iid):
        if not isinstance(iid, str) or iid not in self.items:
            raise KeyError("That picture/video is no longer in the gallery.")
        return self.items[iid]

    def update(self, iid, **changes):
        it = dict(self.get(iid))
        for k in ("favourite", "project", "title", "character"):
            if k in changes:
                it[k] = changes[k]
        self._write(it)
        return it

    RECIPE_TAGS = ("recipe_cache_key", "recipe_hash", "recipe", "sha256")

    def tag(self, iid, **fields):
        """Recipe bookkeeping on a finished result: its cache key, canonical hash and file sha256."""
        it = dict(self.get(iid))
        for key in self.RECIPE_TAGS:
            if fields.get(key):
                it[key] = fields[key]
        self._write(it)
        return it

    def delete(self, iid):
        it = self.get(iid)
        with self.lock:
            self.items.pop(iid, None)
            p = self.path(it)
            if os.path.exists(p):
                shutil.move(p, os.path.join(self.trash, f"{iid}_{os.path.basename(p)}"))
            j = os.path.join(self.items_dir, iid + ".json")
            if os.path.exists(j):
                shutil.move(j, os.path.join(self.trash, iid + ".json"))

    def list(self, character=None, project=None, type=None, favourites=False, role=None, limit=500, area="default"):
        out = sorted(self.items.values(), key=lambda d: -d["created"])
        if area != "all":
            out = [i for i in out if (i.get("area") or "default") == ("adult" if area == "adult" else "default")]
        if character:
            out = [i for i in out if i.get("character") == character]
        if project:
            out = [i for i in out if i.get("project") == project]
        if type:
            out = [i for i in out if i["type"] == type]
        if role:
            out = [i for i in out if i.get("role") == role]
        if favourites:
            out = [i for i in out if i.get("favourite")]
        return out[:limit]

    def projects(self, area="default"):
        return sorted({i["project"] for i in self.items.values() if i.get("project")
                       and (i.get("area") or "default") == area})

    # ---- safety helpers ----
    @staticmethod
    def _not_flagged(it):
        appearance = it.get("appearance_check") or {}
        held = it.get("held") or appearance.get("held") or it.get("age_check") in (
            "unchecked", "blocked_age_check_unavailable", "unavailable", "error", "timeout", "off")
        if it.get("age_flag") or appearance.get("status") in ("flag", "blocked_age_check_unavailable", "unchecked", "off") or (
                held and it.get("age_check") != "ok"):
            raise PermissionError("The age check held this picture, so it can't be used. Pick another one.")

    def person_image(self, iid):
        it = self.get(iid)
        self._not_flagged(it)
        if it["type"] != "image":
            raise ValueError("Please pick a picture (not a video or 3D file).")
        if it.get("role") == "scenery" or it.get("place") is True:
            raise PermissionError(
                "This photo is a place, not a person. It cannot be a character, a face swap, or a clothing-removal edit.")
        if it.get("role") not in PERSON_ROLES:
            raise PermissionError(
                f"This picture was uploaded as '{it.get('role')}', so it can only be used as a reference, "
                "not as the character being edited. Pick a picture Easy Studio made, or upload one as "
                "'My fictional character'.")
        return it

    def ref_image(self, iid, allowed=REF_ROLES):
        it = self.get(iid)
        self._not_flagged(it)
        if it["type"] != "image":
            raise ValueError("Please pick a picture.")
        if it.get("role") == "scenery" or it.get("place") is True:
            raise PermissionError(
                "This photo is a place, not a person. It cannot be a character reference, a face swap, or a clothing-removal edit.")
        if it.get("role") not in allowed:
            raise PermissionError(f"A '{it.get('role')}' picture can't be used here.")
        return it

    @staticmethod
    def derived_role(parent):
        r = parent.get("role")
        return "made" if r in PERSON_ROLES else r


class AreaView:
    """The library as seen by one job / request: 18+ items only inside the 18+ section."""

    def __init__(self, lib, area):
        self.lib = lib
        self.area = "adult" if area == "adult" else "default"

    def __getattr__(self, k):
        return getattr(self.lib, k)

    def _ok(self, it):
        if (it.get("area") or "default") == "adult" and self.area != "adult":
            raise PermissionError("That one lives in the 18+ section. Open the 18+ section to use it.")
        return it

    def get(self, iid):
        return self._ok(self.lib.get(iid))

    def person_image(self, iid):
        return self._ok(self.lib.person_image(iid))

    def ref_image(self, iid, allowed=REF_ROLES):
        return self._ok(self.lib.ref_image(iid, allowed))

    def list(self, **kw):
        kw["area"] = self.area
        return self.lib.list(**kw)

    def list_usable(self, **kw):
        """Everything this area may use: the 18+ section can also use normal items; the normal area only its own."""
        kw["area"] = "all" if self.area == "adult" else "default"
        return self.lib.list(**kw)
