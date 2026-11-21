#!/usr/bin/env python3
"""Write the Candy master USB. A DRY RUN unless you add --write (or --update-boot). Only Ak runs this.

    python3 server-kit/usb/list_candidates.py                                    # shows SERIAL and UUID of the new SSD
    python3 server-kit/usb/write_master_usb.py --serial SERIAL --volume-uuid UUID           # dry run: what it would do
    python3 server-kit/usb/write_master_usb.py --serial SERIAL --volume-uuid UUID --write   # erases THAT disk only
    python3 server-kit/usb/write_master_usb.py --serial SERIAL --volume-uuid UUID --update-boot   # new installer files,
                                                                                         # models on the USB kept

It picks the disk ONLY by the serial number plus a volume UUID you confirm for this run. It refuses: internal disks,
disk images, anything not on USB, a generic serial, any APFS or Time Machine volume, any filesystem it cannot inspect,
and any disk that holds files (a non-empty Trash counts) unless both its volumes carry this kit's own marker. A
deny-list (make_denylist.py) is optional and only adds refusals. It reads the disk's identity again right before
erasing and stops if anything changed. It writes only from a real Terminal, never from an agent. No size rule, no sudo.

Layout written: MBR (GPT above 2 TiB) with FAT32 "TURINBOOT" (12 GB: the official Ubuntu ISO's files, SHA256-checked,
plus this kit's installer files) and exFAT "TURINDATA" (the rest: models and offline software, filled by
stage_store.py). UEFI boot only.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid as uuidlib

KIT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from kitlib import diskinfo, marker, target  # noqa: E402
from kitlib.target import Refused  # noqa: E402

DEFAULT_PLAN = KIT / 'build' / 'usb-plan.json'
DEFAULT_DENYLIST = '~/.candy-server-kit/disk-denylist.json'
PLAN_FORMAT = 'candy-server-kit.usb-plan/1'
FAT32_MAX = 4 * 1024 ** 3 - 1
AGENT_ENV = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CODEX_SANDBOX', 'CODEX_HOME', 'CURSOR_AGENT', 'CURSOR_TRACE_ID')
F_NOCACHE = 48  # macOS fcntl: read from the device, not from the page cache


def digest(path, algo='sha256', block=8 * 1024 * 1024, nocache=False):
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        if nocache and sys.platform == 'darwin':
            import fcntl
            fcntl.fcntl(f.fileno(), F_NOCACHE, 1)
        for b in iter(lambda: f.read(block), b''):
            h.update(b)
    return h.hexdigest()


def seatbelt(env=os.environ, stdin=sys.stdin):
    """Only a person at a real Terminal writes a disk. A seatbelt, not the control: no session ever runs this tool."""
    marks = [k for k in env if k in AGENT_ENV or k.startswith(('CODEX_', 'CURSOR_'))]
    if marks:
        raise Refused('this looks like an AI agent session (' + ', '.join(sorted(marks)) + '); only Ak writes the USB, from Terminal')
    if not stdin.isatty():
        raise Refused('run this in Terminal (the confirmation must be typed by hand)')


def load_plan(path):
    plan = json.loads(pathlib.Path(path).read_text())
    if plan.get('format') != PLAN_FORMAT:
        raise Refused(f'{path} is not a usb-plan from builder.py; run builder.py first')
    iso, overlay = plan['iso'], plan['overlay']
    if not pathlib.Path(iso['path']).is_file():
        raise Refused(f'the ISO in the plan is missing: {iso["path"]}')
    if int(iso.get('max_file_bytes', 0)) > FAT32_MAX:
        raise Refused('the ISO holds a file of 4 GiB or more, which FAT32 cannot store')
    for f in overlay['files']:
        p = pathlib.PurePosixPath(f['path'])
        if p.is_absolute() or '..' in p.parts:
            raise Refused('unsafe overlay path ' + f['path'])
    return plan


class Writer:
    def __init__(self, run=subprocess.run, inventory=diskinfo.inventory, listdir=os.listdir, read_marker=marker.read,
                 ask=input, out=print, now=None, sleep=time.sleep, wait_seconds=60, volumes_prefix='/Volumes/',
                 tm=diskinfo.time_machine_mounts, guard=seatbelt):
        self.run, self.inventory, self.listdir, self.read_marker = run, inventory, listdir, read_marker
        self.tm, self.guard = tm, guard
        self.ask, self.out, self.sleep, self.wait_seconds = ask, out, sleep, wait_seconds
        self.volumes_prefix = volumes_prefix
        self.now = now or (lambda: datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))

    # ------------------------------------------------------------ checks
    def pick(self, serial, volume_uuid, denylist, need=0):
        return target.select(self.inventory(), serial, volume_uuid, denylist, need, self.listdir, self.read_marker, self.tm())

    def recheck(self, before, serial, volume_uuid, denylist, need=0):
        """Read the disk's identity again immediately before a destructive step."""
        after, vol = self.pick(serial, volume_uuid, denylist, need)
        if not target.same_identity(before, after):
            raise Refused('the disk changed since you confirmed it (device node, serial, size or volumes); nothing was written')
        return after, vol

    def find_kit_volumes(self, serial):
        """The TURINBOOT and TURINDATA volumes of the disk with this serial, once macOS has mounted them."""
        waited = 0
        while True:
            hits = [d for d in self.inventory() if diskinfo.norm_serial(serial) in [diskinfo.norm_serial(s) for s in d.serials]]
            if len(hits) == 1:
                vols = {v.volume_name: v for v in hits[0].volumes}
                boot, data = vols.get(marker.BOOT_LABEL), vols.get(marker.DATA_LABEL)
                if boot and data and boot.mount_point and data.mount_point:
                    for v in (boot, data):
                        if not v.mount_point.startswith(self.volumes_prefix) or not v.volume_uuid:
                            raise Refused(f'{v.device} is not mounted under /Volumes or has no UUID; stopped')
                    return hits[0], boot, data
            if waited >= self.wait_seconds:
                raise Refused('the new TURINBOOT / TURINDATA volumes did not appear; unplug the USB, plug it back in and run '
                              'this again with --update-boot')
            self.sleep(2); waited += 2

    # ------------------------------------------------------------ writing
    def write_marker(self, vol, role, serial, run_id, extra=None):
        doc = marker.make(role, serial, vol.volume_uuid, run_id, self.now(), KIT_VERSION)
        doc.update(extra or {})
        path = os.path.join(vol.mount_point, marker.MARKER_NAME)
        with open(path, 'w') as f:
            f.write(json.dumps(doc, indent=2) + '\n'); f.flush(); os.fsync(f.fileno())

    def extract_iso(self, plan, boot):
        argv = ['bsdtar', '-xf', plan['iso']['path'], '-C', boot.mount_point]
        for x in plan['iso'].get('exclude', []):
            argv += ['--exclude', x]
        self.run(argv, check=True)

    def copy_overlay(self, plan, boot):
        src = pathlib.Path(plan['overlay']['dir'])
        for top in plan['overlay'].get('replace_dirs', []):
            p = pathlib.Path(boot.mount_point, top)
            if p.is_dir():
                shutil.rmtree(p)  # only the kit's own folders on the kit's own, marker-checked volume
        for f in plan['overlay']['files']:
            dst = pathlib.Path(boot.mount_point, f['path']); dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / f['path'], dst)

    def verify_boot(self, plan, boot):
        """Read every file back from the USB: each ISO file and each installer file against its SHA256 in the plan
        (the ISO's own md5sum.txt skips the UEFI loaders, so it is not enough)."""
        bad, checked = [], 0
        for f in plan['iso']['files'] + plan['overlay']['files']:
            p = os.path.join(boot.mount_point, f['path'])
            if not os.path.isfile(p) or os.path.getsize(p) != f['size'] or digest(p, nocache=True) != f['sha256']:
                bad.append(f['path'])
            checked += 1
        if bad:
            raise Refused(f'{len(bad)} file(s) did not read back correctly from the USB, e.g. {bad[:3]}. Run again with '
                          '--update-boot; if it keeps failing, use another USB port or cable.')
        return checked

    def execute(self, a, plan, denylist):
        need = int(plan.get('boot_bytes', 12 * 1000 ** 3)) + int(plan.get('store_bytes', 0))
        d, vol = self.pick(a.serial, a.volume_uuid, denylist, need)
        mode = 'write' if a.write else 'update-boot' if a.update_boot else 'dry-run'
        kit_disk = len(vol['kit_owned']) == 2
        self.out(f'Target: {d.device}, {d.media_name or "?"}, {d.size / 1e9:.1f} GB, bus {d.bus}, serial {d.serial}')
        self.out('  passed: exactly one disk with this serial; external USB; not a disk image; no APFS or Time Machine '
                 f'volume; {"not on the deny-list; " if denylist else ""}UUID {a.volume_uuid} present; '
                 + ('both volumes carry this kit\'s marker' if kit_disk else 'no volume holds files'))
        if not 0.9e12 <= d.size <= 2.3e12:
            self.out(f'  note: {d.size / 1e12:.2f} TB is not the 1-2 TB USB SSD the kit expects. Size never decides anything; '
                     'just make sure this is the drive you bought for the server.')
        argv = target.partition_argv(d, plan.get('boot_size', '12G'))
        if mode == 'dry-run':
            self.out('DRY RUN - nothing was written. With --write it would:')
            self.out('  1. ask you to type ERASE ' + d.serial + ', then read the disk\'s identity again')
            self.out('  2. run: ' + ' '.join(argv))
            self.out('  3. write the kit marker on TURINBOOT and TURINDATA')
            self.out('  4. run: bsdtar -xf ' + plan['iso']['path'] + ' -C /Volumes/TURINBOOT ' +
                     ' '.join('--exclude ' + x for x in plan['iso'].get('exclude', [])))
            self.out(f'  5. copy {len(plan["overlay"]["files"])} installer files, then read every file back and check it')
            return 0
        if os.geteuid() == 0:
            raise Refused('do not run the writer with sudo; it needs no root rights')
        self.guard()
        if not pathlib.Path(plan['iso']['path']).is_file() or digest(plan['iso']['path']) != plan['iso']['sha256']:
            raise Refused('the ISO no longer matches the SHA256 in the plan; run builder.py again')
        run_id = uuidlib.uuid4().hex[:12]
        if mode == 'update-boot':
            if not kit_disk:
                raise Refused('--update-boot only works on a disk that is already a Candy master USB (both markers valid)')
            if self.ask(f'Type UPDATE {d.serial} to replace the installer files on it (models stay): ').strip() != 'UPDATE ' + d.serial:
                raise Refused('not confirmed; nothing was written')
            d, vol = self.recheck(d, a.serial, a.volume_uuid, denylist, need)
            _, boot, data = self.find_kit_volumes(a.serial)
            old = self.read_marker(boot.mount_point) or {}
            if old.get('iso_sha256') != plan['iso']['sha256'] or old.get('status') != 'complete':
                self.write_marker(boot, 'boot', d.serial, run_id, {'status': 'writing'})
                self.extract_iso(plan, boot)
        else:
            if kit_disk and not a.wipe_store:
                raise Refused('this disk is already your master USB and --write would erase the models on it. Use '
                              '--update-boot to change only the installer, or add --wipe-store to start over.')
            if self.ask(f'Type ERASE {d.serial} to erase {d.device} ({d.size / 1e9:.1f} GB) and write the master USB: ').strip() \
                    != 'ERASE ' + d.serial:
                raise Refused('not confirmed; nothing was written')
            d, vol = self.recheck(d, a.serial, a.volume_uuid, denylist, need)
            self.run(target.partition_argv(d, plan.get('boot_size', '12G')), check=True)
            _, boot, data = self.find_kit_volumes(a.serial)
            for v in (boot, data):
                left = marker.user_entries(v.mount_point, self.listdir)
                if left:
                    raise Refused(f'{v.device} is not empty right after partitioning ({left[:3]}); stopped')
            self.write_marker(data, 'data', d.serial, run_id)
            self.write_marker(boot, 'boot', d.serial, run_id, {'status': 'writing'})
            self.extract_iso(plan, boot)
        self.copy_overlay(plan, boot)
        checked = self.verify_boot(plan, boot)
        self.write_marker(boot, 'boot', d.serial, run_id, {'status': 'complete', 'iso_sha256': plan['iso']['sha256'],
                                                            'overlay_sha256': plan['overlay'].get('sha256', '')})
        self.out(f'Done: {checked} installer files read back and matched. TURINBOOT UUID {boot.volume_uuid}, '
                 f'TURINDATA UUID {data.volume_uuid}.')
        self.out('Next: fill the models and offline software (dry run first):')
        self.out(f'  python3 server-kit/usb/stage_store.py --serial {d.serial} --volume-uuid {data.volume_uuid}')
        return 0


