#!/usr/bin/env python3
"""Mac <-> server link: key-only SSH over the wired LAN, with tunnels to the server's loopback-only services.

A DRY RUN unless you add --apply. It never touches ~/.ssh, the Mac's firewall, DNS or any system setting: its own
SSH config, known-hosts file and connection socket live in ~/.candy-server-kit/, and `setup --undo` removes exactly
what it created. The SSH key is Ak's, held by the 1Password SSH agent; this script only points at its public half.

    python3 server-kit/mac/candy_link.py setup --public-key ~/.candy-server-kit/epyc-studio.pub          # dry run
    python3 server-kit/mac/candy_link.py setup --public-key ~/.candy-server-kit/epyc-studio.pub --apply
    python3 server-kit/mac/candy_link.py connect --apply      # tunnels up, dashboard opens  (Connect-EPYC-Studio.command)
    python3 server-kit/mac/candy_link.py desktop --apply      # remote desktop via Screen Sharing (Open-Remote-Desktop.command)
    python3 server-kit/mac/candy_link.py status
    python3 server-kit/mac/candy_link.py disconnect --apply   # (Disconnect-EPYC-Studio.command)
    python3 server-kit/mac/candy_link.py setup --undo --apply # remove everything setup created

Ports on the Mac (127.0.0.1 only): 8099 dashboard, 7860 Easy Studio, 8188/8189 ComfyUI GPU 0/1, 8000 Director LLM,
15900 -> server 5900 remote desktop (macOS Screen Sharing refuses a loopback :5900).
"""
import argparse, json, os, pathlib, re, shlex, subprocess, sys

KIT = pathlib.Path(__file__).resolve().parents[1]
STATE = pathlib.Path('~/.candy-server-kit').expanduser()
CONFIG = STATE / 'ssh_config'
CREATED = STATE / 'created-by-candy-link.json'
OP_AGENT = '~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock'
APPS = [(8099, '/', 'dashboard'), (7860, '/', 'Easy Studio'), (8188, '/', 'ComfyUI GPU 0'), (8189, '/', 'ComfyUI GPU 1')]


def forwards():
    kit = json.loads((KIT / 'config' / 'kit.json').read_text())
    return [tuple(x) for x in kit['server']['mac_forwards']]


def render(host, user, public_key, agent=OP_AGENT, state=STATE, tailscale_ip=None):
    for v, what in ((host, 'host'), (user, 'user')):
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,253}', v or ''):
            raise SystemExit(f'invalid {what}: {v!r}')
    fw = ''.join(f'    LocalForward 127.0.0.1:{a} 127.0.0.1:{b}\n' for a, b in forwards())
    common = (f'    User {user}\n    IdentityFile "{public_key}"\n    IdentitiesOnly yes\n'
              + (f'    IdentityAgent "{agent}"\n' if agent and agent != 'none' else '')
              + f'    UserKnownHostsFile "{state}/known_hosts"\n    StrictHostKeyChecking ask\n    ForwardAgent no\n'
              f'    ForwardX11 no\n    ServerAliveInterval 30\n    ServerAliveCountMax 3\n    ControlMaster auto\n'
              f'    ControlPath "{state}/cm-%C"\n    ControlPersist 8h\n    ExitOnForwardFailure no\n' + fw)
    text = ('# Written by server-kit/mac/candy_link.py. Used only with `ssh -F` by the Candy scripts; ~/.ssh is untouched.\n'
            f'Host epyc-studio\n    HostName {host}\n' + common)
    if tailscale_ip:
        text += f'\nHost epyc-studio-ts\n    HostName {tailscale_ip}\n' + common
    return text


