"""Ventana principal: barra lateral, páginas y utilidades comunes (tareas en segundo plano, desbloqueo)."""
import datetime as dt
import json
import os
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox, ttk

from ..config import load_config, save_config
from ..controller.device import DeviceController
from ..controller.relocks import RelockController
from ..meta.store import MetaStore
from ..paths import FILES_META
from ..sync import BlocksSync
from ..theme import AMBER, BG, BORDER, CARD, GREEN, MUTED, RED, SIDEBAR, SIDEBAR_HI, TEXT
from ..utils import short_app_name
from .gate import Gate
from .pages.apps import AppsPage
from .pages.dns import DnsPage
from .pages.home import HomePage
from .pages.install import InstallPage
from .pages.settings import SettingsPage
from .styles import apply_styles, placeholder_icon


class Panel(HomePage, AppsPage, InstallPage, DnsPage, SettingsPage, DeviceController, RelockController, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Panel ADB")
        self.geometry("1040x700")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.cfg = load_config()
        self.device = None
        self.usb_serial = None
        self.wifi_connected = False
        self.packages = {}
        self.busy = False
        self.images = {}
        self.last_wifi_try = 0
        self.refresh_pending = False
        self.current_page = None
        self.state_cache = {"dns": None, "applock": None, "model": ""}
        self.files = {}
        self.meta = MetaStore(lambda pkg: self.after(0, self.on_meta, pkg))
        try:
            with open(FILES_META) as f:
                self.files_meta = json.load(f)
        except (OSError, ValueError):
            self.files_meta = {}
        self.file_pool = ThreadPoolExecutor(2)

        apply_styles(self)
        self.placeholder = placeholder_icon()
        self._build()
        self.sync = BlocksSync(self)
        self.show_page("inicio")
        self.after(200, self.poll_device)
        self.after(1000, self.sync_tick)

    def sync_tick(self):
        self.sync.tick()
        self.after(1000, self.sync_tick)

    def _build(self):
        side = tk.Frame(self, bg=SIDEBAR, width=200)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="📱 Panel ADB", bg=SIDEBAR, fg="white", font=("Sans", 14, "bold"),
                 anchor="w", padx=20, pady=22).pack(fill="x")
        self.nav = {}
        for key, label in (("inicio", "🏠   Inicio"), ("apps", "📲   Apps"), ("instalar", "📦   Instalar"),
                           ("dns", "🌐   DNS"), ("ajustes", "⚙   Ajustes")):
            b = tk.Label(side, text=label, bg=SIDEBAR, fg="#c9cfdb", font=("Sans", 11), anchor="w",
                         padx=22, pady=11, cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=key: self.show_page(k))
            self.nav[key] = b
        self.side_status = tk.Label(side, text="● buscando…", bg=SIDEBAR, fg="#c9cfdb", anchor="w",
                                    padx=20, pady=16, justify="left", wraplength=170)
        self.side_status.pack(side="bottom", fill="x")

        main = ttk.Frame(self)
        main.pack(side="left", fill="both", expand=True)
        self.status = tk.Label(main, text="", anchor="w", bg=BG, fg=MUTED, padx=24, pady=6)
        self.status.pack(side="bottom", fill="x")
        self.content = ttk.Frame(main)
        self.content.pack(fill="both", expand=True)
        self.pages = {
            "inicio": self._page_home(),
            "apps": self._page_apps(),
            "instalar": self._page_install(),
            "dns": self._page_dns(),
            "ajustes": self._page_settings(),
        }

    def show_page(self, key):
        for k, page in self.pages.items():
            page.pack_forget()
            self.nav[k].config(bg=SIDEBAR_HI if k == key else SIDEBAR, fg="white" if k == key else "#c9cfdb")
        self.pages[key].pack(fill="both", expand=True, padx=24, pady=(20, 0))
        self.current_page = key
        if key == "instalar":
            self.scan_files()
        elif key == "ajustes":
            self.render_log()
        elif key == "inicio":
            self.render_home()

    def page(self, title, subtitle):
        f = ttk.Frame(self.content)
        tk.Label(f, text=title, bg=BG, fg=TEXT, font=("Sans", 18, "bold")).pack(anchor="w")
        tk.Label(f, text=subtitle, bg=BG, fg=MUTED).pack(anchor="w", pady=(2, 14))
        return f

    def card(self, parent, title=None, **pack):
        c = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER, padx=18, pady=14)
        c.pack(**({"fill": "x", "pady": (0, 14)} | pack))
        if title:
            tk.Label(c, text=title, bg=CARD, fg=TEXT, font=("Sans", 11, "bold")).pack(anchor="w", pady=(0, 8))
        return c

    def pill(self, parent):
        return tk.Label(parent, text="—", bg="#eef0f4", fg=MUTED, font=("Sans", 9, "bold"), padx=10, pady=3)

    def set_pill(self, pill, text, kind):
        colors = {"on": ("#e3f4e8", GREEN), "off": ("#fde8e8", RED), "warn": ("#fdf3e1", AMBER),
                  "neutral": ("#eef0f4", MUTED)}
        bg, fg = colors[kind]
        pill.config(text=text, bg=bg, fg=fg)

    def set_status(self, text):
        self.status.config(text=text)

    def run_bg(self, work, done=None, label="Trabajando…"):
        """Corre `work` en un hilo y luego `done(resultado)` en el hilo de la UI."""
        if self.busy:
            self.set_status("Espera, hay otra operación en curso…")
            return
        self.busy = True
        self.set_status(label)
        self.config(cursor="watch")

        def target():
            try:
                res = work()
            except Exception as e:  # noqa: BLE001
                res = e
            self.after(0, finish, res)

        def finish(res):
            self.busy = False
            self.config(cursor="")
            if isinstance(res, Exception):
                self.set_status(f"Error: {res}")
            elif done:
                done(res)

        threading.Thread(target=target, daemon=True).start()

    def gate(self, action, temporary=False, short=False):
        """Pide motivo + espera + contraseña. Regresa None si se cancela. `short`: a lo más 15 min."""
        g = Gate(self, action, temporary, short)
        self.wait_window(g)
        if g.result:
            self.cfg["unlock_log"].append({"ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "action": action,
                                           "reason": g.result["reason"], "minutes": g.result["minutes"]})
            self.cfg["unlock_log"] = self.cfg["unlock_log"][-300:]
            save_config(self.cfg)
        return g.result

    def need_device(self):
        if not self.device:
            messagebox.showwarning("Sin teléfono", "Conecta el teléfono (cable o WiFi) con depuración activada.",
                                   parent=self)
            return False
        return True

    def icon_for(self, key, path=None):
        if key in self.images:
            return self.images[key]
        path = path or self.meta.icon_path(key)
        if not path or not os.path.exists(path):
            return self.placeholder
        try:
            img = tk.PhotoImage(file=path)
        except tk.TclError:
            return self.placeholder
        self.images[key] = img
        return img

    def display_name(self, pkg):
        name = self.meta.name(pkg)
        return short_app_name(name) if name else pkg.rsplit(".", 1)[-1]

    def names(self, pkgs):
        shown = ", ".join(self.display_name(p) for p in pkgs[:4])
        return shown + (f" y {len(pkgs) - 4} más" if len(pkgs) > 4 else "")
