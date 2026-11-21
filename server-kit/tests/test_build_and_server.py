"""Builder, model lock, apt resolver, stager, store import, server disk guard, downloader, health, provisioning config.
Everything is offline: local in-process HTTP, synthetic indices and ISO, fake system tools in temp folders."""
import contextlib
import functools
import gzip
import hashlib
import http.server
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest

KIT = pathlib.Path(__file__).resolve().parents[1]
for p in (KIT, KIT / 'usb', KIT / 'payload', KIT / 'tests'):
    sys.path.insert(0, str(p))
from kitlib import aptrepo, diskinfo, fetch, lock as locklib, marker  # noqa: E402
from fakemac import FakeMac  # noqa: E402
import builder  # noqa: E402
import stage_store  # noqa: E402
import store_import  # noqa: E402


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


guard = load('disk_guard', KIT / 'payload/disk_guard.py')
health = load('turin_health', KIT / 'payload/turin-health.py')
burnin = load('turin_burnin', KIT / 'payload/turin-burnin.py')
aptoff = load('apt_offline', KIT / 'payload/apt_offline.py')
units = load('setup_units', KIT / 'payload/setup_units.py')
web = load('status_web', KIT / 'payload/turin-status-web.py')
sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
GB = 1000 ** 3
KITCFG = json.loads((KIT / 'config/kit.json').read_text())


class Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(); self.t = pathlib.Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Range(Quiet):
    def do_GET(self):
        p = pathlib.Path(self.directory) / self.path.lstrip('/').split('?')[0]
        if not p.is_file():
            self.send_error(404); return
        data = p.read_bytes(); rng = self.headers.get('Range')
        if rng:
            start = int(rng.split('=')[1].split('-')[0]); body = data[start:]; self.send_response(206)
        else:
            body = data; self.send_response(200)
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)


@contextlib.contextmanager
def serve(directory):
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Range, directory=str(directory)))
    t = threading.Thread(target=s.serve_forever, daemon=True); t.start()
    try:
        yield f'http://127.0.0.1:{s.server_port}'
    finally:
        s.shutdown(); s.server_close(); t.join()


@contextlib.contextmanager
def serve_handler(handler):
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    t = threading.Thread(target=s.serve_forever, daemon=True); t.start()
    try:
        yield f'http://127.0.0.1:{s.server_port}'
    finally:
        s.shutdown(); s.server_close(); t.join()


def lock_file(path, rows):
    path.write_text(json.dumps({'schema': 'test', 'rows': rows})); return path


# ------------------------------------------------------------------ model lock
class Lock(Tmp):
    def test_ascii_names_and_opaque_fields(self):
        rows = [{'id': 'a', 'wave': 1, 'url': 'https://example.org/x', 'dest': 'comfy/loras/fam/role/n–ame “x” café.safetensors',
                 'size': 1, 'sha256': 'A' * 64, 'name': 'never read', 'trigger_words': ['never'], 'title': 'never'}]
        lk = locklib.load(lock_file(self.t / 'l.json', rows))
        r = lk['rows'][0]
        self.assertEqual(r['dest'], 'comfy/loras/fam/role/n-ame_x_cafe.safetensors')
        self.assertNotIn('name', r); self.assertNotIn('trigger_words', r); self.assertNotIn('title', r)
        self.assertEqual(r['sha256'], 'a' * 64)

    def test_held_removed_runtimes_and_link_types(self):
        rows = [{'id': 'keep', 'wave': 3, 'url': 'https://civitai.com/api/download/models/2', 'dest': 'comfy/loras/f/r/1_2.safetensors',
                 'size': 1, 'sha256': 'a' * 64, 'civitai': {'model_id': 1, 'version_id': 2}},
                {'id': 'gone', 'wave': 3, 'url': 'https://civitai.com/api/download/models/4', 'dest': 'comfy/loras/f/r/3_4.safetensors',
                 'size': 1, 'sha256': 'b' * 64, 'civitai': {'model_id': 3, 'version_id': 4}},
                {'id': 'held1', 'wave': 1, 'url': 'https://example.org/h', 'dest': 'h.bin', 'size': 1, 'sha256': 'c' * 64},
                {'id': 'age', 'wave': 1, 'url': 'https://example.org/a', 'dest': 'comfy/age/m.pt', 'size': 1, 'sha256': 'd' * 64,
                 'comfy_link': {'type': 'easy_studio/age_check/torch/hub/checkpoints', 'name': '-m.pt'}}]
        doc = {'rows': rows, 'removed': [{'model_id': 3, 'version_id': 4, 'reason': 'x'}], 'held': ['held1'],
               'runtimes': {'strata': {'repo': 'https://github.com/Niko1221/Strata', 'commit': 'c3b3f5035506f3e966f1b4b7b188aeaabae92f1d'},
                            'bad': {'repo': 'https://example.org/x', 'commit': 'zz'}}}
        (self.t / 'l.json').write_text(json.dumps(doc))
        lk = locklib.load(self.t / 'l.json')
        self.assertEqual([r['id'] for r in lk['rows']], ['keep', 'age']); self.assertEqual(lk['skipped_held_or_removed'], 2)
        self.assertEqual(lk['rows'][1]['comfy_link'], {'type': 'easy_studio/age_check/torch/hub/checkpoints', 'name': 'm.pt'})
        self.assertEqual(lk['runtimes'], [{'id': 'strata', 'url': 'https://github.com/Niko1221/Strata.git', 'commit': 'c3b3f5035506f3e966f1b4b7b188aeaabae92f1d',
                                           'dest': '/srv/ai/strata', 'optional': True}])
        for bad, good in (('-rf.safetensors', 'rf.safetensors'), ('.hidden', 'hidden'), ('..', None)):
            if good:
                self.assertEqual(locklib.ascii_name(bad), good)
        with self.assertRaises(locklib.LockError):
            locklib.ascii_dest('a/../b')

    def test_refusals_and_dedupe(self):
        base = {'id': 'a', 'wave': 1, 'url': 'https://example.org/x', 'dest': 'a/b.bin', 'size': 5, 'sha256': 'b' * 64}
        for bad in ({'dest': '../x'}, {'dest': '/etc/x'}, {'url': 'http://example.org/x'}, {'size': 0}, {'sha256': 'z'},
                    {'url': 'https://huggingface.co/o/r/resolve/main/f.bin'}, {'wave': 0}):
            with self.assertRaises(locklib.LockError, msg=str(bad)):
                locklib.load(lock_file(self.t / 'l.json', [dict(base, **bad)]))
        lk = locklib.load(lock_file(self.t / 'l.json', [base, dict(base), dict(base, sha256='c' * 64)]))
        self.assertEqual([r['dest'] for r in lk['rows']], ['a/b.bin', 'a/b-cccccccc.bin'])


