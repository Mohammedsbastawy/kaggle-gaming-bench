import base64
import remote_exec

script = """#!/bin/bash
exec > /tmp/wolf_vt.log 2>&1

PULSE_SOCK=$(find /tmp -name native 2>/dev/null | grep pulse | head -n 1)
if [ -n "$PULSE_SOCK" ]; then
    export PULSE_SERVER="unix:$PULSE_SOCK"
fi
export PULSE_COOKIE="/home/gamer/.config/pulse/cookie"
export DISPLAY=:0
export WINEPREFIX=/home/gamer/.wine
export PULSE_LATENCY_MSEC=60
export SDL_AUDIODRIVER=pulse
export WINEDLLOVERRIDES="dxgi=b;d3d11=b;opengl32=b"

export VGL_DISPLAY=egl0
export VGL_COMPRESS=proxy
export VGL_PROFILE=1
export VGL_VERBOSE=1
export VGL_READBACK=sync
export VGL_SYNC=1
export VGL_LOGO=1

GAME_EXE=$(find /home/gamer /kaggle -name WolfNewOrder_x64.exe 2>/dev/null | head -n 1)
WINE_BIN=$(find /home/gamer/.config/heroic/tools/wine -name wine64 -o -name wine 2>/dev/null | grep "/bin/wine" | head -n 1)

echo "PULSE_SERVER is: $PULSE_SERVER"
echo "Launching Wolfenstein: The New Order with sync readback..."

cd "$(dirname "$GAME_EXE")"
exec /opt/VirtualGL/bin/vglrun -d egl0 \
    "$WINE_BIN" \
    "$GAME_EXE" \
    +set com_skipIntroVideo 1 \
    +set com_skipBootSequence 1 \
    +set r_fullscreen 0 \
    +set r_mode -1 \
    +set r_windowedWidth 1280 \
    +set r_windowedHeight 720 \
    +set vt_cuda 0 \
    +set vt_maxPPF 16
"""

b64 = base64.b64encode(script.encode('utf-8')).decode('ascii')
cmd = f'echo {b64} | base64 -d > /tmp/run_wolf_optimized.sh && chmod +x /tmp/run_wolf_optimized.sh && chown gamer:gamer /tmp/run_wolf_optimized.sh'
res = remote_exec.run_cmd(cmd)
print("Deploy result:", res)
