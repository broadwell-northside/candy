// Improvement loop (v3): never print "null" when an optional part of a page is left out.
(function () {
  const ap = Element.prototype.append;
  Element.prototype.append = function (...kids) { return ap.apply(this, kids.filter(k => k !== null && k !== undefined && k !== false)); };
})();
/* Easy Studio 3 additions: the 18+ section, Video studio (any model), LoRA library, Train my character,
   Godot export, age-check badges and settings. Loaded after app.js; extends it. */
"use strict";

// ------------------------------------------------------------------ the 18+ section (area)
S.area = "default";
const _api0 = api;
const AREA_GET = /^\/api\/(gallery|loras|jobs|advanced\/options|train\/status)(\?|$)/;
api = async function (path, opts = {}) {
  if (S.area === "adult") {
    const o = { ...opts };
    if (o.body instanceof FormData) { if (!o.body.has("area")) o.body.append("area", "adult"); }
    else if (o.body && typeof o.body === "object" && /^\/api\/(jobs|loras\/civitai\/download)$/.test(path) && !o.body.area) o.body = { ...o.body, area: "adult" };
    if ((!o.method || o.method === "GET") && AREA_GET.test(path) && !/[?&]area=/.test(path)) path += (path.includes("?") ? "&" : "?") + "area=adult";
    opts = o;
  }
  try { return await _api0(path, opts); }
  catch (e) { if (/18\+ section is locked|SFW mode is on/.test(e.message) && S.area === "adult") setArea("default"); throw e; }
};
// One switch (PRD §7): area "adult" <=> SFW mode off. The server keeps the flag; this only asks it.
async function setSfw(on) {
  try { await _api0("/api/settings", { method: "POST", body: { sfw_mode: !!on } }); }
  catch (e) { toast(e.message, "bad"); return false; }
  setArea(on ? "default" : "adult");
  return true;
}
function setArea(a) {
  S.area = a === "adult" ? "adult" : "default";
  document.body.classList.toggle("area-adult", S.area === "adult");
  S.advOpts = null; S.loraLib = null;
  const b = $("#adultBtn");
  if (b) {
    b.textContent = S.area === "adult" ? "🔞 Leave 21+" : "🔞 21+";
    b.title = S.area === "adult" ? "SFW mode is off. Press to switch SFW mode back on." : "SFW mode is on. Press to open 21+ (fictional adults only).";
  }
  const bar = $("#adultBar");
  if (bar) bar.classList.toggle("hidden", S.area !== "adult");
  if (S.cat) go(S.tab);
}
async function adultGate() {
  let st;
  try { st = await api("/api/adult/status"); } catch (e) { return toast(e.message, "bad"); }
  if (st.unlocked) { await refreshCatalog(); return setSfw(false); }
  const first = !st.device_confirmed;
  let a1 = !first, a2 = !first;
  const pin = h("input", { type: "password", inputmode: "numeric", maxlength: 8, placeholder: st.pin ? "Your PIN" : "Optional: 4–8 digits", autocomplete: "off" });
  const goB = h("button", { class: "btn primary", disabled: first }, "Open 21+");
  const upd = () => { goB.disabled = !(a1 && a2) || (st.pin && !pin.value); };
  pin.oninput = upd;
  const body = h("div", {},
    h("h2", {}, "21+"),
    first ? h("div", {},
      h("p", { class: "hint" }, "A separate area with its own gallery for explicit pictures and videos of fictional adult characters. Asked once on this device."),
      h("label", { class: "row", style: { alignItems: "flex-start", margin: "10px 0" } }, h("input", { type: "checkbox", onchange: e => { a1 = e.target.checked; upd(); } }),
        h("span", {}, "I am 21 or older, and viewing adult content is legal where I am.")),
      h("label", { class: "row", style: { alignItems: "flex-start", margin: "10px 0" } }, h("input", { type: "checkbox", onchange: e => { a2 = e.target.checked; upd(); } }),
        h("span", {}, "I understand the rules still apply here: fictional adult characters only (21+), never real people or anyone I know, never minors, and the automatic checks stay on.")))
      : h("p", { class: "hint" }, "This device is already confirmed." + (st.pin ? " Type your PIN." : "")),
    (first || st.pin) ? h("div", {}, h("label", { class: "f" }, st.pin ? "PIN" : "PIN (optional — asked again every 12 hours)"), pin) : null,
    h("br"), goB);
  goB.onclick = async () => {
    const b = first ? { confirm_age: a1, confirm_rules: a2 } : {};
    if (st.pin) b.pin = pin.value; else if (pin.value) b.new_pin = pin.value;
    try { await api("/api/adult/unlock", { method: "POST", body: b }); closeModal(); await refreshCatalog(); await setSfw(false); toast("21+ open", "good"); }
    catch (e) { toast(e.message, "bad"); }
  };
  if (!first && !st.pin) { try { await api("/api/adult/unlock", { method: "POST", body: {} }); await refreshCatalog(); return setSfw(false); } catch (e) {} }
  modal(body, { gate: true });
  upd();
}
async function refreshCatalog() { try { S.cat = await api("/api/catalog"); } catch (e) {} }
const adultOn = () => S.area === "adult" && S.cat && S.cat.adult;
const motionsHere = () => S.cat.motions.concat(adultOn() ? S.cat.adult.motions : []);

(function topbar() {
  const b = h("button", { id: "adultBtn", class: "jobs-pill", title: "SFW mode is on. Press to open 21+ (fictional adults only).", onclick: () => S.area === "adult" ? setSfw(true) : adultGate() }, "🔞 21+");
  $("#jobsBtn").before(b);
  const bar = h("div", { id: "adultBar", class: "adult-bar hidden" },
    h("span", { class: "adult-label" }, "21+"),
    h("span", { class: "adult-bar-note" }, "separate gallery · fictional adults only · all safety checks on"),
    h("span", { class: "spacer" }),
    h("button", { class: "btn small", title: "Switch SFW mode back on", onclick: () => setSfw(true) }, "Leave"),
    h("button", { class: "btn small", onclick: async () => { await api("/api/adult/lock", { method: "POST" }); setArea("default"); toast("21+ locked"); } }, "🔒 Lock"));
  $(".layout").before(bar);
  $(".brand .ver").textContent = "3";
})();

