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
        xrandr --output DVI-D-0 --mode "${WIDTH}x${HEIGHT}"
fi

# Ensure independent PulseAudio daemon is running
mkdir -p /home/gamer/.config/pulse /run/user/1000/pulse /tmp/pulse 2>/dev/null || true
chmod 777 /run/user/1000 /run/user/1000/pulse /tmp/pulse 2>/dev/null || true

if ! pgrep -u gamer -x pulseaudio >/dev/null 2>&1 && ! pgrep -u root -x pulseaudio >/dev/null 2>&1; then
    runuser -u gamer -- pulseaudio --daemonize=yes --exit-idle-time=-1 --disallow-exit=yes 2>/dev/null || \
    pulseaudio --system --daemonize=yes --disallow-exit=yes 2>/dev/null || true
fi

PULSE_SOCK=""
for s in /run/user/1000/pulse/native /tmp/pulse-*/native /run/user/0/pulse/native; do
    if [ -S "$s" ]; then
        chmod 666 "$s" 2>/dev/null || true
        PULSE_SOCK="unix:$s"
        break
    fi
done

if [ -n "$PULSE_SOCK" ]; then
    echo "$PULSE_SOCK" > "$BENCH/pulse-server-path"
    chmod 666 "$BENCH/pulse-server-path" 2>/dev/null || true
fi

PULSE_SERVER="$(cat "$BENCH/pulse-server-path" 2>/dev/null || true)"
export DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" PULSE_SERVER
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
        PULSE_SERVER="$PULSE_SERVER" SDL_AUDIODRIVER=pulse \
        CUDA_VISIBLE_DEVICES=0 GAMELAB_DIRECT_XORG=1 \
        SELKIES_JS_SOCKET_PATH="$SELKIES_JS_SOCKET_PATH" \
        PYTHONPATH=/root/.local/lib/python3.13/site-packages:/usr/local/lib/python3.13/dist-packages \
        "$@" > "$BENCH/logs/direct-${label}.log" 2>&1 < /dev/null &
    echo $! > "$pidfile"
}
start_desktop() {
    chmod 666 "$SELKIES_JS_SOCKET_PATH"/*.sock 2>/dev/null || true
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
    python3 -m selkies --port="$PORT" --enable-basic-auth=false \
    --command-enabled=false --file-transfers=none --printing-enabled=false \
    --web-root="$BENCH/web-root" --ui-title='7BZ Dev Cloud Game' \
    --ui-show-sidebar=true --ui-show-logo=false \
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
