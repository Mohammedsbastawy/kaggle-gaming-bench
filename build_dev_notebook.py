"""Build the three-cell Kaggle notebook from the pinned Git release."""
import json
from pathlib import Path


ROOT = Path(__file__).parent
REPO = "https://github.com/Mohammedsbastawy/kaggle-gaming-bench.git"
REF = "main"

clone = f'''from pathlib import Path
import subprocess, time

bench = Path('/tmp/kaggle-game-dev-bench')
Path('/tmp/7bz-boot-start').write_text(str(time.time()))
repo = {REPO!r}
ref = {REF!r}
if (bench / '.git').is_dir():
    subprocess.run(['git', '-C', str(bench), 'fetch', '--depth', '1', 'origin', ref], check=True)
    subprocess.run(['git', '-C', str(bench), 'reset', '--hard', 'FETCH_HEAD'], check=True)
else:
    subprocess.run(['git', 'clone', '--depth', '1', '--branch', ref, repo, str(bench)], check=True)
print('Repository:', subprocess.check_output(['git', '-C', str(bench), 'rev-parse', '--short', 'HEAD'], text=True).strip())
'''

bootstrap = '''import subprocess
subprocess.run(['/bin/bash', '/tmp/kaggle-game-dev-bench/setup.sh'], check=True)
'''

start = '''from pathlib import Path
import runpy
runpy.run_path(str(Path('/tmp/kaggle-game-dev-bench/start_bench.py')), run_name='__main__')
'''


def cell(kind, source, number):
    result = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True),
              "id": f"7bz-fastboot-{number}"}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


notebook = {
    "cells": [
        cell("markdown", """# 7BZ Dev Cloud Game · Version 34

Fast cold boot: clone the pinned release, install desktop essentials, then start Selkies. The dashboard appears before Wine, NVIDIA 3D driver injection, and optional storefronts are installed. Those are prepared when a game or storefront is first launched.

Set Kaggle Accelerator to **GPU T4 x2** and Internet to **On**, then Run All. Cell 3 prints `STREAM_READY_SECONDS` and shows the authenticated stream connector. The first game launch can take longer while compatibility packages are prepared.
""", 1),
        cell("code", clone, 2),
        cell("code", bootstrap, 3),
        cell("code", start, 4),
    ],
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}},
    "nbformat": 4,
    "nbformat_minor": 5,
}

target = ROOT / "kaggle_game_dev_bench.ipynb"
target.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
print("Built", target)
