"""Caché de nombres/iconos de las apps instaladas, que se llena en segundo plano."""
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from ..paths import CACHE_DIR, ENTRY_SCRIPT, ICON_DIR, META_FILE
from .play import fetch_play_meta


class MetaStore:
    """Caché de nombres/iconos de apps instaladas que se llena en segundo plano."""

    def __init__(self, on_update):
        self.on_update = on_update   # llamado (desde hilos) con el paquete actualizado
        self.lock = threading.Lock()
        self.pending = set()
        self.play_pool = ThreadPoolExecutor(6)
        self.apk_pool = ThreadPoolExecutor(2)
        try:
            with open(META_FILE) as f:
                self.meta = json.load(f)
        except (OSError, ValueError):
            self.meta = {}

    def name(self, pkg):
        return (self.meta.get(pkg) or {}).get("name")

    def icon_path(self, pkg):
        p = os.path.join(ICON_DIR, pkg + ".png")
        return p if os.path.exists(p) else None

    def request(self, pkgs, serial):
        for pkg in pkgs:
            with self.lock:
                if pkg in self.meta or pkg in self.pending:
                    continue
                self.pending.add(pkg)
            self.play_pool.submit(self._play, pkg, serial)

    def _play(self, pkg, serial):
        try:
            m = fetch_play_meta(pkg)
        except (OSError, ValueError):  # sin internet: no se guarda, se reintenta luego
            with self.lock:
                self.pending.discard(pkg)
            return
        if m is None:
            self.apk_pool.submit(self._apk, pkg, serial)
        else:
            self._store(pkg, m)

    def _apk(self, pkg, serial):
        try:
            r = subprocess.run([sys.executable, ENTRY_SCRIPT, "--apk-meta", serial, pkg],
                               capture_output=True, text=True, timeout=300)
            m = json.loads(r.stdout.strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            m = {"name": None, "src": "none"}
        self._store(pkg, m)

    def _store(self, pkg, m):
        with self.lock:
            self.meta[pkg] = m
            self.pending.discard(pkg)
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(META_FILE + ".tmp", "w") as f:
                json.dump(self.meta, f, ensure_ascii=False)
            os.replace(META_FILE + ".tmp", META_FILE)
        self.on_update(pkg)
