#!/bin/bash
set -e
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_storefront.sh legendary
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export HOME="/home/gamer"
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/legendary_gui.log"

# Ensure Wine-GE is linked as system wine fallback
for w in /home/gamer/.config/heroic/tools/wine/*/bin/wine; do
    if [ -f "$w" ]; then
        if [ ! -f /usr/bin/wine ]; then
            ln -sf "$w" /usr/bin/wine 2>/dev/null || true
            ln -sf "$(dirname "$w")/wineserver" /usr/bin/wineserver 2>/dev/null || true
            ln -sf "$(dirname "$w")/wineboot" /usr/bin/wineboot 2>/dev/null || true
        fi
        if [ ! -f /usr/local/bin/wine ]; then
            ln -sf "$w" /usr/local/bin/wine 2>/dev/null || true
        fi
        break
    fi
done

# Launch Graphical Legendary Interface
if python3 -c "import tkinter" >/dev/null 2>&1; then
    exec python3 /tmp/kaggle-game-dev-bench/legendary_gui.py >> "$LOG" 2>&1
else
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update -qq && apt-get install -y -qq python3-tk >> "$LOG" 2>&1 || true
        if python3 -c "import tkinter" >/dev/null 2>&1; then
            exec python3 /tmp/kaggle-game-dev-bench/legendary_gui.py >> "$LOG" 2>&1
        fi
    fi
    exec xterm -geometry 105x32 -title "Legendary Epic Games Manager" -e /bin/bash /tmp/kaggle-game-dev-bench/legendary_menu.sh >> "$LOG" 2>&1
fi
