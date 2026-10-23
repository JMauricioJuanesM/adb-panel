"""Nombre, paquete, versión e icono leídos de un APK (en el teléfono o en un archivo local).

Corre en un subproceso (`adb_panel.py --apk-meta / --file-meta`) porque pyaxmlparser puede
tardar o fallar feo con algunos paquetes.
"""
import hashlib
import io
import json
import subprocess
import zipfile

from ..adb import client
from ..adb.client import adb
from .icons import save_icon


def apk_info(apk):
    """(nombre, ruta del icono dentro del APK) con pyaxmlparser, tolerando sus fallos."""
    name = icon = None
    try:
        name = apk.get_app_name()
    except Exception:  # noqa: BLE001 — pyaxmlparser falla con algunos recursos
        pass
    try:
        icon = apk.get_app_icon()
    except Exception:  # noqa: BLE001
        pass
    if name and name.startswith("@"):
        name = None
    if icon and not icon.lower().endswith((".png", ".webp", ".jpg")):
        icon = None
    return name, icon


def apk_meta(serial, pkg):
    """Lee nombre e icono directo del APK en el teléfono (sin bajarlo completo)."""
    client.set_serial(serial)
    _, out = adb("shell", "pm", "path", pkg)
    paths = [l[8:] for l in out.splitlines() if l.startswith("package:")]
    base = next((p for p in paths if p.endswith("/base.apk")), paths[0] if paths else None)
    if not base:
        return {"name": None, "src": "none"}

    def unzip(name):
        return subprocess.run(["adb", "-s", serial, "exec-out", "unzip", "-p", base, name],
                              capture_output=True, timeout=120).stdout

    from pyaxmlparser import APK
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("AndroidManifest.xml", unzip("AndroidManifest.xml"))
        z.writestr("resources.arsc", unzip("resources.arsc"))
    name, icon = apk_info(APK(buf.getvalue(), raw=True))
    if icon:
        try:
            save_icon(pkg, unzip(icon))
        except Exception:  # noqa: BLE001
            pass
    return {"name": name, "src": "apk"}


def file_meta(path):
    """Información de un paquete local (.apk/.xapk/.apks/.apkm)."""
    from pyaxmlparser import APK
    key = "file-" + hashlib.md5(path.encode()).hexdigest()[:12]
    meta = {"pkg": None, "name": None, "version": None, "icon": None}
    if path.lower().endswith(".apk"):
        apk = APK(path)
        meta.update(pkg=apk.package, version=apk.version_name)
        meta["name"], icon = apk_info(apk)
        if icon:
            with zipfile.ZipFile(path) as z:
                meta["icon"] = save_icon(key, z.read(icon))
        return meta
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for info_name in ("manifest.json", "info.json"):
            if info_name in names:
                info = json.loads(z.read(info_name))
                meta["pkg"] = info.get("package_name") or info.get("pname")
                meta["name"] = info.get("name") or info.get("app_name")
                meta["version"] = info.get("version_name") or info.get("release_version")
        icon_file = next((n for n in ("icon.png", "icon.webp") if n in names), None)
        if icon_file:
            meta["icon"] = save_icon(key, z.read(icon_file))
        base = next((n for n in names if n.lower() in ("base.apk", f"{meta['pkg']}.apk")), None)
        if base and (not meta["pkg"] or not meta["name"] or not meta["icon"]):
            apk = APK(z.read(base), raw=True)
            meta["pkg"] = meta["pkg"] or apk.package
            meta["version"] = meta["version"] or apk.version_name
            name, icon = apk_info(apk)
            meta["name"] = meta["name"] or name
            if icon and not meta["icon"]:
                with zipfile.ZipFile(io.BytesIO(z.read(base))) as bz:
                    meta["icon"] = save_icon(key, bz.read(icon))
    return meta
