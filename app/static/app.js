/* Easy Studio 2 -- the whole web page. Plain JavaScript, no build step. */
"use strict";

// ------------------------------------------------------------------ tiny helpers
const $ = (s, el = document) => el.querySelector(s);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat(9)) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : document.createTextNode(c));
  return el;
}
async function api(path, opts = {}) {
  const o = { ...opts };
  o.headers = { "X-Easy-Studio": "1", ...(o.headers || {}) };
  if (o.body && !(o.body instanceof FormData)) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(o.body); }
  let r;
  try { r = await fetch(path, o); }
  catch (e) { throw new Error("Can't reach Easy Studio. Check that this computer is on and the text window that started Easy Studio is still open."); }
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(j.error || (typeof j.detail === "string" && j.detail) || ({ 401: "Please reload the page and type the password (it's in outputs/password.txt on this computer).",
    413: "That file is too big.", 500: "Something went wrong inside Easy Studio. Try again; if it repeats, restart it." }[r.status] || `Error ${r.status}`));
  return j;
}
function toast(msg, kind = "") {
  const t = h("div", { class: "toast " + kind }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "bad" ? 9000 : 4500);
}
const store = {
  get(k, d) { try { const v = localStorage.getItem("es." + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("es." + k, JSON.stringify(v)); } catch (e) {} },
};
function seg(options, value, onChange) {
  const el = h("div", { class: "seg" });
  const draw = () => { el.innerHTML = ""; for (const [v, label] of options) el.append(h("button", { class: v === value ? "on" : "", onclick: () => { value = v; draw(); onChange(v); } }, label)); };
  draw();
  return el;
}
function chipEl(c, on, onclick) {
  return h("span", { class: "chip" + (on ? " on" : "") + (c.swatch ? " swatch" : ""), onclick, title: c.p || c.label },
    c.swatch ? h("span", { class: "sw", style: { background: c.swatch } }) : null, c.icon ? c.icon + " " : "", c.label);
}
/** chips(list, value, onChange, {multi, optional}) */
function chips(list, value, onChange, o = {}) {
  const el = h("div", { class: "chips" });
  let cur = o.multi ? [...(value || [])] : value;
  const draw = () => {
    el.innerHTML = "";
    for (const c of list) {
      const on = o.multi ? cur.includes(c.id) : cur === c.id;
      el.append(chipEl(c, on, () => {
        if (o.multi) cur = on ? cur.filter(x => x !== c.id) : [...cur, c.id];
        else cur = on && o.optional !== false ? null : c.id;
        draw(); onChange(cur);
      }));
    }
  };
  draw();
  return el;
}
const fmtTime = t => new Date(t * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

// ------------------------------------------------------------------ state
const S = {
  cat: null, status: null, chars: [], tab: store.get("tab", "home"),
  current: null,      // the "working picture" shared by every tool
  currentVideo: null, // the "working video"
  dna: store.get("dna", null), advOpts: null, lastJob: {},
};

function catX(k) {  // the normal lists, plus the 18+ extras while inside the 18+ section
  const b = S.cat[k] || [];
  return S.area === "adult" && S.cat.adult && S.cat.adult[k] ? b.concat(S.cat.adult[k]) : b;
}
const TABS = [
  ["create", "✨", "Create"], ["characters", "👥", "My characters"], "-",
  ["wardrobe", "👗", "Wardrobe"], ["pose", "🧍", "Pose"], ["scene", "🏞️", "Scene & background"], ["objects", "🪄", "Add objects"],
  ["photoshoot", "📸", "Photoshoot"], "-",
  ["video", "🎬", "Video"], ["3d", "🧊", "3D model"], ["assets", "🎮", "Game assets"], "-",
  ["gallery", "🖼️", "Gallery"], ["advanced", "🛠️", "Advanced"], ["setup", "⚙️", "Setup"],
];

function nav() {
  const n = $("#nav");
  n.innerHTML = "";
  for (const t of TABS) {
    if (t === "-") { n.append(h("div", { class: "sep" })); continue; }
    n.append(h("button", { class: S.tab === t[0] ? "active" : "", "data-tab": t[0], title: t[2], onclick: () => go(t[0]) },
      h("span", { class: "ic" }, t[1]), t[2]));
  }
}
function go(tab, opts = {}) {
  S.tab = tab; store.set("tab", tab); nav();
  if (!opts.fromPop) {
    const url = "#/" + tab;
    if (location.hash !== url) history.pushState({ tab }, "", url);
  }
  const m = $("#main"); m.innerHTML = "";
  const need = { create: ["create_photo"], wardrobe: ["edit", "paint"], pose: ["edit", "pose_read", "pose_new"], scene: ["edit", "remove_bg"],
    objects: ["edit"], photoshoot: ["edit"], video: ["video"], "3d": ["model3d"], assets: ["turnaround", "upscale", "remove_bg"] }[tab] || [];
  const off = S.status && S.status.comfy_up ? S.status.features.filter(f => need.includes(f.id) && !f.ready) : [];
  if (S.status && !S.status.comfy_up && need.length) m.append(h("div", { class: "warn-bar", onclick: () => go("setup") }, "⚠️ The engine (ComfyUI) isn't running, so buttons won't work yet. Start Easy Studio with the start script. ", h("u", {}, "Details")));
  else if (off.length) m.append(h("div", { class: "warn-bar", onclick: () => go("setup") }, `⚠️ Not installed yet: ${off.map(f => f.label).join(", ")}. `, h("u", {}, "Open Setup to get it")));
  const fail = e => { console.error(e); m.append(h("div", { class: "err" }, "This screen failed to draw: " + e.message)); };
  try { Promise.resolve((VIEWS[tab] || VIEWS.home || VIEWS.create)(m)).catch(fail); } catch (e) { fail(e); }
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ status + jobs tray
async function refreshStatus() {
  try {
    S.status = await api("/api/status");
    const p = $("#statusPill");
    const ready = S.status.features.filter(f => f.ready).length;
    if (!S.status.comfy_up) { p.className = "status-pill bad"; p.textContent = "● Engine offline"; }
    else { p.className = "status-pill ok"; p.textContent = `● Ready · ${ready}/${S.status.features.length} tools`; }
    p.onclick = () => go("setup");
  } catch (e) { $("#statusPill").textContent = "● App offline"; $("#statusPill").className = "status-pill bad"; }
}
async function refreshJobs() {
  try {
    const jobs = await api("/api/jobs");
    const active = jobs.filter(j => j.status === "queued" || j.status === "running");
    $("#jobsCount").textContent = active.length;
    const p = $("#jobsPanel");
    if (!p.classList.contains("hidden")) {
      p.innerHTML = "";
      p.append(h("h2", {}, "Jobs"));
      if (!jobs.length) p.append(h("div", { class: "hint" }, "No jobs yet. Start one from Create, Wardrobe, or Video. This list shows the queue."));
      for (const j of jobs.slice(0, 20)) p.append(h("div", { class: "jobrow" },
        h("b", {}, KIND_NAME[j.kind] || j.kind), " · ", j.status === "blocked_age_check_unavailable" ? "held" : j.status, j.status === "running" ? ` ${Math.round(j.progress * 100)}%` : "",
        h("div", { class: "hint" }, j.error ? j.error.slice(0, 180) : (j.message || "")),
        (j.status === "running" || j.status === "queued") ? h("button", { class: "btn small", title: "Stop this job. A queued job stops at once. A running job stops as soon as the current step can.", onclick: () => api(`/api/jobs/${j.id}/cancel`, { method: "POST" }).then(refreshJobs) }, "Stop") : null));
    }
  } catch (e) {}
}
$("#jobsBtn").title = "Jobs and queue. See what is running, and stop a job.";
$("#jobsBtn").onclick = () => { $("#jobsPanel").classList.toggle("hidden"); refreshJobs(); };
const KIND_NAME = {
  create: "Create pictures", edit: "Edit picture", inpaint: "Paint a change", outfit_locked: "Keep the body",
  video: "Video", video_any: "Video studio", extend: "Extend video", video_still: "Save a still",
  model3d: "3D model", prop: "3D prop", photoshoot: "Photoshoot", pose_new: "New pose", pose_extract: "Read a pose",
  remove_bg: "Cut out", bg_quick: "Swap background", upscale: "Upscale", turnaround: "Turnaround",
  expressions: "Expressions", sprites: "Sprite sheet", export: "Export pack", export_godot: "Godot export",
  train_dataset: "Training pictures", train_lora: "Train character", workshop_still: "Make a still",
  keep_face: "Keep this face", refine_skin: "Refine skin", refine_anatomy: "Refine anatomy", raw: "Your workflow",
  regenerate: "Another picture", contact_repair: "Still edit", film: "Make a short film",
};

// ------------------------------------------------------------------ modal
function modal(content, { wide, gate } = {}) {
  const m = $("#modal"), body = $(".modal-body", m);
  body.innerHTML = ""; body.append(content);
  const box = $(".modal-box", m);
  box.style.width = wide ? "min(1100px,96vw)" : "";
  box.classList.toggle("gate", !!gate);
  m.classList.remove("hidden");
  return new Promise(res => {
    const close = v => { m.classList.add("hidden"); body.innerHTML = ""; res(v); };
    $(".modal-x", m).onclick = () => close(null);
    m.onclick = e => { if (e.target === m) close(null); };
    m._close = close;
  });
}
const closeModal = v => $("#modal")._close && $("#modal")._close(v);

// ------------------------------------------------------------------ uploads (role + confirmation)
const ROLES = {
  my_character: ["My fictional character", "This is a fictional ADULT character (21+) that I created, drew or 3D-rendered myself. It is NOT a photo of a real person — not even of me. It may be edited and used for training."],
  clothing: ["Clothing / outfit picture", "It shows clothing (or a fictional character). It's only used as an outfit reference -- the person in it is not copied."],
  object: ["Object / prop picture", "It shows an object or prop, not a real person. It's only used as a reference."],
  background: ["Background / place", "It shows a place or background with no real people in it."],
  pose_ref: ["Pose reference", "Only the stick-figure pose is read from it; the picture itself is never used or shown to a model."],
};
function sceneryDialog() {
  let file = null, ok = false;
  const go = h("button", { id: "sceneryGo", class: "btn primary", type: "button", disabled: true }, "Upload");
  const refuse = h("div", { id: "sceneryRefuse", class: "err hidden" });
  const check = () => { go.disabled = !(file && ok); };
  const box = h("div", {},
    h("h2", {}, "Upload a place photo"),
    h("p", { class: "hint" }, "A photo is a place, not a person. It cannot be a character, a face swap, or a clothing-removal edit."),
    h("input", { id: "sceneryFile", type: "file", accept: "image/png,image/jpeg,image/webp", onchange: e => { file = e.target.files[0]; check(); } }),
    h("label", { class: "row", style: { margin: "14px 0", alignItems: "flex-start" } },
      h("input", { id: "sceneryOk", type: "checkbox", onchange: e => { ok = e.target.checked; check(); } }),
      h("span", {}, "This photo is a place, not a person. It is not a character, a face swap, or a clothing-removal edit.")),
    refuse, h("br"), go);
  go.onclick = async () => {
    go.disabled = true; go.textContent = "Uploading…";
    refuse.classList.add("hidden"); refuse.textContent = "";
    const fd = new FormData();
    fd.append("file", file); fd.append("role", "scenery"); fd.append("confirm", "yes");
    try { closeModal(await api("/api/upload", { method: "POST", body: fd })); }
    catch (e) {
      refuse.textContent = e.message;
      refuse.classList.remove("hidden");
      go.disabled = false; go.textContent = "Upload";
    }
  };
  return modal(box);
}
function uploadDialog(role) {
  let file = null, ok = false;
  const go = h("button", { class: "btn primary", disabled: true }, "Upload");
  const ageInput = role === "my_character"
    ? h("input", { class: "stated-age", type: "text", inputmode: "numeric", autocomplete: "off", placeholder: "Type the character's age" })
    : null;
  const check = () => { go.disabled = !(file && ok); };
  const box = h("div", {},
    h("h2", {}, "Upload: " + ROLES[role][0]),
    h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", onchange: e => { file = e.target.files[0]; check(); } }),
    ageInput ? h("label", { class: "f" }, "Stated age (21+)", ageInput, h("div", { class: "hint" }, "Type the character's stated age. Nothing is guessed.")) : null,
    h("label", { class: "row", style: { margin: "14px 0", alignItems: "flex-start" } },
      h("input", { type: "checkbox", onchange: e => { ok = e.target.checked; check(); } }),
      h("span", {}, ROLES[role][1])),
    h("div", { class: "hint" }, "No real people, no minors, no faces of anyone you know. Uploads stay on your PC."), h("br"), go);
  go.onclick = async () => {
    go.disabled = true; go.textContent = "Uploading…";
    const fd = new FormData(); fd.append("file", file); fd.append("role", role); fd.append("confirm", "yes");
    if (ageInput) fd.append("age", ageInput.value.trim());
    try { closeModal(await api("/api/upload", { method: "POST", body: fd })); }
    catch (e) { toast(e.message, "bad"); go.disabled = false; go.textContent = "Upload"; }
  };
  return modal(box);
}

// ------------------------------------------------------------------ gallery picker
async function pickFromGallery({ type = "image", roles = null, title = "Pick a picture" } = {}) {
  const g = await api(`/api/gallery?type=${type}&limit=400`);
  let items = g.items;
  if (roles) items = items.filter(i => roles.includes(i.role));
  const grid = h("div", { class: "grid small" });
  if (!items.length) grid.append(h("div", { class: "empty" }, h("span", { class: "big" }, "🖼️"), "Nothing here yet."));
  for (const it of items) grid.append(h("div", { class: "res", onclick: () => closeModal(it), style: { cursor: "pointer" } },
    h("div", { class: "media" + (it.alpha ? " checker" : "") }, mediaEl(it, true), it.role !== "made" ? h("span", { class: "badge" }, it.role) : null)));
  return modal(h("div", {}, h("h2", {}, title), grid), { wide: true });
}

// ------------------------------------------------------------------ media + result cards
function mediaEl(it, thumb) {
  if (it.type === "video") return h("video", { src: it.url, muted: true, loop: true, playsinline: true, autoplay: !thumb, controls: !thumb, preload: "metadata", onmouseenter: e => thumb && e.target.play(), onmouseleave: e => thumb && e.target.pause() });
  if (it.type === "model") return thumb ? h("div", { style: { height: "160px", display: "grid", placeItems: "center", fontSize: "3rem" } }, "🧊") : viewer(it);
  if (it.type === "image") return h("img", { src: it.url, loading: "lazy", alt: it.kind, style: it.w && it.h ? { aspectRatio: `${it.w}/${it.h}` } : {} });
  return h("div", { style: { padding: "30px", textAlign: "center" } }, it.type === "zip" ? "📦 " : "📄 ", it.file.split("/").pop());
}
function viewer(it) {
  return h("div", {},
    h("model-viewer", { src: it.url, "camera-controls": true, "auto-rotate": true, "shadow-intensity": "1", exposure: "1.05", "environment-image": "neutral", "touch-action": "pan-y", alt: "3D model" }),
    h("div", { class: "hint" }, "Drag to spin · scroll / pinch to zoom · right-drag to move."));
}
function setCurrent(it, msg = true) {
  if (it.type === "video") { S.currentVideo = it; store.set("currentVideo", it.id); }
  else { S.current = it; store.set("current", it.id); }
  if (msg) toast("Working picture set ✓", "good");
}
const ACTIONS = {
  image: [["👗", "Outfit", "wardrobe"], ["🧍", "Pose", "pose"], ["🏞️", "Scene", "scene"], ["🪄", "Object", "objects"],
          ["🎬", "Animate", "video"], ["🧊", "3D", "3d"], ["🎮", "Sheets", "assets"]],
};
function resultCard(it, { compare, extra, compact, guided } = {}) {
  const fav = h("button", { class: "fav", title: "Favourite", onclick: async e => { e.stopPropagation(); const u = await api(`/api/items/${it.id}`, { method: "PATCH", body: { favourite: !it.favourite } }); it.favourite = u.favourite; fav.textContent = it.favourite ? "⭐" : "☆"; } }, it.favourite ? "⭐" : "☆");
  const media = h("div", { class: "media" + (it.alpha ? " checker" : ""), onclick: () => lightbox(it) },
    compare && it.type === "image" ? compareEl(compare, it) : mediaEl(it, false), fav);
  if (compare && it.type === "image") media.onclick = null;
  if (guided) {
    media.onclick = null;
    media.style.cursor = "default";
    const pic = $("img", media);
    if (pic) pic.alt = "Generated picture. Not a photograph.";
  }
  const acts = h("div", { class: "actions" });
  if (!guided && it.type === "image" && ["made", "my_character"].includes(it.role)) {
    for (const [ic, label, tab] of ACTIONS.image) acts.append(h("button", { onclick: () => { setCurrent(it, false); go(tab); } }, ic + " " + label));
    acts.append(h("button", { onclick: () => { setCurrent(it, false); go("video"); } }, "🎬 To video"));
    acts.append(h("button", { onclick: () => quickJob("upscale", { image: it.id, scale: 2 }, "Upscaling") }, "🔍 Upscale"));
    acts.append(h("button", { onclick: () => quickJob("remove_bg", { image: it.id }, "Cutting out") }, "✂️ Cut out"));
  }
  if (!guided && it.type === "video") {
    acts.append(h("button", { onclick: () => quickJob("video_still", { video: it.id, frame: "last" }, "Saving a still") }, "🖼️ Save still"));
    acts.append(h("button", { onclick: () => { setCurrent(it, false); go("assets"); } }, "🎞️ Sprite sheet"));
  }
  if (!guided) acts.append(h("a", { href: it.url, download: it.file.split("/").pop() }, "⬇️ Download"));
  for (const [label, fn] of (extra || [])) acts.prepend(h("button", { onclick: () => fn(it), style: { borderColor: "var(--accent)" } }, label));
  return h("div", { class: "res" + (compact ? " compact" : "") }, media, acts);
}
function compareEl(before, after) {
  const wrap = h("div", { class: "compare" });
  const b = h("div", { class: "before" }, h("img", { src: before.url }));
  const line = h("div", { class: "line" });
  const range = h("input", { type: "range", min: 0, max: 100, value: 50, oninput: e => set(e.target.value), onclick: e => e.stopPropagation() });
  const set = v => { b.style.clipPath = `inset(0 ${100 - v}% 0 0)`; line.style.left = v + "%"; };
  wrap.append(h("img", { src: after.url }), b, line, h("span", { class: "lbl", style: { left: "8px" } }, "Before"), h("span", { class: "lbl", style: { right: "48px" } }, "After"), range);
  set(50);
  return wrap;
}
async function lightbox(it) {
  const set = h("button", { class: "btn", onclick: () => { setCurrent(it); closeModal(); } }, "✔ Use as working picture");
  const proj = h("input", { type: "text", value: it.project || "", placeholder: "Project name (e.g. Chapter 1)" });
  const side = h("div", {},
    h("h2", {}, it.title || it.kind),
    h("div", { class: "kv" }, h("b", {}, "Made: "), fmtTime(it.created)),
    it.model ? h("div", { class: "kv" }, h("b", {}, "Model: "), it.model) : null,
    it.seed ? h("div", { class: "kv" }, h("b", {}, "Seed: "), String(it.seed)) : null,
    it.role !== "made" ? h("div", { class: "kv" }, h("b", {}, "Type: "), it.role) : null,
    it.prompt ? h("details", {}, h("summary", { class: "kv" }, "Prompt used"), h("pre", {}, it.prompt)) : null,
    h("label", { class: "f" }, "Project"), proj,
    h("div", { class: "row", style: { marginTop: "12px" } },
      (it.type === "image" || it.type === "video") && !it.age_flag ? set : null,
      h("button", { class: "btn", onclick: async () => { await api(`/api/items/${it.id}`, { method: "PATCH", body: { project: proj.value } }); toast("Saved"); } }, "Save project"),
      it.age_flag ? h("div", { class: "hint" }, "Hidden because it may look under 21. It can't be downloaded, reused, or trained on.") : h("a", { class: "btn", href: it.url, download: it.file.split("/").pop() }, "⬇️ Download"),
      h("button", { class: "btn danger", onclick: async () => { if (!confirm("Move to trash?")) return; await api(`/api/items/${it.id}`, { method: "DELETE" }); closeModal(); toast("Moved to trash (outputs/_trash)"); if (S.tab === "gallery") go("gallery"); } }, "🗑 Delete")));
  modal(h("div", { class: "lightbox" }, h("div", { class: "big" + (it.alpha ? " checker" : "") }, mediaEl(it, false)), side), { wide: true });
}

// ------------------------------------------------------------------ working picture widget
function workingPicture({ video = false, title = "Working picture", roles = ["made", "my_character"] } = {}) {
  const el = h("div", { class: "card" });
  const draw = () => {
    const it = video ? S.currentVideo : S.current;
    el.innerHTML = "";
    el.append(h("h2", {}, h("span", { class: "stepnum" }, "1"), title));
    el.append(h("div", { class: "working" },
      h("div", { class: "thumb", style: it && it.type === "image" ? { backgroundImage: `url(${it.url})` } : {} }, it ? (it.type === "video" ? "🎬" : "") : (video ? "🎬" : "🖼️")),
      h("div", { class: "meta" }, it ? h("div", {}, h("b", { style: { color: "var(--text)" } }, it.title || it.kind), h("br"), fmtTime(it.created)) : (video ? "No video chosen yet." : "No picture chosen yet."),
        h("div", { class: "row", style: { marginTop: "8px" } },
          h("button", { class: "btn small", onclick: async () => { const x = await pickFromGallery({ type: video ? "video" : "image", roles, title: video ? "Pick a video" : "Pick a picture" }); if (x) { setCurrent(x, false); draw(); el.dispatchEvent(new Event("change")); } } }, "Choose from gallery"),
          video ? null : h("button", { class: "btn small", onclick: async () => { const x = await uploadDialog("my_character"); if (x) { setCurrent(x, false); draw(); el.dispatchEvent(new Event("change")); } } }, "⬆ Upload my character")))));
  };
  draw();
  el.redraw = draw;
  return el;
}
function needCurrent(video = false) {
  const it = video ? S.currentVideo : S.current;
  if (!it) { toast(video ? "Pick a video first (step 1)." : "Pick a picture first (step 1).", "bad"); return null; }
  return it;
}

// ------------------------------------------------------------------ Advanced drawer
function advanced(key, { loras = true, sampler = true } = {}) {
  const saved = store.get("adv." + key, {});
  const f = {};
  const inp = (name, attrs) => { f[name] = h("input", { type: "number", ...attrs, value: saved[name] ?? "" }); return f[name]; };
  const sel = name => { f[name] = h("select", {}, h("option", { value: "" }, "(default)")); return f[name]; };
  const loraRows = [];
  const loraBox = h("div", {});
  const fill = async () => {
    if (!S.advOpts) { try { S.advOpts = await api("/api/advanced/options"); } catch (e) { S.advOpts = { samplers: [], schedulers: [], loras: [] }; } }
    for (const [n, list] of [["sampler", S.advOpts.samplers], ["scheduler", S.advOpts.schedulers]]) {
      if (!f[n] || f[n].options.length > 1) continue;
      for (const o of list) f[n].append(h("option", { value: o }, o));
      f[n].value = saved[n] || "";
    }
    if (loras && !loraRows.length) {
      for (let i = 0; i < 3; i++) {
        const s = h("select", {}, h("option", { value: "" }, S.advOpts.loras.length ? "(no extra LoRA)" : "(no LoRAs found in ComfyUI/models/loras)"));
        for (const o of S.advOpts.loras) s.append(h("option", { value: o }, o));
        const st = h("input", { type: "number", step: "0.05", value: (saved.loras?.[i]?.strength) ?? 1, style: { width: "90px" } });
        s.value = saved.loras?.[i]?.name || "";
        loraRows.push([s, st]);
        loraBox.append(h("div", { class: "row", style: { flexWrap: "nowrap", marginBottom: "6px" } }, s, st));
      }
    }
  };
  const d = h("details", { class: "adv", ontoggle: e => { store.set("advopen." + key, e.target.open); if (e.target.open) fill(); } },
    h("summary", {}, "🛠️ Advanced settings"),
    h("div", { class: "in" },
      h("div", { class: "g2" }, h("div", {}, h("label", { class: "f" }, "Seed (blank = random)"), inp("seed", { min: 0, placeholder: "random" })),
        sampler ? h("div", {}, h("label", { class: "f" }, "Steps"), inp("steps", { min: 1, max: 150, placeholder: "model default" })) : h("div")),
      sampler ? h("div", { class: "g2" }, h("div", {}, h("label", { class: "f" }, "CFG / guidance"), inp("cfg", { step: "0.1", min: 0, max: 30, placeholder: "default" })),
        h("div", {}, h("label", { class: "f" }, "Denoise (0–1: how much may change)"), inp("denoise", { step: "0.05", min: 0, max: 1, placeholder: "default" }))) : null,
      sampler ? h("div", { class: "g2" }, h("div", {}, h("label", { class: "f" }, "Sampler"), sel("sampler")), h("div", {}, h("label", { class: "f" }, "Scheduler"), sel("scheduler"))) : null,
      loras ? h("div", {}, h("label", { class: "f" }, "Extra LoRAs + strength (put .safetensors files in ComfyUI/models/loras)"), loraBox) : null,
      h("div", { class: "row", style: { marginTop: "10px" } },
        h("button", { class: "btn small", onclick: () => showWorkflow(key) }, "{ } Show last workflow (API JSON)"),
        h("button", { class: "btn small", onclick: () => { for (const x of Object.values(f)) x.value = ""; loraRows.forEach(([s, st]) => { s.value = ""; st.value = 1; }); store.set("adv." + key, {}); } }, "Reset")),
      h("div", { class: "hint" }, "Leave anything blank to use the tested default. Settings are remembered per tool.")));
  if (store.get("advopen." + key, false)) { d.open = true; fill(); }
  d.get = () => {
    const out = {};
    for (const [k, el] of Object.entries(f)) if (el.value !== "") out[k] = el.value;
    const ls = loraRows.map(([s, st]) => ({ name: s.value, strength: parseFloat(st.value || "1") })).filter(x => x.name);
    if (ls.length) out.loras = ls;
    store.set("adv." + key, { ...out, loras: loraRows.map(([s, st]) => ({ name: s.value, strength: st.value })) });
    return out;
  };
  return d;
}
async function showWorkflow(key) {
  const jid = S.lastJob[key];
  if (!jid) return toast("Run this tool once first.");
  const w = await api(`/api/jobs/${jid}/workflow`);
  const txt = JSON.stringify(w.workflows[w.workflows.length - 1] || {}, null, 2);
  const ta = h("textarea", { style: { minHeight: "50vh", fontFamily: "ui-monospace,Menlo,monospace", fontSize: ".8rem" } }, txt);
  modal(h("div", {}, h("h2", {}, "Last workflow sent to ComfyUI"),
    h("p", { class: "hint" }, "Paste this into ComfyUI (drag a .json file in, or use Advanced → Raw workflow here)."), ta,
    h("div", { class: "row", style: { marginTop: "10px" } }, h("button", { class: "btn", onclick: () => { ta.select(); document.execCommand("copy"); navigator.clipboard?.writeText(txt).catch(() => {}); toast("Copied"); } }, "Copy"))), { wide: true });
}

// ------------------------------------------------------------------ running jobs
/** runJob: start a job and show its progress + results inside `box`. */
async function runJob(kind, params, box, { key, label = "Working", compare = null, onDone, extra, guided = false, recipe = null, retryOf = null } = {}) {
  box.innerHTML = "";
  const bar = h("i"), msg = h("div", { class: "hint" }, "Sending to the engine…");
  const stop = h("button", { class: "btn small", title: "Stop this job", type: "button" }, "■ Stop");
  const prog = h("div", { class: "progress" }, h("div", { class: "row" }, h("b", {}, label), h("div", { class: "spacer", style: { flex: 1 } }), stop), h("div", { class: "bar" }, bar), msg);
  box.append(prog);
  let job;
  const request_id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())) ;
  try {
    // retryOf: the same job again with a new seed, after the age check deleted a result (D-C-51). Every rule runs again.
    job = retryOf ? await api(`/api/jobs/${retryOf}/retry`, { method: "POST" })
                  : await api("/api/jobs", { method: "POST", body: { kind, params, request_id, ...(recipe ? { recipe } : {}) } });
  }
  catch (e) { box.innerHTML = ""; box.append(h("div", { class: "err" }, e.message)); return; }
  S.lastJob[key || kind] = job.id;
  try { sessionStorage.setItem("es.liveJob", job.id); } catch (e) {}
  stop.onclick = () => api(`/api/jobs/${job.id}/cancel`, { method: "POST" });
  const t0 = Date.now();
  while (true) {
    await new Promise(r => setTimeout(r, 900));
    try { job = await api(`/api/jobs/${job.id}`); } catch (e) { msg.textContent = "Lost contact with the app… retrying"; continue; }
    bar.style.width = Math.round((job.progress || 0) * 100) + "%";
    const secs = Math.round((Date.now() - t0) / 1000);
    msg.textContent = (job.status === "queued" ? `Waiting in line (position ${job.position || 1})` : (job.message || "Working")) + ` · ${secs}s`;
    if (["done", "error", "cancelled", "blocked_age_check_unavailable"].includes(job.status)) break;
  }
  try { if (sessionStorage.getItem("es.liveJob") === job.id) sessionStorage.removeItem("es.liveJob"); } catch (e) {}
  refreshJobs();
  const live = document.getElementById("liveJobBar");
  if (live) live.remove();
  box.innerHTML = "";
  if (job.status === "error" || job.status === "blocked_age_check_unavailable") box.append(h("div", { class: "err" }, "⚠️ " + (job.error || job.status)));
  if (job.can_retry) {
    const again = h("button", { class: "btn small", type: "button", title: "Run the same job again with a new seed" }, "Try again with a new seed");
    again.onclick = () => runJob(kind, params, box, { key, label, compare, onDone, extra, guided, recipe, retryOf: job.id });
    box.append(again);
  }
  if (job.status === "cancelled") box.append(h("div", { class: "err" }, "Stopped."));
  if (job.results.length) {
    const g = h("div", { class: "grid" });
    for (const it of job.results) g.append(resultCard(it, { extra, guided, compare: compare && it.type === "image" && !it.kind.startsWith("sheet") ? compare : null }));
    box.append(g);
  } else if (job.status === "done") box.append(h("div", { class: "err" }, "Finished, but nothing came back."));
  onDone && onDone(job);
  return job;
}
async function quickJob(kind, params, label) {
  toast(label + "… (see the ⏳ Jobs button)");
  const box = h("div");
  const j = await runJob(kind, params, box, { label });
  if (j && j.status === "done") { toast("Done ✓ — it's in the Gallery", "good"); if (j.results[0]) lightbox(j.results[0]); }
  else if (j) toast(j.error || "Stopped", "bad");
}
function resultsBox(emptyText = "Your results appear here.") {
  return h("div", { class: "results" }, h("div", { class: "empty" }, h("span", { class: "big" }, "✨"), emptyText));
}
function bigButton(text, fn) {
  const b = h("button", { class: "btn primary", type: "button" }, text);
  b.onclick = async (ev) => {
    if (b.disabled || b.dataset.busy === "1") { ev.preventDefault(); ev.stopPropagation(); return; }
    b.dataset.busy = "1";
    b.disabled = true;
    try { await fn(); }
    finally {
      b.dataset.busy = "0";
      if (typeof b._sync === "function") b._sync();
      else b.disabled = false;
    }
  };
  return b;
}
function ageOk(d) {
  return !!(d && d.ageSet === true && Number.isInteger(d.age) && d.age >= 21);
}
function ageProblem(raw) {
  const t = String(raw ?? "").trim();
  if (!t) return "Type the character's age, or drag the slider. Easy Studio does not guess or fill this in.";
  if (!/^\d+$/.test(t)) return "Age has to be a whole number, such as 28.";
  const n = +t;
  if (n < 21) return "That age is under 21, so it is rejected. Easy Studio does not raise it to 21.";
  if (t.length > 3) return "That number is too long to be an age. Type a real age of 21 or older.";
  return "";
}
const HELP_PHRASES = [
  ["Who", ["a fictional adult woman", "a fictional adult man"]],
  ["Where", ["in a sunlit studio", "on a rainy city street", "in a quiet bedroom"]],
  ["Mood", ["calm and confident", "smiling", "serious"]],
];
function promptHelper(input, { limit = 500, unit = "characters" } = {}) {
  const note = h("div", { class: "hint help-note" }, "");
  const refresh = () => {
    const t = input.value || "";
    const n = unit === "words" ? (t.trim() ? t.trim().split(/\s+/).length : 0) : t.length;
    const over = n > limit;
    note.textContent = (t ? `${n} of ${limit} ${unit}. ` : "Optional. Use a chip if you would rather not write it. ")
      + (over ? `Shorten it. Past ${limit} ${unit}, the extra is cut or refused. ` : "")
      + "Wording is checked when you press the button.";
  };
  input.addEventListener("input", refresh);
  const checkBtn = h("button", { type: "button", class: "btn small", title: "Check these words now, without starting a job", onclick: async () => {
    note.textContent = "Checking…";
    try {
      const r = await api("/api/check-text", { method: "POST", body: { text: input.value } });
      note.textContent = r.ok ? "Those words are allowed." : r.error;
      if (!r.ok) note.classList.add("bad-note"); else note.classList.remove("bad-note");
    } catch (e) { note.textContent = e.message; note.classList.add("bad-note"); }
  } }, "Check wording");
  const box = h("div", { class: "prompt-help" },
    h("div", { class: "hint" }, "Prompt helper — click a phrase to add it"),
    ...HELP_PHRASES.map(([label, bits]) => h("div", { class: "row" }, h("span", { class: "hint" }, label),
      ...bits.map(b => h("button", { type: "button", class: "btn small", title: "Add: " + b, onclick: () => {
        const cur = input.value.trim();
        input.value = cur ? cur + ", " + b : b;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        refresh();
      } }, b)))),
    h("div", { class: "row" }, checkBtn), note);
  refresh();
  return box;
}
function estimateNote(text) { return h("div", { class: "hint estimate" }, text); }
function gateNote(ok, why, estimate) {
  return h("div", { class: "hint action-why" }, ok ? (estimate || "") : why);
}

// ================================================================== VIEWS
const VIEWS = {};
const newDNA = () => ({ style: "photo", gender: "woman", age: null, ageSet: false, traits: {}, name: "", extra: "", notes: "" });

async function loadChars() { try { S.chars = await api("/api/characters"); } catch (e) { S.chars = []; } return S.chars; }

function charStrip(selectedId, onPick, { allowNew = true } = {}) {
  const el = h("div", { class: "strip" });
  const draw = () => {
    el.innerHTML = "";
    if (allowNew) el.append(h("div", { class: "mini" + (!selectedId ? " on" : ""), onclick: () => { selectedId = null; draw(); onPick(null); } }, h("div", { class: "face" }, "＋"), "New"));
    for (const c of S.chars) el.append(h("div", { class: "mini" + (selectedId === c.id ? " on" : ""), onclick: () => { selectedId = c.id; draw(); onPick(c); } },
      h("div", { class: "face", style: c.hero_url ? { backgroundImage: `url(${c.hero_url})` } : {} }, c.hero_url ? "" : "👤"), c.name));
    if (!S.chars.length && !allowNew) el.append(h("div", { class: "hint" }, "No saved characters yet — make one in ✨ Create."));
  };
  draw();
  return el;
}

// ------------------------------------------------------------------ Create
// First photo: one ready preset. A made-up adult woman of a stated age of 30, everyday section, photographic, a fashion-show look
// in Z-Image Turbo (the "realistic" look). Every rule still decides: it goes through the same Create job as any other picture.
const FIRST_PHOTO = {
  dna: { name: "First photo", gender: "woman", age: 30, style: "photo", traits: { hair_style: "long_wavy", hair_length: "very_long", makeup: "m_glam" } },
  outfit: "dressy:evening", scene: "studio", lighting: "dramatic", camera: "full", aspect: "wide", count: 2, speed: "best", look: "realistic", engine: "",
  extra_scene: "walking a fashion show runway, confident runway pose, glamorous, realistic skin texture, long flowing hair, wide fashion-show framing",
};

VIEWS.create = async (m) => {
  await loadChars();
  if (!S.dna) S.dna = newDNA();
  const d = S.dna;
  if (REALISTIC_ONLY && d.style !== "photo") d.style = "photo";  // realistic only on the first-run path
  if (!(d.ageSet === true && Number.isInteger(d.age) && d.age >= 21)) { d.ageSet = false; d.age = null; }
  const save = () => store.set("dna", d);
  const opt = { outfit: store.get("c.outfit", null), camera: store.get("c.camera", "half"), scene: store.get("c.scene", "studio"),
    lighting: store.get("c.lighting", "soft"), speed: store.get("c.speed", "best"), count: store.get("c.count", 4), aspect: store.get("c.aspect", "portrait"),
    lookpreset: store.get("c.lookpreset", "realistic"), lens: store.get("c.lens", null), engine: store.get("c.engine", "") };
  const keep = () => Object.entries(opt).forEach(([k, v]) => store.set("c." + k, v));
  const summary = h("div", { class: "summary" });
  const res = resultsBox("Pick a look on the left, then press Create. You'll get up to 4 pictures to choose from.");
  const name = h("input", { type: "text", maxlength: "60", placeholder: "Name (e.g. Lyra)", title: "Up to 60 characters. Names are checked for the same safety rules as prompts.", value: d.name || "", oninput: e => { d.name = e.target.value; save(); } });
  const left = h("div");
  let createBtn;
  const drawSummary = () => {
    const words = [];
    const st = S.cat.styles.find(x => x.id === d.style); words.push(st ? st.label : "");
    words.push(d.gender === "man" ? "Man" : "Woman");
    words.push(ageOk(d) ? String(d.age) : "age not set");
    for (const g of S.cat.groups) { const v = d.traits[g.id]; for (const id of [].concat(v || [])) { const c = g.chips.find(x => x.id === id); if (c) words.push(c.label.toLowerCase()); } }
    summary.textContent = "🪪 " + words.filter(Boolean).join(" · ") + (d.extra ? ` · “${d.extra}”` : "");
  };
  const drawLeft = () => {
    left.innerHTML = "";
    const ageLbl = h("b", {}, ageOk(d) ? `Adult · ${d.age}` : "Not set");
    const ageHint = h("div", { class: "hint action-why", id: "ageWhy" }, ageOk(d) ? "" : "Type an age of 21 or older, or drag the slider. Nothing is filled in for you.");
    const ageInput = h("input", { class: "stated-age", type: "text", inputmode: "numeric", autocomplete: "off",
      placeholder: "Type an age, 21 or older", value: ageOk(d) ? String(d.age) : "",
      title: "The character's stated age. Easy Studio does not guess.",
      oninput: e => {
        const raw = e.target.value.trim();
        const problem = ageProblem(raw);
        if (!problem && raw) { d.age = +raw; d.ageSet = true; }
        else { d.age = null; d.ageSet = false; }
        ageLbl.textContent = ageOk(d) ? `Adult · ${d.age}` : "Not set";
        ageHint.textContent = problem || (ageOk(d) ? "" : "Type an age of 21 or older.");
        if (ageOk(d)) ageSlider.value = String(Math.min(+ageSlider.max, Math.max(+ageSlider.min, d.age)));
        save(); drawSummary(); if (createBtn._sync) createBtn._sync();
      } });
    const ageSlider = h("input", { type: "range", min: S.cat.age.min, max: S.cat.age.max,
      value: ageOk(d) ? Math.min(S.cat.age.max, d.age) : S.cat.age.min,
      title: "Drag to choose an age from 21 to 70. It stays unset until you move it. For an age over 70, type it.",
      oninput: e => {
        if (e.target.dataset.touched !== "1" && document.activeElement !== e.target) return;
        d.age = +e.target.value; d.ageSet = true; ageInput.value = String(d.age);
        ageLbl.textContent = `Adult · ${d.age}`; ageHint.textContent = "";
        save(); drawSummary(); if (createBtn._sync) createBtn._sync();
      } });
    ageSlider.dataset.touched = ageOk(d) ? "1" : "0";
    ageSlider.addEventListener("pointerdown", () => { ageSlider.dataset.touched = "1"; });
    ageSlider.addEventListener("keydown", () => { ageSlider.dataset.touched = "1"; });
    left.append(
      h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "1"), "Style & basics"),
        h("div", { class: "tiles", style: { gridTemplateColumns: "repeat(4,1fr)" } }, firstRunStyles(S.cat.styles).map(st => h("div", { class: "tile" + (d.style === st.id ? " on" : ""), onclick: () => { d.style = st.id; save(); drawLeft(); } }, h("span", { class: "big" }, st.icon), st.label))),
        h("div", { class: "row", style: { marginTop: "12px" } }, seg(S.cat.genders.map(g => [g.id, g.icon + " " + g.label]), d.gender, v => { d.gender = v; save(); drawLeft(); })),
        h("label", { class: "f" }, "Age ", ageLbl, h("span", { class: "pillnote" }, `adults only · ${S.cat.age.min}+ · not guessed`)),
        ageInput, ageSlider, ageHint),
      lookCard(),
      h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "First photo"),
        h("h3", {}, "Outfit"), outfitPicker(opt.outfit, v => { opt.outfit = v; keep(); }),
        h("h3", {}, "Look"), chips(catX("looks"), opt.lookpreset || "realistic", v => { opt.lookpreset = v; keep(); }),
        h("h3", {}, "Lens"), chips(S.cat.lenses || [], opt.lens, v => { opt.lens = v; keep(); }),
        h("h3", {}, "Framing"), chips(S.cat.cameras, opt.camera, v => { opt.camera = v; keep(); }),
        h("h3", {}, "Place"), chips(S.cat.scenes.slice(0, 12), opt.scene, v => { opt.scene = v; keep(); }),
        h("h3", {}, "Light"), chips(S.cat.lighting, opt.lighting, v => { opt.lighting = v; keep(); }),
        h("h3", {}, "Speed & size"),
        h("div", { class: "row" },
          d.style === "anime" ? h("span", { class: "hint" }, "Anime uses NoobAI-XL") : seg([["best", "💎 Best"], ["fast", "⚡ Fast draft"]], opt.speed, v => { opt.speed = v; keep(); }),
          d.style === "photo" && S.area !== "adult" ? seg([["", "Standard"], ["sd15", "Photo (SD 1.5)"]], opt.engine || "", v => { opt.engine = v; keep(); }) : null,
          seg([[1, "1"], [2, "2"], [4, "4"]], opt.count, v => { opt.count = v; keep(); }),
          seg([["portrait", "▯ Portrait"], ["square", "□ Square"], ["wide", "▭ Wide"]], opt.aspect, v => { opt.aspect = v; keep(); }))),
      h("div", { class: "card" }, summary, h("label", { class: "f" }, "Name (up to 60 characters)"), name,
        h("div", { class: "hint" }, "Leave the name blank until you save. Create still works."),
        createBtn = bigButton("✨ Create pictures", create),
        gateNote(ageOk(d), "Type or choose an age of 21 or older before Create turns on. Easy Studio will not guess.", "Usually under a minute for Fast, or a couple of minutes for Best."),
        adv),
    );
    createBtn._sync = () => {
      const ok = ageOk(d);
      createBtn.disabled = !ok;
      createBtn.title = ok ? "Usually under a minute for Fast, or a couple of minutes for Best." : "Type or choose an age of 21 or older. Easy Studio will not guess.";
      const why = createBtn.nextElementSibling;
      if (why) why.textContent = ok ? "Usually under a minute for Fast, or a couple of minutes for Best." : "Type or choose an age of 21 or older before Create turns on. Easy Studio will not guess.";
    };
    createBtn._sync();
    drawSummary();
  };
  const LOOK_TABS = [["body", "🧍 Body", ["body", "height", "bust", "hips"]], ["skin", "🎨 Skin", ["skin", "skin_details"]],
    ["face", "🙂 Face", ["face", "eyes", "eye_shape", "lips", "makeup"]], ["hair", "💇 Hair", ["hair_style", "hair_color", "hair_length"]],
    ["extra", "🧝 Fantasy & more", ["fantasy"]]];
  let lookTab = store.get("c.look", "body");
  function lookCard() {
    const known = new Set(LOOK_TABS.flatMap(t => t[2]));
    const tabDef = LOOK_TABS.find(t => t[0] === lookTab) || LOOK_TABS[0];
    const ids = tabDef[0] === "extra" ? [...tabDef[2], ...S.cat.groups.map(g => g.id).filter(id => !known.has(id))] : tabDef[2];
    const groups = ids.map(id => S.cat.groups.find(g => g.id === id)).filter(Boolean);
    const count = t => t[2].filter(id => d.traits[id] && [].concat(d.traits[id]).length).length;
    return h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "Look",
        h("button", { class: "btn small", style: { marginLeft: "auto" }, title: "Random look", onclick: surprise }, "🎲 Surprise me")),
      h("div", { class: "subtabs" }, LOOK_TABS.map(t => h("button", { class: lookTab === t[0] ? "on" : "", onclick: () => { lookTab = t[0]; store.set("c.look", lookTab); drawLeft(); } },
        t[1], count(t) ? h("span", { class: "dot" }, String(count(t))) : null))),
      groups.map(g => {
        const list = g.chips.filter(c => !c.only || c.only === d.gender);
        if (!list.length) return null;
        return h("div", {}, h("h3", {}, g.label), chips(list, d.traits[g.id] || (g.multi ? [] : null), v => { if (v && (!g.multi || v.length)) d.traits[g.id] = v; else delete d.traits[g.id]; save(); drawSummary(); }, { multi: g.multi }));
      }),
      lookTab === "extra" ? [h("label", { class: "f" }, "Anything else? (optional, up to 500 characters)"),
        (() => { const extra = h("input", { type: "text", maxlength: "500", value: d.extra || "", placeholder: "e.g. small scar over the left eyebrow, silver nose ring", title: "Extra words for this fictional adult. Checked like every other prompt.", oninput: e => { d.extra = e.target.value; save(); drawSummary(); } }); return h("div", {}, extra, promptHelper(extra, { limit: 500 })); })()] : null,
      h("div", { class: "row", style: { marginTop: "12px", justifyContent: "space-between" } },
        LOOK_TABS.findIndex(t => t[0] === lookTab) > 0 ? h("button", { class: "btn small", onclick: () => step(-1) }, "← Back") : h("span"),
        LOOK_TABS.findIndex(t => t[0] === lookTab) < LOOK_TABS.length - 1 ? h("button", { class: "btn small", onclick: () => step(1) }, "Next →") : h("span")));
  }
  function step(n) { const i = LOOK_TABS.findIndex(t => t[0] === lookTab); lookTab = LOOK_TABS[Math.max(0, Math.min(LOOK_TABS.length - 1, i + n))][0]; store.set("c.look", lookTab); drawLeft(); }
  function surprise() {
    const pick = a => a[Math.floor(Math.random() * a.length)];
    d.traits = {};
    for (const g of S.cat.groups) {
      const list = g.chips.filter(c => !c.only || c.only === d.gender);
      if (!list.length || g.multi) continue;
      d.traits[g.id] = pick(list).id;
    }
    const rolled = 21 + Math.floor(Math.random() * 20);
    if (!Number.isInteger(rolled) || rolled < 21 || rolled > 40) {
      d.age = null; d.ageSet = false;
      save(); drawLeft(); toast("Surprise me did not store an age.", "bad");
      return;
    }
    d.age = rolled;
    d.ageSet = true;
    save(); drawLeft(); toast("🎲 New random look — age " + d.age + " was chosen because you pressed Surprise me. Change it if you want.");
  }
  const adv = advanced("create");
  async function create() {
    if (!ageOk(d)) { toast("Type or choose an age of 21 or older first. Easy Studio will not guess.", "bad"); return; }
    const person = { ...d, traits: { ...d.traits } };
    delete person.ageSet;
    const p = { dna: person, ...opt, engine: d.style === "photo" && S.area !== "adult" ? opt.engine : "", look: d.style === "photo" ? (opt.lookpreset || "realistic") : null,
      speed: d.style === "anime" ? "best" : opt.speed, character_id: d.id || null, advanced: adv.get() };
    await runJob("create", p, res, { key: "create", label: `Creating ${opt.count} picture${opt.count > 1 ? "s" : ""}`, extra: [["👤 Save as character", saveAsCharacter]] });
  }
  async function saveAsCharacter(it) {
    if (!d.name) { const n = prompt("Name this character:", "New character"); if (!n) return; d.name = n; name.value = n; }
    try {
      const c = await api("/api/characters", { method: "POST", body: { ...d, hero: it.id, seed: it.seed || 0 } });
      d.id = c.id; save(); await loadChars(); setCurrent(it, false);
      toast(`Saved “${c.name}” ✓ — now try Wardrobe, Pose or Photoshoot`, "good");
      strip.replaceWith(strip = charStrip(d.id, pickChar));
    } catch (e) { toast(e.message, "bad"); }
  }
  const pickChar = c => {
    if (c) {
      const age = Number(c.age);
      S.dna = { ...c, traits: { ...(c.traits || {}) }, age: Number.isInteger(age) ? age : null, ageSet: Number.isInteger(age) && age >= 21 };
    } else S.dna = newDNA();
    store.set("dna", S.dna); go("create");
  };
  let strip = charStrip(d.id, pickChar);
  const firstPhoto = bigButton("📸 First photo", async () => {
    if (S.area === "adult") { toast("First photo is for the everyday section.", "bad"); return; }
    await runJob("create", JSON.parse(JSON.stringify(FIRST_PHOTO)), res, { key: "firstphoto", label: "Making your first photo (2 pictures)" });
  });
  firstPhoto.id = "createFirstPhoto";
  m.append(h("h1", {}, "Create a character"), h("p", { class: "sub" }, "Pick each part with a click, then set an age of 21 or older. Every character is a fictional adult."),
    h("div", { class: "card", id: "firstPhotoCard" }, h("h2", {}, "First photo"),
      h("p", { class: "hint" }, "One click, no choices: a made-up adult woman of a stated age of 30 on a fashion show runway, realistic skin, long flowing hair, glamorous, in a wide frame. " +
        "It makes 2 pictures with Z-Image Turbo, which needs the “Fast drafts + poses” download. Movement such as flowing hair comes in the video step."),
      firstPhoto),
    h("div", { class: "card flat", style: { padding: "0 0 6px", border: 0 } }, strip),
    h("div", { class: "cols" }, left, res));
  drawLeft();
};