# ------------------------------------------------------------------ Director placement (the lead's app/placement.json)
class Director(Tmp):
    """Profiles shaped like the lead's config/llm_models.json (ids, placement sizes, launch lines; no titles)."""
    REG = {'default_profile': 'moe35', 'scorer': {'id': 'vl7', 'weights_gb': 16.6},
           'profiles': [
               {'id': 'moe35', 'runtime': 'llama-server', 'base_url': 'http://127.0.0.1:8000/v1', 'placement': {'gpu1_gb': 45.8, 'ram_gb': 0},
                'launch': 'CUDA_VISIBLE_DEVICES=1 llama-server -m <models>/a.gguf -ngl 99 -c 32768 --host 127.0.0.1 --port 8000 --alias moe35'},
               {'id': 'big84', 'runtime': 'llama-server', 'base_url': 'http://127.0.0.1:8000/v1', 'placement': {'gpu1_gb': 84.0},
                'launch': 'CUDA_VISIBLE_DEVICES=1 llama-server -m <models>/b.gguf -ngl 99 -c 16384 --host 127.0.0.1 --port 8000 --alias big84'},
               {'id': 'offload', 'runtime': 'llama-server --lora', 'base_url': 'http://127.0.0.1:8002/v1', 'placement': {'gpu1_gb': 86.0, 'ram_gb': 42},
                'launch': "llama-server -m <models>/c.gguf -ngl 99 -ot 'exps=CPU' -c 16384 --host 127.0.0.1 --port 8002 --alias off"},
               {'id': 'both', 'runtime': 'Strata', 'base_url': 'http://127.0.0.1:8001/v1', 'placement': {'gpu0_gb': 76.0, 'gpu1_gb': 76.0}, 'launch': ''}]}

    def setUp(self):
        super().setUp()
        sys.modules.setdefault('kitlock', locklib); sys.modules.setdefault('kitfetch', fetch)
        self.gp = load('gpu_policy', KIT / 'payload/gpu_policy.py'); sys.modules['gpu_policy'] = self.gp
        self.rd = load('run_director', KIT / 'payload/run_director.py')
        self.locks = self.t / 'locks'; self.locks.mkdir()
        (self.locks / 'llm_models.json').write_text(json.dumps(self.REG))
        self.real = json.loads((KIT.parent / 'app/placement.json').read_text())
        first = json.loads(json.dumps(self.real))  # the first format: no per-profile list, the 70 GB rule decides
        for k in ('profiles', 'unlisted_profiles', 'unlisted_why'):
            first['director'].pop(k, None)
        (self.locks / 'placement.json').write_text(json.dumps(first))
        lock_file(self.locks / 'server_model_lock.json', [
            {'id': f'g{n}', 'wave': 1, 'url': 'https://example.org/' + n, 'dest': f'llm/{n}.gguf', 'size': 1, 'sha256': 'a' * 64, 'profile': n}
            for n in ('moe35', 'big84', 'offload')])
        self.place = self.gp.placement(self.locks)

    def plan(self, pid):
        return self.gp.director_plan(self.gp.profile(pid, self.REG), self.place)

    def test_default_director_runs_hybrid_on_the_placement_lane(self):
        self.assertEqual(self.place['director']['lane'], 'gpu0', 'the lead placed the Director on GPU0 (app/placement.json)')
        p = self.plan('moe35')
        self.assertEqual((p['gpus'], p['hybrid'], p['pauses']), ('0', True, []))
        self.assertTrue(self.gp.comfy1_allowed(self.gp.profile('moe35', self.REG), self.place), 'the video lane keeps GPU1')
        argv, files, plan = self.rd.argv_for('moe35', root=self.t / 'models', locks=self.locks)
        self.assertEqual(argv[argv.index('-ot') + 1], 'exps=CPU', 'hybrid: MoE experts in system RAM')
        self.assertEqual(argv[argv.index('--port') + 1], '8000'); self.assertEqual(argv[argv.index('--host') + 1], '127.0.0.1')
        self.assertEqual([f['id'] for f in files], ['gmoe35']); self.assertEqual(plan['gpus'], '0')

    def test_profiles_above_70_gb_take_gpu1_and_pause_the_video_lane(self):
        for pid in ('big84', 'offload'):
            p = self.plan(pid)
            self.assertEqual((p['gpus'], p['pauses']), ('1', ['gpu1']), pid)
            self.assertFalse(self.gp.comfy1_allowed(self.gp.profile(pid, self.REG), self.place), pid)
        argv, _f, _p = self.rd.argv_for('big84', root=self.t / 'models', locks=self.locks)
        self.assertNotIn('-ot', argv, 'a whole card: no expert offload')
        argv, _f, _p = self.rd.argv_for('offload', root=self.t / 'models', locks=self.locks)
        self.assertEqual(argv.count('-ot'), 1); self.assertEqual(argv[argv.index('-ot') + 1], 'exps=CPU', 'the registry\'s own -ot wins')
        self.assertEqual(self.plan('both')['gpus'], '0,1'); self.assertEqual(self.plan('both')['pauses'], ['gpu1'])

    def per_profile(self, entries, unlisted='exclusive_gpu1'):
        doc = json.loads((self.locks / 'placement.json').read_text())
        doc['director'].update(profiles=entries, unlisted_profiles=unlisted)
        (self.locks / 'placement.json').write_text(json.dumps(doc)); self.place = self.gp.placement(self.locks)

    def test_per_profile_list_decides_who_shares_gpu0(self):
        self.per_profile({'moe35': {'lane': 'gpu0', 'mode': 'hybrid', 'vram_est_gb': 8, 'launch_adds': '-ot exps=CPU'}})
        p = self.plan('moe35')
        self.assertEqual((p['gpus'], p['hybrid'], p['adds'], p['pauses']), ('0', True, ['-ot', 'exps=CPU'], []))
        argv, _f, _p = self.rd.argv_for('moe35', root=self.t / 'models', locks=self.locks)
        self.assertEqual(argv.count('-ot'), 1); self.assertEqual(argv[argv.index('-ot') + 1], 'exps=CPU')
        for pid in ('big84', 'offload'):  # unlisted: GPU1 alone, whatever the size
            self.assertEqual((self.plan(pid)['gpus'], self.plan(pid)['pauses']), ('1', ['gpu1']), pid)
        small = {'id': 'small20', 'placement': {'gpu1_gb': 20.0}}
        self.assertEqual(self.gp.director_plan(small, self.place)['gpus'], '1', 'unlisted and small still takes GPU1 alone')
        self.assertFalse(self.gp.comfy1_allowed(small, self.place))

    def test_per_profile_list_refuses_unknown_rules_and_non_offload_flags(self):
        self.per_profile({}, unlisted='share_gpu0')
        with self.assertRaises(SystemExit):
            self.plan('big84')
        for bad in ('--host 0.0.0.0', '-ot exps=CPU --port 9000', '-ot'):
            self.per_profile({'moe35': {'lane': 'gpu0', 'mode': 'hybrid', 'launch_adds': bad}})
            with self.assertRaises(SystemExit, msg=bad):
                self.plan('moe35')
        self.assertEqual(self.gp.offload_args('--cpu-moe -ot exps=CPU'), ['--cpu-moe', '-ot', 'exps=CPU'])

    def test_real_placement_file_plans_its_own_profiles(self):
        for pid, e in (self.real['director'].get('profiles') or {}).items():
            plan = self.gp.director_plan({'id': pid, 'placement': {}}, self.real)
            self.assertEqual(plan['gpus'], str(self.real['lanes'][e['lane']]['gpu']), pid)

    def test_missing_placement_is_a_clear_stop(self):
        (self.locks / 'placement.json').unlink()
        with self.assertRaises(SystemExit) as e:
            self.gp.placement(self.locks)
        self.assertIn('placement.json', str(e.exception))

    def test_director_unit_leaves_the_card_to_the_launcher(self):
        d = self.t / 'units'; d.mkdir(); units.main(d)
        text = (d / 'turin-director.service').read_text()
        self.assertNotIn('CUDA_VISIBLE_DEVICES', text, 'run_director.py sets the card from placement.json')
        self.assertIn('CUDA_VISIBLE_DEVICES=1', (d / 'turin-comfy1.service').read_text())
        self.assertIn('gpu_policy.py --allow-comfy1', (d / 'turin-comfy1.service').read_text())


