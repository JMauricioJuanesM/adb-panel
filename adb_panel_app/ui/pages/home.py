"""Página de inicio: conexión, protecciones y desbloqueos temporales."""
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ...adb.device import enable_wifi_adb, get_applock, set_applock, wifi_connect
from ...config import save_config
from ...paths import WIFI_PORT
from ...theme import AMBER, CARD, GREEN, MUTED, TEXT


class HomePage:
    def _page_home(self):
        f = self.page("Inicio", "El estado de tu teléfono y sus protecciones de un vistazo.")

        c = self.card(f, "Conexión")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        self.conn_lbl = tk.Label(row, text="Buscando el teléfono…", bg=CARD, fg=TEXT, font=("Sans", 11))
        self.conn_lbl.pack(side="left")
        ttk.Button(row, text="Conectar por WiFi", command=self.do_wifi_connect).pack(side="right")
        ttk.Button(row, text="Activar WiFi (con cable)", command=self.do_wifi_enable).pack(side="right", padx=6)
        self.wifi_lbl = tk.Label(c, text="", bg=CARD, fg=MUTED)
        self.wifi_lbl.pack(anchor="w", pady=(6, 0))

        c = self.card(f, "Protecciones")
        self.prot = {}
        for key, icon, name in (("dns", "🌐", "DNS privado (filtro de sitios)"),
                                ("applock", "🔐", "Bloqueo de apps de Xiaomi"),
                                ("apps", "🚫", "Apps bloqueadas")):
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=icon, bg=CARD, font=("Sans", 14)).pack(side="left")
            tk.Label(row, text=name, bg=CARD, fg=TEXT, font=("Sans", 11)).pack(side="left", padx=10)
            btn = ttk.Button(row, text="")
            btn.pack(side="right")
            pill = self.pill(row)
            pill.pack(side="right", padx=12)
            self.prot[key] = (pill, btn)

        ttk.Button(f, text="🛡   Aplicar todos los bloqueos ahora", style="Big.Accent.TButton",
                   command=self.apply_blocks).pack(fill="x", pady=(0, 14))

        c = self.card(f, "Desbloqueos temporales")
        self.relock_box = tk.Frame(c, bg=CARD)
        self.relock_box.pack(fill="x")
        self.phone_lbl = tk.Label(c, text="", bg=CARD, fg=MUTED, justify="left", wraplength=700)
        self.phone_lbl.pack(anchor="w", pady=(10, 0))
        return f

    def render_home(self):
        dns, applock = self.state_cache["dns"], self.state_cache["applock"]
        pill, btn = self.prot["dns"]
        if dns is None:
            self.set_pill(pill, "sin leer", "neutral")
            btn.config(text="Leer", command=self.refresh_states, style="TButton")
        elif dns[0] == "hostname":
            name = next((s["name"] for s in self.cfg["dns_servers"] if s["host"] == dns[1]), dns[1])
            self.set_pill(pill, f"ENCENDIDO · {name}", "on")
            btn.config(text="Apagar… 🔒", command=self.do_dns_off, style="TButton")
        else:
            self.set_pill(pill, "APAGADO", "off")
            btn.config(text="Encender", command=self.do_dns_on, style="Good.TButton")

        pill, btn = self.prot["applock"]
        if applock == "1":
            self.set_pill(pill, "ENCENDIDO", "on")
            btn.config(text="Apagar… 🔒", command=lambda: self.do_applock(False), style="TButton")
        elif applock == "0":
            self.set_pill(pill, "APAGADO", "off")
            btn.config(text="Encender", command=lambda: self.do_applock(True), style="Good.TButton")
        else:
            self.set_pill(pill, "sin leer", "neutral")
            btn.config(text="Leer", command=self.refresh_states, style="TButton")

        pill, btn = self.prot["apps"]
        n = len(self.cfg["blocked_apps"])
        self.set_pill(pill, f"{n} app{'s' if n != 1 else ''}", "on" if n else "neutral")
        btn.config(text="Ver", command=self.show_blocked, style="TButton")

        for w in self.relock_box.winfo_children():
            w.destroy()
        if not self.cfg["relocks"]:
            tk.Label(self.relock_box, text="✔  Ninguno: todo lo que bloqueaste sigue bloqueado.", bg=CARD,
                     fg=GREEN).pack(anchor="w")
        for r in sorted(self.cfg["relocks"], key=lambda r: r["at"] or float("inf")):
            row = tk.Frame(self.relock_box, bg=CARD)
            row.pack(fill="x", pady=2)
            if r["at"] is None:
                text = f"🔓  {r['label']} — desbloqueado hasta que lo reactives"
            else:
                text = f"⏳  {r['label']} — se vuelve a bloquear en {max(0, int(r['at'] - time.time())) // 60} min"
            tk.Label(row, text=text, bg=CARD, fg=AMBER).pack(side="left")
            ttk.Button(row, text="Bloquear ya", style="Accent.TButton",
                       command=lambda r=r: self.relock_now(r)).pack(side="right")
        self.phone_lbl.config(text=self.phone_guard_text())

        self.render_connection()

    def phone_guard_text(self):
        """¿El teléfono cumplirá los desbloqueos aunque apagues la compu?"""
        if not self.sync.enabled:
            return "Sin sincronización: los desbloqueos solo se revierten con la compu prendida y el panel abierto."
        if not self.sync.online:
            return "Sin conexión con el servidor: el teléfono no se ha enterado de los últimos cambios."
        info = self.sync.phone_info()
        if not info:
            return "La app Pomodoro del teléfono no ha reportado: instálala para que cumpla los bloqueos sola."
        missing = [name for key, name in (("secure", "ajustes seguros"), ("guard", "accesibilidad")) if not info.get(key)]
        if missing:
            return (f"📱 A la app del teléfono le falta: {', '.join(missing)}. Conecta el teléfono y se los doy "
                    "por ADB.")
        return "📱 El teléfono cumple estos desbloqueos y bloqueos él solo, aunque apagues la compu."

    def show_blocked(self):
        self.show_page("apps")
        self.filter.set("Bloqueadas")
        self.refresh_list()

    def render_connection(self):
        if self.device:
            via = " y ".join(x for x in ("cable" if self.usb_serial else "", "WiFi" if self.wifi_connected else "")
                             if x)
            model = self.state_cache["model"]
            self.conn_lbl.config(text=f"✅  {model or 'Teléfono'} conectado por {via}")
            self.side_status.config(text=f"● {model or 'Teléfono'}\n   conectado por {via}", fg="#7ee2a0")
        else:
            self.conn_lbl.config(text="⚠  Sin teléfono. Conéctalo con el cable o por WiFi.")
            self.side_status.config(text="● sin teléfono", fg="#f19a9a")
        ip = self.cfg.get("wifi_ip")
        if self.wifi_connected:
            self.wifi_lbl.config(text=f"WiFi: conectado a {ip}:{WIFI_PORT}. Ya puedes quitar el cable.")
        elif ip:
            self.wifi_lbl.config(text=f"WiFi: sin conexión (última IP {ip}). Si reiniciaste el teléfono, "
                                      "conecta el cable una vez y se reactiva solo.")
        else:
            self.wifi_lbl.config(text="WiFi: nunca activado. Conecta el cable y se activa solo.")

    def do_applock(self, on):
        if not self.need_device():
            return
        if on:
            self.clear_relock("applock")
        else:
            g = self.gate("Apagar el bloqueo de apps de Xiaomi", temporary=True, short=True)
            if not g:
                return
            self.add_relock("applock", g["minutes"], "Bloqueo de apps de Xiaomi")

        def done(v):
            self.state_cache["applock"] = v
            self.render_home()
            self.set_status("Bloqueo de apps " + ("encendido." if on else "apagado."))

        self.run_bg(lambda: (set_applock(on), get_applock())[1], done, "Cambiando bloqueo de apps…")

    def do_wifi_enable(self):
        if not self.usb_serial:
            messagebox.showinfo("ADB por WiFi", "Para activarlo conecta el teléfono con el cable.", parent=self)
            return
        usb = self.usb_serial

        def done(res):
            ok, out, ip = res
            if ip:
                self.cfg["wifi_ip"] = ip
                save_config(self.cfg)
            self.set_status(f"ADB por WiFi activado ({ip}). Ya puedes desconectar el cable." if ok
                            else f"No se pudo: {out}")

        self.run_bg(lambda: enable_wifi_adb(usb), done, "Activando ADB por WiFi…")

    def do_wifi_connect(self):
        ip = self.cfg.get("wifi_ip")
        if not ip:
            ip = simpledialog.askstring("ADB por WiFi", "IP del teléfono:", parent=self)
            if not ip:
                return
            self.cfg["wifi_ip"] = ip.strip()
            save_config(self.cfg)
        self.run_bg(lambda: wifi_connect(self.cfg["wifi_ip"]),
                    lambda r: self.set_status("Conectado por WiFi." if r[0] else
                                              f"No conectó: {r[1]} (¿reiniciaste el teléfono? conecta el cable)"),
                    "Conectando por WiFi…")
