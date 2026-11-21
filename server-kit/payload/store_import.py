#!/usr/bin/env python3
"""Installer late-command: copy the master USB's store onto the new system, checking every byte.

    python3 /cdrom/turin/payload/store_import.py --target /target

Finds the one exFAT volume labelled TURINDATA that carries the kit's marker (on any attached disk, so it also works
when the installer was booted from BMC virtual media or a small stick), mounts it READ-ONLY, and copies:
  models/<dest>  -> /target/srv/ai/models/<dest>   (with a .verified sidecar, so first boot does not re-hash)
  everything else (apt mirror, wheels, source archives, locks) -> /target/var/lib/turin/store/
Each file's SHA256 is computed while copying and compared with store-manifest.json; a mismatch is deleted and left
for first boot to download. Never fails the install: whatever is missing is fetched later (pinned, resumable).
Result: /target/var/lib/turin/store-import.json
"""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, sys, time

LABEL = 'TURINDATA'
MARKER = 'TURIN-MASTER-USB.json'
MOUNT = pathlib.Path('/run/turin-store')
RESERVE = 50 * 1000 ** 3  # Ak's floor: 50 GB always stays free


def find_store(run=subprocess.check_output):
    devs = json.loads(run(['lsblk', '-J', '-p', '-o', 'NAME,LABEL,FSTYPE,TYPE,MOUNTPOINT'], text=True))['blockdevices']
    hits = []

    def walk(nodes):
        for n in nodes or []:
            if str(n.get('label') or '') == LABEL and str(n.get('fstype') or '') == 'exfat':
                hits.append(n)
            walk(n.get('children'))
    walk(devs)
    return hits


def safe_rel(rel):
    p = pathlib.PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('unsafe path in store manifest')
    return p


def copy_verified(src, dst, sha256, size, staging=None):
    """Copy while hashing into `staging`; only a verified file is renamed into place (never a half or wrong file where
    ComfyUI loads models)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = (staging / (sha256 + '.part')) if staging else dst.with_name(dst.name + '.part')
    tmp.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(); n = 0
    with open(src, 'rb') as fi, open(tmp, 'wb') as fo:
        for b in iter(lambda: fi.read(16 * 1024 * 1024), b''):
            h.update(b); fo.write(b); n += len(b)
        fo.flush(); os.fsync(fo.fileno())
    if n != size or h.hexdigest() != sha256:
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, dst)
    return True


def write_sidecar(p, sha256):
    st = p.stat()
    pathlib.Path(str(p) + '.verified').write_text(json.dumps({'sha256': sha256, 'size': st.st_size, 'mtime_ns': st.st_mtime_ns}))


def import_store(store_root, target, out=print, reserve=RESERVE):
    """Copy store_root (the mounted TURINDATA volume) into target. Returns the result dict."""
    store_root, target = pathlib.Path(store_root), pathlib.Path(target)
    t0 = time.time()
    marker = json.loads((store_root / MARKER).read_text())
    if marker.get('format') != 'candy-server-kit.master-usb/1' or marker.get('role') != 'data':
        return {'status': 'not-a-kit-store'}
    man = json.loads((store_root / 'turin-store' / 'store-manifest.json').read_text())
    files = man.get('files', [])
    need = sum(f['size'] for f in files)
    free = shutil.disk_usage(target).free
    if free < need + reserve:
        return {'status': 'no-space', 'need_bytes': need, 'free_bytes': free}
    copied, bad, done = 0, [], 0
    for f in files:
        rel = safe_rel(f['path'])
        src = store_root / 'turin-store' / rel
        if f.get('kind') == 'model':
            dst = target / 'srv/ai/models' / safe_rel(f['dest'])
        else:
            dst = target / 'var/lib/turin/store' / rel
        ok = src.is_file() and copy_verified(src, dst, f['sha256'], f['size'], staging=target / 'srv/ai/models/.incoming')
        if ok:
            copied += 1
            if f.get('kind') == 'model':
                write_sidecar(dst, f['sha256'])
        else:
            bad.append(f.get('id') or f['path'])
        done += f['size']
        if copied % 25 == 0:
            out(f'store import: {done / 1e9:.1f} / {need / 1e9:.1f} GB checked', flush=True)
    for name in ('server_model_lock.json', 'kit.json', 'llm_models.json'):
        p = store_root / 'turin-store' / 'locks' / name
        if p.is_file():
            (target / 'var/lib/turin/store/locks').mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target / 'var/lib/turin/store/locks' / name)
    return {'status': 'ok' if not bad else 'partial', 'copied': copied, 'bad': bad[:50], 'bad_count': len(bad),
            'bytes': need, 'seconds': round(time.time() - t0), 'store_created': man.get('created'),
            'marker_serial': marker.get('device_serial')}


def main(argv=None, run=subprocess.check_output, call=subprocess.run):
    ap = argparse.ArgumentParser(); ap.add_argument('--target', default='/target'); a = ap.parse_args(argv)
    target = pathlib.Path(a.target)
    result_path = target / 'var/lib/turin/store-import.json'
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result = {'status': 'no-store'}
    try:
        hits = find_store(run)
        if len(hits) > 1:
            result = {'status': 'ambiguous', 'devices': [h['name'] for h in hits]}
        elif hits:
            dev = hits[0]['name']
            mounted = hits[0].get('mountpoint')
            if not mounted:
                MOUNT.mkdir(parents=True, exist_ok=True)
                call(['mount', '-t', 'exfat', '-o', 'ro', dev, str(MOUNT)], check=True)
            try:
                result = import_store(mounted or MOUNT, target)
                result['device'] = dev
            finally:
                if not mounted:
                    call(['umount', str(MOUNT)], check=False)
    except Exception as e:  # noqa: BLE001 - the install must go on; first boot downloads what is missing
        result = {'status': 'error', 'error': str(e)[:500]}
    result['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    print('TURIN STORE IMPORT:', json.dumps({k: v for k, v in result.items() if k != 'bad'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