function outfitPicker(value, onChange) {
  let cat = (catX("outfits").find(c => c.items.some(i => i.id === value)) || catX("outfits")[0]).id;
  const box = h("div");
  const draw = () => {
    box.innerHTML = "";
    box.append(h("div", { class: "chips", style: { marginBottom: "8px" } }, catX("outfits").map(c => h("span", { class: "chip" + (cat === c.id ? " on" : ""), onclick: () => { cat = c.id; draw(); } }, c.icon + " " + c.label))));
    box.append(chips(catX("outfits").find(c => c.id === cat).items, value, v => { value = v; onChange(v); }));
  };
  draw();
  return box;
}

// ------------------------------------------------------------------ My characters
VIEWS.characters = async (m) => {
  await loadChars();
  const grid = h("div", { class: "charcards" });
  m.append(h("h1", {}, "My characters"), h("p", { class: "sub" }, "Your saved cast. Each one keeps its look, so every tool can reuse it."),
    h("div", { class: "row", style: { marginBottom: "16px" } }, h("button", { class: "btn", onclick: () => { S.dna = newDNA(); store.set("dna", S.dna); go("create"); } }, "＋ New character")), grid);
  if (!S.chars.length) grid.append(h("div", { class: "empty" }, h("span", { class: "big" }, "👥"), "No characters yet. Make one in ✨ Create, then press “👤 Save as character” on the picture you like."));
  for (const c of S.chars) {
    const notes = h("textarea", { placeholder: "Writing notes for your game (personality, backstory…)" }, c.notes || "");
    grid.append(h("div", { class: "ccard" },
      h("div", { class: "face", style: c.hero_url ? { backgroundImage: `url(${c.hero_url})` } : {}, onclick: () => { S.dna = { ...c }; store.set("dna", S.dna); go("create"); } }, c.hero_url ? "" : "👤"),
      h("div", { class: "body" }, h("div", { class: "name" }, c.name), h("div", { class: "small" }, `${c.gender}, ${c.age} · ${c.style} · ${c.count} item${c.count === 1 ? "" : "s"}`),
        h("div", { class: "actions", style: { padding: "8px 0" } },
          h("button", { onclick: () => { S.dna = { ...c }; store.set("dna", S.dna); go("create"); } }, "✏️ Edit look"),
          h("button", { onclick: () => quickJob("regenerate", { character: c.id }, "New picture, same character") }, "🔁 Again"),
          c.hero_url ? h("button", { onclick: async () => { setCurrent(await api(`/api/items/${c.hero}`), false); go("wardrobe"); } }, "👗 Outfit only") : null,
          h("button", { onclick: () => { store.set("shoot.char", c.id); go("photoshoot"); } }, "📸 Shoot"),
          h("button", { onclick: () => { store.set("gal.char", c.id); go("gallery"); } }, "🖼️ Pictures"),
          h("button", { onclick: async () => { await api(`/api/characters/${c.id}/duplicate`, { method: "POST" }); toast("Made a “sister” with the same look (new seed)"); go("characters"); } }, "👯 Sister"),
          h("button", { onclick: () => quickJob("export", { character: c.id }, "Packing an export zip") }, "📦 Export"),
          h("button", { onclick: async () => { if (!confirm(`Delete ${c.name}? (pictures stay in the gallery)`)) return; await api(`/api/characters/${c.id}`, { method: "DELETE" }); go("characters"); } }, "🗑")),
        h("details", {}, h("summary", { class: "small", style: { cursor: "pointer" } }, "📝 Notes"), notes,
          h("button", { class: "btn small", onclick: async () => { try { await api("/api/characters", { method: "POST", body: { ...c, notes: notes.value } }); toast("Notes saved"); } catch (e) { toast(e.message, "bad"); } } }, "Save notes")))));
  }
};

