"""Just enough of apt, in pure Python, to stage a partial mirror on the master USB.

It parses signed InRelease files and Packages indices, compares Debian versions, and computes a SUPERSET of the
packages apt will want on the server: Depends + Pre-Depends from an empty base, so everything the real apt on the
server needs is on the USB (apt itself makes the final choice there, and checks every signature and hash). What this
cannot resolve is listed, and the server's provisioner falls back to the same pinned sources online.
"""
import gzip
import re

# ------------------------------------------------------------------ Debian version comparison (deb-version(7))


def _order(c):
    if c == '~':
        return -1
    if c.isdigit():
        return 0
    if c.isalpha():
        return ord(c)
    return ord(c) + 256


def _cmp_part(a, b):
    """dpkg's verrevcmp: alternate non-digit runs (lexical, '~' first, letters before symbols) and digit runs."""
    while a or b:
        pa = re.match(r'\D*', a).group(); pb = re.match(r'\D*', b).group()
        for k in range(max(len(pa), len(pb))):
            ca = _order(pa[k]) if k < len(pa) else 0
            cb = _order(pb[k]) if k < len(pb) else 0
            if ca != cb:
                return ca - cb
        a, b = a[len(pa):], b[len(pb):]
        na = re.match(r'\d*', a).group(); nb = re.match(r'\d*', b).group()
        if int(na or 0) != int(nb or 0):
            return int(na or 0) - int(nb or 0)
        a, b = a[len(na):], b[len(nb):]
    return 0


def split_version(v):
    epoch, _, rest = v.partition(':') if ':' in v else ('0', '', v)
    upstream, _, rev = rest.rpartition('-') if '-' in rest else (rest, '', '0')
    return int(epoch or 0), upstream, rev


def vercmp(a, b):
    """<0, 0, >0 like dpkg --compare-versions."""
    ea, ua, ra = split_version(a); eb, ub, rb = split_version(b)
    if ea != eb:
        return ea - eb
    return _cmp_part(ua, ub) or _cmp_part(ra, rb)


def satisfies(version, op, want):
    c = vercmp(version, want)
    return {'=': c == 0, '>=': c >= 0, '<=': c <= 0, '>>': c > 0, '<<': c < 0, '>': c >= 0, '<': c <= 0}[op]


# ------------------------------------------------------------------ parsing


def stanzas(text):
    for block in re.split(r'\n\s*\n', text):
        d, key = {}, None
        for line in block.splitlines():
            if line[:1] in (' ', '\t') and key:
                d[key] += '\n' + line.strip()
            elif ':' in line:
                key, _, val = line.partition(':'); key = key.strip(); d[key] = val.strip()
        if d:
            yield d


def packages_from_gz(data):
    return list(stanzas(gzip.decompress(data).decode('utf-8', 'replace')))


def release_files(inrelease_text):
    """{path: (size, sha256)} from the SHA256 section of an InRelease/Release file (the signature is checked by apt
    on the server; here we only use it to verify what we download)."""
    body = inrelease_text.split('-----BEGIN PGP SIGNATURE-----')[0]
    out, on = {}, False
    for line in body.splitlines():
        if re.match(r'^SHA256:\s*$', line):
            on = True; continue
        if on:
            if not line.startswith(' '):
                break
            sha, size, path = line.split()
            out[path] = (int(size), sha)
    return out


def parse_deps(field):
    """'a (>= 1) | b, c:any' -> [[('a', '>=', '1'), ('b', None, None)], [('c', None, None)]]"""
    groups = []
    for clause in (field or '').split(','):
        alts = []
        for alt in clause.split('|'):
            alt = alt.strip()
            if not alt:
                continue
            m = re.match(r'([a-z0-9][a-z0-9+.\-]*)(?::[a-z0-9]+)?\s*(?:\(\s*([<>=]+)\s*([^)\s]+)\s*\))?\s*(\[.*\])?$', alt)
            if m:
                alts.append((m.group(1), m.group(2), m.group(3)))
        if alts:
            groups.append(alts)
    return groups


# ------------------------------------------------------------------ index + closure


class Index:
    def __init__(self):
        self.versions = {}   # name -> [stanza, ...]
        self.provides = {}   # virtual -> {name, ...}

    def add(self, pkgs, source_id, base_uri, only=None):
        rx = re.compile(only) if only else None
        for p in pkgs:
            name = p.get('Package')
            if not name or p.get('Architecture') not in ('amd64', 'all') or (rx and not rx.match(name)):
                continue
            p = dict(p, _source=source_id, _base=base_uri.rstrip('/'))
            self.versions.setdefault(name, []).append(p)
            for g in parse_deps(p.get('Provides', '')):
                for virt, _op, _v in g:
                    self.provides.setdefault(virt, set()).add(name)

    def best(self, name, op=None, want=None):
        cands = [p for p in self.versions.get(name, []) if not op or satisfies(p['Version'], op, want)]
        if not cands:
            return None
        top = cands[0]
        for p in cands[1:]:
            if vercmp(p['Version'], top['Version']) > 0:
                top = p
        return top


