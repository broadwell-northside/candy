"""Open every tab of Easy Studio in a real (headless) Chrome, click the main controls, check for
JavaScript errors and save screenshots to docs/screenshots/. Needs: pip install playwright.

    python tests/ui_smoke.py            # starts the fake ComfyUI + the app by itself
"""
import json
import re
import os
import subprocess
import sys
import tempfile
import time

import shutil

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from run_tests import App, free_port  # noqa: E402

SHOTS = os.path.join(ROOT, "docs", "screenshots")
TABS = ["home", "make", "play", "library", "create", "workshop", "characters", "wardrobe", "pose", "scene", "objects", "photoshoot", "video", "3d", "assets", "studio", "loras", "lora-workshop", "train", "gallery", "advanced", "setup"]


def seed_demo(a):
    dna = {"gender": "woman", "age": 28, "style": "photo", "name": "Ruby",
           "traits": {"hair_color": "red", "hair_style": "long_wavy", "body": "curvy", "eyes": "green"}}
    j = a.job("create", {"dna": dna, "count": 4, "outfit": "lace_set", "scene": "bedroom"})
    hero = j["results"][0]
    import shot_qc
    qc = shot_qc.passing_qc(hero["id"], j["results"][1]["id"])
    ch = a.post("/api/characters", json={**dna, "hero": hero["id"], "notes": "Main love interest, chapter 1"}).json()
    dna2 = {"gender": "woman", "age": 31, "style": "anime", "name": "Kira", "traits": {"hair_color": "silver", "fantasy": ["elf_ears"]}}
    j2 = a.job("create", {"dna": dna2, "count": 1})
    a.post("/api/characters", json={**dna2, "hero": j2["results"][0]["id"]})
    a.job("edit", {"image": hero["id"], "op": "outfit", "item": "cocktail", "color": "black"})
    v = a.job("video", {"image": hero["id"], "motion": "wind", "seconds": 2, "qc": qc})["results"][0]
    a.job("model3d", {"image": hero["id"], "quality": "game"})
    a.job("photoshoot", {"character": ch["id"], "pack": "game_portraits"})
    return hero, v, ch