# ------------------------------------------------------------------ apt resolver
def pkg(name, ver, deps='', provides='', arch='amd64', pre=''):
    s = f'Package: {name}\nVersion: {ver}\nArchitecture: {arch}\nFilename: pool/{name}_{ver}.deb\nSize: 10\nSHA256: {"0" * 64}\n'
    if deps: s += f'Depends: {deps}\n'
    if pre: s += f'Pre-Depends: {pre}\n'
    if provides: s += f'Provides: {provides}\n'
    return s


class Apt(unittest.TestCase):
    def index(self):
        ub = '\n'.join([pkg('drv', '580.178.04-0ubuntu0.24.04.1', 'libcompute (= 580.178.04-0ubuntu0.24.04.1), awk'),
                        pkg('libcompute', '580.178.04-0ubuntu0.24.04.1', 'libc6 (>= 2.34)'), pkg('libc6', '2.39-0ubuntu8.6'),
                        pkg('mawk', '1.3.4', provides='awk'), pkg('tool', '1.0', 'missing-thing | libc6', pre='libc6')])
        nv = '\n'.join([pkg('drv', '580.95.05-0ubuntu1'), pkg('cuda-toolkit-12-8', '12.8.2-1', 'cuda-nvcc-12-8 (>= 12.8)'),
                        pkg('cuda-nvcc-12-8', '12.8.93-1'), pkg('cuda-nvcc-12-8', '12.8.61-1')])
        ix = aptrepo.Index()
        ix.add(list(aptrepo.stanzas(ub)), 'ubuntu', 'https://u')
        ix.add(list(aptrepo.stanzas(nv)), 'nvidia', 'https://n', KITCFG['apt']['sources'][1]['only_packages_matching'])
        return ix

    def test_closure_pins_provides_alternatives_and_source_limits(self):
        chosen, unresolved = aptrepo.closure(self.index(), ['drv=580.178.04-0ubuntu0.24.04.1', 'cuda-toolkit-12-8=12.8.2-1', 'tool', 'ghost'])
        self.assertEqual(chosen['drv']['_source'], 'ubuntu', 'NVIDIA repo driver builds are never picked')
        self.assertIn('mawk', chosen, 'virtual package awk resolved through Provides')
        self.assertEqual(chosen['cuda-nvcc-12-8']['Version'], '12.8.93-1', 'highest version satisfying >=')
        self.assertEqual(unresolved, ['ghost'])
        files = aptrepo.deb_files(chosen)
        self.assertTrue(all(f['url'].startswith(('https://u/pool/', 'https://n/pool/')) for f in files))

    def test_pins_are_kept_and_version_clashes_listed(self):
        ix = aptrepo.Index()
        ix.add(list(aptrepo.stanzas('\n'.join([pkg('a', '1'), pkg('a', '2'), pkg('c', '1', 'a'), pkg('b', '1', 'a (>= 2)')]))), 'u', 'https://u')
        chosen, unresolved = aptrepo.closure(ix, ['a=1', 'c'])
        self.assertEqual(chosen['a']['Version'], '1', 'an unversioned dependency never swaps out a pinned version')
        self.assertEqual(unresolved, [])
        chosen, unresolved = aptrepo.closure(ix, ['b', 'a=1'])
        self.assertEqual(chosen['a']['Version'], '1')
        self.assertEqual(unresolved, ['a (>= 2) <- b [chose a 1]'], 'a chosen package only counts when its version fits')

    def pairing_set(self, built='580.178.04-0ubuntu0.24.04.1', abi='7.0.0-42', common='580.178.04-0ubuntu0.24.04.1', image=True):
        mods = pkg(f'linux-modules-nvidia-580-open-{abi}-generic', '7.0.0-42.42~24.04.1', f'linux-image-{abi}-generic')
        if built:
            mods += f'Built-Using: nvidia-dkms-580-open (= {built})\n'
        texts = [mods, pkg('nvidia-kernel-common-580', common)] + ([pkg(f'linux-image-{abi}-generic', '7.0.0-42.42~24.04.1')] if image else [])
        return {s['Package']: s for s in aptrepo.stanzas('\n'.join(texts))}

    def test_driver_and_kernel_module_pairing(self):
        wanted = KITCFG['apt']['install']
        self.assertEqual(aptrepo.driver_pairing(self.pairing_set(), wanted), [], 'the real pins (checked against the 20261105 snapshot)')
        self.assertEqual(aptrepo.driver_pairing({}, ['drv=1.0']), [], 'no prebuilt module pinned: nothing to pair')
        cases = {'built from NVIDIA 580.159': self.pairing_set(built='580.159.03-0ubuntu0.24.04.1'),
                 'does not say which NVIDIA driver': self.pairing_set(built=''),
                 'is for kernel 7.0.0-31': self.pairing_set(abi='7.0.0-31'),
                 'not in the closure': self.pairing_set(image=False),
                 'nvidia-kernel-common-580 resolved to': self.pairing_set(common='580.180.01-0ubuntu0.24.04.1')}
        for words, chosen in cases.items():
            self.assertIn(words, ' '.join(aptrepo.driver_pairing(chosen, wanted)), words)
        self.assertIn('no prebuilt', ' '.join(aptrepo.driver_pairing({}, wanted)))

    def test_release_files_and_deps_parser(self):
        text = 'Origin: X\nSHA256:\n ' + 'a' * 64 + ' 123 main/binary-amd64/Packages.gz\n ' + 'b' * 64 + ' 9 Release\nMD5Sum:\n x 1 y\n'
        self.assertEqual(aptrepo.release_files(text)['main/binary-amd64/Packages.gz'], (123, 'a' * 64))
        self.assertEqual(aptrepo.parse_deps('a (>= 1.0) | b:any, c [amd64]'), [[('a', '>=', '1.0'), ('b', None, None)], [('c', None, None)]])

    def test_kit_pins_every_driver_kernel_and_cuda_package(self):
        pinned = {p.split('=')[0]: p.split('=')[1] for p in KITCFG['apt']['install'] if '=' in p}
        self.assertNotIn('nvidia-driver-580-open', ' '.join(KITCFG['apt']['install']), 'that metapackage pulls dkms')
        for name in ('linux-generic-hwe-24.04', 'nvidia-headless-no-dkms-580-open', 'nvidia-utils-580', 'linux-modules-nvidia-580-open-generic-hwe-24.04',
                     'cuda-toolkit-12-8', 'tailscale'):
            self.assertIn(name, pinned, name)
        joined = json.dumps(KITCFG) + (KIT / 'payload/turin-provision.sh').read_text()
        for gone in ('docker', 'nvidia-container-toolkit', 'turin-set-tokens', 'secrets.env'):
            self.assertNotIn(gone, joined, gone)


