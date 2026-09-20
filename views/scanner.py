# views/scanner.py  –  QQE Signal & Multi-Indicator Confluence Scanner (Windows 11 Light)
"""
Runs QQE technical analysis with multi-indicator confluence scoring
(Trend EMA 50/200, Volume Surge, RSI momentum, and Volatility)
on all enabled symbols and displays signals with quality grades and risk levels.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ui_utils import (
    FormCard, SortableTreeview, ThreadedTask,
    WIN11_GREEN, WIN11_RED, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED,
    GRADE_A_PLUS, GRADE_A, GRADE_B, GRADE_C,
    FONT_TITLE, FONT_BODY
)

if TYPE_CHECKING:
    from app import MainApp


class ScannerTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._all_results: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="QQE Signal & Confluence Scanner", font=FONT_TITLE).pack(side="left")

        # ── Parameters Colorful Form Card ───────────────────────────────
        self.params_card = FormCard(
            self,
            title="QQE Strategy & Confluence Filter",
            accent_color="#4f46e5",
            bg_color="#f8faff",
            border_color="#c7d2fe",
            icon="🔍",
        )
        self.params_card.pack(fill="x", pady=(0, 10))

        param_row = tk.Frame(self.params_card.body, bg="#f8faff")
        param_row.pack(fill="x")

        tk.Label(param_row, text="RSI Period:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.rsi_var = tk.IntVar(value=14)
        ttk.Spinbox(param_row, from_=2, to=50, textvariable=self.rsi_var, width=5).pack(side="left", padx=(0, 14))

        tk.Label(param_row, text="SF:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sf_var = tk.IntVar(value=5)
        ttk.Spinbox(param_row, from_=1, to=20, textvariable=self.sf_var, width=5).pack(side="left", padx=(0, 14))

        tk.Label(param_row, text="QQE Factor:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.qqe_var = tk.DoubleVar(value=4.238)
        ttk.Entry(param_row, textvariable=self.qqe_var, width=7).pack(side="left", padx=(0, 14))

        tk.Label(param_row, text="Threshold:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(param_row, from_=1, to=50, textvariable=self.thresh_var, width=5).pack(side="left", padx=(0, 16))

        ttk.Button(param_row, text="🔍 Scan All Stocks", command=self._run_scan,
                   style="Accent.TButton").pack(side="right", padx=4)

        # ── Filter Row ──────────────────────────────────────────────────
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", pady=(0, 10))

        self.filter_var = tk.StringVar(value="all")
        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 8))
        filters = [
            ("All Signals", "all"),
            ("⭐ High Conviction (Grade A/A+)", "high_conviction"),
            ("▲ Long Only", "long"),
            ("▼ Short Only", "short"),
        ]
        for text, val in filters:
            ttk.Radiobutton(filter_frame, text=text, variable=self.filter_var,
                            value=val, command=self._apply_filter).pack(side="left", padx=5)

        self.count_var = tk.StringVar(value="0 signals found")
        ttk.Label(filter_frame, textvariable=self.count_var,
                  font=FONT_BODY, foreground=WIN11_TEXT_MUTED).pack(side="right")

        # ── Results Table ───────────────────────────────────────────────
        table_container = ttk.Frame(self)
        table_container.pack(fill="both", expand=True)

        cols = ("symbol", "industry", "signal", "grade", "score", "trend", "vol_ratio", "price", "rsi_ma", "date")
        self.tree = SortableTreeview(table_container, columns=cols, height=22)
        self.tree.heading("symbol", text="Symbol")
        self.tree.heading("industry", text="Industry")
        self.tree.heading("signal", text="Signal")
        self.tree.heading("grade", text="Grade & Conviction")
        self.tree.heading("score", text="Score")
        self.tree.heading("trend", text="Trend (200 EMA)")
        self.tree.heading("vol_ratio", text="Volume")
        self.tree.heading("price", text="Price (LKR)")
        self.tree.heading("rsi_ma", text="RSI")
        self.tree.heading("date", text="Date")

        self.tree.column("symbol", width=95, minwidth=75)
        self.tree.column("industry", width=130, minwidth=90)
        self.tree.column("signal", width=80, minwidth=65, anchor="center")
        self.tree.column("grade", width=125, minwidth=100, anchor="center")
        self.tree.column("score", width=60, minwidth=50, anchor="center")
        self.tree.column("trend", width=110, minwidth=85, anchor="center")
        self.tree.column("vol_ratio", width=70, minwidth=55, anchor="center")
        self.tree.column("price", width=85, minwidth=60, anchor="e")
        self.tree.column("rsi_ma", width=65, minwidth=50, anchor="e")
        self.tree.column("date", width=85, minwidth=75, anchor="center")

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Color Tags for Signal and Quality Grades
        self.tree.tag_configure("grade_a_plus", foreground=GRADE_A_PLUS)
        self.tree.tag_configure("grade_a", foreground=GRADE_A)
        self.tree.tag_configure("grade_b", foreground=GRADE_B)
        self.tree.tag_configure("grade_c", foreground=GRADE_C)
        self.tree.tag_configure("long", foreground=WIN11_GREEN)
        self.tree.tag_configure("short", foreground=WIN11_RED)

        self.tree.bind("<Double-1>", self._on_double_click)

    # ── Scan Execution ──────────────────────────────────────────────────

    def _run_scan(self):
        self.app.set_status("Scanning symbols with QQE & Confluence Engine... please wait")
        self.app.start_progress()

        params = {
            "rsi_period": self.rsi_var.get(),
            "sf": self.sf_var.get(),
            "qqe_factor": self.qqe_var.get(),
            "threshold": self.thresh_var.get(),
        }

        ThreadedTask(
            self.app.root,
            target=self.app.engine.run_qqe_scan,
            kwargs=params,
            on_done=self._on_scan_done,
            on_error=self._on_error,
        ).start()

    def _on_scan_done(self, results: list[dict]):
        self._all_results = results
        self._apply_filter()
        self.app.stop_progress()
        high_conv = sum(1 for r in results if r.get("grade") in ["A+", "A"])
        self.app.set_status(f"Scan complete: {len(results)} signals found ({high_conv} High Conviction)")

    def _apply_filter(self):
        f = self.filter_var.get()
        self.tree.delete(*self.tree.get_children())

        filtered = self._all_results
        if f == "high_conviction":
            filtered = [r for r in self._all_results if r.get("grade") in ["A+", "A"]]
        elif f == "long":
            filtered = [r for r in self._all_results if r["signal"] == 1]
        elif f == "short":
            filtered = [r for r in self._all_results if r["signal"] == -1]

        for r in filtered:
            sig_text = "▲ LONG" if r["signal"] == 1 else "▼ SHORT"
            grade = r.get("grade", "B")
            stars = r.get("stars", "⭐⭐⭐")
            score = r.get("score", 50)
            trend = r.get("trend", "—")
            vol_ratio = r.get("vol_ratio", "1.0x")
            grade_display = f"{grade} {stars}"

            # Choose tag based on grade
            if grade == "A+":
                tag = "grade_a_plus"
            elif grade == "A":
                tag = "grade_a"
            elif grade == "B":
                tag = "grade_b"
            else:
                tag = "grade_c"

            self.tree.insert("", "end", values=(
                r["symbol"],
                r["industry"],
                sig_text,
                grade_display,
                f"{score}/100",
                trend,
                vol_ratio,
                f"{float(r['price']):.2f}",
                f"{float(r['rsi_ma']):.2f}",
                r["date"],
            ), tags=(tag,))

        self.count_var.set(f"{len(filtered)} signals shown (of {len(self._all_results)})")

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Scan error: {exc}")

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            symbol = self.tree.item(sel[0], "values")[0]
            if symbol:
                # Find matching result row to forward entry & stop loss
                matched = next((r for r in self._all_results if r["symbol"] == symbol), None)
                entry = float(matched["price"]) if matched else None
                stop_loss = float(matched.get("stop_loss", 0)) if matched else None
                self.app.switch_to_chart(symbol, entry=entry, stop_loss=stop_loss)
