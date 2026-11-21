#!/bin/bash
# Runs INSIDE the freshly installed system during the install (curtin in-target). Writes config only: nothing here
# loads firewall rules into the installer's kernel or starts a service; they all take effect on first boot.
#   - SSH: key-only, admin user only, local port forwarding only (the Mac's tunnels)       (K-04, K-05)
#   - sudo (K-04): no blanket NOPASSWD. Without a password the admin may run only the kit's own root-owned helpers
#     and the exact Tailscale join/leave commands; full sudo needs the account password, which Ak sets once over SSH
#     with `turin-first-login` (the account is locked until then). The SSH key lives in Ak's 1Password.
#   - firewall: deny all incoming except SSH (+ mDNS) from private/link-local ranges and the tailscale0 interface.
#     No other port is open: the dashboard and every app listen on 127.0.0.1 and ride the SSH tunnel.   (K-05)
set -euo pipefail
CONF=/opt/turin/config/install.json
USER_NAME="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["username"])' "$CONF")"
[[ $USER_NAME =~ ^[a-z][a-z0-9-]{0,30}$ ]] || { echo "bad username in $CONF"; exit 1; }
install -d -m 0755 /var/lib/turin /var/log/turin
chmod -R a+rX /opt/turin/payload
for helper in /opt/turin/payload/bin/*; do install -m 0755 -o root -g root "$helper" "/usr/local/bin/$(basename "$helper")"; done

# ---- SSH (first file wins in sshd_config.d, so 10- comes before cloud-init's 50-)
install -d -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/10-turin.conf <<SSHD
# Candy server kit: key-only SSH for ${USER_NAME}; the Mac reaches the loopback services through LocalForward.
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers ${USER_NAME}
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding local
AllowStreamLocalForwarding no
GatewayPorts no
PermitTunnel no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 30
ClientAliveCountMax 4
SSHD
chmod 0644 /etc/ssh/sshd_config.d/10-turin.conf
install -d -m 0755 /run/sshd
ssh-keygen -A   # host keys may not exist yet inside the install target; sshd -t needs them (cloud-init may renew them)
sshd -t -f /etc/ssh/sshd_config

# ---- sudo
SUDOERS=/etc/sudoers.d/90-turin-admin
usermod -aG sudo "$USER_NAME"   # full sudo, with the password set at first login
install -d -m 0755 /etc/sudoers.d
{
  echo '# Candy server kit: password-less sudo ONLY for these root-owned helpers; everything else asks for the password.'
  echo 'Cmnd_Alias TURIN_HELPERS = /usr/local/bin/turin-health, /usr/local/bin/turin-burnin, /usr/local/bin/turin-llm-profile, /usr/local/bin/turin-enable-heavy-llms, /usr/local/bin/turin-set-password, /usr/local/bin/turin-desktop-restart, /usr/bin/tailscale up --accept-dns\=false --hostname\=epyc-studio, /usr/bin/tailscale down'
  printf '%s ALL=(root) NOPASSWD: TURIN_HELPERS\n' "$USER_NAME"
} > "$SUDOERS.tmp"
chmod 0440 "$SUDOERS.tmp"
visudo -cf "$SUDOERS.tmp"
mv -f "$SUDOERS.tmp" "$SUDOERS"

# ---- firewall: rules are written now and loaded by ufw.service on first boot. If ufw cannot run inside the install
# target, the install goes on and turin-provision.sh applies the same rules first thing on first boot.
if ! bash /opt/turin/payload/firewall_rules.sh; then
  echo 'firewall rules deferred to first boot'; touch /var/lib/turin/ufw-deferred
fi

# ---- first-boot units
cat > /etc/systemd/system/turin-status-web.service <<'UNIT'
[Unit]
Description=Candy server setup dashboard (read-only, 127.0.0.1:8099, reached over the SSH tunnel)
After=network.target
[Service]
ExecStart=/usr/bin/python3 /opt/turin/payload/turin-status-web.py --host 127.0.0.1 --port 8099
User=nobody
Group=nogroup
Restart=on-failure
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/turin-firstboot.service <<'UNIT'
[Unit]
Description=Candy server provisioning (offline from the store first, pinned online fallback, resumable)
Wants=network-online.target turin-status-web.service
After=network-online.target turin-status-web.service ufw.service
StartLimitIntervalSec=0
[Service]
Type=oneshot
ExecStart=/bin/bash /opt/turin/payload/turin-provision.sh
TimeoutStartSec=infinity
Restart=on-failure
RestartSec=60
[Install]
WantedBy=multi-user.target
UNIT
systemctl enable ufw ssh turin-status-web turin-firstboot
