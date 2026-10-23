# Kaggle Game Lab architecture

## Interactive path

```text
Browser (video, audio, pointer, keyboard, gamepad)
  ↕ HTTPS / WebSocket
Kaggle signed Jupyter proxy `/proxy/8080/`
  ↕ localhost
Selkies 2.1.0 → Xvfb :0 → H.264 NVENC on Tesla T4
             ↘ PulseAudio monitor → stereo Opus
             ↘ X11 input + userspace gamepad interposer
Openbox / tint2 / `gamer` home screen
  ↳ Steam, Heroic, Legendary, Minigalaxy, Lutris, EA installer, test builds
```

The notebook uses Kaggle's own authenticated Jupyter ingress, with no external tunnel or VPN. Its URL is valid only while the interactive session is active. Selkies is configured for 1280×720 at 60 FPS; the measured game frame rate can be lower.

## Rendering boundary

T4 NVENC is verified for video encoding. The container does not expose `/dev/nvidia-modeset` or a DRM render node to Xvfb, so GPU Vulkan/DXVK game rendering is unavailable. Mesa llvmpipe can run some Linux OpenGL and WineD3D games on CPU, with performance depending on the title. No claim that all DX11 games or storefront titles work follows from NVENC detection.

## Storefront verification

Earlier Kaggle runs showed mapped windows for Heroic, Minigalaxy, Lutris and the EA installer. Steam was still in first-run setup during its short smoke window. These results prove that GUI processes started; they do not prove account login, game installation, or a real title launch. The user reported Wolfenstein launched through Legendary in an earlier prototype and that multiple Heroic games now remain at “Launching.” Current game execution must be rechecked after the runner repair.

Heroic 2.22.4 stores global settings under `defaultSettings` in `~/.config/heroic/config.json` and per-game settings under each game ID in `~/.config/heroic/GamesConfig/<id>.json`. The notebook configures a Wine runner with both `wine` and `wineserver`, disables UMU and Vulkan translation for this container, and writes backups before repairing existing settings. It does not remove DLLs or reset existing Wine prefixes. Heroic play logs are in `GamesConfig/*-lastPlay.log`.

## User and session lifecycle

The notebook installs programs as root, then starts one Pygame home screen and storefront processes as the `gamer` user. Openbox and tint2 provide window management. User accounts, storefront sessions, Wine prefixes and installed games live in the ephemeral Kaggle container. The standard Kaggle session time and GPU quota still apply.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for acceptance checks and the console UI plan.
