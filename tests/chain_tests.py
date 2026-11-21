# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""S4-7: the hand-off chain picture -> video -> longer video -> 3D, closed on the mock.

Unit checks: the .glb check (Codex finding N05), the 5B timing, where the joins are, the 3D engine
from the machine profile, and the unscored-proof rules (D-C-28).
End to end: one fictional adult (stated age 30, clothed, D-C-27) through create, an unscored 5B
proof, extend and 3D on the m5_max profile; then the server profile for the 14B loop and TRELLIS.
"""
import json
import os
import struct
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

BAD_GLB_SEED = 4040404  # tests/mock_comfy.py writes a broken .glb for this seed
ADULT = {"name": "Evidence", "gender": "man", "age": 30, "style": "photo"}


def glb(vertices=None, indices=None, mutate=None):
    """A small binary glTF. mutate(doc) can break the JSON before it is packed."""
    vertices = vertices or [(-.5, 0, -.3), (.5, 0, -.3), (.5, 1.7, -.3), (-.5, 1.7, -.3),
                            (-.5, 0, .3), (.5, 0, .3), (.5, 1.7, .3), (-.5, 1.7, .3)]
    indices = indices if indices is not None else [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4,
                                                   3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5]
    vb = b"".join(struct.pack("<3f", *v) for v in vertices)
    ib = b"".join(struct.pack("<H", i) for i in indices)
    ib += b"\x00" * ((4 - len(ib) % 4) % 4)
    lo = [min(v[k] for v in vertices) for k in range(3)]
    hi = [max(v[k] for v in vertices) for k in range(3)]
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
           "buffers": [{"byteLength": len(vb) + len(ib)}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vb)},
                           {"buffer": 0, "byteOffset": len(vb), "byteLength": len(ib)}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(vertices), "type": "VEC3", "min": lo, "max": hi},
                         {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"}]}
    if mutate:
        mutate(doc)
    js = json.dumps(doc).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    binb = vb + ib
    total = 12 + 8 + len(js) + 8 + len(binb)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js
            + struct.pack("<I4s", len(binb), b"BIN\x00") + binb)


def _refused(fn, contains=""):
    try:
        fn()
    except Exception as e:  # noqa: BLE001 -- any refusal type counts; the text is checked
        return contains.lower() in str(e).lower()
    return False


def unit(check):
    print("\n[chain] Hand-off chain: .glb check, 5B timing, joins, 3D engine, unscored proof")
    import comfy_client as cc
    import machine_profiles
    import mesh_check
    import pipelines as P
    import pipelines_v3 as P3
    import video_tools as V

    good = glb()
    stats = mesh_check.glb_stats_bytes(good)
    check("a valid .glb reports its vertices, faces and bounding box",
          stats["vertices"] == 8 and stats["faces"] == 12 and stats["bbox"] == {"min": [-.5, 0, -.3], "max": [.5, 1.7, .3]},
          stats)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "cube.glb")
        with open(path, "wb") as f:
            f.write(good)
        check("the file reader agrees with the byte reader", mesh_check.glb_stats(path)["faces"] == 12)
    bad = {
        "a header with nothing behind it": struct.pack("<4sII", b"glTF", 2, 64) + b"\x00" * 8,
        "the wrong magic": b"gltf" + good[4:],
        "container version 1": good[:4] + struct.pack("<I", 1) + good[8:],
        "a length that does not match": good[:8] + struct.pack("<I", len(good) + 4) + good[12:],
        "a truncated file": good[:-10],
        "no JSON chunk": struct.pack("<4sII", b"glTF", 2, 20) + struct.pack("<I4s", 0, b"BIN\x00"),
        "JSON that does not parse": glb()[:20] + b"x" + glb()[21:],
        "asset version 1.0": glb(mutate=lambda d: d["asset"].update(version="1.0")),
        "no mesh": glb(mutate=lambda d: d.update(meshes=[])),
        "no POSITION": glb(mutate=lambda d: d["meshes"][0]["primitives"][0].update(attributes={})),
        "a buffer view past the binary chunk": glb(mutate=lambda d: d["bufferViews"][0].update(byteLength=10 ** 6)),
        "an accessor past its view": glb(mutate=lambda d: d["accessors"][0].update(count=10 ** 5)),
        "mesh data in an outside file": glb(mutate=lambda d: d["buffers"][0].update(uri="https://example.invalid/x.bin")),
        "no triangles": glb(indices=[0, 1]),
    }
    for name, data in bad.items():
        check(f".glb with {name} is refused", _refused(lambda d=data: mesh_check.glb_stats_bytes(d)), name)
        check(f"the ComfyUI download check calls .glb with {name} corrupt", cc.media_problem("m.glb", data) == "corrupt")
    check("the ComfyUI download check accepts a valid .glb", cc.media_problem("m.glb", good) is None)

    # Runtime report 19:55 ET: ComfyUI 0.43.0 refused weight_dtype "fp16" on the 5B graph (UNETLoader has no fp16 choice).
    bad_dtype = []
    folder = os.path.join(HERE, "..", "app", "workflows")
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".json"):
            graph = json.load(open(os.path.join(folder, fname), encoding="utf-8"))
            bad_dtype += [(fname, n["inputs"].get("weight_dtype")) for n in graph.values()
                          if isinstance(n, dict) and n.get("class_type") == "UNETLoader"
                          and n.get("inputs", {}).get("weight_dtype") not in cc.UNET_WEIGHT_DTYPES]
    check("every shipped UNETLoader asks for a weight_dtype ComfyUI 0.43.0 accepts", not bad_dtype, bad_dtype[:4])
    check("the ComfyUI 0.43.0 UNETLoader list has no fp16 or bf16", not {"fp16", "bf16"} & set(cc.UNET_WEIGHT_DTYPES))
    five_b = json.load(open(os.path.join(HERE, "..", "app", "workflows", P.FIVE_B_WORKFLOW), encoding="utf-8"))
    check("2 s on the 5B model is 49 frames at 24 fps", P._five_b_timing(five_b, 2) == (49, False, 24.0))
    check("4 s on the 5B model is 97 frames", P._five_b_timing(five_b, 4)[:2] == (97, False))
    check("8 s on the 5B model stops at the template's 121 frames and chains the rest",
          P._five_b_timing(five_b, 8) == (121, True, 24.0))

    with tempfile.TemporaryDirectory() as tmp:
        a = V.make_test_video(os.path.join(tmp, "a.mp4"), frames=49, fps=24)
        b = V.make_test_video(os.path.join(tmp, "b.mp4"), frames=49, fps=24)
        joins = P.join_points([a, b, b])
        check("join points: each added clip starts where the last one ended",
              [j["frame"] for j in joins] == [49, 97] and abs(joins[0]["seconds"] - 49 / 24) < 0.01, joins)
        out = V.stitch([a, b], os.path.join(tmp, "ab.mp4"))
        check("the joined video has every frame but the repeated one", V.probe(out)["frames"] == 49 + 48)

    profiles = machine_profiles.load()["profiles"]
    mac, server, card = (dict(profiles[k], id=k) for k in ("m5_max", "rtx_pro_6000", "rtx_4090"))
    check("3D on the Mac defaults to the Hunyuan3D shape engine", P.model3d_engine({}, mac) == "hunyuan")
    check("3D on the server defaults to TRELLIS.2", P.model3d_engine({}, server) == "trellis")
    check("a request can still name its 3D engine", P.model3d_engine({"engine": "trellis"}, mac) == "trellis")
    check("an unknown 3D engine is refused", _refused(lambda: P.model3d_engine({"engine": "splat"}, mac), "engine"))
    check("the Mac and the 4090 animate on the 5B model; the server does not",
          P.five_b_profile(mac) and P.five_b_profile(card) and not P.five_b_profile(server))

    P.set_area("default")
    check("D-C-28: no scores on the Mac's first-test 5B proof is an unscored proof", P.unscored_proof_allowed({}, mac))
    check("a request that carries scores still goes through the still-first gate",
          not P.unscored_proof_allowed({"qc": {"variants": []}}, mac))
    check("a photoreal (finished) clip still needs scored keyframes", not P.unscored_proof_allowed({"photoreal": True}, mac))
    check("A-to-B is never an unscored proof", not P.unscored_proof_allowed({}, mac, end={"id": "x"}))
    check("the 4090 preview card is not the first-test machine, so it needs scores", not P.unscored_proof_allowed({}, card))
    check("the server needs scores", not P.unscored_proof_allowed({}, server))
    P.set_area("adult")
    check("the unscored proof is everyday-section only", not P.unscored_proof_allowed({}, mac))
    P.set_area("default")
    proof = {"id": "p1", "type": "image", "role": "made", "character": "c1", "proof": True, "qc_status": "unscored_proof"}
    child = P._meta_from(proof)
    check("anything made from a proof stays a proof", child.get("proof") is True and child.get("qc_status") == "unscored_proof")
    check("a scored item is not marked as a proof", "proof" not in P._meta_from({"id": "s1", "role": "made"}))
    check("training refuses a picture from an unscored proof",
          _refused(lambda: P3._check_training_source(None, proof, {"id": "c1"}), "unscored motion proof"))
    # Reviewer S2 at 364961d: a path that does not copy the mark must not lose it. The check walks parent links.
    lineage = {"p1": proof, "c1": {"id": "c1", "parent": "p1"}, "c2": {"id": "c2", "parent": "c1"},
               "loop": {"id": "loop", "parent": "loop"}, "orphan": {"id": "orphan", "parent": "gone"}}
    get = lineage.__getitem__
    check("a grandchild of a proof that lost the mark is still a proof", P.is_proof(lineage["c2"], get))
    check("without a lookup only the item's own mark counts", not P.is_proof(lineage["c2"]))
    check("a parent loop ends the walk", not P.is_proof(lineage["loop"], get))
    check("a missing parent ends the walk without blocking the child", not P.is_proof(lineage["orphan"], get))
    check("the mark to copy is found through the parents", P.proof_mark(lineage["c2"], get) == {"proof": True, "qc_status": "unscored_proof"}
          and P.proof_mark({"id": "s1"}, get) == {})
    ctx = types.SimpleNamespace(lib=types.SimpleNamespace(get=get))
    unmarked = dict(lineage["c2"], type="image", role="made", character="c1")
    check("training refuses an unmarked picture whose parent chain reaches a proof",
          _refused(lambda: P3._check_training_source(ctx, unmarked, {"id": "c1"}), "unscored motion proof"))


def _job(a, kind, params, **kw):
    return a.job(kind, params, **kw)


def _last_graph(requests, mock_url):
    return requests.get(mock_url + "/mock/log").json()[-1]


def _graphs_since(requests, mock_url, start):
    return requests.get(mock_url + "/mock/log").json()[start:]


def _unet(graph):
    return [n["inputs"].get("unet_name") or n["inputs"].get("ckpt_name") for n in graph.values()
            if n.get("class_type") in ("UNETLoader", "ImageOnlyCheckpointLoader")]


def e2e(a, mock_url, out_dir, ffprobe_frames, requests, check):
    print("\n[chain] Picture -> video -> longer video -> 3D on the mock (m5_max, then the server profile)")
    import shot_qc
    j = _job(a, "create", {"dna": dict(ADULT), "extra_scene": "fully clothed in a grey suit, standing in a bright office",
                           "count": 2, "aspect": "wide", "look": "realistic", "advanced": {"seed": 20261106}})
    stills = j.get("results") or []
    check("E1: two stills of one fictional adult", j["status"] == "done" and len(stills) == 2, j.get("error"))
    if len(stills) < 2:
        return
    e1 = stills[0]
    check("E1 provenance names the Z-Image Turbo workflow and the seed",
          (e1.get("provenance") or {}).get("workflow") == "image_zimage_turbo_api.json"
          and (e1.get("provenance") or {}).get("seed") == 20261106, e1.get("provenance"))

    j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 4, "mode": "fast", "quality": "480"})
    check("E2 with no scores runs as an unscored 5B proof on the Mac (D-C-28)", j["status"] == "done", j.get("error"))
    e2 = (j.get("results") or [None])[0]
    if not e2:
        return
    prov = e2.get("provenance") or {}
    check("E2 is flagged as a proof, never as QC-passed",
          e2.get("proof") is True and e2.get("qc_status") == "unscored_proof" and (prov.get("qc") or {}).get("status") == "unscored_proof"
          and (prov.get("qc") or {}).get("scores") is None and not (prov.get("qc") or {}).get("variants"), prov.get("qc"))
    check("E2 ran the 5B template at 24 fps", prov.get("workflow") == "vm_wan22_5b_i2v_api.json" and prov.get("fps") == 24
          and prov.get("video_proof") == "wan22_ti2v_5b" and prov.get("machine") == "m5_max", prov)
    graph = _last_graph(requests, mock_url)
    check("E2 sent the 5B fp16 weights", "wan2.2_ti2v_5B_fp16.safetensors" in _unet(graph), _unet(graph))
    dtypes = [n["inputs"].get("weight_dtype") for n in graph.values() if n.get("class_type") == "UNETLoader"]
    check("E2 loads the 5B file at its own precision (weight_dtype default, as ComfyUI 0.43.0 allows)",
          dtypes == ["default"], dtypes)
    n2, _, _ = ffprobe_frames(a.file(e2))
    check("E2 is 4 s: 97 frames at 24 fps", n2 == 97 and prov.get("frames") == 97, (n2, prov.get("frames")))
    check("E2 is at least 2 s", n2 / 24 >= 2)

    other = stills[1]
    failing = shot_qc.passing_qc(e1["id"], other["id"])
    failing["variants"][0]["scores"]["hands"] = 2
    j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 2, "qc": failing})
    check("a request with a failing score is still refused", j["status"] in ("error", "refused"), j.get("error"))
    j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 2, "photoreal": True})
    check("a photoreal clip with no scores is still refused", j["status"] in ("error", "refused")
          and "keyframe" in (j.get("error") or "").lower(), j.get("error"))
    j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 2, "qc": shot_qc.passing_qc(e1["id"], other["id"])})
    scored = (j.get("results") or [{}])[0]
    check("the fully scored path keeps its scores and is not a proof", j["status"] == "done" and not scored.get("proof")
          and ((scored.get("provenance") or {}).get("qc") or {}).get("use") == e1["id"], j.get("error"))

    start = len(requests.get(mock_url + "/mock/log").json())
    j = _job(a, "extend", {"video": e2["id"], "segments": [{"motion": "walk", "seconds": 4}]})
    check("E3: extend runs on the Mac", j["status"] == "done", j.get("error"))
    e3 = (j.get("results") or [None])[0]
    if e3:
        sent = _graphs_since(requests, mock_url, start)
        check("E3 used only the 5B template, from the last frame", sent and all(
            "wan2.2_ti2v_5B_fp16.safetensors" in _unet(g) for g in sent), [_unet(g) for g in sent])
        p3 = e3.get("provenance") or {}
        n3, _, _ = ffprobe_frames(a.file(e3))
        check("E3 is E2 plus a 4 s clip, joined without the repeated frame", n3 == 97 + 96, n3)
        check("E3 is at least 1.8 times E2", n3 >= 1.8 * n2, (n2, n3))
        check("E3 provenance names the 5B workflow, the machine and the join point",
              p3.get("workflow") == "vm_wan22_5b_i2v_api.json" and p3.get("machine") == "m5_max"
              and p3.get("join_points") and p3["join_points"][0]["frame"] == 97 and p3.get("source") == e2["id"], p3)
        check("E3 stays a proof because E2 was one", e3.get("proof") is True and e3.get("qc_status") == "unscored_proof")
        still = _job(a, "video_still", {"video": e3["id"], "frame": "last"})
        frame = (still.get("results") or [{}])[0]
        check("a still taken from a proof is still a proof", still["status"] == "done" and frame.get("proof") is True,
              still.get("error"))
        if frame.get("id"):
            j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 2,
                                  "qc": shot_qc.passing_qc(e1["id"], frame["id"])})
            check("a proof frame can't be a scored keyframe", j["status"] in ("error", "refused")
                  and "proof" in (j.get("error") or "").lower(), j.get("error"))
            r = a.post("/api/characters", json=dict(ADULT, name="Proof portrait", hero=frame["id"]))
            said = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            check("a proof frame can't be a character's portrait", r.status_code == 400
                  and "proof" in str(said.get("error") or said.get("detail") or "").lower(), (r.status_code, r.text[:200]))
    j = _job(a, "video_any", {"model": "wan22_5b_i2v", "extend_from": e2["id"], "text": "the camera slowly pans", "seconds": 2})
    more = (j.get("results") or [{}])[0]
    check("video_any extending a proof keeps the proof mark", j["status"] == "done" and more.get("proof") is True
          and more.get("qc_status") == "unscored_proof", j.get("error") or more)
    j = _job(a, "extend", {"video": e2["id"], "segments": [{"motion": "walk", "seconds": 2}], "loop": True})
    check("a loop on the Mac is refused with a plain reason", j["status"] in ("error", "refused")
          and "14B" in (j.get("error") or ""), j.get("error"))

    j = _job(a, "model3d", {"image": e1["id"]})
    check("E4: 3D with no engine named runs on the Mac", j["status"] == "done", j.get("error"))
    e4 = (j.get("results") or [None])[0]
    if e4:
        p4 = e4.get("provenance") or {}
        graph = _last_graph(requests, mock_url)
        check("E4 used the Hunyuan3D 2.1 shape engine from the machine profile",
              "hunyuan_3d_v2.1.safetensors" in _unet(graph) and p4.get("engine") == "hunyuan"
              and p4.get("workflow") == "3d_hunyuan21_shape_api.json", (p4, _unet(graph)))
        check("E4 provenance carries the mesh numbers", (p4.get("mesh") or {}).get("vertices") == 8
              and (p4.get("mesh") or {}).get("faces") == 12 and (p4.get("mesh") or {}).get("bbox"), p4.get("mesh"))
        check("E4 is a .glb file", a.file(e4)[:4] == b"glTF")
    before = len(a.get("/api/gallery?type=model&limit=2000").json()["items"])
    j = _job(a, "model3d", {"image": e1["id"], "advanced": {"seed": BAD_GLB_SEED}})
    after = len(a.get("/api/gallery?type=model&limit=2000").json()["items"])
    check("N05: a broken .glb from ComfyUI is refused and not saved", j["status"] in ("error", "refused")
          and "glb" in (j.get("error") or "").lower() and after == before, (j.get("error"), before, after))

    # The server profile: the 14B loop and TRELLIS.2 still work, and no-score video is refused there.
    over = os.path.join(out_dir, "machine_profile.json")
    with open(over, "w", encoding="utf-8") as f:
        json.dump({"default": "rtx_pro_6000"}, f)
    try:
        j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 2})
        check("on the server a clip with no scores is refused", j["status"] in ("error", "refused")
              and "keyframe" in (j.get("error") or "").lower(), j.get("error"))
        j = _job(a, "video", {"image": e1["id"], "motion": "look", "seconds": 3, "qc": shot_qc.passing_qc(e1["id"], other["id"])})
        v14 = (j.get("results") or [None])[0]
        check("on the server a scored clip runs on the 14B model", j["status"] == "done"
              and (v14.get("provenance") or {}).get("video_proof") == "wan22_14b_i2v", j.get("error"))
        if v14:
            start = len(requests.get(mock_url + "/mock/log").json())
            j = _job(a, "extend", {"video": v14["id"], "segments": [{"motion": "look", "seconds": 2},
                                                                     {"text": "she waves", "seconds": 2}], "loop": True})
            sent = _graphs_since(requests, mock_url, start)
            check("on the server, extend 2 parts + loop runs on the 14B model", j["status"] == "done" and sent and not any(
                "wan2.2_ti2v_5B_fp16.safetensors" in _unet(g) for g in sent), j.get("error"))
        j = _job(a, "model3d", {"image": e1["id"], "quality": "max"})
        sent = json.dumps(_last_graph(requests, mock_url))
        check("on the server, 3D defaults to TRELLIS.2 with the quality settings",
              j["status"] == "done" and "700000" in sent and ((j.get("results") or [{}])[0].get("provenance") or {}).get("engine") == "trellis",
              j.get("error"))
    finally:
        os.remove(over)

