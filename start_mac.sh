#!/bin/bash
# Start Easy Studio on this Mac: the picture engine (ComfyUI) and the app, then open the app in the browser.
# Both listen on this computer only (127.0.0.1). Run it in Terminal, or double-click start_mac.command in Finder.
#
#   ./start_mac.sh           start what is not running yet and open the browser
#   ./start_mac.sh --check   say what would start, and start nothing
#   ./stop_mac.sh            stop what this started
#
# Press Ctrl-C or close the window to stop what this started. Something that was already running is left alone.
#
# Settings (all optional): CANDY_RUNTIME (where the engine is installed, default ~/candy/runtime), COMFY_PORT (8188),
# EASY_STUDIO_PORT (7860), EASY_STUDIO_OUTPUTS (where your work is kept, default ~/candy/studio-data/outputs),
# EASY_STUDIO_MACHINE (m5_max), COMFY_FLAGS (extra engine flags), NO_OPEN=1 (do not open the browser).
#
# The logs under <runtime>/logs can hold the text of prompts. They stay on this computer.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RT="${CANDY_RUNTIME:-$HOME/candy/runtime}"
COMFY_PORT="${COMFY_PORT:-8188}"
APP_PORT="${EASY_STUDIO_PORT:-7860}"
DATA="${EASY_STUDIO_OUTPUTS:-$HOME/candy/studio-data/outputs}"
MACHINE="${EASY_STUDIO_MACHINE:-m5_max}"
COMFY_FLAGS="${COMFY_FLAGS:-}"
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1
ENGINE_URL="http://127.0.0.1:$COMFY_PORT"
APP_URL="http://127.0.0.1:$APP_PORT"
ENGINE_PID=""
APP_PID=""
ENGINE_PIDFILE="$RT/start_mac.engine.pid"  # read by stop_mac.sh
APP_PIDFILE="$RT/start_mac.app.pid"

say() { printf '%s\n' "$*"; }

need() {
  if [ ! -e "$1" ]; then
    say "Not found: $1"
    say "$2"
    exit 1
  fi
}

answers() { curl -s -o /dev/null --max-time 2 "$1"; }

listener() {  # "ssh" when a running ssh program forwards this port, else nothing: a -L forward on the command line, or
  # the server kit's own tunnel (an ssh -F <config under .candy-server-kit>, whose forward is in that file). Reads the
  # process list only: lsof is not used, because it can hang for good on a Mac with a stuck volume.
  ps -axo command= 2>/dev/null | grep -E "(^|/)ssh( |$)" | grep -E -- "-L *([^ ]*:)?$1:|-F [^ ]*/\.candy-server-kit/" | head -1 | sed 's/.*/ssh/'
}

case " $COMFY_FLAGS" in
  *" --listen"*)
    say "COMFY_FLAGS must not set --listen. The picture engine listens on this computer only."
    exit 1 ;;
esac

wait_for() {  # url, seconds, pid
  local waited=0
  until answers "$1"; do
    if ! kill -0 "$3" 2>/dev/null; then return 1; fi
    if [ "$waited" -ge "$2" ]; then return 1; fi
    sleep 1
    waited=$((waited + 1))
  done
}

stop_all() {
  trap - EXIT INT TERM HUP
  for pid in $APP_PID $ENGINE_PID; do
    pkill -P "$pid" 2>/dev/null  # the program under the keep-awake helper
    kill "$pid" 2>/dev/null
  done
  [ -n "$APP_PID" ] && rm -f "$APP_PIDFILE"
  [ -n "$ENGINE_PID" ] && rm -f "$ENGINE_PIDFILE"
  [ -n "$APP_PID$ENGINE_PID" ] && say "Stopped."
  exit 0
}

need "$HERE/app/server.py" "This file must stay in the Easy Studio folder."
need "$RT/ComfyUI/main.py" "The picture engine is not installed in $RT yet."
need "$RT/venv/bin/python" "The picture engine's Python is not installed in $RT yet."
need "$RT/app-venv/bin/python" "The app's Python is not installed in $RT yet."

