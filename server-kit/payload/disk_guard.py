#!/usr/bin/env python3
"""Installer early-command: choose the OS NVMe BEFORE Subiquity probes or partitions anything.

    python3 disk_guard.py --select-blank-nvme /cdrom/turin/config/install.json   (os_disk_mode auto_single_blank_nvme)
    python3 disk_guard.py --exact-serial      /cdrom/turin/config/install.json   (os_disk_mode exact_serial)

Mode 1 (auto_single_blank_nvme, brand-new build): succeeds ONLY when the machine has exactly one NVMe disk and it is
completely blank (no partitions, filesystem, RAID/LVM member, label incl. *KEEP*, mount, wipefs/blkid signature) and
>= 250 GB. Zero NVMe, any non-blank NVMe or more than one NVMe => hard abort, nothing touched.
Mode 2 (exact_serial): the single NVMe whose serial equals the configured one, with the same blank checks.
On success it writes /autoinstall-storage.yaml (audit copy) and rewrites the storage section of /autoinstall.yaml,
which Subiquity re-reads after early-commands, to match that disk by udev ID_SERIAL *and* kernel path.
Any failure exits non-zero, which aborts the autoinstall before storage is touched.
"""
import json, pathlib, re, subprocess, sys

MIN_BYTES = 250 * 1000 ** 3
KIT_LABELS = {'TURINBOOT', 'TURINDATA'}  # the master USB's own volumes: never an install target
GLOB = re.compile(r'[*?\[\]]')
AUTOINSTALL = pathlib.Path('/autoinstall.yaml')
AUDIT = pathlib.Path('/autoinstall-storage.yaml')


class Refused(ValueError):
    pass


def truthy(v):
    return v in (True, 1, '1', 'true', 'True')


def nvme_disks(devices):
    """Internal NVMe disks only: transport exactly `nvme` (a USB enclosure reports `usb`; a missing transport is refused),
    not removable, and not the master USB, whatever their name. The hotplug flag is NOT used: the board's BIOS switch
    "PCIE Hotplug" covers M2_1/M2_2 and would mark the real OS disk hot-pluggable."""
    return [d for d in devices if d.get('type') == 'disk' and str(d.get('name', '')).startswith('nvme')
            and d.get('tran') == 'nvme' and not truthy(d.get('rm')) and not kit_volume(d)]


def kit_volume(d):
    """True if this disk or any of its partitions carries the master USB's labels."""
    for node in [d] + list(d.get('children') or []):
        if str(node.get('label') or '').upper() in KIT_LABELS or str(node.get('partlabel') or '').upper() in KIT_LABELS:
            return True
    return False


def blank_problems(d):
    why = []
    if d.get('children'): why.append('has partitions')
    for k in ('fstype', 'label', 'partlabel', 'pttype', 'mountpoint'):
        if d.get(k): why.append(f'{k}={d[k]}')
    if any(m for m in (d.get('mountpoints') or []) if m): why.append('mounted')
    if 'KEEP' in str(d.get('label') or '').upper(): why.append('KEEP label')
    if int(d.get('size') or 0) < MIN_BYTES: why.append(f'smaller than 250 GB ({int(d.get("size") or 0)} bytes)')
    return why


def choose(c, devices):
    """Pure selection logic (unit-tested). Returns the lsblk dict of the one disk to install to."""
    mode = c.get('os_disk_mode', 'exact_serial')
    if c.get('approve_blank_disk_install') is not True: raise Refused('Blank-disk installation was not approved in the Mac wizard')
    disks = nvme_disks(devices)
    if not disks: raise Refused('No internal NVMe disk found (USB and removable disks are never used). Install one blank NVMe SSD in M2_1 or M2_2; nothing was touched.')
    if mode == 'auto_single_blank_nvme':
        if len(disks) != 1:
            desc = ', '.join(f"{d['name']} serial={str(d.get('serial') or '').strip() or '?'} {'blank' if not blank_problems(d) else 'NOT blank'}" for d in disks)
            raise Refused(f'{len(disks)} NVMe disks present ({desc}). Automatic mode only installs when exactly one blank NVMe exists; '
                          're-run the Mac wizard and choose option 2 with the exact serial. Nothing was touched.')
        target = disks[0]
    elif mode == 'exact_serial':
        serial = str(c.get('os_disk_serial', '')).strip()
        if not serial or GLOB.search(serial): raise Refused('Exact NVMe serial missing or contains glob characters')
        hits = [d for d in disks if str(d.get('serial') or '').strip() == serial]
        if len(hits) != 1: raise Refused(f'Expected exactly one NVMe with serial {serial!r}, found {len(hits)}; nothing was touched.')
        target = hits[0]
    else:
        raise Refused(f'Unknown os_disk_mode {mode!r}')
    why = blank_problems(target)
    if why: raise Refused(f"/dev/{target['name']} is not blank ({'; '.join(why)}). Existing data is NEVER erased automatically; nothing was touched.")
    return target


