"""Utilidades pequeñas: notificaciones de escritorio y formatos."""
import re
import shutil
import subprocess


def notify(title, body=""):
    if shutil.which("notify-send"):
        subprocess.Popen(["notify-send", "-a", "Panel ADB", title, body])


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_minutes(m):
    if m is None:
        return "permanente"
    return f"{m // 60} h" if m >= 60 and m % 60 == 0 else f"{m} min"


def short_app_name(name):
    """"Duolingo: Aprende Idiomas" → "Duolingo"."""
    return re.split(r":\s| [-–|] ", name, maxsplit=1)[0].strip() or name
