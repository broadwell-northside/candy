"""Read-only macOS disk inventory: who is who, by serial number and UUIDs.

Everything here only READS. The commands are `diskutil list -plist`, `diskutil info -plist <id>`, `ioreg -a -l -r -c
<class>` and `system_profiler SPNVMeDataType -json`. Nothing mounts, unmounts, erases or writes a disk.

Every command goes through an injectable `run(argv) -> bytes`, so the tests feed captured or synthetic output and
never touch a real disk.

Identity model (used by the deny-list and the USB writer):
  serial:<S>        device serial from the IORegistry (USB serial, SCSI/NVMe serial). The strongest key.
  disk_uuid:<U>     each partition's GUID/UUID (diskutil DiskUUID).
  volume_uuid:<U>   each filesystem's UUID (diskutil VolumeUUID), including APFS volumes in a synthesized container.
  media:<name>|<n>  media name + exact byte size. Only recorded for disks with no readable serial, so they stay
                    covered even if they are reformatted.
"""
import json
import plistlib
import re
import subprocess
from dataclasses import dataclass, field

SERIAL_KEYS = ('USB Serial Number', 'kUSBSerialNumberString', 'Serial Number')
IOREG_CLASSES = ('IOUSBHostDevice', 'IONVMeController')
# Serials that cheap USB bridges report for every unit; they identify nothing.
DEGENERATE = re.compile(r'^(?:0+|F+|1234567890(?:ABCDEF)?|0123456789(?:ABCDEF)?|(?P<c>.)(?P=c)+|[0-9A-F]{0,5})$')
EFI_TYPE = 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B'
MSR_TYPE = 'E3C9E316-0B5C-4DB8-817D-F92DF00215AE'


def real_run(argv):
    """Run a READ-ONLY inventory command. Only these four tools are allowed through here."""
    ok = (argv[0] in ('ioreg', 'system_profiler') or (argv[0] == 'diskutil' and argv[1] in ('list', 'info'))
          or argv[:3] == ['tmutil', 'destinationinfo', '-X'])
    if not ok:
        raise ValueError('diskinfo only runs read-only inventory commands, not %r' % (argv,))
    return subprocess.run(argv, check=True, capture_output=True, timeout=120).stdout


def norm_serial(s):
    return re.sub(r'\s+', '', str(s or '')).upper()


def serial_is_degenerate(s):
    return bool(DEGENERATE.match(norm_serial(s)))


@dataclass
class Volume:
    device: str
    content: str = ''
    size: int = 0
    disk_uuid: str = ''
    volume_uuid: str = ''
    volume_name: str = ''
    mount_point: str = ''
    filesystem: str = ''

    def is_small_efi(self):
        return (self.content.upper() in ('EFI', EFI_TYPE) or self.volume_name == 'EFI') and 0 < self.size <= 1024 ** 3

    def is_microsoft_reserved(self):
        return (self.content in ('Microsoft Reserved', MSR_TYPE)) and not self.volume_uuid and 0 < self.size <= 128 * 1024 ** 2


@dataclass
class Disk:
    device: str
    bus: str = ''
    internal: bool = True
    virtual: bool = False
    size: int = 0
    media_name: str = ''
    content: str = ''
    serials: list = field(default_factory=list)
    volumes: list = field(default_factory=list)

    @property
    def serial(self):
        """The serial Ak confirms: the first non-degenerate one (USB device serial comes first)."""
        good = [s for s in self.serials if not serial_is_degenerate(s)]
        return good[0] if good else ''

    def identifiers(self):
        ids = {'serial:' + norm_serial(s) for s in self.serials if norm_serial(s)}
        for v in self.volumes:
            if v.disk_uuid: ids.add('disk_uuid:' + v.disk_uuid.upper())
            if v.volume_uuid: ids.add('volume_uuid:' + v.volume_uuid.upper())
        if not self.serial:
            ids.add('media:%s|%d' % (self.media_name, self.size))
        return ids

    def mounted_at_system_path(self):
        return any(v.mount_point == '/' or v.mount_point.startswith('/System/Volumes') for v in self.volumes)

    def summary(self):
        return {'device': self.device, 'bus': self.bus, 'internal': self.internal, 'virtual': self.virtual,
                'size_bytes': self.size, 'media_name': self.media_name, 'serial': self.serial,
                'all_serials': list(self.serials),
                'volumes': [{'device': v.device, 'filesystem': v.filesystem or v.content, 'volume_uuid': v.volume_uuid,
                             'disk_uuid': v.disk_uuid, 'mounted': bool(v.mount_point), 'size_bytes': v.size}
                            for v in self.volumes]}


