# 7BZ Cloud Gaming: developer guide

## Purpose

7BZ streams a Linux desktop from a Kaggle GPU session so developers can browse, download, and run their own Windows game builds. A local `.exe` launches through Wine on the same display, audio, input, and GPU selection path used by Legendary. The default workflow needs no game store account.

## Source of truth and startup

Git holds the application and boot code. `build_dev_notebook.py` generates the small `kaggle_game_dev_bench.ipynb` entrypoint. The notebook clones or fast-forwards the Git checkout to `/tmp/kaggle-game-dev-bench`, runs `setup.sh`, then runs `boot_kaggle.py` and `notebook_connect.py`. It does not embed or overwrite application source.

`setup.sh` has two profiles, selected by `GAMELAB_SETUP_PROFILE` in the first notebook code cell:

| Profile | Use | Setup |
| --- | --- | --- |
| `local` (default) | Developer `.exe` games and Epic login | Desktop, browser, aria2, Wine/Wine-GE, GPU translation layers, Selkies, gamepad support, Legendary |
| `full` | Historical storefront suite | Everything in `local`, plus Steam, Heroic, Lutris, Minigalaxy, EA installer, storefront libraries and GUI smoke tests |

The `full` path remains available for compatibility. The local path avoids optional storefront downloads and their repeated setup. Within the same Kaggle session, a `.setup-complete` marker keyed by Git revision and profile skips setup when the required tools are still present. A new Kaggle container has no installed packages or marker; Git alone cannot preserve apt packages, Wine prefixes, or browser binaries across fresh sessions. For a larger cold-start reduction, distribute a compatible prebuilt environment through a Kaggle dataset or image, then verify GPU driver compatibility before changing this path.

The local profile also skips boot-time Visual C++ installers, `winetricks vcrun2019`, and repeated Wine registry writes. `gpu_runtime.py` applies the game input settings at launch. If a build needs Microsoft VC runtimes, set `GAMELAB_PREINSTALL_PREREQS=1` in the first notebook code cell before running setup, or use the `full` profile. The notebook prints setup duration to help compare cold starts. This change reduces setup work but does not promise a particular cold-start time; apt, Wine-GE, GPU provisioning, and network speed still vary by Kaggle session.

## Runtime map

| File | Responsibility |
| --- | --- |
| `setup.sh` | Install desktop, Wine, graphics, streaming, browser, and optional storefront packages |
| `install_lichii.sh` | Install pinned Lichii build 117 Linux PGO AppImage without FUSE |
| `boot_kaggle.py` | Start direct NVIDIA Xorg stream, fall back to Selkies desktop, report health |
| `start_direct_stream.sh`, `start_desktop.sh` | Desktop and stream process launch |
| `dev_launcher.py`, `local_tools.py` | 7BZ UI, file browser, browser launch, HTTP/torrent downloads |
| `gpu_runtime.py` | Probe graphics backend and run local `.exe` or Legendary title through Wine |
| `session_control.py`, `web_client/` | Input mode, emergency game exit, streaming HUD |
| `notebook_connect.py` | Kaggle proxy connection UI |

Local builds should be complete folders containing the `.exe` and its assets/DLLs. The Local Games browser starts in `/tmp/game-builds`; downloads go to `/home/gamer/Downloads`. Select the `.exe` and choose **Run Selected .EXE**. The game process starts with its containing folder as the working directory. Torrent transfers depend on Kaggle's network allowing peer connections.

The Lichii EMU tab launches `/opt/lichii/squashfs-root/AppRun` from the pinned build 117 AppImage installed in either setup profile. The upstream package needs glibc 2.39 or newer, as provided by Ubuntu 24.04. Lichii settings and saves live under the `gamer` home directory; game files, keys, and firmware are supplied by the user. A fresh Kaggle session downloads the package again. A failed download leaves the tab visible with an unavailable status.

## Validation and limits

Run `python -m unittest test_local_tools.py`, `python -m py_compile boot_kaggle.py notebook_connect.py dev_launcher.py gpu_runtime.py`, and regenerate the notebook with `python build_dev_notebook.py`. The Kaggle session must still be checked with an actual developer build to establish launch success, in-game frame rate, audio, and input. A 60 FPS stream does not prove the game renders at 60 FPS.

## Backup and rollback

Before the startup refactor, the notebook and full local Git checkout (including `.git` and uncommitted files) were saved in `D:\Kaggle Cloud Gaming Backups\2026-10-28-pre-startup`. The notebook copy is `kaggle_game_dev_bench.ipynb`; the repository snapshot is `repository-full.tar.gz`. The notebook copy's SHA-256 is `F4143D7425519FAC6EF439381FF48ECFE10EA3C25C2B837C17BFF8F85D7F96DC`.

For Kaggle rollback, restore the previous notebook version from Kaggle version history or upload the backed-up notebook. For local rollback, extract the full archive to a new directory and inspect it before replacing the current checkout. The archive contains both committed history and the then-current working tree. Never reset or clean the current checkout merely to roll back; it may contain newer work.

## Saved live-session fixes — 2026-11-10

The notebook continues to load the latest `main` revision from Git. Updating this repository does not restart an active Kaggle session.

Fresh boots prefer direct NVIDIA Xorg, with VirtualGL/Xvfb retained as a fallback. Streaming remains 1080p/30 FPS with a two-frame backpressure queue and a 6 Mbps initial bitrate (1.5–10 Mbps range). Ghostrunner uses 67% render scale and a 30 FPS limit, preserving original configuration backups. Vulkan presentation must still pass its probe before DXVK is selected; black surfaces on WineD3D remain unresolved.

The Wine launcher preserves the stream's controller socket directory and sets up input interposers before starting Wine configuration commands. The HUD resynchronizes late-connected gamepads and acquires relative mouse capture on a game-surface click. Physical reconnect and mouse behavior still require user validation. Game saves and installed games in the temporary container are not made persistent by these source changes.

## Direct WebRTC profile — 2026-11-10

Fresh direct-Xorg boots now use 1080p/60 FPS WebRTC with NVENC, an 8 Mbps initial bitrate (6–12 Mbps range), congestion control, and 5 ms audio frames. `rtc_config.json` uses STUN only, avoiding the default public TURN relay. Live testing reported 190–210 ms RTT at 1080p, compared with over 250 ms on the earlier WebSocket session. These are observations for one connection, not a latency guarantee or measured input-to-display latency. The remaining delay is substantial.

STUN-only WebRTC may fail on restrictive networks. Set `GAMELAB_TRANSPORT=websockets` before boot for the previous transport, or provide `SELKIES_RTC_CONFIG_JSON` containing suitable ICE servers. Keep TURN credentials outside Git. Transport switching remains enabled. The WebSocket fallback queue is one frame. The source change does not migrate or restart an active session.
