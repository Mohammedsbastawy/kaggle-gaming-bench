#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export WINEPREFIX="/home/gamer/ea-prefix"
export WINEARCH=win64
export WINEDLLOVERRIDES="mscoree,mshtml="
mkdir -p "$WINEPREFIX" /tmp/ea-store /home/gamer/logs
chown -R gamer:gamer "$WINEPREFIX" /home/gamer/logs 2>/dev/null || true

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

exec runuser -u gamer -- env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    WINEPREFIX="$WINEPREFIX" \
    WINEARCH=win64 \
    WINEDLLOVERRIDES="$WINEDLLOVERRIDES" \
    HOME="/home/gamer" \
    wine "$TARGET" "$@" >> "$LOG" 2>&1
