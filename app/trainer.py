"""'Train my character': teach a LoRA what ONE saved character looks like, so she looks the same in every
picture / video. Uses ostris' ai-toolkit (MIT licence), installed separately into trainer/ai-toolkit
by install/install_trainer.sh (or .bat).

DELIBERATE LIMIT: training pictures can only be pictures Easy Studio made of a saved character, or your own
drawn / 3D-rendered fictional character art uploaded with the "my fictional character" tick box. There is no
way to train on photos of real people -- including yourself. That is on purpose: a LoRA of a real person plus
the 18+ section would mean nude pictures of a real person, which Easy Studio does not do.
Every training picture must also pass the automatic age check (flagged pictures are never used).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

# base id -> (label, ai-toolkit model block, steps, rank, LoRA family, resolution list)
BASES = {
    "photo": dict(label="Realistic pictures (Chroma1-HD)", family="flux", steps=2000, rank=16, res=[512, 768, 1024],
                  model={"name_or_path": "lodestones/Chroma1-HD", "arch": "chroma", "quantize": True},
                  noise="flowmatch", tested=False),
    "fast": dict(label="Fast pictures (Z-Image Turbo)", family="zimage", steps=1500, rank=16, res=[512, 768, 1024],
                 model={"name_or_path": "Tongyi-MAI/Z-Image-Turbo", "arch": "zimage", "quantize": True,
                        "assistant_lora_path": "ostris/zimage_turbo_training_adapter/zimage_turbo_training_adapter_v2.safetensors"},
                 noise="flowmatch", tested=False),
    "anime": dict(label="Anime pictures (NoobAI-XL)", family="sdxl", steps=2000, rank=16, res=[768, 1024],
                  model={"name_or_path": "Laxhar/noobai-XL-1.1", "arch": "sdxl", "is_xl": True},
                  noise="ddpm", tested=False),
    "video": dict(label="Videos (Wan 2.2 14B)", family="wan14b", steps=2000, rank=32, res=[512, 768],
                  model={"name_or_path": "ai-toolkit/Wan2.2-T2V-A14B-Diffusers-bf16", "arch": "wan22_14b", "quantize": True,
                         "qtype": "uint4|ostris/accuracy_recovery_adapters/wan22_14b_t2i_torchao_uint4.safetensors",
                         "quantize_te": True, "qtype_te": "qfloat8", "low_vram": True,
                         "model_kwargs": {"train_high_noise": True, "train_low_noise": True}},
                  noise="flowmatch", tested=False, extra_train={"timestep_type": "linear", "switch_boundary_every": 10,
                                                                 "cache_text_embeddings": True}),
}
MIN_PICTURES, MAX_PICTURES = 10, 60

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOCK = os.path.join(ROOT, "config", "trainer_bases_lock.json")
LOCAL_BASES = ("fast", "photo")   # the two bases that have a download group on the Models page: they train from this computer's files
GROUPS = {"fast": "trainer-fast", "photo": "trainer-photo"}
GROUP_LABEL = {"fast": "Trainer base for Fast pictures (Z-Image Turbo)", "photo": "Trainer base for Realistic pictures (Chroma1-HD)"}  # as the Models page shows them


class TrainerBaseMissing(RuntimeError):
    """A base the trainer would have had to fetch from the internet. The message says what to press, in plain words."""


def _test_run():
    return os.environ.get("EASY_STUDIO_TEST_RUN") == "1"


def models_root():
    return os.path.join(os.environ.get("COMFY_DIR") or os.path.join(ROOT, "ComfyUI"), "models")


def base_dir(base_id):
    return os.path.join(models_root(), "easy_studio", "trainer", base_id)


def base_rows(base_id):
    try:
        with open(LOCK, encoding="utf-8") as f:
            return [r for r in json.load(f)["rows"] if r.get("base") == base_id]
    except (OSError, ValueError):
        return []


def base_status(base_id):
    """(ready, missing names): every file of the base's lock is on this computer at its pinned size."""
    rows = base_rows(base_id)
    missing = []
    for r in rows:
        path = os.path.join(models_root(), r["folder"], r["name"])
        try:
            if os.path.getsize(path) != r["size"]:
                missing.append(r["name"])
        except OSError:
            missing.append(r["name"])
    return bool(rows) and not missing, missing

