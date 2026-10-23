"""Llamadas a `adb`. Todas usan el dispositivo activo (`set_serial`) salvo que se pase otro."""
import subprocess

SERIAL = None  # dispositivo activo


def set_serial(serial):
    global SERIAL
    SERIAL = serial


def adb(*args, timeout=30, serial=None):
    """Ejecuta adb y regresa (ok, salida)."""
    serial = serial if serial is not None else SERIAL
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, "adb no está instalado"
    except subprocess.TimeoutExpired:
        return False, "adb tardó demasiado"
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def list_devices():
    """[(serial, estado)] de `adb devices`."""
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [tuple(l.split()[:2]) for l in out.splitlines()[1:] if len(l.split()) >= 2]


def is_wifi(serial):
    return ":" in serial
