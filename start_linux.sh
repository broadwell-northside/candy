#!/usr/bin/env bash
# One click: starts ComfyUI (engine, private to this PC) + Easy Studio (the app, open to your home network).
cd "$(dirname "$0")"
ROOT="$(pwd)"
export COMFY_URL="http://127.0.0.1:8188"
export COMFY_DIR="$ROOT/ComfyUI"            # lets Easy Studio manage the LoRA folder
export COMFY_PYTHON="$ROOT/ComfyUI/venv/bin/python"  # runs the age check
export EASY_STUDIO_HOST="${EASY_STUDIO_HOST:-0.0.0.0}"
export EASY_STUDIO_PORT="${EASY_STUDIO_PORT:-7860}"
mkdir -p "$ROOT/outputs"
echo "Starting ComfyUI ... (log: outputs/comfyui.log)"
"$ROOT/ComfyUI/venv/bin/python" "$ROOT/ComfyUI/main.py" --listen 127.0.0.1 --port 8188 \
  > "$ROOT/outputs/comfyui.log" 2>&1 &
COMFY_PID=$!
trap 'echo; echo "Stopping ComfyUI"; kill $COMFY_PID 2>/dev/null' EXIT INT TERM
for i in $(seq 1 120); do
  curl -s http://127.0.0.1:8188/system_stats >/dev/null && break
  kill -0 $COMFY_PID 2>/dev/null || { echo "ComfyUI crashed. Last lines of the log:"; tail -20 "$ROOT/outputs/comfyui.log"; exit 1; }
  sleep 1
done
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "=============================================================="
echo " Easy Studio is starting."
echo "   On this PC:        http://127.0.0.1:${EASY_STUDIO_PORT}"
echo "   From your MacBook: http://${IP:-THIS-PC-IP}:${EASY_STUDIO_PORT}"
echo " Other devices will be asked for a password: it is printed below and saved in outputs/password.txt"
echo " Close this window (or press Ctrl+C) to stop everything."
echo "=============================================================="
"$ROOT/.venv/bin/python" "$ROOT/app/server.py"
