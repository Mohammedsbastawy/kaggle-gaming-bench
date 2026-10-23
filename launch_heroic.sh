#!/bin/bash
set -e
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_gaming.sh
sudo -n /bin/bash /tmp/kaggle-game-dev-bench/ensure_storefront.sh heroic
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
export LD_PRELOAD='/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so'
export SELKIES_JS_SOCKET_PATH="$XDG_RUNTIME_DIR"
export SDL_JOYSTICK_DISABLE_UDEV=1
export SDL_JOYSTICK_DEVICE=/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003

mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/heroic.log"
HEROIC_BIN=$(which heroic 2>/dev/null || echo /usr/bin/heroic)

# Source auto-optimizer Wine settings if available
if [ -f /home/gamer/.config/gamelab_wine_env.sh ]; then
    source /home/gamer/.config/gamelab_wine_env.sh
fi

# Automatically sanitize Heroic configuration and clean DXVK DLLs before launch
python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py >> "$LOG" 2>&1

echo "Starting Heroic as user gamer at $(date)..." >> "$LOG"
HEROIC_PREFIX=()
VGL_TARGET=$(PYTHONPATH=/tmp/kaggle-game-dev-bench python3 -c 'from gpu_runtime import diagnose; d=diagnose(); print(d["virtualgl_display"] if d["virtualgl"] and d["nvidia_32bit_gl"] else "")' 2>/dev/null)
if [ -n "$VGL_TARGET" ]; then
    HEROIC_PREFIX=(/opt/VirtualGL/bin/vglrun -d "$VGL_TARGET")
fi
if [ "$(id -u)" -eq 0 ]; then
    USER_PREFIX=(runuser -u gamer --)
else
    USER_PREFIX=()
fi
exec "${USER_PREFIX[@]}" env \
    DISPLAY="$DISPLAY" \
    PATH="$PATH" \
    SDL_AUDIODRIVER=pulse \
    LD_PRELOAD="$LD_PRELOAD" \
    SELKIES_JS_SOCKET_PATH="$SELKIES_JS_SOCKET_PATH" \
    SDL_JOYSTICK_DISABLE_UDEV=1 \
    SDL_JOYSTICK_DEVICE="$SDL_JOYSTICK_DEVICE" \
    HOME="/home/gamer" \
    "${HEROIC_PREFIX[@]}" "$HEROIC_BIN" --no-sandbox --disable-gpu --disable-gpu-compositing "$@" >> "$LOG" 2>&1
