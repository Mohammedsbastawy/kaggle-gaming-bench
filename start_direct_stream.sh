#!/bin/bash
# Stream the NVIDIA Xorg display directly. Run as root after the notebook's
# ordinary desktop session has created PulseAudio and gpu_xorg.sh has run.
set -euo pipefail
BENCH=/tmp/kaggle-game-dev-bench
PORT="${DIRECT_STREAM_PORT:-8080}"
WIDTH="${DIRECT_STREAM_WIDTH:-1280}"
HEIGHT="${DIRECT_STREAM_HEIGHT:-720}"
ORIGIN="${SELKIES_ALLOWED_ORIGINS:-https://kkb-production.jupyter-proxy.kaggle.net}"
if [ "$(id -u)" -ne 0 ]; then
    echo 'This Xorg installation requires root for Selkies MIT-SHM capture.' >&2
    exit 1
fi
bash "$BENCH/gpu_xorg.sh"
test -e "$BENCH/gpu-xorg-ready"
DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" \
    glxinfo -B | grep -q 'OpenGL vendor string: NVIDIA'
if command -v xrandr >/dev/null; then
    DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" \
        xrandr -s "${WIDTH}x${HEIGHT}" 2>/dev/null || true
fi

# Use one stable, gamer-owned PulseAudio runtime for Wine and Selkies. A
# socket pathname alone is not proof of a running or authenticated server.
AUDIO_RUNTIME="$BENCH/pulse-runtime"
AUDIO_COOKIE=/home/gamer/.config/pulse/cookie
PULSE_SERVER="unix:$AUDIO_RUNTIME/pulse/native"
install -d -o gamer -g gamer -m 700 /home/gamer/.config/pulse "$AUDIO_RUNTIME" "$AUDIO_RUNTIME/pulse"
if [ -f "$AUDIO_COOKIE" ]; then
    chown gamer:gamer "$AUDIO_COOKIE"
    chmod 600 "$AUDIO_COOKIE"
fi
pulse_user() {
    runuser -u gamer -- env HOME=/home/gamer XDG_RUNTIME_DIR="$AUDIO_RUNTIME" \
        PULSE_SERVER="$PULSE_SERVER" PULSE_COOKIE="$AUDIO_COOKIE" "$@"
}
if ! pulse_user pactl info >/dev/null 2>&1; then
    runuser -u gamer -- env HOME=/home/gamer XDG_RUNTIME_DIR="$AUDIO_RUNTIME" \
        PULSE_COOKIE="$AUDIO_COOKIE" \
        pulseaudio --daemonize=yes --exit-idle-time=-1 --disallow-exit=yes \
        >> "$BENCH/logs/pulseaudio.log" 2>&1 || true
fi
audio_ready=false
for attempt in $(seq 1 20); do
    if [ -S "$AUDIO_RUNTIME/pulse/native" ] && pulse_user pactl info >/dev/null 2>&1; then
        audio_ready=true
        break
    fi
    sleep 0.5
done
if [ "$audio_ready" = true ]; then
    if ! pulse_user pactl list short sinks | awk '$2 == "output" { found=1 } END { exit !found }'; then
        pulse_user pactl load-module module-null-sink sink_name=output \
            sink_properties=device.description=GameAudio >/dev/null || true
    fi
    pulse_user pactl set-default-sink output || true
    pulse_user pactl set-sink-mute output 0 || true
    pulse_user pactl set-sink-volume output 100% || true
    if ! PULSE_SERVER="$PULSE_SERVER" PULSE_COOKIE="$AUDIO_COOKIE" pactl info >/dev/null 2>&1; then
        echo 'Selkies cannot authenticate to the gamer PulseAudio server.' >&2
    fi
else
    echo "PulseAudio did not start; see $BENCH/logs/pulseaudio.log" >&2
fi
printf '%s' "$PULSE_SERVER" > "$BENCH/pulse-server-path"
chmod 644 "$BENCH/pulse-server-path"
export DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" PULSE_SERVER PULSE_COOKIE="$AUDIO_COOKIE"
export PULSE_SINK=output
ENCODER_DEVICE=0
if [ -e /dev/nvidia1 ]; then ENCODER_DEVICE=1; fi
export CUDA_VISIBLE_DEVICES="$ENCODER_DEVICE"
export SELKIES_ALLOWED_ORIGINS="$ORIGIN"
export SELKIES_JS_SOCKET_PATH="$BENCH/direct-stream-sockets"
mkdir -p "$SELKIES_JS_SOCKET_PATH" "$BENCH/logs"
test -f "$BENCH/web-root/index.html"
# Keep the system Openbox settings, with a rule for the game's Wine window.
# EWMH fullscreen removes both the title bar and tint2's reserved screen area.
python3 - "$BENCH/direct-openbox-rc.xml" <<'PY'
from pathlib import Path
import sys

