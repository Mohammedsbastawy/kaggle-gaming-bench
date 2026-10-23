"""Local control service for the 7BZ streaming HUD and dashboard."""
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Dict

from aiohttp import web

from game_catalog import discover_games


BENCH = Path("/tmp/kaggle-game-dev-bench")
STATE = BENCH / "active-game.json"
PORT = int(os.environ.get("SEVEN_BZ_CONTROL_PORT", "8766"))


def write_active_game(pid: int, pgid: int, title: str, source: str) -> None:
    """Record a dashboard-launched process after validating its identity."""
    STATE.write_text(json.dumps({"pid": pid, "pgid": pgid, "title": title,
                                 "source": source, "started": time.time()}), encoding="utf-8")


def clear_active_game(pid: int = 0) -> None:
    """Remove the active record when it still belongs to the given process."""
    try:
        current = json.loads(STATE.read_text(encoding="utf-8"))
        if not pid or int(current.get("pid", 0)) == pid:
            STATE.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError):
        STATE.unlink(missing_ok=True)


def _state() -> Dict[str, Any]:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
        if pid > 1 and Path(f"/proc/{pid}").exists():
            data["running"] = True
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {"running": False, "title": "No active game"}


def _owned_process(pid: int) -> bool:
    """Confirm a recorded process exists and belongs to this service's user."""
    try:
        return Path(f"/proc/{pid}").stat().st_uid == os.getuid()
    except OSError:
        return False


async def _end_group(pgid: int, sig: signal.Signals) -> bool:
    try:
        os.killpg(pgid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


async def reset_session() -> Dict[str, Any]:
    """Stop the tracked game group, Wine servers, and restore the dashboard."""
    state = _state()
    stopped = False
    pid = int(state.get("pid", 0) or 0)
    pgid = int(state.get("pgid", 0) or 0)
    if pid > 1 and pgid > 1 and _owned_process(pid):
        stopped = await _end_group(pgid, signal.SIGTERM)
        for _ in range(12):
            if not Path(f"/proc/{pid}").exists():
                break
            await asyncio.sleep(0.25)
        if Path(f"/proc/{pid}").exists():
            await _end_group(pgid, signal.SIGKILL)
    clear_active_game(pid)
    subprocess.run(["wineserver", "-k"], check=False, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=5)
    subprocess.run(["wmctrl", "-a", "7BZ Dev Cloud Game"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    return {"ok": True, "stopped": stopped, "message": "Game stopped. Dashboard restored."}


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "7bz-control"})


async def status(_request: web.Request) -> web.Response:
    return web.json_response(_state())


async def catalog(_request: web.Request) -> web.Response:
    return web.json_response({"games": discover_games()})


async def reset(request: web.Request) -> web.Response:
    if request.headers.get("X-7BZ-Action") != "hud":
        raise web.HTTPForbidden(text="Missing HUD action header")
    return web.json_response(await reset_session())


def main() -> None:
    """Serve narrow session actions on the loopback-only control port."""
    app = web.Application(client_max_size=16 * 1024)
    app.add_routes([web.get("/health", health), web.get("/status", status),
                    web.get("/catalog", catalog), web.post("/reset", reset)])
    web.run_app(app, host="127.0.0.1", port=PORT, access_log=None)


if __name__ == "__main__":
    main()
