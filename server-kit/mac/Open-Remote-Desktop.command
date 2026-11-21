#!/bin/bash
# Double-click on the Mac (Ak only). Opens the server's desktop in macOS Screen Sharing (sets the desktop password the first time).
# Runs: python3 server-kit/mac/candy_link.py desktop --apply
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/candy_link.py" desktop --apply
[[ -t 0 ]] && read -r -p "Press Return to close. " _ || true
