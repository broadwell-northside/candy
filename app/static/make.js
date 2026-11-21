/* PRIVATE BUILD — NOT FOR DISTRIBUTION
   Easy Studio home: three calm doors, Make · Play · Library, and a Settings gear (PRD §9).
   Make opens Recipes (the Graphic Workflow Editor, PRD §5). The 12 Classic tools stay, unchanged,
   behind one "Classic tools" link at the bottom of Make. Loaded after app.js, lora_workshop.js and v3.js. */
"use strict";

const DOORS = ["home", "make", "recipe", "play", "library"];

// The new home is shown first once after this version, even when the browser remembers an old tab.
(function doorsOnce() {
  try {
    if (!store.get("doors.v", 0)) {
      store.set("doors.v", 1);
      if (!(location.hash || "").replace(/^#\/?/, "")) { S.tab = "home"; store.set("tab", "home"); }
    }
  } catch (e) {}
})();

// Classic tools keep their sidebar; the doors hide it. Every Classic screen gets a "⌂ Home" button.
(function () {
  const nav0 = nav;
  nav = function () {
    nav0();
    const doors = DOORS.includes(S.tab);
    document.body.classList.toggle("doors", doors);
    const n = $("#nav");
    if (!doors && n && !$("#nav [data-tab='home']")) {
      n.prepend(h("button", { "data-tab": "home", class: "home-link", title: "Back to Make · Play · Library", onclick: () => go("home") },
        h("span", { class: "ic" }, "⌂"), "Home"), h("div", { class: "sep" }));
    }
  };
})();

function door(id, icon, title, words) {
  return h("button", { class: "door", id: "door-" + id, type: "button", onclick: () => go(id) },
    h("span", { class: "door-ic" }, icon), h("span", { class: "door-title" }, title), h("span", { class: "door-words" }, words));
}

VIEWS.home = (m) => {
  m.append(
    h("div", { class: "home-head" },
      h("div", {}, h("h1", {}, "Easy Studio"), h("p", { class: "sub" }, "Make pictures and short films, play the island, or look through what you made.")),
      h("button", { class: "btn small gear", id: "homeGear", title: "Setup: model downloads, the self-test and switches", onclick: () => go("setup") }, "⚙️ Setup")),
    h("div", { class: "doors-grid" },
      door("make", "🎨", "Make", "Recipes for a portrait still, a film from a still, or a pack for the island."),
      door("play", "🏝️", "Play", "Stillwater, the island. The door puzzle on the beach, and Edit this place."),
      door("library", "🖼️", "Library", "Everything you made and kept.")),
    h("p", { class: "hint" }, "Fictional adults only, 21 and over. Nothing here is a real person."));
};

let RCAT = null;
// Like api(), but a refusal keeps the stage it belongs to, so the message shows under that stage.
async function apiStage(path, body) {
  let r;
  try { r = await fetch(path, { method: "POST", headers: { "X-Easy-Studio": "1", "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch (e) { throw new Error("Can't reach Easy Studio. Check that this computer is on and the text window that started Easy Studio is still open."); }
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (!r.ok) { const err = new Error(j.error || (typeof j.detail === "string" && j.detail) || `Error ${r.status}`); err.stage = j.stage || ""; throw err; }
  return j;
}
async function recipeCatalogue(force) {
  if (!RCAT || force) RCAT = await api("/api/recipes");
  return RCAT;
}

VIEWS.make = async (m) => {
  m.append(h("h1", {}, "Make"), h("p", { class: "sub" }, "Pick a recipe. Each one is a short form; the stages always run in the same order."));
  let cat;
  try { cat = await recipeCatalogue(true); } catch (e) { m.append(h("div", { class: "err" }, e.message)); return; }
  const grid = h("div", { class: "recipe-grid" });
  for (const r of cat.recipes) {
    grid.append(h("button", { class: "recipe-card", type: "button", "data-recipe": r.id, onclick: () => openRecipe(r.id) },
      h("span", { class: "door-ic" }, r.icon), h("b", {}, r.label), h("span", { class: "hint" }, r.blurb),
      h("span", { class: "uses" }, "Uses: " + r.uses.map(s => cat.stages.find(x => x.id === s).label).join(" · "))));
  }
  const file = h("input", { type: "file", accept: ".json,.esrecipe.json,.png", class: "hidden", id: "recipeImportFile" });
  file.onchange = () => importRecipe(file.files[0]);
  m.append(grid,
    h("div", { class: "card make-tools" },
      h("h2", {}, "Bring a recipe back"),
      h("p", { class: "hint" }, "Open a .esrecipe.json you exported. A ComfyUI graph from elsewhere is only looked at: Easy Studio lists its missing models and nodes and never turns it into stages."),
      h("button", { class: "btn small", onclick: () => file.click() }, "📂 Open a recipe or graph"), file,
      h("div", { id: "importReport" })),
    h("div", { class: "classic-link" },
      h("button", { class: "btn small", id: "classicTools", title: "The 12 tools from before: Create, My characters, Wardrobe, Pose, Scene, Objects, Photoshoot, Video, 3D, Game assets, Gallery, Advanced, Setup", onclick: () => go("create") }, "🧰 Classic tools")));
}

async function importRecipe(f) {
  const box = $("#importReport");
  if (!f || !box) return;
  box.innerHTML = "";
  const fd = new FormData();
  fd.append("file", f);
  try {
    const res = await api("/api/recipes/import" + (S.area === "adult" ? "?area=adult" : ""), { method: "POST", body: fd });
    if (res.kind === "own") {
      box.append(h("p", { class: res.matches ? "ok-note" : "err" }, res.matches
        ? "This recipe rebuilds the same graph it was exported with (hash " + res.canonical_hash.slice(0, 12) + "…)."
        : "This recipe rebuilds a different graph than it was exported with. The saved character or still may have changed."),
        h("button", { class: "btn small", onclick: () => { S.recipeDoc = res.recipe; S.recipeId = res.recipe.recipe; go("recipe"); } }, "Open it"));
    } else {
      const r = res.report || {};
      box.append(h("p", { class: "hint" }, res.note || ""),
        h("p", {}, "Node types: " + ((r.node_types || []).join(", ") || "none")),
        r.missing_node_types && r.missing_node_types.length ? h("p", { class: "err" }, "Not installed here: " + r.missing_node_types.join(", ")) : null,
        r.models && r.models.length ? h("p", {}, "Models it names: " + r.models.join(", ")) : null,
        r.refused_nodes && r.refused_nodes.length ? h("p", { class: "err" }, "Refused here: " + r.refused_nodes.join(", ")) : null,
        h("p", { class: "hint" }, r.can_run_as_raw ? "It can run as a raw graph from Classic tools → Advanced." : "It cannot run as a raw graph."));
    }
  } catch (e) { box.append(h("div", { class: "err" }, e.message)); }
}

function blankRecipe(id) {
  return { recipe: id, name: "", order: ["subject", "look", "pose", "scene", "camera", "quality", "output"], stages: {}, seed: null };
}

function openRecipe(id, preset) {
  S.recipeId = id;
  S.recipeDoc = blankRecipe(id);
  if (preset) for (const [sid, values] of Object.entries(preset)) S.recipeDoc.stages[sid] = { on: true, values: { ...values } };
  S.recipeNew = null;
  go("recipe");
}

function stageState(doc, spec, sid) {
  if (!doc.stages[sid]) doc.stages[sid] = { on: spec.uses.includes(sid) && !["pose", "scene"].includes(sid), values: {} };
  if (sid === "subject") doc.stages[sid].on = true;
  return doc.stages[sid];
}

VIEWS.recipe = async (m) => {
  let cat;
  try { cat = await recipeCatalogue(); } catch (e) { m.append(h("div", { class: "err" }, e.message)); return; }
  const spec = cat.recipes.find(r => r.id === S.recipeId) || cat.recipes[0];
  if (!S.recipeDoc || S.recipeDoc.recipe !== spec.id) S.recipeDoc = blankRecipe(spec.id);
  const doc = S.recipeDoc;
  const errors = {};
  const head = h("div", { class: "row recipe-head" },
    h("button", { class: "btn small", onclick: () => go("make") }, "← Make"),
    h("h1", {}, spec.icon + " " + spec.label));
  const form = h("div", { class: "stages" });
  const res = h("div", { class: "results", id: "recipeResults" });
  const phase = h("p", { class: "hint phase" });
  const drawer = h("pre", { class: "node-drawer hidden", id: "nodeDrawer" });
  const drawerBtn = h("button", { class: "btn small", id: "nodeDrawerToggle", title: "Read only. Editing graphs is a later decision.",
    onclick: () => { drawer.classList.toggle("hidden"); drawerBtn.textContent = drawer.classList.contains("hidden") ? "For experts: show the graph (read only)" : "Hide the graph"; } },
    "For experts: show the graph (read only)");
  let chars = [], stillsList = [];
  try { chars = (await api("/api/characters")).filter(c => !c.real_person && !c.player_only && c.identity !== "player_me"); } catch (e) {}
  if (spec.id === "one_actor_film") {
    try { stillsList = ((await api("/api/gallery?type=image&limit=60")).items || []).filter(it => it.role === "made" && !it.age_flag && (it.kind === "still" || it.kind.startsWith("edit"))); } catch (e) {}
  }

  const draw = () => {
    form.innerHTML = "";
    cat.stages.forEach((st, i) => form.append(stageBlock(st, i + 1)));
  };

  function stageBlock(st, n) {
    const sid = st.id;
    const used = spec.uses.includes(sid);
    const state = stageState(doc, spec, sid);
    const box = h("section", { class: "stage" + (used ? "" : " unused") + (used && !state.on ? " off" : ""), "data-stage": sid, title: st.tip });
    const toggle = h("input", { type: "checkbox", checked: state.on, disabled: sid === "subject" || !used, title: sid === "subject" ? "Subject is always on" : "Switch this stage on or off" });
    toggle.onchange = () => { state.on = toggle.checked; draw(); };
    const presetBtn = used && sid !== "subject" ? h("button", { class: "btn small ghost", title: "Save this stage's choices to use again", onclick: () => savePreset(sid, state.values) }, "Save as preset") : null;
    box.append(h("div", { class: "stage-head" }, h("span", { class: "stepnum" }, String(n)), h("b", {}, st.label),
      h("span", { class: "hint stage-tip" }, used ? ((spec.tips || {})[sid] || st.tip) : (spec.unused[sid] || "This recipe does not use this stage.")),
      h("span", { class: "spacer" }), presetBtn, used ? h("label", { class: "switch" }, toggle, h("span", {}, state.on ? "On" : "Off")) : null));
    if (errors[sid]) box.append(h("div", { class: "err stage-err" }, errors[sid]));
    if (!used) return box;
    const presets = ((cat.presets || {})[spec.id] || {})[sid] || {};
    if (Object.keys(presets).length) box.append(h("div", { class: "chips presets" }, Object.entries(presets).map(([name, vals]) =>
      h("span", { class: "chip", onclick: () => { state.values = { ...vals }; state.on = true; draw(); } }, "⭐ " + name))));
    if (!state.on) return box;
    const v = state.values;
    const body = h("div", { class: "stage-body" });
    const pick = (list, key, opts = {}) => chips(list.map(x => ({ id: x.id, label: x.label })), v[key] || (opts.def || null), val => { if (val) v[key] = val; else delete v[key]; draw(); }, { optional: !opts.required });
    if (spec.fixed[sid]) body.append(h("p", { class: "fixed" }, spec.fixed[sid]));
    if (sid === "subject" && spec.id !== "one_actor_film") {
      body.append(h("label", { class: "f" }, "Saved fictional adult ", h("span", { class: "needed" }, "needed")),
        chips(chars.map(c => ({ id: c.id, label: `${c.name} · ${c.age}` })), v.character || null, val => { if (val) { v.character = val; S.recipeNew = null; } else delete v.character; draw(); }));
      if (spec.id === "portrait_still") {
        const nw = S.recipeNew || (S.recipeNew = { name: "", gender: null, age: "" });
        const age = h("input", { type: "number", class: "stated-age", id: "recipeAge", min: 21, step: 1, inputmode: "numeric", placeholder: "Type an age, 21 or older", value: nw.age });
        age.oninput = () => { nw.age = age.value; };
        const nm = h("input", { type: "text", id: "recipeName", placeholder: "Name (optional)", maxlength: 60, value: nw.name });
        nm.oninput = () => { nw.name = nm.value; };
        body.append(h("details", { class: "new-adult", open: !v.character },
          h("summary", {}, "Or a new fictional adult"),
          h("div", { class: "row" }, nm),
          h("label", { class: "f" }, "Gender ", h("span", { class: "needed" }, "needed")),
          chips((S.cat.genders || []).map(g => ({ id: g.id, label: g.label })), nw.gender, val => { nw.gender = val; if (val) delete v.character; draw(); }),
          h("label", { class: "f" }, "Stated age ", h("span", { class: "needed" }, "needed")), age,
          h("p", { class: "hint" }, "Typed by you and saved with this character. There is no default and it is never guessed.")));
      }
    }
    if (sid === "subject" && spec.id === "one_actor_film") {
      body.append(h("label", { class: "f" }, "A still you kept ", h("span", { class: "needed" }, "needed")));
      const strip = h("div", { class: "still-strip" });
      for (const it of stillsList.slice(0, 24)) {
        strip.append(h("button", { class: "still-pick" + (v.still === it.id ? " on" : ""), "data-still": it.id, title: it.title || it.kind, onclick: () => { v.still = it.id; draw(); } },
          h("img", { src: it.url, alt: "kept still", loading: "lazy" })));
      }
      if (!stillsList.length) strip.append(h("p", { class: "hint" }, "No kept stills yet. Make a portrait still first."));
      body.append(strip);
      if (v.still) body.append(shotStrip(v.still));
    }
    if (sid === "look") {
      body.append(h("label", { class: "f" }, "Clothes ", h("span", { class: "needed" }, "needed")), pick(cat.wardrobe, "wardrobe", { required: true }),
        h("label", { class: "f" }, "Body"), pick(cat.bodies.map(b => ({ id: b, label: b.replace(/_/g, " ") })), "body"));
      const look = h("input", { type: "text", maxlength: cat.look_limit, placeholder: "A few words about the look (optional)", value: v.look || "" });
      look.oninput = () => { if (look.value.trim()) v.look = look.value; else delete v.look; };
      body.append(look);
    }
    if (sid === "pose") body.append(spec.id === "one_actor_film" ? pick(cat.motions, "motion") : pick(cat.poses, "pose"));
    if (sid === "scene") body.append(pick(cat.scenes, "scene"));
    if (sid === "camera") {
      const list = spec.id === "one_actor_film" ? cat.camera_moves : cat.cameras;
      body.append(pick(list, "camera", { def: (list.find(x => x.default) || {}).id }), h("p", { class: "hint" }, "This is the one stage with a default."));
    }
    if (sid === "output") {
      if (spec.id === "one_actor_film") body.append(h("label", { class: "f" }, "Length ", h("span", { class: "needed" }, "needed")),
        chips(cat.seconds.map(n => ({ id: String(n), label: n + " seconds" })), v.seconds ? String(v.seconds) : null, val => { if (val) v.seconds = Number(val); else delete v.seconds; draw(); }));
      if (spec.id !== "send_to_island") {
        const seed = h("input", { type: "number", id: "recipeSeed", min: 0, step: 1, placeholder: "Seed: blank picks one for you", value: doc.seed === null || doc.seed === undefined ? "" : doc.seed });
        seed.oninput = () => { doc.seed = seed.value === "" ? null : seed.value; };
        body.append(h("label", { class: "f" }, "Seed"), seed);
        if (S.recipeSeedUsed) body.append(h("p", { class: "hint", id: "seedUsed" }, "Seed used: " + S.recipeSeedUsed));
      }
    }
    box.append(body);
    return box;
  }

  async function savePreset(sid, values) {
    const name = prompt("Name this preset");
    if (!name) return;
    try { await api("/api/recipes/preset", { method: "POST", body: { recipe: spec.id, stage: sid, values, name } }); toast("Preset saved", "good"); RCAT = null; cat = await recipeCatalogue(true); draw(); }
    catch (e) { toast(e.message, "bad"); }
  }

  async function ensureSubject() {
    const sub = stageState(doc, spec, "subject");
    if (spec.id !== "portrait_still" || sub.values.character) return true;
    const nw = S.recipeNew || {};
    if (!nw.gender || !String(nw.age || "").trim()) { errors.subject = "Pick a saved fictional adult, or pick a gender and type an age for a new one."; draw(); return false; }
    try {
      const saved = await api("/api/characters", { method: "POST", body: { name: nw.name || "", gender: nw.gender, age: Number(nw.age), style: "photo" } });
      sub.values.character = saved.id;
      S.recipeNew = null;
      return true;
    } catch (e) { errors.subject = e.message; draw(); return false; }
  }

  async function compile() {
    for (const k of Object.keys(errors)) delete errors[k];
    if (!(await ensureSubject())) return null;
    try {
      const out = await apiStage("/api/recipes/compile", { recipe: doc, area: S.area });
      doc.seed = out.recipe.seed;
      S.recipeSeedUsed = out.recipe.seed;
      drawer.textContent = out.graph ? JSON.stringify(out.graph, null, 1) : "This recipe has no ComfyUI graph: " + (out.note || "");
      return out;
    } catch (e) {
      const stage = (e.stage || (/needs|Pick clothes|wardrobe/i.test(e.message) ? "look" : "subject"));
      errors[stage] = e.message;
      draw();
      return null;
    }
  }

  async function make(fresh) {
    if (fresh) { doc.seed = null; S.recipeSeedUsed = null; }
    const out = await compile();
    if (!out) return;
    draw();
    phase.textContent = out.phase + (out.process ? ` · runs on ${out.process.label} (port ${out.process.port})` : "");
    if (out.cached && !fresh) {
      res.innerHTML = "";
      res.append(h("p", { class: "hint" }, "Already made with exactly these choices. Here it is."), resultCard(out.cached, {}),
        h("button", { class: "btn small", onclick: () => make(true) }, "Make it again with a new seed"));
      afterResult({ results: [out.cached], status: "done" }, out);
      return;
    }
    const job = await runJob(out.kind, out.params, res, { label: out.phase, recipe: { cache_key: out.cache_key, canonical_hash: out.canonical_hash, name: spec.label } });
    if (job) afterResult(job, out);
  }

  function afterResult(job, out) {
    if (job.status !== "done" || !job.results || !job.results.length) return;
    const it = job.results[0];
    const next = h("div", { class: "row next-steps" });
    if (spec.id === "portrait_still" && it.type === "image") {
      next.append(h("button", { class: "btn small", id: "sendToFilm", onclick: () => { openRecipe("one_actor_film", { subject: { still: it.id } }); } }, "🎬 Make a film from this"),
        h("button", { class: "btn small", id: "sendToIsland", onclick: () => { openRecipe("send_to_island", { subject: { character: it.character } }); } }, "🏝️ Send to the island"));
      const prev = (S.recipePrevStill || {})[it.character];
      if (prev && prev.id !== it.id) next.append(h("button", { class: "btn small", onclick: () => modal(h("div", {}, h("h2", {}, "Before and after"), compareEl(prev, it)), { wide: true }) }, "↔ Compare with the last one"));
      S.recipePrevStill = { ...(S.recipePrevStill || {}), [it.character]: it };
    }
    if (spec.id === "one_actor_film") {
      next.append(h("button", { class: "btn small", onclick: async () => {
        const src = await api("/api/items/" + doc.stages.subject.values.still).catch(() => null);
        if (src) modal(h("div", { class: "compare-pair" }, h("h2", {}, "The still and the film"), h("div", { class: "row" }, mediaEl(src, false), mediaEl(it, false))), { wide: true });
      } }, "↔ Compare with the still"));
    }
    if (spec.id === "send_to_island" && it.type === "zip") {
      const box = h("div", { id: "islandCheck" });
      next.append(h("button", { class: "btn small", id: "islandDryRun", onclick: async () => {
        box.innerHTML = "";
        const ch = chars.find(c => c.id === doc.stages.subject.values.character) || {};
        try {
          const r = await api("/api/island/dry-run", { method: "POST", body: { item: it.id, character: (ch.name || "guest").toLowerCase().replace(/[^a-z0-9_]/g, ""), area: S.area } });
          box.append(h("p", { class: r.project_godot_unchanged ? "ok-note" : "err" }, r.message),
            h("p", { class: "hint" }, `Would copy ${r.summary.portraits} portrait(s) and ${r.summary.videos} clip(s) for “${r.character}”, stated age ${r.summary.stated_age}.`));
        } catch (e) { box.append(h("div", { class: "err" }, e.message)); }
      } }, "🔍 Check it against the island (dry run)"), box);
    }
    res.append(next);
  }

  function shotStrip(stillId) {
    const strip = h("div", { class: "shot-strip", title: "The still and the films made from it" }, h("span", { class: "hint" }, "Shot strip: "));
    api("/api/gallery?limit=200").then(({ items = [] }) => {
      const src = items.find(x => x.id === stillId);
      if (src) strip.append(h("img", { src: src.url, alt: "source still" }));
      for (const f of items.filter(x => x.parent === stillId && x.type === "video").slice(0, 6)) strip.append(h("video", { src: f.url, muted: true, preload: "metadata" }));
    }).catch(() => {});
    return strip;
  }

  const exportBtn = h("button", { class: "btn small", id: "recipeExport", onclick: async () => {
    if (!(await ensureSubject())) return;
    try {
      const out = await apiStage("/api/recipes/export", { recipe: doc, area: S.area });
      const a = h("a", { href: URL.createObjectURL(new Blob([out.text], { type: "application/json" })), download: out.filename });
      document.body.append(a); a.click(); a.remove();
      toast("Saved " + out.filename + " to this computer", "good");
    } catch (e) { toast(e.message, "bad"); }
  } }, "⬇️ Export recipe");

  const makeBtn = bigButton("Make it", () => make(false));
  makeBtn.id = "recipeMake";
  draw();
  m.append(head, h("p", { class: "sub" }, spec.blurb), form,
    h("div", { class: "card recipe-actions" }, makeBtn, phase, h("div", { class: "row" }, exportBtn, drawerBtn), drawer), res);
};

VIEWS.library = async (m) => {
  await VIEWS.gallery(m);
  const t = $("h1", m);
  if (t) t.textContent = S.area === "adult" ? "Library (21+)" : "Library";
};

VIEWS.play = async (m) => {
  m.append(h("h1", {}, "Play"), h("p", { class: "sub" }, "Stillwater, the private island. It runs in Godot on this Mac."));
  let st = {};
  try { st = await api("/api/island/status"); } catch (e) {}
  m.append(
    h("div", { class: "card" }, h("h2", {}, "🏝️ Open the island"),
      st.game_here ? h("p", {}, "The island folder is on this computer. Open it with Godot 4: ", h("code", {}, "godot --path game")) : h("p", { class: "hint" }, "The island folder (game/) is not on this computer."),
      h("p", { class: "hint" }, "The 21+ gate is asked once. After it, the island is in full 21+ mode; SFW mode is one switch in its Settings.")),
    h("div", { class: "card" }, h("h2", {}, "🚪 The door puzzle on the beach"),
      h("p", {}, "Two pressure pads and a brass key. You hold one pad, your companion holds the other, and she sets the key in the door. Do them in any order; the door opens when both are true."),
      h("p", { class: "hint" }, st.puzzle ? "The puzzle file is in place and its hash is checked when the island loads it." : "The puzzle file is missing.")),
    h("div", { class: "card", id: "editPlace" }, h("h2", {}, "✏️ Edit this place"),
      h("p", {}, "In the island, on the beach, press E (or the Edit this place button). Move the pads, the door and the key on the sand, then Save draft. The draft is used on your next visit."),
      h("p", { class: "hint" }, "To keep a draft as the real level, run this once on the Mac. It checks the draft with the one level checker and writes the file and its hash:"),
      h("pre", {}, "python3 game/tools/puzzle_level.py promote")));
};
