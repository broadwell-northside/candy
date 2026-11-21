# The face check

The app makes pictures of a real person, so it checks once that the photos are of the person using it. The check runs on this Mac. Nothing leaves it.

## What it is

- `app/workers/face_worker.py` runs in the picture engine's own Python. It uses two small models and one library:
  - YuNet (MIT) finds the face and five landmarks (eyes, nose tip, mouth corners).
  - SFace (Apache-2.0) turns the face into 128 numbers for matching.
  - OpenCV (headless build, Apache-2.0) runs both.
- `app/workers/face_logic.py` holds the rules: which pose each step needs, the live verdict, the threshold.
- The files, their sizes and hashes are in `config/server_model_lock.json`: two rows (`face.face_detection_yunet_2023mar`, `face.face_recognition_sface_2021dec`) in their own download group `face`, which is not in the default set, so the Models page and `download_models.py all` do not fetch them and the library under `runtimes.opencv_python_headless`.

## Putting it in place (by hand, when the owner says so)

1. Fetch the two files named in the lock rows into `<runtime>/ComfyUI/models/easy_studio/face_check/`. Check each file's SHA-256 against its row. The worker checks the same hash before it loads anything.
2. Install the library into the engine's Python, from the wheel named under `runtimes.opencv_python_headless`, with `--no-deps --require-hashes`.
3. Start the app. The Setup page's Enrol button shows the check as ready.

If the library does not import with the numpy that is installed, install the older wheel named under `runtimes.opencv_python_headless.fallback` instead (4.13.0.92). Its hash is in the lock too.

When the check cannot start, the app says why in one of three fixed ways: the model files are missing, the files are not the ones the app expects, or the library did not start.

## What it checks

- Each picture shows exactly one face.
- Each picture shows the pose that was asked: turn left, turn right, tilt, look up, or straight. The older "blink" step is gone: five landmarks cannot see a blink.
- The pictures of a capture are distinct, and the turns to the left and to the right lie on opposite sides.
- One face runs through all the pictures of a capture.
- Later, a picture made by the app counts as the owner only when its face matches the enrolled one.

## What it cannot check

**Whether a real person is in front of the camera.** Five landmarks on still pictures cannot tell a person from a recording of a person making the poses, or from a series of pictures of someone in the five poses shown to the camera in turn. A single still photograph is unlikely to pass, because the steps need different poses and the turns, tilt and look-up are measured against the straight pictures of the same capture. The live verdict says the poses, their order, the difference between pictures and one identity held up. It does not say a real person was there. A check for that would need another model.

**18+ pictures of the likeness need more than this check gives.** A recording of another person making the five poses would pass the pose-only verdict, and 18+ pictures of that person must never be possible. So the 18+ consent cannot be given, and an 18+ likeness job is refused, unless the enrolment was made with a live check of kind `pad` (a real presentation-attack check). With the shipped worker (`poses_only`) the message says "18+ pictures of your likeness need a live check this face check does not have yet". Everyday pictures of the owner are not affected. Enrolments made before the kind was recorded count as pose-only.

The worker names what kind of verdict it gives (`"liveness": "poses_only"` in its first line). The app accepts only the kinds in `ACCEPTED_LIVENESS` (`poses_only`, and `pad` for a worker with a real presentation-attack check), records the kind with the enrolment, and saves nothing for a worker that names no kind or an unknown one. Dropping `poses_only` from that list makes enrolment refuse until a worker with a real check exists.

The other gates of enrolment are unchanged: a stated age of 21 or more, the age check on every picture, no more than one face, a fresh code for every step, a time limit per step, and the camera page as the only input.

## The numbers are untuned

The match threshold is 0.40, cosine similarity of two SFace embeddings. OpenCV publishes 0.363 as the value at which two pictures count as the same person; the app never goes below it. The pose limits in `face_logic.py` come from how faces are built, not from anyone's pictures. The first real run is the first test. At enrolment the app keeps the lowest and the mean score of the capture (numbers only, in `outputs/owner/match_set.json`) so the numbers can be tuned after it.

## Which model made the enrolment

The enrolment records the model's name, which carries the short hashes of both files. A picture judged by another model is never a match: the numbers mean nothing across models. Changing the files means enrolling again.
