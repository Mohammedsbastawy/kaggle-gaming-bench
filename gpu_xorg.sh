#!/bin/bash
# Optional NVIDIA 3D server for VirtualGL. Selkies keeps its Xvfb desktop.
set -u
BENCH=/tmp/kaggle-game-dev-bench
READY="$BENCH/gpu-xorg-ready"
LOG="$BENCH/logs/gpu-xorg.log"
rm -f "$READY"
mkdir -p "$BENCH/logs"

if [ ! -c /dev/nvidia-modeset ]; then
    mknod -m 666 /dev/nvidia-modeset c 195 254 2>/dev/null || nvidia-modprobe -m 2>/dev/null || true
fi
if [ ! -c /dev/nvidiactl ] || [ ! -c /dev/nvidia0 ] || [ ! -c /dev/nvidia-modeset ]; then
    echo 'NVIDIA display devices were not mounted by the container host.' | tee -a "$LOG"
    exit 0
fi
mkdir -p /usr/lib/xorg/modules/drivers /usr/lib/xorg/modules/extensions 2>/dev/null || true
if [ -d /usr/local/nvidia/lib64/xorg/modules ]; then
    cp -fL /usr/local/nvidia/lib64/xorg/modules/drivers/nvidia_drv.so /usr/lib/xorg/modules/drivers/ 2>/dev/null || true
    cp -fL /usr/local/nvidia/lib64/xorg/modules/extensions/libglxserver_nvidia.so* /usr/lib/xorg/modules/extensions/ 2>/dev/null || true
fi
for drv in $(find /usr/local/nvidia /usr/lib -name nvidia_drv.so 2>/dev/null); do
    if [ -f "$drv" ] && [ ! -f /usr/lib/xorg/modules/drivers/nvidia_drv.so ]; then
        cp -a "$drv" /usr/lib/xorg/modules/drivers/ 2>/dev/null || true
    fi
done
for glx in $(find /usr/local/nvidia /usr/lib -name 'libglxserver_nvidia.so*' 2>/dev/null); do
    if [ -f "$glx" ] && [ ! -f /usr/lib/xorg/modules/extensions/libglxserver_nvidia.so ]; then
        cp -a "$glx" /usr/lib/xorg/modules/extensions/libglxserver_nvidia.so 2>/dev/null || true
    fi
done

if ! command -v Xorg >/dev/null || ! find /usr/lib /usr/local/nvidia -name nvidia_drv.so -print -quit 2>/dev/null | grep -q .; then
    echo 'NVIDIA Xorg display driver or Xorg is missing. Host graphics/display capability is required.' | tee -a "$LOG"
    exit 1
fi
# Identical T4 renderer strings cannot identify the card. Pin this X server
# to nvidia-smi GPU 0's PCI address instead of relying on Xorg probe order.
pci_address=$(nvidia-smi -i 0 --query-gpu=pci.bus_id --format=csv,noheader 2>/dev/null | head -n 1 | tr -d '[:space:]')
if [[ ! "$pci_address" =~ ^([[:xdigit:]]+):([[:xdigit:]]+):([[:xdigit:]]+)\.([0-7])$ ]]; then
    echo "Cannot determine GPU 0 PCI bus ID: $pci_address" | tee -a "$LOG"
    exit 0
fi
domain=$((16#${BASH_REMATCH[1]}))
bus=$((16#${BASH_REMATCH[2]}))
device=$((16#${BASH_REMATCH[3]}))
func_num=${BASH_REMATCH[4]}
bus_id="PCI:${bus}:${device}:${func_num}"
if [ "$domain" -ne 0 ]; then bus_id="PCI:${bus}@${domain}:${device}:${func_num}"; fi
# Xorg can leave its socket and PID lock behind after a crash. A dead lock
# owner proves that removing those exact files cannot disconnect a live server.
if [ -S /tmp/.X11-unix/X1 ] && [ -f /tmp/.X1-lock ]; then
    lock_pid=$(tr -cd '0-9' < /tmp/.X1-lock)
    if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
        rm -f -- /tmp/.X11-unix/X1 /tmp/.X1-lock
        echo 'Removed stale Xorg :1 socket and lock.' | tee -a "$LOG"
    fi
fi
if [ -S /tmp/.X11-unix/X1 ]; then
    if grep -Fq "BusID \"$bus_id\"" "$BENCH/nvidia-headless.conf" 2>/dev/null && \
       DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" glxinfo -B 2>&1 | grep -Eiq 'OpenGL vendor string:.*NVIDIA'; then
        DISPLAY=:1 XAUTHORITY="$BENCH/nvidia-Xauthority" xhost +si:localuser:gamer >> "$LOG" 2>&1
        touch "$READY"
        echo 'Reusing verified NVIDIA Xorg display :1.' | tee -a "$LOG"
    else
        echo 'Display :1 is occupied by an unverified X server.' | tee -a "$LOG"
    fi
    exit 0
fi

cat > "$BENCH/nvidia-headless.conf" <<EOF
Section "ServerLayout"
    Identifier "HeadlessNVIDIA"
    Screen 0 "Screen0"
EndSection
Section "Device"
    Identifier "GPU0"
    Driver "nvidia"
    BusID "$bus_id"
    Option "AllowEmptyInitialConfiguration" "true"
    Option "ConnectedMonitor" "DFP-0"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "GPU0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1280x720"
    EndSubSection
EndSection
EOF

AUTH="$BENCH/nvidia-Xauthority"
touch "$AUTH"
chmod 600 "$AUTH"
xauth -f "$AUTH" add :1 . "$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
nohup /usr/lib/xorg/Xorg :1 -config "$BENCH/nvidia-headless.conf" -auth "$AUTH" -nolisten tcp -noreset >> "$LOG" 2>&1 < /dev/null &
PID=$!
disown "$PID" 2>/dev/null || true
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
if DISPLAY=:1 XAUTHORITY="$AUTH" glxinfo -B 2>&1 | grep -Eiq 'OpenGL (vendor|renderer) string:.*(NVIDIA|Tesla)'; then
    touch "$READY"
    echo 'Verified NVIDIA OpenGL on display :1.' | tee -a "$LOG"
else
    echo 'Display :1 is not NVIDIA accelerated.' | tee -a "$LOG"
fi
