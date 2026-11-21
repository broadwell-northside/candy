#!/usr/bin/env python3
"""Four plain questions -> server-kit/config/install.json, so nobody edits JSON. Changes nothing else on this Mac.

    python3 server-kit/mac/configure.py
    python3 server-kit/mac/configure.py --non-interactive --disk-mode auto --public-key ~/.candy-server-kit/epyc-studio.pub --checklist-done
"""
import argparse, json, os, pathlib, re, sys

KIT = pathlib.Path(__file__).resolve().parents[1]
OUT = KIT / 'config' / 'install.json'
EXAMPLE = KIT / 'config' / 'install.example.json'


def build(disk_mode, serial, public_key, checklist_done, hostname='epyc-studio', username='andrew'):
    if disk_mode not in ('auto', 'serial'):
        raise SystemExit('disk mode is auto or serial')
    if disk_mode == 'serial' and not re.fullmatch(r'[A-Za-z0-9_.-]{4,100}', serial or ''):
        raise SystemExit('That NVMe serial does not look right (letters, digits, - _ . only). Nothing was written.')
    pub = pathlib.Path(os.path.expanduser(public_key))
    if not pub.is_file():
        raise SystemExit(f'No public key at {pub}. In 1Password, open your SSH key item, use "Download public key" (or copy the '
                         'public key) and save it there. The kit never creates or reads a private key.')
    if not checklist_done:
        raise SystemExit('Work through server-kit/HARDWARE-CHECKLIST.md first. Nothing was written.')
    c = json.loads(EXAMPLE.read_text())
    c.pop('_comment', None)
    c.update(hostname=hostname, username=username, os_disk_mode='exact_serial' if disk_mode == 'serial' else 'auto_single_blank_nvme',
             os_disk_serial=serial if disk_mode == 'serial' else '', ssh_public_key_file=str(pub),
             approve_blank_disk_install=True, hardware_checklist_confirmed=True)
    return c


def main(argv=None, ask=input):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--non-interactive', action='store_true'); ap.add_argument('--disk-mode', choices=['auto', 'serial'])
    ap.add_argument('--disk-serial', default=''); ap.add_argument('--public-key', default='~/.candy-server-kit/epyc-studio.pub')
    ap.add_argument('--checklist-done', action='store_true'); ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args(argv)
    if a.non_interactive:
        c = build(a.disk_mode or 'auto', a.disk_serial, a.public_key, a.checklist_done)
    else:
        print('1) Which drive in the server gets Ubuntu?\n   [1] Automatic: the server has exactly ONE new, empty NVMe (it is checked; anything not blank stops the install)\n'
              '   [2] I will type the NVMe serial (needed if there is more than one NVMe)')
        mode = 'serial' if ask('   Type 1 or 2 [1]: ').strip() == '2' else 'auto'
        serial = ask('   NVMe serial (from the BIOS NVMe page or the SSD label): ').strip() if mode == 'serial' else ''
        print('2) Your SSH key: create it in 1Password (SSH key item) and save its PUBLIC key as a file.')
        pk = ask(f'   Public key file [{a.public_key}]: ').strip() or a.public_key
        print('3) Have you worked through every item in server-kit/HARDWARE-CHECKLIST.md (RAM slots, cables, pump at 100 %, BIOS)?')
        done = ask('   [y/N]: ').strip().lower().startswith('y')
        c = build(mode, serial, pk, done)
    out = pathlib.Path(a.out); tmp = out.with_suffix('.tmp')
    tmp.write_text(json.dumps(c, indent=2) + '\n'); os.replace(tmp, out)
    print(f'Saved {out}. Next: python3 server-kit/builder.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
