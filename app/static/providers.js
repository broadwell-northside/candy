// API keys (Setup) and "Video (API)" (Video studio). A key is typed once, goes to the Mac's Keychain, and is
// never shown again: the page only ever learns "saved" or "not saved".
(function () {
  async function state() {
    try { return await api("/api/providers"); } catch (e) { return null; }
  }

  function keyRow(k, after) {
    const input = h("input", { type: "password", autocomplete: "off", spellcheck: "false", placeholder: k.configured ? "Saved. Paste a new key to replace it." : "Paste the key here", style: { width: "100%" } });
    const say = h("div", { class: "hint" }, k.configured ? "✓ Saved in the Keychain" : "Not saved yet");
    const save = h("button", { class: "btn small", onclick: async () => {
      const value = input.value.trim();
      input.value = "";  // gone from the page at once, whatever happens next
      if (!value) return toast("Paste the key first.", "bad");
      try { await api("/api/providers/key", { method: "POST", body: { name: k.name, key: value } }); toast("Key saved.", "good"); after(); }
      catch (e) { toast(e.message, "bad"); }
    } }, "Save");
    const remove = k.configured ? h("button", { class: "btn small", onclick: async () => {
      if (!confirm("Remove this key from the Keychain?")) return;
      try { await api("/api/providers/key/" + k.name, { method: "DELETE" }); after(); } catch (e) { toast(e.message, "bad"); }
    } }, "Remove") : null;
    return h("div", { style: { margin: "10px 0" } }, h("b", {}, k.label), say, h("div", { class: "row", style: { marginTop: "6px" } }, input, save, remove));
  }

  async function keysCard() {
    const card = h("div", { class: "card", id: "apiKeysCard" });
    const draw = async () => {
      const st = await state();
      card.innerHTML = "";
      card.append(h("h2", {}, "API keys"));
      if (!st) { card.append(h("div", { class: "err" }, "This part answers only on this computer.")); return; }
      card.append(h("div", { class: "hint" }, "Optional. A key lets the app use a hosted service for video or text. It is kept in this Mac's Keychain and is not shown again. Your likeness and anything in the 18+ area are never sent to a hosted service."));
      st.keys.forEach(k => card.append(keyRow(k, draw)));
      const box = h("input", { type: "checkbox" });
      box.checked = !!st.hosted_media;
      box.onchange = async () => {
        let body = { on: box.checked };
        if (box.checked) {
          if (!confirm("Allow pictures and video to be sent to a hosted service? Only pictures that passed the age check and are not your likeness can go.")) { box.checked = false; return; }
          body.confirm = "I understand";
        }
        try { await api("/api/providers/hosted-media", { method: "POST", body }); } catch (e) { toast(e.message, "bad"); box.checked = !box.checked; }
      };
      card.append(h("label", { class: "row" }, box, h("span", {}, "Allow a picture to be sent to a hosted service (off by default)")));
    };
    await draw();
    return card;
  }

  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    await setup0(m);
    m.append(await keysCard());
  };

  const studio0 = VIEWS.studio;
  VIEWS.studio = async (m) => {
    await studio0(m);
    const st = await state();
    if (!st) return;
    const ready = (st.keys.find(k => k.name === "dashscope") || {}).configured;
    const res = resultsBox("A clip made by the hosted service appears here.");
    let start = null, from = null;
    const words = h("textarea", { rows: 3, placeholder: "e.g. she smiles and turns to the camera", title: "Plain words. Fictional adults only." });
    let secs = 5;
    const secLbl = h("b", {}, secs + " s");
    const pic = h("div", { class: "hint" }, "No picture: words only.");
    const pick = h("button", { class: "btn small", onclick: async () => {
      if (!st.hosted_media) return toast("Turn on “Allow a picture to be sent to a hosted service” in Setup first.", "bad");
      const x = await pickFromGallery({ type: "image", roles: ["made", "my_character"], title: "Start picture" });
      if (x) { start = x; from = null; clipNote.textContent = "No clip chosen."; pic.textContent = "Start picture: " + (x.title || x.kind); }
    } }, "Choose a start picture");
    const clipNote = h("div", { class: "hint" }, "No clip chosen.");
    const pickClip = h("button", { class: "btn small", onclick: async () => {
      if (!st.hosted_media) return toast("Turn on “Allow a picture to be sent to a hosted service” in Setup first.", "bad");
      const x = await pickFromGallery({ type: "video", roles: ["made", "my_character"], title: "Clip to continue" });
      if (x) { from = x; start = null; clipNote.textContent = "Continuing: " + (x.title || x.kind) + " (its last frame is sent)"; pic.textContent = "No picture: words only."; }
    } }, "Continue a clip");
    const card = h("div", { class: "card", id: "videoApiCard" }, h("h2", {}, "Video (API)"),
      h("div", { class: "hint" }, "Made by a hosted Wan model. Short clips of made-up adults; it comes back to the gallery marked remote and age-checked like any clip. Your likeness never goes here."),
      ready ? null : h("div", { class: "warnt" }, "Add the Alibaba Model Studio key in ⚙️ Setup → API keys first."),
      h("label", { class: "f" }, "Describe it (for a continuation: what happens next)"), words,
      h("div", { class: "row", style: { marginTop: "8px" } }, pickClip, " ", clipNote),
      h("div", { class: "row", style: { marginTop: "8px" } }, pick, " ", pic),
      h("label", { class: "f" }, "Length ", secLbl),
      h("input", { type: "range", min: 2, max: 15, step: 1, value: secs, oninput: e => { secs = +e.target.value; secLbl.textContent = secs + " s"; } }),
      h("br"), h("button", { class: "btn", type: "button", id: "videoApiGo", onclick: () => {
        if (!ready) return toast("Add the key in Setup first.", "bad");
        if (!words.value.trim()) return toast("Describe what happens.", "bad");
        const p = { text: words.value.trim(), seconds: secs };
        if (from) p.extend_from = from.id;
        else if (start) p.image = start.id;
        runJob("video_api", p, res, { key: "studio-api", label: "Video (API): making the clip" });
      } }, "🌐 Send to the hosted service"));
    m.append(card, res);
  };
})();
