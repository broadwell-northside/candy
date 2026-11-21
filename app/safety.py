"""Hard safety rules for Easy Studio.

Easy Studio has NO "NSFW filter" for adult, fictional content. It has two hard limits that
cannot be switched off from the app:

1. Adults only. Text that describes minors or child-like characters is refused. Every
   person needs an explicit stated age of 21 or older. Missing, invalid, under-21, and
   conflicting ages are refused. Ages are not defaulted and not clamped. "adult" is added
   to every prompt and minor terms are added to every negative prompt.
2. No real people. No face-swap / likeness tools exist; text asking for celebrities, deepfakes
   or a real person's face is refused; raw workflows that use face-swap/identity nodes are refused;
   uploaded pictures need a role and a confirmation (see server.py).

The word lists err on the side of blocking. They are a guard rail, not a guarantee.
"""
import json
import os
import re
import unicodedata

_MINOR_PATTERNS = [
    r"\bchild(ren|ish|like|hood)?\b", r"\bkids?\b(?!\s*(gloves?|leather|skin|suede))", r"\bkiddie\b", r"\btoddlers?\b", r"\binfants?\b",
    r"\bbab(y|ies)\b(?!\s*(oil|blue|pink|powder|dol+|'?s\s*breath|hairs?\b))", r"\bminors?\b", r"\bunder\s*-?\s*age(d)?\b",
    r"\bteen(s|age|aged|ager|agers|y)?\b", r"\btweens?\b", r"\bpre-?teens?\b", r"\bpre-?pubescent\b",
    r"\bpubescent\b", r"\bpuberty\b", r"\bjuvenile\b", r"\bloli(con|ta)?s?\b", r"\bshota(con)?s?\b", r"\bcub\b",
    r"\b(young|little|small|tiny)\s+(girl|boy|girls|boys|one|ones)\b", r"\bschool\s*(girl|boy|kid)s?\b",
    r"\b(elementary|primary|middle|junior[\s-]*high|high)[\s-]*school(er|ers|[\s-]*student)?s?\b", r"\bgrade\s*schooler\b",
    r"\b(\d+(st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\s+grader?s?\b",
    r"\bfreshman\b", r"\bsophomore\b", r"\bjailbait\b", r"\bchild-?like\b", r"\byoung-?looking\b",
    r"\byouthful[\s-]*look(ing)?\b", r"\bbarely\s*legal\b",
    r"\b(step-?)?(daughter|niece|nephew)s?\b", r"\bstep-?sons?\b",
    r"\b(my|your|his|her|their|our|young|little|teenage|baby|infant|small)\s+sons?\b", r"\blittle\s+(sister|brother|sis|bro)\b",
    r"\bunderdeveloped\b", r"\bunderaged?\b", r"\bnot\s+(yet\s+)?(an\s+)?adult\b", r"\bunder\s*18\b",
    r"\bkindergart(e|en)n?(er)?s?\b", r"\bnursery\b(?!\s*rhyme)", r"\bdiaper\b", r"\bageplay\b", r"\bage\s*play\b",
    r"\bchibi\s+(girl|boy)\b", r"\b(is|being|she\'?s|he\'?s|i\'?m|turned|turns|turning)\s+(only\s+|just\s+|barely\s+|almost\s+|nearly\s+)?(1[0-9]|20|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty(?![\s-]*(one|two|three|four|five|six|seven|eight|nine)))\b(?!\s*(feet|ft|foot|inch|inches|cm|m|meters|metres|kg|lbs?|%|percent|degrees|times|minutes|mins|hours|seconds|of|out))",
    r"\byoung(ster|sters|ling|lings)\b", r"\bpre-?adult\b",
    r"\b(look|looks|looking|appear|appears|appearing|seem|seems|pass(es)?\s+for|act|acts|acting)\s+(like\s+|to\s+be\s+|about\s+|around\s+|maybe\s+)*(she\'?s\s+|he\'?s\s+|an?\s+)?(1[0-9]|20|[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty(?![\s-]*(one|two|three|four|five|six|seven|eight|nine)))\b(?!\s*(feet|ft|foot|inch|inches|cm|m|meters|metres|kg|lbs?|stone|%|percent|degrees))",
    r"\b(look|looks|looking|appear|appears)\s+(very\s+|really\s+|much\s+)?(younger|underage|young\s+for)\b", r"\bflat-?chested\s+(girl|child)\b", r"\bbaby\s*face\b",
]
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
              "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
              "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
MIN_AGE = 21  # youngest allowed age, in text and on the slider
_AGE_RE = re.compile(r"\b((?:(?:" + "|".join(_TENS) + r")[\s-]*)?(?:\d{1,2}|" + "|".join(_NUM_WORDS) + r"))\s*(-|\s)?\s*(years?|yrs?|y/?o|yo)\b(\s*-?\s*old)?", re.I)
_AGE_RE2 = re.compile(r"\b(aged?|age\s*:|age\s+of)\s*((?:(?:" + "|".join(_TENS) + r")[\s-]*)?(?:\d{1,2}|" + "|".join(_NUM_WORDS) + r"))\b", re.I)


def _num(g):
    """'17' -> 17, 'seventeen' -> 17, 'twenty-five' -> 25, 'thirty' -> 30."""
    g = g.lower().strip()
    if g.isdigit():
        return int(g)
    parts = [x for x in re.split(r"[\s-]+", g) if x]
    total = 0
    for x in parts:
        total += _TENS.get(x, _NUM_WORDS.get(x, 0)) if not x.isdigit() else int(x)
    return total or 99