def main():
    from playwright.sync_api import sync_playwright
    out = tempfile.mkdtemp(prefix="es_ui_")
    mp, ap = free_port(), free_port()
    py = sys.executable
    # same fake ComfyUI folder / age checker / trainer as run_tests.py, plus two demo LoRAs with thumbnails
    from v3_tests import fake_lora
    comfy_dir = tempfile.mkdtemp(prefix="es_ui_comfy_")
    ldir = os.path.join(comfy_dir, "models", "loras")
    os.makedirs(ldir)
    agedir = os.path.join(comfy_dir, "models", "easy_studio", "age_check")
    os.makedirs(os.path.join(agedir, "torch", "hub", "checkpoints"))
    for n in ("model.safetensors", "config.json", "preprocessor_config.json", os.path.join("torch", "hub", "checkpoints", "yunet_final.pth")):
        open(os.path.join(agedir, n), "w").write("{}")
    fake_lora(os.path.join(ldir, "film_grain_look.safetensors"), ["lora_unet_input_blocks_4_1_proj_in.lora_down.weight", "lora_unet_input_blocks_4_1_proj_in.lora_up.weight"],
              {"ss_tag_frequency": '{"img": {"filmgrain": 20, "35mm": 12}}', "ss_base_model_version": "sdxl_base_v1-0"})
    fake_lora(os.path.join(ldir, "soft_light_chroma.safetensors"), ["diffusion_model.double_blocks.0.img_attn.qkv.lora_A.weight", "diffusion_model.double_blocks.0.img_attn.qkv.lora_B.weight"], {})
    try:
        from PIL import Image
        Image.new("RGB", (256, 256), (180, 120, 90)).save(os.path.join(ldir, "film_grain_look.preview.png"))
    except Exception:
        pass
    tdir = tempfile.mkdtemp(prefix="es_ui_trainer_")
    shutil.copy(os.path.join(HERE, "fake_trainer_run.py"), os.path.join(tdir, "run.py"))
    mock = subprocess.Popen([py, os.path.join(HERE, "mock_comfy.py"), str(mp)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                            env=dict(os.environ, MOCK_LORA_DIR=ldir))
    env = dict(os.environ, EASY_STUDIO_OUTPUTS=out, COMFY_URL=f"http://127.0.0.1:{mp}", EASY_STUDIO_PORT=str(ap),
               COMFY_DIR=comfy_dir, COMFY_PYTHON=py, EASY_STUDIO_TEST_RUN="1", EASY_STUDIO_AGE_WORKER=os.path.join(HERE, "fake_age_worker.py"),
               EASY_STUDIO_TRAINER_DIR=tdir, EASY_STUDIO_TRAINER_PYTHON=py, EASY_STUDIO_LORA_OFFLINE="1")
    srv = subprocess.Popen([py, os.path.join(ROOT, "app", "server.py")], env=env, stdout=open(out + "/server.log", "w"), stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{ap}"
    errors, fails = [], []
    try:
        for _ in range(80):
            try:
                requests.get(base + "/api/status", timeout=2)
                break
            except Exception:
                time.sleep(.25)
        a = App(base)
        hero, vid, ch = seed_demo(a)
        os.makedirs(SHOTS, exist_ok=True)
        with sync_playwright() as p:
            exe = os.environ.get("CHROME", "/usr/bin/google-chrome")
            b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None)
            for label, vp in (("desktop", {"width": 1440, "height": 1000}), ("phone", {"width": 390, "height": 844})):
                pg = b.new_page(viewport=vp)
                pg.on("pageerror", lambda e: errors.append(f"{label}: {e}"))
                pg.on("console", lambda m: m.type == "error" and errors.append(f"{label} console: {m.text}"))
                pg.goto(base + "/")
                pg.evaluate(f"localStorage.setItem('es.current', JSON.stringify('{hero['id']}')); localStorage.setItem('es.currentVideo', JSON.stringify('{vid['id']}'))")
                pg.reload()
                pg.wait_for_selector("#door-make", timeout=15000)  # first screen: Make · Play · Library
                pg.evaluate("go('create')")  # Classic tools keep their sidebar
                pg.wait_for_selector("#nav button", timeout=15000)
                for t in TABS if label == "desktop" else ["create", "wardrobe", "gallery"]:
                    pg.evaluate(f"go('{t}')")
                    pg.wait_for_timeout(900)
                    txt = pg.inner_text("#main")
                    if len(txt.strip()) < 30:
                        fails.append(f"{label}/{t}: page looks empty")
                    if re.search(r"\b(null|undefined|NaN)\b", txt):
                        fails.append(f"{label}/{t}: page shows 'null'/'undefined'/'NaN'")
                    pg.screenshot(path=os.path.join(SHOTS, f"{label}_{t}.png"), full_page=(label == "desktop"))
                if label == "desktop":
                    # click-through: run a real job from the UI
                    pg.evaluate("go('create')")
                    pg.wait_for_timeout(600)
                    age = pg.locator("#main input.stated-age")
                    if age.count():
                        age.fill("28")
                        age.dispatch_event("input")
                    btn = pg.locator("button.btn.primary", has_text="Create").first
                    btn.click()
                    pg.wait_for_selector(".results .grid img", timeout=30000, state="attached")
                    pg.wait_for_timeout(1500)
                    pg.screenshot(path=os.path.join(SHOTS, "desktop_create_results.png"), full_page=True)
                    pg.evaluate("go('3d')")
                    pg.wait_for_timeout(800)
                    pg.locator("#propMake").click()
                    pg.wait_for_selector("model-viewer", timeout=30000)
                    pg.wait_for_timeout(2500)
                    pg.screenshot(path=os.path.join(SHOTS, "desktop_3d_result.png"))
                    pg.evaluate("go('gallery')")
                    pg.wait_for_timeout(900)
                    cards = pg.locator("#main .grid img")
                    if cards.count():
                        cards.first.click()
                        pg.wait_for_timeout(700)
                        pg.screenshot(path=os.path.join(SHOTS, "desktop_lightbox.png"))
                        pg.keyboard.press("Escape")
                    # Video studio: pick the A-to-B mode on the first model card
                    pg.evaluate("go('studio')")
                    pg.wait_for_timeout(900)
                    cards = pg.locator(".mcard")
                    if cards.count() < 6:
                        fails.append(f"video studio shows only {cards.count()} model cards")
                    # Train: make training pictures for the saved character
                    pg.evaluate("go('train')")
                    pg.wait_for_timeout(900)
                    mk = pg.locator("button.btn.primary", has_text="Make training pictures")
                    if mk.count():
                        mk.first.click()
                        try:
                            pg.wait_for_function("/[1-9][0-9]* picked/.test(document.querySelector('#main').innerText)", timeout=120000)
                        except Exception:
                            fails.append("train: no training pictures appeared")
                        pg.wait_for_timeout(1500)
                        pg.screenshot(path=os.path.join(SHOTS, "desktop_train_dataset.png"), full_page=True)
                    else:
                        fails.append("train: no 'Make training pictures' button")
                    # 18+ gate: open it, tick both boxes, enter
                    pg.evaluate("go('create')")
                    pg.wait_for_timeout(500)
                    pg.click("#adultBtn")
                    pg.wait_for_timeout(700)
                    pg.screenshot(path=os.path.join(SHOTS, "desktop_adult_gate.png"))
                    if pg.inner_text("#main").count("null") or pg.inner_text("#modal").count("null"):
                        fails.append("a page shows the word 'null'")
                    for cb in pg.locator(".modal input[type=checkbox], dialog input[type=checkbox], .overlay input[type=checkbox]").all():
                        cb.check()
                    pg.locator("button.btn.primary", has_text="Open 21+").first.click()
                    pg.wait_for_timeout(1200)
                    if not pg.locator("#adultBar:not(.hidden)").count():
                        fails.append("18+: bar not shown after entering")
                    for t in ("create", "photoshoot", "gallery"):
                        pg.evaluate(f"go('{t}')")
                        pg.wait_for_timeout(900)
                        pg.screenshot(path=os.path.join(SHOTS, f"desktop_adult_{t}.png"), full_page=True)
                pg.close()
            b.close()
    finally:
        srv.terminate()
        mock.terminate()
        print("server log:", out + "/server.log")
    print(json.dumps({"js_errors": errors, "problems": fails, "screenshots": sorted(os.listdir(SHOTS))}, indent=1))
    sys.exit(1 if errors or fails else 0)


if __name__ == "__main__":
    import tmp_hygiene
    tmp_hygiene.run(main)
