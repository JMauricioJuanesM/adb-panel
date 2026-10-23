"""Estilos ttk y el icono de relleno para las listas."""
from tkinter import ttk

from ..paths import ICON_SIZE
from ..theme import ACCENT, BG, BORDER, CARD, GREEN, MUTED, RED, TEXT


def apply_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, font=("Sans", 10))
    s.configure("TFrame", background=BG)
    s.configure("TLabel", background=BG)
    s.configure("TCheckbutton", background=CARD)
    s.configure("TRadiobutton", background=CARD)
    s.map("TCheckbutton", background=[("active", CARD)])
    s.map("TRadiobutton", background=[("active", CARD)])
    s.configure("TButton", padding=(12, 6), relief="flat", background="#e8eaf0", bordercolor=BORDER)
    s.map("TButton", background=[("active", "#dde1ea"), ("disabled", "#f0f1f4")])
    for name, color, hover in (("Accent", ACCENT, "#2c56d6"), ("Danger", RED, "#a51f1f"),
                               ("Good", GREEN, "#156b2e")):
        s.configure(f"{name}.TButton", background=color, foreground="white", bordercolor=color)
        s.map(f"{name}.TButton", background=[("active", hover), ("disabled", "#c9ccd3")],
              foreground=[("disabled", "#f4f4f4")])
    s.configure("Big.Accent.TButton", font=("Sans", 12, "bold"), padding=(18, 12))
    s.configure("Treeview", rowheight=ICON_SIZE + 10, background=CARD, fieldbackground=CARD,
                bordercolor=BORDER, font=("Sans", 10))
    s.configure("Treeview.Heading", background="#eef0f4", font=("Sans", 9, "bold"), relief="flat",
                foreground=MUTED, padding=(6, 6))
    s.map("Treeview", background=[("selected", "#dce6ff")], foreground=[("selected", TEXT)])
    s.configure("TEntry", padding=6)


def placeholder_icon():
    from PIL import Image, ImageDraw, ImageTk
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((2, 2, ICON_SIZE - 3, ICON_SIZE - 3), 6, fill="#c9ccd1")
    return ImageTk.PhotoImage(img)
