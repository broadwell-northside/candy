"""The start and stop commands for the Mac (start_mac.command, start_mac.sh, stop_mac.sh), on stand-ins: nothing real is started.

A stand-in engine and a stand-in app answer on two free loopback ports. The checks: the command refuses in plain
words when the engine is not installed, its check mode starts nothing, it starts both on 127.0.0.1 only with the
right settings, and stopping it stops what it started."""
import json
import os
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "start_mac.sh")
NAMES = ("start_mac.command", "start_mac.sh", "stop_mac.sh")

STAND_IN = '''import http.server, json, os, sys
port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else int(os.environ["EASY_STUDIO_PORT"])
host = sys.argv[sys.argv.index("--listen") + 1] if "--listen" in sys.argv else os.environ["EASY_STUDIO_HOST"]
seen = {"argv": sys.argv[1:], "cwd": os.getcwd(), "env": {k: v for k, v in os.environ.items() if k.startswith(("EASY_STUDIO_", "COMFY_"))}}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(seen).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a):
        pass
http.server.HTTPServer((host, port), H).serve_forever()
'''


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return json.loads(r.read().decode())
    except (OSError, ValueError):
        return None


def _runtime():
    """A runtime folder whose two Pythons are this interpreter and whose engine is the stand-in."""
    rt = tempfile.mkdtemp(prefix="es_rt_")
    for venv in ("venv", "app-venv"):
        os.makedirs(os.path.join(rt, venv, "bin"))
        os.symlink(sys.executable, os.path.join(rt, venv, "bin", "python"))
    os.makedirs(os.path.join(rt, "ComfyUI"))
    with open(os.path.join(rt, "ComfyUI", "main.py"), "w", encoding="utf-8") as f:
        f.write(STAND_IN)
    return rt


def _app_folder():
    """A copy of the command next to a stand-in app/server.py, so the real app is not started."""
    folder = tempfile.mkdtemp(prefix="es_app_")
    os.makedirs(os.path.join(folder, "app"))
    with open(os.path.join(folder, "app", "server.py"), "w", encoding="utf-8") as f:
        f.write(STAND_IN)
    for name in NAMES:
        with open(os.path.join(ROOT, name), encoding="utf-8") as src, open(os.path.join(folder, name), "w", encoding="utf-8") as dst:
            dst.write(src.read())
        os.chmod(os.path.join(folder, name), 0o755)
    return folder, os.path.join(folder, "start_mac.command")  # the double-click file, which runs start_mac.sh