// ------------------------------------------------------------------ new tabs
TABS.splice(TABS.findIndex(t => t[0] === "create") + 1, 0, ["workshop", "🌿", "Workshop"]);
TABS.splice(TABS.findIndex(t => t[0] === "video") + 1, 0, ["studio", "🎞️", "Video studio"]);
TABS.splice(TABS.findIndex(t => t[0] === "assets") + 1, 0, ["loras", "🧩", "LoRA library"], ["lora-workshop", "🌊", "LoRA workshop"], ["train", "🎓", "Train my character"]);

// One page of steps. The still step shows only the knobs that matter. The graph stays hidden.
VIEWS.workshop = async (m) => {
  const pack = (S.cat && S.cat.workshop) || { bodies: [], wardrobe: [], tradeoff: "", timing: "" };
  const person = { name: "", gender: "woman", style: "photo", age: null, ageSet: false, traits: {} };
  let saved = null;
  let madeStill = false;
  let stillId = null;
  let bodyId = null;
  let wardrobeId = (pack.wardrobe[0] && pack.wardrobe[0].id) || null;
  const ageWhy = h("div", { class: "hint action-why", id: "workshopAgeWhy" }, "Type an age of 21 or older. Nothing is filled in for you.");
  const ageInput = h("input", { id: "workshopAge", class: "stated-age", type: "text", inputmode: "numeric", autocomplete: "off",
    placeholder: "Type an age, 21 or older", title: "The character's stated age. Easy Studio does not guess." });
  const nameInput = h("input", { id: "workshopName", type: "text", maxlength: "60", placeholder: "Name (e.g. Mara)" });
  const lookInput = h("textarea", { id: "workshopLook", maxlength: "300", rows: "3",
    placeholder: "Olive skin, long dark hair, a linen shirt" });
  const ageShown = h("p", { id: "workshopAgeShown", class: "stated-age-shown" }, "");
  const savedLine = h("p", { id: "workshopSaved" }, "");
  const faceNote = h("p", { id: "workshopFaceNote", class: "hint" }, "");
  const res = resultsBox("A still shows up here.");
  res.id = "workshopResults";
  const wardrobeRow = h("div", { id: "workshopWardrobe", class: "chips" });
  function nudeChip() {
    if (!(typeof adultOn === "function" && adultOn()) || !S.cat || !S.cat.adult) return null;
    for (const cat of S.cat.adult.outfits || []) {
      for (const item of cat.items || []) if (item.id === "nude") return item;
    }
    return null;
  }
  function drawWardrobe() {
    const clothes = (pack.wardrobe || []).map(c => ({ id: c.id, label: c.label, p: c.p }));
    const nude = nudeChip();
    if (nude) clothes.push({ id: nude.id, label: nude.label, p: nude.p });
    if (!clothes.some(c => c.id === wardrobeId)) wardrobeId = clothes[0] ? clothes[0].id : null;
    wardrobeRow.innerHTML = "";
    for (const c of clothes) {
      const el = chipEl(c, wardrobeId === c.id, () => { wardrobeId = c.id; drawWardrobe(); });
      if (c.id === "nude") el.id = "workshopNude";
      wardrobeRow.append(el);
    }
  }
  const bodyRow = chips(pack.bodies || [], null, (id) => { bodyId = id; }, { optional: true });
  bodyRow.id = "workshopBody";
  const syncSave = () => {
    const ok = ageOk(person);
    saveBtn.disabled = !ok;
    saveBtn.title = ok ? "Save this fictional adult" : "Type an age of 21 or older. Easy Studio will not guess.";
  };
  ageInput.addEventListener("input", () => {
    const raw = ageInput.value.trim();
    const problem = ageProblem(raw);
    if (!problem && raw) { person.age = +raw; person.ageSet = true; }
    else { person.age = null; person.ageSet = false; }
    ageWhy.textContent = problem || (ageOk(person) ? "" : "Type an age of 21 or older. Nothing is filled in for you.");
    syncSave();
    if (sendBtn && sendBtn._sync) sendBtn._sync();
  });
  nameInput.addEventListener("input", () => { person.name = nameInput.value; });
  function savedAgeOk() { return !!(saved && Number.isInteger(saved.age) && saved.age >= 21); }
  async function savePerson() {
    if (!ageOk(person)) { toast("Type an age of 21 or older first. Easy Studio will not guess.", "bad"); return; }
    const body = { name: person.name || "New character", gender: person.gender, style: person.style, age: person.age, traits: {} };
    try {
      saved = await api("/api/characters", { method: "POST", body });
    } catch (e) { toast(e.message, "bad"); return; }
    madeStill = false;
    stillId = null;
    savedLine.textContent = "Saved " + saved.name + ".";
    ageShown.textContent = "Stated age: " + saved.age;
    faceNote.textContent = saved.look && saved.look.lora_id ? "This face is saved." : "";
    if (saved.look && saved.look.lora_id) madeStill = true;
    next.classList.remove("hidden");
    refine.classList.remove("hidden");
    drawWardrobe();
    if (stillBtn._sync) stillBtn._sync();
    if (keepBtn._sync) keepBtn._sync();
    if (skinBtn._sync) skinBtn._sync();
    if (anatomyBtn && anatomyBtn._sync) anatomyBtn._sync();
    if (sendBtn && sendBtn._sync) sendBtn._sync();
    toast("Saved", "good");
  }
  function rememberStill(job) {
    const it = job && job.results && job.results.find(row => row && !row.age_flag && row.age_check === "ok");
    if (job && job.status === "done" && it) {
      madeStill = true;
      stillId = it.id;
      if (keepBtn._sync) keepBtn._sync();
      if (skinBtn._sync) skinBtn._sync();
      if (anatomyBtn && anatomyBtn._sync) anatomyBtn._sync();
    }
  }
  async function makeStill() {
    if (!savedAgeOk()) { toast("Save a stated age of 21 or older first.", "bad"); return; }
    if (!wardrobeId) { toast("Pick clothes.", "bad"); return; }
    const params = { character: saved.id, look: lookInput.value.trim(), wardrobe: wardrobeId };
    if (bodyId) params.body = bodyId;
    await runJob("workshop_still", params, res, {
      key: "workshop", label: "Making a still", guided: true, onDone: rememberStill,
    });
  }
  async function keepFace() {
    if (!savedAgeOk() || !madeStill) { toast("Make a still of this person first.", "bad"); return; }
    await runJob("keep_face", { character: saved.id }, res, {
      key: "workshop-face", label: "Keeping this face", guided: true, onDone: (job) => {
        if (job && job.status === "done" && job.lora) {
          faceNote.textContent = "This face is saved.";
          saved.look = { lora_id: job.lora };
        }
      },
    });
  }
  async function refineSkin() {
    if (!savedAgeOk() || !(stillId || madeStill)) { toast("Make a still of this person first.", "bad"); return; }
    const params = { character: saved.id };
    if (stillId) params.source = stillId;
    await runJob("refine_skin", params, res, {
      key: "workshop-skin", label: "Refining skin", guided: true, onDone: (job) => {
        rememberStill(job);
        if (job && job.status === "done") skinStatus.textContent = "The second pass is done. This picture is generated. It is not a photograph.";
      },
    });
  }
  async function refineAnatomy() {
    if (!(typeof adultOn === "function" && adultOn())) { toast("Refine anatomy stays off until the 21+ switch is on.", "bad"); return; }
    if (!savedAgeOk() || !(stillId || madeStill)) { toast("Make a still of this person first.", "bad"); return; }
    const params = { character: saved.id };
    if (stillId) params.source = stillId;
    await runJob("refine_anatomy", params, res, {
      key: "workshop-anatomy", label: "Refining anatomy", guided: true, onDone: rememberStill,
    });
  }
  const saveBtn = bigButton("Save this person", savePerson);
  saveBtn.id = "workshopSave";
  const stillBtn = bigButton("Make a still", makeStill);
  stillBtn.id = "workshopStill";
  stillBtn.disabled = true;
  stillBtn._sync = () => { stillBtn.disabled = !savedAgeOk(); };
  const keepBtn = bigButton("Keep this face", keepFace);
  keepBtn.id = "workshopKeep";
  keepBtn.disabled = true;
  keepBtn._sync = () => { keepBtn.disabled = !(savedAgeOk() && madeStill); };
  const skinBtn = bigButton("Refine skin", refineSkin);
  skinBtn.id = "workshopSkin";
  skinBtn.disabled = true;
  skinBtn._sync = () => { skinBtn.disabled = !(savedAgeOk() && (stillId || madeStill)); };
  const skinStatus = h("p", { id: "workshopSkinStatus", class: "hint" }, "");
  const anatomyOn = typeof adultOn === "function" && adultOn();
  const anatomyBtn = anatomyOn ? bigButton("Refine anatomy", refineAnatomy) : null;
  if (anatomyBtn) {
    anatomyBtn.id = "workshopAnatomy";
    anatomyBtn.disabled = true;
    anatomyBtn._sync = () => { anatomyBtn.disabled = !(savedAgeOk() && (stillId || madeStill)); };
  }
  const refine = h("div", { id: "workshopRefine", class: "card hidden" },
    h("h2", {}, h("span", { class: "stepnum" }, "3"), "Refine"),
    h("p", { id: "workshopSkinCopy" }, "This is a light second pass of the same picture model. It can make skin a little clearer. It does not make a photograph. Hands and small shapes can still look wrong. A kept face stays on the slower picture model. The fast model does not keep the face."),
    h("p", { id: "workshopDetailerNote", class: "hint" }, "No extra detailer is loaded. An extra detailer stays off until a license card says private use is allowed. This step will not load that file until the card exists."),
    h("p", { id: "workshopCheckNote", class: "hint" }, "The check can miss a youthful result and can flag a young-looking adult. It is not a guarantee. If the check fails, times out, cannot see a face, or is unsure, the picture is held. A held picture cannot be reused, exported, or used for training."),
    skinBtn,
    skinStatus,
    anatomyBtn,
    anatomyOn ? h("p", { id: "workshopAnatomyCopy", class: "hint" }, "This uses Chroma, which is allowed for private use, and only while 21+ is open. No anatomy add-on is loaded. Those add-ons stay off until a license card says private use is allowed. This pass does not use the saved face, so the face can change. It does not remove clothes from an uploaded photo.") : null);
  function islandWhyText() {
    if (savedAgeOk()) return "";
    const raw = ageInput.value.trim();
    if (!raw) return "A missing age is not sent.";
    if (!/^\d+$/.test(raw)) return "That age is not a whole number, so this pack is not sent.";
    if (+raw < 21) return "That age is under 21, so this pack is not sent.";
    return "Save this person first.";
  }
  const islandWhy = h("p", { id: "workshopIslandWhy", class: "hint" }, "");
  const islandFile = h("div", { id: "workshopIslandFile" });
  async function sendIsland() {
    if (!savedAgeOk()) { toast("Save a stated age of 21 or older first. A missing age is not sent.", "bad"); return; }
    await runJob("export_godot", { character: saved.id }, res, {
      key: "workshop-island", label: "Sending to the island", guided: true,
      onDone: (job) => {
        islandFile.innerHTML = "";
        const it = job && job.results && job.results[0];
        if (job && job.status === "done" && it && it.url) {
          const file = (it.file || "pack.zip").split("/").pop();
          islandFile.append(h("a", { href: it.url, download: file }, "Download the pack"));
        }
      },
    });
  }
  const sendBtn = bigButton("Send to the island", sendIsland);
  sendBtn.id = "workshopSend";
  sendBtn.disabled = true;
  sendBtn._sync = () => {
    const ok = savedAgeOk();
    sendBtn.disabled = !ok;
    sendBtn.title = ok ? "Write the pack the island importer reads." : "Save a stated age of 21 or older first.";
    islandWhy.textContent = islandWhyText();
  };
  const island = h("div", { id: "workshopIsland", class: "card" },
    h("h2", {}, h("span", { class: "stepnum" }, "4"), "Send to the island"),
    h("p", { id: "workshopIslandNote" }, "This pack is what the island importer reads, and dropping it into the island is a separate game update."),
    islandWhy, sendBtn, islandFile);
  const next = h("div", { id: "workshopNext", class: "card hidden" },
    h("h2", {}, h("span", { class: "stepnum" }, "2"), "Make a still"),
    savedLine,
    h("p", { id: "workshopTradeoff" }, pack.tradeoff),
    h("p", { id: "workshopTiming", class: "hint" }, pack.timing),
    h("label", { class: "f" }, "Look"), lookInput,
    h("label", { class: "f" }, "Body"), bodyRow,
    h("label", { class: "f" }, "Stated age ", h("span", { class: "pillnote" }, "saved · not guessed")),
    ageShown,
    h("label", { class: "f" }, "Wardrobe"), wardrobeRow,
    stillBtn, keepBtn,
    h("p", { class: "hint" }, "Uses only stills this app made of this person."),
    faceNote);
  m.append(
    h("h1", {}, "Workshop"),
    h("p", { class: "sub" }, "One path for a fictional adult. State the age yourself."),
    h("div", { class: "cols" },
      h("div", {},
        h("div", { class: "card" },
          h("h2", {}, h("span", { class: "stepnum" }, "1"), "Person"),
          h("label", { class: "f" }, "Name"), nameInput,
          h("label", { class: "f" }, "Age ", h("span", { class: "pillnote" }, "21+ · not guessed")),
          ageInput, ageWhy, saveBtn),
        next,
        refine,
        island),
      res));
  drawWardrobe();
  syncSave();
  sendBtn._sync();
};

