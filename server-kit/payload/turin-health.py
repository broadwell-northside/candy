#!/usr/bin/env python3
"""Hardware health report for the Candy GPU server: real readings, nothing assumed.

    sudo turin-health                 # print the report
    sudo turin-health --write /var/lib/turin/health.json

Reads: CPU (lscpu), memory and the populated DIMM slots (dmidecode), NVMe disks and their SMART health (nvme-cli),
both GPUs (nvidia-smi: VRAM, power limit, PCIe link generation and width, ECC, MIG, throttling), NIC link speeds,
Secure Boot state, CPU temperature (lm-sensors) and fan/pump RPM from the BMC (ipmitool). A reading that cannot be
taken is reported as unavailable, never guessed. Exit 0 = no problems, 1 = problems listed in the report.
"""
import argparse, glob, json, os, re, subprocess, sys, time

EXPECT = {'gpus': 2, 'gpu_name': 'RTX PRO 6000', 'gpu_min_mib': 89000, 'gpu_max_power_w': 300.5, 'pcie_width': 16,
          'pcie_gen': 5, 'dimm_slots': ['A1', 'C1', 'G1', 'I1'], 'ram_min_gib': 250, 'cpu': 'EPYC 9275F'}
GPU_FIELDS = ('index,name,pci.bus_id,memory.total,memory.used,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.max.sm,'
              'pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max,ecc.mode.current,'
              'mig.mode.current,driver_version,vbios_version,clocks_event_reasons.active')


def cmd(argv, timeout=20):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def num(s):
    try:
        return float(str(s).strip().split()[0])
    except (ValueError, IndexError):
        return None


def parse_gpus(csv_text):
    keys = GPU_FIELDS.split(',')
    out = []
    for line in (csv_text or '').strip().splitlines():
        vals = [v.strip() for v in line.split(',')]
        if len(vals) == len(keys):
            out.append(dict(zip(keys, vals)))
    return out


def parse_dimms(text):
    """dmidecode -t memory -> populated DIMMs (locator, size, speed, part)."""
    dimms = []
    for block in (text or '').split('\n\n'):
        if 'Memory Device' not in block:
            continue
        f = dict(re.findall(r'^\s*([^:\n]+):\s*(.*)$', block, flags=re.M))
        size = f.get('Size', '')
        if not size or 'No Module' in size or size.startswith('0'):
            continue
        dimms.append({'locator': f.get('Locator', ''), 'bank': f.get('Bank Locator', ''), 'size': size,
                      'speed': f.get('Configured Memory Speed') or f.get('Speed', ''), 'type': f.get('Type', ''),
                      'part': f.get('Part Number', '').strip(), 'ecc': f.get('Error Correction Type', '')})
    return dimms


def slot_of(locator):
    m = re.search(r'([A-L])\s*_?\s*(\d)\s*$', locator.upper())
    return m.group(1) + m.group(2) if m else locator


def parse_sdr(text):
    """ipmitool sdr type Fan / Temperature output -> [{name, value, unit, status}]."""
    rows = []
    for line in (text or '').splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 5:
            m = re.match(r'([\d.]+)\s*(\S.*)?', parts[4])
            rows.append({'name': parts[0], 'status': parts[2], 'value': float(m.group(1)) if m else None,
                         'unit': (m.group(2) or '').strip() if m else parts[4]})
    return rows