class Link:
    def __init__(self, apply=False, run=subprocess.run, out=print, state=STATE):
        self.apply, self.run, self.out, self.state = apply, run, out, state
        self.config, self.created = state / 'ssh_config', state / 'created-by-candy-link.json'

    def do(self, argv, **kw):
        self.out(('RUN: ' if self.apply else 'WOULD RUN: ') + ' '.join(shlex.quote(str(a)) for a in argv))
        if self.apply:
            return self.run(argv, **kw)
        return subprocess.CompletedProcess(argv, 0, '', '')

    def ssh(self, *args, host='epyc-studio'):
        return ['ssh', '-F', str(self.config), *args, host]

    def setup(self, a):
        if a.undo:
            return self.undo()
        pub = pathlib.Path(os.path.expanduser(a.public_key))
        if not pub.is_file() or 'PRIVATE KEY' in pub.read_text()[:200]:
            raise SystemExit(f'{pub}: export the PUBLIC key of your 1Password SSH key item to this file first')
        text = render(a.host, a.user, str(pub), a.identity_agent, self.state, a.tailscale_ip)
        self.out(('WRITE: ' if self.apply else 'WOULD WRITE: ') + str(self.config))
        self.out(text)
        if self.apply:
            made = []
            if not self.state.exists():
                self.state.mkdir(mode=0o700); made.append(str(self.state))
            if not self.config.exists():
                made.append(str(self.config))
            self.config.write_text(text); self.config.chmod(0o600)
            kh = self.state / 'known_hosts'
            if not kh.exists():
                kh.touch(mode=0o600); made.append(str(kh))
            old = json.loads(self.created.read_text()) if self.created.exists() else []
            self.created.write_text(json.dumps(sorted(set(old + made + [str(self.created)])), indent=1))
        return 0

    def undo(self):
        if not self.created.exists():
            self.out('Nothing to undo: candy_link.py setup has not created anything here.'); return 0
        made = json.loads(self.created.read_text())
        self.do(self.ssh('-O', 'exit'), capture_output=True)
        for p in sorted(made, key=len, reverse=True):
            pp = pathlib.Path(p)
            if not str(pp).startswith(str(self.state)):
                continue  # only ever inside ~/.candy-server-kit
            self.out(('REMOVE: ' if self.apply else 'WOULD REMOVE: ') + p)
            if self.apply:
                if pp.is_dir():
                    for sock in pp.glob('cm-*'):
                        sock.unlink()
                    try:
                        pp.rmdir()
                    except OSError:
                        self.out(f'  kept {p}: it holds files this script did not create')
                elif pp.exists():
                    pp.unlink()
        return 0

    def connected(self):
        return self.apply and self.run(self.ssh('-O', 'check'), capture_output=True).returncode == 0

    def connect(self, a, quiet=False):
        if not self.config.exists():
            raise SystemExit('Run `candy_link.py setup --public-key ... --apply` first.')
        host = 'epyc-studio-ts' if a.tailscale else 'epyc-studio'
        if not self.connected():
            self.out('Connecting (first time: compare the host-key fingerprint with the server console, then type yes) ...')
            if self.do(self.ssh('-fN', host=host)).returncode:
                self.out('Could not reach the server. Is it on, finished installing, and its host LAN cable plugged in?')
                return 1
        if not quiet:
            for port, path, name in APPS:
                self.do(['open', f'http://127.0.0.1:{port}{path}'])
        self.out('Connected. Disconnect: candy_link.py disconnect --apply')
        return 0

    def desktop(self, a):
        if self.connect(a, quiet=True):
            return 1
        if self.apply and self.run(self.ssh('turin-first-login', '--check'), capture_output=True).returncode:
            self.do(['ssh', '-F', str(self.config), '-t', 'epyc-studio', 'turin-first-login'])
        return self.do(['open', 'vnc://127.0.0.1:15900']).returncode

    def status(self, a):
        r = self.run(self.ssh('-O', 'check'), capture_output=True, text=True) if self.config.exists() else None
        self.out('tunnel: ' + ('up' if r is not None and r.returncode == 0 else 'down'))
        return 0

    def disconnect(self, a):
        self.do(self.ssh('-O', 'exit'), capture_output=True)
        return 0


def main(argv=None, link=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('command', choices=['setup', 'connect', 'desktop', 'status', 'disconnect'])
    ap.add_argument('--apply', action='store_true', help='really do it (default: show what would happen)')
    ap.add_argument('--undo', action='store_true', help='with setup: remove what setup created')
    ap.add_argument('--host', default='epyc-studio.local', help='server address on the wired LAN (mDNS name or fixed IP)')
    ap.add_argument('--user', default='andrew')
    ap.add_argument('--public-key', default='~/.candy-server-kit/epyc-studio.pub')
    ap.add_argument('--identity-agent', default=OP_AGENT, help='SSH agent socket (1Password by default; "none" to use your own)')
    ap.add_argument('--tailscale-ip', help='with setup: also add host epyc-studio-ts at this Tailscale IP')
    ap.add_argument('--tailscale', action='store_true', help='with connect/desktop: go over Tailscale instead of the LAN')
    a = ap.parse_args(argv)
    lk = link or Link(apply=a.apply)
    if not a.apply and a.command not in ('status',):
        lk.out('DRY RUN - nothing is changed. Add --apply to do it.')
    return getattr(lk, a.command)(a)


if __name__ == '__main__':
    sys.exit(main())
