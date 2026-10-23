# Linux Gaming & Game-Development Bench for Kaggle

A ready-to-use, self-contained cloud gaming and game-development visual test bench running on Kaggle with dual NVIDIA Tesla T4 GPUs, Selkies 2.1.0 60 FPS WebSockets streaming, and multi-storefront integration.

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
  * **Heroic Games Launcher**: Full graphical Electron UI for library browsing and OAuth authentication. Pre-configured with automatic sanitization to disable DXVK/VKD3D.
  * **Legendary CLI**: Fast, terminal-based launcher running games directly via **WineD3D** (DirectX translated to OpenGL via Mesa llvmpipe). Verified working for *Wolfenstein: The New Order*, *Borderlands 2*, *Brotato*, etc.
* **Wine-GE Runner**: Pre-configured `Wine-GE-Proton8-26` runner providing Windows API compatibility and media codecs.
* **GOG Galaxy**: Minigalaxy GTK for DRM-free Linux and Wine titles.
* **Lutris**: Multi-storefront aggregator running on Python 3.12.
* **Steam**: Valve official deb client running under unprivileged user `gamer`.

---

## Hardware Reality & Constraints

* **NVENC 60 FPS Streaming**: Tesla T4 hardware encoder captures Xvfb at 1280×720 @ 60 FPS over WebSockets.
* **Desktop 3D Graphics**: Datacenter Tesla T4 containers lack physical display scanout hardware (`/dev/nvidia-modeset`) and Vulkan ICD. All 3D rendering uses **Mesa llvmpipe software rasterization via WineD3D**. Native DXVK and hardware Vulkan are unavailable.
* **Controller Support**: 4 virtual Xbox 360 controllers enumerated via Selkies input interposer without `/dev/uinput`.
