# views/settings.py  –  Settings & Configuration Tab (Windows 11 Colorful UI)
"""
Application settings: database path, QQE defaults, Telegram config,
Gemini API key, theme toggle, and about info styled with colorful FormCards.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import TYPE_CHECKING

import sv_ttk
from ui_utils import FormCard, setup_win11_styles, WIN11_BG, WIN11_TEXT_MAIN, FONT_TITLE, FONT_SECTION, FONT_BODY

if TYPE_CHECKING:
    from app import MainApp


class SettingsTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        ttk.Label(self, text="Settings & Preferences", font=FONT_TITLE).pack(anchor="w", pady=(0, 10))

        # ── Database Colorful Card ──────────────────────────────────────
        self.db_card = FormCard(
            self,
            title="SQLite Database Connection",
            accent_color="#0284c7",
            bg_color="#f0f7ff",
            border_color="#bae6fd",
            icon="📂",
        )
        self.db_card.pack(fill="x", pady=(0, 8))

        db_row = tk.Frame(self.db_card.body, bg="#f0f7ff")
        db_row.pack(fill="x")
        tk.Label(db_row, text="Database Path:", font=FONT_BODY, bg="#f0f7ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 8))
        self.db_var = tk.StringVar(value=self.app.engine.db_path)
        ttk.Entry(db_row, textvariable=self.db_var, width=60,
                  state="readonly").pack(side="left", padx=(0, 8), fill="x", expand=True)
        ttk.Button(db_row, text="📂 Browse", command=self._browse_db).pack(side="left")

        # ── QQE Defaults Colorful Card ──────────────────────────────────
        self.qqe_card = FormCard(
            self,
            title="Default QQE Strategy Parameters",
            accent_color="#4f46e5",
            bg_color="#f8faff",
            border_color="#c7d2fe",
            icon="⚡",
        )
        self.qqe_card.pack(fill="x", pady=(0, 8))

        qqe_row = tk.Frame(self.qqe_card.body, bg="#f8faff")
        qqe_row.pack(fill="x")

        tk.Label(qqe_row, text="RSI Period:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.rsi_var = tk.IntVar(value=14)
        ttk.Spinbox(qqe_row, from_=2, to=50, textvariable=self.rsi_var, width=5).pack(side="left", padx=(0, 20))

        tk.Label(qqe_row, text="SF:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sf_var = tk.IntVar(value=5)
        ttk.Spinbox(qqe_row, from_=1, to=20, textvariable=self.sf_var, width=5).pack(side="left", padx=(0, 20))

        tk.Label(qqe_row, text="QQE Factor:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.qqe_var = tk.DoubleVar(value=4.238)
        ttk.Entry(qqe_row, textvariable=self.qqe_var, width=7).pack(side="left", padx=(0, 20))

        tk.Label(qqe_row, text="Threshold:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(qqe_row, from_=1, to=50, textvariable=self.thresh_var, width=5).pack(side="left")

        # ── Telegram Colorful Card ──────────────────────────────────────
        self.tg_card = FormCard(
            self,
            title="Telegram Signal Alerts Integration",
            accent_color="#0ea5e9",
            bg_color="#f0f9ff",
            border_color="#7dd3fc",
            icon="✈",
        )
        self.tg_card.pack(fill="x", pady=(0, 8))

        tg_row1 = tk.Frame(self.tg_card.body, bg="#f0f9ff")
        tg_row1.pack(fill="x", pady=(0, 6))
        tk.Label(tg_row1, text="Bot Token:", font=FONT_BODY, bg="#f0f9ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 8))
        self.tg_token_var = tk.StringVar(value=os.getenv("TELEGRAM_BOT_TOKEN", ""))
        ttk.Entry(tg_row1, textvariable=self.tg_token_var, width=50,
                  show="•").pack(side="left", fill="x", expand=True, padx=(0, 8))

        tg_row2 = tk.Frame(self.tg_card.body, bg="#f0f9ff")
        tg_row2.pack(fill="x")
        tk.Label(tg_row2, text="Chat ID:", font=FONT_BODY, bg="#f0f9ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 8))
        self.tg_chat_var = tk.StringVar(value=os.getenv("TELEGRAM_CHAT_ID", ""))
        ttk.Entry(tg_row2, textvariable=self.tg_chat_var, width=28).pack(side="left", padx=(0, 12))

        ttk.Button(tg_row2, text="📤 Test Alert Message", command=self._test_telegram).pack(side="left")

        # ── Gemini API Colorful Card ────────────────────────────────────
        self.gem_card = FormCard(
            self,
            title="Google Gemini 2.5 Flash AI API",
            accent_color="#7c3aed",
            bg_color="#faf5ff",
            border_color="#ddd6fe",
            icon="🤖",
        )
        self.gem_card.pack(fill="x", pady=(0, 8))

        gem_row = tk.Frame(self.gem_card.body, bg="#faf5ff")
        gem_row.pack(fill="x")
        tk.Label(gem_row, text="API Key:", font=FONT_BODY, bg="#faf5ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 8))
        import gemini_analyzer as ga
        self.gem_key_var = tk.StringVar(value=os.getenv("GEMINI_API_KEY", ga.API_KEY))
        ttk.Entry(gem_row, textvariable=self.gem_key_var, width=50,
                  show="•").pack(side="left", fill="x", expand=True)

        # ── Theme Colorful Card ─────────────────────────────────────────
        self.theme_card = FormCard(
            self,
            title="Windows 11 Appearance Theme",
            accent_color="#0d9488",
            bg_color="#f0fdfa",
            border_color="#99f6e4",
            icon="🎨",
        )
        self.theme_card.pack(fill="x", pady=(0, 8))

        theme_row = tk.Frame(self.theme_card.body, bg="#f0fdfa")
        theme_row.pack(fill="x")
        tk.Label(theme_row, text="Theme Mode:", font=FONT_BODY, bg="#f0fdfa", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 12))

        self.theme_var = tk.StringVar(value="light")
        ttk.Radiobutton(theme_row, text="☀️ Light (Windows 11 Fluent)", variable=self.theme_var,
                        value="light", command=self._toggle_theme).pack(side="left", padx=8)
        ttk.Radiobutton(theme_row, text="🌙 Dark", variable=self.theme_var,
                        value="dark", command=self._toggle_theme).pack(side="left", padx=8)

        # ── About Card ──────────────────────────────────────────────────
        self.about_card = FormCard(
            self,
            title="Application Details",
            accent_color="#475569",
            bg_color="#f8fafc",
            border_color="#cbd5e1",
            icon="ℹ",
        )
        self.about_card.pack(fill="x")

        about_body = self.about_card.body
        tk.Label(about_body, text="CSE Stock Analyzer", font=("Segoe UI Semibold", 11), bg="#f8fafc", fg=WIN11_TEXT_MAIN).pack(anchor="w")
        tk.Label(about_body, text="Colombo Stock Exchange Technical Analysis Desktop Application",
                 font=FONT_BODY, fg="#64748b", bg="#f8fafc").pack(anchor="w", pady=(2, 0))
        tk.Label(about_body, text="Native Windows 11 UI  •  Light Theme  •  Python 3.14.7",
                 font=FONT_BODY, fg="#94a3b8", bg="#f8fafc").pack(anchor="w", pady=(2, 0))

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
