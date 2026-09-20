# views/scanner.py  –  QQE Signal & Multi-Indicator Confluence Scanner (Windows 11 Light)
"""
Runs QQE technical analysis with multi-indicator confluence scoring
(Trend EMA 50/200, Volume Surge, RSI Divergence, Weekly Macro Trend,
Candlestick Patterns, and 52-Week Breakout Proximity) on all enabled symbols.
Provides CSV export, Telegram broadcasting, and a 6-Pillar Confluence Audit Scorecard.
"""
from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import TYPE_CHECKING

from ui_utils import (
    FormCard, SortableTreeview, ThreadedTask,
    WIN11_BG, WIN11_CARD_BG, WIN11_GREEN, WIN11_RED, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED,
    GRADE_A_PLUS, GRADE_A, GRADE_B, GRADE_C,
    FONT_TITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SECTION
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
        self.params_card.pack(fill="x", pady=(0, 8))

        param_row = tk.Frame(self.params_card.body, bg="#f8faff")
        param_row.pack(fill="x")

        tk.Label(param_row, text="RSI Period:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.rsi_var = tk.IntVar(value=14)
        ttk.Spinbox(param_row, from_=2, to=50, textvariable=self.rsi_var, width=5).pack(side="left", padx=(0, 10))

        tk.Label(param_row, text="SF:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sf_var = tk.IntVar(value=5)
        ttk.Spinbox(param_row, from_=1, to=20, textvariable=self.sf_var, width=5).pack(side="left", padx=(0, 10))

        tk.Label(param_row, text="QQE Factor:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.qqe_var = tk.DoubleVar(value=4.238)
        ttk.Entry(param_row, textvariable=self.qqe_var, width=6).pack(side="left", padx=(0, 10))

        tk.Label(param_row, text="Threshold:", font=FONT_BODY, bg="#f8faff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(param_row, from_=1, to=50, textvariable=self.thresh_var, width=5).pack(side="left", padx=(0, 12))

        ttk.Button(param_row, text="🔍 Scan All Stocks", command=self._run_scan,
                   style="Accent.TButton").pack(side="right", padx=4)

        # ── Filter & Action Row ─────────────────────────────────────────
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", pady=(0, 8))

        self.filter_var = tk.StringVar(value="all")
        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 4))
        filters = [
            ("All", "all"),
            ("⭐ High Conviction (A/A+)", "high_conviction"),
            ("🔥 Near 52W Breakout", "breakout"),
            ("▲ Long", "long"),
            ("▼ Short", "short"),
        ]
        for text, val in filters:
            ttk.Radiobutton(filter_frame, text=text, variable=self.filter_var,
                            value=val, command=self._apply_filter).pack(side="left", padx=3)

        # Action Buttons on right
        ttk.Button(filter_frame, text="📋 Confluence Audit", command=self._open_audit_modal).pack(side="right", padx=3)
        ttk.Button(filter_frame, text="📱 Send to Telegram", command=self._send_to_telegram,
                   style="Accent.TButton").pack(side="right", padx=3)
        ttk.Button(filter_frame, text="📥 Export CSV", command=self._export_csv).pack(side="right", padx=3)

        self.count_var = tk.StringVar(value="0 signals found")
        ttk.Label(filter_frame, textvariable=self.count_var,
                  font=FONT_BODY, foreground=WIN11_TEXT_MUTED).pack(side="right", padx=(0, 8))

        # ── Results Table ───────────────────────────────────────────────
        table_container = ttk.Frame(self)
        table_container.pack(fill="both", expand=True)

        cols = ("symbol", "industry", "signal", "grade", "score", "pattern", "trend", "weekly", "div", "dist_52w", "vol_ratio", "price", "rsi_ma", "date")
        self.tree = SortableTreeview(table_container, columns=cols, height=22)
        self.tree.heading("symbol", text="Symbol")
        self.tree.heading("industry", text="Industry")
        self.tree.heading("signal", text="Signal")
        self.tree.heading("grade", text="Grade & Stars")
        self.tree.heading("score", text="Score")
        self.tree.heading("pattern", text="Pattern")
        self.tree.heading("trend", text="Daily Trend")
        self.tree.heading("weekly", text="Weekly Macro")
        self.tree.heading("div", text="Divergence")
        self.tree.heading("dist_52w", text="52W High")
        self.tree.heading("vol_ratio", text="Volume")
        self.tree.heading("price", text="Price (LKR)")
        self.tree.heading("rsi_ma", text="RSI")
        self.tree.heading("date", text="Date")

        self.tree.column("symbol", width=85, minwidth=65)
        self.tree.column("industry", width=105, minwidth=75)
        self.tree.column("signal", width=70, minwidth=55, anchor="center")
        self.tree.column("grade", width=110, minwidth=85, anchor="center")
        self.tree.column("score", width=50, minwidth=40, anchor="center")
        self.tree.column("pattern", width=95, minwidth=70, anchor="center")
        self.tree.column("trend", width=85, minwidth=65, anchor="center")
        self.tree.column("weekly", width=80, minwidth=65, anchor="center")
        self.tree.column("div", width=90, minwidth=65, anchor="center")
        self.tree.column("dist_52w", width=75, minwidth=55, anchor="center")
        self.tree.column("vol_ratio", width=60, minwidth=45, anchor="center")
        self.tree.column("price", width=75, minwidth=50, anchor="e")
        self.tree.column("rsi_ma", width=55, minwidth=40, anchor="e")
        self.tree.column("date", width=75, minwidth=65, anchor="center")

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
        breakouts = sum(1 for r in results if r.get("near_breakout"))
        self.app.set_status(f"Scan complete: {len(results)} signals found ({high_conv} High Conviction, {breakouts} Near 52W Breakout)")

    def _apply_filter(self):
        f = self.filter_var.get()
        self.tree.delete(*self.tree.get_children())

        filtered = self._all_results
        if f == "high_conviction":
            filtered = [r for r in self._all_results if r.get("grade") in ["A+", "A"]]
        elif f == "breakout":
            filtered = [r for r in self._all_results if r.get("near_breakout")]
        elif f == "long":
            filtered = [r for r in self._all_results if r["signal"] == 1]
        elif f == "short":
            filtered = [r for r in self._all_results if r["signal"] == -1]

        for r in filtered:
            sig_text = "▲ LONG" if r["signal"] == 1 else "▼ SHORT"
            grade = r.get("grade", "B")
            stars = r.get("stars", "★★★")
            score = r.get("score", 50)
            pattern = r.get("pattern", "—")
            trend = r.get("trend", "—")
            weekly = r.get("weekly_trend", "—")
            div = r.get("divergence", "—")
            dist_52w = r.get("dist_52w", "0.0%")
            vol_ratio = r.get("vol_ratio", "1.0x")
            grade_display = f"{grade} {stars}"

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
                pattern,
                trend,
                weekly,
                div,
                dist_52w,
                vol_ratio,
                f"{float(r['price']):.2f}",
                f"{float(r['rsi_ma']):.2f}",
                r["date"],
            ), tags=(tag,))

        self.count_var.set(f"{len(filtered)} signals shown (of {len(self._all_results)})")

    # ── Export & Telegram Broadcast Actions ─────────────────────────────

    def _export_csv(self):
        if not self._all_results:
            messagebox.showwarning("No Data", "No scan results available to export. Run a scan first.")
            return

        file_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Signals to CSV",
            initialfile="cse_signals_confluence.csv",
        )
        if not file_path:
            return

        try:
            fields = [
                "symbol", "industry", "signal_text", "grade", "score",
                "pattern", "trend", "weekly_trend", "divergence", "dist_52w",
                "vol_ratio", "price", "stop_loss", "trailing_stop", "target1",
                "target2", "atr", "date"
            ]
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self._all_results)

            messagebox.showinfo("Export Successful", f"Successfully exported {len(self._all_results)} signals to:\n{file_path}")
            self.app.set_status(f"Exported {len(self._all_results)} signals to CSV")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save CSV file:\n{e}")

    def _send_to_telegram(self):
        if not self._all_results:
            messagebox.showwarning("No Data", "No scan results available. Run a scan first.")
            return

        high_conv = [r for r in self._all_results if r.get("grade") in ["A+", "A"]]
        count = len(high_conv) if high_conv else min(3, len(self._all_results))

        if not messagebox.askyesno("Confirm Broadcast", f"Broadcast {count} top signals to Telegram?"):
            return

        self.app.set_status("Broadcasting signals to Telegram...")
        self.app.start_progress()

        ThreadedTask(
            self.app.root,
            target=self.app.engine.send_telegram_signals,
            args=(self._all_results,),
            on_done=self._on_telegram_done,
            on_error=self._on_error,
        ).start()

    def _on_telegram_done(self, result: str):
        self.app.stop_progress()
        self.app.set_status(result)
        messagebox.showinfo("Telegram Broadcast", result)

    # ── Confluence Audit Scorecard Modal ────────────────────────────────

    def _open_audit_modal(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select Stock", "Please select a row in the table first to view its Confluence Audit.")
            return

        symbol = self.tree.item(sel[0], "values")[0]
        match = next((r for r in self._all_results if r["symbol"] == symbol), None)
        if not match:
            return

        # Create Modal
        win = tk.Toplevel(self.app.root)
        win.title(f"Confluence Audit Scorecard — {symbol}")
        win.geometry("540x580")
        win.configure(bg=WIN11_BG)
        win.resizable(False, False)
        win.transient(self.app.root)
        win.grab_set()

        # Header Card
        hdr_frame = tk.Frame(win, bg="#4f46e5", padx=16, pady=12)
        hdr_frame.pack(fill="x")
        tk.Label(hdr_frame, text=f"📊 {symbol} — {match.get('industry', '')}", font=("Segoe UI Semibold", 13), bg="#4f46e5", fg="#ffffff").pack(anchor="w")
        grade_str = f"Grade: {match.get('grade', 'A')} {match.get('stars', '')} | Score: {match.get('score', 0)}/100 | Signal: {match.get('signal_text', 'LONG')}"
        tk.Label(hdr_frame, text=grade_str, font=("Segoe UI", 10), bg="#4f46e5", fg="#e0e7ff").pack(anchor="w", pady=(2, 0))

        # Checklist Body
        body = tk.Frame(win, bg=WIN11_CARD_BG, padx=18, pady=14, highlightbackground="#cbd5e1", highlightthickness=1)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(body, text="6-Pillar Technical Confluence Breakdown:", font=FONT_SECTION, bg=WIN11_CARD_BG, fg=WIN11_TEXT_MAIN).pack(anchor="w", pady=(0, 10))

        pillars = [
            ("1. Trend Filter (EMA 50 / 200)", match.get("trend", "—"), "Above 200 EMA indicates macro bull phase"),
            ("2. Volume Accumulation", match.get("vol_ratio", "1.0x"), "Volume expansion confirms institutional backing"),
            ("3. Weekly Macro Direction", match.get("weekly_trend", "▲ Bullish"), "Higher timeframe momentum alignment"),
            ("4. RSI Divergence Status", match.get("divergence", "—"), "Reversal pattern indicating potential turning point"),
            ("5. Candlestick Price Action", match.get("pattern", "—"), "Execution trigger on recent price action bar"),
            ("6. 52-Week Range Proximity", match.get("dist_52w", "0.0%"), "Breakout or value accumulation position"),
        ]

        for title, val, desc in pillars:
            p_frame = tk.Frame(body, bg="#f8fafc", padx=10, pady=5, highlightbackground="#e2e8f0", highlightthickness=1)
            p_frame.pack(fill="x", pady=3)
            tk.Label(p_frame, text=title, font=FONT_BODY_BOLD, bg="#f8fafc", fg=WIN11_TEXT_MAIN).pack(side="left")
            tk.Label(p_frame, text=val, font=FONT_BODY_BOLD, bg="#f8fafc", fg="#4f46e5").pack(side="right")

        # Trade Parameters Box
        trade_frame = tk.Frame(body, bg="#f0fdf4", padx=10, pady=8, highlightbackground="#86efac", highlightthickness=1)
        trade_frame.pack(fill="x", pady=(10, 4))
        tk.Label(trade_frame, text="Suggested Trade Parameters:", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#059669").pack(anchor="w")

        p = float(match.get("price", 0))
        sl = float(match.get("stop_loss", 0))
        ts = float(match.get("trailing_stop", 0))
        t1 = float(match.get("target1", 0))
        t2 = float(match.get("target2", 0))

        t_txt = f"Entry: {p:.2f} LKR  |  Stop-Loss: {sl:.2f} LKR  |  ATR Trail: {ts:.2f} LKR\nTarget 1 (1:1.5): {t1:.2f} LKR  |  Target 2 (1:2.5): {t2:.2f} LKR"
        tk.Label(trade_frame, text=t_txt, font=FONT_BODY, bg="#f0fdf4", fg="#1e293b", justify="left").pack(anchor="w", pady=(2, 0))

        # Buttons
        btn_row = tk.Frame(win, bg=WIN11_BG, padx=16, pady=(0, 12))
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="📈 Open in Chart", style="Accent.TButton",
                   command=lambda: [win.destroy(), self.app.switch_to_chart(symbol, p, sl)]).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="right", padx=4)

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Error: {exc}")

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            symbol = self.tree.item(sel[0], "values")[0]
            if symbol:
                matched = next((r for r in self._all_results if r["symbol"] == symbol), None)
                entry = float(matched["price"]) if matched else None
                stop_loss = float(matched.get("stop_loss", 0)) if matched else None
                self.app.switch_to_chart(symbol, entry=entry, stop_loss=stop_loss)
