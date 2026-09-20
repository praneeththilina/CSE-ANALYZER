# views/chart.py  –  Interactive Charts Tab (Windows 11 Light)
"""
Candlestick + volume chart with QQE indicator overlay, using matplotlib
and mplfinance embedded in a tkinter canvas styled for Windows 11 Light.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ui_utils import ThreadedTask, FormCard, WIN11_BG, WIN11_CARD_BG, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED, FONT_TITLE

if TYPE_CHECKING:
    from app import MainApp

# Matplotlib setup for tkinter embedding
import logging
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import mplfinance as mpf


class ChartTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._current_symbol = ""
        self._build_ui()

    def _build_ui(self):
        # ── Controls Colorful Form Card ─────────────────────────────────
        self.ctrl_card = FormCard(
            self,
            title="Chart Display & Indicators",
            accent_color="#0067c0",
            bg_color="#f0f7ff",
            border_color="#93c5fd",
            icon="📈",
        )
        self.ctrl_card.pack(fill="x", pady=(0, 10))

        ctrl = tk.Frame(self.ctrl_card.body, bg="#f0f7ff")
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Symbol:", font=("Segoe UI Semibold", 9), bg="#f0f7ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 6))

        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(ctrl, textvariable=self.symbol_var, width=16, font=("Segoe UI", 9))
        self.symbol_combo.pack(side="left", padx=(0, 8))
        self.symbol_combo.bind("<<ComboboxSelected>>", lambda e: self._on_load())
        self.symbol_combo.bind("<Return>", lambda e: self._on_load())

        ttk.Button(ctrl, text="📈 Load Chart", style="Accent.TButton", command=self._on_load).pack(side="left", padx=4)

        # Period selector
        ttk.Separator(ctrl, orient="vertical").pack(side="left", fill="y", padx=12)
        tk.Label(ctrl, text="Period:", font=("Segoe UI Semibold", 9), bg="#f0f7ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.period_var = tk.StringVar(value="1Y")
        for p in ["1M", "3M", "6M", "1Y", "All"]:
            ttk.Radiobutton(ctrl, text=p, variable=self.period_var, value=p,
                            command=self._on_load).pack(side="left", padx=3)

        # Indicator toggles
        ttk.Separator(ctrl, orient="vertical").pack(side="left", fill="y", padx=12)
        self.show_ma_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="MA 50/200", variable=self.show_ma_var,
                        command=self._on_load).pack(side="left", padx=4)
        self.show_qqe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="QQE Signals", variable=self.show_qqe_var,
                        command=self._on_load).pack(side="left", padx=4)

        # ── Chart Canvas Area ───────────────────────────────────────────
        self.chart_frame = tk.Frame(self, bg=WIN11_CARD_BG, highlightbackground="#cbd5e1",
                                    highlightthickness=1, bd=0)
        self.chart_frame.pack(fill="both", expand=True)

        # Placeholder label
        self._placeholder = tk.Label(
            self.chart_frame,
            text="Select a CSE symbol and click 'Load Chart' to visualize candles & QQE signals",
            font=("Segoe UI", 11), fg=WIN11_TEXT_MUTED, bg=WIN11_CARD_BG,
            anchor="center",
        )
        self._placeholder.pack(expand=True)

        self._canvas = None
        self._toolbar = None

        # Pre-populate symbols immediately
        self._load_symbols_list()

    def on_tab_shown(self):
        if not self.symbol_combo["values"]:
            self._load_symbols_list()

    def _load_symbols_list(self):
        try:
            symbols = self.app.engine.get_symbol_list()
            self.symbol_combo["values"] = symbols
            if symbols and not self.symbol_var.get():
                self.symbol_combo.current(0)
        except Exception:
            pass

    # ── Public method for cross-tab navigation ──────────────────────────

    def load_symbol(self, symbol: str):
        self.symbol_var.set(symbol)
        self._on_load()

    # ── Chart Loading ───────────────────────────────────────────────────

    def _on_load(self, *_):
        symbol = self.symbol_var.get().strip().upper()
        if not symbol:
            return
        self.symbol_var.set(symbol)
        self._current_symbol = symbol
        period = self.period_var.get()
        show_qqe = self.show_qqe_var.get()
        self.app.set_status(f"Loading chart for {symbol}...")
        self.app.start_progress()
        ThreadedTask(
            self.app.root,
            target=self._fetch_chart_data, args=(symbol, period, show_qqe),
            on_done=self._render_chart,
            on_error=self._on_error,
        ).start()

    def _fetch_chart_data(self, symbol: str, period: str, show_qqe: bool) -> dict:
        import stocks
        df = self.app.engine.get_bars(symbol)
        if df.empty:
            raise ValueError(f"No historical price bars found for {symbol}")

        # Apply period filter
        if period != "All":
            days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}[period]
            cutoff = df.index[-1] - pd.Timedelta(days=days)
            df = df[df.index >= cutoff]

        result = {"df": df, "symbol": symbol}

        # QQE signals
        if show_qqe:
            try:
                con = self.app.engine.connect()
                closes = stocks.get_symbol_closes(con, symbol)
                con.close()
                if len(closes) >= 60:
                    qqe = stocks.compute_qqe_from_closes(closes)
                    qqe_df = pd.concat([closes.rename("close"), qqe], axis=1).dropna(subset=["close"])
                    if period != "All":
                        qqe_df = qqe_df[qqe_df.index >= df.index[0]]
                    result["qqe"] = qqe_df
            except Exception:
                pass

        return result

    def _render_chart(self, data: dict):
        df = data["df"]
        symbol = data["symbol"]

        # Clean up old canvas
        if self._canvas:
            self._canvas.get_tk_widget().destroy()
        if self._toolbar:
            self._toolbar.destroy()
        self._placeholder.pack_forget()

        # Build OHLCV DataFrame for mplfinance
        ohlcv = df[["open", "high", "low", "close", "volume"]].copy()
        ohlcv.index = pd.DatetimeIndex(ohlcv.index)

        # Crisp Windows 11 Light Theme for Matplotlib
        mc = mpf.make_marketcolors(
            up="#0e700e",
            down="#d13438",
            edge={"up": "#0e700e", "down": "#d13438"},
            wick={"up": "#0e700e", "down": "#d13438"},
            volume={"up": "#0e700e70", "down": "#d1343870"},
        )
        style = mpf.make_mpf_style(
            base_mpf_style="classic",
            marketcolors=mc,
            facecolor="#ffffff",
            edgecolor="#e2e8f0",
            figcolor="#ffffff",
            gridcolor="#f1f5f9",
            gridstyle="--",
            rc={
                "axes.labelcolor": "#475569",
                "xtick.color": "#64748b",
                "ytick.color": "#64748b",
                "axes.edgecolor": "#cbd5e1",
            }
        )

        # Additional plots
        addplots = []

        # Moving averages
        if self.show_ma_var.get() and len(ohlcv) > 50:
            ma50 = ohlcv["close"].rolling(50).mean()
            addplots.append(mpf.make_addplot(ma50, color="#d97706", width=1.2, linestyle="--", label="MA50"))
            if len(ohlcv) > 200:
                ma200 = ohlcv["close"].rolling(200).mean()
                addplots.append(mpf.make_addplot(ma200, color="#0284c7", width=1.2, linestyle="--", label="MA200"))

        # QQE signal markers
        if "qqe" in data and self.show_qqe_var.get():
            qqe_df = data["qqe"]
            buy_signals = pd.Series(np.nan, index=ohlcv.index)
            sell_signals = pd.Series(np.nan, index=ohlcv.index)
            for idx in qqe_df.index:
                if idx in ohlcv.index:
                    sig = qqe_df.loc[idx, "signal"]
                    if sig == 1:
                        buy_signals[idx] = ohlcv.loc[idx, "low"] * 0.98
                    elif sig == -1:
                        sell_signals[idx] = ohlcv.loc[idx, "high"] * 1.02

            if buy_signals.notna().any():
                addplots.append(mpf.make_addplot(
                    buy_signals, type="scatter", marker="^",
                    markersize=90, color="#0e700e"
                ))
            if sell_signals.notna().any():
                addplots.append(mpf.make_addplot(
                    sell_signals, type="scatter", marker="v",
                    markersize=90, color="#d13438"
                ))

        # Create the chart
        plot_kwargs = {
            "type": "candle",
            "style": style,
            "volume": True,
            "title": f"\n{symbol}",
            "figsize": (12, 7),
            "returnfig": True,
            "panel_ratios": (4, 1),
        }
        if addplots:
            plot_kwargs["addplot"] = addplots

        fig, axes = mpf.plot(ohlcv, **plot_kwargs)

        # Style the title
        fig.suptitle(symbol, fontsize=13, fontweight="bold", color="#0f172a", y=0.98)

        # Embed in tkinter
        self._canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        self._toolbar = NavigationToolbar2Tk(self._canvas, self.chart_frame)
        self._toolbar.config(background="#ffffff")
        self._toolbar.update()

        self.app.stop_progress()
        self.app.set_status(f"Chart loaded: {symbol} ({len(ohlcv)} bars)")
        plt.close(fig)

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Chart error: {exc}")
