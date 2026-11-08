"""Run once on Kaggle to produce a reusable 7BZ runtime cache output.

Keep this notebook private and attach its output to the main 7BZ notebook.
"""

from pathlib import Path
import subprocess

repo = Path('/tmp/kaggle-game-dev-bench')
if not (repo / '.git').is_dir():
    subprocess.run(['git', 'clone', '--depth', '1',
                    'https://github.com/Mohammedsbastawy/kaggle-gaming-bench.git',
                    str(repo)], check=True)
else:
    subprocess.run(['git', '-C', str(repo), 'pull', '--ff-only'], check=True)

subprocess.run(['python3', str(repo / 'runtime_cache.py'), 'baseline'], check=True)
subprocess.run(['bash', str(repo / 'setup.sh')], check=True)
subprocess.run(['python3', str(repo / 'runtime_cache.py'), 'build'], check=True)
