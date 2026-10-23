# id Tech 5 OpenGL on the Kaggle dual-T4 desktop

## Why the game currently fails

Wine-GE's X11 WGL bridge queries the **visible** X server for the GLX
extension. The reported `GLX extension is missing` means the captured `:0`
server fails that check. `vglrun -d egl0 glxinfo -B` proves that VirtualGL can
reach NVIDIA through EGL; it does not prove that Wine can initialize WGL on
this Xvfb. VirtualGL's EGL GLX emulation also requires GLX on the 2D X server.

Check the server from the same account and environment used by Wine:

```bash
export DISPLAY=:0
xdpyinfo -queryExtensions | grep -E '^[[:space:]]*GLX[[:space:]]+\(opcode:'
/opt/VirtualGL/bin/vglrun -d egl0 glxinfo -B
```

If the first command finds no GLX, restart the **captured** Xvfb with GLX
enabled. Stop the Selkies session that owns `:0` first; do not remove an X
socket or kill an unrelated X server. This is a known Xvfb startup form:

```bash
Xvfb :0 -screen 0 1280x720x24 \
  +extension GLX +extension RENDER +extension MIT-SHM \
  -nolisten tcp -noreset > /tmp/xvfb-glx.log 2>&1 &
export DISPLAY=:0
xdpyinfo -queryExtensions | grep -E '^[[:space:]]*GLX[[:space:]]+\(opcode:'
```

If the packaged Xvfb still does not advertise GLX, it cannot be enabled with
an environment variable. Use a build of Xvfb that contains the GLX extension,
or make an NVIDIA Xorg server on GPU 0 the captured `:0` display and attach
Selkies to that display. Starting NVIDIA Xorg on `:1` alone does not repair
Wine's GLX query against a GLX-less `:0`.

## Preferred game path after `:0` advertises GLX

Use VirtualGL's EGL device backend first. It avoids the extra NVIDIA Xorg
server while preserving the Selkies desktop on `:0`:

```bash
export DISPLAY=:0
export WINEPREFIX=/home/gamer/.wine
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/1000/pulse/native}"

/opt/VirtualGL/bin/eglinfo -e
/opt/VirtualGL/bin/vglrun -d egl0 glxinfo -B

python3 /tmp/kaggle-game-dev-bench/launch_idtech5.py \
  --wine /home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine \
  --egl-device egl0 \
  '/path/to/WolfNewOrder_x64.exe'
```

Use the EGL device that maps to **GPU 0**. `egl0` is an EGL enumeration ID,
not a guarantee that it equals `/dev/nvidia0`; both GPUs have the same model
and renderer string. Check `eglinfo -e` against the GPUs' PCI bus IDs, then
watch per-GPU graphics and encoder load while the game is running:

```bash
nvidia-smi --query-gpu=index,uuid,pci.bus_id --format=csv
nvidia-smi dmon -s u -c 20
nvidia-smi pmon -s um -c 20
```

GPU 0 should show game graphics activity; GPU 1 should show NVENC activity.
Selkies must choose GPU 1 in **its own process**. `CUDA_VISIBLE_DEVICES=1`
renumbers that GPU as CUDA ordinal 0 inside Selkies; an encoder setting that
also selects ordinal 1 can therefore select no device. Confirm the actual
encoder device from Selkies logs and `nvidia-smi` rather than the variable names.

## If VirtualGL's EGL backend fails a game-specific GLX feature

A headless NVIDIA Xorg `:1` bound to GPU 0 can provide VirtualGL's fuller GLX
backend. It still sends the Wine window and completed pixels to GLX-capable
Xvfb `:0`:

```bash
# First verify that gpu_xorg.sh created GPU 0's NVIDIA GLX server.
test -e /tmp/kaggle-game-dev-bench/gpu-xorg-ready
DISPLAY=:1 XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority glxinfo -B

DISPLAY=:0 VGL_COMPRESS=proxy \
  /opt/VirtualGL/bin/vglrun -d :1 \
  /home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine \
  '/path/to/WolfNewOrder_x64.exe'
```

Ensure `gpu_xorg.sh` actually binds `:1` to GPU 0; a renderer string of
`Tesla T4` alone cannot distinguish identical cards. The Xorg path requires
the NVIDIA X driver and accessible `/dev/nvidia-modeset`. VirtualGL does not
redirect DXVK or VKD3D Vulkan presentation; those need a Vulkan-capable
captured display and are unrelated to this OpenGL title.

Do not set `MESA_GL_VERSION_OVERRIDE`, `MESA_LOADER_DRIVER_OVERRIDE=zink`,
`__NV_PRIME_RENDER_OFFLOAD`, or `__GLX_VENDOR_LIBRARY_NAME` to solve the
missing GLX extension. Those variables cannot add an X server extension.
Zink is a separate Mesa-on-Vulkan experiment and still needs an appropriate
X11 presentation path. Current VirtualGL enables its dlopen interposer by
default: use `vglrun -d egl0 wine ...`, without `-dl`.

Sources: [Wine X11 OpenGL initialization](https://github.com/wine-mirror/wine/blob/master/dlls/winex11.drv/opengl.c),
[VirtualGL changelog](https://github.com/VirtualGL/virtualgl/blob/main/ChangeLog.md),
[VirtualGL vglrun](https://github.com/VirtualGL/virtualgl/blob/main/server/vglrun.in),
[VirtualGL device selection](https://github.com/VirtualGL/virtualgl/blob/main/doc/advancedconfig.txt),
[Mesa Zink](https://docs.mesa3d.org/drivers/zink.html), and
[CUDA device enumeration](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html).
