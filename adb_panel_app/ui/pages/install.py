"""Página de instalar: paquetes encontrados en tus carpetas y su instalación."""
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...adb.installer import install_package_file
from ...paths import CACHE_DIR, ENTRY_SCRIPT, FILES_META, PACKAGE_EXTS
from ...theme import BG, BORDER, CARD, MUTED
from ...utils import human_size, notify


class InstallPage:
    def _page_install(self):
        f = self.page("Instalar", "Paquetes .apk, .xapk, .apks y .apkm encontrados en tus carpetas.")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        self.folders_lbl = tk.Label(bar, text="", bg=BG, fg=MUTED, anchor="w", justify="left", wraplength=480)
        self.folders_lbl.pack(side="left")
        ttk.Button(bar, text="↻ Buscar de nuevo", command=self.scan_files).pack(side="right")
        ttk.Button(bar, text="📂 Abrir carpeta APK", command=self.open_apk_folder).pack(side="right", padx=6)

        box = tk.Frame(f, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True)
        self.ftree = ttk.Treeview(box, columns=("ver", "file", "size", "estado"), show="tree headings",
                                  selectmode="browse")
        for col, text, w in (("#0", "App", 240), ("ver", "Versión", 90), ("file", "Archivo", 220),
                             ("size", "Tamaño", 80), ("estado", "En el teléfono", 110)):
            self.ftree.heading(col, text=text)
            self.ftree.column(col, width=w, minwidth=60, stretch=col in ("#0", "file"),
                              anchor="w" if col in ("#0", "file") else "center")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.ftree.yview)
        self.ftree.configure(yscrollcommand=sb.set)
        self.ftree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.ftree.bind("<Double-1>", lambda e: self.do_install())

        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="Instalar en el teléfono 🔒", style="Accent.TButton",
                   command=self.do_install).pack(side="left")
        ttk.Button(actions, text="Elegir otro archivo…", command=self.pick_file).pack(side="left", padx=6)
        tk.Label(actions, text="Instalar apps nuevas también pide pensarlo: es una puerta de entrada.",
                 bg=BG, fg=MUTED).pack(side="right")
        return f

    def folders(self):
        return [os.path.expanduser(p) for p in self.cfg["apk_folders"]]

    def scan_files(self):
        folders = [p for p in self.folders() if os.path.isdir(p)]
        home = os.path.expanduser("~")
        self.folders_lbl.config(text="Buscando en: " + ", ".join(p.replace(home, "~", 1) for p in folders))
        found = {}
        for folder in folders:
            for root, dirs, files in os.walk(folder):
                if root.count(os.sep) - folder.count(os.sep) >= 2:
                    dirs[:] = []
                for n in files:
                    # Las partes sueltas de una app dividida no se instalan solas.
                    if n.lower().endswith(PACKAGE_EXTS) and not re.match(r"(split_|config\.)", n):
                        p = os.path.join(root, n)
                        try:
                            st = os.stat(p)
                        except OSError:
                            continue
                        found[p] = (st.st_size, st.st_mtime)
        self.files = found
        for path, (size, mtime) in found.items():
            key = f"{size}:{mtime}"
            m = self.files_meta.get(path)
            if not m or m.get("key") != key:
                self.files_meta[path] = {"key": key, "loading": True}
                self.file_pool.submit(self._file_meta_bg, path, key)
        self.render_files()

    def _file_meta_bg(self, path, key):
        try:
            r = subprocess.run([sys.executable, ENTRY_SCRIPT, "--file-meta", path],
                               capture_output=True, text=True, timeout=300)
            m = json.loads(r.stdout.strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            m = {}
        m["key"] = key

        def done():
            self.files_meta[path] = m
            self.images.pop("f:" + path, None)
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(FILES_META, "w") as f:
                json.dump(self.files_meta, f, ensure_ascii=False)
            self.render_files()

        self.after(0, done)

    def render_files(self):
        sel = self.ftree.selection()
        self.ftree.delete(*self.ftree.get_children())
        if not self.files:
            self.ftree.insert("", "end", iid="__empty__",
                              text="  No hay paquetes. Descarga un .apk/.xapk o ponlo en ~/Documents/APK",
                              values=("", "", "", ""))
            return
        installed = set(self.packages)
        for path in sorted(self.files, key=lambda p: -self.files[p][1]):
            m = self.files_meta.get(path, {})
            size = self.files[path][0]
            if m.get("loading"):
                name, state = os.path.basename(path), "leyendo…"
            else:
                name = m.get("name") or os.path.basename(path)
                state = ("instalada" if m.get("pkg") in installed else "nueva") if self.packages else "—"
            img = self.icon_for("f:" + path, m.get("icon")) if m.get("icon") else self.placeholder
            self.ftree.insert("", "end", iid=path, text=" " + name, image=img,
                              values=(m.get("version") or "", os.path.basename(path), human_size(size), state))
        if sel and self.ftree.exists(sel[0]):
            self.ftree.selection_set(sel[0])

    def open_apk_folder(self):
        folder = os.path.expanduser("~/Documents/APK")
        os.makedirs(folder, exist_ok=True)
        subprocess.Popen(["xdg-open", folder])

    def pick_file(self):
        path = filedialog.askopenfilename(parent=self, title="Elegir paquete",
                                          filetypes=[("Paquetes Android", "*.apk *.xapk *.apks *.apkm")])
        if path:
            self.install(path)

    def do_install(self):
        sel = self.ftree.selection()
        if sel and sel[0] in self.files:
            self.install(sel[0])

    def install(self, path):
        if not self.need_device():
            return
        m = self.files_meta.get(path, {})
        name = m.get("name") or os.path.basename(path)
        if not self.gate(f"Instalar {name} en el teléfono"):
            return

        def done(res):
            ok, out = res
            if ok and "Success" in out:
                self.set_status(f"✅ {name} instalada.")
                notify("App instalada", name)
                self.load_packages()
            else:
                hints = {
                    "MISSING_SPLIT": "La app está instalada en varias partes y este APK es solo una. "
                                     "Descarga la versión .xapk / .apks / .apkm.",
                    "VERSION_DOWNGRADE": "En el teléfono ya hay una versión más nueva de esta app.",
                    "UPDATE_INCOMPATIBLE": "La app instalada está firmada distinto (otra fuente). "
                                           "Desinstálala primero.",
                    "INSUFFICIENT_STORAGE": "El teléfono no tiene espacio suficiente.",
                    "NO_MATCHING_ABIS": "Este paquete no es para el procesador de tu teléfono.",
                    "USER_RESTRICTED": "El teléfono rechazó la instalación: acepta el aviso en su pantalla "
                                       "(en Xiaomi activa «Instalar vía USB» en Opciones de desarrollador).",
                }
                hint = next((h for k, h in hints.items() if k in out), "")
                messagebox.showerror("No se pudo instalar", (hint + "\n\n" if hint else "") + out[-800:],
                                     parent=self)
                self.set_status("La instalación falló.")

        self.run_bg(lambda: install_package_file(path), done, f"Instalando {name}… (puede tardar)")
