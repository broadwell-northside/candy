/* Two plain pages for video: "Build a video" (#/video-build) and "Extend a video" (#/video-extend).
   Loaded after app.js, v3.js and make.js. It reuses runJob, pickFromGallery, the gallery and the LoRA library; it changes none of them.
   Jobs used: POST /api/jobs {kind:"video_any", ...} to build, {kind:"extend", params:{video, segments:[{text, seconds}], loras, engine}} to extend. */
"use strict";

(function () {
  const REALISTIC = "Realistic only: every clip is made to look like real filmed footage of fictional adults.";
  const OUTSIDE = "Easy Studio can continue videos it made — a video of a real person from outside is refused.";
  const EXAMPLES = [
    "she turns around and walks into the forest and sees trees",
    "the camera follows her as she walks slowly along the water's edge",
    "she stops, looks up at the sky and smiles",
  ];
  const BUILD_EXAMPLES = [
    "a woman walks down a quiet beach at sunrise, waves rolling in, soft natural light",
    "a woman sits at a cafe table by the window and lifts her coffee, handheld camera",
  ];
  const SECONDS = [3, 5, 8, 10];
  // The 20-second proof: one click builds a 5-second clip, then adds three more of 5 seconds with the existing multi-part extend.
  // Everyday section, a woman of a stated age of 30, photographic live-action. No LoRA. The words are plain on purpose.
  const PROOF = {
    age: 30,
    words: "a woman, 30 years old, in a small bikini walks along the shoreline of a sandy beach, photographic live-action footage, natural daylight, the camera follows her at a steady pace",
    parts: ["she keeps walking along the waterline",
            "she turns toward the waves and walks into the shallow water",
            "she turns back and walks up the beach toward the dunes"],
    seconds: 5,
  };
  const VIDEO_FAMILIES = { wan14b: "Wan 14B", wan5b: "Wan 5B", ltx2: "LTX", hunyuan_video: "Hunyuan", kandinsky5: "Kandinsky" };
  const STYLE_WORDS = /anime|cartoon|toon|animated|illustrat|manga|hentai/i;   // never offered on these pages

  const say = (el, text, kind) => { el.innerHTML = ""; if (text) el.append(h("div", { class: kind || "hint" }, text)); };
  const famOf = (s) => {
    s = String(s || "").toLowerCase();
    if (VIDEO_FAMILIES[s]) return s;
    if (/5b/.test(s)) return "wan5b";
    if (/wan/.test(s)) return "wan14b";
    if (/ltx/.test(s)) return "ltx2";
    if (/hunyuan/.test(s)) return "hunyuan_video";
    if (/kandinsky/.test(s)) return "kandinsky5";
    return "";
  };
  // A video Easy Studio itself made (not an upload, not held back by the age check).
  const isMade = (it) => !!it && it.type === "video" && it.role === "made" && !it.age_flag && !/^upload/.test(String(it.kind || ""));

  const header = (title, sub) => h("div", {},
    h("button", { class: "btn small", type: "button", id: "vxHome", onclick: () => go("home") }, "⌂ Home"),
    h("h1", {}, title), h("p", { class: "sub" }, sub),
    h("div", { class: "hint", id: "vxRealistic" }, "🎥 " + REALISTIC));

  async function pickVideo() {
    const g = await api("/api/gallery?type=video&limit=400");
    const items = g.items.filter(isMade);
    const grid = h("div", { class: "grid small", id: "vxVideoGrid" });
    if (!items.length) grid.append(h("div", { class: "empty" }, h("span", { class: "big" }, "🎬"), "No videos made here yet. Build one first."));
    for (const it of items) grid.append(h("div", { class: "res", "data-id": it.id, style: { cursor: "pointer" }, onclick: () => closeModal(it) },
      h("div", { class: "media" }, mediaEl(it, true))));
    return modal(h("div", {}, h("h2", {}, "Pick a video"), h("p", { class: "hint" }, OUTSIDE), grid), { wide: true });
  }
  async function pickPicture() {
    const x = await pickFromGallery({ type: "image", roles: ["made", "my_character"], title: "Pick a start picture" });
    return x && !x.age_flag ? x : null;
  }

  // Engine: This Mac, plus any video API provider that has a key (the provider layer owns that list; absent = This Mac only).
  async function engineChoice() {
    let list = [];
    try { const r = await api("/api/providers"); list = (Array.isArray(r) ? r : r.providers || []).filter(p => p.kind === "video" && p.configured); } catch (e) {}
    const s = h("select", { id: "vxEngine" }, h("option", { value: "local" }, "This Mac"));
    for (const p of list) s.append(h("option", { value: p.name }, (p.label || p.name) + " (API)"));
    return s;
  }
  // LoRAs: video families only, never a blocked one, matched to the video's family when that is known.
  async function loraChoice(family) {
    let all = [];
    try { all = (await api("/api/loras")).loras || []; } catch (e) {}
    const fit = (r) => !r.blocked && VIDEO_FAMILIES[r.family] && (!family || r.family === family) && !STYLE_WORDS.test(`${r.name} ${r.title} ${(r.trigger_words || []).join(" ")}`);
    const rows = all.filter(fit), by = Object.fromEntries(rows.map(r => [r.name, r]));
    const s = h("select", { id: "vxLora" }, h("option", { value: "" }, rows.length ? "(none)" : "(none for this video model yet; add one on the LoRAs page)"));
    for (const r of rows) s.append(h("option", { value: r.name }, `${r.title} · ${VIDEO_FAMILIES[r.family]}${r.trigger_words?.length ? " · trigger: " + r.trigger_words[0] : ""}`));
    const note = h("div", { class: "hint", id: "vxLoraNote" });
    s.addEventListener("change", () => { const r = by[s.value]; note.textContent = r && r.trigger_words?.length ? `The trigger word “${r.trigger_words[0]}” is added to your words for you.` : ""; });
    return { select: s, note,
      // words as sent: the trigger word goes in front, once
      words(text) { const r = by[s.value]; const t = r && r.trigger_words?.[0]; return t && !text.toLowerCase().includes(t.toLowerCase()) ? `${t}, ${text}` : text; },
      list() { const r = by[s.value]; return r ? [{ name: r.name, strength: r.strength_known && r.strength != null ? r.strength : 1 }] : []; } };
  }
  const secondsChoice = (st) => seg(SECONDS.map(n => [n, n + " s"]), st.seconds, v => st.seconds = v);
  const field = (label, ...kids) => h("div", { style: { marginTop: "14px" } }, h("label", { class: "f" }, label), ...kids);
  const playing = (it) => h("video", { src: it.url, controls: true, muted: true, loop: true, playsinline: true, preload: "metadata", style: { maxWidth: "100%", borderRadius: "10px" } });
  const download = (it, label) => h("a", { class: "btn", id: "vxDownload", href: it.url, download: (it.id || "video") + ".mp4" }, label);

  // ---------------------------------------------------------------- Build a video
  VIEWS["video-build"] = async (m) => {
    const st = { seconds: 5, start: null };
    m.append(header("Build a video", "Describe what you want to see. Easy Studio makes a short clip you can then extend."));
    let models = [];
    try { models = (await api("/api/video/models")).models || []; } catch (e) { m.append(h("div", { class: "err", id: "vxError" }, e.message)); return; }
    const pick = (mode) => models.find(x => x.ready && x.mode === mode);
    const text = h("textarea", { id: "vbText", rows: 5, placeholder: "e.g. " + BUILD_EXAMPLES[0], style: { width: "100%", fontSize: "18px" } });
    const age = h("input", { id: "vbAge", type: "text", inputmode: "numeric", placeholder: "21 or more", style: { width: "8em" } });
    const startBox = h("div", { class: "working", id: "vbStart" });
    const drawStart = () => { startBox.innerHTML = "";
      startBox.append(h("div", { class: "thumb", style: st.start ? { backgroundImage: `url(${st.start.url})` } : {} }, st.start ? "" : "🖼️"),
        h("div", { class: "meta" }, st.start ? (st.start.title || "Start picture") : "No start picture",
          h("div", { class: "row", style: { marginTop: "8px" } },
            h("button", { class: "btn small", type: "button", id: "vbPickStart", onclick: async () => { const x = await pickPicture(); if (x) { st.start = x; drawStart(); } } }, "Choose from gallery"),
            st.start ? h("button", { class: "btn small", type: "button", onclick: () => { st.start = null; drawStart(); } }, "✕") : null))); };
    drawStart();
    const engine = await engineChoice();
    const lora = await loraChoice(famOf((pick("t2v") || pick("i2v") || {}).family));
    const status = h("div", { id: "vxStatus" }), out = h("div", { id: "vxResult" });
    const noModel = !pick("t2v") && !pick("i2v");
    const go1 = bigButton("🎬 Build video", async () => {
      const words = text.value.trim();
      if (!words) return say(status, "Write what you want to see first.", "err");
      const x = st.start ? pick("i2v") : pick("t2v");
      if (!x) return say(status, st.start ? "No picture-to-video model is installed yet. Open Setup." : "No text-to-video model is installed yet. Open Setup.", "err");
      // A hosted engine is its own job (Video (API)): the local build job has no hosted engine, and would run on this Mac.
      const hosted = !!engine.value && engine.value !== "local";
      const p = hosted ? { text: words, seconds: st.seconds, stated_age: age.value.trim(), advanced: { loras: lora.list() } }
        : { model: x.id, text: lora.words(words), seconds: st.seconds, stated_age: age.value.trim(), quality: "fast", aspect: "landscape", engine: engine.value, advanced: { loras: lora.list() } };
      if (st.start) p[hosted ? "image" : "start"] = st.start.id;
      out.innerHTML = "";
      await runJob(hosted ? "video_api" : "video_any", p, status, { key: "vbuild", label: "Building the video", onDone: j => {
        const it = j.results && j.results[0];
        if (j.status !== "done" || !it) return;
        if (it.age_flag) return say(status, "The automatic age check held that clip back, so it is not shown. Try again with different words.", "err");
        status.innerHTML = ""; setCurrent(it, false);
        out.append(h("div", { class: "card" }, h("h2", {}, "Your clip"), playing(it),
          h("div", { class: "row", style: { marginTop: "12px", gap: "10px" } },
            h("button", { class: "btn primary", type: "button", id: "vbExtend", onclick: () => { store.set("vx.handoff", it.id); try { sessionStorage.removeItem("es.vx.chain"); } catch (e) {} go("video-extend"); } }, "Extend this clip"),
            download(it, "Download"))));
      } });
    });
    go1.id = "vbBuild";
    // ---- the 20-second proof (see PROOF above): build 5 s, then one extend of three parts of 5 s each, joined
    const proofOut = h("div", { id: "vbProofResult" });
    const proofBtn = bigButton("🎞️ Make the 20-second proof", async () => {
      const x = pick("t2v");
      if (!x) return say(status, "No text-to-video model is installed yet. Open Setup.", "err");
      text.value = PROOF.words;                       // shown, so you can see what was sent
      age.value = String(PROOF.age);
      lora.select.value = "";                         // no LoRA in the proof
      lora.select.dispatchEvent(new Event("change"));
      proofOut.innerHTML = "";
      const hosted = !!engine.value && engine.value !== "local";
      const first = hosted ? { text: PROOF.words, seconds: PROOF.seconds, stated_age: String(PROOF.age) }
        : { model: x.id, text: PROOF.words, seconds: PROOF.seconds, stated_age: String(PROOF.age), quality: "fast", aspect: "landscape", engine: engine.value, advanced: { loras: [] } };
      await runJob(hosted ? "video_api" : "video_any", first, status, { key: "vproof1", label: "Proof, part 1 of 4 (5 seconds)", onDone: async j1 => {
        const base = j1.results && j1.results[0];
        if (j1.status !== "done" || !base) return;
        if (base.age_flag) return say(status, "The automatic age check held the first clip back, so the proof stopped. Try again.", "err");
        const more = { video: base.id, segments: PROOF.parts.map(t => ({ text: t, seconds: PROOF.seconds })), loras: [], engine: engine.value };
        await runJob("extend", more, status, { key: "vproof2", label: "Proof, parts 2 to 4 (15 seconds, joined)", onDone: j2 => {
          const it = j2.results && j2.results[0];
          if (j2.status !== "done" || !it) return;
          if (it.age_flag) return say(status, "The automatic age check held the joined clip back, so it is not shown. Try again.", "err");
          status.innerHTML = ""; setCurrent(it, false);
          proofOut.append(h("div", { class: "card", id: "vbProofCard2" }, h("h2", {}, "Your 20-second clip"), playing(it),
            h("div", { class: "row", style: { marginTop: "12px", gap: "10px" } },
              h("button", { class: "btn primary", type: "button", id: "vbProofExtend", onclick: () => { store.set("vx.handoff", it.id); try { sessionStorage.removeItem("es.vx.chain"); } catch (e) {} go("video-extend"); } }, "Extend this clip"),
              download(it, "Download"))));
        } });
      } });
    });
    proofBtn.id = "vbProof";
    if (noModel) { go1.disabled = true; go1._sync = () => { go1.disabled = true; }; m.append(h("div", { class: "warn-bar", id: "vxNoModel", onclick: () => go("setup") }, "⚠️ No video model is installed yet, so Build stays off. Open Setup to get one.")); }
    m.append(h("div", { class: "card" },
      field("What do you want to see?", text, h("div", { class: "hint" }, "Use plain words, like “a woman walks down a quiet beach.”")),
      field("Age of the person in it", age, h("div", { class: "hint" }, "Needed when your words bring in a person. It must be 21 or more; an age is never guessed from how someone looks.")),
      field("Start picture (optional)", startBox),
      field("How long?", secondsChoice(st)),
      field("LoRA (optional)", lora.select, lora.note),
      field("Engine", engine),
      h("div", { style: { marginTop: "18px" } }, go1)),
      h("div", { class: "card", id: "vbProofBox" }, h("h2", {}, "20-second proof"),
        h("p", { class: "hint" }, "One click: a woman of a stated age of 30 in a small bikini walks along a beach, in four parts of 5 seconds joined into one 20-second clip. " +
          "It uses the Engine chosen above and no LoRA. On this Mac it takes a long while, about 10 minutes for each part."),
        proofBtn),
      status, proofOut, out);
  };

  // ---------------------------------------------------------------- Extend a video
  VIEWS["video-extend"] = async (m) => {
    const st = { seconds: 5 };
    let chain = { steps: [] };   // chain.base = the first clip; each step = {text, seconds, item} where item is the whole joined video so far
    try { chain = JSON.parse(sessionStorage.getItem("es.vx.chain") || "null") || chain; } catch (e) {}
    const save = () => { try { sessionStorage.setItem("es.vx.chain", JSON.stringify(chain)); } catch (e) {} };
    if (!chain.base) {
      const hid = store.get("vx.handoff", null);
      let it = null;
      if (hid) { try { it = await api("/api/items/" + hid); } catch (e) {} }
      if (!isMade(it) && isMade(S.currentVideo)) it = S.currentVideo;
      if (isMade(it)) { chain = { base: it, steps: [] }; save(); }
    }
    m.append(header("Extend a video", "Say what happens next. Easy Studio makes the next clip and joins it on."));
    m.append(h("div", { class: "hint", id: "vxOutside" }, OUTSIDE));
    const latest = () => chain.steps.length ? chain.steps[chain.steps.length - 1].item : chain.base;
    const timeline = h("ol", { id: "vxTimeline", style: { listStyle: "none", padding: 0, margin: "18px 0" } });
    const drawTimeline = () => {
      timeline.innerHTML = "";
      if (chain.base) timeline.append(h("li", { class: "vx-step", style: { marginBottom: "16px" } }, h("b", {}, "Start"), h("div", {}, playing(chain.base))));
      chain.steps.forEach((s, i) => timeline.append(h("li", { class: "vx-step", style: { marginBottom: "16px" } },
        h("b", {}, `Then (${i + 1}): ${s.text}`), h("div", { class: "hint" }, `+${s.seconds} seconds, joined on`), h("div", {}, playing(s.item)))));
      dl.innerHTML = "";
      if (chain.steps.length) dl.append(download(latest(), "⬇ Download the joined video"),
        h("button", { class: "btn", type: "button", id: "vxAgain", style: { marginLeft: "10px" }, onclick: () => { text.value = ""; text.focus(); text.scrollIntoView({ block: "center" }); } }, "Extend again"),
        h("button", { class: "btn small", type: "button", id: "vxReset", style: { marginLeft: "10px" }, onclick: () => { chain = { steps: [] }; save(); go("video-extend"); } }, "Start over"));
    };
    const dl = h("div", { id: "vxDl", style: { margin: "10px 0" } });
    const pickBox = h("div", { class: "working", id: "vxPick" });
    const drawPick = () => { pickBox.innerHTML = "";
      if (chain.steps.length) return pickBox.append(h("div", { class: "hint" }, "Continuing from the newest clip below."));
      pickBox.append(h("div", { class: "thumb" }, "🎬"), h("div", { class: "meta" }, chain.base ? (chain.base.title || "Your video") : "No video picked yet",
        h("div", { class: "row", style: { marginTop: "8px" } }, h("button", { class: "btn small", type: "button", id: "vxPickVideo", onclick: async () => {
          const x = await pickVideo(); if (!x) return; chain = { base: x, steps: [] }; save(); setCurrent(x, false); drawPick(); drawTimeline(); renderLora(); } }, "Choose from gallery")))); };
    const text = h("textarea", { id: "vxText", rows: 5, placeholder: "e.g. " + EXAMPLES[0], style: { width: "100%", fontSize: "20px" } });
    const chips = h("div", { class: "row", style: { gap: "8px", flexWrap: "wrap", marginTop: "8px" } },
      EXAMPLES.map(e => h("button", { class: "btn small vx-example", type: "button", onclick: () => { text.value = e; } }, e)));
    const engine = await engineChoice();
    const loraBox = h("div");
    let lora;
    const renderLora = async () => { lora = await loraChoice(famOf(latest() && (latest().model || latest().family))); loraBox.innerHTML = ""; loraBox.append(lora.select, lora.note); };
    await renderLora();
    const status = h("div", { id: "vxStatus" });
    const go1 = bigButton("➕ Extend", async () => {
      const words = text.value.trim();
      if (!latest()) return say(status, "Pick a video to continue first.", "err");
      if (!words) return say(status, "Say what happens next first.", "err");
      const sent = lora.words(words);
      const params = { video: latest().id, segments: [{ text: sent, seconds: st.seconds }], loras: lora.list(), engine: engine.value };
      await runJob("extend", params, status, { key: "vextend", label: "Making the next clip", onDone: j => {
        const it = j.results && j.results[0];
        if (j.status !== "done" || !it) return;
        if (it.age_flag) return say(status, "The automatic age check held that clip back, so it was not added. Try different words.", "err");
        status.innerHTML = "";
        chain.steps.push({ text: words, seconds: st.seconds, item: it }); save(); setCurrent(it, false);
        text.value = ""; drawPick(); drawTimeline();
      } });
    });
    go1.id = "vxExtend";
    drawPick(); drawTimeline();
    m.append(h("div", { class: "card" },
      field("Video", pickBox),
      field("What happens next?", text, chips),
      field("How long?", secondsChoice(st)),
      field("LoRA (optional)", loraBox),
      field("Engine", engine),
      h("div", { style: { marginTop: "18px" } }, go1)), status, timeline, dl);
  };

  DOORS.push("video-build", "video-extend");   // so the address #/video-build and #/video-extend open directly
})();
