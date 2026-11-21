"""Resumable HTTPS download with exact size + SHA256 check before a file is ever promoted to its final name.

Used on the Mac by stage_store.py (writing straight onto the USB) and on the server by the model downloader
fallback. `<file>.part` + HTTP Range resumes; a server that ignores Range restarts cleanly; a `<file>.verified`
sidecar (size, mtime, sha256) lets restarts skip re-hashing hundreds of GB. Tokens are only ever sent to
their own host (Hugging Face or Civitai), as headers that are never carried across a redirect to another host
(the CDN a download redirects to never sees them), are read from the environment, and are never written anywhere.
"""
import hashlib
import json
import os
import pathlib
import shutil
import urllib.request

BLOCK = 8 * 1024 * 1024
UA = 'candy-server-kit/0.2'


class FetchError(IOError):
    pass


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(BLOCK), b''):
            h.update(b)
    return h.hexdigest()


def sidecar_ok(p, sha):
    try:
        s = json.loads(pathlib.Path(str(p) + '.verified').read_text()); st = os.stat(p)
        return s['sha256'] == sha and s['size'] == st.st_size and s['mtime_ns'] == st.st_mtime_ns
    except (OSError, ValueError, KeyError):
        return False


def write_sidecar(p, sha):
    st = os.stat(p); side = pathlib.Path(str(p) + '.verified'); tmp = side.with_name(side.name + '.tmp')
    tmp.write_text(json.dumps({'sha256': sha, 'size': st.st_size, 'mtime_ns': st.st_mtime_ns})); os.replace(tmp, side)


def verified(p, sha, size=None):
    p = pathlib.Path(p)
    if not p.is_file() or (size is not None and p.stat().st_size != size):
        return False
    if sidecar_ok(p, sha):
        return True
    if sha256_file(p) == sha:
        write_sidecar(p, sha); return True
    return False


TOKEN_HOSTS = {'HF_TOKEN': ('huggingface.co',), 'CIVITAI_API_TOKEN': ('civitai.com',)}


def token_for(url, tokens):
    """The one token meant for this URL's host, or None. tokens: {'HF_TOKEN': ..., 'CIVITAI_API_TOKEN': ...}."""
    host = urllib.request.urlparse(url).hostname or ''
    for name, hosts in TOKEN_HOSTS.items():
        if (tokens or {}).get(name) and any(host == h or host.endswith('.' + h) for h in hosts):
            return tokens[name]
    return None


def download(url, dest, size, sha, tokens=None, opener=urllib.request.urlopen, progress=None, staging=None):
    """Fetch url to dest. The partial file lives in `staging` (or next to dest) and only a fully verified file is
    renamed to dest, so nothing half-downloaded or wrong ever sits where ComfyUI loads files. Raises FetchError."""
    if not url.startswith('https://') and not url.startswith('http://127.0.0.1'):
        raise FetchError('HTTPS required')
    dest = pathlib.Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    if verified(dest, sha, size):
        return 'present'
    part = (pathlib.Path(staging) / (sha + '.part')) if staging else pathlib.Path(str(dest) + '.part')
    part.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    if size is not None and have > size:
        part.unlink(); have = 0
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    tok = token_for(url, tokens)
    if tok:
        req.add_unredirected_header('Authorization', 'Bearer ' + tok)  # dropped on any redirect
    if have:
        req.add_header('Range', f'bytes={have}-')
    try:
        with opener(req, timeout=120) as r:
            mode = 'ab' if have and getattr(r, 'status', 200) == 206 else 'wb'
            with open(part, mode) as f:
                done = have if mode == 'ab' else 0
                for b in iter(lambda: r.read(BLOCK), b''):
                    f.write(b); done += len(b)
                    if size is not None and done > size:
                        raise FetchError('server sent more bytes than the lock says')
                    if progress:
                        progress(done, size)
                f.flush(); os.fsync(f.fileno())
    except FetchError:
        raise
    except Exception as e:  # noqa: BLE001 - network errors are retried by the caller
        raise FetchError(str(e)[:200]) from None
    if size is not None and part.stat().st_size != size:
        raise FetchError(f'incomplete: {part.stat().st_size} of {size} bytes (will resume)')
    if sha256_file(part) != sha:
        part.unlink()
        raise FetchError('SHA256 mismatch: the file was deleted and will be fetched again')
    os.replace(part, dest)
    write_sidecar(dest, sha)
    return 'downloaded'


def free_bytes(path):
    p = pathlib.Path(path)
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free