ENGINE_UP=0
if answers "$ENGINE_URL/system_stats"; then
  ENGINE_UP=1
  ENGINE_BY="$(listener "$COMFY_PORT")"
  case "$ENGINE_BY" in
    ssh*|autossh*)
      say "Port $COMFY_PORT on this computer is a link to another computer ($ENGINE_BY), not the picture engine on this Mac."
      say "Close that link, or set COMFY_PORT to another port, then start again."
      exit 1 ;;
  esac
fi

KEEP_AWAKE=""
command -v caffeinate >/dev/null 2>&1 && KEEP_AWAKE="caffeinate -i"

if [ "$CHECK" = 1 ]; then
  if [ "$ENGINE_UP" = 1 ]; then say "Engine: already running at $ENGINE_URL (program: a local one, not a link to another computer)"
  else say "Engine: would start: $RT/venv/bin/python -u main.py --listen 127.0.0.1 --port $COMFY_PORT $COMFY_FLAGS"; fi
  if answers "$APP_URL/"; then say "App: already running at $APP_URL"
  else say "App: would start: EASY_STUDIO_HOST=127.0.0.1 EASY_STUDIO_PORT=$APP_PORT $RT/app-venv/bin/python -u app/server.py"; fi
  say "Your work is kept in: $DATA"
  say "Machine profile: $MACHINE"
  say "Nothing was started."
  exit 0
fi

mkdir -p "$RT/logs" "$DATA"
STAMP="$(date +%Y%m%d-%H%M%S)"
trap stop_all EXIT INT TERM HUP

if [ "$ENGINE_UP" = 1 ]; then
  say "The picture engine is already running (program: a local one, not a link to another computer)."
else
  say "Starting the picture engine ..."
  ( cd "$RT/ComfyUI" && exec $KEEP_AWAKE "$RT/venv/bin/python" -u main.py --listen 127.0.0.1 --port "$COMFY_PORT" $COMFY_FLAGS \
      >> "$RT/logs/comfy-$STAMP.log" 2>&1 ) &
  ENGINE_PID=$!
  echo "$ENGINE_PID" > "$ENGINE_PIDFILE"
  if ! wait_for "$ENGINE_URL/system_stats" 300 "$ENGINE_PID"; then
    say "The picture engine did not start. Its log: $RT/logs/comfy-$STAMP.log"
    exit 1
  fi
fi

if answers "$APP_URL/"; then
  say "The app is already running."
else
  say "Starting the app ..."
  ( cd "$HERE" && EASY_STUDIO_HOST=127.0.0.1 EASY_STUDIO_PORT="$APP_PORT" COMFY_URL="$ENGINE_URL" COMFY_DIR="$RT/ComfyUI" \
      COMFY_PYTHON="$RT/venv/bin/python" EASY_STUDIO_OUTPUTS="$DATA" EASY_STUDIO_MACHINE="$MACHINE" \
      EASY_STUDIO_TRAINER_DIR="${EASY_STUDIO_TRAINER_DIR:-$RT/trainer/ai-toolkit}" \
      exec $KEEP_AWAKE "$RT/app-venv/bin/python" -u app/server.py >> "$RT/logs/app-$STAMP.log" 2>&1 ) &
  APP_PID=$!
  echo "$APP_PID" > "$APP_PIDFILE"
  if ! wait_for "$APP_URL/" 120 "$APP_PID"; then
    say "The app did not start. Its log: $RT/logs/app-$STAMP.log"
    exit 1
  fi
fi

say "Easy Studio is ready: $APP_URL"
[ "${NO_OPEN:-}" = 1 ] || open "$APP_URL" 2>/dev/null
[ -z "$APP_PID$ENGINE_PID" ] && { trap - EXIT; exit 0; }
say "Leave this window open. To stop: press Ctrl-C here, or run ./stop_mac.sh."
wait
