"""Everything the picker screens show: chips, swatches, presets. Plain data -- edit freely.

Each chip: id, label, the words it adds to the prompt ("p"), and optionally an emoji icon or a colour swatch.
SAFETY: there are deliberately no youthful / child-coded chips. Anything added here still goes through
safety.check_prompt() before reaching a model.
"""

def C(id, label, p, icon=None, swatch=None, only=None):
    d = {"id": id, "label": label, "p": p}
    if icon: d["icon"] = icon
    if swatch: d["swatch"] = swatch
    if only: d["only"] = only          # e.g. only shown for "woman"
    return d

AGE_MIN, AGE_MAX, AGE_DEFAULT = 21, 70, 25  # published only; never copy default onto a character

STYLES = [
    C("photo", "Realistic photo", "photorealistic photograph, natural skin texture, detailed, sharp focus", "📷"),
    C("anime", "Anime", "anime illustration, clean line art, vibrant colors", "🎨"),
    C("render3d", "3D render", "high-end 3D character render, subsurface scattering, studio lighting", "🧊"),
    C("painted", "Painted", "digital painting, painterly brushwork, fantasy concept art", "🖌️"),
]

GENDERS = [C("woman", "Woman", "woman", "👩"), C("man", "Man", "man", "👨")]

CHARACTER_GROUPS = [
    {"id": "body", "label": "Body type", "chips": [
        C("slim", "Slim", "slim body", "🩰"), C("athletic", "Athletic", "athletic toned body", "🏃"),
        C("average", "Average", "average build", "🙂"), C("curvy", "Curvy", "curvy hourglass figure", "⏳"),
        C("plus", "Plus-size", "plus-size full figure", "🍑"), C("muscular", "Muscular", "muscular powerful physique", "💪")]},
    {"id": "height", "label": "Height", "chips": [
        C("petite", "Petite adult", "short petite adult stature", "⬇️"), C("avg_h", "Average height", "average height", "↕️"),
        C("tall", "Tall", "tall long-legged", "⬆️")]},
    {"id": "bust", "label": "Bust", "chips": [
        C("b_small", "Small", "small bust", only="woman"), C("b_med", "Medium", "medium bust", only="woman"),
        C("b_large", "Large", "large bust", only="woman"), C("b_xl", "Very large", "very large bust", only="woman")]},
    {"id": "hips", "label": "Hips", "chips": [
        C("h_narrow", "Narrow", "narrow hips"), C("h_med", "Medium", "medium hips"), C("h_wide", "Wide", "wide hips")]},
    {"id": "skin", "label": "Skin tone", "chips": [
        C("s1", "Porcelain", "very fair porcelain skin", swatch="#F6E3D7"), C("s2", "Fair", "fair skin", swatch="#EED1BC"),
        C("s3", "Light", "light skin", swatch="#E0B593"), C("s4", "Olive", "olive skin", swatch="#C69C72"),
        C("s5", "Tan", "tan skin", swatch="#B07A50"), C("s6", "Brown", "brown skin", swatch="#8D5A3B"),
        C("s7", "Deep", "deep brown skin", swatch="#5E3A24"), C("s8", "Ebony", "dark ebony skin", swatch="#3B2418")]},
    {"id": "skin_details", "multi": True, "label": "Skin details", "chips": [
        C("freckles", "Freckles", "freckles", "✨"), C("tanlines", "Tan lines", "tan lines", "☀️"),
        C("tattoos", "Tattoos", "tasteful tattoos", "🐉"), C("piercings", "Piercings", "piercings", "💍"),
        C("mole", "Beauty mark", "beauty mark", "•")]},
    {"id": "face", "label": "Face shape", "chips": [
        C("oval", "Oval", "oval face"), C("heart", "Heart", "heart-shaped face"), C("round", "Round", "round face, mature features"),
        C("square", "Square jaw", "strong square jawline"), C("high_cheek", "High cheekbones", "high cheekbones, defined features")]},
    {"id": "eyes", "label": "Eye colour", "chips": [
        C("e_brown", "Brown", "brown eyes", swatch="#6B4226"), C("e_hazel", "Hazel", "hazel eyes", swatch="#8E7618"),
        C("e_green", "Green", "green eyes", swatch="#3F8A4F"), C("e_blue", "Blue", "blue eyes", swatch="#3D7CC9"),
        C("e_grey", "Grey", "grey eyes", swatch="#8A949C"), C("e_amber", "Amber", "amber eyes", swatch="#D08A1C"),
        C("e_violet", "Violet", "violet eyes", swatch="#8250C4"), C("e_red", "Red (fantasy)", "glowing red eyes", swatch="#C42B2B")]},
    {"id": "eye_shape", "label": "Eye shape", "chips": [
        C("almond", "Almond", "almond-shaped eyes"), C("big", "Large", "large expressive eyes"), C("hooded", "Hooded", "hooded eyes"),
        C("monolid", "Monolid", "monolid eyes"), C("cat", "Cat-eye", "upturned cat eyes")]},
    {"id": "lips", "label": "Lips", "chips": [
        C("l_thin", "Thin", "thin lips"), C("l_med", "Natural", "natural lips"), C("l_full", "Full", "full lips")]},
    {"id": "makeup", "label": "Makeup", "chips": [
        C("m_none", "None", "no makeup, natural look"), C("m_light", "Light", "light natural makeup"),
        C("m_glam", "Glam", "glamorous makeup, winged eyeliner, red lipstick"), C("m_goth", "Goth", "dark gothic makeup, black lipstick")]},
    {"id": "hair_style", "label": "Hair style", "chips": [
        C("long_straight", "Long straight", "long straight hair", "💁"), C("long_wavy", "Long wavy", "long wavy hair", "🌊"),
        C("curly", "Curly", "voluminous curly hair", "➰"), C("bob", "Bob", "chin-length bob cut", "✂️"),
        C("pixie", "Pixie", "short pixie cut", "✂️"), C("ponytail", "Ponytail", "high ponytail", "🎀"),
        C("twin", "Twin tails", "twin tails hairstyle", "🎀"), C("braid", "Braid", "long side braid", "🪢"),
        C("bun", "Bun", "messy bun", "🍙"), C("afro", "Afro", "big afro", "☁️"), C("locs", "Locs", "long locs", "🪢"),
        C("undercut", "Undercut", "undercut hairstyle", "⚡"), C("shaved", "Buzz cut", "buzz cut", "🪒"),
        C("bangs", "With bangs", "with blunt bangs", "➖"), C("updo", "Elegant updo", "elegant updo", "👑")]},
    {"id": "hair_color", "label": "Hair colour", "chips": [
        C("black", "Black", "black hair", swatch="#16110E"), C("dbrown", "Dark brown", "dark brown hair", swatch="#3B2416"),
        C("brown", "Brown", "brown hair", swatch="#6A4128"), C("auburn", "Auburn", "auburn hair", swatch="#8C3B1F"),
        C("red", "Red", "bright red hair", swatch="#B5281C"), C("ginger", "Ginger", "ginger hair", swatch="#D9772B"),
        C("blonde", "Blonde", "golden blonde hair", swatch="#E2C16B"), C("platinum", "Platinum", "platinum blonde hair", swatch="#EFE6CF"),
        C("silver", "Silver", "silver hair", swatch="#C7CBD1"), C("white", "White", "white hair", swatch="#F7F7F7"),
        C("pink", "Pink", "pastel pink hair", swatch="#F2A1C4"), C("blue", "Blue", "blue hair", swatch="#3C6FE0"),
        C("purple", "Purple", "purple hair", swatch="#7B44C9"), C("green", "Green", "emerald green hair", swatch="#2E9A62")]},
    {"id": "hair_length", "label": "Hair length", "chips": [
        C("short", "Short", "short hair"), C("shoulder", "Shoulder", "shoulder-length hair"),
        C("long", "Long", "long hair"), C("very_long", "Very long", "very long hair")]},
    {"id": "fantasy", "multi": True, "label": "Fantasy (optional)", "chips": [
        C("elf", "Elf ears", "pointed elf ears", "🧝"), C("horns", "Horns", "curved horns", "😈"),
        C("tail", "Tail", "demon tail", "〰️"), C("wings", "Wings", "large feathered wings", "🪽"),
        C("vampire", "Vampire", "vampire fangs, pale skin", "🧛"), C("android", "Android", "android with subtle mechanical seams", "🤖"),
        C("kemono", "Cat ears (adult)", "adult with cat ears and tail", "🐱"), C("succubus", "Succubus", "succubus with small horns and bat wings", "🦇")]},
]

