// Add photos: the owner's own photos from disk, kept only if they show the enrolled person (D-C-54).
// A step between Enrol and Train on the My likeness card. Add a whole folder or pick files; each photo gets a plain result.
// It does nothing when that card is not on the page (before enrolment the step stays out of the way), so whatever hides
// the card hides this too. No picture is shown here: the page lists names and results only.
(function () {
  const PHOTO_WORDS = "Add photos of yourself from this computer, a whole folder or single files. A photo is kept only if it shows " +
    "exactly one face, that face is yours, and the age check clears it. Photos of your body count when your face is in them. " +
    "Anything else is dropped, and the list below says why. Photos stay on this Mac.";
  const READ = /\.(jpe?g|png)$/i;                      // what the app reads
  const OTHER_PICTURE = /\.(heic|heif|webp|tiff?|gif|bmp|avif)$/i;   // pictures it cannot read: listed, not sent

  async function decorate() {
    const card = document.getElementById("ownerCard");
    const steps = card && card.querySelector("#ownerSteps");
    const panel = card && card.querySelector("#ownerPanel");
    const say = card && card.querySelector("#ownerSay");
    if (!steps || !panel || !say || steps.querySelector("#ownerPhotosBtn")) return;
    let st;
    try { st = await api("/api/owner/status"); } catch (e) { return; }
    const train = steps.querySelector("#ownerTrainBtn");
    if (!train) return;

    async function unlocked(then) {
      let now;
      try { now = await api("/api/owner/status"); } catch (e) { say.textContent = e.message; return; }
      if (now.unlocked) return then();
      const pass = h("input", { id: "ownerPhotosPass", type: "password", autocomplete: "current-password", placeholder: "Your passphrase" });
      const go = h("button", { class: "btn small", type: "button", id: "ownerPhotosUnlock", onclick: async () => {
        try { await api("/api/owner/unlock", { method: "POST", body: { passphrase: pass.value } }); }
        catch (e) { say.textContent = e.message; return; }
        row.remove();
        then();
      } }, "Unlock");
      const row = h("div", { id: "ownerPhotosUnlockRow" }, h("label", { class: "f" }, "Passphrase"), pass, go);
      panel.prepend(row);
      say.textContent = "Type your passphrase to go on. An unlock lasts five minutes.";
    }

    function photosPanel() {
      panel.replaceChildren(h("p", { id: "ownerPhotosWords" }, PHOTO_WORDS));
      const list = h("ol", { id: "ownerPhotosList", style: { fontSize: ".9rem", paddingLeft: "1.4em" } });
      const totals = h("p", { id: "ownerPhotosTotals", class: "hint" });
      const folder = h("input", { id: "ownerPhotoFolder", type: "file", webkitdirectory: true, multiple: true });
      const files = h("input", { id: "ownerPhotoFile", type: "file", accept: "image/jpeg,image/png", multiple: true });
      const go = h("button", { class: "btn", type: "button", id: "ownerPhotoAdd" }, "Add these photos");
      const stop = h("button", { class: "btn small", type: "button", id: "ownerPhotosStop", disabled: true }, "Stop");
      const clear = h("button", { class: "btn small", type: "button", id: "ownerPhotosRemove" }, "Remove my added photos");
      let stopped = false;
      stop.onclick = () => { stopped = true; stop.disabled = true; };
      const note = (name, text, bad) => list.append(h("li", { class: bad ? "err" : "" }, name + " — " + text));
      go.onclick = () => unlocked(async () => {
        const chosen = [...Array.from(folder.files || []), ...Array.from(files.files || [])];
        if (!chosen.length) { say.textContent = "Choose a folder or some photos first."; return; }
        const name = f => f.webkitRelativePath || f.name;
        const send = chosen.filter(f => READ.test(f.name));
        const unread = chosen.filter(f => !READ.test(f.name) && OTHER_PICTURE.test(f.name));
        const ignored = chosen.length - send.length - unread.length;
        list.replaceChildren(); totals.textContent = "";
        stopped = false; go.disabled = true; stop.disabled = false;
        let kept = 0, dropped = 0, fatal = "";
        try {
          for (const file of send) {
            if (stopped) break;
            const body = new FormData();
            body.append("file", file, file.name);
            try {
              const got = await api("/api/owner/photos", { method: "POST", body });
              if (got.kept) { kept++; note(name(file), "kept"); }
              else { dropped++; note(name(file), "dropped: " + got.message + (got.score != null ? " (match " + Number(got.score).toFixed(2) + ")" : ""), true); }
            } catch (e) {
              fatal = e.message; dropped++; note(name(file), "stopped: " + e.message, true);
              break;   // a problem that is not about the photo (not enrolled, checker off, locked): the same for every file
            }
            say.textContent = "Checked " + (kept + dropped) + " of " + send.length + " ...";
          }
        } finally { go.disabled = false; stop.disabled = true; folder.value = ""; files.value = ""; }
        for (const f of unread) note(name(f), "not read: this app reads JPEG and PNG; export it as JPEG", true);
        const left = send.length - kept - dropped;
        say.textContent = kept + " kept, " + dropped + " dropped" + (unread.length ? ", " + unread.length + " not read" : "") +
          (left > 0 ? ", " + left + " not checked (stopped)" : "") + ".";
        totals.textContent = (ignored ? ignored + " other file" + (ignored === 1 ? "" : "s") + " in the folder were left alone. " : "") +
          (fatal ? "Stopped at a problem that is not about the photo: " + fatal : "");
      });
      clear.onclick = () => unlocked(async () => {
        try {
          const got = await api("/api/owner/photos", { method: "DELETE" });
          say.textContent = "Removed " + got.removed + " added photos.";
        } catch (e) { say.textContent = e.message; }
      });
      say.textContent = "Choose a folder, or photos, of yourself.";
      panel.append(h("label", { class: "f" }, "A folder of photos"), folder, h("label", { class: "f" }, "Or single photos"), files,
        h("div", { class: "row", style: { marginTop: "8px" } }, go, stop, clear), totals, list);
    }

    steps.insertBefore(h("button", { class: "btn primary", type: "button", id: "ownerPhotosBtn", disabled: !st.enrolled, onclick: photosPanel }, "Add photos"), train);
    steps.insertBefore(document.createTextNode(" "), train);
  }

  const setup0 = VIEWS.setup;
  VIEWS.setup = async (m) => {
    await setup0(m);
    await decorate();
  };
})();
