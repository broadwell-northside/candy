"""The two video pages (#/video-build, #/video-extend): static checks run from run_tests.py (unit), and a browser run
against stand-in answers (python tests/video_pages_tests.py). No model runs, no real API request: the server's gallery,
LoRA, model, provider and job answers are replaced inside the page by canned ones."""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))

JS = os.path.join(ROOT, "app", "static", "video_pages.js")
BAD_WORDS = re.compile(r"\b(girl|girls|anime|animated|animation|cartoon)\b", re.I)


def unit(check):
    print("\n[video pages] static checks")
    src = open(JS, encoding="utf-8").read()
    check("video pages file is included once in index.html",
          open(os.path.join(ROOT, "app", "static", "index.html"), encoding="utf-8").read().count("/static/video_pages.js") == 1)
    check("both pages are registered and reachable by address", 'VIEWS["video-build"]' in src and 'VIEWS["video-extend"]' in src and "DOORS.push" in src)
    check("the extend job is sent as the contract says", 'runJob("extend"' in src and "segments: [{ text: sent, seconds: st.seconds }]" in src)
    shown = re.sub(r"STYLE_WORDS\s*=.*", "", src)           # the one filter line names the words it hides
    check("no girl/anime/animated wording on the pages", not BAD_WORDS.search(shown), BAD_WORDS.findall(shown))


# ------------------------------------------------------------------ browser run on stand-in answers
VIDEO = "data:video/mp4;base64,AAAA"


def vid(i, **kw):
    d = {"id": i, "type": "video", "role": "made", "kind": "video:i2v", "url": VIDEO, "file": "items/%s.mp4" % i, "created": 1.0, "favourite": False, "title": "clip " + i, "model": "Wan 2.2 14B i2v -- stand-in"}
    d.update(kw)
    return d


GALLERY = [vid("v1"), vid("v2"), vid("up1", role="reference", kind="upload"), vid("flag1", age_flag=True)]
LORAS = [
    {"name": "wan_walk.safetensors", "title": "Walking", "family": "wan14b", "family_label": "Wan 2.1 / 2.2 14B (video)", "trigger_words": ["wlk"], "blocked": False, "strength": 0.8, "strength_known": True},
    {"name": "toon_pop.safetensors", "title": "Pop", "family": "sdxl", "family_label": "SDXL / NoobAI / Illustrious / Pony (anime pictures)", "trigger_words": [], "blocked": False},
    {"name": "bad.safetensors", "title": "Blocked one", "family": "wan14b", "family_label": "x", "trigger_words": [], "blocked": True},
    {"name": "ltx_look.safetensors", "title": "Other family", "family": "ltx2", "family_label": "x", "trigger_words": [], "blocked": False},
]
MODELS = [{"id": "wan_t2v", "label": "Wan t2v", "family": "Wan 2.2 14B", "mode": "t2v", "ready": True, "fps": 16, "max_s": 10},
          {"id": "wan_i2v", "label": "Wan i2v", "family": "Wan 2.2 14B", "mode": "i2v", "ready": True, "fps": 16, "max_s": 10}]


