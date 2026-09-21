# ui_utils.py  –  Facade & Shared UI Utilities for CSE Analyzer
"""
Backward-compatible facade that re-exports Windows 11 Fluent design tokens,
theme manager, components, and thread execution utilities.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

# Re-export design tokens, typography, and styling from new ui.theme layer
from ui.theme.tokens import (
    ThemeManager,
    DARK,
    LIGHT,
    SPACING,
    RADII,
    FONTS,
    get_token,
    get_theme_mode,
    set_theme_mode,
    WIN11_BG,
    WIN11_CARD_BG,
    WIN11_CARD_BORDER,
    WIN11_TEXT_MAIN,
    WIN11_TEXT_MUTED,
    WIN11_TEXT_SUBTLE,
    WIN11_ACCENT,
    WIN11_ACCENT_HOVER,
    WIN11_GREEN,
    WIN11_GREEN_BG,
    WIN11_RED,
    WIN11_RED_BG,
    WIN11_BORDER,
    WIN11_HEADER_BG,
    WIN11_SELECT_BG,
    WIN11_SELECT_FG,
    GRADE_A_PLUS,
    GRADE_A_PLUS_BG,
    GRADE_A,
    GRADE_A_BG,
    GRADE_B,
    GRADE_B_BG,
    GRADE_C,
    GRADE_C_BG,
    FONT_TITLE,
    FONT_SECTION,
    FONT_SUBTITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_CARD_TITLE,
    FONT_CARD_VAL,
    FONT_MONO,
)

from ui.theme.styles import setup_win11_styles, apply_theme
from ui.theme.icons import ICONS, get_icon

# Re-export components from ui.components
from ui.components.card import Card, InfoCard, FormCard
from ui.components.buttons import PrimaryButton, GhostButton, IconButton, SegmentedButton
from ui.components.entries import LabeledEntry, StateEntry
from ui.components.badges import Badge, Pill
from ui.components.stat_tile import StatTile
from ui.components.data_table import DataTable, SortableTreeview
from ui.components.search_box import SearchBox
from ui.components.nav_rail import NavRail
from ui.components.toast import ToastManager, show_toast
from ui.components.tooltip import ToolTip
from ui.charts.canvas_candlestick import CanvasCandlestick


# ══════════════════════════════════════════════════════════════════════════
# Formatters
# ══════════════════════════════════════════════════════════════════════════

def fmt_currency(value: float | int | None, prefix: str = "LKR ") -> str:
    """Format a number as LKR currency string."""
    if value is None:
        return "—"
    try:
        v = float(value)
        if abs(v) >= 1_000_000:
            return f"{prefix}{v / 1_000_000:,.2f}M"
        if abs(v) >= 1_000:
            return f"{prefix}{v:,.2f}"
        return f"{prefix}{v:.2f}"
    except (ValueError, TypeError):
        return str(value)


def fmt_pct(value: float | int | None) -> str:
    """Format a number as a percentage string."""
    if value is None:
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except (ValueError, TypeError):
        return str(value)


def fmt_volume(value: float | int | None) -> str:
    """Format volume with K/M suffixes."""
    if value is None:
        return "—"
    try:
        v = float(value)
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v / 1_000:.1f}K"
        return f"{v:.0f}"
    except (ValueError, TypeError):
        return str(value)


# ══════════════════════════════════════════════════════════════════════════
# Scrollable Frame
# ══════════════════════════════════════════════════════════════════════════

class ScrollableFrame(ttk.Frame):
    """A frame with a vertical scrollbar for content that exceeds the view."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)

        tokens = ThemeManager.tokens()
        self._canvas = tk.Canvas(self, highlightthickness=0, bg=tokens["bg"])
        self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner = ttk.Frame(self._canvas)

        self.inner.bind("<Configure>", lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")

        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        ThemeManager.register_listener(self._on_theme_change)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self._canvas.configure(bg=tokens["bg"])


# ══════════════════════════════════════════════════════════════════════════
# Modern Form Card (Backward Compatibility)
# ══════════════════════════════════════════════════════════════════════════

class ModernFormCard(tk.Frame):
    """Refined form card container with accent top strip and pill header."""

    def __init__(
        self,
        parent,
        title: str = "",
        icon: str = "⚙",
        accent_color: str = "#0067c0",
        bg_color: str = "#ffffff",
        **kw
    ):
        super().__init__(
            parent,
            bg=bg_color,
            highlightbackground="#e2e8f0",
            highlightthickness=1,
            bd=0,
            **kw
        )
        self.accent_color = accent_color
        self.bg_color = bg_color

        # 1. Top Accent Stripe
        self._stripe = tk.Frame(self, bg=accent_color, height=3)
        self._stripe.pack(fill="x", side="top")

        # 2. Header Bar with Pill Badge
        header_bar = tk.Frame(self, bg=bg_color, padx=14, pady=8)
        header_bar.pack(fill="x", side="top")

        badge = tk.Frame(header_bar, bg=accent_color, padx=8, pady=3)
        badge.pack(side="left")
        tk.Label(
            badge,
            text=f"{icon} {title.upper()}",
            font=("Segoe UI Semibold", 9),
            fg="#ffffff",
            bg=accent_color,
        ).pack()

        # 3. Content Body
        self.body = tk.Frame(self, bg=bg_color, padx=14, pady=8)
        self.body.pack(fill="both", expand=True, side="top")


# ══════════════════════════════════════════════════════════════════════════
# Status Bar
# ══════════════════════════════════════════════════════════════════════════

class StatusBar(tk.Frame):
    """Persistent status bar with Windows 11 light/dark styling."""

    def __init__(self, parent, **kw):
        tokens = ThemeManager.tokens()
        super().__init__(
            parent,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=4,
            **kw
        )

        self._msg_var = tk.StringVar(value="Ready")

        # Dot indicator
        self._dot = tk.Label(self, text="●", font=FONT_CAPTION, fg=tokens["gain"], bg=tokens["surface"])
        self._dot.pack(side="left", padx=(0, 4))

        self._lbl = tk.Label(
            self,
            textvariable=self._msg_var,
            font=FONT_CAPTION,
            fg=tokens["text_dim"],
            bg=tokens["surface"],
        )
        self._lbl.pack(side="left")

        self._progress = ttk.Progressbar(self, mode="indeterminate", length=140)
        self._progress.pack(side="right", padx=6, pady=1)

        # Connection / engine state indicator
        self._conn_lbl = tk.Label(
            self,
            text="CSE DataEngine: Connected (262 Equities)",
            font=FONT_CAPTION,
            fg=tokens["text_subtle"],
            bg=tokens["surface"]
        )
        self._conn_lbl.pack(side="right", padx=(0, 16))

        ThemeManager.register_listener(self._on_theme_change)

    def set_message(self, text: str):
        self._msg_var.set(text)

    def start_progress(self):
        self._progress.start(10)

    def stop_progress(self):
        self._progress.stop()

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"])
        self._dot.configure(bg=tokens["surface"])
        self._lbl.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        self._conn_lbl.configure(bg=tokens["surface"], fg=tokens["text_subtle"])


# ══════════════════════════════════════════════════════════════════════════
# Threaded Task Runner
# ══════════════════════════════════════════════════════════════════════════

class ThreadedTask:
    """Run a callable in a background thread and deliver the result to tkinter."""

    def __init__(
        self,
        root: tk.Tk | tk.Toplevel,
        target: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
        on_done: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ):
        self._root = root
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self._on_done = on_done
        self._on_error = on_error

    def start(self):
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _worker(self):
        try:
            result = self._target(*self._args, **self._kwargs)
            if self._on_done:
                try:
                    self._root.after(0, self._on_done, result)
                except Exception:
                    pass
        except Exception as exc:
            if self._on_error:
                try:
                    self._root.after(0, self._on_error, exc)
                except Exception:
                    pass
