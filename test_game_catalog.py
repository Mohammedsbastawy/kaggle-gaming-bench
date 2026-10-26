import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import game_catalog


class TestGameCatalog(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.home = Path(self.test_dir) / "gamer"
        self.home.mkdir(parents=True)
        self.patch_home = patch.object(game_catalog, "HOME", self.home)
        self.patch_home.start()

    def tearDown(self):
        self.patch_home.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_missing_disk_directory_is_not_treated_as_installed(self):
        # Setup fake Heroic config with an app that does NOT exist on disk
        heroic_dir = self.home / ".config" / "heroic" / "legendaryConfig" / "legendary"
        heroic_dir.mkdir(parents=True)
        installed_file = heroic_dir / "installed.json"
        
        stale_record = {
            "fake_app_123": {
                "app_name": "fake_app_123",
                "title": "Wolfenstein: The New Order",
                "install_path": str(self.home / "Games" / "NonExistentGame"),
                "executable": "WolfNewOrder_x64.exe",
                "install_size": 47772868294
            }
        }
        installed_file.write_text(json.dumps(stale_record, indent=2), encoding="utf-8")

        # Query installed games
        installed = game_catalog.legendary_installed_games()
        self.assertEqual(len(installed), 0, "Games missing from disk must NOT be reported as installed")

        # Verify stale record was automatically purged
        purged = json.loads(installed_file.read_text(encoding="utf-8"))
        self.assertNotIn("fake_app_123", purged, "Stale record should be cleaned up from json")

    def test_existing_disk_directory_is_treated_as_installed(self):
        heroic_dir = self.home / ".config" / "heroic" / "legendaryConfig" / "legendary"
        heroic_dir.mkdir(parents=True)
        installed_file = heroic_dir / "installed.json"

        game_dir = self.home / "Games" / "RealGame"
        game_dir.mkdir(parents=True)
        (game_dir / "game.exe").write_text("dummy")

        record = {
            "real_app_456": {
                "app_name": "real_app_456",
                "title": "Real Installed Game",
                "install_path": str(game_dir),
                "executable": "game.exe",
                "install_size": 1024 * 1024 * 500
            }
        }
        installed_file.write_text(json.dumps(record, indent=2), encoding="utf-8")

        installed = game_catalog.legendary_installed_games()
        self.assertEqual(len(installed), 1)
        self.assertTrue(installed[0]["is_installed"])
        self.assertEqual(installed[0]["title"], "Real Installed Game")


if __name__ == '__main__':
    unittest.main()
