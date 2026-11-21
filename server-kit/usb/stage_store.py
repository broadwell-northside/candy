#!/usr/bin/env python3
"""Fill the master USB's TURINDATA volume with the models and the offline software. A DRY RUN unless --apply.

    python3 server-kit/usb/stage_store.py --serial SERIAL --volume-uuid TURINDATA_UUID            # plan + sizes only
    python3 server-kit/usb/stage_store.py --serial SERIAL --volume-uuid TURINDATA_UUID --apply    # download onto the USB
    HF_TOKEN=... python3 server-kit/usb/stage_store.py ... --apply      # only if the lock has gated rows

Everything downloads STRAIGHT ONTO THE USB, never onto this Mac's disk, resumable (run it again after any stop) and
checked: models by the SHA256 in the lead's lock, .deb files by the SHA256 in the vendor's signed index, wheels by
the SHA256 pip resolves, source archives made with `git archive` after git itself checked the pinned commit.
It writes only to the TURINDATA volume of the disk with that serial, whose marker matches; nothing else.

What lands in TURINDATA/turin-store/:
  models/<dest>                       every lock row in waves 1-3 (--with-heavy adds wave 4)
  apt/ubuntu|nvidia|tailscale/...     partial mirrors: signed InRelease + Packages.gz + the needed .deb files
  wheels/*.whl + requirements-*.lock.txt   ComfyUI (torch cu128) and Easy Studio, hash-locked
  src/<id>-<commit>.tar.gz            ComfyUI and llama.cpp at their pinned commits
  locks/                              the model lock, kit.json, llm_models.json
  store-manifest.json                 every file: path, size, sha256, kind
"""
import argparse, datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, urllib.request

KIT = pathlib.Path(__file__).resolve().parents[1]
REPO = KIT.parent
sys.path.insert(0, str(KIT))
from kitlib import aptrepo, diskinfo, fetch, lock as locklib, marker  # noqa: E402
from kitlib.target import Refused  # noqa: E402

DEFAULT_DENYLIST = '~/.candy-server-kit/disk-denylist.json'
PLATFORMS = ['manylinux_2_39_x86_64', 'manylinux_2_35_x86_64', 'manylinux_2_34_x86_64', 'manylinux_2_31_x86_64',
             'manylinux_2_28_x86_64', 'manylinux_2_27_x86_64', 'manylinux_2_24_x86_64', 'manylinux_2_17_x86_64',
             'manylinux2014_x86_64', 'linux_x86_64']
MARGIN = 5 * 1000 ** 3


def find_data_volume(disks, serial, volume_uuid, denylist, read_marker=marker.read, prefix='/Volumes/'):
    hits = [d for d in disks if diskinfo.norm_serial(serial) in [diskinfo.norm_serial(s) for s in d.serials]]
    if len(hits) != 1:
        raise Refused(f'expected one disk with serial {serial}, found {len(hits)}')
    d = hits[0]
    if d.internal or d.virtual:
        raise Refused('that serial belongs to an internal disk or a disk image')
    if denylist and diskinfo.denied_by(d, denylist):
        raise Refused('that disk is on the deny-list (one of your data drives)')
    vol = next((v for v in d.volumes if v.volume_uuid.upper() == volume_uuid.upper()), None)
    if not vol or vol.volume_name != marker.DATA_LABEL:
        raise Refused(f'no TURINDATA volume with UUID {volume_uuid} on that disk (write the USB first with write_master_usb.py)')
    if not vol.mount_point.startswith(prefix) or vol.mount_point in ('/', '/System/Volumes/Data'):
        raise Refused('TURINDATA is not mounted under /Volumes; unplug and replug the USB')
    probs = marker.problems(read_marker(vol.mount_point), d.serial, vol.volume_uuid, 'data')
    if probs:
        raise Refused('TURINDATA does not carry this kit\'s marker for this disk: ' + '; '.join(probs))
    return d, vol


# ------------------------------------------------------------------ planning
def plan_models(lock, waves):
    return [{'kind': 'model', 'id': r['id'], 'path': 'models/' + r['dest'], 'dest': r['dest'], 'url': r['url'],
             'size': r['size'], 'sha256': r['sha256'], 'requires_token': r.get('requires_token')}
            for r in locklib.select(lock, waves)]


def http_get(url, opener=urllib.request.urlopen):
    with opener(urllib.request.Request(url, headers={'User-Agent': fetch.UA}), timeout=120) as r:
        return r.read()


