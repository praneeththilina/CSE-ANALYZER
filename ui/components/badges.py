# ui/components/badges.py  –  Signal Badges and Status Pills
"""
Badges and pills for displaying trade conviction, signal types, and status tags.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from ui.theme.tokens import ThemeManager, FONTS


class Badge(tk.Frame):
    """Rounded-style badge with colored background and contrasting foreground."""

    # Default badge palettes
    COLOR_MAP = {
        "strong_buy": ("#059669", "#ecfdf5", "#059669"),
        "buy":        ("#10b981", "#f0fdf4", "#10b981"),
        "hold":       ("#64748b", "#f1f5f9", "#64748b"),
        "avoid":      ("#ef4444", "#fef2f2", "#ef4444"),
        "warn":       ("#f59e0b", "#fffbeb", "#f59e0b"),
        "info":       ("#3b82f6", "#eff6ff", "#3b82f6"),
        "purple":     ("#8b5cf6", "#f5f3ff", "#8b5cf6"),
    }

    def __init__(
        self,
        parent,
        text: str,
        variant: str = "info",
        fg: Optional[str] = None,
        bg: Optional[str] = None,
        border: Optional[str] = None,
        padx: int = 8,
        pady: int = 2,
        **kwargs
    ):
        v = variant.lower().replace(" ", "_")
        palette = self.COLOR_MAP.get(v, self.COLOR_MAP["info"])
        text_fg = fg or palette[0]
        bg_col = bg or palette[1]
        border_col = border or palette[2]

        super().__init__(
            parent,
            bg=bg_col,
            highlightbackground=border_col,
            highlightthickness=1,
            padx=padx,
            pady=pady,
            **kwargs
        )

        self._lbl = tk.Label(
            self,
            text=text,
            font=FONTS["caption"],
            fg=text_fg,
            bg=bg_col,
        )
        self._lbl.pack()

    def set_text(self, text: str):
        self._lbl.config(text=text)


Pill = Badge
