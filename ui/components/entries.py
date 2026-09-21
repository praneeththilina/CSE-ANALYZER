# ui/components/entries.py  –  State-Border Input Fields
"""
Input entry components with colorful state-based borders
(Default, Focused 2px, Valid, Error, Warn) matching Windows 11 Fluent design.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional, Callable

from ui.theme.tokens import ThemeManager, INPUT_STATES, FONTS


class StateEntry(tk.Frame):
    """Entry wrapper with dynamic border color based on validation/focus state."""

    def __init__(
        self,
        parent,
        textvariable: Optional[tk.StringVar] = None,
        placeholder: str = "",
        width: int = 24,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(
            parent,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["accent"],
            highlightthickness=1,
            bd=0,
            padx=2,
            pady=2,
        )

        self._placeholder = placeholder
        self._on_change = on_change
        self._current_state = "default"  # 'default', 'focused', 'valid', 'error', 'warn'
        self.var = textvariable or tk.StringVar()

        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            font=FONTS["body"],
            bg=tokens["surface"],
            fg=tokens["text"],
            insertbackground=tokens["text"],
            relief="flat",
            bd=0,
            width=width,
            **kwargs
        )
        self.entry.pack(fill="both", expand=True, padx=4, pady=3)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.var.trace_add("write", self._on_var_write)

        ThemeManager.register_listener(self._on_theme_change)

    def set_state(self, state: str):
        """Set state: 'default', 'valid', 'error', 'warn'."""
        self._current_state = state
        self._update_border()

    def get(self) -> str:
        return self.var.get()

    def set(self, val: str):
        self.var.set(val)

    def _on_focus_in(self, _):
        if self._current_state not in ("error", "warn"):
            self.configure(
                highlightbackground=ThemeManager.tokens()["accent"],
                highlightcolor=ThemeManager.tokens()["accent"],
                highlightthickness=2
            )

    def _on_focus_out(self, _):
        self.configure(highlightthickness=1)
        self._update_border()

    def _on_var_write(self, *args):
        if self._on_change:
            self._on_change(self.var.get())

    def _update_border(self):
        mode = ThemeManager.get_mode()
        palette = INPUT_STATES.get(mode, INPUT_STATES["light"])
        border_col = palette.get(self._current_state, palette["default"])
        self.configure(
            highlightbackground=border_col,
            highlightcolor=border_col
        )

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"])
        self.entry.configure(
            bg=tokens["surface"],
            fg=tokens["text"],
            insertbackground=tokens["text"]
        )
        self._update_border()


class LabeledEntry(tk.Frame):
    """Combines a descriptive label, StateEntry, and optional helper text."""

    def __init__(
        self,
        parent,
        label: str,
        textvariable: Optional[tk.StringVar] = None,
        placeholder: str = "",
        helper_text: str = "",
        width: int = 24,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(parent, bg=tokens["surface"], **kwargs)

        self._lbl = tk.Label(
            self,
            text=label,
            font=FONTS["caption"],
            fg=tokens["text_dim"],
            bg=tokens["surface"],
            anchor="w",
        )
        self._lbl.pack(fill="x", pady=(0, 2))

        self.state_entry = StateEntry(
            self,
            textvariable=textvariable,
            placeholder=placeholder,
            width=width,
        )
        self.state_entry.pack(fill="x")

        self._helper = tk.Label(
            self,
            text=helper_text,
            font=FONTS["caption"],
            fg=tokens["text_subtle"],
            bg=tokens["surface"],
            anchor="w",
        )
        if helper_text:
            self._helper.pack(fill="x", pady=(2, 0))

        ThemeManager.register_listener(self._on_theme_change)

    def set_error(self, message: str):
        self.state_entry.set_state("error")
        self._helper.config(text=message, fg=ThemeManager.tokens()["loss"])
        if not self._helper.winfo_ismapped():
            self._helper.pack(fill="x", pady=(2, 0))

    def set_valid(self, message: str = ""):
        self.state_entry.set_state("valid")
        self._helper.config(text=message, fg=ThemeManager.tokens()["gain"])

    def set_warn(self, message: str):
        self.state_entry.set_state("warn")
        self._helper.config(text=message, fg=ThemeManager.tokens()["warn"])

    def reset_state(self):
        self.state_entry.set_state("default")
        self._helper.config(text="", fg=ThemeManager.tokens()["text_subtle"])

    def get(self) -> str:
        return self.state_entry.get()

    def set(self, val: str):
        self.state_entry.set(val)

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"])
        self._lbl.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        self._helper.configure(bg=tokens["surface"])
