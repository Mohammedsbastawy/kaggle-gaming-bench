"""Controller-friendly launcher and diagnostic interface for Linux gaming storefronts."""
from pathlib import Path
import json
import math
import os
import shutil
import subprocess
import time

import pygame

# Ensure /usr/games is in PATH
os.environ['PATH'] = f"/usr/games:/usr/local/bin:/usr/bin:{os.environ.get('PATH', '')}"

BENCH = Path('/tmp/kaggle-game-dev-bench')
LOGS = Path('/home/gamer/logs')
LOGS.mkdir(parents=True, exist_ok=True)
BUILDS = Path('/tmp/game-builds')
BUILDS.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1280, 720
BG = (7, 15, 26)
CARD_BG = (15, 28, 43)
ITEM_BG = (19, 38, 53)
ITEM_SEL_BG = (27, 68, 86)
TEXT_WHITE = (235, 242, 255)
TEXT_MUTED = (134, 154, 187)
ACCENT = (102, 207, 226)
GREEN = (46, 204, 113)
YELLOW = (241, 196, 15)
RED = (231, 76, 60)
BORDER_SEL = (77, 205, 242)

pygame.init()
pygame.display.set_caption('Game Lab')
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
clock = pygame.time.Clock()

font_title = pygame.font.SysFont('DejaVu Sans', 27, bold=True)
font_hero = pygame.font.SysFont('DejaVu Sans', 38, bold=True)
font_item = pygame.font.SysFont('DejaVu Sans', 18, bold=True)
font_badge = pygame.font.SysFont('DejaVu Sans', 13, bold=True)
font_body = pygame.font.SysFont('DejaVu Sans', 15)
font_mono = pygame.font.SysFont('DejaVu Sans Mono', 13)
font_small = pygame.font.SysFont('DejaVu Sans', 13)

