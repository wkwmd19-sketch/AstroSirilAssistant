from __future__ import annotations
import tkinter as tk
from tkinter import ttk

# Astro Cozy Dark
# Softer navy-charcoal surfaces, warm off-white text and low-saturation accents.
# The app deliberately stays dependency-free (Tk/ttk only), so the "rounded"
# feel is created with borderless cards, generous padding and pill-like controls
# rather than replacing the stable GUI toolkit.
PALETTE = {
    "bg": "#10151D",
    "surface": "#171E28",
    "card": "#1D2632",
    "card_alt": "#273241",
    "border": "#334152",
    "border_soft": "#2A3544",
    "text": "#F1EEE8",
    "muted": "#A7B2BF",
    "accent": "#83B8D8",
    "accent_hover": "#9AC8E2",
    "accent_pressed": "#6AA3C6",
    "success": "#79C6A3",
    "success_hover": "#92D4B6",
    "warning": "#D7B172",
    "danger": "#D9878D",
    "danger_hover": "#E39AA0",
    "input_bg": "#141B24",
    "select_bg": "#365065",
    "scroll": "#4B596A",
}


def apply_screen_aware_geometry(root: tk.Tk, *, max_width=1240, max_height=940):
    sw = max(800, int(root.winfo_screenwidth()))
    sh = max(600, int(root.winfo_screenheight()))

    width = min(max_width, max(900, int(sw * 0.84)))
    height = min(max_height, max(620, int(sh * 0.84)))
    width = min(width, max(760, sw - 70))
    height = min(height, max(540, sh - 110))

    x = max(10, (sw - width) // 2)
    y = max(10, (sh - height) // 3)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(min(840, sw - 40), min(560, sh - 80))


def apply_astro_theme(root: tk.Misc):
    """Apply the dependency-free Astro Cozy Dark theme shared by both GUIs."""
    p = dict(PALETTE)
    setattr(root, "_astro_palette", p)

    try:
        root.configure(background=p["bg"])
    except Exception:
        pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    default_font = ("Segoe UI", 10)
    small_font = ("Segoe UI", 9)
    title_font = ("Segoe UI Semibold", 19)
    section_font = ("Segoe UI Semibold", 10)
    badge_font = ("Segoe UI Semibold", 9)

    style.configure(".", font=default_font)
    style.configure("TFrame", background=p["bg"])
    style.configure("Surface.TFrame", background=p["surface"])
    style.configure("Card.TFrame", background=p["card"])
    style.configure("SoftBar.TFrame", background=p["surface"])

    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Card.TLabel", background=p["card"], foreground=p["text"])
    style.configure(
        "Muted.TLabel", background=p["bg"], foreground=p["muted"], font=small_font
    )
    style.configure(
        "CardMuted.TLabel", background=p["card"], foreground=p["muted"], font=small_font
    )
    style.configure(
        "Title.TLabel", background=p["surface"], foreground=p["text"], font=title_font
    )
    style.configure(
        "Subtitle.TLabel", background=p["surface"], foreground=p["muted"], font=small_font
    )
    style.configure(
        "FlowCurrent.TLabel", background=p["surface"], foreground=p["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "FlowNext.TLabel", background=p["surface"], foreground=p["accent"],
        font=("Segoe UI Semibold", 10),
    )
    style.configure(
        "Badge.TLabel", background=p["accent"], foreground="#13202A",
        font=badge_font, padding=(11, 5),
    )
    style.configure(
        "SuccessBadge.TLabel", background=p["success"], foreground="#13231B",
        font=badge_font, padding=(11, 5),
    )

    # Cards: remove the hard 1px box and rely on spacing + a softer surface.
    for name in ("TLabelframe", "Card.TLabelframe"):
        style.configure(
            name,
            background=p["card"],
            bordercolor=p["border_soft"],
            lightcolor=p["card"],
            darkcolor=p["card"],
            relief="flat",
            borderwidth=0,
            padding=(16, 14),
        )
    style.configure(
        "TLabelframe.Label", background=p["card"], foreground=p["text"],
        font=section_font, padding=(1, 0, 8, 2),
    )
    style.configure(
        "Card.TLabelframe.Label", background=p["card"], foreground=p["accent"],
        font=("Segoe UI Semibold", 10), padding=(1, 0, 8, 2),
    )

    # Default buttons are intentionally borderless and roomy. With the clam
    # engine this reads much more like a soft capsule than a toolbar rectangle.
    style.configure(
        "TButton",
        background=p["card_alt"], foreground=p["text"],
        bordercolor=p["card_alt"], lightcolor=p["card_alt"], darkcolor=p["card_alt"],
        relief="flat", borderwidth=0, padding=(14, 8),
        focusthickness=1, focuscolor=p["accent"],
    )
    style.map(
        "TButton",
        background=[
            ("pressed", p["accent_pressed"]),
            ("active", "#314053"),
            ("disabled", "#202936"),
        ],
        foreground=[("disabled", "#687687"), ("active", p["text"])],
        bordercolor=[("focus", p["accent"])],
    )

    style.configure(
        "Accent.TButton",
        background=p["accent"], foreground="#12202A",
        bordercolor=p["accent"], lightcolor=p["accent"], darkcolor=p["accent"],
        relief="flat", borderwidth=0, padding=(16, 9),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("pressed", p["accent_pressed"]),
            ("active", p["accent_hover"]),
            ("disabled", "#405667"),
        ],
        foreground=[("disabled", "#83909B")],
    )

    style.configure(
        "Success.TButton",
        background=p["success"], foreground="#13231B",
        bordercolor=p["success"], relief="flat", borderwidth=0,
        padding=(16, 9), font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Success.TButton",
        background=[("active", p["success_hover"]), ("pressed", "#64AD8D")],
    )

    style.configure(
        "Danger.TButton",
        background="#4A3038", foreground="#F5DEE0",
        bordercolor="#4A3038", relief="flat", borderwidth=0,
        padding=(14, 8), font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Danger.TButton",
        background=[
            ("active", p["danger"]),
            ("pressed", "#C8757B"),
            ("disabled", "#2A2830"),
        ],
        foreground=[("disabled", "#756D75")],
    )

    style.configure(
        "Quiet.TButton",
        background=p["surface"], foreground=p["muted"],
        bordercolor=p["surface"], relief="flat", borderwidth=0,
        padding=(12, 7),
    )
    style.map(
        "Quiet.TButton",
        background=[("active", p["card_alt"]), ("pressed", p["card"])],
        foreground=[("active", p["text"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=p["input_bg"], foreground=p["text"],
        bordercolor=p["border_soft"], lightcolor=p["input_bg"], darkcolor=p["input_bg"],
        insertcolor=p["text"], relief="flat", borderwidth=0, padding=(10, 8),
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", p["accent"])],
        lightcolor=[("focus", p["accent"])],
        darkcolor=[("focus", p["accent"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground=p["input_bg"], background=p["card_alt"], foreground=p["text"],
        arrowcolor=p["muted"], bordercolor=p["border_soft"],
        lightcolor=p["input_bg"], darkcolor=p["input_bg"],
        relief="flat", borderwidth=0, padding=(9, 7), arrowsize=14,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", p["input_bg"])],
        foreground=[("readonly", p["text"])],
        selectbackground=[("readonly", p["select_bg"])],
        selectforeground=[("readonly", p["text"])],
        bordercolor=[("focus", p["accent"])],
    )

    style.configure(
        "TCheckbutton", background=p["bg"], foreground=p["text"],
        indicatorcolor=p["input_bg"], bordercolor=p["border_soft"], padding=(4, 5),
    )
    style.map(
        "TCheckbutton",
        background=[("active", p["bg"])],
        foreground=[("disabled", "#687687")],
        indicatorcolor=[("selected", p["accent"]), ("pressed", p["accent_pressed"])],
    )
    style.configure(
        "Card.TCheckbutton", background=p["card"], foreground=p["text"],
        indicatorcolor=p["input_bg"], bordercolor=p["border_soft"], padding=(4, 5),
    )
    style.map(
        "Card.TCheckbutton",
        background=[("active", p["card"])],
        indicatorcolor=[("selected", p["accent"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        background=p["accent"], troughcolor=p["input_bg"],
        bordercolor=p["input_bg"], lightcolor=p["accent"], darkcolor=p["accent"],
        relief="flat", borderwidth=0, thickness=8,
    )

    style.configure(
        "Vertical.TScrollbar", background=p["card_alt"], troughcolor=p["bg"],
        bordercolor=p["bg"], arrowcolor=p["muted"], relief="flat", borderwidth=0,
    )
    style.configure(
        "Horizontal.TScrollbar", background=p["card_alt"], troughcolor=p["bg"],
        bordercolor=p["bg"], arrowcolor=p["muted"], relief="flat", borderwidth=0,
    )

    style.configure("TPanedwindow", background=p["border_soft"], sashwidth=5)
    style.configure("TSeparator", background=p["border_soft"])

    try:
        root.option_add("*TCombobox*Listbox.background", p["input_bg"])
        root.option_add("*TCombobox*Listbox.foreground", p["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", p["select_bg"])
        root.option_add("*TCombobox*Listbox.selectForeground", p["text"])
        root.option_add("*Font", default_font)
    except Exception:
        pass

    return p


def style_text_widget(widget: tk.Text, palette=None):
    p = palette or PALETTE
    widget.configure(
        background=p["input_bg"], foreground=p["text"], insertbackground=p["text"],
        selectbackground=p["select_bg"], selectforeground=p["text"],
        relief="flat", borderwidth=0, highlightthickness=1,
        highlightbackground=p["border_soft"], highlightcolor=p["accent"],
        padx=12, pady=10, font=("Cascadia Mono", 9),
    )


def style_canvas(widget: tk.Canvas, palette=None):
    p = palette or PALETTE
    widget.configure(background=p["bg"])
