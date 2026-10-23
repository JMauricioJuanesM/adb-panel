"""Configuración: valores por defecto, carga y guardado (el archivo queda solo para tu usuario).

Orden de carga: valores de este archivo → `~/.config/adb-panel/defaults.json` (tus datos personales,
p. ej. tu servidor de NextDNS; ver `defaults.example.json`) → `~/.config/adb-panel/config.json`.
"""
import copy
import hashlib
import json
import os

from .paths import CONFIG_DIR, CONFIG_FILE, PERSONAL_DEFAULTS

PUBLIC_DNS = [
    {"name": "CleanBrowsing Familia", "host": "family-filter-dns.cleanbrowsing.org"},
    {"name": "CleanBrowsing Adultos", "host": "adult-filter-dns.cleanbrowsing.org"},
    {"name": "AdGuard Familia", "host": "family.adguard-dns.com"},
    {"name": "AdGuard (sin anuncios)", "host": "dns.adguard-dns.com"},
    {"name": "Cloudflare Familia", "host": "family.cloudflare-dns.com"},
    {"name": "Cloudflare", "host": "one.one.one.one"},
    {"name": "Google", "host": "dns.google"},
    {"name": "Quad9", "host": "dns.quad9.net"},
]

DEFAULT_CONFIG = {
    "password_hash": None,
    "password_salt": None,
    "dns_hostname": PUBLIC_DNS[0]["host"],   # servidor activo
    "dns_servers": PUBLIC_DNS,
    "blocked_apps": [],          # apps que el panel mantiene desactivadas
    "auto_apply_on_connect": True,
    "keep_applock_on": True,     # re-encender el bloqueo de apps de Xiaomi al aplicar bloqueos
    "wifi_auto": True,           # activar ADB por WiFi al conectar por USB y reconectar solo
    "wifi_ip": None,
    "unlock_wait_sec": 20,       # segundos para "pensarlo" antes de desbloquear algo
    "unlock_log": [],            # historial de desbloqueos
    "relocks": [],               # desbloqueos temporales pendientes de revertir
    "apk_folders": ["~/Downloads", "~/Documents/APK"],
}


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_config():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    personal = _read_json(PERSONAL_DEFAULTS) or {}
    personal.pop("_comentario", None)
    cfg.update(copy.deepcopy(personal))
    cfg.update(_read_json(CONFIG_FILE) or {})
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_FILE)


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
