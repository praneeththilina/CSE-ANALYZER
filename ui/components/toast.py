# ui/components/toast.py  –  Floating Toast Notifications
"""
Non-blocking animated floating toast notifications styled for Windows 11 Fluent UI.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from ui.theme.tokens import ThemeManager, FONTS


class ToastManager:
    """Manages creation and auto-dismissal of floating toast messages."""

    _active_toast: Optional[tk.Toplevel] = None

    @classmethod
    def show(
        cls,
        root: tk.Tk,
        message: str,
        title: str = "Notification",
        kind: str = "info",  # 'info', 'success', 'warn', 'error'
        duration_ms: int = 3500
    ):
        if cls._active_toast:
            try:
                cls._active_toast.destroy()
            except Exception:
                pass
            cls._active_toast = None

        tokens = ThemeManager.tokens()
        palette = {
            "info": (tokens["accent"], "ℹ️"),
            "success": (tokens["gain"], "✔"),
            "warn": (tokens["warn"], "⚠️"),
            "error": (tokens["loss"], "✖"),
        }.get(kind, (tokens["accent"], "ℹ️"))

        toast = tk.Toplevel(root)
        cls._active_toast = toast
        toast.wm_overrideredirect(True)
        toast.wm_attributes("-topmost", True)

        frame = tk.Frame(
            toast,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["accent"],
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        frame.pack(fill="both", expand=True)

        # Left accent color strip
        strip = tk.Frame(frame, bg=palette[0], width=4)
        strip.pack(side="left", fill="y", padx=(0, 10))

        content = tk.Frame(frame, bg=tokens["surface"])
        content.pack(side="left", fill="both", expand=True)

        header = tk.Label(
            content,
            text=f"{palette[1]}  {title}",
            font=FONTS["body_bold"],
            fg=tokens["text"],
            bg=tokens["surface"],
            anchor="w"
        )
        header.pack(fill="x")

        msg_lbl = tk.Label(
            content,
            text=message,
            font=FONTS["body"],
            fg=tokens["text_dim"],
            bg=tokens["surface"],
            anchor="w",
            wraplength=280,
            justify="left"
        )
        msg_lbl.pack(fill="x", pady=(2, 0))

        # Position in bottom-right corner of root window
        root.update_idletasks()
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        rw = root.winfo_width()
        rh = root.winfo_height()

        tw = 320
        th = 75
        tx = rx + rw - tw - 24
        ty = ry + rh - th - 36

        toast.geometry(f"{tw}x{th}+{tx}+{ty}")

        # Auto-dismiss
        def dismiss():
            if cls._active_toast == toast:
                cls._active_toast = None
            try:
                toast.destroy()
            except Exception:
                pass

        toast.after(duration_ms, dismiss)
        toast.bind("<Button-1>", lambda e: dismiss())


def show_toast(root: tk.Tk, message: str, title: str = "Notification", kind: str = "info", duration_ms: int = 3500):
    ToastManager.show(root, message, title=title, kind=kind, duration_ms=duration_ms)
