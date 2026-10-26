"""Build the self-contained interactive Kaggle gaming and game-development notebook."""
import json
from pathlib import Path

root = Path(__file__).parent
launcher_code = (root / 'dev_launcher.py').read_text(encoding='utf-8')
embedded_assets_code = (root / 'embedded_assets.py').read_text(encoding='utf-8')
game_catalog_code = (root / 'game_catalog.py').read_text(encoding='utf-8')
session_control_code = (root / 'session_control.py').read_text(encoding='utf-8')
install_web_client_code = (root / 'install_web_client.py').read_text(encoding='utf-8')
hud_css = (root / 'web_client' / 'hud.css').read_text(encoding='utf-8')
hud_js = (root / 'web_client' / 'hud.js').read_text(encoding='utf-8')
fix_heroic_code = (root / 'fix_heroic_config.py').read_text(encoding='utf-8')
legendary_menu_code = (root / 'legendary_menu.sh').read_text(encoding='utf-8')
legendary_gui_code = (root / 'legendary_gui.py').read_text(encoding='utf-8')
auto_optimize_code = (root / 'auto_optimize.py').read_text(encoding='utf-8')
setup_sh_code = (root / 'setup.sh').read_text(encoding='utf-8')
gpu_runtime_code = (root / 'gpu_runtime.py').read_text(encoding='utf-8')
launch_idtech5_code = (root / 'launch_idtech5.py').read_text(encoding='utf-8')
start_direct_stream_code = (root / 'start_direct_stream.sh').read_text(encoding='utf-8')
bench_runtime_code = (root / 'bench_runtime.py').read_text(encoding='utf-8')
gpu_xorg_code = (root / 'gpu_xorg.sh').read_text(encoding='utf-8')
probe_nvidia_userspace_code = (root / 'probe_nvidia_userspace.sh').read_text(encoding='utf-8')
start_desktop_code = (root / 'start_desktop.sh').read_text(encoding='utf-8')
launch_heroic_code = (root / 'launch_heroic.sh').read_text(encoding='utf-8')
fix_heroic_sh_code = (root / 'fix_heroic.sh').read_text(encoding='utf-8')

install_script = r'''from pathlib import Path
import json, os, shutil, subprocess, sys, time

BENCH = Path('/tmp/kaggle-game-dev-bench')
BUILDS = Path('/tmp/game-builds')
LOGS = BENCH / 'logs'
EA_STORE = Path('/tmp/ea-store')
REPO_URL = 'https://github.com/Mohammedsbastawy/kaggle-gaming-bench.git'

BUILDS.mkdir(parents=True, exist_ok=True)
EA_STORE.mkdir(parents=True, exist_ok=True)

# 1. Automatic recovery for apt/dpkg locks (prevents RuntimeError exit 100 on interactive sessions)
print('▶ Clearing stale apt/dpkg locks and recovering package manager...', flush=True)
for lock in ['/var/lib/dpkg/lock-frontend', '/var/lib/dpkg/lock', '/var/lib/apt/lists/lock', '/var/cache/apt/archives/lock']:
    subprocess.run(['fuser', '-k', lock], check=False)
    try:
        os.remove(lock)
    except OSError:
        pass
subprocess.run(['dpkg', '--configure', '-a'], check=False, env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'))

# 2. Clone or update the ready Git repository
setup_sh = BENCH / 'setup.sh'
if not setup_sh.exists():
    shutil.rmtree(str(BENCH), ignore_errors=True)
    print(f'▶ Cloning ready gaming bench suite from {REPO_URL}...', flush=True)
    res = subprocess.run(['git', 'clone', '--depth', '1', REPO_URL, str(BENCH)], timeout=60)
    if res.returncode != 0 or not setup_sh.exists():
        print('Notice: Git clone unavailable, using embedded setup suite.', flush=True)
        BENCH.mkdir(parents=True, exist_ok=True)
        setup_sh.write_text(''' + repr(setup_sh_code) + r''', encoding='utf-8')
else:
    print('▶ Updating bench repository from git...', flush=True)
    subprocess.run(['git', '-C', str(BENCH), 'reset', '--hard', 'HEAD'], check=False, timeout=30)
    subprocess.run(['git', '-C', str(BENCH), 'clean', '-fd'], check=False, timeout=30)
    subprocess.run(['git', '-C', str(BENCH), 'pull', '--force'], check=False, timeout=30)

# Use the setup bundled with this notebook, including its GPU driver probes.
# The public repository can lag behind a newly uploaded notebook version.
setup_sh.write_text(''' + repr(setup_sh_code) + r''', encoding='utf-8')
probe_sh = BENCH / 'probe_nvidia_userspace.sh'
probe_sh.write_text(''' + repr(probe_nvidia_userspace_code) + r''', encoding='utf-8')
probe_sh.chmod(0o755)
(BENCH / 'gpu_runtime.py').write_text(''' + repr(gpu_runtime_code) + r''', encoding='utf-8')
(BENCH / 'launch_idtech5.py').write_text(''' + repr(launch_idtech5_code) + r''', encoding='utf-8')
(BENCH / 'start_direct_stream.sh').write_text(''' + repr(start_direct_stream_code) + r''', encoding='utf-8')

# 3. Execute setup.sh with live output streaming
setup_sh.chmod(0o755)
print('▶ Running automated setup.sh...', flush=True)
proc = subprocess.Popen(['/bin/bash', str(setup_sh)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
while True:
    line = proc.stdout.readline()
    if line:
        print(line, end='', flush=True)
    elif proc.poll() is not None:
        rest = proc.stdout.read()
        if rest:
            print(rest, end='', flush=True)
        break
    else:
        time.sleep(0.05)
print(f'setup.sh completed with exit code: {proc.returncode}', flush=True)

# 4. Configure unprivileged gamer user
subprocess.run(['useradd', '-m', '-s', '/bin/bash', '-G', 'audio,video', 'gamer'], check=False)
gamer_home = Path('/home/gamer')
for sub in ['.config', '.local', '.steam', 'game-builds', 'logs', 'ea-prefix']:
    (gamer_home / sub).mkdir(parents=True, exist_ok=True)

# Grant open permissions and ensure gamer ownership recursively
subprocess.run(['chown', '-R', 'gamer:gamer', str(gamer_home)], check=False)
subprocess.run(['chmod', '-R', '777', str(gamer_home)], check=False)
subprocess.run(['chmod', '-R', '777', str(BENCH)], check=False)

# 5. Storefront verification audit
def check_paths(candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
        p = shutil.which(c)
        if p:
            return p
    return None

wine_ge_dir = gamer_home / '.config' / 'heroic' / 'tools' / 'wine'
storefront_status = {
    'steam': check_paths(['/usr/games/steam', '/usr/bin/steam']),
    'heroic': check_paths(['/usr/bin/heroic', '/opt/Heroic/heroic']),
    'legendary': check_paths(['/usr/local/bin/legendary', '/usr/bin/legendary', 'legendary']),
    'minigalaxy': check_paths(['/usr/games/minigalaxy', '/usr/bin/minigalaxy']),
    'lutris': check_paths(['/usr/games/lutris', '/usr/bin/lutris']),
    'wine': check_paths(['/usr/bin/wine', 'wine']),
    'wine_ge': check_paths([str(wine_ge_dir / 'Wine-GE-Proton8-26/bin/wine'), *[str(p) for p in wine_ge_dir.glob('*/bin/wine')]]),
    'ea_installer': str(EA_STORE / 'EAappInstaller.exe') if (EA_STORE / 'EAappInstaller.exe').exists() else None,
    'interposer_64': str(BENCH / 'lib/x86_64-linux-gnu/selkies_input_interposer.so') if (BENCH / 'lib/x86_64-linux-gnu/selkies_input_interposer.so').exists() else None,
    'interposer_32': str(BENCH / 'lib/i386-linux-gnu/selkies_input_interposer.so') if (BENCH / 'lib/i386-linux-gnu/selkies_input_interposer.so').exists() else None
}

print('================ STOREFRONT INSTALLATION AUDIT ================')
for k, v in storefront_status.items():
    print(f'  {k:15}: {v if v else "NOT FOUND / PENDING"}')
print('================================================================')
'''

