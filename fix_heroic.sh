#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/heroic_fix.log"
exec xterm -geometry 95x25 -title "Heroic Config Sanitizer" -e bash -c "echo '=== Sanitizing Heroic Settings & Prefixes ===' | tee -a '$LOG'; python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py 2>&1 | tee -a '$LOG'; chown -R gamer:gamer /home/gamer 2>/dev/null || true; chmod -R u+rwX /home/gamer 2>/dev/null || true; echo ''; echo 'Sanitization complete! All games configured for WineD3D.'; echo ''; read -p 'Press Enter to close window...'"
