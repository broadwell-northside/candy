# First run: what to click, in order

Nothing real has run yet. Everything here was built and tested on stand-ins (a pretend picture engine, a pretend Keychain, no model files, no network). Your first click on a real model is the first real test, so expect rough edges and tell us what you see.

## 1. Start it

1. Open the repository folder containing `start_mac.command` in Finder and double-click **start_mac.command**. (In Terminal: `./start_mac.sh`.)
2. It starts the picture engine and the app, both on this Mac only, and opens your browser at `http://127.0.0.1:7860`. Leave the window open.
3. To stop: press Ctrl-C in that window, or run `./stop_mac.sh`.

If it says the picture engine is not installed, stop there and tell us.

## 2. Download the models (Setup, then Models)

Open **Setup** (the gear). The **Models** card has one **Download** button per group. Press them yourself; nothing downloads on its own.

- The page shows each group's size and how much space is free. It refuses a download if less than 50 GB would be left, it checks every file against its pinned hash, and it picks up where it left off if it is interrupted.
- Start with **Automatic age check** (about 0.4 GB, a few small files). Without it the app refuses to make anything.
- For video: **Small video model (Wan 2.2 5B)**, about 18 GB.
- For pictures: **Fast drafts + poses (Z-Image Turbo)**, about 24 GB.
- Those three together are about 42 GB. With about 100 GB free and 50 GB that must stay free, they fit; **Photo (SD 1.5)**, 4.3 GB, fits only just, and **Realistic pictures (Chroma1-HD)**, about 28 GB, does not fit with them. The page refuses a download that would break the floor, and shows the exact sizes and the free space.
- A group that says **Not pinned yet** cannot be downloaded from the page. Leave it.

## Your first photo

A made-up adult woman of a stated age of 30 on a fashion show runway: realistic skin, long flowing hair, glamorous, in a wide frame. One button, no choices.

1. Double-click **start_mac.command**, as in step 1.
2. **Setup, then Models.** Press **Download** for **Automatic age check** (small) and **Fast drafts + poses (Z-Image Turbo)** (about 24 GB; the page shows the exact size). The page refuses a download that would leave less than 50 GB free; if it refuses, free some space and press it again.
3. **Create**, then **First photo**. It makes 2 pictures, in the everyday section, with the same rules as any other picture. Movement such as flowing hair belongs to the video step (Build a video, then Extend).

How long it takes: not measured on this Mac yet. Expect a few minutes the first time, because the model has to load, and less after that. A picture the age check flags is deleted and never shown; press the button again for a new try.

If something fails, send back **the red message on the screen, exactly as written** (select it and copy it), and which button you pressed. A refusal from a rule is meant to be final: the message says which rule, and the answer is not to reword around it. The log of the run is in `~/candy/runtime/logs`.
## Add your own photos (Phase two, after Enrol)

After you enrol at the camera, **Add photos** takes a whole folder of photos of yourself, or single files, and tells you what it did with each one.

- A photo is kept only if it shows **exactly one face**, that face **matches the one you enrolled**, and the **age check clears it**. A photo of your body counts when your face is in it. A photo with no clear face, with two faces, of someone else, or that the age check flags is dropped, and the list says which. A flagged photo is final.
- Only **JPEG and PNG** are read. A HEIC file from an iPhone is listed as "not read": export it as JPEG first.
- Kept photos stay on this Mac in a private folder, with the same mark as your enrolment pictures, and are used only to train your likeness. **Remove my added photos** deletes them all. No picture is shown on the page and none is sent anywhere.
- A dropped "not the enrolled person" photo shows its match score, a number, so the match threshold can be tuned if too many of your own photos are dropped.

## 3. Make a video (Home)

- **Build a video**: type what you want to see in plain words, choose how long, pick a start picture if you like, and press **Build video**. Videos are realistic live-action only.
- **Extend a video**: take a clip you made and type what happens next. Press the button again to add another part. Each part starts from where the last one ended.
- **LoRAs**: the Build and Extend pages have a LoRA list, matched to the video model. The **LoRAs** tile lists what is on this computer.
- **Engine**: "This Mac" runs the local model. A hosted engine appears only after you add a key (next step).

## The 20-second proof (Build a video)