_REAL_PERSON_PATTERNS = [
    r"\bceleb(rity|rities|s)?\b", r"\bdeep\s*-?fakes?\b", r"\bface\s*-?swap(ped|ping)?\b", r"\bswap\s+(the\s+|her\s+|his\s+)?face\b",
    r"\blikeness\b", r"\blook-?alike\b", r"\bdoppelg(a|ä)nger\b", r"\bimpersonat", r"\breal\s+(person|people|woman|man|girl|guy)\b",
    r"\b(my|our|his|her)\s+(ex|wife|husband|girlfriend|boyfriend|gf|bf|coworker|co-worker|colleague|neighbou?r|boss|classmate|crush|teacher|friend|roommate|sister|brother|mom|mum|mother|dad|father|cousin|aunt)\b",
    r"\bactress\b", r"\bactor\b", r"\binfluencer\b", r"\bpornstar\b", r"\bporn\s*star\b", r"\bonlyfans\b", r"\bstreamer\b",
    r"\bsinger\b", r"\bpop\s*star\b", r"\bpolitician\b", r"\bpresident\b", r"\bprincess\s+(diana|kate)\b",
    r"\b(from|in)\s+(this|the|my|that)\s+(photo|picture|selfie|instagram|insta|tiktok|video)\b", r"\bselfie\s+of\b",
    r"\bsame\s+face\s+as\b",
    r"\b(replace|change|put|paste|transfer|copy)\s+(her|his|their|the|my)\s+face\b", r"\bface\s+(from|of)\s+(image|picture|photo)\b",
]
# "looks like Taylor Swift" -- capitalised first/last names after "like"/"as"; checked case-sensitively.
_NAME_RE = re.compile(r"\b(?i:looks?|looking|resembl\w*|styled|dressed|made|drawn|cosplay\w*|disguised|costumed)\s+(?i:up\s+)?(?i:exactly\s+)?(?i:like|as)\s+(?:(?i:a|an|the)\s+)?([A-Z][a-z]+(?:[\s.\-]+[A-Z][a-z]+)+)")

# Costumes of well-known FICTIONAL adult characters are fine ("dressed as Wonder Woman").
# Only characters who are adults in their source material, and not tied to one real actor's face.
# Anything else that looks like "Firstname Lastname" after "dressed as / looks like" is still refused,
# because the app can't tell a fictional name from a real person's.
FICTIONAL_COSTUMES = {
    "wonder woman", "harley quinn", "poison ivy", "black widow", "scarlet witch", "captain marvel",
    "jean grey", "black canary", "lara croft", "jessica rabbit", "samus aran", "morticia addams",
    "mrs claus", "mrs. claus", "santa claus", "red sonja", "jill valentine", "ada wong", "lady dimitrescu",
    "sonya blade", "cat woman", "invisible woman", "she hulk", "she-hulk", "grim reaper", "tooth fairy",
    "easter bunny", "lady liberty", "queen of hearts", "evil queen", "wicked witch", "bride of frankenstein",
    "frankenstein", "count dracula", "power girl", "emma frost", "silk spectre", "lady death", "dark phoenix",
    "space ranger", "jedi knight", "sith lord", "star trek officer", "fairy godmother", "mother nature",
}

# Raw workflows: node types that copy a face / identity from a picture are not allowed.
NODE_DENY_RE = re.compile(r"(face|swap|reactor|instantid|pulid|ipadapter|ip_adapter|faceid|roop|insightface|photomaker|ecomid|infiniteyou|lora_?train|trainlora)", re.I)

# nodes that train or save models, or read whole folders of pictures -- training only happens through
# Easy Studio's own "Train my character" tool, whose sources are limited to characters made in the app.
SAVE_TRAIN_DENY_RE = re.compile(r"^(TrainLoraNode|SaveLoRA\w*|LoraSave|\w*CheckpointSave\w*|ModelSave|CLIPSave|VAESave|"
                                r"ModelMergeSave|Save\w*Dataset\w*|Load\w*Dataset\w*|LoadImageSetFromFolder\w*|\w*FromFolder\w*)$", re.I)
# LoRA names: narrower than NODE_DENY_RE (a "freckled face" style LoRA is fine; face-swap / identity ones aren't)
LORA_DENY_RE = re.compile(r"(face[\s_\-.]*swap|reactor|instantid|pulid|faceid|roop|insightface|photomaker|ecomid|"
                          r"infiniteyou|deep[\s_\-]*fake|look[\s_\-]*alike|celeb\w*|real[\s_\-]*person)", re.I)
ALWAYS_NEGATIVE = ("child, minor, teen, underage, childlike body, young-looking face, loli, "
                   "real person, celebrity")
ADULT_HINT = "adult"

