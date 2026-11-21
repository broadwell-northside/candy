"""Browser end-to-end tests for Easy Studio. No GPU, no RunPod, no secrets.

Starts the repo's fake ComfyUI and the real server, then drives Chromium.

    python tests/e2e_browser.py

Writes docs/E2E_PAIRWISE.md and a JSON summary under docs/e2e_last_run.json.
A full Cartesian product of the Create screen is not run. See the pairwise file.
"""
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
from run_tests import App, free_port  # noqa: E402

SHOTS = os.path.join(ROOT, "docs", "screenshots", "e2e")
ARTIFACTS = os.environ.get("E2E_ARTIFACTS", "/opt/cursor/artifacts")
FINDINGS = []
NOT_RUN = [
    "Real GPU pictures and video (ComfyUI with weights). The fake engine draws stand-in pictures.",
    "RunPod and any paid GPU. Not contacted.",
    "Downloading real model files (tens of gigabytes).",
    "A real Civitai download. Lookup of a bad link is tested. No API key is sent and nothing is bought.",
    "The real age-check neural net. The fake checker is used, including its under-21 flag.",
    "1Password and op:// paths. Not read and not changed.",
    "Quality of skin, hands, or motion. That needs a GPU and is not judged here.",
    "A not-installed video model card. The fake engine pretends every weight file is present, so every card is ready. The Make video button is still turned off in the page when a card is not ready.",
]


def finding(name, ok, detail=""):
    FINDINGS.append({"name": name, "ok": bool(ok), "detail": "" if ok else str(detail)[:500]})
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  -- {detail}"))
    return ok


def all_pairs(factors):
    """factors: list of (name, [values]). Every pair of values across two factors appears in some row.

    A full Cartesian product is the product of the lengths. This is the smaller covering set.
    """
    factors = [(n, list(v)) for n, v in factors if v]
    if not factors:
        return []
    names = [n for n, _ in factors]
    values = [v for _, v in factors]
    rows = [{names[0]: a} for a in values[0]] if len(values) == 1 else []
    if len(values) >= 2:
        rows = []
        for a in values[0]:
            for b in values[1]:
                rows.append({names[0]: a, names[1]: b})
    for fi in range(2, len(values)):
        name = names[fi]
        vals = values[fi]
        need = {(pj, row_val, v) for pj in range(fi) for row_val in values[pj] for v in vals}
        for row in rows:
            best, cover = vals[0], -1
            for v in vals:
                c = sum((pj, row[names[pj]], v) in need for pj in range(fi))
                if c > cover or (c == cover and str(v) < str(best)):
                    best, cover = v, c
            row[name] = best
            for pj in range(fi):
                need.discard((pj, row[names[pj]], best))
        while need:
            pj, prev, v = sorted(need, key=lambda item: (item[0], str(item[1]), str(item[2])))[0]
            need.discard((pj, prev, v))
            row = {names[k]: values[k][0] for k in range(fi + 1)}
            row[names[pj]] = prev
            row[name] = v
            for other in sorted(need, key=lambda item: (str(item[2]), item[0], str(item[1]))):
                opj, oprev, ov = other
                if ov == v and row.get(names[opj]) == values[opj][0]:
                    row[names[opj]] = oprev
                    need.discard(other)
            rows.append(row)
    for i, j in itertools.combinations(range(len(factors)), 2):
        have = {(r[names[i]], r[names[j]]) for r in rows}
        for a in values[i]:
            for b in values[j]:
                if (a, b) not in have:
                    row = {names[k]: values[k][0] for k in range(len(names))}
                    row[names[i]] = a
                    row[names[j]] = b
                    rows.append(row)
                    have.add((a, b))
    for i, j in itertools.combinations(range(len(factors)), 2):
        have = {(r[names[i]], r[names[j]]) for r in rows}
        for a in values[i]:
            for b in values[j]:
                if (a, b) not in have:
                    raise AssertionError(f"all-pairs missed {(names[i], a, names[j], b)}")
    return rows


def cartesian_size(factors):
    n = 1
    for _, vals in factors:
        n *= max(1, len(list(vals)))
    return n


class World:
    def __init__(self):
        self.out = tempfile.mkdtemp(prefix="es_e2e_")
        self.comfy = tempfile.mkdtemp(prefix="es_e2e_comfy_")
        self.mp, self.ap = free_port(), free_port()
        ldir = os.path.join(self.comfy, "models", "loras")
        os.makedirs(ldir)
        agedir = os.path.join(self.comfy, "models", "easy_studio", "age_check")
        os.makedirs(os.path.join(agedir, "torch", "hub", "checkpoints"))
        for n in ("model.safetensors", "config.json", "preprocessor_config.json",
                  os.path.join("torch", "hub", "checkpoints", "yunet_final.pth")):
            open(os.path.join(agedir, n), "w").write("{}")
        from v3_tests import fake_lora
        fake_lora(os.path.join(ldir, "film_grain_look.safetensors"),
                  ["lora_unet_input_blocks_4_1_proj_in.lora_down.weight",
                   "lora_unet_input_blocks_4_1_proj_in.lora_up.weight"],
                  {"ss_tag_frequency": '{"img": {"filmgrain": 20}}', "ss_base_model_version": "sdxl_base_v1-0"})
        self.trainer = tempfile.mkdtemp(prefix="es_e2e_tr_")
        shutil.copy(os.path.join(HERE, "fake_trainer_run.py"), os.path.join(self.trainer, "run.py"))
        py = sys.executable
        self.mock = subprocess.Popen([py, os.path.join(HERE, "mock_comfy.py"), str(self.mp)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                                     env=dict(os.environ, MOCK_LORA_DIR=ldir))
        env = dict(os.environ, EASY_STUDIO_OUTPUTS=self.out, COMFY_URL=f"http://127.0.0.1:{self.mp}",
                   EASY_STUDIO_PORT=str(self.ap), COMFY_DIR=self.comfy, COMFY_PYTHON=py,
                   EASY_STUDIO_TEST_RUN="1", EASY_STUDIO_AGE_WORKER=os.path.join(HERE, "fake_age_worker.py"),
                   EASY_STUDIO_TRAINER_DIR=self.trainer, EASY_STUDIO_TRAINER_PYTHON=py,
                   EASY_STUDIO_LORA_OFFLINE="1")
        self.srv = subprocess.Popen([py, os.path.join(ROOT, "app", "server.py")], env=env,
                                    stdout=open(self.out + "/server.log", "w"), stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.ap}"
        for _ in range(80):
            try:
                requests.get(self.base + "/api/status", timeout=2)
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("server did not start: " + open(self.out + "/server.log").read()[-500:])
        self.api = App(self.base)

    def close(self):
        self.srv.terminate()
        self.mock.terminate()


def shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    os.makedirs(ARTIFACTS, exist_ok=True)
    path = os.path.join(SHOTS, name + ".png")
    page.screenshot(path=path, full_page=True)
    shutil.copy(path, os.path.join(ARTIFACTS, name + ".png"))
    return path


def go(page, tab):
    page.evaluate("(t) => go(t)", tab)
    page.wait_for_function("(t) => document.body.innerText.length > 40", arg=tab, timeout=10000)
    page.wait_for_timeout(150)


def wait_job_ui(page, timeout=90000):
    page.wait_for_selector("#main .results .grid img, #main .results .grid video, #main .results model-viewer, #main .results .err, #main .results a[href*='/files/']", timeout=timeout)


def main():
    from playwright.sync_api import sync_playwright
    world = World()
    errors = []
    try:
        cat = world.api.get("/api/catalog").json()
        with sync_playwright() as p:
            exe = os.environ.get("CHROME", "/usr/bin/google-chrome")
            browser = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text and "favicon" not in m.text else None)
            page.goto(world.base + "/", wait_until="domcontentloaded")
            doors(page)
            desktop(page, world, cat)
            phone = browser.new_page(viewport={"width": 390, "height": 844})
            phone.on("pageerror", lambda e: errors.append("phone " + str(e)))
            phone.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text and "favicon" not in m.text else None)
            phone.goto(world.base + "/", wait_until="domcontentloaded")
            phone.wait_for_selector("#door-make", timeout=15000)
            mobile(phone, world)
            recipe_path(browser, world)
            browser.close()
        finding("no JavaScript errors", not errors, errors[:5])
        write_pairwise(world.api, cat)
    except Exception:
        finding("suite crashed", False, traceback.format_exc()[-800:])
    finally:
        world.close()
    report = {"passed": sum(1 for f in FINDINGS if f["ok"]), "failed": sum(1 for f in FINDINGS if not f["ok"]),
              "cases": FINDINGS, "not_run": NOT_RUN, "js_errors": errors[:20]}
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    json.dump(report, open(os.path.join(ROOT, "docs", "e2e_last_run.json"), "w"), indent=1)
    print(f"\n{report['passed']}/{report['passed'] + report['failed']} browser cases passed")
    sys.exit(1 if report["failed"] or errors else 0)