One click makes a 20-second clip of a woman of a stated age of 30, in a small bikini, walking along a beach: four parts of 5 seconds, joined. It is an everyday-section clip, photographic and live-action, with no LoRA.

1. Download only what it needs: **Automatic age check** and **Small video model (Wan 2.2 5B)**, about 18.5 GB in all. A start picture is not needed for the proof. (A start picture of your own needs the **Z-Image** group from Create.)
2. Open **Build a video** and press **Make the 20-second proof**. It fills the description and the age (30) for you; you can read them in the boxes.
3. Choose the **Engine** first. **This Mac** runs Wan 2.2 5B. The hosted engine appears after you add your Alibaba Model Studio key (below); it is the higher-quality path, it needs the key, and a hosted extend sends the last picture of the clip, which needs **Allow a picture to be sent to a hosted service** to be on.
4. The first 5 seconds are built, then one extend adds three more parts, in this order: she keeps walking along the waterline; she turns toward the waves and walks into the shallow water; she turns back and walks up the beach toward the dunes.

How long it takes, honestly: about 10 minutes for each 4-second clip with the 5B model on this Mac, so roughly 50 to 60 minutes for the 20 seconds. Nothing has been run on a real model yet, so the first run is also the first test. If something stops, the page says why; a clip the age check flags is deleted and you can try again with a new seed.

A person that your words bring in ("a woman ...") needs an age of 21 or more in the **Age of the person** box. Without it, or under 21, the job is refused.

## 4. Optional: a hosted video service (Setup, then API keys)

Paste your Alibaba Model Studio key once. It goes into the Mac's Keychain, the app never shows it again, and it is never written to a file. The hosted engine then appears on the Build and Extend pages. Sending a picture or the end of a clip to it is off until you tick **Allow a picture to be sent to a hosted service**.

## 5. Check the whole chain (Setup, then Self-test)

**Run the self-test** builds a picture, a clip, a longer clip and a 3D model of a made-up adult through the same jobs as the pages, and shows pass or fail, the time and the numbers for each step. It takes a while. **Test the trainer** runs a short training test on drawn shapes.

## Train your likeness (the trainer, safely)

Training your own picture model runs on this Mac and needs two things you download yourself. Nothing is installed or downloaded for you.

1. **Install the trainer once.** In a terminal, from the Easy Studio folder: `install/install_trainer_mac.sh`. It takes one fixed version of the trainer (a pinned commit), checks the commit and the two requirements files against their hashes, and installs into its own folder. It never pulls "latest" and downloads no model.
2. **Download the trainer's base model (Setup, then Models).** There is one group per base: **Trainer base for Fast pictures (Z-Image Turbo)**, about 33 GB, and **Trainer base for Realistic pictures (Chroma1-HD)**, about 28 GB. Each file is pinned to a revision and a hash, and the page refuses the download if less than 50 GB would be left free. Pick the one you train on.
3. **It runs offline.** At run time the trainer never reaches Hugging Face or anything else. Every offline switch is on, no login or key is passed to it, and on a Mac the system itself denies it everything on the network, including this computer's own programs and the name lookup; only its own worker processes can talk to each other, inside a private folder. If a base is not fully downloaded, the run stops with a plain message naming the group to download.
4. **Test the trainer** (Setup, then Self-test) is the go or no-go. The real trainer has never run on this Mac.

Not every package the trainer needs is pinned by hash: its own requirements files pin only some, so pip takes the rest from the public index at install time. That is the one part of the install that is not fixed.

## What it will not do

- **18+ and likeness stay on this Mac.** A hosted service is never used for the 18+ section, for anything marked as your likeness, for any LoRA, or for a picture the age check has not cleared. The app refuses before it sends anything.
- **Phase two is hidden:** My likeness, the face scan, Add photos, the avatar and the 3D self-model. They are built and switched off. The switch is **Setup, then Phase two**. The face check's model files are not offered on the Models page while it is hidden.
- **Refused in every section:** violence and gore, non-consensual or degrading acts, cruelty to animals, other grave harm, and anyone who is not a clearly stated adult of 21 or more.
- A picture or clip the age check flags is deleted and never shown. The job says so and offers another try with a new seed.
- The hosted video service was written from its public documentation and has never been tried with a real key.