// ------------------------------------------------------------------ Wardrobe
VIEWS.wardrobe = (m) => {
  const res = resultsBox("Pick a picture, pick an outfit, press Change outfit.");
  let mode = store.get("w.mode", "pick");
  let changeBtn;
  const st = { item: store.get("w.item", null), color: null, material: null, text: "", ref: null, count: 1, reference_strength: 0.8 };
  const wp = workingPicture();
  const body = h("div");
  const adv = advanced("wardrobe");
  const paintAdv = advanced("paint", { loras: true });
  let painter = null;
  const draw = () => {
    body.innerHTML = "";
    body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "How?"),
      seg([["pick", "👗 Pick an outfit"], ["tryon", "🧥 Try on a clothing picture"], ["paint", "🖌️ Paint an area"]], mode, v => { mode = v; store.set("w.mode", v); draw(); })));
    if (mode === "pick") {
      body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Outfit"),
        outfitPicker(st.item, v => { st.item = v; store.set("w.item", v); if (changeBtn && changeBtn._sync) changeBtn._sync(); }),
        h("h3", {}, "Colour"), chips(S.cat.colors, st.color, v => st.color = v),
        h("h3", {}, "Material"), chips(S.cat.materials, st.material, v => st.material = v),
        h("label", { class: "f" }, "Details (optional)"), h("input", { type: "text", placeholder: "e.g. with a high slit, gold buttons", oninput: e => { st.text = e.target.value; if (changeBtn && changeBtn._sync) changeBtn._sync(); } }),
        h("h3", {}, "How many versions"), seg([[1, "1"], [2, "2"], [4, "4"]], st.count, v => st.count = v),
        h("br"), h("br"), changeBtn = bigButton("👗 Change outfit", () => run("pick")),
        h("div", { class: "hint action-why" }, "Pick a picture and an outfit. This usually takes under a minute."),
        h("button", { class: "btn", style: { marginLeft: "8px" }, title: "Change the clothes and keep the body the same", onclick: () => { const it = needCurrent(); if (!it) return; if (!st.item && !(st.text || "").trim()) return toast("Pick an outfit or describe one first.", "bad"); runJob("outfit_locked", { image: it.id, item: st.item, text: st.text }, res, { label: "Keeping the body" }); } }, "Keep the body"),
        adv));
      changeBtn._sync = () => {
        const why = !S.current ? "Pick a picture in step 1." : (!st.item && !(st.text || "").trim()) ? "Pick an outfit, or describe one." : "";
        changeBtn.disabled = !!why;
        changeBtn.title = why || "Usually under a minute.";
        const note = changeBtn.nextElementSibling;
        if (note) note.textContent = why || "Usually under a minute.";
      };
      changeBtn._sync();
    } else if (mode === "tryon") {
      const refBox = h("div", { class: "working" });
      const drawRef = () => { refBox.innerHTML = ""; refBox.append(h("div", { class: "thumb", style: st.ref ? { backgroundImage: `url(${st.ref.url})` } : {} }, st.ref ? "" : "🧥"),
        h("div", { class: "meta" }, st.ref ? "Clothing picture ready" : "Upload a picture of the clothing (flat-lay, product photo, or one of your characters wearing it).",
          h("div", { class: "row", style: { marginTop: "8px" } },
            h("button", { class: "btn small", onclick: async () => { const x = await uploadDialog("clothing"); if (x) { st.ref = x; drawRef(); } } }, "⬆ Upload clothing"),
            h("button", { class: "btn small", onclick: async () => { const x = await pickFromGallery({ roles: ["clothing", "made", "my_character"], title: "Pick the clothing picture" }); if (x) { st.ref = x; drawRef(); } } }, "From gallery")))); };
      drawRef();
      const refLbl = h("b", {}, Number(st.reference_strength).toFixed(2));
      body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Clothing picture"), refBox,
        h("label", { class: "f" }, "What is it? (helps the model)"), h("input", { type: "text", placeholder: "e.g. red silk dress", oninput: e => st.text = e.target.value }),
        h("label", { class: "f" }, "How closely to follow that picture ", refLbl), h("input", { type: "range", min: 0.2, max: 1, step: 0.05, value: st.reference_strength, title: "Low follows it loosely. High copies the clothes more closely.", oninput: e => { st.reference_strength = +e.target.value; refLbl.textContent = st.reference_strength.toFixed(2); } }),
        h("div", { class: "hint" }, "0.20 is loose and 1.00 copies the clothes closely. This does not change the paint brush."),
        h("br"), bigButton("🧥 Try it on", () => run("tryon")), adv));
    } else {
      const holder = h("div");
      const cur = S.current;
      if (cur) { painter = paintCanvas(cur); holder.append(painter.el); } else holder.append(h("div", { class: "hint" }, "Pick a picture first (step 1)."));
      const txt = h("textarea", { placeholder: "What should be in the painted area? e.g. black lace bra" });
      const strength = h("input", { type: "range", min: 0.4, max: 1, step: 0.05, value: 0.9 });
      body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Paint over what should change"), holder,
        h("label", { class: "f" }, "Describe the new look"), txt,
        h("label", { class: "f" }, "How much to change (low = subtle, high = new)"), strength,
        h("div", { class: "hint" }, "Best for precise or very adult changes. Everything outside your paint stays exactly the same."),
        h("br"), bigButton("🖌️ Paint it", async () => {
          const it = needCurrent(); if (!it || !painter) return;
          const mask = painter.mask(); if (!mask) return toast("Paint over the area first.", "bad");
          await runJob("inpaint", { image: it.id, mask, text: txt.value, strength: +strength.value, advanced: paintAdv.get() }, res, { key: "paint", label: "Painting the change", compare: it });
        }), paintAdv));
    }
  };
  async function run(how) {
    const it = needCurrent(); if (!it) return;
    const p = { image: it.id, op: "outfit", text: st.text, count: st.count, advanced: adv.get() };
    if (how === "pick") Object.assign(p, { item: st.item, color: st.color, material: st.material });
    else { if (!st.ref) return toast("Add the clothing picture first.", "bad"); p.ref = st.ref.id; p.reference_strength = st.reference_strength; }
    await runJob("edit", p, res, { key: "wardrobe", label: "Changing the outfit", compare: it });
  }
  wp.addEventListener("change", draw);
  m.append(h("h1", {}, "Wardrobe"), h("p", { class: "sub" }, "Dress your character. The face, hair and body stay the same."), h("div", { class: "cols" }, h("div", {}, wp, body), res));
  draw();
};