def resolve_bin(candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
        p = shutil.which(c)
        if p:
            return p
    return candidates[0] if candidates else None

STOREFRONTS = [
    {
        'id': 'steam',
        'badge': 'STM',
        'badge_color': (30, 80, 160),
        'title': 'Steam',
        'script': str(BENCH / 'launch_steam.sh'),
        'log': str(LOGS / 'steam.log'),
        'desc': 'Open Steam and sign in to your own library. The first launch may download client components and request agreement acceptance.',
        'compat': 'Linux native builds run directly. Proton/DXVK games requiring hardware Vulkan ICD will fail (Tesla T4 lacks container display/render nodes).',
        'cmd': 'steam -no-cef-sandbox -cef-disable-gpu -cef-force-software-rendering'
    },
    {
        'id': 'epic',
        'badge': 'EGS',
        'badge_color': (30, 140, 70),
        'title': 'Epic Games · Heroic',
        'script': str(BENCH / 'launch_heroic.sh'),
        'log': str(LOGS / 'heroic.log'),
        'desc': 'Browse your Epic and GOG libraries in Heroic. For a game stuck on Launching, use the diagnostics tile and inspect its lastPlay log.',
        'compat': 'WineD3D is configured for Windows games. Actual game launch depends on the title and its runtime requirements.',
        'cmd': 'heroic --no-sandbox --disable-gpu --disable-gpu-compositing'
    },
    {
        'id': 'legendary',
        'badge': 'LEG',
        'badge_color': (35, 120, 180),
        'title': 'Epic Games · Legendary',
        'script': str(BENCH / 'launch_legendary.sh'),
        'log': str(LOGS / 'legendary.log'),
        'desc': 'Direct Epic Games launch path for diagnosing Heroic. Sign in, list installed games, then launch with Wine and capture the exact output.',
        'compat': 'An earlier prototype launched Wolfenstein here. Recheck each title in the current Kaggle session.',
        'cmd': 'legendary launch APP --wine WINE_BIN'
    },
    {
        'id': 'heroic_fix',
        'badge': 'FIX',
        'badge_color': (220, 100, 30),
        'title': 'Heroic diagnostics & repair',
        'script': str(BENCH / 'fix_heroic.sh'),
        'log': str(LOGS / 'heroic_fix.log'),
        'desc': 'Back up Heroic game settings, select WineD3D compatible options, and display recent launch logs. Existing Wine prefixes stay intact.',
        'compat': 'Settings repair can address runner mismatch. It does not guarantee every game will run.',
        'cmd': 'python3 /tmp/kaggle-game-dev-bench/fix_heroic_config.py'
    },
    {
        'id': 'gog',
        'badge': 'GOG',
        'badge_color': (140, 40, 160),
        'title': 'GOG · Minigalaxy',
        'script': str(BENCH / 'launch_minigalaxy.sh'),
        'log': str(LOGS / 'minigalaxy.log'),
        'desc': "DRM-free GOG library client running as user 'gamer'. Fast lightweight GTK interface for native Linux and Wine games. (GOG is also accessible inside Heroic).",
        'compat': 'Client starts in this container; sign-in and individual game execution require interactive validation.',
        'cmd': 'minigalaxy'
    },
    {
        'id': 'lutris',
        'badge': 'LUT',
        'badge_color': (200, 120, 20),
        'title': 'Lutris',
        'script': str(BENCH / 'launch_lutris.sh'),
        'log': str(LOGS / 'lutris.log'),
        'desc': "Universal game manager running as user 'gamer'. Integrates Steam, Epic Games, GOG, EA, Wine runners, and custom Linux emulators and test builds.",
        'compat': 'Multi-storefront aggregator. Runner management and automated installer scripts.',
        'cmd': 'lutris'
    },
    {
        'id': 'ea',
        'badge': 'EA ',
        'badge_color': (180, 40, 40),
        'title': 'EA App · experimental',
        'script': str(BENCH / 'launch_ea.sh'),
        'log': str(LOGS / 'ea.log'),
        'desc': "Electronic Arts Windows installer/client under Wine64 as user 'gamer'. Downloads official EAappInstaller.exe into isolated wineprefix.",
        'compat': 'Installer window was observed. Client sign-in and game launch are unverified.',
        'cmd': 'WINEPREFIX=/home/gamer/ea-prefix wine EAappInstaller.exe'
    },
    {
        'id': 'terminal',
        'badge': 'CLI',
        'badge_color': (80, 90, 110),
        'title': 'Terminal (xterm)',
        'script': 'xterm',
        'log': str(LOGS / 'terminal.log'),
        'desc': 'Interactive X11 shell for inspecting the container, checking wine prefixes, running apt or git commands, or viewing logs.',
        'compat': 'Shell access in active Kaggle session.',
        'cmd': 'xterm -geometry 100x30 -title "Dev Bench Terminal"'
    },
    {
        'id': 'audio',
        'badge': 'AUD',
        'badge_color': (40, 160, 180),
        'title': 'Stereo Audio Test',
        'script': None,
        'log': None,
        'desc': 'Generates stereo tone (440 Hz Left, 660 Hz Right) through PulseAudio monitor sink -> Selkies Opus stereo stream.',
        'compat': 'Verifies PulseAudio -> Selkies Opus 128 kbps stereo pipeline in your browser.',
        'cmd': 'pygame.mixer stereo tone (440Hz L / 660Hz R)'
    },
    {
        'id': 'video',
        'badge': 'VID',
        'badge_color': (60, 180, 100),
        'title': 'Video Motion Test',
        'script': None,
        'log': None,
        'desc': 'Toggles real-time animated vertical bars to verify 60 FPS Xvfb capture and Tesla T4 NVENC H.264 encode smoothness.',
        'compat': 'Tesla T4 NVENC hardware encoder active.',
        'cmd': 'Real-time 60 FPS animated pattern'
    }
]

# Track background processes
procs = {}

def scan_builds():
    builds = []
    if BUILDS.exists():
        for path in sorted(BUILDS.iterdir()):
            if path.is_file() and path.suffix.lower() in ('.sh', '.appimage', '.x86_64', '.bin'):
                builds.append({
                    'id': f'build_{path.name}',
                    'badge': 'BLD',
                    'badge_color': (100, 100, 200),
                    'title': f'Build: {path.name}',
                    'script': str(path),
                    'log': str(LOGS / f'{path.name}.log'),
                    'desc': f'Uploaded Linux executable build in /tmp/game-builds/{path.name}. Upload more via Selkies Files panel.',
                    'compat': 'Executes inside container X11/PulseAudio environment.',
                    'cmd': f'/bin/bash {path}' if path.suffix.lower() == '.sh' else str(path)
                })
    return builds

def tone():
    """A stereo left/right tone for testing the browser audio path."""
    import array
    rate = 48000
    samples = array.array('h')
    for i in range(rate):
        t = i / rate
        samples.extend((int(7000 * math.sin(2 * math.pi * 440 * t)),
                        int(7000 * math.sin(2 * math.pi * 660 * t))))
    try:
        pygame.mixer.init(frequency=rate, size=-16, channels=2, buffer=512)
        pygame.mixer.Sound(buffer=samples.tobytes()).play()
        return 'Stereo tone emitted: 440 Hz Left, 660 Hz Right'
    except Exception as exc:
        return 'Audio unavailable: ' + str(exc)[:80]

def launch_item(item):
    item_id = item['id']
    if item_id == 'audio':
        return tone()
    if item_id == 'video':
        return 'Video test running in bottom strip. Check 60 FPS.'
    
    # Check if already running
    p = procs.get(item_id)
    if p is not None and p.poll() is None:
        return f'{item["title"]} is already running (PID {p.pid}). Switch to it via taskbar or Alt+Tab.'
    
    script = item.get('script')
    if not script:
        return 'No executable script configured.'
    
    try:
        log_path = item.get('log') or str(LOGS / f'{item_id}.log')
        log_fh = open(log_path, 'a', buffering=1)
        log_fh.write(f"\n--- Launching {item['title']} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        
        env = os.environ.copy()
        env['DISPLAY'] = env.get('DISPLAY', ':0')
        env['PATH'] = f"/usr/games:/usr/local/bin:/usr/bin:{env.get('PATH', '')}"
        env['SDL_AUDIODRIVER'] = 'pulse'
        
        if script == 'xterm':
            cmd = ['xterm', '-geometry', '100x30', '-title', 'Dev Bench Terminal']
        elif script.endswith('.sh'):
            cmd = ['/bin/bash', script]
        else:
            if not os.access(script, os.X_OK):
                return f'{Path(script).name} is not executable. Set its execute bit after upload.'
            cmd = [script]
            
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        procs[item_id] = proc
        return f'Launched {item["title"]} (PID {proc.pid}). Window will appear in Openbox.'
    except Exception as exc:
        return f'Failed to launch {item["title"]}: {str(exc)[:80]}'

def stop_item(item):
    item_id = item['id']
    p = procs.get(item_id)
    if p is not None and p.poll() is None:
        try:
            p.terminate()
            return f'Sent SIGTERM to {item["title"]} (PID {p.pid}).'
        except Exception as exc:
            return f'Error terminating process: {exc}'
    return f'{item["title"]} is not currently running.'

def get_proc_status(item):
    item_id = item['id']
    if item_id in ('audio', 'video'):
        return 'READY', GREEN
    p = procs.get(item_id)
    if p is None:
        return 'IDLE', TEXT_MUTED
    poll = p.poll()
    if poll is None:
        return f'RUNNING (PID {p.pid})', GREEN
    elif poll == 0:
        return 'STOPPED (Exit 0)', TEXT_MUTED
    else:
        return f'EXITED ({poll})', RED

def read_tail(log_path, lines=4):
    if not log_path or not os.path.exists(log_path):
        return ['(No log entries yet)']
    try:
        content = Path(log_path).read_text(encoding='utf-8', errors='replace').splitlines()
        tail = [l for l in content if l.strip()][-lines:]
        return tail if tail else ['(Log is empty)']
    except Exception:
        return ['(Unable to read log)']

selected = 0
message = 'Use D-Pad / Stick / Arrow keys to navigate. Press A / Enter to launch.'
pointer_dx = pointer_dy = 0
pad_state = 'No gamepad event detected'
last_scan = 0
builds = []
scroll_offset = 0

running = True
while running:
    now = time.monotonic()
    if now - last_scan > 2:
        builds = scan_builds()
        last_scan = now
    
    all_items = STOREFRONTS + builds
    selected %= max(1, len(all_items))
    cur = all_items[selected]
    
    # Event loop
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                selected = (selected + 1) % len(all_items)
            elif event.key in (pygame.K_UP, pygame.K_w):
                selected = (selected - 1) % len(all_items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                message = launch_item(cur)
            elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                message = stop_item(cur)
            elif event.key == pygame.K_x:
                message = tone()
            elif pygame.K_1 <= event.key <= pygame.K_8:
                idx = event.key - pygame.K_1
                if idx < len(all_items):
                    selected = idx
                    message = launch_item(all_items[selected])
        elif event.type == pygame.MOUSEMOTION:
            pointer_dx, pointer_dy = event.rel
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            if event.button == 1:
                # Left pane item click
                if 30 <= mx <= 520 and 125 <= my <= 620:
                    idx = (my - 125) // 56 + scroll_offset
                    if 0 <= idx < len(all_items):
                        selected = idx
                        message = launch_item(all_items[selected])
                # Launch button
                elif 550 <= mx <= 700 and 560 <= my <= 605:
                    message = launch_item(cur)
                # Stop button
                elif 715 <= mx <= 840 and 560 <= my <= 605:
                    message = stop_item(cur)
                # Audio button
                elif 855 <= mx <= 1000 and 560 <= my <= 605:
                    message = tone()
            elif event.button == 4:
                scroll_offset = max(0, scroll_offset - 1)
            elif event.button == 5:
                scroll_offset = min(max(0, len(all_items) - 8), scroll_offset + 1)
        elif event.type == pygame.JOYDEVICEADDED:
            pad = pygame.joystick.Joystick(event.device_index)
            pad.init()
            pad_state = f'Gamepad Connected: {pad.get_name()[:40]}'
        elif event.type == pygame.JOYBUTTONDOWN:
            pad_state = f'Button {event.button} pressed'
            if event.button == 0:
                message = launch_item(cur)
            elif event.button == 1:
                message = stop_item(cur)
            elif event.button == 2:
                message = tone()
            elif event.button in (11, 13):
                selected = (selected + (1 if event.button == 13 else -1)) % len(all_items)
        elif event.type == pygame.JOYAXISMOTION:
            if event.axis == 1:
                if event.value > 0.6:
                    selected = (selected + 1) % len(all_items)
                    time.sleep(0.12)
                elif event.value < -0.6:
                    selected = (selected - 1) % len(all_items)
                    time.sleep(0.12)
            pad_state = f'Axis {event.axis}: {event.value:+.2f}'

    # Adjust scroll offset
    if selected < scroll_offset:
        scroll_offset = selected
    elif selected >= scroll_offset + 8:
        scroll_offset = selected - 7

    # Render frame
    w, h = screen.get_size()
    screen.fill(BG)
    for gy in range(0, min(h, 720), 3):
        t = gy / 720
        pygame.draw.rect(screen, (int(7 + 10*t), int(15 + 17*t), int(26 + 21*t)), (0, gy, w, 3))

    # Top Header Banner
    pygame.draw.rect(screen, (20, 41, 55), pygame.Rect(0, 0, w, 112))
    pygame.draw.rect(screen, ACCENT, pygame.Rect(0, 0, 7, 112))
    screen.blit(font_title.render('GAME LAB', True, TEXT_WHITE), (34, 16))
    screen.blit(font_body.render('LIBRARY    •    STORES    •    BUILDS    •    DIAGNOSTICS', True, ACCENT), (242, 29))
    screen.blit(font_small.render('Temporary interactive game development session', True, TEXT_MUTED), (36, 54))
    
    # Status pills in header
    pills = [
        ('T4 NVENC  •  H.264', GREEN),
        ('3D  •  llvmpipe', YELLOW),
        ('AUDIO  •  OPUS', GREEN),
        ('SESSION  •  gamer', GREEN)
    ]
    px = 36
    for ptext, pcolor in pills:
        s_surf = font_small.render(ptext, True, pcolor)
        pr = pygame.Rect(px, 78, s_surf.get_width() + 14, 24)
        pygame.draw.rect(screen, CARD_BG, pr, border_radius=6)
        pygame.draw.rect(screen, pcolor, pr, 1, border_radius=6)
        screen.blit(s_surf, (px + 7, 82))
        px += pr.width + 10

    screen.blit(font_small.render('YOUR LIBRARY', True, TEXT_MUTED), (36, 111))
    # Left Pane: Storefront & App List
    visible_items = all_items[scroll_offset:scroll_offset + 8]
    for i, it in enumerate(visible_items):
        actual_idx = scroll_offset + i
        y = 125 + i * 56
        is_sel = (actual_idx == selected)
        rect = pygame.Rect(30, y, 480, 50)
        
        pygame.draw.rect(screen, ITEM_SEL_BG if is_sel else ITEM_BG, rect, border_radius=10)
        if is_sel:
            pygame.draw.rect(screen, BORDER_SEL, rect, 2, border_radius=10)
            
        badge_rect = pygame.Rect(40, y + 10, 42, 30)
        pygame.draw.rect(screen, it['badge_color'], badge_rect, border_radius=6)
        b_txt = font_badge.render(it['badge'], True, TEXT_WHITE)
        screen.blit(b_txt, (badge_rect.centerx - b_txt.get_width() // 2, badge_rect.centery - b_txt.get_height() // 2))
        
        t_color = TEXT_WHITE if is_sel else (200, 215, 235)
        screen.blit(font_item.render(it['title'][:32], True, t_color), (92, y + 14))
        
        pstatus, pcolor = get_proc_status(it)
        dot_color = GREEN if 'RUNNING' in pstatus or pstatus == 'READY' else (RED if 'EXITED' in pstatus else TEXT_MUTED)
        pygame.draw.circle(screen, dot_color, (495, y + 25), 5)

    # Right Pane: Selected Item Detail Card
    card_rect = pygame.Rect(530, 125, 720, 490)
    pygame.draw.rect(screen, CARD_BG, card_rect, border_radius=14)
    pygame.draw.rect(screen, (30, 45, 75), card_rect, 1, border_radius=14)
    pygame.draw.rect(screen, cur['badge_color'], pygame.Rect(530, 125, 720, 5), border_top_left_radius=14, border_top_right_radius=14)

    # Card Title & Badge
    cb_rect = pygame.Rect(550, 145, 50, 32)
    pygame.draw.rect(screen, cur['badge_color'], cb_rect, border_radius=6)
    cb_txt = font_badge.render(cur['badge'], True, TEXT_WHITE)
    screen.blit(cb_txt, (cb_rect.centerx - cb_txt.get_width() // 2, cb_rect.centery - cb_txt.get_height() // 2))
    screen.blit(font_title.render(cur['title'], True, TEXT_WHITE), (610, 144))

    # Description
    desc_y = 190
    words = cur['desc'].split()
    line = ''
    for word in words:
        test_line = line + (' ' if line else '') + word
        if font_body.size(test_line)[0] > 670:
            screen.blit(font_body.render(line, True, (210, 225, 245)), (550, desc_y))
            desc_y += 22
            line = word
        else:
            line = test_line
    if line:
        screen.blit(font_body.render(line, True, (210, 225, 245)), (550, desc_y))
        desc_y += 26

    # Process Status Box
    pbox_rect = pygame.Rect(550, desc_y, 680, 50)
    pygame.draw.rect(screen, (13, 20, 35), pbox_rect, border_radius=8)
    pstatus, pcolor = get_proc_status(cur)
    screen.blit(font_small.render('PROCESS STATE:', True, TEXT_MUTED), (562, desc_y + 8))
    screen.blit(font_item.render(pstatus, True, pcolor), (562, desc_y + 24))
    desc_y += 62

    # Command line
    screen.blit(font_small.render('EXECUTION COMMAND:', True, TEXT_MUTED), (550, desc_y))
    desc_y += 18
    cmd_rect = pygame.Rect(550, desc_y, 680, 32)
    pygame.draw.rect(screen, (13, 20, 35), cmd_rect, border_radius=6)
    screen.blit(font_mono.render(cur['cmd'][:85], True, ACCENT), (560, desc_y + 8))
    desc_y += 44

    # Compatibility Box
    screen.blit(font_small.render('COMPATIBILITY & HARDWARE DIAGNOSTICS:', True, TEXT_MUTED), (550, desc_y))
    desc_y += 18
    compat_rect = pygame.Rect(550, desc_y, 680, 52)
    pygame.draw.rect(screen, (13, 20, 35), compat_rect, border_radius=6)
    screen.blit(font_small.render(cur['compat'][:95], True, YELLOW), (560, desc_y + 8))
    screen.blit(font_small.render('T4 NVENC captures screen. Games requiring hardware Vulkan/DXVK will fail without ICD.', True, TEXT_MUTED), (560, desc_y + 28))
    desc_y += 64

    # Log tail
    screen.blit(font_small.render('RECENT LOG OUTPUT:', True, TEXT_MUTED), (550, desc_y))
    desc_y += 18
    log_rect = pygame.Rect(550, desc_y, 680, 78)
    pygame.draw.rect(screen, (10, 15, 26), log_rect, border_radius=6)
    tails = read_tail(cur.get('log'), lines=4)
    for ly, line_txt in enumerate(tails):
        screen.blit(font_mono.render(line_txt[:90], True, (170, 185, 205)), (560, desc_y + 6 + ly * 17))
    desc_y += 90

    # Action Buttons
    btn_launch = pygame.Rect(550, 560, 150, 42)
    pygame.draw.rect(screen, (30, 110, 180), btn_launch, border_radius=8)
    screen.blit(font_item.render('▶ Launch (A)', True, TEXT_WHITE), (568, 571))
    
    btn_stop = pygame.Rect(715, 560, 130, 42)
    pygame.draw.rect(screen, (140, 40, 40), btn_stop, border_radius=8)
    screen.blit(font_item.render('■ Stop (B)', True, TEXT_WHITE), (735, 571))
    
    btn_audio = pygame.Rect(860, 560, 150, 42)
    pygame.draw.rect(screen, (30, 120, 90), btn_audio, border_radius=8)
    screen.blit(font_item.render('♫ Audio (X)', True, TEXT_WHITE), (878, 571))

    screen.blit(font_small.render('D-Pad/Stick: Navigate', True, TEXT_MUTED), (1030, 564))
    screen.blit(font_small.render('Enter: Launch', True, TEXT_MUTED), (1030, 584))

    # Bottom Area: Motion test bar + Diagnostics footer
    bottom_y = 625
    tick = now * 180
    for i in range(16):
        bx = int((tick + i * 85) % (w + 100)) - 50
        pygame.draw.rect(screen, (20 + i * 4, 45 + i * 5, 80 + i * 6),
                         pygame.Rect(bx, bottom_y, 25, 6), border_radius=3)
    
    # Status Row
    screen.blit(font_small.render(f'FPS: {clock.get_fps():.1f} | Display: {w}x{h} | Mouse: {pointer_dx:+d}, {pointer_dy:+d}', True, TEXT_WHITE), (34, 638))
    screen.blit(font_small.render(pad_state[:75], True, TEXT_MUTED), (34, 660))
    screen.blit(font_small.render(message[:110], True, ACCENT), (34, 684))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
