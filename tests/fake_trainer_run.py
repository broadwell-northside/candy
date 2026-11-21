"""Stand-in for ai-toolkit's run.py in tests: reads the config, checks the dataset, prints tqdm-like progress
and writes a tiny LoRA .safetensors (or a Wan 2.2 high/low pair) where ai-toolkit would."""
import json
import os
import struct
import sys

cfg = json.load(open(sys.argv[1]))
proc = cfg["config"]["process"][0]
name = cfg["config"]["name"]
ds = proc["datasets"][0]["folder_path"]
pics = sorted(f for f in os.listdir(ds) if f.endswith(".png"))
caps = sorted(f for f in os.listdir(ds) if f.endswith(".txt"))
assert len(pics) == len(caps) >= 10, "dataset incomplete"
assert all("[trigger]" in open(os.path.join(ds, c)).read() for c in caps), "captions need [trigger]"
assert proc["train"]["disable_sampling"] is True
steps = 10
for i in range(1, steps + 1):
    sys.stdout.write(f"\r{name}: {i * 10}%|##| {i}/{steps} [00:01<00:00, loss=0.1]")
    sys.stdout.flush()
print()
out = os.path.join(proc["training_folder"], name)
os.makedirs(out, exist_ok=True)


def write(path, keys):
    hdr = {"__metadata__": {"es_trigger": proc["trigger_word"]}}
    off = 0
    for k in keys:
        hdr[k] = {"dtype": "F16", "shape": [2, 2], "data_offsets": [off, off + 8]}
        off += 8
    h = json.dumps(hdr).encode()
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(h)) + h + b"\0" * off)


keys = ["diffusion_model.blocks.0.self_attn.q.lora_A.weight", "diffusion_model.blocks.0.self_attn.q.lora_B.weight"]
if proc["network"].get("split_multistage_loras"):
    write(os.path.join(out, f"{name}_high_noise.safetensors"), keys)
    write(os.path.join(out, f"{name}_low_noise.safetensors"), keys)
    write(os.path.join(out, f"{name}_000000005_high_noise.safetensors"), keys)
else:
    write(os.path.join(out, f"{name}.safetensors"), ["transformer.single_blocks.0.lora_A.weight"])
    write(os.path.join(out, f"{name}_000000005.safetensors"), ["transformer.single_blocks.0.lora_A.weight"])
