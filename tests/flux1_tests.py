# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Flux.1 dev (Ak's proven stack, D-10): template, look, lane and a mock still."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
sys.path.insert(0, HERE)

import comfy_client as cc  # noqa: E402
import hardware_map as HW  # noqa: E402
import photoreal  # noqa: E402


def unit(check):
    print("\n[flux1] Flux.1 dev template and look")
    wf = cc.load_workflow("image_flux1dev_api.json")
    loaders = {n["class_type"]: n["inputs"] for n in wf.values()}
    check("the template loads Flux.1 dev, T5-XXL + CLIP-L and the ae VAE",
          loaders["UNETLoader"]["unet_name"] == "flux1-dev.safetensors"
          and {loaders["DualCLIPLoader"]["clip_name1"], loaders["DualCLIPLoader"]["clip_name2"]} == {"t5xxl_fp16.safetensors", "clip_l.safetensors"}
          and loaders["VAELoader"]["vae_name"] == "ae.safetensors")
    titles = {(n.get("_meta") or {}).get("title") for n in wf.values()}
    check("the template keeps the titles fill() uses", {"POSITIVE", "NEGATIVE", "SEED", "SIZE"} <= titles)
    check("Flux.1 dev runs on the image lane", HW.family_of_graph(wf) == "flux"
          and HW.HardwareMap().process_for("flux")["gpu"] == 0)
    row = photoreal.look("flux")
    check("the Flux.1 dev look uses its template", row["workflow"] == "image_flux1dev_api.json" and row["model_id"] == "flux1_dev")
    check("the Flux.1 dev look is not 18+ only", photoreal.resolve_look({"look": "flux"}, "photo", "default")["id"] == "flux")
    filled = cc.fill(json.loads(json.dumps(wf)), prompt="a fictional adult, natural skin", negative="blurry", seed=7,
                     width=832, height=1216)
    ids = {(n.get("_meta") or {}).get("title"): nid for nid, n in wf.items()}  # fill() strips _meta from its copy
    check("fill() writes the prompt, seed and size", filled[ids["POSITIVE"]]["inputs"]["text"].startswith("a fictional adult")
          and filled[ids["SEED"]]["inputs"]["seed"] == 7 and filled[ids["SIZE"]]["inputs"]["width"] == 832
          and filled[ids["SIZE"]]["inputs"]["height"] == 1216)
    import mock_comfy
    check("the 0.43 node snapshot accepts the graph", not mock_comfy.validate(cc.finalize(filled)))
    cards = json.load(open(os.path.join(HERE, "..", "app", "model_cards.json"), encoding="utf-8"))["cards"]
    card = next((c for c in cards if c.get("id") == "flux1_dev"), {})
    check("the Flux.1 dev card says non-commercial and gated", card.get("commercial") == "no" and card.get("gated") is True)


def e2e(a, mock_url, requests):
    print("\n[flux1] Flux.1 dev still on the mock")
    dna = {"gender": "woman", "age": 31, "style": "photo", "name": "Lio", "traits": {"body": "average"}}
    j = a.job("create", {"dna": dna, "count": 1, "look": "flux", "camera": "closeup"})
    check = a.check
    check("a Flux.1 dev still is made", j["status"] == "done" and j["results"], j.get("error"))
    sent = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("the job sent the Flux.1 dev graph", "flux1-dev.safetensors" in sent and "FluxGuidance" in sent)
    if j.get("results"):
        check("still provenance names the Flux look", j["results"][0].get("provenance", {}).get("look") == "flux")


if __name__ == "__main__":
    failed = []

    def _check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {extra}"))
        if not cond:
            failed.append(name)
    unit(_check)
    sys.exit(1 if failed else 0)
