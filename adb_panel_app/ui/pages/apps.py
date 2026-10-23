"""Página de apps: lista, búsqueda y acciones (bloquear, desactivar, activar, desinstalar)."""
import tkinter as tk
from tkinter import messagebox, ttk

from ...adb.device import disable_app, dns_on, enable_app, list_packages, set_applock, uninstall_app
from ...config import save_config
from ...theme import BG, BORDER, CARD, RED


class AppsPage:
    def _page_apps(self):
        f = self.page("Apps", "Bloquear es inmediato. Activar o quitar bloqueos pide pensarlo un momento.")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        tk.Label(bar, text="🔍", bg=BG).pack(side="left", padx=(0, 4))
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.refresh_list())
        ttk.Entry(bar, textvariable=self.search, width=34).pack(side="left", padx=(0, 16))
        self.filter = ttk.Combobox(bar, values=["Todas", "Activas", "Desactivadas", "Bloqueadas"],
                                   state="readonly", width=13)
        self.filter.set("Todas")
        self.filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())
        self.filter.pack(side="left")
        self.show_system = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Incluir apps del sistema", variable=self.show_system, bg=BG,
                       activebackground=BG, highlightthickness=0, command=self.load_packages).pack(side="left",
                                                                                                padx=14)
        ttk.Button(bar, text="↻ Recargar", command=self.load_packages).pack(side="right")

        box = tk.Frame(f, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, columns=("pkg", "estado"), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="App")
        self.tree.heading("pkg", text="Paquete")
        self.tree.heading("estado", text="Estado")
        self.tree.column("#0", width=280)
        self.tree.column("pkg", width=300)
        self.tree.column("estado", width=150, anchor="center")
        self.tree.tag_configure("off", foreground=RED)
        self.tree.tag_configure("blocked", foreground=RED, background="#fff4f4")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Button-3>", self.apps_menu)

        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="🚫 Bloquear", style="Accent.TButton", command=self.do_block).pack(side="left")
        ttk.Button(actions, text="Desactivar", command=self.do_disable).pack(side="left", padx=6)
        ttk.Button(actions, text="🗑 Desinstalar…", style="Danger.TButton", command=self.do_uninstall).pack(side="left")
        ttk.Button(actions, text="Quitar bloqueo 🔒", command=self.do_unblock).pack(side="right")
        ttk.Button(actions, text="Activar 🔒", command=self.do_enable).pack(side="right", padx=6)
        return f

    def apps_menu(self, e):
        row = self.tree.identify_row(e.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="🚫 Bloquear", command=self.do_block)
        m.add_command(label="Desactivar", command=self.do_disable)
        m.add_command(label="🗑 Desinstalar…", command=self.do_uninstall)
        m.add_separator()
        m.add_command(label="Activar 🔒", command=self.do_enable)
        m.add_command(label="Quitar bloqueo 🔒", command=self.do_unblock)
        m.tk_popup(e.x_root, e.y_root)

    def load_packages(self):
        if not self.device:
            return
        inc = self.show_system.get()

        def done(pkgs):
            self.packages = pkgs
            self.refresh_list()
            self.meta.request(sorted(pkgs), self.device)
            self.set_status(f"{len(pkgs)} apps. Los nombres e iconos que falten se cargan en segundo plano.")

        self.run_bg(lambda: list_packages(inc), done, "Cargando apps…")

    def refresh_list(self):
        self.refresh_pending = False
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        q = self.search.get().lower().strip()
        flt = self.filter.get()
        blocked = set(self.cfg["blocked_apps"])
        rows = sorted(self.packages, key=lambda p: (self.meta.name(p) is None, self.display_name(p).lower()))
        for pkg in rows:
            name = self.display_name(pkg)
            if q and q not in pkg.lower() and q not in name.lower():
                continue
            enabled, system = self.packages[pkg]
            is_blocked = pkg in blocked
            if (flt == "Activas" and not enabled) or (flt == "Desactivadas" and enabled) \
                    or (flt == "Bloqueadas" and not is_blocked):
                continue
            if is_blocked:
                state, tags = "🚫 bloqueada", ["blocked"]
            elif not enabled:
                state, tags = "desactivada", ["off"]
            else:
                state, tags = "activa", []
            if self.relock_pending("app", pkg):
                state = "⏳ temporal"
            self.tree.insert("", "end", iid=pkg, text=" " + name + ("  ·  sistema" if system else ""),
                             image=self.icon_for(pkg), values=(pkg, state), tags=tags)
        keep = [p for p in sel if self.tree.exists(p)]
        if keep:
            self.tree.selection_set(keep)

    def on_meta(self, pkg):
        self.images.pop(pkg, None)
        if self.tree.exists(pkg):
            system = self.packages.get(pkg, (True, False))[1]
            self.tree.item(pkg, text=" " + self.display_name(pkg) + ("  ·  sistema" if system else ""),
                           image=self.icon_for(pkg))
        if not self.refresh_pending:   # reordena cada tanto, no en cada icono
            self.refresh_pending = True
            self.after(4000, self.refresh_list)

    def selected(self):
        return list(self.tree.selection())

    def _batch(self, pkgs, fn, verb):
        def work():
            errors = []
            for p in pkgs:
                ok, out = fn(p)
                if not ok or "Exception" in out or "Failure" in out or "Error" in out:
                    errors.append(f"{p}: {out}")
            return errors

        def done(errors):
            if errors:
                messagebox.showerror("Algunas fallaron", "\n".join(errors[:10]), parent=self)
            self.set_status(f"{verb}: {len(pkgs) - len(errors)} de {len(pkgs)}.")
            self.load_packages()

        self.run_bg(work, done, f"{verb}…")

    def do_block(self):
        pkgs = self.selected()
        if not pkgs or not self.need_device():
            return
        self.cfg["blocked_apps"] = sorted(set(self.cfg["blocked_apps"]) | set(pkgs))
        self.cfg["relocks"] = [r for r in self.cfg["relocks"] if not (r["kind"] == "app" and r["pkg"] in pkgs)]
        save_config(self.cfg)
        self._batch(pkgs, disable_app, "Bloqueadas")

    def do_disable(self):
        pkgs = self.selected()
        if pkgs and self.need_device():
            self._batch(pkgs, disable_app, "Desactivadas")

    def do_enable(self):
        pkgs = self.selected()
        if not pkgs or not self.need_device():
            return
        g = self.gate(f"Activar {self.names(pkgs)}", temporary=True)
        if not g:
            return
        self.cfg["blocked_apps"] = [p for p in self.cfg["blocked_apps"] if p not in pkgs]
        for p in pkgs:  # temporal: se vuelve a bloquear sola
            self.add_relock("app", g["minutes"], self.display_name(p), pkg=p)
        save_config(self.cfg)
        self._batch(pkgs, enable_app, "Activadas")

    def do_unblock(self):
        pkgs = [p for p in self.selected() if p in self.cfg["blocked_apps"]]
        if not pkgs:
            self.set_status("Selecciona apps bloqueadas.")
            return
        if not self.gate(f"Quitar de la lista de bloqueo: {self.names(pkgs)}"):
            return
        self.cfg["blocked_apps"] = [p for p in self.cfg["blocked_apps"] if p not in pkgs]
        save_config(self.cfg)
        self.refresh_list()
        self.set_status("Quitadas de la lista (siguen desactivadas; usa Activar si quieres).")

    def do_uninstall(self):
        pkgs = self.selected()
        if not pkgs or not self.need_device():
            return
        system = [p for p in pkgs if self.packages.get(p, (True, False))[1]]
        msg = f"¿Desinstalar {self.names(pkgs)}?\n\nSe borran la app y sus datos."
        if system:
            msg += ("\n\nOjo: incluye apps del sistema. Esas solo se quitan para tu usuario (se pueden "
                    "recuperar), pero quitar algunas puede causar fallas.")
        if not messagebox.askyesno("Desinstalar", msg, icon="warning", parent=self):
            return
        self.cfg["blocked_apps"] = [p for p in self.cfg["blocked_apps"] if p not in pkgs]
        save_config(self.cfg)
        self._batch(pkgs, lambda p: uninstall_app(p, p in system), "Desinstaladas")

    def _apply_blocks_work(self):
        apps = [p for p in self.cfg["blocked_apps"] if not self.relock_pending("app", p)]
        for p in apps:
            disable_app(p)
        parts = [f"{len(apps)} apps desactivadas"]
        if not self.relock_pending("dns"):
            dns_on(self.cfg["dns_hostname"])
            parts.append("DNS encendido")
        if self.cfg["keep_applock_on"] and not self.relock_pending("applock"):
            set_applock(True)
            parts.append("bloqueo de apps encendido")
        return "Bloqueos aplicados: " + ", ".join(parts)

    def apply_blocks(self):
        if not self.need_device():
            return

        def done(msg):
            self.set_status(msg)
            self.load_packages()
            self.after(200, self.refresh_states)

        self.run_bg(self._apply_blocks_work, done, "Aplicando bloqueos…")