def collect():
    r = {'taken_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'kernel': os.uname().release}
    lscpu = cmd(['lscpu', '-J'])
    if lscpu:
        f = {x['field'].rstrip(':'): x['data'] for x in json.loads(lscpu).get('lscpu', [])}
        r['cpu'] = {'model': f.get('Model name'), 'sockets': f.get('Socket(s)'), 'cores_per_socket': f.get('Core(s) per socket'),
                    'threads': f.get('CPU(s)'), 'max_mhz': f.get('CPU max MHz'), 'numa_nodes': f.get('NUMA node(s)')}
    mem = open('/proc/meminfo').read() if os.path.exists('/proc/meminfo') else ''
    m = re.search(r'MemTotal:\s+(\d+) kB', mem)
    r['memory'] = {'total_gib': round(int(m.group(1)) / 1024 ** 2, 1) if m else None,
                   'dimms': parse_dimms(cmd(['dmidecode', '-t', 'memory']))}
    r['gpus'] = parse_gpus(cmd(['nvidia-smi', '--query-gpu=' + GPU_FIELDS, '--format=csv,noheader,nounits']))
    lsblk = cmd(['lsblk', '-J', '-b', '-d', '-o', 'NAME,MODEL,SERIAL,SIZE,TRAN,TYPE'])
    r['disks'] = json.loads(lsblk)['blockdevices'] if lsblk else None
    r['nvme_smart'] = {}
    for d in glob.glob('/dev/nvme[0-9]'):
        s = cmd(['nvme', 'smart-log', d, '-o', 'json'])
        if s:
            j = json.loads(s)
            r['nvme_smart'][d] = {k: j.get(k) for k in ('temperature', 'percent_used', 'media_errors', 'critical_warning')}
    r['nics'] = {}
    for p in sorted(glob.glob('/sys/class/net/*/speed')):
        name = p.split('/')[4]
        if name == 'lo':
            continue
        try:
            r['nics'][name] = {'speed_mbps': int(open(p).read().strip()), 'state': open(p.replace('speed', 'operstate')).read().strip()}
        except (OSError, ValueError):
            r['nics'][name] = {'speed_mbps': None}
    sb = cmd(['mokutil', '--sb-state'])
    r['secure_boot'] = sb.strip() if sb else 'unavailable'
    sens = cmd(['sensors', '-j'])
    if sens:
        temps = {}
        for chip, d in json.loads(sens).items():
            if chip.startswith('k10temp'):
                for label, v in d.items():
                    if isinstance(v, dict):
                        for k, x in v.items():
                            if k.endswith('_input'):
                                temps[label] = x
        r['cpu_temps_c'] = temps
    r['bmc_fans'] = parse_sdr(cmd(['ipmitool', 'sdr', 'type', 'Fan']))
    r['bmc_temps'] = parse_sdr(cmd(['ipmitool', 'sdr', 'type', 'Temperature']))
    mod = cmd(['modinfo', '-F', 'license', 'nvidia'])
    r['nvidia_module_license'] = mod.strip() if mod else 'unavailable'
    return r


def evaluate(r, e=EXPECT):
    problems, warnings = [], []
    g = r.get('gpus') or []
    if len(g) != e['gpus']:
        problems.append(f'{len(g)} GPU(s) visible to nvidia-smi, expected {e["gpus"]}')
    for x in g:
        i = x.get('index')
        if e['gpu_name'] not in x.get('name', ''):
            problems.append(f'GPU {i}: unexpected name {x.get("name")}')
        if (num(x.get('memory.total')) or 0) < e['gpu_min_mib']:
            problems.append(f'GPU {i}: only {x.get("memory.total")} MiB VRAM visible (check ECC/MIG)')
        if (num(x.get('power.limit')) or 0) > e['gpu_max_power_w']:
            warnings.append(f'GPU {i}: power limit {x.get("power.limit")} W is above the Max-Q 300 W')
        w = num(x.get('pcie.link.width.max'))
        if w is not None and w < e['pcie_width']:
            problems.append(f'GPU {i}: PCIe link is x{int(w)}, not x16 (wrong slot? PCIE1/PCIE3 are x8 on this board)')
        gen = num(x.get('pcie.link.gen.max'))
        if gen is not None and gen < e['pcie_gen']:
            warnings.append(f'GPU {i}: PCIe Gen{int(gen)} maximum (Gen5 expected; check the BIOS link setting or a riser)')
        if str(x.get('mig.mode.current', '')).lower() == 'enabled':
            warnings.append(f'GPU {i}: MIG is enabled')
    mem = r.get('memory') or {}
    if mem.get('total_gib') is not None and mem['total_gib'] < e['ram_min_gib']:
        problems.append(f'{mem["total_gib"]} GiB RAM visible, expected about 256')
    dimms = mem.get('dimms') or []
    if dimms:
        slots = sorted(slot_of(d['locator']) for d in dimms)
        if slots != sorted(e['dimm_slots']):
            problems.append(f'DIMMs in slots {slots}; the board manual (section 2.4) wants 4 DIMMs in {e["dimm_slots"]}')
    else:
        warnings.append('DIMM slots unreadable (dmidecode needs root)')
    cpu = (r.get('cpu') or {}).get('model') or ''
    if cpu and e['cpu'] not in cpu:
        warnings.append(f'CPU reports {cpu!r}, expected {e["cpu"]}')
    fans = r.get('bmc_fans') or []
    if not fans:
        warnings.append('no fan/pump readings from the BMC (ipmitool); check the pump RPM in the BMC web page')
    for f in fans:
        if f.get('unit', '').upper().startswith('RPM') and f.get('value') == 0 and f.get('status', '').lower() not in ('ns', 'na'):
            problems.append(f'BMC sensor {f["name"]} reads 0 RPM')
    for d, s in (r.get('nvme_smart') or {}).items():
        if s.get('critical_warning'):
            problems.append(f'{d}: NVMe critical warning {s["critical_warning"]}')
        if s.get('media_errors'):
            warnings.append(f'{d}: {s["media_errors"]} NVMe media errors')
    fast = [n for n, v in (r.get('nics') or {}).items() if (v.get('speed_mbps') or 0) >= 1000 and v.get('state') == 'up']
    if not fast:
        warnings.append('no wired link at 1 Gb/s or faster is up')
    return {'problems': problems, 'warnings': warnings, 'ok': not problems}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--write'); a = ap.parse_args(argv)
    if a.write and not os.path.realpath(a.write).startswith('/var/lib/turin/'):
        raise SystemExit('reports are written under /var/lib/turin/ only')
    r = collect(); r['verdict'] = evaluate(r)
    text = json.dumps(r, indent=2)
    if a.write:
        tmp = a.write + '.tmp'; open(tmp, 'w').write(text + '\n'); os.chmod(tmp, 0o644); os.replace(tmp, a.write)
    print(text)
    return 0 if r['verdict']['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