# No blood, violence, gore or hurtful depictions, in any section (the owner's rule, D-C-46).
# Word-level only, like the rules above: a guard rail, not a judgement of a whole scene.
# Colour and drink names with "blood" in them stay allowed; "choker" (a necklace) is not "choke".
_VIOLENCE_PATTERNS = [
    r"\bblood(?![\s-]*(?:orange|moon|red)\b)(?!y\s+mary\b)(?:y|ied|shed|bath|stained|soaked)?\b",
    r"\bbleed(?:s|ing)?\b", r"\bbled\b",
    r"\bgor(?:e|y)\b(?![\s-]*tex\b)", r"\bgruesome\b", r"\bentrails\b", r"\bviscera\b", r"\bguts\b", r"\bintestines\b",
    r"\bbroken\s+bones?\b", r"\b(?:eating|eats)\s+(?:human\s+)?flesh\b",
    r"\bviolen(?:ce|t|tly)\b", r"\bbrutal(?:ly|ity|i[sz]ed?)?\b",
    r"\bwound(?:s|ed)\b", r"\b(?:open|deep|gaping|fresh|flesh|stab|knife|bullet|gunshot|head|bloody)\s+wound\b",
    r"\bwound\s+(?:on|in|to|across)\b",  # "hair wound into a bun" and "a scarf wound around" still pass
    r"\binjur(?:y|ies|ed|ing)\b", r"\bbruis(?:e|es|ed|ing)\b", r"\ba\s+black\s+eye\b",  # "black eyes" is an eye colour
    r"\bgunshots?\b", r"\bgunned\s+down\b", r"\bbullet\s+(?:holes?|wounds?)\b", r"\bat\s+(?:gun|knife)point\b",
    r"\bshot\s+(?:dead|to\s+death|in\s+the\s+(?:head|chest|back|face|stomach|leg|arm|neck)|him|her|them)\b",
    r"\b(?:throat|wrists?)\s+(?:slit|cut|slashed)\b", r"\bslit\s+(?:throat|wrists?)\b", r"\bslash(?:ed|es|ing)\b",
    r"\bhanged\s+(?:from|by)\b", r"\bhanging\s+by\s+(?:the|his|her)\s+neck\b", r"\blynch\w*",
    r"\bknife\s+to\s+(?:his|her|their|the)\s+(?:neck|throat)\b",
    r"\bdead\s+(?:man|woman|person|people|soldiers?)\b", r"\bdying\b", r"\bexecut(?:ion|ions|ed)\b", r"\bfiring\s+squad\b",
    r"\bburn(?:ed|t|ing)\s+alive\b", r"\b(?:man|woman|person|body)\s+on\s+fire\b",
    r"\bcorpses?\b", r"\bcadavers?\b", r"\bdead\s+bod(?:y|ies)\b", r"\bsevered\b",
    r"\bdismember\w*", r"\bdecapitat\w*", r"\bbehead\w*", r"\bmutilat\w*", r"\bdisembowel\w*", r"\bimpal(?:e|ed|es|ing)\b",
    r"\bmurder\w*", r"\bkill(?:s|ed|ing)?\b", r"\bslaughter\w*", r"\bmassacre\w*",
    r"\btortur\w*", r"\bstab(?:s|bed|bing)?\b", r"\bstrangl\w*", r"\bchok(?:e|es|ed|ing)\b",
    r"\bsuffocat\w*", r"\basphyxiat\w*",
    r"\bbeaten\b", r"\bbeat(?:s|ing)?\s+(?:up|him|her|them)\b", r"\bbeat(?:s|ing)?\s+(?:a|the)\s+(?:man|woman|person)\b",
    r"\bkick(?:s|ed|ing)\s+(?:him|her|them|a\s+(?:man|woman|person))\b",
    r"\bwhip(?:s|ped|ping)\b(?!\s+cream)", r"\bbatter(?:ed|ing)\b(?!\s+(?:fish|cod|shrimp))",
    r"\bpunch(?:es|ed|ing)\b", r"\bslap(?:s|ped|ping)?\b",
    r"\bfist\s*fight\w*", r"\bbrawl\w*",
    r"\babus(?:e|ed|es|ing|ive)\b", r"\bassault(?:s|ed|ing)?\b", r"\brap(?:e|ed|es|ing|ist|ists)\b",
    r"\bself[\s-]*harm\w*", r"\bsuicid\w*", r"\bnoose\b",
    r"\bhurt(?:s|ing)?\b", r"\bharm(?:s|ed|ing)?\b", r"\bin\s+(?:pain|agony)\b", r"\bagony\b",
]
VIOLENCE_REASON = "describes blood, violence, gore or a hurtful scene. This app does not make those, in any section."

# The rest of the hard floor (D-C-50), by category, in plain category words: acts against people that are
# non-consensual, abusive or degrading; cruelty to animals; other grave harm. Same rail, same places, every section.
# Patterns come from the category words only. Everyday words that merely share a stem stay allowed ("forced perspective",
# "a stalk of celery", "poached eggs", "a bully breed", "a dogfight between planes"); the tests pin both sides.
_ANIMAL_WORDS = (r"(?:animal|dog|puppy|cat|kitten|horse|pony|cow|calf|pig|bird|rabbit|pet|livestock|donkey|monkey|fox|wolf|bear|deer)s?")
FLOOR_PATTERNS = {
    "people": [
        r"\bnon[\s-]*consen\w*", r"\bwithout\s+(?:\w+\s+)?consent\b", r"\bagainst\s+(?:her|his|their|my|your)\s+will\b",
        r"\bcoerc(?:e|ed|es|ing|ion|ive)\b", r"\bforced\s+(?:to|into|upon|on)\b", r"\bforc(?:e|es|ing)\s+(?:her|him|them)\s+(?:to|into)\b",
        r"\bblackmail\w*", r"\bextort\w*", r"\bmolest\w*", r"\bgrop(?:e|ed|es|ing)\b", r"\bharass\w*",
        r"\bstalkers?\b", r"\bstalk(?:ed|ing)\s+(?:her|him|them|victims?|a\s+(?:woman|man|girl|boy|person))\b",
        r"\bbull(?:ied|ying)\b",
        r"\bhumiliat\w*", r"\bdegrading\b", r"\bdegrad(?:e|es|ed)\s+(?:her|him|them|a\s+(?:woman|man|person)|people)\b",
        r"\bdemean\w*", r"\bdehumani[sz]\w*", r"\bexploitation\b",
        r"\bdrugg?ed\s+(?:her|him|them|a\s+(?:woman|man|person))\b", r"\bspik(?:ed|ing)\s+(?:her|his|their)\s+drink\b",
        r"\bvoyeur\w*",
    ],
    "animals": [
        r"\banimal\s+(?:cruelty|abuse|torture|torment|fighting|sacrifice|suffering)\b",
        r"\bcruelty\s+(?:to|towards?)\s+" + _ANIMAL_WORDS + r"\b",
        r"\bdog[\s-]*fighting\b", r"\b(?:cock|bull|bear|badger)[\s-]*fight\w*", r"\b(?:bear|bull|badger|dog)[\s-]*baiting\b",
        r"\b(?:tortur(?:e|es|ed|ing)|torment(?:s|ed|ing)?|beat(?:s|ing)?|beaten|kick(?:s|ed|ing)?|starv(?:e|es|ed|ing)|"
        r"abus(?:e|es|ed|ing)|neglect(?:s|ed|ing)?|poison(?:s|ed|ing)?|drown(?:s|ed|ing)?|strangl(?:e|es|ed|ing)|"
        r"mutilat(?:e|es|ed|ing)|whip(?:s|ped|ping)?|hit(?:s|ting)?|burn(?:s|ed|t|ing)?)\s+"
        r"(?:the\s+|a\s+|an\s+|his\s+|her\s+|their\s+|my\s+|some\s+|stray\s+)?" + _ANIMAL_WORDS + r"\b",
    ],
    "harm": [
        r"\bkidnap\w*", r"\b(?:human|sex|people|child)\s+traffick\w*", r"\btraffick(?:ed|er|ers)\b",
        r"\benslav\w*", r"\bslavery\b", r"\bhostages?\b", r"\bheld\s+captive\b",
        r"\bgenocid\w*", r"\bethnic\s+cleansing\b", r"\bterroris[tm]\w*", r"\bhate\s+crimes?\b",
        r"\bp(?:a|ae|e)d(?:o|e)phil\w*", r"\bnecrophil\w*", r"\bbestiality\b", r"\bincest\w*",
        r"\b(?:boiled|buried|skinned)\s+alive\b",
    ],
}
FLOOR_REASONS = {
    "people": "describes a non-consensual, abusive or degrading act against people. This app does not make those, in any section.",
    "animals": "describes cruelty to animals. This app does not make that, in any section.",
    "harm": "describes grave harm to people (such as kidnapping, trafficking, slavery, terror, genocide or hate crimes). "
            "This app does not make that, in any section.",
}
# Added to every avoid list, beside the child and teen words.
VIOLENCE_NEGATIVE = "blood, gore, violence, wounds, injury"