function paintCanvas(it) {
  const img = h("img", { src: it.url, draggable: "false" });
  const cv = h("canvas");
  let size = 40, erase = false, drawing = false, painted = false;
  const wrap = h("div", { class: "paint" }, img, cv);
  img.onload = () => { cv.width = img.naturalWidth; cv.height = img.naturalHeight; };
  const ctx = () => cv.getContext("2d");
  const pos = e => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height, cv.width / r.width]; };
  let last = null;
  const stroke = e => {
    const [x, y, sc] = pos(e); const c = ctx();
    c.globalCompositeOperation = erase ? "destination-out" : "source-over";
    c.strokeStyle = "rgba(255,40,120,1)"; c.lineWidth = size * sc; c.lineCap = "round"; c.lineJoin = "round";
    c.beginPath(); c.moveTo(...(last || [x, y])); c.lineTo(x, y); c.stroke(); last = [x, y]; painted = true;
  };
  cv.addEventListener("pointerdown", e => { drawing = true; last = null; cv.setPointerCapture(e.pointerId); stroke(e); });
  cv.addEventListener("pointermove", e => drawing && stroke(e));
  cv.addEventListener("pointerup", () => { drawing = false; last = null; });
  const el = h("div", {}, wrap,
    h("div", { class: "row", style: { marginTop: "8px" } },
      h("span", { class: "hint" }, "Brush"), h("input", { type: "range", min: 5, max: 160, value: size, style: { width: "130px" }, oninput: e => size = +e.target.value }),
      seg([["paint", "🖌️ Paint"], ["erase", "🧽 Erase"]], "paint", v => erase = v === "erase"),
      h("button", { class: "btn small", onclick: () => { ctx().clearRect(0, 0, cv.width, cv.height); painted = false; } }, "Clear"),
      h("button", { class: "btn small", onclick: () => { const c = ctx(); c.globalCompositeOperation = "xor"; c.fillStyle = "rgba(255,40,120,1)"; c.fillRect(0, 0, cv.width, cv.height); painted = true; } }, "Invert")));
  return {
    el, mask: () => {
      if (!painted) return null;
      const out = h("canvas"); out.width = cv.width; out.height = cv.height;
      const o = out.getContext("2d"); o.fillStyle = "#000"; o.fillRect(0, 0, out.width, out.height);
      const tmp = h("canvas"); tmp.width = cv.width; tmp.height = cv.height; const t = tmp.getContext("2d");
      t.drawImage(cv, 0, 0); t.globalCompositeOperation = "source-in"; t.fillStyle = "#fff"; t.fillRect(0, 0, tmp.width, tmp.height);
      o.drawImage(tmp, 0, 0);
      return out.toDataURL("image/png");
    },
  };
}