# ------------------------------------------------------------------ builder
def fake_scan(iso):
    files = [{'path': 'casper/vmlinuz', 'size': 3, 'sha256': sha(b'k')}, {'path': 'EFI/boot/bootx64.efi', 'size': 1, 'sha256': sha(b'e')},
             {'path': 'boot/grub/grub.cfg', 'size': 1, 'sha256': 'x'}, {'path': 'md5sum.txt', 'size': 1, 'sha256': 'y'}]
    grub = b'set timeout=30\nmenuentry "Try or Install Ubuntu Server" {\n\tlinux\t/casper/vmlinuz  ---\n}\n' \
           b'menuentry "Ubuntu Server with the HWE kernel" {\n\tlinux\t/casper/hwe-vmlinuz  ---\n}\n'
    md5 = b'aaaa  ./boot/grub/grub.cfg\nbbbb  ./casper/vmlinuz\n'
    return files, ['dists/stable', 'ubuntu'], {'boot/grub/grub.cfg': grub, 'md5sum.txt': md5}


class Builder(Tmp):
    def setUp(self):
        super().setUp()
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'test-only', '-f', str(self.t / 'id')], check=True)
        (self.t / 'id').unlink()  # the kit only ever sees a public key
        self.c = {'hostname': 'epyc-studio', 'username': 'andrew', 'os_disk_mode': 'auto_single_blank_nvme', 'os_disk_serial': '',
                  'approve_blank_disk_install': True, 'hardware_checklist_confirmed': True, 'ssh_public_key_file': str(self.t / 'id.pub')}
        self.lock = locklib.load(lock_file(self.t / 'l.json', [
            {'id': 'm1', 'wave': 1, 'url': 'https://example.org/a', 'dest': 'comfy/a.safetensors', 'size': 10, 'sha256': 'a' * 64},
            {'id': 'm4', 'wave': 4, 'url': 'https://example.org/b', 'dest': 'llm/b.gguf', 'size': 99, 'sha256': 'b' * 64}]))

    def test_validate_requires_approvals_and_a_public_key(self):
        builder.validate(self.c, KITCFG)
        for k in ('approve_blank_disk_install', 'hardware_checklist_confirmed'):
            with self.assertRaises(ValueError, msg=k):
                builder.validate(dict(self.c, **{k: False}), KITCFG)
        with self.assertRaises(ValueError):
            builder.validate(dict(self.c, os_disk_mode='exact_serial', os_disk_serial=''), KITCFG)
        for body in ('-----BEGIN OPENSSH ' + 'PRIVATE KEY-----\nabc', 'ssh-ed25519 AAAA\nssh-ed25519 BBBB', 'not a key'):
            (self.t / 'bad.pub').write_text(body)
            with self.assertRaises(ValueError):
                builder.validate(dict(self.c, ssh_public_key_file=str(self.t / 'bad.pub')), KITCFG)

    def test_render_is_offline_safe_and_fails_closed(self):
        a = builder.render(self.c, KITCFG, builder.validate(self.c, KITCFG))['autoinstall']
        self.assertEqual(a['packages'], [], 'nothing the ISO pool cannot supply')
        self.assertEqual(a['apt']['fallback'], 'offline-install')
        self.assertIn('snapshot.ubuntu.com/ubuntu/20261105T000000Z', a['apt']['primary'][0]['uri'])
        self.assertEqual(a['storage']['layout']['match']['serial'], builder.PLACEHOLDER_SERIAL)
        self.assertFalse(a['ssh']['allow-pw']); self.assertEqual(a['identity']['password'], '!')
        self.assertEqual(a['shutdown'], 'poweroff'); self.assertIn('--select-blank-nvme', a['early-commands'][0])
        self.assertTrue(any('store_import.py' in x for x in a['late-commands']))
        self.assertNotIn('users', a['user-data'], 'sudo is set by a reviewed sudoers file, not cloud-init')

    def test_build_overlay_and_plan(self):
        plan = builder.build(self.c, KITCFG, builder.validate(self.c, KITCFG), self.lock, self.t / 'fake.iso', self.t / 'ov',
                             app_dir=None, scan=fake_scan)
        ov = self.t / 'ov'
        grub = (ov / 'boot/grub/grub.cfg').read_text()
        self.assertTrue(grub.startswith('set default=1')); self.assertEqual(grub.count('autoinstall ds=nocloud'), 2)
        self.assertIn('search --no-floppy --set=root --file /.disk/info', (ov / 'EFI/boot/grub.cfg').read_text())
        self.assertEqual((ov / 'turin/locks/placement.json').read_bytes(), (KIT.parent / 'app/placement.json').read_bytes(), 'the lead\'s file, not a copy kept here')
        for rel in ('turin/payload/disk_guard.py', 'turin/payload/kitlock.py', 'turin/payload/kitfetch.py', 'turin/locks/server_model_lock.json',
                    'turin/config/kit.json', 'nocloud/user-data', 'nocloud/meta-data'):
            self.assertTrue((ov / rel).is_file(), rel)
        eff = json.loads((ov / 'turin/config/install.json').read_text())
        self.assertNotIn('ssh_public_key_file', eff)
        md5 = (ov / 'md5sum.txt').read_text()
        self.assertNotIn('aaaa  ./boot/grub/grub.cfg', md5); self.assertIn('bbbb  ./casper/vmlinuz', md5)
        self.assertIn(hashlib.md5(grub.encode()).hexdigest() + '  ./boot/grub/grub.cfg', md5)
        self.assertEqual([f['path'] for f in plan['iso']['files']], ['casper/vmlinuz', 'EFI/boot/bootx64.efi'])
        self.assertEqual(plan['iso']['exclude'], ['dists/stable', 'ubuntu'])
        self.assertEqual((plan['lock']['usb_rows'], plan['store_bytes']), (1, 10), 'waves 1-3 on the USB, wave 4 optional')

    def test_app_bundle_is_one_commit_only(self):
        repo = self.t / 'repo'; repo.mkdir()
        g = ['git', '-C', str(repo), '-c', 'user.email=t@t', '-c', 'user.name=t', '-c', 'commit.gpgsign=false']
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        for rel in ('app/server.py', 'app/x.py', '.env.local', 'outputs/o.png', 'm.safetensors', 'server-kit/builder.py',
                    'docs/screenshots/s.png', 'requirements.txt'):
            p = repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('x')
        subprocess.run(g + ['add', '-A', '-f'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'c1'], check=True)
        (repo / 'app/untracked_secret.py').write_text('never shipped')   # not committed
        (repo / 'app/x.py').write_text('uncommitted change')              # not committed
        a, n, commit = builder.make_app_bundle(repo, self.t / 'b1.tgz'); b, _, _ = builder.make_app_bundle(repo, self.t / 'b2.tgz')
        self.assertEqual(a, b); self.assertRegex(commit, '^[0-9a-f]{40}$')
        tf = tarfile.open(self.t / 'b1.tgz')
        names = sorted(m.name for m in tf.getmembers() if m.isfile())
        self.assertEqual(names, ['app/server.py', 'app/x.py', 'requirements.txt'])
        self.assertEqual(tf.extractfile('app/x.py').read(), b'x', 'the committed file, not the working copy')

    @unittest.skipUnless(os.environ.get('CANDY_ISO'), 'set CANDY_ISO to the official ISO to scan it for real')
    def test_real_iso_scan(self):
        files, links, keep = builder.scan_iso(os.environ['CANDY_ISO'])
        self.assertIn('ubuntu', links); self.assertIn('boot/grub/grub.cfg', keep)
        self.assertLess(max(f['size'] for f in files), 4 * 1024 ** 3)