OUTFIT_CATEGORIES = [
    {"id": "casual", "label": "Casual", "icon": "👕", "items": [
        C("jeans_tee", "Jeans & tee", "fitted jeans and a white t-shirt"), C("sundress", "Sundress", "flowy floral sundress"),
        C("hoodie", "Oversized hoodie", "oversized hoodie and shorts"), C("leather", "Leather jacket", "black leather jacket, ripped jeans, boots"),
        C("yoga", "Yoga set", "matching sports bra and yoga leggings")]},
    {"id": "dressy", "label": "Dressy", "icon": "👗", "items": [
        C("evening", "Evening gown", "elegant floor-length evening gown"), C("cocktail", "Cocktail dress", "tight little black cocktail dress"),
        C("suit", "Tailored suit", "tailored suit with open collar"), C("qipao", "Qipao", "silk qipao dress"),
        C("kimono", "Kimono", "traditional silk kimono")]},
    {"id": "lingerie", "label": "Lingerie", "icon": "🩱", "items": [
        C("lace_set", "Lace set", "black lace lingerie set"), C("silk_robe", "Silk robe", "short silk robe"),
        C("corset", "Corset", "corset with stockings and garters"), C("bodysuit", "Bodysuit", "sheer lace bodysuit"),
        C("babydoll", "Nightie", "satin nightie")]},
    {"id": "swim", "label": "Swim", "icon": "👙", "items": [
        C("bikini", "Bikini", "string bikini"), C("onepiece", "One-piece", "high-cut one-piece swimsuit"),
        C("sarong", "Bikini & sarong", "bikini with a sarong wrap")]},
    {"id": "costume", "label": "Costumes", "icon": "🎭", "items": [
        C("knight", "Knight armour", "ornate fantasy plate armour"), C("witch", "Witch", "dark witch outfit with pointed hat"),
        C("cyber", "Cyberpunk", "cyberpunk techwear with neon accents"), C("nurse", "Nurse (adult costume)", "adult nurse costume"),
        C("maid", "Maid (adult costume)", "adult french maid costume"), C("pirate", "Pirate", "pirate captain coat and boots"),
        C("bunny", "Bunny suit", "playboy-style bunny suit"), C("latex", "Latex catsuit", "glossy black latex catsuit"),
        C("space", "Space suit", "sleek sci-fi pilot suit")]},
    {"id": "coverups", "label": "Cover-ups", "icon": "🛁", "items": [
        C("towel", "Just a towel", "wrapped in a bath towel"), C("sheet", "Bedsheet", "covered only by a bedsheet")]},
    {"id": "shoes", "label": "Shoes", "icon": "👠", "items": [
        C("heels", "Heels", "high heels"), C("boots", "Thigh boots", "thigh-high boots"), C("sneakers", "Sneakers", "white sneakers"),
        C("barefoot", "Barefoot", "barefoot")]},
    {"id": "acc", "label": "Accessories", "icon": "💎", "items": [
        C("glasses", "Glasses", "stylish glasses"), C("choker", "Choker", "choker necklace"), C("hat", "Sun hat", "wide sun hat"),
        C("earrings", "Earrings", "gold hoop earrings"), C("gloves", "Long gloves", "long satin gloves"), C("stockings", "Stockings", "sheer black stockings")]},
]
COLORS = [
    C("c_black", "Black", "black", swatch="#111111"), C("c_white", "White", "white", swatch="#F5F5F5"),
    C("c_red", "Red", "red", swatch="#C4161C"), C("c_pink", "Pink", "pink", swatch="#F48FB1"),
    C("c_blue", "Blue", "blue", swatch="#2E5BDA"), C("c_navy", "Navy", "navy", swatch="#1B2A4A"),
    C("c_green", "Emerald", "emerald green", swatch="#127A4B"), C("c_gold", "Gold", "gold", swatch="#D4AF37"),
    C("c_silver", "Silver", "silver", swatch="#C0C0C0"), C("c_purple", "Purple", "purple", swatch="#6A3FB5"),
    C("c_beige", "Beige", "beige", swatch="#D9C3A0"), C("c_leopard", "Leopard", "leopard print", swatch="#C8963E"),
]
MATERIALS = [C("silk", "Silk", "silk"), C("lace", "Lace", "lace"), C("leather", "Leather", "leather"), C("latex", "Latex", "latex"),
             C("denim", "Denim", "denim"), C("cotton", "Cotton", "cotton"), C("satin", "Satin", "satin"), C("mesh", "Sheer mesh", "sheer mesh")]

