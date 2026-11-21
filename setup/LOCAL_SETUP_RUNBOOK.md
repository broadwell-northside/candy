# Local setup runbook

This is for Codex, on the owner's computers, using computer control. It does not change
the safety rules. It does not create another inbox.

Report every step on GitHub issue #1:
https://github.com/broadwell-northside/easy-studio/issues/1

Use a new id each time, `ES-SETUP-YYYYMMDD-NNN`. Copy this shape:

```
ES-SETUP-YYYYMMDD-NNN
Sender: Codex
Status: READY_FOR_INGEST or BLOCKED
Scope: the step name below
Command run: the command
Output summary: a few lines, with no secrets
Pass or fail:
Notes:
```

Stop at the first step whose output does not match. Post the report, and do not continue.

## Rules before any command

- Work only inside the Easy Studio folder, for example `C:\easy-studio` or `~/easy-studio`.
- Do not open, edit, build, or run BlueNord or any other project.
- Do not change global Git settings. Do not change the system Python other projects use.
- Easy Studio uses its own `.venv`, `ComfyUI/venv`, and `trainer/ai-toolkit/venv`.
- Do not commit model weights, `outputs/`, `password.txt`, pictures, or videos.
- Do not put a Hugging Face token, a Civitai key, a cookie, or a password in a file or in the issue.
- If a download asks for a token, the owner types it in that terminal window. Clear it afterwards with `set HF_TOKEN=` on Windows or `unset HF_TOKEN` on Linux and macOS.
- Re-running a step is safe. "Already installed" or "already there" is a pass.
- The evidence pull request stays separate. Do not merge it, and do not copy evidence into this folder.

The app installers already exist. Use them. Do not write a second installer.

| Job | Windows | Linux |
|---|---|---|
| App, ComfyUI, default models | `install_windows.bat` | `bash install_linux.sh` |
| Skip the big download | `install_windows.bat -NoModels` | `bash install_linux.sh nomodels` |
| Character trainer | `install_trainer.bat` | `bash install_trainer.sh` |
| Start | `start_windows.bat` | `./start_linux.sh` |
| Model groups | `.venv\Scripts\python install\download_models.py` | `.venv/bin/python install/download_models.py` |

No custom nodes are required. The workflows use nodes that ship with ComfyUI.

## Machine 1 — desktop

Windows 11 is the preferred path. The Linux path is the same steps with the Linux command.
The graphics card is not confirmed until the install hold ends. Andrew has deferred
this setup, so do not assume the desktop is reachable. Write down whatever
`nvidia-smi` prints when it is. Do not treat a 96 GB RTX PRO 6000 as a measured fact.

### Step 0 — preflight

Windows:

```
cd C:\easy-studio
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python setup\preflight.py
```

Linux:

```
cd ~/easy-studio
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python setup/preflight.py
```

Check: the command prints one line per item.

Expected:

- `INFO  GPU:` the name nvidia-smi printed. This line does not pass or fail.
- `INFO  VRAM:` the MiB number, recorded the same way. A missing GPU is `FAIL`.
- `PASS  Driver:` is 570 or newer
- `PASS  CUDA:` is 12.8 or newer
- `PASS  RAM:` is 64 GB or more
- `PASS  Disk:` is at least 200 GB free
- `MANUAL  PSU:` you still read the power-supply label and write the wattage in the issue

If any line says `FAIL`, stop and report. Do not start the installer.
Between 32 and 64 GB of RAM is a fail until the owner says to continue.
An unfamiliar GPU name is not a fail. Copy it into the issue.

Also write down Windows or Linux. That is part of the report.

### Step 1 — install Git, Python, FFmpeg, ComfyUI, and PyTorch

Windows, in the Easy Studio folder:

```
install_windows.bat -NoModels
```

Linux:

```
bash install_linux.sh nomodels
```

This is allowed to take a long time. If it stops, run the same command again.

Check, Windows:

```
git --version
py -3.12 --version
ffmpeg -version
.venv\Scripts\python -c "import fastapi, PIL, numpy, requests; print('app-ok')"
ComfyUI\venv\Scripts\python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Check, Linux:

```
git --version
python3 --version
ffmpeg -version
.venv/bin/python -c "import fastapi, PIL, numpy, requests; print('app-ok')"
ComfyUI/venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Expected:

- Git, Python, and FFmpeg each print a version.
- `app-ok`
- PyTorch prints a version ending in `+cu130` or `+cu128`, then `True`

