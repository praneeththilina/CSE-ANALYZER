# ui/theme/styles.py  –  ttk Style Configurations & Windows 11 Polish
"""
Configures Sun Valley (sv_ttk) theme, native ttk style elements, and
pywinstyles title-bar / header matching for both Light and Dark modes.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import sv_ttk

from ui.theme.tokens import (
    ThemeManager,
    DARK,
    LIGHT,
    FONTS,
    FONT_TITLE,
    FONT_SECTION,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SUBTITLE,
    FONT_CARD_TITLE,
    FONT_CARD_VAL,
)


def apply_theme(root: tk.Tk, mode: str | None = None) -> str:
    """Apply either 'light' or 'dark' Windows 11 Fluent theme across ttk and title bar."""
    if mode is not None:
        ThemeManager.set_mode(mode)
    current_mode = ThemeManager.get_mode()
    tokens = ThemeManager.tokens()

    # 1. Update Sun-Valley TTK theme
    try:
        sv_ttk.set_theme(current_mode)
    except Exception:
        pass

    # 2. Configure root window background
    root.configure(bg=tokens["bg"])

    # 3. Configure ttk Styles
    style = ttk.Style(root)

    # General Frames
    style.configure("TFrame", background=tokens["bg"])
    style.configure(
        "Card.TFrame",
        background=tokens["surface"],
        relief="solid",
        borderwidth=1,
        bordercolor=tokens["border"]
    )
    style.configure(
        "Elevated.TFrame",
        background=tokens["surface_hi"],
        relief="solid",
        borderwidth=1,
        bordercolor=tokens["border"]
    )

    # Label Frames
    style.configure("TLabelframe", background=tokens["bg"], bordercolor=tokens["border"])
    style.configure("TLabelframe.Label", background=tokens["bg"], foreground=tokens["text"], font=FONT_SECTION)

    # Labels
    style.configure("TLabel", background=tokens["bg"], foreground=tokens["text"], font=FONT_BODY)
    style.configure("Title.TLabel", font=FONT_TITLE, foreground=tokens["text"], background=tokens["bg"])
    style.configure("Subtitle.TLabel", font=FONT_SUBTITLE, foreground=tokens["text_dim"], background=tokens["bg"])
    style.configure("CardTitle.TLabel", background=tokens["surface"], foreground=tokens["text_dim"], font=FONT_CARD_TITLE)
    style.configure("CardVal.TLabel", background=tokens["surface"], foreground=tokens["text"], font=FONT_CARD_VAL)

    # Metric Delta Labels
    style.configure("Gain.TLabel", foreground=tokens["gain"], font=FONT_BODY_BOLD)
    style.configure("Loss.TLabel", foreground=tokens["loss"], font=FONT_BODY_BOLD)
    style.configure("Warn.TLabel", foreground=tokens["warn"], font=FONT_BODY_BOLD)

    # Treeview Tables
    style.configure(
        "Treeview",
        background=tokens["surface"],
        fieldbackground=tokens["surface"],
        foreground=tokens["text"],
        rowheight=30,
        font=FONT_BODY,
        borderwidth=1,
        relief="solid",
        bordercolor=tokens["border"]
    )
    style.map(
        "Treeview",
        background=[("selected", tokens["select_bg"])],
        foreground=[("selected", tokens["select_fg"])],
    )
    style.configure(
        "Treeview.Heading",
        background=tokens["header_bg"],
        foreground=tokens["text"],
        font=FONT_BODY_BOLD,
        relief="flat",
        padding=(8, 6)
    )
    style.map(
        "Treeview.Heading",
        background=[("active", tokens["surface_hi"])],
        foreground=[("active", tokens["accent"])]
    )

    # Buttons
    style.configure("TButton", font=FONT_BODY_BOLD, padding=(12, 6))
    style.configure("Accent.TButton", font=FONT_BODY_BOLD, padding=(12, 6))

    # Notebook Tabs
    style.configure("TNotebook", background=tokens["bg"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=tokens["bg"],
        foreground=tokens["text_dim"],
        padding=(14, 8),
        font=FONT_BODY_BOLD
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", tokens["surface"]), ("active", tokens["surface_hi"])],
        foreground=[("selected", tokens["accent"]), ("active", tokens["text"])],
    )

    # Progressbar
    style.configure("Horizontal.TProgressbar", background=tokens["accent"], troughcolor=tokens["surface_hi"])

    # 4. Update Windows 11 Title-bar & Header styling via pywinstyles
    try:
        import pywinstyles
        pywinstyles.apply_style(root, "mica" if current_mode == "dark" else "mica")
        pywinstyles.change_header_color(root, tokens["bg"])
    except Exception:
        pass

    return current_mode


def setup_win11_styles(root: tk.Tk):
    """Initial theme setup wrapper."""
    return apply_theme(root, ThemeManager.get_mode())
