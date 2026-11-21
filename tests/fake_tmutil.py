"""Stand-in for /usr/bin/tmutil in tests: remembers excluded paths in a JSON file, changes nothing on the machine.

FAKE_TMUTIL_STATE is the file. While the file FAKE_TMUTIL_STATE + ".fail" exists, addexclusion fails.
"""
import json
import os
import sys

state = os.environ["FAKE_TMUTIL_STATE"]
try:
    paths = json.load(open(state, encoding="utf-8"))
except (OSError, ValueError):
    paths = []
verb, path = sys.argv[1], os.path.abspath(sys.argv[2])
if verb == "addexclusion":
    if os.path.exists(state + ".fail"):
        sys.exit(1)
    if path not in paths:
        paths.append(path)
    json.dump(paths, open(state, "w", encoding="utf-8"))
elif verb == "isexcluded":
    print(("[Excluded]    " if path in paths else "[Included]    ") + path)
else:
    sys.exit(2)