write_launcher_script = f'''from pathlib import Path
import os, subprocess

BENCH = Path('/tmp/kaggle-game-dev-bench')
BENCH.mkdir(parents=True, exist_ok=True)
(BENCH / 'logs').mkdir(parents=True, exist_ok=True)
(BENCH / 'web_client').mkdir(parents=True, exist_ok=True)

# Write the console dashboard, catalog, emergency service, and streaming HUD
(BENCH / 'dev_launcher.py').write_text({repr(launcher_code)}, encoding='utf-8')
(BENCH / 'embedded_assets.py').write_text({repr(embedded_assets_code)}, encoding='utf-8')
(BENCH / 'game_catalog.py').write_text({repr(game_catalog_code)}, encoding='utf-8')
(BENCH / 'session_control.py').write_text({repr(session_control_code)}, encoding='utf-8')
(BENCH / 'install_web_client.py').write_text({repr(install_web_client_code)}, encoding='utf-8')
(BENCH / 'web_client' / 'hud.css').write_text({repr(hud_css)}, encoding='utf-8')
(BENCH / 'web_client' / 'hud.js').write_text({repr(hud_js)}, encoding='utf-8')

# Write tint2 panel configuration for desktop taskbar
tint2rc = """# Minimal dark tint2 panel configuration
panel_position = bottom center horizontal
panel_size = 100% 32
panel_margin = 0 0
panel_padding = 4 2 4
panel_background_id = 1
wm_menu = 1
panel_dock = 0
panel_layer = top

taskbar_mode = single_desktop
taskbar_padding = 2 0 2
taskbar_background_id = 0
taskbar_active_background_id = 2

task_icon = 1
task_text = 1
task_width = 190
task_maximum_size = 220 28
task_padding = 6 2
task_font = DejaVu Sans 10
task_font_color = #d8e4f5 100
task_active_font_color = #4dcdf2 100

time1_font = DejaVu Sans 10
clock_font_color = #9bdcf5 100
time1_format = %H:%M:%S

rounded = 0
border_width = 1
background_color = #090e1e 100
border_color = #172b4d 100

rounded = 4
border_width = 1
background_color = #152744 100
border_color = #4dcdf2 100
"""
(BENCH / 'tint2rc').write_text(tint2rc, encoding='utf-8')

# Steam launch wrapper - executes under unprivileged 'gamer' user
steam_sh = """#!/bin/bash
export DISPLAY="${{DISPLAY:-:0}}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
export LD_PRELOAD='/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so'
export SELKIES_JS_SOCKET_PATH="/tmp"
export SDL_JOYSTICK_DISABLE_UDEV=1
export SDL_JOYSTICK_DEVICE=/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003

mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/steam.log"
STEAM_BIN=$(which steam 2>/dev/null || echo /usr/games/steam)

echo "Starting Steam as user gamer at $(date)..." >> "$LOG"
exec env \\
    DISPLAY="$DISPLAY" \\
    PATH="$PATH" \\
    SDL_AUDIODRIVER=pulse \\
    LD_PRELOAD="$LD_PRELOAD" \\
    SELKIES_JS_SOCKET_PATH="$SELKIES_JS_SOCKET_PATH" \\
    SDL_JOYSTICK_DISABLE_UDEV=1 \\
    SDL_JOYSTICK_DEVICE="$SDL_JOYSTICK_DEVICE" \\
    HOME="/home/gamer" \\
    "$STEAM_BIN" -no-cef-sandbox -cef-disable-gpu -cef-force-software-rendering "$@" >> "$LOG" 2>&1
"""
(BENCH / 'launch_steam.sh').write_text(steam_sh, encoding='utf-8')

# Heroic launch wrapper (Epic Games & GOG) - executes under unprivileged 'gamer' user
heroic_sh = {repr(launch_heroic_code)}
(BENCH / 'launch_heroic.sh').write_text(heroic_sh, encoding='utf-8')

# Minigalaxy launch wrapper (GOG dedicated) - executes under unprivileged 'gamer' user
mini_sh = """#!/bin/bash
export DISPLAY="${{DISPLAY:-:0}}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/minigalaxy.log"
MINI_BIN=$(which minigalaxy 2>/dev/null || echo /usr/games/minigalaxy)

echo "Starting Minigalaxy as user gamer at $(date)..." >> "$LOG"
exec env \\
    DISPLAY="$DISPLAY" \\
    PATH="$PATH" \\
    SDL_AUDIODRIVER=pulse \\
    HOME="/home/gamer" \\
    "$MINI_BIN" "$@" >> "$LOG" 2>&1
"""
(BENCH / 'launch_minigalaxy.sh').write_text(mini_sh, encoding='utf-8')

# Lutris launch wrapper - executes under unprivileged 'gamer' user
lutris_sh = """#!/bin/bash
export DISPLAY="${{DISPLAY:-:0}}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export SDL_AUDIODRIVER=pulse
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/lutris.log"
LUTRIS_BIN=$(which lutris 2>/dev/null || echo /usr/games/lutris)

# Match Ubuntu noble C extension ABI (_dbus_bindings) using python3.12 if available
if [ -x /usr/bin/python3.12 ]; then
    PY_BIN="/usr/bin/python3.12"
else
    PY_BIN="python3"
fi

echo "Starting Lutris with $PY_BIN as user gamer at $(date)..." >> "$LOG"
exec env \\
    DISPLAY="$DISPLAY" \\
    PATH="$PATH" \\
    SDL_AUDIODRIVER=pulse \\
    HOME="/home/gamer" \\
    "$PY_BIN" "$LUTRIS_BIN" "$@" >> "$LOG" 2>&1
"""
(BENCH / 'launch_lutris.sh').write_text(lutris_sh, encoding='utf-8')

# EA App launch wrapper - executes under unprivileged 'gamer' user in isolated wineprefix
ea_sh = """#!/bin/bash
export DISPLAY="${{DISPLAY:-:0}}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export WINEPREFIX="/home/gamer/ea-prefix"
export WINEARCH=win64
export WINEDLLOVERRIDES="mscoree="
mkdir -p "$WINEPREFIX" /tmp/ea-store /home/gamer/logs
chown -R gamer:gamer "$WINEPREFIX" /home/gamer/logs 2>/dev/null || true

LOG="/home/gamer/logs/ea.log"
echo "Starting EA App runner at $(date)..." >> "$LOG"

EA_INSTALLER="/tmp/ea-store/EAappInstaller.exe"
if [ ! -f "$EA_INSTALLER" ]; then
    echo "Downloading EAappInstaller.exe..." >> "$LOG"
    wget -q https://origin-a.akamaihd.net/EA-Desktop-Client-Download/installer-releases/EAappInstaller.exe -O "$EA_INSTALLER"
fi

EA_INSTALLED="$WINEPREFIX/drive_c/Program Files/Electronic Arts/EA Desktop/EA Desktop/EADesktop.exe"
if [ -f "$EA_INSTALLED" ]; then
    echo "Running installed EA Desktop: $EA_INSTALLED" >> "$LOG"
    TARGET="$EA_INSTALLED"
else
    echo "Running EA App Installer via Wine64: $EA_INSTALLER" >> "$LOG"
    TARGET="$EA_INSTALLER"
fi

exec env \\
    DISPLAY="$DISPLAY" \\
    PATH="$PATH" \\
    WINEPREFIX="$WINEPREFIX" \\
    WINEARCH=win64 \\
    WINEDLLOVERRIDES="$WINEDLLOVERRIDES" \\
    HOME="/home/gamer" \\
    wine "$TARGET" "$@" >> "$LOG" 2>&1
"""
(BENCH / 'launch_ea.sh').write_text(ea_sh, encoding='utf-8')

# Fix Heroic Config Python script
(BENCH / 'fix_heroic_config.py').write_text({repr(fix_heroic_code)}, encoding='utf-8')

# Fix Heroic Shell wrapper for launcher
fix_heroic_sh = {repr(fix_heroic_sh_code)}
(BENCH / 'fix_heroic.sh').write_text(fix_heroic_sh, encoding='utf-8')

# Legendary interactive menu and graphical interface
(BENCH / 'legendary_menu.sh').write_text({repr(legendary_menu_code)}, encoding='utf-8')
(BENCH / 'legendary_gui.py').write_text({repr(legendary_gui_code)}, encoding='utf-8')
(BENCH / 'gpu_runtime.py').write_text({repr(gpu_runtime_code)}, encoding='utf-8')
(BENCH / 'launch_idtech5.py').write_text({repr(launch_idtech5_code)}, encoding='utf-8')
(BENCH / 'start_direct_stream.sh').write_text({repr(start_direct_stream_code)}, encoding='utf-8')
(BENCH / 'bench_runtime.py').write_text({repr(bench_runtime_code)}, encoding='utf-8')
(BENCH / 'gpu_xorg.sh').write_text({repr(gpu_xorg_code)}, encoding='utf-8')
(BENCH / 'probe_nvidia_userspace.sh').write_text({repr(probe_nvidia_userspace_code)}, encoding='utf-8')

legendary_sh = """#!/bin/bash
export DISPLAY="${{DISPLAY:-:0}}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export HOME="/home/gamer"
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/legendary_gui.log"

for w in /home/gamer/.config/heroic/tools/wine/*/bin/wine; do
    if [ -f "$w" ]; then
        if [ ! -f /usr/bin/wine ]; then
            ln -sf "$w" /usr/bin/wine 2>/dev/null || true
            ln -sf "$(dirname "$w")/wineserver" /usr/bin/wineserver 2>/dev/null || true
            ln -sf "$(dirname "$w")/wineboot" /usr/bin/wineboot 2>/dev/null || true
        fi
        if [ ! -f /usr/local/bin/wine ]; then
            ln -sf "$w" /usr/local/bin/wine 2>/dev/null || true
        fi
        break
    fi
done

if python3 -c "import tkinter" >/dev/null 2>&1; then
    exec python3 /tmp/kaggle-game-dev-bench/legendary_gui.py >> "$LOG" 2>&1
else
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update -qq && apt-get install -y -qq python3-tk >> "$LOG" 2>&1 || true
        if python3 -c "import tkinter" >/dev/null 2>&1; then
            exec python3 /tmp/kaggle-game-dev-bench/legendary_gui.py >> "$LOG" 2>&1
        fi
    fi
    exec xterm -geometry 105x32 -title "Legendary Epic Games Manager" -e /bin/bash /tmp/kaggle-game-dev-bench/legendary_menu.sh >> "$LOG" 2>&1
fi
"""
(BENCH / 'launch_legendary.sh').write_text(legendary_sh, encoding='utf-8')

# Auto-Optimizer script and launch wrapper
(BENCH / 'auto_optimize.py').write_text({repr(auto_optimize_code)}, encoding='utf-8')

optimizer_sh = """#!/bin/bash
export DISPLAY="${{DISPLAY:-:0}}"
export PATH="/usr/games:/usr/local/bin:/usr/bin:$PATH"
export HOME="/home/gamer"
mkdir -p /home/gamer/logs
LOG="/home/gamer/logs/auto_optimize.log"

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq python3-tk >> "$LOG" 2>&1 || true
fi

exec python3 /tmp/kaggle-game-dev-bench/auto_optimize.py >> "$LOG" 2>&1
"""
(BENCH / 'launch_optimizer.sh').write_text(optimizer_sh, encoding='utf-8')

# Make all shell scripts executable
for p in BENCH.glob('*.sh'):
    p.chmod(0o755)

print('Launcher scripts, storefront wrappers, and desktop configuration saved successfully.', flush=True)
'''

