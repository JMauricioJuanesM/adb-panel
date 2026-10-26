"""Diálogo de desbloqueo lento: motivo + espera para pensarlo + contraseña (+ duración)."""
import datetime as dt
import tkinter as tk
from tkinter import messagebox, ttk

from ..config import hash_password
from ..theme import CARD, MUTED, TEXT


class Gate(tk.Toplevel):
    """Diálogo para desbloquear: motivo + espera para pensarlo + contraseña (+ duración).

    `self.result` queda en None si se cancela, o {"minutes": int | None} (None = permanente).
    """

    DURATIONS = [("15 min", 15), ("30 min", 30), ("1 hora", 60), ("2 horas", 120), ("Hasta que lo reactive", None)]
    # DNS y bloqueo de Xiaomi: abrirlos es riesgo de recaída; para revisar algo rápido bastan 15 min
    # (el teléfono también los corta a los 15 min, pida lo que pida el panel).
    SHORT_DURATIONS = [("5 min", 5), ("10 min", 10), ("15 min", 15)]

    def __init__(self, app, action, temporary, short=False):
        super().__init__(app)
        self.app = app
        self.result = None
        self.title("Desbloquear")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(app)

        today = dt.date.today().isoformat()
        n_today = sum(1 for e in app.cfg["unlock_log"] if e["ts"].startswith(today))
        # Cada desbloqueo del día agrega 15 s más de espera.
        self.left = min(180, app.cfg["unlock_wait_sec"] + 15 * n_today)

        f = tk.Frame(self, bg=CARD, padx=26, pady=22)
        f.pack()
        tk.Label(f, text="🔓  " + action, bg=CARD, fg=TEXT, font=("Sans", 14, "bold"),
                 wraplength=420, justify="left").pack(anchor="w")
        msg = "Bloquear es fácil; desbloquear te pide pensarlo un momento."
        if n_today:
            msg += f"\nHoy ya desbloqueaste {n_today} {'vez' if n_today == 1 else 'veces'}."
        tk.Label(f, text=msg, bg=CARD, fg=MUTED, justify="left").pack(anchor="w", pady=(4, 14))

        tk.Label(f, text="¿Para qué lo necesitas?", bg=CARD, fg=TEXT, font=("Sans", 10, "bold")).pack(anchor="w")
        self.reason = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.reason, width=48)
        e.pack(anchor="w", fill="x", pady=(2, 12))
        e.focus_set()

        self.durations = self.SHORT_DURATIONS if short else self.DURATIONS
        self.duration = tk.IntVar(value=1)
        if temporary:
            tk.Label(f, text="¿Por cuánto tiempo?", bg=CARD, fg=TEXT, font=("Sans", 10, "bold")).pack(anchor="w")
            row = tk.Frame(f, bg=CARD)
            row.pack(anchor="w", pady=(2, 12))
            for i, (label, _) in enumerate(self.durations):
                ttk.Radiobutton(row, text=label, value=i, variable=self.duration).pack(side="left", padx=(0, 8))
        self.temporary = temporary

        self.pw = tk.StringVar()
        if app.cfg.get("password_hash"):
            tk.Label(f, text="Contraseña", bg=CARD, fg=TEXT, font=("Sans", 10, "bold")).pack(anchor="w")
            ttk.Entry(f, textvariable=self.pw, show="•", width=30).pack(anchor="w", pady=(2, 12))

        self.bar = ttk.Progressbar(f, maximum=self.left, length=420)
        self.bar.pack(fill="x")
        self.wait_lbl = tk.Label(f, text="", bg=CARD, fg=MUTED)
        self.wait_lbl.pack(anchor="w", pady=(4, 12))

        row = tk.Frame(f, bg=CARD)
        row.pack(fill="x")
        self.ok_btn = ttk.Button(row, text="Desbloquear", style="Danger.TButton", command=self.accept)
        self.ok_btn.pack(side="right")
        ttk.Button(row, text="Mejor no", style="Accent.TButton", command=self.destroy).pack(side="right", padx=8)
        self.total = self.left
        self.reason.trace_add("write", lambda *_: self.update_state())
        self.pw.trace_add("write", lambda *_: self.update_state())
        self.tick()
        self.grab_set()

    def tick(self):
        if not self.winfo_exists():
            return
        self.bar["value"] = self.total - self.left
        if self.left > 0:
            self.wait_lbl.config(text=f"Respira. Podrás continuar en {self.left} s…")
            self.left -= 1
            self.after(1000, self.tick)
        else:
            self.wait_lbl.config(text="Listo. Si de verdad lo necesitas, continúa.")
        self.update_state()

    def update_state(self):
        ready = (self.left <= 0 and len(self.reason.get().strip()) >= 8
                 and (not self.app.cfg.get("password_hash") or self.pw.get()))
        self.ok_btn.state(["!disabled"] if ready else ["disabled"])

    def accept(self):
        cfg = self.app.cfg
        if cfg.get("password_hash") and hash_password(self.pw.get(), cfg["password_salt"]) != cfg["password_hash"]:
            messagebox.showerror("Contraseña", "Contraseña incorrecta.", parent=self)
            return
        minutes = self.durations[self.duration.get()][1] if self.temporary else None
        self.result = {"minutes": minutes, "reason": self.reason.get().strip()}
        self.destroy()
