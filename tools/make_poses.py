"""Draw the bundled pose presets as OpenPose-style stick figures (app/static/poses/*.png).
Run:  python tools/make_poses.py      (Pillow only; re-run after editing a pose below)
Coordinates are 0..1 of an 832x1216 canvas. 'R'/'L' are the figure's own right/left
(a figure facing you has its right side on the image's left)."""
import os
from PIL import Image, ImageDraw

W, H = 832, 1216
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "static", "poses")
NAMES = ["nose", "neck", "rsho", "relb", "rwri", "lsho", "lelb", "lwri", "rhip", "rknee", "rank",
         "lhip", "lknee", "lank", "reye", "leye", "rear", "lear"]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
         (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0),
          (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255),
          (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]

STAND = dict(nose=(.5, .13), neck=(.5, .21), rsho=(.40, .22), relb=(.37, .35), rwri=(.36, .47), lsho=(.60, .22),
             lelb=(.63, .35), lwri=(.64, .47), rhip=(.44, .50), rknee=(.44, .70), rank=(.44, .90), lhip=(.56, .50),
             lknee=(.56, .70), lank=(.56, .90), reye=(.48, .115), leye=(.52, .115), rear=(.46, .125), lear=(.54, .125))


def pose(**changes):
    d = dict(STAND)
    d.update(changes)
    return d


def shift_head(d, dx, dy=0):
    for k in ("nose", "reye", "leye", "rear", "lear"):
        x, y = d[k]
        d[k] = (x + dx, y + dy)
    return d


