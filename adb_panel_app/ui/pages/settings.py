"""Página de ajustes: automatismos, seguridad, carpetas de APK e historial."""
import os
import secrets
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from ...config import hash_password, save_config
from ...theme import BG, BORDER, CARD, MUTED
from ...utils import human_minutes


class SettingsPage:
    def _page_settings(self):
        f = self.page("Ajustes", "Quitar protecciones automáticas también pide pensarlo.")
        cols = ttk.Frame(f)
        cols.pack(fill="x")
        left = tk.Frame(cols, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 7))
        right = tk.Frame(cols, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(7, 0))

        c = self.card(left, "Automático")
        self.flags = {}
        for key, text in (("auto_apply_on_connect", "Al conectar el teléfono, aplicar todos los bloqueos"),
                          ("keep_applock_on", "Mantener encendido el bloqueo de apps de Xiaomi"),
                          ("wifi_auto", "Activar ADB por WiFi al conectar el cable y reconectar solo")):
            v = tk.BooleanVar(value=self.cfg[key])
            ttk.Checkbutton(c, text=text, variable=v, command=lambda k=key, v=v: self.toggle_flag(k, v)).pack(
                anchor="w", pady=2)
            self.flags[key] = v

        c = self.card(right, "Seguridad")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Contraseña para desbloquear", bg=CARD).pack(side="left")
        ttk.Button(row, text="Cambiar…", command=self.change_password).pack(side="right")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=6)
        tk.Label(row, text="Segundos de espera para desbloquear", bg=CARD).pack(side="left")
        self.wait_var = tk.IntVar(value=self.cfg["unlock_wait_sec"])
        ttk.Spinbox(row, from_=5, to=120, textvariable=self.wait_var, width=5,
                    command=self.change_wait).pack(side="right")
        tk.Label(c, text="Cada desbloqueo del mismo día suma 15 s más.", bg=CARD, fg=MUTED).pack(anchor="w")

        c = self.card(f, "Carpetas donde buscar APKs")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        self.folders_list = tk.Listbox(row, height=3, relief="flat", highlightthickness=1,
                                       highlightbackground=BORDER)
        self.folders_list.pack(side="left", fill="x", expand=True)
        b = tk.Frame(row, bg=CARD)
        b.pack(side="left", padx=(10, 0))
        ttk.Button(b, text="＋ Agregar", command=self.add_folder).pack(fill="x")
        ttk.Button(b, text="Quitar", command=self.remove_folder).pack(fill="x", pady=4)
        self.render_folders()

        c = self.card(f, "Historial de desbloqueos", fill="both", expand=True)
        self.log_tree = ttk.Treeview(c, columns=("cuando", "accion", "motivo", "duracion"), show="headings",
                                     height=6)
        for col, text, w in (("cuando", "Cuándo", 130), ("accion", "Qué", 260), ("motivo", "Motivo", 300),
                             ("duracion", "Por", 90)):
            self.log_tree.heading(col, text=text)
            self.log_tree.column(col, width=w)
        self.log_tree.pack(fill="both", expand=True)
        return f

    def render_folders(self):
        self.folders_list.delete(0, "end")
        for p in self.cfg["apk_folders"]:
            self.folders_list.insert("end", p)

    def add_folder(self):
        p = filedialog.askdirectory(parent=self, initialdir=os.path.expanduser("~"))
        if p:
            p = p.replace(os.path.expanduser("~"), "~", 1)
            if p not in self.cfg["apk_folders"]:
                self.cfg["apk_folders"].append(p)
                save_config(self.cfg)
                self.render_folders()

    def remove_folder(self):
        sel = self.folders_list.curselection()
        if sel:
            del self.cfg["apk_folders"][sel[0]]
            save_config(self.cfg)
            self.render_folders()

    def toggle_flag(self, key, var):
        if not var.get():  # apagar una protección automática cuesta
            labels = {"auto_apply_on_connect": "Dejar de aplicar bloqueos al conectar",
                      "keep_applock_on": "Dejar de mantener el bloqueo de apps encendido",
                      "wifi_auto": "Desactivar la reconexión automática por WiFi"}
            if not self.gate(labels[key]):
                var.set(True)
                return
        self.cfg[key] = var.get()
        save_config(self.cfg)

    def change_wait(self):
        try:
            new = max(5, min(120, int(self.wait_var.get())))
        except (tk.TclError, ValueError):
            return
        if new < self.cfg["unlock_wait_sec"] and not self.gate("Reducir la espera para desbloquear"):
            self.wait_var.set(self.cfg["unlock_wait_sec"])
            return
        self.cfg["unlock_wait_sec"] = new
        save_config(self.cfg)

    def render_log(self):
        self.log_tree.delete(*self.log_tree.get_children())
        for e in reversed(self.cfg["unlock_log"]):
            self.log_tree.insert("", "end", values=(e["ts"], e["action"], e["reason"],
                                                    human_minutes(e.get("minutes"))))

    def change_password(self):
        if self.cfg.get("password_hash") and not self.gate("Cambiar la contraseña"):
            return
        pw = simpledialog.askstring("Contraseña", "Nueva contraseña (vacío = quitar):", show="•", parent=self)
        if pw is None:
            return
        if pw == "":
            self.cfg["password_hash"] = self.cfg["password_salt"] = None
            save_config(self.cfg)
            self.set_status("Contraseña eliminada.")
            return
        pw2 = simpledialog.askstring("Contraseña", "Repite la contraseña:", show="•", parent=self)
        if pw2 != pw:
            messagebox.showerror("Contraseña", "No coinciden.", parent=self)
            return
        salt = secrets.token_hex(16)
        self.cfg["password_salt"] = salt
        self.cfg["password_hash"] = hash_password(pw, salt)
        save_config(self.cfg)
        self.set_status("Contraseña guardada.")
