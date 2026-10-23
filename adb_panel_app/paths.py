"""Rutas y constantes de archivos. `ADB_PANEL_CONFIG_DIR` permite usar otra carpeta (p. ej. para pruebas)."""
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY_SCRIPT = os.path.join(PROJECT_DIR, "adb_panel.py")

CONFIG_DIR = os.environ.get("ADB_PANEL_CONFIG_DIR") or os.path.expanduser("~/.config/adb-panel")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
# Tus valores por defecto personales (p. ej. tu servidor de NextDNS). Viven fuera del repositorio.
PERSONAL_DEFAULTS = os.path.join(CONFIG_DIR, "defaults.json")

CACHE_DIR = os.path.expanduser("~/.cache/adb-panel")
ICON_DIR = os.path.join(CACHE_DIR, "icons")
META_FILE = os.path.join(CACHE_DIR, "meta.json")
FILES_META = os.path.join(CACHE_DIR, "files.json")

ICON_SIZE = 28
WIFI_PORT = 5555
PACKAGE_EXTS = (".apk", ".xapk", ".apks", ".apkm")