SCENES = [
    C("studio", "Studio (white)", "plain white photo studio background", "⬜"), C("studio_dark", "Studio (dark)", "dark grey seamless studio backdrop", "⬛"),
    C("bedroom", "Bedroom", "cozy modern bedroom with soft bedding", "🛏️"), C("bathroom", "Luxury bath", "luxury marble bathroom", "🛁"),
    C("beach", "Beach", "tropical beach with turquoise water", "🏖️"), C("pool", "Pool", "rooftop infinity pool", "🏊"),
    C("neon", "Neon city", "neon-lit city street at night, rain reflections", "🌃"), C("bar", "Cocktail bar", "dim cocktail bar", "🍸"),
    C("forest", "Forest", "misty enchanted forest", "🌲"), C("castle", "Castle hall", "grand castle throne hall", "🏰"),
    C("dungeon", "Dungeon", "torch-lit stone dungeon", "🕯️"), C("spaceship", "Spaceship", "sleek spaceship bridge", "🚀"),
    C("office", "Office", "modern glass office", "🏢"), C("onsen", "Hot spring", "japanese hot spring onsen at dusk", "♨️"),
    C("gym", "Gym", "modern gym", "🏋️"), C("cafe", "Café", "sunny parisian café terrace", "☕"),
    C("desert", "Desert", "golden desert dunes", "🏜️"), C("snow", "Snow cabin", "cozy log cabin with fireplace, snow outside", "🏔️"),
]
LIGHTING = [
    C("golden", "Golden hour", "warm golden hour sunlight", "🌅"), C("soft", "Soft studio", "soft studio softbox lighting", "💡"),
    C("neon_l", "Neon", "pink and blue neon lighting", "🔮"), C("candle", "Candlelight", "warm candlelight", "🕯️"),
    C("moon", "Moonlight", "cool moonlight", "🌙"), C("dramatic", "Dramatic", "dramatic low-key rim lighting", "🎭"),
]
CAMERAS = [
    C("portrait", "Portrait", "head and shoulders portrait"), C("half", "Half body", "medium shot, waist up"),
    C("full", "Full body", "full body shot, head to toe"), C("closeup", "Close-up", "close-up of the face"),
    C("low", "Low angle", "low angle shot"), C("high", "From above", "high angle shot from above"),
    C("back", "From behind", "view from behind, looking over shoulder"),
]
OBJECTS = [
    C("sword", "Sword", "an ornate sword", "🗡️"), C("wine", "Wine glass", "a glass of red wine", "🍷"),
    C("flowers", "Bouquet", "a bouquet of roses", "💐"), C("guitar", "Guitar", "an acoustic guitar", "🎸"),
    C("umbrella", "Umbrella", "a transparent umbrella", "☂️"), C("cat", "Cat", "a fluffy cat", "🐈"),
    C("sofa", "Sofa", "a velvet sofa", "🛋️"), C("bike", "Motorbike", "a sleek black motorbike", "🏍️"),
    C("book", "Book", "an old leather-bound book", "📕"), C("phone", "Phone", "a smartphone", "📱"),
    C("staff", "Magic staff", "a glowing magic staff", "🪄"), C("gun", "Sci-fi pistol", "a futuristic sci-fi pistol", "🔫"),
    C("coffee", "Coffee", "a cup of coffee", "☕"), C("pillow", "Pillow", "a large pillow", "🛏️"),
]
PLACEMENTS = [
    C("hand", "In her/his hand", "held in the character's hand"), C("beside", "Next to them", "next to the character"),
    C("table", "On a table", "on a table near the character"), C("bg", "In the background", "in the background"),
    C("left", "Left side", "on the left side of the picture"), C("right", "Right side", "on the right side of the picture"),
]
EXPRESSIONS = [
    C("neutral", "Neutral", "neutral expression"), C("smile", "Smile", "warm smile"), C("laugh", "Laugh", "laughing joyfully"),
    C("angry", "Angry", "angry frown"), C("sad", "Sad", "sad teary eyes"), C("surprised", "Surprised", "surprised open mouth"),
    C("flirty", "Flirty", "flirty smirk, one eyebrow raised"), C("sleepy", "Sleepy", "sleepy half-closed eyes"),
]
MOTIONS = [
    C("turn", "Turn around", "slowly turns around to face the camera", "🔄"), C("walk", "Walk to camera", "walks confidently toward the camera", "🚶"),
    C("wind", "Hair in wind", "hair and clothes moving gently in the wind", "🌬️"), C("wink", "Wink & smile", "winks and smiles at the camera", "😉"),
    C("dance", "Dance", "dances slowly and sensually", "💃"), C("sit", "Sit down", "sits down gracefully", "🪑"),
    C("stretch", "Stretch", "stretches arms above head", "🙆"), C("look", "Look around", "looks around, then back at the camera", "👀"),
    C("idle", "Idle loop", "breathing, subtle idle motion, blinking", "🫧"), C("orbit", "Camera orbit", "the camera orbits slowly around her", "🎥"),
]

