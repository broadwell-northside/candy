#!/usr/bin/env python3
"""turin-models.service: make /srv/ai/models match the lead's model lock, SHA256 for SHA256.

The installer already copied everything the master USB carried (store_import.py) and left a `.verified` sidecar per
file, so on a full USB this only confirms. Anything missing - a row added to the lock after the USB was written, or
a USB without models - is downloaded here: resumable, exact size and SHA256 before promotion, 20 GiB kept free.
Rows needing a token (gated files) are skipped: the server holds no token; stage those on the USB from the Mac.
Status for the dashboard: /srv/ai/models/download-status.json (ids, waves, sizes, states; no names).
Exit 0 = nothing a retry could fix; exit 1 = transient failures (systemd retries later).
"""
import argparse, json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kitfetch  # noqa: E402  (copy of server-kit/kitlib/fetch.py)
import kitlock  # noqa: E402   (copy of server-kit/kitlib/lock.py)

LOCK = pathlib.Path('/opt/turin/locks/server_model_lock.json')
KIT_JSON = pathlib.Path('/opt/turin/config/kit.json')
ROOT = pathlib.Path('/srv/ai/models')
HEAVY_FLAG = pathlib.Path('/etc/turin-ai/heavy-llms.enabled')
RESERVE = 50 * 1000 ** 3  # Ak's floor: 50 GB always stays free
PERMANENT = ('needs a token', 'HTTP Error 401', 'HTTP Error 403', 'HTTP Error 404', 'not enough free space')


def link_into_comfy(root, row):
    link = row.get('comfy_link')
    if not link:
        return
    target = root / row['dest']
    d = root / 'comfy' / link['type']; d.mkdir(parents=True, exist_ok=True)  # type and name already cleaned by kitlock
    lnk = d / link['name']; rel = os.path.relpath(target, d)
    if lnk.is_symlink() and os.readlink(lnk) == rel:
        return
    if lnk.exists() or lnk.is_symlink():
        lnk.unlink()
    lnk.symlink_to(rel)


def write_status(root, rows, heavy):
    waves = {}
    for r in rows:
        w = waves.setdefault(str(r['wave']), {'files': 0, 'verified': 0, 'bytes_total': 0, 'bytes_verified': 0, 'blocked': 0, 'skipped': 0})
        w['files'] += 1; w['bytes_total'] += r['size_bytes']
        if r['state'] == 'verified':
            w['verified'] += 1; w['bytes_verified'] += r['size_bytes']
        elif r['state'] in ('blocked', 'skipped'):
            w[r['state']] += 1
    doc = {'updated_epoch': time.time(), 'heavy_llms_enabled': heavy, 'waves': waves, 'rows': rows}
    p = root / 'download-status.json'; tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(doc)); tmp.chmod(0o644); os.replace(tmp, p)


def run(root=ROOT, lock_path=LOCK, waves=None, heavy=None, fetch=kitfetch.download, out=print):
    root = pathlib.Path(root); root.mkdir(parents=True, exist_ok=True)
    kit = json.loads(KIT_JSON.read_text()) if KIT_JSON.exists() else {'models': {'usb_waves': [1, 2, 3], 'optional_waves': [4]}}
    heavy = HEAVY_FLAG.exists() if heavy is None else heavy
    waves = waves or (kit['models']['usb_waves'] + (kit['models']['optional_waves'] if heavy else []))
    lock = kitlock.load(lock_path)
    status, transient = [], 0
    for r in kitlock.select(lock, waves):
        row = {'id': r['id'], 'wave': r['wave'], 'size_bytes': r['size'], 'state': 'checking'}
        status.append(row)
        dest = root / r['dest']
        try:
            if kitfetch.verified(dest, r['sha256'], r['size']):
                row['state'] = 'verified'; link_into_comfy(root, r); continue
            if r.get('requires_token'):
                row['state'] = 'skipped'; row['error'] = 'needs a token: stage this file on the master USB from the Mac'; continue
            part = root / '.incoming' / (r['sha256'] + '.part')
            have = part.stat().st_size if part.exists() else 0
            if kitfetch.free_bytes(dest.parent) < r['size'] - have + RESERVE:
                row['state'] = 'blocked'; row['error'] = 'not enough free space (50 GB kept free)'; continue
            row['state'] = 'downloading'; write_status(root, status, heavy)
            fetch(r['url'], dest, r['size'], r['sha256'], staging=root / '.incoming')
            row['state'] = 'verified'; link_into_comfy(root, r)
        except Exception as e:  # noqa: BLE001 - every row reports, the queue continues
            row['state'] = 'blocked'; row['error'] = str(e)[:300]
            if not any(k in row['error'] for k in PERMANENT):
                transient += 1
        finally:
            write_status(root, status, heavy)
    done = sum(1 for r in status if r['state'] == 'verified')
    out(f'models: {done}/{len(status)} verified, {transient} transient failure(s)', flush=True)
    return 1 if transient else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=str(ROOT)); ap.add_argument('--wave', type=int, action='append')
    ap.add_argument('--heavy', action='store_true'); ap.add_argument('--plan', action='store_true')
    a = ap.parse_args(argv)
    if a.plan:
        for r in kitlock.select(kitlock.load(LOCK), a.wave or [1, 2, 3, 4]):
            print(f"wave {r['wave']}  {r['size'] / 1e9:8.2f} GB  {r['id']}")
        return 0
    return run(a.root, waves=a.wave, heavy=True if a.heavy else None)


if __name__ == '__main__':
    sys.exit(main())
