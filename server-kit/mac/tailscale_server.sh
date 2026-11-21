#!/bin/bash
# Join the SERVER to Ak's tailnet, over the wired-LAN SSH connection. A DRY RUN unless --apply. Ak runs it himself.
#   bash server-kit/mac/tailscale_server.sh                 # show what it would do
#   bash server-kit/mac/tailscale_server.sh --apply         # prints a login link: open it on the Mac and sign in
#   bash server-kit/mac/tailscale_server.sh --undo --apply  # tailscale down on the server
# The server keeps its own DNS (--accept-dns=false) and advertises nothing. No auth key is used or stored.
# Afterwards, add the printed Tailscale IP to the link config:
#   python3 server-kit/mac/candy_link.py setup --tailscale-ip 100.x.y.z --apply
set -euo pipefail
APPLY=0; UNDO=0
for a in "$@"; do case "$a" in --apply) APPLY=1;; --undo) UNDO=1;; *) echo "unknown option $a"; exit 2;; esac; done
CFG="$HOME/.candy-server-kit/ssh_config"
if [[ $UNDO == 1 ]]; then REMOTE='sudo tailscale down'; else REMOTE='sudo tailscale up --accept-dns=false --hostname=epyc-studio && tailscale ip -4 | head -n1'; fi
if [[ $APPLY == 0 ]]; then
  echo "DRY RUN - nothing is changed. With --apply it would run: ssh -F $CFG -t epyc-studio '$REMOTE'"
  exit 0
fi
[[ -f $CFG ]] || { echo 'Run: python3 server-kit/mac/candy_link.py setup --apply   first.'; exit 1; }
ssh -F "$CFG" -t epyc-studio "$REMOTE"
