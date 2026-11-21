# Stillwater

A quiet, private island for one player. You walk the beach, swim, lie in the sun, and talk. The other places on the island are still to come.

Everyone in the game is a fictional adult, aged 21 or older. There are no real people. The pictures that ship with the game are simple coloured shapes, so you can play before any art exists. Your own pictures, made in Easy Studio, can replace them later.

## Play it on a Mac

1. Download **Godot 4** from [godotengine.org/download](https://godotengine.org/download/macos/). Choose the standard version (not the .NET one). Open it once so the Mac lets it run.
2. In Godot, click **Import**, then choose the `game` folder inside Easy Studio. That is the folder that contains `project.godot`.
3. Press the **Play** button (the triangle at the top right), or press F5. Confirm you are 21 or older, then choose **New game** and a save slot. On the island, choose **Beach**.

Windows and Linux are the same three steps. Godot 4.3 or newer is enough. This project was tried on Godot 4.7.

The project opens on GL Compatibility so it can run without a fast graphics card. For the desktop look (Forward+), start it with:

```bash
godot --path game --rendering-method forward_plus
```

Or run `bash game/tools/play_forward.sh`. You can also choose **Forward+** under Settings, Graphics. The headless checks stay on GL Compatibility.

## What you do

The first time, the game asks you to confirm you are 21 or older. If you are under 21, it closes. If you already confirmed on a build that asked for 18, the game asks again.

The title screen has:

- **Continue**, once the game has saved anything. This picks up the autosave.
- **New game**. Three slots. If a slot already has a story, click it twice to replace it.
- **Load**.
- **Settings**.
- **Quit**.

On the island map, only the **Beach** is open. Lagoon, Cliffs, Village and Hut say **Coming soon**. Clicking them does not take you there.

The beach is a 3D place. You walk the sand with W A S D or the arrow keys. The camera sits behind you. Click the view and move the mouse to look. Esc releases the mouse. **Map** returns to the island. **View** switches between that camera and first person. **Let a little time pass** moves the day along.

The person you walk as is a plate at eye level, with a little parallax and a breathing motion. In the morning, Mira Costa and Nia Sol stand on the sand as the same kind of plate, with a name above each of them. Each of their files states an age of 21 or older. One press of **Let a little time pass** puts each of them on the spot written for the next part of the day. The picture that ships here is a person-shaped stand-in. A small caption says it is not the finished photo. The words are not painted on the figure. When you have one, put an alpha-matted still or a short `.ogv` clip in `game/data/plate.json`. That main slot is the full picture. An optional SFW file can sit beside it, and SFW mode stays off unless that file is selected. The beach is not locked to one covered outfit.

The beach level and the plate are glTF files: `game/assets/beach/level.gltf` and `game/assets/plates/plate.gltf`. Godot plays them. They are not stored as a Godot-only scene. Rebuild them with `python3 game/tools/export_beach_gltf.py`.

The beach itself shows only a few labels: the place and the time, View, Let a little time pass, Map, the two names, and a small stand-in caption.

Nothing in the game hurries you. There is no score and no way to lose.

## Saving

There are three save slots, plus an autosave. The game writes the autosave when you change place, finish a conversation, swim, rest, or the light changes. **Continue** on the title screen loads that autosave.

The slots live on your computer, not in the `game` folder:

- Mac: `~/Library/Application Support/Godot/app_userdata/Stillwater/`
- Linux: `~/.local/share/godot/app_userdata/Stillwater/`
- Windows: `%APPDATA%\Godot\app_userdata\Stillwater\`

Deleting those files starts you over. It does not change the game itself.

## Settings

- **Volume**
- **Fullscreen**
- **Graphics.** GL Compatibility, or Forward+ on a desktop machine.
- **Text speed** (slow, normal, fast). Click a line of dialogue to show the rest of it at once.
- **Adult pictures.** This is **off** to start with. It applies to the older picture screens. Off uses the covered file. On uses the adult variant, once you have added one. The 3D beach plate does not use this switch. Its main file is the full slot, and its SFW files stay unused unless `sfw_mode` is turned on in `plate.json`. The placeholder art is not explicit either way. Everyone is still a fictional adult.
- **Conversation helper.** Built-in lines work with nothing else installed. If you later run [Ollama](https://ollama.com) on this computer, you can switch the helper to Ollama and type its address (normally `http://127.0.0.1:11434`) and a model name. If Ollama does not answer, the game uses its built-in lines.

## If a character is refused

On startup the game reads every file in `game/data/characters/`. `stated_age` has to be a whole number, 21 or older. A blank, a word, or a fraction such as 21.5 is refused. The game does not guess an age or round one up. If any file is refused, the game stops and names the file. It will not skip that character and carry on. Fix the age or remove the file.

## Putting your Easy Studio pictures in

In Easy Studio, open **Game assets** and use **Export to Godot 4**. You get a zip.

On the Mac, open Terminal, go to the Easy Studio folder, and run one command. Use `covered` for everyday pictures and `adult` for pictures that should appear only when Adult pictures is on:

```bash
python3 game/tools/import_easy_studio.py "/path/to/Mira_godot.zip" --character mira --variant covered
```

```bash
python3 game/tools/import_easy_studio.py "/path/to/Mira_godot.zip" --character mira --variant adult
```

`--character` is the id the game already uses: `mira`, `leo` or `nia`. A new id is also fine if you add a matching conversation later. The person's age must be a whole number, 21 or older. The script refuses anyone younger, anyone with no age, a blank, a word, or a fraction. If the file has both `stated_age` and `age`, those two values have to match. The script does not guess 21, and it does not copy a file it refuses.

A workshop pack is the zip Easy Studio writes for the island. Inside it, `assets/characters/<name>/character.json` names the person, the age, and which files are covered or adult. That zip also contains a small preview `project.godot`. The importer does not open that file and does not copy it over the island. Keep opening the island's own `project.godot`.

`--variant` has to match `variant` when the character file has one. With `--variant covered`, only the covered files are copied. `--variant adult` is the switch for explicit files: they go in the adult slot, and the covered files still go in the covered slot. Adult pictures in the game stay off until you turn them on. Off always shows the covered file.

`look.lora_id` is copied when the pack includes one. The importer does not invent an id. An empty id stays empty. Pictures land in `assets/imports/`. That folder is left out of git. Do not commit a generated pack.

Video needs **ffmpeg** installed (`brew install ffmpeg` on a Mac). The script turns `.mp4` into `.ogv`, which is the clip Godot can play, and it saves a still picture beside it. If a clip is missing, the game shows the still.

Then open the game in Godot again. Godot will notice the new files. You do not need to press anything else.

If the zip holds more than one person, add `--source` with the folder name from inside the zip, for example `--source mira_costa`.

## Folder layout

```
game/
  project.godot          Open this in Godot
  icon.png
  export_presets.cfg     Linux and macOS export settings
  README.md              This file
  data/
    characters/          One JSON file per person
    dialogues/           Their conversations
    scenes.json          Which picture or clip plays for a place, person, time and activity
    locations.json       The island places, and which ones are locked
  assets/
    backgrounds/         Beach paintings for morning, midday, sunset and night
    characters/          Placeholder portraits
    plates/              The Stage 1 stand-in plate and its depth map
    scenes/              Placeholder scene stills, and one sample .ogv clip
    audio/               Waves and wind
    imports/             Created by the import script when you add Easy Studio art
  data/plate.json        The plate slot: glTF mesh, full still or clip, optional SFW files
  assets/beach/level.gltf  The beach meshes, in glTF
  assets/plates/plate.gltf The Stage 1 plate, in glTF
  scenes/                The Godot screens, including the 3D beach
  scripts/               The game code
  shaders/               Sand, ocean, and the plate
  tools/
    import_easy_studio.py
    make_placeholders.py Rebuilds the coloured-shape art
  tests/                 Checks that run without opening a window
```

A character file looks like this:

```json
{
  "id": "mira",
  "name": "Mira Costa",
  "stated_age": 32,
  "personality": "Warm and unhurried.",
  "look": {
    "summary": "A fictional adult woman of 32, with olive skin and a linen shirt.",
    "lora_id": "easy_studio/mira_costa"
  },
  "portraits": {
    "smile": {
      "covered": "res://assets/characters/mira/smile_covered.png",
      "adult": "res://assets/characters/mira/smile_adult.png"
    }
  },
  "clips": {
    "idle": { "covered": "", "adult": "" }
  }
}
```

`stated_age` is required and must be a whole number, 21 or more. `lora_id` is the Easy Studio look, for when you train one. Portraits are still pictures. Clips are for short movies. Each one can have a `covered` file and an `adult` file.

`scenes.json` picks what plays. A row names a place, a person (`any` means whoever is there), a time of day (`any` is fine), an activity such as `swim`, and how close you need to be. The scene player uses the covered file unless Adult pictures is on.

## What is not in this version yet

- A finished photo on the beach. What stands there now is a person-shaped stand-in, not the final still or clip. A rigged body is only a later hook and is not shown.
- Real paintings and clips. Easy Studio is where the real art will come from.
- A talking AI, unless you install Ollama yourself and switch it on. The built-in lines are the normal way to play.
- Voices.
- The lagoon, the cliffs, the village and the hut. They are on the map so you can see they are planned.
- The rest of the holiday. This beach has two people and the time of day. The other places are not in this build.

## Checking it still works

From the Easy Studio folder, with Godot 4 installed as `godot`:

```bash
python3 game/tools/test_import.py
godot --headless --rendering-method gl_compatibility --path game res://scenes/tests.tscn
```

Those checks cover the age rule, the scene list, saving and loading, conversation branches, the locked places, and that adult pictures start off. GitHub runs the same checks, and it also builds a Linux file and a Mac zip.