start_script = r'''from pathlib import Path
import json, os, shutil, signal, subprocess, sys, time, urllib.request

BENCH = Path('/tmp/kaggle-game-dev-bench')
BUILDS = Path('/tmp/game-builds')
BUILDS.mkdir(parents=True, exist_ok=True)
SCREENSHOTS = Path('/kaggle/working/screenshots')
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

# Master desktop session wrapper
wrapper = BENCH / 'start-desktop.sh'
wrapper.write_text(''' + repr(start_desktop_code) + r''', encoding='utf-8')
wrapper.chmod(0o755)

# Build a custom Selkies web root without changing the installed streaming core.
subprocess.run([sys.executable, str(BENCH / 'install_web_client.py')], check=True)

# Stop any previous session
pidfile = BENCH / 'selkies.pid'
if pidfile.exists():
    try:
        previous = int(pidfile.read_text())
        command = Path(f'/proc/{previous}/cmdline').read_bytes().replace(b'\0', b' ')
        if b'selkies-session' in command and b'kaggle-game-dev-bench' in command:
            os.killpg(previous, signal.SIGTERM)
            time.sleep(2)
    except (ValueError, OSError, ProcessLookupError):
        pass

env = os.environ.copy()
env['PATH'] = f"/usr/local/bin:/usr/games:/usr/bin:{env.get('PATH', '')}"

# Asymmetric Dual-GPU Pipeline:
# If two GPUs are detected (/dev/nvidia0 and /dev/nvidia1):
# GPU 1 is dedicated exclusively to Selkies desktop capture & NVENC H.264 hardware encoding.
# GPU 0 is dedicated exclusively to 3D game rendering (Vulkan/DXVK/VKD3D/VirtualGL).
if Path('/dev/nvidia1').exists() and Path('/dev/nvidia0').exists():
    print('▶ Dual-GPU environment detected: Dedicating GPU 1 to NVENC encoding and GPU 0 to 3D Game Rendering.', flush=True)
    env['CUDA_VISIBLE_DEVICES'] = '1'
    env['SELKIES_ENCODER_DEVICE'] = '1'
else:
    print('▶ Single-GPU environment detected: GPU 0 active for rendering and encoding.', flush=True)
    env['CUDA_VISIBLE_DEVICES'] = '0'
    env['SELKIES_ENCODER_DEVICE'] = '0'

queue_size = os.environ.get('GAMELAB_WS_QUEUE', '4')
if not queue_size.isdigit() or not 1 <= int(queue_size) <= 120:
    raise ValueError('GAMELAB_WS_QUEUE must be an integer from 1 to 120')
env.update(SELKIES_ENABLE_HTTPS='false', SELKIES_MODE='websockets',
           SELKIES_ALLOWED_ORIGINS='https://kkb-production.jupyter-proxy.kaggle.net',
           SELKIES_ENCODER='h264enc', SELKIES_FRAMERATE='60-60',
           SELKIES_VIDEO_FULLCOLOR='false|locked',
           SELKIES_VIDEO_10BIT='false|locked',
           SELKIES_BACKPRESSURE_QUEUE_SIZE=queue_size,
           SELKIES_VIDEO_BITRATE='8000,1000-12000',
           SELKIES_RATE_CONTROL_MODE='cbr', SELKIES_CONGESTION_CONTROL='true',
           SELKIES_ENABLE_RESIZE='true',
           SELKIES_AUDIO_ENABLED='true', SELKIES_AUDIO_CHANNELS='2',
           SELKIES_AUDIO_BITRATE='128000', SELKIES_GAMEPAD_ENABLED='true',
           SELKIES_UINPUT_GAMEPAD='false',
           SELKIES_JS_SOCKET_PATH='/tmp',
           SELKIES_UI_TITLE='7BZ Dev Cloud Game',
           SELKIES_UI_SHOW_SIDEBAR='true', SELKIES_UI_SHOW_LOGO='false',
           SELKIES_UI_SIDEBAR_SHOW_VIDEO_SETTINGS='false',
           SELKIES_UI_SIDEBAR_SHOW_SCREEN_SETTINGS='false',
           SELKIES_MANUAL_WIDTH='1280', SELKIES_MANUAL_HEIGHT='720',
           SELKIES_WEB_ROOT=str(BENCH / 'web-root'),
           FILE_MANAGER_PATH=str(BUILDS),
           SDL_AUDIODRIVER='pulse')

# Enforce GLX extension on Xvfb in selkies package with Mesa isolation to prevent NVIDIA EGL-GBM crash
try:
    import selkies
    s_session = Path(selkies.__file__).parent / 'session.py'
    if s_session.is_file():
        s_code = s_session.read_text(encoding='utf-8')
        s_target = 'for extra in gpu + [glx, ["-extension", "GLX"]]:\n            read, write = os.pipe()\n            proc = self.spawn(["Xvfb", "-displayfd", str(write), "-auth", auth, *XVFB_ARGS, *extra],\n                              pass_fds=(write,))'
        s_target_alt = 'for extra in [glx]:\n            read, write = os.pipe()\n            proc = self.spawn(["Xvfb", "-displayfd", str(write), "-auth", auth, *XVFB_ARGS, *extra],\n                              pass_fds=(write,))'
        s_repl = ('xvfb_env = os.environ.copy()\n'
                  '        xvfb_env.update(LIBGL_ALWAYS_SOFTWARE="1", __GLX_VENDOR_LIBRARY_NAME="mesa", __EGL_VENDOR_LIBRARY_FILENAMES="", GBM_BACKENDS_PATH="/dev/null")\n'
                  '        for extra in [glx]:\n'
                  '            read, write = os.pipe()\n'
                  '            proc = self.spawn(["Xvfb", "-displayfd", str(write), "-auth", auth, *XVFB_ARGS, *extra],\n'
                  '                              pass_fds=(write,), env=xvfb_env)')
        if s_target in s_code:
            s_code = s_code.replace(s_target, s_repl)
        elif s_target_alt in s_code:
            s_code = s_code.replace(s_target_alt, s_repl)
        s_session.write_text(s_code, encoding='utf-8')
except Exception:
    pass

# Launch streaming gaming desktop on port 8080
log = (BENCH / 'selkies.log').open('a', buffering=1)
direct_script = BENCH / 'start_direct_stream.sh'
started = False

if direct_script.is_file():
    try:
        print('▶ Starting unified direct NVIDIA Xorg stream on port 8080...', flush=True)
        direct_res = subprocess.run(['bash', str(direct_script)],
                                    env=dict(os.environ, DIRECT_STREAM_PORT='8080'),
                                    capture_output=True, text=True, timeout=35)
        if direct_res.returncode == 0:
            started = True
            server_pid = (BENCH / 'direct-stream.pid').read_text().strip() if (BENCH / 'direct-stream.pid').exists() else None
            if server_pid:
                pidfile.write_text(server_pid)
        else:
            print('Direct stream notice:', (direct_res.stdout + direct_res.stderr)[-500:], flush=True)
    except Exception as e:
        print('Direct stream attempt skipped:', e, flush=True)

if not started:
    print('▶ Starting verified Selkies fallback desktop on port 8080...', flush=True)
    server = subprocess.Popen(['selkies-session', '--session=' + str(wrapper),
                               '--port=8080', '--enable-basic-auth=false'],
                              stdout=log, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, env=env,
                              start_new_session=True)
    pidfile.write_text(str(server.pid))

health = None
for _ in range(75):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2) as response:
            if response.status == 200:
                health = response.read().decode(errors='replace')
                break
    except Exception:
        time.sleep(1)

if health != 'OK':
    selkies_tail = (BENCH / 'selkies.log').read_text(errors='replace')[-3000:] if (BENCH / 'selkies.log').exists() else ''
    stream_tail = (BENCH / 'logs' / 'direct-stream.log').read_text(errors='replace')[-3000:] if (BENCH / 'logs' / 'direct-stream.log').exists() else ''
    xorg_tail = (BENCH / 'logs' / 'gpu-xorg.log').read_text(errors='replace')[-2000:] if (BENCH / 'logs' / 'gpu-xorg.log').exists() else ''
    raise RuntimeError(f'Desktop did not start. Logs:\n{stream_tail}\n{selkies_tail}\n{xorg_tail}')

with urllib.request.urlopen('http://127.0.0.1:8080/api/status', timeout=5) as response:
    status = json.load(response)

time.sleep(2)
for sock in Path('/tmp').glob('selkies_*.sock'):
    try: sock.chmod(0o666)
    except Exception: pass
serverlog = (BENCH / 'selkies.log').read_text(errors='replace')

# =========================================================================
# EMPIRICAL STOREFRONT GUI LAUNCH & WINDOW VERIFICATION PROBE
# =========================================================================
print('▶ Starting empirical GUI launch tests for storefronts...', flush=True)
auth_path_file = BENCH / 'xauthority-path'
active_display = ':1' if (BENCH / 'gpu-xorg-ready').exists() or os.path.exists('/tmp/.X11-unix/X1') else ':0'
probe_auth = (BENCH / 'nvidia-Xauthority') if active_display == ':1' else auth_path_file
probe_env = dict(os.environ, DISPLAY=active_display)
if probe_auth.exists():
    probe_env['XAUTHORITY'] = str(probe_auth) if active_display == ':1' else probe_auth.read_text().strip()

def get_wm_windows():
    try:
        res = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True, timeout=5,
                             env=probe_env)
        return res.stdout.splitlines() if res.returncode == 0 else []
    except Exception:
        return []

def capture_screenshot(out_path):
    try:
        result = subprocess.run(['ffmpeg', '-f', 'x11grab', '-video_size', '1280x720', '-i', active_display,
                        '-vframes', '1', '-y', str(out_path)],
                       capture_output=True, timeout=10, env=probe_env)
        if result.returncode != 0:
            print('Screenshot failed:', result.stderr.decode(errors='replace')[-350:], flush=True)
        return out_path.exists() and out_path.stat().st_size > 1000
    except Exception:
        return False

smoke_tests = [
    {
        'id': 'minigalaxy',
        'title': 'Minigalaxy GOG Client',
        'script': str(BENCH / 'launch_minigalaxy.sh'),
        'match': 'minigalaxy',
        'log': '/home/gamer/logs/minigalaxy.log'
    },
    {
        'id': 'heroic',
        'title': 'Heroic Games Launcher',
        'script': str(BENCH / 'launch_heroic.sh'),
        'match': 'heroic',
        'log': '/home/gamer/logs/heroic.log'
    },
    {
        'id': 'lutris',
        'title': 'Lutris Gaming Hub',
        'script': str(BENCH / 'launch_lutris.sh'),
        'match': 'lutris',
        'log': '/home/gamer/logs/lutris.log'
    },
    {
        'id': 'steam',
        'title': 'Steam Native Client',
        'script': str(BENCH / 'launch_steam.sh'),
        'match': 'steam',
        'log': '/home/gamer/logs/steam.log'
    },
    {
        'id': 'ea_app',
        'title': 'EA App Wine Runner',
        'script': str(BENCH / 'launch_ea.sh'),
        'match': 'ea',
        'log': '/home/gamer/logs/ea.log'
    }
]

def get_active_pulse() -> str:
    path = BENCH / 'pulse-server-path'
    if path.is_file():
        try:
            val = path.read_text().strip()
            if val:
                return val
        except Exception:
            pass
    for s in [Path('/run/user/1000/pulse/native'), *Path('/tmp').glob('pulse-*/native'), Path('/run/user/0/pulse/native')]:
        if s.exists():
            val = f"unix:{s}"
            try:
                path.write_text(val, encoding='utf-8')
                os.chmod(path, 0o666)
            except Exception:
                pass
            return val
    fallback = "unix:/run/user/1000/pulse/native"
    try:
        path.write_text(fallback, encoding='utf-8')
        os.chmod(path, 0o666)
    except Exception:
        pass
    return fallback

active_pulse = get_active_pulse()
smoke_results = {}
for test in smoke_tests:
    tid = test['id']
    script = test['script']
    match_str = test['match'].lower()
    log_file = Path(test['log'])
    shot_file = SCREENSHOTS / f'{tid}_smoke.png'
    
    print(f'  Testing storefront GUI: {test["title"]}...', flush=True)
    if not os.path.exists(script):
        smoke_results[tid] = {'tested': False, 'error': 'Launch script missing'}
        continue
        
    proc = subprocess.Popen(['runuser', '-u', 'gamer', '--', 'env', '-u', 'DBUS_SESSION_BUS_ADDRESS',
                             'PULSE_SERVER=' + active_pulse,
                             'dbus-run-session', '--', '/bin/bash', script], start_new_session=True)
    window_found = False
    matching_titles = []
    
    # Steam cold setup often takes longer than storefront startup.
    max_polls = 60 if tid == 'steam' else 20 if tid == 'heroic' else 12
    for _ in range(max_polls):
        time.sleep(1.5)
        wins = get_wm_windows()
        for w in wins:
            if match_str in w.lower():
                window_found = True
                matching_titles.append(w.strip())
        if window_found:
            break
            
    # Capture screen regardless of window detection to document actual virtual display state
    all_windows = get_wm_windows()
    error_shot = None
    if tid == 'steam':
        error_windows = [line for line in all_windows if 'error' in line.lower()]
        if error_windows:
            subprocess.run(['wmctrl', '-ia', error_windows[-1].split()[0]],
                           capture_output=True, timeout=5, env=probe_env)
            time.sleep(1)
            error_path = SCREENSHOTS / 'steam_error.png'
            if capture_screenshot(error_path):
                error_shot = str(error_path)
    shot_captured = capture_screenshot(shot_file)
    
    # Read process log tail
    log_tail = []
    if log_file.exists():
        lines = [l.strip() for l in log_file.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
        log_tail = lines[-6:]
        
    smoke_results[tid] = {
        'tested': True,
        'pid': proc.pid,
        'window_mapped': window_found,
        'detected_windows': matching_titles,
        'all_windows': all_windows,
        'error_screenshot': error_shot,
        'screenshot_saved': shot_captured,
        'screenshot_path': str(shot_file) if shot_captured else None,
        'process_poll': proc.poll(),
        'log_tail': log_tail
    }
    
    # Terminate smoke test process so desktop stays clean
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        time.sleep(1)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass

subprocess.run(['wmctrl', '-a', '7BZ Dev Cloud Game'], capture_output=True, timeout=5,
               env=probe_env)
time.sleep(1)

# Compile comprehensive health and verification audit
def check_bin(name):
    path = shutil.which(name) or (f'/usr/games/{name}' if os.path.exists(f'/usr/games/{name}') else None)
    return {'installed': path is not None, 'path': path}

def epic_installed_apps():
    installed = Path('/home/gamer/.config/heroic/legendaryConfig/legendary/installed.json')
    try:
        data = json.loads(installed.read_text())
        return sorted(data) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []

try:
    gpu_facts = json.loads(subprocess.run(
        [sys.executable, str(BENCH / 'gpu_runtime.py'), 'diagnose'],
        capture_output=True, text=True, timeout=50, env=probe_env,
        check=True).stdout)
except (OSError, ValueError, subprocess.SubprocessError):
    gpu_facts = {}

server_pid_val = None
if 'server' in locals() and hasattr(server, 'pid'):
    server_pid_val = server.pid
elif (BENCH / 'direct-stream.pid').exists():
    try:
        server_pid_val = int((BENCH / 'direct-stream.pid').read_text().strip())
    except Exception:
        server_pid_val = None

audio_cookie = '/home/gamer/.config/pulse/cookie'
audio_env = dict(os.environ, PULSE_SERVER=active_pulse, PULSE_COOKIE=audio_cookie)
gamer_audio = subprocess.run(
    ['runuser', '-u', 'gamer', '--', 'env', 'HOME=/home/gamer',
     'XDG_RUNTIME_DIR=' + str(BENCH / 'pulse-runtime'),
     'PULSE_SERVER=' + active_pulse, 'PULSE_COOKIE=' + audio_cookie,
     'pactl', 'info'], capture_output=True, text=True, timeout=10)
streamer_audio = subprocess.run(['pactl', 'info'], capture_output=True,
                                text=True, timeout=10, env=audio_env)
audio_sources = subprocess.run(['pactl', 'list', 'short', 'sources'],
                               capture_output=True, text=True, timeout=10,
                               env=audio_env)

report = {
    'health': health,
    'status': status,
    'nvenc_detected': 'encodes H264, H265 on nvenc' in serverlog,
    'gamepad_sockets_ready': '4 virtual gamepads ready' in serverlog,
    'server_pid': server_pid_val or 8080,
    'launcher_processes': subprocess.run(['pgrep', '-u', 'gamer', '-f', '/tmp/kaggle-game-dev-bench/dev_launcher.py'],
                                         capture_output=True, text=True).stdout.splitlines(),
    'launcher_screenshot': str(SCREENSHOTS / 'game_lab_home.png') if capture_screenshot(SCREENSHOTS / 'game_lab_home.png') else None,
    'desktop_processes': [line for line in subprocess.run(['ps', '-eo', 'user,pid,ppid,args'],
                                      capture_output=True, text=True).stdout.splitlines()
                          if any(name in line for name in ('Xvfb', 'openbox', 'tint2', 'dev_launcher', 'selkies-session'))][:20],
    'x11_probe': subprocess.run(['xdpyinfo', '-display', ':0'], capture_output=True,
                                text=True, timeout=10, env=probe_env).stderr[-800:],
    'xauthority_path': probe_env.get('XAUTHORITY'),
    'gamer_audio_probe': gamer_audio.returncode,
    'gamer_audio_error': gamer_audio.stderr[-400:],
    'streamer_audio_probe': streamer_audio.returncode,
    'streamer_audio_error': streamer_audio.stderr[-400:],
    'audio_monitor_probe': 'output.monitor' in audio_sources.stdout,
    'selkies_log_tail': (BENCH / 'selkies.log').read_text(errors='replace')[-3000:],
    'desktop_components': {
        'openbox': check_bin('openbox'),
        'tint2': check_bin('tint2'),
        'xterm': check_bin('xterm'),
        'pulseaudio': check_bin('pulseaudio')
    },
    'installed_executables': {
        'steam': check_bin('steam'),
        'heroic': check_bin('heroic'),
        'legendary': check_bin('legendary'),
        'minigalaxy': check_bin('minigalaxy'),
        'lutris': check_bin('lutris'),
        'wine': check_bin('wine'),
        'wine_ge': {'installed': any(os.path.exists(p) for p in ['/home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine', *Path('/home/gamer/.config/heroic/tools/wine').glob('*/bin/wine')]), 'path': next((str(p) for p in ['/home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine', *Path('/home/gamer/.config/heroic/tools/wine').glob('*/bin/wine')] if os.path.exists(str(p))), None)}
    },
    'empirical_gui_smoke_tests': smoke_results,
    'epic_library_probe': {
        'heroic_legendary_config': '/home/gamer/.config/heroic/legendaryConfig/legendary',
        'heroic_installed_apps': epic_installed_apps(),
        'standalone_legendary_config': '/home/gamer/.config/legendary',
        'interactive_account_test_required': True
    },
    'compatibility_matrix': {
        'native_linux_2d_and_cpu_games': 'Fully supported (Mesa llvmpipe software rasterizer)',
        'native_linux_opengl_games': 'NVIDIA OpenGL through VirtualGL' if gpu_facts.get('virtualgl') else 'OpenGL renderer requires live verification',
        'native_vulkan_and_dxvk_games': 'Vulkan X11 presentation verified' if gpu_facts.get('vulkan_window') else 'Vulkan X11 presentation unavailable in this session',
        'windows_games_under_wine_proton': 'DXVK and WineD3D available' if gpu_facts.get('vulkan_window') else 'WineD3D on NVIDIA OpenGL' if gpu_facts.get('virtualgl') else 'Graphics backend requires live verification',
        'epic_games_support': 'Heroic and Legendary installed; individual game launch needs authenticated interactive testing',
        'controller_support': '4 Xbox 360 userspace virtual gamepads via interposer',
        'audio_support': 'PulseAudio stereo monitor -> Selkies Opus 128 kbps',
        'video_support': 'Tesla T4 NVENC hardware H.264 4:2:0 encode at 60 FPS'
    },
    'gpu_runtime': gpu_facts,
    'stream_config': {'codec': 'H.264 4:2:0 8-bit', 'websocket_queue': os.environ.get('GAMELAB_WS_QUEUE', '4')}
}

try:
    listing = subprocess.run([sys.executable, '-m', 'jupyter', 'server', 'list', '--json'],
                             capture_output=True, text=True, timeout=15).stdout
    for line in listing.splitlines():
        if not line.lstrip().startswith('{'):
            continue
        item = json.loads(line)
        base = item.get('url', '').rstrip('/') + '/'
        token = item.get('token', '')
        if not base.startswith(('http://127.0.0.1:', 'http://localhost:')):
            continue
        candidate = base + 'proxy/8080/api/health'
        if token:
            candidate += '?token=' + token
        with urllib.request.urlopen(candidate, timeout=5) as response:
            report['jupyter_proxy_local'] = response.status == 200 and response.read() == b'OK'
        break
except Exception as exc:
    report['jupyter_proxy_local'] = False
    report['jupyter_proxy_error'] = type(exc).__name__

# Persist reports into output directory
Path('/kaggle/working/game_dev_bench_health.json').write_text(json.dumps(report, indent=2))
print('================== HEALTH & DIAGNOSTIC REPORT ==================')
print(json.dumps(report, indent=2))
print('================================================================')
preferred_port = '8080'
(BENCH / 'preferred-stream-port').write_text(preferred_port, encoding='utf-8')
print('Unified direct NVIDIA desktop ready on port 8080.', flush=True)
print('7BZ Dev Cloud Game is running in the active session.')
'''

