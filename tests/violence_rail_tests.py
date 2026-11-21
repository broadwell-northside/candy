# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""No blood, violence, gore or hurtful depictions, in any section (the owner's rule, D-C-46).

A fixed word rail beside the minors and real-person rails. It only refuses more: nothing that was
refused before is accepted now. The app's own catalog prompts are scanned by count, never printed.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import safety  # noqa: E402

# One or two plain examples per word family in safety._VIOLENCE_PATTERNS.
REFUSED = [
    "a pool of blood on the floor", "a bloody shirt", "blood-soaked sand", "she is bleeding", "he bled",
    "a gory scene", "gore everywhere", "a gruesome sight", "entrails", "viscera",
    "a violent scene", "an act of violence", "a brutal beating", "open wounds", "a wounded soldier",
    "a serious injury", "an injured arm", "a bruised cheek", "a black eye",
    "a corpse", "a dead body", "a severed hand", "dismembered", "decapitated", "a beheading", "mutilated", "impaled",
    "a murder scene", "kill him", "killing spree", "a slaughter", "a massacre",
    "being tortured", "stabbed in the back", "a stabbing", "strangled", "choking her", "suffocating", "asphyxiated",
    "badly beaten", "beating him", "punching the man", "she slaps him", "a fist fight", "a bar brawl",
    "abusive", "abused", "an assault", "raped",
    "self-harm", "suicidal", "a noose",
    "he hurts her", "harming the animal", "screaming in pain", "in agony",
    # The review's 24 phrases at ea599a1: each passed the first word list.
    "an open wound", "a deep wound on his arm", "gunshot wound",
    "shot dead on the ground", "a man shot in the chest", "bullet holes in his body",
    "throat slit", "slashed throat", "hanged from a tree", "lynching",
    "a dead man", "dying soldier", "war scene with dead soldiers", "execution by firing squad", "burned alive", "a man on fire",
    "beating a man with a bat", "kicking a man on the ground", "a woman being whipped", "battered face",
    "holding a knife to his neck", "guts spilling out", "broken bones sticking out", "zombie eating flesh",
]
# The same words through the tricks the minors rail already undoes.
TRICKS = ["b l o o d on the wall", "bl00d", "g.o.r.e", "v1olent", "to​rture", "kіll him"]  # the last one has a Cyrillic i
# Ordinary words that contain or resemble a pattern, and stay allowed.
ALLOWED = [
    "blood orange juice on the table", "a blood-red dress", "blood red lipstick", "a blood moon over the sea",
    "a bloody mary at the bar", "a velvet choker", "killer heels", "a skilled dancer", "a brutalist concrete building",
    "a scarf wound around her neck", "wind-up toy", "harmony of colours", "a harmless smile", "painterly style",
    "striking a model pose", "a photo shoot at golden hour", "a grape harvest", "draped in linen", "whipped cream",
    "a fruit punch bowl", "a hit song playing", "the beating heart of the city", "a pharmacy sign", "a therapist's office",
    "hurtling down the slope", "a stable door", "a constable", "an establishing shot", "hammered gold jewellery",
    "linen shirt, warm sand", "soft window light from one side", "a 30-year-old adult woman smiling",
    # Everyday meanings next to the review's patterns.
    "a headshot portrait", "shooting a photo", "photo shot in the studio", "hair wound into a bun", "battered fish",
    "a dress with a thigh slit", "hanging plants", "kicking a ball", "beating heart", "executive portrait",
    "drop-dead gorgeous", "a woman with black eyes", "a Gore-Tex jacket", "a shot of espresso", "a sale sign",
]


def _catalog_refusals():
    """How many of the app's own catalog strings the rail would refuse. Ids only; a string is never returned."""
    import catalog
    hits, seen = [], [0]

    def walk(x, where):
        if isinstance(x, dict):
            ident = str(x.get("id") or "")
            for key, value in x.items():
                walk(value, where + [ident or str(key)])
        elif isinstance(x, (list, tuple)):
            for index, value in enumerate(x):
                walk(value, where + [str(index)])
        elif isinstance(x, str):
            seen[0] += 1
            if not safety.check_violence(x)[0]:
                hits.append("/".join(where)[:60])

    for name in dir(catalog):
        value = getattr(catalog, name)
        if name.isupper() and isinstance(value, (list, tuple, dict)):
            walk(value, [name])
    return seen[0], hits


