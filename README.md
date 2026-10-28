# 7BZ Dev Cloud Game

A controller-first cloud gaming and game-development console running on Kaggle with dual Tesla T4 GPUs, Selkies 2.1.0 streaming, and unified storefront integration. The verified Wolfenstein path renders directly on GPU 0's NVIDIA Xorg display and streams that desktop with GPU 1's NVENC encoder.

[![Kaggle Notebook](https://img.shields.io/badge/Kaggle-Interactive%20GPU%20Bench-20BEFF?logo=kaggle)](https://www.kaggle.com/code/mohammedbastawy/interactive-gpu-game-development-bench-20261023)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Architecture Overview

```text
Browser: 7BZ glass HUD + WebCodecs H.264 + Opus + Gamepad API
    ↕ WSS / HTTPS
Kaggle Jupyter Server Proxy (/proxy/8080/)
    ↕ localhost
Selkies 2.1.0 (Tesla T4 NVENC hardware H.264 60 FPS + PulseAudio Opus)
    ↕
NVIDIA Xorg :1 (GPU 0 renders desktop and games)
    ↕
7BZ console dashboard + Openbox window management
    ↕
Card game library and storefront switcher (`dev_launcher.py`)
    ↕
Unprivileged User `gamer` (UID 1000):
    ├── Steam Native (Valve 32/64-bit client)
    ├── Heroic Games Launcher (Epic Games & GOG GUI)
    ├── Legendary game catalog (direct NVIDIA Xorg + Wine-GE)
    ├── Minigalaxy (DRM-free GOG GTK client)
    ├── Lutris Gaming Hub (Python 3.12 runner)
    └── EA App (Wine64 runner)
```

---

## Quickstart in Kaggle Notebook

Open [`kaggle_game_dev_bench.ipynb`](kaggle_game_dev_bench.ipynb) in Kaggle with
T4 x2 acceleration and Internet enabled, then run all cells. The notebook
contains its own setup scripts, launcher updates, and web client. It starts
the unified direct NVIDIA Xorg desktop on port 8080 automatically and offers
that stream as the primary link. The link cell asks for Kaggle's current
VSCode Compatible URL to build the authenticated proxy URL; no shell commands
are needed. The direct stream serves the full 7BZ top HUD, and Wolfenstein
opens borderless across 1280×720.

For continuous FPS mouse look, open the stream in a Chrome or Edge tab and
enable Gaming Mode. The Codex in-app browser rejected fullscreen and pointer
lock during the live check. See [mouse input diagnosis](MOUSE_INPUT.md).

---

## Storefront Integration & WineD3D

The default dashboard opens on **Local Games**. Browse `/tmp/game-builds`, `/home/gamer/Downloads`, or any directory under the cloud desktop home and select a Windows `.exe`. **Run Selected .EXE** invokes the same `gpu_runtime.py` Wine runner and probed NVIDIA graphics path used for Legendary games, with the executable's own directory as its working directory. No storefront or launcher account is needed for local builds. Upload complete game folders, including DLLs and assets, rather than only the executable.

The **Browser** tab opens a native browser window on the streamed desktop. Browser downloads go to `/home/gamer/Downloads`. The **Downloads** tab uses aria2 for direct HTTP(S) links, magnet links, and `.torrent` files. Select a `.torrent` in Local Games to start it. Transfers are resumable, with progress, speed, ETA, and stop controls. Game compatibility still depends on the build's Windows dependencies and the live Kaggle GPU/runtime; a successful process launch alone does not prove in-game performance.

* **Epic Games Dual Frontends**: 
  * **Heroic Games Launcher**: Full graphical Electron UI for library browsing and OAuth authentication. DXVK is enabled only when its NVIDIA Vulkan path passes the runtime probe.
  * **Legendary CLI**: Fast, terminal-based launcher using the measured NVIDIA renderer when available. CPU WineD3D is available by explicit opt-in for lightweight titles.
* **Wine-GE Runner**: Pre-configured `Wine-GE-Proton8-26` runner providing Windows API compatibility and media codecs.
* **GOG Galaxy**: Minigalaxy GTK for DRM-free Linux and Wine titles.
* **Lutris**: Multi-storefront aggregator running on Python 3.12.
* **Steam**: Valve official deb client running under unprivileged user `gamer`.

---

## Hardware Reality & Constraints

* **NVENC 60 FPS Streaming**: GPU 1 encodes the NVIDIA Xorg desktop at 1280×720 over WebSockets.
* **Desktop 3D Graphics**: GPU 0 renders Wine OpenGL directly on that same Xorg display. Clicking Play in Legendary was verified through a live Wolfenstein 3D scene. Native VirtualGL `egl0` probes succeed, but this game rendered black through that path.
* **Compatibility**: Vulkan and DXVK remain capability-gated. Games use the verified OpenGL/Wine path when Vulkan presentation is unavailable. `GAMELAB_ALLOW_SOFTWARE=1` remains an explicit fallback for lightweight titles.
* **Controller Support**: 4 virtual Xbox 360 controllers enumerated via Selkies input interposer without `/dev/uinput`.

See [GPU deployment](GPU_DEPLOYMENT.md) for the probe ladder and portable GPU host requirements.
See [community 3D research](COMMUNITY_3D_RESEARCH.md) for the isolated matching-driver injection experiment and the evidence behind it.

## NVIDIA 3D deployment and verification

The container host must provide graphics driver components **when it creates the container**. Setting `NVIDIA_DRIVER_CAPABILITIES` later in a Kaggle notebook cannot add missing device mounts or libraries. On a host you control, create the container with the NVIDIA Container Toolkit and capabilities `compute,utility,video,graphics,display,compat32` and expose the NVIDIA device nodes. The exact Docker example is:

```bash
docker run --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics,display,compat32 \
  -it your-image bash
```

The host must have matching NVIDIA 64-bit and 32-bit graphics libraries. Keep its NVIDIA kernel driver and container libraries on the **same driver version**. The repository's `setup.sh` installs Xorg, VirtualGL 3.1.5 (both bitnesses), and DXVK 2.6.2 only when the relevant NVIDIA devices or ICD are present. The downloaded packages are SHA-256 checked. It does **not** install a second NVIDIA kernel driver or create a fake Vulkan ICD.

`start_direct_stream.sh` starts NVIDIA Xorg `:1`, independent PulseAudio, Openbox, the dashboard, and Legendary. It streams directly on port 8080 via Selkies with NVENC hardware acceleration on GPU 1. `gpu_runtime.py` runs games directly on `:1` using GPU 0 hardware acceleration without VirtualGL overhead. See [Wolfenstein's verified launch path](IDTECH5_OPENGL.md).

From a running desktop terminal, check the result as user `gamer`:

```bash
python3 /tmp/kaggle-game-dev-bench/gpu_runtime.py diagnose
DISPLAY=:1 glxinfo -B                    # only when gpu-xorg-ready exists
vulkaninfo --summary                     # deviceName must be NVIDIA Tesla T4
nvidia-smi dmon -s u                     # inspect 3D/graphics utilization during a game
```

`direct_gl` or `virtualgl` must be true for GPU WineD3D. `egl_device` checks NVIDIA's display-independent EGL path separately; it alone does not prove that VirtualGL can present into Xvfb. `vulkan_window`, `vulkan_32bit_loader`, and `dxvk_files` must all be true for DXVK. `nvidia_32bit_gl` must be true for 32-bit WineD3D games. NVENC activity and a 60 FPS stream alone do not establish game frame rate or GPU rasterization. Missing `/dev/nvidia-modeset` blocks the Xorg path, but does not alone rule out EGL device rendering. `__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME`, `LD_PRELOAD`, and a hand-written `nvidia_icd.json` cannot supply driver libraries or device access that the host withheld.

### Low-latency profile and live comparison

The direct Xorg stream uses hardware H.264 8-bit 4:2:0 at 1280×720 and 60 FPS. Selkies 2.1.0's [CBR congestion control](https://github.com/selkies-project/selkies/releases/tag/2.1.0) automatically lowers video bitrate when the connection cannot carry the target 8 Mbps, down to 1 Mbps, and recovers when it can. The 7BZ HUD no longer sends competing bitrate, resolution, or frame-rate commands. Its manual video and screen sections are hidden in the Selkies sidebar. Keeping 60 FPS avoids adding frame interval delay when the route has a high but stable RTT.

WebSocket backpressure is bounded to 4 frames/chunks on the direct stream and the fallback desktop; `GAMELAB_WS_QUEUE` can override the fallback for a controlled comparison. [Selkies documents](https://docs.selkies.io/latest/reference/settings) that a larger queue can add latency. A high steady RTT with low jitter and no loss mainly reflects the network route; lowering bitrate cannot remove that baseline delay. WebRTC may offer a faster media path when direct UDP works, but a distant [TURN relay](https://github.com/selkies-project/selkies/blob/main/docs/firewall.md) can make it slower. Compare both transports in the same browser and session before changing the default WebSocket mode.

The Pygame dashboard redraws at 15 FPS while focused and 2 FPS while a game covers it. In a live T4 session this reduced its CPU use from roughly one core to about 8% of a core during Wolfenstein, while the 3D opening scene streamed at 60 FPS. The same session's client-to-Kaggle HTTP round trip had a 175 ms median, close to the browser's 181 ms stream RTT; this is evidence of a route-delay floor for that session, not an encoder or bitrate problem.

Use `GAMELAB_GRAPHICS_BACKEND=auto` (default), `wined3d`, or `dxvk` before launching a game. `dxvk` exits with a clear error unless Vulkan X11 presentation and both DXVK bitnesses pass the runtime probe. VirtualGL is only a fallback path for OpenGL WineD3D; the verified game path renders directly on NVIDIA Xorg. The setting is inherited by the Legendary launcher. Restart the game after changing the graphics backend.

During the same repeatable gameplay segment for each candidate, run:

```bash
python3 /tmp/kaggle-game-dev-bench/bench_runtime.py --label blood-west-wined3d --seconds 30 --output /kaggle/working/blood-west-wined3d.json
```

Record actual **in-game FPS**, frame-time spikes, and browser HUD input latency alongside the JSON report. The sampler records cgroup CPU consumption/throttling and per-GPU render/encoder activity. Stream FPS measures delivery, not game FPS. Compare at identical scene, resolution, and graphics settings; favor stable game frame times and low input latency over GPU utilization percentage alone.
