#!/bin/bash
# Capture a Mesa GLX desktop while VirtualGL renders games on the T4.
set -euo pipefail

BENCH=/tmp/kaggle-game-dev-bench
PORT="${DIRECT_STREAM_PORT:-8080}"
WIDTH="${DIRECT_STREAM_WIDTH:-1920}"
HEIGHT="${DIRECT_STREAM_HEIGHT:-1080}"
DISPLAY=:2
ORIGIN="${SELKIES_ALLOWED_ORIGINS:-https://kkb-production.jupyter-proxy.kaggle.net}"
RUNTIME="$BENCH/pulse-runtime"
COOKIE=/home/gamer/.config/pulse/cookie
PULSE_SERVER="unix:$RUNTIME/pulse/native"
LOGS="$BENCH/logs"
mkdir -p "$LOGS"

if [ "$(id -u)" -ne 0 ]; then
    echo 'The stream launcher must run as root to prepare Xvfb and PulseAudio.' >&2
    exit 1
fi

ensure_control() {
    if curl -fsS http://127.0.0.1:8766/health >/dev/null 2>&1; then return; fi
    nohup runuser -u gamer -- env DISPLAY=:2 HOME=/home/gamer \
        XDG_RUNTIME_DIR="$RUNTIME" PULSE_SERVER="$PULSE_SERVER" \
        python3 "$BENCH/session_control.py" \
        > "$LOGS/game-control.log" 2>&1 < /dev/null &
    echo $! > "$BENCH/game-control.pid"
    for attempt in $(seq 1 20); do
        curl -fsS http://127.0.0.1:8766/health >/dev/null 2>&1 && return
        sleep 0.25
    done
    echo '7BZ control service did not start.' >&2
    tail -15 "$LOGS/game-control.log" >&2
    exit 1
}

share_gamepad_sockets() {
    local socket attempt
    for attempt in $(seq 1 20); do
        [ -S /tmp/selkies_js0.sock ] && break
        sleep 0.25
    done
    for socket in /tmp/selkies_js*.sock /tmp/selkies_event*.sock; do
        [ -S "$socket" ] || continue
        chgrp gamer "$socket"
        chmod 770 "$socket"
    done
}

if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    ensure_control
    share_gamepad_sockets
    echo "Stream and control ready on port $PORT"
    exit 0
fi

# The Kaggle NVIDIA EGL library crashes Xvfb when Mesa GLX initializes.
# Give the X server Mesa only; game processes keep NVIDIA libraries for VGL.
if ! DISPLAY=:2 xdpyinfo >/dev/null 2>&1; then
    nohup env -u LD_LIBRARY_PATH \
        __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json \
        LIBGL_ALWAYS_SOFTWARE=1 \
        Xvfb :2 -screen 0 "${WIDTH}x${HEIGHT}x24" -nolisten tcp -noreset \
        > "$LOGS/game-xvfb.log" 2>&1 < /dev/null &
    echo $! > "$BENCH/game-xvfb.pid"
fi
for attempt in $(seq 1 20); do
    DISPLAY=:2 xdpyinfo >/dev/null 2>&1 && break
    sleep 0.5
done
DISPLAY=:2 xdpyinfo >/dev/null
if ! runuser -u gamer -- env DISPLAY=:2 HOME=/home/gamer VGL_DISPLAY=egl0 \
    vglrun -d egl0 glxinfo -B 2>&1 | grep -q 'OpenGL vendor string: NVIDIA'; then
    echo 'VirtualGL could not render on the NVIDIA GPU.' >&2
    exit 1
fi

install -d -o gamer -g gamer -m 700 /home/gamer/.config/pulse "$RUNTIME" "$RUNTIME/pulse"
pulse_user() {
    runuser -u gamer -- env HOME=/home/gamer XDG_RUNTIME_DIR="$RUNTIME" \
        PULSE_SERVER="$PULSE_SERVER" PULSE_COOKIE="$COOKIE" "$@"
}
if ! pulse_user pactl info >/dev/null 2>&1; then
    runuser -u gamer -- env HOME=/home/gamer XDG_RUNTIME_DIR="$RUNTIME" \
        PULSE_COOKIE="$COOKIE" \
        pulseaudio --daemonize=yes --exit-idle-time=-1 --disallow-exit=yes \
        >> "$LOGS/game-pulse.log" 2>&1 || true
