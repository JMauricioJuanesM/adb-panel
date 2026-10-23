"""Iconos de apps: se guardan en la caché ya recortados y del tamaño de la lista."""
import io
import os

from ..paths import ICON_DIR, ICON_SIZE


def save_icon(key, data, rounded=False):
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    if rounded:  # los iconos de Play vienen cuadrados
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), img.width // 4.5, fill=255)
        img.putalpha(Image.composite(img.getchannel("A"), mask, mask))
    img.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    os.makedirs(ICON_DIR, exist_ok=True)
    path = os.path.join(ICON_DIR, key + ".png")
    img.save(path)
    return path
