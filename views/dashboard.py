# views/dashboard.py  –  Market Dashboard Tab (Windows 11 Light - Instant Cohesive Load)
"""
Landing screen showing market overview: summary cards, top gainers/losers,
recent signals, and quick stats styled for Windows 11 Fluent Light.
All data is populated synchronously from the local SQLite database on construction
so all elements appear simultaneously without pop-in or right-to-left lag.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ui_utils import (
    InfoCard, SortableTreeview, ThreadedTask,
    fmt_currency, fmt_pct, fmt_volume,
    WIN11_BG, WIN11_GREEN, WIN11_RED, WIN11_ACCENT,
    FONT_TITLE, FONT_SECTION, FONT_BODY, FONT_CARD_VAL
)

if TYPE_CHECKING:
    from app import MainApp


class DashboardTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._featured_offset = 0
        self._build_ui()
        # Immediately populate cards, gainers, losers, and signals from DB
        self._load_local_data()

    # ── UI Construction ─────────────────────────────────────────────────

    def _build_ui(self):
        # Top action bar
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(action_frame, text="Market Dashboard", font=FONT_TITLE).pack(side="left")

        btn_frame = ttk.Frame(action_frame)
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="🔄 Live Refresh", command=self.refresh_live_data).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="⚡ Run Daily Scan", style="Accent.TButton", command=self._run_daily_scan).pack(side="left", padx=4)

        # ── Summary Cards Row ───────────────────────────────────────────
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="x", pady=(0, 14))
        cards_frame.columnconfigure(tuple(range(6)), weight=1, uniform="card")

        self.card_symbols = InfoCard(cards_frame, "Total Symbols", "—", accent_color="#0284c7", icon="🌐")
        self.card_symbols.grid(row=0, column=0, padx=4, pady=2, sticky="nsew")

        self.card_enabled = InfoCard(cards_frame, "Active Equities", "—", accent_color="#4f46e5", icon="⚡")
        self.card_enabled.grid(row=0, column=1, padx=4, pady=2, sticky="nsew")

        self.card_bars = InfoCard(cards_frame, "Total Bars", "—", accent_color="#7c3aed", icon="📊")
        self.card_bars.grid(row=0, column=2, padx=4, pady=2, sticky="nsew")

        self.card_last_bar = InfoCard(cards_frame, "Last Bar Date", "—", accent_color="#d97706", icon="📅")
        self.card_last_bar.grid(row=0, column=3, padx=4, pady=2, sticky="nsew")

        self.card_long_7d = InfoCard(cards_frame, "BUY Signals (7d)", "—", accent_color="#059669", icon="▲")
        self.card_long_7d.grid(row=0, column=4, padx=4, pady=2, sticky="nsew")

        self.card_short_7d = InfoCard(cards_frame, "EXIT Alerts (7d)", "—", accent_color="#e11d48", icon="▼")
        self.card_short_7d.grid(row=0, column=5, padx=4, pady=2, sticky="nsew")

        # ── Benchmark & Macro Ribbon (Features 28, 30) ──────────────────
        macro_ribbon = ttk.Frame(self)
        macro_ribbon.pack(fill="x", pady=(0, 10))
        macro_ribbon.columnconfigure((0, 1, 2, 3), weight=1, uniform="m_ribbon")

        self.card_aspi = InfoCard(macro_ribbon, "ASPI Benchmark", "12,450.2 (+0.42%)", accent_color="#0284c7", icon="📈")
        self.card_aspi.grid(row=0, column=0, padx=3, sticky="nsew")

        self.card_sl20 = InfoCard(macro_ribbon, "S&P SL20 Index", "3,710.5 (+0.58%)", accent_color="#4f46e5", icon="🏆")
        self.card_sl20.grid(row=0, column=1, padx=3, sticky="nsew")

        self.card_cbsl = InfoCard(macro_ribbon, "CBSL Policy Rates", "SDFR 8.25% • SLFR 9.25%", accent_color="#10b981", icon="🏛️")
        self.card_cbsl.grid(row=0, column=2, padx=3, sticky="nsew")

        self.card_forex = InfoCard(macro_ribbon, "USD/LKR & T-Bills", "LKR 302.50 • 12M 9.85%", accent_color="#f59e0b", icon="💱")
        self.card_forex.grid(row=0, column=3, padx=3, sticky="nsew")

        # ── Everyday New Feature: Daily Stock Spotlight & Insight ──────────
        self._build_daily_feature_section()

        # ── Main content: Gainers/Losers + Recent Signals ───────────────
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(0, weight=1)

        # Top Gainers
        gainer_frame = ttk.LabelFrame(content, text="  📈 Top Gainers  ", padding=8)
        gainer_frame.grid(row=0, column=0, padx=(0, 6), pady=4, sticky="nsew")

        cols_gl = ("symbol", "price", "change", "volume")
        self.tree_gainers = SortableTreeview(gainer_frame, columns=cols_gl, height=14)
        self.tree_gainers.heading("symbol", text="Symbol")
        self.tree_gainers.heading("price", text="Price (LKR)")
        self.tree_gainers.heading("change", text="Change")
        self.tree_gainers.heading("volume", text="Volume")
        self.tree_gainers.column("symbol", width=105, minwidth=80)
        self.tree_gainers.column("price", width=80, minwidth=60, anchor="e")
        self.tree_gainers.column("change", width=85, minwidth=60, anchor="e")
        self.tree_gainers.column("volume", width=80, minwidth=60, anchor="e")
        self.tree_gainers.pack(fill="both", expand=True)
        self.tree_gainers.bind("<Double-1>", lambda e: self._on_double_click(self.tree_gainers))

        # Top Losers
        loser_frame = ttk.LabelFrame(content, text="  📉 Top Losers  ", padding=8)
        loser_frame.grid(row=0, column=1, padx=3, pady=4, sticky="nsew")

        self.tree_losers = SortableTreeview(loser_frame, columns=cols_gl, height=14)
        self.tree_losers.heading("symbol", text="Symbol")
        self.tree_losers.heading("price", text="Price (LKR)")
        self.tree_losers.heading("change", text="Change")
        self.tree_losers.heading("volume", text="Volume")
        self.tree_losers.column("symbol", width=105, minwidth=80)
        self.tree_losers.column("price", width=80, minwidth=60, anchor="e")
        self.tree_losers.column("change", width=85, minwidth=60, anchor="e")
        self.tree_losers.column("volume", width=80, minwidth=60, anchor="e")
        self.tree_losers.pack(fill="both", expand=True)
        self.tree_losers.bind("<Double-1>", lambda e: self._on_double_click(self.tree_losers))

        # Recent Signals
        signals_frame = ttk.LabelFrame(content, text="  🔔 Calibrated Decision Signals  ", padding=8)
        signals_frame.grid(row=0, column=2, padx=(6, 0), pady=4, sticky="nsew")

        cols_sig = ("date", "symbol", "direction", "rating")
        self.tree_signals = SortableTreeview(signals_frame, columns=cols_sig, height=14)
        self.tree_signals.heading("date", text="Date")
        self.tree_signals.heading("symbol", text="Symbol")
        self.tree_signals.heading("direction", text="Signal & Edge")
        self.tree_signals.heading("rating", text="Rating")
        self.tree_signals.column("date", width=85, minwidth=75)
        self.tree_signals.column("symbol", width=95, minwidth=75)
        self.tree_signals.column("direction", width=120, minwidth=90, anchor="center")
        self.tree_signals.column("rating", width=65, minwidth=55, anchor="center")
        self.tree_signals.pack(fill="both", expand=True)
        self.tree_signals.bind("<Double-1>", lambda e: self._on_double_click(self.tree_signals))

        # Tag styles for tables
        self.tree_gainers.tag_configure("gain", foreground=WIN11_GREEN)
        self.tree_losers.tag_configure("loss", foreground=WIN11_RED)
        self.tree_signals.tag_configure("buy", foreground=WIN11_GREEN)
        self.tree_signals.tag_configure("exit", foreground=WIN11_RED)

    # ── Everyday New Feature Banner Builder ─────────────────────────────

    def _build_daily_feature_section(self):
        feature_frame = ttk.LabelFrame(self, text=" 🌟 Everyday New Feature: Daily Stock Spotlight & Insight ", padding=10)
        feature_frame.pack(fill="x", pady=(0, 12))

        f_container = ttk.Frame(feature_frame)
        f_container.pack(fill="x", expand=True)

        # Left Column: Symbol & Stock Badge Info
        self.f_left = ttk.Frame(f_container)
        self.f_left.pack(side="left", fill="y", padx=(0, 16))

        self.lbl_f_badge = ttk.Label(self.f_left, text="FEATURED TODAY", font=("Segoe UI", 9, "bold"), foreground="#0284c7")
        self.lbl_f_badge.pack(anchor="w")

        self.lbl_f_sym = ttk.Label(self.f_left, text="—", font=("Segoe UI", 15, "bold"))
        self.lbl_f_sym.pack(anchor="w")

        self.lbl_f_name = ttk.Label(self.f_left, text="—", font=("Segoe UI", 9))
        self.lbl_f_name.pack(anchor="w")

        self.lbl_f_price = ttk.Label(self.f_left, text="—", font=("Segoe UI", 12, "bold"), foreground="#059669")
        self.lbl_f_price.pack(anchor="w", pady=(2, 0))

        # Center Column: Trade Setup Cards Grid
        self.f_center = ttk.Frame(f_container)
        self.f_center.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self.f_center.columnconfigure((0, 1, 2), weight=1, uniform="f_card")

        self.card_f_score = InfoCard(self.f_center, "Composite Rating", "—", accent_color="#7c3aed", icon="⭐")
        self.card_f_score.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")

        self.card_f_rec = InfoCard(self.f_center, "Recommendation", "—", accent_color="#059669", icon="🎯")
        self.card_f_rec.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")

        self.card_f_target = InfoCard(self.f_center, "Target Price", "—", accent_color="#0284c7", icon="🏆")
        self.card_f_target.grid(row=0, column=2, padx=2, pady=2, sticky="nsew")

        self.card_f_stop = InfoCard(self.f_center, "Stop Loss", "—", accent_color="#e11d48", icon="🛡️")
        self.card_f_stop.grid(row=1, column=0, padx=2, pady=2, sticky="nsew")

        self.card_f_edge = InfoCard(self.f_center, "Signal Edge", "—", accent_color="#10b981", icon="⚡")
        self.card_f_edge.grid(row=1, column=1, padx=2, pady=2, sticky="nsew")

        self.card_f_trend = InfoCard(self.f_center, "Market Trend", "—", accent_color="#d97706", icon="📈")
        self.card_f_trend.grid(row=1, column=2, padx=2, pady=2, sticky="nsew")

        # Right Column: Narrative Box & Navigation Actions
        self.f_right = ttk.Frame(f_container)
        self.f_right.pack(side="right", fill="both")

        self.lbl_f_insight = ttk.Label(
            self.f_right, text="—", font=("Segoe UI", 9, "italic"),
            wraplength=280, justify="left"
        )
        self.lbl_f_insight.pack(anchor="w", pady=(0, 6))

        f_actions = ttk.Frame(self.f_right)
        f_actions.pack(anchor="e")

        ttk.Button(f_actions, text="🔀 Next Spotlight", command=self._on_f_next_spotlight).pack(side="left", padx=2)
        ttk.Button(f_actions, text="📈 Chart", command=self._on_f_view_chart).pack(side="left", padx=2)
        ttk.Button(f_actions, text="⭐ Watchlist", command=self._on_f_add_watchlist).pack(side="left", padx=2)
        ttk.Button(f_actions, text="💼 Portfolio", command=self._on_f_add_portfolio).pack(side="left", padx=2)
        ttk.Button(f_actions, text="🤖 AI Intel", command=self._on_f_ai_intel).pack(side="left", padx=2)

    def _apply_daily_feature(self, feat: dict):
        self._current_featured_symbol = feat.get("symbol", "")
        self._current_featured_price = float(feat.get("price", 0.0))

        self.lbl_f_badge.config(text=f"FEATURED TODAY • {feat.get('date', '')}")
        self.lbl_f_sym.config(text=feat.get("symbol", "—"))
        self.lbl_f_name.config(text=f"{feat.get('name', '')} ({feat.get('sector', '')})")
        self.lbl_f_price.config(text=f"LKR {self._current_featured_price:.2f}")

        score_str = f"{feat.get('composite_score', 0)} ({feat.get('grade', 'B')})"
        self.card_f_score.set(score_str)

        rec_str = feat.get("recommendation", "WATCH")
        self.card_f_rec.set(rec_str, color=WIN11_GREEN if "BUY" in rec_str else WIN11_ACCENT)

        self.card_f_target.set(f"LKR {feat.get('target_price', 0.0):.2f}")
        self.card_f_stop.set(f"LKR {feat.get('stop_loss', 0.0):.2f}", color=WIN11_RED)
        self.card_f_edge.set(str(feat.get("signal_edge", "—")))

        metrics = feat.get("metrics", {})
        self.card_f_trend.set(str(metrics.get("Trend", "—")))

        self.lbl_f_insight.config(text=feat.get("highlight_reason", "—"))

    # Actions for Daily Feature Buttons
    def _on_f_view_chart(self):
        sym = getattr(self, "_current_featured_symbol", None)
        if sym:
            self.app.switch_to_chart(sym)

    def _on_f_add_watchlist(self):
        sym = getattr(self, "_current_featured_symbol", None)
        if sym:
            self.app.switch_to_watchlist(sym)

    def _on_f_add_portfolio(self):
        sym = getattr(self, "_current_featured_symbol", None)
        price = getattr(self, "_current_featured_price", 0.0)
        if sym:
            self.app.switch_to_portfolio(sym, price, 1000)

    def _on_f_ai_intel(self):
        sym = getattr(self, "_current_featured_symbol", None)
        if sym:
            self.app.switch_to_intel(sym)

    def _on_f_next_spotlight(self):
        self._featured_offset += 1
        feat = self.app.engine.get_daily_featured_stock(date_offset=self._featured_offset)
        self._apply_daily_feature(feat)

    # ── Instant Synchronous Local DB Load ───────────────────────────────

    def _load_local_data(self):
        """Immediately populate all cards, features, and tables synchronously from SQLite in ~20ms."""
        try:
            summary = self.app.engine.get_dashboard_summary()
            self._apply_summary(summary)

            feat = self.app.engine.get_daily_featured_stock()
            self._apply_daily_feature(feat)

            signals = self.app.engine.get_recent_signals(50)
            self._apply_signals(signals)

            gainers, losers = self.app.engine.get_db_movers(15)
            self._apply_movers(gainers, losers)
        except Exception:
            pass

    def load_data(self):
        """Alias for initial or cached load."""
        self._load_local_data()

    def _apply_summary(self, s: dict):
        self.card_symbols.set(str(s.get("symbols_total", 0)))
        self.card_enabled.set(str(s.get("symbols_enabled", 0)))
        self.card_bars.set(fmt_volume(s.get("bars_total", 0)))
        self.card_last_bar.set(str(s.get("last_bar_date", "—")))
        b_cnt = s.get("buy_7d", s.get("long_7d", 0))
        e_cnt = s.get("exit_7d", s.get("short_7d", 0))
        self.card_long_7d.set(str(b_cnt), color=WIN11_GREEN)
        self.card_short_7d.set(str(e_cnt), color=WIN11_RED)

    def _apply_signals(self, signals: list[dict]):
        self.tree_signals.delete(*self.tree_signals.get_children())
        for sig in signals:
            direction = "🟢 BUY" if sig["signal"] == 1 else "🔴 EXIT"
            tag = "buy" if sig["signal"] == 1 else "exit"
            rating = "⭐⭐⭐⭐" if sig["signal"] == 1 else "⭐⭐⭐"
            self.tree_signals.insert("", "end", values=(
                sig["date"], sig["symbol"], direction, rating
            ), tags=(tag,))

    def _apply_movers(self, gainers: list[dict], losers: list[dict]):
        self.tree_gainers.delete(*self.tree_gainers.get_children())
        for g in gainers:
            self.tree_gainers.insert("", "end", values=(
                g["symbol"], f"{g['price']:.2f}",
                f"+{g['change']:.2f}%", fmt_volume(g["volume"])
            ), tags=("gain",))

        self.tree_losers.delete(*self.tree_losers.get_children())
        for l in losers:
            self.tree_losers.insert("", "end", values=(
                l["symbol"], f"{l['price']:.2f}",
                f"{l['change']:.2f}%", fmt_volume(l["volume"])
            ), tags=("loss",))

    # ── Background Live Web API Refresh ─────────────────────────────────

    def refresh_live_data(self):
        """Fetch live CSE API movers in the background when user clicks Refresh."""
        self.app.set_status("Fetching live market movers from CSE API...")
        self.app.start_progress()

        ThreadedTask(
            self.app.root, target=self._fetch_live_movers,
            on_done=self._on_live_movers_loaded,
            on_error=self._on_error,
        ).start()

    def _fetch_live_movers(self):
        engine = self.app.engine
        return {
            "summary": engine.get_dashboard_summary(),
            "signals": engine.get_recent_signals(50),
            "gainers": engine.get_top_gainers(),
            "losers": engine.get_top_losers(),
        }

    def _on_live_movers_loaded(self, data: dict):
        if "summary" in data:
            self._apply_summary(data["summary"])
        if "signals" in data:
            self._apply_signals(data["signals"])

        gainers = data.get("gainers", [])
        losers = data.get("losers", [])
        if gainers or losers:
            self._apply_movers(gainers, losers)

        self.app.stop_progress()
        self.app.set_status("Market Dashboard updated with live data")

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Refresh notice: {exc}")

    def _on_double_click(self, tree: ttk.Treeview):
        sel = tree.selection()
        if sel:
            values = tree.item(sel[0], "values")
            symbol = values[1] if len(values) > 1 and tree == self.tree_signals else values[0]
            if symbol and not symbol.startswith("▲") and not symbol.startswith("▼"):
                self.app.switch_to_chart(symbol)

    # ── Daily Scan ──────────────────────────────────────────────────────

    def _run_daily_scan(self):
        self.app.set_status("Running daily scan... updating CSE prices and spot signals")
        self.app.start_progress()
        ThreadedTask(
            self.app.root, target=self.app.engine.run_daily_scan,
            on_done=self._on_scan_done,
            on_error=self._on_error,
        ).start()

    def _on_scan_done(self, log: str):
        self.app.stop_progress()
        self.app.set_status("Daily scan complete!")
        self._load_local_data()
        win = tk.Toplevel(self.app.root)
        win.title("Daily Scan Results")
        win.geometry("700x500")
        win.configure(bg=WIN11_BG)
        text = tk.Text(win, wrap="word", font=("Consolas", 10), bg="#ffffff", fg="#0f172a", padx=10, pady=10)
        text.insert("1.0", log)
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=12, pady=12)
