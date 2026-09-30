from __future__ import annotations
import tkinter as tk
from tkinter import ttk

PALETTE = {
    "bg": "#0B1220",
    "surface": "#111827",
    "card": "#172033",
    "card_alt": "#1E293B",
    "border": "#2A3A52",
    "text": "#E5ECF6",
    "muted": "#91A4BD",
    "accent": "#45A6FF",
    "accent_hover": "#67B7FF",
    "accent_pressed": "#278BDF",
    "success": "#2DCB85",
    "warning": "#F3B34C",
    "danger": "#EF6A78",
    "input_bg": "#0F1A2B",
    "select_bg": "#244463",
    "scroll": "#425772",
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
    """Dependency-free modern graphite theme shared by both GUIs."""
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
    title_font = ("Segoe UI Semibold", 18)
    section_font = ("Segoe UI Semibold", 10)
    badge_font = ("Segoe UI Semibold", 9)

    style.configure(".", font=default_font)
    style.configure("TFrame", background=p["bg"])
    style.configure("Surface.TFrame", background=p["surface"])
    style.configure("Card.TFrame", background=p["card"])

    style.configure(
        "TLabel",
        background=p["bg"],
        foreground=p["text"],
    )
    style.configure(
        "Card.TLabel",
        background=p["card"],
        foreground=p["text"],
    )
    style.configure(
        "Muted.TLabel",
        background=p["bg"],
        foreground=p["muted"],
        font=small_font,
    )
    style.configure(
        "CardMuted.TLabel",
        background=p["card"],
        foreground=p["muted"],
        font=small_font,
    )
    style.configure(
        "Title.TLabel",
        background=p["surface"],
        foreground=p["text"],
        font=title_font,
    )
    style.configure(
        "Subtitle.TLabel",
        background=p["surface"],
        foreground=p["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "FlowCurrent.TLabel",
        background=p["surface"],
        foreground=p["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "FlowNext.TLabel",
        background=p["surface"],
        foreground=p["accent"],
        font=("Segoe UI Semibold", 10),
    )
    style.configure(
        "Badge.TLabel",
        background=p["accent"],
        foreground="#06111E",
        font=badge_font,
        padding=(9, 4),
    )
    style.configure(
        "SuccessBadge.TLabel",
        background=p["success"],
        foreground="#06150F",
        font=badge_font,
        padding=(9, 4),
    )

    style.configure(
        "TLabelframe",
        background=p["card"],
        bordercolor=p["border"],
        relief="solid",
        borderwidth=1,
        padding=10,
    )
    style.configure(
        "TLabelframe.Label",
        background=p["card"],
        foreground=p["text"],
        font=section_font,
    )
    style.configure(
        "Card.TLabelframe",
        background=p["card"],
        bordercolor=p["border"],
        relief="solid",
        borderwidth=1,
        padding=10,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=p["card"],
        foreground=p["accent"],
        font=("Segoe UI Semibold", 10),
    )

    style.configure(
        "TButton",
        background=p["card_alt"],
        foreground=p["text"],
        bordercolor=p["border"],
        lightcolor=p["card_alt"],
        darkcolor=p["card_alt"],
        relief="flat",
        padding=(10, 6),
        focusthickness=1,
        focuscolor=p["accent"],
    )
    style.map(
        "TButton",
        background=[
            ("pressed", p["accent_pressed"]),
            ("active", "#263A53"),
            ("disabled", "#182233"),
        ],
        foreground=[
            ("disabled", "#60738D"),
            ("active", p["text"]),
        ],
        bordercolor=[("active", "#416181"), ("focus", p["accent"])],
    )

    style.configure(
        "Accent.TButton",
        background=p["accent"],
        foreground="#05111D",
        bordercolor=p["accent"],
        lightcolor=p["accent"],
        darkcolor=p["accent"],
        relief="flat",
        padding=(12, 7),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("pressed", p["accent_pressed"]),
            ("active", p["accent_hover"]),
            ("disabled", "#24445F"),
        ],
        foreground=[("disabled", "#718397")],
    )

    style.configure(
        "Success.TButton",
        background=p["success"],
        foreground="#06150F",
        bordercolor=p["success"],
        relief="flat",
        padding=(12, 7),
        font=("Segoe UI Semibold", 10),
    )
    style.map(
        "Success.TButton",
        background=[("active", "#4AD99A"), ("pressed", "#23AA6F")],
    )

    style.configure(
        "TEntry",
        fieldbackground=p["input_bg"],
        foreground=p["text"],
        bordercolor=p["border"],
        lightcolor=p["border"],
        darkcolor=p["border"],
        insertcolor=p["text"],
        padding=6,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", p["accent"])],
        lightcolor=[("focus", p["accent"])],
        darkcolor=[("focus", p["accent"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground=p["input_bg"],
        background=p["card_alt"],
        foreground=p["text"],
        arrowcolor=p["muted"],
        bordercolor=p["border"],
        lightcolor=p["border"],
        darkcolor=p["border"],
        padding=5,
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
        "TCheckbutton",
        background=p["bg"],
        foreground=p["text"],
        indicatorcolor=p["input_bg"],
        bordercolor=p["border"],
        padding=(2, 3),
    )
    style.map(
        "TCheckbutton",
        background=[("active", p["bg"])],
        foreground=[("disabled", "#60738D")],
        indicatorcolor=[
            ("selected", p["accent"]),
            ("pressed", p["accent_pressed"]),
        ],
    )

    style.configure(
        "Card.TCheckbutton",
        background=p["card"],
        foreground=p["text"],
        indicatorcolor=p["input_bg"],
        bordercolor=p["border"],
    )
    style.map(
        "Card.TCheckbutton",
        background=[("active", p["card"])],
        indicatorcolor=[("selected", p["accent"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        background=p["accent"],
        troughcolor=p["input_bg"],
        bordercolor=p["border"],
        lightcolor=p["accent"],
        darkcolor=p["accent"],
    )

    style.configure(
        "Vertical.TScrollbar",
        background=p["card_alt"],
        troughcolor=p["bg"],
        bordercolor=p["bg"],
        arrowcolor=p["muted"],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=p["card_alt"],
        troughcolor=p["bg"],
        bordercolor=p["bg"],
        arrowcolor=p["muted"],
    )

    style.configure("TPanedwindow", background=p["border"])
    style.configure("TSeparator", background=p["border"])

    # Tk option database helps native popups/listboxes follow the palette.
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
        background=p["input_bg"],
        foreground=p["text"],
        insertbackground=p["text"],
        selectbackground=p["select_bg"],
        selectforeground=p["text"],
        relief="flat",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=p["border"],
        highlightcolor=p["accent"],
        padx=10,
        pady=8,
        font=("Cascadia Mono", 9),
    )

def style_canvas(widget: tk.Canvas, palette=None):
    p = palette or PALETTE
    widget.configure(background=p["bg"])