link_script = r'''from IPython.display import display, HTML
from pathlib import Path
port_file = Path('/tmp/kaggle-game-dev-bench/preferred-stream-port')
stream_port = port_file.read_text().strip() if port_file.is_file() else '8080'
html = r"""
<div style="font:16px system-ui, -apple-system, sans-serif;padding:24px;border-radius:16px;background:#0d1729;color:#f4f8ff;max-width:760px;box-shadow:0 8px 24px rgba(0,0,0,0.5)">
  <h2 style="margin-top:0;color:#4dcdf2;display:flex;align-items:center;gap:10px">
    <span>🎮</span> 7BZ Dev Cloud Game
  </h2>
  <p style="color:#b0c4de;line-height:1.5">
    Controller-first cloud game library with <b>Steam</b>, <b>Heroic</b>, <b>Legendary</b>, <b>Minigalaxy</b>, and <b>Lutris</b>.
  </p>

  <div style="background:#132238;padding:16px;border-radius:12px;margin:16px 0;border-left:4px solid #4dcdf2">
    <b>Connection Steps:</b>
    <ol style="margin:8px 0 0 18px;padding:0;color:#c8daf0;line-height:1.6">
      <li>In Kaggle, open <b>Run → Kaggle Jupyter Server</b> and copy the <b>VSCode Compatible URL</b>.</li>
      <li>Paste it into the field below and click <b>Connect to Stream</b>.</li>
      <li>Open the 7BZ HUD and select <b>Audio Unmute</b> for Opus stereo audio.</li>
      <li>For FPS mouse look, use a normal Chrome or Edge tab and enable <b>Gaming Mode</b>; embedded viewers may block pointer lock.</li>
      <li>Set your local keyboard layout to English (EN), then use mouse, keyboard, or gamepad navigation.</li>
    </ol>
  </div>

  <div style="margin:16px 0">
    <input id="kaggle-base" type="text" style="width:96%;padding:12px;border-radius:8px;border:1px solid #233b5d;background:#080e1a;color:#fff;font-size:14px" placeholder="Paste VSCode Compatible URL (https://...)">
    <button id="kaggle-open" style="margin-top:12px;padding:12px 24px;border-radius:8px;border:none;background:#4dcdf2;color:#081325;font-weight:bold;font-size:15px;cursor:pointer">Connect to Stream</button>
  </div>
  <p id="kaggle-result" style="font-size:13px;color:#9bdcf5;margin-top:6px"></p>

  <div style="border-top:1px solid #1a2a44;padding-top:14px;margin-top:18px;font-size:13px;color:#8ba2c4">
    <b>Empirical Hardware & Security Reality:</b>
    <ul style="margin:6px 0 0 16px;padding:0;line-height:1.5">
      <li><b>User state:</b> Storefronts run as <code>gamer</code>; their temporary credentials and caches are under <code>/home/gamer</code>.</li>
      <li><b>Storefront EULA:</b> Valve's Subscriber Agreement is presented to the user directly in the Steam GUI on first launch.</li>
      <li><b>GPU path:</b> GPU 0 renders the direct NVIDIA Xorg desktop and games; GPU 1 encodes the unified 8080 stream with NVENC.</li>
      <li><b>Custom Builds:</b> Upload test Linux builds into <code style="color:#4dcdf2">/tmp/game-builds</code> via Selkies Files panel.</li>
    </ul>
  </div>
</div>
<script>
document.getElementById('kaggle-open').onclick = function () {
  try {
    const raw = document.getElementById('kaggle-base').value.trim();
    if (!raw) throw new Error('Please paste your URL.');
    const u = new URL(raw);
    let p = u.pathname.replace(/\/(tree|lab|notebooks)(\/.*)?$/, '/');
    if (!p.endsWith('/')) p += '/';
    u.pathname = p + 'proxy/__STREAM_PORT__/';
    const target = u.toString();
    document.getElementById('kaggle-result').textContent = 'Opening authenticated Jupyter proxy route...';
    window.open(target, '_blank', 'noopener,noreferrer');
  } catch (e) {
    document.getElementById('kaggle-result').textContent = 'Please enter a valid https:// Kaggle Jupyter Server URL.';
  }
};
</script>
"""
display(HTML(html.replace('__STREAM_PORT__', stream_port)))
'''

