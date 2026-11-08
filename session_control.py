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
                                 "source": source, "started": time.time(),
                                 "input_mode": _get_input_mode()}), encoding="utf-8")


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


def _windows() -> List[Dict[str, Any]]:
    """List switchable windows on the game display, with the dashboard first."""
    try:
        result = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True, timeout=3)
        if result.returncode:
            return []
        active = subprocess.run(["xdotool", "getactivewindow"], capture_output=True,
                                text=True, timeout=2)
        active_id = int(active.stdout.strip()) if active.returncode == 0 else 0
        windows = []
        for line in result.stdout.splitlines():
            parts = line.split(maxsplit=4)
            if len(parts) < 5:
                continue
            window_id, desktop, pid_text, _host, title = parts
            if desktop == "-1" or not title.strip():
                continue
            try:
                pid = int(pid_text)
                numeric_id = int(window_id, 16)
            except ValueError:
                continue
            dashboard = title.strip() in ("7BZ Cloud Gaming", "7BZ Dev Cloud Game")
            windows.append({"id": window_id, "pid": pid, "title": title.strip()[:100],
                            "dashboard": dashboard, "active": numeric_id == active_id})
        return sorted(windows, key=lambda item: (not item["dashboard"], item["title"].lower()))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []


def _focus_window(window_id: str) -> bool:
    result = subprocess.run(["wmctrl", "-ia", window_id], capture_output=True,
                            text=True, timeout=3)
    return result.returncode == 0


def _focus_dashboard() -> bool:
    dashboard = next((item for item in _windows() if item["dashboard"]), None)
    return bool(dashboard and _focus_window(dashboard["id"]))


def _owned_process(pid: int) -> bool:
    """Confirm a recorded process exists and belongs to this service's user."""
    try:
        return Path(f"/proc/{pid}").stat().st_uid == os.getuid()
    except OSError:
        return False


def _game_process(pid: int) -> bool:
    if not _owned_process(pid):
        return False
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", errors="replace").lower()
        return any(marker in command for marker in (".exe", "wine", "proton", "gpu_runtime.py"))
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
    groups = set()
    if pid > 1 and pgid > 1 and _owned_process(pid):
        groups.add(pgid)
    for item in _windows():
        window_pid = item["pid"]
        if item["dashboard"] or not _game_process(window_pid):
            continue
        try:
            group = os.getpgid(window_pid)
            if group != os.getpgrp():
                groups.add(group)
        except ProcessLookupError:
            pass
    for group in groups:
        stopped = await _end_group(group, signal.SIGTERM) or stopped
    for _ in range(12):
        if not any(_game_process(item["pid"]) for item in _windows() if not item["dashboard"]):
            break
        await asyncio.sleep(0.25)
    for group in groups:
        group_alive = False
        try:
            os.killpg(group, 0)
            group_alive = True
        except ProcessLookupError:
            pass
        if group_alive and (group == pgid or any(
                _game_process(item["pid"]) for item in _windows() if not item["dashboard"])):
            await _end_group(group, signal.SIGKILL)
    clear_active_game(pid)
    restored = _focus_dashboard()
    return {"ok": True, "stopped": stopped, "restored": restored,
            "message": "Game stopped. Dashboard restored." if restored else "Game stopped; dashboard window unavailable."}


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "7bz-control"})


async def status(_request: web.Request) -> web.Response:
    data = _state()
    data["windows"] = _windows()
    if not data["running"]:
        game = next((item for item in data["windows"]
                     if not item["dashboard"] and _game_process(item["pid"])), None)
        if game:
            data.update({"running": True, "title": game["title"]})
    current_mode = _get_input_mode()
    data["current_input_mode"] = current_mode
    if data["running"]:
        recorded = data.get("input_mode")
        if recorded:
            data["input_mode_needs_restart"] = recorded != current_mode
        else:
            try:
                changed = json.loads(INPUT_MODE_FILE.read_text(encoding="utf-8")).get("updated", 0)
                data["input_mode_needs_restart"] = changed > float(data.get("started", changed))
            except (OSError, ValueError, TypeError):
                data["input_mode_needs_restart"] = False
    else:
        data["input_mode_needs_restart"] = False
    return web.json_response(data)