# ------------------------------------------------------------------ stager
def packages_gz(text):
    return gzip.compress(text.encode())


class Stager(Tmp):
    def kit(self):
        k = json.loads(json.dumps(KITCFG))
        k['apt']['sources'] = [{'id': 'ubuntu', 'uri': 'https://snap.test/ubuntu', 'suites': ['noble'], 'components': ['main'],
                                'flat': False, 'keyring': '/k'}]
        k['apt']['install'] = ['drv=1.0']
        return k

    def fake_get(self):
        pg = packages_gz(pkg('drv', '1.0', 'libc6') + '\n' + pkg('libc6', '2.39'))
        inrel = ('Origin: Ubuntu\nSHA256:\n ' + sha(pg) + f' {len(pg)} main/binary-amd64/Packages.gz\n').encode()
        pages = {'https://snap.test/ubuntu/dists/noble/InRelease': inrel, 'https://snap.test/ubuntu/dists/noble/main/binary-amd64/Packages.gz': pg}
        return lambda url: pages[url]

    def test_plan_apt_checks_indices_against_inrelease(self):
        idx, debs, unresolved = stage_store.plan_apt(self.kit(), self.fake_get())
        self.assertEqual([d['path'] for d in debs], ['apt/ubuntu/pool/drv_1.0.deb', 'apt/ubuntu/pool/libc6_2.39.deb'])
        self.assertEqual(unresolved, [])
        bad = self.fake_get()
        with self.assertRaises(stage_store.Refused):
            stage_store.plan_apt(self.kit(), lambda u: bad(u) + (b'tampered' if u.endswith('.gz') else b''))

    def test_plan_apt_refuses_unpaired_driver(self):
        k = self.kit(); k['apt']['install'] = ['nvidia-utils-580=2.0', 'linux-generic-hwe-24.04=7.0.0-42.42~24.04.1',
                                               'linux-modules-nvidia-580-open-generic-hwe-24.04=7.0.0-42.42~24.04.1']
        text = '\n'.join([pkg('nvidia-utils-580', '2.0'), pkg('linux-generic-hwe-24.04', '7.0.0-42.42~24.04.1', 'linux-image-7.0.0-42-generic'),
                          pkg('linux-image-7.0.0-42-generic', '7.0.0-42.42~24.04.1'),
                          pkg('linux-modules-nvidia-580-open-generic-hwe-24.04', '7.0.0-42.42~24.04.1', 'linux-modules-nvidia-580-open-7.0.0-42-generic'),
                          pkg('linux-modules-nvidia-580-open-7.0.0-42-generic', '7.0.0-42.42~24.04.1') + 'Built-Using: nvidia-dkms-580-open (= 1.0)\n'])
        pg = packages_gz(text)
        inrel = ('Origin: Ubuntu\nSHA256:\n ' + sha(pg) + f' {len(pg)} main/binary-amd64/Packages.gz\n').encode()
        pages = {'https://snap.test/ubuntu/dists/noble/InRelease': inrel, 'https://snap.test/ubuntu/dists/noble/main/binary-amd64/Packages.gz': pg}
        with self.assertRaises(stage_store.Refused) as e:
            stage_store.plan_apt(k, pages.__getitem__)
        self.assertIn('built from NVIDIA 1.0, but the userland pin is 2.0', str(e.exception))

    def test_find_data_volume_refusals(self):
        mac = FakeMac(); data = self.t / 'TURINDATA'; data.mkdir()
        mac.partition('disk9', str(self.t / 'TURINBOOT'), str(data))
        dl = diskinfo.make_denylist([d for d in diskinfo.inventory(mac.run) if d.device != 'disk9'], 't')
        disks = diskinfo.inventory(mac.run); uuid = 'D0000009-0000-4000-8000-00000000D002'
        with self.assertRaises(stage_store.Refused):  # no marker yet
            stage_store.find_data_volume(disks, '2345E6F7A8B9', uuid, dl, prefix=str(self.t))
        (data / marker.MARKER_NAME).write_text(json.dumps(marker.make('data', '2345E6F7A8B9', uuid, 'r', 't', 'v')))
        d, vol = stage_store.find_data_volume(disks, '2345E6F7A8B9', uuid, dl, prefix=str(self.t))
        self.assertEqual(vol.volume_name, 'TURINDATA')
        with self.assertRaises(stage_store.Refused):  # a data drive's serial
            stage_store.find_data_volume(disks, 'NAA1B2C3', '5A000000-0000-4000-8000-000000000001', dl, prefix=str(self.t))
        with self.assertRaises(stage_store.Refused):  # boot volume, not data
            stage_store.find_data_volume(disks, '2345E6F7A8B9', 'B0000009-0000-4000-8000-00000000B001', dl, prefix=str(self.t))

    def test_apply_downloads_verifies_resumes_and_writes_manifest(self):
        srv = self.t / 'srv'; srv.mkdir(); good = os.urandom(200_000); (srv / 'm.bin').write_bytes(good)
        store = self.t / 'store'
        with serve(srv) as url:
            entries = [{'kind': 'model', 'id': 'm1', 'path': 'models/comfy/m.bin', 'dest': 'comfy/m.bin', 'url': url + '/m.bin',
                        'size': len(good), 'sha256': sha(good)},
                       {'kind': 'model', 'id': 'm2', 'path': 'models/comfy/bad.bin', 'dest': 'comfy/bad.bin', 'url': url + '/m.bin',
                        'size': len(good), 'sha256': '0' * 64},
                       {'kind': 'model', 'id': 'g1', 'path': 'models/g.bin', 'dest': 'g.bin', 'url': url + '/m.bin', 'size': 1,
                        'sha256': '1' * 64, 'requires_token': 'HF_TOKEN'},
                       {'kind': 'lock', 'path': 'locks/kit.json', 'data': b'{}', 'size': 2, 'sha256': sha(b'{}')}]
            part = store / '.incoming' / (sha(good) + '.part'); part.parent.mkdir(parents=True); part.write_bytes(good[:50_000])
            lines = []
            st = stage_store.Stager(out=lines.append, git=lambda pin, s: (_ for _ in ()).throw(OSError('offline test')))
            env = {k: v for k, v in os.environ.items() if k not in ('HF_TOKEN', 'CIVITAI_API_TOKEN')}
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                doc = st.apply(store, entries, KITCFG, {'format': 'candy-server-kit.store/1'})
        self.assertEqual((store / 'models/comfy/m.bin').read_bytes(), good, 'resumed from .part')
        self.assertFalse((store / 'models/comfy/bad.bin').exists(), 'a wrong file never lands')
        man = json.loads((store / 'store-manifest.json').read_text())
        self.assertEqual(sorted(f['path'] for f in man['files']), ['locks/kit.json', 'models/comfy/m.bin'])
        self.assertIn('g1', man['missing']); self.assertIn('m2', man['missing'])
        self.assertNotIn('HF_TOKEN', json.dumps(man))
        self.assertEqual(doc['files'], man['files'])
        self.assertFalse(list((store / 'models').rglob('*.part')), 'partial files never sit among the models')

    def test_wheel_lock_text(self):
        t = stage_store.lock_text([{'name': 'Torch', 'version': '2.9.0+cu128', 'sha256': 'a' * 64}, {'name': 'six', 'version': '1.17.0', 'sha256': 'b' * 64}])
        self.assertEqual(t.splitlines(), ['six==1.17.0 --hash=sha256:' + 'b' * 64, 'Torch==2.9.0+cu128 --hash=sha256:' + 'a' * 64])


