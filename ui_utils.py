# ui_utils.py  –  Shared UI helpers & Windows 11 Light Theme for CSE Analyzer
"""
Reusable widgets, typography, formatters, and threading helpers styled
for a native Windows 11 Fluent Light appearance.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


# ══════════════════════════════════════════════════════════════════════════
# Windows 11 Design System Tokens
# ══════════════════════════════════════════════════════════════════════════

WIN11_BG = "#f3f3f3"            # App canvas background
WIN11_CARD_BG = "#ffffff"       # Elevated card surface
WIN11_CARD_BORDER = "#e2e8f0"   # Card stroke / outline
WIN11_TEXT_MAIN = "#0f172a"     # Primary text (slate 900)
WIN11_TEXT_MUTED = "#64748b"    # Secondary text (slate 500)
WIN11_TEXT_SUBTLE = "#94a3b8"   # Tertiary text (slate 400)
WIN11_ACCENT = "#0067c0"        # Windows 11 Fluent blue
WIN11_ACCENT_HOVER = "#1879cd"
WIN11_GREEN = "#0e700e"         # Accessible success green
WIN11_GREEN_BG = "#f0fdf4"      # Soft green tint
WIN11_RED = "#c42b1c"           # Accessible error red
WIN11_RED_BG = "#fef2f2"        # Soft red tint
WIN11_BORDER = "#cbd5e1"        # Divider / border
WIN11_HEADER_BG = "#f8fafc"     # Table header background
WIN11_SELECT_BG = "#e0f2fe"     # Selection blue
WIN11_SELECT_FG = "#0369a1"

# Signal Confluence Grades
GRADE_A_PLUS = "#059669"        # Emerald - Strong High Conviction
GRADE_A_PLUS_BG = "#ecfdf5"     # Soft Emerald tint
GRADE_A = "#0284c7"             # Sky Blue - Solid Setup
GRADE_A_BG = "#f0f9ff"          # Soft Sky tint
GRADE_B = "#d97706"             # Amber - Moderate Setup
GRADE_B_BG = "#fffbeb"          # Soft Amber tint
GRADE_C = "#e11d48"             # Rose - Low Confluence / Warning
GRADE_C_BG = "#fff1f2"          # Soft Rose tint

# Typography
FONT_FAMILY = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"

FONT_TITLE = (FONT_SEMIBOLD, 15)
FONT_SECTION = (FONT_SEMIBOLD, 12)
FONT_SUBTITLE = (FONT_FAMILY, 9)
FONT_BODY = (FONT_FAMILY, 9)
FONT_BODY_BOLD = (FONT_SEMIBOLD, 9)
FONT_CAPTION = (FONT_FAMILY, 8)
FONT_CARD_TITLE = (FONT_SEMIBOLD, 9)
FONT_CARD_VAL = (FONT_SEMIBOLD, 17)
FONT_MONO = ("Consolas", 9)


# ══════════════════════════════════════════════════════════════════════════
# Theme Configuration
# ══════════════════════════════════════════════════════════════════════════

def setup_win11_styles(root: tk.Tk):
    """Apply native Windows 11 light styling to ttk widgets."""
    root.configure(bg=WIN11_BG)
    style = ttk.Style(root)

    # General Frames
    style.configure("TFrame", background=WIN11_BG)
    style.configure("Card.TFrame", background=WIN11_CARD_BG, relief="solid", borderwidth=1, bordercolor=WIN11_CARD_BORDER)

    # Label Frames
    style.configure("TLabelframe", background=WIN11_BG, bordercolor=WIN11_CARD_BORDER)
    style.configure("TLabelframe.Label", background=WIN11_BG, foreground=WIN11_TEXT_MAIN, font=FONT_SECTION)

    # Labels
    style.configure("TLabel", background=WIN11_BG, foreground=WIN11_TEXT_MAIN, font=FONT_BODY)
    style.configure("Title.TLabel", font=FONT_TITLE, foreground=WIN11_TEXT_MAIN)
    style.configure("Subtitle.TLabel", font=FONT_SUBTITLE, foreground=WIN11_TEXT_MUTED)
    style.configure("CardTitle.TLabel", background=WIN11_CARD_BG, foreground=WIN11_TEXT_MUTED, font=FONT_CARD_TITLE)
    style.configure("CardVal.TLabel", background=WIN11_CARD_BG, foreground=WIN11_TEXT_MAIN, font=FONT_CARD_VAL)

    # Treeview (Modern Windows 11 table)
    style.configure(
        "Treeview",
        background=WIN11_CARD_BG,
        fieldbackground=WIN11_CARD_BG,
        foreground=WIN11_TEXT_MAIN,
        rowheight=28,
        font=FONT_BODY,
        borderwidth=1,
        relief="solid",
        bordercolor=WIN11_CARD_BORDER,
    )
    style.map(
        "Treeview",
        background=[("selected", WIN11_SELECT_BG)],
        foreground=[("selected", WIN11_SELECT_FG)],
    )

    style.configure(
        "Treeview.Heading",
        background=WIN11_HEADER_BG,
        foreground=WIN11_TEXT_MUTED,
        font=FONT_BODY_BOLD,
        relief="flat",
        padding=(6, 6),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", "#f1f5f9")],
        foreground=[("active", WIN11_TEXT_MAIN)],
    )

    # Notebook Tabs
    style.configure(
        "TNotebook",
        background=WIN11_BG,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        font=FONT_BODY_BOLD,
        padding=(14, 8),
    )


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

        self._canvas = tk.Canvas(self, highlightthickness=0, bg=WIN11_BG)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner = ttk.Frame(self._canvas)

        self.inner.bind("<Configure>", lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")

        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ══════════════════════════════════════════════════════════════════════════
# Info Card Widget (Windows 11 Light Surface Card with Color Stripe)
# ══════════════════════════════════════════════════════════════════════════

class InfoCard(tk.Frame):
    """
    A native Windows 11 KPI card with a vibrant top accent stripe,
    crisp white background, and bold Segoe UI metric typography.
    """

    def __init__(self, parent, title: str = "", value: str = "—", accent_color: str = "#0284c7", icon: str = "", **kw):
        super().__init__(parent, bg=WIN11_CARD_BG, highlightbackground=WIN11_CARD_BORDER,
                         highlightthickness=1, bd=0, **kw)

        self._accent = accent_color
        display_title = f"{icon + ' ' if icon else ''}{title.upper()}"
        self._title_var = tk.StringVar(value=display_title)
        self._value_var = tk.StringVar(value=value)

        # 3px colorful accent stripe on top
        self._top_stripe = tk.Frame(self, bg=accent_color, height=3)
        self._top_stripe.pack(fill="x", side="top")

        # Internal container with comfortable padding
        inner = tk.Frame(self, bg=WIN11_CARD_BG, padx=12, pady=10)
        inner.pack(fill="both", expand=True)

        # Title / Label
        self._title_lbl = tk.Label(
            inner,
            textvariable=self._title_var,
            font=FONT_CARD_TITLE,
            fg=WIN11_TEXT_MUTED,
            bg=WIN11_CARD_BG,
            anchor="w",
        )
        self._title_lbl.pack(fill="x", anchor="w")

        # Metric Value in Accent Color
        self._val_lbl = tk.Label(
            inner,
            textvariable=self._value_var,
            font=FONT_CARD_VAL,
            fg=self._accent,
            bg=WIN11_CARD_BG,
            anchor="w",
        )
        self._val_lbl.pack(fill="x", anchor="w", pady=(2, 0))

    def set(self, value: str, title: str | None = None, color: str | None = None):
        self._value_var.set(value)
        if title is not None:
            self._title_var.set(title.upper())
        if color is not None:
            self._accent = color
            self._top_stripe.configure(bg=color)
            self._val_lbl.configure(fg=color)


# ══════════════════════════════════════════════════════════════════════════
# Form Card Widget (Colorful Container for Forms & Control Panels)
# ══════════════════════════════════════════════════════════════════════════

class FormCard(tk.Frame):
    """
    A vibrant Windows 11 Form Area with a colored accent stripe,
    pill badge header, tinted background, and crisp border.
    """

    def __init__(
        self,
        parent,
        title: str = "",
        accent_color: str = "#0067c0",
        bg_color: str = "#f8faff",
        border_color: str = "#bfdbfe",
        icon: str = "⚙",
        **kw
    ):
        super().__init__(
            parent,
            bg=bg_color,
            highlightbackground=border_color,
            highlightthickness=1,
            bd=0,
            **kw
        )
        self.accent_color = accent_color
        self.bg_color = bg_color

        # 1. Top Accent Stripe (3px vibrant line)
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

        # 3. Content Body for form controls
        self.body = tk.Frame(self, bg=bg_color, padx=14, pady=8)
        self.body.pack(fill="both", expand=True, side="top")


# ══════════════════════════════════════════════════════════════════════════
# Status Bar
# ══════════════════════════════════════════════════════════════════════════

class StatusBar(tk.Frame):
    """Persistent status bar with Windows 11 light border and typography."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg="#eaeaea", highlightbackground=WIN11_BORDER,
                         highlightthickness=1, bd=0, padx=8, pady=4, **kw)

        self._msg_var = tk.StringVar(value="Ready")
        self._lbl = tk.Label(
            self,
            textvariable=self._msg_var,
            font=FONT_CAPTION,
            fg=WIN11_TEXT_MUTED,
            bg="#eaeaea",
        )
        self._lbl.pack(side="left")

        self._progress = ttk.Progressbar(self, mode="indeterminate", length=120)
        self._progress.pack(side="right", padx=6, pady=1)

    def set_message(self, text: str):
        self._msg_var.set(text)

    def start_progress(self):
        self._progress.start(10)

    def stop_progress(self):
        self._progress.stop()


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


# ══════════════════════════════════════════════════════════════════════════
# Sortable Treeview
# ══════════════════════════════════════════════════════════════════════════

class SortableTreeview(ttk.Treeview):
    """A Treeview that sorts columns when headers are clicked."""

    def __init__(self, parent, columns, **kw):
        super().__init__(parent, columns=columns, show="headings", **kw)
        self._sort_reverse: dict[str, bool] = {}

        for col in columns:
            self._sort_reverse[col] = False
            self.heading(col, command=lambda c=col: self._sort_by(c))

    def _sort_by(self, col: str):
        data = [(self.set(child, col), child) for child in self.get_children("")]

        try:
            data.sort(
                key=lambda t: float(
                    t[0].replace(",", "")
                    .replace("%", "")
                    .replace("+", "")
                    .replace("LKR ", "")
                    .replace("₨ ", "")
                    .replace("▲ ", "")
                    .replace("▼ ", "")
                ),
                reverse=self._sort_reverse[col],
            )
        except (ValueError, TypeError):
            data.sort(key=lambda t: t[0], reverse=self._sort_reverse[col])

        for idx, (_, child) in enumerate(data):
            self.move(child, "", idx)

        self._sort_reverse[col] = not self._sort_reverse[col]
