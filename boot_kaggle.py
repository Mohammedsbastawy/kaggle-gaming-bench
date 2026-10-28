"""Boot Kaggle Cloud Gaming desktop and stream services."""
from pathlib import Path
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

BENCH = Path("/tmp/kaggle-game-dev-bench")
BUILDS = Path("/tmp/game-builds")
BUILDS.mkdir(parents=True, exist_ok=True)
LOGS = BENCH / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
PORT_FILE = BENCH / "preferred-stream-port"

print("==========================================================", flush=True)
print("    7BZ CLOUD GAMING: STARTING DESKTOP & STREAM           ", flush=True)
print("==========================================================", flush=True)

# 1. Install custom web client HUD if available
install_web = BENCH / "install_web_client.py"
if install_web.is_file():
    try:
        print("▶ Installing web client HUD and theme...", flush=True)
        subprocess.run([sys.executable, str(install_web)], check=False, timeout=30)
    except Exception as e:
        print(f"Notice: Web client installation: {e}", flush=True)

# 2. Stop any previous stream session to avoid port conflicts
for pid_path in (BENCH / "direct-stream.pid", BENCH / "selkies.pid"):
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
        except (ValueError, OSError):
            pass

# 3. Environment configuration for asymmetric dual-GPU (GPU 0 render, GPU 1 encode)
env = os.environ.copy()
env["PATH"] = f"/usr/local/bin:/usr/games:/usr/bin:{env.get('PATH', '')}"
if Path("/dev/nvidia1").exists() and Path("/dev/nvidia0").exists():
    print("▶ Dual-GPU detected: GPU 0 (Render) + GPU 1 (NVENC Hardware Encode).", flush=True)
    env["CUDA_VISIBLE_DEVICES"] = "1"
    env["SELKIES_ENCODER_DEVICE"] = "1"
else:
    print("▶ Single-GPU detected: GPU 0 active for rendering and streaming.", flush=True)
    env["CUDA_VISIBLE_DEVICES"] = "0"
    env["SELKIES_ENCODER_DEVICE"] = "0"

queue_size = os.environ.get("GAMELAB_WS_QUEUE", "4")
env.update(
    SELKIES_ENABLE_HTTPS="false",
    SELKIES_MODE="websockets",
    SELKIES_ALLOWED_ORIGINS="https://kkb-production.jupyter-proxy.kaggle.net",
    SELKIES_ENCODER="h264enc",
    SELKIES_FRAMERATE="60-60",
    SELKIES_BACKPRESSURE_QUEUE_SIZE=queue_size,
    SELKIES_VIDEO_BITRATE="3000,800-6000",
    SELKIES_RATE_CONTROL_MODE="cbr",
    SELKIES_CONGESTION_CONTROL="true",
    SELKIES_AUDIO_ENABLED="true",
    SELKIES_AUDIO_CHANNELS="2",
    SELKIES_AUDIO_BITRATE="128000",
    SELKIES_GAMEPAD_ENABLED="true",
    SELKIES_UINPUT_GAMEPAD="false",
    DIRECT_STREAM_PORT="8080"
)

# 4. Launch unified direct NVIDIA Xorg stream
direct_script = BENCH / "start_direct_stream.sh"
started = False

if direct_script.is_file():
    try:
        print("▶ Launching direct NVIDIA Xorg stream on port 8080...", flush=True)
        res = subprocess.run(
            ["bash", str(direct_script)],
            env=env,
            capture_output=True,
            text=True,
            timeout=45
        )
        if res.returncode == 0:
            print("✓ Direct NVIDIA stream initiated successfully.", flush=True)
            started = True
        else:
            print(f"Direct stream notice: {res.stdout[-300:]} {res.stderr[-300:]}", flush=True)
    except Exception as e:
        print(f"Direct stream launch exception: {e}", flush=True)

# 5. Fallback to standard Selkies desktop session if direct Xorg did not start
if not started:
    desktop_script = BENCH / "start_desktop.sh"
    print("▶ Starting standard Selkies desktop fallback on port 8080...", flush=True)
    selkies_log = (LOGS / "direct-stream.log").open("a", buffering=1)
    try:
        subprocess.Popen(
            ["selkies-session", f"--session={desktop_script}", "--port=8080", "--enable-basic-auth=false"],
            stdout=selkies_log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True
        )
    except Exception as e:
        print(f"Fallback launch failed: {e}", flush=True)

# 6. Verify health
stream_ready = False
for attempt in range(30):
    time.sleep(1)
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8080/api/health", timeout=2)
        if req.status == 200:
            stream_ready = True
            break
    except Exception:
        pass

PORT_FILE.write_text("8080", encoding="utf-8")

if stream_ready:
    print("==========================================================", flush=True)
    print("✓ 7BZ CLOUD GAMING DESKTOP READY ON PORT 8080!            ", flush=True)
    print("  Run the next cell (Cell 3) to connect to your stream.   ", flush=True)
    print("==========================================================", flush=True)
else:
    print("⚠ Stream server starting up... Check logs at /tmp/kaggle-game-dev-bench/logs/", flush=True)
