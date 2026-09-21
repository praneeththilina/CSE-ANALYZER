# app.py  –  Main Application Window (Fast & Native Responsive)
"""
Creates the root ttk.Notebook with all 7 tabs, persistent status bar,
and on-demand lazy tab loading for instantaneous native responsiveness.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core.data_engine import DataEngine
from ui_utils import StatusBar

from views.dashboard import DashboardTab
from views.scanner import ScannerTab
from views.chart import ChartTab
from views.watchlist import WatchlistTab
from views.market_intel import MarketIntelTab
from views.portfolio import PortfolioTab
from views.backtest import BacktestTab
from views.ai_analysis import AIAnalysisTab
from views.settings import SettingsTab


class MainApp(ttk.Frame):
    """Top-level application frame containing the tab notebook + status bar."""

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.root = root
        self.engine = DataEngine()
        self._loaded_tabs: set[ttk.Frame] = set()

        # ── Notebook (tabs) ─────────────────────────────────────────────
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=(4, 0))

        # Create each tab
        self.dashboard = DashboardTab(self.notebook, self)
        self.scanner = ScannerTab(self.notebook, self)
        self.chart = ChartTab(self.notebook, self)
        self.watchlist = WatchlistTab(self.notebook, self)
        self.market_intel = MarketIntelTab(self.notebook, self)
        self.portfolio = PortfolioTab(self.notebook, self)
        self.backtest = BacktestTab(self.notebook, self)
        self.ai_analysis = AIAnalysisTab(self.notebook, self)
        self.settings = SettingsTab(self.notebook, self)

        self.notebook.add(self.dashboard, text="  📊 Dashboard  ")
        self.notebook.add(self.scanner, text="  🔍 Stock Scanner  ")
        self.notebook.add(self.chart, text="  📈 Charts  ")
        self.notebook.add(self.watchlist, text="  ⭐ Watchlist  ")
        self.notebook.add(self.market_intel, text="  🏛️ Market Intel  ")
        self.notebook.add(self.portfolio, text="  💼 Portfolio  ")
        self.notebook.add(self.backtest, text="  ⚡ Backtest  ")
        self.notebook.add(self.ai_analysis, text="  🤖 AI Analysis  ")
        self.notebook.add(self.settings, text="  ⚙ Settings  ")

        # Bind lazy loading on tab switch
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # ── Status Bar ──────────────────────────────────────────────────
        self.status_bar = StatusBar(self)
        self.status_bar.pack(fill="x", side="bottom")

        # ── Dashboard immediate load ────────────────────────────────────
        self._loaded_tabs.add(self.dashboard)
        self.dashboard.load_data()

    def _on_tab_changed(self, event=None):
        try:
            sel = self.notebook.select()
            if not sel:
                return
            current_widget = self.notebook.nametowidget(sel)
            if current_widget not in self._loaded_tabs:
                self._loaded_tabs.add(current_widget)
                if hasattr(current_widget, "on_tab_shown"):
                    current_widget.on_tab_shown()
        except Exception:
            pass

    def switch_to_chart(self, symbol: str, entry: float | None = None, stop_loss: float | None = None):
        """Switch to the Charts tab and load a specific symbol with optional trade levels."""
        self.notebook.select(self.chart)
        self.chart.load_symbol(symbol, entry=entry, stop_loss=stop_loss)

    def switch_to_portfolio(self, symbol: str, price: float, qty: int):
        """Switch to Portfolio tab and pre-fill trade details."""
        self.notebook.select(self.portfolio)
        self.portfolio.prefill(symbol, price, qty)

    def switch_to_watchlist(self, symbol: str | None = None):
        """Switch to Watchlist tab and optionally select/prefill a symbol."""
        self.notebook.select(self.watchlist)
        if symbol:
            self.watchlist.sym_var.set(symbol)

    def switch_to_intel(self, symbol: str | None = None):
        """Switch to Market Intel tab and optionally analyze a symbol."""
        self.notebook.select(self.market_intel)
        if symbol:
            self.market_intel.sym_var.set(symbol)
            self.market_intel.load_symbol_intel()

    def set_status(self, message: str):
        self.status_bar.set_message(message)

    def start_progress(self):
        self.status_bar.start_progress()

    def stop_progress(self):
        self.status_bar.stop_progress()
