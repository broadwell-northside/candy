#!/bin/bash
# Headless remote desktop for the server (XFCE + TigerVNC on 127.0.0.1:5900). The Mac reaches it only through the
# SSH tunnel (Mac 127.0.0.1:15900 -> server 127.0.0.1:5900). The packages come from the pinned apt set; the firewall
# is set once in install_services.sh and opens nothing for VNC. Tailscale is installed (pinned) but NOT joined here:
# joining is Ak's own step, from the Mac (server-kit/mac/tailscale_server.sh), with --accept-dns=false.
set -euo pipefail
USER_NAME="$(python3 -c 'import json;print(json.load(open("/opt/turin/config/install.json"))["username"])')"
[[ $USER_NAME =~ ^[a-z][a-z0-9-]{0,30}$ ]] || exit 1
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
install -d -m 0700 -o "$USER_NAME" -g "$USER_NAME" "$USER_HOME/.vnc"
cat > "$USER_HOME/.vnc/xstartup" <<'START'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec dbus-run-session -- startxfce4
START
chown "$USER_NAME:$USER_NAME" "$USER_HOME/.vnc/xstartup"
chmod 0700 "$USER_HOME/.vnc/xstartup"
cat > /etc/systemd/system/turin-desktop.service <<UNIT
[Unit]
Description=Password-protected headless XFCE desktop (127.0.0.1:5900, SSH tunnel only)
After=network.target
ConditionPathExists=$USER_HOME/.vnc/passwd
[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$USER_HOME
Environment=HOME=$USER_HOME
ExecStart=/usr/bin/tigervncserver :1 -fg -localhost yes -rfbport 5900 -SecurityTypes VncAuth -PasswordFile $USER_HOME/.vnc/passwd -geometry 1920x1080 -depth 24 -xstartup $USER_HOME/.vnc/xstartup
ExecStop=-/usr/bin/tigervncserver -kill :1
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
# The desktop starts once a VNC password exists; it is chosen over SSH with `turin-first-login`, never shipped.
