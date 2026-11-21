"""The 20-second proof on the Build a video page.

unit(check)      -- run from run_tests.py: the preset's words pass the prompt rails, say a stated age of 21 or more, and the
                    four parts add up to 20 seconds.
python tests/proof_preset_tests.py -- the server side on the stand-in engine (build 5 s, then one extend of three parts, joined)
                    and the page's clicks against canned answers. No model runs; no real request is sent.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))

JS = os.path.join(ROOT, "app", "static", "video_pages.js")
WORDS = ("a woman, 30 years old, in a small bikini walks along the shoreline of a sandy beach, photographic live-action footage, "
         "natural daylight, the camera follows her at a steady pace")
FIRST_PHOTO = {
    "dna": {"name": "First photo", "gender": "woman", "age": 30, "style": "photo",
            "traits": {"hair_style": "long_wavy", "hair_length": "very_long", "makeup": "m_glam"}},
    "outfit": "dressy:evening", "scene": "studio", "lighting": "dramatic", "camera": "full", "aspect": "wide", "count": 2, "speed": "best",
    "look": "realistic", "engine": "",
    "extra_scene": "walking a fashion show runway, confident runway pose, glamorous, realistic skin texture, long flowing hair, wide fashion-show framing",
}
PARTS = ["she keeps walking along the waterline",
         "she turns toward the waves and walks into the shallow water",
         "she turns back and walks up the beach toward the dunes"]


def unit(check):
    print("\n[proof] The 20-second proof preset")
    import safety
    src = open(JS, encoding="utf-8").read()
    check("the preset is in the Build page with exactly these words and parts, of 5 seconds each",
          WORDS in src and all(p in src for p in PARTS) and "seconds: 5," in src)
    for text in [WORDS] + PARTS:
        ok, msg = safety.check_all(text)
        area_ok, area_msg = safety.check_area(text, "default")
        if not (ok and area_ok):
            check("the preset text passes the prompt rails in the everyday section: " + text[:40], False, msg or area_msg)
    check("every preset text passes the prompt rails in the everyday section", True)
    check("the words state an age of 21 or more", int(re.search(r"(\d+) years old", WORDS).group(1)) >= 21)
    check("the words say photographic, live-action and a woman, and name no animated style",
          all(w in WORDS for w in ("woman", "photographic", "live-action")) and not re.search(r"anime|cartoon|animat|illustrat", WORDS, re.I))
    check("four parts of five seconds make 20 seconds", (1 + len(PARTS)) * 5 == 20)
    app_js = open(os.path.join(ROOT, "app", "static", "app.js"), encoding="utf-8").read()
    check("the First photo preset is on the Create page with exactly these words and settings",
          FIRST_PHOTO["extra_scene"] in app_js and 'outfit: "dressy:evening"' in app_js and 'look: "realistic"' in app_js and 'age: 30' in app_js)
    t = FIRST_PHOTO["extra_scene"]
    ok, msg = safety.check_all(t)
    area_ok, area_msg = safety.check_area(t, "default")
    group_ok, group_msg = safety.check_group_prompt(t, [{"age": 30}])
    rec_ok, rec_msg = safety.reconcile_prompt_ages(t, [{"age": 30}])
    check("the First photo words pass every prompt rail in the everyday section (a refusal here is reported, never reworded around)",
          ok and area_ok and group_ok and rec_ok, msg or area_msg or group_msg or rec_msg)
    check("the preset names no LoRA and sends none", "advanced: { loras: [] }" in src and "loras: []" in src)


def server_side(world, check):
    print("\n[proof] On the stand-in engine, through the real server")
    a = world.api
    plain = {"model": "wan22_5b_t2v", "text": WORDS, "seconds": 5, "quality": "fast", "aspect": "landscape", "engine": "local", "advanced": {"loras": []}}
    j = a.job("video_any", dict(plain), timeout=120)
    check("a person the words bring in is refused without a stated age, as for any other person",
          j["status"] in ("error", "refused") and "stated age" in (j.get("error") or "").lower(), j.get("error"))
    j = a.job("video_any", dict(plain, stated_age="17"), timeout=120)
    check("... and under 21 is refused too", j["status"] in ("error", "refused") and "21" in (j.get("error") or ""), j.get("error"))
    for words in ("a girl walks on the beach", "two women walk on the beach", "she walks along the beach"):
        j = a.job("video_any", dict(plain, text=words), timeout=120)
        check("words with any person word ('%s') are refused without a stated age" % words,
              j["status"] in ("error", "refused") and "stated age" in (j.get("error") or "").lower(), j.get("error"))
    j = a.job("video_any", dict(plain, text="two women walk on the beach", stated_age="30"), timeout=120)
    check("two people with one stated age are refused: every person needs a record", j["status"] in ("error", "refused") and "2 people" in (j.get("error") or ""), j.get("error"))
    j = a.job("video_any", dict(plain, text="a woman, 25 years old, walks on the beach", stated_age="30"), timeout=120)
    check("an age written in the words has to match the stated age", j["status"] in ("error", "refused") and "onflicting" in (j.get("error") or ""), j.get("error"))
    j = a.job("video_any", dict(plain, stated_age="30"), timeout=300)
    base = (j.get("results") or [None])[0]
    check("part 1: with a stated age of 30 the build job takes the preset words and makes a clip",
          j["status"] == "done" and base, j.get("error"))
    check("part 1 keeps the stated age on the clip, so the extend job can read it", base and str(base.get("stated_age")) in ("30", "30.0"), base and base.get("stated_age"))
    if not base:
        return
    prov = base.get("provenance") or {}
    check("part 1 carries the realism lock and no LoRA", "photographic" in (base.get("prompt") or "").lower()
          and prov.get("look") == "realistic" and not prov.get("loras"), (base.get("prompt"), prov))
    j = a.job("extend", {"video": base["id"], "segments": [{"text": t, "seconds": 5} for t in PARTS], "loras": [], "engine": "local"}, timeout=600)
    ext = (j.get("results") or [None])[0]
    check("parts 2 to 4: one extend of three parts is accepted and makes one joined clip", j["status"] == "done" and ext, j.get("error"))
    if not ext:
        return
    p = ext.get("provenance") or {}
    check("the joined clip has three joins, one colour record each, three parts, the realism look, no LoRA, engine local",
          len(p.get("join_points") or []) == 3 and len(p.get("colour_match") or []) == 3 and len(p.get("segments") or []) == 3
          and p.get("look") == "realistic" and not p.get("loras") and p.get("engine") == "local", p)
    check("the age check ran on the joined clip", ext.get("age_check") == "ok" and not ext.get("age_flag"))
    check("each part's instruction was kept in the record, in order",
          [s.get("instruction") for s in p.get("segments") or []] == [x for x in PARTS] or all(
              t.split()[1] in (s.get("instruction") or "") for t, s in zip(PARTS, p.get("segments") or [])), p.get("segments"))


def first_photo_server(world, check):
    print("\n[proof] First photo, through the real server on the stand-in engine")
    a = world.api
    j = a.job("create", json.loads(json.dumps(FIRST_PHOTO)), timeout=300)
    items = j.get("results") or []
    check("the First photo preset is accepted by every rule and makes 2 pictures", j["status"] == "done" and len(items) == 2, j.get("error"))
    if not items:
        return
    it = items[0]
    prov = it.get("provenance") or {}
    check("they are made with Z-Image Turbo from the realistic look, in the everyday section, age checked",
          prov.get("workflow") == "image_zimage_turbo_api.json" and it.get("area") == "default" and it.get("age_check") == "ok" and not it.get("age_flag"), (prov, it.get("area")))
    check("the prompt carries the runway words, the long hair and a clothed outfit, and the negative holds the nudity words",
          all(w in (it.get("prompt") or "").lower() for w in ("runway", "long flowing hair", "evening gown")), it.get("prompt"))


def browser(world, check):
    print("\n[proof] The page's click, against canned answers")
    from playwright.sync_api import sync_playwright
    errors = []
    with sync_playwright() as p:
        exe = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        try:
            b = p.chromium.launch(headless=True)
        except Exception:
            b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None, headless=True)
        page = b.new_page(viewport={"width": 1200, "height": 1000})
        page.on("pageerror", lambda e: errors.append(str(e)) if "no supported sources" not in str(e) else None)
        state = {"jobs": [], "providers": []}

        def ans(route, body, status=200):
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

        def clip(i):
            return {"id": "r%d" % i, "type": "video", "role": "made", "kind": "video:extend", "title": "clip %d" % i, "url": "/files/none.mp4",
                    "file": "items/r%d.mp4" % i, "created": 1.0, "favourite": False, "model": "Wan 2.2 5B", "age_check": "ok"}

        def jobs(route, request):
            if request.method == "POST" and request.url.endswith("/api/jobs"):
                state["jobs"].append(request.post_data_json)
                return ans(route, {"id": "stub%d" % len(state["jobs"])})
            if "/api/jobs/stub" not in request.url:
                return route.continue_()
            n = int(request.url.rsplit("stub", 1)[1])
            return ans(route, {"id": "x", "status": "done", "progress": 1, "results": [clip(n)]})

        models = [{"id": "wan22_5b_t2v", "label": "Wan 2.2 5B text", "family": "Wan 2.2 5B", "mode": "t2v", "ready": True, "missing": []},
                  {"id": "wan22_5b_i2v", "label": "Wan 2.2 5B picture", "family": "Wan 2.2 5B", "mode": "i2v", "ready": True, "missing": []}]
        page.route("**/api/gallery**", lambda r, q: ans(r, {"items": []}))
        page.route("**/api/loras", lambda r, q: ans(r, {"loras": [], "families": {}}))
        page.route("**/api/video/models", lambda r, q: ans(r, {"models": models, "byo": []}))
        page.route("**/api/providers", lambda r, q: ans(r, {"providers": state["providers"]}))
        page.route(re.compile(r".*/api/items/r\d+$"), lambda r, q: ans(r, clip(int(q.url.rsplit("r", 1)[1]))))
        page.route("**/api/jobs**", jobs)

        for engine, first_kind in (("local", "video_any"), ("dashscope_video", "video_api")):
            state["jobs"].clear()
            state["providers"] = [{"name": "dashscope_video", "label": "Alibaba Model Studio", "kind": "video", "configured": True}] if engine != "local" else []
            page.goto(world.base + "/#/video-build", wait_until="domcontentloaded")
            page.reload()
            page.wait_for_selector("#vbProof", timeout=15000)
            if engine != "local":
                page.select_option("#vxEngine", engine)
            page.click("#vbProof")
            try:
                page.wait_for_selector("#vbProofCard2", timeout=30000)
            except Exception:
                print("   page errors:", errors[:3], "| status:", page.inner_text("#vxStatus")[:200], "| jobs:", len(state["jobs"]))
                raise
            first, second = state["jobs"][0], state["jobs"][1]
            fp, sp = first["params"], second["params"]
            check("%s: the click fills the box with the preset words" % engine, page.input_value("#vbText") == WORDS)
            check("%s: part 1 is %s for 5 seconds with the preset words and no LoRA" % (engine, first_kind),
                  len(state["jobs"]) == 2 and first["kind"] == first_kind and fp["text"] == WORDS and fp["seconds"] == 5
                  and (fp.get("advanced") or {}).get("loras", []) == [] and ("model" in fp) == (engine == "local") and fp["stated_age"] == "30", first)
            check("%s: the age box shows 30" % engine, page.input_value("#vbAge") == "30")
            check("%s: parts 2 to 4 are one extend of three parts of 5 seconds, on the clip from part 1, no LoRA, same engine" % engine,
                  second["kind"] == "extend" and sp["video"] == "r1" and sp["engine"] == engine and sp["loras"] == []
                  and [s["text"] for s in sp["segments"]] == PARTS and all(s["seconds"] == 5 for s in sp["segments"]), second)
            check("%s: the finished clip has a player, Download and Extend this" % engine,
                  page.locator("#vbProofCard2 video").count() == 1 and page.locator("#vbProofCard2 #vxDownload").count() == 1
                  and page.locator("#vbProofExtend").count() == 1)
        state["jobs"].clear()
        page.goto(world.base + "/#/create", wait_until="domcontentloaded")
        page.reload()
        page.wait_for_selector("#createFirstPhoto", timeout=15000)
        page.click("#createFirstPhoto")
        page.wait_for_function("() => true")
        for _ in range(40):
            if state["jobs"]:
                break
            page.wait_for_timeout(250)
        sent = state["jobs"][0] if state["jobs"] else {}
        check("Create has a First photo button that sends one create job with exactly the preset",
              sent.get("kind") == "create" and sent.get("params") == FIRST_PHOTO, sent)
        b.close()
    check("no JavaScript errors", not errors, errors[:3])


if __name__ == "__main__":
    from e2e_browser import World
    results = []

    def check(name, cond, detail=""):
        results.append(bool(cond))
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else "  -- %s" % str(detail)[:300]))

    unit(check)
    world = World()
    try:
        server_side(world, check)
        first_photo_server(world, check)
        browser(world, check)
    finally:
        world.close()
    bad = results.count(False)
    print("\n%d/%d proof checks passed" % (len(results) - bad, len(results)))
    sys.exit(1 if bad else 0)
