"""Local control service for the 7BZ streaming HUD and dashboard."""
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Dict, List

from aiohttp import web

from game_catalog import discover_games


BENCH = Path("/tmp/kaggle-game-dev-bench")
STATE = BENCH / "active-game.json"
PORT = int(os.environ.get("SEVEN_BZ_CONTROL_PORT", "8766"))


def get_gpu_metrics() -> List[Dict[str, Any]]:
    """Query live metrics for all available NVIDIA GPUs."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=2
        )
        if res.returncode != 0:
            return []
        gpus = []
        for line in res.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx = int(parts[0])
                role = "Render (Game)" if idx == 0 else "Encode (Stream)"
                gpus.append({
                    "index": idx,
                    "name": parts[1],
                    "role": role,
                    "utilization": int(parts[2]),
                    "memory_used": int(parts[3]),
                    "memory_total": int(parts[4]),
                })
        return gpus
    except Exception:
        return []


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
    state_data: Dict[str, Any] = {"running": False, "title": "No active game"}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
        if pid > 1 and Path(f"/proc/{pid}").exists():
            data["running"] = True
            state_data = data
    except (OSError, ValueError, TypeError):
        pass
    state_data["gpus"] = get_gpu_metrics()
    return state_data


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


INPUT_MODE_FILE = BENCH / "input-mode.json"


def _get_input_mode() -> str:
    try:
        if INPUT_MODE_FILE.is_file():
            data = json.loads(INPUT_MODE_FILE.read_text(encoding="utf-8"))
            return data.get("mode", "mouse_keyboard")
    except Exception:
        pass
    return "mouse_keyboard"


def _set_input_mode(mode: str) -> str:
    valid = "gamepad" if mode == "gamepad" else "mouse_keyboard"
    try:
        INPUT_MODE_FILE.write_text(json.dumps({"mode": valid, "updated": time.time()}), encoding="utf-8")
    except Exception:
        pass
    return valid


async def input_mode_get(_request: web.Request) -> web.Response:
    return web.json_response({"mode": _get_input_mode()})


async def input_mode_post(request: web.Request) -> web.Response:
    if request.headers.get("X-7BZ-Action") != "hud":
        raise web.HTTPForbidden(text="Missing HUD action header")
    try:
        body = await request.json()
        target_mode = body.get("mode", "")
    except Exception:
        target_mode = ""
    if not target_mode:
        current = _get_input_mode()
        target_mode = "gamepad" if current == "mouse_keyboard" else "mouse_keyboard"
    new_mode = _set_input_mode(target_mode)
    return web.json_response({"ok": True, "mode": new_mode, "message": f"Input mode set to {new_mode}"})


async def reset(request: web.Request) -> web.Response:
    if request.headers.get("X-7BZ-Action") != "hud":
        raise web.HTTPForbidden(text="Missing HUD action header")
    return web.json_response(await reset_session())


async def gpus_handler(_request: web.Request) -> web.Response:
    return web.json_response({"gpus": get_gpu_metrics()})


def main() -> None:
    """Serve narrow session actions on the loopback-only control port."""
    app = web.Application(client_max_size=16 * 1024)
    app.add_routes([web.get("/health", health), web.get("/status", status),
                    web.get("/catalog", catalog), web.get("/gpus", gpus_handler),
                    web.post("/reset", reset),
                    web.get("/input-mode", input_mode_get), web.post("/input-mode", input_mode_post)])
    web.run_app(app, host="127.0.0.1", port=PORT, access_log=None)


if __name__ == "__main__":
    main()
