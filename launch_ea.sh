#!/bin/bash
set -e
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_gaming.sh
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export WINEPREFIX="/home/gamer/ea-prefix"
export WINEARCH=win64
export WINEDLLOVERRIDES="mscoree,mshtml="
mkdir -p "$WINEPREFIX" /tmp/ea-store /home/gamer/logs

LOG="/home/gamer/logs/ea.log"
echo "Starting EA App runner at $(date)..." >> "$LOG"

EA_INSTALLER="/tmp/ea-store/EAappInstaller.exe"
if [ ! -f "$EA_INSTALLER" ]; then
    echo "Downloading EAappInstaller.exe..." >> "$LOG"
    wget -q https://origin-a.akamaihd.net/EA-Desktop-Client-Download/installer-releases/EAappInstaller.exe -O "$EA_INSTALLER"
fi

EA_INSTALLED="$WINEPREFIX/drive_c/Program Files/Electronic Arts/EA Desktop/EA Desktop/EADesktop.exe"
if [ -f "$EA_INSTALLED" ]; then
    echo "Running installed EA Desktop: $EA_INSTALLED" >> "$LOG"
    TARGET="$EA_INSTALLED"
else
    echo "Running EA App Installer via Wine64: $EA_INSTALLER" >> "$LOG"
    TARGET="$EA_INSTALLER"
fi

if [ "$(id -u)" -eq 0 ]; then USER_PREFIX=(runuser -u gamer --); else USER_PREFIX=(); fi
exec "${USER_PREFIX[@]}" env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    WINEPREFIX="$WINEPREFIX" \
    WINEARCH=win64 \
    WINEDLLOVERRIDES="$WINEDLLOVERRIDES" \
    HOME="/home/gamer" \
    wine "$TARGET" "$@" >> "$LOG" 2>&1
