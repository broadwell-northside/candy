#!/usr/bin/env python3
"""First-boot apt: the master USB's partial mirror first, the SAME pinned sources online as the fallback.

    python3 apt_offline.py configure      # sources, keyrings, preferences (idempotent)
    python3 apt_offline.py install        # apt-get install the pinned set from kit.json; online fallback on a miss
    python3 apt_offline.py --print        # show the files it would write, change nothing

Pins (K-08) live in /opt/turin/config/kit.json: the Ubuntu snapshot stamp, the HWE kernel, Ubuntu's own
headless NVIDIA 580 driver (no DKMS) with its Canonical-signed prebuilt modules, cuda-toolkit-12-8 and tailscale versions.
The stock /etc/apt/sources.list.d/ubuntu.sources (unpinned, live archive) is switched off, so nothing floats.
Every index is checked by apt against the vendor's signing key (Ubuntu's keyring ships with the OS; NVIDIA's and
Tailscale's keyrings are themselves pinned by SHA256).
"""
import hashlib, json, os, pathlib, subprocess, sys, urllib.request

KIT_JSON = pathlib.Path('/opt/turin/config/kit.json')
STORE = pathlib.Path('/var/lib/turin/store')
ETC = pathlib.Path('/etc/apt')
NVIDIA_ALLOW = ('cuda-* libcublas* libcufft* libcufile* libcurand* libcusolver* libcusparse* libnpp* libnvjitlink* '
                'libnvjpeg* libnvfatbin* libnvptxcompiler* nsight-* gds-tools*')
APT_CONF = '''// Candy server kit: the local store mirror holds .gz indices only and no by-hash copies.
Acquire::By-Hash "no";
Acquire::Languages "none";
Acquire::CompressionTypes::Order { "gz"; };
Acquire::Retries "5";
APT::Install-Recommends "false";
'''
PREFS = f'''# Candy server kit: the NVIDIA driver comes from Ubuntu (Canonical-signed prebuilt modules); NVIDIA's CUDA repo
# only supplies the CUDA toolkit and its libraries.
Package: *
Pin: release o=NVIDIA
Pin-Priority: 100

Package: {NVIDIA_ALLOW}
Pin: release o=NVIDIA
Pin-Priority: 500
'''


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def stanza(src, uri, enabled=True, local=False):
    lines = ['Types: deb', 'URIs: ' + uri]
    if src.get('flat'):
        lines.append('Suites: /')
    else:
        lines += ['Suites: ' + ' '.join(src['suites']), 'Components: ' + ' '.join(src['components'])]
    lines += ['Architectures: amd64', 'Signed-By: ' + src['keyring']]
    if local:
        lines += ['Check-Valid-Until: no', 'Targets: Packages']
    if not enabled:
        lines.append('Enabled: no')
    return '\n'.join(lines) + '\n'


def render(kit, store=STORE, online=False):
    """{path: text} for every apt file the kit manages."""
    local, remote = [], []
    for src in kit['apt']['sources']:
        mirror = store / 'apt' / src['id']
        if mirror.is_dir():
            local.append(stanza(src, 'file:' + str(mirror) + ('/' if src.get('flat') else ''), local=True))
        remote.append(stanza(src, src['uri'] + ('/' if src.get('flat') else ''), enabled=online or not mirror.is_dir()))
    files = {ETC / 'apt.conf.d/90turin': APT_CONF, ETC / 'preferences.d/turin-nvidia': PREFS,
             ETC / 'sources.list.d/turin-online.sources': '\n'.join(remote)}
    if local:
        files[ETC / 'sources.list.d/turin-local.sources'] = '\n'.join(local)
    return files


def install_keyrings(kit, store=STORE, run=subprocess.run, fetch=None):
    fetch = fetch or (lambda url, dest: urllib.request.urlretrieve(url, dest))
    for src in kit['apt']['sources']:
        if 'keyring_deb' in src and not pathlib.Path(src['keyring']).exists():
            kd = src['keyring_deb']; p = store / 'apt' / src['id'] / kd['file']
            if not p.is_file():
                p = pathlib.Path('/var/cache/turin-' + kd['file']); fetch(src['uri'] + '/' + kd['file'], p)
            if sha256(p) != kd['sha256']:
                raise SystemExit(f'{kd["file"]}: SHA256 mismatch; refusing to trust it')
            run(['dpkg', '-i', str(p)], check=True)
            for extra in (ETC / 'sources.list.d').glob('cuda-*.list'):
                extra.unlink()  # the keyring package adds its own online source; the kit's own files define it
        if 'keyring_file' in src:
            kf = src['keyring_file']; dest = pathlib.Path(src['keyring'])
            if dest.exists() and sha256(dest) == kf['sha256']:
                continue
            p = store / 'apt' / src['id'] / pathlib.PurePosixPath(kf['url']).name
            if not p.is_file():
                p = pathlib.Path('/var/cache/turin-' + src['id'] + '.gpg'); fetch(kf['url'], p)
            if sha256(p) != kf['sha256']:
                raise SystemExit(f'{src["id"]} keyring: SHA256 mismatch; refusing to trust it')
            dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(p.read_bytes()); dest.chmod(0o644)


def configure(kit, store=STORE, online=False, run=subprocess.run):
    stock = ETC / 'sources.list.d/ubuntu.sources'
    if stock.exists():
        os.replace(stock, stock.with_name('ubuntu.sources.disabled-by-turin'))
    legacy = ETC / 'sources.list'
    if legacy.exists() and any(ln.strip() and not ln.lstrip().startswith('#') for ln in legacy.read_text().splitlines()):
        os.replace(legacy, legacy.with_name('sources.list.disabled-by-turin'))
    install_keyrings(kit, store, run)
    for path, text in render(kit, store, online).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp'); tmp.write_text(text); os.replace(tmp, path)


def install(kit, store=STORE, run=subprocess.run, out=print):
    pkgs = kit['apt']['install']
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    argv = ['apt-get', '-y', '-o', 'Dpkg::Options::=--force-confold', 'install'] + pkgs
    run(['apt-get', 'update'], check=True, env=env)
    if run(argv, env=env).returncode == 0:
        out('apt: everything installed from the master USB store'); return 'store'
    out('apt: something was not in the store; enabling the same pinned sources online and retrying')
    configure(kit, store, online=True, run=run)
    run(['apt-get', 'update'], check=True, env=env)
    run(argv, check=True, env=env)
    return 'online-fallback'


def main(argv=None):
    a = (argv if argv is not None else sys.argv[1:]) or ['--print']
    kit = json.loads(KIT_JSON.read_text())
    if a[0] == '--print':
        for path, text in render(kit).items():
            print(f'==> {path}\n{text}')
        return 0
    if a[0] == 'configure':
        configure(kit); return 0
    if a[0] == 'install':
        configure(kit); print('apt source used:', install(kit)); return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main())