# 4 views for a turnaround sheet; words match ComfyUI's CameraAngle node vocabulary (Multiple-Angles LoRA).
TURNAROUND = [("front", "front view eye-level shot wide shot"), ("right", "right side view eye-level shot wide shot"),
              ("back", "back view eye-level shot wide shot"), ("left", "left side view eye-level shot wide shot")]

POSES = [  # id, label; the stick-figure PNG lives in static/poses/<id>.png (drawn by tools/make_poses.py)
    ("standing", "Standing"), ("hands_hips", "Hands on hips"), ("arms_up", "Arms up"), ("walking", "Walking"),
    ("sitting", "Sitting"), ("kneeling", "Kneeling"), ("lying", "Lying down"), ("over_shoulder", "Over the shoulder"),
    ("leaning", "Leaning"), ("crouching", "Crouching"), ("hand_hair", "Hand in hair"), ("t_pose", "T-pose (for 3D)"),
    ("a_pose", "A-pose (for 3D)"),     ("reaching", "Reaching out"),
    ("angle_front", "Front"), ("angle_side", "Side"), ("angle_back", "Back"),
    ("angle_overhead", "Overhead"), ("angle_low", "Low angle"),
]

SHOOT_PACKS = [
    {"id": "beach", "label": "Beach day", "icon": "🏖️", "shots": [
        ("beach", "golden", "full", "standing", "bikini"), ("beach", "golden", "half", "hand_hair", "bikini"),
        ("beach", "golden", "back", "over_shoulder", "bikini"), ("pool", "golden", "full", "sitting", "onepiece"),
        ("beach", "golden", "portrait", None, "sarong"), ("beach", "golden", "full", "walking", "sarong")]},
    {"id": "boudoir", "label": "Boudoir", "icon": "🌹", "shots": [
        ("bedroom", "soft", "full", "lying", "lace_set"), ("bedroom", "candle", "half", "kneeling", "corset"),
        ("bedroom", "soft", "portrait", None, "silk_robe"), ("bathroom", "candle", "half", "leaning", "towel"),
        ("bedroom", "moon", "full", "sitting", "bodysuit"), ("bedroom", "soft", "back", "over_shoulder", "sheet")]},
    {"id": "fantasy", "label": "Fantasy hero", "icon": "⚔️", "shots": [
        ("castle", "dramatic", "full", "standing", "knight"), ("forest", "moon", "full", "walking", "witch"),
        ("dungeon", "candle", "half", "crouching", "knight"), ("castle", "dramatic", "low", "hands_hips", "knight")]},
    {"id": "night_out", "label": "Night out", "icon": "🌃", "shots": [
        ("neon", "neon_l", "full", "walking", "cocktail"), ("bar", "candle", "half", "leaning", "cocktail"),
        ("neon", "neon_l", "portrait", None, "leather"), ("bar", "dramatic", "half", "sitting", "evening")]},
    {"id": "game_portraits", "label": "Game portraits", "icon": "🎮", "shots": [
        ("studio", "soft", "portrait", None, None), ("studio", "soft", "half", "hands_hips", None),
        ("studio", "soft", "full", "standing", None), ("studio", "soft", "full", "a_pose", None)]},
]