# ------------------------------------------------------------------ installer store import
class StoreImport(Tmp):
    def make_store(self):
        root = self.t / 'usb'; s = root / 'turin-store'
        files = {'models/comfy/a.bin': b'model-a', 'apt/ubuntu/pool/x.deb': b'deb', 'wheels/w.whl': b'wheel'}
        man = []
        for rel, data in files.items():
            p = s / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
            e = {'path': rel, 'size': len(data), 'sha256': sha(data), 'kind': 'model' if rel.startswith('models/') else 'apt'}
            if e['kind'] == 'model':
                e['dest'] = rel[len('models/'):]
            man.append(e)
        man.append({'path': 'models/corrupt.bin', 'size': 3, 'sha256': '0' * 64, 'kind': 'model', 'dest': 'corrupt.bin', 'id': 'bad1'})
        (s / 'models/corrupt.bin').write_bytes(b'abc')
        (s / 'store-manifest.json').write_text(json.dumps({'files': man, 'created': 't'}))
        (root / marker.MARKER_NAME).write_text(json.dumps(marker.make('data', 'S1', 'U1', 'r', 't', 'v')))
        return root

    def test_copy_verify_and_sidecars(self):
        target = self.t / 'target'; target.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            r = store_import.import_store(self.make_store(), target, out=lambda *a, **k: None, reserve=0)  # CI disks are small
        self.assertEqual((r['status'], r['copied'], r['bad']), ('partial', 3, ['bad1']))
        self.assertEqual((target / 'srv/ai/models/comfy/a.bin').read_bytes(), b'model-a')
        self.assertTrue(fetch.sidecar_ok(target / 'srv/ai/models/comfy/a.bin', sha(b'model-a')))
        self.assertTrue((target / 'var/lib/turin/store/apt/ubuntu/pool/x.deb').is_file())
        self.assertFalse((target / 'srv/ai/models/corrupt.bin').exists())

    def test_free_space_floor(self):
        target = self.t / 'target'; target.mkdir()
        r = store_import.import_store(self.make_store(), target, out=lambda *a, **k: None, reserve=10 ** 18)
        self.assertEqual(r['status'], 'no-space')

    def test_main_never_fails_the_install(self):
        target = self.t / 't'; target.mkdir()
        none = lambda argv, text=True: json.dumps({'blockdevices': [{'name': '/dev/nvme0n1', 'children': []}]})  # noqa: E731
        two = lambda argv, text=True: json.dumps({'blockdevices': [{'name': '/dev/sda', 'children': [  # noqa: E731
            {'name': '/dev/sda2', 'label': 'TURINDATA', 'fstype': 'exfat'}]}, {'name': '/dev/sdb', 'children': [
            {'name': '/dev/sdb2', 'label': 'TURINDATA', 'fstype': 'exfat'}]}]})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(store_import.main(['--target', str(target)], run=none), 0)
            self.assertEqual(json.loads((target / 'var/lib/turin/store-import.json').read_text())['status'], 'no-store')
            self.assertEqual(store_import.main(['--target', str(target)], run=two), 0)
            self.assertEqual(json.loads((target / 'var/lib/turin/store-import.json').read_text())['status'], 'ambiguous')


# ------------------------------------------------------------------ server disk guard (Grok Bot's guard, kept and tightened)
def nvme(name='nvme0n1', serial='S7EXAMPLE123', size=2000 * GB, **kw):
    return {'name': name, 'type': 'disk', 'serial': serial, 'model': 'Samsung SSD 990 PRO 2TB', 'size': size, 'fstype': None,
            'label': None, 'partlabel': None, 'pttype': None, 'mountpoint': None, 'mountpoints': [None], 'tran': 'nvme', 'rm': False,
            'hotplug': False, **kw}


class DiskGuard(Tmp):
    def run_guard(self, devices, mode='--select-blank-nvme', cfg=None, wipefs='', blkid_rc=2):
        c = cfg or {'approve_blank_disk_install': True}
        (self.t / 'i.json').write_text(json.dumps(c))
        auto = self.t / 'autoinstall.yaml'; audit = self.t / 'audit.json'
        auto.write_text(json.dumps({'autoinstall': {'version': 1, 'storage': {'layout': {'name': 'direct', 'match': {'serial': 'TURIN-DISK-GUARD-DID-NOT-RUN'}}}}}))

        def run(args, text=True):
            if args[0] == 'lsblk':
                return json.dumps({'blockdevices': devices})
            if args[0] == 'wipefs':
                return wipefs
            if args[0] == 'blkid':
                if blkid_rc:
                    raise subprocess.CalledProcessError(blkid_rc, args)
                return 'TYPE=ext4'
            if args[0] == 'udevadm':
                return 'ID_SERIAL=Samsung_SSD_990_PRO_2TB_S7EXAMPLE123\n'
            raise AssertionError(args)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            rc = guard.main([mode, str(self.t / 'i.json')], run=run, autoinstall=auto, audit=audit)
        return rc, auto.read_text()

    def test_one_blank_internal_nvme_selected(self):
        rc, text = self.run_guard([nvme(), {'name': 'sda', 'type': 'disk', 'tran': 'usb', 'size': 2000 * GB}])
        self.assertEqual(rc, 0); self.assertIn('/dev/nvme0n1', text)

    def test_refusals_leave_the_placeholder(self):
        usb_nvme = nvme('nvme1n1', 'S7USB', tran='usb')
        cases = {'usb nvme only': [usb_nvme], 'removable': [nvme(rm=True)], 'no transport': [nvme(tran=None)],
                 'master usb label': [nvme(children=[{'name': 'nvme0n1p2', 'label': 'TURINDATA'}])],
                 'two blank': [nvme(), nvme('nvme1n1', 'S7OTHER')], 'partitioned': [nvme(children=[{'name': 'p1'}])],
                 'keep label': [nvme(label='DATA_KEEP')], 'too small': [nvme(size=128 * GB)], 'pttype': [nvme(pttype='gpt')]}
        for name, devs in cases.items():
            rc, text = self.run_guard(devs)
            self.assertNotEqual(rc, 0, name); self.assertIn('TURIN-DISK-GUARD-DID-NOT-RUN', text, name)
        self.assertNotEqual(self.run_guard([nvme()], wipefs=json.dumps({'signatures': [{'type': 'gpt'}]}))[0], 0)
        self.assertNotEqual(self.run_guard([nvme()], blkid_rc=0)[0], 0)
        self.assertNotEqual(self.run_guard([nvme()], cfg={'approve_blank_disk_install': False})[0], 0)

    def test_bios_hotplug_flag_does_not_block_the_internal_nvme(self):
        rc, text = self.run_guard([nvme(hotplug=True)])
        self.assertEqual(rc, 0); self.assertIn('/dev/nvme0n1', text)

    def test_usb_nvme_beside_internal_is_ignored(self):
        rc, text = self.run_guard([nvme(), nvme('nvme1n1', 'S7USB', tran='usb')])
        self.assertEqual(rc, 0, 'the USB-attached NVMe is not counted, so the single internal one is used')
        self.assertIn('/dev/nvme0n1', text)


