"""Store-independent desktop tools for developer game builds."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from urllib.parse import urlparse

HOME = Path("/home/gamer")
DOWNLOADS = HOME / "Downloads"
BUILDS = Path("/tmp/game-builds")
ROOTS = (BUILDS, DOWNLOADS, HOME / "Games", HOME)


def entries(folder):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(str(folder))
    result = []
    for path in folder.iterdir():
        if path.name.startswith("."):
            continue
        try:
            if path.is_dir() or path.suffix.lower() in {".exe", ".torrent", ".zip", ".7z", ".rar"}:
                result.append(path)
        except OSError:
            continue
    return sorted(result, key=lambda p: (not p.is_dir(), p.name.lower()))


def launch_browser(env):
    binary = next((shutil.which(name) for name in ("chromium", "chromium-browser", "firefox", "google-chrome-stable")
                   if shutil.which(name)), None)
    if not binary:
        raise RuntimeError("Browser is not installed. Run setup.sh again.")
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    env = env.copy()
    env.pop("LD_PRELOAD", None)
    env.pop("SELKIES_JS_SOCKET_PATH", None)
    env.pop("SDL_JOYSTICK_DEVICE", None)
    profile = HOME / ".config" / "7bz-browser"
    args = [binary]
    if "chromium" in Path(binary).name or "chrome" in Path(binary).name:
        args += [f"--user-data-dir={profile}", "--no-first-run", "--disable-dev-shm-usage",
                 "--password-store=basic", "--start-maximized"]
    args += ["about:blank"]
    return subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


class DownloadManager:
    """One controlled aria2 transfer at a time, with a visible log and cancel action."""

    def __init__(self):
        self.proc = None
        self.state = "Idle"
        self.source = ""
        self.percent = 0.0
        self.speed = ""
        self.eta = ""
        self.detail = "Paste an HTTPS URL, magnet link, or choose a .torrent file."
        self._lock = threading.Lock()

    def start(self, source):
        source = source.strip()
        parsed = urlparse(source)
        torrent_file = Path(source).expanduser()
        if not (parsed.scheme in ("https", "http", "magnet") or
                (torrent_file.is_file() and torrent_file.suffix.lower() == ".torrent")):
            raise ValueError("Enter an HTTP(S) URL, magnet link, or .torrent file path.")
        if not shutil.which("aria2c"):
            raise RuntimeError("aria2 is not installed. Run setup.sh again.")
        with self._lock:
            if self.proc and self.proc.poll() is None:
                raise RuntimeError("A download is already running.")
            DOWNLOADS.mkdir(parents=True, exist_ok=True)
            args = ["aria2c", "--dir", str(DOWNLOADS), "--continue=true",
                    "--max-tries=5", "--retry-wait=3", "--summary-interval=1",
                    "--console-log-level=warn", "--enable-color=false", source]
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True,
                                         bufsize=1, start_new_session=True)
            self.source = source
            self.state = "Downloading"
            self.percent = 0.0
            self.speed = ""
            self.eta = ""
            self.detail = "Starting transfer..."
            proc = self.proc
        threading.Thread(target=self._watch, args=(proc,), daemon=True).start()

    def _watch(self, proc):
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            match = re.search(r"\((\d+(?:\.\d+)?)%\)", line)
            if match:
                self.percent = float(match.group(1))
            speed = re.search(r"(?:DL|UL):([^\s]+)", line)
            if speed:
                self.speed = speed.group(1)
            eta = re.search(r"ETA:([^\s]+)", line)
            if eta:
                self.eta = eta.group(1)
            self.detail = line[-110:]
        code = proc.wait()
        with self._lock:
            if self.proc is proc:
                self.state = "Complete" if code == 0 else "Stopped" if code < 0 else f"Failed ({code})"
                if code == 0:
                    self.percent = 100.0
                self.proc = None

    def cancel(self):
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                return False
            self.proc.terminate()
            self.state = "Stopping"
            return True
