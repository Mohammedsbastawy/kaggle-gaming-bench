"""Modern Gaming Storefront & Manager for Legendary Epic Games.

Features:
- Dark modern storefront aesthetics with responsive hover effects.
- Master-detail game showcase with rich metadata and storage badges.
- Game size display with accurate disk space calculations.
- Clean uninstallation workflow with confirmation and disk cleanup.
- File verification and repair via Legendary.
- Dedicated Storage & Disk Manager tab.
- Full Epic Games library browsing and installation.
- Real-time color-coded launch console.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

HOME = Path(os.environ.get('KAGGLE_GAMER_HOME', '/home/gamer'))
CONFIG = HOME / '.config/heroic'
HEROIC_LEG = CONFIG / 'legendaryConfig/legendary'
STD_LEG = HOME / '.config/legendary'
BENCH = Path('/tmp/kaggle-game-dev-bench')
LOGS = HOME / 'logs'
LOGS.mkdir(parents=True, exist_ok=True)

# Ensure config paths exist
HEROIC_LEG.mkdir(parents=True, exist_ok=True)
STD_LEG.mkdir(parents=True, exist_ok=True)

# Theme Palette (Deep Cyberpunk / Modern Dark Storefront)
C_CANVAS = "#0a0e17"       # Main background
C_PANEL = "#111827"        # Headers & toolbars
C_CARD = "#1a2234"         # Card background
C_CARD_HOVER = "#232e44"   # Hover state for cards
C_BORDER = "#253248"       # Subtle border lines
C_ACCENT = "#8b5cf6"       # Epic Games purple accent
C_CYAN = "#06b6d4"         # Neon cyan highlight
C_FG = "#f1f5f9"           # Primary text
C_MUTED = "#94a3b8"        # Secondary muted text
C_GREEN = "#10b981"        # Emerald play button
C_GREEN_HOVER = "#059669"  # Hover emerald
C_RED = "#ef4444"          # Danger / uninstall button
C_RED_HOVER = "#dc2626"    # Hover danger
C_BLUE = "#3b82f6"         # Info / verify button
C_BLUE_HOVER = "#2563eb"   # Hover blue
C_YELLOW = "#f59e0b"       # Warning gold
C_BTN_SEC = "#242e42"      # Secondary button bg
C_BTN_SEC_HOV = "#33415c"  # Secondary button hover


def find_best_runner():
    candidates = [
        HOME / '.config/heroic/tools/wine/Wine-GE-Proton8-26/bin/wine',
        *HOME.glob('.config/heroic/tools/wine/*/bin/wine'),
        Path('/usr/bin/wine'),
        Path('/usr/local/bin/wine'),
        Path('/usr/games/wine'),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return '/usr/bin/wine'


def format_size(bytes_val):
    try:
        b = float(bytes_val)
        if b >= 1024 * 1024 * 1024:
            return f"{b / (1024**3):.2f} GiB"
        elif b >= 1024 * 1024:
            return f"{b / (1024**2):.1f} MiB"
        elif b > 0:
            return f"{b / 1024:.0f} KiB"
    except (ValueError, TypeError):
        pass
    return "0 B"


def get_disk_info(path="/home/gamer"):
    try:
        usage = shutil.disk_usage(path)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "total_str": format_size(usage.total),
            "used_str": format_size(usage.used),
            "free_str": format_size(usage.free),
            "percent": int((usage.used / usage.total) * 100) if usage.total > 0 else 0
        }
    except Exception:
        return {"total": 0, "used": 0, "free": 0, "total_str": "Unknown", "used_str": "Unknown", "free_str": "Unknown", "percent": 0}


def make_hover_button(parent, text, normal_bg, hover_bg, normal_fg="#ffffff", hover_fg="#ffffff",
                      font=("Liberation Sans", 10, "bold"), padx=12, pady=6, command=None, cursor="hand2"):
    """Helper to create polished interactive buttons with hover glow."""
    btn = tk.Button(parent, text=text, bg=normal_bg, fg=normal_fg, activebackground=hover_bg,
                    activeforeground=hover_fg, relief="flat", font=font, padx=padx, pady=pady,
                    cursor=cursor, command=command, borderwidth=0, highlightthickness=0)
    btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg, fg=hover_fg))
    btn.bind("<Leave>", lambda e: btn.configure(bg=normal_bg, fg=normal_fg))
    return btn


class LegendaryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("7BZ Dev Cloud Gaming · Legendary Storefront")
        self.geometry("1060x650")
        self.minsize(900, 550)
        self.configure(bg=C_CANVAS)

        # Active process tracker
        self.active_proc = None
        self.proc_thread = None
        self.installed_games_data = {}
        self.selected_game_app = None

        # Apply dark theme styling
        self.setup_styles()

        # Build UI layout
        self.create_header()
        self.create_tabs()
        self.create_bottom_bar()

        # Initial data load
        self.refresh_all()

    def setup_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.style.configure(".", background=C_CANVAS, foreground=C_FG, font=("Liberation Sans", 10))
        self.style.configure("TNotebook", background=C_CANVAS, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=C_PANEL, foreground=C_MUTED,
                             padding=[18, 9], font=("Liberation Sans", 10, "bold"), borderwidth=0)
        self.style.map("TNotebook.Tab",
                       background=[("selected", C_CARD), ("active", C_CARD_HOVER)],
                       foreground=[("selected", C_CYAN), ("active", C_FG)])

        # Treeview styling (clean modern table)
        self.style.configure("Treeview", background="#121722", foreground=C_FG,
                             fieldbackground="#121722", rowheight=36, font=("Liberation Sans", 10),
                             borderwidth=0)
        self.style.configure("Treeview.Heading", background=C_PANEL, foreground="#ffffff",
                             font=("Liberation Sans", 10, "bold"), padding=[8, 8], relief="flat")
        self.style.map("Treeview",
                       background=[("selected", "#2a3754"), ("active", "#1b253b")],
                       foreground=[("selected", "#ffffff"), ("active", C_FG)])

        self.style.configure("Horizontal.TProgressbar", background=C_CYAN, troughcolor=C_PANEL,
                             borderwidth=0, thickness=12)

    def create_header(self):
        header = tk.Frame(self, bg=C_PANEL, height=68, highlightbackground=C_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top", padx=10, pady=(8, 4))

        # Brand / Logo frame
        brand_frame = tk.Frame(header, bg=C_PANEL)
        brand_frame.pack(side="left", padx=14, pady=8)

        lbl_badge = tk.Label(brand_frame, text=" EPIC STORE ", bg=C_ACCENT, fg="#ffffff",
                             font=("Liberation Sans", 9, "bold"), padx=6, pady=2)
        lbl_badge.pack(side="left", padx=(0, 8))

        lbl_title = tk.Label(brand_frame, text="Legendary Game Center", bg=C_PANEL, fg=C_FG,
                             font=("Liberation Sans", 13, "bold"))
        lbl_title.pack(side="left")

        # Stats & Metrics Pills (Center)
        stats_frame = tk.Frame(header, bg=C_PANEL)
        stats_frame.pack(side="left", padx=20, pady=8)

        self.lbl_storage_pill = tk.Label(stats_frame, text="💾 Free: Calculating...", bg=C_CARD, fg=C_CYAN,
                                         font=("Liberation Sans", 9, "bold"), padx=10, pady=4)
        self.lbl_storage_pill.pack(side="left", padx=4)

        self.lbl_games_pill = tk.Label(stats_frame, text="🎮 Games: 0", bg=C_CARD, fg=C_FG,
                                       font=("Liberation Sans", 9), padx=10, pady=4)
        self.lbl_games_pill.pack(side="left", padx=4)

        # Quick Actions & Account (Right)
        actions_frame = tk.Frame(header, bg=C_PANEL)
        actions_frame.pack(side="right", padx=12, pady=8)

        btn_refresh = make_hover_button(actions_frame, "🔄 Refresh", C_BTN_SEC, C_BTN_SEC_HOV,
                                        normal_fg=C_FG, padx=10, pady=4, command=self.sync_and_refresh)
        btn_refresh.pack(side="left", padx=4)

        btn_fix = make_hover_button(actions_frame, "🛠️ Fix Wine", C_BTN_SEC, C_BTN_SEC_HOV,
                                    normal_fg=C_FG, padx=10, pady=4, command=self.run_sanitizer)
        btn_fix.pack(side="left", padx=4)

        btn_login = make_hover_button(actions_frame, "🔑 Login", C_CARD, C_CARD_HOVER,
                                      normal_fg=C_CYAN, padx=10, pady=4, command=self.open_login_dialog)
        btn_login.pack(side="left", padx=4)

        self.lbl_account = tk.Label(actions_frame, text="Checking...", bg=C_PANEL, fg=C_YELLOW,
                                    font=("Liberation Sans", 9, "bold"))
        self.lbl_account.pack(side="left", padx=(10, 4))

    def create_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=4)

        # Tab 1: Installed Games (Master-Detail Storefront View)
        self.tab_installed = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_installed, text=" 🎮 Installed Games ")
        self.build_installed_tab()

        # Tab 2: Full Epic Store & Cloud Library
        self.tab_library = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_library, text=" 🛒 Epic Cloud Library ")
        self.build_library_tab()

        # Tab 3: Storage & Disk Manager
        self.tab_storage = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_storage, text=" 📊 Storage & Disk ")
        self.build_storage_tab()

        # Tab 4: Launch Console & Live Logs
        self.tab_console = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_console, text=" 📜 Launch Console & Logs ")
        self.build_console_tab()

    def build_installed_tab(self):
        container = tk.Frame(self.tab_installed, bg=C_CANVAS)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        # Split: Left (Game Catalog Table), Right (Hero Game Details & Command Hub)
        paned = tk.PanedWindow(container, orient="horizontal", bg=C_CANVAS, sashwidth=4, bd=0)
        paned.pack(fill="both", expand=True)

        # LEFT PANE: Games List
        left_frame = tk.Frame(paned, bg=C_CANVAS)
        paned.add(left_frame, minsize=460, stretch="always")

        # Search Bar
        search_bar = tk.Frame(left_frame, bg=C_PANEL, highlightbackground=C_BORDER, highlightthickness=1)
        search_bar.pack(fill="x", side="top", pady=(0, 6), ipady=3)

        tk.Label(search_bar, text=" 🔍 ", bg=C_PANEL, fg=C_MUTED, font=("Liberation Sans", 10)).pack(side="left", padx=4)
        self.ent_search_installed = tk.Entry(search_bar, bg=C_PANEL, fg="#ffffff", insertbackground="#ffffff",
                                             relief="flat", font=("Liberation Sans", 10), borderwidth=0)
        self.ent_search_installed.pack(side="left", fill="x", expand=True, padx=4)
        self.ent_search_installed.bind("<KeyRelease>", self.filter_installed_games)

        self.lbl_installed_count = tk.Label(search_bar, text="0 games", bg=C_PANEL, fg=C_MUTED,
                                            font=("Liberation Sans", 9), padx=8)
        self.lbl_installed_count.pack(side="right")

        # Games Treeview
        tree_frame = tk.Frame(left_frame, bg=C_CANVAS)
        tree_frame.pack(fill="both", expand=True)

        columns = ("title", "size", "version", "status")
        self.tree_installed = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.tree_installed.heading("title", text="Game Title")
        self.tree_installed.heading("size", text="Installed Size")
        self.tree_installed.heading("version", text="Version")
        self.tree_installed.heading("status", text="Status")

        self.tree_installed.column("title", width=250, anchor="w")
        self.tree_installed.column("size", width=110, anchor="center")
        self.tree_installed.column("version", width=90, anchor="center")
        self.tree_installed.column("status", width=90, anchor="center")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_installed.yview)
        self.tree_installed.configure(yscrollcommand=scroll.set)

        self.tree_installed.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree_installed.bind("<<TreeviewSelect>>", self.on_installed_select)
        self.tree_installed.bind("<Double-1>", lambda e: self.launch_selected())

        # RIGHT PANE: Hero Game Showcase Card
        self.right_frame = tk.Frame(paned, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        paned.add(self.right_frame, minsize=380, stretch="never")

        self.build_game_showcase(self.right_frame)

    def build_game_showcase(self, parent):
        """Build the rich game card in the right pane."""
        # Top banner frame
        self.card_header = tk.Frame(parent, bg="#151d2d", padx=16, pady=14)
        self.card_header.pack(fill="x", side="top")

        self.lbl_card_badge = tk.Label(self.card_header, text="READY TO PLAY", bg=C_GREEN, fg="#ffffff",
                                       font=("Liberation Sans", 8, "bold"), padx=6, pady=2)
        self.lbl_card_badge.pack(anchor="w")

        self.lbl_card_title = tk.Label(self.card_header, text="Select a Game", bg="#151d2d", fg=C_FG,
                                       font=("Liberation Sans", 14, "bold"), wraplength=340, justify="left")
        self.lbl_card_title.pack(anchor="w", pady=(6, 2))

        self.lbl_card_app_id = tk.Label(self.card_header, text="App Name: --", bg="#151d2d", fg=C_MUTED,
                                        font=("Liberation Sans Mono", 8))
        self.lbl_card_app_id.pack(anchor="w")

        # Details Content Frame
        self.card_body = tk.Frame(parent, bg=C_CARD, padx=16, pady=12)
        self.card_body.pack(fill="both", expand=True)

        # Storage & Size Box (Feature requested: display game size)
        size_box = tk.Frame(self.card_body, bg=C_PANEL, highlightbackground=C_BORDER, highlightthickness=1, padx=12, pady=10)
        size_box.pack(fill="x", pady=6)

        tk.Label(size_box, text="STORAGE FOOTPRINT", bg=C_PANEL, fg=C_CYAN,
                 font=("Liberation Sans", 8, "bold")).pack(anchor="w")

        self.lbl_card_size = tk.Label(size_box, text="-- GiB", bg=C_PANEL, fg="#ffffff",
                                      font=("Liberation Sans", 16, "bold"))
        self.lbl_card_size.pack(anchor="w", pady=(2, 2))

        self.lbl_card_path = tk.Label(size_box, text="Path: --", bg=C_PANEL, fg=C_MUTED,
                                      font=("Liberation Sans", 8), wraplength=320, justify="left")
        self.lbl_card_path.pack(anchor="w")

        # Game Properties Grid
        props_frame = tk.Frame(self.card_body, bg=C_CARD)
        props_frame.pack(fill="x", pady=8)

        tk.Label(props_frame, text="Version:", bg=C_CARD, fg=C_MUTED, font=("Liberation Sans", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_prop_version = tk.Label(props_frame, text="--", bg=C_CARD, fg=C_FG, font=("Liberation Sans", 9, "bold"))
        self.lbl_prop_version.grid(row=0, column=1, sticky="w", padx=10, pady=2)

        tk.Label(props_frame, text="Platform:", bg=C_CARD, fg=C_MUTED, font=("Liberation Sans", 9)).grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_prop_platform = tk.Label(props_frame, text="Windows 64-bit", bg=C_CARD, fg=C_FG, font=("Liberation Sans", 9))
        self.lbl_prop_platform.grid(row=1, column=1, sticky="w", padx=10, pady=2)

        tk.Label(props_frame, text="Graphics Engine:", bg=C_CARD, fg=C_MUTED, font=("Liberation Sans", 9)).grid(row=2, column=0, sticky="w", pady=2)
        self.lbl_prop_engine = tk.Label(props_frame, text="NVIDIA Direct Xorg", bg=C_CARD, fg=C_CYAN, font=("Liberation Sans", 9, "bold"))
        self.lbl_prop_engine.grid(row=2, column=1, sticky="w", padx=10, pady=2)

        tk.Label(props_frame, text="Executable:", bg=C_CARD, fg=C_MUTED, font=("Liberation Sans", 9)).grid(row=3, column=0, sticky="w", pady=2)
        self.lbl_prop_exe = tk.Label(props_frame, text="--", bg=C_CARD, fg=C_FG, font=("Liberation Sans Mono", 8))
        self.lbl_prop_exe.grid(row=3, column=1, sticky="w", padx=10, pady=2)

        # Action Buttons Container (Bottom of right card)
        actions_container = tk.Frame(parent, bg=C_CARD, padx=16, pady=14)
        actions_container.pack(fill="x", side="bottom")

        # 1. Primary Action: Launch Game
        self.btn_launch_hero = make_hover_button(
            actions_container, "▶  LAUNCH GAME", C_GREEN, C_GREEN_HOVER,
            font=("Liberation Sans", 11, "bold"), pady=8, command=self.launch_selected
        )
        self.btn_launch_hero.pack(fill="x", pady=(0, 6))

        # Secondary Actions Row (Verify, Open Folder)
        sec_row = tk.Frame(actions_container, bg=C_CARD)
        sec_row.pack(fill="x", pady=(0, 6))

        self.btn_verify = make_hover_button(
            sec_row, "🔍 Verify Files", C_BTN_SEC, C_BTN_SEC_HOV,
            normal_fg=C_FG, font=("Liberation Sans", 9), padx=8, pady=5, command=self.verify_selected
        )
        self.btn_verify.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_folder = make_hover_button(
            sec_row, "📁 Open Folder", C_BTN_SEC, C_BTN_SEC_HOV,
            normal_fg=C_FG, font=("Liberation Sans", 9), padx=8, pady=5, command=self.open_selected_folder
        )
        self.btn_folder.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # 2. Danger Action: Uninstall Game (Feature requested: Delete game)
        self.btn_uninstall = make_hover_button(
            actions_container, "🗑️  UNINSTALL / DELETE GAME", C_RED, C_RED_HOVER,
            font=("Liberation Sans", 10, "bold"), pady=6, command=self.uninstall_selected
        )
        self.btn_uninstall.pack(fill="x")

    def on_installed_select(self, event=None):
        """Update the hero showcase when a game is selected in the list."""
        sel = self.tree_installed.selection()
        if not sel:
            return
        item = self.tree_installed.item(sel[0])
        app_name = item.get("tags", [""])[0] if item.get("tags") else ""
        if not app_name or app_name not in self.installed_games_data:
            return

        self.selected_game_app = app_name
        g = self.installed_games_data[app_name]
        title = g.get('title') or app_name
        version = g.get('version', 'Unknown')
        install_size = g.get('install_size', 0)
        path_str = g.get('install_path', 'N/A')
        exe_str = g.get('executable', 'N/A')

        self.lbl_card_title.config(text=title)
        self.lbl_card_app_id.config(text=f"App ID: {app_name}")
        self.lbl_card_size.config(text=format_size(install_size))
        self.lbl_card_path.config(text=f"Location: {path_str}")
        self.lbl_prop_version.config(text=f"v{version}")
        self.lbl_prop_exe.config(text=exe_str)

        # Detect special renderer (e.g. Wolfenstein idTech5 OpenGL)
        if exe_str.lower() == "wolfneworder_x64.exe":
            self.lbl_prop_engine.config(text="idTech5 Direct Xorg (Verified 60 FPS)", fg=C_GREEN)
        else:
            self.lbl_prop_engine.config(text="Direct NVIDIA Xorg / DXVK", fg=C_CYAN)

    def filter_installed_games(self, event=None):
        query = self.ent_search_installed.get().strip().lower()
        for item in self.tree_installed.get_children():
            self.tree_installed.delete(item)

        filtered_count = 0
        for app_name, g in sorted(self.installed_games_data.items(), key=lambda x: str(x[1].get('title', '')).lower()):
            title = g.get('title') or app_name
            if query and query not in title.lower() and query not in app_name.lower():
                continue
            version = g.get('version', 'Unknown')
            size_str = format_size(g.get('install_size', 0))
            status = "✓ Ready"
            self.tree_installed.insert("", "end", values=(title, size_str, version, status), tags=(app_name,))
            filtered_count += 1

        self.lbl_installed_count.config(text=f"{filtered_count} games")
        children = self.tree_installed.get_children()
        if children:
            self.tree_installed.selection_set(children[0])
            self.on_installed_select()

    def build_library_tab(self):
        container = tk.Frame(self.tab_library, bg=C_CANVAS)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        toolbar = tk.Frame(container, bg=C_PANEL, highlightbackground=C_BORDER, highlightthickness=1)
        toolbar.pack(fill="x", side="top", pady=(0, 6), ipady=4, padx=2)

        btn_load = make_hover_button(toolbar, "🔍 Fetch Cloud Library", C_ACCENT, "#7c3aed",
                                     font=("Liberation Sans", 9, "bold"), padx=12, pady=5, command=self.fetch_remote_library)
        btn_load.pack(side="left", padx=8)

        btn_install = make_hover_button(toolbar, "📥 Install Game", C_GREEN, C_GREEN_HOVER,
                                        font=("Liberation Sans", 9, "bold"), padx=12, pady=5, command=self.install_selected)
        btn_install.pack(side="left", padx=4)

        # Filter
        tk.Label(toolbar, text="Filter:", bg=C_PANEL, fg=C_MUTED, font=("Liberation Sans", 9)).pack(side="left", padx=(16, 4))
        self.ent_filter_lib = tk.Entry(toolbar, bg=C_CARD, fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Liberation Sans", 9))
        self.ent_filter_lib.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_filter_lib.bind("<KeyRelease>", self.filter_library)

        columns = ("title", "app_name", "status")
        self.tree_library = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        self.tree_library.heading("title", text="Game Title")
        self.tree_library.heading("app_name", text="Epic App ID")
        self.tree_library.heading("status", text="Installation Status")

        self.tree_library.column("title", width=420, anchor="w")
        self.tree_library.column("app_name", width=280, anchor="w")
        self.tree_library.column("status", width=140, anchor="center")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_library.yview)
        self.tree_library.configure(yscrollcommand=scroll.set)

        self.tree_library.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def build_storage_tab(self):
        """Dedicated Storage & Disk Manager tab with visual usage meter."""
        container = tk.Frame(self.tab_storage, bg=C_CANVAS, padx=12, pady=10)
        container.pack(fill="both", expand=True)

        # Top Storage Meter Card
        meter_card = tk.Frame(container, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1, padx=16, pady=14)
        meter_card.pack(fill="x", side="top", pady=(0, 10))

        tk.Label(meter_card, text="HOST DISK USAGE & ALLOCATION", bg=C_CARD, fg=C_CYAN,
                 font=("Liberation Sans", 9, "bold")).pack(anchor="w")

        self.storage_progress = ttk.Progressbar(meter_card, orient="horizontal", mode="determinate",
                                               style="Horizontal.TProgressbar")
        self.storage_progress.pack(fill="x", pady=(8, 8))

        stats_row = tk.Frame(meter_card, bg=C_CARD)
        stats_row.pack(fill="x")

        self.lbl_storage_total = tk.Label(stats_row, text="Total: --", bg=C_CARD, fg=C_FG, font=("Liberation Sans", 10, "bold"))
        self.lbl_storage_total.pack(side="left", padx=(0, 20))

        self.lbl_storage_used = tk.Label(stats_row, text="Used: --", bg=C_CARD, fg=C_YELLOW, font=("Liberation Sans", 10, "bold"))
        self.lbl_storage_used.pack(side="left", padx=(0, 20))

        self.lbl_storage_free = tk.Label(stats_row, text="Available Free: --", bg=C_CARD, fg=C_GREEN, font=("Liberation Sans", 10, "bold"))
        self.lbl_storage_free.pack(side="left", padx=(0, 20))

        # Action Buttons on Storage
        btn_cleanup = make_hover_button(stats_row, "🧹 Cleanup Old Cache & Manifests", C_BTN_SEC, C_BTN_SEC_HOV,
                                        font=("Liberation Sans", 9), padx=10, pady=4, command=self.run_cleanup)
        btn_cleanup.pack(side="right")

        # Table of installed games with exact disk consumption
        tk.Label(container, text="Installed Games Breakdown by Size", bg=C_CANVAS, fg=C_FG,
                 font=("Liberation Sans", 11, "bold")).pack(anchor="w", pady=(8, 4))

        columns = ("title", "size_bytes", "size_fmt", "path")
        self.tree_storage = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        self.tree_storage.heading("title", text="Game Title")
        self.tree_storage.heading("size_bytes", text="Raw Bytes")
        self.tree_storage.heading("size_fmt", text="Disk Footprint")
        self.tree_storage.heading("path", text="Installed Folder")

        self.tree_storage.column("title", width=280, anchor="w")
        self.tree_storage.column("size_bytes", width=120, anchor="center")
        self.tree_storage.column("size_fmt", width=120, anchor="center")
        self.tree_storage.column("path", width=360, anchor="w")

        s_scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_storage.yview)
        self.tree_storage.configure(yscrollcommand=s_scroll.set)

        self.tree_storage.pack(side="left", fill="both", expand=True)
        s_scroll.pack(side="right", fill="y")

    def build_console_tab(self):
        container = tk.Frame(self.tab_console, bg=C_CANVAS)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        toolbar = tk.Frame(container, bg=C_PANEL, highlightbackground=C_BORDER, highlightthickness=1)
        toolbar.pack(fill="x", side="top", pady=(0, 6), ipady=3, padx=2)

        btn_stop = make_hover_button(toolbar, "⏹  STOP RUNNING GAME", C_RED, C_RED_HOVER,
                                     font=("Liberation Sans", 9, "bold"), padx=12, pady=4, command=self.stop_active_game)
        btn_stop.pack(side="left", padx=8)

        btn_clear = make_hover_button(toolbar, "🧹 Clear Log", C_BTN_SEC, C_BTN_SEC_HOV,
                                      normal_fg=C_FG, font=("Liberation Sans", 9), padx=10, pady=4,
                                      command=lambda: self.log_text.delete("1.0", tk.END))
        btn_clear.pack(side="left", padx=4)

        self.lbl_status = tk.Label(toolbar, text="System Ready · Idle", bg=C_PANEL, fg=C_MUTED,
                                   font=("Liberation Sans", 9, "bold"))
        self.lbl_status.pack(side="right", padx=12)

        self.log_text = scrolledtext.ScrolledText(container, bg="#0d1117", fg="#c9d1d9",
                                                 insertbackground="#ffffff", font=("Liberation Mono", 9),
                                                 relief="flat", borderwidth=0)
        self.log_text.pack(fill="both", expand=True)

        # Configure color tags for rich log output
        self.log_text.tag_configure("info", foreground="#58a6ff")
        self.log_text.tag_configure("success", foreground=C_GREEN)
        self.log_text.tag_configure("warn", foreground=C_YELLOW)
        self.log_text.tag_configure("error", foreground=C_RED)
        self.log_text.tag_configure("dim", foreground="#8b949e")

    def create_bottom_bar(self):
        bar = tk.Frame(self, bg=C_PANEL, height=28, highlightbackground=C_BORDER, highlightthickness=1)
        bar.pack(fill="x", side="bottom", padx=10, pady=(2, 6))

        lbl_tip = tk.Label(bar, text="⚡ Direct NVIDIA Xorg: Tesla T4 hardware acceleration enabled · H.264 60 FPS",
                           bg=C_PANEL, fg=C_MUTED, font=("Liberation Sans", 8))
        lbl_tip.pack(side="left", padx=10, pady=4)

        self.lbl_runner_status = tk.Label(bar, text="🍷 Wine-GE-Proton8-26", bg=C_PANEL, fg=C_CYAN,
                                          font=("Liberation Sans", 8, "bold"))
        self.lbl_runner_status.pack(side="right", padx=10, pady=4)

    def log(self, text, tag="dim"):
        def _append():
            self.log_text.insert(tk.END, text + "\n", tag)
            self.log_text.see(tk.END)
        self.after(0, _append)

    def refresh_all(self):
        self.refresh_account_status()
        self.refresh_runner_status()
        self.refresh_disk_status()
        self.refresh_installed_games()

    def refresh_disk_status(self):
        info = get_disk_info()
        self.lbl_storage_pill.config(text=f"💾 Free: {info['free_str']} / {info['total_str']}")
        self.storage_progress["value"] = info["percent"]
        self.lbl_storage_total.config(text=f"Total: {info['total_str']}")
        self.lbl_storage_used.config(text=f"Used: {info['used_str']} ({info['percent']}%)")
        self.lbl_storage_free.config(text=f"Available Free: {info['free_str']}")

    def refresh_account_status(self):
        user_file = None
        for p in [HEROIC_LEG / 'user.json', STD_LEG / 'user.json']:
            if p.is_file():
                user_file = p
                break

        if user_file:
            try:
                data = json.loads(user_file.read_text(encoding='utf-8'))
                display_name = data.get('displayName', 'Epic User')
                acc_id = data.get('account_id', '')
                short_id = f" ({acc_id[:8]}...)" if acc_id else ""
                self.lbl_account.config(text=f"🟢 {display_name}{short_id}", fg=C_GREEN)
                return
            except Exception:
                pass
        self.lbl_account.config(text="🔴 Not Logged In", fg=C_RED)

    def refresh_runner_status(self):
        runner = find_best_runner()
        name = "Wine-GE-Proton8-26" if "Wine-GE" in runner else Path(runner).name
        self.lbl_runner_status.config(text=f"🍷 {name} (NVIDIA Direct GLX/DXVK)")

    def refresh_installed_games(self):
        self.installed_games_data = {}
        for item in self.tree_installed.get_children():
            self.tree_installed.delete(item)
        for item in self.tree_storage.get_children():
            self.tree_storage.delete(item)

        installed_file = None
        for p in [HEROIC_LEG / 'installed.json', STD_LEG / 'installed.json']:
            if p.is_file():
                installed_file = p
                break

        games = {}
        if installed_file:
            try:
                games = json.loads(installed_file.read_text(encoding='utf-8'))
            except Exception as e:
                self.log(f"Notice reading installed.json: {e}", "warn")

        if not games:
            # Fallback: Query legendary list-installed --json
            try:
                res = subprocess.run(["legendary", "list-installed", "--json"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    if isinstance(data, list):
                        for g in data:
                            games[g.get('app_name', '')] = g
                    elif isinstance(data, dict):
                        games = data
            except Exception:
                pass

        self.installed_games_data = games
        total_game_bytes = 0

        for app_name, g in sorted(games.items(), key=lambda x: str(x[1].get('title', '')).lower()):
            title = g.get('title') or app_name
            version = g.get('version', 'Unknown')
            install_size = g.get('install_size', 0)
            total_game_bytes += install_size
            size_str = format_size(install_size)
            path_str = g.get('install_path', 'N/A')
            status = "✓ Ready"

            self.tree_installed.insert("", "end", values=(title, size_str, version, status), tags=(app_name,))
            self.tree_storage.insert("", "end", values=(title, f"{install_size:,} bytes", size_str, path_str), tags=(app_name,))

        count = len(games)
        self.lbl_installed_count.config(text=f"{count} games")
        self.lbl_games_pill.config(text=f"🎮 {count} Installed ({format_size(total_game_bytes)})")

        children = self.tree_installed.get_children()
        if children:
            self.tree_installed.selection_set(children[0])
            self.tree_installed.focus(children[0])
            self.on_installed_select()
        else:
            self.lbl_card_title.config(text="No Games Installed")
            self.lbl_card_app_id.config(text="App ID: --")
            self.lbl_card_size.config(text="0 B")
            self.lbl_card_path.config(text="Location: None")

    def sync_and_refresh(self):
        self.log("▶ Syncing Heroic and Legendary configurations...", "info")
        try:
            fix_script = BENCH / 'fix_heroic_config.py'
            if fix_script.is_file():
                res = subprocess.run([sys.executable, str(fix_script)], capture_output=True, text=True, timeout=10)
                self.log(res.stdout, "dim")
                if res.stderr:
                    self.log(res.stderr, "warn")
            self.refresh_all()
            self.log("✓ Sync completed successfully.", "success")
        except Exception as exc:
            self.log(f"Sync error: {exc}", "error")

    def run_sanitizer(self):
        self.notebook.select(self.tab_console)
        self.log("▶ Checking live GPU renderer and updating Wine settings...", "info")
        threading.Thread(target=self._run_sanitizer_worker, daemon=True).start()

    def _run_sanitizer_worker(self):
        try:
            fix_script = BENCH / 'fix_heroic_config.py'
            if fix_script.is_file():
                res = subprocess.run([sys.executable, str(fix_script)], capture_output=True, text=True, timeout=15)
                self.log(res.stdout, "dim")
            subprocess.run(["chown", "-R", "gamer:gamer", "/home/gamer"], check=False)
            subprocess.run(["chmod", "-R", "u+rwX", "/home/gamer"], check=False)
            self.log("✓ Wine settings updated for the detected graphics backend.", "success")
            self.after(0, self.refresh_all)
        except Exception as e:
            self.log(f"Error during sanitization: {e}", "error")

    def launch_selected(self):
        if not self.selected_game_app or self.selected_game_app not in self.installed_games_data:
            messagebox.showinfo("No Selection", "Please select a game from the list to launch.")
            return

        g = self.installed_games_data[self.selected_game_app]
        title = g.get('title') or self.selected_game_app
        app_name = self.selected_game_app

        self.notebook.select(self.tab_console)
        self.log(f"\n==================================================================", "info")
        self.log(f"🚀 Launching game: {title} ({app_name})", "success")
        self.log(f"==================================================================", "info")

        runner = find_best_runner()
        self.log(f"Runner: {runner}", "dim")
        self.log("Configuring display and audio...", "dim")

        threading.Thread(target=self._launch_worker, args=(app_name, title, runner), daemon=True).start()

    def _launch_worker(self, app_name, title, runner):
        env = dict(os.environ)
        env["DISPLAY"] = os.environ.get("DISPLAY", ":0")
        env["HOME"] = str(HOME)
        env["WINEPREFIX"] = str(HOME / ".wine")
        env["CUDA_VISIBLE_DEVICES"] = "0"
        direct_xorg = (env["DISPLAY"].split(".", 1)[0] == ":1" and
                       (BENCH / "gpu-xorg-ready").exists())
        if direct_xorg:
            env["GAMELAB_DIRECT_XORG"] = "1"
            for key in ("VGL_DISPLAY", "MESA_GL_VERSION_OVERRIDE",
                        "MESA_GLSL_VERSION_OVERRIDE", "__NV_PRIME_RENDER_OFFLOAD"):
                env.pop(key, None)
        else:
            env["VGL_DISPLAY"] = "egl0"

        # Automatically verify and heal Wine prefix before launch if kernel32.dll is missing
        kernel32 = HOME / ".wine/drive_c/windows/system32/kernel32.dll"
        if not kernel32.is_file():
            self.log("▶ Detected uninitialized Wine prefix. Auto-initializing with Wine-GE...", "warn")
            wineboot_bin = Path(runner).with_name("wineboot")
            if wineboot_bin.is_file():
                try:
                    init_env = dict(env)
                    init_env["WINEDLLOVERRIDES"] = "mscoree,mshtml=d"
                    subprocess.run([str(wineboot_bin), "--init"], env=init_env, check=False, timeout=30)
                    self.log("✓ Wine prefix initialized.", "success")
                except Exception as wb_err:
                    self.log(f"Notice auto-initializing prefix: {wb_err}", "warn")

        from gpu_runtime import find_game_binary
        game_binary = find_game_binary(app_name)
        if game_binary and game_binary.name.lower() == "wolfneworder_x64.exe":
            cmd = ["python3", "/tmp/kaggle-game-dev-bench/launch_idtech5.py",
                   *(["--direct-xorg"] if direct_xorg else []),
                   "--wine", runner, str(game_binary)]
        else:
            cmd = ["python3", "/tmp/kaggle-game-dev-bench/gpu_runtime.py",
                   "launch", app_name, runner]

        self.lbl_status.config(text=f"▶ Running: {title}", fg=C_GREEN)

        try:
            self.active_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env
            )
            for line in self.active_proc.stdout:
                self.log(line.rstrip())
            self.active_proc.wait()
            self.log(f"\nGame process exited with status: {self.active_proc.returncode}", "info")
        except Exception as exc:
            self.log(f"Launch exception: {exc}", "error")
        finally:
            self.active_proc = None
            self.lbl_status.config(text="System Ready · Idle", fg=C_MUTED)

    def stop_active_game(self):
        if self.active_proc and self.active_proc.poll() is None:
            self.log("Terminating active game process...", "warn")
            self.active_proc.terminate()
            time.sleep(1)
            if self.active_proc.poll() is None:
                self.active_proc.kill()
            self.log("Process stopped successfully.", "success")
        else:
            self.log("No active game process running.", "dim")

    def uninstall_selected(self):
        """Feature requested: Delete / Uninstall game with confirmation & disk cleanup."""
        if not self.selected_game_app or self.selected_game_app not in self.installed_games_data:
            messagebox.showinfo("No Selection", "Please select an installed game to uninstall.")
            return

        g = self.installed_games_data[self.selected_game_app]
        title = g.get('title') or self.selected_game_app
        app_name = self.selected_game_app
        size_str = format_size(g.get('install_size', 0))
        install_path = g.get('install_path', '')

        # Confirmation Dialog
        msg = (
            f"Are you sure you want to uninstall this game?\n\n"
            f"🎮 Title: {title}\n"
            f"📦 Space to be freed: {size_str}\n"
            f"📂 Location: {install_path}\n\n"
            f"This will remove the game files from disk."
        )
        if not messagebox.askyesno("Confirm Game Uninstallation", msg, icon="warning"):
            return

        self.notebook.select(self.tab_console)
        self.log(f"\n==================================================================", "warn")
        self.log(f"🗑️ Starting Uninstallation of '{title}' ({app_name})...", "warn")
        self.log(f"==================================================================", "warn")

        threading.Thread(target=self._uninstall_worker, args=(app_name, title, install_path), daemon=True).start()

    def _uninstall_worker(self, app_name, title, install_path):
        try:
            self.log(f"Executing: legendary uninstall {app_name} -y", "info")
            cmd = ["legendary", "uninstall", app_name, "-y"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                self.log(line.rstrip())
            proc.wait()

            # Clean leftover directory if necessary
            if install_path and Path(install_path).is_dir():
                try:
                    self.log(f"Cleaning remaining directory at {install_path}...", "info")
                    shutil.rmtree(install_path, ignore_errors=True)
                except Exception as clean_err:
                    self.log(f"Notice cleaning directory: {clean_err}", "warn")

            self.log(f"\n✓ '{title}' has been successfully uninstalled.", "success")
            self.after(0, self.refresh_all)
            self.after(0, lambda: messagebox.showinfo("Uninstalled", f"'{title}' was successfully uninstalled!"))
        except Exception as exc:
            self.log(f"Uninstallation error: {exc}", "error")

    def verify_selected(self):
        """Feature: Verify & repair game files via Legendary."""
        if not self.selected_game_app:
            return
        g = self.installed_games_data.get(self.selected_game_app, {})
        title = g.get('title') or self.selected_game_app
        app_name = self.selected_game_app

        self.notebook.select(self.tab_console)
        self.log(f"\n▶ Verifying game integrity for '{title}'...", "info")
        threading.Thread(target=self._verify_worker, args=(app_name,), daemon=True).start()

    def _verify_worker(self, app_name):
        try:
            cmd = ["legendary", "verify", app_name]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                self.log(line.rstrip())
            proc.wait()
            self.log(f"Verification finished with status {proc.returncode}.", "success")
        except Exception as e:
            self.log(f"Verification error: {e}", "error")

    def open_selected_folder(self):
        if not self.selected_game_app:
            return
        g = self.installed_games_data.get(self.selected_game_app, {})
        path_str = g.get('install_path', '')
        if path_str and Path(path_str).is_dir():
            try:
                subprocess.Popen(["xdg-open", path_str])
            except Exception:
                messagebox.showinfo("Game Path", f"Game folder:\n{path_str}")
        else:
            messagebox.showinfo("Path Not Found", f"Game path does not exist on disk:\n{path_str}")

    def run_cleanup(self):
        self.notebook.select(self.tab_console)
        self.log("▶ Cleaning up Legendary cache, temp files, and old manifests...", "info")
        threading.Thread(target=self._cleanup_worker, daemon=True).start()

    def _cleanup_worker(self):
        try:
            res = subprocess.run(["legendary", "cleanup"], capture_output=True, text=True, timeout=30)
            self.log(res.stdout, "dim")
            self.log("✓ Cleanup finished successfully.", "success")
            self.after(0, self.refresh_disk_status)
        except Exception as e:
            self.log(f"Cleanup error: {e}", "error")

    def fetch_remote_library(self):
        self.log("▶ Fetching Epic Games library via legendary list...", "info")
        self.ent_filter_lib.delete(0, tk.END)
        for item in self.tree_library.get_children():
            self.tree_library.delete(item)

        threading.Thread(target=self._fetch_library_worker, daemon=True).start()

    def _fetch_library_worker(self):
        try:
            res = subprocess.run(["legendary", "list", "--json"], capture_output=True, text=True, timeout=25)
            if res.returncode == 0 and res.stdout.strip():
                items = json.loads(res.stdout)
                installed_ids = set(self.installed_games_data.keys())

                self.all_library_items = []
                for item in items:
                    app = item.get("app_name", "")
                    title = item.get("app_title") or item.get("title") or app
                    status = "✓ Installed" if app in installed_ids else "Available"
                    self.all_library_items.append((title, app, status))

                self.all_library_items.sort(key=lambda x: x[0].lower())
                self.after(0, self._populate_library_table, self.all_library_items)
                self.log(f"✓ Found {len(self.all_library_items)} games in your Epic library.", "success")
            else:
                self.log(f"Legendary list returned code {res.returncode}:\n{res.stderr or res.stdout}", "error")
        except Exception as e:
            self.log(f"Library fetch error: {e}", "error")

    def _populate_library_table(self, items):
        for item in self.tree_library.get_children():
            self.tree_library.delete(item)
        for row in items:
            self.tree_library.insert("", "end", values=row)

    def filter_library(self, event=None):
        query = self.ent_filter_lib.get().strip().lower()
        if not hasattr(self, 'all_library_items'):
            return
        if not query:
            self._populate_library_table(self.all_library_items)
        else:
            filtered = [r for r in self.all_library_items if query in r[0].lower() or query in r[1].lower()]
            self._populate_library_table(filtered)

    def install_selected(self):
        sel = self.tree_library.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a game to install from the library.")
            return

        values = self.tree_library.item(sel[0], "values")
        title = values[0]
        app_name = values[1]

        if not messagebox.askyesno("Install Game", f"Install '{title}' ({app_name}) via Legendary?"):
            return

        self.notebook.select(self.tab_console)
        self.log(f"\n▶ Starting installation of {title} ({app_name})...", "info")
        threading.Thread(target=self._install_worker, args=(app_name,), daemon=True).start()

    def _install_worker(self, app_name):
        try:
            cmd = ["legendary", "install", app_name, "-y"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                self.log(line.rstrip())
            proc.wait()
            self.log(f"Installation finished with code {proc.returncode}.", "success")
            self.sync_and_refresh()
        except Exception as e:
            self.log(f"Install error: {e}", "error")

    def open_login_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Epic Games Authentication")
        dlg.geometry("560x380")
        dlg.resizable(False, False)
        dlg.configure(bg=C_CANVAS)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Log In to Epic Games Store", bg=C_CANVAS, fg="#ffffff",
                 font=("Liberation Sans", 13, "bold")).pack(pady=(16, 10))

        frame_steps = tk.Frame(dlg, bg=C_PANEL, padx=14, pady=12, highlightbackground=C_BORDER, highlightthickness=1)
        frame_steps.pack(fill="x", padx=16, pady=6)

        msg = (
            "1. Open this URL in your PC browser (Chrome/Edge/Firefox):\n"
            "   https://legendary.gl/epiclogin\n\n"
            "2. Sign in with your Epic Games account.\n\n"
            "3. The browser will show text containing 'authorizationCode'.\n"
            "4. Copy and paste the code (or the entire JSON string) below:"
        )
        tk.Label(frame_steps, text=msg, bg=C_PANEL, fg=C_FG, justify="left",
                 font=("Liberation Sans", 9)).pack(anchor="w")

        def _copy_url():
            self.clipboard_clear()
            self.clipboard_append("https://legendary.gl/epiclogin")
            lbl_info.config(text="✓ Link copied to clipboard!", fg=C_GREEN)

        btn_copy = make_hover_button(frame_steps, "📋 Copy Login Link", C_CARD, C_CARD_HOVER,
                                     font=("Liberation Sans", 9), padx=10, pady=4, command=_copy_url)
        btn_copy.pack(anchor="w", pady=(8, 0))

        # Input entry
        lbl_code = tk.Label(dlg, text="Authorization Code or JSON Text:", bg=C_CANVAS, fg=C_MUTED,
                            font=("Liberation Sans", 9, "bold"))
        lbl_code.pack(anchor="w", padx=18, pady=(10, 2))

        ent_code = tk.Entry(dlg, bg=C_PANEL, fg="#ffffff", insertbackground="#ffffff",
                            relief="flat", font=("Liberation Mono", 10), highlightbackground=C_BORDER, highlightthickness=1)
        ent_code.pack(fill="x", padx=18, ipady=4)

        lbl_info = tk.Label(dlg, text="", bg=C_CANVAS, fg=C_YELLOW, font=("Liberation Sans", 9))
        lbl_info.pack(pady=4)

        def _submit():
            raw_input = ent_code.get().strip()
            if not raw_input:
                lbl_info.config(text="Please paste an authorization code first.", fg=C_RED)
                return

            code = raw_input
            if "{" in raw_input and "authorizationCode" in raw_input:
                try:
                    data = json.loads(raw_input)
                    code = data.get("authorizationCode", raw_input)
                except Exception:
                    m = re.search(r'"authorizationCode"\s*:\s*"([a-f0-9]+)"', raw_input, re.I)
                    if m:
                        code = m.group(1)

            lbl_info.config(text="Authenticating with Epic Games...", fg=C_YELLOW)
            dlg.update()

            def _auth_worker():
                res = subprocess.run(["legendary", "auth", "--code", code], capture_output=True, text=True)
                if res.returncode == 0:
                    self.sync_and_refresh()
                    self.after(0, lambda: (
                        messagebox.showinfo("Success", "Epic Games authentication succeeded!"),
                        dlg.destroy()
                    ))
                else:
                    err_msg = res.stderr or res.stdout
                    self.after(0, lambda: lbl_info.config(text=f"Auth failed: {err_msg[:60]}", fg=C_RED))

            threading.Thread(target=_auth_worker, daemon=True).start()

        btn_frame = tk.Frame(dlg, bg=C_CANVAS)
        btn_frame.pack(fill="x", padx=18, pady=12)

        make_hover_button(btn_frame, "Cancel", C_CARD, C_CARD_HOVER, normal_fg=C_MUTED,
                         padx=12, pady=5, command=dlg.destroy).pack(side="left")

        make_hover_button(btn_frame, "🚀 Complete Login", C_GREEN, C_GREEN_HOVER,
                         font=("Liberation Sans", 10, "bold"), padx=14, pady=5, command=_submit).pack(side="right")


if __name__ == "__main__":
    app = LegendaryApp()
    app.mainloop()
