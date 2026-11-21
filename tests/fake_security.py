"""Stand-in for /usr/bin/security in tests. Keeps keys in a JSON file (FAKE_SECURITY_STATE) and logs every
command line it is started with, to FAKE_SECURITY_STATE + ".argv", so a test can prove a key never was an argument.
Handles: find-generic-password [-w], delete-generic-password, and `-i` (commands on standard input)."""
import json
import os
import shlex
import sys

state = os.environ["FAKE_SECURITY_STATE"]
with open(state + ".argv", "a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")
try:
    store = json.load(open(state, encoding="utf-8"))
except (OSError, ValueError):
    store = {}


def opt(args, flag):
    return args[args.index(flag) + 1] if flag in args else None


def run(args):
    verb = args[0]
    key = (opt(args, "-s") or "") + "/" + (opt(args, "-a") or "")
    if verb == "add-generic-password":
        if os.path.exists(state + ".fail"):
            return 1
        store[key] = opt(args, "-w")
        return 0
    if verb == "find-generic-password":
        if key not in store:
            print("security: SecKeychainSearchCopyNext: The specified item could not be found in the keychain.", file=sys.stderr)
            return 44
        if "-w" in args:
            print(store[key])
        else:
            print('keychain: "login.keychain"\nattributes:\n    "acct"<blob>="%s"' % (opt(args, "-a")))
        return 0
    if verb == "delete-generic-password":
        return 0 if store.pop(key, None) is not None else 44
    return 2


if sys.argv[1:2] == ["-i"]:
    code = 0
    for line in sys.stdin:
        if line.strip():
            code = run(shlex.split(line))
else:
    code = run(sys.argv[1:])
json.dump(store, open(state, "w", encoding="utf-8"))
sys.exit(code)