def plan_apt(kit, get=http_get, out=print):
    """Read the vendors' signed indices (in memory) and return (index files, deb files, unresolved)."""
    index, index_files = aptrepo.Index(), []
    for src in kit['apt']['sources']:
        base = src['uri'].rstrip('/')
        suites = ['.'] if src.get('flat') else src['suites']
        for suite in suites:
            rel_dir = '' if src.get('flat') else f'dists/{suite}/'
            inrel = get(f'{base}/{rel_dir}InRelease')
            index_files.append({'kind': 'apt', 'path': f'apt/{src["id"]}/{rel_dir}InRelease', 'data': inrel,
                                'size': len(inrel), 'sha256': hashlib.sha256(inrel).hexdigest()})
            listed = aptrepo.release_files(inrel.decode('utf-8', 'replace'))
            comps = [''] if src.get('flat') else [c + '/' for c in src['components']]
            for comp in comps:
                rel = f'{comp}binary-amd64/Packages.gz' if comp else 'Packages.gz'
                if rel not in listed:
                    continue
                size, sha = listed[rel]
                data = get(f'{base}/{rel_dir}{rel}')
                if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
                    raise Refused(f'{src["id"]} {suite} {rel}: index does not match its signed InRelease')
                index_files.append({'kind': 'apt', 'path': f'apt/{src["id"]}/{rel_dir}{rel}', 'data': data, 'size': size, 'sha256': sha})
                index.add(aptrepo.packages_from_gz(data), src['id'], base, src.get('only_packages_matching'))
        for key in ('keyring_deb',):
            if key in src:
                kd = src[key]
                index_files.append({'kind': 'apt', 'path': f'apt/{src["id"]}/{kd["file"]}', 'url': f'{base}/{kd["file"]}',
                                    'size': kd['size'], 'sha256': kd['sha256']})
        if 'keyring_file' in src:
            kf = src['keyring_file']
            index_files.append({'kind': 'apt', 'path': f'apt/{src["id"]}/{pathlib.PurePosixPath(kf["url"]).name}',
                                'url': kf['url'], 'size': None, 'sha256': kf['sha256']})
    chosen, unresolved = aptrepo.closure(index, kit['apt']['install'])
    pairing = aptrepo.driver_pairing(chosen, kit['apt']['install'])
    if pairing:
        raise Refused('NVIDIA driver and kernel pins do not pair: ' + '; '.join(pairing))
    debs = [{'kind': 'apt', 'path': f'apt/{f["source"]}/{f["path"]}', 'url': f['url'], 'size': f['size'], 'sha256': f['sha256']}
            for f in aptrepo.deb_files(chosen)]
    return index_files, debs, unresolved


def pip_report(requirements, extra_args=(), run=subprocess.run):
    with tempfile.TemporaryDirectory() as td:
        rep = pathlib.Path(td) / 'report.json'
        argv = [sys.executable, '-m', 'pip', 'install', '--dry-run', '--ignore-installed', '--no-cache-dir', '--quiet',
                '--report', str(rep), '--target', str(pathlib.Path(td) / 't'), '--only-binary=:all:', '--python-version', '3.12',
                '--implementation', 'cp', '--abi', 'cp312'] + [x for p in PLATFORMS for x in ('--platform', p)] + list(extra_args) + list(requirements)
        r = run(argv, capture_output=True, text=True)
        if r.returncode:
            raise Refused('pip could not resolve Linux wheels: ' + (r.stderr or r.stdout).strip().splitlines()[-1][:300])
        doc = json.loads(rep.read_text())
    items = []
    for i in doc.get('install', []):
        di = i['download_info']; sha = di.get('archive_info', {}).get('hashes', {}).get('sha256')
        name = di['url'].split('#')[0].rsplit('/', 1)[-1]
        if not sha or not name.endswith('.whl'):
            raise Refused(f'{i["metadata"]["name"]}: no wheel with a SHA256 (pip found only {name})')
        items.append({'name': i['metadata']['name'], 'version': i['metadata']['version'], 'file': urllib.request.unquote(name),
                      'url': di['url'].split('#')[0], 'sha256': sha})
    return items


def lock_text(items):
    return ''.join(f'{i["name"]}=={i["version"]} --hash=sha256:{i["sha256"]}\n' for i in sorted(items, key=lambda x: x['name'].lower()))


def plan_wheels(kit, comfy_requirements, app_requirements, report=pip_report):
    sw = kit['software']
    torch_args = ['--index-url', sw['torch_index'], '--extra-index-url', 'https://pypi.org/simple']
    sets = {'comfyui': report(list(sw['torch_packages']) + ['-r', str(comfy_requirements)], torch_args)}
    if app_requirements and pathlib.Path(app_requirements).is_file():
        sets['easy-studio'] = report(['-r', str(app_requirements)])
    files, seen = [], set()
    for items in sets.values():
        for i in items:
            if i['file'] in seen:
                continue
            seen.add(i['file'])
            files.append({'kind': 'wheel', 'path': 'wheels/' + i['file'], 'url': i['url'], 'size': None, 'sha256': i['sha256']})
    locks = [{'kind': 'wheel', 'path': f'wheels/requirements-{k}.lock.txt', 'data': lock_text(v).encode()} for k, v in sets.items()]
    for f in locks:
        f['size'] = len(f['data']); f['sha256'] = hashlib.sha256(f['data']).hexdigest()
    return files + locks


