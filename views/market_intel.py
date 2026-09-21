# views/market_intel.py — Fundamental Intelligence, Macro Context & News Suite
"""
Market Intelligence Tab covering Features 21 to 27, 29 to 31, and 34 to 36:
- Fundamental Ratios Dashboard (P/E, P/B, ROE, ROCE, D/E, Dividend Yield)
- Intrinsic Value Models (DCF, Graham Number, Dividend Discount Model)
- Financial Health Scores (Piotroski F-Score 0-9 Checklist, Altman Z-Score)
- Peer & Sector Valuation Comparison
- Macroeconomic Overlay (CBSL Rates, Inflation, T-Bills, USD/LKR, Foreign Flows)
- Sector Rotation Heatmap Matrix
- Corporate Announcements with Sentiment Analysis & Event Calendar
- Anomaly & Manipulation Detection Radar
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ui_utils import (
    InfoCard, FormCard, SortableTreeview, ThreadedTask,
    fmt_currency, fmt_pct, fmt_volume,
    WIN11_BG, WIN11_CARD_BG, WIN11_GREEN, WIN11_RED, WIN11_ACCENT,
    FONT_TITLE, FONT_SECTION, FONT_BODY, FONT_CARD_VAL
)

if TYPE_CHECKING:
    from app import MainApp


class MarketIntelTab(ttk.Frame):
    """Deep fundamental, macroeconomic, and sentiment intelligence view."""

    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self.engine = app.engine
        self.current_symbol = "COMB.N0000"

        self._build_ui()

    def _build_ui(self):
        # ── Header & Symbol Selector ────────────────────────────────────
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(header_frame, text="🏛️ Market Intelligence & Fundamentals", font=FONT_TITLE).pack(side="left")

        selector_frame = ttk.Frame(header_frame)
        selector_frame.pack(side="right")

        ttk.Label(selector_frame, text="Select Equity:", font=FONT_BODY).pack(side="left", padx=(0, 6))

        self.sym_var = tk.StringVar(value="COMB.N0000")
        symbols = self.engine.get_symbol_list()
        self.sym_combo = ttk.Combobox(selector_frame, textvariable=self.sym_var, values=symbols, width=16)
        self.sym_combo.pack(side="left", padx=4)
        self.sym_combo.bind("<<ComboboxSelected>>", lambda e: self.load_symbol_intel())

        ttk.Button(selector_frame, text="🔍 Analyze", style="Accent.TButton", command=self.load_symbol_intel).pack(side="left", padx=4)
        ttk.Button(selector_frame, text="🔄 Refresh Macro", command=self._refresh_macro_data).pack(side="left", padx=4)

        # ── Notebook Sub-tabs ───────────────────────────────────────────
        self.intel_notebook = ttk.Notebook(self)
        self.intel_notebook.pack(fill="both", expand=True, pady=(4, 0))

        # Sub-tab 1: Fundamentals & Valuation
        self.tab_fundamentals = ttk.Frame(self.intel_notebook, padding=12)
        self.intel_notebook.add(self.tab_fundamentals, text="  📊 Valuation & Financial Health  ")

        # Sub-tab 2: Macro & Sector Rotation
        self.tab_macro = ttk.Frame(self.intel_notebook, padding=12)
        self.intel_notebook.add(self.tab_macro, text="  🌐 Macro Overlay & Sector Heatmap  ")

        # Sub-tab 3: News, Disclosures & Events
        self.tab_news = ttk.Frame(self.intel_notebook, padding=12)
        self.intel_notebook.add(self.tab_news, text="  📰 Disclosures & Event Calendar  ")

        # Sub-tab 4: Anomaly Radar
        self.tab_anomalies = ttk.Frame(self.intel_notebook, padding=12)
        self.intel_notebook.add(self.tab_anomalies, text="  🚨 Market Anomaly Radar  ")

        self._build_fundamentals_tab()
        self._build_macro_tab()
        self._build_news_tab()
        self._build_anomalies_tab()

    # ── Tab 1: Fundamentals & Health ────────────────────────────────────

    def _build_fundamentals_tab(self):
        # Top KPI cards row
        cards_row = ttk.Frame(self.tab_fundamentals)
        cards_row.pack(fill="x", pady=(0, 12))
        cards_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="fund_card")

        self.card_pe = InfoCard(cards_row, "P/E Ratio", "—", accent_color="#0284c7", icon="🏷️")
        self.card_pe.grid(row=0, column=0, padx=4, sticky="nsew")

        self.card_pb = InfoCard(cards_row, "P/B Ratio", "—", accent_color="#7c3aed", icon="📖")
        self.card_pb.grid(row=0, column=1, padx=4, sticky="nsew")

        self.card_roe = InfoCard(cards_row, "ROE %", "—", accent_color="#10b981", icon="📈")
        self.card_roe.grid(row=0, column=2, padx=4, sticky="nsew")

        self.card_div = InfoCard(cards_row, "Dividend Yield", "—", accent_color="#f59e0b", icon="💰")
        self.card_div.grid(row=0, column=3, padx=4, sticky="nsew")

        self.card_fscore = InfoCard(cards_row, "Piotroski F-Score", "—", accent_color="#10b981", icon="🛡️")
        self.card_fscore.grid(row=0, column=4, padx=4, sticky="nsew")

        # Split pane: Intrinsic Valuation & Scores (Left) + Piotroski 9 Criteria & Comps (Right)
        paned = ttk.Panedwindow(self.tab_fundamentals, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left Column: Intrinsic Value Models & Altman Z-score
        left_frame = FormCard(paned, title="Intrinsic Value & Solvency Models")
        paned.add(left_frame, weight=1)

        val_grid = ttk.Frame(left_frame)
        val_grid.pack(fill="x", pady=6)

        # DCF Model
        ttk.Label(val_grid, text="DCF Intrinsic Fair Value:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.lbl_dcf = ttk.Label(val_grid, text="—", font=("Segoe UI", 11, "bold"), foreground=WIN11_ACCENT)
        self.lbl_dcf.grid(row=0, column=1, sticky="w", padx=8)

        # Graham Number
        ttk.Label(val_grid, text="Benjamin Graham Number:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.lbl_graham = ttk.Label(val_grid, text="—", font=("Segoe UI", 11, "bold"), foreground="#10B981")
        self.lbl_graham.grid(row=1, column=1, sticky="w", padx=8)

        # DDM Value
        ttk.Label(val_grid, text="Dividend Discount (DDM):", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=4)
        self.lbl_ddm = ttk.Label(val_grid, text="—", font=("Segoe UI", 11, "bold"), foreground="#7C3AED")
        self.lbl_ddm.grid(row=2, column=1, sticky="w", padx=8)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", pady=10)

        # Altman Z-Score
        ttk.Label(left_frame, text="Altman Z-Score Credit Risk:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 2))
        self.lbl_altman = ttk.Label(left_frame, text="—", font=("Segoe UI", 10))
        self.lbl_altman.pack(anchor="w")

        # Peer Comparison
        ttk.Label(left_frame, text="Sector Peer Comparison:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.lbl_peer = ttk.Label(left_frame, text="—", font=("Segoe UI", 10), wraplength=340)
        self.lbl_peer.pack(anchor="w")

        # Right Column: Piotroski F-Score 9-Criteria Audit Checklist
        right_frame = FormCard(paned, title="Piotroski F-Score Audit Checklist (0–9 Scale)")
        paned.add(right_frame, weight=1)

        self.piotroski_listbox = tk.Listbox(
            right_frame,
            font=("Segoe UI", 9),
            bg="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightcolor="#cbd5e1"
        )
        self.piotroski_listbox.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Tab 2: Macro & Sector Heatmap ───────────────────────────────────

    def _build_macro_tab(self):
        # Macro indicators row
        macro_frame = FormCard(self.tab_macro, title="Central Bank of Sri Lanka (CBSL) & Macroeconomic Overlay")
        macro_frame.pack(fill="x", pady=(0, 10))

        macro_grid = ttk.Frame(macro_frame)
        macro_grid.pack(fill="x", padx=4, pady=4)
        macro_grid.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="macro_col")

        self.card_sdfr = InfoCard(macro_grid, "CBSL Policy SDFR", "8.25%", accent_color="#0284c7", icon="🏦")
        self.card_sdfr.grid(row=0, column=0, padx=4, sticky="nsew")

        self.card_slfr = InfoCard(macro_grid, "CBSL Policy SLFR", "9.25%", accent_color="#4f46e5", icon="🏛️")
        self.card_slfr.grid(row=0, column=1, padx=4, sticky="nsew")

        self.card_inflation = InfoCard(macro_grid, "CCPI Inflation", "1.8% YoY", accent_color="#10b981", icon="📉")
        self.card_inflation.grid(row=0, column=2, padx=4, sticky="nsew")

        self.card_tbill = InfoCard(macro_grid, "12M T-Bill Yield", "9.85%", accent_color="#f59e0b", icon="📜")
        self.card_tbill.grid(row=0, column=3, padx=4, sticky="nsew")

        self.card_usdlkr = InfoCard(macro_grid, "USD / LKR Forex", "302.50", accent_color="#7c3aed", icon="💱")
        self.card_usdlkr.grid(row=0, column=4, padx=4, sticky="nsew")

        # Sector Rotation Matrix
        sector_frame = FormCard(self.tab_macro, title="CSE Sector Rotation Heatmap & Capital Flows")
        sector_frame.pack(fill="both", expand=True)

        cols = [
            ("sector", "Sector Name", 220),
            ("daily_change_pct", "Daily %", 100),
            ("weekly_change_pct", "Weekly %", 100),
            ("monthly_change_pct", "Monthly %", 100),
            ("rotation_stage", "Rotation Stage & Flow", 180),
        ]
        self.tree_sector = SortableTreeview(sector_frame, cols, selectmode="browse")
        self.tree_sector.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Tab 3: News & Announcements ─────────────────────────────────────

    def _build_news_tab(self):
        paned = ttk.Panedwindow(self.tab_news, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Corporate Disclosures
        left_card = FormCard(paned, title="Corporate Disclosures & Sentiment Analysis")
        paned.add(left_card, weight=3)

        cols_news = [
            ("date", "Date", 90),
            ("symbol", "Symbol", 100),
            ("title", "Announcement Headline", 380),
            ("sentiment", "Sentiment Label", 120),
            ("score", "Score", 80)
        ]
        self.tree_news = SortableTreeview(left_card, cols_news, selectmode="browse")
        self.tree_news.pack(fill="both", expand=True, padx=4, pady=4)

        # Event Calendar
        right_card = FormCard(paned, title="Upcoming Financial Events Calendar")
        paned.add(right_card, weight=2)

        cols_events = [
            ("date", "Event Date", 90),
            ("symbol", "Symbol", 100),
            ("event_type", "Event Type", 150),
            ("details", "Details", 180)
        ]
        self.tree_events = SortableTreeview(right_card, cols_events, selectmode="browse")
        self.tree_events.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Tab 4: Anomaly Radar ────────────────────────────────────────────

    def _build_anomalies_tab(self):
        frame = FormCard(self.tab_anomalies, title="CSE Unusual Volume Spikes & Price Manipulation Alerts")
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Automated monitoring for pump-and-dump behavior, abnormal order-book absorption, and thin-market price swings.",
            font=FONT_BODY,
            foreground="#64748b"
        ).pack(anchor="w", padx=6, pady=(0, 8))

        self.txt_anomalies = tk.Text(
            frame,
            font=("Consolas", 10),
            bg="#f8fafc",
            relief="flat",
            highlightthickness=1,
            highlightcolor="#cbd5e1"
        )
        self.txt_anomalies.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Data Loading Logic ──────────────────────────────────────────────

    def on_tab_shown(self):
        """Called by notebook on tab activation."""
        self.load_symbol_intel()
        self._refresh_macro_data()

    def load_symbol_intel(self):
        sym = self.sym_var.get().strip().upper()
        if not sym:
            return
        self.current_symbol = sym
        self.app.set_status(f"Analyzing {sym} fundamentals & news...")
        self.app.start_progress()

        def task():
            fund = self.engine.get_fundamental_profile(sym)
            pred = self.engine.get_ml_prediction(sym)
            news = self.engine.get_news_and_events(sym)
            return fund, pred, news

        def on_done(result):
            self.app.stop_progress()
            self.app.set_status("Ready")
            fund, pred, news = result
            self._render_fundamentals(fund)
            self._render_anomalies(sym, pred.get("anomaly_check", {}))
            self._render_news_events(news)

        ThreadedTask(self.app.root, target=task, on_done=on_done, on_error=self._on_error).start()

    def _render_fundamentals(self, fund: Dict[str, Any]):
        self.card_pe.set_value(f"{fund['pe_ratio']:.1f}x")
        self.card_pb.set_value(f"{fund['pb_ratio']:.2f}x")
        self.card_roe.set_value(f"{fund['roe_pct']:.1f}%")
        self.card_div.set_value(f"{fund['dividend_yield_pct']:.1f}%")

        f_info = fund.get("piotroski", {})
        self.card_fscore.set_value(f"{f_info.get('f_score', 0)} / 9")

        # Intrinsic values
        dcf = fund.get("dcf_value")
        self.lbl_dcf.config(text=f"LKR {dcf:.2f}" if dcf else "N/A")

        graham = fund.get("graham_number")
        self.lbl_graham.config(text=f"LKR {graham:.2f}" if graham else "N/A")

        ddm = fund.get("ddm_value")
        self.lbl_ddm.config(text=f"LKR {ddm:.2f}" if ddm else "N/A")

        # Altman Z
        altman = fund.get("altman_z", {})
        self.lbl_altman.config(
            text=f"Z-Score: {altman.get('z_score', 0.0)}  •  {altman.get('zone', 'N/A')}",
            foreground=altman.get("color", "#1e293b")
        )

        # Peer comparison
        peer = fund.get("peer_comparison", {})
        self.lbl_peer.config(
            text=f"Sector ({peer.get('sector', '')}) Median P/E: {peer.get('sector_pe', 0)}x, P/B: {peer.get('sector_pb', 0)}x.\nVerdict: {peer.get('peer_verdict', '')}"
        )

        # Piotroski checklist
        self.piotroski_listbox.delete(0, "end")
        for item in f_info.get("breakdown", []):
            self.piotroski_listbox.insert("end", f"  ✔ {item}" if "(+1)" in item else f"  ✘ {item}")

    def _render_news_events(self, news: Dict[str, Any]):
        # Clear news
        self.tree_news.delete(*self.tree_news.get_children())
        for a in news.get("announcements", []):
            sent = a.get("sentiment", {})
            self.tree_news.insert("", "end", values=(
                a.get("date", ""),
                a.get("symbol", ""),
                a.get("title", ""),
                sent.get("sentiment_label", "Neutral"),
                f"{sent.get('sentiment_score', 0.0):+.2f}"
            ))

        # Clear events
        self.tree_events.delete(*self.tree_events.get_children())
        for ev in news.get("calendar", []):
            self.tree_events.insert("", "end", values=(
                ev.get("event_date", ""),
                ev.get("symbol", ""),
                ev.get("event_type", ""),
                ev.get("details", "")
            ))

    def _render_anomalies(self, symbol: str, anomaly_data: Dict[str, Any]):
        self.txt_anomalies.delete("1.0", "end")
        alerts = anomaly_data.get("alerts", [])
        if alerts:
            self.txt_anomalies.insert("end", f"=== ANOMALIES DETECTED FOR {symbol} ===\n\n")
            for alert in alerts:
                self.txt_anomalies.insert("end", f"• {alert}\n")
        else:
            self.txt_anomalies.insert("end", f"=== {symbol} ORDER BOOK & VOLUME STATUS ===\n\n")
            self.txt_anomalies.insert("end", "✔ No abnormal volume spikes or manipulation patterns detected.\n")
            self.txt_anomalies.insert("end", f"• Volume Z-Score: {anomaly_data.get('volume_z_score', 0.0):.2f}\n")
            self.txt_anomalies.insert("end", f"• Trailing Price Change: {anomaly_data.get('price_change_pct', 0.0):+.2f}%\n")

    def _refresh_macro_data(self):
        def task():
            macro = self.engine.get_macro_overlay()
            sectors = self.engine.get_sector_rotation()
            return macro, sectors

        def on_done(result):
            macro, sectors = result
            # Update sector heatmap
            self.tree_sector.delete(*self.tree_sector.get_children())
            for s in sectors:
                self.tree_sector.insert("", "end", values=(
                    s.get("sector", ""),
                    f"{s.get('daily_change_pct', 0.0):+.1f}%",
                    f"{s.get('weekly_change_pct', 0.0):+.1f}%",
                    f"{s.get('monthly_change_pct', 0.0):+.1f}%",
                    s.get("rotation_stage", "")
                ))

        ThreadedTask(self.app.root, target=task, on_done=on_done, on_error=self._on_error).start()

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Error: {exc}")