// ------------------------------------------------------------------ Pose
VIEWS.pose = async (m) => {
  await loadChars();
  const res = resultsBox("Pick a pose and press the button.");
  let mode = store.get("p.mode", "repose");
  let pose = store.get("p.pose", "standing");
  let custom = [];
  try { custom = (await api("/api/gallery?role=skeleton&limit=60")).items; } catch (e) {}
  const wp = workingPicture();
  const body = h("div");
  const adv = advanced("pose");
  let charId = store.get("p.char", null), strength = 0.8;
  const poseGrid = () => {
    const g = h("div", { class: "tiles" });
    const all = [...catX("poses"), ...custom.map(c => ({ id: c.id, label: c.title || "My pose", img: c.url }))];
    for (const p of all) g.append(h("div", { class: "tile" + (pose === p.id ? " on" : ""), onclick: () => { pose = p.id; store.set("p.pose", pose); draw(); } }, h("img", { src: p.img, loading: "lazy" }), p.label));
    return g;
  };
  const draw = () => {
    body.innerHTML = "";
    body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "How?"),
      seg([["repose", "🔁 Re-pose this picture"], ["new", "🆕 New picture of a saved character"]], mode, v => { mode = v; store.set("p.mode", v); draw(); }),
      h("div", { class: "hint" }, mode === "repose" ? "Keeps the outfit and place, changes the body pose." : "Draws a fresh full-body picture that follows the stick figure exactly.")));
    if (mode === "new") body.append(h("div", { class: "card" }, h("h2", {}, "Character"), charStrip(charId, c => { charId = c && c.id; store.set("p.char", charId); }, { allowNew: false }),
      h("label", { class: "f" }, "How strictly to follow the pose"), h("input", { type: "range", min: 0.3, max: 1, step: 0.05, value: strength, oninput: e => strength = +e.target.value })));
    body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Pose"), poseGrid(),
      h("div", { class: "row", style: { marginTop: "12px" } },
        h("button", { class: "btn small", onclick: copyPose }, "📷 Copy a pose from a picture…")),
      h("div", { class: "hint" }, "Copying reads only the stick figure — the picture itself is never used."),
      h("br"), bigButton("🧍 Apply pose", run), adv));
  };
  async function copyPose() {
    const x = await uploadDialog("pose_ref"); if (!x) return;
    const box = h("div"); res.innerHTML = ""; res.append(box);
    const j = await runJob("pose_extract", { image: x.id, name: "My pose" }, box, { label: "Reading the pose" });
    if (j && j.status === "done") { custom.unshift(j.results[0]); pose = j.results[0].id; draw(); toast("Pose added ✓", "good"); }
  }
  async function run() {
    if (mode === "repose") { const it = needCurrent(); if (!it) return; await runJob("edit", { image: it.id, op: "pose", pose, advanced: adv.get() }, res, { key: "pose", label: "Re-posing", compare: it }); }
    else { if (!charId) return toast("Pick a saved character.", "bad"); await runJob("pose_new", { character: charId, pose, strength, advanced: adv.get() }, res, { key: "pose", label: "Drawing the pose" }); }
  }
  m.append(h("h1", {}, "Pose"), h("p", { class: "sub" }, "Click a stick figure. Your character copies it."), h("div", { class: "cols" }, h("div", {}, wp, body), res));
  draw();
};