// ------------------------------------------------------------------ age-check badge on results
const _resultCard0 = resultCard;
resultCard = function (it, o = {}) {
  const card = _resultCard0(it, o);
  if (it.age_flag) {
    card.classList.add("flagged");
    $(".media", card).append(h("span", { class: "badge flag", title: "The automatic age check thought this may look under 21, so it can't be used." }, "⚠️ Hidden: may look under 21"));
    const fav = $(".fav", card);
    if (fav) fav.remove();
    for (const b of [...$(".actions", card).children]) if (b.tagName === "BUTTON" || b.tagName === "A") b.remove();
    $(".actions", card).append(h("div", { class: "hint" }, "Hidden because it may look under 21. It can't be downloaded, reused, or trained on."));
  } else if (it.area === "adult") $(".media", card).append(h("span", { class: "badge adult" }, "21+"));
  return card;
};

// ------------------------------------------------------------------ LoRA names in every Advanced drawer
async function loraLib() {
  if (!S.loraLib) { try { S.loraLib = await api("/api/loras"); } catch (e) { S.loraLib = { loras: [], families: {} }; } }
  return S.loraLib;
}
const _advanced0 = advanced;
advanced = function (key, o = {}) {
  const d = _advanced0(key, o);
  const label = async () => {
    const lib = await loraLib();
    const by = Object.fromEntries(lib.loras.map(r => [r.name, r]));
    for (const s of d.querySelectorAll("select")) {
      if (![...s.options].some(op => op.value.endsWith(".safetensors"))) continue;
      for (const op of s.options) { const r = by[op.value]; if (r) op.textContent = `${r.title} · ${r.family_label}${r.trigger_words?.length ? " · trigger: " + r.trigger_words[0] : ""}`; }
      if (!s._hint) {
        s._hint = h("div", { class: "hint" });
        s.parentElement.after(s._hint);
        const show = () => { const r = by[s.value]; s._hint.textContent = r && r.trigger_words?.length ? `Trigger word(s): ${r.trigger_words.join(", ")} — the app adds them to the prompt for you.` : ""; };
        s.addEventListener("change", show); show();
      }
    }
  };
  d.addEventListener("toggle", () => d.open && setTimeout(label, 300));
  if (d.open) setTimeout(label, 600);
  return d;
};

