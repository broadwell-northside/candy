#!/bin/bash
# Join THIS Mac to Ak's tailnet without touching its DNS (K-06). A DRY RUN unless --apply. Ak runs it himself.
#   bash server-kit/mac/tailscale_mac.sh            # show what it would do
#   bash server-kit/mac/tailscale_mac.sh --apply    # tailscale up --accept-dns=false
#   bash server-kit/mac/tailscale_mac.sh --undo --apply   # tailscale down (the app stays installed)
# It installs nothing, changes no firewall, DNS, VPN or system setting itself. Install the Tailscale app yourself
# (Mac App Store or tailscale.com); macOS asks you to approve its VPN configuration the first time.
set -euo pipefail
APPLY=0; UNDO=0
for a in "$@"; do case "$a" in --apply) APPLY=1;; --undo) UNDO=1;; *) echo "unknown option $a"; exit 2;; esac; done
TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
if [[ $UNDO == 1 ]]; then CMD=("$TS" down); else CMD=("$TS" up --accept-dns=false --accept-routes=false); fi
if [[ $APPLY == 0 ]]; then
  echo "DRY RUN - nothing is changed. With --apply it would run: ${CMD[*]}"
  [[ -x $TS ]] || echo "Note: the Tailscale app is not installed at /Applications/Tailscale.app (install it yourself first)."
  exit 0
fi
[[ $(uname -s) == Darwin ]] || { echo 'macOS only'; exit 1; }
[[ -x $TS ]] || { echo 'Install the Tailscale app first (Mac App Store or tailscale.com), then run this again.'; exit 1; }
"${CMD[@]}"
[[ $UNDO == 1 ]] || echo "This Mac is on the tailnet; its DNS was left alone (--accept-dns=false). Tailscale IP: $("$TS" ip -4 2>/dev/null | head -n1)"