def unit(check):
    print("\n[violence] No blood, violence, gore or hurtful depictions, in any section")
    missed = [text for text in REFUSED if safety.check_prompt(text)[0]]
    check("every violence word family is refused in a prompt (%d examples)" % len(REFUSED), not missed, missed[:6])
    said = safety.check_prompt("a pool of blood")[1]
    check("the refusal says what and that it holds in every section", "blood, violence, gore" in said and "any section" in said, said)
    missed = [text for text in TRICKS if safety.check_prompt(text)[0]]
    check("spaced, dotted, look-alike and zero-width spellings are refused too", not missed, missed)
    wrong = [(text, safety.check_violence(text)[1]) for text in ALLOWED if not safety.check_violence(text)[0]]
    check("ordinary words that only resemble a pattern stay allowed (%d examples)" % len(ALLOWED), not wrong, wrong[:4])
    check("the rail is part of the check every section runs first", not safety.check_all("soft light", "a gory scene")[0])
    # The text check every job runs (pipelines._txt), in each section. The 18+ section gets no exception.
    import pipelines
    for section in ("default", "adult"):
        pipelines.set_area(section)
        try:
            pipelines._txt("soft light", "a gory scene")
            said = ""
        except pipelines.UserError as exc:
            said = str(exc)
        finally:
            pipelines.set_area("default")
        check("a job's text check refuses a violence word in the %s section" % ("18+" if section == "adult" else "everyday"),
              "blood, violence, gore" in said, said)
    workflow = {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a corpse in the snow"}}}
    check("a raw workflow with a violence word in any text is refused", not safety.check_workflow(workflow)[0])
    check("a raw workflow with ordinary text still passes this rail",
          safety.check_workflow({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a blood orange on a plate"}}})[0])
    check("a LoRA whose name carries a violence word is refused", not safety.check_lora("gore_style_v2.safetensors")[0])
    check("a LoRA whose trigger words carry one is refused",
          not safety.check_lora("shore_style.safetensors", triggers=["shore", "bloody"])[0])
    check("a LoRA whose description carries one is refused",
          not safety.check_lora("shore_style.safetensors", meta={"description": "soft light, then a stabbing"})[0])
    avoid = safety.safe_negative("blurry")
    check("the avoid list always carries the violence words, beside the child and teen words",
          all(word in avoid for word in ("blood", "gore", "violence", "wounds", "injury", "child", "teen")), avoid)
    check("an empty avoid list still gets them", "gore" in safety.safe_negative("") and "child" in safety.safe_negative(None))
    check("the earlier refusals still refuse", not safety.check_prompt("a teen girl")[0] and not safety.check_prompt("age 17")[0])
    seen, hits = _catalog_refusals()
    check("none of the app's own catalog prompts is refused by the new rail (%d strings)" % seen, seen > 500 and not hits, hits[:8])


def e2e(a, mock_url):
    import requests
    check = a.check
    print("\n[violence] The rail through the app")
    dna = {"gender": "woman", "age": 30, "style": "photo", "name": "Ines"}
    job = a.job("create", {"dna": dna, "count": 1, "extra_scene": "standing in a pool of blood"})
    check("a create prompt with a violence word is refused through the app",
          job["status"] in ("refused", "error") and "blood, violence, gore" in (job.get("error") or ""), job.get("error"))
    saved = a.post("/api/characters", json=dict(dna, name="Gore Queen"))
    check("a character name with a violence word is refused", saved.status_code == 400 and "blood, violence, gore" in saved.text, saved.text[:200])
    fine = a.job("create", {"dna": dna, "count": 1, "extra_scene": "holding a blood orange, blood-red dress"})
    check("ordinary words near the rail still make a picture", fine["status"] == "done", fine.get("error"))
    sent = json.dumps(requests.get(mock_url + "/mock/log").json()[-1])
    check("the picture's avoid list carries the violence words and the child words", "gore" in sent and "wounds" in sent and "child" in sent)
