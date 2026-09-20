# views/settings.py  –  Settings & Configuration Tab (Windows 11 Light)
"""
Application settings: database path, QQE defaults, Telegram config,
Gemini API key, theme toggle, and about info styled for Windows 11 Light.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import TYPE_CHECKING

import sv_ttk
from ui_utils import setup_win11_styles, WIN11_BG, FONT_TITLE, FONT_SECTION, FONT_BODY

if TYPE_CHECKING:
    from app import MainApp


class SettingsTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        ttk.Label(self, text="Settings", font=FONT_TITLE).pack(anchor="w", pady=(0, 12))

        # ── Database ────────────────────────────────────────────────────
        db_frame = ttk.LabelFrame(self, text="  Database  ", padding=12)
        db_frame.pack(fill="x", pady=(0, 10))

        db_row = ttk.Frame(db_frame)
        db_row.pack(fill="x")
        ttk.Label(db_row, text="Database Path:").pack(side="left", padx=(0, 8))
        self.db_var = tk.StringVar(value=self.app.engine.db_path)
        ttk.Entry(db_row, textvariable=self.db_var, width=60,
                  state="readonly").pack(side="left", padx=(0, 8), fill="x", expand=True)
        ttk.Button(db_row, text="📂 Browse", command=self._browse_db).pack(side="left")

        # ── QQE Defaults ────────────────────────────────────────────────
        qqe_frame = ttk.LabelFrame(self, text="  QQE Default Parameters  ", padding=12)
        qqe_frame.pack(fill="x", pady=(0, 10))

        qqe_row = ttk.Frame(qqe_frame)
        qqe_row.pack(fill="x")

        ttk.Label(qqe_row, text="RSI Period:").pack(side="left", padx=(0, 4))
        self.rsi_var = tk.IntVar(value=14)
        ttk.Spinbox(qqe_row, from_=2, to=50, textvariable=self.rsi_var,
                     width=5).pack(side="left", padx=(0, 20))

        ttk.Label(qqe_row, text="SF:").pack(side="left", padx=(0, 4))
        self.sf_var = tk.IntVar(value=5)
        ttk.Spinbox(qqe_row, from_=1, to=20, textvariable=self.sf_var,
                     width=5).pack(side="left", padx=(0, 20))

        ttk.Label(qqe_row, text="QQE Factor:").pack(side="left", padx=(0, 4))
        self.qqe_var = tk.DoubleVar(value=4.238)
        ttk.Entry(qqe_row, textvariable=self.qqe_var, width=7).pack(side="left", padx=(0, 20))

        ttk.Label(qqe_row, text="Threshold:").pack(side="left", padx=(0, 4))
        self.thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(qqe_row, from_=1, to=50, textvariable=self.thresh_var,
                     width=5).pack(side="left")

        # ── Telegram ────────────────────────────────────────────────────
        tg_frame = ttk.LabelFrame(self, text="  Telegram Alerts  ", padding=12)
        tg_frame.pack(fill="x", pady=(0, 10))

        tg_row1 = ttk.Frame(tg_frame)
        tg_row1.pack(fill="x", pady=(0, 6))
        ttk.Label(tg_row1, text="Bot Token:").pack(side="left", padx=(0, 8))
        self.tg_token_var = tk.StringVar(value=os.getenv("TELEGRAM_BOT_TOKEN", ""))
        ttk.Entry(tg_row1, textvariable=self.tg_token_var, width=50,
                  show="•").pack(side="left", fill="x", expand=True, padx=(0, 8))

        tg_row2 = ttk.Frame(tg_frame)
        tg_row2.pack(fill="x")
        ttk.Label(tg_row2, text="Chat ID:").pack(side="left", padx=(0, 8))
        self.tg_chat_var = tk.StringVar(value=os.getenv("TELEGRAM_CHAT_ID", ""))
        ttk.Entry(tg_row2, textvariable=self.tg_chat_var, width=28).pack(side="left", padx=(0, 12))

        ttk.Button(tg_row2, text="📤 Test Alert", command=self._test_telegram).pack(side="left")

        # ── Gemini API ──────────────────────────────────────────────────
        gem_frame = ttk.LabelFrame(self, text="  Google Gemini AI  ", padding=12)
        gem_frame.pack(fill="x", pady=(0, 10))

        gem_row = ttk.Frame(gem_frame)
        gem_row.pack(fill="x")
        ttk.Label(gem_row, text="API Key:").pack(side="left", padx=(0, 8))
        import gemini_analyzer as ga
        self.gem_key_var = tk.StringVar(value=os.getenv("GEMINI_API_KEY", ga.API_KEY))
        ttk.Entry(gem_row, textvariable=self.gem_key_var, width=50,
                  show="•").pack(side="left", fill="x", expand=True)

        # ── Theme ───────────────────────────────────────────────────────
        theme_frame = ttk.LabelFrame(self, text="  Appearance  ", padding=12)
        theme_frame.pack(fill="x", pady=(0, 10))

        theme_row = ttk.Frame(theme_frame)
        theme_row.pack(fill="x")
        ttk.Label(theme_row, text="Theme Mode:").pack(side="left", padx=(0, 12))

        self.theme_var = tk.StringVar(value="light")
        ttk.Radiobutton(theme_row, text="☀️ Light (Windows 11)", variable=self.theme_var,
                        value="light", command=self._toggle_theme).pack(side="left", padx=8)
        ttk.Radiobutton(theme_row, text="🌙 Dark", variable=self.theme_var,
                        value="dark", command=self._toggle_theme).pack(side="left", padx=8)

        # ── About ───────────────────────────────────────────────────────
        about_frame = ttk.LabelFrame(self, text="  About  ", padding=12)
        about_frame.pack(fill="x")

        ttk.Label(about_frame, text="CSE Stock Analyzer", font=("Segoe UI Semibold", 11)).pack(anchor="w")
        ttk.Label(about_frame, text="Colombo Stock Exchange Technical Analysis Desktop Application",
                  font=FONT_BODY, foreground="#64748b").pack(anchor="w", pady=(2, 0))
        ttk.Label(about_frame, text="Native Windows 11 UI  •  Light Theme  •  Python 3.14.7",
                  font=FONT_BODY, foreground="#94a3b8").pack(anchor="w", pady=(2, 0))

    # ── Actions ─────────────────────────────────────────────────────────

    def _browse_db(self):
        path = filedialog.askopenfilename(
            title="Select Database File",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
        )
        if path:
            self.db_var.set(path)
            self.app.engine.db_path = path
            self.app.set_status(f"Database changed to: {path}")

    def _test_telegram(self):
        import stocks
        token = self.tg_token_var.get().strip()
        chat_id = self.tg_chat_var.get().strip()
        if not token or not chat_id:
            messagebox.showwarning("Warning", "Please enter both Bot Token and Chat ID")
            return
        os.environ["TELEGRAM_BOT_TOKEN"] = token
        os.environ["TELEGRAM_CHAT_ID"] = chat_id
        try:
            stocks.send_telegram_message("✅ Test message from CSE Stock Analyzer desktop app!", force=True)
            messagebox.showinfo("Success", "Test message sent successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send: {e}")

    def _toggle_theme(self):
        theme = self.theme_var.get()
        sv_ttk.set_theme(theme)
        if theme == "light":
            setup_win11_styles(self.app.root)
        try:
            import pywinstyles
            color = "#f3f3f3" if theme == "light" else "#1c1c1c"
            pywinstyles.change_header_color(self.app.root, color)
        except Exception:
            pass
        self.app.set_status(f"Theme changed to {theme}")
