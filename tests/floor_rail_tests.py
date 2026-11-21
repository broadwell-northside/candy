"""The hard floor by category (D-C-50): the violence rail extended by plain category words.

Fixed in code, the same in every section. Categories are named in words; the tests use plain category words only,
one per pattern, and every pattern must be hit by one of them so none is dead. Nothing refused before is accepted now:
the earlier lists are pinned by count and by the earlier tests, which still run.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import safety  # noqa: E402

CATEGORIES = ("people", "animals", "harm")
# One plain category word or short phrase per pattern. Category names are in safety.FLOOR_REASONS.
EXAMPLES = {
    "people": [
        "non-consensual", "nonconsensual", "without her consent", "without consent", "against her will",
        "coerced", "coercion", "forced to obey", "forced into silence", "forcing her to", "blackmail", "blackmailed", "extortion",
        "molested", "molestation", "groped", "groping", "harassment", "harassed", "a stalker", "stalking her",
        "bullied", "bullying", "humiliating", "humiliation", "degrading", "degrade her", "demeaning", "dehumanising", "dehumanized",
        "exploitation", "drugged her", "spiking her drink", "voyeurism",
    ],
    "animals": [
        "animal cruelty", "animal abuse", "animal torture", "animal sacrifice", "cruelty to animals", "cruelty towards pets",
        "cockfighting", "bullfighting", "bear baiting", "dog fighting", "dogfighting",
        "torturing a dog", "kicking the cat", "beating a horse", "starving the dog", "neglected animals", "poisoning a bird",
    ],
    "harm": [
        "kidnapped", "kidnapping", "human trafficking", "sex trafficking", "trafficked", "a trafficker", "enslaved", "slavery",
        "taken hostage", "a hostage", "held captive", "genocide", "ethnic cleansing", "terrorism", "a terrorist", "hate crime",
        "paedophilia", "pedophile", "necrophilia", "bestiality", "incest", "buried alive", "skinned alive",
    ],
}
# Ordinary phrases that share a word with a pattern and stay allowed.
ALLOWED = [
    "forced perspective photo", "a degraded vintage film look", "a cruel queen in a velvet gown", "a dogfight between two planes",
    "a bomb squad robot toy", "poached eggs on toast", "a trafficking light", "a stalk of celery", "a bully breed puppy sitting",
    "slave to the rhythm lyrics on a poster", "a consensual agreement contract", "a cheerful consent form", "bull riding at a rodeo",
    "animal print dress", "a cat sleeping on a sofa", "a dog running on the beach", "terrier puppy playing", "a horse in a meadow",
    "a fox in the snow", "kind to animals sign", "a bird on a branch", "a humble farmer", "an exploited loophole",
    "a cat stalking across the roof", "hitched a horse to the cart", "a bear in the woods",
    "feeding the dog", "kicking back on the sofa", "a cheerful barista",
]
# The same words through the tricks the other rails already undo (spaced, look-alike letters, l33t, zero-width).
TRICKS = ["k i d n a p p e d", "bl4ckmail", "kіdnapped", "non​consensual", "g.e.n.o.c.i.d.e", "h0stage", "an1mal cruelty"]
# Lengths of the earlier lists when this rail was added: they may grow, never shrink.
EARLIER = {"_MINOR_PATTERNS": 51, "_VIOLENCE_PATTERNS": 77, "_ADULT_AREA_PATTERNS": 14, "_REAL_PERSON_PATTERNS": 27}


def unit(check):
    print("\n[floor] The hard floor by category: acts against people, cruelty to animals, other grave harm")
    check("the floor has exactly the named categories", tuple(safety.FLOOR_PATTERNS) == CATEGORIES and
          set(safety.FLOOR_REASONS) == set(CATEGORIES), list(safety.FLOOR_PATTERNS))
    total = sum(len(v) for v in EXAMPLES.values())
    for cat in CATEGORIES:
        missed = [w for w in EXAMPLES[cat] if safety.check_prompt(w)[0]]
        check("every %s category word is refused in a prompt (%d)" % (cat, len(EXAMPLES[cat])), not missed, missed[:6])
        wrong = [w for w in EXAMPLES[cat] if safety.check_violence(w)[0]]
        check("and by the violence rail itself, so every caller has it (%s)" % cat, not wrong, wrong[:6])
        said = safety.check_prompt(EXAMPLES[cat][0])[1]
        check("the %s refusal names its category and that it holds in every section" % cat,
              safety.FLOOR_REASONS[cat] in said and "any section" in said, said)
        dead = [p for p in safety.FLOOR_PATTERNS[cat] if not any(re.search(p, w, re.I) for w in EXAMPLES[cat])]
        check("no %s pattern is untested: one category word hits each" % cat, not dead, len(dead))
    check("%d category words in all" % total, total >= 70, total)
    missed = [w for w in TRICKS if safety.check_prompt(w)[0]]
    check("spaced, dotted, look-alike, l33t and zero-width spellings are refused too", not missed, missed)
    wrong = [w for w in ALLOWED if not safety.check_prompt(w)[0]]
    check("ordinary phrases that only share a word stay allowed (%d)" % len(ALLOWED), not wrong, wrong[:4])

    # nothing refused before is accepted now
    import violence_rail_tests
    still = [w for w in violence_rail_tests.REFUSED if safety.check_prompt(w)[0]]
    check("every earlier violence example is still refused (%d)" % len(violence_rail_tests.REFUSED), not still, still[:4])
    wrong = [w for w in violence_rail_tests.ALLOWED if not safety.check_violence(w)[0]]
    check("and the earlier allowed list is still allowed", not wrong, wrong[:4])
    short = {name: (len(getattr(safety, name)), n) for name, n in EARLIER.items() if len(getattr(safety, name)) < n}
    check("no earlier pattern list shrank", not short, short)
    for text in ("a teen girl", "age 17", "looks like a real person", "a face swap"):
        check("an earlier minors, age and real-person refusal still refuses (%s)" % text.split()[0], not safety.check_prompt(text)[0])
    seen, hits = violence_rail_tests._catalog_refusals()
    check("none of the app's own catalog prompts is refused by the floor (%d strings)" % seen, seen > 500 and not hits, hits[:8])

    # the places a word can come in
    import pipelines
    for section in ("default", "adult"):
        pipelines.set_area(section)
        try:
            pipelines._txt("soft light", "non-consensual")
            said = ""
        except pipelines.UserError as exc:
            said = str(exc)
        finally:
            pipelines.set_area("default")
        check("a job's text check refuses a floor word in the %s section" % ("18+" if section == "adult" else "everyday"),
              safety.FLOOR_REASONS["people"] in said, said)
    check("a raw workflow with a floor word in any text is refused",
          not safety.check_workflow({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "cruelty to animals"}}})[0])
    check("a LoRA whose name, trigger words or description carry one is refused",
          not safety.check_lora("kidnapped_v2.safetensors")[0]
          and not safety.check_lora("shore_style.safetensors", triggers=["shore", "slavery"])[0]
          and not safety.check_lora("shore_style.safetensors", meta={"description": "soft light, then genocide"})[0])
    check("the group, minors and age rails still run first and unchanged: an under-21 age wins over a floor word",
          "under 21" in safety.check_prompt("age 17, non-consensual")[1] or "minor" in safety.check_prompt("age 17, non-consensual")[1])