def check_violence(text):
    """(ok, message). Refuses blood, violence, gore and hurtful depictions, and the floor categories (FLOOR_PATTERNS).
    The same in every section."""
    if not text:
        return True, ""
    _orig, forms = _variants(str(text))
    for f in forms[:4]:
        for p in _VIOLENCE_PATTERNS:
            m = re.search(p, f, re.I)
            if m:
                return False, f"Blocked: '{m.group(0)}' {VIOLENCE_REASON}"
        for category, patterns in FLOOR_PATTERNS.items():
            for p in patterns:
                m = re.search(p, f, re.I)
                if m:
                    return False, f"Blocked: '{m.group(0)}' {FLOOR_REASONS[category]}"
    return True, ""

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "l"})
_ZW = re.compile(r"[\u200b-\u200f\u2060\ufeff\u00ad]")
_SPACED = re.compile(r"\b(?:[a-z][\s.\-_*+]{1,3}){2,}[a-z]\b")


def _variants(text):
    """The text plus normalised versions that undo common tricks (unicode look-alikes,
    zero-width characters, l33tspeak, s p a c e d   l e t t e r s, dot.ted words)."""
    t = unicodedata.normalize("NFKC", text)
    t = _ZW.sub("", t)
    t = t.translate(_HOMOGLYPHS)  # Cyrillic / Greek letters that look like Latin ones (adversarial pass v3)
    low = t.lower()
    leet = low.translate(_LEET)
    spaced = _SPACED.sub(lambda m: re.sub(r"[\s.\-_*+]", "", m.group(0)), leet)
    squashed = re.sub(r"(.)\1{2,}", r"\1\1", spaced)  # teeeen -> teen
    squashed2 = re.sub(r"(.)\1+", r"\1", spaced)     # tteenn -> ten? only used for the minor list
    return t, [low, leet, spaced, squashed, squashed2]


# Cyrillic and Greek look-alikes -> Latin, so "ѕchoolgirl" (Cyrillic ѕ) is read as "schoolgirl".
_HOMOGLYPHS = str.maketrans({
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "х": "x", "ѕ": "s", "і": "i", "ї": "i", "ј": "j", "ԁ": "d", "ɡ": "g", "һ": "h", "ӏ": "l", "ց": "g",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "Ѕ": "S", "І": "I", "Ј": "J", "α": "a", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N",
    "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X"})


def _load_celebs():
    try:
        names = [l.strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "celebrity_names.txt"), encoding="utf-8")
                 if l.strip() and not l.startswith("#")]
    except OSError:
        return None
    parts = [r"[\s_\-.]*".join(re.escape(w) for w in n.split()) for n in names]
    return re.compile(r"(?<![a-z0-9])(" + "|".join(parts) + r")(?![a-z0-9])")


_CELEB_RE = _load_celebs()


def check_prompt(text):
    """Return (ok, message). ok=False means the text is refused."""
    if not text:
        return True, ""
    if not isinstance(text, str):
        text = str(text)
    orig, forms = _variants(text)
    for f in forms:
        for p in _MINOR_PATTERNS:
            m = re.search(p, f, re.I)
            if m:
                return False, (f"Blocked: '{m.group(0)}' describes a minor or child-like character. "
                               "Easy Studio only makes fictional ADULT characters.")
    for rx in (_AGE_RE, _AGE_RE2):
        for m in rx.finditer(orig):
            g = m.group(1) if rx is _AGE_RE else m.group(2)
            n = _num(g)
            if n < MIN_AGE:
                return False, f"Blocked: '{m.group(0)}' is under {MIN_AGE}. Characters in Easy Studio are {MIN_AGE} or older."
    ok, msg = check_violence(orig)
    if not ok:
        return ok, msg
    for f in forms[:3]:
        for p in _REAL_PERSON_PATTERNS:
            m = re.search(p, f, re.I)
            if m:
                return False, (f"Blocked: '{m.group(0)}' looks like a request for a real person or their likeness. "
                               "Easy Studio is for fictional characters only (no real people, no face-swaps).")
    if _CELEB_RE is not None:
        for f in forms[:3]:
            m = _CELEB_RE.search(f.lower())
            if m:
                return False, (f"Blocked: '{m.group(0)}' is a real person. Easy Studio is for fictional characters only "
                               "(no real people, no look-alikes). Describe your own character's look instead.")
    for m in _NAME_RE.finditer(orig):
        name = re.sub(r"[\s\-]+", " ", m.group(1)).strip().lower()
        if name in FICTIONAL_COSTUMES or name.replace(".", "") in FICTIONAL_COSTUMES:
            continue
        return False, (f"Blocked: '{m.group(0)}' names a person to copy. Describe the look with traits instead "
                       "(Easy Studio does not copy real people). Fictional costumes like 'dressed as Wonder Woman' are fine.")
    # A whole catalog dump is one JSON document, not a scene that introduces a person.
    if not str(orig).lstrip().startswith(("{", "[")):
        ok, msg = check_group_prompt(orig)
        if not ok:
            return ok, msg
    return True, ""