If CUDA is `False`, stop. Do not download models yet. The usual cause is the driver.
Install the current NVIDIA driver for this desktop card, reboot, and run preflight again.

### Step 2 — confirm no extra custom nodes

```
dir ComfyUI\custom_nodes
```

Linux: `ls ComfyUI/custom_nodes`

Expected: only what a fresh ComfyUI clone contains (an example file is normal).
If you see a pack you installed yourself, or ComfyUI-Manager, stop and report.
Do not install custom nodes.

### Step 3 — default model download

Windows:

```
.venv\Scripts\python install\download_models.py --comfy ComfyUI --list
.venv\Scripts\python install\download_models.py --comfy ComfyUI --what all
```

Linux: the same commands with `.venv/bin/python`.

`--what all` is the default set: image, anime, fast, edit, tools, video, 3D, and the
age check. It is about 139 GB. It skips files that are already there. Run it again if
a download stops.

Expected last line: `All model files are in place.`

Do not download the optional groups in this step.

Optional groups, only if the owner asks later:

| Group | About | Note |
|---|---|---|
| `video-t2v` | 38 GB | Wan 2.2 text to video |
| `video-wan5b` | 18 GB | Wan 2.2 5B |
| `video-ltx` | 40 GB | Needs the owner to accept the licence on Hugging Face and type `HF_TOKEN` in the terminal. Do not save the token. |
| `video-hunyuan` | 46 GB | Not licensed in the EU, the UK, or South Korea |
| `video-kandinsky` | 19 GB | |
| `3d-shape` | 7 GB | Same territory limit. Not in the default install. |

Example, only when asked: `--what video-ltx`

### Step 4 — character trainer

Windows: `install_trainer.bat`
Linux: `bash install_trainer.sh`

The trainer's script installs PyTorch for CUDA 12.8. The app installer tries CUDA 13
first. If the trainer's PyTorch install fails, stop and report. Do not edit the
installer in this step.

Check, Windows:

```
trainer\ai-toolkit\venv\Scripts\python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Linux: `trainer/ai-toolkit/venv/bin/python` with the same command.

Expected: a version string and `True`.

### Step 5 — firewall

ComfyUI must listen only on this PC. The app port is 7860, and only for the home network.

Windows, in an administrator PowerShell:

```
powershell -NoProfile -ExecutionPolicy Bypass -File setup\firewall_windows.ps1
```

Expected: `PASS` and one rule named `Easy Studio LAN 7860` for Private networks.
There must be no rule from this script for port 8188.

Linux:

```
bash setup/firewall_linux.sh
```

Expected: either `PASS` and a ufw line for port 7860, or `MANUAL` saying ufw is off.
If ufw is off, stop and report. Do not turn ufw on yourself.

### Step 6 — self-test, no GPU pictures

Windows: `.venv\Scripts\python tests\run_tests.py`
Linux: `.venv/bin/python tests/run_tests.py`

Expected last line: `482/482 checks passed`

If the number is lower, stop and paste the `FAIL` lines. Do not paste a password.

### Step 7 — start the app

Windows: double-click `start_windows.bat` or run it from the folder.
Linux: `./start_linux.sh`

Check from the desktop:

```
curl -s http://127.0.0.1:8188/system_stats
curl -s -o NUL -w "%{http_code}" http://127.0.0.1:7860/api/status
```

Linux uses `-o /dev/null` instead of `NUL`.

Expected:

- The ComfyUI address returns JSON.
- The app returns `200` from this PC. This PC does not need the password when the
  password was created automatically.
- The window prints a LAN address and says the password is in `outputs/password.txt`.
- Read that file only to use it. Do not commit it and do not paste it into the issue.

From another machine, port 8188 must not answer. The next machine checks that.

### Step 8 — first real GPU smoke

Leave the app running. In a second terminal, from the Easy Studio folder:

Windows:

```
.venv\Scripts\python setup\gpu_smoke.py --out outputs\gpu_smoke_report.md
```

Linux:

```
.venv/bin/python setup/gpu_smoke.py --out outputs/gpu_smoke_report.md
```

The report file is under `outputs/`, which is not committed. Copy its text into
issue #1. It has the seconds and peak VRAM for the image, the 2 second video, the
extend, and the 3D model.

Expected: four `PASS` rows. A `FAIL` row means stop. The first run can take a long
time because models load from disk.

### Step 9 — auto-start, only if the owner asks

Skip this unless the owner asked for it.

Windows, one scheduled task at logon, only this app:

```
schtasks /Create /TN "Easy Studio" /SC ONLOGON /RL LIMITED /F /TR "cmd /c set EASY_STUDIO_NO_PAUSE=1&& C:\easy-studio\start_windows.bat"
```

`start_windows.bat` still waits for a key when a person double-clicks it. The task
above does not remove that.

Remove it with: `schtasks /Delete /TN "Easy Studio" /F`

Linux, a user service, not a system service:

```
mkdir -p ~/.config/systemd/user
```

Write `~/.config/systemd/user/easy-studio.service` with:

```
[Service]
WorkingDirectory=/home/THE_USER/easy-studio
ExecStart=/home/THE_USER/easy-studio/start_linux.sh
Restart=no