def doors(page):
    """First paint is the new home: Make · Play · Library and a Settings gear. Classic tools sit at the
    bottom of Make and open the 12 tabs exactly as before, with a Home button on top."""
    page.wait_for_selector("#door-make", timeout=15000)
    finding("first screen is Make · Play · Library", all(page.locator(f"#door-{d}").is_visible() for d in ("make", "play", "library")))
    finding("Settings is a gear on the home screen", page.locator("#homeGear").is_visible())
    tools = ["video-build", "video-extend", "create", "loras", "advanced"]
    finding("the home page is video first: Build a video, Extend a video, Make a picture, LoRAs, Advanced, each with a line",
            all(page.locator(f"#tool-{t}").is_visible() and page.locator(f"#tool-{t} .hint").inner_text().strip() for t in tools))
    before = page.evaluate("() => location.hash")
    page.locator("#soon-3d").click()
    finding("a Coming soon tile says so and opens nothing",
            page.locator("#soon-3d .hint").inner_text() == "Coming soon" and page.evaluate("() => location.hash") == before
            and page.locator("#firstRunSoon .tool-card.soon").count() == 11)
    go(page, "create")
    page.wait_for_selector("#main .tile", timeout=10000)
    txt = page.locator("#main").inner_text()
    finding("Create offers the realistic photo style only: no Anime, 3D render or Painted",
            "Realistic photo" in txt and "Anime" not in txt and "3D render" not in txt and "Painted" not in txt)
    go(page, "home")
    page.wait_for_selector("#door-make", timeout=10000)
    finding("Start here is the first tile on Home", page.locator("#firstRunTools > button").first.get_attribute("id") == "tool-start-here")
    page.click("#tool-start-here")
    page.wait_for_selector("#startHereGuide", timeout=10000)
    heads = page.locator("#startHereGuide h2").all_inner_texts()
    finding("the guide has its parts as plain headings, and the three downloads",
            len(heads) == 10 and heads[1].startswith("Part 1") and heads[5].startswith("Part 5")
            and "Small video model (Wan 2.2 5B)" in page.locator("#guide-1").inner_text())
    page.locator("#guide-1 a.guide-link").first.click()
    page.wait_for_selector("#modelsCard", timeout=15000)
    page.wait_for_function("() => { const r = document.getElementById('modelsCard').getBoundingClientRect(); return r.top < window.innerHeight; }", timeout=10000)
    finding("a guide link opens Setup at the Models card", True)
    go(page, "start-here")
    page.wait_for_selector("#startHereGuide", timeout=10000)
    page.locator("#guide-2 a.guide-link").first.click()
    page.wait_for_function("() => document.querySelector('#main').innerText.includes('Create a character')", timeout=10000)
    finding("the guide's Make a picture link opens Create", True)
    go(page, "home")
    page.wait_for_selector("#door-make", timeout=10000)
    finding("the Classic sidebar is not on the home screen", not page.locator("#nav").is_visible())
    page.locator("#door-make").click()
    page.wait_for_selector(".recipe-card", timeout=10000)
    finding("Make opens Recipes", page.locator(".recipe-card").count() == 3)
    finding("Classic tools is one link at the bottom of Make", page.locator("#classicTools").count() == 1)
    page.locator("#classicTools").click()
    page.wait_for_selector("#nav button[data-tab='studio']", timeout=15000)
    finding("Classic tools has a Home button", page.locator("#nav [data-tab='home']").is_visible())


def desktop(page, world, cat):
    page.wait_for_function("() => document.querySelector('#main').innerText.includes('Create a character')", timeout=10000)
    finding("Classic tools opens Create", "Create a character" in page.inner_text("#main"))
    finding("private build notice stays visible",
            page.locator(".private-build").inner_text() == "PRIVATE BUILD — NOT FOR DISTRIBUTION")
    finding("adult area is labeled 21+", "21+" in page.locator("#adultBtn").inner_text())
    finding("fictional-adults note is visible", page.locator(".adult-note").is_visible())
    finding("Video studio is in the nav on first paint", page.locator("#nav [data-tab='studio']").count() == 1)
    finding("LoRA library is in the nav on first paint", page.locator("#nav [data-tab='loras']").count() == 1)
    finding("Train is in the nav on first paint", page.locator("#nav [data-tab='train']").count() == 1)
    tabs = ["create", "workshop", "characters", "wardrobe", "pose", "scene", "objects", "photoshoot", "video", "studio",
            "3d", "assets", "loras", "lora-workshop", "train", "gallery", "advanced", "setup"]
    for tab in tabs:
        go(page, tab)
        text = page.inner_text("#main")
        finding(f"screen {tab} has words", len(text.strip()) > 40, text[:80])
        finding(f"screen {tab} does not say null", "null" not in text.lower() and "undefined" not in text.lower())
    go(page, "characters")
    finding("characters empty state", "No characters yet" in page.inner_text("#main"))
    go(page, "gallery")
    finding("gallery empty state", "Nothing here yet" in page.inner_text("#main"))
    shot(page, "gallery_empty")
    go(page, "create")
    age_cases(page)
    create_and_save(page, world)
    prop_page(page, world)
    workshop_path(page, world)
    prompt_helper(page)
    back_and_jobs(page, world)
    wardrobe_pose_scene_objects(page)
    video_journey(page)
    gallery_and_reuse(page)
    lora_and_train(page, world)
    studio_3d_assets(page, world)
    safety_cases(page, world)
    self_test(page)
    adult_and_settings(page, world)
    lora_workshop_page(page, world)
    likeness_card(page)
    pairwise_jobs(world, cat)
    shot(page, "after_create")


def age_cases(page):
    page.evaluate("""() => {
      S.dna = { style: "photo", gender: "woman", age: 25, ageSet: false, traits: {}, name: "", extra: "", notes: "" };
    }""")
    go(page, "create")
    btn = page.locator("#main button.btn.primary", has_text="Create")
    finding("catalog default 25 is not kept when it was not stated",
            page.evaluate("() => S.dna.age === null && S.dna.ageSet === false && S.cat.age.default === 25")
            and page.locator("#main input.stated-age").input_value() == "")
    finding("an unmoved age slider is not stored as 21", page.evaluate("""() => {
      const slider = document.querySelector("#main input[type=range]");
      return S.dna.age === null && slider && Number(slider.value) === S.cat.age.min;
    }"""))
    finding("Create is off until an age is typed", btn.is_disabled())
    why = page.locator("#main button.btn.primary", has_text="Create").get_attribute("title") or ""
    finding("missing age explains itself", "21" in why and "guess" in why.lower(), why)
    age = page.locator("#main input.stated-age")
    finding("age box starts empty", age.input_value() == "")
    page.locator("#main button", has_text="Surprise me").click()
    page.wait_for_timeout(200)
    rolled = page.evaluate("() => S.dna.age")
    finding("Surprise me stores a whole number from 21 through 40",
            isinstance(rolled, int) and 21 <= rolled <= 40 and page.evaluate("() => S.dna.ageSet === true"), rolled)
    for raw, needle in [("18", "under 21"), ("eighteen", "whole number"), ("", "guess"), ("9" * 20, "too long")]:
        age.fill(raw)
        age.dispatch_event("input")
        msg = page.locator("#ageWhy").inner_text()
        finding(f"age {raw!r} is not accepted", needle in msg and btn.is_disabled(), msg)
    age.fill("21")
    age.dispatch_event("input")
    finding("age 21 turns Create on", not btn.is_disabled())
    age.fill("70")
    age.dispatch_event("input")
    finding("age 70 is accepted", not btn.is_disabled() and "70" in page.inner_text("#main"))
    age.fill("200")
    age.dispatch_event("input")
    finding("a typed age over the slider, 200, is kept", not btn.is_disabled())
    age.fill("28")
    age.dispatch_event("input")
    name = page.locator("#main input[placeholder*='Lyra']")
    name.fill("L" * 80)
    finding("name stops at 60 characters", len(name.input_value()) == 60)
    name.fill("Lyra")
    shot(page, "create_age_set")


def create_and_save(page, world):
    go(page, "create")
    page.locator("#main input.stated-age").fill("28")
    page.locator("#main input[placeholder*='Lyra']").fill("Lyra")
    page.locator("#main .seg button", has_text="Fast draft").click()
    page.locator("#main .seg button").filter(has_text="1").first.click()
    before = len(world.api.get("/api/jobs").json())
    btn = page.locator("#main button.btn.primary", has_text="Create")
    btn.click()
    page.wait_for_timeout(80)
    btn.click(force=True)
    wait_job_ui(page)
    jobs = world.api.get("/api/jobs").json()
    created = [j for j in jobs if j["kind"] == "create"]
    finding("double-click starts one create job", len(created) == 1, len(created))
    finding("create shows a picture", page.locator("#main .results img").count() >= 1)
    page.locator("#main button", has_text="Save as character").first.click()
    page.wait_for_timeout(400)
    chars = world.api.get("/api/characters").json()
    finding("character saved with stated age 28", any(c.get("name") == "Lyra" and c.get("age") == 28 for c in chars), chars[:1])
    shot(page, "after_create_result")


