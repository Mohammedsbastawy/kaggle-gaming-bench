"""Generate the small Kaggle entrypoint; application code lives in Git."""

import json
from pathlib import Path

ROOT = Path(__file__).parent

bootstrap = '''from pathlib import Path
import importlib.util, os, shutil, subprocess, sys

REPO = Path('/tmp/kaggle-game-dev-bench')
URL = 'https://github.com/Mohammedsbastawy/kaggle-gaming-bench.git'
PROFILE = os.environ.get('GAMELAB_SETUP_PROFILE', 'local')
if PROFILE not in ('local', 'full'):
    raise ValueError('GAMELAB_SETUP_PROFILE must be local or full')

if not (REPO / '.git').is_dir():
    subprocess.run(['git', 'clone', '--depth', '1', URL, str(REPO)], check=True, timeout=180)
else:
    subprocess.run(['git', '-C', str(REPO), 'pull', '--ff-only'], check=True, timeout=90)

revision = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()
marker = REPO / '.setup-complete'
ready = (marker.is_file() and marker.read_text().strip() == f'{revision}:{PROFILE}'
         and shutil.which('wine') and shutil.which('aria2c')
         and importlib.util.find_spec('selkies') and importlib.util.find_spec('pygame'))
if ready:
    print('7BZ environment already prepared in this Kaggle session; skipping setup.', flush=True)
else:
    print(f'Preparing 7BZ {PROFILE} profile from Git revision {revision[:12]}...', flush=True)
    env = dict(os.environ, GAMELAB_SETUP_PROFILE=PROFILE)
    subprocess.run(['bash', str(REPO / 'setup.sh')], check=True, env=env)
    marker.write_text(f'{revision}:{PROFILE}', encoding='utf-8')
    print('7BZ setup complete.', flush=True)
'''

start = '''from pathlib import Path
import runpy
runpy.run_path(str(Path('/tmp/kaggle-game-dev-bench/boot_kaggle.py')), run_name='__main__')
'''

connect = '''from pathlib import Path
import runpy
runpy.run_path(str(Path('/tmp/kaggle-game-dev-bench/notebook_connect.py')), run_name='__main__')
'''

def cell(kind, source, index):
    result = {'cell_type': kind, 'metadata': {}, 'source': source.splitlines(keepends=True),
              'id': f'game-lab-{index}'}
    if kind == 'code':
        result.update(execution_count=None, outputs=[])
    return result


notebook = {
    'cells': [
        cell('markdown', '''# 7BZ Cloud Gaming

Git is the source of truth for the dashboard, Wine/GPU runner, browser, downloads, desktop, and diagnostics. This notebook only boots that source on Kaggle.

1. Enable **GPU T4 x2** and **Internet** in Kaggle.
2. Run the cells in order. The default `local` setup omits optional game stores and storefront GUI smoke tests.
3. Open the connection link in the final cell. Upload complete Windows game folders and launch `.exe` files from **Local Games**.

To restore the historical storefront suite, set `GAMELAB_SETUP_PROFILE=full` in the first code cell before running setup. See `PROJECT_GUIDE.md` in Git for architecture, startup profiles, limitations, and rollback.
''', 1),
        cell('code', bootstrap, 2),
        cell('code', start, 3),
        cell('code', connect, 4),
    ],
    'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                 'language_info': {'name': 'python'}},
    'nbformat': 4,
    'nbformat_minor': 5,
}

target = ROOT / 'kaggle_game_dev_bench.ipynb'
target.write_text(json.dumps(notebook, indent=1), encoding='utf-8')
print(f'Built {target} ({target.stat().st_size} bytes)')
