"""Ten-foot console dashboard for 7BZ Dev Cloud Game."""
import hashlib
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import pygame

from game_catalog import STOREFRONTS, cache_path, discover_games
from session_control import clear_active_game, write_active_game


os.environ["PATH"] = f"/usr/games:/usr/local/bin:/usr/bin:{os.environ.get('PATH', '')}"
BENCH = Path("/tmp/kaggle-game-dev-bench")
LOGS = Path("/home/gamer/logs")
LOGS.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
BG = (7, 10, 20)
PANEL = (16, 22, 39)
PANEL_LIGHT = (24, 33, 56)
TEXT = (244, 247, 255)
MUTED = (150, 162, 188)
CYAN = (72, 215, 255)
VIOLET = (143, 124, 255)
GREEN = (78, 230, 168)
TABS = ("HOME", "LIBRARY", "STORES", "BUILDS")

pygame.init()
pygame.display.set_caption("7BZ Dev Cloud Game")
display = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
screen = pygame.Surface((WIDTH, HEIGHT)).convert()
clock = pygame.time.Clock()
font_logo = pygame.font.SysFont("DejaVu Sans", 27, bold=True)
font_hero = pygame.font.SysFont("DejaVu Sans", 35, bold=True)
font_card = pygame.font.SysFont("DejaVu Sans", 17, bold=True)
font_body = pygame.font.SysFont("DejaVu Sans", 14)
font_small = pygame.font.SysFont("DejaVu Sans", 12)
font_tiny = pygame.font.SysFont("DejaVu Sans", 10, bold=True)


def pulse_server() -> str:
    """Return the active PulseAudio socket for every child process."""
    configured = os.environ.get("PULSE_SERVER", "")
    if configured:
        return configured
    candidates = [Path("/run/user/1000/pulse/native")]
    candidates.extend(Path("/tmp").glob("pulse-*/native"))
    for candidate in candidates:
        if candidate.exists():
            return f"unix:{candidate}"
    return ""


INPUT_MODE_FILE = BENCH / "input-mode.json"


def get_launcher_input_mode() -> str:
    try:
        if INPUT_MODE_FILE.is_file():
            data = json.loads(INPUT_MODE_FILE.read_text(encoding="utf-8"))
            return data.get("mode", "mouse_keyboard")
    except Exception:
        pass
    return "mouse_keyboard"


def toggle_launcher_input_mode() -> str:
    curr = get_launcher_input_mode()
    new_m = "gamepad" if curr == "mouse_keyboard" else "mouse_keyboard"
    try:
        INPUT_MODE_FILE.write_text(json.dumps({"mode": new_m, "updated": time.time()}), encoding="utf-8")
    except Exception:
        pass
    return new_m


def game_env() -> Dict[str, str]:
    """Build the common X11, controller, and PulseAudio environment."""
    env = os.environ.copy()
    env.update(DISPLAY=env.get("DISPLAY", ":0"), HOME="/home/gamer", SDL_AUDIODRIVER="pulse")
    server = pulse_server()
    if server:
        env["PULSE_SERVER"] = server
    mode = get_launcher_input_mode()
    if mode == "mouse_keyboard":
        env.pop("LD_PRELOAD", None)
        env["SDL_JOYSTICK_DEVICE"] = ""
        env["SDL_JOYSTICK_DISABLE_UDEV"] = "1"
        env["WINEDLLOVERRIDES"] = env.get("WINEDLLOVERRIDES", "") + ";winebus.sys=d"
    else:
        env["SELKIES_JS_SOCKET_PATH"] = "/tmp"
        env["SDL_JOYSTICK_DISABLE_UDEV"] = "1"
        env["SDL_JOYSTICK_DEVICE"] = "/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003"
        interposer = "/tmp/kaggle-game-dev-bench/$LIB/selkies_input_interposer.so:/tmp/kaggle-game-dev-bench/$LIB/selkies_fake_udev.so"
        env["LD_PRELOAD"] = os.environ.get("LD_PRELOAD", interposer)
    return env


def wine_runner() -> str:
    candidates = [Path("/home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine"),
                  *Path("/home/gamer/.config/heroic/tools/wine").glob("*/bin/wine"), Path("/usr/bin/wine")]
    return str(next((path for path in candidates if path.is_file()), Path("/usr/bin/wine")))


