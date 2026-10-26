import asyncio
import sys
sys.path.append(r'd:\Kaggle Cloud Gaming')
import exec_remote

code = """
import os, subprocess, time

# Kill old launcher
subprocess.run(['pkill', '-9', '-f', 'dev_launcher.py'], check=False)
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
time.sleep(2)
print('Is running:', proc.poll() is None)
"""

print(asyncio.run(exec_remote.execute_code(code)))