def _writable_dir(directory):
    if os.path.isdir(directory):
        return os.access(directory, os.W_OK)
    parent = os.path.dirname(directory.rstrip(os.sep))
    return bool(parent) and os.path.isdir(parent) and os.access(parent, os.W_OK)


def save_prop_media(page, filename):
    """Save one screenshot. Extra copies are skipped when that folder is not writable."""
    os.makedirs(SHOTS, exist_ok=True)
    shot_path = os.path.join(SHOTS, filename)
    page.screenshot(path=shot_path, full_page=True)
    copies = []
    for directory in ("/cursor/stores/self/media", ARTIFACTS):
        if not _writable_dir(directory):
            continue
        try:
            os.makedirs(directory, exist_ok=True)
            dest = os.path.join(directory, filename)
            shutil.copy(shot_path, dest)
            copies.append(dest)
        except OSError:
            continue
    finding("saved " + filename,
            os.path.isfile(shot_path) and os.path.getsize(shot_path) > 1000
            and all(os.path.isfile(path) and os.path.getsize(path) > 1000 for path in copies))


def prop_page(page, world):
    from PIL import Image, ImageDraw
    jobs = [j for j in world.api.get("/api/jobs").json() if j.get("kind") == "create" and j.get("results")]
    if not jobs:
        finding("prop page has a still to use", False, "no create job")
        return
    still = jobs[0]["results"][0]
    still_id = still["id"] if isinstance(still, dict) else still
    page.evaluate("""async (id) => {
      const it = await api('/api/items/' + id);
      S.current = it;
      store.set('current', id);
    }""", still_id)
    go(page, "3d")
    text = page.inner_text("#main")
    finding("the prop page states the mesh limit",
            "rough prop mesh" in text and "not a rigged person" in text and "not a scan you can walk inside" in text, text[:400])
    finding("the prop page hides the node graph",
            "Show last workflow" not in text and "ComfyUI" not in text and "KSampler" not in text and "API JSON" not in text)
    finding("the prop page has two inputs",
            page.locator("#propStill").count() == 1 and page.locator("#propScenery").count() == 1)
    finding("the prop page does not offer a splat or a clay body",
            "Gaussian" not in text and "Hunyuan" not in text and "op://" not in text)
    page.locator("#propMake").click()
    page.wait_for_selector("#propResults model-viewer", timeout=90000)
    finding("a still becomes a prop on the page", page.locator("#propResults model-viewer").count() == 1)
    save_prop_media(page, "prop-from-still.png")
    page.locator("#propScenery").click()
    page.wait_for_selector("#sceneryFile", timeout=10000)
    picture = os.path.join(world.out, "visitors.png")
    face = Image.new("RGB", (80, 80), (30, 90, 50))
    ImageDraw.Draw(face).ellipse([18, 16, 62, 64], fill=(230, 190, 170))
    face.save(picture)
    page.locator("#sceneryFile").set_input_files(picture)
    page.locator("#sceneryOk").check()
    page.locator("#sceneryGo").click()
    page.wait_for_selector("#sceneryRefuse:not(.hidden)", timeout=10000)
    note = page.locator("#sceneryRefuse").inner_text()
    finding("a scenery photo with a face is refused on the page", "refused" in note.lower(), note)
    save_prop_media(page, "scenery-refused.png")
    page.locator(".modal-x").click()
    page.wait_for_timeout(200)


def save_export_shot(page, name):
    """One viewport tall enough for the page, so a sticky header is not painted twice."""
    previous = page.viewport_size
    height = page.evaluate("() => Math.ceil(document.documentElement.scrollHeight)")
    page.set_viewport_size({"width": 1440, "height": max(900, min(height + 40, 2600))})
    page.evaluate("() => window.scrollTo(0, 0)")
    dests = [os.environ.get("E2E_ARTIFACTS", "/opt/cursor/artifacts")]
    if os.path.isdir("/cursor/stores/self"):
        dests.append("/cursor/stores/self/media")
    written = []
    try:
        for dest in dests:
            os.makedirs(dest, exist_ok=True)
            path = os.path.join(dest, name)
            page.screenshot(path=path, full_page=False)
            written.append(path)
    finally:
        if previous:
            page.set_viewport_size(previous)
    finding("saved " + name, all(os.path.isfile(path) and os.path.getsize(path) > 1000 for path in written), written)


def save_still_shot(page, name):
    dest = os.environ.get("STILL_MEDIA")
    if not dest:
        return
    os.makedirs(dest, exist_ok=True)
    page.screenshot(path=os.path.join(dest, name), full_page=True)


def save_refine_shot(page, name):
    dest = os.environ.get("REFINE_MEDIA")
    if not dest:
        return
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, name)
    page.screenshot(path=path, full_page=True)
    finding(f"saved {name}", os.path.isfile(path) and os.path.getsize(path) > 1000, path)


def _unet_and_loras(world, job):
    wf = world.api.get(f"/api/jobs/{job['id']}/workflow").json()["workflows"][-1]
    unets = [n["inputs"].get("unet_name") for n in wf.values() if n.get("class_type") == "UNETLoader"]
    loras = [n["inputs"].get("lora_name") for n in wf.values() if n.get("class_type") == "LoraLoaderModelOnly"]
    return unets, loras


