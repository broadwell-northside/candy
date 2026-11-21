#!/usr/bin/env python3
"""Candy server kit tests. Offline, no GPU, no root, no real disk.

What is MOCKED here, and stays `hardware_pending` (HARDWARE_PENDING.md) until the real machines run it:
  * every macOS disk tool (diskutil, ioreg, system_profiler) -> tests/fakemac.py, a synthetic Mac shaped like macOS 27's
    real output; `diskutil partitionDisk` and `bsdtar` are replaced by fakes that write into temp folders
  * the server's lsblk / udevadm / wipefs / blkid / mount / nvidia-smi / ipmitool / systemctl / apt / ufw
  * all network: HTTP servers are local, in-process (127.0.0.1), with made-up files
  * the Ubuntu ISO: a tiny synthetic tar stands in for it (set CANDY_ISO=<path to the real ISO> to also scan the real one)
Run:  python3 server-kit/tests/run_tests.py
"""
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

KIT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / 'tests')); sys.path.insert(0, str(KIT / 'usb'))
from kitlib import diskinfo, marker, target  # noqa: E402
from fakemac import FakeMac  # noqa: E402
import write_master_usb as wmu  # noqa: E402
import make_denylist  # noqa: E402
import list_candidates  # noqa: E402

NEW_SERIAL = '2345E6F7A8B9'
NEW_UUID = '9A000000-0000-4000-8000-000000000001'


def denylist_for(mac, *skip):
    """The deny-list Ak would make with every data drive attached and the new SSD unplugged."""
    disks = [d for d in diskinfo.inventory(mac.run) if d.device not in skip]
    return diskinfo.make_denylist(disks, '2026-11-06T00:00:00Z')


class Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(); self.t = pathlib.Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()


class Inventory(unittest.TestCase):
    def test_serials_uuids_and_apfs_folding(self):
        disks = {d.device: d for d in diskinfo.inventory(FakeMac().run)}
        self.assertEqual(disks['disk4'].serial, 'NAA1B2C3')
        self.assertIn('volume_uuid:5A000000-0000-4000-8000-000000000001', disks['disk4'].identifiers(),
                      'the APFS volume in container disk5 belongs to physical disk4')
        self.assertTrue(disks['disk5'].virtual and disks['disk3'].virtual and disks['disk8'].virtual)
        self.assertTrue(disks['disk0'].internal)
        self.assertEqual(disks['disk7'].serial, '')
        self.assertIn('media:External USB 3.0|4000787030016', disks['disk7'].identifiers(), 'no serial -> media key kept')
        self.assertNotIn('media:Samsung PSSD T7|2000398934016', disks['disk6'].identifiers(), 'serial present -> no weak key')
        self.assertEqual(disks['disk9'].serial, NEW_SERIAL)

    def test_only_read_only_commands(self):
        mac = FakeMac(); diskinfo.inventory(mac.run)
        for argv in mac.calls:
            self.assertIn(argv[0], ('diskutil', 'ioreg', 'system_profiler'))
            if argv[0] == 'diskutil': self.assertIn(argv[1], ('list', 'info'))
        with self.assertRaises(ValueError):
            diskinfo.real_run(['diskutil', 'eraseDisk', 'ExFAT', 'X', 'disk9'])
        with self.assertRaises(ValueError):
            diskinfo.real_run(['dd', 'if=/dev/zero'])

    def test_degenerate_serials(self):
        for s in ('000000000000', 'FFFFFFFF', '0123456789ABCDEF', 'AAAAAAAAAA', '123', ''):
            self.assertTrue(diskinfo.serial_is_degenerate(s), s)
        for s in ('2345E6F7A8B9', 'NAA1B2C3', 'S6WXNS0T123456A'):
            self.assertFalse(diskinfo.serial_is_degenerate(s), s)