[Install]
WantedBy=default.target
```

Then `systemctl --user daemon-reload` and `systemctl --user enable --now easy-studio.service`.

Remove it with `systemctl --user disable --now easy-studio.service` and delete that file.
Do not disable any other service.

## Machine 2 — MacBook Pro M5 Max, 128 GB

Chat and the story model are the lowest priority. Do this after Machine 1 is serving
the app. Do not install this on the desktop, and do not touch other projects.

### Step M1 — who you are

```
whoami
scutil --get ComputerName
system_profiler SPHardwareDataType | egrep "Model Name|Chip|Memory"
```

Expected: a username, and a line that shows the M5 Max and about 128 GB.
Post the username on issue #1. That is one of the facts the build needs.

### Step M2 — LM Studio and the story model

1. Download LM Studio from https://lmstudio.ai and install it. If it is already installed, leave it.
2. In the search tab, paste `huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated-MTP-GGUF`.
3. Download the **Q8_0** file (about 38 GB).
4. If that file will not load, use the MLX build instead:
   `leonsarmiento/Huihui-Qwen3.6-35B-A3B-abliterated-6bit-XL-mlx` (about 28 GB).
5. Load the model. Open the system-prompt box. Paste the whole file
   `writing/game_writer_system_prompt.txt` from the Easy Studio folder.
   Copy it by USB or by the owner. Do not commit a changed copy.
6. The file says fictional adults and no real people. Do not edit it.

Check: ask the model, "What is your age rule, in one sentence?"

Expected: it says adult characters only, and it does not offer to write about minors
or real people. If it does, stop and report. Do not keep prompting it.

### Step M3 — reach the desktop app

On the desktop, read the LAN address printed by `start_windows.bat` or `start_linux.sh`.
Prefer an address that starts with `192.168.` or `10.`.

On the Mac:

```
bash setup/mac_reach_check.sh THE-DESKTOP-IP
```

Expected:

- `PASS` for port 8188 not answering
- `PASS` for port 7860 asking for a password (401), then `PASS` after the password

The script asks for the password and does not save it. If 8188 answers, stop.
ComfyUI is exposed.

Then open `http://THE-DESKTOP-IP:7860` in Safari or Chrome. Sign in. Open Setup.
Expected: the page loads, and the tools that have models show as ready.

## Machine 3 — Godot 4 on the MacBook

Do this after Machine 1 has made at least one character. The game scene itself is a
later pull request. This step only proves Godot opens an export.

1. Download Godot 4.3 or newer from https://godotengine.org . Use the standard
   macOS Apple Silicon build, not the .NET build. If Godot is already there, use it.
2. On the desktop, with the app running, export is a button in Game assets:
   **Export to Godot 4**. It writes a zip under `outputs/`. Do not commit the zip.
3. Copy the zip to the Mac by AirDrop or a USB stick. Unzip it.
4. Open Godot. Import. Pick that folder's `project.godot`.

Check: Godot's title shows the project, and the FileSystem dock contains
`res://assets/characters/`.

Expected: the project opens without an import error. You do not need to play a scene.
If Godot asks to convert the project, allow the conversion for this copy only.

Post `ES-SETUP-...` with pass or fail. Do not commit the project folder.

## If something does not match

