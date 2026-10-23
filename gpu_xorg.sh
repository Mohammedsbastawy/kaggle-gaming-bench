#!/bin/bash
# Optional NVIDIA 3D server for VirtualGL. Selkies keeps its Xvfb desktop.
set -u
BENCH=/tmp/kaggle-game-dev-bench
READY="$BENCH/gpu-xorg-ready"
LOG="$BENCH/logs/gpu-xorg.log"
rm -f "$READY"
mkdir -p "$BENCH/logs"

if [ ! -c /dev/nvidiactl ] || [ ! -c /dev/nvidia0 ] || [ ! -c /dev/nvidia-modeset ]; then
    echo 'NVIDIA display devices were not mounted by the container host.' | tee -a "$LOG"
    exit 0
fi
if ! command -v Xorg >/dev/null || ! find /usr/lib -name nvidia_drv.so -print -quit 2>/dev/null | grep -q .; then
    echo 'NVIDIA Xorg display driver or Xorg is missing. Host graphics/display capability is required.' | tee -a "$LOG"
    exit 0
fi
if [ -S /tmp/.X11-unix/X1 ]; then
    if DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" glxinfo -B 2>&1 | grep -Eiq 'OpenGL renderer string:.*NVIDIA'; then
        DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" xhost +si:localuser:gamer >> "$LOG" 2>&1
        touch "$READY"
        echo 'Reusing verified NVIDIA Xorg display :1.' | tee -a "$LOG"
    else
        echo 'Display :1 is occupied by an unverified X server.' | tee -a "$LOG"
    fi
    exit 0
fi

cat > "$BENCH/nvidia-headless.conf" <<'EOF'
Section "ServerLayout"
    Identifier "HeadlessNVIDIA"
    Screen 0 "Screen0"
EndSection
Section "Device"
    Identifier "GPU0"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration" "true"
    Option "UseDisplayDevice" "none"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "GPU0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Virtual 1280 720
    EndSubSection
EndSection
EOF

AUTH="$BENCH/nvidia-Xauthority"
touch "$AUTH"
chmod 600 "$AUTH"
xauth -f "$AUTH" add :1 . "$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
Xorg :1 -config "$BENCH/nvidia-headless.conf" -auth "$AUTH" -nolisten tcp -noreset >> "$LOG" 2>&1 &
PID=$!
for attempt in $(seq 1 20); do
    if [ -S /tmp/.X11-unix/X1 ]; then break; fi
    if ! kill -0 "$PID" 2>/dev/null; then break; fi
    sleep 0.5
done
if [ ! -S /tmp/.X11-unix/X1 ]; then
    echo 'NVIDIA Xorg failed; see gpu-xorg.log.' | tee -a "$LOG"
    exit 0
fi
DISPLAY=:1 XAUTHORITY="$AUTH" xhost +si:localuser:gamer >> "$LOG" 2>&1
if DISPLAY=:1 XAUTHORITY="$AUTH" glxinfo -B 2>&1 | grep -Eiq 'OpenGL renderer string:.*NVIDIA'; then
    touch "$READY"
    echo 'Verified NVIDIA OpenGL on display :1.' | tee -a "$LOG"
else
    echo 'Display :1 is not NVIDIA accelerated.' | tee -a "$LOG"
fi
