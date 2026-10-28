"""Local developer workspace behavior that does not require a GPU session."""

from pathlib import Path
import tempfile
import unittest

import local_tools
import gpu_runtime


class LocalToolsTests(unittest.TestCase):
    def test_explorer_keeps_game_files_and_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game").mkdir()
            (root / "Game.exe").write_bytes(b"MZ")
            (root / "asset.dat").write_bytes(b"data")
            (root / "download.torrent").write_bytes(b"torrent")
            names = [path.name for path in local_tools.entries(root)]
            self.assertEqual(names, ["game", "download.torrent", "Game.exe"])

    def test_local_launch_rejects_missing_or_non_exe_before_gpu_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "not-a-game.sh"
            script.write_text("exit 0")
            self.assertEqual(gpu_runtime.launch("", "wine", local_path=script), 2)
            self.assertEqual(gpu_runtime.launch("", "wine", local_path=script.with_suffix(".exe")), 2)

    def test_download_manager_rejects_unsupported_source(self):
        manager = local_tools.DownloadManager()
        with self.assertRaises(ValueError):
            manager.start("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
