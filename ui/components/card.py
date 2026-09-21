# ui/components/card.py  –  Windows 11 Fluent Cards
"""
Surface card components with subtle borders, rounded appearance,
theme reactivity, and typography hierarchy.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.theme.tokens import (
    ThemeManager,
    FONTS,
    FONT_CARD_TITLE,
    FONT_CARD_VAL,
    FONT_SUBTITLE,
    FONT_SECTION,
)


class Card(tk.Frame):
    """Modern Windows 11 elevated card with subtle border and theme reactivity."""

    def __init__(
        self,
        parent,
        title: Optional[str] = None,
        icon: Optional[str] = None,
        padx: int = 16,
        pady: int = 14,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        self._custom_bg = kwargs.pop("bg", tokens["surface"])
        self._custom_border = kwargs.pop("highlightbackground", tokens["border"])

        super().__init__(
            parent,
            bg=self._custom_bg,
            highlightbackground=self._custom_border,
            highlightcolor=self._custom_border,
            highlightthickness=1,
            padx=padx,
            pady=pady,
            **kwargs
        )

        self._title_text = title
        self._icon_text = icon
        self._title_label = None
        self._icon_label = None

        if title or icon:
            self._header_frame = tk.Frame(self, bg=self._custom_bg)
            self._header_frame.pack(fill="x", pady=(0, 10))

            if icon:
                self._icon_label = tk.Label(
                    self._header_frame,
                    text=f"{icon} ",
                    font=FONTS["subtitle"],
                    fg=tokens["accent"],
                    bg=self._custom_bg
                )
                self._icon_label.pack(side="left")

            if title:
                self._title_label = tk.Label(
                    self._header_frame,
                    text=title,
                    font=FONT_SECTION,
                    fg=tokens["text"],
                    bg=self._custom_bg
                )
                self._title_label.pack(side="left")

        ThemeManager.register_listener(self._on_theme_change)

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"], highlightcolor=tokens["border"])
        if hasattr(self, "_header_frame"):
            self._header_frame.configure(bg=tokens["surface"])
        if self._title_label:
            self._title_label.configure(bg=tokens["surface"], fg=tokens["text"])
        if self._icon_label:
            self._icon_label.configure(bg=tokens["surface"], fg=tokens["accent"])


class InfoCard(tk.Frame):
    """Metric tile card displaying title, big numerical value, accent stripe, and optional subtitle."""

    def __init__(
        self,
        parent,
        title: str,
        value: str = "—",
        subtitle: str = "",
        accent_color: Optional[str] = None,
        value_color: Optional[str] = None,
        icon: Optional[str] = None,
        width: int = 160,
        height: int = 86,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        self._accent = accent_color or value_color or tokens["accent"]
        self._custom_accent = accent_color is not None
        self._title_text = title.upper()
        self._value_text = value
        self._icon_text = icon

        super().__init__(
            parent,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["border"],
            highlightthickness=1,
            width=width,
            height=height,
            bd=0,
            **kwargs
        )
        self.pack_propagate(False)

        # 1. Top Accent Stripe (3px vibrant line)
        self._stripe = tk.Frame(self, bg=self._accent, height=3)
        self._stripe.pack(fill="x", side="top")

        # 2. Inner padding container
        inner = tk.Frame(self, bg=tokens["surface"], padx=12, pady=8)
        inner.pack(fill="both", expand=True)

        # Card Title
        header_text = f"{icon}  {self._title_text}" if icon else self._title_text
        self._lbl_title = tk.Label(
            inner,
            text=header_text,
            font=FONT_CARD_TITLE,
            fg=tokens["text_dim"],
            bg=tokens["surface"],
            anchor="w",
        )
        self._lbl_title.pack(fill="x")

        # Metric Value
        self._lbl_val = tk.Label(
            inner,
            text=value,
            font=FONT_CARD_VAL,
            fg=self._accent,
            bg=tokens["surface"],
            anchor="w",
        )
        self._lbl_val.pack(fill="x", pady=(2, 0))

        # Subtitle / Delta indicator
        self._lbl_sub = tk.Label(
            inner,
            text=subtitle,
            font=FONT_SUBTITLE,
            fg=tokens["text_subtle"],
            bg=tokens["surface"],
            anchor="w",
        )
        if subtitle:
            self._lbl_sub.pack(fill="x")

        ThemeManager.register_listener(self._on_theme_change)

    def set(self, value: str, title: Optional[str] = None, color: Optional[str] = None, subtitle: Optional[str] = None):
        """Update value, title, color, and optional subtitle."""
        tokens = ThemeManager.tokens()
        if color:
            self._accent = color
            self._stripe.configure(bg=color)
            self._lbl_val.configure(fg=color)
        self._lbl_val.config(text=str(value))

        if title is not None:
            self._title_text = title.upper()
            header_text = f"{self._icon_text}  {self._title_text}" if self._icon_text else self._title_text
            self._lbl_title.config(text=header_text)

        if subtitle is not None:
            self._lbl_sub.config(text=subtitle)
            if not self._lbl_sub.winfo_ismapped():
                self._lbl_sub.pack(fill="x")

    def set_value(self, value: str, title: Optional[str] = None, color: Optional[str] = None):
        """Alias for .set()."""
        self.set(value, title=title, color=color)

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"], highlightcolor=tokens["border"])
        self._lbl_title.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        if not self._custom_accent:
            self._accent = tokens["accent"]
            self._stripe.configure(bg=tokens["accent"])
            self._lbl_val.configure(bg=tokens["surface"], fg=tokens["text"])
        else:
            self._lbl_val.configure(bg=tokens["surface"])
        self._lbl_sub.configure(bg=tokens["surface"], fg=tokens["text_subtle"])


class FormCard(tk.Frame):
    """Vibrant section container for structured form inputs styled for Windows 11."""

    def __init__(
        self,
        parent,
        title: str = "",
        accent_color: str = "#0067c0",
        bg_color: Optional[str] = None,
        border_color: Optional[str] = None,
        icon: str = "⚙",
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        bg = bg_color or tokens["surface"]
        border = border_color or tokens["border"]

        super().__init__(
            parent,
            bg=bg,
            highlightbackground=border,
            highlightthickness=1,
            bd=0,
            **kwargs
        )
        self.accent_color = accent_color
        self.bg_color = bg

        # 1. Top Accent Stripe
        self._stripe = tk.Frame(self, bg=accent_color, height=3)
        self._stripe.pack(fill="x", side="top")

        # 2. Header Bar with Pill Badge
        if title or icon:
            header_bar = tk.Frame(self, bg=bg, padx=14, pady=8)
            header_bar.pack(fill="x", side="top")

            badge = tk.Frame(header_bar, bg=accent_color, padx=8, pady=3)
            badge.pack(side="left")
            self._badge_lbl = tk.Label(
                badge,
                text=f"{icon}  {title.upper()}" if icon else title.upper(),
                font=FONT_CARD_TITLE,
                fg="#ffffff",
                bg=accent_color,
            )
            self._badge_lbl.pack()

        # 3. Content Body for form controls
        self.body = tk.Frame(self, bg=bg, padx=14, pady=8)
        self.body.pack(fill="both", expand=True, side="top")

        ThemeManager.register_listener(self._on_theme_change)

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"])
        if hasattr(self, "body"):
            self.body.configure(bg=tokens["surface"])