# ------------------------------------------------------------------ health + burn-in
GPU_LINE = '0, NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition, 00000000:41:00.0, 97887, 10, 35, 20.5, 300.00, 300, 3090, 5, 5, 16, 16, Enabled, Disabled, 580.178.04, 98.02, 0x0'
DMI = '\n\n'.join(f'Handle 0x00{i}, DMI type 17\nMemory Device\n\tSize: 64 GB\n\tLocator: DIMM_{s}\n\tBank Locator: P0 CHANNEL {s[0]}\n'
                  f'\tType: DDR5\n\tConfigured Memory Speed: 6000 MT/s\n\tPart Number: TESTPART\n' for i, s in enumerate(['A1', 'C1', 'G1', 'I1']))
DMI += '\n\nHandle 0x0099, DMI type 17\nMemory Device\n\tSize: No Module Installed\n\tLocator: DIMM_B1\n'
SDR = 'FAN1             | 30h | ok  | 29.1 | 1800 RPM\nFAN2             | 31h | ns  | 29.2 | No Reading\nCPU_PUMP         | 32h | ok  | 29.3 | 0 RPM\n'


class Health(unittest.TestCase):
    def report(self, gpu_lines, dimms=DMI, sdr=SDR):
        return {'gpus': health.parse_gpus(gpu_lines), 'memory': {'total_gib': 251.5, 'dimms': health.parse_dimms(dimms)},
                'cpu': {'model': 'AMD EPYC 9275F 24-Core Processor'}, 'bmc_fans': health.parse_sdr(sdr), 'nvme_smart': {},
                'nics': {'enp65s0f0np0': {'speed_mbps': 10000, 'state': 'up'}}}

    def test_parsers_and_good_machine(self):
        r = self.report(GPU_LINE + '\n' + GPU_LINE.replace('0, NVIDIA', '1, NVIDIA', 1), sdr='FAN1 | 30h | ok | 29.1 | 1800 RPM\n')
        self.assertEqual([health.slot_of(d['locator']) for d in r['memory']['dimms']], ['A1', 'C1', 'G1', 'I1'])
        v = health.evaluate(r)
        self.assertEqual(v['problems'], []); self.assertTrue(v['ok'])

    def test_problems_are_real_numbers(self):
        x8 = GPU_LINE.replace(', 16, 16,', ', 8, 8,')
        v = health.evaluate(self.report(x8, dimms=DMI.replace('DIMM_I1', 'DIMM_H1')))
        text = ' '.join(v['problems'])
        self.assertIn('1 GPU(s) visible', text); self.assertIn('x8', text); self.assertIn("'H1'", text); self.assertIn('CPU_PUMP reads 0 RPM', text)

    def test_burnin_limits(self):
        s = {'gpus': [{'index': '0', 'temp_c': 88.0}, {'index': '1', 'temp_c': 70.0}], 'cpu_tctl_c': 96.0, 'fans': [{'name': 'CPU_PUMP', 'rpm': 0}]}
        self.assertEqual(burnin.breach(s), ['GPU 0 at 88.0 C', 'CPU Tctl at 96.0 C', 'CPU_PUMP at 0 RPM'])
        self.assertEqual(burnin.breach({'gpus': [{'index': '0', 'temp_c': 80.0}], 'cpu_tctl_c': 80.0, 'fans': [{'name': 'F', 'rpm': 900}]}), [])