| What you see | What to do |
|---|---|
| `nvidia-smi` is missing, or CUDA in PyTorch is `False` | Stop. Install the current NVIDIA driver, reboot, run preflight again. |
| Driver older than 570, or CUDA older than 12.8 | Stop. Same as above. Do not keep going with an old driver. |
| Less than 200 GB free | Stop. Free space on this drive only. Do not delete other projects. |
| A download stops or says rate limited | Run the same download command again. It resumes. For LTX only, the owner types `HF_TOKEN` in that window. |
| Hugging Face says 401 or 403 on a default file | Stop and report the file name. Default files are public. Do not invent a token for them. |
| Gated LTX file | The owner accepts the licence in the browser, then types the token. Do not save it. |
| Port 7860 refused on the Mac | Both machines on the same Wi-Fi. Private-network firewall rule only. The desktop window must still be open. |
| Port 8188 answers on the Mac | Stop. ComfyUI must stay on 127.0.0.1. Do not add a firewall allow for 8188. |
| Windows path too long | Stop and report the path. Do not set `core.longpaths` globally. |
| Antivirus locked a download | Stop and report the file. Do not disable antivirus. |
| Trainer PyTorch fails | Stop and report. The trainer script uses CUDA 12.8 wheels. |
| Self-test is not 482/482 | Stop and paste the failed check names. |
| Out of memory on the smoke test | Stop and report the step and the VRAM number. Do not change quality settings to hide it. |

## Photoreal weights (after the default install)

The default install already includes Z-Image Turbo (the realistic still) and Wan 2.2 image-to-video. The film look, the draft model, the video upscaler and the frame interpolation are a separate group. Do not download them until the default self-test has passed.

Windows:

```
.venv\Scripts\python install\download_models.py --comfy ComfyUI --what photoreal
```

Linux: the same command with `.venv/bin/python`.

Expected last line: `All model files are in place.` If a line says BAD, stop and report the file name. Do not invent another address.

| File | Size | What it is |
|---|---|---|
| `krea2_turbo_fp8_scaled.safetensors` | 13.1 GB | Film look (Krea 2). A 26.3 GB bf16 file exists on the same Hugging Face repo if the owner asks for it. |
| `qwen3vl_4b_fp8_scaled.safetensors` | 5.2 GB | Text encoder for the film look |
| `flux-2-klein-4b.safetensors` | 7.8 GB | Draft stills |
| `flux2-vae.safetensors` | 0.3 GB | Draft stills |
| `seedvr2_7b_sharp_fp16.safetensors` | 16.5 GB | Video upscale. Use the sharp 7B, not the 3B. |
| `seedvr2_ema_vae_fp16.safetensors` | 0.5 GB | Video upscale |
| `gimmvfi_r_arb_lpips_fp32.safetensors` | 0.1 GB | 16 fps to 30 fps |
| `gimmvfi_f_arb_lpips_fp32.safetensors` | 0.1 GB | 16 fps to 30 fps |

Z-Image Turbo and Wan 2.2 are already in the default groups `fast` and `video`. Skin LoRAs are optional and are added by hand in the LoRA library, one at a time, close-ups only. 18+ body-part LoRAs are added only from inside the 18+ section.

The model names the app uses are in `app/model_registry.py`. To try a different file without editing code, put `outputs/model_registry.json` on the desktop (that folder is not committed) and override a role's `id`, `workflow`, or `weights`. Do not put tokens in that file.

These roles are named in the registry and do not have a download line yet. Do not invent files for them: SCAIL-2 (`video_control`, backups Wan 2.2 Animate and Wan2.2-VACE-Fun), SVI 2.0 Pro and FLF2V with a color match (`video_long`), regional repair (`video_fix`), and the Lightning preview (`video_preview`). SeedVR2's recorded target is 1080p. GIMM-VFI's recorded target is 30 fps. The app sets that frame rate with ffmpeg until the GIMM node is installed. It does not claim the upscaler ran.

Token packs and paywalls are not downloaded and not built. Candy's shop screens stay in the evidence branch.

Node packs the video chain expects on the desktop, installed into this ComfyUI only:

- SeedVR2 (the sharp 7B weights above)
- GIMM-VFI
- ComfyUI Impact Pack, for the face and hand detailer

If a pack is missing, say so in the step report. Do not install packs into any other project.

## Rollback

Do this only if the owner asks to remove Easy Studio.

1. Close `start_windows.bat` and the ComfyUI window, or press Ctrl+C in `start_linux.sh`.
2. Windows: `powershell -File setup\firewall_windows.ps1 -Remove`
   Linux: `bash setup/firewall_linux.sh --remove`
3. Remove the auto-start task or user service from Step 9, if it was created.
4. Delete the Easy Studio folder. That removes ComfyUI, the virtualenvs, the models,
   and `outputs/` for this app only.
5. Do not uninstall Git, Python, FFmpeg, LM Studio, or Godot unless the owner asks.
   Other work may be using them.
6. Do not delete BlueNord or any folder outside Easy Studio.
