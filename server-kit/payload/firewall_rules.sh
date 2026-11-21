#!/bin/bash
# The server's firewall (K-05), used by install_services.sh during the install and by turin-provision.sh if it had
# to be deferred. Deny every incoming connection except SSH (rate-limited) and mDNS from private and link-local
# addresses, and SSH on the tailscale0 interface. Tailscale needs no open port (it connects outward). Nothing else is open: the
# dashboard and every app listen on 127.0.0.1 and are reached through the SSH tunnel.
set -euo pipefail
ufw default deny incoming
ufw default allow outgoing
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16; do
  ufw limit proto tcp from "$net" to any port 22
  ufw allow proto udp from "$net" to any port 5353
done
for net in fe80::/10 fd00::/8; do
  ufw limit proto tcp from "$net" to any port 22
  ufw allow proto udp from "$net" to any port 5353
done
ufw allow in on tailscale0 to any port 22 proto tcp
python3 - /etc/ufw/ufw.conf <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
open(p, 'w').write(re.sub(r'(?m)^ENABLED=.*$', 'ENABLED=yes', s))
PY
