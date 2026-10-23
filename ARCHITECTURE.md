# 7BZ Dev Cloud Game architecture

## Interactive path

```text
Browser (7BZ HUD, video, audio, pointer, keyboard, gamepad)
  ↕ HTTPS / WebSocket
Kaggle signed Jupyter proxy `/proxy/8080/`
  ↕ localhost
Selkies 2.1.0 → Xvfb :0 → H.264 NVENC on Tesla T4
             ↘ PulseAudio monitor → stereo Opus
             ↘ X11 input + userspace gamepad interposer
7BZ console dashboard / Openbox / `gamer` session
  ↳ Steam, Heroic, Legendary, Minigalaxy, Lutris, EA installer, test builds
  ↳ VirtualGL `egl0` → Tesla T4 offscreen 3D
HUD emergency control → loopback service on port 8766 → tracked game process group
```

The notebook uses Kaggle's own authenticated Jupyter ingress, with no external tunnel or VPN. Its URL is valid only while the interactive session is active. Selkies is configured for 1280×720 at 60 FPS; the measured game frame rate can be lower.

## Rendering path

T4 NVENC encodes the Xvfb desktop. VirtualGL renders supported OpenGL and WineD3D games on the T4 through its verified display-independent `egl0` device and copies the result into Xvfb for capture. DXVK is enabled only after the NVIDIA Vulkan device, X11 presentation, 32-bit loader, and bundled DXVK files all pass their probes.

## Storefront verification

Earlier Kaggle runs showed mapped windows for Heroic, Minigalaxy, Lutris and the EA installer. Steam was still in first-run setup during its short smoke window. These results prove that GUI processes started; they do not prove account login, game installation, or a real title launch. The user reported Wolfenstein launched through Legendary in an earlier prototype and that multiple Heroic games now remain at “Launching.” Current game execution must be rechecked after the runner repair.

Heroic 2.22.4 stores global settings under `defaultSettings` in `~/.config/heroic/config.json` and per-game settings under each game ID in `~/.config/heroic/GamesConfig/<id>.json`. The notebook configures a Wine runner with both `wine` and `wineserver`, disables UMU and Vulkan translation for this container, and writes backups before repairing existing settings. It does not remove DLLs or reset existing Wine prefixes. Heroic play logs are in `GamesConfig/*-lastPlay.log`.

## User and session lifecycle

The notebook installs programs as root, then starts the console dashboard, storefronts, games, and the narrow emergency-control service as `gamer`. The service terminates only the tracked game process group, then asks Wine to exit and restores dashboard focus. Selkies, Xvfb, PulseAudio, and the dashboard remain running.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for acceptance checks and the console UI plan.