source = Path('/etc/xdg/openbox/rc.xml').read_text(encoding='utf-8')
rule = '''<applications>
  <application class="wolfneworder_x64.exe">
    <decor>no</decor>
    <fullscreen>yes</fullscreen>
    <focus>yes</focus>
  </application>
  <application class="*dev_launcher*">
    <decor>no</decor>
    <position force="yes"><x>0</x><y>0</y></position>
    <focus>yes</focus>
  </application>
  <application title="*7BZ Cloud Gaming*">
    <decor>no</decor>
    <position force="yes"><x>0</x><y>0</y></position>
    <focus>yes</focus>
  </application>'''
if source.count('<applications>') != 1:
    raise SystemExit('Cannot locate Openbox application rules')
Path(sys.argv[1]).write_text(source.replace('<applications>', rule, 1), encoding='utf-8')
PY
start_desktop_program() {
    local label="$1"
    shift
    local pidfile="$BENCH/direct-${label}.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        return
    fi
    runuser -u gamer -- env DISPLAY=:1 HOME=/home/gamer \
        XDG_RUNTIME_DIR="$AUDIO_RUNTIME" PULSE_SERVER="$PULSE_SERVER" \
        PULSE_COOKIE="$AUDIO_COOKIE" PULSE_SINK=output SDL_AUDIODRIVER=pulse \
        CUDA_VISIBLE_DEVICES=0 GAMELAB_DIRECT_XORG=1 \
        SELKIES_JS_SOCKET_PATH="$SELKIES_JS_SOCKET_PATH" \
        PYTHONPATH=/root/.local/lib/python3.13/site-packages:/usr/local/lib/python3.13/dist-packages \
        "$@" > "$BENCH/logs/direct-${label}.log" 2>&1 < /dev/null &
    echo $! > "$pidfile"
}
start_desktop() {
    chmod 666 "$SELKIES_JS_SOCKET_PATH"/*.sock 2>/dev/null || true
    # The HUD's input-mode switch and diagnostics live on this control port.
    # The fallback desktop starts it separately, but direct Xorg must too.
    start_desktop_program control python3 "$BENCH/session_control.py"
    start_desktop_program openbox openbox --config-file "$BENCH/direct-openbox-rc.xml"
    if command -v tint2 >/dev/null; then
        start_desktop_program tint2 tint2 -c "$BENCH/tint2rc"
    fi
    start_desktop_program dashboard python3 "$BENCH/dev_launcher.py"
    start_desktop_program legendary python3 "$BENCH/legendary_gui.py"
}
if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    start_desktop
    echo "Direct desktop already streaming on port $PORT"
    exit 0
fi
# This process runs as root because Xorg rejected the gamer's MIT-SHM attach.
# Disable command execution and transfers on this privileged stream.
nohup env SELKIES_ENCODER_DEVICE="$ENCODER_DEVICE" SELKIES_ENCODER=h264enc \
    SELKIES_AUDIO_ENABLED=true SELKIES_AUDIO_ON_START=true \
    SELKIES_AUDIO_DEVICE_NAME=output.monitor \
    python3 -m selkies --port="$PORT" --enable-basic-auth=false \
    --framerate=60-60 --video-bitrate=3000,800-6000 \
    --rate-control-mode=cbr --congestion-control=true \
    --backpressure-queue-size=4 \
    --command-enabled=false --file-transfers=none --printing-enabled=false \
    --web-root="$BENCH/web-root" --ui-title='7BZ Dev Cloud Game' \
    --ui-show-sidebar=true --ui-show-logo=false \
    --ui-sidebar-show-video-settings=false \
    --ui-sidebar-show-screen-settings=false \
    --manual-resolution=true --manual-width="$WIDTH" --manual-height="$HEIGHT" \
    > "$BENCH/logs/direct-stream.log" 2>&1 < /dev/null &
echo $! > "$BENCH/direct-stream.pid"
for attempt in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
        start_desktop
        echo "Direct NVIDIA stream ready on port $PORT"
        exit 0
    fi
    sleep 0.5
done
echo "Direct stream did not start; see $BENCH/logs/direct-stream.log" >&2
exit 1
