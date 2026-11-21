# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Which ComfyUI process runs which model family (PRD §4).

Owner's home box (when hardware is switched on; profile rtx_pro_6000 is still confirmed: false):
    process 8188 -> GPU0 -> Z-Image family (Z-Image, Chroma1-HD, Qwen-Image-Edit-2511, Flux, SDXL)
    process 8189 -> GPU1 -> Wan 2.2 14B (high + low)
Two processes never share a GPU. Changing model family on one process frees ComfyUI memory on that
process first. The Mac's own profile is Wan 5B; it is not the 14B film machine.

Build sessions and CI use the mock engine only: every process points at the one mock URL, nothing is
downloaded and no GPU is called. The owner can override the map with outputs/hardware_map.json:

    {"processes": [{"port": 8188, "gpu": 0, "url": "http://127.0.0.1:8188", "families": ["zimage", ...]},
                   {"port": 8189, "gpu": 1, "url": "http://127.0.0.1:8189", "families": ["wan14b"]}]}
"""
import json
import os
import threading

DEFAULT_PROCESSES = [
    {"port": 8188, "gpu": 0, "families": ["zimage", "chroma", "qwen_edit", "flux", "flux2", "krea2", "sdxl",
                                          "trellis2", "hunyuan3d", "other"],
     "label": "GPU0 · image lane"},
    {"port": 8189, "gpu": 1, "families": ["wan14b", "wan5b", "hunyuan15", "ltx25", "kandinsky5"],
     "label": "GPU1 · video lane"},
]
# VRAM estimates per family, Director and scorer placement: app/placement.json (estimates until measured).


def family_of_graph(graph):
    """The model family a ComfyUI graph loads, from its model loader file names."""
    names = []
    for node in (graph or {}).values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        for key in ("unet_name", "ckpt_name"):
            if isinstance(inputs.get(key), str):
                names.append(inputs[key].lower())
    blob = " ".join(names)
    if "wan" in blob and "14b" in blob:
        return "wan14b"
    if "wan" in blob and "5b" in blob:
        return "wan5b"
    # Specific families before the generic tokens (flux-2 before flux, hunyuanvideo before hunyuan_3d).
    for token, fam in (("hunyuanvideo", "hunyuan15"), ("ltx", "ltx25"), ("kandinsky", "kandinsky5"),
                       ("trellis", "trellis2"), ("hunyuan_3d", "hunyuan3d"), ("hunyuan3d", "hunyuan3d"),
                       ("krea", "krea2"), ("flux-2", "flux2"), ("flux2", "flux2"),
                       ("chroma", "chroma"), ("qwen", "qwen_edit"), ("z_image", "zimage"), ("flux", "flux"),
                       ("noob", "sdxl"), ("sdxl", "sdxl")):
        if token in blob:
            return fam
    return "other"


class HardwareMap:
    def __init__(self, processes=None, default_url="", mock=True):
        self.processes = [dict(p) for p in (processes or DEFAULT_PROCESSES)]
        self.mock = mock
        for proc in self.processes:
            proc.setdefault("url", default_url)
        self._validate()
        self.last_family = {}
        self.freed = []
        self.lock = threading.Lock()

    def _validate(self):
        ports = [p.get("port") for p in self.processes]
        gpus = [p.get("gpu") for p in self.processes]
        if len(set(ports)) != len(ports):
            raise ValueError("Two ComfyUI processes cannot use the same port.")
        if len(set(gpus)) != len(gpus):
            raise ValueError("Two ComfyUI processes never share a GPU.")
        seen = {}
        for proc in self.processes:
            for fam in proc.get("families") or []:
                if fam in seen:
                    raise ValueError(f"The {fam} family is mapped to two processes.")
                seen[fam] = proc["port"]

    @classmethod
    def load(cls, out_dir, default_url):
        path = os.path.join(out_dir, "hardware_map.json")
        data = {}
        if os.path.exists(path):
            try:
                data = json.load(open(path, encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        procs = data.get("processes") if isinstance(data.get("processes"), list) else None
        return cls(procs, default_url=default_url, mock=bool(data.get("mock", procs is None)))

    def process_for(self, family):
        for proc in self.processes:
            if family in (proc.get("families") or []):
                return proc
        return self.processes[0]

    def before_run(self, family, client):
        """Call ComfyUI memory-free on the process when the family on that process changes."""
        proc = self.process_for(family)
        with self.lock:
            prev = self.last_family.get(proc["port"])
            self.last_family[proc["port"]] = family
        if prev is not None and prev != family:
            try:
                client.free_memory()
            except Exception:
                pass  # the next job still runs; a missing /free is not a reason to stop
            self.freed.append({"port": proc["port"], "from": prev, "to": family})
            return True
        return False

    def summary(self):
        return {"mock": self.mock, "processes": [
            {k: p.get(k) for k in ("port", "gpu", "families", "label")} for p in self.processes],
            "note": "This session uses the mock engine only. No weights are downloaded and no GPU is called."}
