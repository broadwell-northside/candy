"""Read the lead's model lock (`config/server_model_lock.json`) as opaque rows: ids, URLs, paths, sizes, SHA256.

The kit never reads names, titles, trigger words or any other descriptive field; it ignores every field it does not
need. File names are cleaned to plain ASCII instead of refusing the row (Ak, AK-CANDY-KIT-BUILDER-AND-LORA-NAME-20261106).
"""
import json
import pathlib
import re
import unicodedata

HEX40 = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
DASHES = dict.fromkeys(map(ord, '‐‑‒–—―−⁃﹘﹣－'), '-')
QUOTES = dict.fromkeys(map(ord, '‘’‚‛“”„‟′″´`'), '')
KEEP = ('id', 'wave', 'url', 'dest', 'size', 'sha256', 'comfy_link', 'requires_token', 'profile', 'priority', 'group')


class LockError(ValueError):
    pass


def ascii_name(part):
    """One path component as clean ASCII: unicode dashes -> '-', quotes dropped, accents stripped, the rest '_'."""
    s = unicodedata.normalize('NFKD', part.translate(DASHES).translate(QUOTES))
    s = s.encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^A-Za-z0-9._+-]+', '_', s).strip('._ ').lstrip('-.') or 'file'  # no leading dash or dot
    return s[:180]


def ascii_path(path):
    """A relative path (e.g. a comfy_link type like easy_studio/age_check) cleaned part by part."""
    return ascii_dest(path)


def ascii_dest(dest):
    p = pathlib.PurePosixPath(str(dest))
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise LockError(f'unsafe destination path in the lock (row with dest of {len(str(dest))} characters)')
    return '/'.join(ascii_name(x) for x in p.parts)


def check_row(r, n):
    where = f'lock row {n}'
    if not isinstance(r.get('url'), str) or not r['url'].startswith('https://'):
        raise LockError(f'{where}: url must be https')
    if 'huggingface.co/' in r['url']:
        m = re.search(r'/resolve/([^/]+)/', r['url'])
        if not m or not HEX40.match(m.group(1)):
            raise LockError(f'{where}: Hugging Face URLs must pin a full 40-hex revision (/resolve/<sha>/)')
    if not isinstance(r.get('size'), int) or r['size'] <= 0:
        raise LockError(f'{where}: size must be a positive byte count')
    if not HEX64.match(str(r.get('sha256', '')).lower()):
        raise LockError(f'{where}: sha256 must be 64 hex characters')
    if not isinstance(r.get('wave'), int) or not 1 <= r['wave'] <= 9:
        raise LockError(f'{where}: wave must be 1-9')


def _blocked_ids(doc):
    """Civitai (model_id, version_id) pairs and lock ids on the lock's `held` and `removed` lists: never downloaded."""
    out = set()
    for key in ('held', 'removed'):
        for x in doc.get(key) or []:
            if isinstance(x, dict):
                if x.get('version_id') is not None:
                    out.add(('civitai', str(x.get('model_id')), str(x['version_id'])))
                if x.get('id'):
                    out.add(('id', str(x['id'])))
            else:
                out.add(('id', str(x)))
    return out


def runtimes(doc):
    """Extra pinned sources from the lock's `runtimes` (e.g. Strata): [{id, url, commit, dest, optional}]."""
    pins = []
    for name, rt in (doc.get('runtimes') or {}).items():
        if not isinstance(rt, dict) or not HEX40.match(str(rt.get('commit', ''))) or not str(rt.get('repo', '')).startswith('https://github.com/'):
            continue
        safe = ascii_name(name)
        pins.append({'id': safe, 'url': rt['repo'].removesuffix('.git') + '.git', 'commit': rt['commit'],
                     'dest': '/srv/ai/' + safe, 'optional': True})
    return pins


def load(path):
    """{'path', 'sha256', 'rows': [...], 'runtimes': [...]} with only the fields the kit uses, dest cleaned to ASCII,
    de-duplicated, and nothing from the lock's `held` / `removed` lists."""
    import hashlib
    raw = pathlib.Path(path).read_bytes()
    doc = json.loads(raw)
    rows_in = doc.get('rows')
    if not isinstance(rows_in, list):
        raise LockError('the lock has no "rows" list')
    blocked = _blocked_ids(doc)
    rows, seen, skipped = [], {}, 0
    for n, r in enumerate(rows_in, 1):
        cv = r.get('civitai') or {}
        if ('id', str(r.get('id'))) in blocked or ('civitai', str(cv.get('model_id')), str(cv.get('version_id'))) in blocked:
            skipped += 1
            continue
        check_row(r, n)
        row = {k: r[k] for k in KEEP if k in r}
        if isinstance(row.get('comfy_link'), dict):
            row['comfy_link'] = {'type': ascii_path(row['comfy_link']['type']), 'name': ascii_name(row['comfy_link']['name'])}
        row['sha256'] = row['sha256'].lower()
        row['dest'] = ascii_dest(r['dest'])
        row.setdefault('id', row['sha256'][:16])
        row.setdefault('priority', n)
        if row['dest'] in seen:
            if seen[row['dest']] == row['sha256']:
                continue  # the same file listed twice
            stem, dot, ext = row['dest'].rpartition('.')
            row['dest'] = f'{stem}-{row["sha256"][:8]}.{ext}' if dot else row['dest'] + '-' + row['sha256'][:8]
        seen[row['dest']] = row['sha256']
        rows.append(row)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'rows': rows, 'runtimes': runtimes(doc),
            'skipped_held_or_removed': skipped}


def select(lock, waves):
    return sorted((r for r in lock['rows'] if r['wave'] in set(waves)), key=lambda r: (r['wave'], r['priority']))


def total_bytes(rows):
    return sum(r['size'] for r in rows)
