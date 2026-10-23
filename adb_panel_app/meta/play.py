"""Nombre e icono de una app desde su página de Google Play."""
import html
import re
import urllib.error
import urllib.request

from .icons import save_icon


def fetch_play_meta(pkg):
    """Nombre e icono desde Google Play. None si la app no está en Play."""
    url = f"https://play.google.com/store/apps/details?id={pkg}&hl=es_MX"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        page = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    title = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    image = re.search(r'<meta property="og:image" content="([^"]*)"', page)
    name = html.unescape(title.group(1)).rsplit(" - Apps en Google Play", 1)[0] if title else None
    if image:
        icon_url = re.sub(r"=[^=/]*$", "", html.unescape(image.group(1))) + "=s96"
        try:
            data = urllib.request.urlopen(urllib.request.Request(
                icon_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read()
            save_icon(pkg, data, rounded=True)
        except (OSError, ValueError):
            pass
    return {"name": name, "src": "play"}
