#!/usr/bin/env python3
"""Build ComfyUI, llama.cpp and Easy Studio on the server, offline from the store when it is there.

Sources: /var/lib/turin/store/src/<id>-<commit>.tar.gz (made by stage_store.py with `git archive` after git itself
checked the pinned commit). Wheels: /var/lib/turin/store/wheels + one hash-locked requirements file per set.
Fallback when the store lacks something: the same pinned commit from GitHub (git verifies it) and the same locked
wheel versions from PyPI / the PyTorch cu128 index.
"""
import hashlib, json, pathlib, posixpath, subprocess, sys, tarfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

KIT = json.loads(pathlib.Path('/opt/turin/config/kit.json').read_text())
C = json.loads(pathlib.Path('/opt/turin/config/install.json').read_text())
STORE = pathlib.Path('/var/lib/turin/store')
BASE = pathlib.Path('/srv/ai')
NVCC = '/usr/local/cuda-12.8/bin/nvcc'


def run(args, cwd=None):
    subprocess.run(['runuser', '-u', 'studio', '--', *map(str, args)], cwd=cwd, check=True)


def safe_extract(archive, dest):
    """Regular files and directories only; no links, devices, absolute paths or '..'. Extracted as user studio."""
    with tarfile.open(archive) as tf:
        for m in tf.getmembers():
            p = pathlib.PurePosixPath(m.name)
            inside_link = m.issym() and not m.linkname.startswith('/') and not posixpath.normpath(
                posixpath.join(str(p.parent), m.linkname)).startswith('..')
            if p.is_absolute() or '..' in p.parts or not (m.isfile() or m.isdir() or inside_link):
                raise ValueError(f'unsafe member in {archive.name}')
    run(['tar', '-xzf', archive, '-C', dest, '--no-same-owner', '--no-same-permissions'])


def source(pin):
    dest = pathlib.Path(pin['dest'])
    stamp = dest / '.turin-commit'
    if stamp.is_file() and stamp.read_text().strip() == pin['commit']:
        return dest
    archive = STORE / 'src' / f'{pin["id"]}-{pin["commit"]}.tar.gz'
    dest.mkdir(parents=True, exist_ok=True); subprocess.run(['chown', 'studio:studio', str(dest)], check=True)
    if archive.is_file():
        safe_extract(archive, dest)
    else:  # fallback: the exact pinned commit; git checks the object hash
        if not (dest / '.git').exists():
            run(['git', 'init', dest]); run(['git', '-C', dest, 'remote', 'add', 'origin', pin['url']])
        run(['git', '-C', dest, 'fetch', '--depth', '1', 'origin', pin['commit']])
        run(['git', '-C', dest, 'checkout', '--detach', 'FETCH_HEAD'])
        got = subprocess.check_output(['git', '-c', 'safe.directory=' + str(dest), '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
        if got != pin['commit']:
            raise ValueError(f'{pin["id"]}: commit mismatch')
    stamp.write_text(pin['commit'] + '\n')
    subprocess.run(['chown', 'studio:studio', str(stamp)], check=True)
    return dest


def venv(dest, lockset):
    py = dest / '.venv/bin/python'
    if not py.exists():
        run(['python3', '-m', 'venv', dest / '.venv'])
    lock = STORE / 'wheels' / f'requirements-{lockset}.lock.txt'
    if lock.is_file():
        try:
            run([py, '-m', 'pip', 'install', '--no-index', '--find-links', STORE / 'wheels', '--require-hashes', '-r', lock])
            return py
        except subprocess.CalledProcessError:
            print(f'{lockset}: offline wheels incomplete; installing the same locked versions online', flush=True)
        run([py, '-m', 'pip', 'install', '--require-hashes', '--extra-index-url', KIT['software']['torch_index'], '-r', lock])
    else:
        print(f'{lockset}: no wheel lock in the store; installing online (unpinned fallback)', flush=True)
        if lockset == 'comfyui':
            run([py, '-m', 'pip', 'install', *KIT['software']['torch_packages'], '--index-url', KIT['software']['torch_index']])
        req = dest / 'requirements.txt'
        if req.exists():
            run([py, '-m', 'pip', 'install', '-r', req])
    return py


pins = {p['id']: p for p in KIT['software']['git_pins']}
comfy = source(pins['comfyui'])
py = venv(comfy, 'comfyui')
run([py, '-c', "import torch; assert torch.cuda.is_available(), 'CUDA not visible to torch'; "
     "assert 'sm_120' in torch.cuda.get_arch_list(), torch.cuda.get_arch_list()"])
# Every ComfyUI folder the lead's lock links into (comfy_link.type), plus the usual ones; easy_studio/* is the app's own.
import kitlock  # noqa: E402  (copy of server-kit/kitlib/lock.py, next to this file)
lock = kitlock.load(pathlib.Path('/opt/turin/locks/server_model_lock.json'))
groups = sorted({'diffusion_models', 'text_encoders', 'vae', 'loras', 'controlnet', 'clip_vision', 'checkpoints', 'upscale_models'}
                | {r['comfy_link']['type'] for r in lock['rows'] if r.get('comfy_link') and '/' not in r['comfy_link']['type']})
for g in groups:
    (BASE / 'models/comfy' / g).mkdir(parents=True, exist_ok=True)
(comfy / 'extra_model_paths.yaml').write_text('turin:\n  base_path: /srv/ai/models/comfy\n' + ''.join(f'  {g}: {g}\n' for g in groups))
subprocess.run(['chown', '-R', 'studio:studio', str(BASE / 'models/comfy'), str(comfy / 'extra_model_paths.yaml')], check=True)

llama = source(pins['llama.cpp'])
run(['cmake', '-S', llama, '-B', llama / 'build', '-DGGML_CUDA=ON', '-DCMAKE_CUDA_COMPILER=' + NVCC,
     '-DCMAKE_CUDA_ARCHITECTURES=120', '-DLLAMA_CURL=OFF', '-DCMAKE_BUILD_TYPE=Release'])
run(['cmake', '--build', llama / 'build', '--config', 'Release', '-j', '24', '--target', 'llama-server'])

# Runtimes pinned in the lead's lock (e.g. Strata for the DeepSeek GSQ/Engram profile): source at the pinned commit,
# a plain CMake + CUDA build. Optional and hardware_pending: a failure is logged and never stops provisioning.
for pin in lock['runtimes']:
    try:
        src_dir = source(pin)
        if pin['id'].lower() == 'strata':
            run(['cmake', '-S', src_dir, '-B', src_dir / 'build', '-DCMAKE_BUILD_TYPE=Release', '-DSTRATA_ENABLE_CUDA=ON',
                 '-DCMAKE_CUDA_COMPILER=' + NVCC, '-DCMAKE_CUDA_ARCHITECTURES=120'])
            run(['cmake', '--build', src_dir / 'build', '--target', 'strata', '-j', '24'])
        print(f'runtime {pin["id"]}: ready', flush=True)
    except (subprocess.CalledProcessError, ValueError, OSError) as e:
        print(f'runtime {pin["id"]}: not built ({e}); the profiles that need it stay off', flush=True)

if C.get('app_bundle'):
    if C['app_bundle'] != 'app-bundle.tar.gz':
        raise ValueError('unexpected app bundle name')
    src = pathlib.Path('/opt/turin/' + C['app_bundle'])
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    if h != C['app_bundle_sha256']:
        raise ValueError('app bundle checksum mismatch')
    safe_extract(src, BASE / 'app')
    venv(BASE / 'app', 'easy-studio')
    (BASE / 'app/.bundle-installed').touch()
print('setup_ai: done', flush=True)
sys.exit(0)
