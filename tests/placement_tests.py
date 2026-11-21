# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Lane placement: every template lands on the right GPU lane and every lane stays under the 88 GB plan."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import hardware_map as HW  # noqa: E402

VIDEO = {"wan14b", "wan5b", "hunyuan15", "ltx25", "kandinsky5"}


def unit(check):
    print("\n[lanes] GPU lane placement")
    place = json.load(open(os.path.join(HERE, "..", "app", "placement.json"), encoding="utf-8"))
    procs = {p["gpu"]: set(p["families"]) for p in HW.DEFAULT_PROCESSES}
    lane_gpu = {k: v["gpu"] for k, v in place["lanes"].items()}
    fams = place["families"]
    check("placement lists exactly the families the processes serve", set(fams) == procs[0] | procs[1])
    check("each family sits on the lane its process serves",
          all(name in procs[lane_gpu[row["lane"]]] for name, row in fams.items()))
    folder = os.path.join(HERE, "..", "app", "workflows")
    wrong = []
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".json"):
            fam = HW.family_of_graph(json.load(open(os.path.join(folder, fname), encoding="utf-8")))
            is_video = fname.startswith(("video_", "vm_"))
            if fam not in fams or (is_video and fam not in VIDEO) or (not is_video and fam in VIDEO):
                wrong.append((fname, fam))
    check("every video template lands on the video lane and nothing else does", not wrong, wrong[:4])
    plan = place["plan_gb_per_card"]
    gpu0 = max(r["vram_est_gb"] for r in fams.values() if r["lane"] == "gpu0")
    gpu0 += place["director"]["vram_est_gb"] + place["scorer"]["vram_est_gb"]
    gpu1 = max(r["vram_est_gb"] for r in fams.values() if r["lane"] == "gpu1")
    check("GPU0 worst case (largest image family + Director + scorer) fits the plan", gpu0 <= plan, gpu0)
    check("GPU1 worst case fits the plan", gpu1 <= plan, gpu1)
    check("placement numbers are marked unmeasured", place["measured"] is False)
    # The Director: only listed hybrid profiles share GPU0; anything else takes GPU1 on its own (kit question, 06:59).
    director, top_image = place["director"], max(r["vram_est_gb"] for r in fams.values() if r["lane"] == "gpu0")
    shared = {k: v for k, v in director["profiles"].items() if v["lane"] == "gpu0"}
    check("every Director profile that shares GPU0 is hybrid and fits beside the largest image family and the scorer",
          shared and all(v["mode"] == "hybrid" and top_image + v["vram_est_gb"] + place["scorer"]["vram_est_gb"] <= plan
                         for v in shared.values()))
    check("an unlisted Director profile never shares GPU0", director["unlisted_profiles"] == "exclusive_gpu1")
    ports = {lane["port"] for lane in place["lanes"].values()} | {director["port"], 8001, 8002, 8003}
    llm = os.path.join(HERE, "..", "config", "llm_models.json")
    if os.path.exists(llm):
        for p in json.load(open(llm, encoding="utf-8"))["profiles"]:
            ports.add(int(p["base_url"].rsplit(":", 1)[1].split("/")[0]))
    check("the scorer's port is no lane's or Director profile's port", place["scorer"]["port"] not in ports,
          place["scorer"]["port"])
    check("the map still refuses a family on two processes",
          _raises(lambda: HW.HardwareMap([{"port": 1, "gpu": 0, "families": ["a"]}, {"port": 2, "gpu": 1, "families": ["a"]}])))


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


if __name__ == "__main__":
    failed = []

    def _check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {extra}"))
        if not cond:
            failed.append(name)
    unit(_check)
    sys.exit(1 if failed else 0)