class DenyList(Tmp):
    def test_make_load_and_merge(self):
        mac = FakeMac()
        dl = denylist_for(mac, 'disk9')
        self.assertEqual(dl['counts'], {'disks': 4, 'external': 3})  # disk0, disk4, disk6, disk7 (images/containers skipped)
        self.assertTrue(any('disk7' in w and 'serial' in w for w in dl['warnings']))
        out = self.t / 'dl.json'
        with contextlib.redirect_stdout(io.StringIO()):
            make_denylist.main(['--out', str(out)], run=FakeMac().run)
        first = diskinfo.load_denylist(out.read_text())
        self.assertEqual(first['counts']['disks'], 5, 'the new SSD was plugged in during this run, so it is denied too')
        with contextlib.redirect_stdout(io.StringIO()):
            make_denylist.main(['--out', str(out)], run=FakeMac().run)
        self.assertEqual(diskinfo.load_denylist(out.read_text())['counts']['disks'], 5, 'merging never duplicates')
        with self.assertRaises(SystemExit):
            make_denylist.main(['--out', '/Volumes/T7/dl.json'], run=FakeMac().run)

    def test_empty_or_foreign_denylist_refused(self):
        with self.assertRaises(ValueError):
            diskinfo.load_denylist(json.dumps({'format': diskinfo.DENYLIST_FORMAT, 'disks': []}))
        with self.assertRaises(ValueError):
            diskinfo.load_denylist(json.dumps({'disks': [{'identifiers': ['serial:X']}]}))


