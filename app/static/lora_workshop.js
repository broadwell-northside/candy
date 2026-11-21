/* LoRA workshop. Loaded after app.js and before v3.js. */
"use strict";

VIEWS["lora-workshop"] = async (m) => {
  const intro = h("p", { class: "sub", id: "loraIntro" }, "Bring in a LoRA, read the card, and test it on the mock engine. Fictional adults are 21 or older. Me is the player, Andrew, and Me is not a partner.");
  m.append(h("h1", {}, "LoRA workshop"), intro);
  const limits = await api("/api/loras/workshop/limits");
  const cat = await api("/api/loras/workshop/catalogue");
  let library = await api("/api/loras");
  let step = "library";
  let picked = "";
  let prompt = "";
  let age = "";
  let seed = "";
  let engine = "wan22_high";
  const stack = [];
  let tick = false;
  let resumeAck = false;

  const root = h("div", { id: "loraWorkshop" });
  const steps = h("div", { class: "seg", id: "loraSteps" });
  const panels = {
    library: h("div", { id: "loraPanelLibrary" }),
    card: h("div", { id: "loraPanelCard" }),
    stack: h("div", { id: "loraPanelStack" }),
    benchmark: h("div", { id: "loraPanelBenchmark" }),
    train: h("div", { id: "loraPanelTrain" }),
  };
  for (const [id, label] of [["library", "Library"], ["card", "Usage card"], ["stack", "Stack"], ["benchmark", "Benchmark"], ["train", "Train and Me"]]) {
    steps.append(h("button", { type: "button", id: "loraGo" + id[0].toUpperCase() + id.slice(1), onclick: () => show(id) }, label));
  }
  function show(id) {
    step = id;
    for (const key of Object.keys(panels)) panels[key].classList.toggle("hidden", key !== id);
    for (const button of steps.querySelectorAll("button")) button.classList.toggle("on", button.id === "loraGo" + id[0].toUpperCase() + id.slice(1));
    if (id === "card") drawCard();
    if (id === "stack") drawStack();
    if (id === "benchmark") drawBench();
    if (id === "train") drawTrain();
  }

  function weightName() {
    return picked || (library.loras[0] && library.loras[0].name) || "";
  }

  const url = h("input", { id: "loraUrl", type: "text", placeholder: "https://civitai.com/models/…" });
  const lookupBox = h("div", { id: "loraLookup" });
  const list = h("div", { id: "loraLibraryList" });
  const drop = h("div", { class: "dropzone", id: "loraDrop" }, "Drop a .safetensors file here, or click to choose");
  const file = h("input", { type: "file", accept: ".safetensors", style: { display: "none" } });
  drop.onclick = () => file.click();
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); uploadFile(e.dataTransfer.files[0]); };
  file.onchange = () => uploadFile(file.files[0]);

  async function uploadFile(one) {
    if (!one) return;
    if (!tick) return toast("Tick the box before the file is saved.", "bad");
    const body = new FormData();
    body.append("file", one);
    body.append("confirm", "yes");
    try {
      const rec = await api("/api/loras/workshop/upload", { method: "POST", body });
      toast("Added " + rec.title, "good");
      picked = rec.name;
      await refreshLibrary();
    } catch (e) { toast(e.message, "bad"); }
  }

  async function refreshLibrary() {
    library = await api("/api/loras");
    drawLibrary();
  }

  function drawLibrary() {
    list.innerHTML = "";
    const ready = (cat.entries || []).filter(row => row.ok);
    const refused = (cat.entries || []).filter(row => !row.ok);
    list.append(h("h2", {}, "Catalogue"));
    list.append(h("p", { class: "hint" }, "This list is metadata. Weights are not downloaded until you confirm."));
    for (const row of refused.concat(ready)) {
      const button = h("button", { class: "btn small", type: "button", disabled: !row.ok || !tick }, row.ok ? "Download after confirm" : "Refused");
      button.onclick = async () => {
        try {
          const rec = await api("/api/loras/workshop/import", { method: "POST", body: { id: row.id, confirm: "yes" } });
          picked = rec.name;
          toast("Added " + rec.title, "good");
          await refreshLibrary();
        } catch (e) { toast(e.message, "bad"); }
      };
      list.append(h("div", { class: "card" + (row.ok ? "" : " warnbox"), id: "loraCat-" + row.id },
        h("b", {}, row.name),
        h("div", { class: "hint" }, (row.baseModel || "Unknown base") + " · hash " + (row.hash_status === "UNKNOWN" ? "UNKNOWN" : "listed")),
        row.trainedWords && row.trainedWords.length ? h("div", {}, "Trigger words: " + row.trainedWords.join(", ")) : h("div", {}, limits.empty_trigger),
        row.ok ? null : h("div", { class: "err", id: row.id === "taken-down" ? "loraTakenDown" : "" }, row.reason),
        button));
    }
    list.append(h("h2", {}, "In this library"));
    const mine = (library.loras || []).filter(row => row.source === "Workshop catalogue" || row.source === "upload" || row.source === "Me portrait" || row.source === "Workshop training");
    if (!mine.length) list.append(h("p", { class: "hint" }, "Nothing from this workshop yet."));
    for (const row of mine) {
      list.append(h("div", { class: "card lora" },
        h("div", {},
          h("b", {}, row.title || row.name),
          h("div", { class: "hint" }, row.name),
          h("button", { class: "btn small", type: "button", onclick: () => { picked = row.name; show("card"); } }, "Open usage card"))));
    }
  }

  async function lookUp() {
    lookupBox.innerHTML = "";
    try {
      const info = await api("/api/loras/workshop/lookup", { method: "POST", body: { url: url.value } });
      const button = h("button", { class: "btn small", type: "button", disabled: !info.ok || !tick }, info.ok ? "Download after confirm" : "Refused");
      button.onclick = async () => {
        const rec = await api("/api/loras/workshop/import", { method: "POST", body: { id: info.id, confirm: "yes" } });
        picked = rec.name;
        await refreshLibrary();
        show("card");
      };
      lookupBox.append(h("div", { class: "card" },
        h("b", {}, info.name || "Lookup"),
        h("div", {}, info.ok ? "Ready to download after you confirm." : info.reason),
        info.trainedWords && info.trainedWords.length ? h("div", { class: "hint" }, info.trainedWords.join(", ")) : h("div", {}, limits.empty_trigger),
        button));
    } catch (e) {
      lookupBox.append(h("div", { class: "err" }, e.message));
    }
  }

  const cardBox = h("div", { id: "loraUsage" });
  const promptBox = h("textarea", { id: "loraPrompt", rows: "3", placeholder: "Prompt for this LoRA" });
  promptBox.addEventListener("input", () => { prompt = promptBox.value; });
  const weightLine = h("p", { id: "loraWeight" }, "");

  async function drawCard() {
    cardBox.innerHTML = "";
    const name = weightName();
    weightLine.textContent = name ? "Weight file: " + name : "Pick a LoRA from the library.";
    if (!name) return;
    let card;
    try { card = await api("/api/loras/workshop/card?name=" + encodeURIComponent(name)); }
    catch (e) { cardBox.append(h("div", { class: "err" }, e.message)); return; }
    if (weightLine.textContent !== "Weight file: " + name) return;
    const words = h("p", { id: "loraTriggers" }, card.trained_words.length ? "Trigger words: " + card.trained_words.join(", ") : card.empty_trigger_note);
    const insert = h("button", { class: "btn small", type: "button", id: "loraInsertTriggers" }, "Put trigger words in the prompt");
    insert.onclick = async () => {
      const out = await api("/api/loras/workshop/prompt", { method: "POST", body: { name, prompt: promptBox.value, action: "triggers" } });
      promptBox.value = out.prompt;
      prompt = out.prompt;
      weightLine.textContent = "Weight file: " + out.weight;
      if (out.note) toast(out.note, "bad");
    };
    cardBox.append(
      h("h2", {}, card.title || "Usage card"),
      h("p", {}, card.author_notes || "No author notes on this file."),
      words,
      h("p", { id: "loraStrengths" }, "Model strength " + card.strength_model + ". Clip strength " + card.strength_clip + "."),
      h("div", { class: "usage-block" }, h("h3", {}, "Author recipe"), h("p", {}, card.author_recipe ? card.author_recipe.text : "No author recipe. Authorship is not verified.")),
      h("div", { class: "usage-block" }, h("h3", {}, "App suggestion"), h("p", {}, card.app_suggestion.text)),
      h("div", { class: "usage-block" }, h("h3", {}, "My tested preset"), h("p", { id: "loraPreset" }, card.tested_preset ? ("Model strength " + card.tested_preset.strength_model + ". Clip strength " + card.tested_preset.strength_clip + ". Seed " + card.tested_preset.seed + ".") : "No tested preset yet.")),
      insert);
    for (const example of card.examples || []) {
      const use = h("button", { class: "btn small", type: "button", id: "loraSamplePrompt" }, "Use this sample");
      use.onclick = async () => {
        const out = await api("/api/loras/workshop/prompt", { method: "POST", body: { name, action: "sample", example: 0 } });
        promptBox.value = out.prompt;
        prompt = out.prompt;
        weightLine.textContent = "Weight file: " + out.weight;
        sampleSource.textContent = out.label + " · " + out.source_id;
      };
      const sampleSource = h("p", { id: "loraSampleSource", class: "hint" }, example.label + " · " + example.source_id);
      cardBox.append(h("div", { class: "usage-block", id: "loraExample" }, h("h3", {}, example.label), h("p", {}, example.prompt), sampleSource, use));
    }
  }

  const stackBox = h("div", { id: "loraStackBody" });
  function drawStack() {
    stackBox.innerHTML = "";
    const choices = h("div", { class: "chips", id: "loraStackPicks" });
    for (const row of library.loras || []) {
      if (row.blocked) continue;
      const on = stack.includes(row.name);
      choices.append(h("button", { class: "chip" + (on ? " on" : ""), type: "button", onclick: () => {
        const at = stack.indexOf(row.name);
        if (at >= 0) stack.splice(at, 1); else stack.push(row.name);
        drawStack();
      } }, row.title || row.name));
    }
    const select = h("select", { id: "loraEngine", onchange: (e) => { engine = e.target.value; drawStack(); } });
    for (const row of limits.engines) select.append(h("option", { value: row.id, selected: row.id === engine }, row.label));
    stackBox.append(h("label", { class: "f" }, "Active engine"), select, h("label", { class: "f" }, "On this stack"), choices, h("div", { id: "loraConflict" }, "Checking the stack…"));
    refreshStack();
  }
  async function refreshStack() {
    const box = document.getElementById("loraConflict");
    if (!box) return;
    if (!stack.length) { box.innerHTML = ""; box.append(h("p", { class: "hint" }, "Add a LoRA to see the stack coach.")); return; }
    try {
      const report = await api("/api/loras/workshop/stack", { method: "POST", body: { names: stack, engine } });
      box.innerHTML = "";
      const first = (report.hard && report.hard[0]) || (report.soft && report.soft[0]);
      if (first) {
        box.append(h("div", { class: "conflict" + (report.blocked ? " hard" : ""), id: "loraConflictBanner" },
          h("h2", {}, "Conflict: " + first.text)));
      } else box.append(h("p", {}, "No conflict on this stack."));
      const coach = h("div", { class: "card", id: "loraCoach" }, h("h2", {}, "Stack coach"));
      for (const line of report.coach || []) coach.append(h("p", {}, line));
      if (first && first.id === "wan21_in_wan22_high") {
        coach.append(h("button", { class: "btn small", type: "button", id: "loraCoachDrop", onclick: () => {
          const name = first.name;
          const at = stack.indexOf(name);
          if (at >= 0) stack.splice(at, 1);
          drawStack();
        } }, "Take the Wan 2.1 LoRA off this stack"));
      }
      box.append(coach);
    } catch (e) { box.innerHTML = ""; box.append(h("div", { class: "err" }, e.message)); }
  }

  const benchBox = h("div", { id: "loraBenchmark" });
  const ageInput = h("input", { id: "loraBenchAge", class: "stated-age", type: "text", inputmode: "numeric", autocomplete: "off", placeholder: "Stated age" });
  const seedInput = h("input", { id: "loraSeed", type: "text", inputmode: "numeric", placeholder: "Seed" });
  ageInput.addEventListener("input", () => { age = ageInput.value.trim(); syncBench(); });
  seedInput.addEventListener("input", () => { seed = seedInput.value.trim(); syncBench(); });
  const benchButton = h("button", { class: "btn primary", type: "button", id: "loraRunBench" }, "Run the benchmark");
  function syncBench() {
    const whole = /^\d+$/.test(age) && +age >= 21 && /^\d+$/.test(seed) && !!weightName() && promptBox.value.trim();
    benchButton.disabled = !whole;
  }
  benchButton.onclick = async () => {
    benchBox.innerHTML = "";
    benchBox.append(h("p", {}, "Running on the mock engine. " + limits.mock_caption));
    try {
      const job = await api("/api/jobs", { method: "POST", body: { kind: "lora_benchmark", params: {
        name: weightName(), prompt: promptBox.value, stated_age: +age, seed: +seed } } });
      let latest = job;
      while (!["done", "error", "cancelled", "blocked_age_check_unavailable"].includes(latest.status)) {
        await new Promise(r => setTimeout(r, 400));
        latest = await api("/api/jobs/" + job.id);
      }
      if (latest.status !== "done") { benchBox.append(h("div", { class: "err" }, latest.error || latest.status)); return; }
      const grid = h("div", { class: "bench", id: "loraBenchGrid" });
      for (const item of latest.results || []) {
        const cap = (item.bench_triggers ? "With triggers" : "Without triggers") + " · " + item.bench_strength_model;
        const save = h("button", { class: "btn small", type: "button" }, "Save as my tested preset");
        save.onclick = async () => {
          await api("/api/loras/workshop/preset", { method: "POST", body: { name: weightName(), item: item.id } });
          toast("Saved on the usage card", "good");
          show("card");
        };
        grid.append(h("figure", {},
          h("img", { src: item.url, alt: limits.mock_caption }),
          h("figcaption", {}, cap, h("div", { class: "hint" }, "Seed " + item.bench_seed + " · clip UNKNOWN"), save)));
      }
      benchBox.innerHTML = "";
      benchBox.append(h("p", {}, "Same seed for every cell. " + limits.mock_caption), grid);
    } catch (e) { benchBox.append(h("div", { class: "err" }, e.message)); }
  };
  function drawBench() {
    ageInput.value = age;
    seedInput.value = seed;
    promptBox.value = prompt;
    syncBench();
  }

  const trainBox = h("div", { id: "loraTrainMe" });
  let trainKind = "character";
  let trainBase = "fast";
  let trainTrigger = "";
  let trainCaption = "linen shirt, warm sand";
  const chosenStills = new Set();
  function drawTrain() {
    trainBox.innerHTML = "";
    const ack = h("input", { id: "loraResumeAck", type: "checkbox", checked: resumeAck });
    ack.onchange = () => { resumeAck = ack.checked; };
    const triggerInput = h("input", { id: "loraTrigger", type: "text", value: trainTrigger, placeholder: "Trigger word" });
    triggerInput.addEventListener("input", () => { trainTrigger = triggerInput.value; });
    const captionInput = h("input", { id: "loraCaption", type: "text", value: trainCaption });
    captionInput.addEventListener("input", () => { trainCaption = captionInput.value; });
    const stillList = h("div", { id: "loraStills" }, "Loading stills this app made…");
    const meList = h("div", { id: "loraMeList" });
    trainBox.append(
      h("div", { class: "card note" },
        h("p", {}, limits.trainer_line),
        h("p", {}, limits.merge_line),
        h("p", {}, limits.spend_line),
        h("p", {}, limits.resume),
        h("p", {}, limits.face_check),
        h("p", {}, "Not in this version: drag-to-next-step, outfit try-on, a beach-day preset, a shot board, phase time estimates, a before/after slider, a defect hold, and Surprise me.")),
      h("div", { class: "card" },
        h("h2", {}, "Guided train"),
        h("p", {}, "Pick approved stills this app made, write a caption and a trigger, then train a character or a concept LoRA."),
        h("div", { class: "seg" },
          h("button", { type: "button", class: trainKind === "character" ? "on" : "", onclick: () => { trainKind = "character"; drawTrain(); } }, "Character"),
          h("button", { type: "button", class: trainKind === "concept" ? "on" : "", onclick: () => { trainKind = "concept"; drawTrain(); } }, "Concept")),
        h("label", { class: "f" }, "Base"),
        h("select", { id: "loraBase", onchange: (e) => { trainBase = e.target.value; } },
          ["fast", "photo", "anime", "video"].map(id => h("option", { value: id, selected: id === trainBase }, id === "fast" ? "Fast pictures" : id === "photo" ? "Realistic pictures" : id === "anime" ? "Anime pictures" : "Video"))),
        h("label", { class: "f" }, "Trigger"), triggerInput,
        h("label", { class: "f" }, "Caption"), captionInput,
        stillList,
        h("label", { class: "row" }, ack, h("span", {}, limits.resume)),
        h("p", { class: "hint" }, "Resume stays off. An inference LoRA is not a checkpoint you can resume."),
        h("button", { class: "btn", type: "button", id: "loraResume", disabled: true }, "Resume training"),
        h("button", { class: "btn primary", type: "button", id: "loraTrainGo", onclick: startTrain }, "Train")),
      h("div", { class: "card", id: "loraMe" },
        h("h2", {}, "Me"),
        h("p", {}, limits.me + " " + limits.me_sexual),
        h("p", { id: "loraMeClosed" }, limits.me_capture_only),
        meList));
    loadTrainLists(stillList, meList);
  }
  async function loadTrainLists(stillList, meList) {
    try {
      const rows = await api("/api/loras/workshop/stills");
      stillList.innerHTML = "";
      stillList.append(h("p", { class: "hint" }, rows.stills.length + " approved stills. Training needs at least " + rows.min + "."));
      for (const row of rows.stills) {
        const box = h("input", { type: "checkbox", checked: chosenStills.has(row.id) });
        box.onchange = () => { if (box.checked) chosenStills.add(row.id); else chosenStills.delete(row.id); };
        stillList.append(h("label", { class: "row" }, box, h("span", {}, (row.title || row.kind) + " · age " + row.stated_age)));
      }
    } catch (e) { stillList.textContent = e.message; }
    try {
      const me = await api("/api/loras/workshop/me");
      meList.innerHTML = "";
      meList.append(h("p", {}, "Photos: " + me.photos.length + ". Curated stills: " + me.stills.length + "."));
      if (me.avatar) meList.append(h("p", { id: "loraAvatar" }, "Player avatar is set. " + me.avatar.notice));
    } catch (e) { meList.textContent = e.message; }
  }
  async function startTrain() {
    if (!resumeAck) return toast(limits.resume, "bad");
    try {
      const chars = trainKind === "character" ? await api("/api/characters") : [];
      const body = { kind: trainKind, base: trainBase, trigger: trainTrigger, caption: trainCaption,
        items: [...chosenStills], resume_ack: "inference-lora-is-not-a-checkpoint" };
      if (trainKind === "character") body.character = (chars[0] || {}).id || "";
      if (trainKind === "concept") body.concept = trainTrigger || "shore light";
      const job = await api("/api/jobs", { method: "POST", body: { kind: "workshop_train", params: body } });
      toast("Training started", "good");
      return job;
    } catch (e) { toast(e.message, "bad"); }
  }
  panels.library.append(
    h("div", { class: "card" },
      h("h2", {}, "Add a LoRA"),
      h("label", { class: "row" }, h("input", { id: "loraConfirm", type: "checkbox", onchange: (e) => { tick = e.target.checked; drawLibrary(); } }),
        h("span", {}, "This LoRA is a style, a concept, or a fictional adult. It is not a real person, not a face-swap, and not someone under 21.")),
      drop, file,
      h("h3", {}, "Civitai link"), url,
      h("button", { class: "btn small", type: "button", id: "loraLookUp", onclick: lookUp }, "Look it up"),
      lookupBox,
      h("p", { class: "hint" }, limits.token)),
    list);
  panels.card.append(h("div", { class: "card", id: "loraUsageCard" }, weightLine, h("label", { class: "f" }, "Active prompt"), promptBox, cardBox));
  panels.stack.append(h("div", { class: "card" }, h("h2", {}, "Stack"), stackBox));
  panels.benchmark.append(h("div", { class: "card" },
    h("h2", {}, "Prompt benchmark"),
    h("p", {}, "One seed. With the trigger words, and without them. Model strengths 0.4, 0.6, 0.8, and 1.0. Clip strength stays UNKNOWN. These are test strengths, not a recommendation."),
    h("p", {}, limits.mock_caption + " No weights are downloaded."),
    h("label", { class: "f" }, "Stated age"), ageInput,
    h("label", { class: "f" }, "Seed"), seedInput,
    benchButton, benchBox));
  panels.train.append(trainBox);

  root.append(steps, panels.library, panels.card, panels.stack, panels.benchmark, panels.train);
  m.append(root);
  drawLibrary();
  show("library");
};
