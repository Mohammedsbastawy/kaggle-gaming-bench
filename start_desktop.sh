#!/bin/bash
export LD_PRELOAD='/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so'
export SDL_AUDIODRIVER=pulse
export SELKIES_JS_SOCKET_PATH="$XDG_RUNTIME_DIR"
export SDL_JOYSTICK_DISABLE_UDEV=1
export SDL_JOYSTICK_DEVICE=/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"

# Grant unprivileged gamer user access to X11 display
xhost +local:gamer 2>/dev/null || xhost + 2>/dev/null || true

# Grant unprivileged gamer user access to PulseAudio socket and runtime directory
chmod 777 "$XDG_RUNTIME_DIR" 2>/dev/null || true
chmod -R 777 "$XDG_RUNTIME_DIR/pulse" 2>/dev/null || true
chmod -R 777 /tmp/kaggle-game-dev-bench 2>/dev/null || true

# Start Openbox window manager in background for window frames, moving & resizing
openbox &

# Start tint2 taskbar panel in background for window switching
if which tint2 >/dev/null 2>&1; then
    tint2 -c /tmp/kaggle-game-dev-bench/tint2rc &
fi

# Run the controller-friendly launcher UI as the main session process
exec /usr/bin/env python3 /tmp/kaggle-game-dev-bench/dev_launcher.py
