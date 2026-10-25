import remote_exec

py_code = """
import subprocess, os

env = os.environ.copy()
env['DISPLAY'] = ':0'
p = subprocess.Popen(['/tmp/run_wolf_optimized.sh'], user='gamer', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('SPAWNED PID:', p.pid)
"""

cmd = f"python3 -c \"{py_code.strip()}\""
res = remote_exec.run_cmd(cmd)
print("Spawn result:", res)
