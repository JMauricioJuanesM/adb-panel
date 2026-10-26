"""Página del DNS privado: servidor activo y lista de servidores."""
import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ...adb.device import dns_off, dns_on, get_dns
from ...config import save_config
from ...theme import BORDER, CARD, GREEN, TEXT


class DnsPage:
    def _page_dns(self):
        f = self.page("DNS privado", "El filtro de sitios del teléfono. En verde, el servidor que se usa.")
        c = self.card(f)
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        tk.Label(row, text="En el teléfono:", bg=CARD, fg=TEXT, font=("Sans", 11, "bold")).pack(side="left")
        self.dns_pill = self.pill(row)
        self.dns_pill.pack(side="left", padx=10)
        ttk.Button(row, text="Apagar… 🔒", command=self.do_dns_off).pack(side="right")
        ttk.Button(row, text="Encender", style="Good.TButton", command=self.do_dns_on).pack(side="right", padx=6)

        box = tk.Frame(f, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True)
        self.dns_tree = ttk.Treeview(box, columns=("host",), show="tree headings")
        self.dns_tree.heading("#0", text="Nombre")
        self.dns_tree.heading("host", text="Servidor")
        self.dns_tree.column("#0", width=260)
        self.dns_tree.column("host", width=380)
        self.dns_tree.tag_configure("active", foreground=GREEN, font=("Sans", 10, "bold"))
        self.dns_tree.pack(fill="both", expand=True)
        self.dns_tree.bind("<Double-1>", lambda e: self.do_dns_use())

        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="Usar este servidor 🔒", command=self.do_dns_use).pack(side="left")
        ttk.Button(actions, text="＋ Agregar…", command=self.do_dns_add).pack(side="left", padx=6)
        ttk.Button(actions, text="Quitar 🔒", command=self.do_dns_remove).pack(side="right")
        self.render_dns_list()
        return f

    def render_dns_list(self):
        sel = self.dns_tree.selection()
        self.dns_tree.delete(*self.dns_tree.get_children())
        for i, s in enumerate(self.cfg["dns_servers"]):
            active = s["host"] == self.cfg["dns_hostname"]
            self.dns_tree.insert("", "end", iid=str(i), text=("✔  " if active else "     ") + s["name"],
                                 values=(s["host"],), tags=["active"] if active else [])
        if sel and self.dns_tree.exists(sel[0]):
            self.dns_tree.selection_set(sel[0])

    def show_dns(self, res):
        mode, host = res
        if mode == "hostname":
            self.set_pill(self.dns_pill, f"ENCENDIDO → {host}", "on")
        elif mode == "off":
            self.set_pill(self.dns_pill, "APAGADO", "off")
        else:
            self.set_pill(self.dns_pill, f"modo: {mode}", "warn")

    def _dns_done(self, res, msg):
        self.state_cache["dns"] = res
        self.show_dns(res)
        self.render_home()
        self.set_status(msg)

    def selected_dns(self):
        sel = self.dns_tree.selection()
        return self.cfg["dns_servers"][int(sel[0])] if sel else None

    def do_dns_use(self):
        s = self.selected_dns()
        if not s or not self.need_device():
            return
        if s["host"] != self.cfg["dns_hostname"]:
            if not self.gate(f"Cambiar el DNS a {s['name']}"):
                return
            self.cfg["dns_hostname"] = s["host"]
            save_config(self.cfg)
            self.render_dns_list()
        self.do_dns_on()

    def do_dns_on(self):
        if not self.need_device():
            return
        host = self.cfg["dns_hostname"]
        self.clear_relock("dns")
        self.run_bg(lambda: (dns_on(host), get_dns())[1], lambda r: self._dns_done(r, f"DNS encendido: {host}"),
                    "Encendiendo DNS…")

    def do_dns_off(self):
        if not self.need_device():
            return
        g = self.gate("Apagar el DNS (filtro de sitios)", temporary=True)
        if not g:
            return
        self.add_relock("dns", g["minutes"], "DNS privado")
        self.run_bg(lambda: (dns_off(), get_dns())[1], lambda r: self._dns_done(r, "DNS apagado."),
                    "Apagando DNS…")

    def do_dns_add(self):
        name = simpledialog.askstring("Agregar DNS", "Nombre (ej. Mi NextDNS):", parent=self)
        if not name:
            return
        host = simpledialog.askstring("Agregar DNS", "Servidor (ej. abc123.dns.nextdns.io):", parent=self)
        if not host or not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", host.strip()):
            if host:
                messagebox.showerror("DNS", "Eso no parece un nombre de servidor válido.", parent=self)
            return
        self.cfg["dns_servers"].append({"name": name.strip(), "host": host.strip()})
        save_config(self.cfg)
        self.render_dns_list()

    def do_dns_remove(self):
        s = self.selected_dns()
        if not s:
            return
        if s["host"] == self.cfg["dns_hostname"]:
            messagebox.showinfo("DNS", "No puedes quitar el servidor activo. Cambia a otro primero.", parent=self)
            return
        if not self.gate(f"Quitar {s['name']} de la lista de DNS"):
            return
        self.cfg["dns_servers"].remove(s)
        save_config(self.cfg)
        self.render_dns_list()
