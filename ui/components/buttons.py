# ui/components/buttons.py  –  Windows 11 Fluent Button Suite
"""
Reusable Fluent-styled buttons: PrimaryButton, GhostButton, IconButton,
and SegmentedButton with theme awareness and interactive hover transitions.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List

from ui.theme.tokens import ThemeManager, FONTS


class PrimaryButton(tk.Button):
    """Windows 11 Accent colored button with hover brightening."""

    def __init__(
        self,
        parent,
        text: str,
        command: Optional[Callable[[], None]] = None,
        icon: Optional[str] = None,
        padx: int = 14,
        pady: int = 6,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        self._icon = icon
        full_text = f"{icon}  {text}" if icon else text

        super().__init__(
            parent,
            text=full_text,
            command=command,
            font=FONTS["body_bold"],
            bg=tokens["accent"],
            fg="#ffffff",
            activebackground=tokens["accent_hover"],
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=padx,
            pady=pady,
            **kwargs
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        ThemeManager.register_listener(self._on_theme_change)

    def _on_enter(self, _):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["accent_hover"])

    def _on_leave(self, _):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["accent"])

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(
            bg=tokens["accent"],
            activebackground=tokens["accent_hover"]
        )


class GhostButton(tk.Button):
    """Subtle transparent button with border and soft hover fill."""

    def __init__(
        self,
        parent,
        text: str,
        command: Optional[Callable[[], None]] = None,
        icon: Optional[str] = None,
        padx: int = 12,
        pady: int = 5,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        self._icon = icon
        full_text = f"{icon}  {text}" if icon else text

        super().__init__(
            parent,
            text=full_text,
            command=command,
            font=FONTS["body"],
            bg=tokens["surface"],
            fg=tokens["text"],
            activebackground=tokens["surface_hi"],
            activeforeground=tokens["text"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["accent"],
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=padx,
            pady=pady,
            **kwargs
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        ThemeManager.register_listener(self._on_theme_change)

    def _on_enter(self, _):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface_hi"])

    def _on_leave(self, _):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"])

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(
            bg=tokens["surface"],
            fg=tokens["text"],
            activebackground=tokens["surface_hi"],
            activeforeground=tokens["text"],
            highlightbackground=tokens["border"]
        )


class IconButton(tk.Button):
    """Compact button presenting a clean icon and optional hover tooltip."""

    def __init__(
        self,
        parent,
        icon: str,
        command: Optional[Callable[[], None]] = None,
        tooltip: Optional[str] = None,
        size: int = 28,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        self._icon = icon
        self._tooltip = tooltip

        super().__init__(
            parent,
            text=icon,
            command=command,
            font=FONTS["subtitle"],
            bg=tokens["surface"],
            fg=tokens["text"],
            activebackground=tokens["surface_hi"],
            activeforeground=tokens["accent"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2",
            **kwargs
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        ThemeManager.register_listener(self._on_theme_change)

    def _on_enter(self, _):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface_hi"], fg=tokens["accent"])

    def _on_leave(self, _):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], fg=tokens["text"])

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(
            bg=tokens["surface"],
            fg=tokens["text"],
            activebackground=tokens["surface_hi"],
            highlightbackground=tokens["border"]
        )


class SegmentedButton(tk.Frame):
    """Pill-style grouped segmented button selector (e.g. 1D | 1W | 1M)."""

    def __init__(
        self,
        parent,
        options: List[str],
        default: Optional[str] = None,
        command: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(
            parent,
            bg=tokens["surface_hi"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            padx=2,
            pady=2,
            **kwargs
        )

        self._option_list = list(options)
        self._command = command
        self._selected = default or (options[0] if options else "")
        self._buttons: dict[str, tk.Label] = {}

        for opt in options:
            lbl = tk.Label(
                self,
                text=opt,
                font=FONTS["caption"],
                cursor="hand2",
                padx=10,
                pady=4,
            )
            lbl.pack(side="left", padx=1)
            lbl.bind("<Button-1>", lambda e, o=opt: self.select(o))
            self._buttons[opt] = lbl

        self._render()
        ThemeManager.register_listener(self._on_theme_change)

    def select(self, option: str):
        if option in self._option_list:
            self._selected = option
            self._render()
            if self._command:
                self._command(option)


    def get(self) -> str:
        return self._selected

    def _render(self):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface_hi"], highlightbackground=tokens["border"])
        for opt, lbl in self._buttons.items():
            if opt == self._selected:
                lbl.configure(
                    bg=tokens["surface"],
                    fg=tokens["accent"],
                    relief="solid",
                    bd=1,
                    highlightbackground=tokens["border"]
                )
            else:
                lbl.configure(
                    bg=tokens["surface_hi"],
                    fg=tokens["text_dim"],
                    relief="flat",
                    bd=0
                )

    def _on_theme_change(self, mode: str):
        self._render()
