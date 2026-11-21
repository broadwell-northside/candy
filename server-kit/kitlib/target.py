"""Pure decision logic for the master-USB writer: which disk (if any) may be written, and why not.

No size rule: a 1-2 TB USB SSD looks exactly like Ak's data drives. The target is chosen only by the device serial
and a volume (or partition) UUID that Ak confirms for this run, and it must also pass every refusal below. A deny-list
is optional (Ak declined an inventory of his drives, AK-CANDY-REVIEWER-ANSWERS-20261106); safety does not depend on it:
any disk that holds files without this kit's marker, any APFS or Time Machine volume, and any filesystem the writer
cannot inspect is refused on its own.
"""
import os

from . import diskinfo, marker

ALLOWED_BUS = {'USB'}
MBR_LIMIT = 2 * 1024 ** 4  # MBR addresses up to 2 TiB; bigger disks use GPT


class Refused(Exception):
    pass


def check_volumes(disk, listdir=os.listdir, read_marker=marker.read, tm_mounts=frozenset()):
    """Return {'kit_owned': [...], 'empty': [...]} or raise Refused if any volume may hold someone's files."""
    owned, empty = [], []
    for v in disk.volumes:
        if v.filesystem == 'apfs' or v.content in ('Apple_APFS', 'EF57347C-0000-11AA-AA11-00306543ECAC'):
            raise Refused(f'{v.device} is an APFS volume. Macs keep data and Time Machine backups (also in snapshots the '
                          'Finder does not show) on APFS, so the writer never erases one. Nothing was written.')
        if v.mount_point and v.mount_point in (tm_mounts or ()):
            raise Refused(f'{v.device} is a Time Machine backup destination; nothing was written')
        if v.is_small_efi() and not v.mount_point:
            continue  # the hidden EFI partition macOS adds to GPT disks; never holds user files
        if v.is_microsoft_reserved() and not v.mount_point:
            continue  # Windows' 16-128 MB reserved partition on factory-formatted drives; no filesystem, no files
        if not v.mount_point:
            if v.volume_uuid or v.filesystem or v.content not in ('', 'Free Space'):
                raise Refused(f'{v.device} has a filesystem that is not mounted, so the writer cannot check it for files. '
                              'Nothing was written. Use a drive whose volumes show up in Finder, or a brand-new drive.')
            continue
        doc = read_marker(v.mount_point)
        role = 'boot' if v.volume_name == marker.BOOT_LABEL else 'data' if v.volume_name == marker.DATA_LABEL else None
        if doc is not None and role and not marker.problems(doc, disk.serial, v.volume_uuid, role):
            owned.append(v.device)  # the kit's own volume, whatever it holds
            continue
        names = user_entries_safe(v.mount_point, listdir)
        if not names:
            empty.append(v.device)
            continue
        raise Refused(f'{v.device} ("{v.volume_name or "untitled"}") holds files ({len(names)} top-level items) and is not the '
                      'kit\'s own master USB. Nothing was written. If this really is the new, empty USB SSD you bought for the '
                      'server (new drives often come with the maker\'s software on them), copy off anything you want, delete '
                      'its files in Finder, empty the Trash, then run this again.')
    return {'kit_owned': owned, 'empty': empty}


def user_entries_safe(mount_point, listdir):
    try:
        return marker.user_entries(mount_point, listdir)
    except OSError as e:
        raise Refused(f'cannot list {mount_point} ({e}); nothing was written')