def check_minor_and_age(text):
    """Only check_prompt's first two rules: minor-coded words and stated ages under 21. Returns (ok, message).

    Used where every other rule already ran or was deliberately waived for one exact file (loras.civitai_check)."""
    if not text:
        return True, ""
    orig, forms = _variants(str(text))
    for f in forms:
        for p in _MINOR_PATTERNS:
            m = re.search(p, f, re.I)
            if m:
                return False, (f"Blocked: '{m.group(0)}' describes a minor or child-like character. "
                               "Easy Studio only makes fictional ADULT characters.")
    for rx in (_AGE_RE, _AGE_RE2):
        for m in rx.finditer(orig):
            g = m.group(1) if rx is _AGE_RE else m.group(2)
            if _num(g) < MIN_AGE:
                return False, f"Blocked: '{m.group(0)}' is under {MIN_AGE}. Characters in Easy Studio are {MIN_AGE} or older."
    return True, ""

def check_all(*texts):
    for t in texts:
        ok, msg = check_prompt(t)
        if not ok:
            return ok, msg
    return True, ""


def check_workflow(wf):
    """Raw ComfyUI workflow check: every string anywhere inside, and every node type."""
    if not isinstance(wf, dict) or not wf:
        return False, "That isn't an API-format ComfyUI workflow (use 'Save (API)' / 'Export (API)' in ComfyUI)."
    for nid, node in wf.items():
        if not isinstance(node, dict) or "class_type" not in node:
            return False, f"Node {nid!r} has no class_type -- please export the workflow in API format."
        ct = str(node["class_type"])
        if NODE_DENY_RE.search(ct) or SAVE_TRAIN_DENY_RE.search(ct):
            return False, f"Blocked: node type '{ct}' copies faces/identity, trains/saves models or reads whole folders, which imported workflows can't do."
    stack = [wf]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            stack.extend(x.values())
            stack.extend(k for k in x.keys() if isinstance(k, str))
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str):
            if NODE_DENY_RE.search(x) and re.search(r"\.(safetensors|pth|onnx|bin|ckpt)$", x, re.I):
                return False, f"Blocked: model file '{x}' looks like a face-swap / identity model."
            ok, msg = check_prompt(x)
            if not ok:
                return False, msg
    return True, ""


# Explicit stated-age fields. Appearance is never an age.
STATED_AGE_FIELDS = ("age", "stated_age", "age_years")
_GROUP_KEYS = ("people", "persons", "characters", "group")
_PERSON_WORD = re.compile(
    r"\b(women|woman|men|man|people|person|adults|adult|ladies|lady|gentlemen|gentleman|guys|guy|"
    r"couples|couple|friends|friend|partners|partner|characters|character)\b",
    re.I)
_STATED_AGE_TEXT = re.compile(
    r"\b(\d{1,3})\s*-\s*year\s*-\s*old\b|\bage(?:d)?\s+(\d{1,3})\b|\b(\d{1,3})\s+years?\s+old\b",
    re.I)
_APPEARANCE_AGE = re.compile(
    r"\b(?:looks?|looking|appears?|appearing|seems?|seeming)\s+(?:about\s+|around\s+|to\s+be\s+)?"
    r"(?:a\s+|an\s+)?\d{1,3}(?:\s*-\s*year\s*-\s*old|\s+years?\s+old)?\b",
    re.I)


def parse_stated_age(value):
    """(age, problem). problem is missing, invalid, under_21, or None.

    Only a whole number is an age. Words, blanks, and appearance are not.
    """
    if value is None or (isinstance(value, str) and not str(value).strip()):
        return None, "missing"
    if isinstance(value, bool) or isinstance(value, (list, dict)):
        return None, "invalid"
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None, "invalid"
        number = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[0-9]+", text):
            return None, "invalid"
        number = int(text)
    else:
        return None, "invalid"
    if number < MIN_AGE:
        return None, "under_21"
    return number, None


def _show_age(value):
    """The caller's original value, for an error. Nothing is rewritten."""
    if value is None:
        return "None"
    return repr(value)


def explicit_age_fields(record):
    """Stated age fields the caller actually sent, including blank ones.

    Appearance keys are ignored and never become an age.
    """
    if not isinstance(record, dict):
        return []
    return [(key, record.get(key)) for key in STATED_AGE_FIELDS if key in record]


def require_stated_age(record):
    """(ok, age or None, message). No default and no clamp.

    The message keeps the caller's original invalid or missing value.
    """
    if not isinstance(record, dict):
        return False, None, "Missing stated age: age is missing."
    fields = explicit_age_fields(record)
    if not fields:
        return False, None, "Missing stated age: age is missing. Age is not inferred from appearance."
    nonempty = [(key, raw) for key, raw in fields if raw not in (None, "")]
    if not nonempty:
        shown = ", ".join(f"{key}={_show_age(raw)}" for key, raw in fields)
        return False, None, f"Missing stated age: {shown}. Age is not inferred from appearance."
    parsed = []
    for key, raw in nonempty:
        age, problem = parse_stated_age(raw)
        if problem == "invalid":
            return False, None, f"Invalid stated age: {key}={_show_age(raw)}."
        if problem == "under_21":
            return False, None, f"Stated age is under 21: {key}={_show_age(raw)}. It is not raised."
        if problem == "missing":
            return False, None, f"Missing stated age: {key}={_show_age(raw)}."
        parsed.append((key, raw, age))
    if len({age for _, _, age in parsed}) > 1:
        shown = ", ".join(f"{key}={_show_age(raw)}" for key, raw, _ in parsed)
        return False, None, f"Conflicting stated ages: {shown}."
    return True, parsed[0][2], ""


