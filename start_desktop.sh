#!/bin/bash
# Asymmetric Dual-GPU Allocation:
# Force all desktop session applications, game runners, and Wine to use GPU 0.
export CUDA_VISIBLE_DEVICES=0
export DRI_PRIME=0
export VGL_DISPLAY=egl0

export LD_PRELOAD='/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so'
export SDL_AUDIODRIVER=pulse
export SELKIES_JS_SOCKET_PATH="/tmp"
export SDL_JOYSTICK_DISABLE_UDEV=1
export SDL_JOYSTICK_DEVICE=/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003
export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"

# Ensure /dev/input nodes and permissions exist
mkdir -p /dev/input 2>/dev/null || true
for i in 0 1 2 3; do touch /dev/input/js$i 2>/dev/null || true; done
for i in 1000 1001 1002 1003; do touch /dev/input/event$i 2>/dev/null || true; done
chmod -R 666 /dev/input 2>/dev/null || true

# Continuous socket permission and mirroring monitor so gamer user can connect to gamepad sockets
(while true; do
    chmod 755 /run/user /run/user/0 2>/dev/null || true
    chmod 666 /tmp/selkies_*.sock /run/user/*/selkies_*.sock 2>/dev/null || true
    ln -sf /run/user/0/selkies_*.sock /tmp/ 2>/dev/null || true
    ln -sf /tmp/selkies_*.sock /run/user/1000/ 2>/dev/null || true
    sleep 2
done) &

# Load NVIDIA userspace driver environment if available
probe_env=/tmp/kaggle-game-dev-bench/nvidia-userspace-probe/env.sh
if [ -f "$probe_env" ]; then
    # shellcheck disable=SC1090
    . "$probe_env"
fi
printf '%s' "${XAUTHORITY:-}" > /tmp/kaggle-game-dev-bench/xauthority-path
printf '%s' "${PULSE_SERVER:-}" > /tmp/kaggle-game-dev-bench/pulse-server-path

if [ -z "${PULSE_SERVER:-}" ]; then
    for pulse_socket in /run/user/1000/pulse/native /tmp/pulse-*/native; do
        if [ -S "$pulse_socket" ]; then
            export PULSE_SERVER="unix:$pulse_socket"
            break
        fi
    done
fi

# Xvfb remains the Selkies capture desktop. A separate NVIDIA Xorg display is
# used only when the host mounted the display driver and a renderer test passes.
if [ "$(id -u)" -eq 0 ]; then
    /bin/bash /tmp/kaggle-game-dev-bench/gpu_xorg.sh || true
fi

# Grant unprivileged gamer user access to X11 display and root packages
xhost + 2>/dev/null || true
chmod 755 /root 2>/dev/null || true
chmod -R 755 /root/.local 2>/dev/null || true
chmod -R 777 /home/gamer 2>/dev/null || true
xset m 0 0 2>/dev/null || true

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

# Keep the emergency HUD control plane separate from Selkies and the desktop.
control_pidfile=/tmp/kaggle-game-dev-bench/session-control.pid
if [ -f "$control_pidfile" ]; then
    control_pid=$(cat "$control_pidfile" 2>/dev/null || true)
    if [ -n "$control_pid" ] && [ -r "/proc/$control_pid/cmdline" ] && \
       tr '\0' ' ' < "/proc/$control_pid/cmdline" | grep -q '/tmp/kaggle-game-dev-bench/session_control.py'; then
        kill "$control_pid" 2>/dev/null || true
    fi
fi
runuser -u gamer -- env DISPLAY="$DISPLAY" HOME=/home/gamer PATH="$PATH" \
    PULSE_SERVER="${PULSE_SERVER:-}" SDL_AUDIODRIVER=pulse \
    python3 /tmp/kaggle-game-dev-bench/session_control.py \
    >> /home/gamer/logs/session-control.log 2>&1 &
echo $! > "$control_pidfile"

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
        PYTHONPATH="/root/.local/lib/python3.13/site-packages:/usr/local/lib/python3.13/dist-packages:${PYTHONPATH:-}" \
        LD_PRELOAD="$LD_PRELOAD" SDL_JOYSTICK_DISABLE_UDEV=1 \
        SDL_JOYSTICK_DEVICE="$SDL_JOYSTICK_DEVICE" \
        bash -c "while true; do python3 /tmp/kaggle-game-dev-bench/dev_launcher.py >> /home/gamer/logs/launcher.log 2>&1 || python3 /tmp/kaggle-game-dev-bench/legendary_gui.py >> /home/gamer/logs/gui.log 2>&1 || sleep 2; done"
fi
exec bash -c "while true; do python3 /tmp/kaggle-game-dev-bench/dev_launcher.py >> /home/gamer/logs/launcher.log 2>&1 || python3 /tmp/kaggle-game-dev-bench/legendary_gui.py >> /home/gamer/logs/gui.log 2>&1 || sleep 2; done"
