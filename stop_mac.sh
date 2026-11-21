#!/bin/bash
# Stop what start_mac.sh started on this Mac: the app and the picture engine. Anything it did not start is left alone.
set -uo pipefail
RT="${CANDY_RUNTIME:-$HOME/candy/runtime}"
stopped=0
for name in app engine; do
  file="$RT/start_mac.$name.pid"
  [ -f "$file" ] || continue
  pid="$(tr -cd '0-9' < "$file")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    # After a crash or a restart of the Mac the saved number can belong to another program. Stop it only when
    # its command line is the one start_mac.sh started: a Python from the runtime folder.
    case "$(ps -o command= -p "$pid" 2>/dev/null)" in
      *"$RT/venv/bin/python"*|*"$RT/app-venv/bin/python"*)
        pkill -P "$pid" 2>/dev/null  # the program under the keep-awake helper
        kill "$pid" 2>/dev/null
        stopped=$((stopped + 1))
        printf 'Stopped the %s.\n' "$name" ;;
      *)
        printf 'The saved number for the %s now belongs to another program. It was left alone.\n' "$name" ;;
    esac
  fi
  rm -f "$file"
done
[ "$stopped" = 0 ] && printf 'Nothing to stop: start_mac.sh has nothing running.\n'
exit 0
