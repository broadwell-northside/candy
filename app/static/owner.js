// The owner's own likeness, as three steps on one card: Enrol, Train, Create.
// Enrolment is by this computer's camera. There is no file field on purpose.
(function () {
  const STEP_WORDS = {
    face_camera: "Look straight at the camera.", turn_left: "Turn your head to the left.",
    turn_right: "Turn your head to the right.", tilt: "Tilt your head to one side.", look_up: "Look up.",
  };
  const FACE_WORDS = "The app is about to make pictures of a real person, so it checks once that the photos are of the person using it. " +
    "It runs on this Mac and nothing leaves it. " +
    "The live check asks you to turn, tilt and look up in front of the camera. It does not detect a recording of you.";
  const TRIGGER = "mylikeness";  // the word the training ties to the owner; the picture job adds it by itself
  const ENDED = ["done", "error", "cancelled", "blocked_age_check_unavailable"];
  let stream = null;

  function stopCamera() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
  }

  async function grab(video) {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return await new Promise(done => canvas.toBlob(done, "image/png"));
  }

  // One capture session (enrolment, or the live match): a camera, one picture per step, then commit.
  function capture(startPath, startBody, say, onEnd) {
    const video = h("video", { id: "ownerVideo", autoplay: true, playsinline: true, muted: true, style: "max-width:320px;display:none" });
    const take = h("button", { class: "btn", type: "button", id: "ownerTake", disabled: true }, "Take picture");
    const start = h("button", { class: "btn", type: "button", id: "ownerStart" }, "Start camera");
    let run = null;
    const ask = () => { say.textContent = "Step " + (run.at + 1) + " of " + run.plan.length + ". " + (STEP_WORDS[run.plan[run.at].step] || run.plan[run.at].step); };
    start.onclick = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
        video.srcObject = stream; video.style.display = "";
        const got = await api(startPath, { method: "POST", body: startBody() });
        run = { session: got.session, plan: got.plan, nonce: got.nonce, at: 0 };
        start.disabled = true; take.disabled = false; ask();
      } catch (e) { stopCamera(); video.style.display = "none"; say.textContent = e.message; }
    };
    take.onclick = async () => {
      if (!run) return;
      const body = new FormData();
      body.append("file", await grab(video), "frame.png"); body.append("session", run.session);
      body.append("index", String(run.at)); body.append("nonce", run.nonce);
      try {
        const got = await api("/api/owner/enrol/frame", { method: "POST", body });
        if (!got.done) { run.at = got.next; run.nonce = got.nonce; ask(); return; }
        const end = await api("/api/owner/enrol/commit", { method: "POST", body: { session: run.session } });
        stopCamera(); video.style.display = "none"; take.disabled = true; run = null;
        onEnd(end);
      } catch (e) { say.textContent = e.message; }
    };
    return [video, start, take];
  }

  async function waitJob(kind, params, area, onTick) {
    const made = await api("/api/jobs", { method: "POST", body: { kind, params, area } });
    for (;;) {
      await new Promise(r => setTimeout(r, 1500));
      const job = await api("/api/jobs/" + made.id);
      if (ENDED.includes(job.status)) return job;
      onTick(job);
    }
  }

  async function card() {
    const box = h("div", { class: "card", id: "ownerCard" }, h("h2", {}, "My likeness"));
    let st, tr = null;
    try {
      st = await api("/api/owner/status");
      if (st.enrolled) tr = await api("/api/owner/trainer");
    } catch (e) { box.append(h("p", { class: "hint" }, e.message)); return box; }
    const trained = !!(tr && tr.likeness_loras > 0);
    const say = h("p", { id: "ownerSay", class: "hint" },
      !st.enrolled ? "Start with Enrol: about a minute at the camera."
        : !trained ? "You are enrolled. Next: Train."
          : "You are enrolled and your likeness is trained. Create makes a picture of you.");
    const panel = h("div", { id: "ownerPanel" });
    const again = async () => { stopCamera(); box.replaceWith(await card()); };
    let busy = false;

    // The passphrase is asked only when a step needs it. An unlock lasts five minutes.
    async function unlocked(then) {
      let now;
      try { now = await api("/api/owner/status"); } catch (e) { say.textContent = e.message; return; }
      if (now.unlocked) return then();
      const pass = h("input", { id: "ownerUnlockPass", type: "password", autocomplete: "current-password", placeholder: "Your passphrase" });
      const go = h("button", { class: "btn small", type: "button", id: "ownerUnlock", onclick: async () => {
        try { await api("/api/owner/unlock", { method: "POST", body: { passphrase: pass.value } }); }
        catch (e) { say.textContent = e.message; return; }
        row.remove();
        then();
      } }, "Unlock");
      const row = h("div", { id: "ownerUnlockRow" }, h("label", { class: "f" }, "Passphrase"), pass, go);
      panel.prepend(row);
      say.textContent = "Type your passphrase to go on. An unlock lasts five minutes.";
    }

    function enrolPanel() {
      panel.replaceChildren(h("p", { id: "ownerFaceWords" }, FACE_WORDS));
      if (st.enrolled) { say.textContent = "One person is enrolled on this app. That is you."; return; }
      if (!st.checker_on) { say.textContent = "The appearance checker is off, so enrolment will not start."; return; }
      if (!st.face_check) { say.textContent = st.face_check_message; return; }
      const age = h("input", { id: "ownerAge", class: "stated-age", type: "text", inputmode: "numeric", placeholder: "Your stated age" });
      const pass = h("input", { id: "ownerPass", type: "password", autocomplete: "new-password", placeholder: "A passphrase (at least " + st.min_passphrase + " characters)" });
      say.textContent = "Be alone in front of the camera. " + st.steps + " pictures are taken, one per step.";
      panel.append(h("label", { class: "f" }, "Stated age"), age, h("label", { class: "f" }, "Passphrase"), pass,
        ...capture("/api/owner/enrol/start", () => { const body = { age: age.value.trim(), passphrase: pass.value }; pass.value = ""; return body; }, say,
          (end) => { if (end.enrolled) again(); else say.textContent = "Enrolment was not saved."; }));
    }

    function trainPanel() {
      panel.replaceChildren();
      if (!tr.trainer_installed) { say.textContent = "The trainer isn't installed yet."; return; }
      unlocked(async () => {
        if (busy) return;
        busy = true;
        try {
          if (!tr.selftest_passed) {
            say.textContent = "First a short test of the trainer, on drawn shapes ...";
            const test = await waitJob("owner_train_selftest", { base: "fast" }, "default", j => { say.textContent = "Trainer test: " + (j.message || "running"); });
            if (test.status !== "done") { say.textContent = "The trainer test did not pass. " + (test.error || test.message || ""); return; }
          }
          say.textContent = "Training your likeness. This takes a while; you can leave this page.";
          const job = await waitJob("owner_train", { base: "fast", trigger: TRIGGER }, "default", j => { say.textContent = "Training: " + (j.message || "running"); });
          if (job.status !== "done") { say.textContent = "Training did not finish. " + (job.error || job.message || ""); return; }
          await again();
        } catch (e) { say.textContent = e.message; } finally { busy = false; }
      });
    }

    function createPanel() {
      const text = h("input", { id: "ownerText", type: "text", placeholder: "Describe the picture of you" });
      const shots = h("div", { id: "ownerGallery" });
      const go = h("button", { class: "btn", type: "button", id: "ownerPicture", onclick: () => unlocked(async () => {
        if (busy) return;
        busy = true; go.disabled = true;
        try {
          const job = await waitJob("owner_picture", { text: text.value, base: "fast" }, (typeof S !== "undefined" && S.area) || undefined,
            j => { say.textContent = "Making the picture: " + (j.message || "running"); });
          if (job.status !== "done") { say.textContent = job.error || job.message || "Nothing was kept. You can try again."; return; }
          say.textContent = job.message || "Saved to your private gallery.";
          await showGallery(shots);
        } catch (e) { say.textContent = e.message; } finally { busy = false; go.disabled = false; }
      }) }, "Make the picture");
      panel.replaceChildren(h("label", { class: "f" }, "A picture of me"), text, go, shots);
      say.textContent = "Describe the picture. It goes to your private gallery and nowhere else.";
    }

    async function showGallery(shots) {
      const got = await api("/api/owner/gallery");
      shots.replaceChildren(...got.items.map(row => h("img", { src: row.url, alt: "A picture of you", style: "max-width:160px;margin:4px" })));
      return got.items.length;
    }

    // Everything else sits under More: the 18+ steps, the private gallery, and delete.
    function more() {
      const shots = h("div", { id: "ownerMoreGallery" });
      const live = h("div", { id: "ownerLivePart" });
      const act = async (run) => { try { await run(); } catch (e) { say.textContent = e.message; } };
      return h("details", { id: "ownerMore" }, h("summary", {}, "More"),
        h("button", { class: "btn small", type: "button", id: "ownerShow", onclick: () => unlocked(() => act(async () => {
          say.textContent = (await showGallery(shots)) + " pictures in your private gallery.";
        })) }, "Show my private gallery"),
        h("button", { class: "btn small", type: "button", id: "ownerLive", onclick: () => unlocked(() => {
          say.textContent = "A live match is three pictures at the camera. An 18+ picture of you starts only for a short time after it.";
          live.replaceChildren(...capture("/api/owner/live/start", () => ({}), say,
            (end) => { live.replaceChildren(); say.textContent = "Live match passed. 18+ likeness jobs can start for " + Math.round(end.seconds / 60) + " minutes."; }));
        }) }, "Live match"),
        h("button", { class: "btn small", type: "button", id: "ownerConsent", onclick: () => unlocked(() => act(async () => {
          const c = await api("/api/owner/consent");
          if (!confirm(c.statement)) return;
          await api("/api/owner/consent", { method: "POST", body: { give: true } });
          say.textContent = "18+ consent given.";
        })) }, "Give 18+ consent"),
        h("button", { class: "btn small", type: "button", id: "ownerWithdraw", onclick: () => unlocked(() => act(async () => {
          const got = await api("/api/owner/consent", { method: "POST", body: { give: false } });
          say.textContent = "18+ consent withdrawn. Pictures deleted: " + got.removed + ".";
        })) }, "Withdraw 18+ consent"),
        h("button", { class: "btn small", type: "button", id: "ownerDelete", onclick: () => act(async () => {
          const words = prompt('This deletes your enrolment, your likeness LoRA and every picture made with it. Type "delete my likeness" to go on.');
          if (words === null) return;
          await api("/api/owner/likeness", { method: "DELETE", body: { confirm: words } });
          await again();
        }) }, "Delete my likeness"),
        live, shots);
    }

    const step = (id, label, on, enabled) => h("button", { class: "btn primary", type: "button", id, disabled: !enabled, onclick: on }, label);
    box.append(
      h("p", {}, st.how),
      h("div", { id: "ownerSteps" },
        step("ownerEnrolBtn", st.enrolled ? "1 Enrol ✓" : "1 Enrol", enrolPanel, true), " ",
        step("ownerTrainBtn", trained ? "2 Train ✓" : "2 Train", trainPanel, st.enrolled), " ",
        step("ownerCreateBtn", "3 Create", createPanel, trained)),
      say, panel);
    if (st.enrolled) box.append(more());
    return box;
  }

  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    stopCamera();
    await setup0(m);
    if (!(await PHASE_TWO.shown())) return;  // phase two: hidden from the first run until the Setup switch is on
    m.append(await card());
  };
})();
