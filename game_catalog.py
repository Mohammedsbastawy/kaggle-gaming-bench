"""Discover games and storefronts for the 7BZ console dashboard."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


HOME = Path(os.environ.get("KAGGLE_GAMER_HOME", "/home/gamer"))
BUILDS = Path(os.environ.get("GAME_BUILDS_DIR", "/tmp/game-builds"))
CACHE = HOME / ".cache" / "7bz-dev-cloud-game"


STOREFRONTS: List[Dict[str, Any]] = [
    {"id": "legendary", "title": "Epic / Legendary", "badge": "EPIC", "color": (50, 56, 70),
     "script": "/tmp/kaggle-game-dev-bench/launch_legendary.sh"},
    {"id": "steam", "title": "Steam", "badge": "STEAM", "color": (24, 83, 122),
     "script": "/tmp/kaggle-game-dev-bench/launch_steam.sh"},
    {"id": "heroic", "title": "Heroic", "badge": "HEROIC", "color": (45, 111, 177),
     "script": "/tmp/kaggle-game-dev-bench/launch_heroic.sh"},
    {"id": "lutris", "title": "Lutris", "badge": "LUTRIS", "color": (225, 123, 44),
     "script": "/tmp/kaggle-game-dev-bench/launch_lutris.sh"},
]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _image_from_metadata(value: Any) -> str:
    """Return the best landscape image URL found in Legendary metadata."""
    if not isinstance(value, dict):
        return ""
    images = value.get("keyImages") or value.get("key_images") or []
    if not isinstance(images, list):
        return ""
    preferred = ("DieselGameBoxWide", "OfferImageWide", "Featured", "Thumbnail")
    for image_type in preferred:
        for entry in images:
            if (isinstance(entry, dict) and entry.get("type") == image_type
                    and isinstance(entry.get("url"), str)):
                return entry["url"]
    return next((entry.get("url", "") for entry in images
                 if isinstance(entry, dict) and entry.get("url")), "")


def _legendary_metadata(app_name: str) -> Dict[str, Any]:
    candidates = (
        HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "metadata" / f"{app_name}.json",
        HOME / ".config" / "legendary" / "metadata" / f"{app_name}.json",
    )
    for path in candidates:
        data = _read_json(path)
        if isinstance(data, dict):
            return data
    return {}


def legendary_games() -> List[Dict[str, Any]]:
    """Return installed Epic games from Heroic's or Legendary's database."""
    candidates = (
        HOME / ".config" / "heroic" / "legendaryConfig" / "legendary" / "installed.json",
        HOME / ".config" / "legendary" / "installed.json",
    )
    raw: Any = None
    for path in candidates:
        raw = _read_json(path)
        if raw:
            break
    if not isinstance(raw, dict):
        return []
    games: List[Dict[str, Any]] = []
    for app_name, record in raw.items():
        if not isinstance(record, dict):
            continue
        metadata = _legendary_metadata(str(app_name))
        title = str(record.get("title") or metadata.get("app_title") or app_name)
        games.append({
            "id": f"epic:{app_name}", "title": title, "store": "Epic Games",
            "status": "Installed", "app_name": str(app_name),
            "install_path": str(record.get("install_path") or record.get("installPath") or ""),
            "art": _image_from_metadata(metadata), "action": "legendary",
            "subtitle": str(record.get("version") or "Ready to play"),
        })
    return games


def _steam_library_paths() -> Iterable[Path]:
    yield HOME / ".steam" / "steam" / "steamapps"
    yield HOME / ".local" / "share" / "Steam" / "steamapps"
    library_file = HOME / ".steam" / "steam" / "steamapps" / "libraryfolders.vdf"
    try:
        for line in library_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if '"path"' in line:
                parts = line.split('"')
                if len(parts) >= 4:
                    yield Path(parts[3].replace("\\\\", "\\")) / "steamapps"
    except OSError:
        return


def steam_games() -> List[Dict[str, Any]]:
    """Return installed Steam games from local app manifests."""
    games: List[Dict[str, Any]] = []
    seen = set()
    for steamapps in _steam_library_paths():
        for manifest in steamapps.glob("appmanifest_*.acf") if steamapps.is_dir() else ():
            text = manifest.read_text(encoding="utf-8", errors="ignore")
            fields: Dict[str, str] = {}
            for line in text.splitlines():
                parts = line.strip().split('"')
                if len(parts) >= 4:
                    fields[parts[1]] = parts[3]
            app_id = fields.get("appid", manifest.stem.removeprefix("appmanifest_"))
            if app_id in seen:
                continue
            seen.add(app_id)
            games.append({
                "id": f"steam:{app_id}", "title": fields.get("name", f"Steam {app_id}"),
                "store": "Steam", "status": "Installed", "app_name": app_id,
                "install_path": str(steamapps / "common" / fields.get("installdir", "")),
                "art": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
                "action": "steam", "subtitle": "Ready in Steam",
            })
    return games


def custom_builds() -> List[Dict[str, Any]]:
    """Return executable custom builds uploaded to the shared build directory."""
    items: List[Dict[str, Any]] = []
    if not BUILDS.is_dir():
        return items
    for path in sorted(BUILDS.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file() and (os.access(path, os.X_OK) or path.suffix.lower() in (".sh", ".appimage", ".x86_64", ".bin")):
            items.append({
                "id": f"build:{path.name}", "title": path.stem, "store": "Custom Build",
                "status": "Ready", "app_name": path.name, "install_path": str(path),
                "art": "", "action": "build", "subtitle": "Uploaded development build",
            })
    return items


def discover_games() -> List[Dict[str, Any]]:
    """Return a stable, title-sorted catalog from every supported local source."""
    games = legendary_games() + steam_games() + custom_builds()
    games.sort(key=lambda item: item["title"].lower())
    return games


def cache_path(item_id: str) -> Path:
    """Return the local artwork path for a catalog item."""
    safe = "".join(ch if ch.isalnum() else "_" for ch in item_id)[:100]
    return CACHE / f"{safe}.img"


def find_game(item_id: str) -> Optional[Dict[str, Any]]:
    """Find one game by its stable catalog identifier."""
    return next((game for game in discover_games() if game["id"] == item_id), None)