# ---------------------------------------------------------------------------
# 18+ section only (fictional adults 21+; every safety rule still applies)
# ---------------------------------------------------------------------------
ADULT_OUTFIT_CATEGORIES = [
    {"id": "nude", "label": "Nude / topless", "icon": "🔞", "adult": True, "items": [
        C("topless", "Topless", "topless, nude from the waist up"), C("nude", "Nude", "fully nude"),
        C("open_shirt", "Open shirt, nothing under", "open unbuttoned shirt with nothing underneath, topless"),
        C("sheer_nude", "Sheer, see-through", "sheer see-through lingerie, nipples visible, nude underneath"),
        C("bottomless", "Just a top", "wearing only a cropped top, bottomless"),
        C("body_paint", "Body paint only", "nude, wearing only artistic body paint")]},
]
ADULT_SHOOT_PACKS = [
    {"id": "art_nude", "label": "Art nude (studio)", "icon": "🖼️", "adult": True, "shots": [
        ("studio", "dramatic", "full", "standing", "nude"), ("studio", "dramatic", "half", "hand_hair", "nude"),
        ("studio_dark", "dramatic", "back", "over_shoulder", "nude"), ("studio", "soft", "full", "reclining", "nude"),
        ("studio_dark", "dramatic", "full", "arms_behind_head", "nude"), ("studio", "soft", "half", "sitting", "topless")]},
    {"id": "morning", "label": "Lazy morning", "icon": "☀️", "adult": True, "shots": [
        ("bedroom", "golden", "full", "lying_back", "nude"), ("bedroom", "golden", "half", "sitting", "open_shirt"),
        ("bedroom", "soft", "full", "reclining", "topless"), ("bathroom", "soft", "half", "leaning", "nude")]},
    {"id": "pinup", "label": "Pin-up", "icon": "💋", "adult": True, "shots": [
        ("studio", "soft", "full", "hands_hips", "topless"), ("studio", "soft", "full", "kneeling", "topless"),
        ("studio", "soft", "half", "arms_behind_head", "topless"), ("studio", "soft", "full", "over_shoulder", "bottomless")]},
    {"id": "onsen", "label": "Hot spring", "icon": "♨️", "adult": True, "shots": [
        ("onsen", "soft", "half", "sitting", "nude"), ("onsen", "golden", "back", "over_shoulder", "nude"),
        ("onsen", "moon", "full", "standing", "towel"), ("onsen", "soft", "portrait", None, "nude")]},
]
ADULT_MOTIONS = [
    C("undress", "Slowly undress", "slowly takes off her top, revealing her bare breasts, confident and smiling", "👚"),
    C("sensual", "Sensual sway", "sways her hips slowly and sensually, nude, looking at the camera", "💃"),
    C("bed_stretch", "Stretch in bed", "lies in bed nude, stretches lazily and smiles at the camera", "🛏️"),
    C("shower", "Shower", "stands nude in the shower, water running down her body, eyes open, smiling", "🚿"),
    C("turn_nude", "Turn around (nude)", "nude, slowly turns around to show her back, then looks over her shoulder", "🔄"),
    C("blow_kiss", "Blow a kiss", "topless, blows a kiss to the camera and laughs", "😘"),
]
ADULT_POSES = [("reclining", "Reclining on side"), ("lying_back", "Lying on back"), ("arms_behind_head", "Arms behind head"),
               ("kneel_back", "Kneeling, leaning back"), ("pair_intimate", "Two adults, close")]


