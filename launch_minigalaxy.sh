#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/minigalaxy.log"
MINI_BIN=$(which minigalaxy 2>/dev/null || echo /usr/games/minigalaxy)

echo "Starting Minigalaxy as user gamer at $(date)..." >> "$LOG"
exec runuser -u gamer -- env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    SDL_AUDIODRIVER=pulse \
    HOME="/home/gamer" \
    "$MINI_BIN" "$@" >> "$LOG" 2>&1