def browser():
    from playwright.sync_api import sync_playwright
    from e2e_browser import World
    results, errors = [], []

    def finding(name, ok, detail=""):
        results.append(bool(ok))
        print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  -- {detail}"))

    world = World()
    try:
        with sync_playwright() as p:
            exe = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            try:
                b = p.chromium.launch(headless=True)
            except Exception:
                b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None, headless=True)
            page = b.new_page(viewport={"width": 1200, "height": 1000})
            page.on("pageerror", lambda e: errors.append(str(e)) if "no supported sources" not in str(e) else None)  # the stand-in clip is not real video
            state = {"jobs": [], "next_error": None, "post_refusal": None, "providers": []}

            def ans(route, body, status=200):
                route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

            def jobs(route, request):
                if request.method == "POST" and request.url.endswith("/api/jobs"):
                    if state["post_refusal"]:
                        return ans(route, {"error": state["post_refusal"]}, 400)
                    state["jobs"].append(request.post_data_json)
                    return ans(route, {"id": "stub%d" % len(state["jobs"])})
                if "/api/jobs/stub" not in request.url:
                    return route.continue_()
                n = int(request.url.rsplit("stub", 1)[1])
                if state["next_error"]:
                    return ans(route, {"id": "x", "status": "error", "error": state["next_error"], "results": [], "progress": 1})
                return ans(route, {"id": "x", "status": "done", "progress": 1, "results": [vid("r%d" % n)]})

            page.route("**/api/gallery**", lambda r, q: ans(r, {"items": GALLERY}))
            page.route("**/api/loras", lambda r, q: ans(r, {"loras": LORAS, "families": {}}))
            page.route("**/api/video/models", lambda r, q: ans(r, {"models": MODELS, "byo": []}))
            page.route("**/api/providers", lambda r, q: ans(r, {"providers": state["providers"]}))
            page.route(re.compile(r".*/api/items/r\d+$"), lambda r, q: ans(r, vid(q.url.rsplit("/", 1)[1])))
            page.route("**/api/jobs**", jobs)

            def text_of_page():
                return page.inner_text("body") + " " + " ".join(page.eval_on_selector_all("[placeholder]", "els => els.map(e => e.placeholder)"))

            # ---- Extend, cold load of the address
            page.goto(world.base + "/#/video-extend", wait_until="domcontentloaded")
            page.wait_for_selector("#vxExtend", timeout=15000)
            body = text_of_page()
            finding("the address opens the Extend page directly", "Extend a video" in page.inner_text("#main"))
            finding("the page says plainly what it can continue", "can continue videos it made" in body and "from outside is refused" in body)
            finding("the Realistic only note is visible", page.locator("#vxRealistic").is_visible() and "Realistic only" in page.inner_text("#vxRealistic"))
            finding("no girl/anime/animated wording on the page", not BAD_WORDS.search(body), BAD_WORDS.findall(body))
            finding("the big box asks 'What happens next?' with an example",
                    "What happens next?" in body and "walks into the forest and sees trees" in page.get_attribute("#vxText", "placeholder"))
            page.click("#vxExtend")
            finding("Extend with nothing picked says so in words", "Pick a video" in page.inner_text("#vxStatus"))
            page.click("#vxPickVideo")
            page.wait_for_selector("#vxVideoGrid .res", timeout=10000)
            ids = page.eval_on_selector_all("#vxVideoGrid .res", "els => els.map(e => e.dataset.id)")
            finding("only videos made here are offered (no upload, no held-back clip)", ids == ["v1", "v2"], ids)
            page.click("#vxVideoGrid .res[data-id='v1']")
            page.wait_for_selector("#vxTimeline .vx-step", timeout=5000)
            page.wait_for_timeout(300)
            opts = page.eval_on_selector_all("#vxLora option", "els => els.map(e => e.textContent)")
            finding("LoRA picker lists only unblocked ones of the video's family, with the trigger word",
                    len(opts) == 2 and "Walking" in opts[1] and "trigger: wlk" in opts[1] and not any("Pop" in o or "Other" in o or "Blocked" in o for o in opts), opts)
            finding("seconds default to 5", page.locator(".seg button.on").inner_text() == "5 s")
            page.select_option("#vxLora", "wan_walk.safetensors")
            finding("picking a LoRA says the trigger word is added", "wlk" in page.inner_text("#vxLoraNote"))
            page.click(".vx-example >> nth=0")
            page.click("#vxExtend")
            page.wait_for_function("() => document.querySelectorAll('#vxTimeline .vx-step').length === 2", timeout=15000)
            sent = state["jobs"][0]
            want = {"video": "v1", "segments": [{"text": "wlk, she turns around and walks into the forest and sees trees", "seconds": 5}],
                    "loras": [{"name": "wan_walk.safetensors", "strength": 0.8}], "engine": "local"}
            finding("Extend sends the contract's job", sent["kind"] == "extend" and sent["params"] == want, sent)
            finding("the new clip is in the timeline with its instruction and a download of the joined video",
                    "she turns around" in page.inner_text("#vxTimeline") and page.locator("#vxDownload").is_visible() and page.get_attribute("#vxDownload", "href") == VIDEO)
            page.click("#vxAgain")
            finding("Extend again clears the box and keeps the chain", page.input_value("#vxText") == "" and page.locator("#vxTimeline .vx-step").count() == 2)
            page.fill("#vxText", "the camera follows her along the water")
            page.click("#vxExtend")
            page.wait_for_function("() => document.querySelectorAll('#vxTimeline .vx-step').length === 3", timeout=15000)
            finding("the second extension continues from the newest clip", state["jobs"][1]["params"]["video"] == "r1", state["jobs"][1])
            state["next_error"] = "That is a video of a real person from outside, so it is refused."
            page.fill("#vxText", "she waves")
            page.click("#vxExtend")
            page.wait_for_selector("#vxStatus .err", timeout=15000)
            finding("a refusal from the server shows in its own words",
                    "from outside, so it is refused" in page.inner_text("#vxStatus") and page.locator("#vxTimeline .vx-step").count() == 3)
            state["next_error"] = None
            state["post_refusal"] = "Easy Studio can only continue videos it made."
            page.click("#vxExtend")
            page.wait_for_function("() => document.querySelector('#vxStatus').innerText.includes('only continue videos it made')", timeout=10000)
            finding("a refusal at the door shows in its own words too", True)
            state["post_refusal"] = None
            state["providers"] = [{"name": "dashscope", "kind": "video", "configured": True}, {"name": "other", "kind": "text", "configured": True}]
            page.reload()
            page.wait_for_selector("#vxExtend", timeout=15000)
            eng = page.eval_on_selector_all("#vxEngine option", "els => els.map(e => e.value)")
            finding("Engine offers This Mac and a configured video provider only", eng == ["local", "dashscope"], eng)
            page.select_option("#vxEngine", "dashscope")
            page.fill("#vxText", "she walks on")
            page.click("#vxExtend")
            page.wait_for_function("() => document.querySelectorAll('#vxTimeline .vx-step').length === 4", timeout=15000)
            finding("the chosen provider is sent as the engine", state["jobs"][-1]["params"]["engine"] == "dashscope")
            page.screenshot(path=os.path.join(tempfile.gettempdir(), "video_extend.png"), full_page=True)

            # ---- Build, cold load, then Extend this
            state["providers"] = []
            n0 = len(state["jobs"])
            page.goto(world.base + "/#/video-build", wait_until="domcontentloaded")
            page.reload()
            page.wait_for_selector("#vbBuild", timeout=15000)
            body = text_of_page()
            finding("Build page: plain box, Realistic only note, no girl/anime/animated wording",
                    page.locator("#vxRealistic").is_visible() and "woman" in body and not BAD_WORDS.search(body), BAD_WORDS.findall(body))
            page.click("#vbBuild")
            finding("Build with an empty box says so", "Write what you want to see" in page.inner_text("#vxStatus"))
            page.fill("#vbText", "a woman walks down a quiet beach at sunrise")
            page.select_option("#vxLora", "wan_walk.safetensors")
            page.click("#vbBuild")
            page.wait_for_selector("#vbExtend", timeout=15000)
            sent = state["jobs"][n0]
            sp = sent["params"]
            finding("Build sends a video job with the words, seconds, LoRA and engine, and no start picture",
                    sent["kind"] == "video_any" and sp["model"] == "wan_t2v" and sp["text"] == "wlk, a woman walks down a quiet beach at sunrise"
                    and sp["seconds"] == 5 and sp["engine"] == "local" and "start" not in sp
                    and sp["advanced"]["loras"] == [{"name": "wan_walk.safetensors", "strength": 0.8}], sent)
            state["providers"] = [{"name": "dashscope_video", "kind": "video", "configured": True}]
            page.reload()
            page.wait_for_selector("#vbBuild", timeout=15000)
            page.fill("#vbText", "a woman walks down a quiet beach at sunrise")
            page.select_option("#vxEngine", "dashscope_video")
            n1 = len(state["jobs"])
            page.click("#vbBuild")
            page.wait_for_selector("#vbExtend", timeout=15000)
            sent = state["jobs"][n1]
            sp = sent["params"]
            finding("Build on a hosted engine sends the Video (API) job with plain words and no local model",
                    sent["kind"] == "video_api" and sp["text"] == "a woman walks down a quiet beach at sunrise" and sp["seconds"] == 5
                    and "model" not in sp and "engine" not in sp and "start" not in sp, sent)
            state["providers"] = []
            page.reload()
            page.wait_for_selector("#vbBuild", timeout=15000)
            page.click("#vbBuild")
            page.fill("#vbText", "a woman walks down a quiet beach at sunrise")
            page.click("#vbBuild")
            page.wait_for_selector("#vbExtend", timeout=15000)
            page.click("#vbExtend")
            page.wait_for_selector("#vxExtend", timeout=15000)
            page.wait_for_selector("#vxTimeline .vx-step", timeout=10000)
            finding("Extend this opens the Extend page on that clip with a fresh chain",
                    page.url.endswith("#/video-extend") and page.locator("#vxTimeline .vx-step").count() == 1)
            b.close()
        finding("no JavaScript errors", not errors, errors[:3])
    finally:
        world.close()
    bad = results.count(False)
    print(f"\n{len(results) - bad}/{len(results)} video page checks passed")
    return bad == 0


if __name__ == "__main__":
    sys.exit(0 if browser() else 1)
