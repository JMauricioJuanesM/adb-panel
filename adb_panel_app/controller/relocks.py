"""Desbloqueos temporales: se vuelven a bloquear solos cuando vence su tiempo.

Cada desbloqueo es {"kind": "dns" | "applock" | "app", "pkg", "label", "at"}; `at` es la hora en que se
vuelve a bloquear, o None si lo desbloqueaste "hasta que lo reactive" (DNS y bloqueo de Xiaomi; una app
desbloqueada sin tiempo simplemente sale de la lista). La lista se comparte con la app del teléfono, que
la cumple aunque la compu esté apagada.
"""
import time

from ..adb.device import disable_app, dns_on, set_applock
from ..config import save_config
from ..utils import notify


class RelockController:
    def clear_relock(self, kind, pkg=None):
        """Ya se volvió a bloquear a mano: olvida su desbloqueo pendiente."""
        self.cfg["relocks"] = [r for r in self.cfg["relocks"] if not (r["kind"] == kind and r.get("pkg") == pkg)]
        save_config(self.cfg)

    def add_relock(self, kind, minutes, label, pkg=None):
        """Registra un desbloqueo; `minutes` None = hasta que lo reactives."""
        self.cfg["relocks"] = [r for r in self.cfg["relocks"] if not (r["kind"] == kind and r.get("pkg") == pkg)]
        if minutes is not None or kind != "app":
            at = time.time() + minutes * 60 if minutes is not None else None
            self.cfg["relocks"].append({"kind": kind, "pkg": pkg, "label": label, "at": at})
        save_config(self.cfg)

    def relock_pending(self, kind, pkg=None):
        return any(r["kind"] == kind and r.get("pkg") == pkg and (r["at"] is None or r["at"] > time.time())
                   for r in self.cfg["relocks"])

    def _relock_work(self, items):
        for r in items:
            if r["kind"] == "dns":
                dns_on(self.cfg["dns_hostname"])
            elif r["kind"] == "applock":
                set_applock(True)
            elif r["kind"] == "app":
                disable_app(r["pkg"])
        return items

    def _relock_done(self, items):
        for r in items:
            if r["kind"] == "app" and r["pkg"] not in self.cfg["blocked_apps"]:
                self.cfg["blocked_apps"].append(r["pkg"])
        self.cfg["relocks"] = [r for r in self.cfg["relocks"] if r not in items]
        save_config(self.cfg)
        names = ", ".join(r["label"] for r in items)
        notify("Se volvió a bloquear", names)
        self.set_status(f"Se volvió a bloquear: {names}")
        self.after(100, self.refresh_states)
        if self.packages:
            self.after(400, self.load_packages)

    def process_relocks(self):
        due = [r for r in self.cfg["relocks"] if r["at"] is not None and r["at"] <= time.time()]
        if due and self.device and not self.busy:
            self.run_bg(lambda: self._relock_work(due), self._relock_done, "Volviendo a bloquear…")

    def relock_now(self, r):
        r["at"] = 0
        self.process_relocks()
