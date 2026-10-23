"""Modern Graphical Interface for Legendary Epic Games Manager."""
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
    return "Unknown"

class LegendaryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Epic Games · Legendary Manager")
        self.geometry("980x660")
        self.minsize(800, 500)

        # Active process tracker
        self.active_proc = None
        self.proc_thread = None

        # Apply dark theme styling
        self.setup_styles()

        # Build UI layout
        self.create_header()
        self.create_tabs()
        self.create_bottom_bar()

        # Initial data load
        self.refresh_all()

    def setup_styles(self):
        self.configure(bg="#141923")
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # Colors
        self.c_bg = "#141923"
        self.c_panel = "#1b2230"
        self.c_card = "#222c3e"
        self.c_fg = "#f0f4fc"
        self.c_muted = "#8fa0bd"
        self.c_accent = "#3498db"
        self.c_green = "#2ecc71"
        self.c_red = "#e74c3c"
        self.c_yellow = "#f39c12"

        self.style.configure(".", background=self.c_bg, foreground=self.c_fg, font=("DejaVu Sans", 10))
        self.style.configure("TNotebook", background=self.c_bg, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=self.c_panel, foreground=self.c_muted,
                             padding=[18, 9], font=("DejaVu Sans", 10, "bold"))
        self.style.map("TNotebook.Tab",
                       background=[("selected", self.c_card), ("active", "#2a364d")],
                       foreground=[("selected", "#ffffff"), ("active", self.c_fg)])

        self.style.configure("Treeview", background="#1a202c", foreground=self.c_fg,
                             fieldbackground="#1a202c", rowheight=32, font=("DejaVu Sans", 10),
                             borderwidth=0)
        self.style.configure("Treeview.Heading", background=self.c_panel, foreground="#ffffff",
                             font=("DejaVu Sans", 10, "bold"), padding=[6, 6])
        self.style.map("Treeview", background=[("selected", "#2b4a70")], foreground=[("selected", "#ffffff")])

        self.style.configure("TFrame", background=self.c_bg)
        self.style.configure("Card.TFrame", background=self.c_panel, relief="flat")

    def create_header(self):
        header = tk.Frame(self, bg=self.c_panel, height=65)
        header.pack(fill="x", side="top", padx=12, pady=(10, 6))

        # Brand badge
        logo_frame = tk.Frame(header, bg=self.c_panel)
        logo_frame.pack(side="left", padx=14, pady=10)

        lbl_badge = tk.Label(logo_frame, text=" LEGENDARY ", bg=self.c_accent, fg="#ffffff",
                             font=("DejaVu Sans", 10, "bold"), padx=6, pady=2)
        lbl_badge.pack(side="left", padx=(0, 10))

        lbl_title = tk.Label(logo_frame, text="Epic Games Launcher", bg=self.c_panel, fg=self.c_fg,
                             font=("DejaVu Sans", 14, "bold"))
        lbl_title.pack(side="left")

        # Account & Runner status
        info_frame = tk.Frame(header, bg=self.c_panel)
        info_frame.pack(side="right", padx=14, pady=10)

        self.lbl_account = tk.Label(info_frame, text="Checking login status...", bg=self.c_panel,
                                    fg=self.c_yellow, font=("DejaVu Sans", 10, "bold"))
        self.lbl_account.pack(anchor="e")

        self.lbl_runner = tk.Label(info_frame, text="Detecting Wine runner...", bg=self.c_panel,
                                   fg=self.c_muted, font=("DejaVu Sans", 9))
        self.lbl_runner.pack(anchor="e")

    def create_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        # Tab 1: Installed Games
        self.tab_installed = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_installed, text=" 🎮 Installed Games ")
        self.build_installed_tab()

        # Tab 2: Epic Library
        self.tab_library = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_library, text=" 📥 Full Epic Library ")
        self.build_library_tab()

        # Tab 3: Console Logs
        self.tab_console = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_console, text=" 📜 Launch Console & Logs ")
        self.build_console_tab()

    def build_installed_tab(self):
        container = tk.Frame(self.tab_installed, bg=self.c_bg)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Toolbar above games table
        toolbar = tk.Frame(container, bg=self.c_bg)
        toolbar.pack(fill="x", side="top", pady=(0, 8))

        btn_launch = tk.Button(toolbar, text=" ▶  LAUNCH SELECTED GAME ", bg=self.c_green, fg="#ffffff",
                               font=("DejaVu Sans", 11, "bold"), relief="flat", padx=16, pady=6,
                               activebackground="#27ae60", activeforeground="#ffffff", cursor="hand2",
                               command=self.launch_selected)
        btn_launch.pack(side="left", padx=(0, 10))

        btn_sync = tk.Button(toolbar, text=" 🔄 Sync Heroic & Refresh ", bg=self.c_card, fg=self.c_fg,
                             font=("DejaVu Sans", 10), relief="flat", padx=12, pady=6,
                             activebackground="#2a364d", cursor="hand2", command=self.sync_and_refresh)
        btn_sync.pack(side="left", padx=5)

        btn_fix = tk.Button(toolbar, text=" 🛠️ Check GPU & Fix Prefixes ", bg=self.c_card, fg=self.c_fg,
                            font=("DejaVu Sans", 10), relief="flat", padx=12, pady=6,
                            activebackground="#2a364d", cursor="hand2", command=self.run_sanitizer)
        btn_fix.pack(side="left", padx=5)

        btn_login = tk.Button(toolbar, text=" 🔑 Login to Epic Games ", bg=self.c_card, fg="#ffffff",
                              font=("DejaVu Sans", 10), relief="flat", padx=12, pady=6,
                              activebackground="#2a364d", cursor="hand2", command=self.open_login_dialog)
        btn_login.pack(side="right")

        # Table of installed games
        columns = ("title", "app_name", "version", "size", "install_path")
        self.tree_installed = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        self.tree_installed.heading("title", text="Game Title")
        self.tree_installed.heading("app_name", text="App Name ID")
        self.tree_installed.heading("version", text="Version")
        self.tree_installed.heading("size", text="Size")
        self.tree_installed.heading("install_path", text="Installed Location")

        self.tree_installed.column("title", width=220, anchor="w")
        self.tree_installed.column("app_name", width=240, anchor="w")
        self.tree_installed.column("version", width=120, anchor="center")
        self.tree_installed.column("size", width=90, anchor="center")
        self.tree_installed.column("install_path", width=250, anchor="w")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_installed.yview)
        self.tree_installed.configure(yscrollcommand=scroll.set)

        self.tree_installed.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree_installed.bind("<Double-1>", lambda e: self.launch_selected())

    def build_library_tab(self):
        container = tk.Frame(self.tab_library, bg=self.c_bg)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        toolbar = tk.Frame(container, bg=self.c_bg)
        toolbar.pack(fill="x", side="top", pady=(0, 8))

        btn_load = tk.Button(toolbar, text=" 🔍 Fetch Library from Epic ", bg=self.c_accent, fg="#ffffff",
                             font=("DejaVu Sans", 10, "bold"), relief="flat", padx=14, pady=6,
                             cursor="hand2", command=self.fetch_remote_library)
        btn_load.pack(side="left", padx=(0, 10))

        btn_install = tk.Button(toolbar, text=" 📥 Install Selected Game ", bg=self.c_card, fg=self.c_fg,
                                font=("DejaVu Sans", 10), relief="flat", padx=12, pady=6,
                                cursor="hand2", command=self.install_selected)
        btn_install.pack(side="left")

        # Filter
        tk.Label(toolbar, text="Filter:", bg=self.c_bg, fg=self.c_muted, font=("DejaVu Sans", 10)).pack(side="left", padx=(20, 5))
        self.ent_filter = tk.Entry(toolbar, bg="#1a202c", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("DejaVu Sans", 10))
        self.ent_filter.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_filter.bind("<KeyRelease>", self.filter_library)

        columns = ("title", "app_name", "status")
        self.tree_library = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        self.tree_library.heading("title", text="Game Title")
        self.tree_library.heading("app_name", text="App Name ID")
        self.tree_library.heading("status", text="Local Status")

        self.tree_library.column("title", width=400, anchor="w")
        self.tree_library.column("app_name", width=300, anchor="w")
        self.tree_library.column("status", width=140, anchor="center")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_library.yview)
        self.tree_library.configure(yscrollcommand=scroll.set)

        self.tree_library.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def build_console_tab(self):
        container = tk.Frame(self.tab_console, bg=self.c_bg)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        toolbar = tk.Frame(container, bg=self.c_bg)
        toolbar.pack(fill="x", side="top", pady=(0, 6))

        btn_stop = tk.Button(toolbar, text=" ⏹  STOP RUNNING GAME ", bg=self.c_red, fg="#ffffff",
                             font=("DejaVu Sans", 10, "bold"), relief="flat", padx=14, pady=5,
                             cursor="hand2", command=self.stop_active_game)
        btn_stop.pack(side="left", padx=(0, 10))

        btn_clear = tk.Button(toolbar, text=" 🧹 Clear Log ", bg=self.c_card, fg=self.c_fg,
                              font=("DejaVu Sans", 9), relief="flat", padx=10, pady=5,
                              cursor="hand2", command=lambda: self.log_text.delete("1.0", tk.END))
        btn_clear.pack(side="left", padx=5)

        self.lbl_status = tk.Label(toolbar, text="Idle", bg=self.c_bg, fg=self.c_muted, font=("DejaVu Sans", 10))
        self.lbl_status.pack(side="right", padx=10)

        self.log_text = scrolledtext.ScrolledText(container, bg="#0d1117", fg="#c9d1d9",
                                                 insertbackground="#ffffff", font=("DejaVu Sans Mono", 9),
                                                 relief="flat", borderwidth=0)
        self.log_text.pack(fill="both", expand=True)

    def create_bottom_bar(self):
        bar = tk.Frame(self, bg=self.c_panel, height=32)
        bar.pack(fill="x", side="bottom", padx=12, pady=(0, 8))

        lbl_tip = tk.Label(bar, text="💡 Game launches require a verified NVIDIA 3D renderer. Run gpu_runtime.py diagnose for details.",
                           bg=self.c_panel, fg=self.c_muted, font=("DejaVu Sans", 9))
        lbl_tip.pack(side="left", padx=12, pady=6)

    def log(self, text):
        def _append():
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)
        self.after(0, _append)

    def refresh_all(self):
        self.refresh_account_status()
        self.refresh_runner_status()
        self.refresh_installed_games()

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
                self.lbl_account.config(text=f"🟢 Logged In: {display_name}{short_id}", fg=self.c_green)
                return
            except Exception:
                pass
        self.lbl_account.config(text="🔴 Not Logged In", fg=self.c_red)

    def refresh_runner_status(self):
        runner = find_best_runner()
        name = "Wine-GE-Proton8-26" if "Wine-GE" in runner else Path(runner).name
        self.lbl_runner.config(text=f"🍷 Runner: {name} (WineD3D OpenGL active)")

    def refresh_installed_games(self):
        for item in self.tree_installed.get_children():
            self.tree_installed.delete(item)

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
                self.log(f"Notice reading installed.json: {e}")

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

        for app_name, g in sorted(games.items(), key=lambda x: str(x[1].get('title', '')).lower()):
            title = g.get('title') or app_name
            version = g.get('version', 'Unknown')
            size_str = format_size(g.get('install_size', 0))
            path_str = g.get('install_path', 'N/A')
            self.tree_installed.insert("", "end", values=(title, app_name, version, size_str, path_str))

        # Select first item if available
        children = self.tree_installed.get_children()
        if children:
            self.tree_installed.selection_set(children[0])
            self.tree_installed.focus(children[0])

    def sync_and_refresh(self):
        self.log("▶ Syncing Heroic and Legendary configurations...")
        try:
            fix_script = BENCH / 'fix_heroic_config.py'
            if fix_script.is_file():
                res = subprocess.run([sys.executable, str(fix_script)], capture_output=True, text=True, timeout=10)
                self.log(res.stdout)
                if res.stderr:
                    self.log(res.stderr)
            self.refresh_all()
            self.log("✓ Sync completed successfully.")
        except Exception as exc:
            self.log(f"Sync error: {exc}")

    def run_sanitizer(self):
        self.notebook.select(self.tab_console)
        self.log("▶ Checking live GPU renderer and updating Wine settings...")
        threading.Thread(target=self._run_sanitizer_worker, daemon=True).start()

    def _run_sanitizer_worker(self):
        try:
            fix_script = BENCH / 'fix_heroic_config.py'
            if fix_script.is_file():
                res = subprocess.run([sys.executable, str(fix_script)], capture_output=True, text=True, timeout=15)
                self.log(res.stdout)
            subprocess.run(["chown", "-R", "gamer:gamer", "/home/gamer"], check=False)
            subprocess.run(["chmod", "-R", "u+rwX", "/home/gamer"], check=False)
            self.log("✓ Wine settings updated for the detected graphics backend.")
            self.after(0, self.refresh_all)
        except Exception as e:
            self.log(f"Error during sanitization: {e}")

    def launch_selected(self):
        selected = self.tree_installed.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a game from the list to launch.")
            return

        values = self.tree_installed.item(selected[0], "values")
        title = values[0]
        app_name = values[1]

        self.notebook.select(self.tab_console)
        self.log(f"\n==================================================================")
        self.log(f"🚀 Launching game: {title} ({app_name})")
        self.log(f"==================================================================")

        runner = find_best_runner()
        self.log(f"Runner: {runner}")
        self.log("Checking for NVIDIA OpenGL before launch...")

        threading.Thread(target=self._launch_worker, args=(app_name, title, runner), daemon=True).start()

    def _launch_worker(self, app_name, title, runner):
        env = dict(os.environ)
        env["DISPLAY"] = os.environ.get("DISPLAY", ":0")
        env["HOME"] = str(HOME)
        env["WINEPREFIX"] = str(HOME / ".wine")

        # Automatically verify and heal Wine prefix before launch if kernel32.dll is missing
        kernel32 = HOME / ".wine/drive_c/windows/system32/kernel32.dll"
        if not kernel32.is_file():
            self.log("▶ Detected incomplete or uninitialized Wine prefix. Auto-initializing with Wine-GE...")
            wineboot_bin = Path(runner).with_name("wineboot")
            if wineboot_bin.is_file():
                try:
                    init_env = dict(env)
                    init_env["WINEDLLOVERRIDES"] = "mscoree,mshtml=d"
                    subprocess.run([str(wineboot_bin), "--init"], env=init_env, check=False, timeout=30)
                    self.log("✓ Wine prefix auto-initialized successfully.")
                except Exception as wb_err:
                    self.log(f"Notice auto-initializing prefix: {wb_err}")

        cmd = ["python3", "/tmp/kaggle-game-dev-bench/gpu_runtime.py",
               "launch", app_name, runner]
        self.lbl_status.config(text=f"▶ Running: {title}", fg=self.c_green)

        try:
            self.active_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env
            )
            for line in self.active_proc.stdout:
                self.log(line.rstrip())
            self.active_proc.wait()
            self.log(f"\nGame process exited with status: {self.active_proc.returncode}")
        except Exception as exc:
            self.log(f"Launch exception: {exc}")
        finally:
            self.active_proc = None
            self.lbl_status.config(text="Idle", fg=self.c_muted)

    def stop_active_game(self):
        if self.active_proc and self.active_proc.poll() is None:
            self.log("Terminating active game process...")
            self.active_proc.terminate()
            time.sleep(1)
            if self.active_proc.poll() is None:
                self.active_proc.kill()
            self.log("Process stopped.")
        else:
            self.log("No active game process running.")

    def fetch_remote_library(self):
        self.log("▶ Fetching Epic Games library via legendary list...")
        self.ent_filter.delete(0, tk.END)
        for item in self.tree_library.get_children():
            self.tree_library.delete(item)

        threading.Thread(target=self._fetch_library_worker, daemon=True).start()

    def _fetch_library_worker(self):
        try:
            res = subprocess.run(["legendary", "list", "--json"], capture_output=True, text=True, timeout=25)
            if res.returncode == 0 and res.stdout.strip():
                items = json.loads(res.stdout)
                installed_ids = {self.tree_installed.item(i, "values")[1] for i in self.tree_installed.get_children()}

                self.all_library_items = []
                for item in items:
                    app = item.get("app_name", "")
                    title = item.get("app_title") or item.get("title") or app
                    status = "✓ Installed" if app in installed_ids else "Available"
                    self.all_library_items.append((title, app, status))

                self.all_library_items.sort(key=lambda x: x[0].lower())
                self.after(0, self._populate_library_table, self.all_library_items)
                self.log(f"✓ Found {len(self.all_library_items)} games in your Epic library.")
            else:
                self.log(f"Legendary list returned code {res.returncode}:\n{res.stderr or res.stdout}")
        except Exception as e:
            self.log(f"Library fetch error: {e}")

    def _populate_library_table(self, items):
        for item in self.tree_library.get_children():
            self.tree_library.delete(item)
        for row in items:
            self.tree_library.insert("", "end", values=row)

    def filter_library(self, event=None):
        query = self.ent_filter.get().strip().lower()
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
        self.log(f"\n▶ Starting installation of {title} ({app_name})...")
        threading.Thread(target=self._install_worker, args=(app_name,), daemon=True).start()

    def _install_worker(self, app_name):
        try:
            cmd = ["legendary", "install", app_name, "-y"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                self.log(line.rstrip())
            proc.wait()
            self.log(f"Installation finished with code {proc.returncode}.")
            self.sync_and_refresh()
        except Exception as e:
            self.log(f"Install error: {e}")

    def open_login_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Epic Games Authentication")
        dlg.geometry("560x380")
        dlg.resizable(False, False)
        dlg.configure(bg=self.c_bg)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Log In to Epic Games", bg=self.c_bg, fg="#ffffff",
                 font=("DejaVu Sans", 13, "bold")).pack(pady=(16, 10))

        frame_steps = tk.Frame(dlg, bg=self.c_panel, padx=14, pady=12)
        frame_steps.pack(fill="x", padx=16, pady=6)

        msg = (
            "1. Open this URL in your PC browser (Chrome/Edge/Firefox):\n"
            "   https://legendary.gl/epiclogin\n\n"
            "2. Sign in with your Epic account.\n\n"
            "3. The browser will show text containing 'authorizationCode'.\n"
            "4. Copy and paste the code (or the entire JSON string) below:"
        )
        tk.Label(frame_steps, text=msg, bg=self.c_panel, fg=self.c_fg, justify="left",
                 font=("DejaVu Sans", 9)).pack(anchor="w")

        # Copy URL button
        def _copy_url():
            self.clipboard_clear()
            self.clipboard_append("https://legendary.gl/epiclogin")
            lbl_info.config(text="✓ Link copied to clipboard!", fg=self.c_green)

        btn_copy = tk.Button(frame_steps, text=" 📋 Copy Login Link ", bg=self.c_card, fg=self.c_fg,
                             font=("DejaVu Sans", 9), relief="flat", cursor="hand2", command=_copy_url)
        btn_copy.pack(anchor="w", pady=(6, 0))

        # Input entry
        lbl_code = tk.Label(dlg, text="Authorization Code or JSON Text:", bg=self.c_bg, fg=self.c_muted,
                            font=("DejaVu Sans", 9, "bold"))
        lbl_code.pack(anchor="w", padx=18, pady=(10, 2))

        ent_code = tk.Entry(dlg, bg="#1a202c", fg="#ffffff", insertbackground="#ffffff",
                            relief="flat", font=("DejaVu Sans Mono", 10))
        ent_code.pack(fill="x", padx=18, ipady=4)

        lbl_info = tk.Label(dlg, text="", bg=self.c_bg, fg=self.c_yellow, font=("DejaVu Sans", 9))
        lbl_info.pack(pady=4)

        def _submit():
            raw_input = ent_code.get().strip()
            if not raw_input:
                lbl_info.config(text="Please paste an authorization code first.", fg=self.c_red)
                return

            # Extract code if full JSON was pasted
            code = raw_input
            if "{" in raw_input and "authorizationCode" in raw_input:
                try:
                    data = json.loads(raw_input)
                    code = data.get("authorizationCode", raw_input)
                except Exception:
                    m = re.search(r'"authorizationCode"\s*:\s*"([a-f0-9]+)"', raw_input, re.I)
                    if m:
                        code = m.group(1)

            lbl_info.config(text="Authenticating with Epic Games...", fg=self.c_yellow)
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
                    self.after(0, lambda: lbl_info.config(text=f"Auth failed: {err_msg[:60]}", fg=self.c_red))

            threading.Thread(target=_auth_worker, daemon=True).start()

        btn_frame = tk.Frame(dlg, bg=self.c_bg)
        btn_frame.pack(fill="x", padx=18, pady=10)

        tk.Button(btn_frame, text=" Cancel ", bg=self.c_card, fg=self.c_muted, relief="flat",
                  cursor="hand2", command=dlg.destroy).pack(side="left")

        tk.Button(btn_frame, text=" 🚀 Log In to Epic Games ", bg=self.c_green, fg="#ffffff",
                  font=("DejaVu Sans", 10, "bold"), relief="flat", padx=14, pady=5,
                  cursor="hand2", command=_submit).pack(side="right")

if __name__ == "__main__":
    app = LegendaryApp()
    app.mainloop()