fi
for attempt in $(seq 1 20); do
    pulse_user pactl info >/dev/null 2>&1 && break
    sleep 0.5
done
pulse_user pactl info >/dev/null
if ! pulse_user pactl list short sinks | awk '$2 == "output" { found=1 } END { exit !found }'; then
    pulse_user pactl load-module module-null-sink sink_name=output \
        sink_properties=device.description=GameAudio >/dev/null
fi
pulse_user pactl set-default-sink output >/dev/null
printf '%s' "$PULSE_SERVER" > "$BENCH/pulse-server-path"

# Wine-GE may use its ALSA driver even when PulseAudio is available. Kaggle
# has no physical ALSA card, so send ALSA's default device to PulseAudio.
if [ ! -e /home/gamer/.asoundrc ]; then
    cat > /home/gamer/.asoundrc <<'EOF'
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
EOF
    chown gamer:gamer /home/gamer/.asoundrc
fi

ENCODER_DEVICE=0
if [ -e /dev/nvidia1 ]; then ENCODER_DEVICE=1; fi
export DISPLAY PULSE_SERVER
unset XAUTHORITY
nohup env CUDA_VISIBLE_DEVICES="$ENCODER_DEVICE" \
    SELKIES_ENCODER_DEVICE="$ENCODER_DEVICE" \
    SELKIES_AUDIO_ENABLED=true SELKIES_AUDIO_ON_START=true \
    SELKIES_AUDIO_DEVICE_NAME=output.monitor PULSE_COOKIE="$COOKIE" \
    SELKIES_JS_SOCKET_PATH=/tmp \
    python3 -m selkies --port="$PORT" --enable-basic-auth=false \
    --mode=websockets --allowed-origins="$ORIGIN" \
    --encoder=h264enc --framerate=30-30 --video-bitrate=3500,800-6000 \
    --rate-control-mode=cbr --congestion-control=true \
    --backpressure-queue-size=4 \
    --command-enabled=false --file-transfers=none --printing-enabled=false \
    --web-root="$BENCH/web-root" --ui-title='7BZ Dev Cloud Game' \
    --manual-resolution=true --manual-width="$WIDTH" --manual-height="$HEIGHT" \
    > "$LOGS/game-stream.log" 2>&1 < /dev/null &
stream_pid=$!
echo "$stream_pid" > "$BENCH/selkies.pid"
for attempt in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then break; fi
    if ! kill -0 "$stream_pid" 2>/dev/null; then
        echo 'Selkies exited during startup.' >&2
        tail -20 "$LOGS/game-stream.log" >&2
        exit 1
    fi
    sleep 0.5
done
curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null
ensure_control
share_gamepad_sockets

# A live session may already have its game desktop and dashboard on :2.
if [ "${GAME_STREAM_ONLY:-0}" = 1 ]; then
    echo "NVIDIA VirtualGL capture ready on port $PORT"
    exit 0
fi

start_gamer_program() {
    local label="$1"
    shift
    local pidfile="$BENCH/game-${label}.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then return; fi
    runuser -u gamer -- env DISPLAY=:2 HOME=/home/gamer \
        XDG_RUNTIME_DIR="$RUNTIME" PULSE_SERVER="$PULSE_SERVER" \
        PULSE_COOKIE="$COOKIE" SDL_AUDIODRIVER=pulse VGL_DISPLAY=egl0 \
        GAMELAB_DIRECT_XORG=0 SELKIES_JS_SOCKET_PATH=/tmp \
        "$@" > "$LOGS/game-${label}.log" 2>&1 < /dev/null &
    echo $! > "$pidfile"
}
start_gamer_program openbox openbox
start_gamer_program dashboard python3 "$BENCH/dev_launcher.py"
echo "NVIDIA VirtualGL game stream ready on port $PORT at ${WIDTH}x${HEIGHT}/30"
