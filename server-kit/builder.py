#!/usr/bin/env python3
"""Build the master-USB installer files. Never touches a disk; everything lands in server-kit/build/.

    python3 server-kit/builder.py --dry-run                 # check config + lock, print the plan, write nothing
    python3 server-kit/builder.py                           # official ISO (SHA256-checked) -> build/boot-overlay + usb-plan.json
    python3 server-kit/builder.py --iso-out                 # plan B: also a remastered ISO for BMC virtual media (needs xorriso)

Inputs: config/install.json (Ak's answers, from mac/guided_configure.py), config/kit.json (pins), the lead's model lock
(config/server_model_lock.json at the repo root) and the public half of Ak's SSH key. Output is read by
usb/write_master_usb.py and usb/stage_store.py.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

KIT = pathlib.Path(__file__).resolve().parent
REPO = KIT.parent
sys.path.insert(0, str(KIT))
from kitlib import lock as locklib  # noqa: E402

BUILD = KIT / 'build'
HEX40 = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
DISK_MODES = {'auto_single_blank_nvme': '--select-blank-nvme', 'exact_serial': '--exact-serial'}
PLACEHOLDER_SERIAL = 'TURIN-DISK-GUARD-DID-NOT-RUN'
EFI_GRUB = ('# Candy master USB: find the partition that holds the installer, then use its GRUB menu.\n'
            'search --no-floppy --set=root --file /.disk/info\nset prefix=($root)/boot/grub\nconfigfile $prefix/grub.cfg\n')
APP_EXCLUDE_DIRS = {'.git', '.venv', 'venv', 'node_modules', 'outputs', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
                    '.godot', '.playwright', 'playwright-report', 'test-results'}
APP_EXCLUDE_PATHS = {'game/data/plates_local', 'ComfyUI', 'server-kit', 'docs/screenshots', 'game/build', 'game/assets/imports'}
APP_EXCLUDE_FILES = ('*.gguf', '*.safetensors', '*.ckpt', '*.pt', '*.pth', '*.onnx', '*.bin', '.env*', '.DS_Store', '*.pyc',
                     '*.pem', '*.key', 'id_rsa*', 'id_ed25519*', 'password.txt', '*.iso')
APP_MAX_BYTES = 400 * 1000 ** 2
FIXED_MTIME = 315532800  # 1980-01-01: same sources => byte-identical bundle => same SHA256


def digest(p, algo='sha256'):
    h = hashlib.new(algo)
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def fetch(url, dest):
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    tmp = pathlib.Path(str(dest) + '.part')
    have = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers={'Range': f'bytes={have}-'} if have else {})
    with urllib.request.urlopen(req, timeout=120) as src:
        mode = 'ab' if have and src.status == 206 else 'wb'
        with open(tmp, mode) as dst:
            shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
    os.replace(tmp, dest)


# ------------------------------------------------------------------ config
def public_key(path):
    keyfile = pathlib.Path(path).expanduser()
    if not keyfile.is_file():
        raise ValueError(f'SSH public key not found at {keyfile}. Create the key in 1Password (SSH key item), export its '
                         'PUBLIC key to that path, and run again. The kit never creates or reads a private key.')
    key = keyfile.read_text().strip()
    if '\n' in key or 'PRIVATE KEY' in key or not re.fullmatch(r'(ssh-ed25519|ecdsa-sha2-nistp(256|384|521)|ssh-rsa) [A-Za-z0-9+/=]{40,}( [ -~]{0,200})?', key):
        raise ValueError('only one public SSH key line (ssh-ed25519 / ecdsa / rsa) may be embedded')
    if key.startswith('ssh-rsa ') and len(key.split()[1]) < 500:
        raise ValueError('RSA keys under 3072 bits are refused; use ed25519')
    if shutil.which('ssh-keygen'):
        if subprocess.run(['ssh-keygen', '-l', '-f', str(keyfile)], capture_output=True).returncode:
            raise ValueError('malformed SSH public key')
    return key


def validate(c, kit):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,30}', c.get('username', '')):
        raise ValueError('invalid username')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', c.get('hostname', '')):
        raise ValueError('invalid hostname')
    mode = c.get('os_disk_mode', 'exact_serial')
    if mode not in DISK_MODES:
        raise ValueError('os_disk_mode must be auto_single_blank_nvme or exact_serial')
    if mode == 'exact_serial' and not re.fullmatch(r'[A-Za-z0-9_.-]{4,100}', c.get('os_disk_serial', '')):
        raise ValueError('exact_serial mode needs the NVMe serial (letters, digits, - _ .); no automatic largest-disk choice')
    if c.get('approve_blank_disk_install') is not True:
        raise ValueError('approve_blank_disk_install must be true (the installer only ever uses a blank NVMe)')
    if c.get('hardware_checklist_confirmed') is not True:
        raise ValueError('confirm server-kit/HARDWARE-CHECKLIST.md first (hardware_checklist_confirmed: true)')
    for pin in kit['software']['git_pins']:
        if not HEX40.match(pin['commit']):
            raise ValueError(f'{pin["id"]}: a full 40-hex commit is required')
    iso = kit['iso']
    if not re.fullmatch(r'ubuntu-24\.04\.[0-9]+-live-server-amd64\.iso', iso['filename']) or not HEX64.match(iso['sha256']):
        raise ValueError('kit.json must pin an Ubuntu 24.04 point-release server ISO by name and SHA256')
    if iso['base_url'] != 'https://releases.ubuntu.com/24.04':
        raise ValueError('only the official Ubuntu release host is allowed')
    return public_key(c['ssh_public_key_file'])


# ------------------------------------------------------------------ autoinstall
def snapshot_uri(kit):
    return next(s['uri'] for s in kit['apt']['sources'] if s['id'] == 'ubuntu')


def render(c, kit, key):
    mirror = [{'arches': ['default'], 'uri': snapshot_uri(kit)}]
    mode = c.get('os_disk_mode', 'exact_serial')
    return {'autoinstall': {
        'version': 1, 'interactive-sections': [], 'refresh-installer': {'update': False},
        'locale': 'en_US.UTF-8', 'keyboard': {'layout': 'us'}, 'timezone': c.get('timezone', 'America/New_York'),
        'identity': {'hostname': c['hostname'], 'username': c['username'], 'password': '!'},
        'ssh': {'install-server': True, 'allow-pw': False, 'authorized-keys': [key]},
        'network': {'version': 2, 'ethernets': {'wired': {'match': {'name': 'en*'}, 'dhcp4': True, 'optional': True}}},
        # Pinned: online the installer uses the same Ubuntu snapshot the kit was built against; offline it installs
        # from the ISO's own pool instead of stopping.
        'apt': {'primary': mirror, 'security': mirror, 'geoip': False, 'fallback': 'offline-install'},
        'drivers': {'install': False}, 'codecs': {'install': False}, 'oem': {'install': False},
        'source': {'id': 'ubuntu-server'},
        # Matches no disk: early-commands' disk_guard.py must rewrite it to the one verified blank NVMe, otherwise the
        # install fails closed before anything is partitioned.
        'storage': {'layout': {'name': 'direct', 'match': {'serial': PLACEHOLDER_SERIAL}}},
        'kernel': {'package': 'linux-generic-hwe-24.04'},
        # Only what the ISO itself carries: everything else is installed on first boot from the USB's store.
        'packages': [],
        'early-commands': ['python3 /cdrom/turin/payload/disk_guard.py ' + DISK_MODES[mode] + ' /cdrom/turin/config/install.json'],
        'error-commands': ['tar -czf /turin-installer-logs.tar.gz /var/log/installer/ || true'],
        'late-commands': [
            'mkdir -p /target/opt/turin', 'cp -a /cdrom/turin/. /target/opt/turin/',
            'python3 /cdrom/turin/payload/store_import.py --target /target',
            'curtin in-target --target=/target -- /bin/bash /opt/turin/payload/install_services.sh'],
        'user-data': {'disable_root': True},
        # Power off, not reboot: when the server turns itself off, unplug the USB and switch it on again. A reboot with
        # the USB still in would start the installer a second time.
        'shutdown': 'poweroff'}}


def patch_grub(text):
    text = re.sub(r'set timeout=\d+', 'set timeout=3', text)
    entries = re.findall(r'^menuentry\s+[\'"]([^\'"]+)', text, flags=re.M)
    default = next((i for i, e in enumerate(entries) if 'HWE' in e), 0)
    text = re.sub(r'set default=.*\n?', '', text)
    text = 'set default=' + str(default) + '\n' + text
    lines = []
    for line in text.splitlines():
        if re.match(r'\s*linux\s', line) and re.search(r'/casper/(hwe-)?vmlinuz', line):
            arg = ' autoinstall ds=nocloud\\;s=/cdrom/nocloud/'
            line = line.replace(' ---', arg + ' ---', 1) if ' ---' in line else line + arg
        lines.append(line)
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------ ISO scan
def scan_iso(iso, run=subprocess.Popen):
    """One streaming pass over the ISO: SHA256 + size of every file, the symlinks (FAT32 cannot hold them), and the
    two small files we patch. Nothing is extracted to disk."""
    proc = run(['bsdtar', '-cf', '-', '--format', 'pax', '@' + str(iso)], stdout=subprocess.PIPE)
    files, links, keep = [], [], {}
    with tarfile.open(fileobj=proc.stdout, mode='r|') as tf:
        for m in tf:
            name = m.name[2:] if m.name.startswith('./') else m.name
            if m.issym() or m.islnk():
                links.append(name); continue
            if not m.isfile():
                continue
            f = tf.extractfile(m); h = hashlib.sha256(); size = 0
            buf = io.BytesIO() if name in ('boot/grub/grub.cfg', 'md5sum.txt') else None
            for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
                h.update(b); size += len(b)
                if buf is not None: buf.write(b)
            files.append({'path': name, 'size': size, 'sha256': h.hexdigest()})
            if buf is not None: keep[name] = buf.getvalue()
    if proc.wait():
        raise RuntimeError('bsdtar could not read the ISO')
    return files, sorted(links), keep


def patch_md5(text, replaced):
    """Ubuntu's media check list (MD5, an integrity check, not the trust check): fix the lines we changed/added."""
    out = [ln for ln in text.splitlines() if ln.split() and ln.split()[-1][2:] not in replaced]
    for rel, data in sorted(replaced.items()):
        out.append(hashlib.md5(data).hexdigest() + '  ./' + rel)
    return '\n'.join(out) + '\n'


