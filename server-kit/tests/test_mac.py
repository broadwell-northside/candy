"""Mac link, Tailscale scripts and the configure wizard: dry runs change nothing, --apply writes only inside the kit's
own state folder, --undo removes exactly that. No real ssh, tailscale or open is ever started here."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

KIT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / 'mac'))
import candy_link  # noqa: E402
import configure  # noqa: E402


class MacTmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(); self.t = pathlib.Path(self._t.name)
        self.pub = self.t / 'epyc.pub'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'test-only', '-f', str(self.t / 'epyc')], check=True)
        (self.t / 'epyc').unlink()

    def tearDown(self):
        self._t.cleanup()


class Link(MacTmp):
    def link(self, apply):
        self.calls, self.lines = [], []

        def run(argv, **kw):
            self.calls.append(argv); return subprocess.CompletedProcess(argv, 1 if argv[-2:] == ['-O', 'check'] or '-O' in argv and 'check' in argv else 0, '', '')
        return candy_link.Link(apply=apply, run=run, out=self.lines.append, state=self.t / 'state')

    def args(self, *extra):
        return ['--public-key', str(self.pub), *extra]

    def test_config_text(self):
        text = candy_link.render('epyc-studio.local', 'andrew', str(self.pub), candy_link.OP_AGENT, self.t / 'state', '100.64.1.2')
        self.assertIn('Host epyc-studio\n    HostName epyc-studio.local', text); self.assertIn('Host epyc-studio-ts\n    HostName 100.64.1.2', text)
        self.assertIn('IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"', text)
        self.assertIn(f'UserKnownHostsFile "{self.t / "state"}/known_hosts"', text)
        for a, b in ((8099, 8099), (7860, 7860), (8188, 8188), (8189, 8189), (8000, 8000), (15900, 5900)):
            self.assertIn(f'LocalForward 127.0.0.1:{a} 127.0.0.1:{b}', text)
        self.assertIn('ForwardAgent no', text); self.assertNotIn('.ssh/', text)
        with self.assertRaises(SystemExit):
            candy_link.render('bad host; rm', 'andrew', str(self.pub))

    def test_dry_run_changes_nothing(self):
        lk = self.link(False)
        self.assertEqual(candy_link.main(['setup', *self.args()], link=lk), 0)
        self.assertFalse((self.t / 'state').exists()); self.assertEqual(self.calls, [])
        self.assertIn('DRY RUN - nothing is changed. Add --apply to do it.', self.lines)

    def test_apply_then_undo(self):
        lk = self.link(True)
        candy_link.main(['setup', *self.args(), '--apply'], link=lk)
        cfg = self.t / 'state/ssh_config'
        self.assertTrue(cfg.is_file()); self.assertEqual(cfg.stat().st_mode & 0o777, 0o600)
        (self.t / 'state/ignored-user-file').write_text('x')
        candy_link.main(['setup', '--undo', '--apply'], link=lk)
        self.assertFalse(cfg.exists()); self.assertFalse((self.t / 'state/known_hosts').exists())
        self.assertTrue((self.t / 'state/ignored-user-file').exists(), 'undo never removes what it did not create')
        self.assertIn(['ssh', '-F', str(cfg), '-O', 'exit', 'epyc-studio'], self.calls)

    def test_connect_and_desktop_dry_run(self):
        lk = self.link(True); candy_link.main(['setup', *self.args(), '--apply'], link=lk)
        lk2 = candy_link.Link(apply=False, run=lambda *a, **k: (_ for _ in ()).throw(AssertionError('dry run ran a command')),
                              out=self.lines.append, state=self.t / 'state')
        candy_link.main(['desktop'], link=lk2)
        text = '\n'.join(self.lines)
        self.assertIn('WOULD RUN: ssh -F ' + str(self.t / 'state/ssh_config') + ' -fN epyc-studio', text)
        self.assertIn('WOULD RUN: open vnc://127.0.0.1:15900', text)

    def test_tailscale_scripts_dry_run_keep_dns(self):
        for script, expect in (('tailscale_mac.sh', '--accept-dns=false'), ('tailscale_server.sh', '--accept-dns=false')):
            r = subprocess.run(['bash', str(KIT / 'mac' / script)], capture_output=True, text=True, env=dict(os.environ, PATH='/usr/bin:/bin'))
            self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('DRY RUN', r.stdout); self.assertIn(expect, r.stdout)
            r = subprocess.run(['bash', str(KIT / 'mac' / script), '--undo'], capture_output=True, text=True)
            self.assertIn('down', r.stdout)
        for name in ('tailscale_mac.sh', 'tailscale_server.sh', 'candy_link.py'):
            t = (KIT / 'mac' / name).read_text()
            if name == 'tailscale_server.sh':  # its only sudo runs on the server, inside the SSH command
                t = t.replace("'sudo tailscale", "'tailscale")
            for bad in ('socketfilterfw', 'networksetup', 'scutil --set', 'sudo ', '--accept-dns=true', 'ssh-keygen -t'):
                self.assertNotIn(bad, t, f'{name}: {bad}')

    def test_launchers_call_the_link_script(self):
        for name, cmd in (('Connect-EPYC-Studio.command', 'connect'), ('Open-Remote-Desktop.command', 'desktop'),
                          ('Disconnect-EPYC-Studio.command', 'disconnect')):
            t = (KIT / 'mac' / name).read_text()
            self.assertIn(f'candy_link.py" {cmd} --apply', t); self.assertEqual(subprocess.run(['bash', '-n', str(KIT / 'mac' / name)]).returncode, 0)


class Configure(MacTmp):
    def test_non_interactive(self):
        out = self.t / 'install.json'
        configure.main(['--non-interactive', '--disk-mode', 'serial', '--disk-serial', 'S7XYZ123', '--public-key', str(self.pub),
                        '--checklist-done', '--out', str(out)])
        c = json.loads(out.read_text())
        self.assertEqual((c['os_disk_mode'], c['os_disk_serial']), ('exact_serial', 'S7XYZ123'))
        self.assertTrue(c['approve_blank_disk_install'] and c['hardware_checklist_confirmed'])
        with self.assertRaises(SystemExit):
            configure.main(['--non-interactive', '--public-key', str(self.pub), '--out', str(self.t / 'x.json')])
        with self.assertRaises(SystemExit):
            configure.main(['--non-interactive', '--public-key', str(self.t / 'missing.pub'), '--checklist-done', '--out', str(self.t / 'x.json')])
        self.assertFalse((self.t / 'x.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
