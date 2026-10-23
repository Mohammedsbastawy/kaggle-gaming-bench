"""Choose a measured graphics path for Legendary/Wine games.

NVENC and nvidia-smi are deliberately not treated as proof of 3D rendering.
Run ``python3 gpu_runtime.py diagnose`` inside the live desktop session.
"""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def run(command, env=None, timeout=12):
    try:
        result = subprocess.run(command, env=env, text=True, errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def clean_env():
    env = os.environ.copy()
    for key in ("LIBGL_ALWAYS_SOFTWARE", "GALLIUM_DRIVER", "MESA_LOADER_DRIVER_OVERRIDE",
                "MESA_GL_VERSION_OVERRIDE", "LIBGL_DRIVERS_PATH",
                "__GLX_VENDOR_LIBRARY_NAME"):
        env.pop(key, None)
    # The Selkies input interposer must not affect graphics probes.
    env.pop("LD_PRELOAD", None)
    return env


def nvidia_renderer(output):
    vendor = re.search(r"OpenGL vendor string:\s*(.+)", output, re.I)
    renderer = re.search(r"OpenGL renderer string:\s*(.+)", output, re.I)
    # Tesla renderers often say "Tesla T4/PCIe/SSE2", without "NVIDIA".
    return bool(vendor and "NVIDIA" in vendor.group(1).upper() and renderer
                and not re.search(r"llvmpipe|softpipe|software", renderer.group(1), re.I))


def has_32bit_library(name):
    injected = os.environ.get("GAMELAB_NVIDIA_LIB32", "")
    if injected:
        candidate = Path(injected) / name
        try:
            with candidate.open("rb") as library:
                if library.read(5) == b"\x7fELF\x01":
                    return True
        except OSError:
            pass
    rc, out = run(["ldconfig", "-p"], timeout=4)
    return rc == 0 and any(f"{name} (libc6)" in line
                           for line in out.splitlines())


def dxvk_available():
    root = Path("/opt/gamelab-dxvk/dxvk-2.6.2")
    return all((root / arch / (name + ".dll")).is_file()
               for arch in ("x32", "x64")
               for name in ("d3d9", "d3d10core", "d3d11", "dxgi"))


def egl_device_probe(env):
    """Test the NVIDIA EGL device directly, independent of Xorg and Xvfb."""
    eglinfo = Path("/opt/VirtualGL/bin/eglinfo")
    if not eglinfo.is_file():
        return False, "VirtualGL eglinfo is not installed", ""
    rc, listing = run([str(eglinfo), "-e"], env, timeout=8)
    candidates = list(dict.fromkeys(re.findall(r"\begl\d+\b", listing)))[:8] if rc == 0 else []
    if not candidates:
        candidates = ["egl0"]
    last_result = listing[-240:]
    for target in candidates:
        rc, out = run([str(eglinfo), target], env, timeout=12)
        renderer = next((line.strip() for line in out.splitlines()
                         if line.strip().startswith("OpenGL renderer string:")), "")
        vendor = next((line.strip() for line in out.splitlines()
                       if line.strip().startswith("OpenGL vendor string:")), "")
        if (rc == 0 and "NVIDIA" in vendor.upper() and renderer
                and not re.search(r"llvmpipe|softpipe|software", renderer, re.I)):
            return True, renderer, target
        last_result = renderer or out[-240:]
    return False, last_result, ""


def cpu_quota_count():
    """Return the cgroup CPU quota as a whole-core budget, if one exists."""
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            return max(1, math.floor(int(quota) / int(period)))
    except (OSError, ValueError, ZeroDivisionError):
        pass
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        if quota > 0:
            return max(1, math.floor(quota / period))
    except (OSError, ValueError, ZeroDivisionError):
        pass
    return None


def software_threads():
    override = os.environ.get("LP_NUM_THREADS", "")
    if override.isdigit() and 1 <= int(override) <= 32:
        return int(override)
    try:
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        cores = os.cpu_count() or 1
    quota = cpu_quota_count()
    if quota is not None:
        cores = min(cores, quota)
    reserve = 2 if cores >= 4 else 1
    return max(1, min(8, cores - reserve))


def lower_software_resolution(env):
    """Best-effort temporary Xvfb mode change; game settings may differ."""
    requested = os.environ.get("GAMELAB_SOFTWARE_RESOLUTION", "854x480")
    if requested == "off" or not shutil.which("xrandr") or not env.get("DISPLAY"):
        return None
    if requested not in ("640x360", "854x480", "1024x576", "1280x720"):
        print(f"Unsupported GAMELAB_SOFTWARE_RESOLUTION={requested!r}; keeping desktop mode.",
              file=sys.stderr)
        return None
    rc, out = run(["xrandr", "--current"], env, timeout=5)
    match = re.search(r"\bcurrent (\d+) x (\d+)\b", out)
    if rc != 0 or not match:
        return None
    previous = f"{match.group(1)}x{match.group(2)}"
    if previous == requested:
        return None
    rc, out = run(["xrandr", "-s", requested], env, timeout=5)
    if rc != 0:
        print(f"Could not set {requested} desktop mode: {out[-200:]}", file=sys.stderr)
        return None
    print(f"Software desktop mode: {requested} (restore {previous} on exit)", flush=True)
    return previous


def install_dxvk(prefix):
    """Install both bitnesses without following Wine DLL symlinks."""
    root = Path("/opt/gamelab-dxvk/dxvk-2.6.2")
    for arch, subdir in (("x64", "system32"), ("x32", "syswow64")):
        destination = Path(prefix) / "drive_c/windows" / subdir
        if not destination.is_dir():
            raise RuntimeError(f"Wine prefix is incomplete: {destination}")
        for name in ("d3d9", "d3d10core", "d3d11", "dxgi"):
            target = destination / (name + ".dll")
            backup = destination / (name + ".dll.gamelab-original")
            temporary = destination / (name + ".dll.gamelab-new")
            shutil.copyfile(root / arch / target.name, temporary)
            if (target.exists() or target.is_symlink()) and not backup.exists():
                os.replace(target, backup)
            os.replace(temporary, target)


def diagnose():
    env = clean_env()
    facts = {
        "display": env.get("DISPLAY", ""),
        "nvidia_control": Path("/dev/nvidiactl").exists(),
        "nvidia_gpu": Path("/dev/nvidia0").exists(),
        "nvidia_modeset": Path("/dev/nvidia-modeset").exists(),
        "nvidia_icd": any(Path(p).exists() for p in (
            "/etc/vulkan/icd.d/nvidia_icd.json",
            "/usr/share/vulkan/icd.d/nvidia_icd.json")) or any(
                Path(p).is_file() and "nvidia" in Path(p).name.lower()
                for p in (env.get("VK_DRIVER_FILES") or env.get("VK_ICD_FILENAMES") or "").split(":") if p),
        "direct_gl": False, "virtualgl": False, "virtualgl_display": "",
        "vulkan_device": False,
        "vulkan_window": False,
        "nvidia_32bit_gl": has_32bit_library("libGLX_nvidia.so.0"),
        "vulkan_32bit_loader": has_32bit_library("libvulkan.so.1"),
        "dxvk_files": dxvk_available(),
    }
    facts["egl_device"], facts["egl_renderer"], facts["egl_device_display"] = egl_device_probe(env)
    if shutil.which("glxinfo") and env.get("DISPLAY"):
        rc, out = run(["glxinfo", "-B"], env)
        facts["direct_gl"] = rc == 0 and nvidia_renderer(out)
        facts["gl_renderer"] = next((line.strip() for line in out.splitlines()
                                     if "OpenGL renderer string:" in line), out[-240:])
        vgl = shutil.which("vglrun") or "/opt/VirtualGL/bin/vglrun"
        if Path(vgl).is_file() and facts["nvidia_control"] and facts["nvidia_gpu"]:
            candidates = [facts["egl_device_display"]] if facts["egl_device"] else ["egl0"]
            if Path("/tmp/kaggle-game-dev-bench/gpu-xorg-ready").exists():
                candidates.append(":1")
            for target in candidates:
                rc, out = run([vgl, "-d", target, "glxinfo", "-B"], env)
                if rc == 0 and nvidia_renderer(out):
                    facts["virtualgl"] = True
                    facts["virtualgl_display"] = target
                    facts["vgl_renderer"] = next((line.strip() for line in out.splitlines()
                                                   if "OpenGL renderer string:" in line), out[-240:])
                    break
    if facts["nvidia_control"] and facts["nvidia_gpu"] and shutil.which("vulkaninfo"):
        rc, out = run(["vulkaninfo", "--summary"], env)
        facts["vulkan_device"] = rc == 0 and bool(re.search(
            r"deviceName\s*=.*(?:NVIDIA|Tesla T4)", out, re.I))
        facts["vulkan_summary"] = out[-500:]
    if facts["vulkan_device"] and env.get("DISPLAY"):
        rc, out = run([sys.executable, "-m", "selkies.gpu_probe", "--vulkan-window"], env)
        facts["vulkan_window"] = rc == 0 and out.strip() == "true"
    return facts


def legendary_install_path(app):
    """Return an installed Epic title's directory from Legendary metadata."""
    home = Path(os.environ.get("KAGGLE_GAMER_HOME", "/home/gamer"))
    candidates = (
        home / ".config/heroic/legendaryConfig/legendary/installed.json",
        home / ".config/legendary/installed.json",
    )
    for installed in candidates:
        try:
            record = json.loads(installed.read_text(encoding="utf-8")).get(app, {})
            path = Path(record.get("install_path") or record.get("installPath") or "")
            if path.is_dir():
                return path
        except (OSError, ValueError, AttributeError):
            continue
    return None


def unreal_shipping_binary(app):
    """Find a UE Shipping executable while excluding prerequisite launchers."""
    install = legendary_install_path(app)
    if install is None:
        return None
    matches = []
    for path in install.rglob("*-Win64-Shipping.exe"):
        lowered = str(path).lower()
        if "prereq" not in lowered and "redist" not in lowered and "crashreport" not in lowered:
            matches.append(path)
    matches.sort(key=lambda path: ("binaries\\win64" not in str(path).lower().replace("/", "\\"), len(str(path))))
    return matches[0] if matches else None


def get_input_mode() -> str:
    """Read the active input mode (mouse_keyboard or gamepad)."""
    mode_file = Path("/tmp/kaggle-game-dev-bench/input-mode.json")
    try:
        if mode_file.is_file():
            data = json.loads(mode_file.read_text(encoding="utf-8"))
            return data.get("mode", "mouse_keyboard")
    except Exception:
        pass
    return os.environ.get("SEVEN_BZ_INPUT_MODE", "mouse_keyboard")


def configure_mouse(wine_bin, env):
    """Apply verified Wine DirectInput, X11 pointer capture, and raw sensitivity."""
    if not wine_bin:
        return
    values = (
        ("HKEY_CURRENT_USER\\Software\\Wine\\DirectInput", "MouseWarpOverride", "force"),
        ("HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver", "GrabPointer", "Y"),
        ("HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver", "UseTakeFocus", "N"),
        ("HKEY_CURRENT_USER\\Control Panel\\Mouse", "MouseSpeed", "0"),
        ("HKEY_CURRENT_USER\\Control Panel\\Mouse", "MouseThreshold1", "0"),
        ("HKEY_CURRENT_USER\\Control Panel\\Mouse", "MouseThreshold2", "0"),
        ("HKEY_CURRENT_USER\\Control Panel\\Mouse", "MouseSensitivity", "10"),
    )
    for key, name, value in values:
        try:
            subprocess.run([wine_bin, "reg", "add", key, "/v", name, "/t", "REG_SZ",
                            "/d", value, "/f"], env=env, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            pass


def select_graphics_backend(facts, preference="auto"):
    """Select only paths whose required presentation probe succeeded."""
    if preference not in ("auto", "dxvk", "wined3d"):
        raise ValueError("GAMELAB_GRAPHICS_BACKEND must be auto, dxvk, or wined3d")
    dxvk_ready = (facts["vulkan_window"] and facts["vulkan_32bit_loader"]
                  and facts["dxvk_files"])
    gl_ready = facts["nvidia_32bit_gl"]
    if preference == "dxvk":
        if not dxvk_ready:
            raise RuntimeError("DXVK requires a working Vulkan X11 swapchain, 32-bit loader, and both DLL sets")
        return "dxvk"
    if preference == "auto" and dxvk_ready:
        return "dxvk"
    if facts["direct_gl"] and gl_ready:
        return "direct_gl"
    if facts["virtualgl"] and gl_ready:
        return "virtualgl"
    if preference == "wined3d":
        raise RuntimeError("WineD3D requires verified NVIDIA GL and 32-bit GL libraries")
    return "software"


def launch(app, wine):
    facts = diagnose()
    env = clean_env()
    env["WINEPREFIX"] = os.environ.get("WINEPREFIX", "/home/gamer/.wine")
    env["WINEDLLOVERRIDES"] = "d3d11,dxgi,d3d9,d3d10core=b;mscoree,mshtml=d"
    env["SDL_AUDIODRIVER"] = "pulse"
    env["HOME"] = os.environ.get("KAGGLE_GAMER_HOME", "/home/gamer")
    env["__GL_SYNC_TO_VBLANK"] = "0"
    if not env.get("PULSE_SERVER"):
        for candidate in ("/run/user/1000/pulse/native", "/tmp/pulse-PKdhtXMmr18n/native"):
            if Path(candidate).exists():
                env["PULSE_SERVER"] = f"unix:{candidate}"
                break
        if not env.get("PULSE_SERVER"):
            try:
                found = list(Path("/tmp").glob("pulse-*/native")) + list(Path("/run/user").glob("*/pulse/native"))
                if found:
                    env["PULSE_SERVER"] = f"unix:{found[0]}"
            except Exception:
                pass

    wine_bin = wine or shutil.which("wine")
    configure_mouse(wine_bin, env)

    input_mode = get_input_mode()
    print(f"Active input mode: {input_mode}", flush=True)
    if input_mode == "mouse_keyboard":
        # Pure Mouse & Keyboard: Remove interposer and disable Wine virtual joystick
        # to prevent ghost controller conflict (locks Pitch / Yaw fighting).
        env.pop("LD_PRELOAD", None)
        env["SDL_JOYSTICK_DISABLE_UDEV"] = "1"
        env["SDL_JOYSTICK_DEVICE"] = ""
        env["WINEDLLOVERRIDES"] = env.get("WINEDLLOVERRIDES", "") + ";winebus.sys=d"
    else:
        # Gamepad Mode: Bind Xbox 360 controller sockets via interposers
        env["SELKIES_JS_SOCKET_PATH"] = "/tmp"
        env["SDL_JOYSTICK_DISABLE_UDEV"] = "1"
        env["SDL_JOYSTICK_DEVICE"] = "/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003"
        interposer = "/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so"
        env["LD_PRELOAD"] = os.environ.get("LD_PRELOAD", interposer)

    shipping = unreal_shipping_binary(app)
    launch_cwd = str(shipping.parent) if shipping else None
    command = [wine_bin, str(shipping)] if shipping and wine_bin else ["legendary", "launch", app, "--wine", wine]
    if shipping:
        print(f"Unreal Engine Shipping binary: {shipping}", flush=True)
    try:
        selected = select_graphics_backend(
            facts, os.environ.get("GAMELAB_GRAPHICS_BACKEND", "auto"))
    except (ValueError, RuntimeError) as exc:
        print(f"Graphics backend unavailable: {exc}", file=sys.stderr)
        return 78
    if selected == "dxvk":
        try:
            install_dxvk(env["WINEPREFIX"])
        except (OSError, RuntimeError) as exc:
            print(f"DXVK setup failed: {exc}", file=sys.stderr)
            return 78
        env["WINEDLLOVERRIDES"] = "d3d11,dxgi,d3d9,d3d10core=n,b;mscoree,mshtml=d"
        env["DXVK_HUD"] = "devinfo,fps"
        backend = "NVIDIA Vulkan through DXVK"
    elif selected == "direct_gl":
        backend = "NVIDIA OpenGL"
    elif selected == "virtualgl":
        display = facts["virtualgl_display"]
        backend = f"NVIDIA OpenGL through VirtualGL ({display})"
        env.update(VGL_READBACK="pbo", VGL_SPOIL="1", VGL_SYNC="0",
                   VGL_COMPRESS="proxy")
        vgl_fps = os.environ.get("GAMELAB_VGL_FPS", "60")
        try:
            if not 0 <= float(vgl_fps) <= 240:
                raise ValueError
        except ValueError:
            print("GAMELAB_VGL_FPS must be between 0 and 240", file=sys.stderr)
            return 78
        env["VGL_FPS"] = vgl_fps
        vgl = shutil.which("vglrun") or "/opt/VirtualGL/bin/vglrun"
        command = ([vgl, "-d", display, *command] if shipping else
                   ["legendary", "launch", app, "--wine", wine,
                    "--wrapper", f"{vgl} -d {display}"])
    elif os.environ.get("GAMELAB_ALLOW_SOFTWARE") == "1":
        backend = "Mesa software (explicit opt-in)"
        env["WINEDLLOVERRIDES"] = "d3d11,dxgi,d3d9,d3d10core=b;mscoree,mshtml=d"
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env["GALLIUM_DRIVER"] = "llvmpipe"
        env["LP_NUM_THREADS"] = str(software_threads())
        if shutil.which("nice"):
            command = ["nice", "-n", "5", *command]
    else:
        backend = "Mesa software (fallback)"
        env["WINEDLLOVERRIDES"] = "d3d11,dxgi,d3d9,d3d10core=b;mscoree,mshtml=d"
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env["GALLIUM_DRIVER"] = "llvmpipe"
        env["LP_NUM_THREADS"] = str(software_threads())
        if shutil.which("nice"):
            command = ["nice", "-n", "5", *command]
    print(f"Rendering backend: {backend}", flush=True)
    if backend.startswith("Mesa software"):
        print(f"llvmpipe worker threads: {env['LP_NUM_THREADS']}", flush=True)
        previous_resolution = lower_software_resolution(env)
        try:
            return subprocess.call(command, env=env, cwd=launch_cwd)
        finally:
            if previous_resolution:
                run(["xrandr", "-s", previous_resolution], env, timeout=5)
    return subprocess.call(command, env=env, cwd=launch_cwd)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "diagnose":
        print(json.dumps(diagnose(), indent=2))
    elif len(sys.argv) == 4 and sys.argv[1] == "launch":
        sys.exit(launch(sys.argv[2], sys.argv[3]))
    else:
        print("Usage: gpu_runtime.py diagnose | launch APP WINE_BIN", file=sys.stderr)
        sys.exit(2)