def workshop_path(page, world):
    go(page, "workshop")
    shot(page, "workshop_empty")
    save = page.locator("#workshopSave")
    finding("workshop save stays off with no age", save.is_disabled())
    jobs_before = len(world.api.get("/api/jobs").json())
    age = page.locator("#workshopAge")
    age.fill("18")
    age.dispatch_event("input")
    finding("workshop rejects an under-21 age", save.is_disabled() and "under 21" in page.locator("#workshopAgeWhy").inner_text())
    finding("an under-21 workshop age does not start a job", len(world.api.get("/api/jobs").json()) == jobs_before)
    island = page.locator("#workshopIsland").inner_text()
    finding("an under-21 age is not sent to the island",
            page.locator("#workshopSend").is_disabled()
            and "under 21" in page.locator("#workshopIslandWhy").inner_text()
            and "not sent" in page.locator("#workshopIslandWhy").inner_text(),
            page.locator("#workshopIslandWhy").inner_text())
    finding("the island step says what the pack is for",
            "island importer" in page.locator("#workshopIslandNote").inner_text()
            and "separate game update" in page.locator("#workshopIslandNote").inner_text(),
            page.locator("#workshopIslandNote").inner_text())
    finding("the island step hides the node graph",
            "Show last workflow" not in island and "ComfyUI" not in island and "KSampler" not in island and "API JSON" not in island,
            island[:400])
    save_export_shot(page, "export-refused.png")
    age.fill("32")
    age.dispatch_event("input")
    page.locator("#workshopName").fill("Mara")
    finding("workshop save turns on for age 32", not save.is_disabled())
    save.click()
    page.wait_for_selector("#workshopNext:not(.hidden)", timeout=10000)
    text = page.locator("#workshopNext").inner_text()
    chars = world.api.get("/api/characters").json()
    mara = next((c for c in chars if c.get("name") == "Mara"), None)
    finding("workshop saves a fictional adult aged 32",
            mara and mara.get("age") == 32 and mara.get("stated_age") == 32 and mara.get("age") != 25, mara)
    finding("workshop shows the still step", "Make a still" in text and "32" in text
            and "fast model does not keep the face" in text, text)
    finding("the still step does not show the ComfyUI graph",
            "Show last workflow" not in text and "API JSON" not in text and "ComfyUI" not in text)
    finding("stated age on the still step is not an editable field",
            page.locator("#workshopNext input.stated-age").count() == 0
            and page.locator("#workshopAgeShown").inner_text().strip() == "Stated age: 32")
    finding("nude preset is absent while the adult switch is off",
            page.locator("#workshopNude").count() == 0 and "Nude" not in page.locator("#workshopWardrobe").inner_text()
            and "Leave" not in page.locator("#adultBtn").inner_text())
    finding("saving the person does not start a picture job", len(world.api.get("/api/jobs").json()) == jobs_before)
    page.locator("#workshopLook").fill("olive skin, long dark hair, a linen shirt")
    page.locator("#workshopBody .chip", has_text="Athletic").click()
    save_still_shot(page, "stills-adult-off.png")
    shot(page, "workshop_next")
    page.locator("#workshopStill").click()
    page.wait_for_selector("#workshopResults img", timeout=30000)
    jobs = [j for j in world.api.get("/api/jobs").json() if j.get("kind") == "workshop_still"]
    unets, loras = _unet_and_loras(world, jobs[0])
    finding("an everyday still uses Z-Image-Turbo and no face LoRA",
            jobs[0].get("status") == "done" and unets == ["z_image_turbo_bf16.safetensors"] and loras == [],
            (jobs[0].get("error"), unets, loras))
    positive = json.dumps(world.api.get(f"/api/jobs/{jobs[0]['id']}/workflow").json())
    finding("the still keeps the saved age of 32", "32-year-old" in positive and "18-year-old" not in positive)
    shot(page, "workshop_still")
    save_still_shot(page, "stills-clothed.png")
    page.wait_for_function("() => { const b = document.querySelector('#workshopSkin'); return b && !b.disabled; }", timeout=10000)
    refine = page.locator("#workshopRefine").inner_text()
    finding("refine anatomy is absent while 21+ is off", page.locator("#workshopAnatomy").count() == 0)
    finding("refine skin is on the workshop path", "Refine skin" in refine and page.locator("#workshopSkin").count() == 1)
    finding("the page says the check can miss a youthful result",
            "The check can miss a youthful result and can flag a young-looking adult. It is not a guarantee." in refine)
    finding("the page says no extra detailer is loaded",
            "No extra detailer is loaded" in refine and "private use is allowed" in refine)
    finding("the refine step hides the node graph",
            "Show last workflow" not in refine and "ComfyUI" not in refine and "KSampler" not in refine)
    preview = page.locator("#workshopResults").inner_text()
    for label in ("Outfit", "Pose", "Scene", "Object", "Animate", "3D", "Sheets", "To video", "Upscale", "Cut out", "Download"):
        finding(f"workshop preview hides {label}", label not in preview, preview[:300])
    finding("workshop preview has no tool buttons",
            page.locator("#workshopResults .actions button, #workshopResults .actions a").count() == 0)
    save_refine_shot(page, "anatomy-hidden.png")
    page.locator("#workshopSkin").click()
    page.wait_for_function(
        "() => { const n = document.querySelector('#workshopSkinStatus'); return n && n.textContent.includes('not a photograph'); }",
        timeout=30000)
    skin_jobs = [j for j in world.api.get("/api/jobs").json() if j.get("kind") == "refine_skin"]
    unets, loras = _unet_and_loras(world, skin_jobs[0])
    finding("refine skin uses the fast model and no extra detailer",
            skin_jobs[0].get("status") == "done" and unets == ["z_image_turbo_bf16.safetensors"] and loras == [],
            (skin_jobs[0].get("error"), unets, loras))
    preview = page.locator("#workshopResults").inner_text()
    finding("the refined preview is not called a photograph",
            page.locator("#workshopResults img").first.get_attribute("alt") == "Generated picture. Not a photograph."
            and "To video" not in preview and "Download" not in preview and "Outfit" not in preview)
    save_refine_shot(page, "skin-refine.png")
    page.locator("#workshopKeep").click()
    page.wait_for_function("() => document.querySelector('#workshopFaceNote') && document.querySelector('#workshopFaceNote').textContent.includes('saved')", timeout=30000)
    chars = world.api.get("/api/characters").json()
    mara = next(c for c in chars if c.get("name") == "Mara")
    finding("keep this face records a LoRA id and does not download weights",
            mara.get("look", {}).get("weights_downloaded") is False and mara["look"]["private_use"] == "yes"
            and mara["look"]["lora_id"].endswith("_identity.safetensors"), mara.get("look"))
    save_still_shot(page, "stills-face-kept.png")
    page.locator("#workshopStill").click()
    page.wait_for_selector("#workshopResults img", timeout=30000)
    kept = [j for j in world.api.get("/api/jobs").json() if j.get("kind") == "workshop_still"][0]
    unets, loras = _unet_and_loras(world, kept)
    finding("a saved face runs on the foundation model, not on Turbo",
            unets == ["z_image_bf16.safetensors"] and loras == [mara["look"]["lora_id"]] and "turbo" not in "".join(unets),
            (unets, loras))
    finding("send to the island turns on for a saved adult", not page.locator("#workshopSend").is_disabled())
    save_export_shot(page, "export-ready.png")
    page.locator("#workshopSend").click()
    page.wait_for_selector("#workshopIslandFile a", timeout=30000)
    pack_jobs = [j for j in world.api.get("/api/jobs").json() if j.get("kind") == "export_godot"]
    finding("send to the island writes a pack without a node graph",
            pack_jobs and pack_jobs[0].get("status") == "done" and not pack_jobs[0].get("has_workflow")
            and "Download the pack" in page.locator("#workshopIslandFile").inner_text()
            and page.locator("#workshopResults .actions button, #workshopResults .actions a").count() == 0,
            pack_jobs[0].get("error") if pack_jobs else "no job")
    for it in (pack_jobs[0].get("results") or []) if pack_jobs else []:
        if it.get("id"):
            world.api.s.delete(world.api.base + "/api/items/" + it["id"], timeout=30)
    go(page, "gallery")
    page.wait_for_selector("#main .actions a", timeout=10000)
    finding("gallery still has Download on its own page",
            page.locator("#main .actions a", has_text="Download").count() >= 1)


def prompt_helper(page):
    go(page, "create")
    page.locator("#main .subtabs button", has_text="Fantasy").click()
    page.locator("#main button", has_text="a fictional adult woman").first.click()
    extra = page.locator("#main input[placeholder*='scar']")
    finding("prompt helper writes a phrase", "fictional adult woman" in extra.input_value())
    extra.fill("standing with a man")
    page.locator("#main button", has_text="Check wording").click()
    page.wait_for_timeout(400)
    note = page.locator("#main .help-note").inner_text()
    finding("prompt helper rejects a second person with no age", "age" in note.lower() or "21" in note, note)
    extra.fill("teen")
    page.locator("#main button", has_text="Check wording").click()
    page.wait_for_timeout(300)
    note = page.locator("#main .help-note").inner_text()
    finding("prompt helper rejects a minor word", "teen" in note.lower() or "blocked" in note.lower(), note)
    extra.fill("")
    shot(page, "prompt_helper")


def back_and_jobs(page, world):
    go(page, "create")
    go(page, "wardrobe")
    page.go_back()
    page.wait_for_timeout(400)
    finding("back button returns to Create", "Create a character" in page.inner_text("#main") or page.evaluate("() => S.tab") == "create")
    dna = {"gender": "woman", "age": 30, "style": "photo", "name": "Hold", "traits": {}, "extra": "e2e_hold_job"}
    world.api.post("/api/jobs", json={"kind": "create", "params": {"dna": dna, "count": 1, "speed": "fast"}})
    page.reload()
    page.wait_for_selector("#liveJobBar", timeout=8000)
    finding("refresh mid-job shows a still-running note", "still running" in page.inner_text("#liveJobBar").lower())
    shot(page, "refresh_mid_job")
    page.click("#jobsBtn")
    page.locator("#jobsPanel button", has_text="Stop").first.wait_for(timeout=8000)
    finding("jobs panel uses a plain name", "Create pictures" in page.inner_text("#jobsPanel"))
    page.locator("#jobsPanel button", has_text="Stop").first.click()
    page.wait_for_timeout(1500)
    jobs = world.api.get("/api/jobs").json()
    finding("stop cancels the held job", any(j.get("status") == "cancelled" for j in jobs), [j.get("status") for j in jobs[:3]])
    shot(page, "jobs_panel")
    if page.locator("#jobsPanel:not(.hidden)").count():
        page.click("#jobsBtn")


def click_card_action(page, label):
    card = page.locator("#main .res").first
    card.hover()
    card.locator("button", has_text=label).click(force=True)


def wardrobe_pose_scene_objects(page):
    go(page, "gallery")
    click_card_action(page, "Outfit")
    page.wait_for_timeout(400)
    finding("wardrobe opens on the picture", "Wardrobe" in page.inner_text("h1"))
    page.locator("#main .chip", has_text="Jeans").first.click()
    finding("wardrobe mode control exists", page.locator("#main .seg button", has_text="Pick an outfit").count() >= 1)
    page.locator("#main button.btn.primary", has_text="Change outfit").click()
    wait_job_ui(page, timeout=60000)
    finding("outfit change returns a picture", page.locator("#main .results img").count() >= 1, page.locator("#main .results").inner_text()[:240])
    go(page, "pose")
    page.locator("#main .tile", has_text="Standing").first.click()
    page.locator("#main button.btn.primary", has_text="Apply pose").click()
    wait_job_ui(page)
    finding("pose returns a picture", page.locator("#main .results img").count() >= 1, page.locator("#main .results").inner_text()[:240])
    go(page, "scene")
    page.locator("#main .tile", has_text="Beach").first.click()
    page.locator("#main button.btn.primary", has_text="Change the scene").click()
    wait_job_ui(page)
    finding("scene change returns a picture", page.locator("#main .results img").count() >= 1)
    go(page, "objects")
    page.locator("#main .tile", has_text="Wine").first.click()
    page.locator("#main button.btn.primary", has_text="Add it").click()
    wait_job_ui(page)
    finding("object add returns a picture", page.locator("#main .results img").count() >= 1)