class TargetSelection(Tmp):
    def mac(self, files=()):
        x10 = self.t / 'X10'; x10.mkdir(exist_ok=True)
        for n in files: (x10 / n).write_text('x')
        return FakeMac(mounts={'disk9s1': str(x10)})

    def pick(self, mac, serial=NEW_SERIAL, uuid=NEW_UUID, dl=None):
        return target.select(diskinfo.inventory(mac.run), serial, uuid, dl or denylist_for(mac, 'disk9'))

    def test_new_empty_drive_accepted(self):
        mac = self.mac(['.Spotlight-V100', '.fseventsd', '._.DS_Store'])
        d, vol = self.pick(mac)
        self.assertEqual(d.device, 'disk9'); self.assertEqual(vol['empty'], ['disk9s1'])
        self.assertEqual(target.partition_argv(d), ['diskutil', 'partitionDisk', '/dev/disk9', 'MBR', 'FAT32', 'TURINBOOT', '12G',
                                                    'ExFAT', 'TURINDATA', 'R'])

    def test_vendor_files_refused_with_plain_instructions(self):
        mac = self.mac(['Samsung Portable SSD Software', 'Manual.pdf'])
        with self.assertRaises(target.Refused) as e:
            self.pick(mac)
        self.assertIn('delete its files in Finder', str(e.exception))

    def test_every_data_drive_refused(self):
        mac = self.mac(); dl = denylist_for(mac, 'disk9')
        for serial, uuid, why in (('NAA1B2C3', '5A000000-0000-4000-8000-000000000001', 'deny-list'),
                                  ('S6WXNS0T123456A', '6A000000-0000-4000-8000-000000000001', 'deny-list')):
            with self.assertRaises(target.Refused) as e:
                self.pick(mac, serial, uuid, dl)
            self.assertIn(why, str(e.exception))

    def test_same_drive_in_new_enclosure_still_refused_by_uuid(self):
        mac = self.mac(); dl = denylist_for(mac, 'disk9')
        mac.usb[1]['USB Serial Number'] = mac.usb[1]['kUSBSerialNumberString'] = 'NEWBRIDGE7788'  # T7 moved to another bridge
        with self.assertRaises(target.Refused) as e:
            self.pick(mac, 'NEWBRIDGE7788', '6A000000-0000-4000-8000-000000000001', dl)
        self.assertIn('volume_uuid:6A000000', str(e.exception))

    def test_internal_image_wrong_uuid_ambiguous_and_generic(self):
        mac = self.mac()
        with self.assertRaises(target.Refused):
            self.pick(mac, uuid='00000000-0000-4000-8000-000000000000')  # UUID not on that disk (swapped / reformatted)
        with self.assertRaises(target.Refused):
            self.pick(mac, serial='000000000000')
        mac.usb[1]['USB Serial Number'] = mac.usb[1]['kUSBSerialNumberString'] = NEW_SERIAL  # two disks report one serial
        with self.assertRaises(target.Refused) as e:
            self.pick(mac)
        self.assertIn('exactly one', str(e.exception))
        mac = self.mac(); mac.whole['disk9']['Internal'] = True
        with self.assertRaises(target.Refused):
            self.pick(mac)
        mac = self.mac(); mac.whole['disk9']['BusProtocol'] = 'Thunderbolt'
        with self.assertRaises(target.Refused):
            self.pick(mac)
        mac = self.mac(); mac.parts['disk9'][0]['MountPoint'] = ''
        with self.assertRaises(target.Refused) as e:
            self.pick(mac)
        self.assertIn('not mounted', str(e.exception))

    def test_denylist_without_data_drives_refused(self):
        mac = self.mac()
        dl = diskinfo.make_denylist([d for d in diskinfo.inventory(mac.run) if d.device == 'disk0'], 't')  # only the internal disk
        with self.assertRaises(target.Refused) as e:
            self.pick(mac, dl=dl)
        self.assertIn('without your data drives', str(e.exception))

    def test_unlisted_drive_attached_refused(self):
        mac = self.mac(); dl = denylist_for(mac, 'disk9', 'disk7')  # disk7 was not attached when the list was made
        with self.assertRaises(target.Refused) as e:
            self.pick(mac, dl=dl)
        self.assertIn('disk7', str(e.exception)); self.assertIn('not on the deny-list', str(e.exception))

    def test_windows_reserved_partition_is_fine(self):
        mac = self.mac()
        mac.parts['disk9'].insert(0, dict(DeviceIdentifier='disk9s0', Content='Microsoft Reserved', Size=16 * 1024 ** 2))
        d, vol = self.pick(mac)
        self.assertEqual(vol['empty'], ['disk9s1'])

    def test_no_denylist_needed_and_data_drives_still_refused(self):
        mac = self.mac()
        d, vol = target.select(diskinfo.inventory(mac.run), NEW_SERIAL, NEW_UUID, None)
        self.assertEqual(d.device, 'disk9')
        t7 = self.t / 'T7'; t7.mkdir(); (t7 / 'Photos 2019').mkdir(); (t7 / 'Photos 2019' / 'a.jpg').write_text('x')
        mac.parts['disk6'][0]['MountPoint'] = str(t7)
        with self.assertRaises(target.Refused) as e:  # a data drive with files, and no deny-list at all
            target.select(diskinfo.inventory(mac.run), 'S6WXNS0T123456A', '6A000000-0000-4000-8000-000000000001', None)
        self.assertIn('holds files', str(e.exception))
        with self.assertRaises(target.Refused) as e:  # the APFS data drive
            target.select(diskinfo.inventory(mac.run), 'NAA1B2C3', '5A000000-0000-4000-8000-000000000001', None)
        self.assertIn('APFS', str(e.exception))

    def test_trash_with_files_counts_as_files(self):
        mac = self.mac()
        (self.t / 'X10' / '.Trashes' / '501').mkdir(parents=True); (self.t / 'X10' / '.fseventsd').mkdir()
        self.pick(mac)  # an empty Trash is fine
        (self.t / 'X10' / '.Trashes' / '501' / 'old tax return.pdf').write_text('x')
        with self.assertRaises(target.Refused):
            self.pick(mac)
        mac = self.mac(); svi = self.t / 'X10' / 'System Volume Information'; svi.mkdir()
        (svi / 'IndexerVolumeGuid').write_text('x'); (svi / 'WPSettings.dat').write_text('x')
        shutil.rmtree(self.t / 'X10' / '.Trashes')
        self.pick(mac)  # Windows' indexer stubs are not files
        (svi / 'restore-point.bin').write_text('x')
        with self.assertRaises(target.Refused):
            self.pick(mac)

    def test_time_machine_volume_refused(self):
        mac = self.mac()
        with self.assertRaises(target.Refused) as e:
            target.select(diskinfo.inventory(mac.run), NEW_SERIAL, NEW_UUID, None, tm_mounts={str(self.t / 'X10')})
        self.assertIn('Time Machine', str(e.exception))
        with self.assertRaises(target.Refused):  # tmutil could not be asked
            target.select(diskinfo.inventory(mac.run), NEW_SERIAL, NEW_UUID, None, tm_mounts=None)

    def test_time_machine_destinations_read(self):
        mac = self.mac()
        self.assertEqual(diskinfo.time_machine_mounts(mac.run), set(), 'no destination: empty set, so the writer does not refuse')
        target.select(diskinfo.inventory(mac.run), NEW_SERIAL, NEW_UUID, None, tm_mounts=diskinfo.time_machine_mounts(mac.run))
        mac.tm = ['/Volumes/TM1', '/Volumes/Backups']
        self.assertEqual(diskinfo.time_machine_mounts(mac.run), {'/Volumes/TM1', '/Volumes/Backups'})

        def failing(argv):
            raise subprocess.CalledProcessError(1, argv)
        self.assertIsNone(diskinfo.time_machine_mounts(failing), 'tmutil failing is unknown, and unknown refuses')

    def test_no_uuid_and_partition_uuid(self):
        mac = self.mac(); mac.parts['disk9'][0]['VolumeUUID'] = ''
        d, _ = target.select(diskinfo.inventory(mac.run), NEW_SERIAL, '9A000000-01', None)  # the partition UUID confirms it
        self.assertEqual(d.device, 'disk9')
        mac.parts['disk9'][0]['DiskUUID'] = ''
        with self.assertRaises(target.Refused) as e:
            target.select(diskinfo.inventory(mac.run), NEW_SERIAL, NEW_UUID, None)
        self.assertIn('erase that drive (and only that drive) as ExFAT', str(e.exception))

    def test_copied_marker_does_not_count(self):
        mac = self.mac(['models'])
        doc = marker.make('data', 'OTHERSERIAL99', NEW_UUID, 'r', 't', 'v')
        (self.t / 'X10' / marker.MARKER_NAME).write_text(json.dumps(doc))
        mac.parts['disk9'][0]['VolumeName'] = 'TURINDATA'
        with self.assertRaises(target.Refused):
            self.pick(mac)
        doc['device_serial'] = NEW_SERIAL; (self.t / 'X10' / marker.MARKER_NAME).write_text(json.dumps(doc))
        d, vol = self.pick(mac)
        self.assertEqual(vol['kit_owned'], ['disk9s1'])

    def test_gpt_above_two_tib(self):
        d = diskinfo.Disk('disk9', size=4 * 1024 ** 4)
        self.assertEqual(target.partition_argv(d)[3], 'GPT')


