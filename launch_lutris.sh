#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/lutris.log"
LUTRIS_BIN=$(which lutris 2>/dev/null || echo /usr/games/lutris)

if [ -x /usr/bin/python3.12 ]; then
    PY_BIN="/usr/bin/python3.12"
else
    PY_BIN="python3"
fi

echo "Starting Lutris with $PY_BIN as user gamer at $(date)..." >> "$LOG"
exec runuser -u gamer -- env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    SDL_AUDIODRIVER=pulse \
    HOME="/home/gamer" \
    "$PY_BIN" "$LUTRIS_BIN" "$@" >> "$LOG" 2>&1