# the shots the dataset builder makes from the portrait: (what changes, Qwen-edit instruction, caption words)
DATASET_SHOTS = [
    ("angle", "Show the same person from a three-quarter left view, eye-level, upper body.", "three-quarter view, upper body"),
    ("angle", "Show the same person from a three-quarter right view, eye-level, upper body.", "three-quarter view, upper body"),
    ("angle", "Show the same person in left side profile view, head and shoulders.", "side profile, head and shoulders"),
    ("angle", "Show the same person seen slightly from above, looking up at the camera.", "high angle, looking up"),
    ("angle", "Show the same person seen slightly from below.", "low angle"),
    ("frame", "Show the same person as a close-up portrait of the face.", "close-up portrait"),
    ("frame", "Show the same person as a full-body shot, standing.", "full body, standing"),
    ("frame", "Show the same person sitting on a chair, full body.", "sitting on a chair, full body"),
    ("expr", "Change only the facial expression to a big happy smile.", "smiling"),
    ("expr", "Change only the facial expression to laughing.", "laughing"),
    ("expr", "Change only the facial expression to serious and calm.", "serious expression"),
    ("expr", "Change only the facial expression to surprised.", "surprised expression"),
    ("outfit", "Change the person's clothing to: blue jeans and a plain white t-shirt.", "wearing jeans and a white t-shirt"),
    ("outfit", "Change the person's clothing to: an elegant black evening dress.", "wearing a black evening dress"),
    ("outfit", "Change the person's clothing to: a grey hoodie and track pants.", "wearing a grey hoodie"),
    ("outfit", "Change the person's clothing to: a red bikini.", "wearing a red bikini"),
    ("outfit", "Change the person's clothing to: a black leather jacket over a dark top.", "wearing a leather jacket"),
    ("scene", "Change the background to a sunny beach. Relight the person to match.", "on a sunny beach"),
    ("scene", "Change the background to a cosy cafe interior. Relight the person to match.", "in a cafe"),
    ("scene", "Change the background to a city street at night with neon signs. Relight the person to match.", "city street at night, neon light"),
    ("scene", "Change the background to a forest in soft daylight. Relight the person to match.", "in a forest"),
    ("light", "Relight the person with dramatic side lighting and deep shadows.", "dramatic side lighting"),
    ("light", "Relight the person with warm golden-hour sunlight.", "golden hour light"),
    ("light", "Relight the person with cool blue moonlight.", "moonlight"),
]
STYLE_WORD = {"photo": "photo", "anime": "anime illustration", "render3d": "3d render", "painted": "digital painting"}


def make_trigger(name):
    """A short, rare word for the character: letters of her name + 'zx' + digit (e.g. 'mirazx7')."""
    base = re.sub(r"[^a-z]", "", (name or "char").lower())[:6] or "char"
    return f"{base}zx{sum(map(ord, base)) % 10}"


def caption(trigger, style, words):
    """Captions describe only what CHANGES (angle, clothes, place, light). What stays the same -- face,
    hair, body -- is left out on purpose, so the LoRA learns it belongs to the trigger word."""
    return ", ".join(x for x in ["[trigger]", STYLE_WORD.get(style, "photo"), words] if x)


def trainer_paths(root):
    d = os.environ.get("EASY_STUDIO_TRAINER_DIR") or os.path.join(root, "trainer", "ai-toolkit")
    py = os.environ.get("EASY_STUDIO_TRAINER_PYTHON")
    if not py:
        for cand in (os.path.join(d, "venv", "bin", "python"), os.path.join(d, "venv", "Scripts", "python.exe")):
            if os.path.exists(cand):
                py = cand
                break
    return d, py


def installed(root):
    d, py = trainer_paths(root)
    return bool(py) and os.path.exists(os.path.join(d, "run.py"))


def training_device():
    """Where the trainer runs on this machine: Apple's GPU on a Mac profile, the first NVIDIA card otherwise."""
    import machine_profiles
    return "mps" if machine_profiles.active().get("device") == "mps" else "cuda:0"


