# views/chart.py  –  Interactive Charts & Smart Risk Calculator Tab (Windows 11 Light)
"""
Candlestick + volume chart with QQE signals, EMA 50/200, dynamic Support/Resistance,
and an integrated Smart Risk & Position Size Calculator tailored for the CSE (LKR + fees).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Dict

import numpy as np
import pandas as pd

from ui_utils import (
    ThreadedTask, FormCard,
    WIN11_BG, WIN11_CARD_BG, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED,
    WIN11_GREEN, WIN11_RED, WIN11_BORDER,
    FONT_TITLE, FONT_BODY, FONT_BODY_BOLD
)

if TYPE_CHECKING:
    from app import MainApp

# Matplotlib setup for tkinter embedding
import logging
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import mplfinance as mpf


class ChartTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._current_symbol = ""
        self._current_data: dict | None = None
        self._last_calc: dict | None = None
        self._build_ui()

    def _build_ui(self):
        # ── Controls Colorful Form Card ─────────────────────────────────
        self.ctrl_card = FormCard(
            self,
            title="Chart Display & Technical Overlays",
            accent_color="#0067c0",
            bg_color="#f0f7ff",
            border_color="#93c5fd",
            icon="📈",
        )
        self.ctrl_card.pack(fill="x", pady=(0, 8))

        ctrl = tk.Frame(self.ctrl_card.body, bg="#f0f7ff")
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Symbol:", font=("Segoe UI Semibold", 9), bg="#f0f7ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 6))

        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(ctrl, textvariable=self.symbol_var, width=15, font=("Segoe UI", 9))
        self.symbol_combo.pack(side="left", padx=(0, 8))
        self.symbol_combo.bind("<<ComboboxSelected>>", lambda e: self._on_load())
        self.symbol_combo.bind("<Return>", lambda e: self._on_load())

        ttk.Button(ctrl, text="📈 Load Chart", style="Accent.TButton", command=self._on_load).pack(side="left", padx=4)

        # Period selector
        ttk.Separator(ctrl, orient="vertical").pack(side="left", fill="y", padx=10)
        tk.Label(ctrl, text="Period:", font=("Segoe UI Semibold", 9), bg="#f0f7ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.period_var = tk.StringVar(value="1Y")
        for p in ["1M", "3M", "6M", "1Y", "All"]:
            ttk.Radiobutton(ctrl, text=p, variable=self.period_var, value=p,
                            command=self._on_load).pack(side="left", padx=2)

        # Indicator toggles
        ttk.Separator(ctrl, orient="vertical").pack(side="left", fill="y", padx=10)
        self.show_ma_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="EMA 50/200", variable=self.show_ma_var,
                        command=self._on_load).pack(side="left", padx=4)

        self.show_qqe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="QQE Signals", variable=self.show_qqe_var,
                        command=self._on_load).pack(side="left", padx=4)

        self.show_sr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="Support/Resistance", variable=self.show_sr_var,
                        command=self._on_toggle_levels).pack(side="left", padx=4)

        self.show_targets_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="Trade Targets", variable=self.show_targets_var,
                        command=self._on_toggle_levels).pack(side="left", padx=4)

        # ── Smart Risk & Position Size Calculator FormCard ─────────────
        self.risk_card = FormCard(
            self,
            title="Smart Risk & Position Size Calculator (CSE LKR + Fees)",
            accent_color="#059669",
            bg_color="#f0fdf4",
            border_color="#86efac",
            icon="⚖️",
        )
        self.risk_card.pack(fill="x", pady=(0, 8))

        # Inputs Row
        calc_row = tk.Frame(self.risk_card.body, bg="#f0fdf4")
        calc_row.pack(fill="x", pady=(0, 4))

        tk.Label(calc_row, text="Capital (LKR):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.calc_capital_var = tk.StringVar(value="500000")
        ttk.Entry(calc_row, textvariable=self.calc_capital_var, width=11).pack(side="left", padx=(0, 10))

        tk.Label(calc_row, text="Risk %:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.calc_risk_pct_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(calc_row, from_=0.5, to=10.0, increment=0.5, textvariable=self.calc_risk_pct_var, width=5).pack(side="left", padx=(0, 10))

        tk.Label(calc_row, text="Entry (LKR):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.calc_entry_var = tk.StringVar(value="")
        ttk.Entry(calc_row, textvariable=self.calc_entry_var, width=9).pack(side="left", padx=(0, 10))

        tk.Label(calc_row, text="Stop-Loss (LKR):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.calc_stop_var = tk.StringVar(value="")
        ttk.Entry(calc_row, textvariable=self.calc_stop_var, width=9).pack(side="left", padx=(0, 10))

        ttk.Button(calc_row, text="⚡ Calculate Risk", command=self._on_calc_risk).pack(side="left", padx=4)
        ttk.Button(calc_row, text="🎯 Plot on Chart", command=self._on_plot_levels).pack(side="left", padx=4)
        ttk.Button(calc_row, text="💼 Send to Portfolio", command=self._send_to_portfolio, style="Accent.TButton").pack(side="right", padx=4)

        # Output Metrics Row
        metric_row = tk.Frame(self.risk_card.body, bg="#f0fdf4")
        metric_row.pack(fill="x", pady=(2, 0))

        self.lbl_shares = tk.Label(metric_row, text="Shares: —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#059669")
        self.lbl_shares.pack(side="left", padx=(0, 14))

        self.lbl_invest = tk.Label(metric_row, text="Investment: —", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN)
        self.lbl_invest.pack(side="left", padx=(0, 14))

        self.lbl_fees = tk.Label(metric_row, text="CSE Fees (~1.12%): —", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MUTED)
        self.lbl_fees.pack(side="left", padx=(0, 14))

        self.lbl_t1 = tk.Label(metric_row, text="Target 1 (1:1.5): —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#0284c7")
        self.lbl_t1.pack(side="left", padx=(0, 14))

        self.lbl_t2 = tk.Label(metric_row, text="Target 2 (1:2.5): —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#059669")
        self.lbl_t2.pack(side="left", padx=(0, 14))

        self.lbl_loss = tk.Label(metric_row, text="Max Loss: —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#c42b1c")
        self.lbl_loss.pack(side="left", padx=(0, 10))

        # ── Chart Canvas Area ───────────────────────────────────────────
        self.chart_frame = tk.Frame(self, bg=WIN11_CARD_BG, highlightbackground="#cbd5e1",
                                    highlightthickness=1, bd=0)
        self.chart_frame.pack(fill="both", expand=True)

        self._placeholder = tk.Label(
            self.chart_frame,
            text="Select a CSE symbol and click 'Load Chart' to visualize candlesticks, signals & key levels",
            font=("Segoe UI", 11), fg=WIN11_TEXT_MUTED, bg=WIN11_CARD_BG,
            anchor="center",
        )
        self._placeholder.pack(expand=True)

        self._canvas = None
        self._toolbar = None

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

    def load_symbol(self, symbol: str, entry: float | None = None, stop_loss: float | None = None):
        self.symbol_var.set(symbol)
        if entry is not None and entry > 0:
            self.calc_entry_var.set(f"{float(entry):.2f}")
        if stop_loss is not None and stop_loss > 0:
            self.calc_stop_var.set(f"{float(stop_loss):.2f}")
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

        # Compute confluence & key levels for this symbol
        confluence = self.app.engine.compute_confluence(df, 1)

        # Apply period filter for chart display
        if period != "All":
            days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}[period]
            cutoff = df.index[-1] - pd.Timedelta(days=days)
            df = df[df.index >= cutoff]

        result = {"df": df, "symbol": symbol, "confluence": confluence}

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
        self._current_data = data
        df = data["df"]
        symbol = data["symbol"]
        confluence = data.get("confluence", {})

        # Auto-fill calculator if empty
        last_price = float(df["close"].iloc[-1])
        if not self.calc_entry_var.get():
            self.calc_entry_var.set(f"{last_price:.2f}")
        if not self.calc_stop_var.get() and confluence.get("suggested_stop"):
            self.calc_stop_var.set(f"{float(confluence['suggested_stop']):.2f}")

        # Compute risk
        self._on_calc_risk(redraw=False)

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

        addplots = []

        # Moving averages (EMA 50 & EMA 200)
        if self.show_ma_var.get() and len(ohlcv) > 20:
            ema50 = ohlcv["close"].ewm(span=50, adjust=False).mean()
            addplots.append(mpf.make_addplot(ema50, color="#d97706", width=1.3, linestyle="-", label="EMA 50"))
            if len(ohlcv) > 50:
                ema200 = ohlcv["close"].ewm(span=200, adjust=False).mean()
                addplots.append(mpf.make_addplot(ema200, color="#0284c7", width=1.4, linestyle="-", label="EMA 200"))

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

        # Horizontal Lines: Support/Resistance & Trade Targets
        hlines_list = []
        colors_list = []
        styles_list = []

        # Support & Resistance levels
        if self.show_sr_var.get() and confluence:
            s1 = confluence.get("support1", 0)
            r1 = confluence.get("resistance1", 0)
            if s1 > 0:
                hlines_list.append(s1)
                colors_list.append("#059669")
                styles_list.append(":")
            if r1 > 0:
                hlines_list.append(r1)
                colors_list.append("#e11d48")
                styles_list.append(":")

        # Trade target lines
        if self.show_targets_var.get() and self._last_calc:
            c = self._last_calc
            e = c.get("entry", 0)
            sl = c.get("stop_loss", 0)
            t1 = c.get("target1", 0)
            t2 = c.get("target2", 0)
            if e > 0:
                hlines_list.append(e)
                colors_list.append("#0067c0")
                styles_list.append("-.")
            if sl > 0:
                hlines_list.append(sl)
                colors_list.append("#c42b1c")
                styles_list.append("--")
            if t1 > 0:
                hlines_list.append(t1)
                colors_list.append("#059669")
                styles_list.append("--")
            if t2 > 0:
                hlines_list.append(t2)
                colors_list.append("#10b981")
                styles_list.append("--")

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
        if hlines_list:
            plot_kwargs["hlines"] = dict(
                hlines=hlines_list,
                colors=colors_list,
                linestyle=styles_list,
                linewidths=1.2,
            )

        fig, axes = mpf.plot(ohlcv, **plot_kwargs)

        # Title subtitle with Grade
        grade_text = f"Grade: {confluence.get('grade', '')} {confluence.get('stars', '')} | Score: {confluence.get('score', 0)}/100 | Vol: {confluence.get('vol_ratio_str', '')}"
        fig.suptitle(f"{symbol}  —  {grade_text}", fontsize=11, fontweight="bold", color="#0f172a", y=0.98)

        # Embed in tkinter
        self._canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        self._toolbar = NavigationToolbar2Tk(self._canvas, self.chart_frame)
        self._toolbar.config(background="#ffffff")
        self._toolbar.update()

        self.app.stop_progress()
        self.app.set_status(f"Chart loaded: {symbol} ({len(ohlcv)} bars) | Confluence Score: {confluence.get('score', 0)}")
        plt.close(fig)

    # ── Risk Calculator Logic ───────────────────────────────────────────

    def _on_calc_risk(self, redraw: bool = False):
        try:
            capital = float(self.calc_capital_var.get().replace(",", "").strip())
            risk_pct = float(self.calc_risk_pct_var.get())
            entry = float(self.calc_entry_var.get().replace(",", "").strip())
            stop_loss = float(self.calc_stop_var.get().replace(",", "").strip())

            res = self.app.engine.calculate_trade_risk(
                capital=capital,
                risk_pct=risk_pct,
                entry=entry,
                stop_loss=stop_loss,
            )
            self._last_calc = res

            # Update Labels
            self.lbl_shares.config(text=f"Shares: {res['shares']:,}")
            self.lbl_invest.config(text=f"Investment: {res['total_cost']:,.2f} LKR ({res['capital_allocated_pct']}%)")
            self.lbl_fees.config(text=f"CSE Fees: ~{res['roundtrip_fee']:,.2f} LKR")
            self.lbl_t1.config(text=f"T1 (1:1.5): {res['target1']:.2f} (+{res['net_profit_t1']:,.2f} net)")
            self.lbl_t2.config(text=f"T2 (1:2.5): {res['target2']:.2f} (+{res['net_profit_t2']:,.2f} net)")
            self.lbl_loss.config(text=f"Max Loss: -{res['net_loss_sl']:,.2f} LKR")

            if redraw and self._current_data:
                self._render_chart(self._current_data)
        except Exception:
            pass

    def _on_plot_levels(self):
        self.show_targets_var.set(True)
        self._on_calc_risk(redraw=True)

    def _on_toggle_levels(self):
        if self._current_data:
            self._render_chart(self._current_data)

    def _send_to_portfolio(self):
        symbol = self._current_symbol or self.symbol_var.get().strip().upper()
        if not symbol:
            return
        try:
            price = float(self.calc_entry_var.get().replace(",", ""))
            shares = int(self._last_calc.get("shares", 100)) if self._last_calc else 100
            self.app.switch_to_portfolio(symbol, price, shares)
            self.app.set_status(f"Pre-filled Portfolio trade for {symbol} ({shares:,} @ {price:.2f})")
        except Exception as e:
            self.app.set_status(f"Error transferring to portfolio: {e}")

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Chart error: {exc}")
