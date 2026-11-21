#!/usr/bin/env bash
# Open only Easy Studio's port on the home network. ComfyUI stays on this PC.
# Safe to run again. Does not enable a firewall that is off, and does not touch other rules.
# Usage: bash setup/firewall_linux.sh
#        bash setup/firewall_linux.sh --remove
set -euo pipefail
PORT="${EASY_STUDIO_PORT:-7860}"
if [[ "${1:-}" == "--remove" ]]; then
  if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Easy Studio"; then
    sudo ufw delete allow proto tcp from 192.168.0.0/16 to any port "$PORT" comment "Easy Studio" || true
    sudo ufw delete allow proto tcp from 10.0.0.0/8 to any port "$PORT" comment "Easy Studio" || true
  fi
  echo "Removed Easy Studio firewall notes if they were present. ComfyUI was not given a rule."
  exit 0
fi
echo "ComfyUI must stay on 127.0.0.1:8188. This script does not open 8188."
if ! command -v ufw >/dev/null 2>&1; then
  echo "MANUAL  ufw is not installed. Do not install a new firewall unless the owner asks."
  echo "Check: ss -ltnp | grep -E '7860|8188' || netstat -ltnp | grep -E '7860|8188'"
  echo "Expected: 8188 is 127.0.0.1 only. 7860 may be 0.0.0.0."
  exit 0
fi
if ! sudo ufw status | head -1 | grep -q "Status: active"; then
  echo "MANUAL  ufw is installed but off. This script will not turn it on."
  echo "Turning it on can cut off other access. Stop and report that the firewall is off."
  exit 0
fi
sudo ufw allow proto tcp from 192.168.0.0/16 to any port "$PORT" comment "Easy Studio"
sudo ufw allow proto tcp from 10.0.0.0/8 to any port "$PORT" comment "Easy Studio"
echo "PASS  private-network rule for TCP ${PORT} is present."
sudo ufw status | grep "$PORT" || true
echo "There must be no rule for 8188 from this script."
