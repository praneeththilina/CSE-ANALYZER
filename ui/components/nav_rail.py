# ui/components/nav_rail.py  –  Windows 11 Left Navigation Rail
"""
Vertical Fluent navigation rail with active pill indicator,
hover highlights, brand header, and instant page routing.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

from ui.theme.tokens import ThemeManager, FONTS


class NavRail(tk.Frame):
    """Modern Windows 11 Left Navigation Rail."""

    def __init__(
        self,
        parent,
        items: List[Tuple[str, str, str]],  # [(key, icon, label), ...]
        on_navigate: Optional[Callable[[str], None]] = None,
        width: int = 210,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(
            parent,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            width=width,
            **kwargs
        )
        self.pack_propagate(False)

        self._items = items
        self._on_navigate = on_navigate
        self._active_key = items[0][0] if items else ""
        self._nav_widgets: Dict[str, Dict[str, tk.Widget]] = {}

        # ── App Brand Header ────────────────────────────────────────────
        self._header = tk.Frame(self, bg=tokens["surface"], padx=16, pady=16)
        self._header.pack(fill="x")

        self._logo_icon = tk.Label(
            self._header,
            text="🇱🇰",
            font=("Segoe UI Emoji", 16),
            bg=tokens["surface"]
        )
        self._logo_icon.pack(side="left", padx=(0, 8))

        brand_text_frame = tk.Frame(self._header, bg=tokens["surface"])
        brand_text_frame.pack(side="left", fill="x")

        self._brand_title = tk.Label(
            brand_text_frame,
            text="CSE ANALYZER",
            font=FONTS["body_bold"],
            fg=tokens["text"],
            bg=tokens["surface"],
            anchor="w"
        )
        self._brand_title.pack(fill="x")

        self._brand_sub = tk.Label(
            brand_text_frame,
            text="Quant Decision System",
            font=FONTS["caption"],
            fg=tokens["text_dim"],
            bg=tokens["surface"],
            anchor="w"
        )
        self._brand_sub.pack(fill="x")

        # Divider
        self._div = tk.Frame(self, bg=tokens["border"], height=1)
        self._div.pack(fill="x", padx=12, pady=(0, 10))

        # ── Navigation Items List ───────────────────────────────────────
        self._items_container = tk.Frame(self, bg=tokens["surface"])
        self._items_container.pack(fill="both", expand=True, padx=8)

        for key, icon, label in items:
            self._create_nav_item(key, icon, label)

        self._render_active_state()
        ThemeManager.register_listener(self._on_theme_change)

    def _create_nav_item(self, key: str, icon: str, label: str):
        tokens = ThemeManager.tokens()
        btn_frame = tk.Frame(self._items_container, bg=tokens["surface"], cursor="hand2")
        btn_frame.pack(fill="x", pady=2)

        # Active indicator pill (left bar)
        indicator = tk.Frame(btn_frame, bg=tokens["surface"], width=3)
        indicator.pack(side="left", fill="y", padx=(2, 6))

        # Icon Label
        icon_lbl = tk.Label(
            btn_frame,
            text=icon,
            font=("Segoe UI Emoji", 12),
            fg=tokens["text_dim"],
            bg=tokens["surface"],
            cursor="hand2"
        )
        icon_lbl.pack(side="left", padx=(4, 8), pady=8)

        # Text Label
        text_lbl = tk.Label(
            btn_frame,
            text=label,
            font=FONTS["body"],
            fg=tokens["text_dim"],
            bg=tokens["surface"],
            cursor="hand2",
            anchor="w"
        )
        text_lbl.pack(side="left", fill="x", expand=True, pady=8)

        self._nav_widgets[key] = {
            "frame": btn_frame,
            "indicator": indicator,
            "icon": icon_lbl,
            "text": text_lbl
        }

        # Bind events across all sub-widgets for smooth interaction
        for w in (btn_frame, indicator, icon_lbl, text_lbl):
            w.bind("<Button-1>", lambda e, k=key: self.select(k))
            w.bind("<Enter>", lambda e, k=key: self._on_item_hover(k, True))
            w.bind("<Leave>", lambda e, k=key: self._on_item_hover(k, False))

    def select(self, key: str):
        """Set active navigation key and trigger callback."""
        if key in self._nav_widgets:
            self._active_key = key
            self._render_active_state()
            if self._on_navigate:
                self._on_navigate(key)

    def get_active(self) -> str:
        return self._active_key

    def _on_item_hover(self, key: str, is_hover: bool):
        if key == self._active_key:
            return
        tokens = ThemeManager.tokens()
        bg_col = tokens["surface_hi"] if is_hover else tokens["surface"]
        fg_col = tokens["text"] if is_hover else tokens["text_dim"]

        widgets = self._nav_widgets.get(key, {})
        widgets["frame"].configure(bg=bg_col)
        widgets["icon"].configure(bg=bg_col, fg=fg_col)
        widgets["text"].configure(bg=bg_col, fg=fg_col)
        widgets["indicator"].configure(bg=bg_col)

    def _render_active_state(self):
        tokens = ThemeManager.tokens()
        for key, w in self._nav_widgets.items():
            if key == self._active_key:
                # Active item gets accent left pill and highlight background
                w["frame"].configure(bg=tokens["accent_bg"])
                w["indicator"].configure(bg=tokens["accent"])
                w["icon"].configure(bg=tokens["accent_bg"], fg=tokens["accent"])
                w["text"].configure(bg=tokens["accent_bg"], fg=tokens["accent"], font=FONTS["body_bold"])
            else:
                w["frame"].configure(bg=tokens["surface"])
                w["indicator"].configure(bg=tokens["surface"])
                w["icon"].configure(bg=tokens["surface"], fg=tokens["text_dim"])
                w["text"].configure(bg=tokens["surface"], fg=tokens["text_dim"], font=FONTS["body"])

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"])
        self._header.configure(bg=tokens["surface"])
        self._logo_icon.configure(bg=tokens["surface"])
        self._brand_title.configure(bg=tokens["surface"], fg=tokens["text"])
        self._brand_sub.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        self._div.configure(bg=tokens["border"])
        self._items_container.configure(bg=tokens["surface"])
        self._render_active_state()