def people_in(record):
    """People in a group prompt, or an empty list when this is one person."""
    if not isinstance(record, dict):
        return []
    for key in _GROUP_KEYS:
        value = record.get(key)
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            return list(value)
    return []


def require_group_ages(record):
    """Refuse the whole group when any person lacks a valid stated age of 21 or older."""
    people = people_in(record)
    if not people:
        return require_stated_age(record)
    ages = []
    for index, person in enumerate(people, start=1):
        ok, age, msg = require_stated_age(person)
        if not ok:
            return False, None, f"Group prompt rejected: person {index}: {msg}"
        ages.append(age)
    return True, ages, ""


# An extra person is introduced on purpose ("and a man", "with her friend").
# "the person" in an edit instruction is the one already declared, not a new record.
_EXTRA_PERSON = re.compile(
    r"\b(?:and|with)\s+(?:a|an|another|her|his|their)\s+"
    r"(?:(\d{1,3})\s*-\s*year\s*-\s*old\s+)?"
    r"(women|woman|men|man|people|person|friends|friend|partners|partner|ladies|lady|guys|guy|adults|characters|character)\b",
    re.I)


# A supported group phrase states an exact count. Anything else is not clearance.
_EXACT_GROUP_COUNTS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "both": 2, "a pair of": 2, "a couple of": 2,
}
_GROUP_WORDING = re.compile(
    r"\b(?P<count>a\s+pair\s+of|a\s+couple\s+of|a\s+group\s+of|several|many|both|two|three|four|five|six)?\s*"
    r"(?P<adj>(?:[a-z][a-z'-]*\s+){0,3})"
    r"(?P<noun>women|men|people|adults|ladies|gentlemen|guys|friends|partners|characters)\b",
    re.I)


# Every person a create request's text adds must have a declared record (P-11 N02). These count people the
# text introduces in the singular ("a woman and a tall man", "with her husband", "a woman, a man") and in
# implicit pairs ("a couple", "twins"). A repeated noun after "the" is the same person, not a new one.
_ADULT_NOUNS = ("woman|man|lady|gentleman|guy|person|adult|partner|friend|husband|wife|boyfriend|girlfriend|"
                "lover|date|companion|stranger|bride|groom|model|dancer|neighbour|neighbor|colleague|roommate")
_RELATION_NOUNS = {"partner", "friend", "husband", "wife", "boyfriend", "girlfriend", "lover", "date", "companion",
                   "bride", "groom", "neighbour", "neighbor", "colleague", "roommate"}
_SINGLE_PERSON = re.compile(
    r"\b(?P<det>a|an|another|one|the|her|his|their|my|your)\s+(?:[a-z][a-z'-]*\s+){0,3}?(?P<noun>" + _ADULT_NOUNS + r")\b",
    re.I)
_IMPLICIT_GROUPS = {"couple": 2, "pair": 2, "duo": 2, "twins": 2, "trio": 3}
_IMPLICIT_GROUP = re.compile(r"\b(couple|pair|duo|twins|trio)\b(?!\s+of\b)", re.I)
# "date" and "model" count as people ("with her date", "a woman and a model") except in two idioms, dropped before
# counting:
# - "on a date": an outing, also "on a first/blind/dinner/... date". "on a double date" or "a group date" counts.
# - "model" naming the look of a pose: "model pose", "model look" or "model style" right after "in", "into",
#   "strike", "do" or "hold" ("in a fashion model pose", "striking a model pose"), or opening the text as a whole
#   tag ("a fashion model pose, ..."). The words in between can be no joiner, determiner or person noun.
# Anywhere else "model" is a person: "a model poses", "a model shot from above" and "a fashion model photo" all show
# one, and so does "a woman and a model pose for a photo".
_NOT_FILLER = (r"(?!(?:and|or|but|nor|with|plus|then|while|as|a|an|the|another|one|her|his|their|my|your|"
               + _ADULT_NOUNS + r")\b)")
_ON_A_DATE = re.compile(
    r"\bon\s+(?:a|an)\s+(?:(?:first|second|blind|dinner|lunch|coffee|romantic)\s+){0,2}date\b", re.I)
_MODEL_LOOK = re.compile(r"\bmodel(?=[\s-]+(?:pose|look|style)\b)", re.I)
_LOOK_HEAD = re.compile(
    r"\b(?:in|into|strikes?|striking|struck|do|does|doing|did|holds?|holding|held)\s+"
    r"(?:(?:a|an|the)\s+)?(?:" + _NOT_FILLER + r"[a-z][a-z'-]*\s+){0,3}$", re.I)
_LOOK_AT_START = re.compile(r"^\s*(?:(?:a|an|the)\s+)?(?:" + _NOT_FILLER + r"[a-z][a-z'-]*\s+){0,3}$", re.I)
_LOOK_TAG_END = re.compile(r"[\s-]+(?:pose|look|style)\s*(?:[,.;]|$)", re.I)


def _drop_person_idioms(text):
    text = _ON_A_DATE.sub("out", text)  # no determiner left behind to attach to a later noun
    parts, last = [], 0
    for m in _MODEL_LOOK.finditer(text):
        before, after = text[:m.start()], text[m.end():]
        if not (_LOOK_HEAD.search(before) or (_LOOK_AT_START.search(before) and _LOOK_TAG_END.match(after))):
            continue  # not clearly a look: "model" here can be a second person
        parts += [text[last:m.start()], "modelled"]
        last = m.end()
    return "".join(parts) + text[last:]


