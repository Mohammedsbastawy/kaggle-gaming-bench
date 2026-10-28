"""Store-independent desktop tools for developer game builds."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse

HOME = Path("/home/gamer")
DOWNLOADS = HOME / "Downloads"
BUILDS = Path("/tmp/game-builds")
ROOTS = (BUILDS, DOWNLOADS, HOME / "Games", HOME)

ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".zst"}


def is_archive(path) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    suf = p.suffix.lower()
    if suf in ARCHIVE_EXTENSIONS:
        return True
    name_lower = p.name.lower()
    return any(name_lower.endswith(ext) for ext in (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst"))


def entries(folder):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        folder.mkdir(parents=True, exist_ok=True)
    result = []
    for path in folder.iterdir():
        if path.name.startswith("."):
            continue
        try:
            if path.is_dir() or path.suffix.lower() in {".exe", ".torrent"} or is_archive(path):
                result.append(path)
        except OSError:
            continue
    return sorted(result, key=lambda p: (not p.is_dir(), p.name.lower()))


def launch_browser(env):
    binary = next((shutil.which(name) for name in ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome", "firefox")
                   if shutil.which(name)), None)
    if not binary:
        raise RuntimeError("Browser is not installed. Run setup.sh again.")
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    env = env.copy()
    env.pop("LD_PRELOAD", None)
    env.pop("SELKIES_JS_SOCKET_PATH", None)
    env.pop("SDL_JOYSTICK_DEVICE", None)
    env.setdefault("DISPLAY", ":1")
    if Path("/tmp/kaggle-game-dev-bench/nvidia-Xauthority").is_file():
        env["XAUTHORITY"] = "/tmp/kaggle-game-dev-bench/nvidia-Xauthority"
    profile = HOME / ".config" / "7bz-browser"
    profile.mkdir(parents=True, exist_ok=True)
    args = [binary]
    if "chromium" in Path(binary).name or "chrome" in Path(binary).name:
        args += [
            f"--user-data-dir={profile}",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--start-maximized",
            "--disable-features=Translate",
            "--disable-breakpad",
            "--test-type",
        ]
    args += ["https://www.google.com"]
    log_dir = Path("/tmp/kaggle-game-dev-bench/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / "browser.log").open("a")
    proc = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                            stdout=log_file, stderr=subprocess.STDOUT,
                            start_new_session=True)
    time.sleep(0.3)
    if proc.poll() is not None:
        try:
            err = (log_dir / "browser.log").read_text()[-300:]
        except Exception:
            err = ""
        raise RuntimeError(f"Browser exited ({proc.returncode}): {err.strip()[:100]}")
    return proc


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


class ExtractionManager:
    """Extracts archives (.rar, .zip, .7z, .tar, etc.) with background thread and visible progress."""

    def __init__(self):
        self.proc = None
        self.state = "Idle"
        self.archive_name = ""
        self.target_dir = ""
        self.detail = "No active extraction."
        self._lock = threading.Lock()

    def extract(self, archive_path, dest_dir=None):
        archive = Path(archive_path).expanduser().resolve()
        if not archive.is_file():
            raise FileNotFoundError(f"Archive not found: {archive}")

        stem = archive.name
        for ext in (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".rar", ".zip", ".7z", ".tar", ".gz"):
            if stem.lower().endswith(ext):
                stem = stem[:-len(ext)]
                break
        dest = Path(dest_dir).expanduser().resolve() if dest_dir else archive.parent / stem
        dest.mkdir(parents=True, exist_ok=True)

        with self._lock:
            if self.proc and self.proc.poll() is None:
                raise RuntimeError("An extraction is already in progress.")

            # Prefer 7z if available (handles rar, 7z, zip, tar, iso)
            if shutil.which("7z"):
                cmd = ["7z", "x", "-y", f"-o{dest}", str(archive)]
            elif shutil.which("unrar") and archive.suffix.lower() == ".rar":
                cmd = ["unrar", "x", "-o+", str(archive), str(dest)]
            elif shutil.which("unzip") and archive.suffix.lower() == ".zip":
                cmd = ["unzip", "-o", str(archive), "-d", str(dest)]
            elif shutil.which("tar") and (archive.suffix.lower() in (".tar", ".gz", ".xz", ".bz2", ".zst") or ".tar." in archive.name.lower()):
                cmd = ["tar", "-xf", str(archive), "-C", str(dest)]
            else:
                try:
                    shutil.unpack_archive(str(archive), str(dest))
                    self.state = "Complete"
                    self.archive_name = archive.name
                    self.target_dir = str(dest)
                    self.detail = f"Extracted to {dest.name}/"
                    return
                except Exception as exc:
                    raise RuntimeError(f"Extraction failed: {exc}")

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True
            )
            self.state = "Extracting"
            self.archive_name = archive.name
            self.target_dir = str(dest)
            self.detail = f"Extracting {archive.name} -> {dest.name}/..."
            proc = self.proc

        threading.Thread(target=self._watch, args=(proc, dest), daemon=True).start()

    def _watch(self, proc, dest):
        last_line = ""
        for line in proc.stdout:
            line = line.strip()
            if line:
                last_line = line
                self.detail = line[-100:]
        code = proc.wait()
        with self._lock:
            if self.proc is proc:
                if code == 0:
                    self.state = "Complete"
                    self.detail = f"Extracted successfully to {Path(dest).name}/"
                else:
                    self.state = f"Failed ({code})"
                    self.detail = f"Extraction failed: {last_line[-80:]}"
                self.proc = None

    def cancel(self):
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                return False
            self.proc.terminate()
            self.state = "Stopped"
            return True