// ------------------------------------------------------------------ extra cards on existing screens
const _gallery0 = VIEWS.gallery;
VIEWS.gallery = async (m) => {
  await _gallery0(m);
  if (S.area === "adult") { const t = $("h1", m); t.textContent = "21+ gallery"; $(".sub", m).textContent = "Only what you made inside 21+. It never shows in the normal gallery."; }
};
const _assets0 = VIEWS.assets;
VIEWS.assets = async (m) => {
  await _assets0(m);
  let charId = S.chars[0]?.id || null;
  const res = $(".results", m);
  const card = h("div", { class: "card" }, h("h2", {}, "🎮 Export to Godot 4"),
    charStrip(charId, c => charId = c && c.id, { allowNew: false }), h("br"),
    bigButton("Export Godot project", () => { if (!charId) return toast("Pick a character.", "bad"); runJob("export_godot", { character: charId }, res, { label: "Making the Godot project" }); }),
    h("div", { class: "hint" }, "A ready Godot 4 folder: portraits, ⭐ favourites, sprite sheets split into frames + SpriteFrames (.tres) for AnimatedSprite2D, .glb models and .ogv videos for VideoStreamPlayer. Open project.godot in Godot."));
  const col = $(".cols > div", m);
  col && col.append(card);
};
const _setup0 = VIEWS.setup;
VIEWS.setup = async (m) => {
  await _setup0(m);
  const s = S.status || {};
  const ag = s.age_check || {};
  const col = $(".cols > div", m);
  const win = navigator.userAgent.includes("Windows");
  const ageToggle = h("input", { type: "checkbox", checked: !!ag.enabled, onchange: async e => {
    const on = e.target.checked;
    let body = { age_check: on };
    if (!on) { if (!confirm("Switch off the automatic age check? Create, video, train, and export will not run while it is off.")) { e.target.checked = true; return; } body.confirm = "I understand"; }
    try { await api("/api/settings", { method: "POST", body }); toast(on ? "Age check on" : "Age check off"); } catch (er) { toast(er.message, "bad"); e.target.checked = !on; }
  } });
  const pinBox = h("div");
  const drawPin = async () => {
    pinBox.innerHTML = "";
    const st = await api("/api/adult/status").catch(() => ({}));
    if (!st.unlocked) { pinBox.append(h("div", { class: "hint" }, "Open 21+ to set or change its PIN.")); return; }
    const oldp = h("input", { type: "password", placeholder: "Current PIN", maxlength: 8 }), newp = h("input", { type: "password", placeholder: "New PIN (blank = no PIN)", maxlength: 8 });
    pinBox.append(st.pin ? oldp : null, newp, h("button", { class: "btn small", onclick: async () => {
      try { await api("/api/adult/pin", { method: "POST", body: { old_pin: oldp.value, new_pin: newp.value } }); toast(newp.value ? "PIN saved" : "PIN removed", "good"); drawPin(); } catch (e) { toast(e.message, "bad"); } } }, "Save PIN"));
  };
  drawPin();
  const themeNow = () => {
    const v = store.get("theme", "match");
    return v === "light" || v === "dark" || v === "match" ? v : "match";
  };
  const applyTheme = (theme) => {
    const t = theme === "light" || theme === "dark" || theme === "match" ? theme : "match";
    document.documentElement.setAttribute("data-theme", t);
    store.set("theme", t);
  };
  col && col.append(
    h("div", { class: "card" }, h("h2", {}, "Appearance"),
      h("div", { class: "hint" }, "Light, Dark, or Match this computer. Match follows this device until you choose."),
      seg([["light", "Light"], ["dark", "Dark"], ["match", "Match this computer"]], themeNow(), applyTheme)),
    h("div", { class: "card" }, h("h2", {}, "🛡️ Automatic age check"),
      h("label", { class: "row" }, ageToggle, h("span", {}, "Check every new picture and video, and delete anything that may look under 21 (recommended)")),
      h("div", { class: "hint" }, ag.installed ? `Installed${ag.device ? " · runs on " + ag.device : ""}.` : "Not installed yet — run: " + (win ? ".venv\\Scripts\\python" : ".venv/bin/python") + " install/download_models.py --comfy ComfyUI --what safety"),
      h("div", { class: "hint" }, "It's a helper, not a guarantee: it can miss some faces (back views, some anime styles) and can wrongly flag young-looking adults. The word rules always apply too.")),
    h("div", { class: "card" }, h("h2", {}, "21+ PIN"), pinBox),
    h("div", { class: "card" }, h("h2", {}, "🎓 Character trainer"), s.trainer ? h("div", { class: "ok-box" }, "✓ Trainer (ai-toolkit) installed")
      : h("div", {}, h("div", { class: "hint" }, "Not installed yet. On the PC, in the Easy Studio folder, run:"), h("pre", {}, win ? "install\\install_trainer.bat" : "bash install/install_trainer.sh"))));
};

