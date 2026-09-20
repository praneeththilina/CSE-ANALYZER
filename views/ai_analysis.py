# views/ai_analysis.py  –  Gemini AI Analysis Tab (Windows 11 Light)
"""
Single-stock AI analysis and daily market summary powered by Google Gemini,
rendered with clean Windows 11 Light typography and rich markdown formatting.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from core.gemini_engine import analyze_stock, market_summary
from ui_utils import ThreadedTask, WIN11_BG, WIN11_CARD_BG, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED, WIN11_ACCENT, FONT_TITLE

if TYPE_CHECKING:
    from app import MainApp


class AIAnalysisTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="AI Analysis (Google Gemini)", font=FONT_TITLE).pack(side="left")

        # ── Controls ────────────────────────────────────────────────────
        ctrl = ttk.LabelFrame(self, text="  Analysis Controls  ", padding=12)
        ctrl.pack(fill="x", pady=(0, 10))

        ctrl_row = ttk.Frame(ctrl)
        ctrl_row.pack(fill="x")

        ttk.Label(ctrl_row, text="Symbol:").pack(side="left", padx=(0, 4))
        self.sym_var = tk.StringVar()
        self.sym_combo = ttk.Combobox(ctrl_row, textvariable=self.sym_var, width=15)
        self.sym_combo.pack(side="left", padx=(0, 12))

        ttk.Button(ctrl_row, text="🤖 Analyze Stock", command=self._analyze_stock,
                   style="Accent.TButton").pack(side="left", padx=4)

        ttk.Separator(ctrl_row, orient="vertical").pack(side="left", fill="y", padx=14)

        ttk.Button(ctrl_row, text="📊 Market Summary", command=self._market_summary).pack(side="left", padx=4)

        ttk.Separator(ctrl_row, orient="vertical").pack(side="left", fill="y", padx=14)

        ttk.Button(ctrl_row, text="📋 Copy Output", command=self._copy_to_clipboard).pack(side="left", padx=4)
        ttk.Button(ctrl_row, text="🗑️ Clear", command=self._clear).pack(side="left", padx=4)

        # ── Loading indicator ───────────────────────────────────────────
        self.loading_var = tk.StringVar(value="")
        self.loading_label = ttk.Label(self, textvariable=self.loading_var,
                                        font=("Segoe UI Semibold", 9), foreground=WIN11_ACCENT)
        self.loading_label.pack(anchor="w", pady=(0, 4))

        # ── Analysis Output ─────────────────────────────────────────────
        output_frame = tk.Frame(self, bg=WIN11_CARD_BG, highlightbackground="#cbd5e1",
                                highlightthickness=1, bd=0)
        output_frame.pack(fill="both", expand=True)

        self.text = tk.Text(
            output_frame,
            wrap="word",
            font=("Segoe UI", 10),
            bg=WIN11_CARD_BG,
            fg=WIN11_TEXT_MAIN,
            insertbackground=WIN11_ACCENT,
            selectbackground="#e0f2fe",
            selectforeground="#0369a1",
            padx=18,
            pady=16,
            relief="flat",
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Configure rich markdown tags
        self._configure_text_tags()

        # Pre-populate symbols immediately
        self._load_symbols()

    def on_tab_shown(self):
        if not self.sym_combo["values"]:
            self._load_symbols()

    def _configure_text_tags(self):
        self.text.tag_configure("h1", font=("Segoe UI Semibold", 15), foreground="#0f172a", spacing3=6)
        self.text.tag_configure("h2", font=("Segoe UI Semibold", 13), foreground="#1e293b", spacing3=4)
        self.text.tag_configure("h3", font=("Segoe UI Semibold", 11), foreground="#334155", spacing3=2)
        self.text.tag_configure("bold", font=("Segoe UI Semibold", 10), foreground="#0f172a")
        self.text.tag_configure("bullet", font=("Segoe UI", 10), foreground="#334155", lmargin1=16, lmargin2=28)
        self.text.tag_configure("code", font=("Consolas", 10), background="#f1f5f9", foreground="#0f172a")
        self.text.tag_configure("green", font=("Segoe UI Semibold", 10), foreground="#0e700e")
        self.text.tag_configure("red", font=("Segoe UI Semibold", 10), foreground="#c42b1c")
        self.text.tag_configure("accent", font=("Segoe UI Semibold", 10), foreground=WIN11_ACCENT)

    def _load_symbols(self):
        try:
            symbols = self.app.engine.get_symbol_list()
            self.sym_combo["values"] = symbols
            if symbols:
                self.sym_combo.current(0)
        except Exception:
            pass

    # ── Actions ─────────────────────────────────────────────────────────

    def _analyze_stock(self):
        symbol = self.sym_var.get().strip().upper()
        if not symbol:
            messagebox.showinfo("Info", "Select a symbol first")
            return

        self._set_loading(f"Analyzing {symbol} with Gemini 2.5 Flash...")
        ThreadedTask(
            self.app.root,
            target=analyze_stock, args=(symbol,),
            on_done=self._on_result,
            on_error=self._on_error,
        ).start()

    def _market_summary(self):
        self._set_loading("Generating CSE daily market summary with Gemini...")
        ThreadedTask(
            self.app.root,
            target=market_summary,
            on_done=self._on_result,
            on_error=self._on_error,
        ).start()

    def _set_loading(self, text: str):
        self.loading_var.set(text)
        self.app.set_status(text)
        self.app.start_progress()

    def _on_result(self, text: str):
        self.loading_var.set("")
        self.app.stop_progress()
        self.app.set_status("AI analysis complete")
        self._render_markdown(text)

    def _on_error(self, exc: Exception):
        self.loading_var.set("")
        self.app.stop_progress()
        self.app.set_status(f"AI error: {exc}")
        messagebox.showerror("Error", f"Gemini API Error: {exc}")

    def _clear(self):
        self.text.delete("1.0", "end")

    def _copy_to_clipboard(self):
        content = self.text.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.app.set_status("Copied analysis to clipboard")

    # ── Markdown-like rendering ─────────────────────────────────────────

    def _render_markdown(self, raw: str):
        self.text.delete("1.0", "end")
        lines = raw.split("\n")

        for line in lines:
            line_str = line.strip()

            if line_str.startswith("### "):
                self.text.insert("end", f"\n{line_str[4:]}\n", "h3")
            elif line_str.startswith("## "):
                self.text.insert("end", f"\n{line_str[3:]}\n", "h2")
            elif line_str.startswith("# "):
                self.text.insert("end", f"\n{line_str[2:]}\n", "h1")
            elif line_str.startswith(("- ", "* ", "• ")):
                bullet_content = line_str[2:]
                self.text.insert("end", "  • ", "accent")
                self._insert_formatted(bullet_content)
                self.text.insert("end", "\n")
            elif line_str.startswith("---") or line_str.startswith("==="):
                self.text.insert("end", "─" * 60 + "\n", "bullet")
            else:
                self._insert_formatted(line)
                self.text.insert("end", "\n")

    def _insert_formatted(self, text: str):
        import re
        tokens = re.split(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)", text)
        for t in tokens:
            if t.startswith("**") and t.endswith("**"):
                inner = t[2:-2]
                tag = "bold"
                lower = inner.lower()
                if any(w in lower for w in ("bullish", "buy", "gain", "strong")):
                    tag = "green"
                elif any(w in lower for w in ("bearish", "sell", "loss", "weak", "risk")):
                    tag = "red"
                self.text.insert("end", inner, tag)
            elif t.startswith("*") and t.endswith("*"):
                self.text.insert("end", t[1:-1], "bullet")
            elif t.startswith("`") and t.endswith("`"):
                self.text.insert("end", f" {t[1:-1]} ", "code")
            else:
                self.text.insert("end", t)
