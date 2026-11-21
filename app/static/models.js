// Setup > Models: one Download button per model group. Ak presses it; the server checks the free space at that
// moment and refuses below the 50 GB floor. Progress is polled; a stopped download resumes on the next press.
(function () {
  const gb = (n) => (n == null ? "?" : (n / 1e9).toFixed(1) + " GB");
  function row(g, free, refresh) {
    const st = g.state || {};
    const running = st.status === "running";
    const btn = h("button", { class: "btn", disabled: !g.can_download || running, title: g.reason || "" }, g.installed ? "Installed" : (running ? "Downloading…" : "Download"));
    const prog = h("div", { class: "hint" });
    if (running) prog.textContent = (st.file || "") + " — " + gb(st.done) + " of " + gb(st.total);
    else if (st.status === "error") prog.textContent = "Stopped: " + st.error + " Press Download to pick up where it left off.";
    else if (st.status === "done") prog.textContent = "Done. Every file matched its pinned check.";
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        const r = await api("/api/models/download", { method: "POST", body: { group: g.id } });
        toast("Download started. " + gb(r.free_bytes) + " was free when you pressed it.");
      } catch (e) { toast(e.message, "bad"); }
      refresh();
    };
    return h("div", { class: "row" }, h("b", {}, g.help || g.id), " ",
      h("span", { class: "hint" }, g.size_bytes ? "(" + gb(g.size_bytes) + (g.need_bytes != null && g.need_bytes < g.size_bytes ? ", " + gb(g.need_bytes) + " to go" : "") + ")" : "(size not known yet)"),
      " ", btn, g.can_download ? null : h("div", { class: "hint" }, g.reason), g.note ? h("div", { class: "hint" }, g.note) : null, prog);
  }
  function card() {
    const box = h("div", { class: "card", id: "modelsCard" }, h("h2", {}, "Models"));
    let timer = null;
    async function refresh() {
      let j;
      try { j = await api("/api/models/groups"); } catch (e) { box.replaceChildren(h("h2", {}, "Models"), h("div", { class: "err" }, e.message)); return; }
      box.replaceChildren(h("h2", {}, "Models"),
        h("p", { class: "hint", id: "modelsStartWith" }, "New here? Start with three: Automatic age check, Small video model (Wan 2.2 5B), and Fast drafts + poses (Z-Image Turbo)."),
        h("p", { class: "hint" }, "Free now: " + gb(j.free_bytes) + ". A download is refused if it would leave less than 50 GB free. Files come only from pinned links, as .safetensors or .gguf, each checked by SHA256; nothing runs from a download."),
        ...j.groups.map(g => row(g, j.free_bytes, refresh)));
      clearTimeout(timer);
      if (j.groups.some(g => (g.state || {}).status === "running") && document.body.contains(box)) timer = setTimeout(refresh, 2000);
    }
    refresh();
    return box;
  }
  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    await setup0(m);
    m.append(card());
  };
})();