# ------------------------------------------------------------------ app bundle
def _excluded(rel):
    import fnmatch
    parts = rel.split('/')
    if any(p in APP_EXCLUDE_DIRS for p in parts):
        return True
    if any(rel == e or rel.startswith(e + '/') for e in APP_EXCLUDE_PATHS):
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in APP_EXCLUDE_FILES)


def make_app_bundle(src, out, ref='HEAD', run=subprocess.run):
    """Reproducible tar.gz of one COMMIT of the Easy Studio repo (`git archive`, so untracked or uncommitted files never
    reach the server), minus weights, keys, .env files, outputs and this kit. Returns (sha256, files, commit)."""
    src = pathlib.Path(src).resolve()
    commit = run(['git', '-C', str(src), 'rev-parse', '--verify', ref + '^{commit}'], capture_output=True, text=True,
                 check=True).stdout.strip()
    proc = subprocess.Popen(['git', '-C', str(src), 'archive', '--format=tar', commit], stdout=subprocess.PIPE)
    out = pathlib.Path(out); out.parent.mkdir(parents=True, exist_ok=True); tmp = out.with_suffix('.tmp')
    files, total, has_server = 0, 0, False
    with tarfile.open(fileobj=proc.stdout, mode='r|') as tin, open(tmp, 'wb') as raw, \
            gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as gz, \
            tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tf:
        for m in tin:
            rel = m.name.rstrip('/')
            if not rel or _excluded(rel) or not (m.isfile() or m.isdir()):
                continue
            ti = tarfile.TarInfo(rel); ti.mtime = FIXED_MTIME; ti.uid = ti.gid = 0; ti.uname = ti.gname = ''
            if m.isdir():
                ti.type = tarfile.DIRTYPE; ti.mode = 0o755; tf.addfile(ti); continue
            ti.size = m.size; ti.mode = 0o755 if m.mode & 0o111 else 0o644
            total += m.size; files += 1; has_server |= rel == 'app/server.py'
            if total > APP_MAX_BYTES:
                raise ValueError(f'the app bundle passed {APP_MAX_BYTES / 1e6:.0f} MB; something large is committed')
            tf.addfile(ti, tin.extractfile(m))
    if proc.wait():
        raise ValueError('git archive failed')
    if not has_server:
        tmp.unlink(missing_ok=True)
        raise ValueError(f'{src} at {commit[:12]} does not look like Easy Studio (no app/server.py)')
    os.replace(tmp, out)
    return digest(out), files, commit