def people_mentioned(text):
    """How many people the text introduces (a conservative count; over-counting refuses, never clears)."""
    text = _drop_person_idioms(text or "")
    introduced, count = set(), 0
    for m in _SINGLE_PERSON.finditer(text):
        det, noun = m.group("det").lower(), m.group("noun").lower()
        if det in ("a", "an", "another", "one") or noun in _RELATION_NOUNS or noun not in introduced:
            count += 1
        introduced.add(noun)
    for m in _IMPLICIT_GROUP.finditer(text):
        count += _IMPLICIT_GROUPS[m.group(1).lower()]
    return count


def scene_records(params):
    """Person records a create request actually declared.

    A group container is not itself a person. Top-level people and a nested
    people list are the same shape: one record per person.
    """
    if not isinstance(params, dict):
        return []
    people = params.get("people") if isinstance(params.get("people"), list) else None
    dna = params.get("dna") if isinstance(params.get("dna"), dict) else None
    if people is not None:
        return [person for person in people if isinstance(person, dict)]
    if isinstance(dna, dict) and people_in(dna) and not explicit_age_fields(dna):
        return list(people_in(dna))
    if isinstance(dna, dict):
        return [dna]
    return []


def check_group_prompt(text, records=None):
    """(ok, message). Clearance comes from declared records, not from a missed phrase.

    Without records, this only rejects an introduced person who has no explicit
    age of 21+. With records, every plural or adjective group phrase must be a
    supported exact count that matches those records. No match is not clearance.
    """
    if records is not None:
        return _clear_scene_people(text, records)
    if not text or not isinstance(text, str):
        return True, ""
    cleaned = _APPEARANCE_AGE.sub(" ", text)
    for match in _EXTRA_PERSON.finditer(cleaned):
        raw = match.group(1)
        who = match.group(2)
        if not raw:
            return False, (
                f"Group prompt rejected: '{match.group(0).strip()}' has no explicit stated age of 21 or older. "
                "Age is not inferred from appearance."
            )
        age = int(raw)
        if age < MIN_AGE:
            return False, f"Group prompt rejected: stated age {age} for {who} is under 21. It is not raised."
    return True, ""


def _clear_scene_people(text, records):
    """Bind free-text group wording to declared 21+ records, or refuse it."""
    declared = []
    for rec in records or []:
        people = people_in(rec) if isinstance(rec, dict) and people_in(rec) and not explicit_age_fields(rec) else [rec]
        for person in people:
            ok, _age, msg = require_stated_age(person)
            if not ok:
                return False, msg
            declared.append(person)
    if not declared:
        return False, "Missing stated age: age is missing. Age is not inferred from appearance."
    ok, msg = check_group_prompt(text)
    if not ok:
        return ok, msg
    cleaned = _APPEARANCE_AGE.sub(" ", text or "")
    for match in _GROUP_WORDING.finditer(cleaned):
        phrase = " ".join(match.group(0).split())
        count_word = " ".join((match.group("count") or "").lower().split())
        if count_word not in _EXACT_GROUP_COUNTS:
            return False, (
                f"Unsupported group wording: '{phrase}' is not a supported group. "
                "Every person needs their own declared record with a stated age of 21 or older."
            )
        count = _EXACT_GROUP_COUNTS[count_word]
        if count != len(declared):
            noun = "record was" if len(declared) == 1 else "records were"
            return False, (
                f"Unbound group: '{phrase}' asks for {count} people but {len(declared)} declared {noun} given."
            )
    mentioned = people_mentioned(cleaned)
    if mentioned > len(declared):
        noun = "record was" if len(declared) == 1 else "records were"
        return False, (
            f"Unbound person: the text adds {mentioned} people but {len(declared)} declared {noun} given. "
            "Every person needs their own declared record with a stated age of 21 or older."
        )
    return True, ""


def ages_in_text(text):
    found = []
    for match in _STATED_AGE_TEXT.finditer(text or ""):
        raw = next(group for group in match.groups() if group)
        found.append(int(raw))
    return found


def known_stated_ages(records):
    """Declared ages from person records. Appearance fields are ignored."""
    known = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        if people_in(rec):
            for person in people_in(rec):
                ok, age, _msg = require_stated_age(person)
                if ok:
                    known.append(age)
        if explicit_age_fields(rec):
            ok, age, _msg = require_stated_age(rec)
            if ok:
                known.append(age)
    return known


def reconcile_prompt_ages(text, records):
    """Prompt ages must match the declared records. A new person needs their own age."""
    ok, msg = check_group_prompt(text)
    if not ok:
        return ok, msg
    known = set(known_stated_ages(records))
    for age in ages_in_text(text):
        if age < MIN_AGE:
            return False, f"Stated age is under 21: age={age}. It is not raised."
        if known and age not in known:
            return False, (
                f"Conflicting stated ages: prompt age={age} is not in the person records "
                f"({', '.join(str(item) for item in sorted(known))})."
            )
    return True, ""


def clamp_age(age, lo=21, hi=70):
    """Refuse to clamp. A stated age of 21 or older is returned unchanged."""
    ok, parsed, msg = require_stated_age({"age": age})
    if not ok:
        raise ValueError(msg)
    return parsed


def add_adult_hint(prompt):
    p = (prompt or "").strip()
    if re.search(r"\badults?\b", p, re.I):
        return p
    return f"{ADULT_HINT}, {p}" if p else ADULT_HINT


def safe_negative(neg):
    neg = (neg or "").strip()
    always = f"{ALWAYS_NEGATIVE}, {VIOLENCE_NEGATIVE}"
    return f"{neg}, {always}" if neg else always


