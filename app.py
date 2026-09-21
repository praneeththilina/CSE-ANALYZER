# app.py  –  Main Application Window (Windows 11 Fluent Layout & 0-Lag Architecture)
"""
Windows 11 Fluent layout architecture featuring:
1. Left Navigation Rail (NavRail) with active indicator pill.
2. Top Action Bar with debounced Symbol Search, Market Status, and Dark/Light Mode toggle.
3. 0-Lag Page Swapper (pack/pack_forget with cached views).
4. Persistent Windows 11 Status Bar with data freshness & progress tracking.
"""
from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Set

from core.data_engine import DataEngine
from ui.theme.tokens import ThemeManager, get_token, FONTS
from ui.theme.styles import apply_theme
from ui.components.nav_rail import NavRail
from ui.components.search_box import SearchBox
from ui.components.toast import show_toast
from ui.components.buttons import GhostButton, IconButton
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


class NotebookCompat:
    """Backward compatibility shim so legacy self.notebook.select(tab) calls route cleanly."""
    def __init__(self, app: MainApp):
        self._app = app

    def select(self, tab_or_id: Optional[tk.Widget] = None):
        if tab_or_id is None:
            active_page = self._app.get_active_page()
            return str(active_page) if active_page else ""
        self._app.switch_to_tab(tab_or_id)

    def nametowidget(self, name: str) -> tk.Widget:
        return self._app.get_active_page()