# ------------------------------------------------------------------ doing
def git_archive(pin, store, run=subprocess.run):
    """Shallow-fetch exactly the pinned commit (git checks the object hash), then `git archive` it onto the USB."""
    out = store / 'src' / f'{pin["id"]}-{pin["commit"]}.tar.gz'
    if out.is_file() and pathlib.Path(str(out) + '.verified').is_file():
        return out
    work = store / '.work' / pin['id']
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    g = ['git', '-C', str(work)]
    run(['git', 'init', '-q', str(work)], check=True)
    run(g + ['fetch', '-q', '--depth', '1', pin['url'], pin['commit']], check=True)
    got = run(g + ['rev-parse', 'FETCH_HEAD'], check=True, capture_output=True, text=True).stdout.strip()
    if got != pin['commit']:
        raise Refused(f'{pin["id"]}: fetched {got}, expected {pin["commit"]}')
    out.parent.mkdir(parents=True, exist_ok=True)
    run(g + ['archive', '--format=tar.gz', '-o', str(out) + '.part', pin['commit']], check=True)
    os.replace(str(out) + '.part', out)
    fetch.write_sidecar(out, fetch.sha256_file(out))
    shutil.rmtree(work, ignore_errors=True)
    return out


def write_bytes(dest, data):
    dest.parent.mkdir(parents=True, exist_ok=True); tmp = dest.with_name(dest.name + '.part')
    with open(tmp, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, dest)


