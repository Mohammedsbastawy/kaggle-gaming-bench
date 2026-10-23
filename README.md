# Linux Gaming & Game-Development Bench for Kaggle

A cloud gaming and game-development visual test bench running on Kaggle with an NVIDIA Tesla T4, Selkies 2.1.0 streaming, and multi-storefront integration. GPU video encoding works in the observed container; 3D game rendering currently falls back to the CPU.

[![Kaggle Notebook](https://img.shields.io/badge/Kaggle-Interactive%20GPU%20Bench-20BEFF?logo=kaggle)](https://www.kaggle.com/code/mohammedbastawy/interactive-gpu-game-development-bench-20261023)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Architecture Overview

```text
Browser: WebCodecs H.264 + Opus Stereo + Gamepad API / Touch Controls
    ↕ WSS / HTTPS
Kaggle Jupyter Server Proxy (/proxy/8080/)
    ↕ localhost
Selkies 2.1.0 (Tesla T4 NVENC hardware H.264 60 FPS + PulseAudio Opus)
    ↕
Openbox Window Manager + tint2 Taskbar Panel
    ↕
Pygame Controller-Friendly Launcher (`dev_launcher.py`)
    ↕
Unprivileged User `gamer` (UID 1000):
    ├── Steam Native (Valve 32/64-bit client)
    ├── Heroic Games Launcher (Epic Games & GOG GUI)
    ├── Legendary CLI Manager (Direct Epic Games execution via WineD3D)
    ├── Minigalaxy (DRM-free GOG GTK client)
    ├── Lutris Gaming Hub (Python 3.12 runner)
    └── EA App (Wine64 runner)
```

---

## Quickstart in Kaggle Notebook

To import and launch the bench directly from this repository:

```python
import subprocess, os
from pathlib import Path

BENCH = Path('/tmp/kaggle-game-dev-bench')
REPO = 'https://github.com/Mohammedsbastawy/kaggle-gaming-bench.git'

if not (BENCH / 'setup.sh').exists():
    subprocess.run(['git', 'clone', REPO, str(BENCH)], check=True)

# Run resilient bootstrap setup
subprocess.run(['bash', str(BENCH / 'setup.sh')], check=True)
```

Then start the Selkies session using the provided starter.

---

## Storefront Integration & WineD3D

* **Epic Games Dual Frontends**: 
  * **Heroic Games Launcher**: Full graphical Electron UI for library browsing and OAuth authentication. DXVK is enabled only when its NVIDIA Vulkan path passes the runtime probe.
  * **Legendary CLI**: Fast, terminal-based launcher using the measured NVIDIA renderer when available. CPU WineD3D is available by explicit opt-in for lightweight titles.
* **Wine-GE Runner**: Pre-configured `Wine-GE-Proton8-26` runner providing Windows API compatibility and media codecs.
* **GOG Galaxy**: Minigalaxy GTK for DRM-free Linux and Wine titles.
* **Lutris**: Multi-storefront aggregator running on Python 3.12.
* **Steam**: Valve official deb client running under unprivileged user `gamer`.

---

## Hardware Reality & Constraints

* **NVENC 60 FPS Streaming**: Tesla T4 hardware encoder captures Xvfb at 1280×720 @ 60 FPS over WebSockets.
* **Desktop 3D Graphics**: Version 28 exposes compute and NVENC, but its observed NVIDIA OpenGL and Vulkan probes fail; Xvfb renders through llvmpipe. The launcher refuses an unaccelerated game launch by default. `GAMELAB_ALLOW_SOFTWARE=1` opts into a CPU profile for light games and basic tests; it cannot make modern AAA games playable.

See [GPU deployment and CPU fallback](GPU_DEPLOYMENT.md) for the Version 28 diagnosis, one final headless EGL test, and portable GPU host requirements.
See [community 3D research](COMMUNITY_3D_RESEARCH.md) for the isolated matching-driver injection experiment and the evidence behind it.

## NVIDIA 3D deployment and verification

The container host must provide graphics driver components **when it creates the container**. Setting `NVIDIA_DRIVER_CAPABILITIES` later in a Kaggle notebook cannot add missing device mounts or libraries. On a host you control, create the container with the NVIDIA Container Toolkit and capabilities `compute,utility,video,graphics,display,compat32` and expose the NVIDIA device nodes. The exact Docker example is:

```bash
docker run --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics,display,compat32 \
  -it your-image bash
```

The host must have matching NVIDIA 64-bit and 32-bit graphics libraries. Keep its NVIDIA kernel driver and container libraries on the **same driver version**. The repository's `setup.sh` installs Xorg, VirtualGL 3.1.5 (both bitnesses), and DXVK 2.6.2 only when the relevant NVIDIA devices or ICD are present. The downloaded packages are SHA-256 checked. It does **not** install a second NVIDIA kernel driver or create a fake Vulkan ICD.

`start_desktop.sh` keeps Selkies on Xvfb and starts an optional NVIDIA Xorg on `:1` when display devices are mounted. VirtualGL first tests its headless EGL device path (`egl0`), then the Xorg path, accepting either only when `glxinfo` reports an NVIDIA renderer. The headless Xorg config uses `AllowEmptyInitialConfiguration` and `UseDisplayDevice none`; `gpu_xorg.sh` logs failures in `/tmp/kaggle-game-dev-bench/logs/gpu-xorg.log`. VirtualGL transfers OpenGL frames from the GPU X server into the Xvfb desktop that Selkies captures. `gpu_runtime.py` checks the live OpenGL renderer and NVIDIA Vulkan device plus an actual X11 Vulkan swapchain. It installs both DXVK DLL bitnesses into the Wine prefix with backups only when the Vulkan check passes; otherwise it uses GPU WineD3D if available. The Legendary GUI and terminal menu call this wrapper automatically. Heroic enables its DXVK setting only when the same Vulkan check passes.

From a running desktop terminal, check the result as user `gamer`:

```bash
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose
DISPLAY=:1 glxinfo -B                    # only when gpu-xorg-ready exists
vulkaninfo --summary                     # deviceName must be NVIDIA Tesla T4
nvidia-smi dmon -s u                     # inspect 3D/graphics utilization during a game
```

`direct_gl` or `virtualgl` must be true for GPU WineD3D. `egl_device` checks NVIDIA's display-independent EGL path separately. `vulkan_window`, `vulkan_32bit_loader`, and `dxvk_files` must all be true for DXVK. `nvidia_32bit_gl` must be true for 32-bit games. NVENC activity and a 60 FPS stream alone do not establish game frame rate or GPU rasterization. Missing `/dev/nvidia-modeset` blocks the Xorg path, but does not alone rule out EGL device rendering. `__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME`, `LD_PRELOAD`, and a hand-written `nvidia_icd.json` cannot supply driver libraries or device access that the host withheld.
* **Controller Support**: 4 virtual Xbox 360 controllers enumerated via Selkies input interposer without `/dev/uinput`.