def resolve_model(base_id):
    """The model block for ai-toolkit with this computer's own files in place of the Hugging Face names, so nothing is fetched at run
    time. A base that is not all here is refused with a plain message. (In a test run the stand-in trainer never opens it, so the
    names stay as they were.)"""
    model = dict(BASES[base_id]["model"])
    if base_id in LOCAL_BASES:
        ready, missing = base_status(base_id)
        if ready:
            model["name_or_path"] = base_dir(base_id)
            if "assistant_lora_path" in model:
                model["assistant_lora_path"] = os.path.join(base_dir(base_id), "adapter", "zimage_turbo_training_adapter_v2.safetensors")
            return model
        if _test_run():
            return model
        shown = GROUP_LABEL[base_id]
        some = "" if len(missing) == len(base_rows(base_id)) else " (%d of its files are missing)" % len(missing)
        raise TrainerBaseMissing("The trainer's base for %s is not on this computer%s. Open Setup, then Models, press Download for "
                                 "\"%s\", and try again. The trainer never fetches it by itself."
                                 % (BASES[base_id]["label"], some, shown))
    if _test_run():
        return model
    raise TrainerBaseMissing("Training on %s is not offered yet: its base model has no download here, and the trainer never fetches "
                             "one by itself. Use Fast pictures or Realistic pictures." % BASES[base_id]["label"])


def write_config(job_dir, name, base_id, trigger, dataset_dir, steps=None, rank=None, device=None):
    b = BASES[base_id]
    model = resolve_model(base_id)
    train = {"batch_size": 1, "steps": int(steps or b["steps"]), "gradient_accumulation": 1, "train_unet": True,
             "train_text_encoder": False, "gradient_checkpointing": True, "noise_scheduler": b["noise"],
             "optimizer": "adamw8bit", "lr": 1e-4, "dtype": "bf16", "disable_sampling": True}
    train.update(b.get("extra_train", {}))
    ds = {"folder_path": dataset_dir, "caption_ext": "txt", "caption_dropout_rate": 0.05, "cache_latents_to_disk": True,
          "resolution": b["res"]}
    if base_id == "video":
        ds["num_frames"] = 1
    r = int(rank or b["rank"])
    cfg = {"job": "extension", "config": {"name": name, "process": [{
        "type": "sd_trainer", "training_folder": os.path.join(job_dir, "output"), "device": device or training_device(),
        "trigger_word": trigger,
        "network": {"type": "lora", "linear": r, "linear_alpha": r,
                    **({"split_multistage_loras": True} if base_id == "video" else {})},
        "save": {"dtype": "float16", "save_every": 500, "max_step_saves_to_keep": 2, "push_to_hub": False},
        "datasets": [ds], "train": train, "model": model}]},
        "meta": {"name": name, "version": "1.0", "made_by": "Easy Studio",
                 "inference_lora_is_not_a_checkpoint": True, "publish_to_civitai": False}}
    path = os.path.join(job_dir, "config.json")  # ai-toolkit reads .json configs as well as .yaml
    with open(path, "w") as f:
        json.dump(cfg, f, indent=1)
    return path


