# 7BZ Cloud Gaming: developer guide

## Purpose

7BZ streams a Linux desktop from a Kaggle GPU session so developers can browse, download, and run their own Windows game builds. A local `.exe` launches through Wine on the same display, audio, input, and GPU selection path used by Legendary. The default workflow needs no game store account.

## Source of truth and startup

Git holds the application and boot code. `build_dev_notebook.py` generates the small `kaggle_game_dev_bench.ipynb` entrypoint. The notebook clones or fast-forwards the Git checkout to `/tmp/kaggle-game-dev-bench`, runs `setup.sh`, then runs `boot_kaggle.py` and `notebook_connect.py`. It does not embed or overwrite application source.

`setup.sh` has two profiles, selected by `GAMELAB_SETUP_PROFILE` in the first notebook code cell:

| Profile | Use | Setup |
| --- | --- | --- |
| `local` (default) | Developer `.exe` games | Desktop, browser, aria2, Wine/Wine-GE, GPU translation layers, Selkies, gamepad support |
| `full` | Historical storefront suite | Everything in `local`, plus Steam, Heroic, Legendary, Lutris, Minigalaxy, EA installer, storefront libraries and GUI smoke tests |

The `full` path remains available for compatibility. The local path avoids optional storefront downloads and their repeated setup. Within the same Kaggle session, a `.setup-complete` marker keyed by Git revision and profile skips setup when the required tools are still present. A new Kaggle container has no installed packages or marker; Git alone cannot preserve apt packages, Wine prefixes, or browser binaries across fresh sessions. For a larger cold-start reduction, distribute a compatible prebuilt environment through a Kaggle dataset or image, then verify GPU driver compatibility before changing this path.

## Runtime map

| File | Responsibility |
| --- | --- |
| `setup.sh` | Install desktop, Wine, graphics, streaming, browser, and optional storefront packages |
| `boot_kaggle.py` | Start direct NVIDIA Xorg stream, fall back to Selkies desktop, report health |
| `start_direct_stream.sh`, `start_desktop.sh` | Desktop and stream process launch |
| `dev_launcher.py`, `local_tools.py` | 7BZ UI, file browser, browser launch, HTTP/torrent downloads |
| `gpu_runtime.py` | Probe graphics backend and run local `.exe` or Legendary title through Wine |
| `session_control.py`, `web_client/` | Input mode, emergency game exit, streaming HUD |
| `notebook_connect.py` | Kaggle proxy connection UI |

Local builds should be complete folders containing the `.exe` and its assets/DLLs. The Local Games browser starts in `/tmp/game-builds`; downloads go to `/home/gamer/Downloads`. Select the `.exe` and choose **Run Selected .EXE**. The game process starts with its containing folder as the working directory. Torrent transfers depend on Kaggle's network allowing peer connections.

## Validation and limits

Run `python -m unittest test_local_tools.py`, `python -m py_compile boot_kaggle.py notebook_connect.py dev_launcher.py gpu_runtime.py`, and regenerate the notebook with `python build_dev_notebook.py`. The Kaggle session must still be checked with an actual developer build to establish launch success, in-game frame rate, audio, and input. A 60 FPS stream does not prove the game renders at 60 FPS.

## Backup and rollback

Before the startup refactor, the notebook and full local Git checkout (including `.git` and uncommitted files) were saved in `D:\Kaggle Cloud Gaming Backups\2026-10-28-pre-startup`. The notebook copy is `kaggle_game_dev_bench.ipynb`; the repository snapshot is `repository-full.tar.gz`. The notebook copy's SHA-256 is `F4143D7425519FAC6EF439381FF48ECFE10EA3C25C2B837C17BFF8F85D7F96DC`.

For Kaggle rollback, restore the previous notebook version from Kaggle version history or upload the backed-up notebook. For local rollback, extract the full archive to a new directory and inspect it before replacing the current checkout. The archive contains both committed history and the then-current working tree. Never reset or clean the current checkout merely to roll back; it may contain newer work.