class Artwork:
    """Download and cache game artwork without blocking the render loop."""

    def __init__(self) -> None:
        self.surfaces: Dict[str, pygame.Surface] = {}
        self.pending = set()

    def get(self, item: Dict[str, Any], size: Tuple[int, int]) -> Optional[pygame.Surface]:
        key = f"{item['id']}:{size[0]}x{size[1]}"
        if key in self.surfaces:
            return self.surfaces[key]
        path = cache_path(item["id"])
        if path.is_file():
            try:
                loaded = pygame.image.load(str(path)).convert()
                self.surfaces[key] = pygame.transform.smoothscale(loaded, size)
                return self.surfaces[key]
            except pygame.error:
                path.unlink(missing_ok=True)
        url = item.get("art", "")
        if url and item["id"] not in self.pending:
            self.pending.add(item["id"])
            threading.Thread(target=self._download, args=(item["id"], url), daemon=True).start()
        return None

    def _download(self, item_id: str, url: str) -> None:
        path = cache_path(item_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(url, headers={"User-Agent": "7BZ-Console/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                data = response.read(8 * 1024 * 1024)
            if len(data) > 512:
                path.write_bytes(data)
        except (OSError, ValueError):
            pass
        finally:
            self.pending.discard(item_id)


artwork = Artwork()
catalog: List[Dict[str, Any]] = []
tab = 0
selected = 0
last_scan = 0.0
message = "Choose a game and press A or Enter to play."
active: Optional[subprocess.Popen] = None
active_title = ""
axis_ready = True


def storefront_items() -> List[Dict[str, Any]]:
    return [{**item, "status": "Ready", "store": "Storefront", "subtitle": "Open your game library",
             "action": "store", "art": ""} for item in STOREFRONTS]


def visible_items() -> List[Dict[str, Any]]:
    if tab == 0:
        return catalog[:8] + storefront_items()[:4] if catalog else storefront_items()
    if tab == 1:
        return catalog
    if tab == 2:
        return storefront_items()
    return [item for item in catalog if item.get("action") == "build"]


def command_for(item: Dict[str, Any]) -> List[str]:
    action = item.get("action")
    if action == "legendary":
        return ["python3", str(BENCH / "gpu_runtime.py"), "launch", item["app_name"], wine_runner()]
    if action == "steam":
        return ["bash", str(BENCH / "launch_steam.sh"), f"steam://rungameid/{item['app_name']}"]
    if action == "build":
        path = item["install_path"]
        return ["bash", path] if path.lower().endswith(".sh") else [path]
    if action == "store":
        return ["bash", item["script"]]
    raise ValueError("This library item has no launch action")


def launch(item: Dict[str, Any]) -> str:
    global active, active_title
    if active is not None and active.poll() is None:
        return f"{active_title} is already running. Press B to stop it first."
    try:
        command = command_for(item)
        log = (LOGS / "dashboard-launch.log").open("a", encoding="utf-8", buffering=1)
        log.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} · {item['title']} ---\n")
        active = subprocess.Popen(command, env=game_env(), stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        active_title = item["title"]
        write_active_game(active.pid, os.getpgid(active.pid), active_title, item.get("store", "7BZ"))
        threading.Thread(target=watch_active, args=(active,), daemon=True).start()
        return f"Launching {active_title}. GPU, audio, and mouse fixes are applied automatically."
    except (OSError, ValueError) as exc:
        return f"Launch failed: {str(exc)[:100]}"


def watch_active(process: subprocess.Popen) -> None:
    process.wait()
    clear_active_game(process.pid)


def stop_active() -> str:
    if active is None or active.poll() is not None:
        return "No active game is running."
    try:
        os.killpg(os.getpgid(active.pid), 15)
        return f"Stopping {active_title}…"
    except OSError as exc:
        return f"Could not stop the game: {exc}"


def clipped(text: str, font: pygame.font.Font, width: int) -> str:
    result = text
    while result and font.size(result + "…")[0] > width:
        result = result[:-1]
    return result + ("…" if result != text else "")


def gradient(rect: pygame.Rect, top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> None:
    for offset in range(rect.height):
        ratio = offset / max(1, rect.height - 1)
        color = tuple(int(top[index] + (bottom[index] - top[index]) * ratio) for index in range(3))
        pygame.draw.line(screen, color, (rect.x, rect.y + offset), (rect.right, rect.y + offset))


def placeholder(item: Dict[str, Any], rect: pygame.Rect) -> None:
    digest = hashlib.sha256(item["id"].encode()).digest()
    color_a = (30 + digest[0] % 45, 35 + digest[1] % 55, 65 + digest[2] % 70)
    gradient(rect, color_a, (12, 14, 27))
    pygame.draw.circle(screen, CYAN, (rect.right - 35, rect.y + 30), 54, 2)
    badge = item.get("store", item.get("badge", "7BZ")).upper()[:8]
    screen.blit(font_tiny.render(badge, True, (220, 231, 255)), (rect.x + 13, rect.y + 12))


def draw_art(item: Dict[str, Any], rect: pygame.Rect) -> None:
    image = artwork.get(item, rect.size)
    if image:
        screen.blit(image, rect)
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((4, 8, 18, 50))
        screen.blit(shade, rect)
    else:
        placeholder(item, rect)


def draw_header(width: int) -> None:
    pygame.draw.rect(screen, (10, 15, 29), (0, 0, width, 88))
    pygame.draw.rect(screen, CYAN, (0, 0, 5, 88))
    pygame.draw.rect(screen, VIOLET, (5, 0, 3, 88))
    screen.blit(font_logo.render("7BZ", True, TEXT), (30, 16))
    screen.blit(font_body.render("DEV CLOUD GAME", True, CYAN), (94, 24))
    x = 360
    for index, label in enumerate(TABS):
        color = TEXT if index == tab else MUTED
        surface = font_body.render(label, True, color)
        screen.blit(surface, (x, 25))
        if index == tab:
            pygame.draw.rect(screen, CYAN, (x, 52, surface.get_width(), 3), border_radius=2)
        x += surface.get_width() + 38
    has_dual_gpu = Path("/dev/nvidia1").exists() and Path("/dev/nvidia0").exists()
    gpu_badge = "DUAL GPU: G0 RENDER · G1 STREAM" if has_dual_gpu else "NVIDIA GPU ACCELERATED"
    screen.blit(font_tiny.render(gpu_badge, True, VIOLET), (width - 380, 26))
    status = "GAME ACTIVE" if active is not None and active.poll() is None else "SYSTEM READY"
    color = CYAN if status == "GAME ACTIVE" else GREEN
    screen.blit(font_tiny.render(f"●  {status}", True, color), (width - 160, 26))
    screen.blit(font_small.render(time.strftime("%H:%M"), True, MUTED), (width - 61, 48))


def draw_featured(item: Dict[str, Any], width: int) -> None:
    rect = pygame.Rect(28, 105, width - 56, 214)
    draw_art(item, rect)
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    for x in range(rect.width):
        alpha = max(0, 215 - int(x / rect.width * 245))
        pygame.draw.line(overlay, (5, 9, 19, alpha), (x, 0), (x, rect.height))
    screen.blit(overlay, rect)
    screen.blit(font_tiny.render(f"{item.get('status', 'READY').upper()}  ·  {item.get('store', '7BZ').upper()}", True, GREEN), (52, 133))
    screen.blit(font_hero.render(clipped(item["title"], font_hero, 590), True, TEXT), (50, 160))
    screen.blit(font_body.render(item.get("subtitle", "Ready to play"), True, (210, 221, 244)), (52, 207))
    play = pygame.Rect(52, 251, 126, 43)
    pygame.draw.rect(screen, TEXT, play, border_radius=10)
    screen.blit(font_card.render("PLAY   A", True, BG), (72, 262))
    screen.blit(font_small.render("Mouse, keyboard, and gamepad ready", True, MUTED), (196, 267))


def draw_cards(items: List[Dict[str, Any]], width: int, chosen: int) -> List[Tuple[int, pygame.Rect]]:
    cards: List[Tuple[int, pygame.Rect]] = []
    screen.blit(font_tiny.render("YOUR CLOUD LIBRARY", True, MUTED), (30, 346))
    gap, columns = 14, 4
    card_width = (width - 60 - gap * (columns - 1)) // columns
    page_start = (chosen // 8) * 8
    for local_index, item in enumerate(items[page_start:page_start + 8]):
        index = page_start + local_index
        row, column = divmod(local_index, columns)
        rect = pygame.Rect(30 + column * (card_width + gap), 372 + row * 137, card_width, 121)
        cards.append((index, rect))
        selected_now = index == chosen
        pygame.draw.rect(screen, PANEL_LIGHT if selected_now else PANEL, rect, border_radius=13)
        draw_art(item, pygame.Rect(rect.x, rect.y, rect.width, 72))
        pygame.draw.rect(screen, CYAN if selected_now else (47, 59, 84), rect, 3 if selected_now else 1, border_radius=13)
        screen.blit(font_card.render(clipped(item["title"], font_card, rect.width - 20), True, TEXT), (rect.x + 10, rect.y + 80))
        screen.blit(font_tiny.render(item.get("store", "7BZ").upper(), True, CYAN if selected_now else MUTED), (rect.x + 10, rect.y + 103))
    return cards


def draw_footer(width: int, height: int) -> None:
    pygame.draw.rect(screen, (10, 15, 29), (0, height - 42, width, 42))
    mode_text = "🖱️ Mouse & Keyboard" if get_launcher_input_mode() == "mouse_keyboard" else "🎮 Gamepad (Xbox 360)"
    mode_label = f"[{mode_text}] (M/I to switch)"
    screen.blit(font_small.render(clipped(f"{mode_label}  ·  {message}", font_small, width - 520), True, CYAN), (28, height - 28))
    hint = "D-Pad Move   A Play   B Stop   M/Select Mode   LB/RB Tabs"
    screen.blit(font_small.render(hint, True, (195, 205, 227)), (width - font_small.size(hint)[0] - 28, height - 28))


running = True
while running:
    now = time.monotonic()
    if now - last_scan > 4:
        catalog = discover_games()
        last_scan = now
    items = visible_items()
    selected = min(selected, max(0, len(items) - 1))
    current = items[selected] if items else {"id": "empty", "title": "No games found", "store": "7BZ",
                                             "status": "Library", "subtitle": "Open a storefront to install a game", "art": ""}
    w, h = WIDTH, HEIGHT
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            display = pygame.display.set_mode((max(640, event.w), max(360, event.h)), pygame.RESIZABLE)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a): selected = max(0, selected - 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d): selected = min(len(items) - 1, selected + 1)
            elif event.key in (pygame.K_UP, pygame.K_w): selected = max(0, selected - 4)
            elif event.key in (pygame.K_DOWN, pygame.K_s): selected = min(len(items) - 1, selected + 4)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and items: message = launch(current)
            elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE, pygame.K_ESCAPE): message = stop_active()
            elif event.key in (pygame.K_m, pygame.K_i):
                new_m = toggle_launcher_input_mode()
                message = f"Input Mode: {'🖱️ Mouse & Keyboard' if new_m == 'mouse_keyboard' else '🎮 Controller (Xbox 360)'}"
            elif event.key == pygame.K_TAB:
                tab = (tab + (-1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)) % len(TABS); selected = 0
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx = round(event.pos[0] * WIDTH / max(1, display.get_width()))
            my = round(event.pos[1] * HEIGHT / max(1, display.get_height()))
            if 345 <= mx <= 900 and 8 <= my <= 70:
                tab_x = 360
                for tab_index, label in enumerate(TABS):
                    tab_width = font_body.size(label)[0] + 38
                    if tab_x <= mx <= tab_x + tab_width:
                        tab, selected = tab_index, 0
                        break
                    tab_x += tab_width
            elif 52 <= mx <= 178 and 251 <= my <= 294 and items:
                message = launch(current)
            else:
                cards = draw_cards(items, w, selected)
                for index, rect in cards:
                    if rect.collidepoint((mx, my)):
                        if index == selected: message = launch(items[index])
                        selected = index
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0 and items: message = launch(current)
            elif event.button == 1: message = stop_active()
            elif event.button in (3, 8):
                new_m = toggle_launcher_input_mode()
                message = f"Input Mode: {'🖱️ Mouse & Keyboard' if new_m == 'mouse_keyboard' else '🎮 Controller (Xbox 360)'}"
            elif event.button in (4, 9): tab = (tab - 1) % len(TABS); selected = 0
            elif event.button in (5, 10): tab = (tab + 1) % len(TABS); selected = 0
            elif event.button in (11, 12): selected = max(0, selected - 4)
            elif event.button in (13, 14): selected = min(len(items) - 1, selected + 4)
        elif event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
            if abs(event.value) < .35:
                axis_ready = True
            elif axis_ready and items:
                selected = max(0, min(len(items) - 1, selected + ((1 if event.value > 0 else -1) if event.axis == 0 else (4 if event.value > 0 else -4))))
                axis_ready = False

    gradient(pygame.Rect(0, 0, w, h), BG, (13, 17, 31))
    draw_header(w)
    draw_featured(current, w)
    if items:
        draw_cards(items, w, selected)
    else:
        screen.blit(font_body.render("No items are available in this section yet.", True, MUTED), (31, 370))
    draw_footer(w, h)
    output = screen if display.get_size() == (WIDTH, HEIGHT) else pygame.transform.smoothscale(screen, display.get_size())
    display.blit(output, (0, 0))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
