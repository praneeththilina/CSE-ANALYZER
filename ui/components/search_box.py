# ui/components/search_box.py  –  Debounced Auto-Complete Search Box
"""
Debounced search input (250ms delay) with animated dropdown auto-complete suggestions.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

from ui.theme.tokens import ThemeManager, FONTS


class SearchBox(tk.Frame):
    """Debounced search box with dropdown suggestion list."""

    def __init__(
        self,
        parent,
        placeholder: str = "Search symbols (e.g. COMB, JKH)...",
        universe: Optional[List[str]] = None,
        on_select: Optional[Callable[[str], None]] = None,
        debounce_ms: int = 250,
        width: int = 30,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(
            parent,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["accent"],
            highlightthickness=1,
            padx=4,
            pady=3,
            **kwargs
        )

        self._universe = universe or []
        self._on_select = on_select
        self._debounce_ms = debounce_ms
        self._after_id = None
        self._popup: Optional[tk.Toplevel] = None

        # Search Icon
        self._icon = tk.Label(self, text="🔍", font=FONTS["caption"], fg=tokens["text_dim"], bg=tokens["surface"])
        self._icon.pack(side="left", padx=(4, 2))

        # Text Variable and Entry
        self.var = tk.StringVar()
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
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=2)

        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Down>", self._on_arrow_down)
        self.entry.bind("<Escape>", self._on_escape)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

        ThemeManager.register_listener(self._on_theme_change)

    def set_universe(self, symbols: List[str]):
        self._universe = symbols

    def get(self) -> str:
        return self.var.get().strip().upper()

    def set(self, val: str):
        self.var.set(val)

    def _on_key_release(self, event):
        if event.keysym in ("Return", "Up", "Down", "Escape"):
            return
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(self._debounce_ms, self._do_search)

    def _do_search(self):
        query = self.var.get().strip().upper()
        if not query or len(query) < 1:
            self._close_popup()
            return

        matches = [s for s in self._universe if query in s.upper()][:8]
        if matches:
            self._show_popup(matches)
        else:
            self._close_popup()

    def _show_popup(self, matches: List[str]):
        tokens = ThemeManager.tokens()
        if not self._popup:
            self._popup = tk.Toplevel(self)
            self._popup.wm_overrideredirect(True)
            self._popup.wm_attributes("-topmost", True)

            self._listbox = tk.Listbox(
                self._popup,
                font=FONTS["body"],
                bg=tokens["surface"],
                fg=tokens["text"],
                selectbackground=tokens["select_bg"],
                selectforeground=tokens["select_fg"],
                relief="solid",
                bd=1,
                highlightthickness=0,
                activestyle="none",
                height=min(8, len(matches))
            )
            self._listbox.pack(fill="both", expand=True)
            self._listbox.bind("<Button-1>", self._on_listbox_click)
            self._listbox.bind("<Return>", self._on_listbox_enter)
            self._listbox.bind("<Escape>", self._on_listbox_escape)

        self._listbox.delete(0, "end")
        for m in matches:
            self._listbox.insert("end", f"  {m}")

        # Position below search entry
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        w = max(self.winfo_width(), 200)
        h = min(220, len(matches) * 26 + 4)
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.deiconify()

    def _close_popup(self):
        if self._popup:
            self._popup.destroy()
            self._popup = None

    def _on_listbox_click(self, event):
        idx = self._listbox.nearest(event.y)
        if idx >= 0:
            item = self._listbox.get(idx).strip()
            self._select_item(item)

    def _on_listbox_enter(self, _):
        cur = self._listbox.curselection()
        if cur:
            item = self._listbox.get(cur[0]).strip()
            self._select_item(item)

    def _on_arrow_down(self, event=None):
        if self._popup and hasattr(self, "_listbox") and self._listbox.size() > 0:
            self._listbox.focus_set()
            if not self._listbox.curselection():
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            return "break"

    def _on_escape(self, event=None):
        if self._popup:
            self._close_popup()
            return "break"

    def _on_listbox_escape(self, event=None):
        self._close_popup()
        self.entry.focus_set()
        return "break"

    def _on_enter(self, _):
        if self._popup and self._listbox.size() > 0:
            item = self._listbox.get(0).strip()
            self._select_item(item)
        else:
            query = self.get()
            if query and self._on_select:
                self._on_select(query)

    def _select_item(self, item: str):
        self.var.set(item)
        self._close_popup()
        if self._on_select:
            self._on_select(item)

    def _on_focus_in(self, _):
        self.configure(
            highlightbackground=ThemeManager.tokens()["accent"],
            highlightthickness=2
        )

    def _on_focus_out(self, _):
        self.configure(highlightthickness=1)
        self.after(200, self._close_popup)

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"], highlightbackground=tokens["border"])
        self._icon.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        self.entry.configure(bg=tokens["surface"], fg=tokens["text"], insertbackground=tokens["text"])
        if self._popup:
            self._close_popup()
