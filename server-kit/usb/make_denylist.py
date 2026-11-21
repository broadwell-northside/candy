#!/usr/bin/env python3
"""OPTIONAL: a disk deny-list, made while your data drives are attached and the new USB SSD is NOT. READ-ONLY.

Ak declined an inventory of his drives (AK-CANDY-REVIEWER-ANSWERS-20261106), so the writer never needs this: it only
adds refusals if you choose to make it.

    python3 server-kit/usb/make_denylist.py
    python3 server-kit/usb/make_denylist.py --out ~/.candy-server-kit/disk-denylist.json

It reads `diskutil list/info`, the IORegistry and the NVMe system profile, and writes one JSON file in your home
folder listing every physical disk attached right now (the internal disk too) by serial number and UUIDs. The USB
writer refuses every disk on this list, whatever its size or name. Running it again ADDS the disks attached then
(it never forgets one) unless you pass --replace.

It never mounts, unmounts, erases or writes a disk, and it refuses to save the list onto an external drive.
"""
import argparse
import datetime
import json
import os
import pathlib
import socket
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from kitlib import diskinfo  # noqa: E402

DEFAULT_OUT = pathlib.Path('~/.candy-server-kit/disk-denylist.json')


def merge(old, new):
    seen = [set(r['identifiers']) for r in old['disks']]
    for r in new['disks']:
        if not any(set(r['identifiers']) <= s for s in seen):
            old['disks'].append(r); seen.append(set(r['identifiers']))
    old['generated_at'] = new['generated_at']
    old.setdefault('history', []).append({'generated_at': new['generated_at'], 'disks_seen': len(new['disks'])})
    old['counts'] = {'disks': len(old['disks']), 'external': sum(1 for r in old['disks'] if not r['internal'])}
    old['warnings'] = sorted(set(old.get('warnings', [])) | set(new['warnings']))
    return old


def main(argv=None, run=diskinfo.real_run, now=None, home=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    ap.add_argument('--replace', action='store_true', help='start a fresh list instead of adding to the existing one')
    a = ap.parse_args(argv)
    if sys.platform != 'darwin' and run is diskinfo.real_run:
        raise SystemExit('macOS only')
    out = pathlib.Path(os.path.expanduser(a.out) if home is None else a.out.replace('~', str(home), 1)).resolve()
    if str(out).startswith('/Volumes/'):
        raise SystemExit('Refused: keep the deny-list on this Mac, not on an external drive (choose a path in your home folder).')
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    new = diskinfo.make_denylist(diskinfo.inventory(run), stamp, socket.gethostname())
    doc = new
    if out.exists() and not a.replace:
        doc = merge(diskinfo.load_denylist(out.read_text()), new)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp'); tmp.write_text(json.dumps(doc, indent=2) + '\n'); os.replace(tmp, out)
    print(f'Deny-list saved: {out}')
    print(f'  {doc["counts"]["disks"]} disks on the list ({doc["counts"]["external"]} external). Seen now:')
    for r in new['disks']:
        print(f'   - {r["device_at_generation"]:<8} {"internal" if r["internal"] else "external"} {r["bus"] or "?":<12} '
              f'{r["size_bytes"] / 1e9:8.1f} GB  serial {r["serial"] or "(none readable)"}  {len(r["identifiers"])} identifiers')
    for w in new['warnings']:
        print('  note:', w)
    print('Was the new master USB SSD plugged in just now? If yes, unplug it and run this again with --replace.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
