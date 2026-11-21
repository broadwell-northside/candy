#!/usr/bin/env bash
# Installs the character trainer (ostris/ai-toolkit, MIT licence) into trainer/ai-toolkit with its own Python, for a Linux PC with an
# NVIDIA card. On a Mac use install/install_trainer_mac.sh. Run once:  bash install/install_trainer.sh   (about 10 GB incl. torch)
#
# It takes ai-toolkit at the exact commit in config/trainer_pin.json (never "latest"), checks the two requirements files by SHA-256,
# and stops at the first thing that does not match. It downloads no model: the trainer's bases come from Setup, Models, and the trainer
# runs offline.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
T="${EASY_STUDIO_TRAINER_DIR:-$ROOT/trainer/ai-toolkit}"
REPO="https://github.com/ostris/ai-toolkit.git"
COMMIT="73c84b091dd0f5647fc6a4b59122a2efc1c8147b"
REQ_SHA="6264997796f6a6da55a3b815481cc3cea63a169b01ca55c8b6ee417367b3f5ea"
REQ_BASE_SHA="9e99c8c5dbe8a8b45dd847efbf504db4b8d409e49b291c32ce23835b04471367"
mkdir -p "$(dirname "$T")"
if [ ! -d "$T/.git" ]; then
  git clone --no-checkout "$REPO" "$T"
fi
git -C "$T" fetch --quiet origin "$COMMIT" || git -C "$T" fetch --quiet origin
git -C "$T" checkout --quiet --detach "$COMMIT"
if [ "$(git -C "$T" rev-parse HEAD)" != "$COMMIT" ]; then echo "Stopped: ai-toolkit is not at the pinned commit."; exit 1; fi
if [ -n "$(git -C "$T" status --porcelain --untracked-files=no)" ]; then echo "Stopped: files of ai-toolkit were changed here."; exit 1; fi
if [ "$(sha256sum "$T/requirements.txt" | cut -d' ' -f1)" != "$REQ_SHA" ] || \
   [ "$(sha256sum "$T/requirements_base.txt" | cut -d' ' -f1)" != "$REQ_BASE_SHA" ]; then
  echo "Stopped: the requirements files are not the ones that were checked."; exit 1
fi
[ -d "$T/venv" ] || python3 -m venv "$T/venv"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1
"$T/venv/bin/python" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
"$T/venv/bin/python" -m pip install -r "$T/requirements.txt"
echo
echo "Trainer installed at the pinned version. Restart Easy Studio; in Setup, Models, download the trainer base you need."
