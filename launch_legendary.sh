#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/legendary.log"
exec xterm -geometry 105x32 -title "Legendary Epic Games Manager" -e /bin/bash /tmp/kaggle-game-dev-bench/legendary_menu.sh >> "$LOG" 2>&1
