#!/bin/bash
export LD_PRELOAD='/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so'
export SDL_AUDIODRIVER=pulse
export SELKIES_JS_SOCKET_PATH="$XDG_RUNTIME_DIR"
export SDL_JOYSTICK_DISABLE_UDEV=1
export SDL_JOYSTICK_DEVICE=/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"

# Opt-in only after the isolated probe confirms an NVIDIA EGL renderer.
if [ "${GAMELAB_USE_INJECTED_DRIVER:-0}" = 1 ]; then
    probe_env=/tmp/kaggle-game-dev-bench/nvidia-userspace-probe/env.sh
    if [ -f "$probe_env" ]; then
        # shellcheck disable=SC1090
        . "$probe_env"
    else
        echo "Requested injected driver, but $probe_env is absent" >&2
    fi
fi
printf '%s' "${XAUTHORITY:-}" > /tmp/kaggle-game-dev-bench/xauthority-path
printf '%s' "${PULSE_SERVER:-}" > /tmp/kaggle-game-dev-bench/pulse-server-path

# Xvfb remains the Selkies capture desktop. A separate NVIDIA Xorg display is
# used only when the host mounted the display driver and a renderer test passes.
if [ "$(id -u)" -eq 0 ]; then
    /bin/bash /tmp/kaggle-game-dev-bench/gpu_xorg.sh || true
fi

# Grant unprivileged gamer user access to X11 display
xhost +si:localuser:gamer 2>/dev/null || true

# Grant unprivileged gamer user access to PulseAudio socket and runtime directory
chmod 777 "$XDG_RUNTIME_DIR" 2>/dev/null || true
chmod -R 777 "$XDG_RUNTIME_DIR/pulse" 2>/dev/null || true

install -d -o gamer -g gamer -m 700 /home/gamer/.config/pulse
if [ -f "$HOME/.config/pulse/cookie" ]; then
    install -o gamer -g gamer -m 600 "$HOME/.config/pulse/cookie" /home/gamer/.config/pulse/cookie
fi

# Ensure /usr/bin/wine exists by symlinking Wine-GE if system wine is absent
for w_candidate in /home/gamer/.config/heroic/tools/wine/*/bin/wine; do
    if [ -f "$w_candidate" ]; then
        if [ ! -f /usr/bin/wine ]; then
            ln -sf "$w_candidate" /usr/bin/wine 2>/dev/null || true
            ln -sf "$(dirname "$w_candidate")/wineserver" /usr/bin/wineserver 2>/dev/null || true
            ln -sf "$(dirname "$w_candidate")/wineboot" /usr/bin/wineboot 2>/dev/null || true
        fi
        if [ ! -f /usr/local/bin/wine ]; then
            ln -sf "$w_candidate" /usr/local/bin/wine 2>/dev/null || true
        fi
        break
    fi
done

# Start Openbox window manager in background for window frames, moving & resizing
openbox &

# Start tint2 taskbar panel in background for window switching
if which tint2 >/dev/null 2>&1; then
    tint2 -c /tmp/kaggle-game-dev-bench/tint2rc &
fi

# Run the controller-friendly launcher UI as the main session process
if [ "$(id -u)" -eq 0 ]; then
    exec runuser -u gamer -- env -u DBUS_SESSION_BUS_ADDRESS DISPLAY="$DISPLAY" HOME=/home/gamer PATH="$PATH" \
        XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" SDL_AUDIODRIVER=pulse \
        PULSE_SERVER="${PULSE_SERVER:-}" SELKIES_JS_SOCKET_PATH="${SELKIES_JS_SOCKET_PATH:-}" \
        GAMELAB_ALLOW_SOFTWARE="${GAMELAB_ALLOW_SOFTWARE:-0}" \
        GAMELAB_SOFTWARE_RESOLUTION="${GAMELAB_SOFTWARE_RESOLUTION:-854x480}" \
        LP_NUM_THREADS="${LP_NUM_THREADS:-}" \
        LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}" \
        __EGL_VENDOR_LIBRARY_FILENAMES="${__EGL_VENDOR_LIBRARY_FILENAMES:-}" \
        VK_DRIVER_FILES="${VK_DRIVER_FILES:-}" VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-}" \
        GAMELAB_NVIDIA_LIB32="${GAMELAB_NVIDIA_LIB32:-}" \
        LD_PRELOAD="$LD_PRELOAD" SDL_JOYSTICK_DISABLE_UDEV=1 \
        SDL_JOYSTICK_DEVICE="$SDL_JOYSTICK_DEVICE" \
        dbus-run-session -- /usr/bin/env python3 /tmp/kaggle-game-dev-bench/dev_launcher.py
fi
exec /usr/bin/env python3 /tmp/kaggle-game-dev-bench/dev_launcher.py
