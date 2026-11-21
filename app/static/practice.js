/* PRIVATE BUILD — NOT FOR DISTRIBUTION
   Practice mode for the owner's likeness (D-C-70): Enrol, Add photos, Train and Create, walked through in the browser
   before any model is on disk. Everything here stays in this page: no request to the server, no photo stored, no item,
   no likeness mark, nothing in outputs/owner. Photos picked from disk are shown as thumbnails made by this browser only.
   On purpose this file has no call to the app's server helper, no network call and no form: the browser test
   (tests/practice_tests.py) counts the requests a full practice walk makes and checks for those words here.
   Loaded last. Page: #/practice. Entries: Setup (on or beside the My likeness card), a Home tile, and the
   "Start here" guide when that page is in the app. */
"use strict";

const PRACTICE = {
  trainSeconds: 30,   // how long the practice training takes; the browser test shortens it
};

(function () {
  if (typeof DOORS !== "undefined" && !DOORS.includes("practice")) DOORS.push("practice");  // #/practice opens directly, calm layout

  // The same words the real enrolment uses for each pose (owner.js), one picture per pose here.
  const POSES = [
    ["face_camera", "Look straight at the camera."], ["turn_left", "Turn your head to the left."],
    ["turn_right", "Turn your head to the right."], ["tilt", "Tilt your head to one side."], ["look_up", "Look up."],
  ];
  // The same words the real Add photos step shows for a photo it does not keep (app/owner_photos.py).
  const DROPS = [
    ["kept", "Kept (all three checks pass)"],
    ["no_face", "no single clear face was found in it"],
    ["two_faces", "more than one face is in it"],
    ["no_match", "that photo doesn't show the enrolled person"],
    ["flagged", "the age check flagged it, which is final"],
  ];
  const READ = /\.(jpe?g|png)$/i;
  const OTHER_PICTURE = /\.(heic|heif|webp|tiff?|gif|bmp|avif)$/i;
  const TRIGGER = "mylikeness";
  const TRAIN_STEPS = [   // the real training job, in order (app/owner_train.py), with a share of the practice time
    ["Age check again on every training picture", 0.10],
    ["Copy the pictures into a private training folder", 0.10],
    ["Caption each picture with your trigger word", 0.10],
    ["Train the LoRA (the long part: hours on this Mac)", 0.60],
    ["Save the LoRA privately and delete the copies", 0.10],
  ];
  const STEPS = [["guide", "Start"], ["enrol", "1 Enrol"], ["photos", "2 Add photos"], ["train", "3 Train"], ["create", "4 Create"]];

  // Practice state lives in this variable only. A reload, or leaving the page, starts over.
  const fresh = () => ({ step: "guide", enrolled: false, frames: 0, photos: [], trained: false, lora: null });
  let P = fresh();
  let stream = null, timer = null;

  function stopCamera() { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; }
  function stopTimer() { if (timer) clearInterval(timer); timer = null; }
  function forgetPhotos() { for (const p of P.photos) if (p.url) URL.revokeObjectURL(p.url); }
  function leave() { stopCamera(); stopTimer(); forgetPhotos(); P = fresh(); }

  // Leaving the page (any other screen) stops the camera and forgets everything picked here.
  const nav0 = nav;
  nav = function () {
    if (S.tab !== "practice") leave();
    nav0();
  };

  const style = document.createElement("style");
  style.textContent = `
    .practice-banner{position:sticky;top:calc(var(--banner-h) + var(--top-h));z-index:5;margin:0 0 16px;padding:10px 16px;border-radius:var(--radius-control);
      background:var(--warn);color:var(--bg);font-weight:700;font-size:16px;letter-spacing:.02em}
    .practice-banner span{font-weight:400}
    .practice-steps{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}
    .practice-tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.06em;color:var(--warn);border:1px solid var(--warn);border-radius:99px;padding:2px 8px;vertical-align:middle;margin-left:8px}
    .practice-list{padding-left:1.4em}.practice-list li{margin:8px 0}
    .practice-shots{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
    .practice-shots canvas,.practice-row img{width:72px;height:72px;object-fit:cover;border-radius:8px;border:1px solid var(--line);background:var(--surface-2)}
    .practice-row{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-top:1px solid var(--line)}
    .practice-row .checks{font-size:14px;color:var(--muted);margin:4px 0}
    .practice-row .verdict{font-weight:600}.practice-row .verdict.bad{color:var(--bad)}.practice-row .verdict.good{color:var(--ok)}
    .practice-bar{height:12px;border-radius:99px;background:var(--surface-2);overflow:hidden;margin:12px 0}
    .practice-bar i{display:block;height:100%;width:0;background:var(--warn);transition:width .3s linear}
    .practice-train li{color:var(--muted)}.practice-train li.now{color:var(--text);font-weight:600}.practice-train li.done{color:var(--ok)}
    .practice-result{width:100%;max-width:300px;margin:12px 0}
    .practice-actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}
    #practiceVideo{max-width:320px;border-radius:var(--radius-control);display:block;margin:12px 0}`;
  document.head.append(style);

  const banner = () => h("div", { class: "practice-banner", id: "practiceBanner", role: "status" },
    "PRACTICE — nothing is saved. ", h("span", {}, "Nothing leaves this page: no photo is stored, nothing is sent, no likeness is made."));
  const tag = () => h("span", { class: "practice-tag" }, "PRACTICE");
  const next = (label, step, id) => h("button", { class: "btn", type: "button", id, onclick: () => show(step) }, label);
  const say = (id, text) => h("p", { class: "hint", id, "aria-live": "polite" }, text);

  // One frame for every practice screen: the banner, the steps, then the screen itself.
  let main = null;
  function show(step) {
    stopCamera(); stopTimer();
    if (P.step === "train" && step !== "train" && !P.trained) P.lora = null;
    P.step = step;
    const screen = SCREENS[step]();
    main.replaceChildren(
      h("button", { class: "btn small", type: "button", id: "practiceHome", onclick: () => go("home") }, "⌂ Home"),
      banner(),
      h("h1", {}, "Your likeness", tag()),
      h("div", { class: "practice-steps", role: "navigation", "aria-label": "Practice steps" }, STEPS.map(([id, label]) =>
        h("button", { class: "chip" + (id === step ? " on" : ""), type: "button", id: "practiceStep-" + id,
          "aria-current": id === step ? "step" : null, onclick: () => show(id) }, label))),
      screen);
    window.scrollTo(0, 0);
  }

  const SCREENS = {
    guide() {
      const row = (n, title, words, step) => h("li", {}, h("b", {}, title), h("div", {}, words),
        h("button", { class: "btn small", type: "button", id: "practiceGo-" + step, style: { marginTop: "8px" }, onclick: () => show(step) }, "Try " + title));
      return h("div", { class: "card", id: "practiceGuide" },
        h("h2", {}, "Practice the four steps", tag()),
        h("p", {}, "This is a walk-through of how the app makes your likeness. It works before any model is on this Mac. " +
          "Every check you see here is simulated, and nothing you do is kept."),
        h("ol", { class: "practice-list" },
          row(1, "Enrol", "About a minute at the camera: you turn, tilt and look up, one picture per pose. This ties the app to you, and only you.", "enrol"),
          row(2, "Add photos", "Pick photos of yourself from this Mac. A photo is kept only if it shows exactly one face, that face is yours, and the age check clears it.", "photos"),
          row(3, "Train", "The app learns your face from the kept pictures and makes a small file, a LoRA. For real this takes hours.", "train"),
          row(4, "Create", "Describe a picture of yourself. The app adds your trigger word and the result goes to your private gallery only.", "create")),
        h("h3", {}, "When you are ready for real"),
        h("p", {}, "The real steps need the models from Setup → Models, the trainer, and Setup → Phase two switched on to show the My likeness card. " +
          "Your photos never leave this Mac. Do not paste or upload them into any chat."),
        h("div", { class: "practice-actions" }, next("Start the practice", "enrol", "practiceStart")));
    },

    enrol() {
      const box = h("div", { class: "card", id: "practiceEnrol" }, h("h2", {}, "1 Enrol", tag()));
      const status = say("practiceSay", "");
      const video = h("video", { id: "practiceVideo", autoplay: true, playsinline: true, muted: true, style: { display: "none" } });
      const shots = h("div", { class: "practice-shots", id: "practiceShots" });
      const age = h("input", { id: "practiceAge", class: "stated-age", type: "text", inputmode: "numeric", placeholder: "Your stated age", autocomplete: "off" });
      const start = h("button", { class: "btn", type: "button", id: "practiceCamStart" }, "Start camera");
      const noCam = h("button", { class: "btn small", type: "button", id: "practiceNoCam" }, "Continue without the camera");
      const take = h("button", { class: "btn", type: "button", id: "practiceTake", disabled: true }, "Take picture");
      let at = 0, camera = false;

      const ask = () => { status.textContent = "Pose " + (at + 1) + " of " + POSES.length + ". " + POSES[at][1]; };
      const ageOkay = () => {
        const t = age.value.trim();
        if (!/^\d{1,3}$/.test(t)) { status.textContent = "Type your age as a whole number first, such as 40."; age.focus(); return false; }
        if (+t < 21) { status.textContent = "The stated age has to be 21 or older. (The real enrolment refuses it the same way.)"; return false; }
        return true;
      };
      const begin = () => { at = 0; P.frames = 0; P.enrolled = false; shots.replaceChildren(); start.disabled = true; noCam.disabled = true; age.disabled = true; take.disabled = false; ask(); };

      start.onclick = async () => {
        if (!ageOkay()) return;
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
        } catch (e) {
          status.textContent = "The camera did not start (" + (e.message || e.name) + "). You can continue without it.";
          return;
        }
        video.srcObject = stream; video.style.display = ""; camera = true;
        begin();
      };
      noCam.onclick = () => { if (!ageOkay()) return; camera = false; begin(); };

      take.onclick = () => {
        // The picture is drawn onto a small canvas in this page and nowhere else. It is never turned into a file.
        const c = h("canvas", { width: 72, height: 72, "aria-label": "Practice picture " + (at + 1) });
        const g = c.getContext("2d");
        let dark = false;
        if (camera && video.videoWidth) {
          const side = Math.min(video.videoWidth, video.videoHeight);
          g.drawImage(video, (video.videoWidth - side) / 2, (video.videoHeight - side) / 2, side, side, 0, 0, 72, 72);
          const px = g.getImageData(0, 0, 72, 72).data;
          let sum = 0;
          for (let i = 0; i < px.length; i += 4) sum += (px[i] + px[i + 1] + px[i + 2]) / 3;
          dark = sum / (px.length / 4) < 25;
        } else {
          g.fillStyle = "#C9D4D0"; g.fillRect(0, 0, 72, 72);
          g.fillStyle = "#5C6B70"; g.beginPath(); g.arc(36, 30, 14, 0, Math.PI * 2); g.fill(); g.fillRect(16, 50, 40, 22);
        }
        if (dark) { status.textContent = "Too dark to see a face. Turn on a light and take it again. " + POSES[at][1]; return; }
        shots.append(c);
        P.frames = at + 1;
        if (++at < POSES.length) { ask(); status.textContent = "Stand-in check (simulated): one face, the right pose. " + status.textContent; return; }
        stopCamera(); video.style.display = "none"; take.disabled = true;
        P.enrolled = true;
        status.textContent = "Practice enrolment finished: " + POSES.length + " pictures, every stand-in check passed (simulated).";
        done.style.display = "";
      };

      const done = h("div", { id: "practiceEnrolDone", style: { display: "none" } },
        h("p", {}, "For real, the app takes 12 pictures, keeps them in your private folder on this Mac, and asks for a passphrase that unlocks the likeness steps. " +
          "Here the pictures above stay in this page and disappear when you leave it."),
        h("div", { class: "practice-actions" }, next("Next: Add photos", "photos", "practiceToPhotos")));

      box.append(
        h("p", {}, "The app is about to make pictures of a real person, so it checks once that the photos are of the person using it. " +
          "The real live check asks you to turn, tilt and look up in front of the camera. It does not detect a recording of you."),
        h("p", { class: "hint" }, "In practice the camera picture stays on this screen. Nothing is sent, and the face check is a stand-in that always passes unless the picture is too dark."),
        h("label", { class: "f", for: "practiceAge" }, "Stated age"), age,
        h("p", { class: "hint" }, "The real enrolment also asks for a passphrase here. Practice skips it."),
        h("div", { class: "practice-actions" }, start, take, noCam),
        video, status, shots, done);
      if (P.enrolled) { status.textContent = "You finished the practice enrolment. You can do it again, or go on."; done.style.display = ""; }
      return box;
    },

    photos() {
      const box = h("div", { class: "card", id: "practicePhotos" }, h("h2", {}, "2 Add photos", tag()));
      const status = say("practicePhotosSay", P.enrolled ? "Choose a folder, or some photos, of yourself."
        : "For real, Add photos opens after Enrol. In practice you can try it now.");
      const list = h("div", { id: "practicePhotoList" });
      const folder = h("input", { id: "practicePhotoFolder", type: "file", webkitdirectory: true, multiple: true });
      const files = h("input", { id: "practicePhotoFiles", type: "file", accept: "image/*,.heic,.heif", multiple: true });
      const check = h("button", { class: "btn", type: "button", id: "practicePhotosCheck" }, "Check these photos");
      const clear = h("button", { class: "btn small", type: "button", id: "practicePhotosClear" }, "Clear the list");
      const totals = h("p", { id: "practicePhotosTotals" });

      const sum = () => {
        const kept = P.photos.filter(p => p.read && p.outcome === "kept").length;
        const dropped = P.photos.filter(p => p.read && p.outcome !== "kept").length;
        const unread = P.photos.filter(p => !p.read).length;
        totals.textContent = P.photos.length ? kept + " would be kept, " + dropped + " dropped" + (unread ? ", " + unread + " not read" : "") +
          ". Nothing was sent or saved." : "";
      };
      // The three checks in order; a picked drop fails the check it belongs to, and the later checks are not reached.
      const checksText = p => {
        const fails = { no_face: 0, two_faces: 0, no_match: 1, flagged: 2 }[p.outcome];
        return ["One face", "Matches your enrolment", "Age check"].map((name, i) =>
          name + ": " + (fails === undefined || i < fails ? "simulated pass" : i === fails ? "simulated fail" : "not reached")).join(" · ");
      };
      const verdictText = p => p.outcome === "kept" ? "Would be kept" : "Would be dropped: " + DROPS.find(d => d[0] === p.outcome)[1];
      const row = (p, i) => {
        if (!p.read) {
          return h("div", { class: "practice-row", "data-photo": i },
            h("div", {}, h("b", {}, p.name), h("div", { class: "verdict bad" }, "Not read: this app reads JPEG and PNG. Export it as JPEG first.")));
        }
        const verdict = h("div", { class: "verdict " + (p.outcome === "kept" ? "good" : "bad") }, verdictText(p));
        const checks = h("div", { class: "checks" }, checksText(p));
        const pick = h("select", { "aria-label": "Practice outcome for " + p.name, class: "practice-outcome", onchange: e => {
          p.outcome = e.target.value; verdict.textContent = verdictText(p); checks.textContent = checksText(p); verdict.className = "verdict " + (p.outcome === "kept" ? "good" : "bad"); sum();
        } }, DROPS.map(([v, label]) => h("option", { value: v, selected: v === p.outcome }, v === "kept" ? label : "Show a drop: " + label)));
        return h("div", { class: "practice-row", "data-photo": i },
          p.url ? h("img", { src: p.url, alt: "", loading: "lazy", decoding: "async" }) : h("div", { class: "hint", style: { width: "72px" } }, "(cleared)"),
          h("div", {}, h("b", {}, p.name),
            checks, verdict, pick));
      };
      const draw = () => { list.replaceChildren(...P.photos.map(row)); sum(); };

      check.onclick = () => {
        const chosen = [...Array.from(folder.files || []), ...Array.from(files.files || [])];
        if (!chosen.length) { status.textContent = "Choose a folder or some photos first."; return; }
        forgetPhotos();
        const pictures = chosen.filter(f => READ.test(f.name) || OTHER_PICTURE.test(f.name));
        const ignored = chosen.length - pictures.length;
        P.photos = pictures.slice(0, 300).map(f => ({
          name: f.webkitRelativePath || f.name, read: READ.test(f.name), outcome: "kept",
          url: READ.test(f.name) ? URL.createObjectURL(f) : null,   // a thumbnail made by this browser; the file is not sent anywhere
        }));
        folder.value = ""; files.value = "";
        draw();
        status.textContent = "Checked " + P.photos.length + " photo" + (P.photos.length === 1 ? "" : "s") + " in practice" +
          (pictures.length > 300 ? " (the real step takes up to 300)" : "") + (ignored ? ". " + ignored + " other file" + (ignored === 1 ? " was" : "s were") + " left alone" : "") +
          ". Use the menu on a photo to see what a drop looks like.";
      };
      clear.onclick = () => { forgetPhotos(); P.photos = []; draw(); status.textContent = "The list is empty. Nothing was kept anywhere."; };

      box.append(
        h("p", {}, "For real, the app keeps a photo only if it shows exactly one face, that face matches your enrolment, and the age check clears it. " +
          "Photos of your body count when your face is in them. Anything else is dropped, and the list says why."),
        h("p", { class: "hint" }, "In practice no check runs: every photo passes unless you pick a drop from its menu. The thumbnails are made by this browser and are gone when you leave."),
        h("label", { class: "f", for: "practicePhotoFolder" }, "A folder of photos"), folder,
        h("label", { class: "f", for: "practicePhotoFiles" }, "Or single photos"), files,
        h("div", { class: "practice-actions" }, check, clear),
        status, totals, list,
        h("div", { class: "practice-actions" }, next("Next: Train", "train", "practiceToTrain")));
      draw();
      return box;
    },

    train() {
      const box = h("div", { class: "card", id: "practiceTrain" }, h("h2", {}, "3 Train", tag()));
      const kept = P.photos.filter(p => p.read && p.outcome === "kept").length;
      const pictures = (P.enrolled ? 12 : 0) + kept;
      const status = say("practiceTrainSay", "Practice training takes about " + PRACTICE.trainSeconds + " seconds. The real one takes hours.");
      const bar = h("i");
      const steps = h("ol", { class: "practice-list practice-train", id: "practiceTrainSteps" }, TRAIN_STEPS.map(s => h("li", {}, s[0])));
      const go1 = h("button", { class: "btn", type: "button", id: "practiceTrainStart" }, P.trained ? "Train again" : "Start practice training");
      const stop = h("button", { class: "btn small", type: "button", id: "practiceTrainStop", disabled: true }, "Stop");
      const result = h("div", { id: "practiceTrainResult" });

      const loraCard = () => h("div", { class: "card", id: "practiceLora", style: { borderColor: "var(--warn)", marginTop: "16px" } },
        h("h2", {}, "Practice LoRA (not real)", tag()),
        h("p", {}, "Trigger word: ", h("b", {}, TRIGGER), " · base: fast · pictures: " + P.lora.pictures),
        h("p", { class: "hint" }, "No file was written. A real LoRA is a small file saved privately on this Mac, tied to your enrolment, and usable only for pictures of you."),
        h("div", { class: "practice-actions" }, next("Next: Create", "create", "practiceToCreate")));

      go1.onclick = () => {
        stopTimer();
        P.trained = false; P.lora = null; result.replaceChildren();
        go1.disabled = true; stop.disabled = false;
        const t0 = Date.now(), total = PRACTICE.trainSeconds * 1000;
        const items = steps.querySelectorAll("li");
        timer = setInterval(() => {
          const f = Math.min(1, (Date.now() - t0) / total);
          bar.style.width = Math.round(f * 100) + "%";
          let edge = 0, now = TRAIN_STEPS.length - 1;
          for (let i = 0; i < TRAIN_STEPS.length; i++) { if (f < edge + TRAIN_STEPS[i][1]) { now = i; break; } edge += TRAIN_STEPS[i][1]; }
          items.forEach((li, i) => { li.className = f >= 1 || i < now ? "done" : i === now ? "now" : ""; });
          status.textContent = f >= 1 ? "Practice training finished." : "Step " + (now + 1) + " of " + TRAIN_STEPS.length + ": " + TRAIN_STEPS[now][0] + " (simulated)";
          if (f >= 1) {
            stopTimer(); go1.disabled = false; go1.textContent = "Train again"; stop.disabled = true;
            P.trained = true; P.lora = { pictures };
            result.replaceChildren(loraCard());
          }
        }, 200);
      };
      stop.onclick = () => {
        stopTimer(); go1.disabled = false; stop.disabled = true; bar.style.width = "0";
        steps.querySelectorAll("li").forEach(li => { li.className = ""; });
        status.textContent = "Stopped. For real, stopping keeps nothing: the copies are deleted and no LoRA is written.";
      };

      box.append(
        h("p", {}, "For real, Train needs your enrolment, the trainer (Setup → Models), and your passphrase. It runs a short test of the trainer on drawn shapes first, " +
          "then trains in the everyday section. Leave the Mac plugged in."),
        h("p", { class: "hint", id: "practiceTrainPictures" }, "Pictures this practice run would use: " + pictures + " (" + (P.enrolled ? "12 from enrolment" : "no enrolment yet") +
          ", " + kept + " kept photo" + (kept === 1 ? "" : "s") + ")." + (pictures < 10 ? " For real, training needs at least 10 pictures." : "")),
        steps, h("div", { class: "practice-bar", role: "progressbar", "aria-label": "Practice training" }, bar), status,
        h("div", { class: "practice-actions" }, go1, stop), result);
      if (P.trained && P.lora) { bar.style.width = "100%"; steps.querySelectorAll("li").forEach(li => { li.className = "done"; }); result.append(loraCard()); }
      return box;
    },

    create() {
      const box = h("div", { class: "card", id: "practiceCreate" }, h("h2", {}, "4 Create", tag()));
      const text = h("input", { id: "practiceText", type: "text", placeholder: "Describe the picture of you, such as: standing on a pier at sunset, smiling",
        onkeydown: e => { if (e.key === "Enter") make.click(); } });
      const status = say("practiceCreateSay", P.trained ? "Describe the picture, then make the practice picture."
        : "For real, Create opens after Train. In practice you can try it now.");
      const result = h("div", { id: "practiceResult" });
      const make = h("button", { class: "btn", type: "button", id: "practiceMake", onclick: () => {
        const words = text.value.trim();
        if (!words) { status.textContent = "Type a few words first: where you are, what you wear, what light."; text.focus(); return; }
        result.replaceChildren(placeholder(words));
        status.textContent = "This is a placeholder, not a picture of you. Nothing was made or kept.";
      } }, "Make the practice picture");
      const link = (label, run) => h("a", { href: "#", onclick: e => { e.preventDefault(); run(); } }, label);
      box.append(
        h("p", {}, "For real, you describe the picture, the app adds your trigger word (" + TRIGGER + ") by itself, the age check looks at the result, " +
          "and the picture goes to your private gallery and nowhere else."),
        h("label", { class: "f", for: "practiceText" }, "A picture of me"), text,
        h("div", { class: "practice-actions" }, make), status, result,
        h("h3", {}, "What the real one needs"),
        h("ul", { class: "practice-list" },
          h("li", {}, "The models: ", link("Setup → Models", () => go("setup")), ", the picture model and the age check. (Opening Setup ends the practice.)"),
          h("li", {}, "The trainer, set up from the same Models page, and a finished training (step 3)."),
          h("li", {}, "Your enrolment at the camera (step 1), on the My likeness card once Setup → Phase two is on.")),
        h("div", { class: "practice-actions" },
          h("button", { class: "btn small", type: "button", id: "practiceAgain", onclick: () => { leave(); show("guide"); } }, "Start the practice over")));
      return box;
    },
  };

  // A drawn stand-in for the result: grey shapes and the word PRACTICE. It never uses a photo picked in step 2.
  function placeholder(words) {
    const ns = "http://www.w3.org/2000/svg";
    const el = (tag, attrs, text) => {   // colours go through style so the theme's variables apply
      const e = document.createElementNS(ns, tag);
      for (const k in attrs) {
        if (k === "fill" || k === "stroke") e.style[k] = attrs[k]; else e.setAttribute(k, attrs[k]);
      }
      if (text) e.textContent = text;
      return e;
    };
    const svg = el("svg", { viewBox: "0 0 420 520", role: "img", "aria-label": "Practice placeholder, not a real picture", class: "practice-result", id: "practicePlaceholder" });
    svg.append(
      el("rect", { x: 0, y: 0, width: 420, height: 520, rx: 16, fill: "var(--surface-2)", stroke: "var(--warn)", "stroke-width": 3 }),
      el("circle", { cx: 210, cy: 190, r: 70, fill: "var(--line)" }),
      el("rect", { x: 110, y: 280, width: 200, height: 180, rx: 60, fill: "var(--line)" }),
      el("text", { x: 210, y: 260, "text-anchor": "middle", "font-size": 64, "font-weight": 700, fill: "var(--warn)", transform: "rotate(-18 210 260)", opacity: 0.9 }, "PRACTICE"),
      el("text", { x: 210, y: 496, "text-anchor": "middle", "font-size": 16, fill: "var(--muted)" }, (words.length > 48 ? words.slice(0, 47) + "…" : words)));
    return h("figure", { style: { margin: 0 } }, svg,
      h("figcaption", { class: "hint" }, "PRACTICE placeholder. The real picture is made on this Mac from your words and your LoRA."));
  }

  VIEWS.practice = (m) => {
    main = h("div", { id: "practicePage" });
    m.append(main);
    show(PRACTICE.start || "guide");
    PRACTICE.start = null;
  };
  PRACTICE.open = (step) => { PRACTICE.start = step || "guide"; go("practice"); };

  // Entry on Setup: a plain button on the My likeness card when it is shown, or a small card of its own while phase two hides it.
  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    await setup0(m);
    if (m.querySelector("#practiceCard, #practiceFromCard")) return;
    const owner = m.querySelector("#ownerCard");
    const button = (id) => h("button", { class: "btn small", type: "button", id, onclick: () => PRACTICE.open("guide") }, "Practice my likeness");
    if (owner) {
      owner.append(h("p", { class: "hint", id: "practiceOnCard" }, "Want to try the steps first? Practice walks through them without saving anything. ", button("practiceFromCard")));
      return;
    }
    const card = h("div", { class: "card", id: "practiceCard" }, h("h2", {}, "My likeness", tag()),
      h("p", { class: "hint" }, "Walk through Enrol, Add photos, Train and Create before any model is on this Mac. Practice only: nothing is saved."),
      button("practiceOpen"));
    const phase = m.querySelector("#phaseTwoCard");   // where the real card would sit, next to its switch
    if (phase) phase.after(card); else m.append(card);
  };

  // Entry on Home: one more tile in the tool list (the list is drawn from this array each time Home opens).
  if (typeof FIRST_RUN_MAIN !== "undefined" && !FIRST_RUN_MAIN.some(t => t[0] === "practice")) {
    FIRST_RUN_MAIN.push(["practice", "🪞", "Practice my likeness", "Walk through Enrol, Add photos, Train and Create. Practice only: nothing is saved.", false]);
  }

  // Entry from the "Start here" guide, when that page is in the app: its own section at the end. Whichever file loads
  // first, the page gets the section, because the hook sits on the VIEWS entry itself.
  const guideSection = () => h("div", { class: "card", id: "practiceGuideSection" },
    h("h2", {}, "Your likeness (practice)", tag()),
    h("ol", { class: "practice-list" },
      h("li", {}, "Enrol: about a minute at the camera, one picture per pose."),
      h("li", {}, "Add photos: pick photos of yourself; see which would be kept and why."),
      h("li", {}, "Train: watch the steps the trainer runs, in about 30 seconds."),
      h("li", {}, "Create: describe a picture of yourself and see where it would go.")),
    h("p", { class: "hint" }, "Practice only: nothing is saved, nothing is sent, and no model is needed."),
    h("button", { class: "btn", type: "button", id: "practiceFromGuide", onclick: () => PRACTICE.open("guide") }, "Practice my likeness"));
  const wrapGuide = f => (typeof f === "function" ? async (m) => { await f(m); if (!m.querySelector("#practiceGuideSection")) m.append(guideSection()); } : f);
  let guide = wrapGuide(VIEWS["start-here"]);
  Object.defineProperty(VIEWS, "start-here", { configurable: true, enumerable: true, get: () => guide, set: f => { guide = wrapGuide(f); } });
})();
