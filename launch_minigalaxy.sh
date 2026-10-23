#!/bin/bash
set -e
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_storefront.sh minigalaxy
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/minigalaxy.log"
MINI_BIN=$(which minigalaxy 2>/dev/null || echo /usr/games/minigalaxy)

echo "Starting Minigalaxy as user gamer at $(date)..." >> "$LOG"
if [ "$(id -u)" -eq 0 ]; then USER_PREFIX=(runuser -u gamer --); else USER_PREFIX=(); fi
exec "${USER_PREFIX[@]}" env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    SDL_AUDIODRIVER=pulse \
    HOME="/home/gamer" \
    "$MINI_BIN" "$@" >> "$LOG" 2>&1
