# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""The face check's rules, in plain Python over landmark numbers: no OpenCV, no numpy, no files.

app/workers/face_worker.py holds the three calls that need OpenCV (load a picture, find faces, make an
embedding). Everything else is here, so it can be tested with made-up landmarks.

Landmarks are YuNet's five points for one face, in this order, in picture coordinates (x to the right,
y down): the subject's right eye (the left one in the picture), the left eye, the nose tip, the right
mouth corner, the left mouth corner.

What the live verdict checks: each picture shows the pose that was asked, the pictures are distinct, and one
identity runs through all of them. A single still photograph is unlikely to pass, because the steps need different
poses and the turns, tilt and look-up are measured against the straight pictures of the same capture.

What it does NOT check: whether a real person is in front of the camera. Five points on still pictures cannot tell
a person from a recording of a person making the poses, or from a series of pictures of someone in the five poses
shown to the camera in turn. Nothing here claims that. A check for that would need another model. The worker says
what kind of verdict it gives (LIVENESS_KIND), and the app records it with the enrolment.

Every number below is a starting value. It was set from how faces are built, not tuned on anyone's pictures;
the first real run is the first test, and the scores are kept so the numbers can be tuned after it.
"""
import math

STEPS = ("face_camera", "turn_left", "turn_right", "tilt", "look_up")
LIVENESS_KIND = "poses_only"  # what the live verdict is: poses, order, distinct pictures, one face. Not a replay check.

# The two model files this check is pinned to. The worker reads them only when the SHA-256 matches.
MODEL_FILES = {
    "detector": {"file": "face_detection_yunet_2023mar.onnx",
                 "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"},
    "embedder": {"file": "face_recognition_sface_2021dec.onnx",
                 "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"},
}

# Match threshold, as cosine similarity of two SFace embeddings. OpenCV publishes 0.363 as the value at which two
# pictures count as the same person; this check asks for more than that, and the app never goes below the floor.
FLOOR = 0.363
THRESHOLD = 0.40

# One picture, on its own (pose numbers as ratios of the eye distance, or degrees):
FRONT_YAW, FRONT_ROLL = 0.15, 8.0      # face_camera: nose near the middle between the eyes, eyes level
TURN_YAW = 0.22                        # turn_left, turn_right: the nose is well off to one side
TILT_ROLL = 12.0                       # tilt: the line through the eyes is clearly slanted
UP_PITCH = 0.50                        # look_up: the nose tip sits high between eyes and mouth
UP_YAW = 0.20                          # ... and the face is not turned
# Against the same capture's face_camera pictures:
REL_TURN = 0.15                        # a turn is at least this much beyond the frontal yaw, to one side
REL_TILT = 8.0                         # a tilt is at least this many degrees beyond the frontal roll
REL_UP = 0.05                          # look up lowers the nose's place between eyes and mouth by this much
DISTINCT = 0.002                       # two pictures differ by at least this much, in landmark units (the same file twice differs by 0)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def pose(lm):
    """yaw, roll (degrees) and pitch of one face from its five landmarks, or None for nonsense landmarks."""
    try:
        pts = [(float(p[0]), float(p[1])) for p in lm]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) != 5 or not all(math.isfinite(v) for p in pts for v in p):
        return None
    re_, le, nose, rm, lm_ = pts
    eyes = _sub(le, re_)
    dist = math.hypot(*eyes)
    mid = ((re_[0] + le[0]) / 2, (re_[1] + le[1]) / 2)
    mouth = ((rm[0] + lm_[0]) / 2, (rm[1] + lm_[1]) / 2)
    down = _sub(mouth, mid)
    span = _dot(down, down)
    if dist < 1e-6 or span < 1e-6:
        return None
    axis = (eyes[0] / dist, eyes[1] / dist)
    return {"yaw": _dot(_sub(nose, mid), axis) / dist,
            "roll": math.degrees(math.atan2(eyes[1], eyes[0])),
            "pitch": _dot(_sub(nose, mid), down) / span}


def shape(lm):
    """The landmarks with the eye distance as the unit and the eye midpoint as the origin: for comparing two pictures."""
    p = pose(lm)
    if p is None:
        return None
    pts = [(float(a[0]), float(a[1])) for a in lm]
    eyes = _sub(pts[1], pts[0])
    dist = math.hypot(*eyes)
    mid = ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
    return [((q[0] - mid[0]) / dist, (q[1] - mid[1]) / dist) for q in pts]


def step_ok(step, p):
    """Does this one picture show the asked pose? Alone, with no frontal picture to compare with."""
    if not p or step not in STEPS:
        return False
    if step == "face_camera":
        return abs(p["yaw"]) <= FRONT_YAW and abs(p["roll"]) <= FRONT_ROLL
    if step in ("turn_left", "turn_right"):
        return abs(p["yaw"]) >= TURN_YAW
    if step == "tilt":
        return abs(p["roll"]) >= TILT_ROLL
    return p["pitch"] <= UP_PITCH and abs(p["yaw"]) <= UP_YAW  # look_up


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def verdict(frames, threshold=THRESHOLD):
    """The live verdict on a whole capture: (True, "") or (False, a plain reason).

    frames: one row per picture, in the order the plan asked for them: {"step", "pose", "shape", "embedding"}.
    Only a True here lets enrolment go on. It says the poses, the order, the difference between pictures and one
    identity held up. It does not say a real person was there (see the top of this file)."""
    if not frames:
        return False, "There were no pictures to check."
    for row in frames:
        if row.get("pose") is None or not row.get("embedding"):
            return False, "A picture did not show one clear face."
    for row in frames:
        if not step_ok(row["step"], row["pose"]):
            return False, "A picture did not show the pose that was asked."
    shapes = [row["shape"] for row in frames]
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            if max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(shapes[i], shapes[j])) < DISTINCT:
                return False, "Two of the pictures are the same picture."
    front = [row["pose"] for row in frames if row["step"] == "face_camera"]
    base = {k: _median([p[k] for p in front]) for k in ("yaw", "roll", "pitch")} if front else None
    sides = {"turn_left": [], "turn_right": []}
    for row in frames:
        p = row["pose"]
        if row["step"] in sides:
            sides[row["step"]].append(p["yaw"] - (base["yaw"] if base else 0.0))
        elif base and row["step"] == "tilt" and abs(p["roll"] - base["roll"]) < REL_TILT:
            return False, "A tilt picture is not tilted enough compared with the straight ones."
        elif base and row["step"] == "look_up" and p["pitch"] > base["pitch"] - REL_UP:
            return False, "A look-up picture does not look up enough compared with the straight ones."
    # Left and right must lie on opposite sides. Which side is which depends on how the camera shows the picture, so
    # only the sign matters: all lefts on one side, all rights on the other, each clearly away from straight.
    signs = {}
    for name, yaws in sides.items():
        if not yaws:
            continue
        if base and any(abs(y) < REL_TURN for y in yaws):
            return False, "A turned picture is not turned enough compared with the straight ones."
        if len({y > 0 for y in yaws}) != 1:
            return False, "The turned pictures for one side do not all turn the same way."
        signs[name] = yaws[0] > 0
    if len(signs) == 2 and signs["turn_left"] == signs["turn_right"]:
        return False, "The left and right turns went the same way."
    vectors = [row["embedding"] for row in frames]
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            if cosine(vectors[i], vectors[j]) < max(threshold, FLOOR):
                return False, "The pictures do not all show the same face."
    return True, ""