# ------------------------------------------------------------------ build
def effective_install(c, app_sha, app_commit=''):
    e = {k: v for k, v in c.items() if k not in ('ssh_public_key_file', 'easy_studio_source_dir', '_comment')}
    e['app_bundle'] = 'app-bundle.tar.gz' if app_sha else ''
    e['app_bundle_sha256'] = app_sha or ''
    e['app_commit'] = app_commit
    return e


def build(c, kit, key, lock, iso, out_dir, app_dir=None, scan=scan_iso, app_ref='HEAD'):
    """Write the overlay tree and return the usb-plan dict."""
    out_dir = pathlib.Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    files, links, keep = scan(iso)
    biggest = max(f['size'] for f in files)
    if biggest > kit['usb']['fat32_max_file_bytes']:
        raise ValueError('the ISO holds a file FAT32 cannot store (4 GiB or more)')
    grub = keep.get('boot/grub/grub.cfg', b'').decode()
    if '/casper/vmlinuz' not in grub:
        raise ValueError('unsupported Ubuntu boot layout (no /casper/vmlinuz in boot/grub/grub.cfg)')
    patched = patch_grub(grub)
    if patched.count('autoinstall ds=nocloud') != len(re.findall(r'^\s*linux\s+/casper/(?:hwe-)?vmlinuz', grub, flags=re.M)):
        raise ValueError('not every installer kernel entry received autoinstall')
    over = {}
    over['nocloud/user-data'] = ('#cloud-config\n' + json.dumps(render(c, kit, key), indent=2) + '\n').encode()
    over['nocloud/meta-data'] = ('instance-id: candy-first-install\nlocal-hostname: ' + c['hostname'] + '\n').encode()
    over['boot/grub/grub.cfg'] = patched.encode()
    over['EFI/boot/grub.cfg'] = EFI_GRUB.encode()
    for p in sorted((KIT / 'payload').rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            over['turin/payload/' + p.relative_to(KIT / 'payload').as_posix()] = p.read_bytes()
    # The server's downloader reuses the kit's own lock reader and fetcher (one source, two places).
    over['turin/payload/kitlock.py'] = (KIT / 'kitlib' / 'lock.py').read_bytes()
    over['turin/payload/kitfetch.py'] = (KIT / 'kitlib' / 'fetch.py').read_bytes()
    over['turin/config/kit.json'] = (KIT / 'config' / 'kit.json').read_bytes()
    over['turin/locks/server_model_lock.json'] = pathlib.Path(lock['path']).read_bytes()
    reg = (KIT / kit['models']['llm_registry']).resolve()
    if reg.is_file():
        over['turin/locks/llm_models.json'] = reg.read_bytes()
    place = (KIT / kit['models']['placement']).resolve()
    if not place.is_file():
        raise ValueError(f'No GPU placement file at {place}: the lead\'s app/placement.json is needed (the Director\'s card comes from it)')
    over['turin/locks/placement.json'] = place.read_bytes()
    app_sha = app_commit = ''
    if app_dir:
        tmp = out_dir.parent / 'app-bundle.tar.gz'
        app_sha, _n, app_commit = make_app_bundle(app_dir, tmp, app_ref)
        over['turin/app-bundle.tar.gz'] = tmp.read_bytes()
    over['turin/config/install.json'] = (json.dumps(effective_install(c, app_sha, app_commit), indent=2) + '\n').encode()
    replaced = {k: v for k, v in over.items()}
    md5 = keep.get('md5sum.txt', b'').decode()
    if not md5:
        raise ValueError('the ISO has no md5sum.txt')
    over['md5sum.txt'] = patch_md5(md5, {k: v for k, v in replaced.items()}).encode()
    entries = []
    for rel, data in sorted(over.items()):
        dst = out_dir / rel; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(data)
        if rel.startswith('turin/payload/') and (rel.endswith('.sh') or '/bin/' in rel or rel.endswith('.py')):
            dst.chmod(0o755)
        entries.append({'path': rel, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    overlay_paths = {e['path'] for e in entries}
    iso_files = [f for f in files if f['path'] not in overlay_paths]
    usb_rows = locklib.select(lock, kit['models']['usb_waves'])
    return {
        'format': 'candy-server-kit.usb-plan/1', 'kit_version': (KIT / 'VERSION').read_text().strip(),
        'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'iso': {'path': str(pathlib.Path(iso).resolve()), 'sha256': kit['iso']['sha256'], 'exclude': links,
                'max_file_bytes': biggest, 'files': iso_files},
        'overlay': {'dir': str(out_dir.resolve()), 'files': entries, 'replace_dirs': ['turin', 'nocloud'],
                    'sha256': hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()},
        'boot_size': kit['usb']['boot_size'], 'boot_bytes': kit['usb']['boot_bytes'],
        'lock': {'path': lock['path'], 'sha256': lock['sha256'], 'rows': len(lock['rows']),
                 'usb_rows': len(usb_rows), 'usb_bytes': locklib.total_bytes(usb_rows)},
        'store_bytes': locklib.total_bytes(usb_rows),
    }


def ensure_iso(kit, iso_dir, offline):
    iso = pathlib.Path(iso_dir) / kit['iso']['filename']
    if not offline:
        sums = pathlib.Path(iso_dir) / 'SHA256SUMS'
        fetch(kit['iso']['base_url'] + '/SHA256SUMS', sums)
        live = {ln.split()[-1].lstrip('*'): ln.split()[0] for ln in sums.read_text().splitlines() if len(ln.split()) == 2}
        if live.get(kit['iso']['filename']) != kit['iso']['sha256']:
            raise SystemExit('the pinned ISO SHA256 does not match Ubuntu\'s official SHA256SUMS; stopped')
        if not iso.exists():
            print('Downloading', kit['iso']['filename'], '(about 4 GB) ...', flush=True)
            fetch(kit['iso']['base_url'] + '/' + kit['iso']['filename'], iso)
    if not iso.is_file():
        raise SystemExit(f'{iso} is missing (run without --offline to download it)')
    print('Checking the ISO SHA256 ...', flush=True)
    if digest(iso) != kit['iso']['sha256']:
        raise SystemExit('official ISO checksum mismatch; stopped')
    return iso


def remaster_iso(plan, out):
    """Plan B for BMC virtual media: the official ISO with the same overlay mapped in (xorriso keeps BIOS+UEFI boot)."""
    if not shutil.which('xorriso'):
        raise SystemExit('xorriso is needed for --iso-out (on the Mac: brew install xorriso)')
    ov = pathlib.Path(plan['overlay']['dir'])
    cmd = ['xorriso', '-indev', plan['iso']['path'], '-outdev', str(out), '-boot_image', 'any', 'replay',
           '-map', str(ov / 'nocloud'), '/nocloud', '-map', str(ov / 'turin'), '/turin',
           '-map', str(ov / 'boot/grub/grub.cfg'), '/boot/grub/grub.cfg', '-map', str(ov / 'md5sum.txt'), '/md5sum.txt',
           '-compliance', 'iso_9660_level=3', '-volid', 'TURIN_INSTALL']
    if out.exists():
        os.replace(out, out.with_name(out.stem + '.previous-' + time.strftime('%Y%m%d-%H%M%S') + '.iso'))
    subprocess.run(cmd, check=True)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(out), '-extract', '/nocloud/user-data', td + '/ud'], check=True)
        if pathlib.Path(td, 'ud').read_bytes() != (ov / 'nocloud/user-data').read_bytes():
            raise SystemExit('read-back of the remastered ISO failed')
    (out.parent / (out.name + '.sha256')).write_text(digest(out) + '  ' + out.name + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--config', default=str(KIT / 'config' / 'install.json'))
    ap.add_argument('--kit-config', default=str(KIT / 'config' / 'kit.json'))
    ap.add_argument('--lock', help='model lock (default: kit.json models.lock, the lead\'s config/server_model_lock.json)')
    ap.add_argument('--iso-dir', default=str(BUILD / 'iso'))
    ap.add_argument('--out', default=str(BUILD / 'boot-overlay'))
    ap.add_argument('--app-dir', default=str(REPO), help='Easy Studio checkout to bundle (default: this repo)')
    ap.add_argument('--app-ref', default='HEAD', help='the commit of Easy Studio to bundle (default: HEAD of --app-dir)')
    ap.add_argument('--no-app', action='store_true')
    ap.add_argument('--offline', action='store_true', help='use the ISO already in --iso-dir; no network')
    ap.add_argument('--iso-out', action='store_true', help='also write build/candy-autoinstall.iso (plan B, needs xorriso)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    kit = json.loads(pathlib.Path(a.kit_config).read_text())
    c = json.loads(pathlib.Path(a.config).read_text())
    key = validate(c, kit)
    lock_path = a.lock or str((KIT / kit['models']['lock']).resolve())
    try:
        lock = locklib.load(lock_path)
    except OSError:
        raise SystemExit(f'No model lock at {lock_path}: the lead\'s config/server_model_lock.json is not there yet '
                         '(or pass --lock PATH).') from None
    place = (KIT / kit['models']['placement']).resolve()
    if not place.is_file():
        raise SystemExit(f'No GPU placement file at {place}: the lead\'s app/placement.json is not there yet.')
    usb = locklib.select(lock, kit['models']['usb_waves'])
    summary = {'mode': 'dry-run' if a.dry_run else 'build', 'writes_disks': False, 'hostname': c['hostname'],
               'disk_mode': c['os_disk_mode'], 'iso': kit['iso']['filename'], 'ubuntu_snapshot': kit['apt']['ubuntu_snapshot'],
               'lock': {'path': lock_path, 'rows': len(lock['rows']), 'usb_rows': len(usb),
                        'usb_gb': round(locklib.total_bytes(usb) / 1e9, 1)},
               'placement': {'path': str(place), 'director_lane': json.loads(place.read_text())['director']['lane']},
               'app_bundle': not a.no_app, 'key_type': key.split()[0]}
    print(json.dumps(summary, indent=2))
    if a.dry_run:
        return 0
    iso = ensure_iso(kit, a.iso_dir, a.offline)
    plan = build(c, kit, key, lock, iso, a.out, None if a.no_app else a.app_dir, app_ref=a.app_ref)
    plan_path = BUILD / 'usb-plan.json'
    plan_path.write_text(json.dumps(plan, indent=1) + '\n')
    print(f'Built {len(plan["overlay"]["files"])} installer files in {a.out}; plan: {plan_path}')
    print(f'ISO files to copy: {len(plan["iso"]["files"])} (skipped symlinks: {", ".join(plan["iso"]["exclude"]) or "none"})')
    if a.iso_out:
        remaster_iso(plan, BUILD / 'candy-autoinstall.iso')
        print('Plan B ISO:', BUILD / 'candy-autoinstall.iso')
    return 0


if __name__ == '__main__':
    sys.exit(main())
