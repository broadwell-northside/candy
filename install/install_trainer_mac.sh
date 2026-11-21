#!/usr/bin/env bash
# Installs the character trainer (ostris/ai-toolkit, MIT licence) for this Mac, at the exact version in config/trainer_pin.json.
# Ak runs it once, by hand:  bash install/install_trainer_mac.sh
#
# What it does, in this order, and stops at the first thing that does not match:
#   1. takes ai-toolkit at the pinned commit (never "latest"; an existing copy is moved to that commit, never pulled);
#   2. checks the SHA-256 of the two requirements files against the pinned ones;
#   3. makes its own Python environment and installs torch at the versions in the pin, then the requirements.
# It downloads no model. The trainer's base models come from the Models page (Setup), one group each, and the trainer then runs
# offline: no Hugging Face fetch, no key, and on a Mac with the network denied by the system.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
RT="${CANDY_RUNTIME:-$HOME/candy/runtime}"
T="${EASY_STUDIO_TRAINER_DIR:-$RT/trainer/ai-toolkit}"
PY="${PYTHON:-python3.12}"
command -v "$PY" >/dev/null 2>&1 || PY=python3

# The pin. config/trainer_pin.json holds the same values; a test keeps the two equal.
REPO="https://github.com/ostris/ai-toolkit.git"
COMMIT="73c84b091dd0f5647fc6a4b59122a2efc1c8147b"
REQ_SHA="6264997796f6a6da55a3b815481cc3cea63a169b01ca55c8b6ee417367b3f5ea"
REQ_BASE_SHA="9e99c8c5dbe8a8b45dd847efbf504db4b8d409e49b291c32ce23835b04471367"
TORCH="torch==2.15.0 torchvision==0.29.2 torchaudio==2.11.1"

echo "Trainer folder: $T"
df -h "$HOME" | tail -1 | awk '{print "Free on this Mac: " $4}'
mkdir -p "$(dirname "$T")"
if [ ! -d "$T/.git" ]; then
  git clone --no-checkout "$REPO" "$T"
fi
git -C "$T" fetch --quiet origin "$COMMIT" || git -C "$T" fetch --quiet origin
git -C "$T" checkout --quiet --detach "$COMMIT"
HEAD_NOW="$(git -C "$T" rev-parse HEAD)"
if [ "$HEAD_NOW" != "$COMMIT" ]; then
  echo "Stopped: ai-toolkit is at $HEAD_NOW, not the pinned $COMMIT."; exit 1
fi
if [ -n "$(git -C "$T" status --porcelain --untracked-files=no)" ]; then
  echo "Stopped: files of ai-toolkit were changed here. Remove $T and run this again."; exit 1
fi
if [ "$(shasum -a 256 "$T/requirements.txt" | cut -d' ' -f1)" != "$REQ_SHA" ] || \
   [ "$(shasum -a 256 "$T/requirements_base.txt" | cut -d' ' -f1)" != "$REQ_BASE_SHA" ]; then
  echo "Stopped: the requirements files are not the ones that were checked."; exit 1
fi
[ -d "$T/venv" ] || "$PY" -m venv "$T/venv"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1
"$T/venv/bin/python" -m pip install $TORCH
"$T/venv/bin/python" -m pip install -r "$T/requirements.txt"
"$T/venv/bin/python" - <<'PYCHECK'
import torch
print("torch", torch.__version__, "| Apple GPU (mps) available:", torch.backends.mps.is_available())
PYCHECK
echo
echo "The trainer is installed at the pinned version. Restart Easy Studio, then in Setup, Models: download the trainer base you need,"
echo "and press Test the trainer. The trainer test is the go or no-go; nothing has trained on this Mac yet."
