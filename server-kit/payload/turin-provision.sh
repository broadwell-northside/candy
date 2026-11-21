#!/bin/bash
# First-boot provisioning for the Candy GPU server. Runs as root from turin-firstboot.service, only on the freshly
# installed server; restarts itself after a failure and picks up where it stopped (state files in /var/lib/turin).
# Order: apt from the store (pinned) -> kernel + NVIDIA driver + CUDA -> one reboot -> GPU check -> ComfyUI and
# llama.cpp from the store's source archives and wheels -> units -> models (store first, resumable download of
# anything missing) -> health report -> services.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run as root on the server'; exit 1; }
exec 9>/run/turin-provision.lock
flock -n 9 || exit 0
ROOT=/opt/turin
STATE=/var/lib/turin
mkdir -p "$STATE" /var/log/turin
exec > >(tee -a /var/log/turin/provision.log) 2>&1
phase() {
  python3 - "$1" "$2" <<'PY'
import json, os, sys, time
p = '/var/lib/turin/phase.json'; t = p + '.tmp'
open(t, 'w').write(json.dumps({'phase': sys.argv[1], 'message': sys.argv[2], 'updated_epoch': time.time()}))
os.chmod(t, 0o644); os.replace(t, p)
PY
}
trap 'phase error "Provisioning stopped; see /var/log/turin/provision.log. It retries by itself in 60 seconds."' ERR
export DEBIAN_FRONTEND=noninteractive
USER_NAME="$(python3 -c 'import json;print(json.load(open("/opt/turin/config/install.json"))["username"])')"
install -d -m 0755 /etc/issue.d
{ echo 'Candy server SSH host keys (compare with what the Mac shows on the first connection):'
  for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done; echo; } > /etc/issue.d/turin-ssh.issue || true
if [[ -f "$STATE/ufw-deferred" ]]; then
  phase firewall 'Applying the firewall rules the installer could not load.'
  bash "$ROOT/payload/firewall_rules.sh"
  ufw --force enable
  rm -f "$STATE/ufw-deferred"
fi

if [[ ! -f "$STATE/packages-installed" ]]; then
  phase packages 'Installing the pinned HWE kernel, NVIDIA 580 driver (signed prebuilt modules), CUDA 12.8 and tools from the store.'
  python3 "$ROOT/payload/apt_offline.py" install
  cat /proc/sys/kernel/random/boot_id > "$STATE/driver-install-boot"
  touch "$STATE/packages-installed"
fi
if [[ "$(cat "$STATE/driver-install-boot")" == "$(cat /proc/sys/kernel/random/boot_id)" ]]; then
  phase reboot 'Rebooting once into the new kernel with the NVIDIA modules.'
  systemctl reboot
  exit 0
fi

phase gpu-check 'Checking both RTX PRO 6000 Blackwell Max-Q cards, the driver and CUDA.'
modprobe nvidia
modinfo -F license nvidia | grep -qi 'MIT\|Dual' || { echo 'Not the open NVIDIA kernel module'; exit 1; }
nvidia-smi -L
python3 - <<'PY'
import subprocess
rows = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,power.limit,driver_version',
                                '--format=csv,noheader,nounits'], text=True).strip().splitlines()
assert len(rows) == 2, f'expected two GPUs, found {len(rows)}'
for row in rows:
    name, mem, power, ver = [x.strip() for x in row.split(',')]
    assert 'RTX PRO 6000' in name and 'Blackwell' in name, name
    assert 0 < float(power) <= 300.5, f'unexpected board power limit {power} W (Max-Q is 300 W)'
    assert float(mem) >= 89000, f'unexpected VRAM {mem} MiB; check ECC/MIG state'
    assert int(ver.split('.')[0]) >= 580, ver
    print('GPU ok:', row)
PY
nvidia-smi -pm 1
systemctl enable --now nvidia-persistenced || true

if ! id studio >/dev/null 2>&1; then useradd --system --create-home --home-dir /srv/ai --shell /usr/sbin/nologin studio; fi
install -d -o studio -g studio /srv/ai/models /srv/ai/ComfyUI /srv/ai/llama.cpp /srv/ai/app /srv/ai/.cache
chown -R studio:studio /srv/ai/models
chmod 0711 /srv/ai; chmod 0755 /srv/ai/models   # traverse-only for the read-only dashboard (user nobody)

if [[ ! -f "$STATE/remote-installed" ]]; then
  phase remote 'Setting up the headless remote desktop (VNC on 127.0.0.1, over the SSH tunnel only).'
  bash "$ROOT/payload/setup_remote.sh"
  touch "$STATE/remote-installed"
fi
if [[ ! -f "$STATE/software-installed" ]]; then
  phase software 'Building ComfyUI and llama.cpp at their pinned commits from the store (CUDA build takes a while).'
  python3 "$ROOT/payload/setup_ai.py"
  touch "$STATE/software-installed"
fi
python3 "$ROOT/payload/setup_units.py"
systemctl daemon-reload
phase health 'Recording the hardware health report (real readings, nothing assumed).'
python3 "$ROOT/payload/turin-health.py" --write "$STATE/health.json" || true
# Models: whatever the store import did not bring is downloaded (resumable, SHA256-checked) by turin-models.
systemctl enable --now turin-models turin-comfy0 turin-director
systemctl enable --now turin-comfy1 || true
if [[ -f /srv/ai/app/.bundle-installed ]]; then systemctl enable --now turin-easy-studio; fi
systemctl enable turin-desktop || true
phase core-online "Core services started for ${USER_NAME}. Each one reports its own health; nothing is shown as ready on a timer."
systemctl disable turin-firstboot
