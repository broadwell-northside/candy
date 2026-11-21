/* PRIVATE BUILD — NOT FOR DISTRIBUTION
   First run: the PHASE_TWO switch and the home page's tool list. Loaded after v3.js and make.js, before owner.js.
   PHASE_TWO is the likeness machinery (My likeness card, enrolment, Add photos, the 3D self-model). It is hidden
   until the owner flips the switch in Setup. Screens ask: `if (!(await PHASE_TWO.shown())) return;` */
"use strict";

const PHASE_TWO = {
  async shown() {
    try { return !(await api("/api/phase_two")).hidden; } catch (e) { return false; }
  },
};

// Realistic only on the first-run path: the anime, 3D-render and painted styles stay in the code, out of the Create screen.
const REALISTIC_ONLY = true;
const firstRunStyles = list => (REALISTIC_ONLY ? list.filter(st => st.id === "photo") : list);

// The home is video. The two video pages are built elsewhere (routes #/video-build and #/video-extend).
const FIRST_RUN_MAIN = [
  ["start-here", "📖", "Start here", "A short, step-by-step guide to your first weekend: models, a picture, a video, a longer video.", false],
  ["video-build", "🎬", "Build a video", "Describe the video you want, or start from a picture, and watch it get made.", true],
  ["video-extend", "➕", "Extend a video", "Take a clip you made and say what happens next. It grows from where it ended.", true],
  ["create", "✨", "Make a picture", "Make a realistic made-up adult from your words, to use as a picture or to start a video.", false],
  ["loras", "🧩", "LoRAs", "See the LoRAs on this computer and choose which ones to use.", false],
  ["advanced", "🛠️", "Advanced", "Every dial and raw workflows, for when you want full control.", false],
];
const FIRST_RUN_SOON = [["3d", "🧊", "3D"], ["avatar", "🧍", "Avatar"], ["face", "🙂", "Face scan"], ["voice", "🎙️", "Voice"],
  ["catalog", "📚", "Catalog"], ["chat", "💬", "Chat"], ["wardrobe", "👗", "Wardrobe"], ["pose", "🧍‍♀️", "Pose"],
  ["scene", "🏞️", "Scene"], ["photoshoot", "📸", "Photoshoot"], ["studio", "🎞️", "Video studio"]];

(function () {
  const home0 = VIEWS.home;
  VIEWS.home = (m) => {
    home0(m);
    const open = id => { if (VIEWS[id]) go(id); else toast("That page is not ready yet.", ""); };
    const main = h("div", { class: "tool-grid main", id: "firstRunTools" }, FIRST_RUN_MAIN.map(t =>
      h("button", { class: "tool-card" + (t[4] ? " big" : ""), id: "tool-" + t[0], type: "button", onclick: () => open(t[0]) },
        h("span", { class: "door-ic" }, t[1]), h("b", {}, t[2]), h("span", { class: "hint" }, t[3]))));
    const soon = h("div", { class: "tool-grid soon", id: "firstRunSoon" }, FIRST_RUN_SOON.map(t =>
      h("div", { class: "tool-card soon", id: "soon-" + t[0], "aria-disabled": "true" },
        h("span", { class: "door-ic" }, t[1]), h("b", {}, t[2]), h("span", { class: "hint" }, "Coming soon"))));
    const box = h("div", { class: "firstrun" }, h("h2", {}, "What do you want to do?"),
      h("p", { class: "sub" }, "Build a video, extend one, or make a picture to start from. Setup (the gear) has the model downloads and the self-test."),
      main, h("h3", {}, "Coming soon"), soon);
    m.insertBefore(box, m.querySelector(".doors-grid"));  // the tools come first; Make, Play and Library stay below
  };

  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    await setup0(m);
    const on = await PHASE_TWO.shown();
    const say = h("span", { class: "hint", id: "phaseTwoSay" }, on ? "Shown." : "Hidden.");
    const box = h("input", { type: "checkbox", id: "phaseTwoSwitch", checked: on, onchange: async e => {
      try { await api("/api/phase_two", { method: "POST", body: { hidden: !e.target.checked } }); }
      catch (er) { toast(er.message, "bad"); e.target.checked = !e.target.checked; return; }
      go("setup");
    } });
    m.append(h("div", { class: "card", id: "phaseTwoCard" }, h("h2", {}, "Phase two"),
      h("p", { class: "hint" }, "My likeness, enrolment, Add photos and the 3D self-model are not part of the first run. Show them here when you want them."),
      h("label", { class: "row" }, box, " Show phase two screens "), say));
  };
})();
