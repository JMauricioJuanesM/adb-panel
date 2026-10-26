"""Sincronización de los bloqueos con la app del teléfono (a través del servidor del Pomodoro en el VPS).

El panel publica lo que debe estar bloqueado (DNS, bloqueo de apps de Xiaomi, apps bloqueadas) y los
desbloqueos temporales con su hora de vencimiento. La app del teléfono los cumple aunque la compu esté
apagada: al vencer un desbloqueo vuelve a bloquear sola y avisa aquí, y el panel adopta ese cambio.

Usa `~/.config/adb-panel/sync.json` o, si no existe, el del Pomodoro (`~/.config/pomodoro-ahuevo/sync.json`):
{"url": "https://…", "token": "…"}. Sin ninguno de los dos, el panel funciona igual, sin sincronizar.
"""
import datetime as dt
import json
import os
import threading
import time
import urllib.error
import urllib.request

from .config import save_config
from .paths import CONFIG_DIR

SOURCE = "panel"
SYNC_FILES = (os.path.join(CONFIG_DIR, "sync.json"), os.path.expanduser("~/.config/pomodoro-ahuevo/sync.json"))


def read_settings():
    for path in SYNC_FILES:
        try:
            with open(path) as f:
                s = json.load(f)
            if s.get("url") and s.get("token"):
                return s
        except (OSError, ValueError):
            continue
    return None


class BlocksSync:
    def __init__(self, app):
        self.app = app
        self.settings = read_settings()
        self.rev = -1                 # -1: la primera consulta responde al instante
        self.remote = None            # último estado recibido del servidor
        self.sent = None              # JSON de lo último que enviamos
        self.pending = None
        self.lock = threading.Condition()
        self.online = False
        if self.settings:
            threading.Thread(target=self._poll_loop, daemon=True).start()
            threading.Thread(target=self._send_loop, daemon=True).start()

    @property
    def enabled(self):
        return self.settings is not None

    # ---------- red (hilos aparte) ----------
    def _req(self, method, path, body=None, timeout=15):
        req = urllib.request.Request(self.settings["url"].rstrip("/") + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + self.settings["token"],
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    def _poll_loop(self):
        while True:
            try:
                st = self._req("GET", f"/api/wait?rev={self.rev}&source={SOURCE}&timeout=40", timeout=60)
                self.online = True
                self.rev = st["rev"]
                self.app.after(0, lambda st=st: self._on_state(st))
            except (OSError, ValueError, urllib.error.URLError):
                self.online = False
                time.sleep(15)

    def _send_loop(self):
        while True:
            with self.lock:
                while self.pending is None:
                    self.lock.wait()
                body = self.pending
            try:
                self._req("PUT", "/api/blocks", body)
                with self.lock:
                    if self.pending is body:
                        self.pending = None
            except (OSError, ValueError, urllib.error.URLError):
                time.sleep(15)

    # ---------- hilo de la interfaz ----------
    def snapshot(self):
        cfg = self.app.cfg
        pkgs = set(cfg["blocked_apps"]) | {r["pkg"] for r in cfg["relocks"] if r.get("pkg")}
        return {"dns_host": cfg["dns_hostname"], "keep_applock_on": cfg["keep_applock_on"],
                "blocked_apps": sorted(cfg["blocked_apps"]), "relocks": cfg["relocks"],
                "unlock_wait_sec": cfg["unlock_wait_sec"], "phone_log": cfg.get("phone_log", []),
                "labels": {p: self.app.display_name(p) for p in sorted(pkgs)}}

    def tick(self):
        """Cada segundo: si cambió algo de los bloqueos, lo manda."""
        if not self.enabled or self.remote is None:   # primero hay que saber qué tiene el servidor
            return
        snap = json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=False)
        if snap != self.sent:
            self.sent = snap
            with self.lock:
                self.pending = {"source": SOURCE, "blocks": json.loads(snap)}
                self.lock.notify()

    def _on_state(self, st):
        self.remote = st
        cfg = self.app.cfg
        blocks = st.get("blocks")
        # Lo que hizo el teléfono (volver a bloquear algo), también si fue con la compu apagada.
        if blocks and st.get("blocks_source") != SOURCE and st.get("blocks_rev", 0) > cfg.get("sync_blocks_rev", 0):
            cfg["relocks"] = blocks.get("relocks", cfg["relocks"])
            cfg["blocked_apps"] = blocks.get("blocked_apps", cfg["blocked_apps"])
            self._import_phone_log(blocks.get("phone_log") or [])
            self.sent = json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=False)
            self.app.after(100, self.app.render_home)
        if cfg.get("sync_blocks_rev") != st.get("blocks_rev", 0):
            cfg["sync_blocks_rev"] = st.get("blocks_rev", 0)
            save_config(cfg)

    def _import_phone_log(self, log):
        """Los desbloqueos de emergencia hechos en el teléfono pasan a tu historial."""
        cfg = self.app.cfg
        known = {e["ts"] for e in cfg.get("phone_log", [])}
        names = {"dns": "Apagar el DNS (desde el teléfono)", "applock": "Apagar el bloqueo de apps de Xiaomi (desde el teléfono)"}
        for e in log:
            if e["ts"] not in known:
                cfg["unlock_log"].append({"ts": dt.datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M"),
                                          "action": names.get(e["kind"], e["kind"]), "reason": e.get("reason", ""),
                                          "minutes": e.get("minutes")})
        cfg["phone_log"] = log

    def phone_info(self):
        return ((self.remote or {}).get("devices") or {}).get("phone", {}).get("info") or {}