// ------------------------------------------------------------------ Scene & background
VIEWS.scene = (m) => {
  const res = resultsBox("Pick a place and press the button.");
  let mode = store.get("s.mode", "smart");
  const st = { scene: store.get("s.scene", "beach"), lighting: store.get("s.light", "golden"), text: "", ref: null, color: "#FFFFFF" };
  const wp = workingPicture();
  const body = h("div");
  const adv = advanced("scene");
  const draw = () => {
    body.innerHTML = "";
    body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "How?"),
      seg([["smart", "🪄 Smart (re-lights)"], ["quick", "✂️ Quick (cut & paste)"], ["remove", "⬜ Transparent"]], mode, v => { mode = v; store.set("s.mode", v); draw(); }),
      h("div", { class: "hint" }, { smart: "The model redraws the background and matches the light. Best looking.", quick: "Cuts the character out and pastes onto a picture or colour. Character pixels stay identical.", remove: "Removes the background completely (transparent PNG for your game)." }[mode])));
    const refPick = (role, label) => {
      const b = h("div", { class: "working" });
      const d2 = () => { b.innerHTML = ""; b.append(h("div", { class: "thumb", style: st.ref ? { backgroundImage: `url(${st.ref.url})` } : {} }, st.ref ? "" : "🏞️"),
        h("div", { class: "meta" }, st.ref ? "Background picture ready" : label, h("div", { class: "row", style: { marginTop: "8px" } },
          h("button", { class: "btn small", onclick: async () => { const x = await uploadDialog("background"); if (x) { st.ref = x; d2(); } } }, "⬆ Upload background"),
          h("button", { class: "btn small", onclick: async () => { const x = await pickFromGallery({ roles: ["background", "made"], title: "Pick a background" }); if (x) { st.ref = x; d2(); } } }, "From gallery"),
          st.ref ? h("button", { class: "btn small", onclick: () => { st.ref = null; d2(); } }, "✕") : null))); };
      d2(); return b;
    };
    if (mode === "smart") body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Where?"),
      h("div", { class: "tiles" }, S.cat.scenes.map(s => h("div", { class: "tile" + (st.scene === s.id ? " on" : ""), onclick: () => { st.scene = s.id; store.set("s.scene", s.id); draw(); } }, h("span", { class: "big" }, s.icon), s.label))),
      h("h3", {}, "Light"), chips(S.cat.lighting, st.lighting, v => { st.lighting = v; store.set("s.light", v); }),
      h("label", { class: "f" }, "Details (optional)"), h("input", { type: "text", placeholder: "e.g. at sunset with lanterns", oninput: e => st.text = e.target.value }),
      h("h3", {}, "…or use your own background picture"), refPick("background", "Optional: a picture of the place."),
      h("br"), bigButton("🏞️ Change the scene", async () => { const it = needCurrent(); if (!it) return;
        await runJob("edit", { image: it.id, op: "scene", scene: st.ref ? null : st.scene, lighting: st.lighting, text: st.text, ref: st.ref?.id, advanced: adv.get() }, res, { key: "scene", label: "Changing the scene", compare: it }); }), adv));
    if (mode === "quick") body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "New background"), refPick("background", "A background picture — or leave empty and pick a colour."),
      h("label", { class: "f" }, "…or a plain colour"), h("input", { type: "color", value: st.color, oninput: e => st.color = e.target.value }),
      h("br"), h("br"), bigButton("✂️ Swap background", async () => { const it = needCurrent(); if (!it) return;
        await runJob("bg_quick", { image: it.id, background: st.ref?.id, color: st.color.toUpperCase() }, res, { label: "Cutting out + placing", compare: it }); })));
    if (mode === "remove") body.append(h("div", { class: "card" }, bigButton("⬜ Remove background", async () => { const it = needCurrent(); if (!it) return;
      await runJob("remove_bg", { image: it.id }, res, { label: "Removing the background" }); })));
  };
  m.append(h("h1", {}, "Scene & background"), h("p", { class: "sub" }, "Put your character anywhere."), h("div", { class: "cols" }, h("div", {}, wp, body), res));
  draw();
};

