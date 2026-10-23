"""Comprehensive regression check for Heroic config repair, DXVK disarm, and Legendary sync."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    home = Path(root)
    configs = home / '.config/heroic/GamesConfig'
    configs.mkdir(parents=True)
    (home / 'logs').mkdir()
    (home / '.config/heroic/config.json').write_text(json.dumps({'defaultSettings': {'autoInstallDxvk': True}}))

    # Test 1: Standard key == stem
    prefix1 = home / 'prefix1'
    (configs / 'Wolf.json').write_text(json.dumps({'Wolf': {'autoInstallDxvk': True, 'winePrefix': str(prefix1)}, 'version': 'v0'}))
    dll1 = prefix1 / 'drive_c/windows/system32/d3d11.dll'
    dll1.parent.mkdir(parents=True)
    dll1.write_bytes(b'dxvk binary content')

    # Test 2: Mismatched stem and key (like Epic catalog ID filename)
    prefix2 = home / 'prefix2'
    (configs / 'e8bbb84be35640cda646233152ff3428.json').write_text(json.dumps({
        'Brotato': {'autoInstallDxvk': True, 'winePrefix': str(prefix2), 'wineVersion': None}
    }))
    dll2 = prefix2 / 'drive_c/windows/system32/dxgi.dll'
    dll2.parent.mkdir(parents=True)
    dll2.write_bytes(b'dxvk dxgi content')

    # Test 3: Flat game config
    (configs / 'FlatGame.json').write_text(json.dumps({
        'autoInstallDxvk': True, 'enableEsync': True, 'wineVersion': 'invalid'
    }))

    # Test 4: Legendary auth sync from Heroic to Legendary
    heroic_leg = home / '.config/heroic/legendaryConfig/legendary'
    heroic_leg.mkdir(parents=True)
    (heroic_leg / 'user.json').write_text('{"token": "epic_secret_token"}')

    env = dict(os.environ, KAGGLE_GAMER_HOME=str(home))
    res = subprocess.run([sys.executable, str(Path(__file__).with_name('fix_heroic_config.py'))],
                         env=env, check=True, capture_output=True, text=True)

    # Verifications
    game1 = json.loads((configs / 'Wolf.json').read_text())
    assert game1['Wolf']['autoInstallDxvk'] is False
    assert game1['Wolf']['disableUMU'] is True
    assert game1['Wolf']['wineVersion']['type'] == 'wine'
    # DXVK DLL disarmed to .dxvk_bak
    assert not dll1.exists()
    assert (prefix1 / 'drive_c/windows/system32/d3d11.dll.dxvk_bak').read_bytes() == b'dxvk binary content'

    # Brotato verification (mismatched key)
    game2 = json.loads((configs / 'e8bbb84be35640cda646233152ff3428.json').read_text())
    assert game2['Brotato']['autoInstallDxvk'] is False
    assert game2['Brotato']['wineVersion']['type'] == 'wine'
    assert any(opt['key'] == 'WINEDLLOVERRIDES' for opt in game2['Brotato']['enviromentOptions'])
    assert not dll2.exists()
    assert (prefix2 / 'drive_c/windows/system32/dxgi.dll.dxvk_bak').read_bytes() == b'dxvk dxgi content'

    # Flat config verification
    game3 = json.loads((configs / 'FlatGame.json').read_text())
    assert game3['autoInstallDxvk'] is False
    assert game3['enableEsync'] is False
    assert game3['wineVersion']['type'] == 'wine'

    # Legendary sync verification
    std_user_json = home / '.config/legendary/user.json'
    assert std_user_json.is_file()
    assert json.loads(std_user_json.read_text())['token'] == 'epic_secret_token'

print('All Heroic repair, DXVK disarm, and Legendary sync regression tests PASSED!')
