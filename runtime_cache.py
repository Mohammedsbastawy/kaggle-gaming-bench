"""Build and restore a Kaggle-local snapshot of the 7BZ local setup.

The snapshot is usable only with the same base Debian package set and NVIDIA
driver. A mismatch returns without changing the container so setup.sh can run.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


SCHEMA = 1
ROOT = Path('/tmp/kaggle-game-dev-bench')
BASELINE = Path('/kaggle/working/7bz-base-packages.json')
CACHE = Path('/kaggle/working/7bz-runtime-cache')
# The first CPU-built archive predates the setup_version manifest field.
INITIAL_CACHE_SETUP_VERSION = '3cb88ac853f462d7'
SETUP_FILES = ('setup.sh', 'install_lichii.sh', 'probe_nvidia_userspace.sh', 'setup_gpu_cache.sh')


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def packages():
    lines = run('dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n').splitlines()
    return dict(line.split('\t', 1) for line in lines if '\t' in line)


def fingerprint(mapping):
    data = json.dumps(mapping, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def setup_version():
    return hashlib.sha256(b''.join((ROOT / name).read_bytes() for name in SETUP_FILES)).hexdigest()[:16]


def driver():
    try:
        return run('nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader').splitlines()[0]
    except (OSError, subprocess.CalledProcessError, IndexError):
        return ''


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def capture_baseline():
    BASELINE.write_text(json.dumps({'packages': packages(), 'driver': driver()}), encoding='utf-8')
    print('Captured clean Kaggle package and GPU baseline.', flush=True)


def build():
    base = json.loads(BASELINE.read_text(encoding='utf-8'))
    current = packages()
    changed = [name for name, version in current.items() if base['packages'].get(name) != version]
    if not changed or not (Path('/opt/lichii/build').is_file()):
        raise RuntimeError('7BZ setup is incomplete; refusing to create a cache.')
    paths = set()
    for name in changed:
        listing = subprocess.run(['dpkg', '-L', name], capture_output=True, text=True, check=True)
        paths.update(line for line in listing.stdout.splitlines() if line.startswith('/') and Path(line).exists())
    extras = [Path('/var/lib/dpkg'), Path('/opt/lichii'), Path('/opt/gamelab-dxvk'),
              Path('/opt/gamelab-vkd3d'), Path('/opt/VirtualGL'),
              Path('/home/gamer/.wine'), Path('/home/gamer/.config/heroic/tools/wine'),
              Path('/tmp/kaggle-game-dev-bench/lib'),
              Path('/tmp/kaggle-game-dev-bench/lib64'),
              Path('/tmp/kaggle-game-dev-bench/lib32'),
              Path('/etc/ld.so.conf.d/00-nvidia-host.conf'), Path('/usr/local/bin/wine'),
              Path('/usr/lib/x86_64-linux-gnu/selkies_input_interposer.so'),
              Path('/usr/lib/x86_64-linux-gnu/selkies_fake_udev.so'),
              Path('/usr/lib/i386-linux-gnu/selkies_input_interposer.so'),
              Path('/usr/lib/i386-linux-gnu/selkies_fake_udev.so')]
    for path in extras:
        if not path.exists() and not path.is_symlink():
            continue
        paths.add(str(path))
        if path.is_dir() and not path.is_symlink():
            for folder, directories, files in os.walk(path):
                paths.add(folder)
                paths.update(str(Path(folder) / name) for name in directories + files)
    CACHE.mkdir(parents=True, exist_ok=True)
    files = CACHE / 'paths.txt'
    files.write_text('\n'.join(sorted(paths)) + '\n', encoding='utf-8')
    archive = CACHE / 'runtime.tar'
    subprocess.run(['tar', '--create', '--file', str(archive), '--no-recursion',
                    '--files-from', str(files)], check=True)
    manifest = {'schema': SCHEMA, 'base_packages_sha256': fingerprint(base['packages']),
                'driver': base['driver'], 'archive_sha256': digest(archive),
                'package_count': len(changed), 'archive_bytes': archive.stat().st_size,
                'setup_version': setup_version()}
    (CACHE / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    files.unlink()
    print(f"Built 7BZ runtime cache: {len(changed)} packages, {archive.stat().st_size / 1e9:.2f} GB.", flush=True)


def restore(cache):
    manifest = json.loads((cache / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != SCHEMA:
        print('Runtime cache schema mismatch; using normal setup.', flush=True)
        return False
    if manifest.get('setup_version', INITIAL_CACHE_SETUP_VERSION) != setup_version():
        print('7BZ setup dependencies changed; using normal setup.', flush=True)
        return False
    if manifest.get('base_packages_sha256') != fingerprint(packages()) or (manifest.get('driver') and manifest.get('driver') != driver()):
        print('Kaggle base image or NVIDIA driver changed; using normal setup.', flush=True)
        return False
    archive = cache / 'runtime.tar'
    if manifest.get('archive_sha256') != digest(archive):
        print('Runtime cache checksum mismatch; using normal setup.', flush=True)
        return False
    # The cache comes from our private builder notebook. Inspect names before
    # extracting so a damaged archive cannot write outside the container root.
    names = run('tar', '-tf', str(archive)).splitlines()
    if any(name.startswith('/') or '..' in Path(name).parts for name in names):
        print('Runtime cache contains unsafe paths; using normal setup.', flush=True)
        return False
    if subprocess.run(['id', '-u', 'gamer'], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode != 0:
        subprocess.run(['useradd', '-m', '-s', '/bin/bash', '-G', 'audio,video', 'gamer'], check=True)
    print('Restoring cached 7BZ gaming environment...', flush=True)
    subprocess.run(['tar', '--extract', '--file', str(archive), '--directory', '/'], check=True)
    subprocess.run(['ldconfig'], check=True)
    if not manifest.get('driver'):
        subprocess.run(['bash', str(ROOT / 'setup_gpu_cache.sh')], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir',
                    'selkies[jupyter]==2.1.0', 'pygame==2.6.1', 'psutil'], check=True)
    from auto_optimize import inject_keyboard_lock
    inject_keyboard_lock()
    Path('/dev/input').mkdir(exist_ok=True)
    for name in [*(f'js{i}' for i in range(4)), *(f'event{i}' for i in range(1000, 1004))]:
        device = Path('/dev/input') / name
        device.touch(exist_ok=True)
        device.chmod(0o666)
    subprocess.run(['chown', '-R', 'gamer:gamer', '/home/gamer'], check=True)
    required = [Path('/opt/lichii/squashfs-root/AppRun'), Path('/usr/bin/wine'),
                Path('/usr/bin/aria2c'), Path('/tmp/kaggle-game-dev-bench/lib/x86_64-linux-gnu/selkies_input_interposer.so')]
    if not all(path.is_file() for path in required):
        raise RuntimeError('Restored runtime is missing required files.')
    print('Cached 7BZ environment restored.', flush=True)
    return True


if __name__ == '__main__':
    command = sys.argv[1]
    if command == 'baseline':
        capture_baseline()
    elif command == 'build':
        build()
    elif command == 'restore':
        sys.exit(0 if restore(Path(sys.argv[2])) else 2)
    else:
        raise SystemExit('Usage: runtime_cache.py baseline|build|restore CACHE_DIR')