def video_journey(page):
    go(page, "gallery")
    click_card_action(page, "Animate")
    page.wait_for_selector("#filmMake", timeout=10000)
    text = page.inner_text("#main")
    finding("the film page says touching is not solved",
            "Two people touching is still the weak spot" in text and "It is not solved" in text, text[:500])
    finding("the film page says Wan has no sound", "Wan has no sound" in text)
    finding("the film page hides the node graph",
            "Show last workflow" not in text and "ComfyUI" not in text and "KSampler" not in text and "API JSON" not in text)
    for banned in ("Where bodies meet looks right", "Repair contact can fix a join.", "Repaint the join between two adults.", "Repair contact"):
        finding("film page does not say " + banned, banned not in text, text[:400])
    finding("explicit films stay behind the 21+ switch",
            "off" in page.locator("#filmSwitch").inner_text().lower() and "21+" in page.locator("#filmSwitch").inner_text())
    finding("no undress chip while 21+ is off", page.locator("#main .chip", has_text="Slowly undress").count() == 0)
    finding("a short film stays off until a still is chosen",
            page.locator("#filmMake").is_disabled() or "kept" in page.locator("#filmChoice").inner_text(),
            page.locator("#filmChoice").inner_text())
    save_prop_media(page, "film-contact-limit.png")
    if page.locator("#filmMake").is_disabled():
        page.locator("#filmStill").click()
        page.wait_for_selector("#modal .res")
        page.locator("#modal .res").first.click()
        page.wait_for_timeout(300)
    make = page.locator("#filmMake")
    finding("make a short film turns on for a kept still", not make.is_disabled(), make.get_attribute("title"))
    make.click()
    page.wait_for_selector("#filmResults video", timeout=90000)
    finding("a short film appears on the page", page.locator("#filmResults video").count() == 1)
    finding("the finished page still says Wan has no sound", "Wan has no sound" in page.inner_text("#main"))
    save_prop_media(page, "film-from-still.png")
    shot(page, "video_screen")


def gallery_and_reuse(page):
    go(page, "gallery")
    finding("gallery has pictures", page.locator("#main .res").count() >= 1)
    page.locator("#main .seg button", has_text="Pictures").click()
    page.wait_for_timeout(300)
    page.locator("#main .res img").first.click()
    page.wait_for_selector("#modal")
    finding("picture details open", "Download" in page.inner_text("#modal") or "Hidden" in page.inner_text("#modal"))
    if page.locator("#modal button", has_text="Use as working picture").count():
        page.locator("#modal button", has_text="Use as working picture").click()
    else:
        page.keyboard.press("Escape")
    page.wait_for_timeout(200)


def lora_and_train(page, world):
    go(page, "loras")
    finding("LoRA card is listed", "film" in page.inner_text("#main").lower() or page.locator(".card.lora").count() >= 1)
    shot(page, "lora_cards")
    blocked = page.locator("#main button.btn.primary", has_text="Change outfit")
    drop = page.locator(".dropzone")
    finding("LoRA drop zone is there", drop.count() == 1)
    page.locator("#main input[placeholder*='civitai']").fill("not a link")
    page.locator("#main button", has_text="Look it up").click()
    page.wait_for_timeout(500)
    finding("bad Civitai link shows an error", page.locator("#main .err").count() >= 1 or "civitai" in page.inner_text("#main").lower())
    go(page, "train")
    text = page.inner_text("#main")
    finding("train screen explains the rule", "never trains on photos" in text.lower() or "real people" in text.lower())
    if page.locator("#main button.btn.primary", has_text="Make training pictures").count():
        page.locator("#main select").first.select_option("12")
        page.locator("#main button.btn.primary", has_text="Make training pictures").click()
        try:
            page.wait_for_function("() => /picked/.test(document.querySelector('#main').innerText)", timeout=120000)
            finding("training pictures appear", True)
        except Exception as e:
            finding("training pictures appear", False, str(e))
    else:
        finding("training pictures appear", False, "button missing")


def studio_3d_assets(page, world):
    go(page, "studio")
    finding("video studio lists model cards", page.locator(".mcard").count() >= 4)
    off = page.locator(".mcard.off")
    if off.count():
        off.first.click()
        page.wait_for_timeout(200)
        make = page.locator("#main button.btn.primary", has_text=re.compile(r"Make video$"))
        finding("uninstalled model disables Make video", make.is_disabled(), make.get_attribute("title"))
    ready = page.locator(".mcard:not(.off)", has_text="Text")
    if not ready.count():
        ready = page.locator(".mcard:not(.off)")
    ready.first.click()
    page.wait_for_timeout(200)
    area = page.locator("#main textarea").first
    if area.count():
        area.fill("a fictional adult woman walks through a studio")
    page.locator("#main button.btn.primary", has_text=re.compile(r"Make video$")).click()
    wait_job_ui(page, timeout=90000)
    finding("video studio returns a clip or a clear error", page.locator("#main .results video, #main .results .err").count() >= 1)
    go(page, "gallery")
    card = page.locator("#main .res").filter(has=page.locator("button", has_text="3D")).first
    card.hover()
    card.locator("button", has_text="3D").click(force=True)
    page.wait_for_selector("#propMake", timeout=10000)
    finding("the gallery opens the prop step", "rough prop mesh" in page.inner_text("#propLimit"))
    page.locator("#propMake").click()
    page.wait_for_selector("model-viewer, #main .results .err", timeout=90000)
    finding("3D result or a clear error", page.locator("model-viewer, #main .results .err").count() >= 1)
    go(page, "assets")
    finding("game assets lists the tools", "Turnaround" in page.inner_text("#main") and "Sprite" in page.inner_text("#main"))
    page.locator("#main button.btn.primary", has_text="Make turnaround").click()
    wait_job_ui(page)
    finding("turnaround returns a picture", page.locator("#main .results img").count() >= 1)


def safety_cases(page, world):
    from PIL import Image, ImageDraw
    picture = os.path.join(world.out, "person.png")
    im = Image.new("RGB", (80, 120), (40, 80, 120))
    ImageDraw.Draw(im).ellipse([20, 15, 60, 60], fill=(230, 190, 170))
    im.save(picture)
    go(page, "gallery")
    page.locator("#main button", has_text="Upload").click()
    page.wait_for_selector("#modal input.stated-age")
    page.locator("#modal input[type=file]").set_input_files(picture)
    page.locator("#modal input[type=checkbox]").check()
    page.locator("#modal input.stated-age").fill("20")
    page.locator("#modal button.btn.primary", has_text="Upload").click()
    page.wait_for_selector(".toast.bad")
    toast = page.locator(".toast.bad").last.inner_text()
    finding("upload age 20 is rejected and not raised", "under 21" in toast and "not raised" in toast, toast)
    page.locator("#modal input.stated-age").fill("")
    page.locator("#modal button.btn.primary", has_text="Upload").click()
    page.wait_for_timeout(400)
    toast = page.locator(".toast.bad").last.inner_text()
    finding("upload with no age is rejected", "missing" in toast.lower() or "not inferred" in toast.lower(), toast)
    page.locator("#modal .modal-x").click()
    cloth = os.path.join(world.out, "dress.png")
    Image.new("RGB", (60, 80), (180, 20, 40)).save(cloth)
    up = world.api.upload(Image.open(cloth), "clothing", name="red_dress.png")
    cloth_id = up.json()["id"]
    mine = world.api.upload(Image.open(picture), "my_character", name="my_oc.png", age="34")
    finding("upload of fictional character art at 34 works", mine.status_code == 200, mine.text[:200])
    mine_id = mine.json()["id"]
    edit = world.api.job("edit", {"image": cloth_id, "op": "outfit", "item": "nude", "text": "remove her clothes"})
    finding("a clothing photo cannot be edited as the person", edit["status"] in ("error", "refused"), edit.get("error"))
    world.api.post("/api/adult/unlock", json={"confirm_age": True, "confirm_rules": True})
    undress = world.api.job("edit", {"image": mine_id, "op": "outfit", "text": "remove her clothes"}, area="adult")
    finding("clothes are not removed from an uploaded picture", undress["status"] in ("error", "refused") and "won't remove" in (undress.get("error") or ""), undress.get("error"))
    world.api.post("/api/adult/lock")
    go(page, "advanced")
    page.locator("#main textarea").fill('{"1": {"class_type": "ReActorFaceSwap", "inputs": {}}}')
    page.locator("#main button.btn.primary", has_text="Run workflow").click()
    page.wait_for_timeout(500)
    finding("face-swap workflow is refused", "face" in page.inner_text("#main").lower() or page.locator("#main .err, .toast.bad").count() >= 1)
    flagged = world.api.job("create", {"dna": {"gender": "woman", "age": 29, "style": "photo", "name": "Flag"},
                                        "count": 1, "speed": "fast", "extra_scene": "magentatest"})
    finding("age-check flag deletes the result: no item, a plain message, a retry offered",
            flagged.get("status") == "error" and not flagged.get("results") and flagged.get("can_retry") is True
            and "deleted" in (flagged.get("error") or ""), flagged.get("error") or flagged.get("warning"))
    go(page, "gallery")
    page.wait_for_timeout(400)
    finding("nothing flagged or blurred is shown in the gallery", page.locator("#main .res.flagged").count() == 0)


