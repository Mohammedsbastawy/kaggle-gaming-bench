"""Apply reversible Heroic settings for this container, disarm DXVK, and sync Legendary auth."""
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

# Select best available Wine runner (Prefer Wine-GE over system wine)
runner = {'bin': '/usr/bin/wine', 'wineserver': '/usr/bin/wineserver',
          'wineboot': '/usr/bin/wineboot', 'name': 'Wine Default', 'type': 'wine'}
for candidate in [RUNNERS / 'Wine-GE-Proton8-26/bin/wine', *RUNNERS.glob('*/bin/wine')]:
    if (candidate.is_file() and os.access(candidate, os.X_OK) and
            candidate.with_name('wineserver').is_file()):
        runner = {'bin': str(candidate), 'wineserver': str(candidate.with_name('wineserver')),
                  'wineboot': str(candidate.with_name('wineboot')),
                  'name': candidate.parent.parent.name, 'type': 'wine'}
        break

GAME_SETTINGS_KEYS = (
    'autoInstallDxvk', 'wineVersion', 'winePrefix', 'autoInstallVkd3d',
    'preferSystemLibs', 'launcherArgs', 'enableEsync', 'enableFsync'
)

def clean_prefix_dxvk(prefix: Path):
    """Safely disarm DXVK DLL overrides so WineD3D (OpenGL) renders without Vulkan hardware crash."""
    for sub in ('drive_c/windows/system32', 'drive_c/windows/syswow64'):
        sys_dir = prefix / sub
        if not sys_dir.is_dir():
            continue
        for dll_name in ('dxgi.dll', 'd3d11.dll', 'd3d10core.dll', 'd3d9.dll'):
            target = sys_dir / dll_name
            if target.is_file():
                try:
                    bak = target.with_name(target.name + '.dxvk_bak')
                    if not bak.exists():
                        target.rename(bak)
                    else:
                        target.unlink()
                    print(f'Disarmed DXVK dll in prefix: {target}')
                except OSError as err:
                    print(f'Notice disarming {target}: {err}')

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

    settings_objects = []
    if global_config:
        # Migrate flat config if found
        if not isinstance(data.get('defaultSettings'), dict):
            keys = ('autoInstallDxvk', 'autoInstallVkd3d', 'autoInstallDxvkNvapi',
                    'enableEsync', 'enableFsync', 'disableUMU', 'wineVersion')
            data['defaultSettings'] = {key: data.pop(key) for key in keys if key in data}
        if isinstance(data.get('defaultSettings'), dict):
            settings_objects.append(data['defaultSettings'])
        else:
            settings_objects.append(data)
    else:
        # Per-game config: handle stem key, arbitrary single key, multiple keys, or flat
        if path.stem in data and isinstance(data[path.stem], dict):
            settings_objects.append(data[path.stem])
        else:
            child_matches = [
                v for v in data.values()
                if isinstance(v, dict) and any(k in v for k in GAME_SETTINGS_KEYS)
            ]
            if child_matches:
                settings_objects.extend(child_matches)
            elif any(k in data for k in GAME_SETTINGS_KEYS):
                settings_objects.append(data)
            elif len(data) == 1 and isinstance(list(data.values())[0], dict):
                settings_objects.append(list(data.values())[0])

    if not settings_objects:
        return 'unexpected settings shape'

    for settings in settings_objects:
        for key in ('autoInstallDxvk', 'autoInstallVkd3d', 'autoInstallDxvkNvapi',
                    'enableEsync', 'enableFsync'):
            settings[key] = False
        settings['disableUMU'] = True

        # Assign Wine runner
        selected = settings.get('wineVersion')
        if (not isinstance(selected, dict) or selected.get('type') != 'wine' or
                not os.path.isfile(selected.get('bin', '')) or
                not os.path.isfile(selected.get('wineserver', ''))):
            settings['wineVersion'] = runner

        # Ensure WINEDLLOVERRIDES forces WineD3D builtins
        env_opts = settings.get('enviromentOptions')
        if not isinstance(env_opts, list):
            env_opts = []
        found_override = False
        for opt in env_opts:
            if isinstance(opt, dict) and opt.get('key') == 'WINEDLLOVERRIDES':
                opt['value'] = 'd3d11,dxgi,d3d9,d3d10core=b'
                found_override = True
                break
        if not found_override:
            env_opts.append({'key': 'WINEDLLOVERRIDES', 'value': 'd3d11,dxgi,d3d9,d3d10core=b'})
        settings['enviromentOptions'] = env_opts

        # Clean prefix DXVK overrides if prefix exists
        pfx = settings.get('winePrefix')
        if pfx and os.path.isdir(pfx):
            clean_prefix_dxvk(Path(pfx))

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

def sync_legendary():
    """Seamlessly share Epic Games auth tokens & installed library between Heroic and Legendary CLI."""
    heroic_leg = CONFIG / 'legendaryConfig/legendary'
    std_leg = HOME / '.config/legendary'
    heroic_leg.mkdir(parents=True, exist_ok=True)
    std_leg.mkdir(parents=True, exist_ok=True)

    synced = []
    for fname in ('user.json', 'installed.json', 'config.ini'):
        h_f = heroic_leg / fname
        s_f = std_leg / fname
        try:
            if h_f.is_file() and not s_f.is_file():
                shutil.copy2(h_f, s_f)
                synced.append(f'{fname} (Heroic -> Legendary)')
            elif s_f.is_file() and not h_f.is_file():
                shutil.copy2(s_f, h_f)
                synced.append(f'{fname} (Legendary -> Heroic)')
            elif h_f.is_file() and s_f.is_file():
                if h_f.stat().st_mtime > s_f.stat().st_mtime:
                    shutil.copy2(h_f, s_f)
                    synced.append(f'{fname} (Heroic -> Legendary, updated)')
                elif s_f.stat().st_mtime > h_f.stat().st_mtime:
                    shutil.copy2(s_f, h_f)
                    synced.append(f'{fname} (Legendary -> Heroic, updated)')
        except Exception as e:
            print(f'Notice syncing {fname}: {e}')
    if synced:
        print('Legendary/Heroic synced:', ', '.join(synced))
    else:
        print('Legendary/Heroic auth status: synchronized')

print('Heroic runner:', runner['bin'])
global_file = CONFIG / 'config.json'
print(global_file, repair(global_file, global_config=True))
for path in sorted(GAME_CONFIG.glob('*.json')):
    print(path, repair(path))
for log in sorted(GAME_CONFIG.glob('*-lastPlay.log'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
    print(f'Latest play log: {log}')
    print('\n'.join(log.read_text(errors='replace').splitlines()[-25:]))

sync_legendary()
