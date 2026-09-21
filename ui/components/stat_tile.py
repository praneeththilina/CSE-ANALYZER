# ui/components/stat_tile.py  –  Prominent KPI Metric Tile
"""
KPI stat tile displaying headline value, delta arrow with percentage change,
label, and optional sparkline/icon.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from ui.theme.tokens import ThemeManager, FONTS


class StatTile(tk.Frame):
    """Large KPI stat tile with value, label, and delta indicator."""

    def __init__(
        self,
        parent,
        label: str,
        value: str = "—",
        delta_pct: Optional[float] = None,
        icon: Optional[str] = None,
        width: int = 200,
        height: int = 95,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(
            parent,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            width=width,
            height=height,
            padx=14,
            pady=10,
            **kwargs
        )
        self.pack_propagate(False)

        # Header: Label + Optional Icon
        top_row = tk.Frame(self, bg=tokens["surface"])
        top_row.pack(fill="x")

        if icon:
            self._icon_lbl = tk.Label(top_row, text=icon, font=FONTS["caption"], fg=tokens["accent"], bg=tokens["surface"])
            self._icon_lbl.pack(side="left", padx=(0, 4))

        self._label = tk.Label(top_row, text=label, font=FONTS["card_title"], fg=tokens["text_dim"], bg=tokens["surface"])
        self._label.pack(side="left")

        # Big Number Value
        self._value_lbl = tk.Label(
            self,
            text=value,
            font=FONTS["display"],
            fg=tokens["text"],
            bg=tokens["surface"],
            anchor="w"
        )
        self._value_lbl.pack(fill="x", pady=(2, 0))

        # Bottom row: Delta arrow and change text
        self._bottom_row = tk.Frame(self, bg=tokens["surface"])
        self._bottom_row.pack(fill="x", pady=(2, 0))

        self._delta_lbl = tk.Label(
            self._bottom_row,
            text="",
            font=FONTS["caption"],
            bg=tokens["surface"]
        )
        if delta_pct is not None:
            self.set_delta(delta_pct)

        ThemeManager.register_listener(self._on_theme_change)

    def set(self, value: str, delta_pct: Optional[float] = None):
        self._value_lbl.config(text=str(value))
        if delta_pct is not None:
            self.set_delta(delta_pct)

    def set_delta(self, delta_pct: float):
        tokens = ThemeManager.tokens()
        if delta_pct > 0:
            arrow = "▲"
            color = tokens["gain"]
            text = f"{arrow} +{delta_pct:.1f}%"
        elif delta_pct < 0:
            arrow = "▼"
            color = tokens["loss"]
            text = f"{arrow} {delta_pct:.1f}%"
        else:
            text = "• 0.0%"
            color = tokens["text_dim"]

        self._delta_lbl.config(text=text, fg=color)
        if not self._delta_lbl.winfo_ismapped():
            self._delta_lbl.pack(side="left")

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"])
        self._value_lbl.configure(bg=tokens["surface"], fg=tokens["text"])
        self._label.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        self._bottom_row.configure(bg=tokens["surface"])
        self._delta_lbl.configure(bg=tokens["surface"])
