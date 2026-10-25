# id Tech 5 OpenGL on the Kaggle dual-T4 desktop

## Verified working path (2026-10-25)

Wolfenstein: The New Order rendered a live 3D cockpit scene through Selkies
when Wine ran **directly on NVIDIA Xorg `:1`**. `ffmpeg -f x11grab -i :1`
captured the same scene. GPU 0 handled the game; Selkies used GPU 1's NVENC
encoder (the live log reported `NVENC H264` and `nvidia-smi` showed encoder
activity on GPU 1). This supersedes the VirtualGL backend hypothesis below
for this title. Native `glxspheres64` still works through VirtualGL, but this
game gave a black Xvfb window through `egl0`; its `:1` VirtualGL attempt hit
`GLXBadDrawable`. The precise failing VirtualGL call remains unproven.

The working path uses one NVIDIA X server for both Wine's WGL/GLX window and
Selkies capture. Running all notebook cells starts the legacy PulseAudio service,
the NVIDIA Xorg server, and the direct stream automatically. The script is also
available for recovery in an existing session:

```bash
bash /tmp/kaggle-game-dev-bench/start_direct_stream.sh
```

The notebook starts Openbox, the dashboard, and Legendary directly on `:1` and
opens **port `8080` as the primary unified desktop**. Its
Play button launches this game on the same display, so no stream switching is
needed. The direct stream holds `1280x720`; client-driven resizing to an
unsupported `928x884` mode collapsed the game's window. Independent PulseAudio supplies
the audio session. Port `8080` serves the custom Selkies web root and 7BZ top HUD.
Openbox applies a Wolfenstein-specific fullscreen rule, so its window covers
the entire 1280×720 display without a title bar or visible tint2 panel.

In the live session, clicking Play in the `:0` Legendary GUI failed with
`GLXBadDrawable` and exit status 1. That GUI inherited `DISPLAY=:0` and used
the VirtualGL path. The working `:1` GUI passed `--direct-xorg`; the same
click launched the game through its menu and into a 3D cockpit scene.

Launch this OpenGL title as `gamer` directly on `:1`:

```bash
runuser -u gamer -- env DISPLAY=:1 HOME=/home/gamer \
  WINEPREFIX=/home/gamer/.wine \
  PULSE_SERVER="$(cat /tmp/kaggle-game-dev-bench/pulse-server-path)" \
  python3 /tmp/kaggle-game-dev-bench/launch_idtech5.py --direct-xorg \
  --wine /home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine \
  /home/gamer/Games/WolfensteinTNO/WolfNewOrder_x64.exe \
  +set com_skipIntroVideo 1 +set com_skipBootSequence 1 \
  +set r_fullscreen 0 +set r_mode -1 \
  +set r_windowedWidth 1280 +set r_windowedHeight 720
```

The direct Selkies server currently runs as root: its `gamer` instance could
connect and encode but Xorg rejected its MIT-SHM attach with `BadAccess`.
The script disables browser command execution and file transfers on this
privileged stream. Keyboard input and live video were verified; gamepad input
on the direct stream still needs an end-to-end test.

Confirm a 3D frame from the actual capture display:

```bash
DISPLAY=:1 XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority \
  ffmpeg -loglevel error -f x11grab -video_size 1280x720 -i :1 \
  -frames:v 1 -y /tmp/screen_verify_3d.png
```

## What the live Kaggle session showed

The original WGL failure was resolved: captured Xvfb `:0` now advertises GLX.
In the live session on 2026-10-25, `qconsole.log` reported an NVIDIA OpenGL
3.2 context and the game process mapped `libvglfaker.so`. `VGL_LOGO=1` drew
the VirtualGL logo in the black game window. Thus Wine initialized WGL and
VirtualGL delivered at least its overlay to Xvfb. The stream displayed that
same black window, so Selkies did not cause this particular black image.

The image stayed black with `VGL_SYNC=1`, synchronous readback, windowed mode,
`+com_skipIntroVideo 1`, and even after temporarily renaming only
`base/bink/loadvideo_pc_xboxone.bik`. The video was restored before the session
ended. The game log rejected `r_customWidth` and `r_customHeight` as unknown
commands. A direct Zink probe on Xvfb failed with `DRI3 not available` and
`couldn't find RGB GLX visual or fbconfig`.

