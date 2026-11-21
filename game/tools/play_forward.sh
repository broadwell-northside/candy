#!/bin/sh
# Desktop play on Forward+. Headless tests do not use this script.
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
exec godot --path "$ROOT" --rendering-method forward_plus "$@"
