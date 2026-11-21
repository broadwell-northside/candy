// Self-test: the owner presses it. It runs the app's own chain on a made-up adult, through the same jobs the
// pages use: text to picture, picture to clip, clip to longer clip, picture to 3D. It shows the numbers.
(function () {
  const SEED = 20261106;
  const STEPS = [
    { id: "picture", title: "Text to picture", kind: "create", params: () => ({
      dna: { name: "Self-test", gender: "man", age: 30, style: "photo" }, outfit: "dressy:suit", scene: "office",
      lighting: "soft", camera: "half", aspect: "portrait", count: 1, seed: SEED }) },
    { id: "clip", title: "Picture to clip", kind: "video", params: (got) => ({
      image: got.picture.id, motion: "look", seconds: 4, mode: "fast", quality: "480", advanced: { seed: SEED } }) },
    { id: "longer", title: "Clip to longer clip", kind: "extend", params: (got) => ({
      video: got.clip.id, segments: [{ motion: "walk", seconds: 4 }] }) },
    { id: "model", title: "Picture to 3D", kind: "model3d", params: (got) => ({ image: got.picture.id }) },
  ];
  const ENDED = ["done", "error", "cancelled", "blocked_age_check_unavailable"];
  let running = false;

  function numbers(item) {
    const p = item.provenance || {};
    const pick = (k) => (item[k] != null ? item[k] : p[k]);
    const out = [];
    if (item.w && item.h) out.push(item.w + " × " + item.h + " pixels");
    if (pick("seconds") != null) out.push(Number(pick("seconds")).toFixed(1) + " seconds");
    if (pick("frames") != null) out.push(pick("frames") + " frames");
    if (pick("fps") != null) out.push(pick("fps") + " frames a second");
    if (Array.isArray(p.segments) && p.segments.length) {
      const sum = (k) => p.segments.reduce((a, one) => a + (Number(one[k]) || 0), 0);
      out.push("added " + sum("seconds").toFixed(1) + " seconds, " + sum("frames") + " frames");
    }
    if (Array.isArray(p.join_points) && p.join_points.length) out.push("joined at frame " + p.join_points.map(j => j.frame).join(", "));
    if (p.mesh) out.push(p.mesh.vertices + " points, " + p.mesh.faces + " faces");
    if (p.machine) out.push("profile " + p.machine);
    return out.join(", ");
  }

  async function runJob(kind, params, onTick) {
    const made = await api("/api/jobs", { method: "POST", body: { kind, params, area: "default" } });  // the everyday section
    for (;;) {
      await new Promise(r => setTimeout(r, 1000));
      const job = await api("/api/jobs/" + made.id);
      if (ENDED.includes(job.status)) return job;
      onTick(job);
    }
  }

  async function runChain(list, say) {
    const got = {};
    let passed = 0;
    list.replaceChildren(...STEPS.map(s => h("li", { id: "selfTest_" + s.id }, s.title + ": waiting")));
    for (const step of STEPS) {
      const row = list.querySelector("#selfTest_" + step.id);
      const t0 = Date.now();
      const took = () => Math.round((Date.now() - t0) / 1000) + " s";
      row.textContent = step.title + ": running ...";
      let job;
      try { job = await runJob(step.kind, step.params(got), j => { row.textContent = step.title + ": " + (j.message || "running") + " (" + took() + ")"; }); }
      catch (e) { job = { status: "error", error: e.message }; }
      const item = (job.results || [])[0];
      if (job.status !== "done" || !item) {
        row.textContent = step.title + ": did not pass after " + took() + ". " + (job.error || job.message || "No result came back.");
        row.className = "err";
        say.textContent = "Self-test stopped: " + passed + " of " + STEPS.length + " steps passed.";
        return;
      }
      got[step.id] = item;
      passed += 1;
      row.textContent = step.title + ": passed in " + took() + ". " + numbers(item);
    }
    say.textContent = "Self-test passed: " + passed + " of " + STEPS.length + " steps. The results are in the gallery under “Self-test”.";
  }

  function card() {
    const say = h("p", { id: "selfTestSay", class: "hint" },
      "Runs the whole chain once on a made-up adult: text to picture, picture to clip, clip to longer clip, picture to 3D. " +
      "It needs the picture engine running and the models on this computer, and it can take a long time.");
    const list = h("ol", { id: "selfTestSteps" });
    const go = h("button", { class: "btn", type: "button", id: "selfTestGo", onclick: async () => {
      if (running) return;
      running = true; go.disabled = true;
      say.textContent = "Self-test running. Leave this page open.";
      try { await runChain(list, say); } finally { running = false; go.disabled = false; }
    } }, "Run the self-test");
    const trainerSay = h("span", { id: "selfTestTrainerSay", class: "hint" }, "");
    const trainer = h("button", { class: "btn small", type: "button", id: "selfTestTrainer", onclick: async () => {
      try { await api("/api/jobs", { method: "POST", body: { kind: "owner_train_selftest", params: { base: "fast" } } }); trainerSay.textContent = " Started. Progress is in the job list."; }
      catch (e) { trainerSay.textContent = " " + e.message; }
    } }, "Test the trainer");
    return h("div", { class: "card", id: "selfTestCard" }, h("h2", {}, "Self-test"), say, go, list,
      h("p", { class: "hint" }, "The trainer has its own short test. It trains on drawn shapes, not on pictures of anyone. ", trainer, trainerSay));
  }

  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    await setup0(m);
    m.append(card());
  };
})();
