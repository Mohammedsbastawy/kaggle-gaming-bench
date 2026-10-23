#!/bin/bash
set -e
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_gaming.sh
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_storefront.sh lutris
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
if [ "$(id -u)" -eq 0 ]; then USER_PREFIX=(runuser -u gamer --); else USER_PREFIX=(); fi
exec "${USER_PREFIX[@]}" env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    SDL_AUDIODRIVER=pulse \
    HOME="/home/gamer" \
    "$PY_BIN" "$LUTRIS_BIN" "$@" >> "$LOG" 2>&1
