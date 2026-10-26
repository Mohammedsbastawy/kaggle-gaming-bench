import asyncio
import base64
import gzip
import os
from pathlib import Path
import sys
sys.path.append(r'd:\Kaggle Cloud Gaming')
import exec_remote

BENCH_DIR = Path(r'd:\Kaggle Cloud Gaming')

def send_file(local_path, remote_path):
    with open(local_path, 'rb') as f:
        data = f.read()
    compressed = gzip.compress(data)
    b64 = base64.b64encode(compressed).decode('ascii')
    code = f"""
import base64, gzip
raw = base64.b64decode({repr(b64)})
decompressed = gzip.decompress(raw)
with open({repr(remote_path)}, 'wb') as f:
    f.write(decompressed)
print('Wrote', {repr(remote_path)}, len(decompressed), 'bytes')
"""
    return asyncio.run(exec_remote.execute_code(code))

print("=== Uploading game_catalog.py ===")
print(send_file(BENCH_DIR / "game_catalog.py", "/tmp/kaggle-game-dev-bench/game_catalog.py"))

print("=== Uploading dev_launcher.py ===")
print(send_file(BENCH_DIR / "dev_launcher.py", "/tmp/kaggle-game-dev-bench/dev_launcher.py"))

restart_code = """
import os, subprocess, time

# Kill old launcher and old legendary_gui
subprocess.run(['pkill', '-9', '-f', 'dev_launcher.py'], check=False)
subprocess.run(['pkill', '-9', '-f', 'legendary_gui.py'], check=False)
time.sleep(1)

cmd = [
    'runuser', '-u', 'gamer', '--',
    'env', 'DISPLAY=:1', 'HOME=/home/gamer',
    'XAUTHORITY=/tmp/kaggle-game-dev-bench/nvidia-Xauthority',
    'XDG_RUNTIME_DIR=/tmp/kaggle-game-dev-bench/pulse-runtime',
    'PULSE_SERVER=unix:/tmp/kaggle-game-dev-bench/pulse-runtime/pulse/native',
    'PULSE_COOKIE=/home/gamer/.config/pulse/cookie',
    'PULSE_SINK=output', 'SDL_AUDIODRIVER=pulse',
    'CUDA_VISIBLE_DEVICES=0', 'GAMELAB_DIRECT_XORG=1',
    'SELKIES_JS_SOCKET_PATH=/tmp/kaggle-game-dev-bench/direct-stream-sockets',
    'PYTHONPATH=/tmp/kaggle-game-dev-bench',
    'python3', '/tmp/kaggle-game-dev-bench/dev_launcher.py'
]

log = open('/tmp/kaggle-game-dev-bench/logs/direct-dashboard.log', 'w')
proc = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
print('Spawned PID:', proc.pid)
time.sleep(3)
print('Is running:', proc.poll() is None)
with open('/tmp/kaggle-game-dev-bench/logs/direct-dashboard.log') as f:
    print('LOG OUTPUT:')
    print(f.read())
"""

print("=== Restarting dev_launcher.py ===")
print(asyncio.run(exec_remote.execute_code(restart_code)))