def udev_serial(path, run=subprocess.check_output):
    props = dict(line.split('=', 1) for line in run(['udevadm', 'info', '--query=property', '--name=' + path], text=True).splitlines() if '=' in line)
    s = props.get('ID_SERIAL', '').strip()
    if not s or GLOB.search(s): raise Refused(f'No usable udev ID_SERIAL for {path}')
    return s


def blkid_probe(path, run=subprocess.check_output):
    """Low-level superblock probe; blkid exits 2 when it finds nothing, i.e. the disk is blank."""
    try:
        return run(['blkid', '-p', '-o', 'export', path], text=True).strip()
    except subprocess.CalledProcessError as e:
        if e.returncode == 2: return ''
        raise


def storage_for(path, id_serial):
    return {'layout': {'name': 'direct', 'match': {'serial': id_serial, 'path': path}}}


def patch_autoinstall(text, storage):
    try:
        import yaml
        doc, dump = yaml.safe_load(text), (lambda d: yaml.safe_dump(d, sort_keys=False))
    except ImportError:  # JSON is valid YAML; the builder emits JSON, Subiquity may re-emit YAML
        doc, dump = json.loads(text), (lambda d: json.dumps(d, indent=2))
    inner = doc['autoinstall'] if isinstance(doc, dict) and 'autoinstall' in doc else doc
    inner['storage'] = storage
    return dump(doc)


def main(argv=None, run=subprocess.check_output, autoinstall=AUTOINSTALL, audit=AUDIT):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in ('--select-blank-nvme', '--exact-serial'):
        print(__doc__); return 2
    c = json.loads(pathlib.Path(argv[1]).read_text())
    c['os_disk_mode'] = 'auto_single_blank_nvme' if argv[0] == '--select-blank-nvme' else 'exact_serial'
    try:
        devices = json.loads(run(['lsblk', '-J', '-b', '-o', 'NAME,TYPE,SERIAL,MODEL,SIZE,FSTYPE,LABEL,PARTLABEL,PTTYPE,MOUNTPOINT,MOUNTPOINTS,TRAN,RM,HOTPLUG'], text=True))['blockdevices']
        d = choose(c, devices); path = '/dev/' + d['name']
        sigs = json.loads(run(['wipefs', '--json', '--no-act', path], text=True) or '{}').get('signatures', [])
        if sigs: raise Refused(f'{path} has on-disk signatures {sigs}; nothing was touched.')
        probe = blkid_probe(path, run)
        if probe: raise Refused(f'{path}: blkid found {probe.split()[:3]}; nothing was touched.')
        storage = storage_for(path, udev_serial(path, run))
    except subprocess.CalledProcessError as e:
        print('TURIN DISK GUARD: probe failed (nothing was touched):', e, file=sys.stderr); return 3
    except Refused as e:
        print('TURIN DISK GUARD REFUSED:', e, file=sys.stderr); return 4
    audit.write_text(json.dumps({'selected': path, 'model': d.get('model'), 'size_bytes': int(d['size']), 'storage': storage}, indent=2) + '\n')
    autoinstall.write_text(patch_autoinstall(autoinstall.read_text(), storage))
    print(f'TURIN DISK GUARD: installing Ubuntu to blank {path} ({int(d["size"]) / 1e9:.0f} GB, {d.get("model") or "?"}, ID_SERIAL {storage["layout"]["match"]["serial"]})')
    return 0


if __name__ == '__main__': sys.exit(main())