def _plist(run, argv):
    out = run(argv)
    return plistlib.loads(out) if out and out.strip() else {}


def _walk_serials(node, inherited, out):
    """Map every descendant `BSD Name` to the serials found on it or on its ancestors (closest last)."""
    if isinstance(node, list):
        for n in node: _walk_serials(n, inherited, out)
        return
    if not isinstance(node, dict):
        return
    found = list(inherited)
    for k in SERIAL_KEYS:
        v = node.get(k)
        if isinstance(v, str) and v.strip() and norm_serial(v) not in [norm_serial(x) for x in found]:
            found.append(v.strip())
    chars = node.get('Device Characteristics')
    if isinstance(chars, dict):
        v = chars.get('Serial Number')
        if isinstance(v, str) and v.strip() and norm_serial(v) not in [norm_serial(x) for x in found]:
            found.append(v.strip())
    bsd = node.get('BSD Name')
    if isinstance(bsd, str) and bsd:
        whole = re.match(r'(disk\d+)', bsd).group(1)
        for s in found:
            if norm_serial(s) not in [norm_serial(x) for x in out.setdefault(whole, [])]:
                out[whole].append(s)
    for child in node.get('IORegistryEntryChildren', []) or []:
        _walk_serials(child, found, out)


def serial_map(run):
    """{'disk7': ['USBSERIAL', 'INNERSERIAL'], ...} from the IORegistry and the NVMe system profile."""
    out = {}
    for cls in IOREG_CLASSES:
        try:
            tree = _plist(run, ['ioreg', '-a', '-l', '-r', '-c', cls])
        except (subprocess.CalledProcessError, plistlib.InvalidFileException, ValueError):
            continue
        _walk_serials(tree, [], out)
    try:
        prof = json.loads(run(['system_profiler', 'SPNVMeDataType', '-json']) or b'{}')
    except (subprocess.CalledProcessError, ValueError):
        prof = {}
    for bus in prof.get('SPNVMeDataType', []) or []:
        for item in bus.get('_items', []) or []:
            bsd, s = item.get('bsd_name'), item.get('device_serial')
            if bsd and s:
                whole = re.match(r'(disk\d+)', bsd).group(1)
                if norm_serial(s) not in [norm_serial(x) for x in out.setdefault(whole, [])]:
                    out[whole].append(s)
    return out