# ------------------------------------------------------------------ apt config, units, dashboard, in-target setup
class ServerConfig(Tmp):
    def test_apt_local_first_online_same_pins(self):
        store = self.t / 'store'; (store / 'apt/ubuntu').mkdir(parents=True); (store / 'apt/nvidia').mkdir(parents=True)
        files = {str(k): v for k, v in aptoff.render(KITCFG, store).items()}
        local = files['/etc/apt/sources.list.d/turin-local.sources']
        self.assertIn('URIs: file:' + str(store / 'apt/ubuntu'), local); self.assertIn('Targets: Packages', local)
        self.assertIn('Check-Valid-Until: no', local); self.assertNotIn('tailscale', local, 'no mirror staged -> online only')
        online = files['/etc/apt/sources.list.d/turin-online.sources']
        self.assertIn('https://snapshot.ubuntu.com/ubuntu/20261105T000000Z', online)
        self.assertEqual(online.count('Enabled: no'), 2, 'online copies of staged mirrors stay off until a miss')
        prefs = files['/etc/apt/preferences.d/turin-nvidia']
        self.assertIn('Pin: release o=NVIDIA\nPin-Priority: 100', prefs)
        self.assertIn('By-Hash "no"', files['/etc/apt/apt.conf.d/90turin'])

    def test_units_loopback_and_no_secrets(self):
        d = self.t / 'units'; d.mkdir(); names = units.main(d)
        for n in names:
            text = (d / f'{n}.service').read_text()
            self.assertNotIn('0.0.0.0', text); self.assertNotIn('secrets', text); self.assertIn('User=studio', text)
        self.assertIn('--listen 127.0.0.1 --port 8188', (d / 'turin-comfy0.service').read_text())

    def test_dashboard_self_test_on_loopback(self):
        r = subprocess.run([sys.executable, str(KIT / 'payload/turin-status-web.py'), '--self-test'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        src = (KIT / 'payload/turin-status-web.py').read_text()
        self.assertIn("p.add_argument('--host',default='127.0.0.1')", src)

    def test_install_services_in_a_fake_target(self):
        root = self.t / 'target'; fake = self.t / 'bin'; fake.mkdir(); log = self.t / 'calls'
        for name in ('ufw', 'systemctl', 'sshd', 'ssh-keygen', 'visudo', 'install', 'chmod', 'usermod'):
            body = 'printf "%s %s\\n" "$(basename "$0")" "$*" >> "$MOCK_LOG"'
            if name == 'install':  # like install -d: create every directory argument
                body = 'if [[ " $* " == *" -d "* ]]; then for a in "$@"; do [[ $a == /* ]] && mkdir -p "$a"; done; fi; ' + body
            (fake / name).write_text('#!/bin/bash\n' + body + '\n'); (fake / name).chmod(0o755)
        (root / 'opt/turin/config').mkdir(parents=True); (root / 'opt/turin/payload/bin').mkdir(parents=True)
        (root / 'opt/turin/config/install.json').write_text(json.dumps({'username': 'andrew'}))
        for d in ('etc/ufw', 'etc/systemd/system', 'etc/ssh', 'usr/local/bin', 'var/lib', 'var/log'):
            (root / d).mkdir(parents=True, exist_ok=True)  # what a real Ubuntu target already has
        (root / 'etc/ufw/ufw.conf').write_text('ENABLED=no\n')
        text = (KIT / 'payload/install_services.sh').read_text()
        import re
        text = re.sub(r'(?<=[ >"=])(/(?:opt|etc|var|run|usr/local)/)', lambda m: str(root) + m.group(1), text)  # one pass
        (self.t / 's.sh').write_text(text)
        fw = re.sub(r'(?<=[ >"=])(/(?:opt|etc|var|run|usr/local)/)', lambda m: str(root) + m.group(1), (KIT / 'payload/firewall_rules.sh').read_text())
        (root / 'opt/turin/payload/firewall_rules.sh').write_text(fw)
        r = subprocess.run(['bash', str(self.t / 's.sh')], env=dict(os.environ, PATH=f'{fake}:{os.environ["PATH"]}', MOCK_LOG=str(log)),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sshd = (root / 'etc/ssh/sshd_config.d/10-turin.conf').read_text()
        for line in ('PasswordAuthentication no', 'PermitRootLogin no', 'AllowUsers andrew', 'AllowTcpForwarding local', 'AllowAgentForwarding no'):
            self.assertIn(line, sshd)
        sudoers = (root / 'etc/sudoers.d/90-turin-admin').read_text()
        self.assertNotIn('NOPASSWD:ALL', sudoers.replace(' ', '')); self.assertNotIn('NOPASSWD: ALL', sudoers)
        self.assertIn('andrew ALL=(root) NOPASSWD: TURIN_HELPERS', sudoers)
        self.assertIn('/usr/bin/tailscale up --accept-dns\\=false --hostname\\=epyc-studio', sudoers)
        self.assertIn('usermod -aG sudo andrew', log.read_text())
        calls = log.read_text()
        self.assertIn('ufw default deny incoming', calls); self.assertNotIn('8099', calls); self.assertNotIn('ufw --force enable', calls)
        self.assertIn('visudo -cf', calls); self.assertIn('sshd -t', calls)
        self.assertIn('ENABLED=yes', (root / 'etc/ufw/ufw.conf').read_text())
        self.assertIn('--host 127.0.0.1 --port 8099', (root / 'etc/systemd/system/turin-status-web.service').read_text())
        self.assertFalse((root / 'var/lib/turin/ufw-deferred').exists())
        (fake / 'ufw').write_text('#!/bin/bash\nexit 1\n')  # ufw cannot run in this target: the install still goes on
        r = subprocess.run(['bash', str(self.t / 's.sh')], env=dict(os.environ, PATH=f'{fake}:{os.environ["PATH"]}', MOCK_LOG=str(log)),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((root / 'var/lib/turin/ufw-deferred').exists())
        self.assertIn('firewall_rules.sh', (KIT / 'payload/turin-provision.sh').read_text())

    def test_firewall_rules_exactly(self):
        lines = [ln.strip() for ln in (KIT / 'payload/firewall_rules.sh').read_text().splitlines() if ln.strip().startswith('ufw ')]
        expect = ['ufw default deny incoming', 'ufw default allow outgoing', 'ufw limit proto tcp from "$net" to any port 22',
                  'ufw allow proto udp from "$net" to any port 5353', 'ufw limit proto tcp from "$net" to any port 22',
                  'ufw allow proto udp from "$net" to any port 5353', 'ufw allow in on tailscale0 to any port 22 proto tcp']
        self.assertEqual(lines, expect, 'every firewall rule, nothing more')
        loops = [ln for ln in (KIT / 'payload/firewall_rules.sh').read_text().splitlines() if ln.startswith('for net in')]
        self.assertEqual(loops, ['for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16; do', 'for net in fe80::/10 fd00::/8; do'])
        for f in KIT.rglob('*.sh'):
            self.assertNotIn('41641', f.read_text(), f.name)

    def test_root_reports_only_under_var_lib_turin(self):
        for script, flag in (('turin-health.py', '--write'), ('turin-burnin.py', '--out')):
            r = subprocess.run([sys.executable, str(KIT / 'payload' / script), flag, '/etc/sudoers.d/x'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('/var/lib/turin/ only', r.stderr + r.stdout)

    def test_tokens_never_follow_a_redirect(self):
        seen = []

        class Rec(Quiet):
            def do_GET(self):
                seen.append((self.server.server_port, self.headers.get('Authorization')))
                if self.path == '/start':
                    self.send_response(302); self.send_header('Location', f'http://127.0.0.1:{other[0]}/file'); self.end_headers(); return
                body = b'payload'; self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        other = []
        with serve_handler(Rec) as b, serve_handler(Rec) as a:
            other.append(int(b.rsplit(':', 1)[1]))
            with unittest.mock.patch.dict(fetch.TOKEN_HOSTS, {'TEST_TOKEN': ('127.0.0.1',)}, clear=True):
                fetch.download(a + '/start', self.t / 'f.bin', 7, sha(b'payload'), tokens={'TEST_TOKEN': 'not-a-real-token'}, staging=self.t / 'stage')
        self.assertEqual(seen[0][1], 'Bearer not-a-real-token'); self.assertIsNone(seen[1][1], 'the redirect target never sees the token')
        self.assertEqual((self.t / 'f.bin').read_bytes(), b'payload'); self.assertFalse(list((self.t / 'stage').iterdir()))
        self.assertIsNone(fetch.token_for('https://huggingface.co.evil.test/x', {'HF_TOKEN': 'x'}))
        self.assertEqual(fetch.token_for('https://civitai.com/api/download/models/1', {'CIVITAI_API_TOKEN': 'c', 'HF_TOKEN': 'h'}), 'c')

    def test_no_foreign_keys_tokens_or_open_binds_anywhere(self):
        hits = []
        for p in KIT.rglob('*'):
            if p.is_file() and 'build' not in p.relative_to(KIT).parts and p.suffix in ('.py', '.sh', '.json', '.md', '.command', ''):
                t = p.read_text(errors='ignore')
                if ('box@' + 'grok') in t or ('AAAAC3NzaC1lZDI1NTE5AAAAIBfz' + '2ck209') in t:
                    hits.append(str(p))
                if p.parent.name in ('payload', 'bin') and "'0.0.0.0'" in t.replace('"0.0.0.0"', "'0.0.0.0'") and 'run_app' not in p.name:
                    hits.append(str(p) + ' binds 0.0.0.0')
        self.assertEqual(hits, [])


import unittest.mock  # noqa: E402

if __name__ == '__main__':
    unittest.main(verbosity=2)