def adult_on():
    """True while a job runs in the 18+ section (pipelines sets AREA_FN)."""
    return bool(AREA_FN and AREA_FN() == "adult")


AREA_FN = None


def all_outfit_categories():
    return OUTFIT_CATEGORIES + (ADULT_OUTFIT_CATEGORIES if adult_on() else [])


def all_shoot_packs():
    return SHOOT_PACKS + (ADULT_SHOOT_PACKS if adult_on() else [])


def find(chips, cid):
    for c in chips:
        if c["id"] == cid:
            return c
    return None

def outfit_item(item_id):
    if isinstance(item_id, str) and ":" in item_id:  # also accept "category:item"
        item_id = item_id.split(":", 1)[1]
    for cat in all_outfit_categories():
        c = find(cat["items"], item_id)
        if c:
            return c
    return None

# Workshop stills. A few clothed presets from the outfits above. Nude is not in this
# list; the page adds it only after the 21+ area is unlocked.
WORKSHOP_CLOTHED = ("jeans_tee", "sundress", "suit", "yoga")
WORKSHOP_NUDE = "nude"
WORKSHOP_TRADEOFF = "The fast model does not keep the face, so a saved face is applied on the foundation model instead."
WORKSHOP_TIMING = "How long this takes on your PC has not been measured."