def self_test(page):
    """The Self-test card on the Setup page: one button runs the chain through the app and shows the numbers."""
    go(page, "setup")
    page.wait_for_selector("#selfTestCard #selfTestGo", timeout=15000)  # the card comes after the Setup page's own parts
    finding("the Setup page shows a Self-test card with its button and the trainer's",
            page.locator("#selfTestCard #selfTestGo").count() == 1 and page.locator("#selfTestCard #selfTestTrainer").count() == 1)
    page.click("#selfTestGo")
    page.wait_for_function("() => /Self-test (passed|stopped)/.test(document.querySelector('#selfTestSay').innerText)", timeout=300000)
    said = page.locator("#selfTestSay").inner_text()
    rows = page.locator("#selfTestSteps li").all_inner_texts()
    finding("the self-test runs text to picture, clip, longer clip and 3D through the app, and all four pass",
            "passed: 4 of 4" in said and len(rows) == 4 and all("passed in" in r for r in rows), said + " | " + " / ".join(rows))
    finding("each step shows its numbers", len(rows) == 4 and "pixels" in rows[0] and "frames" in rows[1] and "frames" in rows[2]
            and "points" in rows[3] and "faces" in rows[3], rows)
    shot(page, "desktop_selftest")


def adult_and_settings(page, world):
    go(page, "create")
    page.click("#adultBtn")
    page.wait_for_selector("#modal")
    text = page.inner_text("#modal")
    finding("18+ gate says 21 or older", "21 or older" in text, text[:240])
    shot(page, "adult_gate")
    for box in page.locator("#modal input[type=checkbox]").all():
        box.check()
    page.locator("#modal button.btn.primary", has_text="Open 21+").click()
    page.wait_for_timeout(600)
    finding("18+ section opens", page.locator("#adultBar:not(.hidden)").count() == 1)
    go(page, "workshop")
    page.locator("#workshopAge").fill("36")
    page.locator("#workshopAge").dispatch_event("input")
    page.locator("#workshopName").fill("Nia")
    page.locator("#workshopSave").click()
    page.wait_for_selector("#workshopRefine:not(.hidden)", timeout=10000)
    page.locator("#workshopLook").fill("short dark hair, a linen shirt")
    page.locator("#workshopStill").click()
    page.wait_for_selector("#workshopResults img", timeout=30000)
    page.wait_for_function("() => { const b = document.querySelector('#workshopAnatomy'); return b && !b.disabled; }", timeout=10000)
    anatomy_jobs = [j for j in world.api.get("/api/jobs").json() if j.get("kind") == "refine_anatomy"]
    finding("refine anatomy is on the page while 21+ is open", page.locator("#workshopAnatomy").inner_text() == "Refine anatomy")
    finding("showing the anatomy control does not run an anatomy job", anatomy_jobs == [])
    finding("the anatomy note says the face can change", "face can change" in page.locator("#workshopAnatomyCopy").inner_text())
    save_refine_shot(page, "anatomy-on.png")
    go(page, "setup")
    toggle = page.locator("#main input[type=checkbox]").first
    dialog_text = {"message": ""}

    def remember(dialog):
        dialog_text["message"] = dialog.message
        dialog.dismiss()

    page.once("dialog", remember)
    toggle.click()
    page.wait_for_timeout(300)
    message = dialog_text["message"]
    finding("age check stays on if you dismiss the warning", toggle.is_checked())
    finding("the confirm sentence does not say unchecked results are still produced",
            "will not run" in message and "won't be checked" not in message and "unchecked" not in message.lower(),
            message)
    page.locator("#adultBar button", has_text="Lock").click()
    page.wait_for_timeout(400)
    finding("lock closes the 18+ section", page.locator("#adultBar.hidden").count() == 1)


def lora_workshop_page(page, world):
    go(page, "lora-workshop")
    page.wait_for_selector("#loraCat-taken-down", timeout=15000)
    text = page.inner_text("#main")
    finding("lora workshop keeps the private notice",
            page.locator(".private-build").inner_text() == "PRIVATE BUILD — NOT FOR DISTRIBUTION")
    for banned in ("girlfriend", "boyfriend", "companion"):
        finding("lora workshop does not say " + banned, banned not in text.lower())
    finding("taken-down LoRA is refused on the library", "TakenDown" in page.locator("#loraTakenDown").inner_text())
    finding("weights stay put until confirm", page.locator("#loraCat-clay-shore button").is_disabled())
    save_export_shot(page, "lora-library.png")
    page.locator("#loraConfirm").check()
    page.locator("#loraCat-clay-shore button").click()
    page.locator("#loraLibraryList .card", has_text="Clay shore light").locator("button", has_text="Open usage card").click(timeout=15000)
    page.wait_for_selector("#loraUsage", timeout=10000)
    card = page.locator("#loraUsageCard").inner_text()
    finding("usage card shows UNKNOWN strengths", "Model strength UNKNOWN" in card and "Clip strength UNKNOWN" in card, card[:400])
    finding("usage card names the three recipes", "Author recipe" in card and "App suggestion" in card and "My tested preset" in card)
    finding("author example keeps its source id", "Author example" in card and "civitai:" in card)
    weight = page.locator("#loraWeight").inner_text()
    page.locator("#loraPrompt").fill("warm sand")
    page.locator("#loraInsertTriggers").click()
    page.wait_for_timeout(400)
    finding("trigger words do not load a different file", page.locator("#loraWeight").inner_text() == weight and "clayshore" in page.locator("#loraPrompt").input_value())
    page.locator("#loraSamplePrompt").click()
    page.wait_for_timeout(400)
    finding("one-tap sample keeps the source id", "civitai:" in page.locator("#loraSampleSource").inner_text() and page.locator("#loraWeight").inner_text() == weight)
    save_export_shot(page, "lora-usage-card.png")
    page.locator("#loraGoLibrary").click()
    page.locator("#loraCat-wan21-face button").click()
    page.wait_for_timeout(500)
    page.locator("#loraGoStack").click()
    page.wait_for_selector("#loraStackPicks")
    page.locator("#loraStackPicks button", has_text="Wan face twenty one").click()
    page.wait_for_selector("#loraConflictBanner", timeout=10000)
    banner = page.locator("#loraConflictBanner").inner_text()
    finding("the stack shows the Wan conflict", "Wan 2.1 LoRA in Wan 2.2 High Noise" in banner, banner)
    finding("stack coach is on the page", "Stack coach" in page.locator("#loraCoach").inner_text())
    save_export_shot(page, "lora-conflict.png")
    page.locator("#loraGoLibrary").click()
    page.locator("#loraLibraryList .card.lora", has_text="Clay shore light").locator("button", has_text="Open usage card").click()
    page.wait_for_selector("#loraWeight", timeout=10000)
    page.locator("#loraPrompt").fill("a fictional adult, age 32, linen shirt, warm sand")
    page.locator("#loraGoBenchmark").click()
    page.locator("#loraBenchAge").fill("32")
    page.locator("#loraBenchAge").dispatch_event("input")
    page.locator("#loraSeed").fill("4242")
    page.locator("#loraSeed").dispatch_event("input")
    page.locator("#loraRunBench").click()
    page.wait_for_selector("#loraBenchGrid img, #loraBenchmark .err", timeout=120000)
    bench_text = page.locator("#loraBenchmark").inner_text()
    pictures = page.locator("#loraBenchGrid img")
    finding("benchmark shows eight mock pictures", pictures.count() == 8, bench_text[:500])
    finding("benchmark pictures are not photographs",
            pictures.count() == 8 and pictures.first.get_attribute("alt") == "Mock picture. Not a photograph.")
    save_export_shot(page, "lora-benchmark.png")
    page.locator("#loraGoTrain").click()
    page.wait_for_selector("#loraTrainMe")
    train = page.locator("#loraTrainMe").inner_text()
    finding("train says ai-toolkit and no publish", "ai-toolkit" in train and "not in this version" in train.lower())
    finding("an inference LoRA is not a checkpoint", "not a resumable training checkpoint" in train)
    finding("Me is the player and not an NPC", "Me is the player, Andrew, not an NPC" in train)
    finding("sexual content is not offered for Me", "Sexual content is not offered for Me" in train)
    finding("the practice run does not spend money", "does not spend money" in train)
    save_export_shot(page, "lora-train-me.png")


