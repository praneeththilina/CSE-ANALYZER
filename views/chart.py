# views/chart.py  –  Interactive Charts & Smart Risk Calculator Tab (Windows 11 Light)
"""
Candlestick + volume chart with spot BUY & EXIT signals, EMA 50/200, dynamic Support/Resistance,
Fibonacci retracements, official CSE company profile, and interactive crosshair HUD.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, Any, Dict

import numpy as np
import pandas as pd

from ui_utils import (
    ThreadedTask, FormCard,
    WIN11_BG, WIN11_CARD_BG, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED,
    WIN11_GREEN, WIN11_RED, WIN11_BORDER,
    FONT_TITLE, FONT_SECTION, FONT_BODY, FONT_BODY_BOLD
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
        super().__init__(parent, padding=(4, 2))
        self.app = app
        self._current_symbol = ""
        self._current_data: dict | None = None
        self._last_calc: dict | None = None
        self._chart_ohlcv: pd.DataFrame | None = None
        self._build_ui()

    def _build_ui(self):
        # ── TradingView-Style Sleek Top Toolbar (1 compact row) ─────────
        self.tv_toolbar = tk.Frame(self, bg="#ffffff", highlightbackground="#cbd5e1",
                                   highlightthickness=1, bd=0, padx=8, pady=4)
        self.tv_toolbar.pack(fill="x", pady=(0, 4))

        # 1. Symbol Search & Load
        tk.Label(self.tv_toolbar, text="Symbol:", font=("Segoe UI Semibold", 9), bg="#ffffff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))

        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(self.tv_toolbar, textvariable=self.symbol_var, width=13, font=("Segoe UI", 9))
        self.symbol_combo.pack(side="left", padx=(0, 4))
        self.symbol_combo.bind("<<ComboboxSelected>>", lambda e: self._on_load())
        self.symbol_combo.bind("<Return>", lambda e: self._on_load())

        ttk.Button(self.tv_toolbar, text="📈 Load", style="Accent.TButton", command=self._on_load).pack(side="left", padx=(0, 6))

        # 2. Timeframe Selector
        ttk.Separator(self.tv_toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.period_var = tk.StringVar(value="1Y")
        for p in ["1M", "3M", "6M", "1Y", "All"]:
            ttk.Radiobutton(self.tv_toolbar, text=p, variable=self.period_var, value=p,
                            command=self._on_load).pack(side="left", padx=1)

        # 3. Technical Overlays
        ttk.Separator(self.tv_toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.show_ma_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tv_toolbar, text="EMA 50/200", variable=self.show_ma_var,
                        command=self._on_load).pack(side="left", padx=3)

        self.show_signals_var = tk.BooleanVar(value=True)
        self.show_qqe_var = self.show_signals_var  # alias
        ttk.Checkbutton(self.tv_toolbar, text="BUY/EXIT Signals", variable=self.show_signals_var,
                        command=self._on_load).pack(side="left", padx=3)

        self.show_sr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tv_toolbar, text="S/R", variable=self.show_sr_var,
                        command=self._on_toggle_levels).pack(side="left", padx=3)

        self.show_fib_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.tv_toolbar, text="Fibonacci", variable=self.show_fib_var,
                        command=self._on_toggle_levels).pack(side="left", padx=3)

        self.show_targets_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tv_toolbar, text="Targets", variable=self.show_targets_var,
                        command=self._on_toggle_levels).pack(side="left", padx=3)

        # 4. Right Side Actions & Drawer Toggles
        ttk.Button(self.tv_toolbar, text="⭐ + Watchlist", command=self._add_to_watchlist_dialog,
                   style="Accent.TButton").pack(side="right", padx=(4, 0))

        self.show_profile_var = tk.BooleanVar(value=False)
        self.btn_profile = tk.Button(self.tv_toolbar, text="🏛️ Profile ▾", font=("Segoe UI", 8, "bold"),
                                     bg="#eef2ff", fg="#3730a3", activebackground="#c7d2fe",
                                     bd=1, relief="solid", cursor="hand2", padx=8, pady=2,
                                     command=self._toggle_profile)
        self.btn_profile.pack(side="right", padx=3)

        self.show_risk_var = tk.BooleanVar(value=False)
        self.btn_risk = tk.Button(self.tv_toolbar, text="⚖️ Risk Calc ▾", font=("Segoe UI", 8, "bold"),
                                  bg="#f0fdf4", fg="#065f46", activebackground="#86efac",
                                  bd=1, relief="solid", cursor="hand2", padx=8, pady=2,
                                  command=self._toggle_risk_calc)
        self.btn_risk.pack(side="right", padx=3)

        # ── Smart Risk & Position Size Calculator FormCard (Collapsible Drawer) ──
        self.risk_card = FormCard(
            self,
            title="Smart Risk & Position Size Calculator (CSE LKR + Fees)",
            accent_color="#059669",
            bg_color="#f0fdf4",
            border_color="#86efac",
            icon="⚖️",
        )

        # Inputs Row
        calc_row = tk.Frame(self.risk_card.body, bg="#f0fdf4")
        calc_row.pack(fill="x", pady=(0, 3))

        tk.Label(calc_row, text="Capital (LKR):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.calc_capital_var = tk.StringVar(value="500000")
        ttk.Entry(calc_row, textvariable=self.calc_capital_var, width=10).pack(side="left", padx=(0, 6))

        tk.Label(calc_row, text="Risk %:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.calc_risk_pct_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(calc_row, from_=0.5, to=10.0, increment=0.5, textvariable=self.calc_risk_pct_var, width=5).pack(side="left", padx=(0, 6))

        tk.Label(calc_row, text="Entry:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 2))
        tk.Button(calc_row, text="−", font=("Segoe UI", 8, "bold"), bg="#d1fae5", fg="#065f46", width=2, bd=0, cursor="hand2", command=lambda: self._step_entry(-0.10)).pack(side="left", padx=1)
        self.calc_entry_var = tk.StringVar(value="")
        ttk.Entry(calc_row, textvariable=self.calc_entry_var, width=8).pack(side="left", padx=1)
        tk.Button(calc_row, text="+", font=("Segoe UI", 8, "bold"), bg="#d1fae5", fg="#065f46", width=2, bd=0, cursor="hand2", command=lambda: self._step_entry(0.10)).pack(side="left", padx=(1, 6))

        tk.Label(calc_row, text="Stop:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 2))
        tk.Button(calc_row, text="−", font=("Segoe UI", 8, "bold"), bg="#fee2e2", fg="#991b1b", width=2, bd=0, cursor="hand2", command=lambda: self._step_stop(-0.10)).pack(side="left", padx=1)
        self.calc_stop_var = tk.StringVar(value="")
        ttk.Entry(calc_row, textvariable=self.calc_stop_var, width=8).pack(side="left", padx=1)
        tk.Button(calc_row, text="+", font=("Segoe UI", 8, "bold"), bg="#fee2e2", fg="#991b1b", width=2, bd=0, cursor="hand2", command=lambda: self._step_stop(0.10)).pack(side="left", padx=(1, 8))

        ttk.Button(calc_row, text="⚡ Calculate Risk", command=self._on_calc_risk).pack(side="left", padx=3)
        ttk.Button(calc_row, text="🎯 Plot on Chart", command=self._on_plot_levels).pack(side="left", padx=3)
        ttk.Button(calc_row, text="💼 Send to Portfolio", command=self._send_to_portfolio, style="Accent.TButton").pack(side="right", padx=4)

        # Quick Presets Row
        preset_row = tk.Frame(self.risk_card.body, bg="#f0fdf4")
        preset_row.pack(fill="x", pady=(0, 3))

        tk.Label(preset_row, text="Capital Presets:", font=("Segoe UI", 8), bg="#f0fdf4", fg=WIN11_TEXT_MUTED).pack(side="left", padx=(0, 4))
        for cap_txt, cap_val in [("250K", 250000), ("500K", 500000), ("1M", 1000000), ("2M", 2000000)]:
            tk.Button(preset_row, text=cap_txt, font=("Segoe UI", 8), bg="#d1fae5", fg="#065f46", bd=0, padx=6, pady=1,
                      cursor="hand2", command=lambda v=cap_val: self._set_capital_preset(v)).pack(side="left", padx=2)

        tk.Label(preset_row, text="Risk Presets:", font=("Segoe UI", 8), bg="#f0fdf4", fg=WIN11_TEXT_MUTED).pack(side="left", padx=(10, 4))
        for r_txt, r_val in [("1.0%", 1.0), ("2.0%", 2.0), ("3.0%", 3.0)]:
            tk.Button(preset_row, text=r_txt, font=("Segoe UI", 8), bg="#e0e7ff", fg="#3730a3", bd=0, padx=6, pady=1,
                      cursor="hand2", command=lambda v=r_val: self._set_risk_preset(v)).pack(side="left", padx=2)

        # Output Metrics Row
        metric_row = tk.Frame(self.risk_card.body, bg="#f0fdf4")
        metric_row.pack(fill="x", pady=(2, 0))

        self.lbl_shares = tk.Label(metric_row, text="Shares: —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#059669")
        self.lbl_shares.pack(side="left", padx=(0, 12))

        self.lbl_invest = tk.Label(metric_row, text="Investment: —", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN)
        self.lbl_invest.pack(side="left", padx=(0, 12))

        self.lbl_fees = tk.Label(metric_row, text="CSE Fees: —", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MUTED)
        self.lbl_fees.pack(side="left", padx=(0, 12))

        self.lbl_t1 = tk.Label(metric_row, text="T1 (1:1.5): —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#0284c7")
        self.lbl_t1.pack(side="left", padx=(0, 12))

        self.lbl_t2 = tk.Label(metric_row, text="T2 (1:2.5): —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#059669")
        self.lbl_t2.pack(side="left", padx=(0, 12))

        self.lbl_trail = tk.Label(metric_row, text="ATR Trail: —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#7c3aed")
        self.lbl_trail.pack(side="left", padx=(0, 12))

        self.lbl_loss = tk.Label(metric_row, text="Max Loss: —", font=FONT_BODY_BOLD, bg="#f0fdf4", fg="#c42b1c")
        self.lbl_loss.pack(side="left", padx=(0, 8))

        # ── Official CSE Company Profile & Leadership FormCard (Collapsible) ─
        self.profile_card = FormCard(
            self,
            title="Official CSE Company Profile & Leadership",
            accent_color="#4f46e5",
            bg_color="#eef2ff",
            border_color="#c7d2fe",
            icon="🏛️",
        )
        # Note: self.profile_card is NOT packed by default; toggled via self.btn_profile

        p_row1 = tk.Frame(self.profile_card.body, bg="#eef2ff")
        p_row1.pack(fill="x", pady=(0, 2))

        self.lbl_prof_name = tk.Label(p_row1, text="Company: —", font=FONT_BODY_BOLD, bg="#eef2ff", fg="#3730a3")
        self.lbl_prof_name.pack(side="left", padx=(0, 16))

        self.lbl_prof_sector = tk.Label(p_row1, text="Sector: —", font=FONT_BODY, bg="#eef2ff", fg=WIN11_TEXT_MAIN)
        self.lbl_prof_sector.pack(side="left", padx=(0, 16))

        self.lbl_prof_board = tk.Label(p_row1, text="Board: —", font=FONT_BODY, bg="#eef2ff", fg=WIN11_TEXT_MAIN)
        self.lbl_prof_board.pack(side="left", padx=(0, 16))

        self.lbl_prof_auditors = tk.Label(p_row1, text="Auditors: —", font=FONT_BODY, bg="#eef2ff", fg=WIN11_TEXT_MUTED)
        self.lbl_prof_auditors.pack(side="left", padx=(0, 16))

        self.lbl_prof_web = tk.Label(p_row1, text="Web: —", font=FONT_BODY, bg="#eef2ff", fg="#2563eb")
        self.lbl_prof_web.pack(side="left")

        p_row2 = tk.Frame(self.profile_card.body, bg="#eef2ff")
        p_row2.pack(fill="x", pady=(2, 0))

        self.lbl_prof_leadership = tk.Label(p_row2, text="Key Leadership: —", font=FONT_BODY_BOLD, bg="#eef2ff", fg="#1e1b4b")
        self.lbl_prof_leadership.pack(side="left", padx=(0, 16))

        self.lbl_prof_summary = tk.Label(p_row2, text="Business: —", font=FONT_BODY, bg="#eef2ff", fg=WIN11_TEXT_MUTED)
        self.lbl_prof_summary.pack(side="left", fill="x", expand=True)

        # ── Chart Canvas Area ───────────────────────────────────────────
        self.chart_frame = tk.Frame(self, bg=WIN11_CARD_BG, highlightbackground="#cbd5e1",
                                    highlightthickness=1, bd=0)
        self.chart_frame.pack(fill="both", expand=True)

        # Dynamic Interactive Hover HUD Ribbon
        self.hud_frame = tk.Frame(self.chart_frame, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
        self.hud_frame.pack(fill="x", side="top", padx=2, pady=(2, 0))
        self.hud_label = tk.Label(
            self.hud_frame,
            text="💡 Move cursor over candlestick chart to inspect bar details (OHLCV, Volume & Pattern)",
            font=("Segoe UI", 8), bg="#f8fafc", fg="#64748b", anchor="w", padx=8, pady=2
        )
        self.hud_label.pack(fill="x")

        self._placeholder = tk.Label(
            self.chart_frame,
            text="Select a CSE symbol and click 'Load Chart' to visualize candlesticks, signals, levels & Fibonacci",
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

    # ── Presets & Steppers ──────────────────────────────────────────────

    def _set_capital_preset(self, val: int):
        self.calc_capital_var.set(str(val))
        self._on_calc_risk(redraw=False)

    def _set_risk_preset(self, val: float):
        self.calc_risk_pct_var.set(val)
        self._on_calc_risk(redraw=False)

    def _step_entry(self, delta: float):
        try:
            val = float(self.calc_entry_var.get().replace(",", "").strip())
            new_val = max(0.10, round(val + delta, 2))
            self.calc_entry_var.set(f"{new_val:.2f}")
            self._on_calc_risk(redraw=False)
        except Exception:
            pass

    def _step_stop(self, delta: float):
        try:
            val = float(self.calc_stop_var.get().replace(",", "").strip())
            new_val = max(0.10, round(val + delta, 2))
            self.calc_stop_var.set(f"{new_val:.2f}")
            self._on_calc_risk(redraw=False)
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
        show_signals = self.show_signals_var.get()
        self.app.set_status(f"Loading chart for {symbol}...")
        self.app.start_progress()
        ThreadedTask(
            self.app.root,
            target=self._fetch_chart_data, args=(symbol, period, show_signals),
            on_done=self._render_chart,
            on_error=self._on_error,
        ).start()

    def _fetch_chart_data(self, symbol: str, period: str, show_signals: bool) -> dict:
        df_full = self.app.engine.get_bars(symbol)
        if df_full.empty:
            raise ValueError(f"No historical price bars found for {symbol}")

        # Compute confluence & key levels for this symbol
        confluence = self.app.engine.compute_confluence(df_full, 1)

        # Compute spot BUY and EXIT signals across history
        signals_data = None
        if show_signals:
            try:
                signals_data = self.app.engine.compute_chart_signals(df_full)
            except Exception:
                pass

        # Apply period filter for chart display
        df = df_full
        if period != "All":
            days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}[period]
            cutoff = df_full.index[-1] - pd.Timedelta(days=days)
            df = df_full[df_full.index >= cutoff]

        result = {"df": df, "symbol": symbol, "confluence": confluence}

        if signals_data:
            buys = signals_data.get("buy_signals")
            exits = signals_data.get("exit_signals")
            if buys is not None:
                buys = buys[buys.index >= df.index[0]]
            if exits is not None:
                exits = exits[exits.index >= df.index[0]]
            result["signals"] = {"buy": buys, "exit": exits}

        # Fetch official CSE company profile (cached)
        try:
            profile = self.app.engine.get_formatted_company_profile(symbol)
        except Exception:
            profile = {}
        result["profile"] = profile

        return result

    def _render_chart(self, data: dict):
        self._current_data = data
        df = data["df"]
        symbol = data["symbol"]
        confluence = data.get("confluence", {})

        # Update Official CSE Company Profile Card
        profile = data.get("profile", {})
        if profile:
            self.lbl_prof_name.config(text=f"Company: {profile.get('name', symbol)}")
            self.lbl_prof_sector.config(text=f"Sector: {profile.get('sector', '—')}")
            self.lbl_prof_board.config(text=f"Board: {profile.get('board_type', '—')} ({profile.get('established', '—')})")
            self.lbl_prof_auditors.config(text=f"Auditors: {profile.get('auditors', '—')}")
            self.lbl_prof_web.config(text=f"🌐 {profile.get('web', '—')}")

            leads = profile.get("leadership", [])
            lead_str = " | ".join([f"{l.get('designation')}: {l.get('name')}" for l in leads[:2]]) if leads else "—"
            self.lbl_prof_leadership.config(text=f"Leadership: {lead_str}")

            b_sum = profile.get("business_summary", "")
            if len(b_sum) > 130:
                b_sum = b_sum[:127] + "…"
            self.lbl_prof_summary.config(text=f"Business: {b_sum}")

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
        self._chart_ohlcv = ohlcv

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

        # Spot Equity BUY & EXIT Signal Markers
        if "signals" in data and self.show_signals_var.get():
            sigs = data["signals"]
            buy_signals = sigs.get("buy")
            exit_signals = sigs.get("exit")

            if buy_signals is not None and buy_signals.notna().any():
                addplots.append(mpf.make_addplot(
                    buy_signals, type="scatter", marker="^",
                    markersize=95, color="#0e700e"
                ))
            if exit_signals is not None and exit_signals.notna().any():
                addplots.append(mpf.make_addplot(
                    exit_signals, type="scatter", marker="v",
                    markersize=95, color="#c42b1c"
                ))

        # Horizontal Lines: Support/Resistance, Fibonacci & Trade Targets
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

        # Fibonacci Retracement levels
        if self.show_fib_var.get() and confluence:
            fib = confluence.get("fibonacci", {})
            fib_map = [
                ("fib_236", "#ec4899", "Fib 23.6%"),
                ("fib_382", "#8b5cf6", "Fib 38.2%"),
                ("fib_500", "#3b82f6", "Fib 50.0%"),
                ("fib_618", "#10b981", "Fib 61.8%"),
            ]
            for key, col, lbl in fib_map:
                val = fib.get(key, 0)
                if val > 0:
                    hlines_list.append(val)
                    colors_list.append(col)
                    styles_list.append("-.")

        # Trade target lines (Entry, Stop Loss, Target 1, Target 2, Trailing Stop)
        if self.show_targets_var.get():
            c = self._last_calc if self._last_calc else {}
            last_p = float(ohlcv["close"].iloc[-1])
            e = c.get("entry", confluence.get("current_price", last_p))
            sl = c.get("stop_loss", confluence.get("suggested_stop", 0))
            t1 = c.get("target1", confluence.get("target1", 0))
            t2 = c.get("target2", confluence.get("target2", 0))
            ts = c.get("trailing_stop", confluence.get("trailing_stop", 0))
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
            if ts > 0 and abs(ts - sl) > 0.05:
                hlines_list.append(ts)
                colors_list.append("#7c3aed")
                styles_list.append(":")

        plot_kwargs = {
            "type": "candle",
            "style": style,
            "volume": True,
            "title": f"\n{symbol}",
            "figsize": (16, 9),
            "returnfig": True,
            "panel_ratios": (5, 1),
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
        try:
            fig.subplots_adjust(left=0.035, right=0.975, top=0.94, bottom=0.05, hspace=0.06)
        except Exception:
            pass

        # Title subtitle with Grade & Breakout & Pattern
        grade = confluence.get("grade", "A")
        stars = confluence.get("stars", "★★★★")
        score = confluence.get("score", 0)
        vol = confluence.get("vol_ratio_str", "1.0x")
        weekly = confluence.get("weekly_trend", "Bullish")
        breakout = "Near 52W High" if confluence.get("near_breakout") else f"52W High: {confluence.get('dist_52w_high', '')}"
        pattern = confluence.get("pattern", "—")
        grade_text = f"Grade: {grade} {stars} ({score}/100) | Vol: {vol} | Weekly: {weekly} | {breakout} | Pattern: {pattern}"
        clean_title = "".join(ch for ch in f"{symbol}  —  {grade_text}" if ord(ch) < 0x25A0 or ord(ch) in [0x2605, 0x25B2, 0x25BC])
        fig.suptitle(clean_title, fontsize=10, fontweight="bold", color="#0f172a", y=0.98)

        # Embed in tkinter
        self._canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        # Connect Interactive Crosshair / Hover HUD Event
        self._canvas.mpl_connect("motion_notify_event", self._on_chart_hover)

        self._toolbar = NavigationToolbar2Tk(self._canvas, self.chart_frame)
        self._toolbar.config(background="#ffffff")
        self._toolbar.update()

        self.app.stop_progress()
        self.app.set_status(f"Chart loaded: {symbol} ({len(ohlcv)} bars) | Confluence: {score}/100 | Pattern: {pattern}")
        plt.close(fig)

    # ── Interactive Hover HUD ───────────────────────────────────────────

    def _on_chart_hover(self, event):
        if event.xdata is None or self._chart_ohlcv is None or self._chart_ohlcv.empty:
            return
        try:
            idx = int(round(event.xdata))
            if 0 <= idx < len(self._chart_ohlcv):
                row = self._chart_ohlcv.iloc[idx]
                dt_str = self._chart_ohlcv.index[idx].strftime("%Y-%m-%d")
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                c = float(row["close"])
                v = float(row["volume"])
                chg = ((c - o) / o) * 100.0 if o > 0 else 0.0
                chg_sign = "+" if chg >= 0 else ""
                txt = f"📅 {dt_str}   O: {o:.2f}   H: {h:.2f}   L: {l:.2f}   C: {c:.2f} ({chg_sign}{chg:.2f}%)   Vol: {int(v):,}"
                self.hud_label.config(text=txt, fg="#0284c7" if chg >= 0 else "#c42b1c")
        except Exception:
            pass

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

            if self._current_data and "confluence" in self._current_data:
                ts = self._current_data["confluence"].get("trailing_stop", 0)
                if ts > 0:
                    self.lbl_trail.config(text=f"ATR Trail: {ts:.2f} LKR")

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

    def _toggle_risk_calc(self):
        new_state = not self.show_risk_var.get()
        self.show_risk_var.set(new_state)
        if new_state:
            self.risk_card.pack(fill="x", pady=(0, 4), before=self.chart_frame)
            self.btn_risk.config(bg="#059669", fg="#ffffff", text="⚖️ Risk Calc ▴")
        else:
            self.risk_card.pack_forget()
            self.btn_risk.config(bg="#f0fdf4", fg="#065f46", text="⚖️ Risk Calc ▾")

    def _toggle_profile(self):
        new_state = not self.show_profile_var.get()
        self.show_profile_var.set(new_state)
        if new_state:
            self.profile_card.pack(fill="x", pady=(0, 4), before=self.chart_frame)
            self.btn_profile.config(bg="#4f46e5", fg="#ffffff", text="🏛️ Profile ▴")
        else:
            self.profile_card.pack_forget()
            self.btn_profile.config(bg="#eef2ff", fg="#3730a3", text="🏛️ Profile ▾")

    def _on_toggle_profile(self):
        self._toggle_profile()

    def _add_to_watchlist_dialog(self):
        """Displays dialog allowing user to add currently loaded stock to any watchlist."""
        symbol = self._current_symbol or self.symbol_var.get().strip().upper()
        if not symbol:
            messagebox.showinfo("Watchlist", "Please load a symbol on the chart first.", parent=self)
            return

        stop_val = self.calc_stop_var.get().strip()

        dlg = tk.Toplevel(self)
        dlg.title(f"Add {symbol} to Watchlist")
        dlg.geometry("400x290")
        dlg.resizable(False, False)
        dlg.configure(bg=WIN11_BG)
        dlg.transient(self)
        dlg.grab_set()

        pad = tk.Frame(dlg, bg=WIN11_BG, padx=18, pady=16)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text=f"⭐ Add {symbol} to Watchlist", font=FONT_SECTION, bg=WIN11_BG, fg=WIN11_TEXT_MAIN).pack(anchor="w", pady=(0, 12))

        f_grid = tk.Frame(pad, bg=WIN11_BG)
        f_grid.pack(fill="x", pady=(0, 12))

        tk.Label(f_grid, text="Watchlist:", font=FONT_BODY, bg=WIN11_BG).grid(row=0, column=0, sticky="w", pady=4)
        names = self.app.engine.get_watchlist_names()
        list_var = tk.StringVar(value=names[0] if names else "⭐ Blue Chips")
        list_cb = ttk.Combobox(f_grid, textvariable=list_var, values=names, width=22)
        list_cb.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        tk.Label(f_grid, text="Alert High (≥):", font=FONT_BODY, bg=WIN11_BG).grid(row=1, column=0, sticky="w", pady=4)
        t1_val = ""
        if self._last_calc and self._last_calc.get("target1"):
            t1_val = str(self._last_calc["target1"])
        ah_var = tk.StringVar(value=t1_val)
        ttk.Entry(f_grid, textvariable=ah_var, width=15).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        tk.Label(f_grid, text="Alert Low (≤):", font=FONT_BODY, bg=WIN11_BG).grid(row=2, column=0, sticky="w", pady=4)
        al_var = tk.StringVar(value=stop_val)
        ttk.Entry(f_grid, textvariable=al_var, width=15).grid(row=2, column=1, sticky="w", padx=8, pady=4)

        tk.Label(f_grid, text="Notes / Strategy:", font=FONT_BODY, bg=WIN11_BG).grid(row=3, column=0, sticky="w", pady=4)
        notes_var = tk.StringVar(value="Chart technical setup")
        ttk.Entry(f_grid, textvariable=notes_var, width=22).grid(row=3, column=1, sticky="w", padx=8, pady=4)

        def _save():
            lname = list_var.get().strip()
            if not lname:
                messagebox.showwarning("Watchlist", "Please enter a watchlist name.", parent=dlg)
                return
            try:
                ah = float(ah_var.get().strip()) if ah_var.get().strip() else 0.0
            except ValueError:
                ah = 0.0
            try:
                al = float(al_var.get().strip()) if al_var.get().strip() else 0.0
            except ValueError:
                al = 0.0

            self.app.engine.add_to_watchlist(lname, symbol, alert_high=ah, alert_low=al, notes=notes_var.get().strip())
            self.app.set_status(f"Added {symbol} to watchlist '{lname}'")
            dlg.destroy()
            messagebox.showinfo("Saved", f"Successfully added {symbol} to '{lname}'!", parent=self)

        btn_row = tk.Frame(pad, bg=WIN11_BG)
        btn_row.pack(fill="x", side="bottom")
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(btn_row, text="💾 Save to Watchlist", command=_save, style="Accent.TButton").pack(side="right", padx=4)

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Chart error: {exc}")
