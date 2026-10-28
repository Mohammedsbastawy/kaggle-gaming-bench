"""Game Catalog and Epic Games Storefront Integration for 7BZ Cloud Gaming.

Integrates directly with Legendary and Heroic metadata without separate windows:
- Queries official Epic user account and cloud library (117+ owned titles).
- Queries installed games (Wolfenstein: The New Order, etc.).
- Asynchronously caches and renders official Epic Games CDN artwork (DieselGameBox & DieselGameBoxTall).
- Discovers local standalone builds and development scripts.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request

try:
    import pygame
except ImportError:
    pygame = None

HOME = Path(os.environ.get("KAGGLE_GAMER_HOME", "/home/gamer"))
BUILDS = Path(os.environ.get("GAME_BUILDS_DIR", "/tmp/game-builds"))
CACHE_DIR = HOME / ".cache" / "7bz-dev-cloud-game" / "artwork"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory surface cache: (cache_key, target_w, target_h) -> pygame.Surface
_surface_cache: Dict[Tuple[str, int, int], Any] = {}
_download_queue = set()
_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="art_downloader")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def get_epic_user() -> Dict[str, Any]:
    """Return Epic account username and login details."""
    candidates = (
        HOME / ".config" / "legendary" / "user.json",
        HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "user.json",
        Path("/root/.config/legendary/user.json"),
    )
    for path in candidates:
        data = _read_json(path)
        if isinstance(data, dict) and data.get("displayName"):
            return {
                "displayName": data["displayName"],
                "accountId": data.get("account_id", ""),
                "status": "Connected",
                "is_authenticated": True
            }
    return {
        "displayName": "Not Logged In",
        "accountId": "",
        "status": "Disconnected",
        "is_authenticated": False
    }


def login_legendary(auth_code: str) -> Tuple[bool, str]:
    """Authenticates legendary with Epic Games using an authorization code or sid."""
    auth_code = auth_code.strip().strip('"').strip("'")
    if "authorizationCode" in auth_code:
        try:
            data = json.loads(auth_code)
            auth_code = data.get("authorizationCode", auth_code)
        except Exception:
            pass
    if "code=" in auth_code:
        auth_code = auth_code.split("code=")[-1].split("&")[0]

    is_root = (os.getuid() == 0) if hasattr(os, "getuid") else False
    prefix = ["runuser", "-u", "gamer", "--"] if is_root else []

    try:
        res = subprocess.run(
            prefix + ["legendary", "auth", "--code", auth_code],
            capture_output=True,
            text=True,
            timeout=45,
            env=os.environ.copy()
        )
        output = res.stdout + res.stderr
        if res.returncode == 0 or "Successfully" in output or "Logged in" in output:
            subprocess.run(prefix + ["legendary", "list-games"], capture_output=True, timeout=60, env=os.environ.copy())
            return True, "Successfully logged in to Epic Games!"
        return False, output.strip()[:120] if output.strip() else "Authentication failed."
    except Exception as exc:
        return False, str(exc)[:100]


def sync_legendary_library() -> Tuple[bool, str]:
    """Sync owned games metadata via legendary list-games."""
    is_root = (os.getuid() == 0) if hasattr(os, "getuid") else False
    prefix = ["runuser", "-u", "gamer", "--"] if is_root else []
    try:
        res = subprocess.run(
            prefix + ["legendary", "list-games"],
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy()
        )
        return res.returncode == 0, res.stdout + res.stderr
    except Exception as exc:
        return False, str(exc)


def _legendary_metadata(app_name: str) -> Dict[str, Any]:
    candidates = (
        HOME / ".config" / "legendary" / "metadata" / f"{app_name}.json",
        HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "metadata" / f"{app_name}.json",
    )
    for path in candidates:
        data = _read_json(path)
        if isinstance(data, dict):
            return data
    return {}


def _extract_images(metadata_dict: Dict[str, Any]) -> Tuple[str, str]:
    """Return (wide_url, tall_url) from Epic metadata."""
    meta = metadata_dict.get("metadata") or metadata_dict
    images = meta.get("keyImages") or meta.get("key_images") or []
    if not isinstance(images, list):
        return "", ""

    wide_url = ""
    tall_url = ""

    # Priority for wide (Hero banner)
    for pref in ("DieselGameBox", "DieselGameBoxWide", "OfferImageWide", "Featured", "Thumbnail"):
        for img in images:
            if isinstance(img, dict) and img.get("type") == pref and img.get("url"):
                wide_url = img["url"]
                break
        if wide_url:
            break

    # Priority for tall (Poster cards)
    for pref in ("DieselGameBoxTall", "OfferImageTall", "DieselStoreFrontTall"):
        for img in images:
            if isinstance(img, dict) and img.get("type") == pref and img.get("url"):
                tall_url = img["url"]
                break
        if tall_url:
            break

    if not wide_url and tall_url:
        wide_url = tall_url
    if not tall_url and wide_url:
        tall_url = wide_url

    return wide_url, tall_url


def cleanup_stale_installed_record(app_name: str):
    """Remove a stale or uninstalled game record from both Legendary and Heroic installed.json files."""
    candidates = (
        HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "installed.json",
        HOME / ".config" / "legendary" / "installed.json",
    )
    for path in candidates:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and app_name in data:
                    del data[app_name]
                    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass


def legendary_installed_games() -> List[Dict[str, Any]]:
    """Return all verified installed Epic games that actually exist on disk."""
    candidates = (
        HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "installed.json",
        HOME / ".config" / "legendary" / "installed.json",
        Path("/root/.config/heroic/legendaryConfig/legendary/installed.json"),
        Path("/root/.config/legendary/installed.json"),
    )
    installed_dict: Dict[str, Any] = {}
    for path in candidates:
        raw = _read_json(path)
        if isinstance(raw, dict):
            installed_dict.update(raw)

    games: List[Dict[str, Any]] = []
    for app_name, record in list(installed_dict.items()):
        if not isinstance(record, dict):
            continue

        raw_ip = record.get("install_path") or f"/home/gamer/Games/{app_name}"
        install_path = Path(str(raw_ip))
        raw_exe = record.get("executable") or ""

        # Verification check: The game directory MUST exist and contain game files
        if not install_path.is_dir():
            cleanup_stale_installed_record(str(app_name))
            continue

        try:
            has_files = any(install_path.iterdir())
        except OSError:
            has_files = False

        if not has_files:
            cleanup_stale_installed_record(str(app_name))
            continue

        # If an executable is specified or expected, ensure at least one .exe exists
        if raw_exe:
            exe_target = install_path / raw_exe
            if not exe_target.is_file():
                # Check recursive search
                found = list(install_path.rglob("*.exe"))
                if not found:
                    cleanup_stale_installed_record(str(app_name))
                    continue
                else:
                    raw_exe = found[0].name
        else:
            found = list(install_path.rglob("*.exe"))
            if not found:
                cleanup_stale_installed_record(str(app_name))
                continue
            raw_exe = found[0].name

        metadata = _legendary_metadata(str(app_name))
        meta_info = metadata.get("metadata", {})
        title = str(record.get("title") or metadata.get("app_title") or app_name)
        wide_url, tall_url = _extract_images(metadata)

        size_bytes = record.get("install_size") or 0
        size_str = f"{size_bytes / (1024**3):.1f} GiB" if size_bytes > 0 else "Installed"

        games.append({
            "id": f"epic:{app_name}",
            "app_name": str(app_name),
            "title": title,
            "store": "Epic Games",
            "is_installed": True,
            "status": "Installed",
            "install_path": str(install_path),
            "executable": str(raw_exe),
            "size": size_str,
            "version": str(record.get("version") or "1.0"),
            "developer": meta_info.get("developer") or "Epic Games",
            "publisher": meta_info.get("publisher") or "Epic Games",
            "wide_art": wide_url,
            "tall_art": tall_url,
            "action": "legendary",
        })
    return games


def epic_library_games() -> List[Dict[str, Any]]:
    """Return the complete cloud library of owned Epic games."""
    installed = {g["app_name"]: g for g in legendary_installed_games()}
    meta_dir = HOME / ".config" / "legendary" / "metadata"
    heroic_meta_dir = HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "metadata"

    seen_apps = set()
    library: List[Dict[str, Any]] = []

    # Put installed games first
    for g in installed.values():
        library.append(g)
        seen_apps.add(g["app_name"])

    # Scan metadata files for owned games
    search_dirs = [
        meta_dir,
        heroic_meta_dir,
        Path("/root/.config/legendary/metadata"),
        Path("/root/.config/heroic/legendaryConfig/legendary/metadata"),
    ]
    for mdir in search_dirs:
        if not mdir.is_dir():
            continue
        for p in sorted(mdir.glob("*.json")):
            app_name = p.stem
            if app_name in seen_apps:
                continue
            seen_apps.add(app_name)

            data = _read_json(p)
            if not isinstance(data, dict):
                continue

            title = data.get("app_title", "")
            if not title or title.startswith("[REDACTED]") or title.lower().startswith("ue4"):
                continue

            meta_info = data.get("metadata", {})
            wide_url, tall_url = _extract_images(data)

            # Skip items without any artwork
            if not wide_url and not tall_url:
                continue

            library.append({
                "id": f"epic:{app_name}",
                "app_name": app_name,
                "title": title,
                "store": "Epic Games",
                "is_installed": False,
                "status": "Ready to Install",
                "install_path": f"/home/gamer/Games/{title.replace(' ', '')}",
                "executable": "Auto",
                "size": "Available in Cloud",
                "version": "Latest",
                "developer": meta_info.get("developer") or "Epic Games",
                "publisher": meta_info.get("publisher") or "Epic Games",
                "wide_art": wide_url,
                "tall_art": tall_url,
                "action": "legendary",
            })

    # Sort remaining non-installed games alphabetically
    installed_count = len(installed)
    library[installed_count:] = sorted(library[installed_count:], key=lambda x: x["title"].lower())
    return library


def local_games() -> List[Dict[str, Any]]:
    """Return local custom builds, development binaries, and bench tools."""
    items: List[Dict[str, Any]] = []

    # 1. Custom build directory
    if BUILDS.is_dir():
        for path in sorted(BUILDS.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file() and (os.access(path, os.X_OK) or path.suffix.lower() in (".sh", ".appimage", ".x86_64", ".bin", ".exe")):
                items.append({
                    "id": f"build:{path.name}",
                    "app_name": path.name,
                    "title": path.stem.replace("_", " ").title(),
                    "store": "Local Build",
                    "is_installed": True,
                    "status": "Local Binary",
                    "install_path": str(path),
                    "executable": path.name,
                    "size": f"{path.stat().st_size / (1024**2):.1f} MB",
                    "version": "1.0-dev",
                    "developer": "Local Development",
                    "publisher": "7BZ Bench",
                    "wide_art": "",
                    "tall_art": "",
                    "action": "build",
                })

    # 2. Check /home/gamer/Games for installed standalone games or Wine directories
    games_dir = HOME / "Games"
    if games_dir.is_dir():
        for sub in sorted(games_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("."):
                exes = list(sub.glob("*.exe")) + list(sub.glob("*.sh"))
                exe_name = exes[0].name if exes else "Main"
                items.append({
                    "id": f"local:{sub.name}",
                    "app_name": sub.name,
                    "title": sub.name.replace("_", " ").title(),
                    "store": "Local Game",
                    "is_installed": True,
                    "status": "Standalone Directory",
                    "install_path": str(sub),
                    "executable": exe_name,
                    "size": "Local Disk",
                    "version": "Direct",
                    "developer": "Custom / Wine",
                    "publisher": "Local User",
                    "wide_art": "",
                    "tall_art": "",
                    "action": "build",
                })

    # 3. Built-in Bench Utilities for testing and development
    bench_dir = Path("/tmp/kaggle-game-dev-bench")
    diag_tools = [
        ("GPU 3D Diagnostic", "test_gpu_runtime.py", "Tesla T4 3D / DXVK / Vulkan probe"),
        ("idTech 5 / OpenGL Probe", "test_idtech5.py", "OpenGL 4.5 Compatibility profile verification"),
        ("Direct Stream Inspector", "run_inspection.py", "Selkies low-latency WebRTC metrics test"),
    ]
    for title, script_name, desc in diag_tools:
        script_path = bench_dir / script_name
        items.append({
            "id": f"bench:{script_name}",
            "app_name": script_name,
            "title": title,
            "store": "Bench Tool",
            "is_installed": True,
            "status": "Ready",
            "install_path": str(script_path),
            "executable": script_name,
            "size": "System Script",
            "version": "2.0-bench",
            "developer": "7BZ Cloud Gaming",
            "publisher": desc,
            "wide_art": "",
            "tall_art": "",
            "action": "build",
        })

    return items


def _download_worker(app_name: str, url: str, kind: str):
    """Download image in background thread and cache to disk."""
    if not url:
        return
    ext = ".png" if ".png" in url.lower() else ".jpg"
    dst = CACHE_DIR / f"{app_name}_{kind}{ext}"
    if dst.is_file() and dst.stat().st_size > 1000:
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=12) as resp, dst.open("wb") as out:
            out.write(resp.read())
    except Exception:
        pass
    finally:
        _download_queue.discard((app_name, kind))
        # Invalidate in-memory cache so next frame immediately loads official artwork
        for k in list(_surface_cache.keys()):
            if k[0].startswith(f"{app_name}_{kind}"):
                _surface_cache.pop(k, None)


def _draw_fallback_card(title: str, store: str, target_w: int, target_h: int) -> Any:
    """Procedurally render a sleek cybernetic fallback poster."""
    if not pygame:
        return None
    surf = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (16, 22, 34), (0, 0, target_w, target_h), border_radius=10)
    pygame.draw.rect(surf, (28, 40, 60), (0, 0, target_w, target_h), width=1, border_radius=10)

    # Accent top bar
    pygame.draw.rect(surf, (0, 240, 255), (10, 10, target_w - 20, 3), border_radius=2)

    try:
        font_big = pygame.font.SysFont("Liberation Sans", 24, bold=True)
        font_txt = pygame.font.SysFont("Liberation Sans", 11, bold=True)
        font_sub = pygame.font.SysFont("Liberation Sans", 9)

        initials = "".join(w[0] for w in title.split() if w)[:3].upper()
        lbl_init = font_big.render(initials, True, (0, 240, 255))
        surf.blit(lbl_init, (target_w // 2 - lbl_init.get_width() // 2, target_h // 2 - 30))

        clean_title = title if len(title) <= 18 else title[:16] + "..."
        lbl_title = font_txt.render(clean_title, True, (245, 248, 255))
        surf.blit(lbl_title, (target_w // 2 - lbl_title.get_width() // 2, target_h // 2 + 15))

        lbl_store = font_sub.render(store.upper(), True, (130, 145, 170))
        surf.blit(lbl_store, (target_w // 2 - lbl_store.get_width() // 2, target_h // 2 + 32))
    except Exception:
        pass

    return surf


def get_artwork(app_name: str, url: str, kind: str, target_w: int, target_h: int, title: str = "", store: str = "Epic Games") -> Any:
    """Return a cached Pygame surface scaled to target dimensions."""
    if not pygame:
        return None

    cache_key = (f"{app_name}_{kind}", target_w, target_h)
    if cache_key in _surface_cache:
        return _surface_cache[cache_key]

    # Check disk cache
    for ext in (".jpg", ".png", ".jpeg"):
        file_path = CACHE_DIR / f"{app_name}_{kind}{ext}"
        if file_path.is_file() and file_path.stat().st_size > 1000:
            try:
                raw_surf = pygame.image.load(str(file_path))
                scaled = pygame.transform.smoothscale(raw_surf, (target_w, target_h))
                _surface_cache[cache_key] = scaled
                return scaled
            except Exception:
                pass

    # Not cached on disk yet: queue background download
    if url and (app_name, kind) not in _download_queue:
        _download_queue.add((app_name, kind))
        _executor.submit(_download_worker, app_name, url, kind)

    # Return fallback (do not cache in _surface_cache so real image takes over when ready)
    return _draw_fallback_card(title or app_name, store, target_w, target_h)


def pre_cache_top_games():
    """Background task to pre-download artwork for top library titles."""
    games = epic_library_games()
    for g in games[:24]:
        app = g["app_name"]
        if g.get("tall_art") and (app, "tall") not in _download_queue:
            _download_queue.add((app, "tall"))
            _executor.submit(_download_worker, app, g["tall_art"], "tall")
        if g.get("wide_art") and (app, "wide") not in _download_queue:
            _download_queue.add((app, "wide"))
            _executor.submit(_download_worker, app, g["wide_art"], "wide")


def get_catalog() -> Dict[str, List[Dict[str, Any]]]:
    """Helper returning complete structured catalog for dev_launcher."""
    return {
        "epic": epic_library_games(),
        "local": local_games(),
    }


def discover_games() -> List[Dict[str, Any]]:
    """Compatibility alias returning combined list of games for session_control API."""
    return epic_library_games() + local_games()


threading.Thread(target=pre_cache_top_games, daemon=True).start()
