"""Turn ComfyUI's official video templates into Easy Studio API workflows (app/workflows/vm_*.json).

  python tools/build_video_models.py  [--templates DIR] [--object-info /tmp/object_info.json]

Steps per template: inline subgraphs -> UI-to-API convert -> turn the prompt enhancer OFF and remove it
(it rewrites the user's words with a second AI) -> keep only what the SaveVideo output needs ->
replace the demo prompt with a neutral one. Controls are then found by app/wfdetect.py at run time.
Templates come from the comfyui-workflow-templates package (v0.11.100, Nov 2026).
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
import ui2api as U  # noqa: E402
import wfdetect as D  # noqa: E402

DEFAULT_T = "/tmp/cvenv/lib/python3.13/site-packages/comfyui_workflow_templates_json/templates/"
# out id -> (template, nodes to un-bypass)
BUILD = {
    "vm_wan22_t2v": ("video_wan2_2_14B_t2v", []),
    "vm_wan22_5b_t2v": ("video_wan2_2_5B_ti2v", []),
    "vm_wan22_5b_i2v": ("video_wan2_2_5B_ti2v", ["56"]),
    "vm_ltx25_t2v": ("video_ltx2_5_t2v", []),
    "vm_ltx25_i2v": ("video_ltx2_5_i2v", []),
    "vm_ltx25_flf2v": ("video_ltx2_5_flf2v", []),
    "vm_hunyuan15_t2v": ("video_hunyuan_video_1.5_720p_t2v", []),
    "vm_hunyuan15_i2v": ("video_hunyuan_video_1.5_720p_i2v", []),
    "vm_kandinsky5_t2v": ("video_kandinsky5_t2v", []),
    "vm_kandinsky5_i2v": ("video_kandinsky5_i2v", []),
}
NEUTRAL = "an adult woman turns toward the camera and smiles, natural motion, cinematic lighting"


def build(tdir, tname, unbypass):
    ui = json.load(open(os.path.join(tdir, tname + ".json")))
    for n in ui["nodes"]:
        if str(n["id"]) in unbypass:
            n["mode"] = 0
    for sg in ui.get("definitions", {}).get("subgraphs", []):
        for n in sg["nodes"]:
            if str(n["id"]) in unbypass:
                n["mode"] = 0
    api = U.convert(U.flatten(ui))
    # prompt enhancer: resolve its switch to the user's own text, then drop it
    for sid, n in list(api.items()):
        if n["class_type"] != "ComfySwitchNode" or sid not in api:
            continue
        sw = n["inputs"].get("switch")
        if isinstance(sw, list) and api.get(sw[0], {}).get("class_type") == "PrimitiveBoolean" and \
                re.search(r"enhanc", api[sw[0]]["_meta"]["title"], re.I):
            U.resolve_switch(api, sid, "on_false")
    outs = [k for k, v in api.items() if v["class_type"] in D.VIDEO_OUTPUTS]
    api = U.prune(api, outs)
    a = D.analyse(api)
    for nid, k in a["prompt"]:
        api[nid]["inputs"][k] = NEUTRAL
    for n in api.values():  # SaveVideo prefix -> our own
        if n["class_type"] in D.VIDEO_OUTPUTS and "filename_prefix" in n["inputs"]:
            n["inputs"]["filename_prefix"] = "easy_studio/video"
    return api


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates", default=DEFAULT_T)
    a = ap.parse_args()
    for out, (t, ub) in BUILD.items():
        api = build(a.templates, t, ub)
        info = D.analyse(api)
        json.dump(api, open(os.path.join(ROOT, "app", "workflows", out + "_api.json"), "w"), indent=1)
        print(f"{out}: {len(api)} nodes, mode={info['mode']}, " + "; ".join(D.summary(info)))


if __name__ == "__main__":
    main()