def workshop_choices():
    bodies = next(g["chips"] for g in CHARACTER_GROUPS if g["id"] == "body")
    clothes = []
    for iid in WORKSHOP_CLOTHED:
        item = outfit_item(iid)
        if item:
            clothes.append({k: item[k] for k in ("id", "label", "p") if k in item})
    return {"bodies": [{k: c[k] for k in ("id", "label", "p", "icon") if k in c} for c in bodies],
            "wardrobe": clothes, "tradeoff": WORKSHOP_TRADEOFF, "timing": WORKSHOP_TIMING}


def adult_extras():
    """Extra chips for the 18+ section (sent only after it is unlocked)."""
    import photoreal
    return {"outfits": ADULT_OUTFIT_CATEGORIES, "motions": ADULT_MOTIONS,
            "anatomy": list(photoreal.ANATOMY),
            "contact_preset": __import__("shot_qc").CONTACT_PRESET,
            "artifact_tips": __import__("shot_qc").public_tips(True),
            "looks": [{"id": "chroma", "label": "Chroma (18+ fallback)", "icon": "🔞"}],
            "poses": [{"id": i, "label": l, "img": f"/static/poses/{i}.png"} for i, l in ADULT_POSES],
            "packs": [{"id": p["id"], "label": p["label"], "icon": p["icon"], "count": len(p["shots"])} for p in ADULT_SHOOT_PACKS]}


def everything():
    """The JSON the web page loads once at start-up."""
    import photoreal
    import model_registry as reg
    lights = LIGHTING + [c if isinstance(c, dict) else c for c in photoreal.EXTRA_LIGHTS]
    return {"age": {"min": AGE_MIN, "max": AGE_MAX, "default": AGE_DEFAULT},
            "styles": STYLES, "genders": GENDERS, "groups": CHARACTER_GROUPS,
            "looks": [{"id": x["id"], "label": x["label"], "icon": x["icon"]} for x in photoreal.LOOKS if x["id"] != "chroma"],
            "clip_lengths": reg.clip_lengths(),
            "artifact_tips": __import__("shot_qc").public_tips(False),
            "shot_pattern": [{"role": "establish", "shot": "wide"}, {"role": "detail", "shot": "closeup"}],
            "lenses": list(photoreal.LENSES),
            "outfits": OUTFIT_CATEGORIES, "colors": COLORS, "materials": MATERIALS,
            "scenes": SCENES, "lighting": lights, "cameras": CAMERAS, "objects": OBJECTS,
            "placements": PLACEMENTS, "expressions": EXPRESSIONS, "motions": MOTIONS,
            "poses": [{"id": i, "label": l, "img": f"/static/poses/{i}.png"} for i, l in POSES],
            "packs": [{"id": p["id"], "label": p["label"], "icon": p["icon"], "count": len(p["shots"])} for p in SHOOT_PACKS],
            "workshop": workshop_choices()}
