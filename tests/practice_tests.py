"""Practice mode for the likeness (#/practice, app/static/practice.js): static checks run from run_tests.py (unit), and a
browser walk (python tests/practice_tests.py) that goes through every practice step and counts the requests the page
sends. The hard requirement: a full practice walk sends no POST, PUT, PATCH or DELETE, asks nothing of the likeness
routes, stores no photo and leaves no folder in outputs/owner. The camera is Chromium's built-in fake camera and the
photos are tiny pictures this test draws; no real camera, no real photo, no model."""
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))

JS = os.path.join(ROOT, "app", "static", "practice.js")
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
# Words that would mean the practice page can reach the server or keep something.
NO_REACH = ["api(", "fetch(", "FormData", "sendBeacon", "XMLHttpRequest", "WebSocket", "EventSource", "<form",
            "localStorage", "sessionStorage", "indexedDB", "store.set", "toBlob", "toDataURL", "/api/"]


def unit(check):
    print("\n[practice] static checks")
    src = open(JS, encoding="utf-8").read()
    html = open(os.path.join(ROOT, "app", "static", "index.html"), encoding="utf-8").read()
    check("practice file is included once, after the other screens", html.count("/static/practice.js") == 1
          and html.index("/static/practice.js") > html.index("/static/owner_photos.js"))
    found = [w for w in NO_REACH if w in src]
    check("the practice page has no way to reach the server or keep anything (no api/fetch/form/storage/file making)", not found, found)
    check("the page is registered and reachable by address", "VIEWS.practice" in src and 'DOORS.push("practice")' in src)
    check("every practice screen is drawn through the one frame with the PRACTICE banner",
          "banner()," in src and src.count("PRACTICE — nothing is saved") == 1 and src.count('h2", {}, "') >= 5)
    check("the photo drop words are the real Add photos step's words",
          all(w in src for w in ("no single clear face was found in it", "more than one face is in it",
                                 "that photo doesn't show the enrolled person", "the age check flagged it, which is final")))
    check("the training steps name the real ones: age check again, copy, caption, train, save",
          all(w in src for w in ("Age check again", "Copy the pictures", "Caption each picture", "Train the LoRA", "Save the LoRA")))
    check("the result is labelled Practice LoRA (not real), and the Create result is a drawn placeholder",
          "Practice LoRA (not real)" in src and "PRACTICE placeholder" in src and "createElementNS" in src)
    check("the stated age under 21 is refused in practice too", "21 or older" in src)

    print("\n[ux clean-up] static checks")
    static = os.path.join(ROOT, "app", "static")
    read = lambda n: open(os.path.join(static, n), encoding="utf-8").read()  # noqa: E731
    vp, models, make, app = read("video_pages.js"), read("models.js"), read("make.js"), read("app.js")
    check("Build and Extend ask the length the same way, and both hand-offs say 'Extend this clip'",
          vp.count('field("How long?"') == 2 and "How many seconds" not in vp and vp.count('"Extend this clip"') == 2)
    check("an empty LoRA list says where to add one", "add one on the LoRAs page" in vp)
    check("no message tells a Mac user to check 'the PC'", not any("the PC" in t for t in (app, make)))
    check("the home gear is labelled Setup, like the page it opens", '"⚙️ Setup"' in make)
    check("the Models card names the three to start with", all(w in models for w in ("Automatic age check", "Small video model (Wan 2.2 5B)", "Fast drafts + poses (Z-Image Turbo)")))


# ------------------------------------------------------------------ browser walk
def png(color):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(b, "PNG")
    return b.getvalue()


