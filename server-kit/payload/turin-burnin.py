#!/usr/bin/env python3
"""Burn-in for the Candy GPU server: load both GPUs, the CPU and RAM, sample real readings, stop on any limit.

    ssh -t epyc-studio sudo turin-burnin --minutes 20            # GPUs + CPU + memory
    ssh -t epyc-studio sudo turin-burnin --minutes 5 --gpu-only

Run it only after the hardware checklist (pump at 100 %, its RPM seen in the BMC). It refuses to start if the BMC
reports no fan/pump readings unless you add --cooling-checked-by-hand. Every 5 s it records GPU temperature, power,
SM clock and throttle reasons, CPU Tctl and fan/pump RPM. It stops everything at once if a GPU passes 87 C, the CPU
passes 95 C, or any fan/pump reads 0 RPM. Afterwards it checks the kernel log for NVIDIA Xid, machine-check and EDAC
errors and stress-ng's memory verification. Report: /var/lib/turin/burnin-<time>.json (real numbers only).
"""
import argparse, json, os, re, signal, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('turin_health', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turin-health.py'))
health = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(health)

TORCH = '/srv/ai/ComfyUI/.venv/bin/python'
GPU_WORKER = r'''
import sys, time, torch
dev = torch.device('cuda:0'); n = 16384; secs = float(sys.argv[1])
a = torch.randn(n, n, device=dev, dtype=torch.bfloat16); b = torch.randn(n, n, device=dev, dtype=torch.bfloat16)
torch.cuda.synchronize(); t0 = time.time(); it = 0
while time.time() - t0 < secs:
    for _ in range(20): c = a @ b
    torch.cuda.synchronize(); it += 20
dt = time.time() - t0
print('TFLOPS %.1f' % (2 * n ** 3 * it / dt / 1e12), flush=True)
'''
LIMITS = {'gpu_c': 87.0, 'cpu_c': 95.0}


def sample(run=health.cmd):
    s = {'t': round(time.time(), 1)}
    s['gpus'] = [{'index': g['index'], 'temp_c': health.num(g['temperature.gpu']), 'power_w': health.num(g['power.draw']),
                  'sm_mhz': health.num(g['clocks.sm']), 'reasons': g.get('clocks_event_reasons.active')}
                 for g in health.parse_gpus(run(['nvidia-smi', '--query-gpu=' + health.GPU_FIELDS, '--format=csv,noheader,nounits']))]
    sens = run(['sensors', '-j'])
    tctl = None
    if sens:
        for chip, d in json.loads(sens).items():
            if chip.startswith('k10temp'):
                for label, v in d.items():
                    if isinstance(v, dict) and label.lower().startswith('tctl'):
                        tctl = next((x for k, x in v.items() if k.endswith('_input')), None)
    s['cpu_tctl_c'] = tctl
    s['fans'] = [{'name': f['name'], 'rpm': f['value']} for f in health.parse_sdr(run(['ipmitool', 'sdr', 'type', 'Fan']))
                 if f.get('unit', '').upper().startswith('RPM')]
    return s


def breach(s, limits=LIMITS):
    why = [f'GPU {g["index"]} at {g["temp_c"]} C' for g in s['gpus'] if (g['temp_c'] or 0) > limits['gpu_c']]
    if s.get('cpu_tctl_c') and s['cpu_tctl_c'] > limits['cpu_c']:
        why.append(f'CPU Tctl at {s["cpu_tctl_c"]} C')
    why += [f'{f["name"]} at 0 RPM' for f in s['fans'] if f['rpm'] == 0]
    return why


def kernel_errors(since, run=health.cmd):
    log = run(['journalctl', '-k', '--since', since, '--no-pager', '-o', 'cat']) or ''
    return {'nvidia_xid': [ln for ln in log.splitlines() if 'NVRM: Xid' in ln][:20],
            'machine_check': [ln for ln in log.splitlines() if re.search(r'mce:|Machine check|Hardware Error', ln)][:20],
            'edac': [ln for ln in log.splitlines() if 'EDAC' in ln and re.search(r'CE|UE|error', ln)][:20]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--minutes', type=float, default=20); ap.add_argument('--interval', type=float, default=5)
    ap.add_argument('--gpu-only', action='store_true'); ap.add_argument('--cooling-checked-by-hand', action='store_true')
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    if a.out and not os.path.realpath(a.out).startswith('/var/lib/turin/'):
        raise SystemExit('reports are written under /var/lib/turin/ only')
    if os.geteuid() != 0:
        raise SystemExit('run with sudo (dmidecode, ipmitool and the kernel log need root)')
    pre = health.collect(); verdict = health.evaluate(pre)
    if verdict['problems']:
        raise SystemExit('health check has problems; fix them first: ' + '; '.join(verdict['problems']))
    if not pre.get('bmc_fans') and not a.cooling_checked_by_hand:
        raise SystemExit('no fan/pump readings from the BMC. Check the pump RPM in the BMC web page, then add --cooling-checked-by-hand')
    secs = a.minutes * 60
    since = time.strftime('%Y-%m-%d %H:%M:%S')
    procs = []
    for g in pre['gpus']:
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=g['index'])
        procs.append(('gpu' + g['index'], subprocess.Popen([TORCH, '-c', GPU_WORKER, str(secs)], env=env, stdout=subprocess.PIPE, text=True)))
    if not a.gpu_only:
        procs.append(('cpu', subprocess.Popen(['stress-ng', '--cpu', '0', '--cpu-method', 'matrixprod', '--timeout', f'{int(secs)}s',
                                               '--metrics-brief'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
        procs.append(('memory', subprocess.Popen(['stress-ng', '--vm', '8', '--vm-bytes', '70%', '--verify', '--timeout', f'{int(secs)}s',
                                                  '--metrics-brief'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
    samples, stopped = [], []
    t0 = time.time()
    try:
        while time.time() - t0 < secs + 30 and any(p.poll() is None for _, p in procs):
            s = sample(); samples.append(s)
            stopped = breach(s)
            if stopped:
                break
            time.sleep(a.interval)
    finally:
        for _, p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
    results = {}
    for name, p in procs:
        try:
            out_text = p.communicate(timeout=60)[0] or ''
        except subprocess.TimeoutExpired:
            p.kill(); out_text = ''
        results[name] = {'exit': p.returncode, 'tail': out_text.strip().splitlines()[-5:]}
    peak = {'gpu_temp_c': max((g['temp_c'] or 0 for s in samples for g in s['gpus']), default=None),
            'gpu_power_w': max((g['power_w'] or 0 for s in samples for g in s['gpus']), default=None),
            'cpu_tctl_c': max((s['cpu_tctl_c'] or 0 for s in samples), default=None),
            'min_fan_rpm': min((f['rpm'] for s in samples for f in s['fans'] if f['rpm'] is not None), default=None)}
    errs = kernel_errors(since)
    mem_fail = any('fail' in ln.lower() for ln in results.get('memory', {}).get('tail', []))
    ok = not stopped and not any(errs.values()) and not mem_fail and all(r['exit'] in (0, None) for r in results.values())
    report = {'started': since, 'minutes_planned': a.minutes, 'seconds_run': round(time.time() - t0), 'stopped_because': stopped,
              'peak': peak, 'workers': results, 'kernel_errors': errs, 'samples': samples, 'pre_check': verdict, 'ok': ok}
    out = a.out or time.strftime('/var/lib/turin/burnin-%Y%m%d-%H%M%S.json')
    with open(out, 'w') as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != 'samples'}, indent=2))
    print('Report:', out)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
