"""Store-independent desktop tools for developer game builds."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Iterable, List, Optional, Set, Union
from urllib.parse import urlparse

HOME = Path("/home/gamer")
DOWNLOADS = HOME / "Downloads"
BUILDS = Path("/tmp/game-builds")
ROOTS = (BUILDS, DOWNLOADS, HOME / "Games", HOME)

ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".zst"}

MULTIPART_RE = re.compile(
    r'^(?P<base>.+?)(?:'
    r'\.part(?P<part_num>\d+)(?P<ext>\.(?:rar|zip|7z))|'
    r'(?P<ext_r>\.r(?P<part_r>\d+))|'
    r'(?P<ext_z>\.z(?P<part_z>\d+))|'
    r'(?P<ext_7z>\.7z)\.(?P<part_7z>\d+)|'
    r'(?P<ext_zip>\.zip)\.(?P<part_zip>\d+)'
    r')$',
    re.IGNORECASE
)


def is_archive(path: Union[str, Path, None]) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    name_lower = p.name.lower()
    if any(name_lower.endswith(ext) for ext in ARCHIVE_EXTENSIONS):
        return True
    if any(name_lower.endswith(ext) for ext in (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst")):
        return True
    return bool(MULTIPART_RE.match(p.name))


def find_first_part(archive_path: Path) -> Path:
    """If archive is part of a multi-volume set (e.g. part02.rar), locates and returns part 1."""
    p = Path(archive_path).expanduser().resolve()
    if not p.is_file():
        return p
    m = MULTIPART_RE.match(p.name)
    if not m:
        return p

    base = m.group("base")
    parent = p.parent
    ext = m.group("ext") or (".rar" if m.group("ext_r") else (".zip" if m.group("ext_z") else ""))
    candidates = []

    if m.group("part_num"):
        for fmt in ("part1", "part01", "part001", "part0001"):
            candidates.append(parent / f"{base}.{fmt}{ext}")
    elif m.group("ext_r"):
        candidates.extend([parent / f"{base}.rar", parent / f"{base}.r00", parent / f"{base}.r01"])
    elif m.group("part_7z"):
        candidates.extend([parent / f"{base}.7z.001", parent / f"{base}.7z.1"])
    elif m.group("part_z"):
        candidates.extend([parent / f"{base}.zip", parent / f"{base}.z01"])
    elif m.group("part_zip"):
        candidates.extend([parent / f"{base}.zip.001", parent / f"{base}.zip.1"])

    for cand in candidates:
        if cand.is_file():
            return cand

    return p


def normalize_archive_list(archive_paths: Iterable[Union[str, Path]]) -> List[Path]:
    """Deduplicates multipart archive sets to their first volume so each set extracts only once."""
    normalized: List[Path] = []
    seen: Set[Path] = set()
    for p in archive_paths:
        p_path = Path(p).expanduser().resolve()
        if not p_path.is_file():
            continue
        first_part = find_first_part(p_path)
        if first_part not in seen:
            seen.add(first_part)
            normalized.append(first_part)
    return normalized


def get_archive_base_name(archive_path: Union[str, Path]) -> str:
    """Returns a clean folder stem for extraction, stripping multi-part indicators."""
    p = Path(archive_path)
    m = MULTIPART_RE.match(p.name)
    if m:
        return m.group("base")
    stem = p.name
    for ext in (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".rar", ".zip", ".7z", ".tar", ".gz"):
        if stem.lower().endswith(ext):
            return stem[:-len(ext)]
    return p.stem


def archive_tag(path: Union[str, Path]) -> str:
    """Returns a user-friendly label for file list displays."""
    p = Path(path)
    m = MULTIPART_RE.match(p.name)
    if m:
        num = (m.group("part_num") or m.group("part_r") or m.group("part_7z")
               or m.group("part_z") or m.group("part_zip"))
        ext = (m.group("ext") or m.group("ext_7z") or m.group("ext_zip") or "").upper().lstrip(".")
        if num is not None:
            return f"PART {num} ({ext})" if ext else f"PART {num}"
    if is_archive(p):
        return f"ARCHIVE ({p.suffix.upper().lstrip('.')})"
    return p.suffix.upper().lstrip(".")


def entries(folder):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        folder.mkdir(parents=True, exist_ok=True)
    result = []
    for path in folder.iterdir():
        if path.name.startswith("."):
            continue
        try:
            if path.is_dir() or path.suffix.lower() == ".exe" or is_archive(path):
                result.append(path)
        except OSError:
            continue
    return sorted(result, key=lambda p: (not p.is_dir(), p.name.lower()))


def is_snap_stub(path: Union[str, Path, None]) -> bool:
    if not path:
        return False
    try:
        p = Path(path)
        if not p.is_file():
            return False
        content = p.read_text(encoding="utf-8", errors="ignore")
        return "snap" in content and ("requires the chromium snap" in content or "snap install" in content)
    except Exception:
        return False


def find_working_browser() -> Optional[str]:
    candidates = (
        "google-chrome-stable",
        "google-chrome",
        "google-chrome-beta",
        "firefox",
        "chromium",
        "chromium-browser",
    )
    for name in candidates:
        path = shutil.which(name)
        if path and not is_snap_stub(path):
            return path
    return None


def launch_browser(env, url="https://www.google.com"):
    binary = find_working_browser()
    if not binary:
        raise RuntimeError("Google Chrome is not installed. Run 'apt-get install -y /tmp/google-chrome-stable_current_amd64.deb'")
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    env = env.copy()
    env.pop("LD_PRELOAD", None)
    env.pop("SELKIES_JS_SOCKET_PATH", None)
    env.pop("SDL_JOYSTICK_DEVICE", None)
    env.setdefault("DISPLAY", ":1")
    if Path("/tmp/kaggle-game-dev-bench/nvidia-Xauthority").is_file():
        env["XAUTHORITY"] = "/tmp/kaggle-game-dev-bench/nvidia-Xauthority"
    elif (HOME / ".Xauthority").is_file():
        env["XAUTHORITY"] = str(HOME / ".Xauthority")

    profile = HOME / ".config" / "7bz-browser"
    try:
        profile.mkdir(parents=True, exist_ok=True)
    except Exception:
        profile = Path("/tmp/7bz-browser")
        profile.mkdir(parents=True, exist_ok=True)

    args = [binary]
    if "chromium" in Path(binary).name or "chrome" in Path(binary).name:
        args += [
            f"--user-data-dir={profile}",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--ozone-platform=x11",
            "--start-maximized",
            "--disable-features=Translate",
            "--disable-breakpad",
            "--test-type",
        ]
    args += [url]

    log_dir = Path("/tmp/kaggle-game-dev-bench/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        log_file = (log_dir / "browser.log").open("a")
    except Exception:
        log_file = open("/tmp/browser.log", "a")

    proc = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                            stdout=log_file, stderr=subprocess.STDOUT,
                            start_new_session=True)
    time.sleep(0.3)
    if proc.poll() is not None and proc.returncode != 0:
        try:
            err = Path("/tmp/browser.log").read_text()[-300:] if not (log_dir / "browser.log").exists() else (log_dir / "browser.log").read_text()[-300:]
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
        self.detail = "Paste a direct HTTPS download URL (Google Drive, Mega, Direct link)..."
        self._lock = threading.Lock()

    def start(self, source):
        source = source.strip()
        parsed = urlparse(source)
        torrent_file = Path(source).expanduser()

        if parsed.scheme == "magnet" or (torrent_file.is_file() and torrent_file.suffix.lower() == ".torrent"):
            raise ValueError("Torrent / P2P traffic is blocked on cloud platforms to prevent provider bans. Please use direct HTTPS links or the built-in browser.")

        if parsed.scheme not in ("https", "http"):
            raise ValueError("Enter a direct HTTP(S) download URL.")
        if not shutil.which("aria2c"):
            raise RuntimeError("aria2 is not installed. Run setup.sh again.")
        with self._lock:
            if self.proc and self.proc.poll() is None:
                raise RuntimeError("A download is already in progress.")
            DOWNLOADS.mkdir(parents=True, exist_ok=True)
            cmd = ["aria2c", "--dir", str(DOWNLOADS), "--summary-interval=1",
                   "--max-connection-per-server=8", "--split=8", "--min-split-size=1M", source]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1, start_new_session=True)
            self.state = "Downloading"
            self.source = source
            self.percent = 0.0
            self.speed = ""
            self.eta = ""
            self.detail = f"Connecting: {source}"
            proc = self.proc
        threading.Thread(target=self._watch, args=(proc,), daemon=True).start()

    def _watch(self, proc):
        pattern = re.compile(r"\[#\w+\s+(?P<pct>\d+)%.*?DL:(?P<spd>[\w/.]+)(?:\s+ETA:(?P<eta>[\w]+))?\]")
        last_line = ""
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            last_line = line
            m = pattern.search(line)
            with self._lock:
                if m:
                    self.percent = float(m.group("pct"))
                    self.speed = m.group("spd")
                    self.eta = m.group("eta") or ""
                    self.detail = f"{self.percent:.0f}% @ {self.speed}" + (f" (ETA {self.eta})" if self.eta else "")
                elif line:
                    self.detail = line[-80:]
        code = proc.wait()
        with self._lock:
            if self.proc is proc:
                if code == 0:
                    self.state = "Complete"
                    self.percent = 100.0
                    self.detail = "Download finished. Saved in /home/gamer/Downloads."
                else:
                    self.state = f"Failed ({code})"
                    self.detail = f"Download ended with code {code}: {last_line[-60:]}"
                self.proc = None

    def cancel(self):
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                return False
            self.proc.terminate()
            self.state = "Stopped"
            self.detail = "Download stopped."
            return True


class ExtractionManager:
    """Extracts archives (.rar, .zip, .7z, .tar, etc.) with queue and multipart resolution."""

    def __init__(self):
        self.proc = None
        self.state = "Idle"
        self.current_archive = ""
        self.target_dir = ""
        self.detail = "No active extraction."
        self.progress_index = 0
        self.total_count = 0
        self._cancel_flag = threading.Event()
        self._lock = threading.Lock()

    def is_busy(self) -> bool:
        with self._lock:
            return self.proc is not None and self.proc.poll() is None

    def extract(self, archive_paths: Union[str, Path, Iterable[Union[str, Path]]], dest_dir: Optional[Union[str, Path]] = None):
        if isinstance(archive_paths, (str, Path)):
            raw_list = [Path(archive_paths)]
        else:
            raw_list = [Path(p) for p in archive_paths]

        items = normalize_archive_list(raw_list)
        if not items:
            raise ValueError("No valid archive files selected for extraction.")

        with self._lock:
            if self.proc and self.proc.poll() is None:
                raise RuntimeError("An extraction is already in progress.")
            self._cancel_flag.clear()
            self.state = "Starting"
            self.detail = f"Queued {len(items)} archive(s)..."

        threading.Thread(target=self._run_queue, args=(items, dest_dir), daemon=True).start()

    def _run_queue(self, items: List[Path], dest_dir: Optional[Union[str, Path]]):
        self.total_count = len(items)

        for idx, archive in enumerate(items, 1):
            if self._cancel_flag.is_set():
                with self._lock:
                    self.state = "Stopped"
                    self.detail = "Extraction cancelled by user."
                    self.proc = None
                return

            clean_stem = get_archive_base_name(archive)
            dest = Path(dest_dir).expanduser().resolve() if dest_dir else archive.parent / clean_stem
            dest.mkdir(parents=True, exist_ok=True)

            with self._lock:
                self.progress_index = idx
                self.current_archive = archive.name
                self.target_dir = str(dest)
                self.state = f"Extracting ({idx}/{self.total_count})" if self.total_count > 1 else "Extracting"
                self.detail = f"Preparing {archive.name} -> {dest.name}/..."

            # Build command
            if shutil.which("7z"):
                cmd = ["7z", "x", "-y", f"-o{dest}", str(archive)]
            elif shutil.which("unrar") and (archive.suffix.lower() == ".rar" or ".r" in archive.suffix.lower()):
                cmd = ["unrar", "x", "-o+", str(archive), str(dest)]
            elif shutil.which("unzip") and archive.suffix.lower() == ".zip":
                cmd = ["unzip", "-o", str(archive), "-d", str(dest)]
            elif shutil.which("tar") and (archive.suffix.lower() in (".tar", ".gz", ".xz", ".bz2", ".zst") or ".tar." in archive.name.lower()):
                cmd = ["tar", "-xf", str(archive), "-C", str(dest)]
            else:
                try:
                    shutil.unpack_archive(str(archive), str(dest))
                    with self._lock:
                        self.detail = f"Extracted {archive.name} -> {dest.name}/"
                    continue
                except Exception as exc:
                    with self._lock:
                        self.state = f"Failed ({idx}/{self.total_count})"
                        self.detail = f"Failed unpacking {archive.name}: {exc}"
                        self.proc = None
                    return

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True
                )
                with self._lock:
                    self.proc = proc
            except Exception as exc:
                with self._lock:
                    self.state = f"Failed ({idx}/{self.total_count})"
                    self.detail = f"Could not start tool: {exc}"
                    self.proc = None
                return

            last_line = ""
            for line in proc.stdout:
                line = line.strip()
                if line:
                    last_line = line
                    with self._lock:
                        prefix = f"[{idx}/{self.total_count}] " if self.total_count > 1 else ""
                        self.detail = f"{prefix}{line[-70:]}"
                if self._cancel_flag.is_set():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break

            code = proc.wait()
            if self._cancel_flag.is_set():
                with self._lock:
                    self.state = "Stopped"
                    self.detail = "Extraction cancelled."
                    self.proc = None
                return

            if code != 0:
                with self._lock:
                    self.state = f"Failed ({idx}/{self.total_count})"
                    self.detail = f"Error extracting {archive.name} (code {code}): {last_line[-50:]}"
                    self.proc = None
                return

        with self._lock:
            self.state = "Complete"
            if self.total_count > 1:
                self.detail = f"Extracted all {self.total_count} archive(s) successfully!"
            else:
                self.detail = f"Extracted {items[0].name} successfully to {dest.name}/"
            self.proc = None

    def cancel(self):
        with self._lock:
            self._cancel_flag.set()
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
                self.state = "Stopped"
                return True
            return False


def get_clipboard_text() -> str:
    """Read clipboard text reliably across X11, Selkies, xclip, xsel, and Tkinter."""
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":1")
    if Path("/tmp/kaggle-game-dev-bench/nvidia-Xauthority").is_file():
        env["XAUTHORITY"] = "/tmp/kaggle-game-dev-bench/nvidia-Xauthority"

    # 1. Try xclip (handles UTF8_STRING and multiple selections)
    for sel in ("clipboard", "primary"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", sel, "-o"],
                capture_output=True, text=True, timeout=1.5,
                env=env
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    # 2. Try xsel
    for flag in ("--clipboard", "--primary"):
        try:
            res = subprocess.run(
                ["xsel", flag, "--output"],
                capture_output=True, text=True, timeout=1.5,
                env=env
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    # 3. Try tkinter with UTF8_STRING then fallback to standard STRING
    try:
        import tkinter
        t = tkinter.Tk()
        t.withdraw()
        val = ""
        for sel in ("CLIPBOARD", "PRIMARY"):
            for typ in ("UTF8_STRING", "STRING"):
                try:
                    val = t.selection_get(selection=sel, type=typ)
                    if val.strip():
                        break
                except Exception:
                    pass
            if val.strip():
                break
        if not val.strip():
            try:
                val = t.clipboard_get()
            except Exception:
                pass
        t.destroy()
        if val.strip():
            return val.strip()
    except Exception:
        pass

    return ""


def set_clipboard_text(text: str) -> bool:
    """Set X11 clipboard text using xclip, xsel, and tkinter."""
    success = False
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":1")
    if Path("/tmp/kaggle-game-dev-bench/nvidia-Xauthority").is_file():
        env["XAUTHORITY"] = "/tmp/kaggle-game-dev-bench/nvidia-Xauthority"

    # 1. Try xclip
    try:
        p = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
            env=env
        )
        p.communicate(input=text.encode("utf-8"), timeout=1.5)
        if p.returncode == 0:
            success = True
    except Exception:
        pass

    # 2. Try xsel
    try:
        p = subprocess.Popen(
            ["xsel", "--clipboard", "--input"],
            stdin=subprocess.PIPE,
            env=env
        )
        p.communicate(input=text.encode("utf-8"), timeout=1.5)
        if p.returncode == 0:
            success = True
    except Exception:
        pass

    # 3. Try tkinter
    try:
        import tkinter
        t = tkinter.Tk()
        t.withdraw()
        t.clipboard_clear()
        t.clipboard_append(text)
        t.update()
        t.destroy()
        success = True
    except Exception:
        pass

    return success

