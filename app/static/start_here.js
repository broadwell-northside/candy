/* PRIVATE BUILD — NOT FOR DISTRIBUTION
   "Start here": the first-weekend guide as one page inside the app. Text only; links open the matching tool.
   Loaded after firstrun.js. It adds the page "start-here" and nothing on the server. */
"use strict";

(function () {
  if (typeof DOORS !== "undefined" && !DOORS.includes("start-here")) DOORS.push("start-here");  // same calm layout as Home

  // A link is [label, tab, card id or null]. Setup cards are scrolled into view once the page has drawn.
  const L = {
    models: ["Setup → Models", "setup", "modelsCard"], setup: ["Setup", "setup", null], create: ["Make a picture", "create", null],
    build: ["Build a video", "video-build", null], extend: ["Extend a video", "video-extend", null],
    selftest: ["Setup → Self-test", "setup", "selfTestCard"], keys: ["Setup → API keys", "setup", "apiKeysCard"],
  };
  const B = t => ({ b: t });
  const I = t => ({ i: t });
  const A = k => ({ a: L[k] });

  const GUIDE = [
    { h: "The idea in one minute", body: [
      ["p", ["Candy turns words into pictures and pictures into video, on your own Mac."]],
      ["ul", [
        [B("A model"), " is a large file that knows how to draw. You download it once. Candy uses one for pictures and one for video."],
        [B("A prompt"), " is the sentence you type. Clear, plain sentences work best."],
        [B("A seed"), " is the dice roll. Same words, new seed, different result. “Try again” just rolls again."],
        [B("The age check"), " looks at every result. If it is unsure, the result is deleted and you are offered another try. That is normal, not a failure."],
        [B("A LoRA"), " is a small add-on file that teaches a model one thing, such as one person. Your own likeness will be a LoRA, later."],
      ]],
      ["p", ["The basic loop is always the same: ", B("words → picture → video → longer video.")]],
    ] },
    { h: "Part 1. Get ready (about an hour, mostly waiting)", body: [
      ["ol", [
        [B("Free up disk space."), " Aim for 100 GiB free or more. Candy refuses to download anything that would leave less than 50 GiB free. To check: Apple menu → About This Mac → More Info → Storage."],
        [B("Start Candy."), " In Finder, open ", { code: "/Users/dfuuu/candy/worktrees/next" }, " and double-click ", B("start_mac.command"),
          ". A window with text opens (leave it open) and your browser shows Candy. To stop later: click that text window and press Ctrl-C."],
        [B("Download the models."), " Open ", A("models"), " (the gear, then the ", B("Models"), " card) and press ", B("Download"), " on these three, one at a time:",
          { ul: [
            [B("Automatic age check"), " (small). Nothing works without it."],
            [B("Small video model (Wan 2.2 5B)"), ", about 18 GB."],
            [B("Fast drafts + poses (Z-Image Turbo)"), ", about 24 GB."],
          ] },
          "Each shows its size and the free space. If one says it would break the floor, free more space."],
      ]],
    ] },
    { h: "Part 2. Your first picture (a made-up person)", body: [
      ["ol", [
        ["On ", B("Home"), ", choose ", A("create"), "."],
        ["Type what you want to see. Describe four things: who, wearing what, where, what light. Example: ",
          I("A woman of 30 in a yellow sundress standing on a beach at sunset, smiling at the camera, soft warm light.")],
        ["Give the person's age when asked. It must be 21 or more."],
        ["Press the button and wait. The first picture takes longest because the model has to load."],
        ["Not happy? Change one thing in the sentence, or try again for a new roll. Change one thing at a time so you learn what each word does."],
      ]],
    ] },
    { h: "Part 3. Your first video", body: [
      ["ol", [
        ["On ", B("Home"), ", choose ", A("build"), "."],
        ["Pick the picture you just made as the start, or type a description instead."],
        ["Say what moves, in one short sentence. Example: ", I("She smiles and slowly waves at the camera.")],
        ["Choose a short length. On this Mac, expect roughly 10 minutes of waiting per 4 seconds of video."],
        [B("Keep the person facing the camera for now."), " If the face turns away, the age check cannot see it and the clip is not saved. This is being improved."],
      ]],
    ] },
    { h: "Part 4. Make it longer", body: [
      ["ol", [
        ["On ", B("Home"), ", choose ", A("extend"), " and pick your clip."],
        ["Type what happens next. Example: ", I("She turns her head and looks out at the sea.")],
        ["Each press adds another part that starts where the last one ended. Three or four parts is a sensible limit for now; after that the picture slowly drifts."],
      ]],
    ] },
    { h: "Part 5. Check that everything works", body: [
      ["p", [B("Setup → Self-test → Run the self-test."), " It makes a picture, a clip, a longer clip and a 3D shape of a made-up adult and shows pass or fail for each step. With only the three models above, the 3D step will not pass; that is fine. "], ],
      ["p", ["Open ", A("selftest"), "."]],
    ] },
    { h: "What to practise this weekend", body: [
      ["ul", [
        ["Write five different prompts for the same person and compare the results."],
        ["Change only the light (“soft morning light”, “studio softbox”, “golden hour”) and watch what it does."],
        ["Change only the camera (“close portrait”, “full body”, “from slightly below”)."],
        ["Make one 4-second clip, then extend it twice."],
        ["Keep notes on which sentences gave you what you wanted. That skill carries over to everything later."],
      ]],
    ] },
    { h: "What comes next (not ready yet)", body: [
      ["p", ["These are being built now. They appear in the app when they land."]],
      ["ol", [
        [B("Turn on Phase two"), " in Setup. This shows the likeness tools."],
        [B("Enrol at the camera"), ", about a minute. This ties the app to you, and only you."],
        [B("Add photos"), ": point it at your folders. It keeps photos where your face is visible and matches."],
        [B("Train."), " This makes your likeness LoRA. It can take hours; leave the Mac plugged in."],
        [B("Create."), " The same loop as above, with you in place of the made-up person."],
      ]],
      ["p", ["Your photos never leave this Mac. Do not paste or upload them into any chat."]],
    ] },
    { h: "If something goes wrong", body: [
      ["ul", [
        [B("“Would leave less than 50 GB”"), " → free more disk space."],
        [B("“The age check flagged this result”"), " → press retry; it rolls again."],
        [B("Nothing happens for a long time"), " → the first run of each model is slow. Look at the text window for movement before giving up."],
        [B("Any other error"), " → copy the exact message into the orchestrator session."],
      ]],
    ] },
    { h: "Words you will see", body: [
      ["ul", [
        [B("Engine"), ": the program underneath that does the drawing (ComfyUI). Candy drives it for you."],
        [B("Everyday section / 18+ section"), ": two areas of the app. Everything in this guide is everyday."],
        [B("Gallery"), ": where everything you make is kept."],
        [B("Hosted engine"), ": an optional outside video service. It needs a key (typed once in ", A("keys"), "), sends your words out, and is never used for your likeness. You can ignore it."],
      ]],
    ] },
  ];

  function open(link) {
    const [, tab, card] = link;
    go(tab);
    if (!card) return;
    let tries = 0;
    const find = () => {
      const el = document.getElementById(card);
      if (el) { el.scrollIntoView({ block: "start" }); return; }
      if (++tries < 40) setTimeout(find, 250);
    };
    find();
  }

  function inline(parts) {
    return parts.map(p => {
      if (typeof p === "string") return p;
      if (p.b) return h("b", {}, p.b);
      if (p.i) return h("em", {}, p.i);
      if (p.code) return h("code", {}, p.code);
      if (p.a) return h("a", { href: "#", class: "guide-link", onclick: e => { e.preventDefault(); open(p.a); } }, p.a[0]);
      if (p.ul) return h("ul", {}, p.ul.map(li => h("li", {}, inline(li))));
      return "";
    });
  }

  VIEWS["start-here"] = (m) => {
    m.append(
      h("div", { class: "home-head" },
        h("div", {}, h("h1", {}, "Candy: your first weekend, step by step"),
          h("p", { class: "sub" }, "Everything here is clothed and everyday. Nothing in this guide uploads anything or sends anything off your Mac.")),
        h("button", { class: "btn small", id: "guideHome", type: "button", onclick: () => go("home") }, "⌂ Home")),
      h("p", { class: "hint" }, "One honest note first: this build has not been run for real yet. Your first clicks are the first real test. " +
        "If a step shows an error, that is expected now and then; copy the message into the orchestrator session and it gets fixed."),
      h("div", { class: "guide", id: "startHereGuide" }, GUIDE.map((sec, n) => h("section", { class: "card guide-sec", id: "guide-" + n },
        h("h2", {}, sec.h),
        sec.body.map(([kind, items]) => kind === "p" ? h("p", {}, inline(items))
          : h(kind, {}, items.map(li => h("li", {}, inline(li)))))))));
  };
})();