KIT_VERSION = (KIT / 'VERSION').read_text().strip() if (KIT / 'VERSION').exists() else 'dev'


def main(argv=None, writer=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--serial', required=True)
    ap.add_argument('--volume-uuid', required=True)
    ap.add_argument('--denylist', default=DEFAULT_DENYLIST, help='optional; only adds refusals')
    ap.add_argument('--plan', default=str(DEFAULT_PLAN))
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--write', action='store_true', help='erase the confirmed disk and write the master USB')
    g.add_argument('--update-boot', action='store_true', help='replace only the installer files on an existing master USB')
    ap.add_argument('--wipe-store', action='store_true', help='with --write: allowed to erase an existing master USB')
    a = ap.parse_args(argv)
    if sys.platform != 'darwin' and writer is None:
        raise SystemExit('The master-USB writer runs on macOS only.')
    w = writer or Writer()
    try:
        dl = pathlib.Path(os.path.expanduser(a.denylist))
        return w.execute(a, load_plan(a.plan), diskinfo.load_denylist(dl.read_text()) if dl.is_file() else None)
    except (Refused, ValueError, KeyError, subprocess.CalledProcessError) as e:
        w.out('REFUSED: ' + str(e))
        return 3


if __name__ == '__main__':
    sys.exit(main())
