"""The master USB's own marker, and the "does this volume hold anyone's files?" check.

A volume counts as the kit's own only when its marker names THIS device's serial and THIS volume's current UUID.
A marker copied from another drive fails both checks.
"""
import json
import os

MARKER_NAME = 'TURIN-MASTER-USB.json'
FORMAT = 'candy-server-kit.master-usb/1'
BOOT_LABEL = 'TURINBOOT'
DATA_LABEL = 'TURINDATA'
# What macOS and Windows create on their own on any mounted volume and that never holds anyone's files.
CLUTTER = {'.Spotlight-V100', '.fseventsd', '.PKInstallSandboxManager', '.DS_Store', '.metadata_never_index',
           '.metadata_never_index_unless_rootfs', '.apdisk', '.VolumeIcon.icns'}
# Folders that are normally empty but CAN hold someone's files (a Trash, Windows' recycle bin, version history, fsck
# leftovers): they count as files unless they are empty. Windows' indexer stubs in System Volume Information are fine.
TRASHY = {'.Trashes', '$RECYCLE.BIN', 'lost+found', 'System Volume Information', '.DocumentRevisions-V100', '.TemporaryItems'}
HARMLESS_FILES = {'.DS_Store', 'desktop.ini', 'IndexerVolumeGuid', 'WPSettings.dat', 'tracking.log'}


def make(role, serial, volume_uuid, run_id, created, kit_version):
    if role not in ('boot', 'data'):
        raise ValueError('role must be boot or data')
    return {'format': FORMAT, 'kit': 'candy-server-kit', 'role': role, 'device_serial': serial,
            'volume_uuid': volume_uuid.upper(), 'run_id': run_id, 'created': created, 'kit_version': kit_version}


def problems(doc, serial, volume_uuid, role=None):
    """Why this marker does NOT prove the volume is the kit's own ([] = it does)."""
    from .diskinfo import norm_serial
    why = []
    if not isinstance(doc, dict) or doc.get('format') != FORMAT:
        return ['not a Candy master-USB marker']
    if norm_serial(doc.get('device_serial')) != norm_serial(serial) or not serial:
        why.append('marker names a different device serial')
    if str(doc.get('volume_uuid', '')).upper() != str(volume_uuid or '').upper() or not volume_uuid:
        why.append('marker names a different volume UUID')
    if role and doc.get('role') != role:
        why.append(f'marker role is {doc.get("role")!r}, expected {role!r}')
    return why


def read(mount_point):
    try:
        with open(os.path.join(mount_point, MARKER_NAME), 'rb') as f:
            return json.loads(f.read(65536))
    except (OSError, ValueError):
        return None


def holds_files(path, uid=None):
    """True if a TRASHY folder holds any file (read-only walk). A folder that cannot be read counts as holding files,
    except macOS's root-owned .Trashes, which is judged by the current user's own trash inside it."""
    uid = os.getuid() if uid is None else uid
    errors = []
    for root, dirs, files in os.walk(path, onerror=errors.append):
        if [f for f in files if f not in HARMLESS_FILES and not f.startswith('._')]:
            return True
    if errors:
        if os.path.basename(path) == '.Trashes' and all(isinstance(e, PermissionError) and e.filename == path for e in errors):
            own = os.path.join(path, str(uid))
            return os.path.isdir(own) and holds_files(own, uid)
        return True
    return False


def user_entries(mount_point, listdir=os.listdir):
    """Top-level names on a mounted volume that may be someone's files (read-only). OS clutter is ignored; a Trash,
    recycle bin or similar counts only when it holds files."""
    out = []
    for n in listdir(mount_point):
        if n in CLUTTER or n.startswith('._') or n == MARKER_NAME:
            continue
        if n in TRASHY and not holds_files(os.path.join(mount_point, n)):
            continue
        out.append(n)
    return sorted(out)
