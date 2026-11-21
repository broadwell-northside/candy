#!/usr/bin/env python3
"""Single source of truth on the server for the Director LLM profile and which GPU it uses.

Registry: /opt/turin/locks/llm_models.json (the lead's config/llm_models.json): model files, context, port, alias.
Placement: /opt/turin/locks/placement.json (the lead's app/placement.json, shared with the app): which card.
  - The Director normally runs on the placement's `director` lane (today GPU 0, port 8000, mode "hybrid": attention
    and KV cache on the card, MoE experts in system RAM via `-ot exps=CPU`), so the video lane keeps all of GPU 1.
  - Per profile (`director.profiles`, the lead's PR #50 format): only listed profiles share GPU 0, with their own
    mode and `launch_adds` (offload flags only); any unlisted profile takes GPU 1 alone and ComfyUI GPU 1 (:8189)
    is paused while it is loaded. Without that list, a profile above `exclusive_profiles.above_gb` (70 GB) does.
    A profile placed on both cards pauses GPU 1 too.
Active profile: /etc/turin-ai/llm-profile (written by `sudo turin-llm-profile <id>`), else LLM_PROFILE, else the
registry's default_profile.
"""
import json, os, pathlib, shlex, sys, urllib.parse
LOCKS = pathlib.Path(os.environ.get('TURIN_LOCKS', '/opt/turin/locks'))
PROFILE_FILE = pathlib.Path('/etc/turin-ai/llm-profile')


def registry(locks=None):
    return json.loads(((locks or LOCKS) / 'llm_models.json').read_text())


def placement(locks=None):
    path = (locks or LOCKS) / 'placement.json'
    try:
        return json.loads(path.read_text())
    except OSError:
        raise SystemExit(f'{path} is missing: the USB was built without app/placement.json; rebuild it with builder.py')


def active_profile_id(reg=None, profile_file=PROFILE_FILE):
    reg = reg or registry()
    try:
        chosen = profile_file.read_text().strip()
    except OSError:
        chosen = os.environ.get('LLM_PROFILE', '').strip()
    return chosen or reg['default_profile']


def profile(pid, reg=None):
    reg = reg or registry()
    for p in reg['profiles']:
        if p['id'] == pid: return p
    raise KeyError(f'unknown LLM profile {pid!r}')


def profile_gb(p):
    pl = p.get('placement') or {}
    return max(float(pl.get('gpu0_gb', 0) or 0), float(pl.get('gpu1_gb', 0) or 0))


# Flags a placement entry's `launch_adds` may carry: MoE/tensor offload only. Never --host, --port or anything else, so
# the placement file cannot open a port or change what the Director binds to.
OFFLOAD_FLAGS = {'-ot': True, '--override-tensor': True, '--cpu-moe': False, '-cmoe': False, '--n-cpu-moe': True, '-ncmoe': True}


def offload_args(text):
    """'-ot exps=CPU' -> ['-ot', 'exps=CPU'], refusing any flag that is not an offload flag."""
    toks, out = shlex.split(text or ''), []
    while toks:
        flag = toks.pop(0)
        if flag not in OFFLOAD_FLAGS:
            raise SystemExit(f'placement.json launch_adds may only carry offload flags ({", ".join(sorted(OFFLOAD_FLAGS))}), not {flag!r}')
        out.append(flag)
        if OFFLOAD_FLAGS[flag]:
            if not toks or toks[0].startswith('-'):
                raise SystemExit(f'placement.json launch_adds: {flag} needs a value')
            out.append(toks.pop(0))
    return out


def director_plan(p, place):
    """{'gpus': '0' | '1' | '0,1', 'hybrid': bool, 'adds': [argv...], 'pauses': [lane, ...], 'why': str} for profile p.

    With `director.profiles` (the lead's per-profile format): a listed profile runs on its own lane and mode; any
    unlisted one follows `director.unlisted_profiles` ("exclusive_gpu1": GPU 1 alone, video lane paused, whatever its
    size). Without it (the first format): the 70 GB size rule decides."""
    pl = p.get('placement') or {}
    lanes, ex, d = place['lanes'], place['exclusive_profiles'], place['director']
    exclusive = {'gpus': str(lanes[ex['pauses_lane']]['gpu']), 'hybrid': False, 'adds': [], 'pauses': [ex['pauses_lane']]}
    if float(pl.get('gpu0_gb', 0) or 0) > 0 and float(pl.get('gpu1_gb', 0) or 0) > 0:
        return {'gpus': f"{lanes['gpu0']['gpu']},{lanes['gpu1']['gpu']}", 'hybrid': False, 'adds': [], 'pauses': [ex['pauses_lane']],
                'why': 'placed on both cards'}
    listed = d.get('profiles')
    if listed is not None:
        if p['id'] in listed:
            e = listed[p['id']]
            hybrid = e.get('mode') == 'hybrid'
            adds = offload_args(e.get('launch_adds', '-ot exps=CPU' if hybrid else ''))
            return {'gpus': str(lanes[e['lane']]['gpu']), 'hybrid': hybrid, 'adds': adds,
                    'pauses': [ex['pauses_lane']] if e['lane'] == ex['pauses_lane'] else [],
                    'why': f'listed in director.profiles: {e["lane"]} ({e.get("mode", "full")})'}
        if d.get('unlisted_profiles') == 'exclusive_gpu1':
            return dict(exclusive, why='not listed in director.profiles: GPU1 alone')
        raise SystemExit(f'placement.json director.unlisted_profiles is {d.get("unlisted_profiles")!r}; this kit knows only "exclusive_gpu1"')
    if profile_gb(p) > float(ex['above_gb']):
        return dict(exclusive, why=f'{profile_gb(p):g} GB is above {ex["above_gb"]} GB: exclusive {ex["pauses_lane"]}')
    hybrid = d.get('mode') == 'hybrid'
    return {'gpus': str(lanes[d['lane']]['gpu']), 'hybrid': hybrid, 'adds': ['-ot', 'exps=CPU'] if hybrid else [], 'pauses': [],
            'why': f'director lane {d["lane"]} ({d.get("mode", "full")})'}


def comfy1_allowed(p, place=None):
    return 'gpu1' not in director_plan(p, place or placement())['pauses']


def launch_args(p):
    """Port / context / alias from the registry's own launch line, so both kits can never disagree."""
    toks = shlex.split(p.get('launch', ''))
    def opt(flag, default=None):
        return toks[toks.index(flag) + 1] if flag in toks else default
    port = int(opt('--port', urllib.parse.urlparse(p['base_url']).port or 0))
    return {'port': port, 'ctx': int(opt('-c', '8192')), 'alias': opt('--alias', p.get('served_model_name', 'local-director')),
            'override_tensors': opt('-ot'), 'runtime': p.get('runtime', '')}


if __name__ == '__main__':
    reg = registry(); place = placement(); pid = active_profile_id(reg); p = profile(pid, reg)
    plan = director_plan(p, place); ok = 'gpu1' not in plan['pauses']
    if sys.argv[1:] == ['--allow-comfy1']:
        print(f'{pid}: ComfyUI GPU1 {"allowed" if ok else "paused (" + plan["why"] + ")"}'); sys.exit(0 if ok else 1)
    print(json.dumps({'profile': pid, 'comfy1_allowed': ok, 'director': plan, **launch_args(p)}))
