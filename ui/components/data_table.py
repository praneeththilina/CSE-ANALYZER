# ui/components/data_table.py  –  Fast Sortable Windows 11 Treeview
"""
High-performance styled Treeview table with column sorting indicators,
alternating zebra rows, cell color tags, and zero-flicker batch row insertion.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, List, Sequence, Tuple

from ui.theme.tokens import ThemeManager, FONTS


class DataTable(ttk.Treeview):
    """Windows 11 styled table supporting sortable columns and batch updates."""

    def __init__(self, parent, columns: Sequence[str], **kwargs):
        super().__init__(parent, columns=columns, show="headings", **kwargs)
        self._sort_reverse: dict[str, bool] = {col: False for col in columns}
        self._col_titles: dict[str, str] = {}

        for col in columns:
            self.heading(col, text=col, command=lambda c=col: self.sort_by(c))

        self._configure_tags()
        ThemeManager.register_listener(self._on_theme_change)

    def _configure_tags(self):
        tokens = ThemeManager.tokens()
        # Alternating zebra rows
        even_bg = tokens["surface"]
        odd_bg = tokens["surface_card"]

        self.tag_configure("even", background=even_bg)
        self.tag_configure("odd", background=odd_bg)
        self.tag_configure("profit", foreground=tokens["gain"])
        self.tag_configure("loss", foreground=tokens["loss"])
        self.tag_configure("gain", foreground=tokens["gain"])
        self.tag_configure("warn", foreground=tokens["warn"])
        self.tag_configure("accent", foreground=tokens["accent"])
        self.tag_configure("muted", foreground=tokens["text_dim"])

    def clear(self):
        """Delete all rows."""
        self.delete(*self.get_children())

    def set_rows(self, rows: Sequence[Tuple[Any, ...]], tag_fn: Any = None):
        """Batch replace rows in a single pass to eliminate GUI freeze."""
        self.clear()
        for idx, row in enumerate(rows):
            zebra = "even" if idx % 2 == 0 else "odd"
            extra_tags = (tag_fn(row),) if callable(tag_fn) else ()
            self.insert("", "end", values=row, tags=(zebra,) + extra_tags)

    def sort_by(self, col: str):
        """Sort by column ascending/descending with header indicator."""
        data = []
        for child in self.get_children(""):
            val = self.set(child, col)
            # Try float/int parsing
            clean = val.replace("₨", "").replace("%", "").replace(",", "").replace("+", "").strip()
            try:
                parsed = float(clean)
            except ValueError:
                parsed = val.lower()
            data.append((parsed, child))

        reverse = self._sort_reverse.get(col, False)
        data.sort(key=lambda t: t[0], reverse=reverse)

        for idx, (_, child) in enumerate(data):
            self.move(child, "", idx)
            # Maintain alternating zebra tags
            current_tags = list(self.item(child, "tags"))
            current_tags = [t for t in current_tags if t not in ("even", "odd")]
            current_tags.insert(0, "even" if idx % 2 == 0 else "odd")
            self.item(child, tags=tuple(current_tags))

        # Update sort indicators in headings
        indicator = " ▼" if reverse else " ▲"
        base_title = self._col_titles.setdefault(col, self.heading(col)["text"].rstrip(" ▲▼"))
        self.heading(col, text=f"{base_title}{indicator}")

        # Reset other column headings
        for other_col in self["columns"]:
            if other_col != col:
                other_base = self._col_titles.setdefault(other_col, self.heading(other_col)["text"].rstrip(" ▲▼"))
                self.heading(other_col, text=other_base)

        self._sort_reverse[col] = not reverse

    def _on_theme_change(self, mode: str):
        self._configure_tags()


# Backward-compatible alias
SortableTreeview = DataTable