class MainApp(tk.Frame):
    """Top-level application window with Left NavRail and 0-lag Page Swapper."""

    def __init__(self, root: tk.Tk):
        tokens = ThemeManager.tokens()
        super().__init__(root, bg=tokens["bg"])
        self.root = root
        self.engine = DataEngine()

        self._loaded_pages: Set[tk.Widget] = set()
        self._current_page_key: str = "dashboard"
        self._pages: Dict[str, tk.Widget] = {}

        # Backward compatibility shim for notebook calls
        self.notebook = NotebookCompat(self)

        # ── 1. Main Horizontal Split (NavRail + Right Area) ─────────────
        self._main_split = tk.Frame(self, bg=tokens["bg"])
        self._main_split.pack(fill="both", expand=True)

        # Left NavRail
        nav_items = [
            ("dashboard", "📊", "Dashboard"),
            ("scanner", "🔍", "Stock Scanner"),
            ("chart", "📈", "Charts"),
            ("watchlist", "⭐", "Watchlist"),
            ("market_intel", "🏛️", "Market Intel"),
            ("portfolio", "💼", "Portfolio"),
            ("backtest", "⚡", "Backtest"),
            ("ai_analysis", "🤖", "AI Analysis"),
            ("settings", "⚙️", "Settings"),
        ]

        self.nav_rail = NavRail(
            self._main_split,
            items=nav_items,
            on_navigate=self._on_nav_navigate,
            width=200
        )
        self.nav_rail.pack(side="left", fill="y")

        # Right Vertical Area (TopBar + ContentArea)
        self._right_area = tk.Frame(self._main_split, bg=tokens["bg"])
        self._right_area.pack(side="right", fill="both", expand=True)

        # ── 2. Top Action Bar ───────────────────────────────────────────
        self._build_top_bar()

        # ── 3. Central Content Area (Page Swapping Container) ───────────
        self.content_area = tk.Frame(self._right_area, bg=tokens["bg"])
        self.content_area.pack(fill="both", expand=True, padx=8, pady=(4, 6))

        # Build and cache all 9 page instances
        self.dashboard = DashboardTab(self.content_area, self)
        self.scanner = ScannerTab(self.content_area, self)
        self.chart = ChartTab(self.content_area, self)
        self.watchlist = WatchlistTab(self.content_area, self)
        self.market_intel = MarketIntelTab(self.content_area, self)
        self.portfolio = PortfolioTab(self.content_area, self)
        self.backtest = BacktestTab(self.content_area, self)
        self.ai_analysis = AIAnalysisTab(self.content_area, self)
        self.settings = SettingsTab(self.content_area, self)

        self._pages = {
            "dashboard": self.dashboard,
            "scanner": self.scanner,
            "chart": self.chart,
            "watchlist": self.watchlist,
            "market_intel": self.market_intel,
            "portfolio": self.portfolio,
            "backtest": self.backtest,
            "ai_analysis": self.ai_analysis,
            "settings": self.settings,
        }

        # ── 4. Persistent Status Bar ────────────────────────────────────
        self.status_bar = StatusBar(self)
        self.status_bar.pack(fill="x", side="bottom")

        # Display initial page (Dashboard)
        self._show_page("dashboard")
        self._loaded_pages.add(self.dashboard)
        self.dashboard.load_data()

        # Feed universe to top search bar
        all_symbols = self.engine.get_symbol_list()
        self.search_box.set_universe(all_symbols)

        ThemeManager.register_listener(self._on_theme_change)

    # ── Top Bar Construction ────────────────────────────────────────────

    def _build_top_bar(self):
        tokens = ThemeManager.tokens()
        self.top_bar = tk.Frame(
            self._right_area,
            bg=tokens["surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            padx=12,
            pady=8
        )
        self.top_bar.pack(fill="x", padx=8, pady=(6, 0))

        # Left of top bar: Debounced Search Box
        self.search_box = SearchBox(
            self.top_bar,
            placeholder="Search stock (e.g. COMB, JKH, SAMP)...",
            on_select=self._on_search_select,
            width=28
        )
        self.search_box.pack(side="left", padx=(0, 16))

        # Live Market Status Pill
        self._market_pill = tk.Label(
            self.top_bar,
            text=self._get_market_status_text(),
            font=FONTS["caption"],
            fg=tokens["gain"],
            bg=tokens["surface_hi"],
            padx=8,
            pady=4,
            relief="solid",
            bd=0
        )
        self._market_pill.pack(side="left", padx=(0, 12))

        # Current Date & SLT Time
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %d %b %Y")
        self._date_label = tk.Label(
            self.top_bar,
            text=f"📅 {date_str}",
            font=FONTS["caption"],
            fg=tokens["text_dim"],
            bg=tokens["surface"]
        )
        self._date_label.pack(side="left")

        # Right of top bar: Theme Toggle and Quick Refresh Buttons
        self._theme_btn = GhostButton(
            self.top_bar,
            text="Dark Mode" if ThemeManager.get_mode() == "light" else "Light Mode",
            icon="🌙" if ThemeManager.get_mode() == "light" else "☀️",
            command=self.toggle_theme,
            padx=10,
            pady=4
        )
        self._theme_btn.pack(side="right", padx=(8, 0))

        self._refresh_btn = GhostButton(
            self.top_bar,
            text="Refresh",
            icon="🔄",
            command=self._on_quick_refresh,
            padx=10,
            pady=4
        )
        self._refresh_btn.pack(side="right")

    def _get_market_status_text(self) -> str:
        now = datetime.datetime.now()
        # CSE Trading Hours: Mon-Fri 09:30 - 14:30 SLT
        is_weekday = now.weekday() < 5
        curr_time = now.time()
        market_open = datetime.time(9, 30)
        market_close = datetime.time(14, 30)

        if is_weekday and market_open <= curr_time <= market_close:
            return "● CSE Market Open (09:30 - 14:30 SLT)"
        return "○ CSE Market Closed"

    # ── Page Swapping & Routing (0 Lag) ─────────────────────────────────

    def _on_nav_navigate(self, key: str):
        self._show_page(key)

    def _show_page(self, key: str):
        """Swap content area page with zero redraw flicker."""
        if key not in self._pages:
            return

        # Hide all pages
        for p_key, page in self._pages.items():
            page.pack_forget()

        # Reveal target page
        target_page = self._pages[key]
        target_page.pack(fill="both", expand=True)
        self._current_page_key = key

        # Lazy activation call on first or active view
        if hasattr(target_page, "on_tab_shown"):
            try:
                target_page.on_tab_shown()
            except Exception:
                pass

        self._loaded_pages.add(target_page)

    def switch_to_tab(self, tab_widget: tk.Widget):
        for key, page in self._pages.items():
            if page == tab_widget:
                self.nav_rail.select(key)
                return

    def _on_tab_changed(self, event=None):
        """Backward compatibility for legacy notebook tab change callbacks."""
        active = self.get_active_page()
        if active and hasattr(active, "on_tab_shown"):
            try:
                active.on_tab_shown()
            except Exception:
                pass

    def get_active_page(self) -> Optional[tk.Widget]:
        return self._pages.get(self._current_page_key)


    def _on_search_select(self, symbol: str):
        """User selected a symbol in the top search bar -> navigate to Charts and load it."""
        sym = symbol.strip().upper()
        if not sym:
            return
        self.switch_to_chart(sym)
        show_toast(self.root, f"Loaded technical analysis and chart for {sym}", title="Symbol Selected", kind="info")

    def _on_quick_refresh(self):
        """Global quick refresh."""
        self.set_status("Refreshing market data and scanner...")
        self.start_progress()
        if hasattr(self.dashboard, "refresh_live_data"):
            self.dashboard.refresh_live_data()
        show_toast(self.root, "Refreshing CSE market movers & sector data...", title="Syncing", kind="info")

    # ── Theme Toggle & Synchronization ──────────────────────────────────

    def toggle_theme(self):
        """Toggle between Light and Dark mode with live title-bar sync."""
        new_mode = ThemeManager.toggle()
        apply_theme(self.root, new_mode)

        # Update theme button label and icon
        self._theme_btn.configure(
            text="Light Mode" if new_mode == "dark" else "Dark Mode"
        )
        show_toast(
            self.root,
            f"Applied Windows 11 {new_mode.capitalize()} theme.",
            title="Theme Changed",
            kind="success"
        )

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["bg"])
        self._main_split.configure(bg=tokens["bg"])
        self._right_area.configure(bg=tokens["bg"])
        self.top_bar.configure(bg=tokens["surface"], highlightbackground=tokens["border"])
        self.content_area.configure(bg=tokens["bg"])
        self._market_pill.configure(bg=tokens["surface_hi"])
        self._date_label.configure(bg=tokens["surface"], fg=tokens["text_dim"])

    # ── External Navigation Helpers ─────────────────────────────────────

    def switch_to_chart(self, symbol: str, entry: float | None = None, stop_loss: float | None = None):
        """Switch to the Charts tab and load a specific symbol with optional trade levels."""
        self.nav_rail.select("chart")
        self.chart.load_symbol(symbol, entry=entry, stop_loss=stop_loss)

    def switch_to_portfolio(self, symbol: str, price: float, qty: int):
        """Switch to Portfolio tab and pre-fill trade details."""
        self.nav_rail.select("portfolio")
        self.portfolio.prefill(symbol, price, qty)

    def switch_to_watchlist(self, symbol: str | None = None):
        """Switch to Watchlist tab and optionally select/prefill a symbol."""
        self.nav_rail.select("watchlist")
        if symbol:
            self.watchlist.sym_var.set(symbol)

    def switch_to_intel(self, symbol: str | None = None):
        """Switch to Market Intel tab and optionally analyze a symbol."""
        self.nav_rail.select("market_intel")
        if symbol:
            self.market_intel.sym_var.set(symbol)
            self.market_intel.load_symbol_intel()

    def set_status(self, message: str):
        self.status_bar.set_message(message)

    def start_progress(self):
        self.status_bar.start_progress()

    def stop_progress(self):
        self.status_bar.stop_progress()