class Candidates(Tmp):
    def test_lists_only_non_denied_usb_disks(self):
        mac = FakeMac(); dl = self.t / 'dl.json'; dl.write_text(json.dumps(denylist_for(mac, 'disk9')))
        lines = []
        rc = list_candidates.main(['--denylist', str(dl)], run=mac.run, listdir=lambda p: [], out=lines.append)
        text = '\n'.join(lines)
        self.assertEqual(rc, 0); self.assertIn('Candidate disk9', text); self.assertIn(f'--serial {NEW_SERIAL} --volume-uuid {NEW_UUID}', text)
        for dev in ('disk4', 'disk6', 'disk7'):
            self.assertIn(f'{dev}: on the deny-list', text)
        self.assertNotIn('Candidate disk8', text)

    def test_plug_in_finds_the_one_new_disk(self):
        mac = FakeMac(); saved = {'whole': mac.whole.pop('disk9'), 'parts': mac.parts.pop('disk9'), 'usb': mac.usb.pop(3)}
        steps = []

        def ask(prompt):
            steps.append(prompt)
            if len(steps) == 2:  # Ak plugs the SSD in
                mac.whole['disk9'] = saved['whole']; mac.parts['disk9'] = saved['parts']; mac.usb.append(saved['usb'])
            return ''
        lines = []
        rc = list_candidates.main(['--plug-in', '--denylist', str(self.t / 'none.json')], run=mac.run, listdir=lambda p: [],
                                  out=lines.append, ask=ask)
        text = '\n'.join(lines)
        self.assertEqual(rc, 0, text); self.assertIn('Candidate disk9', text); self.assertNotIn('disk6', text)


