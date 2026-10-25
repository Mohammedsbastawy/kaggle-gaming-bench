"""Launch a 64-bit id Tech OpenGL game on the Selkies X desktop.

The GLX extension must exist on the captured X server.  VirtualGL sends
OpenGL work to the selected NVIDIA GLX server or EGL device and copies
completed frames into the Wine window on DISPLAY. Selkies captures :0.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


VGL = Path("/opt/VirtualGL/bin/vglrun")


def probe(args, env, timeout=15):
    result = subprocess.run(args, env=env, text=True, errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=timeout, check=False)
    return result.returncode, result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path,
                        help="Path to a 64-bit Windows OpenGL game executable")
    parser.add_argument("--wine", type=Path, required=True,
                        help="Path to Wine-GE's bin/wine or bin/wine64")
    parser.add_argument("--vgl-display", default="auto",
                        help="VirtualGL target: auto, :1, or egl0 (default: auto)")
    parser.add_argument("--direct-xorg", action="store_true",
                        help="Run directly on the NVIDIA Xorg display :1 (use its Selkies stream)")
    parser.add_argument("--egl-device", default=None,
                        help="Deprecated alias for --vgl-display")
    parser.add_argument("--prefix", type=Path,
                        default=Path("/home/gamer/.wine"))
    parser.add_argument("game_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    game = args.game.resolve()
    wine = args.wine.resolve()
    if not game.is_file() or not wine.is_file() or (not args.direct_xorg and not VGL.is_file()):
        parser.error("game, Wine binary, and selected graphics launcher must exist")

    env = os.environ.copy()
    env["DISPLAY"] = ":1" if args.direct_xorg else (env.get("DISPLAY") or ":0")
    env["WINEPREFIX"] = str(args.prefix)
    env["VGL_COMPRESS"] = "proxy"
    env["SDL_AUDIODRIVER"] = "pulse"
    overrides = env.get("WINEDLLOVERRIDES", "")
    env["WINEDLLOVERRIDES"] = (overrides + ";" if overrides else "") + "opengl32=b"
    # These variables cannot add GLX to Xvfb or select the VirtualGL GPU.
    for key in ("LIBGL_ALWAYS_SOFTWARE", "GALLIUM_DRIVER",
                "MESA_LOADER_DRIVER_OVERRIDE", "MESA_GL_VERSION_OVERRIDE",
                "MESA_GLSL_VERSION_OVERRIDE", "__NV_PRIME_RENDER_OFFLOAD",
                "__GLX_VENDOR_LIBRARY_NAME"):
        env.pop(key, None)

    if args.direct_xorg:
        # A direct GLX context and the captured window must live on the same
        # NVIDIA X server. VirtualGL's cross-server drawable mapping is not
        # reliable for this game's multi-context WGL path.
        env.pop("VGL_DISPLAY", None)
        for key in ("VGL_SYNC", "VGL_READBACK", "VGL_LOGO", "VGL_PROFILE"):
            env.pop(key, None)
        socket_dir = Path("/tmp/kaggle-game-dev-bench/direct-stream-sockets")
        input_hook = Path("/tmp/kaggle-game-dev-bench/lib64/selkies_input_interposer.so")
        if socket_dir.is_dir() and input_hook.is_file():
            env["SELKIES_JS_SOCKET_PATH"] = str(socket_dir)
            env["LD_PRELOAD"] = (str(input_hook) + ":" + env.get("LD_PRELOAD", "")).rstrip(":")
            env["SDL_JOYSTICK_DISABLE_UDEV"] = "1"
        try:
            rc, info = probe(["glxinfo", "-B"], env)
            if rc or not re.search(r"OpenGL vendor string:\s*NVIDIA", info):
                raise RuntimeError("NVIDIA GLX is unavailable on :1: " + info[-500:])
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            print(f"Graphics prerequisite failed: {exc}", file=sys.stderr)
            return 78
        wine_bin = wine.with_name("wine64") if wine.with_name("wine64").is_file() else wine
        command = [str(wine_bin), str(game)]
        command.extend(args.game_args or
                       ["+set", "com_skipIntroVideo", "1",
                        "+set", "com_skipBootSequence", "1",
                        "+set", "r_fullscreen", "0", "+set", "r_mode", "-1",
                        "+set", "r_windowedWidth", "1280",
                        "+set", "r_windowedHeight", "720"])
        print("OpenGL target: direct NVIDIA Xorg :1", flush=True)
        print("Stream this display using start_direct_stream.sh", flush=True)
        return subprocess.call(command, cwd=game.parent, env=env)

    try:
        rc, extensions = probe(["xdpyinfo", "-queryExtensions"], env)
        if rc or not re.search(r"(?m)^\s*GLX\s+\(opcode:", extensions):
            raise RuntimeError(
                f"{env['DISPLAY']} does not advertise GLX. Wine's winex11.drv "
                "will disable WGL. Restart the captured Xvfb with GLX enabled "
                "or use a GLX-capable captured X server."
            )

        selected = args.egl_device or args.vgl_display
        if selected == "auto":
            candidates = ([":1"] if Path("/tmp/kaggle-game-dev-bench/gpu-xorg-ready").exists()
                          else []) + ["egl0"]
        else:
            candidates = [selected]
        failures = []
        for candidate in candidates:
            rc, info = probe([str(VGL), "-d", candidate, "glxinfo", "-B"], env)
            if (not rc and re.search(r"OpenGL vendor string:\s*NVIDIA", info)
                    and not re.search(r"OpenGL renderer string:.*(?:llvmpipe|softpipe)", info, re.I)):
                selected = candidate
                break
            failures.append(f"{candidate}: {info[-500:]}")
        else:
            raise RuntimeError("VirtualGL NVIDIA probe failed:\n" + "\n".join(failures))
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"Graphics prerequisite failed: {exc}", file=sys.stderr)
        return 78

    # vglrun already preloads libdlfaker and libvglfaker by default.
    wine_bin = wine.with_name("wine64") if wine.with_name("wine64").is_file() else wine
    env["VGL_DISPLAY"] = selected
    command = [str(VGL), "-d", selected, str(wine_bin), str(game)]
    if not args.game_args:
        command.extend(["-window", "+com_skipIntroVideo", "1", "+r_fullscreen", "0"])
    else:
        command.extend(args.game_args)
    print("OpenGL target:", selected, flush=True)
    print("Wine window:", env["DISPLAY"], flush=True)
    return subprocess.call(command, cwd=game.parent, env=env)


if __name__ == "__main__":
    sys.exit(main())