# ---------------------------------------------------------------------------
# Areas (v3): the everyday area is "no nudity"; explicit content lives in the 18+ section.
# Lingerie, bikinis, swimwear, yoga clothes and "sexy" are fine everywhere.
# ---------------------------------------------------------------------------
_EXPLICIT_RE = re.compile(
    r"\b(nude|nudes|nudity|naked|topless|bottomless|nipples?|areolae?|genitals?|genitalia|vaginal?|vulva|pussy|penis|"
    r"cock|dick|erect(ion)?|testicles|anus|anal|sex|sexual\s+intercourse|intercourse|porn\w*|hardcore|explicit|nsfw|"
    r"uncensored|masturbat\w*|orgasm\w*|blow\s*job|cum(ming|shot|s)?|ejaculat\w*|xxx|fuck\w*|"
    r"(bare|exposed|uncovered)\s+(breasts?|chest|butt|bottom|crotch)|breasts?\s+out|no\s+clothes|without\s+clothes|unclothed|undress\w*)\b",
    re.I)
NUDITY_NEGATIVE = "nudity, nude, naked, nipples, genitals, explicit, nsfw"

# Extra refusals inside the 18+ section: themes that code an adult as a child or a school pupil.
_ADULT_AREA_PATTERNS = [
    r"\bschool\s*(uniform|outfit|skirt|blazer|bag|desk|classroom|girl|boy)s?\b", r"\b(class\s*room|homeroom|detention|teacher'?s\s+pet)\b", r"\b(student|pupil)s?\b", r"\binnocent\b",
    r"\b(young|youthful|younger)[\s-]*look(ing)?\b", r"\blooks?\s+(very\s+|so\s+|really\s+)?young\b",
    r"\b(pig\s*tails?|twin\s*tails?)\b.*\b(small|tiny|petite|flat)\b", r"\bstep-?(sister|sis|daughter|brother|bro)\b",
    r"\bpetite\b.*\b(flat[\s-]*chest\w*|tiny\s+body|small\s+body|child\w*)\b",
    r"\b(flat[\s-]*chest\w*|tiny\s+body|small\s+body)\b.*\bpetite\b",
    r"\b(first\s+time|virgin)\b.*\b(young|little)\b", r"\bcandid\b|\bhidden\s+camera\b|\bvoyeur\w*\b|\bupskirt\b|\bspy\s*cam\b",
    r"\b(asleep|sleeping|unconscious|drugged|passed\s+out|drunk)\b", r"\b(non-?con\w*|forced|rape\w*)\b",
]


def explicit_word(text):
    """The first explicit word in the text, or ''."""
    if not text:
        return ""
    _orig, forms = _variants(str(text))
    for f in forms[:3]:
        m = _EXPLICIT_RE.search(f)
        if m:
            return m.group(0)
    return ""


def check_area(text, area):
    """Area rules on top of check_prompt. area: 'default' or 'adult'."""
    if not text:
        return True, ""
    ok, msg = check_group_prompt(text)
    if not ok:
        return ok, msg
    if area == "adult":
        _orig, forms = _variants(str(text))
        for f in forms[:4]:
            for p in _ADULT_AREA_PATTERNS:
                m = re.search(p, f, re.I)
                if m:
                    return False, (f"Blocked in the 18+ section: '{m.group(0)}'. Adult content must be clearly between "
                                   "consenting, awake adults, with no school / child / family-roleplay themes "
                                   "and no hidden-camera or non-consent themes.")
        return True, ""
    w = explicit_word(text)
    if w:
        return False, (f"'{w}' is 18+ content. Open the 18+ section (top-right button) to make adult pictures and "
                       "videos -- they are kept in their own private gallery. Lingerie and swimwear are fine here.")
    return True, ""


def check_lora(name, meta=None, triggers=None):
    """LoRA files: refuse ones whose file name, metadata or trigger words point at minors,
    real people / celebrities or face-swap. Returns (ok, message)."""
    pretty = re.sub(r"[_\-.]+", " ", re.sub(r"\.(safetensors|pt|ckpt|bin)$", "", str(name or ""), flags=re.I))
    if LORA_DENY_RE.search(str(name or "")) or LORA_DENY_RE.search(pretty):
        return False, f"Blocked: LoRA '{name}' looks like a face-swap / identity model."
    if re.search(r"\b(age|ages|younger|young|youth|de\s*age|deage|aging)\s*(slider|tweak|adjust\w*)\b", pretty, re.I):
        return False, (f"Blocked: '{name}' looks like an age slider. Age sliders can make characters look under 21, "
                       "so they are not allowed in Easy Studio.")
    if re.search(r"\b(my\s*(own\s*)?(face|self|likeness|selfies?|photos?|wife|girlfriend|boyfriend|husband)|myself|me\s*lora)\b", pretty, re.I):
        return False, (f"Blocked: '{name}' looks like a LoRA of a real person. Easy Studio only uses LoRAs of fictional characters "
                       "(train your own fictional character in 🎓 Train my character).")
    texts = [pretty] + [str(t) for t in (triggers or [])]
    meta = meta or {}
    for k in ("ss_output_name", "modelspec.title", "modelspec.description", "modelspec.tags", "ss_dataset_dirs",
              "name", "description", "tags"):
        if meta.get(k):
            value = str(meta[k])
            # A description is read in full: an identity-copy word past the old 4000-character cut slipped through (D-C-19).
            texts.append(value if k in ("description", "modelspec.description") else value[:4000])
    tf = meta.get("ss_tag_frequency")
    if tf:
        try:
            d = json.loads(tf) if isinstance(tf, str) else tf
            texts.append(" , ".join(str(t) for sub in d.values() for t in list(sub)[:300]))
        except Exception:
            pass
    for t in texts:
        # tags are comma lists; check each tag so "1girl, solo" style metadata is judged per tag.
        # Every piece is checked: a 2000-piece cap left the tail of a long, comma-heavy description unread (D-C-19).
        for part in re.split(r"[,\n]", t):
            if not part.strip():
                continue
            ok, msg = check_prompt(part)
            if not ok:
                return False, "This LoRA can't be used. " + msg
    if meta.get("poi") in (True, "true", "True"):
        return False, "Blocked: this LoRA is marked as depicting a real person."
    return True, ""