def likeness_card(page):
    """The My likeness card: three steps (Enrol, Train, Create), everything else under More.

    First against the app as it is here (no face check installed, nobody enrolled). Then with canned answers for
    the likeness routes, to walk Train and Create in the page without a camera or a model."""
    go(page, "setup")
    page.wait_for_selector("#phaseTwoCard", timeout=15000)
    finding("phase two is hidden by default: no My likeness card on Setup, one switch to show it",
            page.locator("#ownerCard").count() == 0 and not page.locator("#phaseTwoSwitch").is_checked())
    page.click("#phaseTwoSwitch")
    page.wait_for_selector("#ownerCard #ownerSteps", timeout=15000)
    finding("the Setup switch shows the My likeness card", page.locator("#phaseTwoSwitch").is_checked())
    page.wait_for_selector("#ownerCard #ownerPhotosBtn", timeout=15000)   # Add photos is drawn into the card after it (owner_photos.js)
    steps = page.locator("#ownerCard button.primary")
    finding("the likeness card shows exactly four steps: Enrol, Add photos, Train, Create",
            steps.all_inner_texts() == ["1 Enrol", "Add photos", "2 Train", "3 Create"], steps.all_inner_texts())
    finding("before enrolment, Add photos, Train and Create cannot be pressed and nothing else is offered",
            page.locator("#ownerPhotosBtn").is_disabled() and page.locator("#ownerTrainBtn").is_disabled() and page.locator("#ownerCreateBtn").is_disabled()
            and page.locator("#ownerMore").count() == 0 and page.locator("#ownerCard input[type=file]").count() == 0)
    page.click("#ownerEnrolBtn")
    words = page.locator("#ownerFaceWords").inner_text()
    finding("Enrol says in plain words what the face check is for, and that its live check does not detect a recording",
            "pictures of a real person" in words and "nothing leaves it" in words and "does not detect a recording" in words, words)
    finding("with no face check installed, Enrol says so and offers no camera",
            "not installed" in page.locator("#ownerSay").inner_text() and page.locator("#ownerStart").count() == 0, page.locator("#ownerSay").inner_text())

    state = {"unlocked": False, "selftest": False, "loras": 0, "jobs": [], "pictures": 0}
    dot = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    def answer(route, body, status=200):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    def owner_routes(route, request):
        path = request.url.split("/api/owner/")[1].split("?")[0]
        if path == "status":
            return answer(route, {"enrolled": True, "checker_on": True, "face_check": True, "face_check_message": "", "steps": 12,
                                  "min_passphrase": 10, "unlocked": state["unlocked"], "consent_18": False, "window_open": False, "how": "By camera."})
        if path == "trainer":
            return answer(route, {"trainer_installed": True, "device": "mps", "selftest_passed": state["selftest"], "likeness_loras": state["loras"]})
        if path == "unlock":
            good = (request.post_data_json or {}).get("passphrase") == "a stand-in passphrase"
            state["unlocked"] = state["unlocked"] or good
            return answer(route, {"ok": True} if good else {"error": "That passphrase is not right."}, 200 if good else 400)
        if path == "gallery":
            return answer(route, {"items": [{"id": "g%d" % n, "url": dot, "area": "default"} for n in range(state["pictures"])]})
        return route.continue_()

    def job_routes(route, request):
        if request.method == "POST" and request.url.endswith("/api/jobs"):
            body = request.post_data_json or {}
            if not str(body.get("kind", "")).startswith("owner_"):
                return route.continue_()
            state["jobs"].append(body)
            return answer(route, {"id": "ownerstub%d" % len(state["jobs"])})
        if "/api/jobs/ownerstub" in request.url:
            kind = state["jobs"][int(request.url.rsplit("ownerstub", 1)[1]) - 1]["kind"]
            state["selftest"] = state["selftest"] or kind == "owner_train_selftest"
            if kind == "owner_train":
                state["loras"] = 1
            if kind == "owner_picture":
                state["pictures"] = 1
            return answer(route, {"id": "x", "status": "done", "message": "Saved to your private gallery (1)." if kind == "owner_picture" else "Done", "results": []})
        return route.continue_()

    page.route("**/api/owner/**", owner_routes)
    page.route("**/api/jobs**", job_routes)
    try:
        go(page, "advanced")
        go(page, "setup")
        page.wait_for_selector("#ownerCard #ownerMore", state="attached", timeout=15000)
        page.wait_for_selector("#ownerCard #ownerPhotosBtn", timeout=15000)
        finding("once enrolled: Enrol is ticked, Train can be pressed, Create waits for the training",
                page.locator("#ownerEnrolBtn").inner_text() == "1 Enrol ✓" and page.locator("#ownerTrainBtn").is_enabled()
                and page.locator("#ownerCreateBtn").is_disabled() and page.locator("#ownerPhotosBtn").is_enabled()
                and len(page.locator("#ownerCard button.primary").all()) == 4)
        finding("everything else sits under More, closed", page.locator("#ownerMore").get_attribute("open") is None
                and page.locator("#ownerMore button").count() == 5 and not page.locator("#ownerDelete").is_visible())
        page.click("#ownerTrainBtn")
        page.wait_for_selector("#ownerUnlockPass", timeout=10000)
        finding("Train asks for the passphrase first, and starts nothing before it", state["jobs"] == [])
        page.fill("#ownerUnlockPass", "not the passphrase")
        page.click("#ownerUnlock")
        page.wait_for_function("() => document.querySelector('#ownerSay').innerText.includes('not right')", timeout=10000)
        finding("a wrong passphrase starts nothing", state["jobs"] == [] and state["unlocked"] is False)
        page.fill("#ownerUnlockPass", "a stand-in passphrase")
        page.click("#ownerUnlock")
        page.wait_for_function("() => (document.querySelector('#ownerTrainBtn') || {}).innerText === '2 Train ✓'", timeout=30000)
        kinds = [(j["kind"], j.get("area")) for j in state["jobs"]]
        finding("one press of Train runs the trainer's own test, then the training, both in the everyday section",
                kinds == [("owner_train_selftest", "default"), ("owner_train", "default")] and state["jobs"][1]["params"].get("base") == "fast", kinds)
        finding("after the training, Create can be pressed", page.locator("#ownerCreateBtn").is_enabled())
        page.click("#ownerCreateBtn")
        page.fill("#ownerText", "standing on a pier at sunset")
        page.click("#ownerPicture")
        page.wait_for_selector("#ownerGallery img", timeout=30000)
        last = state["jobs"][-1]
        finding("Create sends one likeness picture job with the words typed, and shows the result from the private gallery",
                last["kind"] == "owner_picture" and last["params"] == {"text": "standing on a pier at sunset", "base": "fast"}
                and page.locator("#ownerGallery img").count() == 1 and "private gallery" in page.locator("#ownerSay").inner_text(), last)
        shot(page, "desktop_likeness")
    finally:
        page.unroute("**/api/owner/**", owner_routes)
        page.unroute("**/api/jobs**", job_routes)
        page.evaluate("() => api('/api/phase_two', { method: 'POST', body: { hidden: true } })")


