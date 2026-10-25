import sys
sys.path.append(r'd:\Kaggle Cloud Gaming')
import remote_exec

script = """
import os
path = os.path.expanduser('~gamer/.wine/drive_c/users/gamer/Saved Games/MachineGames/Wolfenstein The New Order/base/qconsole.log')
with open(path, 'r', errors='ignore') as f:
    lines = f.readlines()
count = 0
for l in lines:
    if 'WARNING: No hardware voices available' in l:
        count += 1
        continue
    if count > 0:
        print(f'... [suppressed {count} duplicate warning lines] ...')
        count = 0
    print(l, end='')
"""

res = remote_exec.run_cmd("cat << 'EOF' > /tmp/parse_log.py\n" + script + "\nEOF\npython3 /tmp/parse_log.py")
with open(r'd:\Kaggle Cloud Gaming\qconsole_clean.log', 'w', encoding='utf-8') as out:
    out.write(res)
print("Saved clean log, total length:", len(res))