def unit(check):
    print("\n[start] The one start command for the Mac")
    text = open(SCRIPT, encoding="utf-8").read()
    check("the three commands are there and can be run",
          all(os.stat(os.path.join(ROOT, n)).st_mode & stat.S_IXUSR and open(os.path.join(ROOT, n)).read().startswith("#!/bin/bash") for n in NAMES))
    check("their shell syntax is right", all(subprocess.run(["bash", "-n", os.path.join(ROOT, n)]).returncode == 0 for n in NAMES))
    check("it names no address but this computer", "0.0.0.0" not in text and "--listen 127.0.0.1" in text and "EASY_STUDIO_HOST=127.0.0.1" in text)
    every = " ".join(open(os.path.join(ROOT, n), encoding="utf-8").read().lower() for n in NAMES)
    check("they set no password, token or key", not any(w in every for w in ("password", "token", "secret", "api_key")))

    folder, script = _app_folder()
    env = dict(os.environ, CANDY_RUNTIME=os.path.join(folder, "nowhere"), NO_OPEN="1")
    got = subprocess.run([script, "--check"], env=env, capture_output=True, text=True, timeout=30)
    check("no engine installed: it stops and says so in plain words", got.returncode == 1 and "not installed" in got.stdout, got.stdout)

    rt = _runtime()
    engine, app, data = _free_port(), _free_port(), os.path.join(folder, "data")
    env = dict(os.environ, CANDY_RUNTIME=rt, COMFY_PORT=str(engine), EASY_STUDIO_PORT=str(app), EASY_STUDIO_OUTPUTS=data, NO_OPEN="1")
    env.pop("EASY_STUDIO_MACHINE", None)
    got = subprocess.run([script, "--check"], env=env, capture_output=True, text=True, timeout=30)
    check("check mode says what would start and starts nothing",
          got.returncode == 0 and got.stdout.count("would start") == 2 and "Nothing was started." in got.stdout
          and _get("http://127.0.0.1:%d/" % engine) is None and not os.path.exists(data), got.stdout)

    proc = subprocess.Popen([script], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    seen_engine = seen_app = None
    for _ in range(80):
        seen_engine, seen_app = _get("http://127.0.0.1:%d/system_stats" % engine), _get("http://127.0.0.1:%d/" % app)
        if (seen_engine and seen_app) or proc.poll() is not None:
            break
        time.sleep(0.25)
    try:
        check("it starts the engine and the app, each answering on this computer", bool(seen_engine) and bool(seen_app), (seen_engine, seen_app))
        argv = (seen_engine or {}).get("argv") or []
        check("the engine listens on 127.0.0.1 only, from its own folder",
              argv == ["--listen", "127.0.0.1", "--port", str(engine)] and os.path.realpath((seen_engine or {}).get("cwd", "")) == os.path.realpath(os.path.join(rt, "ComfyUI")), argv)
        e = (seen_app or {}).get("env") or {}
        check("the app is told: this computer only, this engine, the engine's folders, the Mac profile, where work is kept",
              e.get("EASY_STUDIO_HOST") == "127.0.0.1" and e.get("COMFY_URL") == "http://127.0.0.1:%d" % engine
              and e.get("COMFY_DIR") == os.path.join(rt, "ComfyUI") and e.get("COMFY_PYTHON") == os.path.join(rt, "venv", "bin", "python")
              and e.get("EASY_STUDIO_MACHINE") == "m5_max" and e.get("EASY_STUDIO_OUTPUTS") == data and os.path.isdir(data), e)
        check("the app runs from the folder the command is in", os.path.realpath((seen_app or {}).get("cwd", "")) == os.path.realpath(folder))
        check("neither answers on another address of this computer", all(not _other_address_answers(p) for p in (engine, app)))
        again = subprocess.run([script, "--check"], env=env, capture_output=True, text=True, timeout=60)
        check("run again while both are up: it finds them and would start nothing new", again.stdout.count("already running") == 2, again.stdout)
    finally:
        try:
            os.kill(proc.pid, signal.SIGTERM)  # not SIGINT: a test run in the background has it switched off
        except OSError:
            pass
        try:
            out = proc.communicate(timeout=20)[0]
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out = proc.communicate()[0]
    for _ in range(40):
        if _get("http://127.0.0.1:%d/system_stats" % engine) is None and _get("http://127.0.0.1:%d/" % app) is None:
            break
        time.sleep(0.25)
    check("stopping it stops the engine and the app it started",
          _get("http://127.0.0.1:%d/system_stats" % engine) is None and _get("http://127.0.0.1:%d/" % app) is None, out[-300:])
    check("it wrote a log for each under the runtime folder", len(os.listdir(os.path.join(rt, "logs"))) == 2, os.listdir(os.path.join(rt, "logs")))
    check("it leaves no pid file behind", not [f for f in os.listdir(rt) if f.endswith(".pid")], os.listdir(rt))

    flagged = subprocess.run([script, "--check"], env=dict(env, COMFY_FLAGS="--force-fp16 --listen 0.0.0.0"), capture_output=True, text=True, timeout=30)
    check("an extra engine flag cannot change where the engine listens", flagged.returncode == 1 and "must not set --listen" in flagged.stdout, flagged.stdout)
    fine = subprocess.run([script, "--check"], env=dict(env, COMFY_FLAGS="--force-fp16"), capture_output=True, text=True, timeout=30)
    check("another extra engine flag is passed on", fine.returncode == 0 and "--force-fp16" in fine.stdout, fine.stdout)

    # A port that answers but is a link to another computer is not taken for the engine on this Mac.
    tools = tempfile.mkdtemp(prefix="es_tools_")
    with open(os.path.join(tools, "ps"), "w", encoding="utf-8") as f:  # a process list that has an ssh link to a server on that port
        f.write("#!/bin/bash\nprintf 'ssh -N -L %d:server:8188 someone@host\\n'\n" % engine)
    os.chmod(os.path.join(tools, "ps"), 0o755)
    stand_in = subprocess.Popen([sys.executable, os.path.join(rt, "ComfyUI", "main.py"), "--listen", "127.0.0.1", "--port", str(engine)])
    try:
        for _ in range(40):
            if _get("http://127.0.0.1:%d/system_stats" % engine):
                break
            time.sleep(0.25)
        linked = subprocess.run([script], env=dict(env, PATH=tools + os.pathsep + env.get("PATH", "")), capture_output=True, text=True, timeout=60)
        check("no command of the start script calls lsof, which can hang for good on a Mac with a stuck volume",
              not [ln for ln in open(SCRIPT, encoding="utf-8") if "lsof" in ln.split("#")[0]])
        check("a port that is a link to another computer is refused, and the app is not started",
              linked.returncode == 1 and "link to another computer" in linked.stdout and _get("http://127.0.0.1:%d/" % app) is None, linked.stdout)
        for name, line, refused in (("the server kit's own tunnel (its forward is in an ssh config file)", "ssh -N -F /Users/x/.candy-server-kit/ssh_config candy-server", True),
                                    ("an ssh program that forwards some other port", "ssh -N -L 9999:server:9999 someone@host", False),
                                    ("an ssh login that forwards nothing", "ssh someone@host", False)):
            other_tools = tempfile.mkdtemp(prefix="es_tools2_")
            with open(os.path.join(other_tools, "ps"), "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\nprintf '%s\\n'\n" % line)
            os.chmod(os.path.join(other_tools, "ps"), 0o755)
            got = subprocess.run([script, "--check"], env=dict(env, PATH=other_tools + os.pathsep + env.get("PATH", "")), capture_output=True, text=True, timeout=60)
            check("%s: %s" % (name, "refused as a link to another computer" if refused else "not mistaken for one"),
                  (got.returncode == 1 and "link to another computer" in got.stdout) if refused else (got.returncode == 0 and "Engine: already running" in got.stdout), got.stdout)
        local = subprocess.run([script, "--check"], env=env, capture_output=True, text=True, timeout=30)
        check("an engine already running on this Mac is used, and the command says which program answered",
              local.returncode == 0 and "Engine: already running" in local.stdout and "program:" in local.stdout, local.stdout)
    finally:
        stand_in.kill()
        stand_in.wait()

    # The stop command, from another window: start again, then stop_mac.sh.
    stop = os.path.join(folder, "stop_mac.sh")
    idle = subprocess.run([stop], env=env, capture_output=True, text=True, timeout=30)
    check("the stop command with nothing running says so and stops nothing", idle.returncode == 0 and "Nothing to stop" in idle.stdout, idle.stdout)
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with open(os.path.join(rt, "start_mac.app.pid"), "w", encoding="utf-8") as f:
        f.write(str(other.pid))  # a number left over from before a restart, now another program's
    stale = subprocess.run([stop], env=env, capture_output=True, text=True, timeout=30)
    check("a saved number that now belongs to another program is left alone, and the file is cleared",
          other.poll() is None and "left alone" in stale.stdout and "Stopped the" not in stale.stdout
          and not os.path.exists(os.path.join(rt, "start_mac.app.pid")), stale.stdout)
    other.kill()
    proc = subprocess.Popen([script], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        for _ in range(80):
            if _get("http://127.0.0.1:%d/system_stats" % engine) and _get("http://127.0.0.1:%d/" % app):
                break
            time.sleep(0.25)
        bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        done = subprocess.run([stop], env=env, capture_output=True, text=True, timeout=30)
        for _ in range(40):
            if _get("http://127.0.0.1:%d/system_stats" % engine) is None and _get("http://127.0.0.1:%d/" % app) is None:
                break
            time.sleep(0.25)
        check("the stop command stops the engine and the app that the start command started",
              done.stdout.count("Stopped the") == 2 and _get("http://127.0.0.1:%d/system_stats" % engine) is None
              and _get("http://127.0.0.1:%d/" % app) is None and not [f for f in os.listdir(rt) if f.endswith(".pid")], done.stdout)
        check("it stops nothing else", bystander.poll() is None)
        bystander.kill()
    finally:
        try:
            os.kill(proc.pid, signal.SIGTERM)  # not SIGINT: a test run in the background has it switched off
        except OSError:
            pass
        try:
            proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def _other_address_answers(port):
    """True if the port answers on this computer's network address (not loopback). No network address: False."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))  # no packet is sent; this only picks the outgoing address
        address = s.getsockname()[0]
        s.close()
    except OSError:
        return False
    if address.startswith("127."):
        return False
    try:
        with socket.create_connection((address, port), timeout=1):
            return True
    except OSError:
        return False