def inventory(run=real_run):
    """Every whole disk with its partitions/volumes and serials. Synthesized APFS containers are folded into the
    physical disk that backs them, so a data drive's APFS volume UUIDs count as that drive's identifiers."""
    lst = _plist(run, ['diskutil', 'list', '-plist'])
    serials = serial_map(run)
    info = {}

    def get(dev):
        if dev not in info:
            try:
                info[dev] = _plist(run, ['diskutil', 'info', '-plist', dev])
            except subprocess.CalledProcessError:
                info[dev] = {}
        return info[dev]

    disks, store_owner = {}, {}
    entries = lst.get('AllDisksAndPartitions', []) or []
    for e in entries:
        dev = e['DeviceIdentifier']
        i = get(dev)
        synthesized = bool(e.get('APFSPhysicalStores')) or i.get('VirtualOrPhysical') == 'Virtual' and i.get('APFSContainerReference') == dev
        d = Disk(device=dev, bus=i.get('BusProtocol', ''), internal=bool(i.get('Internal', True)),
                 virtual=i.get('VirtualOrPhysical') == 'Virtual' or i.get('BusProtocol') == 'Disk Image',
                 size=int(i.get('TotalSize') or i.get('Size') or e.get('Size') or 0),
                 media_name=i.get('MediaName') or i.get('IORegistryEntryName') or '', content=e.get('Content', ''),
                 serials=list(serials.get(dev, [])))
        for p in (e.get('Partitions') or []) + (e.get('APFSVolumes') or []):
            pi = get(p['DeviceIdentifier'])
            d.volumes.append(Volume(device=p['DeviceIdentifier'], content=p.get('Content', '') or pi.get('Content', ''),
                                    size=int(p.get('Size') or pi.get('TotalSize') or 0),
                                    disk_uuid=p.get('DiskUUID') or pi.get('DiskUUID') or '',
                                    volume_uuid=p.get('VolumeUUID') or pi.get('VolumeUUID') or '',
                                    volume_name=p.get('VolumeName') or pi.get('VolumeName') or '',
                                    mount_point=p.get('MountPoint') or pi.get('MountPoint') or '',
                                    filesystem=pi.get('FilesystemType') or ''))
        if synthesized:
            for st in e.get('APFSPhysicalStores') or []:
                store = st.get('DeviceIdentifier') or st.get('APFSPhysicalStore') or ''
                m = re.match(r'(disk\d+)', store)
                if m: store_owner[dev] = m.group(1)
        disks[dev] = d
    for synth, owner in store_owner.items():
        if owner in disks and synth in disks and synth != owner:
            disks[owner].volumes.extend(disks[synth].volumes)
            for s in disks[synth].serials:
                if s not in disks[owner].serials: disks[owner].serials.append(s)
            disks[synth].virtual = True
    return [disks[k] for k in sorted(disks, key=lambda x: int(x[4:]))]


def time_machine_mounts(run=real_run):
    """Mount points of every Time Machine destination macOS knows (`tmutil destinationinfo -X`, read-only)."""
    try:
        doc = _plist(run, ['tmutil', 'destinationinfo', '-X'])
    except (subprocess.CalledProcessError, plistlib.InvalidFileException, ValueError, OSError):
        return None  # unknown
    return {d['MountPoint'] for d in doc.get('Destinations', []) if d.get('MountPoint')}


# ---------------------------------------------------------------- deny-list (optional: Ak declined an inventory)
DENYLIST_FORMAT = 'candy-server-kit.disk-denylist/1'


def make_denylist(disks, generated_at, host=''):
    """Every physical disk attached right now, internal ones included, by every identifier it has."""
    rows, warnings = [], []
    for d in disks:
        if d.virtual:
            continue
        ids = sorted(d.identifiers())
        if not d.serial:
            warnings.append(f'{d.device}: no readable device serial; it is denied by its UUIDs and media name + size')
        if not any(i.startswith(('volume_uuid:', 'disk_uuid:')) for i in ids):
            warnings.append(f'{d.device}: no partition or volume UUIDs; it is denied by serial or media name + size only')
        rows.append({'device_at_generation': d.device, 'internal': d.internal, 'bus': d.bus, 'size_bytes': d.size,
                     'serial': d.serial, 'identifiers': ids})
    return {'format': DENYLIST_FORMAT, 'generated_at': generated_at, 'host': host, 'disks': rows,
            'counts': {'disks': len(rows), 'external': sum(1 for r in rows if not r['internal'])}, 'warnings': warnings}


def load_denylist(text):
    doc = json.loads(text)
    if doc.get('format') != DENYLIST_FORMAT or not isinstance(doc.get('disks'), list):
        raise ValueError('not a Candy server kit deny-list')
    if not doc['disks']:
        raise ValueError('the deny-list is empty; generate it while your data drives are attached')
    return doc


def denied_by(disk, denylist):
    """Identifiers this disk shares with any deny-listed disk (empty list = not denied)."""
    banned = set()
    for row in denylist['disks']:
        banned.update(row.get('identifiers', []))
    return sorted(disk.identifiers() & banned)