// ------------------------------------------------------------------ Objects
VIEWS.objects = (m) => {
  const res = resultsBox("Pick an object and where it goes.");
  const st = { object: store.get("o.obj", "wine"), placement: "hand", text: "", ref: null, how: "describe" };
  const wp = workingPicture();
  const body = h("div");
  const adv = advanced("objects");
  let painter = null;
  const draw = () => {
    body.innerHTML = "";
    const refB = h("div", { class: "working" });
    const d2 = () => { refB.innerHTML = ""; refB.append(h("div", { class: "thumb", style: st.ref ? { backgroundImage: `url(${st.ref.url})` } : {} }, st.ref ? "" : "📦"),
      h("div", { class: "meta" }, st.ref ? "Object picture ready" : "Optional: a picture of the exact object.", h("div", { class: "row", style: { marginTop: "8px" } },
        h("button", { class: "btn small", onclick: async () => { const x = await uploadDialog("object"); if (x) { st.ref = x; d2(); } } }, "⬆ Upload object"),
        st.ref ? h("button", { class: "btn small", onclick: () => { st.ref = null; d2(); } }, "✕") : null))); };
    d2();
    body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "What?"),
      h("div", { class: "tiles" }, S.cat.objects.map(o => h("div", { class: "tile" + (st.object === o.id ? " on" : ""), onclick: () => { st.object = o.id; store.set("o.obj", o.id); draw(); } }, h("span", { class: "big" }, o.icon), o.label))),
      h("label", { class: "f" }, "…or describe it"), h("input", { type: "text", value: st.text, placeholder: "e.g. a glowing blue crystal", oninput: e => st.text = e.target.value }),
      h("h3", {}, "…or use a picture of it"), refB));
    body.append(h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "3"), "Where?"),
      seg([["describe", "📍 Choose a spot"], ["paint", "🖌️ Paint the spot"]], st.how, v => { st.how = v; draw(); }),
      st.how === "describe" ? h("div", { style: { marginTop: "10px" } }, chips(S.cat.placements, st.placement, v => st.placement = v, { optional: false }))
        : (S.current ? (painter = paintCanvas(S.current)).el : h("div", { class: "hint" }, "Pick a picture first.")),
      h("br"), bigButton("🪄 Add it", run), adv));
  };
  async function run() {
    const it = needCurrent(); if (!it) return;
    if (st.how === "paint") {
      const mask = painter && painter.mask(); if (!mask) return toast("Paint where the object goes.", "bad");
      const o = S.cat.objects.find(x => x.id === st.object);
      return runJob("inpaint", { image: it.id, mask, text: st.text || (o ? o.p : ""), strength: 1.0, advanced: adv.get() }, res, { key: "objects", label: "Adding the object", compare: it });
    }
    await runJob("edit", { image: it.id, op: "object", object: st.text ? null : st.object, placement: st.placement, text: st.text, ref: st.ref?.id, advanced: adv.get() }, res, { key: "objects", label: "Adding the object", compare: it });
  }
  m.append(h("h1", {}, "Add objects"), h("p", { class: "sub" }, "Props, pets, furniture — placed with matching light and shadow."), h("div", { class: "cols" }, h("div", {}, wp, body), res));
  draw();
};

// ------------------------------------------------------------------ Photoshoot
VIEWS.photoshoot = async (m) => {
  await loadChars();
  let charId = store.get("shoot.char", S.chars[0]?.id || null), pack = store.get("shoot.pack", "beach");
  let shootBtn;
  const res = resultsBox("Pick a character and a shoot. You get a matching set of photos in one go.");
  const tiles = h("div", { class: "tiles" });
  const drawTiles = () => { tiles.innerHTML = ""; for (const p of catX("packs")) tiles.append(h("div", { class: "tile" + (pack === p.id ? " on" : ""), onclick: () => { pack = p.id; store.set("shoot.pack", pack); drawTiles(); } }, h("span", { class: "big" }, p.icon), p.label, h("div", { class: "hint" }, `${p.count} shots`))); };
  drawTiles();
  m.append(h("h1", {}, "Photoshoot"), h("p", { class: "sub" }, "One click, a whole consistent set — great for game galleries."),
    h("div", { class: "cols" }, h("div", {},
      h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "1"), "Who?"), charStrip(charId, c => { charId = c && c.id; store.set("shoot.char", charId); if (shootBtn && shootBtn._sync) shootBtn._sync(); const why = document.getElementById("shootWhy"); if (why) why.textContent = charId ? "A set of pictures. Usually a few minutes. The face stays the same because each shot starts from the portrait." : "Save a character in Create first. This stays off until you pick one."; }, { allowNew: false })),
      h("div", { class: "card" }, h("h2", {}, h("span", { class: "stepnum" }, "2"), "Which shoot?"), tiles,
        h("br"), shootBtn = bigButton("📸 Start the shoot", () => { if (!charId) return; runJob("photoshoot", { character: charId, pack }, res, { label: "Photoshoot" }); }),
        h("div", { class: "hint action-why", id: "shootWhy" }, charId ? "A set of pictures. Usually a few minutes. The face stays the same because each shot starts from the portrait." : "Save a character in Create first. This stays off until you pick one.")),
      h("div", { class: "hint" }, "Results are grouped as a project in the Gallery."))), res);
  const shootBtnNode = m.querySelector("button.btn.primary");
  if (shootBtnNode) {
    shootBtnNode._sync = () => {
      shootBtnNode.disabled = !charId;
      shootBtnNode.title = charId ? "A set of pictures. Usually a few minutes." : "Save a character in Create first.";
    };
    shootBtnNode._sync();
  }
};

// ------------------------------------------------------------------ Video
function keptFilmStill(it) {
  if (!it || it.type !== "image" || it.role !== "made" || it.kind === "upload" || it.place || it.role === "scenery") return false;
  if (it.age_flag || (it.age_check && it.age_check !== "ok")) return false;
  return true;
}
VIEWS.video = async (m) => {
  const res = resultsBox("The short film will show here. Wan has no sound.");
  res.id = "filmResults";
  const lengths = ((S.cat && S.cat.clip_lengths) || [2, 5]).filter(n => n === 2 || n === 5);
  const allowed = lengths.length ? lengths : [2, 5];
  let seconds = allowed.includes(5) ? 5 : allowed[0];
  let motion = "wind";
  let chosen = keptFilmStill(S.current) ? S.current : null;
  const choice = h("p", { id: "filmChoice", class: "hint" }, "Nothing chosen yet.");
  const btn = bigButton("Make a short film", async () => {
    if (!chosen) return;
    await runJob("film", { image: chosen.id, seconds, motion }, res, {
      key: "film", label: "Making a short film", guided: true,
      onDone: j => j.results && j.results[0] && setCurrent(j.results[0], false),
    });
  });
  btn.id = "filmMake";
  const sync = () => {
    btn.disabled = !chosen;
    btn.title = chosen ? "A silent clip. Wan has no sound." : "Choose a still this app kept.";
    choice.textContent = chosen ? "Using a still this app kept." : "Nothing chosen yet. A rejected, held, or missing still cannot start a film.";
  };
  btn._sync = sync;
  const lenBox = h("div", { id: "filmLengths", class: "chips" });
  const drawLen = () => {
    lenBox.innerHTML = "";
    allowed.forEach(n => lenBox.append(h("span", {
      class: "chip" + (seconds === n ? " on" : ""),
      onclick: () => { seconds = n; drawLen(); },
    }, n + " seconds")));
  };
  drawLen();
  const pick = h("button", { id: "filmStill", class: "btn", type: "button" }, "Choose a still");
  pick.onclick = async () => {
    const it = await pickFromGallery({ roles: ["made"], title: "Choose a still this app kept" });
    if (!it) return;
    if (!keptFilmStill(it)) {
      toast("Choose a still this app kept. A rejected, held, or missing still cannot start a film.", "bad");
      return;
    }
    chosen = it;
    setCurrent(it, false);
    sync();
  };
  sync();
  const motions = catX("motions");
  m.append(
    h("h1", {}, "Make a short film"),
    h("p", { id: "filmSound", class: "sub" }, "Wan has no sound. This clip is pictures only."),
    h("p", { id: "filmContact" }, "Two people touching is still the weak spot. It is not solved. A clip can warp where two bodies meet. This step does not fix that."),
    h("p", { id: "filmSwitch", class: "hint" }, S.area === "adult"
      ? "21+ is open, so an explicit film of a fictional adult can start here. It still has no sound."
      : "Explicit films stay behind the 21+ switch. That switch is off."),
    h("div", { class: "card" },
      h("h2", {}, "1. A still this app kept"),
      h("p", { class: "hint" }, "Start from a still this app kept. A rejected, held, or missing still cannot start a film. The age stays on the still."),
      pick, choice),
    h("div", { class: "card" },
      h("h2", {}, "2. Length"),
      h("p", { class: "hint" }, "2 seconds or 5 seconds. The film model is Wan 2.2. You do not pick a different one."),
      lenBox,
      h("label", { class: "f" }, "What happens"),
      chips(motions, motion, v => { motion = v || "wind"; }, { optional: false })),
    h("br"), btn, res);
};


// ------------------------------------------------------------------ 3D prop
VIEWS["3d"] = async (m) => {
  const res = resultsBox("The prop will show here.");
  res.id = "propResults";
  let chosen = null;
  const choice = h("p", { id: "propChoice", class: "hint" }, "Nothing chosen yet.");
  const btn = bigButton("Make a 3D prop", async () => {
    if (!chosen) return;
    await runJob("prop", { source: chosen.source, image: chosen.item.id }, res, { key: "prop", label: "Making the 3D prop" });
  });
  btn.id = "propMake";
  const sync = () => {
    btn.disabled = !chosen;
    btn.title = chosen ? "Makes a .glb file Godot can import." : "Choose a still or a place photo first.";
    if (!chosen) { choice.textContent = "Nothing chosen yet."; return; }
    choice.textContent = chosen.source === "still" ? "Using a still this app made." : "Using a place photo.";
  };
  btn._sync = sync;
  if (S.current && S.current.type === "image" && S.current.role === "made" && !S.current.age_flag) chosen = { source: "still", item: S.current };
  const pickStill = h("button", { id: "propStill", class: "btn", type: "button" }, "Choose a still");
  pickStill.onclick = async () => {
    const it = await pickFromGallery({ roles: ["made"], title: "Choose a still this app made" });
    if (!it) return;
    if (it.type !== "image" || it.role !== "made" || it.age_flag) { toast("Choose a still this app made of a fictional adult.", "bad"); return; }
    chosen = { source: "still", item: it };
    sync();
  };
  const pickPlace = h("button", { id: "propScenery", class: "btn", type: "button" }, "Upload a place photo");
  pickPlace.onclick = async () => {
    const it = await sceneryDialog();
    if (!it || it.role !== "scenery") return;
    chosen = { source: "scenery", item: it };
    sync();
  };
  sync();
  m.append(h("h1", {}, "Make a 3D prop"),
    h("p", { id: "propLimit", class: "sub" }, "The result is a rough prop mesh. It can have holes and a soft back. It is not a rigged person, and it is not a scan you can walk inside."),
    h("div", { class: "card" }, h("h2", {}, "1. A still this app made"),
      h("p", { class: "hint" }, "A still of a fictional adult. The age stays on the still. This step does not ask again."),
      pickStill),
    h("div", { class: "card" }, h("h2", {}, "2. A photo of a place"),
      h("p", { class: "hint" }, "A photo is a place, not a person. If a face is in it, the face is blurred, or the photo is refused."),
      pickPlace),
    choice, h("br"), btn,
    h("p", { class: "hint" }, "You get a .glb file. Godot imports it: drag the file into the FileSystem panel."),
    res);
};

