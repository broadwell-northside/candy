#!/bin/bash
# Double-click on the Mac (Ak only). Opens the SSH tunnels to the server and the dashboard and apps.
# Runs: python3 server-kit/mac/candy_link.py connect --apply
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/candy_link.py" connect --apply
[[ -t 0 ]] && read -r -p "Press Return to close. " _ || true