def select(disks, serial, volume_uuid, denylist=None, need_bytes=0, listdir=os.listdir, read_marker=marker.read,
           tm_mounts=frozenset()):
    """The one disk that may be written, plus the reasons it passed. Raises Refused otherwise."""
    want = diskinfo.norm_serial(serial)
    if not want or diskinfo.serial_is_degenerate(want):
        raise Refused('a real device serial is required (the one list_candidates.py shows for the new USB SSD)')
    if not volume_uuid:
        raise Refused('the volume UUID that list_candidates.py shows for the new USB SSD is required')
    if tm_mounts is None:
        raise Refused('could not ask macOS which disks hold Time Machine backups (tmutil); nothing was written')
    if denylist is not None and not any(not r.get('internal', True) for r in denylist.get('disks', [])):
        raise Refused('the deny-list holds no external drive, so it was made without your data drives attached. Unplug the '
                      'new USB SSD, attach your data drives, run make_denylist.py again. Nothing was written.')
    hits = [d for d in disks if want in [diskinfo.norm_serial(s) for s in d.serials]]
    if len(hits) != 1:
        raise Refused(f'expected exactly one attached disk with serial {serial!r}, found {len(hits)}; nothing was written')
    d = hits[0]
    if d.internal:
        raise Refused(f'{d.device} is an internal disk; nothing was written')
    if d.virtual:
        raise Refused(f'{d.device} is a disk image or synthesized volume, not a physical USB disk; nothing was written')
    if d.bus not in ALLOWED_BUS:
        raise Refused(f'{d.device} is on {d.bus or "an unknown bus"}, not USB; nothing was written')
    if d.mounted_at_system_path():
        raise Refused(f'{d.device} holds a system volume; nothing was written')
    if diskinfo.serial_is_degenerate(d.serial) or diskinfo.norm_serial(d.serial) != want:
        raise Refused(f'{d.device} reports a generic or ambiguous serial; nothing was written')
    uuids = {v.volume_uuid.upper() for v in d.volumes if v.volume_uuid} | {v.disk_uuid.upper() for v in d.volumes if v.disk_uuid}
    if not uuids:
        raise Refused(f'{d.device} reports no volume or partition UUID, so it cannot be confirmed. In Disk Utility, erase that '
                      'drive (and only that drive) as ExFAT with any name, then run list_candidates.py again. Nothing was written.')
    if volume_uuid.upper() not in uuids:
        raise Refused(f'the disk with serial {serial} has no volume with UUID {volume_uuid}; it may have been swapped or '
                      'reformatted. Run list_candidates.py again and use what it shows now. Nothing was written.')
    hit = diskinfo.denied_by(d, denylist) if denylist else []
    if hit:
        raise Refused(f'{d.device} matches the deny-list ({", ".join(hit[:3])}); it is one of the drives that were attached '
                      'when the deny-list was made. Nothing was written.')
    unknown = [x for x in disks if denylist and x is not d and not x.internal and not x.virtual and not diskinfo.denied_by(x, denylist)]
    if unknown:
        x = unknown[0]
        raise Refused(f'{x.device} ({x.media_name or "?"}, {x.size / 1e9:.0f} GB, serial {x.serial or "none"}) is attached but is '
                      'not on the deny-list. Unplug it, or add it by running make_denylist.py with it attached and the new '
                      'USB SSD unplugged. Nothing was written.')
    if need_bytes and d.size < need_bytes:
        raise Refused(f'{d.device} holds {d.size} bytes but the plan needs {need_bytes}; nothing was written')
    vol = check_volumes(d, listdir, read_marker, tm_mounts)
    return d, vol


def partition_argv(disk, boot_size='12G'):
    scheme = 'MBR' if disk.size <= MBR_LIMIT else 'GPT'
    return ['diskutil', 'partitionDisk', '/dev/' + disk.device, scheme,
            'FAT32', marker.BOOT_LABEL, boot_size, 'ExFAT', marker.DATA_LABEL, 'R']


def same_identity(before, after):
    """Re-check right before writing: same node, serial, size and volume UUIDs as when Ak confirmed."""
    return (before.device == after.device and diskinfo.norm_serial(before.serial) == diskinfo.norm_serial(after.serial)
            and before.size == after.size and before.bus == after.bus and before.media_name == after.media_name
            and sorted(v.volume_uuid for v in before.volumes) == sorted(v.volume_uuid for v in after.volumes))