STEP_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*\[")

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
def no_network_profile(tmp):
    """Everything on the network is denied (IP, loopback, name lookup, every other program's local socket). The only thing allowed back is
    a Unix socket inside the trainer's own private temp folder, which its data-loader workers may use and which cannot leave it."""
    t = os.path.realpath(tmp).replace("\\", "\\\\").replace('"', '\\"')
    return ('(version 1)(allow default)(deny network*)'
            '(allow network* (local unix-socket (subpath "%s")))(allow network* (remote unix-socket (subpath "%s")))' % (t, t))


# Never passed to the trainer: a stored login or key, or the address of an agent that holds one, must not reach it. These names, and any variable named like a key, token or secret.
SECRET_ENV = ("HF_ENDPOINT", "SSH_AUTH_SOCK", "DOCKER_HOST", "GPG_AGENT_INFO", "OP_SOCKET_PATH")
SECRET_PART = re.compile(r"(API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)


def offline_env(trainer_dir, base=None):
    """The environment the trainer runs in: offline by every switch the libraries have, a private empty Hugging Face home (no stored
    login), no key, no telemetry."""
    env = {k: v for k, v in (base if base is not None else os.environ).items() if k not in SECRET_ENV and not SECRET_PART.search(k)}
    home = os.path.join(trainer_dir, "hf_home")
    os.makedirs(home, exist_ok=True)
    tmp = private_tmp(trainer_dir)
    env.update(TMPDIR=tmp, TEMP=tmp, TMP=tmp)
    env.update(PYTHONUNBUFFERED="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1", DIFFUSERS_OFFLINE="1",
               HF_HOME=home, HF_HUB_CACHE=os.path.join(home, "hub"), HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_ENABLE_HF_TRANSFER="0",
               DO_NOT_TRACK="1", WANDB_MODE="disabled", WANDB_DISABLED="true", ANONYMIZED_TELEMETRY="False", NO_ALBUMENTATIONS_UPDATE="1")
    return env


def private_tmp(trainer_dir):
    t = os.path.realpath(os.path.join(trainer_dir, "tmp"))
    os.makedirs(t, mode=0o700, exist_ok=True)
    return t


def network_off(trainer_dir):
    """On a Mac the trainer also runs with the network denied by the system (sandbox-exec), so a library that ignores the offline
    switches still cannot reach anything. Elsewhere only the switches above apply."""
    if sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC):
        return [SANDBOX_EXEC, "-p", no_network_profile(private_tmp(trainer_dir))]
    return []


def run_training(root, config_path, on_progress, should_stop, log_path):
    d, py = trainer_paths(root)
    if not py:
        raise RuntimeError("The trainer isn't installed yet. Run install/install_trainer.sh (Windows: install_trainer.bat).")
    env = offline_env(d)
    with open(log_path, "w") as log:
        p = subprocess.Popen(network_off(d) + [py, "run.py", config_path], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=env, text=True, bufsize=1, errors="replace")
        buf = ""
        try:
            while True:
                ch = p.stdout.read(1)
                if not ch:
                    break
                log.write(ch)
                if ch in "\r\n":
                    m = STEP_RE.search(buf)
                    if m and int(m.group(2)) > 0:
                        on_progress(int(m.group(1)) / int(m.group(2)), f"Training: step {m.group(1)} of {m.group(2)}")
                    buf = ""
                    if should_stop():
                        p.terminate()
                        break
                else:
                    buf = buf[-500:] + ch
        finally:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
    if should_stop():
        return None
    if p.returncode != 0:
        tail = open(log_path, errors="replace").read()[-1500:]
        raise RuntimeError("Training stopped with an error. Last lines of the log:\n" + tail)
    return True


def find_outputs(job_dir, name):
    """Final LoRA file(s): name.safetensors, or a high/low-noise pair for Wan 2.2 14B."""
    out = os.path.join(job_dir, "output", name)
    files = sorted(f for f in os.listdir(out) if f.endswith(".safetensors")) if os.path.isdir(out) else []
    # The final files are exactly <name>.safetensors or <name>_high_noise / _low_noise. A step checkpoint has
    # a number between the name and the half. The run name itself can end in a time stamp (_194116), which
    # an unanchored "_<6 digits>" test mistook for a step number and dropped a half of the pair.
    final = [f for f in files if re.fullmatch(re.escape(name) + r"(_high_noise|_low_noise)?\.safetensors", f)]
    if not final:
        final = [f for f in files if not re.search(r"_\d{6,}(_high_noise|_low_noise)?\.safetensors$", f)]
    pick = final or files[-1:]
    pair = {}
    for f in pick:
        if "high_noise" in f:
            pair["high_noise"] = os.path.join(out, f)
        elif "low_noise" in f:
            pair["low_noise"] = os.path.join(out, f)
    if pair:
        if len(pair) != 2:
            raise ValueError("Training made only one half of the Wan 2.2 high/low pair, so it was not added. "
                             "A 14B LoRA is only used as a matching pair.")
        return pair
    return {"single": os.path.join(out, pick[0])} if pick else {}
