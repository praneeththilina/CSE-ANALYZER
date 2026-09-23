# ui/components/tooltip.py  –  Windows 11 Hover Tooltips
"""
Subtle non-intrusive hover tooltips for buttons, cards, and icons.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from ui.theme.tokens import ThemeManager, FONTS


class ToolTip:
    """Hover tooltip for Tkinter widgets."""

    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip_window: Optional[tk.Toplevel] = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._schedule()

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _schedule(self):
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        if self._tip_window or not self.text:
            return

        tokens = ThemeManager.tokens()
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self._tip_window = tk.Toplevel(self.widget)
        self._tip_window.wm_overrideredirect(True)
        self._tip_window.wm_attributes("-topmost", True)

        lbl = tk.Label(
            self._tip_window,
            text=self.text,
            font=FONTS["caption"],
            bg=tokens["surface_hi"],
            fg=tokens["text"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            padx=8,
            pady=4,
        )
        lbl.pack()
        self._tip_window.geometry(f"+{x}+{y}")

    def _hide(self):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None
