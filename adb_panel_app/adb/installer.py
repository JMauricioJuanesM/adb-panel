"""Instalación de paquetes .apk / .xapk / .apks / .apkm."""
import os
import shutil
import tempfile
import zipfile

from .client import adb


def install_package_file(path):
    """Instala .apk, .xapk, .apks o .apkm. Regresa (ok, salida)."""
    if path.lower().endswith(".apk"):
        return adb("install", "-r", path, timeout=600)
    tmp = tempfile.mkdtemp(prefix="adb-panel-")
    try:
        with zipfile.ZipFile(path) as z:
            apks = [n for n in z.namelist() if n.lower().endswith(".apk")]
            obbs = [n for n in z.namelist() if n.lower().endswith(".obb")]
            if not apks:
                return False, "el archivo no trae APKs (¿está cifrado?)"
            z.extractall(tmp, apks + obbs)
        files = [os.path.join(tmp, n) for n in apks]
        ok, out = adb("install-multiple", "-r", *files, timeout=900)
        if ok and obbs:  # datos extra de juegos (XAPK)
            for n in obbs:
                dest = "/sdcard/" + n if n.startswith("Android/") else "/sdcard/Android/obb/" + n
                adb("shell", "mkdir", "-p", os.path.dirname(dest))
                adb("push", os.path.join(tmp, n), dest, timeout=900)
        return ok, out
    except zipfile.BadZipFile:
        return False, "el archivo está dañado o cifrado"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