The next test is VirtualGL's GLX backend on NVIDIA Xorg `:1`. VirtualGL's
[architecture guide](https://github.com/VirtualGL/virtualgl/blob/main/doc/index.html)
says its EGL backend emulates a subset of GLX using renderbuffers, while its
GLX backend supports more GLX features. The old session expired before this
test could be completed; this is a compatibility hypothesis, not a verified
game fix.

Wine-GE's X11 WGL bridge still requires GLX on the **visible** display `:0`.
Check it separately from the VirtualGL hardware target:

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
an environment variable. Starting NVIDIA Xorg on `:1` alone does not repair
Wine's GLX query against a GLX-less `:0`.

## Launch path after `:0` advertises GLX

The notebook installs `xserver-xorg-core` and the NVIDIA Xorg display driver,
then `start_desktop.sh` tries to start GPU 0's headless GLX server on `:1`.
`launch_idtech5.py` uses `:1` when `gpu-xorg-ready` exists and its NVIDIA probe
passes; otherwise it falls back to `egl0`. Both paths draw into the Wine
window on captured `:0`.

```bash
export DISPLAY=:0
export WINEPREFIX=/home/gamer/.wine
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/1000/pulse/native}"

/opt/VirtualGL/bin/eglinfo -e
/opt/VirtualGL/bin/vglrun -d egl0 glxinfo -B

python3 /tmp/kaggle-game-dev-bench/launch_idtech5.py \
  --wine /home/gamer/.config/heroic/tools/wine/lutris-GE-Proton8-26-x86_64/bin/wine \
  /home/gamer/Games/WolfensteinTNO/WolfNewOrder_x64.exe
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

## Test the NVIDIA GLX backend explicitly

A headless NVIDIA Xorg `:1` bound to GPU 0 can provide VirtualGL's fuller GLX
backend. It still sends the Wine window and completed pixels to GLX-capable
Xvfb `:0`. Verify `gpu_xorg.sh` and its GPU 0 BusID before launching:

```bash
# First verify that gpu_xorg.sh created GPU 0's NVIDIA GLX server.
test -e /tmp/kaggle-game-dev-bench/gpu-xorg-ready
DISPLAY=:1 XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority glxinfo -B

DISPLAY=:0 python3 /tmp/kaggle-game-dev-bench/launch_idtech5.py \
  --vgl-display :1 \
  --wine /home/gamer/.config/heroic/tools/wine/lutris-GE-Proton8-26-x86_64/bin/wine \
  /home/gamer/Games/WolfensteinTNO/WolfNewOrder_x64.exe
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

## Black screen with game audio

Audio and a live Wine process show that startup progressed; they do not show
whether a non-black frame reached the Xvfb window. Use this diagnostic launch
to request windowed mode and synchronous frame delivery. It did not fix the
old session's black image, but it distinguished delivery from game content:

```bash
export DISPLAY=:0
export VGL_COMPRESS=proxy
export VGL_SYNC=1
export VGL_READBACK=sync
export VGL_LOGO=1
export VGL_PROFILE=1
export VGL_VERBOSE=1

python3 /tmp/kaggle-game-dev-bench/launch_idtech5.py \
  --wine /home/gamer/.config/heroic/tools/wine/lutris-GE-Proton8-26-x86_64/bin/wine \
  /home/gamer/Games/WolfensteinTNO/WolfNewOrder_x64.exe \
  -window +com_skipIntroVideo 1 +r_fullscreen 0 \
  2>&1 | tee /tmp/wolf-vgl.log
```

`+com_skipIntroVideo 1` is used by the published Lutris installer for this
title, but it did not cure the live black screen. Inspect the engine log at
`/home/gamer/.wine/drive_c/users/gamer/Saved Games/MachineGames/Wolfenstein The New Order/base/qconsole.log`
for the actual renderer and command line results. The game rejected the
previous `r_customWidth` and `r_customHeight` flags.

Inspect the resulting window and the frame path while the game is active:

```bash
xwininfo -root -tree | grep -Ei 'Wolf|Wine|desktop'
grep -Ei 'VGL|frame|readback|error' /tmp/wolf-vgl.log | tail -80
nvidia-smi dmon -s u -c 10

# If ffmpeg is available, compare this direct Xvfb capture with Selkies.
ffmpeg -loglevel error -f x11grab -video_size 1280x720 -i :0 \
  -frames:v 1 -y /tmp/wolf-xvfb.png
```

Interpret the evidence before changing more settings:

| Observation | Next action |
| --- | --- |
| Xvfb PNG has the game, browser is black | Investigate Selkies capture/encode, not Wine or VirtualGL. |
| Game window is absent or outside 1280x720 | Check its X11 geometry and try Wine's virtual desktop at 1280x720. |
| VirtualGL shows its logo over a black game image | The overlay reached Xvfb; check `qconsole.log`, then compare the EGL and GLX VirtualGL backends. |
| No frame transfers or logo, while the game window exists | Check that `libvglfaker.so` is loaded into the actual Wine game process; then try the `:1` NVIDIA GLX backend. |
| EGL backend fails but `:1` NVIDIA GLX succeeds | Use `vglrun -d :1` with the same captured `DISPLAY=:0`. |

After diagnosis, unset the temporary synchronous settings before normal
streaming: `unset VGL_SYNC VGL_READBACK VGL_LOGO VGL_PROFILE VGL_VERBOSE`.
`VGL_FORCEALPHADEPTH` is not a documented VirtualGL setting;
`VGL_FORCEALPHA=1` can help a specific PBO pixel-format mismatch, but is not
a general black-screen remedy. `VGL_SYNC=1` forces readback and display at
each frame trigger and can lower frame rate, so use it to locate the failure
before tuning for 60 FPS.

The intro flag is documented in the [Lutris installer](https://lutris.net/games/install/18692/view).
VirtualGL documents [frame profiling, diagnostic logo, synchronous transport,
and readback modes](https://github.com/VirtualGL/virtualgl/blob/main/doc/advancedconfig.txt).

Sources: [Wine X11 OpenGL initialization](https://github.com/wine-mirror/wine/blob/master/dlls/winex11.drv/opengl.c),
[VirtualGL changelog](https://github.com/VirtualGL/virtualgl/blob/main/ChangeLog.md),
[VirtualGL vglrun](https://github.com/VirtualGL/virtualgl/blob/main/server/vglrun.in),
[VirtualGL device selection](https://github.com/VirtualGL/virtualgl/blob/main/doc/advancedconfig.txt),
[Mesa Zink](https://docs.mesa3d.org/drivers/zink.html), and
[CUDA device enumeration](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html).
