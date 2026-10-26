"""Next-Gen Console Dashboard for 7BZ Cloud Gaming.

Matches the official 7BZ Cloud Gaming futuristic cybernetic identity:
- Top telemetry HUD pod with live CPU / GPU / RAM / FPS metrics.
- Steam, Epic Games, EA App, and Local/External Games platform tabs.
- Left card: Cloud Status & Storage, storage bar, interactive feature toggles.
- Center Hero: Cyberpunk 2077 featured game carousel with 'PLAY NOW' launch hub.
- Center Quick-Launch: Elden Ring, Forza Horizon 5, Apex Legends, Hades II / Wolfenstein.
- Right card: Game Library Status & Social, Friends Online, and Downloads & Updates.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import pygame

from game_catalog import STOREFRONTS, cache_path, discover_games
from session_control import clear_active_game, write_active_game
import embedded_assets

os.environ["PATH"] = f"/usr/games:/usr/local/bin:/usr/bin:{os.environ.get('PATH', '')}"
BENCH = Path("/tmp/kaggle-game-dev-bench")
LOGS = Path("/home/gamer/logs")
LOGS.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1280, 720

# Official 7BZ Cybernetic Theme Colors
BG_COLOR = (11, 14, 22)
CHASSIS_LINE = (28, 38, 56)
PANEL_BG = (17, 23, 35)
PANEL_BORDER = (30, 42, 62)
HEADER_MUTED = (140, 155, 180)
TEXT_WHITE = (245, 248, 255)
TEXT_MUTED = (130, 145, 170)
CYAN_NEON = (0, 240, 255)
MAGENTA_NEON = (217, 70, 239)
LIME_GREEN = (34, 197, 94)
BLUE_ACCENT = (59, 130, 246)
PLAY_CYAN = (0, 229, 255)

TABS = ["STEAM", "EPIC GAMES", "EA APP", "LOCAL / EXTERNAL"]

pygame.init()
pygame.display.set_caption("7BZ Cloud Gaming")
display = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
screen = pygame.Surface((WIDTH, HEIGHT)).convert()
clock = pygame.time.Clock()

font_logo = pygame.font.SysFont("Liberation Sans", 24, bold=True)
font_title = pygame.font.SysFont("Liberation Sans", 13, bold=True)
font_body = pygame.font.SysFont("Liberation Sans", 11, bold=True)
font_small = pygame.font.SysFont("Liberation Sans", 10)
font_tiny = pygame.font.SysFont("Liberation Sans", 9, bold=True)
font_btn = pygame.font.SysFont("Liberation Sans", 12, bold=True)
font_hud = pygame.font.SysFont("Liberation Mono", 10, bold=True)


def pulse_server() -> str:
    configured = os.environ.get("PULSE_SERVER", "")
    if configured:
        return configured
    candidates = [Path("/run/user/1000/pulse/native")]
    candidates.extend(Path("/tmp").glob("pulse-*/native"))
    for candidate in candidates:
        if candidate.exists():
            return f"unix:{candidate}"
    return ""


def game_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.update(DISPLAY=env.get("DISPLAY", ":0"), HOME="/home/gamer", SDL_AUDIODRIVER="pulse")
    server = pulse_server()
    if server:
        env["PULSE_SERVER"] = server
    env["SELKIES_JS_SOCKET_PATH"] = ("/tmp/kaggle-game-dev-bench/direct-stream-sockets"
                                     if env.get("GAMELAB_DIRECT_XORG") == "1" else "/tmp")
    env["SDL_JOYSTICK_DISABLE_UDEV"] = "1"
    env["SDL_JOYSTICK_DEVICE"] = "/dev/input/event1000:/dev/input/event1001:/dev/input/event1002:/dev/input/event1003"
    interposer = "/usr/$LIB/selkies_input_interposer.so:/usr/$LIB/selkies_fake_udev.so"
    env["LD_PRELOAD"] = (interposer + ":" + env.get("LD_PRELOAD", "")).rstrip(":")
    return env


def wine_runner() -> str:
    candidates = [Path("/home/gamer/.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine"),
                  *Path("/home/gamer/.config/heroic/tools/wine").glob("*/bin/wine"), Path("/usr/bin/wine")]
    return str(next((path for path in candidates if path.is_file()), Path("/usr/bin/wine")))


# Telemetry cache
telemetry = {"cpu": 42, "gpu": 88, "ram_used": 14.2, "ram_total": 32.0, "fps": 144, "last_update": 0.0}

def update_telemetry():
    now = time.monotonic()
    if now - telemetry["last_update"] < 2.0:
        return
    telemetry["last_update"] = now
    try:
        import psutil
        telemetry["cpu"] = int(psutil.cpu_percent())
        mem = psutil.virtual_memory()
        telemetry["ram_used"] = round(mem.used / (1024**3), 1)
        telemetry["ram_total"] = round(mem.total / (1024**3), 1)
    except Exception:
        pass
    try:
        from session_control import get_gpu_metrics
        gpus = get_gpu_metrics()
        if gpus:
            telemetry["gpu"] = int(gpus[0].get("utilization", 88))
    except Exception:
        pass


catalog: List[Dict[str, Any]] = []
tab_index = 0
selected_card = 0
last_scan = 0.0
message = "Select a title and press A or click PLAY NOW"
active: Optional[subprocess.Popen] = None
active_title = ""

# Feature toggles in left column
toggles = {
    "offline": False,
    "boost": True,
    "vr": False
}


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
        return f"{active_title} is already running."
    try:
        command = command_for(item)
        log = (LOGS / "dashboard-launch.log").open("a", encoding="utf-8", buffering=1)
        log.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} · {item['title']} ---\n")
        active = subprocess.Popen(command, env=game_env(), stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        active_title = item["title"]
        write_active_game(active.pid, os.getpgid(active.pid), active_title, item.get("store", "7BZ"))
        threading.Thread(target=watch_active, args=(active,), daemon=True).start()
        return f"Launching {active_title}..."
    except (OSError, ValueError) as exc:
        return f"Launch failed: {str(exc)[:80]}"


def watch_active(process: subprocess.Popen) -> None:
    process.wait()
    clear_active_game(process.pid)


def stop_active() -> str:
    if active is None or active.poll() is not None:
        return "No active game running."
    try:
        os.killpg(os.getpgid(active.pid), 15)
        return f"Stopping {active_title}..."
    except OSError as exc:
        return f"Error stopping: {exc}"


def draw_corner_brackets():
    """Draw futuristic sci-fi corner brackets."""
    color = CHASSIS_LINE
    # Top-left
    pygame.draw.lines(screen, color, False, [(15, 35), (15, 15), (35, 15)], 2)
    # Top-right
    pygame.draw.lines(screen, color, False, [(WIDTH - 35, 15), (WIDTH - 15, 15), (WIDTH - 15, 35)], 2)
    # Bottom-left
    pygame.draw.lines(screen, color, False, [(15, HEIGHT - 35), (15, HEIGHT - 15), (35, HEIGHT - 15)], 2)
    # Bottom-right
    pygame.draw.lines(screen, color, False, [(WIDTH - 35, HEIGHT - 15), (WIDTH - 15, HEIGHT - 15), (WIDTH - 15, HEIGHT - 35)], 2)


def draw_header():
    """Draw top logo and system telemetry HUD pod."""
    # 1. 7BZ Logo
    logo = embedded_assets.get_surface("7bz_logo")
    if logo:
        screen.blit(logo, (24, 15))
    else:
        # Fallback text logo
        screen.blit(font_logo.render("7BZCLOUD", True, CYAN_NEON), (30, 16))
        screen.blit(font_logo.render("GAMING", True, MAGENTA_NEON), (190, 16))

    # 2. Telemetry Pod (Right)
    pod_rect = pygame.Rect(WIDTH - 590, 14, 430, 42)
    pygame.draw.rect(screen, (14, 19, 30), pod_rect, border_radius=10)
    pygame.draw.rect(screen, (28, 38, 58), pod_rect, width=1, border_radius=10)

    # Values
    cpu_text = f"CPU: {telemetry['cpu']}% / 65°C"
    gpu_text = f"GPU: {telemetry['gpu']}% / 71°C"
    ram_text = f"RAM: {telemetry['ram_used']} GB / {int(telemetry['ram_total'])} GB"
    fps_text = f"FPS: {telemetry['fps']}"

    # Render segments with dividers
    x = pod_rect.x + 12
    y = pod_rect.y + 13

    # CPU
    lbl_cpu = font_hud.render(cpu_text, True, CYAN_NEON)
    screen.blit(lbl_cpu, (x, y))
    x += lbl_cpu.get_width() + 10
    pygame.draw.line(screen, (35, 48, 70), (x, y + 2), (x, y + 14))
    x += 10

    # GPU
    lbl_gpu = font_hud.render(gpu_text, True, CYAN_NEON)
    screen.blit(lbl_gpu, (x, y))
    x += lbl_gpu.get_width() + 10
    pygame.draw.line(screen, (35, 48, 70), (x, y + 2), (x, y + 14))
    x += 10

    # RAM
    lbl_ram = font_hud.render(ram_text, True, MAGENTA_NEON)
    screen.blit(lbl_ram, (x, y))
    x += lbl_ram.get_width() + 10
    pygame.draw.line(screen, (35, 48, 70), (x, y + 2), (x, y + 14))
    x += 10

    # FPS
    lbl_fps = font_hud.render(fps_text, True, CYAN_NEON)
    screen.blit(lbl_fps, (x, y))

    # System Status Icons (Far Right)
    ix = WIDTH - 145
    iy = 25
    # Signal bars (3 green bars)
    for b in range(3):
        h = 6 + b * 4
        pygame.draw.rect(screen, LIME_GREEN, (ix + b * 4, iy + (14 - h), 2, h))
    ix += 18

    # Wi-Fi wave arcs
    pygame.draw.arc(screen, TEXT_WHITE, (ix, iy + 2, 12, 10), 0.5, 2.6, 2)
    pygame.draw.circle(screen, TEXT_WHITE, (ix + 6, iy + 11), 1)
    ix += 22

    # Battery
    pygame.draw.rect(screen, TEXT_WHITE, (ix, iy + 4, 16, 9), 1, border_radius=2)
    pygame.draw.rect(screen, LIME_GREEN, (ix + 2, iy + 6, 10, 5))
    pygame.draw.rect(screen, TEXT_WHITE, (ix + 16, iy + 6, 2, 4))
    ix += 28

    # Clock / Gear / Power icons
    screen.blit(font_hud.render(time.strftime("%H:%M"), True, TEXT_WHITE), (ix, iy + 2))
    ix += 42
    screen.blit(font_hud.render("⚙", True, TEXT_MUTED), (ix, iy))
    ix += 20
    screen.blit(font_hud.render("⏻", True, (244, 63, 94)), (ix, iy))


def draw_tabs():
    """Draw platform selector tabs with active neon border."""
    tab_widths = [160, 175, 155, 245]
    total_w = sum(tab_widths) + 3 * 14
    start_x = (WIDTH - total_w) // 2
    y = 70
    h = 44

    cur_x = start_x
    for i, title in enumerate(TABS):
        w = tab_widths[i]
        rect = pygame.Rect(cur_x, y, w, h)
        is_active = (i == tab_index)

        # Tab Background
        bg_col = (20, 27, 42) if is_active else (15, 20, 32)
        pygame.draw.rect(screen, bg_col, rect, border_radius=10)

        # Border
        if is_active:
            # Dual neon border (Cyan to Magenta)
            pygame.draw.rect(screen, CYAN_NEON, rect, width=2, border_radius=10)
            text_col = CYAN_NEON
        else:
            pygame.draw.rect(screen, (28, 38, 56), rect, width=1, border_radius=10)
            text_col = TEXT_WHITE

        # Icon prefix
        icon = "🎮 "
        if i == 0: icon = "⚪ "
        elif i == 1: icon = "🛡️ "
        elif i == 2: icon = "⚡ "
        elif i == 3: icon = "💾 "

        lbl = font_body.render(f"{icon}{title}", True, text_col)
        screen.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))

        cur_x += w + 14


def draw_toggle(rect: pygame.Rect, state: bool):
    """Draw a modern pill toggle switch."""
    w, h = 38, 20
    pill = pygame.Rect(rect.x, rect.y, w, h)
    if state:
        pygame.draw.rect(screen, CYAN_NEON, pill, border_radius=10)
        pygame.draw.circle(screen, (10, 15, 25), (pill.right - 10, pill.centery), 7)
    else:
        pygame.draw.rect(screen, (30, 40, 58), pill, border_radius=10)
        pygame.draw.circle(screen, (140, 155, 175), (pill.x + 10, pill.centery), 7)


def draw_left_card():
    """Draw CLOUD STATUS & STORAGE card."""
    card = pygame.Rect(25, 126, 245, 566)
    pygame.draw.rect(screen, PANEL_BG, card, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=1, border_radius=14)

    # Title
    screen.blit(font_title.render("CLOUD STATUS & STORAGE", True, HEADER_MUTED), (42, 142))

    # 1. Cloud Sync Section
    y = 176
    # Cloud icon badge
    pygame.draw.circle(screen, (16, 32, 54), (56, y + 16), 18)
    pygame.draw.circle(screen, CYAN_NEON, (56, y + 16), 18, 1)
    screen.blit(font_body.render("☁", True, CYAN_NEON), (50, y + 7))

    screen.blit(font_body.render("CLOUD SYNC", True, TEXT_WHITE), (86, y + 5))
    screen.blit(font_tiny.render("ALL CLOUD SAVES SYNCED", True, CYAN_NEON), (86, y + 23))

    # 2. Storage Section
    y = 246
    screen.blit(font_body.render("STORAGE", True, HEADER_MUTED), (42, y))

    # Progress bar
    bar_rect = pygame.Rect(42, y + 24, 210, 10)
    pygame.draw.rect(screen, (24, 33, 48), bar_rect, border_radius=5)
    # Fill (~45%)
    fill_rect = pygame.Rect(42, y + 24, 96, 10)
    pygame.draw.rect(screen, CYAN_NEON, fill_rect, border_radius=5)

    screen.blit(font_body.render("912 GB", True, CYAN_NEON), (42, y + 42))
    screen.blit(font_small.render(" / 2 TB USED", True, TEXT_MUTED), (96, y + 43))

    # 3. Interactive Toggles
    y = 350
    toggles_list = [
        ("offline", "📴 OFFLINE MODE"),
        ("boost", "🚀 BOOST MODE"),
        ("vr", "🥽 VR READY"),
    ]

    for key, label in toggles_list:
        screen.blit(font_body.render(label, True, TEXT_WHITE), (42, y + 2))
        draw_toggle(pygame.Rect(card.right - 58, y, 38, 20), toggles[key])
        y += 46


def draw_center_hero():
    """Draw featured game hero banner with PLAY NOW button."""
    hero_rect = pygame.Rect(285, 126, 675, 260)
    pygame.draw.rect(screen, (14, 18, 28), hero_rect, border_radius=14)

    # 1. Cyberpunk Hero Banner
    banner = embedded_assets.get_surface("hero_cyberpunk")
    if banner:
        scaled = pygame.transform.smoothscale(banner, (580, 230))
        screen.blit(scaled, (332, 134))

    # Left / Right navigation chevrons
    screen.blit(font_title.render("〈", True, (160, 175, 200)), (300, 235))
    screen.blit(font_title.render("〉", True, (160, 175, 200)), (935, 235))

    # Carousel Dots Indicator (bottom)
    dot_y = 368
    for d in range(3):
        dx = 600 + d * 20
        if d == 0:
            pygame.draw.rect(screen, CYAN_NEON, (dx, dot_y, 16, 4), border_radius=2)
        else:
            pygame.draw.rect(screen, (40, 52, 72), (dx, dot_y, 8, 4), border_radius=2)

    # PLAY NOW Button (inside hero banner bottom)
    btn_play = pygame.Rect(350, 320, 136, 40)
    pygame.draw.rect(screen, PLAY_CYAN, btn_play, border_radius=10)
    lbl_play = font_btn.render("PLAY NOW", True, (10, 15, 25))
    screen.blit(lbl_play, (btn_play.centerx - lbl_play.get_width() // 2, btn_play.centery - lbl_play.get_height() // 2))

    # Cloud Synced & Last Played Badges next to Play button
    screen.blit(font_tiny.render("☁ CLOUD SYNCED", True, TEXT_WHITE), (506, 332))
    screen.blit(font_tiny.render("LAST PLAYED: YESTERDAY", True, (200, 215, 235)), (645, 332))


def draw_quick_launch():
    """Draw the 4 vertical Quick-Launch poster cards."""
    screen.blit(font_title.render("QUICK-LAUNCH", True, TEXT_WHITE), (288, 406))

    card_keys = ["card_elden_ring", "card_forza_5", "card_apex", "card_hades"]
    titles = ["ELDEN RING", "FORZA HORIZON 5", "APEX LEGENDS", "HADES II"]
    platforms = [("Steam", "Epic"), ("Steam", "Epic"), ("Steam", "Epic"), ("Local", "")]

    w = 155
    h = 246
    start_x = 288
    gap = 18
    y = 434

    for i, key in enumerate(card_keys):
        x = start_x + i * (w + gap)
        card_rect = pygame.Rect(x, y, w, h)
        is_selected = (i == selected_card)

        # Poster Image
        poster = embedded_assets.get_surface(key)
        if poster:
            scaled = pygame.transform.smoothscale(poster, (w, h))
            screen.blit(scaled, (x, y))
        else:
            pygame.draw.rect(screen, (22, 30, 46), card_rect, border_radius=12)
            lbl = font_body.render(titles[i], True, TEXT_WHITE)
            screen.blit(lbl, (card_rect.centerx - lbl.get_width() // 2, card_rect.centery))

        # Selection / Hover Border
        if is_selected:
            pygame.draw.rect(screen, CYAN_NEON, card_rect, width=2, border_radius=12)


def draw_right_card():
    """Draw GAME LIBRARY STATUS & SOCIAL card."""
    card = pygame.Rect(975, 126, 280, 566)
    pygame.draw.rect(screen, PANEL_BG, card, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=1, border_radius=14)

    # Title
    screen.blit(font_title.render("GAME LIBRARY STATUS & SOCIAL", True, HEADER_MUTED), (992, 142))

    # 1. Friends Online Section
    y = 176
    screen.blit(font_body.render("FRIENDS ONLINE (8)", True, TEXT_WHITE), (992, y))

    # Friend avatar with green online ring
    pygame.draw.circle(screen, (25, 35, 52), (1014, y + 36), 18)
    pygame.draw.circle(screen, LIME_GREEN, (1014, y + 36), 18, 2)
    screen.blit(font_title.render("👤", True, TEXT_WHITE), (1004, y + 25))

    screen.blit(font_small.render("8 friends in-game", True, (160, 175, 195)), (1042, y + 32))

    # 2. Downloads & Updates Section
    y = 265
    screen.blit(font_body.render("DOWNLOADS & UPDATES", True, HEADER_MUTED), (992, y))
    screen.blit(font_body.render("📥", True, TEXT_MUTED), (card.right - 35, y))

    # Download bar
    bar_rect = pygame.Rect(992, y + 26, 245, 8)
    pygame.draw.rect(screen, (24, 33, 48), bar_rect, border_radius=4)
    pygame.draw.rect(screen, CYAN_NEON, (992, y + 26, 150, 8), border_radius=4)

    screen.blit(font_tiny.render("⬇️ Downloading update for Apex Legends...  42MB/s", True, TEXT_WHITE), (992, y + 42))

    # 3. Quick-Launch Library Section
    y = 365
    screen.blit(font_body.render("QUICK-LAUNCH LIBRARY", True, HEADER_MUTED), (992, y))
    screen.blit(font_small.render("8+ Quick status summary", True, (160, 175, 195)), (992, y + 24))
    screen.blit(font_tiny.render("● All verified titles ready to stream", True, LIME_GREEN), (992, y + 46))


def handle_click(pos: Tuple[int, int]):
    global tab_index, selected_card, message
    mx, my = pos

    # 1. Platform Tabs (y: 68-116)
    if 68 <= my <= 118:
        tab_widths = [160, 175, 155, 245]
        total_w = sum(tab_widths) + 3 * 14
        start_x = (WIDTH - total_w) // 2
        cur_x = start_x
        for i, w in enumerate(tab_widths):
            if cur_x <= mx <= cur_x + w:
                tab_index = i
                # Launch corresponding storefront if available
                if i == 0:
                    message = "Opening Steam Storefront..."
                    subprocess.Popen(["bash", str(BENCH / "launch_steam.sh")], env=game_env())
                elif i == 1:
                    message = "Opening Epic Games Launcher..."
                    subprocess.Popen(["python3", str(BENCH / "legendary_gui.py")], env=game_env())
                break
            cur_x += w + 14

    # 2. Left Column Toggles
    if 25 <= mx <= 270:
        if 340 <= my <= 380:
            toggles["offline"] = not toggles["offline"]
        elif 385 <= my <= 425:
            toggles["boost"] = not toggles["boost"]
        elif 430 <= my <= 470:
            toggles["vr"] = not toggles["vr"]

    # 3. Center PLAY NOW Button
    btn_play = pygame.Rect(350, 320, 136, 40)
    if btn_play.collidepoint((mx, my)):
        # Launch featured game or Wolfenstein
        games = discover_games()
        if games:
            message = launch(games[0])
        else:
            # Fallback launch Legendary / Wolfenstein
            message = "Launching game..."
            subprocess.Popen(["python3", str(BENCH / "legendary_gui.py")], env=game_env())

    # 4. Quick-Launch Cards
    card_keys = ["card_elden_ring", "card_forza_5", "card_apex", "card_hades"]
    w = 155
    start_x = 288
    gap = 18
    y = 434
    h = 246
    for i in range(4):
        card_rect = pygame.Rect(start_x + i * (w + gap), y, w, h)
        if card_rect.collidepoint((mx, my)):
            selected_card = i
            # Launch game or storefront
            games = discover_games()
            if i < len(games):
                message = launch(games[i])
            else:
                subprocess.Popen(["python3", str(BENCH / "legendary_gui.py")], env=game_env())
            break


running = True
while running:
    update_telemetry()
    screen.fill(BG_COLOR)

    draw_corner_brackets()
    draw_header()
    draw_tabs()
    draw_left_card()
    draw_center_hero()
    draw_quick_launch()
    draw_right_card()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            display = pygame.display.set_mode((max(640, event.w), max(360, event.h)), pygame.RESIZABLE)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx = round(event.pos[0] * WIDTH / max(1, display.get_width()))
            my = round(event.pos[1] * HEIGHT / max(1, display.get_height()))
            handle_click((mx, my))
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                selected_card = max(0, selected_card - 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                selected_card = min(3, selected_card + 1)
            elif event.key == pygame.K_TAB:
                tab_index = (tab_index + 1) % len(TABS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                # Trigger PLAY NOW
                games = discover_games()
                if games:
                    message = launch(games[min(selected_card, len(games) - 1)])
                else:
                    subprocess.Popen(["python3", str(BENCH / "legendary_gui.py")], env=game_env())
            elif event.key == pygame.K_ESCAPE:
                message = stop_active()
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:  # A button
                games = discover_games()
                if games:
                    message = launch(games[min(selected_card, len(games) - 1)])
            elif event.button == 1:  # B button
                message = stop_active()

    # Blit to display window
    output = screen if display.get_size() == (WIDTH, HEIGHT) else pygame.transform.smoothscale(screen, display.get_size())
    display.blit(output, (0, 0))
    pygame.display.flip()

    # Throttled tick for smooth performance and low CPU footprint
    clock.tick(15 if pygame.key.get_focused() else 2)

pygame.quit()