class Writer(Tmp):
    """The real write path, end to end, against the synthetic Mac: diskutil and bsdtar are fakes into temp folders."""

    def setUp(self):
        super().setUp()
        self.vol = self.t / 'Volumes'; (self.vol / 'X10').mkdir(parents=True)
        self.mac = FakeMac(mounts={'disk9s1': str(self.vol / 'X10')})
        self.dl = self.t / 'dl.json'; self.dl.write_text(json.dumps(denylist_for(self.mac, 'disk9')))
        iso_tree = self.t / 'isotree'
        files = {'casper/vmlinuz': b'kernel', 'EFI/boot/bootx64.efi': b'shim', '.disk/info': b'Ubuntu-Server 24.04.5',
                 'boot/grub/grub.cfg': b'original', 'md5sum.txt': b'original'}
        for rel, data in files.items():
            p = iso_tree / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        self.iso = self.t / 'fake.iso'; self.iso.write_bytes(b'not really an iso')
        ov = self.t / 'overlay'
        over = {'boot/grub/grub.cfg': b'patched', 'md5sum.txt': b'patched', 'nocloud/user-data': b'#cloud-config\n{}',
                'turin/payload/disk_guard.py': b'print(1)'}
        for rel, data in over.items():
            p = ov / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
        self.plan = {'format': wmu.PLAN_FORMAT, 'boot_size': '12G', 'boot_bytes': 12 * 10 ** 9, 'store_bytes': 10 ** 9,
                     'iso': {'path': str(self.iso), 'sha256': sha(self.iso.read_bytes()), 'exclude': ['ubuntu'], 'max_file_bytes': 9,
                             'files': [{'path': k, 'size': len(v), 'sha256': sha(v)} for k, v in files.items() if k not in over]},
                     'overlay': {'dir': str(ov), 'replace_dirs': ['turin', 'nocloud'], 'sha256': 'x',
                                 'files': [{'path': k, 'size': len(v), 'sha256': sha(v)} for k, v in over.items()]}}
        self.plan_path = self.t / 'plan.json'; self.plan_path.write_text(json.dumps(self.plan))
        self.iso_tree, self.destructive = iso_tree, []

    def fake_run(self, argv, check=True):
        self.destructive.append(list(argv))
        if argv[:2] == ['diskutil', 'partitionDisk']:
            dev = argv[2].replace('/dev/', '')
            shutil.rmtree(self.vol / 'X10', ignore_errors=True)
            for n in ('TURINBOOT', 'TURINDATA'): (self.vol / n).mkdir(exist_ok=True)
            self.mac.partition(dev, str(self.vol / 'TURINBOOT'), str(self.vol / 'TURINDATA'))
        elif argv[0] == 'bsdtar':
            shutil.copytree(self.iso_tree, argv[argv.index('-C') + 1], dirs_exist_ok=True)
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0)

    def writer(self, answers):
        out = []
        w = wmu.Writer(run=self.fake_run, inventory=lambda: diskinfo.inventory(self.mac.run), ask=lambda _p: answers.pop(0),
                       out=out.append, sleep=lambda s: None, wait_seconds=0, volumes_prefix=str(self.vol),
                       tm=lambda: diskinfo.time_machine_mounts(self.mac.run), guard=lambda: None)
        return w, out

    def main(self, extra, answers=()):
        w, out = self.writer(list(answers))
        rc = wmu.main(['--serial', NEW_SERIAL, '--volume-uuid', NEW_UUID, '--denylist', str(self.dl), '--plan', str(self.plan_path)] + extra,
                      writer=w)
        return rc, '\n'.join(out)

    def test_dry_run_writes_nothing(self):
        rc, out = self.main([])
        self.assertEqual(rc, 0); self.assertIn('DRY RUN', out); self.assertEqual(self.destructive, [])
        self.assertIn('diskutil partitionDisk /dev/disk9 MBR FAT32 TURINBOOT 12G ExFAT TURINDATA R', out)

    def test_write_end_to_end(self):
        rc, out = self.main(['--write'], ['ERASE ' + NEW_SERIAL])
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.destructive[0], ['diskutil', 'partitionDisk', '/dev/disk9', 'MBR', 'FAT32', 'TURINBOOT', '12G',
                                               'ExFAT', 'TURINDATA', 'R'])
        self.assertEqual(self.destructive[1][:4], ['bsdtar', '-xf', str(self.iso), '-C'])
        self.assertEqual(len(self.destructive), 2, 'exactly one partition command and one extraction')
        boot = marker.read(str(self.vol / 'TURINBOOT')); data = marker.read(str(self.vol / 'TURINDATA'))
        self.assertEqual((boot['role'], boot['status'], boot['device_serial']), ('boot', 'complete', NEW_SERIAL))
        self.assertEqual(data['volume_uuid'], 'D0000009-0000-4000-8000-00000000D002')
        self.assertEqual((self.vol / 'TURINBOOT/boot/grub/grub.cfg').read_bytes(), b'patched')
        self.assertIn('stage_store.py --serial ' + NEW_SERIAL, out)
        # now it is the kit's own disk: a second --write needs --wipe-store; --update-boot keeps the models
        (self.vol / 'TURINDATA' / 'turin-store').mkdir()
        rc, out = self.main_uuid('B0000009-0000-4000-8000-00000000B001', ['--write'], ['ERASE ' + NEW_SERIAL])
        self.assertEqual(rc, 3); self.assertIn('--wipe-store', out)
        self.destructive.clear()
        (self.vol / 'TURINBOOT/turin/payload/stale.py').write_text('old')
        rc, out = self.main_uuid('B0000009-0000-4000-8000-00000000B001', ['--update-boot'], ['UPDATE ' + NEW_SERIAL])
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.destructive, [], 'update-boot: no partitioning, no re-extraction of an unchanged ISO')
        self.assertFalse((self.vol / 'TURINBOOT/turin/payload/stale.py').exists())
        self.assertTrue((self.vol / 'TURINDATA' / 'turin-store').is_dir(), 'models stay')

    def main_uuid(self, uuid, extra, answers):
        w, out = self.writer(list(answers))
        rc = wmu.main(['--serial', NEW_SERIAL, '--volume-uuid', uuid, '--denylist', str(self.dl), '--plan', str(self.plan_path)] + extra,
                      writer=w)
        return rc, '\n'.join(out)

    def test_wrong_confirmation_writes_nothing(self):
        rc, out = self.main(['--write'], ['ERASE disk9'])
        self.assertEqual(rc, 3); self.assertEqual(self.destructive, []); self.assertIn('not confirmed', out)

    def test_disk_swapped_after_confirmation(self):
        w, out = self.writer(['ERASE ' + NEW_SERIAL])
        orig = w.ask

        def swap(prompt):
            self.mac.whole['disk9']['TotalSize'] += 512  # a different disk now answers at the same node
            return orig(prompt)
        w.ask = swap
        rc = wmu.main(['--serial', NEW_SERIAL, '--volume-uuid', NEW_UUID, '--denylist', str(self.dl), '--plan', str(self.plan_path),
                       '--write'], writer=w)
        self.assertEqual(rc, 3); self.assertEqual(self.destructive, []); self.assertIn('changed', '\n'.join(out))

    def test_corrupt_readback_reported(self):
        def bad_run(argv, check=True):
            r = self.fake_run(argv, check)
            if argv[0] == 'bsdtar':
                (self.vol / 'TURINBOOT/casper/vmlinuz').write_bytes(b'flipped')
            return r
        w, out = self.writer(['ERASE ' + NEW_SERIAL]); w.run = bad_run
        rc = wmu.main(['--serial', NEW_SERIAL, '--volume-uuid', NEW_UUID, '--denylist', str(self.dl), '--plan', str(self.plan_path),
                       '--write'], writer=w)
        self.assertEqual(rc, 3); self.assertIn('casper/vmlinuz', '\n'.join(out))
        self.assertEqual(marker.read(str(self.vol / 'TURINBOOT'))['status'], 'writing', 'an unfinished USB is never marked complete')

    def test_works_without_a_denylist(self):
        self.dl.unlink()
        rc, out = self.main(['--write'], ['ERASE ' + NEW_SERIAL])
        self.assertEqual(rc, 0, out); self.assertNotIn('not on the deny-list', out)

    def test_seatbelt(self):
        class Tty:
            def __init__(self, t): self.t = t
            def isatty(self): return self.t
        with self.assertRaises(target.Refused):
            wmu.seatbelt(env={'CLAUDECODE': '1'}, stdin=Tty(True))
        with self.assertRaises(target.Refused):
            wmu.seatbelt(env={'CODEX_SANDBOX': 'x'}, stdin=Tty(True))
        with self.assertRaises(target.Refused):
            wmu.seatbelt(env={}, stdin=Tty(False))
        wmu.seatbelt(env={'HOME': '/Users/ak'}, stdin=Tty(True))
        w, out = self.writer(['ERASE ' + NEW_SERIAL]); w.guard = lambda: (_ for _ in ()).throw(target.Refused('agent'))
        rc = wmu.main(['--serial', NEW_SERIAL, '--volume-uuid', NEW_UUID, '--plan', str(self.plan_path), '--write'], writer=w)
        self.assertEqual(rc, 3); self.assertEqual(self.destructive, [], 'the seatbelt stops before anything is written')


from test_build_and_server import *  # noqa: E402,F401,F403
from test_mac import *  # noqa: E402,F401,F403

if __name__ == '__main__':
    unittest.main(verbosity=2)