POSES = {
    "standing": pose(),
    "hands_hips": pose(relb=(.30, .33), rwri=(.42, .46), lelb=(.70, .33), lwri=(.58, .46)),
    "arms_up": pose(relb=(.36, .12), rwri=(.40, .03), lelb=(.64, .12), lwri=(.60, .03)),
    "walking": pose(relb=(.39, .35), rwri=(.43, .46), lelb=(.62, .34), lwri=(.60, .45), rknee=(.42, .69),
                    rank=(.37, .88), lknee=(.58, .71), lank=(.60, .91)),
    "sitting": pose(rhip=(.44, .55), lhip=(.56, .55), rknee=(.38, .62), lknee=(.62, .62), rank=(.40, .84),
                    lank=(.60, .84), rwri=(.40, .55), lwri=(.60, .55), relb=(.37, .40), lelb=(.63, .40),
                    **{k: (v[0], v[1] + .08) for k, v in STAND.items() if k in ("nose", "neck", "rsho", "lsho", "reye", "leye", "rear", "lear")}),
    "kneeling": pose(**{k: (v[0], v[1] + .12) for k, v in STAND.items() if k in ("nose", "neck", "rsho", "lsho", "reye", "leye", "rear", "lear", "relb", "lelb", "rwri", "lwri")},
                     rhip=(.44, .62), lhip=(.56, .62), rknee=(.43, .82), lknee=(.57, .82), rank=(.43, .95), lank=(.57, .95)),
    "lying": {"nose": (.16, .62), "neck": (.25, .64), "rsho": (.26, .60), "relb": (.20, .52), "rwri": (.13, .52),
              "lsho": (.26, .68), "lelb": (.38, .70), "lwri": (.50, .69), "rhip": (.55, .62), "rknee": (.71, .60),
              "rank": (.88, .62), "lhip": (.55, .67), "lknee": (.70, .70), "lank": (.86, .72), "reye": (.15, .60),
              "leye": (.15, .63), "rear": (.18, .59), "lear": (.18, .65)},
    "over_shoulder": shift_head(pose(rsho=(.58, .22), lsho=(.42, .22), relb=(.62, .35), rwri=(.63, .47),
                                     lelb=(.38, .35), lwri=(.37, .47), rhip=(.55, .50), lhip=(.45, .50),
                                     rknee=(.55, .70), lknee=(.45, .70), rank=(.55, .90), lank=(.45, .90),
                                     reye=(.47, .115), leye=(.47, .115), rear=(.53, .125), lear=(.47, .14)), -.04),
    "leaning": pose(neck=(.47, .22), nose=(.45, .14), reye=(.43, .125), leye=(.47, .12), rear=(.41, .13), lear=(.49, .13),
                    rsho=(.37, .24), lsho=(.57, .22), relb=(.27, .30), rwri=(.20, .25), lelb=(.62, .35), lwri=(.60, .47),
                    rknee=(.47, .70), rank=(.52, .90)),
    "crouching": pose(**{k: (v[0], v[1] + .22) for k, v in STAND.items() if k in ("nose", "neck", "rsho", "lsho", "reye", "leye", "rear", "lear")},
                      relb=(.37, .54), rwri=(.42, .64), lelb=(.63, .54), lwri=(.58, .64), rhip=(.44, .70), lhip=(.56, .70),
                      rknee=(.34, .66), lknee=(.66, .66), rank=(.40, .90), lank=(.60, .90)),
    "hand_hair": pose(relb=(.30, .14), rwri=(.44, .08), lelb=(.66, .34), lwri=(.58, .47)),
    "t_pose": pose(relb=(.26, .22), rwri=(.12, .22), lelb=(.74, .22), lwri=(.88, .22)),
    "a_pose": pose(relb=(.31, .31), rwri=(.23, .40), lelb=(.69, .31), lwri=(.77, .40), rank=(.42, .90), lank=(.58, .90)),
    # 18+ section poses (still ordinary body poses)
    "reclining": {"nose": (.20, .52), "neck": (.27, .56), "rsho": (.27, .52), "relb": (.20, .44), "rwri": (.17, .36),
                  "lsho": (.30, .60), "lelb": (.40, .62), "lwri": (.50, .60), "rhip": (.55, .60), "rknee": (.70, .56),
                  "rank": (.86, .62), "lhip": (.56, .65), "lknee": (.72, .68), "lank": (.88, .70), "reye": (.19, .50),
                  "leye": (.21, .51), "rear": (.23, .49), "lear": (.24, .53)},
    "lying_back": {"nose": (.14, .60), "neck": (.23, .62), "rsho": (.24, .57), "relb": (.14, .50), "rwri": (.06, .55),
                   "lsho": (.24, .67), "lelb": (.14, .74), "lwri": (.06, .69), "rhip": (.55, .59), "rknee": (.70, .54),
                   "rank": (.86, .60), "lhip": (.55, .65), "lknee": (.71, .68), "lank": (.87, .66), "reye": (.13, .58),
                   "leye": (.13, .62), "rear": (.16, .57), "lear": (.16, .64)},
    "arms_behind_head": pose(relb=(.30, .10), rwri=(.46, .09), lelb=(.70, .10), lwri=(.54, .09)),
    "kneel_back": pose(**{k: (v[0] + .04, v[1] + .14) for k, v in STAND.items() if k in ("nose", "neck", "reye", "leye", "rear", "lear")},
                       rsho=(.42, .36), lsho=(.62, .36), relb=(.40, .50), rwri=(.42, .64), lelb=(.64, .50), lwri=(.62, .64),
                       rhip=(.46, .64), lhip=(.58, .64), rknee=(.40, .84), lknee=(.62, .84), rank=(.52, .95), lank=(.70, .95)),
    "reaching": pose(lelb=(.72, .20), lwri=(.86, .16), relb=(.37, .35), rwri=(.36, .47)),
}


def draw(kp, path):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(kp[n][0] * W, kp[n][1] * H) for n in NAMES]
    for i, (a, b) in enumerate(LIMBS):
        d.line([pts[a], pts[b]], fill=tuple(int(c * .6) for c in COLORS[i % 18]), width=14)
    for i, p in enumerate(pts):
        r = 8
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=COLORS[i])
    im.save(path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, kp in POSES.items():
        draw(kp, os.path.join(OUT, name + ".png"))
    print(f"wrote {len(POSES)} poses to {os.path.abspath(OUT)}")
