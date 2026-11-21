"""Tests for tools/evidence_run.py (the evidence run of the Easy Studio chain).

Run:  python tests/evidence_tests.py
Needs ffmpeg/ffprobe (as the app's own suite does). The last test starts the real app with the mock
ComfyUI (Tier 1) on free loopback ports, in temporary folders; Playwright is used when it is installed.
No test opens or displays any image, video or mesh: every check is a number read from the files.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import evidence_run as ev  # noqa: E402

FFMPEG = ev.ffbin("ffmpeg")


def make_glb(path, positions, indices, with_minmax=False):
    pos = b"".join(struct.pack("<3f", *p) for p in positions)
    idx = b"".join(struct.pack("<H", i) for i in indices)
    idx += b"\0" * (-len(idx) % 4)
    binchunk = pos + idx
    acc_pos = {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3"}
    if with_minmax:
        acc_pos["min"] = [min(p[k] for p in positions) for k in range(3)]
        acc_pos["max"] = [max(p[k] for p in positions) for k in range(3)]
    gltf = {"asset": {"version": "2.0", "generator": "evidence test"},
            "buffers": [{"byteLength": len(binchunk)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos)},
                            {"buffer": 0, "byteOffset": len(pos), "byteLength": len(indices) * 2}],
            "accessors": [acc_pos, {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}]}
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binchunk)
    with open(path, "wb") as fh:
        fh.write(b"glTF" + struct.pack("<II", 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(binchunk), 0x004E4942) + binchunk)


CUBE = [(-1, 0, -1), (1, 0, -1), (1, 2, -1), (-1, 2, -1), (-1, 0, 1), (1, 0, 1), (1, 2, 1), (-1, 2, 1)]
CUBE_IDX = [0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 2, 3, 7, 2, 7, 6, 1, 2, 6, 1, 6, 5, 0, 3, 7, 0, 7, 4]


def ffmpeg(*args):
    subprocess.run([FFMPEG, "-y", "-v", "error", *args], check=True, capture_output=True)


class Placeholders(unittest.TestCase):
    ctx = {"seed": 7, "prompt": "an office", "E1": {"id": "a1", "results": ["a1", "b2"]},
           "chain": {"qc": {"variants": [{"image": "{E1.results.1}"}]}}, "profile": {"id": "m5_max"}}

    def test_whole_placeholder_keeps_its_type_and_reads_lists(self):
        out = ev.resolve({"seed": "{seed}", "img": "{E1.results.1}", "t": "seed {seed} in {profile.id}"}, self.ctx)
        self.assertEqual(out, {"seed": 7, "img": "b2", "t": "seed 7 in m5_max"})

    def test_optional_placeholder_drops_the_key_and_a_missing_one_raises(self):
        self.assertEqual(ev.resolve({"qc": "{chain.nothing?}", "a": 1}, self.ctx), {"a": 1})
        self.assertEqual(ev.resolve(["{chain.nothing?}", "x"], self.ctx), ["x"])
        with self.assertRaises(KeyError):
            ev.resolve({"qc": "{chain.nothing}"}, self.ctx)

    def test_a_var_file_may_name_earlier_results(self):
        self.assertEqual(ev.resolve({"qc": "{chain.qc}"}, self.ctx), {"qc": {"variants": [{"image": "b2"}]}})

    def test_vars_from_the_command_line(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "qc.json")
        json.dump({"use": "{E1.id}"}, open(p, "w"))
        vals, files = ev.parse_vars(["qc=@" + p, "n=3", "word=plain"])
        self.assertEqual(vals, {"qc": {"use": "{E1.id}"}, "n": 3, "word": "plain"})
        self.assertEqual(files["qc"]["sha256"], ev.sha256_file(p))
        with self.assertRaises(ev.Stop):
            ev.parse_vars(["no equals sign"])


class ChainSpec(unittest.TestCase):
    def write(self, spec):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "chain.json")
        json.dump(spec, open(p, "w"))
        return p

    def base(self, subject="fictional_adult", **step):
        return {"subject": subject, "steps": [{"id": "E1", "kind": "create",
                                               "params": step or {"dna": {"age": 30}, "seed": "{seed}"}}]}

    def test_default_chain_loads_and_reads_in_order(self):
        spec = ev.load_chain(ev.DEFAULT_CHAIN)
        self.assertEqual([s["id"] for s in spec["steps"]], ["E1", "E2", "E3", "E4"])
        self.assertEqual(spec["subject"], "fictional_adult")
        self.assertEqual(ev.step_needs(spec["steps"][2]), {"E2"})
        self.assertEqual(ev.step_needs(spec["steps"][3]), {"E1"})

    def test_refusals(self):
        bad = [
            ({"subject": "anything", "steps": [{"id": "E1", "kind": "create", "params": {}}]}, "subject"),
            ({"subject": "place", "steps": [{"id": "E1", "kind": "x", "params": {"image": "{E2.id}"}},
                                            {"id": "E2", "kind": "y", "params": {}}]}, "before they exist"),
            (self.base(area="adult"), "area"),
            ({"subject": "place", "steps": [{"id": "E1", "kind": "x", "area": "adult", "params": {}}]}, "area"),
            (self.base("place", text="a lighthouse and a woman on the rocks"), "names a person"),
            (self.base(text="lingerie in the office"), "not clothed"),
            (self.base(dna={"age": 19}), "21 or more"),
            (self.base(dna={"age": "thirty"}), "21 or more"),
            ({"subject": "fictional_adult", "steps": [{"id": "E1", "kind": "x", "params": {}}],
              "vars": {"x": {"text": "a teen at school"}}}, "not clothed"),
            ({"subject": "place", "steps": [{"id": "E1", "kind": "x", "params": {}},
                                            {"id": "E1", "kind": "y", "params": {}}]}, "unique id"),
        ]
        for spec, words in bad:
            with self.subTest(words=words), self.assertRaises(ev.Stop) as cm:
                ev.load_chain(self.write(spec))
            self.assertIn(words, str(cm.exception))

    def test_place_and_adult_chains_that_pass(self):
        ev.load_chain(self.write(self.base("place", text="a stone lighthouse on a rocky coast at dusk")))
        ev.load_chain(self.write(self.base(dna={"age": 30, "gender": "man"}, text="tailored suit, calm office")))


class Media(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(prefix="evidence_media_")
        cls.moving = os.path.join(cls.d, "moving.mp4")
        cls.still = os.path.join(cls.d, "still.mp4")
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24", "-t", "2", "-pix_fmt", "yuv420p", cls.moving)
        ffmpeg("-f", "lavfi", "-i", "color=c=gray:size=320x240:rate=24", "-t", "1", "-pix_fmt", "yuv420p", cls.still)

    def test_video_numbers(self):
        v = ev.probe_video(self.moving)
        self.assertEqual((v["width"], v["height"], v["frames"]), (320, 240, 48))
        self.assertAlmostEqual(v["fps"], 24.0)
        self.assertAlmostEqual(v["duration_s"], 2.0, delta=0.05)
        moving = ev.frame_stats(self.moving, join_frame=24)
        still = ev.frame_stats(self.still)
        self.assertEqual(moving["decoded_frames"], 48)
        self.assertGreater(moving["mean_frame_diff"], 0.3)
        self.assertIn("ratio_to_median", moving["join"])
        self.assertLess(still["mean_frame_diff"], 0.05)
        self.assertEqual(still["still_pairs"], 23)
        self.assertLess(still["first_frame_std"], 1)

    def test_image_numbers(self):
        from PIL import Image
        flat, busy = os.path.join(self.d, "flat.png"), os.path.join(self.d, "busy.png")
        Image.new("RGB", (64, 32), (90, 90, 90)).save(flat)
        Image.effect_noise((64, 32), 60).convert("RGB").save(busy)
        a, b = ev.probe_image(flat), ev.probe_image(busy)
        self.assertEqual((a["width"], a["height"], a["pixel_std"]), (64, 32, 0.0))
        self.assertGreater(b["pixel_std"], 20)

    def test_glb_counts_and_bbox_with_and_without_min_max(self):
        for with_minmax in (False, True):
            p = os.path.join(self.d, f"cube_{with_minmax}.glb")
            make_glb(p, CUBE, CUBE_IDX, with_minmax)
            m = ev.probe_glb(p)
            self.assertEqual((m["vertices"], m["faces"], m["primitives"]), (8, 12, 1))
            self.assertEqual(m["bbox"]["size"], [2.0, 2.0, 2.0])
            self.assertEqual(ev.probe_output(p, "model")["mesh"]["faces"], 12)
        junk = os.path.join(self.d, "junk.glb")
        open(junk, "wb").write(b"not a mesh at all")
        with self.assertRaises(ValueError):
            ev.probe_glb(junk)

    def test_obj_counts(self):
        p = os.path.join(self.d, "quad.obj")
        open(p, "w").write("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n")
        m = ev.probe_obj(p)
        self.assertEqual((m["vertices"], m["faces"], m["bbox"]["size"]), (4, 2, [1.0, 1.0, 0.0]))


class ModelsAndWorkflows(unittest.TestCase):
    def test_models_are_found_hashed_once_and_cached(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "models", "diffusion_models"))
        f = os.path.join(d, "models", "diffusion_models", "unet_a.safetensors")
        open(f, "wb").write(b"x" * 1000)
        cache_path = os.path.join(d, "cache.json")
        idx = ev.ModelIndex([os.path.join(d, "models")], ev.HashCache(cache_path))
        row = idx.row("unet_a.safetensors")
        self.assertEqual((row["path"], row["sha256"], row["size"]), (f, ev.sha256_file(f), 1000))
        self.assertIsNone(idx.row("missing.safetensors")["sha256"])
        self.assertEqual(len(json.load(open(cache_path))), 1)
        self.assertEqual(ev.HashCache(cache_path).sha(f), row["sha256"])

    def test_template_match_breaks_shape_ties_on_model_files(self):
        shape = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "a.safetensors"}},
                 "2": {"class_type": "KSampler", "inputs": {"seed": 1}}}
        other = json.loads(json.dumps(shape))
        other["1"]["inputs"]["unet_name"] = "b.safetensors"
        sent = json.loads(json.dumps(other))
        sent["2"]["inputs"]["seed"] = 99
        m = ev.match_template(sent, {"a_api.json": shape, "b_api.json": other})
        self.assertEqual((m["name"], m["score"], m["model_files_matched"]), ("b_api.json", 1.0, 1))
        self.assertEqual(ev.workflow_seeds(sent), [99])
        self.assertEqual(ev.workflow_models(sent)[0]["name"], "b.safetensors")

    def test_log_tap_keeps_only_new_lines_and_withholds_credentials(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "app.log")
        open(p, "w").write("old line\n")
        tap = ev.LogTap(p)
        tap.mark()
        with open(p, "a") as fh:
            fh.write("job started\nPassword for other devices: x\nAuthorization: Basic abc\njob done\n")
        row = ev.save_excerpt(tap.excerpt(), os.path.join(d, "x.log"), d)
        self.assertEqual(row["lines_total"], 4)
        self.assertEqual(row["tail"][0], "job started")
        self.assertEqual(row["tail"][3], "job done")
        self.assertTrue(all("withheld" in x for x in row["tail"][1:3]))
        self.assertNotIn("abc", open(os.path.join(d, "x.log")).read())
        self.assertEqual(ev.save_excerpt(ev.LogTap(None).excerpt(), os.path.join(d, "y.log"), d), {"available": False})


class Checks(unittest.TestCase):
    def rec(self, sid, **video):
        return {"id": sid, "job": {"status": "done"}, "workflows": [{"template": {"name": "vm_wan22_5b_i2v_api.json"}}],
                "output": {"sha256": "ab", "type": "video", "video": {"width": 512, "height": 768, "frames": 65,
                                                                      "fps": 24.0, **video}}}

    def test_extend_must_reach_one_point_eight_times_the_first_clip(self):
        e2 = self.rec("E2", duration_s=2.7)
        for dur, ok in ((4.86, True), (4.85, False)):
            checks = []
            ev.step_checks(self.rec("E3", duration_s=dur), {"E2": e2},
                           {"min_duration_ratio": {"of": "E2", "ratio": 1.8}, "same_size_as": "E2",
                            "templates": ["vm_wan22_5b_i2v_api.json"]}, checks)
            got = {c["id"]: c["ok"] for c in checks}
            self.assertEqual(got["duration_vs_E2"], ok, dur)
            self.assertTrue(got["same_size_as_E2"] and got["workflow_templates"])

    def test_wrong_template_fps_and_still_video_fail(self):
        rec = self.rec("E2", duration_s=2.7)
        rec["workflows"] = [{"template": {"name": "video_wan22_i2v_fast_api.json"}}]
        rec["output"]["video"]["fps"] = 16.0
        rec["output"]["motion"] = {"mean_frame_diff": 0.01, "first_frame_std": 40}
        checks = []
        ev.step_checks(rec, {}, {"templates": ["vm_wan22_5b_i2v_api.json"], "fps": 24, "min_mean_frame_diff": 0.3}, checks)
        got = {c["id"]: (c["ok"], c["level"]) for c in checks}
        self.assertEqual(got["workflow_templates"], (False, "required"))
        self.assertEqual(got["fps"], (False, "media"))
        self.assertEqual(got["moves"], (False, "media"))

    def test_keyframe_scores_follow_the_tier(self):
        variants = {"use": "a", "variants": [{"image": "a"}, {"image": "b"}]}
        self.assertEqual(ev.qc_declaration({}, "T2"), (None, None))
        sent, label = ev.qc_declaration({"qc": {"source": "mock", **variants}}, "T1")
        self.assertEqual((sent, label), (variants, {"source": "mock"}))
        sent, label = ev.qc_declaration({"qc": {"source": "ak_scores", "scored_by": "Ak", **variants}}, "T2")
        self.assertEqual((sent, label["scored_by"]), (variants, "Ak"))
        for qc, tier in (({"source": "mock", **variants}, "T2"), (variants, "T2"),
                         ({"source": "ak_scores", **variants}, "T2"), ({"source": "ak_scores", "scored_by": "Ak", **variants}, "T1"),
                         (variants, "T1"), (["not", "a", "dict"], "T1")):
            with self.subTest(qc=qc, tier=tier), self.assertRaises(ev.Stop):
                ev.qc_declaration({"qc": qc}, tier)

    def test_tier_follows_the_backend(self):
        self.assertEqual(ev.decide_tier(False, {"comfy_version": "0.43.0 (mock)"})[0], "T1")
        self.assertEqual(ev.decide_tier(True, {})[0], "T1")
        self.assertEqual(ev.decide_tier(False, {"comfy_version": "0.43.0", "machine": {"device": "mps"}})[0], "T2")
        self.assertEqual(ev.decide_tier(False, {"comfy_version": "0.43.0", "machine": {"device": "cuda"}})[0], "T3")


class MockChain(unittest.TestCase):
    """The default chain on the real app with the mock ComfyUI (Tier 1): E1 first, then a resume that adds
    the keyframe scores, as on the night (Ak scores the two stills; this test uses mock scores)."""

    def test_e1_then_resume_with_scores(self):
        root = tempfile.mkdtemp(prefix="evidence_t1_")
        chain = json.load(open(ev.DEFAULT_CHAIN))
        for step in chain["steps"]:  # candy-main extends on the 14B graph until the chain branch lands
            if step["id"] == "E3":
                step["expect"].pop("templates")
        chain_path = os.path.join(root, "chain.json")
        json.dump(chain, open(chain_path, "w"))
        scores = os.path.join(root, "qc.json")
        json.dump({"source": "mock", "note": "plumbing test only", "use": "{E1.results.0}", "variants": [
            {"image": "{E1.results.0}", "scores": {"hands": 8, "anatomy": 8, "contact": 8, "skin": 7, "lighting": 7}},
            {"image": "{E1.results.1}", "scores": {"hands": 5, "anatomy": 4, "contact": 4, "skin": 6, "lighting": 6}}]},
            open(scores, "w"))
        common = ["--mock", "--chain", chain_path, "--evidence-root", root, "--poll", "0.2", "--quiet"]
        os.environ["MOCK_DELAY"] = "0.01"
        self.assertEqual(ev.main(common + ["--run-id", "night", "--only", "E1", "--no-ui"]), 0)
        first = json.load(open(os.path.join(root, "night", "manifest.json")))
        self.assertEqual((first["tier"], first["status"]), ("T1", "partial"))
        self.assertEqual([s["status"] for s in first["steps"]], ["done", "skipped", "skipped", "skipped"])
        e1 = first["steps"][0]
        self.assertEqual(len(e1["result_ids"]), 2)
        self.assertEqual(e1["workflow_template"], "image_zimage_turbo_api.json")
        self.assertEqual(e1["seed"], 20261106)
        self.assertIn("stated age 30", first["rules"])
        self.assertNotIn("no people", first["rules"])
        state = os.path.join(root, ".mock_state", "night")
        self.assertTrue(os.path.isdir(state) and not first["app"]["mock_state"]["removed"])

        code = ev.main(common + ["--resume", "night", "--var", "qc=@" + scores])
        m = json.load(open(os.path.join(root, "night", "manifest.json")))
        self.assertEqual(code, 0, m.get("summary"))
        self.assertEqual(m["status"], "complete")
        steps = {s["id"]: s for s in m["steps"]}
        self.assertTrue(steps["E1"].get("kept_from_earlier_run"))
        self.assertEqual(steps["E1"]["job"]["id"], e1["job"]["id"])
        self.assertEqual(steps["E2"]["params_sent"]["image"], e1["result_ids"][0])
        self.assertEqual(steps["E2"]["params_sent"]["qc"]["variants"][1]["image"], e1["result_ids"][1])
        self.assertTrue(steps["E2"]["qc_route"]["scores_given"])
        self.assertEqual({k: s["qc_source"] for k, s in steps.items()},
                         {"E1": "not_applicable", "E2": "mock", "E3": "not_applicable", "E4": "not_applicable"})
        self.assertNotIn("source", steps["E2"]["params_sent"]["qc"])  # the label stays in the manifest only
        self.assertEqual(m["chain"]["qc_label"], {"source": "mock", "note": "plumbing test only"})
        self.assertTrue(m["app"]["mock_state"]["removed"])
        self.assertFalse(os.path.exists(state))
        self.assertEqual(steps["E2"]["workflow_template"], "vm_wan22_5b_i2v_api.json")
        self.assertEqual(steps["E2"]["params_sent"]["advanced"], {"seed": 20261106})
        self.assertIn(20261106, steps["E2"]["workflows"][0]["seeds"])  # the clip's sampler took the chain seed
        self.assertEqual(steps["E4"]["workflow_template"], "3d_hunyuan21_shape_api.json")
        v2, v3 = steps["E2"]["output"]["video"], steps["E3"]["output"]["video"]
        self.assertGreaterEqual(v3["duration_s"], 1.8 * v2["duration_s"])
        self.assertEqual(steps["E3"]["output"]["motion"]["join"]["frame"], v2["frames"])
        self.assertGreater(steps["E4"]["output"]["mesh"]["faces"], 0)
        for s in steps.values():  # every output: the downloaded copy equals the app's own file
            self.assertEqual(s["output"]["app_sha256"], s["output"]["sha256"])
            self.assertTrue(s["logs"]["app"]["available"])
        run_dir = os.path.join(root, "night")
        for row in m["files"]:
            self.assertEqual(ev.sha256_file(os.path.join(run_dir, row["path"])), row["sha256"], row["path"])
        self.assertTrue(any(c["id"] == "models_hashed" and not c["ok"] and c["counts"] for c in m["checks"]))
        ui = m["ui_walk"]
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.assertFalse(ui["ran"])
            return
        self.assertTrue(ui["ran"], ui)
        self.assertFalse(ui["viewed_by_session"])
        self.assertEqual(len(ui["screenshots"]), 5)
        self.assertTrue(ui["model_viewer"]["loaded"], ui["model_viewer"])
        self.assertEqual(ui["page_errors"], [])
        shutil.rmtree(root, ignore_errors=True)


class RequestIds(unittest.TestCase):
    """The app returns the job it already has for a repeated request_id + kind (server.py, by design), so a
    re-run on --resume must post a new id (orchestrator 20:21 ET)."""

    def test_a_rerun_is_a_new_job_even_when_the_manifest_lost_its_attempts(self):
        root = tempfile.mkdtemp(prefix="evidence_rid_")
        chain = json.load(open(ev.DEFAULT_CHAIN))
        chain["steps"] = [s for s in chain["steps"] if s["id"] == "E1"]
        path = os.path.join(root, "chain.json")
        json.dump(chain, open(path, "w"))
        os.environ["MOCK_DELAY"] = "0.01"
        # one app for all three calls: its request ids live in memory, as with the runtime's app on the night
        stack = ev.MockStack(ev.REPO, os.path.join(root, "app_state"))
        self.addCleanup(stack.close)
        common = ["--base", stack.base, "--outputs", stack.out, "--app-log", stack.app_log,
                  "--comfy-log", stack.comfy_log, "--chain", path, "--evidence-root", root, "--poll", "0.2",
                  "--quiet", "--no-ui", "--only", "E1"]
        mpath = os.path.join(root, "rid", "manifest.json")

        self.assertEqual(ev.main(common + ["--run-id", "rid"]), 0)
        first = json.load(open(mpath))["steps"][0]
        self.assertEqual((first["request_id"], first["attempt"]), ("evidence-rid-E1", 1))

        self.assertEqual(ev.main(common + ["--resume", "rid", "--seed", "7"]), 0)
        second = json.load(open(mpath))["steps"][0]
        self.assertEqual((second["request_id"], second["attempt"]), ("evidence-rid-E1-a2", 2))
        self.assertNotEqual(second["job"]["id"], first["job"]["id"])
        self.assertEqual([a["job"]["id"] for a in second["attempts"]], [first["job"]["id"]])
        self.assertEqual(second["seed"], 7)
        self.assertNotIn("request_ids_already_used", second)

        m = json.load(open(mpath))  # an older manifest that lost its attempts: -a2 is taken, so -a3
        m["steps"][0].pop("attempts")
        json.dump(m, open(mpath, "w"))
        self.assertEqual(ev.main(common + ["--resume", "rid"]), 0)
        third = json.load(open(mpath))["steps"][0]
        self.assertEqual((third["request_id"], third["attempt"]), ("evidence-rid-E1-a3", 3))
        self.assertEqual(third["request_ids_already_used"],
                         [{"request_id": "evidence-rid-E1-a2", "job": second["job"]["id"], "status": "done"}])
        self.assertNotIn(third["job"]["id"], (first["job"]["id"], second["job"]["id"]))
        shutil.rmtree(root, ignore_errors=True)


class AgeHeld(unittest.TestCase):
    """Held media never reach the bundle (reviewer S2, 20:14 ET). The mock age checker flags a picture whose
    graph carries the test word "magentatest" (the app deletes it and says so)."""

    def test_held_results_stay_out_of_the_bundle_and_are_kept_as_attempts(self):
        root = tempfile.mkdtemp(prefix="evidence_held_")
        chain = json.load(open(ev.DEFAULT_CHAIN))
        chain["steps"] = [s for s in chain["steps"] if s["id"] in ("E1", "E4")]
        clean = os.path.join(root, "clean.json")
        json.dump(chain, open(clean, "w"))
        chain["steps"][0]["params"]["extra_scene"] = "magentatest"
        flagged = os.path.join(root, "flagged.json")
        json.dump(chain, open(flagged, "w"))
        common = ["--mock", "--evidence-root", root, "--poll", "0.2", "--quiet"]
        os.environ["MOCK_DELAY"] = "0.01"
        run_dir = os.path.join(root, "agerun")

        # 1. the E1 job's picture is flagged and deleted by the app: E1 is held, no file is written, E4 waits
        self.assertEqual(ev.main(common + ["--chain", flagged, "--run-id", "agerun", "--no-ui"]), 1)
        m = json.load(open(os.path.join(run_dir, "manifest.json")))
        e1 = m["steps"][0]
        self.assertEqual((e1["status"], e1["output"]), ("held", None))
        self.assertEqual([(a["age_flag"], a["deleted"]) for a in e1["results_age"]], [(True, True)])
        self.assertEqual(m["steps"][1]["status"], "skipped")
        self.assertFalse([f for f in os.listdir(run_dir) if f.startswith("E1_")])
        self.assertIn("E1.age_check_publishable", m["summary"]["failing"])

        # 2. a clean resume renders E1 again; the held try stays in attempts[] with no file
        self.assertEqual(ev.main(common + ["--chain", clean, "--resume", "agerun", "--no-ui", "--only", "E1",
                                           "--note", "E1 first try age-flagged by the app; re-rendered"]), 0)
        m = json.load(open(os.path.join(run_dir, "manifest.json")))
        e1 = m["steps"][0]
        self.assertEqual(e1["status"], "done")
        self.assertEqual([a["status"] for a in e1["attempts"]], ["held"])
        self.assertTrue(e1["output"]["publishable"] and e1["output"]["age"]["age_check"] == "ok")
        self.assertEqual(m["notes"][0]["text"], "E1 first try age-flagged by the app; re-rendered")

        # 3. a done step whose app item is flagged afterwards (an older tool kept it) is moved out and redone
        items = os.path.join(root, ".mock_state", "agerun", "outputs", "items")
        path = os.path.join(items, e1["output"]["item_id"] + ".json")
        item = json.load(open(path))
        item.update(age_flag=True, age_check="flag", p_under21=0.9)
        json.dump(item, open(path, "w"))
        old_sha = e1["output"]["sha256"]
        self.assertEqual(ev.main(common + ["--chain", clean, "--resume", "agerun"]), 0)
        m = json.load(open(os.path.join(run_dir, "manifest.json")))
        e1, e4 = m["steps"]
        self.assertEqual([a["status"] for a in e1["attempts"]], ["held", "held"])
        moved = e1["attempts"][1]["held_file_moved_to"]
        self.assertTrue(moved.startswith(os.path.join(root, ".held", "agerun")) and os.path.isfile(moved))
        self.assertEqual(ev.sha256_file(moved), old_sha)
        self.assertNotEqual(e1["output"]["item_id"], item["id"])
        self.assertEqual(e4["status"], "done")
        self.assertEqual(e4["output"]["age"]["basis"], "source picture " + e1["output"]["item_id"])
        self.assertTrue(e4["output"]["publishable"])
        # the bundle holds one E1 file, the new render's (the mock renders the same bytes for the same seed)
        self.assertEqual([r["path"] for r in m["files"] if r["path"].startswith("E1_")], [e1["output"]["file"]])
        self.assertTrue(e1["output"]["publishable"])
        self.assertEqual(m["notes"][0]["text"], "E1 first try age-flagged by the app; re-rendered")
        ui = m["ui_walk"]
        if ui.get("ran"):
            # a flagged result is deleted and a flagged older item is not listed (D-C-51): the gallery shows nothing held
            self.assertNotIn("gallery_skipped", ui)
            self.assertIn("gallery", [s["tab"] for s in ui["screenshots"]])
            self.assertEqual(ui["app_items_age_held"], 0)
            # a second walk moves the first walk's screenshots out of the bundle
            self.assertEqual(ev.main(common + ["--chain", clean, "--resume", "agerun"]), 0)
            m = json.load(open(os.path.join(run_dir, "manifest.json")))
            self.assertTrue(any("earlier UI screenshots moved" in n["text"] for n in m["notes"]))
            self.assertEqual(sorted(os.listdir(os.path.join(run_dir, "ui"))),
                             sorted(os.path.basename(s["path"]) for s in m["ui_walk"]["screenshots"])
                             + ([os.path.basename(m["ui_walk"]["model_viewer"]["screenshot"]["path"])]
                                if (m["ui_walk"].get("model_viewer") or {}).get("screenshot") else []))
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
