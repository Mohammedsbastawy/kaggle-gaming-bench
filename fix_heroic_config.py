"""Apply reversible Heroic settings for this container and collect launch evidence."""
import json
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone

HOME = Path(os.environ.get('KAGGLE_GAMER_HOME', '/home/gamer'))
CONFIG = HOME / '.config/heroic'
GAME_CONFIG = CONFIG / 'GamesConfig'
RUNNERS = CONFIG / 'tools/wine'
BACKUPS = HOME / 'logs/heroic-config-backups'
BACKUPS.mkdir(parents=True, exist_ok=True)

runner = {'bin': '/usr/bin/wine', 'wineserver': '/usr/bin/wineserver',
          'wineboot': '/usr/bin/wineboot', 'name': 'Wine Default', 'type': 'wine'}
for candidate in [RUNNERS / 'Wine-GE-Proton8-26/bin/wine', *RUNNERS.glob('*/bin/wine')]:
    if (candidate.is_file() and os.access(candidate, os.X_OK) and
            candidate.with_name('wineserver').is_file()):
        runner = {'bin': str(candidate), 'wineserver': str(candidate.with_name('wineserver')),
                  'wineboot': str(candidate.with_name('wineboot')),
                  'name': candidate.parent.parent.name, 'type': 'wine'}
        break

def repair(path, global_config=False):
    if not path.exists():
        return 'missing'
    try:
        old_text = path.read_text(encoding='utf-8')
        data = json.loads(old_text)
        if not isinstance(data, dict):
            return 'unexpected JSON shape'
    except (OSError, json.JSONDecodeError) as exc:
        return f'not edited: {exc}'
    # Migrate the earlier malformed flat file without discarding unrelated keys.
    if global_config and not isinstance(data.get('defaultSettings'), dict):
        keys = ('autoInstallDxvk', 'autoInstallVkd3d', 'autoInstallDxvkNvapi',
                'enableEsync', 'enableFsync', 'disableUMU', 'wineVersion')
        data['defaultSettings'] = {key: data.pop(key) for key in keys if key in data}
    # Heroic 2.22 stores global defaults under defaultSettings and per-game settings under game ID.
    settings_objects = ([data['defaultSettings']] if isinstance(data.get('defaultSettings'), dict) else []) if global_config else ([data[path.stem]] if isinstance(data.get(path.stem), dict) else [])
    if not settings_objects:
        return 'unexpected settings shape'
    for settings in settings_objects:
        for key in ('autoInstallDxvk', 'autoInstallVkd3d', 'autoInstallDxvkNvapi',
                    'enableEsync', 'enableFsync'):
            settings[key] = False
        settings['disableUMU'] = True
        selected = settings.get('wineVersion')
        if (not isinstance(selected, dict) or selected.get('type') != 'wine' or
                not os.path.isfile(selected.get('bin', '')) or
                not os.path.isfile(selected.get('wineserver', ''))):
            settings['wineVersion'] = runner
    new_text = json.dumps(data, indent=2) + '\n'
    if new_text == old_text:
        return 'already configured'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = BACKUPS / f'{path.name}.{stamp}.bak'
    shutil.copy2(path, backup)
    tmp = path.with_suffix(path.suffix + '.new')
    tmp.write_text(new_text, encoding='utf-8')
    os.replace(tmp, path)
    return f'updated; backup {backup}'

print('Heroic runner:', runner['bin'])
global_file = CONFIG / 'config.json'
print(global_file, repair(global_file, global_config=True))
for path in sorted(GAME_CONFIG.glob('*.json')):
    print(path, repair(path))
for log in sorted(GAME_CONFIG.glob('*-lastPlay.log'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
    print(f'Latest play log: {log}')
    print('\n'.join(log.read_text(errors='replace').splitlines()[-25:]))
print('Wine prefixes and DLLs were left intact.')
