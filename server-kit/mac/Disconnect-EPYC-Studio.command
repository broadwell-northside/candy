#!/bin/bash
# Double-click on the Mac (Ak only). Closes the SSH tunnels to the server.
# Runs: python3 server-kit/mac/candy_link.py disconnect --apply
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/candy_link.py" disconnect --apply
[[ -t 0 ]] && read -r -p "Press Return to close. " _ || true
