#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export HOME="/home/gamer"
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/auto_optimize.log"

# Install tkinter if missing
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq python3-tk >> "$LOG" 2>&1 || true
fi

exec python3 /tmp/kaggle-game-dev-bench/auto_optimize.py >> "$LOG" 2>&1
