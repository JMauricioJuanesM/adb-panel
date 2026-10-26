"""Operaciones sobre el teléfono: apps, DNS privado, bloqueo de apps de Xiaomi y ADB por WiFi."""
import re
import time

from ..paths import WIFI_PORT
from .client import adb


def pm_list(*flags):
    ok, out = adb("shell", "pm", "list", "packages", *flags)
    return {l[8:].strip() for l in out.splitlines() if l.startswith("package:")} if ok else set()


def list_packages(include_system):
    """{paquete: (activa, es_del_sistema)}"""
    user = pm_list("-3")
    pkgs = pm_list() if include_system else user
    disabled = pm_list("-d")
    return {p: (p not in disabled, p not in user) for p in pkgs}


def disable_app(pkg):
    return adb("shell", "pm", "disable-user", "--user", "0", pkg)


def enable_app(pkg):
    return adb("shell", "pm", "enable", pkg)


def uninstall_app(pkg, system):
    if system:  # se quita solo para el usuario; se puede recuperar con `cmd package install-existing`
        return adb("shell", "pm", "uninstall", "-k", "--user", "0", pkg)
    return adb("uninstall", pkg, timeout=120)


def get_dns():
    _, mode = adb("shell", "settings", "get", "global", "private_dns_mode")
    _, host = adb("shell", "settings", "get", "global", "private_dns_specifier")
    return mode.strip(), host.strip()


def dns_on(hostname):
    adb("shell", "settings", "put", "global", "private_dns_specifier", hostname)
    return adb("shell", "settings", "put", "global", "private_dns_mode", "hostname")


def dns_off():
    return adb("shell", "settings", "put", "global", "private_dns_mode", "off")


# Bloqueo de aplicaciones de Xiaomi (vive dentro de la app Seguridad).
# Bloqueo de aplicaciones de Xiaomi (vive dentro de la app Seguridad).
def get_applock():
    ok, out = adb("shell", "settings", "get", "secure", "access_control_lock_enabled")
    return out.strip() if ok else "?"


def set_applock(on):
    return adb("shell", "settings", "put", "secure", "access_control_lock_enabled", "1" if on else "0")


POMODORO_PKG = "com.mauriciojuanes.pomodoro"


def grant_phone_app():
    """Deja que la app Pomodoro del teléfono vuelva a encender el DNS y el bloqueo de Xiaomi por su cuenta."""
    ok, out = adb("shell", "pm", "list", "packages", POMODORO_PKG)
    if ok and POMODORO_PKG in out:
        adb("shell", "pm", "grant", POMODORO_PKG, "android.permission.WRITE_SECURE_SETTINGS")


def phone_model():
    _, name = adb("shell", "getprop", "ro.product.marketname")
    if not name.strip():
        _, name = adb("shell", "getprop", "ro.product.model")
    return name.strip()


def phone_ip():
    ok, out = adb("shell", "ip", "-f", "inet", "addr", "show", "wlan0")
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out) if ok else None
    return m.group(1) if m else None


def enable_wifi_adb(usb_serial):
    """Pone el teléfono a escuchar ADB por WiFi y se conecta. Regresa (ok, mensaje, ip)."""
    ip = phone_ip()
    if not ip or ip.startswith("127."):
        return False, "el teléfono no está conectado a WiFi", None
    _, port = adb("shell", "getprop", "service.adb.tcp.port", serial=usb_serial)
    if port.strip() != str(WIFI_PORT):
        adb("tcpip", str(WIFI_PORT), serial=usb_serial)
        time.sleep(3)
        adb("wait-for-device", serial=usb_serial, timeout=15)
    ok, out = wifi_connect(ip)
    return ok, out, ip


def wifi_connect(ip):
    ok, out = adb("connect", f"{ip}:{WIFI_PORT}", timeout=6, serial="")
    return ok and "connected" in out and "cannot" not in out, out