def closure(index, wanted):
    """wanted: ['pkg', 'pkg=1.2-3', ...]. Returns (chosen {name: stanza}, unresolved [str]).

    The pins are taken first, so a dependency can never swap a pinned package for another version, and a package that is
    already chosen only satisfies a dependency whose version constraint it meets; a clash is listed as unresolved."""
    chosen, unresolved, queue = {}, [], []

    def take(p):
        if p['Package'] not in chosen:
            chosen[p['Package']] = p
            queue.append(p)

    for w in wanted:
        name, _, ver = w.partition('=')
        p = index.best(name, '=' if ver else None, ver or None)
        if p is None:
            unresolved.append(w)
        else:
            take(p)
    while queue:
        p = queue.pop()
        for group in parse_deps(p.get('Pre-Depends', '')) + parse_deps(p.get('Depends', '')):
            if any(n in chosen and (not op or satisfies(chosen[n]['Version'], op, v)) for n, op, v in group):
                continue
            pick = None
            for n, op, v in group:
                if n in chosen:
                    continue  # chosen at a version this dependency does not accept
                pick = index.best(n, op, v)
                if pick:
                    break
                provs = sorted(index.provides.get(n, ()))
                prov = next((x for x in provs if x in chosen), None) or (provs[0] if provs else None)
                if prov:
                    pick = index.best(prov)
                    if pick:
                        break
            if pick:
                take(pick)
            else:
                clash = ''.join(f' [chose {n} {chosen[n]["Version"]}]' for n, _o, _v in group if n in chosen)
                unresolved.append(' | '.join(n + (f' ({op} {v})' if op else '') for n, op, v in group) + ' <- ' + p['Package'] + clash)
    return chosen, sorted(set(unresolved))


# ------------------------------------------------------------------ NVIDIA driver / kernel pairing
NV_MODULES = re.compile(r'^linux-modules-nvidia-(?P<branch>\d+)(?P<flavour>-open)?(?:-server)?-(?P<abi>\d+\.\d+\.\d+-\d+)-generic$')
NV_USERLAND = re.compile(r'^nvidia-utils-(?P<branch>\d+)(?:-server)?$')
KERNEL_META = ('linux-generic-hwe-24.04', 'linux-generic')


def driver_pairing(chosen, wanted):
    """Problems (empty = paired) when the kit pins a prebuilt NVIDIA kernel module: that module must be built from exactly
    the pinned userland driver version (its Built-Using field) and for the pinned kernel ABI, and the chosen
    nvidia-kernel-common must be that same version. A mismatch would leave nvidia-smi with 'Driver/library version mismatch'
    on the server, or make the server's apt refuse the pins."""
    pins = dict(w.partition('=')[::2] for w in wanted)
    if not any(n.startswith('linux-modules-nvidia-') for n in pins):
        return []
    problems = []
    drv = {m.group('branch'): pins[n] for n in pins if (m := NV_USERLAND.match(n)) and pins[n]}
    kmeta = next((pins[k] for k in KERNEL_META if pins.get(k)), '')
    km = re.match(r'^(\d+\.\d+\.\d+-\d+)\.', kmeta)
    if not drv:
        problems.append('no pinned nvidia-utils-<branch>=<version> to pair the kernel module with')
    if not km:
        problems.append('no pinned linux-generic(-hwe) kernel version to pair the kernel module with')
    mods = {n: m for n in chosen if (m := NV_MODULES.match(n))}
    if not mods:
        problems.append('no prebuilt linux-modules-nvidia-<branch>-<kernel>-generic package was resolved')
    for n, m in sorted(mods.items()):
        want = drv.get(m.group('branch'))
        if km and m.group('abi') != km.group(1):
            problems.append(f'{n} is for kernel {m.group("abi")}, but the kernel pin is {km.group(1)}')
        if 'linux-image-' + m.group('abi') + '-generic' not in chosen:
            problems.append(f'{n}: linux-image-{m.group("abi")}-generic is not in the closure')
        built = [v for b, _op, v in (g[0] for g in parse_deps(chosen[n].get('Built-Using', '')))
                 if b.startswith(('nvidia-dkms-' + m.group('branch'), 'nvidia-graphics-drivers-' + m.group('branch')))]
        if not built:
            problems.append(f'{n} does not say which NVIDIA driver it was built from (no Built-Using)')
        elif want and any(v != want for v in built):
            problems.append(f'{n} was built from NVIDIA {built[0]}, but the userland pin is {want}')
        common = chosen.get('nvidia-kernel-common-' + m.group('branch'))
        if want and common and common['Version'] != want:
            problems.append(f'nvidia-kernel-common-{m.group("branch")} resolved to {common["Version"]}, not the pinned {want}')
    return problems


def deb_files(chosen):
    """[{source, path, url, size, sha256}] for the chosen packages."""
    out = []
    for p in sorted(chosen.values(), key=lambda x: x['Package']):
        rel = p['Filename'][2:] if p['Filename'].startswith('./') else p['Filename']
        out.append({'source': p['_source'], 'path': rel, 'url': p['_base'] + '/' + rel, 'size': int(p['Size']),
                    'sha256': p['SHA256'].lower(), 'package': p['Package'], 'version': p['Version']})
    return out
