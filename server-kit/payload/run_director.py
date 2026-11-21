#!/usr/bin/env python3
"""turin-director.service: start llama-server for the active Director profile once its GGUF is SHA256-verified.

The profile registry is the lead's llm_models.json; the GGUF files are the lock rows tagged with that profile id.
The card comes from the lead's placement.json (gpu_policy.director_plan): GPU 0 in hybrid mode by default (MoE
experts in RAM), a whole GPU 1 for a profile above 70 GB. It binds 127.0.0.1 only and starts once every file it needs
is SHA256-verified on disk (never on a timer).
"""
import os, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gpu_policy as gp  # noqa: E402
import kitfetch  # noqa: E402
import kitlock  # noqa: E402
LLAMA = '/srv/ai/llama.cpp/build/bin/llama-server'
ROOT = pathlib.Path('/srv/ai/models')


def files_for(pid, lock, lock_ids=None):
    """The profile's GGUF rows: by the registry's `lock_ids` when it has them (the lead's format), else by `profile`."""
    ids = set(lock_ids or [])
    rows = [r for r in lock['rows'] if (r['id'] in ids if ids else r.get('profile') == pid) and r['dest'].endswith('.gguf')]
    lora = [r for r in rows if 'lora' in r['dest'].rsplit('/', 1)[-1].lower()]
    main = sorted([r for r in rows if r not in lora and 'Engram' not in r['dest']], key=lambda r: r['dest'])
    return main, lora


def argv_for(pid, root=ROOT, locks=None):
    locks = locks or gp.LOCKS
    reg = gp.registry(locks); p = gp.profile(pid, reg)
    if p.get('remote'): raise SystemExit(f'{pid} is a remote pay-per-use profile; turin-director only serves local GGUF profiles')
    a = gp.launch_args(p)
    if not a['runtime'].lower().startswith('llama-server'):
        raise SystemExit(f'{pid} runtime is {a['runtime']!r}; this kit only installs llama.cpp llama-server (Strata for separate-Engram DeepSeek is not installed); '
                         'llama-server is not claimed to run it. Choose another profile: sudo turin-llm-profile qwen36_35b_a3b_abliterated_q8')
    lock = kitlock.load(locks / 'server_model_lock.json')
    main, lora = files_for(pid, lock, p.get('lock_ids'))
    if not main: raise SystemExit(f'{pid}: no SHA256-locked GGUF in server_model_lock.json (not downloaded by this kit)')
    argv = [LLAMA, '-m', str(pathlib.Path(root) / main[0]['dest']), '-ngl', '99', '-c', str(a['ctx']),
            '--host', '127.0.0.1', '--port', str(a['port']), '--alias', a['alias']]
    plan = gp.director_plan(p, gp.placement(locks))
    if a['override_tensors']:
        argv += ['-ot', a['override_tensors']]  # the registry's own offload wins
    else:
        argv += plan['adds']  # hybrid: MoE expert weights stay in system RAM, the rest on the card
    for r in lora: argv += ['--lora', str(pathlib.Path(root) / r['dest'])]
    return argv, main + lora, plan


def main():
    pid = gp.active_profile_id(); argv, needed, plan = argv_for(pid)
    root = ROOT
    while True:  # Wave 1 is still downloading on a fresh server: wait for verified bytes, never a timer
        missing = [r for r in needed if not kitfetch.verified(root / r['dest'], r['sha256'], r['size'])]
        if not missing: break
        print(f'{pid}: waiting for {len(missing)} verified file(s), e.g. {missing[0]["id"]}', flush=True); time.sleep(30)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=plan['gpus'])
    print(f'Starting on GPU {plan["gpus"]} ({plan["why"]}):', ' '.join(argv), flush=True)
    os.execve(argv[0], argv, env)


if __name__ == '__main__': main()
