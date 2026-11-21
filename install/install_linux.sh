#!/usr/bin/env bash
# Easy Studio installer for Linux (tested target: Ubuntu 24.04 + NVIDIA RTX PRO 6000 Blackwell).
# Usage:  bash install/install_linux.sh            (installs everything + downloads ~139 GB of models)
#         bash install/install_linux.sh nomodels   (skip the big downloads)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
COMFY="$ROOT/ComfyUI"
say() { printf "\n\033[1;36m== %s ==\033[0m\n" "$*"; }

say "Step 1/5: system tools (git, python, ffmpeg)"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update || echo "(apt update had a problem -- continuing)"
  sudo apt-get install -y git ffmpeg python3 python3-venv python3-pip curl \
    || echo "(apt install had a problem -- checking what is already there)"
else
  echo "Not an apt-based Linux. Please install git, ffmpeg, python3 (3.12 or 3.13) and python3-venv yourself."
fi
for t in git ffmpeg python3 curl; do
  command -v "$t" >/dev/null 2>&1 || { echo "MISSING: $t -- please install it and run this again."; exit 1; }
done
python3 -c "import venv" || { echo "MISSING: python3-venv"; exit 1; }
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "WARNING: 'nvidia-smi' not found. Install the NVIDIA driver first (Ubuntu: 'sudo ubuntu-drivers install', then reboot)."
else
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
fi

say "Step 2/5: ComfyUI (the engine)"
if [ ! -d "$COMFY/.git" ]; then
  git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFY"
else
  git -C "$COMFY" pull --ff-only || echo "(could not update ComfyUI; keeping current version)"
fi
[ -d "$COMFY/venv" ] || python3 -m venv "$COMFY/venv"
"$COMFY/venv/bin/python" -m pip install --upgrade pip wheel
# PyTorch with CUDA 13.0 (needed for Blackwell cards); falls back to CUDA 12.8.
"$COMFY/venv/bin/pip" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130 \
  || "$COMFY/venv/bin/pip" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
"$COMFY/venv/bin/pip" install -r "$COMFY/requirements.txt"
# Custom nodes: none are required -- Easy Studio's workflows only use built-in ComfyUI nodes.

say "Step 3/5: Easy Studio app"
[ -d "$ROOT/.venv" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"

say "Step 4/5: model files (~139 GB, resumable; re-run if it stops)"
df -h "$ROOT" | tail -1 | awk '{print "Free disk space here: "$4" (need about 150 GB)"}'
if [ "${1:-}" != "nomodels" ]; then
  "$ROOT/.venv/bin/python" "$ROOT/install/download_models.py" --comfy "$COMFY" --what all
else
  echo "Skipped. Later run: .venv/bin/python install/download_models.py --comfy ComfyUI --what all"
fi

say "Step 5/5: quick self-test (no GPU needed)"
"$ROOT/.venv/bin/python" "$ROOT/tests/run_tests.py" || echo "Self-test had a problem -- see above."
chmod +x "$ROOT/start_linux.sh"
say "Done! Start everything with:  ./start_linux.sh"