// ================================================================== 🎞️ Video studio (any model)
const MODE_TXT = { t2v: "Text → video", i2v: "Picture → video", ab: "Start → end (A to B)", extend: "Extend a video" };
VIEWS.studio = async (m) => {
  const res = resultsBox("Pick a model, give it a picture or words, press Make video.");
  let data;
  try { data = await api("/api/video/models"); } catch (e) { m.append(h("div", { class: "err" }, e.message)); return; }
  const all = data.models.concat(data.byo.map(b => ({ id: "byo:" + b.id, label: b.name, family: "your workflow", mode: b.mode, fps: b.fps, max_s: 10, ready: true, missing: [], byo: b, note: b.summary })));
  const st = { model: store.get("vs.model", "wan22_i2v"), start: null, end: null, from: null, text: "", motion: null, seconds: 5, quality: "fast", aspect: "landscape" };
  for (const x of all) if (x.mode === "flf2v") x.mode = "ab";  // server name for start + end picture
  if (!all.some(x => x.id === st.model)) st.model = all[0]?.id;
  const cur = () => all.find(x => x.id === st.model) || all[0];
  const adv = advanced("studio", { loras: true });
  const cards = h("div", { class: "model-cards" });
  const form = h("div");
  const pickBox = (label, key, o = {}) => {
    const box = h("div", { class: "working" });
    const draw = () => { const it = st[key]; box.innerHTML = "";
      box.append(h("div", { class: "thumb", style: it && it.type === "image" ? { backgroundImage: `url(${it.url})` } : {} }, it ? (it.type === "video" ? "🎬" : "") : (o.video ? "🎬" : "🖼️")),
        h("div", { class: "meta" }, it ? (it.title || it.kind) : label, h("div", { class: "row", style: { marginTop: "8px" } },
          h("button", { class: "btn small", onclick: async () => { const x = await pickFromGallery({ type: o.video ? "video" : "image", roles: ["made", "my_character"], title: label }); if (x) { st[key] = x; draw(); } } }, "Choose from gallery"),
          it ? h("button", { class: "btn small", onclick: () => { st[key] = null; draw(); } }, "✕") : null))); };
    if (!st[key]) st[key] = o.video ? S.currentVideo || null : (key === "start" ? S.current || null : null);
    draw(); return box;
  };
  const drawCards = () => {
    cards.innerHTML = "";
    for (const g of [["Ready to use", all.filter(x => x.ready)], ["Not installed yet", all.filter(x => !x.ready)]]) {
      if (!g[1].length) continue;
      cards.append(h("h3", {}, g[0]));
      for (const x of g[1]) cards.append(h("div", { class: "mcard" + (x.id === st.model ? " on" : "") + (x.ready ? "" : " off"), onclick: () => { st.model = x.id; store.set("vs.model", x.id); drawCards(); drawForm(); } },
        h("b", {}, x.label.split(" -- ")[0]), h("div", { class: "hint" }, `${MODE_TXT[x.mode] || x.mode} · ${x.family} · up to ${x.max_s}s · ${x.fps} fps`),
        x.ready ? null : h("div", { class: "hint warnt" }, "Missing: " + x.missing.slice(0, 2).join(", ") + (x.missing.length > 2 ? "…" : "") + " — see ⚙️ Setup"),
        x.byo ? h("button", { class: "btn small", onclick: async e => { e.stopPropagation(); if (!confirm("Remove this workflow?")) return; await api("/api/byo/" + x.byo.id, { method: "DELETE" }); go("studio"); } }, "Remove") : null));
    }
  };
  const drawForm = () => {
    const x = cur(); form.innerHTML = "";
    if (!x) return;
    const secLbl = h("b", {}, st.seconds + " s");
    const desc = h("textarea", { rows: 3, placeholder: x.mode === "t2v" ? "e.g. a fictional adult woman in a leather jacket walks through neon rain at night" : "e.g. she smiles and turns to the camera", title: "Plain words. Fictional adults only.", oninput: e => st.text = e.target.value }, st.text);
    st.seconds = Math.min(st.seconds, x.max_s);
    form.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), MODE_TXT[x.mode] || "Video"),
      x.note ? h("div", { class: "hint" }, x.note) : null,
      x.mode === "i2v" || x.mode === "ab" ? pickBox("Start picture", "start") : null,
      x.mode === "ab" ? pickBox("End picture (the clip ends here)", "end") : null,
      x.mode === "extend" || x.mode === "i2v" ? h("details", { open: x.mode === "extend" }, h("summary", {}, "…or continue an existing video"), pickBox("Video to continue", "from", { video: true })) : null,
      x.mode === "t2v" ? h("div", {}, h("label", { class: "f" }, "Shape"), seg([["landscape", "▭ Wide"], ["portrait", "▯ Tall"], ["square", "□ Square"]], st.aspect, v => st.aspect = v)) : null,
      h("label", { class: "f" }, "Motion"), chips(catX("motions"), st.motion, v => st.motion = v),
      h("label", { class: "f" }, "Describe it" + (x.mode === "t2v" ? "" : " (optional)")),
      desc, promptHelper(desc, { limit: 400, unit: "characters" }),
      h("label", { class: "f" }, "Length ", secLbl), h("input", { type: "range", min: 2, max: x.max_s, step: 1, value: st.seconds, oninput: e => { st.seconds = +e.target.value; secLbl.textContent = st.seconds + " s"; } }),
      h("div", { class: "row", style: { marginTop: "10px" } }, seg([["fast", "⚡ Fast"], ["best", "💎 Best"]], st.quality, v => st.quality = v)),
      h("br"), bigButton("🎞️ Make video", () => {
        if (!x.ready) return toast("This model isn't installed yet — see ⚙️ Setup.", "bad");
        const p = { model: x.id, motion: st.motion, text: st.text, seconds: st.seconds, quality: st.quality, aspect: st.aspect, advanced: adv.get() };
        if (st.from && (x.mode === "extend" || x.mode === "i2v")) p.extend_from = st.from.id;
        else if (x.mode === "i2v" || x.mode === "ab") { if (!st.start) return toast("Pick a start picture.", "bad"); p.start = st.start.id; }
        if (x.mode === "ab") { if (!st.end) return toast("Pick an end picture.", "bad"); p.end = st.end.id; }
        if (x.mode === "extend" && !p.extend_from) return toast("Pick a video to continue.", "bad");
        runJob("video_any", p, res, { key: "studio", label: x.label.split(" -- ")[0] + ": making the video", onDone: j => j.results[0] && setCurrent(j.results[0], false) });
      }),
      h("div", { class: "hint estimate" }, x.ready ? "A short clip. Usually a few minutes. Bigger models take longer." : "This model isn't installed yet, so Make video stays off. Open Setup for the download."),
      adv));
    const make = form.querySelector("button.btn.primary");
    if (make && !x.ready) {
      make.disabled = true;
      make.title = "This model isn't installed yet. Open Setup to see the download command.";
      make._sync = () => { make.disabled = true; };
    }
  };
  const file = h("input", { type: "file", accept: ".json,application/json", style: { display: "none" } });
  const paste = h("textarea", { rows: 3, placeholder: "…or paste the workflow JSON here" });
  const nm = h("input", { type: "text", placeholder: "Name, e.g. My Wan 2.2 workflow" });
  const doImport = async (text) => {
    let wf; try { wf = JSON.parse(text); } catch (e) { return toast("That isn't a ComfyUI workflow file (JSON).", "bad"); }
    try { const r = await api("/api/byo", { method: "POST", body: { name: nm.value || "My workflow", workflow: wf } }); toast(`Imported: ${MODE_TXT[r.mode] || r.mode} — ${r.summary || ""}`, "good"); go("studio"); }
    catch (e) { toast(e.message, "bad"); }
  };
  file.onchange = async () => file.files[0] && doImport(await file.files[0].text());
  const byo = h("div", { class: "card" }, h("h2", {}, "➕ Use your own ComfyUI video workflow"),
    h("div", { class: "hint" }, "Export any video workflow from ComfyUI (normal or API format). Easy Studio finds the prompt, picture, length and seed boxes by itself, then it appears here like any other model."),
    nm, h("div", { class: "row", style: { margin: "8px 0" } }, h("button", { class: "btn", onclick: () => file.click() }, "📂 Choose workflow file"), file),
    paste, h("button", { class: "btn small", onclick: () => paste.value.trim() && doImport(paste.value) }, "Import pasted workflow"));
  drawCards(); drawForm();
  m.append(h("h1", {}, "Video studio"), h("p", { class: "sub" }, "Any video model: pick one, give it words or pictures, done. Big models are optional downloads."),
    h("div", { class: "cols" }, h("div", {}, h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "1"), "Model"), cards), form, byo), res));
};