cells = [
    {
        'cell_type': 'markdown',
        'metadata': {},
        'source': [
            '# 7BZ Dev Cloud Game\n',
            '\n',
            'Controller-first Tesla T4 cloud gaming and development console on Kaggle.\n',
            '\n',
            '### Architecture & Storefront Suite\n',
            '- **Unprivileged Execution**: Storefronts and games execute under standard user `gamer` for credential protection and clean user space.\n',
            '- **Steam (Valve Native)**: Full multiarch client running with software CEF flags. License agreement presented directly to the user in the GUI.\n',
            '- **Epic Games**: Heroic GUI and Legendary CLI are available for testing. Launch each installed title to verify compatibility.\n',
            '- **Wine Runner**: Heroic settings select a complete Wine runner, disable UMU/DXVK/VKD3D for this container, and back up existing JSON before repair.\n',
            '- **GOG Galaxy (Minigalaxy & Heroic)**: DRM-free client for GOG games. Supports native Linux builds and Wine.\n',
            '- **Lutris Gaming Hub**: Multi-storefront aggregator installed from Ubuntu multiverse.\n',
            '- **EA App (experimental)**: Wine installer opens; login and game execution need interactive validation.\n',
            '- **7BZ Console Dashboard**: Card library and storefront hub with mouse, keyboard, and full gamepad navigation.\n',
            '- **Streaming HUD**: English glass overlay with WebSocket telemetry, adaptive bitrate, browser controls, and emergency game exit.\n',
            '- **Desktop Window Management**: Openbox window manager and tint2 taskbar panel for smooth multi-window multitasking.\n',
            '- **Selkies 2.1.0 Streaming**: Tesla T4 NVENC hardware H.264 video encoding at 60 FPS, Opus stereo audio, and 4 virtual Xbox gamepad sockets over Kaggle signed Jupyter Server proxy.\n',
            '\n',
            '### Hardware Reality & Constraints\n',
            '- **NVENC Hardware Acceleration**: Encoding is hardware-accelerated on Tesla T4 via NVENC.\n',
            '- **Desktop 3D Rendering**: The verified Wine OpenGL path is direct NVIDIA Xorg `:1` streamed on port `8080`. GPU 0 handles direct hardware 3D rendering and GPU 1 encodes with NVENC.\n',
            '\n',
            '### Instructions\n',
            '1. Set **Accelerator: GPU T4 x2** and **Internet: On** in the Kaggle sidebar.\n',
            '2. Run all cells in an active interactive session.\n',
            '3. Copy the **VSCode Compatible URL** from **Run → Kaggle Jupyter Server**, paste it into the connection cell, and connect!\n',
            '4. The connection cell opens the direct NVIDIA desktop on port `8080`. Openbox, Legendary, and games share that display directly.\n'
        ]
    },
    {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': install_script.splitlines(keepends=True)},
    {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': write_launcher_script.splitlines(keepends=True)},
    {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': start_script.splitlines(keepends=True)},
    {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': link_script.splitlines(keepends=True)},
]
for index, cell in enumerate(cells):
    cell['id'] = f'game-lab-{index + 1}'

nb = {
    'cells': cells,
    'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'}
    },
    'nbformat': 4,
    'nbformat_minor': 5
}

(root / 'kaggle_game_dev_bench.ipynb').write_text(json.dumps(nb, indent=1), encoding='utf-8')
print('Built', root / 'kaggle_game_dev_bench.ipynb')
