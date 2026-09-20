# views/scanner.py  –  QQE Signal Scanner Tab (Windows 11 Light)
"""
Runs QQE technical analysis on all enabled symbols and displays
buy/sell signals in a sortable, color-coded table styled for Windows 11 Light.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ui_utils import (
    SortableTreeview, ThreadedTask,
    WIN11_GREEN, WIN11_RED, WIN11_TEXT_MUTED,
    FONT_TITLE, FONT_SECTION, FONT_BODY
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
        ttk.Label(header, text="QQE Signal Scanner", font=FONT_TITLE).pack(side="left")

        # ── Parameters Frame ────────────────────────────────────────────
        params_frame = ttk.LabelFrame(self, text="  QQE Parameters  ", padding=12)
        params_frame.pack(fill="x", pady=(0, 10))

        param_row = ttk.Frame(params_frame)
        param_row.pack(fill="x")

        ttk.Label(param_row, text="RSI Period:").pack(side="left", padx=(0, 4))
        self.rsi_var = tk.IntVar(value=14)
        ttk.Spinbox(param_row, from_=2, to=50, textvariable=self.rsi_var, width=5).pack(side="left", padx=(0, 16))

        ttk.Label(param_row, text="SF:").pack(side="left", padx=(0, 4))
        self.sf_var = tk.IntVar(value=5)
        ttk.Spinbox(param_row, from_=1, to=20, textvariable=self.sf_var, width=5).pack(side="left", padx=(0, 16))

        ttk.Label(param_row, text="QQE Factor:").pack(side="left", padx=(0, 4))
        self.qqe_var = tk.DoubleVar(value=4.238)
        ttk.Entry(param_row, textvariable=self.qqe_var, width=7).pack(side="left", padx=(0, 16))

        ttk.Label(param_row, text="Threshold:").pack(side="left", padx=(0, 4))
        self.thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(param_row, from_=1, to=50, textvariable=self.thresh_var, width=5).pack(side="left", padx=(0, 16))

        ttk.Button(param_row, text="🔍 Scan Now", command=self._run_scan,
                   style="Accent.TButton").pack(side="right", padx=4)

        # ── Filter Row ──────────────────────────────────────────────────
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", pady=(0, 10))

        self.filter_var = tk.StringVar(value="all")
        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 8))
        for text, val in [("All Signals", "all"), ("▲ Long Only", "long"), ("▼ Short Only", "short")]:
            ttk.Radiobutton(filter_frame, text=text, variable=self.filter_var,
                            value=val, command=self._apply_filter).pack(side="left", padx=4)

        self.count_var = tk.StringVar(value="0 signals found")
        ttk.Label(filter_frame, textvariable=self.count_var,
                  font=FONT_BODY, foreground=WIN11_TEXT_MUTED).pack(side="right")

        # ── Results Table ───────────────────────────────────────────────
        table_container = ttk.Frame(self)
        table_container.pack(fill="both", expand=True)

        cols = ("symbol", "industry", "signal", "price", "rsi_ma", "fast_tl", "date")
        self.tree = SortableTreeview(table_container, columns=cols, height=22)
        self.tree.heading("symbol", text="Symbol")
        self.tree.heading("industry", text="Industry")
        self.tree.heading("signal", text="Signal")
        self.tree.heading("price", text="Price (LKR)")
        self.tree.heading("rsi_ma", text="RSI MA")
        self.tree.heading("fast_tl", text="Fast TL")
        self.tree.heading("date", text="Date")

        self.tree.column("symbol", width=110, minwidth=80)
        self.tree.column("industry", width=160, minwidth=100)
        self.tree.column("signal", width=85, minwidth=65, anchor="center")
        self.tree.column("price", width=90, minwidth=60, anchor="e")
        self.tree.column("rsi_ma", width=80, minwidth=60, anchor="e")
        self.tree.column("fast_tl", width=80, minwidth=60, anchor="e")
        self.tree.column("date", width=95, minwidth=80)

        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("long", foreground=WIN11_GREEN)
        self.tree.tag_configure("short", foreground=WIN11_RED)

        self.tree.bind("<Double-1>", self._on_double_click)

    # ── Scan Execution ──────────────────────────────────────────────────

    def _run_scan(self):
        self.app.set_status("Scanning symbols with QQE... please wait")
        self.app.start_progress()

        params = {
            "rsi_period": self.rsi_var.get(),
            "sf": self.sf_var.get(),
            "qqe_factor": self.qqe_var.get(),
            "threshold": self.thresh_var.get(),
        }

        ThreadedTask(
            self.app.root,
            target=self.app.engine.scan_qqe_signals,
            kwargs=params,
            on_done=self._on_scan_done,
            on_error=self._on_error,
        ).start()

    def _on_scan_done(self, results: list[dict]):
        self._all_results = results
        self._apply_filter()
        self.app.stop_progress()
        self.app.set_status(f"Scan complete: {len(results)} signals found")

    def _apply_filter(self):
        f = self.filter_var.get()
        self.tree.delete(*self.tree.get_children())

        filtered = self._all_results
        if f == "long":
            filtered = [r for r in self._all_results if r["signal"] == 1]
        elif f == "short":
            filtered = [r for r in self._all_results if r["signal"] == -1]

        for r in filtered:
            sig_text = "▲ LONG" if r["signal"] == 1 else "▼ SHORT"
            tag = "long" if r["signal"] == 1 else "short"
            self.tree.insert("", "end", values=(
                r["symbol"],
                r["industry"],
                sig_text,
                f"{r['price']:.2f}",
                f"{r['rsi_ma']:.2f}",
                f"{r['fast_tl']:.2f}",
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
                self.app.switch_to_chart(symbol)