// ================================================================== 🧩 LoRA library
VIEWS.loras = async (m) => {
  S.loraLib = null;
  const lib = await loraLib();
  const list = h("div", { class: "grid lora-grid" });
  let tick = false;
  const famSel = (r) => h("select", { onchange: e => save(r, { base: e.target.value }) }, Object.entries(lib.families).map(([k, v]) => h("option", { value: k, selected: r.family === k }, v)));
  const save = async (r, ch) => { try { await api("/api/loras", { method: "PATCH", body: { name: r.name, ...ch } }); S.loraLib = null; toast("Saved", "good"); } catch (e) { toast(e.message, "bad"); go("loras"); } };
  const draw = () => {
    list.innerHTML = "";
    if (!lib.loras.length) list.append(h("div", { class: "empty" }, h("span", { class: "big" }, "🧩"), "No LoRAs yet. Drop a .safetensors file above, or paste a Civitai link."));
    for (const r of lib.loras) {
      const known = r.strength_known === true;
      const sLbl = h("b", {}, known ? Number(r.strength).toFixed(2) : "UNKNOWN");
      const trig = h("input", { type: "text", value: (r.trigger_words || []).join(", "), placeholder: "trigger words (comma separated)", disabled: !lib.folder || r.source?.includes("ComfyUI") });
      trig.onchange = () => save(r, { trigger_words: trig.value.split(",").map(s => s.trim()).filter(Boolean) });
      list.append(h("div", { class: "card lora" + (r.blocked ? " blocked" : "") },
        h("div", { class: "lthumb", style: r.thumb_url ? { backgroundImage: `url(${r.thumb_url})` } : {} }, r.thumb_url ? "" : "🧩"),
        h("div", { class: "lbody" },
          h("b", {}, r.title), r.area === "adult" ? h("span", { class: "badge adult" }, "21+") : null, r.character ? h("span", { class: "badge" }, "🎓 trained") : null,
          h("div", { class: "hint" }, r.name + (r.size_mb ? ` · ${r.size_mb} MB` : "") + (r.source ? ` · ${r.source}` : "")),
          r.blocked ? h("div", { class: "err" }, "🚫 Blocked: " + r.blocked_reason) : h("div", {},
            h("label", { class: "f" }, "Works with"), lib.folder && r.source !== "another ComfyUI folder" ? famSel(r) : h("div", {}, h("div", { class: "hint" }, r.family_label || r.family), h("div", { class: "hint" }, "Locked because this file sits in ComfyUI's own folder. You can still pick it under Advanced settings.")),
            h("label", { class: "f" }, "Trigger words"), trig,
            trig.disabled ? h("div", { class: "hint" }, "Trigger words are locked for this file. Easy Studio still adds them when you use the LoRA.") : null,
            h("label", { class: "f" }, known ? "Saved strength " : "Strength ", sLbl),
            known ? h("input", { type: "range", min: -1, max: 2, step: 0.05, value: r.strength, disabled: !lib.folder,
              oninput: e => sLbl.textContent = (+e.target.value).toFixed(2), onchange: e => save(r, { strength: +e.target.value }) })
              : h("div", { class: "hint" }, "UNKNOWN. No strength was saved, and this is not a recommendation."),),
          lib.folder && r.source !== "another ComfyUI folder" ? h("button", { class: "btn small", onclick: async () => { if (!confirm(`Move "${r.title}" to the trash?`)) return; await api("/api/loras?name=" + encodeURIComponent(r.name), { method: "DELETE" }); go("loras"); } }, "🗑 Remove") : null)));
    }
  };
  const upload = async (files) => {
    if (!tick) return toast("Tick the box first: not a real person, not a child.", "bad");
    for (const f of files) {
      const fd = new FormData(); fd.append("file", f); fd.append("confirm", "yes");
      try { const r = await api("/api/loras/upload", { method: "POST", body: fd }); toast(`Added ${r.title} (${r.family_label})`, "good"); }
      catch (e) { toast(f.name + ": " + e.message, "bad"); }
    }
    go("loras");
  };
  const inp = h("input", { type: "file", accept: ".safetensors", multiple: true, style: { display: "none" }, onchange: e => upload([...e.target.files]) });
  const drop = h("div", { class: "dropzone", onclick: () => inp.click() }, "⬇ Drop .safetensors LoRA files here, or click to choose");
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); upload([...e.dataTransfer.files]); };
  const url = h("input", { type: "text", placeholder: "https://civitai.com/models/…" });
  const key = h("input", { type: "password", placeholder: "Civitai API key (only for gated / adult downloads — never saved)", autocomplete: "off" });
  const civ = h("div");
  const look = async () => {
    civ.innerHTML = "Looking it up…";
    let info; try { info = await api("/api/loras/civitai/lookup", { method: "POST", body: { url: url.value, api_key: key.value } }); } catch (e) { civ.innerHTML = ""; civ.append(h("div", { class: "err" }, e.message)); return; }
    civ.innerHTML = "";
    const showThumb = info.thumb_url && (!info.thumb_adult || S.area === "adult");
    civ.append(h("div", { class: "working" }, h("div", { class: "thumb", style: showThumb ? { backgroundImage: `url(${info.thumb_url})` } : {} }, showThumb ? "" : "🧩"),
      h("div", { class: "meta" }, h("b", {}, info.name), ` · ${info.version || ""}`, h("br"), `${info.base || "?"} · ${info.size_mb} MB`,
        info.trigger_words?.length ? h("div", { class: "hint" }, "Trigger: " + info.trigger_words.join(", ")) : null,
        info.nsfw ? h("div", { class: "hint" }, "Civitai marks this as adult — it goes to 21+.") : null,
        info.early_access ? h("div", { class: "hint" }, "Early access on Civitai — needs your own account / key.") : null,
        info.ok ? null : h("div", { class: "err" }, "🚫 " + info.reason))));
    if (!info.ok) return;
    if (info.nsfw && S.area !== "adult") { civ.append(h("div", { class: "err" }, "Open 21+ to add this one.")); return; }
    const prog = h("div", { class: "hint" });
    civ.append(h("button", { class: "btn primary", onclick: async () => {
      if (!tick) return toast("Tick the box first: not a real person, not a child.", "bad");
      try { const d = await api("/api/loras/civitai/download", { method: "POST", body: { url: url.value, api_key: key.value, confirm: "yes" } });
        const poll = async () => { const all = await api("/api/loras/downloads"); const x = all.find(y => y.id === d.id) || {};
          prog.textContent = x.status === "downloading" ? `Downloading… ${Math.round((x.progress || 0) * 100)}%` : x.status === "done" ? "✓ Added" : "⚠️ " + (x.error || x.status);
          if (x.status === "downloading") setTimeout(poll, 1000); else if (x.status === "done") { S.loraLib = null; setTimeout(() => go("loras"), 800); } };
        poll();
      } catch (e) { toast(e.message, "bad"); } } }, "⬇ Add to my library"), prog);
  };
  m.append(h("h1", {}, S.area === "adult" ? "LoRA library (21+)" : "LoRA library"),
    h("p", { class: "sub" }, "LoRAs add a style, a look or a trained character. Add them here once; then pick them in any Advanced drawer (pictures and videos). Their trigger words are added for you."),
    lib.folder ? "" : h("div", { class: "err" }, "Easy Studio can't see ComfyUI's LoRA folder on this PC, so it only lists what ComfyUI reports. Start Easy Studio with the start script (it sets COMFY_DIR) to add, edit or remove LoRAs."),
    h("div", { class: "cols" }, h("div", {},
      h("div", { class: "card" }, h("h2", {}, "Add LoRAs"),
        h("label", { class: "row", style: { alignItems: "flex-start", margin: "6px 0 10px" } }, h("input", { type: "checkbox", onchange: e => tick = e.target.checked }),
          h("span", {}, "These LoRAs are not of a real person (no celebrities, no one I know) and not of a child or teen-looking character.")),
        drop, inp,
        h("h3", {}, "From Civitai"), url, key, h("button", { class: "btn small", style: { marginTop: "6px" }, onclick: look }, "🔎 Look it up"), civ,
        h("div", { class: "hint" }, "Easy Studio refuses LoRAs of real people, of minors, of face-swaps, and files Civitai has taken down. A future Civitai token is an op:// reference. It is not printed and it is not stored here."))),
      h("div", {}, list)));
  draw();
};

