# views/dashboard.py  –  Market Dashboard Tab (Windows 11 Light - Instant Cohesive Load)
"""
Landing screen showing market overview: summary cards, top gainers/losers,
recent QQE signals, and quick stats styled for Windows 11 Fluent Light.
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

        self.card_enabled = InfoCard(cards_frame, "Enabled (QQE)", "—", accent_color="#4f46e5", icon="⚡")
        self.card_enabled.grid(row=0, column=1, padx=4, pady=2, sticky="nsew")

        self.card_bars = InfoCard(cards_frame, "Total Bars", "—", accent_color="#7c3aed", icon="📊")
        self.card_bars.grid(row=0, column=2, padx=4, pady=2, sticky="nsew")

        self.card_last_bar = InfoCard(cards_frame, "Last Bar Date", "—", accent_color="#d97706", icon="📅")
        self.card_last_bar.grid(row=0, column=3, padx=4, pady=2, sticky="nsew")

        self.card_long_7d = InfoCard(cards_frame, "Long Signals (7d)", "—", accent_color="#059669", icon="▲")
        self.card_long_7d.grid(row=0, column=4, padx=4, pady=2, sticky="nsew")

        self.card_short_7d = InfoCard(cards_frame, "Short Signals (7d)", "—", accent_color="#e11d48", icon="▼")
        self.card_short_7d.grid(row=0, column=5, padx=4, pady=2, sticky="nsew")

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
        signals_frame = ttk.LabelFrame(content, text="  🔔 Recent Signals  ", padding=8)
        signals_frame.grid(row=0, column=2, padx=(6, 0), pady=4, sticky="nsew")

        cols_sig = ("date", "symbol", "direction", "rating")
        self.tree_signals = SortableTreeview(signals_frame, columns=cols_sig, height=14)
        self.tree_signals.heading("date", text="Date")
        self.tree_signals.heading("symbol", text="Symbol")
        self.tree_signals.heading("direction", text="Signal")
        self.tree_signals.heading("rating", text="Rating")
        self.tree_signals.column("date", width=85, minwidth=75)
        self.tree_signals.column("symbol", width=95, minwidth=75)
        self.tree_signals.column("direction", width=75, minwidth=60, anchor="center")
        self.tree_signals.column("rating", width=75, minwidth=60, anchor="center")
        self.tree_signals.pack(fill="both", expand=True)
        self.tree_signals.bind("<Double-1>", lambda e: self._on_double_click(self.tree_signals))

        # Tag styles for tables
        self.tree_gainers.tag_configure("gain", foreground=WIN11_GREEN)
        self.tree_losers.tag_configure("loss", foreground=WIN11_RED)
        self.tree_signals.tag_configure("long", foreground=WIN11_GREEN)
        self.tree_signals.tag_configure("short", foreground=WIN11_RED)

    # ── Instant Synchronous Local DB Load ───────────────────────────────

    def _load_local_data(self):
        """Immediately populate all 6 cards and all 3 tables synchronously from SQLite in ~20ms."""
        try:
            summary = self.app.engine.get_dashboard_summary()
            self._apply_summary(summary)

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
        self.card_long_7d.set(str(s.get("long_7d", 0)), color=WIN11_GREEN)
        self.card_short_7d.set(str(s.get("short_7d", 0)), color=WIN11_RED)

    def _apply_signals(self, signals: list[dict]):
        self.tree_signals.delete(*self.tree_signals.get_children())
        for sig in signals:
            direction = "▲ LONG" if sig["signal"] == 1 else "▼ SHORT"
            tag = "long" if sig["signal"] == 1 else "short"
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
        self.app.set_status("Running daily scan... updating CSE prices and QQE signals")
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