// ------------------------------------------------------------------ Game assets
VIEWS.assets = async (m) => {
  await loadChars();
  const res = resultsBox("Pick a tool on the left.");
  const wp = workingPicture();
  const wv = workingPicture({ video: true, title: "Video for sprites" });
  let frames = 16, cols = 8, rb = true;
  let exp = S.cat.expressions.map(e => e.id);
  let charId = S.chars[0]?.id || null;
  m.append(h("h1", {}, "Game assets"), h("p", { class: "sub" }, "Sheets and packs your game engine can use straight away."),
    h("div", { class: "cols" }, h("div", {}, wp,
      h("div", { class: "card" }, h("h2", {}, "🔄 Turnaround sheet"), h("div", { class: "hint" }, "Front, right, back and left views side by side — for 3D modelling or reference."), h("br"),
        bigButton("Make turnaround", () => { const it = needCurrent(); if (it) runJob("turnaround", { image: it.id }, res, { label: "Turnaround (4 views)" }); })),
      h("div", { class: "card" }, h("h2", {}, "😊 Expression sheet"), chips(S.cat.expressions, exp, v => exp = v, { multi: true }), h("br"),
        bigButton("Make expressions", () => { const it = needCurrent(); if (it) runJob("expressions", { image: it.id, expressions: exp }, res, { label: "Expressions" }); })),
      h("div", { class: "card" }, h("h2", {}, "🔍 Upscale"), h("div", { class: "row" },
        h("button", { class: "btn", onclick: () => { const it = needCurrent(); if (it) runJob("upscale", { image: it.id, scale: 2 }, res, { label: "Upscaling ×2" }); } }, "×2 sharper"),
        h("button", { class: "btn", onclick: () => { const it = needCurrent(); if (it) runJob("upscale", { image: it.id, scale: 4 }, res, { label: "Upscaling ×4" }); } }, "×4 (big)"),
        h("button", { class: "btn", onclick: () => { const it = needCurrent(); if (it) runJob("remove_bg", { image: it.id }, res, { label: "Cutting out" }); } }, "✂️ Transparent PNG"))),
      wv,
      h("div", { class: "card" }, h("h2", {}, "🎞️ Sprite sheet from video"),
        h("div", { class: "g2" }, h("div", {}, h("label", { class: "f" }, "Frames"), h("select", { onchange: e => frames = +e.target.value }, [8, 12, 16, 24, 32, 48].map(x => h("option", { value: x, selected: x === 16 }, x)))),
          h("div", {}, h("label", { class: "f" }, "Columns"), h("select", { onchange: e => cols = +e.target.value }, [4, 6, 8, 12].map(x => h("option", { value: x, selected: x === 8 }, x))))),
        h("label", { class: "row", style: { marginTop: "10px" } }, h("input", { type: "checkbox", checked: true, onchange: e => rb = e.target.checked }), "Transparent background (slower)"), h("br"),
        bigButton("Make sprite sheet", () => { const v = needCurrent(true); if (v) runJob("sprites", { video: v.id, frames, columns: cols, remove_bg: rb }, res, { label: "Sprite sheet" }); }),
        h("div", { class: "hint" }, "You get a PNG sheet plus a .json atlas (TexturePacker-style) that Unity, Godot and Phaser can read.")),
      h("div", { class: "card" }, h("h2", {}, "📦 Export a character pack"), charStrip(charId, c => charId = c && c.id, { allowNew: false }), h("br"),
        bigButton("Export zip", () => { if (!charId) return toast("Pick a character.", "bad"); runJob("export", { character: charId }, res, { label: "Packing" }); }),
        h("div", { class: "hint" }, "Includes the character file, portrait, ⭐ favourites, sheets and 3D models."))), res));
};

// ------------------------------------------------------------------ Gallery
VIEWS.gallery = async (m) => {
  await loadChars();
  const f = { character: store.get("gal.char", ""), type: store.get("gal.type", ""), project: "", favourites: false };
  const grid = h("div", { class: "grid" });
  const bar = h("div", { class: "row", style: { marginBottom: "16px" } });
  const load = async () => {
    const q = new URLSearchParams({ character: f.character || "", type: f.type || "", project: f.project || "", favourites: f.favourites, limit: 300 });
    const g = await api("/api/gallery?" + q);
    grid.innerHTML = "";
    if (!g.items.length) grid.append(h("div", { class: "empty" }, h("span", { class: "big" }, "🖼️"), "Nothing here yet."));
    for (const it of g.items) grid.append(resultCard(it, { compact: true }));
    bar.innerHTML = "";
    bar.append(seg([["", "All"], ["image", "🖼️ Pictures"], ["video", "🎬 Videos"], ["model", "🧊 3D"], ["zip", "📦 Exports"]], f.type, v => { f.type = v; store.set("gal.type", v); load(); }),
      h("select", { style: { width: "auto" }, onchange: e => { f.character = e.target.value; store.set("gal.char", f.character); load(); } }, h("option", { value: "" }, "All characters"), S.chars.map(c => h("option", { value: c.id, selected: f.character === c.id }, c.name))),
      h("select", { style: { width: "auto" }, onchange: e => { f.project = e.target.value; load(); } }, h("option", { value: "" }, "All projects"), g.projects.map(p => h("option", { value: p, selected: f.project === p }, p))),
      h("label", { class: "row" }, h("input", { type: "checkbox", checked: f.favourites, onchange: e => { f.favourites = e.target.checked; load(); } }), "⭐ only"),
      h("button", { class: "btn small", onclick: async () => { const r = await uploadDialog("my_character"); if (r) load(); } }, "⬆ Upload"));
  };
  m.append(h("h1", {}, "Gallery"), h("p", { class: "sub" }, "Everything you've made. Click a picture for details; use the buttons to keep working on it."), bar, grid);
  load();
};

// ------------------------------------------------------------------ Advanced (raw workflow)
VIEWS.advanced = (m) => {
  const res = resultsBox("Results of your raw workflow appear here.");
  const ta = h("textarea", { style: { minHeight: "360px", fontFamily: "ui-monospace,Menlo,monospace", fontSize: ".8rem" }, placeholder: '{ "1": { "class_type": "...", "inputs": { ... } } }' }, store.get("raw", ""));
  ta.oninput = () => store.set("raw", ta.value);
  m.append(h("h1", {}, "Advanced"), h("p", { class: "sub" }, "For power users. Every tool also has its own 🛠️ Advanced drawer (seed, steps, sampler, LoRAs)."),
    h("div", { class: "cols" }, h("div", {},
      h("div", { class: "card" }, h("h2", {}, "Raw ComfyUI workflow (API format)"),
        h("div", { class: "hint" }, "In ComfyUI: Workflow → Export (API). Paste it here. Pictures must come from the gallery — click the button to insert one (it adds an es_<id>.png name)."), h("br"), ta,
        h("div", { class: "row", style: { marginTop: "10px" } },
          h("button", { class: "btn small", onclick: async () => { const x = await pickFromGallery({ roles: ["made", "my_character"] }); if (x) { const name = `es_${x.id}.png`; navigator.clipboard?.writeText(name).catch(() => {}); ta.setRangeText(`"${name}"`, ta.selectionStart, ta.selectionEnd, "end"); store.set("raw", ta.value); toast("Inserted " + name); } } }, "🖼️ Insert gallery picture"),
          h("button", { class: "btn small", onclick: async () => { const w = Object.values(S.lastJob).pop(); if (!w) return toast("Run any tool first."); const j = await api(`/api/jobs/${w}/workflow`); ta.value = JSON.stringify(j.workflows.pop() || {}, null, 2); store.set("raw", ta.value); } }, "Load the last workflow I ran")),
        h("br"), bigButton("▶ Run workflow", () => runJob("raw", { workflow: ta.value }, res, { label: "Running your workflow" })),
        h("div", { class: "hint" }, "The same safety rules apply: every text inside is checked, and face-swap / identity nodes are refused."))), res));
};

// ------------------------------------------------------------------ Setup
VIEWS.setup = async (m) => {
  await refreshStatus();
  const s = S.status || { features: [] };
  const win = navigator.userAgent.includes("Windows");
  const py = win ? ".venv\\Scripts\\python" : ".venv/bin/python";
  const missingGroups = [...new Set(s.features.flatMap(f => f.groups))];
  m.append(h("h1", {}, "Setup"), h("p", { class: "sub" }, "What's installed and what's missing."),
    h("div", { class: "cols" }, h("div", {},
      h("div", { class: "card" }, h("h2", {}, "Engine"),
        s.comfy_up ? h("div", { class: "ok-box" }, `✓ ComfyUI ${s.comfy_version || ""} is running`, s.gpu ? ` on ${s.gpu.name}${s.gpu.vram_gb ? ` (${s.gpu.vram_gb} GB)` : ""}` : "")
          : h("div", { class: "err" }, `✗ Can't reach ComfyUI at ${s.comfy_url}. Close this window and start Easy Studio again with the start script.`),
        h("div", { class: "hint" }, `App version ${s.app || "?"} · password ${s.password ? "on" : "off"} (set EASY_STUDIO_PASSWORD to turn it on).`)),
      missingGroups.length ? h("div", { class: "card" }, h("h2", {}, "Download what's missing"),
        h("div", { class: "hint" }, "Run this in the Easy Studio folder (it resumes if it stops), then restart Easy Studio:"),
        h("pre", {}, `${py} install/download_models.py --comfy ComfyUI --what ${missingGroups.join(",")}`)) : null),
      h("div", { class: "card" }, h("h2", {}, "Tools"), s.features.map(f => h("div", { class: "feat" }, h("div", { class: "st" }, f.ready ? "✅" : "⛔"),
        h("div", {}, h("b", {}, f.label), f.ready ? null : h("div", { class: "hint" }, f.missing.length ? "Missing: " + f.missing.join(", ") : "Engine offline")))))));
};

// ------------------------------------------------------------------ start
(async function init() {
  try { S.cat = await api("/api/catalog"); }
  catch (e) { $("#main").append(h("div", { class: "err" }, "Can't reach the Easy Studio app: " + e.message)); return; }
  const ids = [store.get("current", null), store.get("currentVideo", null)];
  for (const [i, id] of ids.entries()) if (id) { try { const it = await api(`/api/items/${id}`); if (i === 0) S.current = it; else S.currentVideo = it; } catch (e) {} }
  await refreshStatus();
  const fromHash = (location.hash || "").replace(/^#\/?/, "");
  const known = t => TABS.some(x => x[0] === t) || (typeof DOORS !== "undefined" && DOORS.includes(t));
  if (fromHash && known(fromHash)) S.tab = fromHash;
  nav(); go(S.tab, { fromPop: true });
  history.replaceState({ tab: S.tab }, "", "#/" + S.tab);
  window.addEventListener("popstate", () => {
    const tab = (history.state && history.state.tab) || (location.hash || "").replace(/^#\/?/, "") || "home";
    if (known(tab)) go(tab, { fromPop: true });
  });
  setInterval(refreshStatus, 15000);
  refreshJobs(); setInterval(refreshJobs, 3000);
  setTimeout(showLiveJob, 0);
})();
async function showLiveJob() {
  let id = "";
  try { id = sessionStorage.getItem("es.liveJob") || ""; } catch (e) {}
  if (!id) {
    try {
      const jobs = await api("/api/jobs");
      const live = jobs.find(j => j.status === "running" || j.status === "queued");
      if (live) id = live.id;
    } catch (e) {}
  }
  if (!id) return;
  const bar = h("div", { class: "warn-bar", id: "liveJobBar" }, "A job is still running. Open Jobs (the clock) to watch it or stop it.");
  $("#main").prepend(bar);
  const tick = async () => {
    let job;
    try { job = await api("/api/jobs/" + id); } catch (e) { bar.remove(); return; }
    if (["done", "error", "cancelled", "blocked_age_check_unavailable"].includes(job.status)) {
      try { sessionStorage.removeItem("es.liveJob"); } catch (e) {}
      bar.remove();
      if (job.status === "done") toast("That job finished. The result is in the Gallery.", "good");
      else toast(job.error || "That job stopped.", job.status === "cancelled" ? "" : "bad");
      return;
    }
    bar.textContent = `A job is still running (${KIND_NAME[job.kind] || job.kind}, ${job.status}${job.status === "running" ? " " + Math.round((job.progress || 0) * 100) + "%" : ""}). Open Jobs to watch it or stop it.`;
    setTimeout(tick, 1000);
  };
  tick();
}