// ================================================================== 🎓 Train my character
VIEWS.train = async (m) => {
  await loadChars();
  let charId = store.get("train.char", S.chars[0]?.id || null);
  if (!S.chars.some(c => c.id === charId)) charId = S.chars[0]?.id || null;
  const res = resultsBox("Pick a character, make training pictures, then train.");
  const body = h("div");
  const draw = async () => {
    body.innerHTML = "";
    if (!charId) { body.append(h("div", { class: "empty" }, "Create and save a character first (✨ Create → Save as character).")); return; }
    let st; try { st = await api(`/api/train/status?character=${encodeURIComponent(charId)}`); } catch (e) { body.append(h("div", { class: "err" }, e.message)); return; }
    const ch = S.chars.find(c => c.id === charId) || {};
    const chosen = new Set(st.pictures.map(p => p.id));
    const count = h("b", {}, `${chosen.size} picked`);
    const grid = h("div", { class: "grid small" });
    for (const p of st.pictures.concat(st.other_pictures.filter(x => x.role === "made" || x.role === "my_character"))) {
      const cb = h("input", { type: "checkbox", checked: chosen.has(p.id), onchange: e => { e.target.checked ? chosen.add(p.id) : chosen.delete(p.id); count.textContent = `${chosen.size} picked`; } });
      grid.append(h("label", { class: "res pick" }, h("div", { class: "media" }, h("img", { src: p.url, loading: "lazy" })), h("div", { class: "row" }, cb, h("span", { class: "hint" }, p.caption ? p.caption.replace("[trigger]", st.trigger || "").slice(0, 60) : p.kind))));
    }
    let n = 20, base = ch.style === "anime" ? "anime" : "photo";
    const problems = [];
    if (!st.installed) problems.push(h("div", {}, "The trainer isn't installed yet. On the PC run ", h("code", {}, navigator.userAgent.includes("Windows") ? "install\\install_trainer.bat" : "bash install/install_trainer.sh")));
    if (!st.age_check.installed || !st.age_check.enabled) problems.push(h("div", {}, "Training needs the automatic age check installed and switched on (⚙️ Setup)."));
    if (!st.lora_folder) problems.push(h("div", {}, "Easy Studio can't see ComfyUI's LoRA folder (start it with the start script)."));
    body.append(
      problems.length ? h("div", { class: "card warnbox" }, h("h2", {}, "Before you can train"), ...problems) : null,
      h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "Training pictures"),
        h("div", { class: "hint" }, `Easy Studio makes ${st.min}–24 varied shots of ${ch.name || "your character"} from her portrait (angles, close-ups, outfits, places, light) and writes a caption for each. Trigger word: `, h("b", {}, st.trigger || "?")),
        h("div", { class: "row" }, h("label", {}, "How many "), h("select", { onchange: e => n = +e.target.value }, [12, 16, 20, 24].map(x => h("option", { value: x, selected: x === n }, x))),
          bigButton("📸 Make training pictures", () => runJob("train_dataset", { character: charId, count: n }, res, { key: "train_ds", label: "Making training pictures", onDone: () => draw() }))),
        h("div", { class: "row" }, count, h("span", { class: "hint" }, " · untick any that don't look like her")), grid),
      h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Train"),
        h("label", { class: "f" }, "What is the LoRA for?"),
        seg(Object.entries(st.bases).map(([k, v]) => [k, v.label]), base, v => base = v),
        h("div", { class: "hint" }, "Pictures take about 30–60 min on your RTX PRO 6000; the video LoRA (Wan 2.2) takes a few hours. ComfyUI pauses while it trains."),
        h("br"), bigButton("🎓 Train", () => {
          if (chosen.size < st.min) return toast(`Pick at least ${st.min} pictures.`, "bad");
          runJob("train_lora", { character: charId, base, items: [...chosen] }, res, { key: "train", label: "Training (this takes a while — you can keep using the app)", onDone: () => { S.loraLib = null; draw(); } });
        })),
      h("div", { class: "card" }, h("h2", {}, "Her LoRAs"), st.loras.length ? h("div", {}, st.loras.map(r => h("div", { class: "row" }, "🧩 ", h("b", {}, r.title), h("span", { class: "hint" }, ` · trigger ${(r.trigger_words || [])[0] || ""} · ${r.family_label}`))),
        h("div", { class: "hint" }, "Pick it in any Advanced drawer → LoRA. Its trigger word is added for you.")) : h("div", { class: "hint" }, "None yet.")));
  };
  m.append(h("h1", {}, "Train my character"), h("p", { class: "sub" }, "Teach the models one character so she looks the same in every picture and video."),
    h("div", { class: "card note" }, "🛡️ Training only uses characters made in Easy Studio, or your own drawn / 3D-rendered fictional art (uploaded with the “my own fictional art” tick). It never trains on photos of real people — including yourself. That's deliberate: a LoRA of a real person would let anyone make nude pictures of them. Every training picture is age-checked again just before training."),
    h("div", { class: "cols" }, h("div", {}, h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "1"), "Character"), charStrip(charId, c => { charId = c && c.id; store.set("train.char", charId); draw(); }, { allowNew: false })), body), res));
  draw();
};

// Improvement loop (v3): Esc closes any open window, and switching tabs closes it too.
if (S.cat && typeof nav === "function") {
  const wanted = store.get("tab", S.tab);
  if (wanted && VIEWS[wanted] && (wanted !== S.tab || !$("#nav [data-tab='studio']"))) go(wanted, { fromPop: true });
  else nav();
}
document.addEventListener("keydown", e => {
  if (e.key === "Escape") { const m = document.getElementById("modal"); if (m && !m.classList.contains("hidden")) { const x = m.querySelector(".modal-x"); if (x) x.click(); } }
});
(function () {
  const _go = window.go;
  if (typeof _go === "function") window.go = function (...a) { const m = document.getElementById("modal"); if (m && !m.classList.contains("hidden")) { const x = m.querySelector(".modal-x"); if (x) x.click(); } return _go.apply(this, a); };
})();
// One switch (PRD §7): after the 21+ attestation the studio opens in full 21+ mode; SFW stays one press away.
(async function sfwOnLoad() {
  try { const st = await _api0("/api/settings"); if (st && st.sfw_mode === false && S.area !== "adult") setArea("adult"); } catch (e) {}
})();