class Stager:
    def __init__(self, out=print, download=fetch.download, git=git_archive):
        self.out, self.download, self.git = out, download, git

    def apply(self, store, entries, kit, meta):
        man, failed = [], []
        # Tokens: read from this process's environment for this run only; sent only to their own host, never written.
        tokens = {k: os.environ[k] for k in fetch.TOKEN_HOSTS if os.environ.get(k)}
        staging = store / '.incoming'
        for n, e in enumerate(entries, 1):
            dest = store / e['path']
            try:
                if 'data' in e:
                    write_bytes(dest, e['data'])
                elif e['kind'] == 'model' and e.get('requires_token') and not tokens.get(e['requires_token']):
                    failed.append(e.get('id') or e['path']); self.out(f'  skipped (needs {e["requires_token"]}): {e.get("id")}'); continue
                else:
                    self.download(e['url'], dest, e['size'], e['sha256'], tokens=tokens if e['kind'] == 'model' else None,
                                  staging=staging)
                size = dest.stat().st_size
                man.append({k: v for k, v in {'path': e['path'], 'size': size, 'sha256': e['sha256'], 'kind': e['kind'],
                                               'dest': e.get('dest'), 'id': e.get('id')}.items() if v is not None})
            except (fetch.FetchError, OSError) as err:
                failed.append(e.get('id') or e['path']); self.out(f'  not yet: {e.get("id") or e["path"]}: {err}')
            if n % 50 == 0:
                self.out(f'  {n}/{len(entries)} files done')
        for pin in kit['software']['git_pins'] + meta.get('runtime_pins', []):
            try:
                p = self.git(pin, store)
                man.append({'path': str(p.relative_to(store)), 'size': p.stat().st_size, 'sha256': fetch.sha256_file(p), 'kind': 'src'})
            except (subprocess.CalledProcessError, Refused, OSError) as err:
                failed.append(pin['id']); self.out(f'  not yet: {pin["id"]}: {err}')
        meta = {k: v for k, v in meta.items() if k != 'runtime_pins'} | {'runtimes': [p['id'] for p in meta.get('runtime_pins', [])]}
        doc = dict(meta, files=man, missing=failed, created=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        write_bytes(store / 'store-manifest.json', (json.dumps(doc, indent=1) + '\n').encode())
        return doc


def main(argv=None, inventory=None, stager=None, get=http_get, report=pip_report, prefix='/Volumes/'):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--serial', required=True); ap.add_argument('--volume-uuid', required=True)
    ap.add_argument('--denylist', default=DEFAULT_DENYLIST); ap.add_argument('--lock')
    ap.add_argument('--with-heavy', action='store_true', help='also wave 4 (the very large optional LLMs)')
    ap.add_argument('--only', default='models,apt,wheels,src,locks')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    out = (stager.out if stager else print)
    kit = json.loads((KIT / 'config/kit.json').read_text())
    try:
        dl = pathlib.Path(os.path.expanduser(a.denylist))
        disks = (inventory or (lambda: diskinfo.inventory()))()
        d, vol = find_data_volume(disks, a.serial, a.volume_uuid, diskinfo.load_denylist(dl.read_text()) if dl.is_file() else None,
                                  prefix=prefix)
        home_free = fetch.free_bytes(os.path.expanduser('~'))
        if a.apply and home_free < 50 * 1000 ** 3:
            raise Refused(f'this Mac has {home_free / 1e9:.0f} GB free; Ak\'s rule needs 50 GB to stay free (nothing big is '
                          'stored here, but pip and git use a little temporary space)')
        store = pathlib.Path(vol.mount_point) / 'turin-store'
        lock_path = a.lock or str((KIT / kit['models']['lock']).resolve())
        try:
            lock = locklib.load(lock_path)
        except OSError:
            raise Refused(f'no model lock at {lock_path}: the lead\'s config/server_model_lock.json is not there yet') from None
        only = set(a.only.split(','))
        waves = kit['models']['usb_waves'] + (kit['models']['optional_waves'] if a.with_heavy else [])
        entries, unresolved = [], []
        if 'models' in only:
            entries += plan_models(lock, waves)
        if 'locks' in only:
            for name, p in (('server_model_lock.json', pathlib.Path(lock_path)), ('kit.json', KIT / 'config/kit.json'),
                            ('llm_models.json', (KIT / kit['models']['llm_registry']).resolve())):
                if p.is_file():
                    data = p.read_bytes()
                    entries.append({'kind': 'lock', 'path': 'locks/' + name, 'data': data, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        if 'apt' in only:
            out('Reading the signed apt indices (Ubuntu snapshot, NVIDIA CUDA, Tailscale) ...')
            idx, debs, unresolved = plan_apt(kit, get)
            entries += idx + debs
        if 'wheels' in only:
            pin = next(p for p in kit['software']['git_pins'] if p['id'] == 'comfyui')
            raw = get(pin['url'].replace('github.com', 'raw.githubusercontent.com').removesuffix('.git') + f'/{pin["commit"]}/requirements.txt')
            with tempfile.TemporaryDirectory() as td:
                req = pathlib.Path(td) / 'comfyui-requirements.txt'; req.write_bytes(raw)
                entries += plan_wheels(kit, req, REPO / 'requirements.txt', report)
        known = sum(e['size'] or 0 for e in entries)
        free = fetch.free_bytes(store if store.exists() else vol.mount_point)
        out(f'Target: TURINDATA on {d.device} (serial {d.serial}), free {free / 1e9:.0f} GB')
        for kind in ('model', 'apt', 'wheel', 'lock'):
            ks = [e for e in entries if e['kind'] == kind]
            out(f'  {kind:<6} {len(ks):5d} files  {sum(e["size"] or 0 for e in ks) / 1e9:8.1f} GB' + ('  (+ wheel sizes resolved on download)' if kind == 'wheel' else ''))
        out(f'  src    {len(kit["software"]["git_pins"]):5d} archives at pinned commits')
        for tok in sorted({e['requires_token'] for e in entries if e.get('requires_token')}):
            n = sum(1 for e in entries if e.get('requires_token') == tok)
            have = 'set' if os.environ.get(tok) else 'NOT set'
            out(f'  {n} file(s) need {tok} in the environment for --apply (now {have}; it is never stored)')
        if lock['runtimes']:
            out(f'  runtimes from the lock: {", ".join(p["id"] + " @ " + p["commit"][:12] for p in lock["runtimes"])}')
        if unresolved:
            out(f'  {len(unresolved)} apt dependency(ies) not resolvable from the pinned indices; the server fetches those online:')
            for u in unresolved[:10]:
                out('    - ' + u)
        if known + MARGIN > free:
            raise Refused(f'not enough room on TURINDATA: need about {(known + MARGIN) / 1e9:.0f} GB, free {free / 1e9:.0f} GB')
        if not a.apply:
            out('DRY RUN - nothing was written. Add --apply to download onto the USB (resumable; run again after any stop).')
            return 0
        meta = {'format': 'candy-server-kit.store/1', 'kit_version': (KIT / 'VERSION').read_text().strip(),
                'device_serial': d.serial, 'lock_sha256': lock['sha256'], 'apt_unresolved': unresolved,
                'runtime_pins': lock['runtimes']}
        doc = (stager or Stager()).apply(store, entries, kit, meta)
        out(f'Store written: {len(doc["files"])} files verified; {len(doc["missing"])} not yet (run again to resume).')
        return 0 if not doc['missing'] else 1
    except (Refused, ValueError, locklib.LockError, KeyError, OSError) as e:
        out('REFUSED: ' + str(e))
        return 3


if __name__ == '__main__':
    sys.exit(main())