def pairwise_jobs(world, cat):
    """Real jobs for the all-pairs rows. The matrix itself is written for the report."""
    dna = {"gender": "woman", "age": 28, "style": "photo", "name": "Pair", "traits": {"hair_color": "red"}}
    base = world.api.job("create", {"dna": dna, "count": 2, "speed": "fast"})
    if base["status"] != "done" or len(base.get("results") or []) < 2:
        finding("pairwise has two pictures", False, base.get("error"))
        return
    a, b = base["results"][0]["id"], base["results"][1]["id"]
    qc = {"use": a, "variants": [
        {"image": a, "scores": {"hands": 8, "anatomy": 8, "contact": 8, "skin": 7, "lighting": 7}},
        {"image": b, "scores": {"hands": 7, "anatomy": 7, "contact": 7, "skin": 6, "lighting": 6}},
    ]}
    screens = {}
    screens["create"] = [("style", [s["id"] for s in cat["styles"]]),
                          ("gender", [g["id"] for g in cat["genders"]]),
                          ("count", [1, 2, 4]),
                          ("aspect", ["portrait", "square", "wide"]),
                          ("speed", ["best", "fast"])]
    colors = [c["id"] for c in cat["colors"]]
    materials = [c["id"] for c in cat["materials"]]
    screens["wardrobe"] = [("color", colors), ("material", materials), ("count", [1, 2, 4])]
    screens["scene"] = [("scene", [s["id"] for s in cat["scenes"]]), ("lighting", [x["id"] for x in cat["lighting"]])]
    screens["objects"] = [("object", [o["id"] for o in cat["objects"]]), ("placement", [p["id"] for p in cat["placements"]])]
    screens["pose"] = [("pose", [p["id"] for p in cat["poses"]]), ("mode", ["repose"])]
    screens["video"] = [("motion", [m["id"] for m in cat["motions"]]), ("seconds", cat["clip_lengths"]),
                        ("mode", ["fast", "best"]), ("quality", ["480", "720"]), ("framing", ["front", "rear", "profile"])]
    screens["3d"] = [("quality", ["game", "standard", "max"])]
    ok_n = fail_n = 0
    for screen, factors in screens.items():
        rows = all_pairs(factors)
        failed_here = 0
        for row in rows:
            if screen == "create":
                params = {"dna": {**dna, "style": row["style"], "gender": row["gender"], "age": 21 if row["count"] == 1 else 70},
                          "count": row["count"], "aspect": row["aspect"], "speed": row["speed"]}
                job = world.api.job("create", params)
            elif screen == "wardrobe":
                job = world.api.job("edit", {"image": a, "op": "outfit", "item": "jeans_tee", **row})
            elif screen == "scene":
                job = world.api.job("edit", {"image": a, "op": "scene", **row})
            elif screen == "objects":
                job = world.api.job("edit", {"image": a, "op": "object", **row})
            elif screen == "pose":
                job = world.api.job("edit", {"image": a, "op": "pose", "pose": row["pose"]})
            elif screen == "video":
                job = world.api.job("video", {"image": a, "photoreal": True, "qc": qc, **row})
            else:
                job = world.api.job("model3d", {"image": a, "quality": row["quality"]})
            if job["status"] == "done" and job.get("results"):
                ok_n += 1
            else:
                fail_n += 1
                failed_here += 1
                if fail_n <= 6:
                    finding(f"pairwise {screen} {row}", False, job.get("error") or job.get("status"))
        finding(f"pairwise {screen}: {len(rows)} rows, Cartesian would be {cartesian_size(factors)}", failed_here == 0, f"{failed_here} failed")
    finding("pairwise jobs finished", fail_n == 0, f"{ok_n} passed, {fail_n} failed")


def write_pairwise(api, cat):
    """Write the matrix the report points at. Jobs were already run in pairwise_jobs."""
    lines = ["# Pairwise matrix", "",
             "A full Cartesian product is not feasible. Create's chips alone are billions of combinations.",
             "Each table is an all-pairs covering: every value of every control appears with every value of every other control in at least one row.",
             "The browser suite runs these rows as real jobs on the fake ComfyUI.", ""]
    blocks = {
        "Create": [("style", [s["id"] for s in cat["styles"]]), ("gender", [g["id"] for g in cat["genders"]]),
                   ("count", [1, 2, 4]), ("aspect", ["portrait", "square", "wide"]), ("speed", ["best", "fast"])],
        "Wardrobe": [("color", [c["id"] for c in cat["colors"]]), ("material", [c["id"] for c in cat["materials"]]), ("count", [1, 2, 4])],
        "Scene": [("scene", [s["id"] for s in cat["scenes"]]), ("lighting", [x["id"] for x in cat["lighting"]])],
        "Objects": [("object", [o["id"] for o in cat["objects"]]), ("placement", [p["id"] for p in cat["placements"]])],
        "Video": [("motion", [m["id"] for m in cat["motions"]]), ("seconds", cat["clip_lengths"]),
                  ("mode", ["fast", "best"]), ("quality", ["480", "720"]), ("framing", ["front", "rear", "profile"])],
        "3D": [("quality", ["game", "standard", "max"])],
    }
    for title, factors in blocks.items():
        rows = all_pairs(factors)
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"Cartesian size: {cartesian_size(factors)}. All-pairs rows: {len(rows)}.")
        lines.append("")
        headers = [n for n, _ in factors]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
        lines.append("")
    path = os.path.join(ROOT, "docs", "E2E_PAIRWISE.md")
    open(path, "w").write("\n".join(lines))
    finding("pairwise matrix written", os.path.exists(path))


def mobile(page, world):
    finding("mobile home shows the three doors", page.locator("#door-make").is_visible() and page.locator("#door-library").is_visible())
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 8")
    finding("mobile home does not spill sideways", not overflow)
    finding("mobile home shows the video entries first", page.locator("#tool-video-build").is_visible() and page.locator("#tool-create").is_visible())
    shot(page, "mobile_home")
    go(page, "create")
    note = page.locator(".adult-note")
    finding("mobile still shows fictional-adults note", note.is_visible())
    box = note.bounding_box()
    finding("mobile note is on screen", box and box["width"] > 20, box)
    finding("mobile nav is on screen", page.locator("#nav").is_visible())
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 8")
    finding("mobile page does not spill sideways", not overflow)
    shot(page, "mobile_create")
    go(page, "video")
    shot(page, "mobile_video")


def recipe_path(browser, world):
    """The one Playwright path the Session Box asks for, in light mode: Make home -> portrait still recipe
    -> a film on it -> send to the island -> island import dry-run. Presses are counted from Recipes; a
    typed age or seed counts as a press, typed names do not. The node drawer stays closed."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.add_init_script("try { localStorage.setItem('es.theme', JSON.stringify('light')); } catch (e) {}")
    page.goto(world.base + "/", wait_until="domcontentloaded")
    page.wait_for_selector("#door-make", timeout=15000)
    finding("recipe path runs in light mode", page.evaluate("() => document.documentElement.dataset.theme") == "light")
    page.locator("#door-make").click()
    page.wait_for_selector(".recipe-card[data-recipe='portrait_still']", timeout=10000)
    shot(page, "recipe_make_light")
    presses = 0

    def press(locator):
        nonlocal presses
        presses += 1
        locator.click()

    press(page.locator(".recipe-card[data-recipe='portrait_still']"))
    page.wait_for_selector("[data-stage='subject']", timeout=10000)
    press(page.locator("[data-stage='subject'] .chip", has_text="Woman"))
    page.locator("#recipeAge").fill("32")
    presses += 1  # a typed age counts as a press
    press(page.locator("[data-stage='look'] .chip", has_text="Jeans"))
    t0 = time.time()
    press(page.locator("#recipeMake"))
    page.wait_for_selector("#recipeResults .grid img", timeout=90000)
    still_seconds = round(time.time() - t0, 2)
    finding("portrait still of a new fictional adult with a typed age in 5 presses or fewer", presses <= 5, presses)
    finding("the node drawer stayed closed", page.locator("#nodeDrawer").is_hidden())
    finding("the seed used is shown", "Seed used:" in page.inner_text("[data-stage='output']"))
    shot(page, "recipe_portrait_light")
    presses = 0
    press(page.locator("#sendToFilm"))
    page.wait_for_selector("[data-stage='subject'] .still-pick.on", timeout=10000)
    press(page.locator("[data-stage='output'] .chip", has_text="2 seconds"))
    press(page.locator("#recipeMake"))
    page.wait_for_selector("#recipeResults .grid video, #recipeResults .grid img", timeout=120000)
    finding("a film on that still in 5 presses or fewer", presses <= 5, presses)
    finding("the film page shows a shot strip", page.locator(".shot-strip").count() >= 1)
    shot(page, "recipe_film_light")
    page.evaluate("() => go('make')")
    page.wait_for_selector(".recipe-card[data-recipe='send_to_island']", timeout=10000)
    page.locator(".recipe-card[data-recipe='send_to_island']").click()
    page.wait_for_selector("[data-stage='subject'] .chip", timeout=10000)
    page.locator("[data-stage='subject'] .chip").first.click()
    page.locator("#recipeMake").click()
    page.wait_for_selector("#islandDryRun", timeout=120000)
    page.locator("#islandDryRun").click()
    page.wait_for_function("() => (document.querySelector('#islandCheck') || {}).innerText && document.querySelector('#islandCheck').innerText.length > 20", timeout=30000)
    check_text = page.inner_text("#islandCheck")
    finding("the island import dry-run accepts the pack and copies nothing",
            "Nothing was copied" in check_text and "project.godot is unchanged" in check_text, check_text)
    shot(page, "recipe_island_dry_run_light")
    finding("the recipe path has no JavaScript errors", not errs, errs[:3])
    print(f"  (mock portrait still in the browser: {still_seconds}s from Make it to the picture)")
    page.close()


if __name__ == "__main__":
    import tmp_hygiene
    tmp_hygiene.run(main)
