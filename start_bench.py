"""Start the fast 7BZ desktop and print its Kaggle connection link."""
from html import escape
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

from IPython.display import HTML, display


BENCH = Path("/tmp/kaggle-game-dev-bench")
WORKING = Path("/kaggle/working")
WORKING.mkdir(parents=True, exist_ok=True)

subprocess.run([sys.executable, str(BENCH / "install_web_client.py")], check=True)
old_pidfile = BENCH / "selkies.pid"
if old_pidfile.exists():
    try:
        pid = int(old_pidfile.read_text())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        if b"selkies-session" in cmdline:
            os.killpg(pid, signal.SIGTERM)
            time.sleep(1)
    except (ValueError, OSError, ProcessLookupError):
        pass

queue = os.environ.get("GAMELAB_WS_QUEUE", "12")
if not queue.isdigit() or not 1 <= int(queue) <= 120:
    raise ValueError("GAMELAB_WS_QUEUE must be an integer from 1 to 120")
env = os.environ.copy()
env["PATH"] = f"/usr/local/bin:/usr/games:/usr/bin:{env.get('PATH', '')}"
env.update(
    SELKIES_ENABLE_HTTPS="false",
    SELKIES_MODE="websockets",
    SELKIES_ALLOWED_ORIGINS="https://kkb-production.jupyter-proxy.kaggle.net",
    SELKIES_ENCODER="h264enc",
    SELKIES_FRAMERATE="60,30-60",
    SELKIES_VIDEO_FULLCOLOR="false|locked",
    SELKIES_VIDEO_10BIT="false|locked",
    SELKIES_BACKPRESSURE_QUEUE_SIZE=queue,
    SELKIES_VIDEO_BITRATE="8000,2000-15000",
    SELKIES_RATE_CONTROL_MODE="cbr",
    SELKIES_ENABLE_RESIZE="true",
    SELKIES_AUDIO_ENABLED="true",
    SELKIES_AUDIO_CHANNELS="2",
    SELKIES_AUDIO_BITRATE="128000",
    SELKIES_GAMEPAD_ENABLED="true",
    SELKIES_UINPUT_GAMEPAD="false",
    SELKIES_UI_TITLE="7BZ Dev Cloud Game",
    SELKIES_UI_SHOW_SIDEBAR="false",
    SELKIES_UI_SHOW_LOGO="false",
    SELKIES_MANUAL_WIDTH="1280",
    SELKIES_MANUAL_HEIGHT="720",
    SELKIES_WEB_ROOT=str(BENCH / "web-root"),
    FILE_MANAGER_PATH="/tmp/game-builds",
    SDL_AUDIODRIVER="pulse",
)

log = (BENCH / "selkies.log").open("a", buffering=1)
server = subprocess.Popen(
    ["selkies-session", "--session=" + str(BENCH / "start_desktop.sh"),
     "--port=8080", "--enable-basic-auth=false"],
    stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
    env=env, start_new_session=True,
)
old_pidfile.write_text(str(server.pid))

health = None
for _ in range(75):
    if server.poll() is not None:
        break
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/api/health", timeout=2) as response:
            if response.status == 200:
                health = response.read().decode(errors="replace")
                break
    except (OSError, TimeoutError):
        time.sleep(1)
if health != "OK":
    raise RuntimeError("Selkies did not start: " +
                       (BENCH / "selkies.log").read_text(errors="replace")[-3500:])
with urllib.request.urlopen("http://127.0.0.1:8080/api/status", timeout=5) as response:
    status = json.load(response)

try:
    started = float(Path("/tmp/7bz-boot-start").read_text())
except (OSError, ValueError):
    started = time.time()
report = {
    "version": 34,
    "health": health,
    "time_to_stream_seconds": round(time.time() - started, 2),
    "status": status,
    "nvenc_detected": "encodes H264, H265 on nvenc" in (BENCH / "selkies.log").read_text(errors="replace"),
    "stream_config": {"codec": "H.264 4:2:0 8-bit", "websocket_queue": int(queue)},
    "deferred": ["NVIDIA 3D userspace", "VirtualGL", "Wine-GE", "VC++ runtimes",
                 "Heroic", "Steam", "Lutris", "Minigalaxy", "EA App"],
}
(WORKING / "game_dev_bench_health.json").write_text(json.dumps(report, indent=2))
print("STREAM_READY_SECONDS=" + str(report["time_to_stream_seconds"]))
print("Selkies health:", health, "NVENC:", report["nvenc_detected"])

# Kaggle's external Jupyter proxy URL is session-specific and cannot be
# reconstructed from localhost. Use it if Kaggle supplies it; otherwise the
# familiar connect control accepts Run -> Kaggle Jupyter Server's URL.
external = os.environ.get("KAGGLE_JUPYTER_SERVER_URL", "").strip()
if external.startswith("https://"):
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(external)
    path = parts.path.rstrip("/") + "/proxy/8080/"
    stream_url = urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))
    print("Authenticated stream URL:", stream_url)
    display(HTML(f'<a target="_blank" rel="noopener" href="{escape(stream_url, quote=True)}">Open 7BZ stream</a>'))
else:
    display(HTML('''<div style="font:16px system-ui;padding:20px;background:#0d1729;color:#f4f8ff;border-radius:12px;max-width:680px">
<b>7BZ stream is ready.</b> In Kaggle, open <b>Run → Kaggle Jupyter Server</b> and copy the VSCode Compatible URL.
<p><input id="seven-base" placeholder="Paste the VSCode Compatible URL" style="width:95%;padding:10px"></p>
<button id="seven-open" style="padding:10px">Open authenticated stream</button>
<script>document.getElementById('seven-open').onclick=()=>{const u=new URL(document.getElementById('seven-base').value.trim());u.pathname=u.pathname.replace(/\\/(tree|lab|notebooks)(\\/.*)?$/,'/').replace(/\\/?$/,'/')+'proxy/8080/';window.open(u.toString(),'_blank','noopener,noreferrer');};</script>
</div>'''))
