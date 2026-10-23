"""Launch a 64-bit id Tech OpenGL game on the Selkies X desktop.

The GLX extension must exist on the captured X server.  VirtualGL sends
OpenGL work to the selected NVIDIA EGL device and copies completed frames
back into the Wine window on DISPLAY; Selkies encodes that desktop separately.
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
    parser.add_argument("--egl-device", default="egl0",
                        help="VirtualGL EGL device verified to map to GPU 0")
    parser.add_argument("--prefix", type=Path,
                        default=Path("/home/gamer/.wine"))
    parser.add_argument("game_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    game = args.game.resolve()
    wine = args.wine.resolve()
    if not game.is_file() or not wine.is_file() or not VGL.is_file():
        parser.error("game, Wine binary, and /opt/VirtualGL/bin/vglrun must exist")

    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY") or ":0"
    env["WINEPREFIX"] = str(args.prefix)
    env["VGL_DISPLAY"] = args.egl_device
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

    try:
        rc, extensions = probe(["xdpyinfo", "-queryExtensions"], env)
        if rc or not re.search(r"(?m)^\s*GLX\s+\(opcode:", extensions):
            raise RuntimeError(
                f"{env['DISPLAY']} does not advertise GLX. Wine's winex11.drv "
                "will disable WGL. Restart the captured Xvfb with GLX enabled "
                "or use a GLX-capable captured X server."
            )

        rc, info = probe([str(VGL), "-d", args.egl_device,
                          "glxinfo", "-B"], env)
        if (rc or not re.search(r"OpenGL vendor string:\s*NVIDIA", info)
                or re.search(r"OpenGL renderer string:.*(?:llvmpipe|softpipe)", info, re.I)):
            raise RuntimeError("VirtualGL NVIDIA probe failed:\n" + info[-2000:])
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"Graphics prerequisite failed: {exc}", file=sys.stderr)
        return 78

    # vglrun already preloads libdlfaker and libvglfaker by default.
    wine_bin = wine.with_name("wine64") if wine.with_name("wine64").is_file() else wine
    command = [str(VGL), "-d", args.egl_device, str(wine_bin), str(game)]
    if not args.game_args:
        command.extend(["+com_skipIntroVideo", "1", "+r_fullscreen", "0",
                        "+r_mode", "-1", "+r_customWidth", "1280", "+r_customHeight", "720"])
    else:
        command.extend(args.game_args)
    print("OpenGL target:", args.egl_device, flush=True)
    print("Wine window:", env["DISPLAY"], flush=True)
    return subprocess.call(command, cwd=game.parent, env=env)


if __name__ == "__main__":
    sys.exit(main())
