#!/usr/bin/env bash
# Run on the MacBook. Checks that Easy Studio answers and ComfyUI does not.
# Usage: bash setup/mac_reach_check.sh 192.168.1.50
# The password is typed at the prompt. It is not saved and not printed.
set -euo pipefail
IP="${1:-}"
PORT="${EASY_STUDIO_PORT:-7860}"
if [[ -z "$IP" ]]; then
  echo "Usage: bash setup/mac_reach_check.sh DESKTOP-LAN-IP"
  exit 2
fi
echo "Check 1: ComfyUI must NOT be reachable from this Mac."
if curl --connect-timeout 5 -sS "http://${IP}:8188/system_stats" >/dev/null; then
  echo "FAIL  http://${IP}:8188 answered. ComfyUI is exposed. Stop and report."
  exit 1
else
  echo "PASS  port 8188 did not return a page (connection failed or timed out)."
fi
echo "Check 2: Easy Studio should ask for a password, or answer if the password is off."
code=$(curl --connect-timeout 8 -s -o /tmp/es_mac_body.txt -w "%{http_code}" "http://${IP}:${PORT}/api/status" || true)
echo "Status without a password: ${code}"
if [[ "$code" == "200" ]]; then
  echo "PASS  the app answered without a password. Confirm the owner meant for that."
  exit 0
fi
if [[ "$code" != "401" ]]; then
  echo "FAIL  expected 401 or 200 from http://${IP}:${PORT}/api/status, got ${code:-none}."
  exit 1
fi
echo "PASS  the app asked for a password (401)."
read -r -s -p "Type the app password (it will not be shown): " PW
echo
code2=$(curl --connect-timeout 8 -s -o /tmp/es_mac_body.txt -w "%{http_code}" -u "mac:${PW}" "http://${IP}:${PORT}/api/status" || true)
unset PW
if [[ "$code2" == "200" ]]; then
  echo "PASS  the MacBook reached Easy Studio."
  exit 0
fi
echo "FAIL  password was not accepted (HTTP ${code2:-none}). Stop and report. Do not write the password down in git."
exit 1