async def windows_handler(_request: web.Request) -> web.Response:
    return web.json_response({"windows": _windows()})


async def activate(request: web.Request) -> web.Response:
    if request.headers.get("X-7BZ-Action") != "hud":
        raise web.HTTPForbidden(text="Missing HUD action header")
    try:
        window_id = (await request.json()).get("id", "")
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="Invalid window")
    if not isinstance(window_id, str) or not any(item["id"] == window_id for item in _windows()):
        raise web.HTTPNotFound(text="Window no longer exists")
    if not _focus_window(window_id):
        raise web.HTTPServiceUnavailable(text="Could not switch window")
    return web.json_response({"ok": True})


async def catalog(_request: web.Request) -> web.Response:
    return web.json_response({"games": discover_games()})


INPUT_MODE_FILE = BENCH / "input-mode.json"


def _get_input_mode() -> str:
    try:
        if INPUT_MODE_FILE.is_file():
            data = json.loads(INPUT_MODE_FILE.read_text(encoding="utf-8"))
            return data.get("mode", "gamepad")
    except Exception:
        pass
    return "gamepad"


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


CONTROLLER_KEYS = {"Escape", "Return", "BackSpace", "Tab", "Up", "Down", "Left", "Right", "Page_Up", "Page_Down", "space", "Home", "End"}


async def controller_action(request: web.Request) -> web.Response:
    """Send bounded controller UI actions to the existing X desktop."""
    if request.headers.get("X-7BZ-Action") != "hud":
        raise web.HTTPForbidden(text="Missing HUD action header")
    try:
        data = await request.json()
        action = data.get("action")
        if action == "move":
            x, y = float(data["x"]), float(data["y"])
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("Coordinates out of range")
            geometry = subprocess.check_output(["xdotool", "getdisplaygeometry"], text=True, timeout=2).split()
            width, height = int(geometry[0]), int(geometry[1])
            command = ["xdotool", "mousemove", str(round(x * (width - 1))), str(round(y * (height - 1)))]
        elif action == "click" and data.get("button") in (1, 3):
            command = ["xdotool", "click", str(data["button"])]
        elif action == "scroll" and data.get("direction") in ("up", "down"):
            command = ["xdotool", "click", "4" if data["direction"] == "up" else "5"]
        elif action == "key" and data.get("key") in CONTROLLER_KEYS:
            command = ["xdotool", "key", "--clearmodifiers", data["key"]]
        elif action == "text" and isinstance(data.get("text"), str) and len(data["text"]) == 1 and data["text"].isprintable():
            command = ["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", data["text"]]
        elif action == "home":
            if not _focus_dashboard():
                raise RuntimeError("7BZ dashboard window is unavailable")
            return web.json_response({"ok": True})
        else:
            raise ValueError("Unknown controller action")
        result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, timeout=3)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Desktop input failed")
        return web.json_response({"ok": True})
    except (ValueError, TypeError, KeyError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        raise web.HTTPServiceUnavailable(text=str(exc)) from exc


def main() -> None:
    """Serve narrow session actions on the loopback-only control port."""
    app = web.Application(client_max_size=16 * 1024)
    app.add_routes([web.get("/health", health), web.get("/status", status),
                    web.get("/catalog", catalog), web.get("/gpus", gpus_handler),
                    web.get("/windows", windows_handler), web.post("/activate", activate),
                    web.post("/reset", reset),
                    web.get("/input-mode", input_mode_get), web.post("/input-mode", input_mode_post),
                    web.post("/controller", controller_action)])
    web.run_app(app, host="127.0.0.1", port=PORT, access_log=None)


if __name__ == "__main__":
    main()
