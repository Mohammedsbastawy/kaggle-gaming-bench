#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
export LD_PRELOAD='/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so'
export SELKIES_JS_SOCKET_PATH="/tmp"
export SDL_JOYSTICK_DISABLE_UDEV=1
export SDL_JOYSTICK_DEVICE=/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003

mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/steam.log"
STEAM_BIN=$(which steam 2>/dev/null || echo /usr/games/steam)

echo "Starting Steam as user gamer at $(date)..." >> "$LOG"
exec runuser -u gamer -- env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    SDL_AUDIODRIVER=pulse \
    LD_PRELOAD="$LD_PRELOAD" \
    SELKIES_JS_SOCKET_PATH="$SELKIES_JS_SOCKET_PATH" \
    SDL_JOYSTICK_DISABLE_UDEV=1 \
    SDL_JOYSTICK_DEVICE="$SDL_JOYSTICK_DEVICE" \
    HOME="/home/gamer" \
    "$STEAM_BIN" -no-cef-sandbox -cef-disable-gpu -cef-force-software-rendering "$@" >> "$LOG" 2>&1