def browser():
    from playwright.sync_api import sync_playwright
    import requests
    from e2e_browser import World
    results, errors = [], []

    def finding(name, ok, detail=""):
        results.append(bool(ok))
        print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  -- {detail}"))

    folder = tempfile.mkdtemp(prefix="es_practice_photos_")
    files = []
    for name, data in (("beach.png", png((200, 160, 120))), ("pier.jpg", None), ("phone.heic", b"not really heic"), ("notes.txt", b"x")):
        path = os.path.join(folder, name)
        if data is None:
            from PIL import Image
            Image.new("RGB", (48, 48), (90, 120, 200)).save(path, "JPEG")
        else:
            open(path, "wb").write(data)
        files.append(path)

    world = World()
    try:
        base = world.base
        gallery_before = requests.get(base + "/api/gallery", timeout=10).json()
        jobs_before = requests.get(base + "/api/jobs", timeout=10).json()
        with sync_playwright() as p:
            args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            exe = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            try:
                b = p.chromium.launch(headless=True, args=args)
            except Exception:
                b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None, headless=True, args=args)
            ctx = b.new_context(viewport={"width": 1280, "height": 1000})
            ctx.grant_permissions(["camera"], origin=base)
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text and "favicon" not in m.text else None)
            shots = os.environ.get("E2E_ARTIFACTS", tempfile.gettempdir())
            os.makedirs(shots, exist_ok=True)

            def snap(name):
                page.screenshot(path=os.path.join(shots, "practice_" + name + ".png"), full_page=True)

            sent = []   # every request the page makes, from the first load on
            page.on("request", lambda r: sent.append((r.method, r.url)))

            def banner_ok(where):
                ok = page.locator("#practiceBanner").is_visible() and "PRACTICE" in page.inner_text("#practiceBanner") \
                    and "nothing is saved" in page.inner_text("#practiceBanner") and page.locator("#main .practice-tag").count() >= 1
                finding("PRACTICE banner and label on the " + where + " screen", ok)

            page.goto(base + "/", wait_until="domcontentloaded")
            page.wait_for_selector("#tool-practice", timeout=15000)
            finding("Home has a Practice my likeness tile", "Practice my likeness" in page.inner_text("#tool-practice"))
            page.evaluate("() => go('setup')")
            page.wait_for_selector("#practiceCard #practiceOpen", timeout=15000)
            finding("with phase two hidden, Setup still offers Practice my likeness (and no real likeness card)",
                    page.locator("#ownerCard").count() == 0 and page.locator("#phaseTwoSwitch").is_checked() is False)

            start = len(sent)
            page.click("#practiceOpen")
            page.wait_for_selector("#practiceGuide", timeout=10000)
            finding("the practice opens on 'Your likeness' with the four steps and a button into each",
                    all(page.locator("#practiceGo-" + s).is_visible() for s in ("enrol", "photos", "train", "create")))
            banner_ok("guide")

            # ---- Enrol
            page.click("#practiceStart")
            page.wait_for_selector("#practiceEnrol", timeout=5000)
            banner_ok("Enrol")
            page.fill("#practiceAge", "19")
            page.click("#practiceCamStart")
            finding("a stated age under 21 is refused in practice, and the camera does not start",
                    "21 or older" in page.inner_text("#practiceSay") and page.locator("#practiceTake").is_disabled())
            page.fill("#practiceAge", "40")
            page.click("#practiceCamStart")
            page.wait_for_function("() => { const v = document.querySelector('#practiceVideo'); return v && v.videoWidth > 0; }", timeout=15000)
            finding("the camera starts and the first pose is asked in the real words", "Look straight at the camera." in page.inner_text("#practiceSay"))
            for _ in range(5):
                page.wait_for_timeout(150)
                page.click("#practiceTake")
            page.wait_for_selector("#practiceEnrolDone", state="visible", timeout=5000)
            snap("enrol")
            finding("five poses, five pictures kept in the page only, the stand-in check says simulated",
                    page.locator("#practiceShots canvas").count() == 5 and "simulated" in page.inner_text("#practiceSay"))
            finding("the camera is stopped after the last pose",
                    page.evaluate("() => { const v = document.querySelector('#practiceVideo'); return !v.srcObject || v.srcObject.getTracks().every(t => t.readyState === 'ended'); }"))

            # ---- Add photos
            page.click("#practiceToPhotos")
            page.wait_for_selector("#practicePhotos", timeout=5000)
            banner_ok("Add photos")
            page.set_input_files("#practicePhotoFiles", files)
            page.click("#practicePhotosCheck")
            page.wait_for_selector("#practicePhotoList .practice-row", timeout=5000)
            srcs = page.eval_on_selector_all("#practicePhotoList img", "els => els.map(e => e.src)")
            finding("each JPEG/PNG gets a thumbnail made by this browser (blob:), not a server address",
                    len(srcs) == 2 and all(s.startswith("blob:") for s in srcs), srcs)
            listing = page.inner_text("#practicePhotoList")
            finding("each photo shows the three checks as simulated", listing.count("One face: simulated pass") == 2
                    and "Matches your enrolment" in listing and "Age check" in listing)
            finding("a HEIC photo is 'not read' with the real advice, and a text file is left alone",
                    "phone.heic" in listing and "Export it as JPEG" in listing and "notes.txt" not in listing
                    and "1 other file was left alone" in page.inner_text("#practicePhotosSay"))
            page.select_option("#practicePhotoList .practice-outcome >> nth=0", "two_faces")
            snap("add_photos")
            finding("picking a drop shows the real message, and the check it fails says so",
                    "Would be dropped: more than one face is in it" in page.inner_text("#practicePhotoList")
                    and "One face: simulated fail · Matches your enrolment: not reached" in page.inner_text("#practicePhotoList .practice-row >> nth=0"))
            finding("the totals say what would be kept and that nothing was sent or saved",
                    page.inner_text("#practicePhotosTotals") == "1 would be kept, 1 dropped, 1 not read. Nothing was sent or saved.",
                    page.inner_text("#practicePhotosTotals"))

            # ---- Train
            page.click("#practiceToTrain")
            page.wait_for_selector("#practiceTrain", timeout=5000)
            banner_ok("Train")
            finding("Train counts the practice pictures (12 from enrolment, 1 kept photo)", "13 (12 from enrolment, 1 kept photo)" in page.inner_text("#practiceTrainPictures"),
                    page.inner_text("#practiceTrainPictures"))
            finding("practice training is about 30 seconds by default", "about 30 seconds" in page.inner_text("#practiceTrainSay"))
            page.evaluate("() => { PRACTICE.trainSeconds = 2; }")
            page.click("#practiceTrainStart")
            page.wait_for_function("() => document.querySelector('#practiceTrainSay').innerText.includes('Step')", timeout=5000)
            finding("the run names the real steps as it goes", "(simulated)" in page.inner_text("#practiceTrainSay"))
            page.wait_for_selector("#practiceLora", timeout=10000)
            lora = page.inner_text("#practiceLora")
            snap("train")
            finding("it ends in a 'Practice LoRA (not real)' card that says no file was written",
                    "Practice LoRA (not real)" in lora and "No file was written" in lora and "mylikeness" in lora, lora)

            # ---- Create
            page.click("#practiceToCreate")
            page.wait_for_selector("#practiceCreate", timeout=5000)
            banner_ok("Create")
            page.click("#practiceMake")
            finding("Create with no words says so", "Type a few words" in page.inner_text("#practiceCreateSay"))
            page.fill("#practiceText", "standing on a pier at sunset")
            page.press("#practiceText", "Enter")
            page.wait_for_selector("#practicePlaceholder", timeout=5000)
            finding("the result is a drawn placeholder labelled PRACTICE, not a photo",
                    "PRACTICE" in page.inner_text("#practiceResult") and page.locator("#practiceResult img").count() == 0)
            need = page.inner_text("#practiceCreate")
            finding("Create explains what the real one needs: the models, the trainer, the enrolment",
                    "Setup → Models" in need and "trainer" in need and "enrolment" in need)
            snap("create")
            page.emulate_media(color_scheme="dark")
            page.evaluate("() => { document.documentElement.dataset.theme = 'dark'; }")
            snap("create_dark")
            colors = page.evaluate("() => { const s = getComputedStyle(document.querySelector('#practiceBanner')); return [s.color, s.backgroundColor]; }")
            finding("the PRACTICE banner keeps dark text on its light colour in the dark theme", colors[0] != colors[1] and colors[0].startswith("rgb(8,"), colors)
            page.evaluate("() => { delete document.documentElement.dataset.theme; }")
            page.emulate_media(color_scheme="light")

            # ---- Leave, by the page's own Home button
            page.click("#practiceHome")
            page.wait_for_selector("#tool-practice", timeout=10000)
            walk = sent[start:]
            writes = [(m, u) for m, u in sent if m in WRITES]
            finding("ZERO POST/PUT/PATCH/DELETE requests during the whole visit, from the first load through the practice walk", not writes, writes)
            own = [u for m, u in walk if u.startswith(base) and re.sub(r"\?.*", "", u[len(base):]) not in ("/api/status", "/api/jobs") and "/static/" not in u]
            finding("during the practice walk the page asked the server for nothing of its own (only the app's status and jobs polling)", not own, own[:5])
            finding("no request to the likeness routes at any point", not [u for _, u in sent if "/api/owner" in u])

            # A positive control: the counter does see a write when one is sent.
            page.evaluate("() => fetch('/api/practice-control-not-a-route', { method: 'POST', headers: { 'X-Easy-Studio': '1' } }).catch(() => null)")
            page.wait_for_timeout(300)
            finding("control: one deliberate POST is counted (so the zero above is real)", len([1 for m, _ in sent if m in WRITES]) == 1)

            # The entry on the real My likeness card, with phase two shown by a stand-in answer (no switch is pressed).
            def phase_shown(route, request):
                if request.method != "GET":
                    return route.continue_()
                route.fulfill(status=200, content_type="application/json", body='{"hidden": false}')
            page.route("**/api/phase_two", phase_shown)
            page.evaluate("() => go('setup')")
            page.wait_for_selector("#ownerCard #practiceFromCard", timeout=15000)
            finding("with phase two shown, the My likeness card has a Practice my likeness button (not a fourth step)",
                    page.locator("#practiceCard").count() == 0 and page.locator("#ownerCard #ownerMore #practiceFromCard").count() == 0
                    and "btn small" in page.get_attribute("#practiceFromCard", "class"))
            page.click("#practiceFromCard")
            page.wait_for_selector("#practiceGuide", timeout=10000)
            page.unroute("**/api/phase_two", phase_shown)
            # The Start here guide (another lane's page, loaded here from its branch): it gets the practice section.
            guide = os.environ.get("PRACTICE_START_HERE_JS", "")   # a copy of start_here.js; absent until that page lands
            if guide and os.path.exists(guide):
                page.add_script_tag(content=open(guide, encoding="utf-8").read())
                page.evaluate("() => go('start-here')")
                page.wait_for_selector("#practiceGuideSection #practiceFromGuide", timeout=10000)
                finding("the Start here guide ends with 'Your likeness (practice)' and a button into the practice",
                        "Your likeness (practice)" in page.inner_text("#practiceGuideSection"))
                page.click("#practiceFromGuide")
                page.wait_for_selector("#practiceGuide", timeout=10000)
            else:
                print("  (Start here page not available here: its hook is not exercised)")
            finding("still ZERO POST/PUT/PATCH/DELETE after the two entry paths, apart from the one control",
                    len([1 for m, _ in sent if m in WRITES]) == 1)

            page.goto(base + "/#/practice", wait_until="domcontentloaded")
            page.wait_for_selector("#practiceGuide", timeout=15000)
            finding("the address #/practice opens the practice directly, with the banner", page.locator("#practiceBanner").is_visible())
            page.click("#practiceGo-enrol")
            page.fill("#practiceAge", "40")
            page.click("#practiceNoCam")
            for _ in range(5):
                page.click("#practiceTake")
            finding("without a camera the walk still goes on (drawn stand-in pictures)",
                    page.locator("#practiceEnrolDone").is_visible() and page.locator("#practiceShots canvas").count() == 5)
            b.close()
        finding("nothing in outputs/owner on the server", not os.path.exists(os.path.join(world.out, "owner")))
        finding("the gallery and the job list are unchanged on the server",
                requests.get(base + "/api/gallery", timeout=10).json() == gallery_before
                and len(requests.get(base + "/api/jobs", timeout=10).json()) == len(jobs_before))
        finding("no JavaScript errors", not errors, errors[:5])
    finally:
        world.close()
    print(f"\n{sum(results)}/{len(results)} practice browser checks passed")
    return all(results) and not errors


if __name__ == "__main__":
    import tmp_hygiene
    tmp_hygiene.run(lambda: sys.exit(0 if browser() else 1))
