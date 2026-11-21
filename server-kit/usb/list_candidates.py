#!/usr/bin/env python3
"""Show the USB disks the writer could use, with the serial and UUID to confirm. READ-ONLY.

    python3 server-kit/usb/list_candidates.py              # every external USB disk and whether the writer would take it
    python3 server-kit/usb/list_candidates.py --plug-in    # unplug the new SSD, press Return, plug it in, press Return:
                                                           # shows only the ONE disk that appeared

For each candidate it prints the serial number, size, volumes and their UUIDs, whether anything would make the writer
refuse it, then the exact dry-run command for the writer. It never mounts, unmounts or writes anything, and it keeps
no record of your drives. A deny-list (make_denylist.py) is optional; when present, disks on it are never offered.
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from kitlib import diskinfo, marker, target  # noqa: E402

DEFAULT_DENYLIST = '~/.candy-server-kit/disk-denylist.json'


def physical_external(disks):
    return [d for d in disks if not d.internal and not d.virtual]


def describe(disks, denylist, listdir=os.listdir, tm_mounts=frozenset()):
    rows = []
    for d in physical_external(disks):
        hit = diskinfo.denied_by(d, denylist) if denylist else []
        state = 'ok'
        try:
            target.check_volumes(d, listdir, tm_mounts=tm_mounts)
        except target.Refused as e:
            state = str(e)
        rows.append({'disk': d, 'denied': hit, 'state': state})
    return rows


def show(r, out):
    d = r['disk']
    out(f'\nCandidate {d.device}: {d.media_name or "?"}, {d.size / 1e9:.1f} GB, bus {d.bus or "?"}, serial {d.serial or "(none readable)"}')
    for v in d.volumes:
        out(f'   {v.device:<10} {v.volume_name or "-":<14} {v.filesystem or v.content or "-":<12} volume UUID {v.volume_uuid or "-"}'
            f'  partition UUID {v.disk_uuid or "-"}{"  mounted at " + v.mount_point if v.mount_point else ""}')
    if d.bus not in target.ALLOWED_BUS or not d.serial or diskinfo.serial_is_degenerate(d.serial):
        out('   Not usable: the writer needs a USB disk with a real serial number.')
        return
    if r['state'] != 'ok':
        out('   Not ready: ' + r['state'])
    uuid = next((v.volume_uuid for v in d.volumes if v.volume_uuid and not v.is_small_efi()), '') or \
        next((v.disk_uuid for v in d.volumes if v.disk_uuid and not v.is_small_efi()), '')
    kit = any(v.volume_name in (marker.BOOT_LABEL, marker.DATA_LABEL) for v in d.volumes)
    out('   Already a Candy master USB.' if kit else '   Looks like a new drive.')
    out('   Dry-run the writer with:')
    out(f'     python3 server-kit/usb/write_master_usb.py --serial {d.serial} --volume-uuid {uuid or "<a UUID above>"}')


def main(argv=None, run=diskinfo.real_run, listdir=os.listdir, out=print, ask=input):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--denylist', default=DEFAULT_DENYLIST, help='optional')
    ap.add_argument('--plug-in', action='store_true', help='find the one disk that appears when you plug the new SSD in')
    a = ap.parse_args(argv)
    dl_path = pathlib.Path(os.path.expanduser(a.denylist))
    denylist = diskinfo.load_denylist(dl_path.read_text()) if dl_path.is_file() else None
    tm = diskinfo.time_machine_mounts(run)
    if a.plug_in:
        ask('Unplug the new USB SSD (leave everything else as it is), then press Return: ')
        before = {d.device: d.identifiers() for d in physical_external(diskinfo.inventory(run))}
        ask('Now plug in the new USB SSD, wait until it shows up in Finder, then press Return: ')
        after = physical_external(diskinfo.inventory(run))
        new = [d for d in after if d.device not in before or not (d.identifiers() & before[d.device])]
        if len(new) != 1:
            out(f'Expected exactly one new disk, saw {len(new)}. Nothing to confirm; try again with only the SSD changing.')
            return 2
        for r in describe(new, denylist, listdir, tm):
            show(r, out)
        return 0
    shown = 0
    for r in describe(diskinfo.inventory(run), denylist, listdir, tm):
        if r['denied']:
            out(f'{r["disk"].device}: on the deny-list; never offered.')
            continue
        shown += 1
        show(r, out)
    if not shown:
        out('No candidate USB disk found. Plug in the new USB SSD and run this again.')
    elif shown > 1:
        out('\nMore than one candidate: use --plug-in to see which one is the new SSD.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
