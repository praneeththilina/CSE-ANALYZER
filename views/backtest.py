# views/backtest.py  –  Backtest Engine Tab (Windows 11 Light)
"""
Configure and run full vector-based backtests on individual symbols.
Displays statistics, equity curve chart, and trade log styled for Windows 11 Light.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ui_utils import (
    InfoCard, FormCard, SortableTreeview, ThreadedTask, fmt_currency,
    WIN11_BG, WIN11_CARD_BG, WIN11_GREEN, WIN11_RED, WIN11_ACCENT, WIN11_TEXT_MAIN,
    FONT_TITLE, FONT_SECTION, FONT_BODY
)

if TYPE_CHECKING:
    from app import MainApp


class BacktestTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._eq_canvas = None
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Backtest Engine", font=FONT_TITLE).pack(side="left")

        # ── Configuration Colorful Form Card ────────────────────────────
        self.config_card = FormCard(
            self,
            title="Strategy & Risk Management Settings",
            accent_color="#d97706",
            bg_color="#fffbeb",
            border_color="#fcd34d",
            icon="⚡",
        )
        self.config_card.pack(fill="x", pady=(0, 10))

        row1 = tk.Frame(self.config_card.body, bg="#fffbeb")
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(row1, text="Symbol:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sym_var = tk.StringVar()
        self.sym_combo = ttk.Combobox(row1, textvariable=self.sym_var, width=15)
        self.sym_combo.pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Capital (LKR):", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.capital_var = tk.StringVar(value="100000")
        ttk.Entry(row1, textvariable=self.capital_var, width=10).pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Comm %:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.comm_var = tk.StringVar(value="0.1")
        ttk.Entry(row1, textvariable=self.comm_var, width=6).pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Stop Loss %:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sl_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.sl_var, width=6).pack(side="left", padx=(0, 16))

        tk.Label(row1, text="Take Profit %:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.tp_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.tp_var, width=6).pack(side="left")

        row2 = tk.Frame(self.config_card.body, bg="#fffbeb")
        row2.pack(fill="x")

        tk.Label(row2, text="RSI Period:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.rsi_var = tk.IntVar(value=14)
        ttk.Spinbox(row2, from_=2, to=50, textvariable=self.rsi_var, width=5).pack(side="left", padx=(0, 16))

        tk.Label(row2, text="SF:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sf_var = tk.IntVar(value=5)
        ttk.Spinbox(row2, from_=1, to=20, textvariable=self.sf_var, width=5).pack(side="left", padx=(0, 16))

        tk.Label(row2, text="QQE Factor:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.qqe_var = tk.DoubleVar(value=4.238)
        ttk.Entry(row2, textvariable=self.qqe_var, width=7).pack(side="left", padx=(0, 16))

        tk.Label(row2, text="Threshold:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.thresh_var = tk.IntVar(value=10)
        ttk.Spinbox(row2, from_=1, to=50, textvariable=self.thresh_var, width=5).pack(side="left", padx=(0, 16))

        ttk.Button(row2, text="⚡ Run Backtest", command=self._run_backtest,
                   style="Accent.TButton").pack(side="right", padx=4)

        # ── Stats Cards ─────────────────────────────────────────────────
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill="x", pady=(0, 10))
        stats_frame.columnconfigure(tuple(range(7)), weight=1, uniform="stat")

        self.stat_return = InfoCard(stats_frame, "Total Return", "—", accent_color="#059669", icon="📈")
        self.stat_return.grid(row=0, column=0, padx=3, sticky="nsew")

        self.stat_trades = InfoCard(stats_frame, "Total Trades", "—", accent_color="#0284c7", icon="🔢")
        self.stat_trades.grid(row=0, column=1, padx=3, sticky="nsew")

        self.stat_winrate = InfoCard(stats_frame, "Win Rate", "—", accent_color="#059669", icon="🎯")
        self.stat_winrate.grid(row=0, column=2, padx=3, sticky="nsew")

        self.stat_pf = InfoCard(stats_frame, "Profit Factor", "—", accent_color="#4f46e5", icon="⚖")
        self.stat_pf.grid(row=0, column=3, padx=3, sticky="nsew")

        self.stat_avgwin = InfoCard(stats_frame, "Avg. Win", "—", accent_color="#059669", icon="▲")
        self.stat_avgwin.grid(row=0, column=4, padx=3, sticky="nsew")

        self.stat_avgloss = InfoCard(stats_frame, "Avg. Loss", "—", accent_color="#e11d48", icon="▼")
        self.stat_avgloss.grid(row=0, column=5, padx=3, sticky="nsew")

        self.stat_dd = InfoCard(stats_frame, "Max Drawdown", "—", accent_color="#e11d48", icon="📉")
        self.stat_dd.grid(row=0, column=6, padx=3, sticky="nsew")

        # ── Lower Split: Equity Curve + Trade Log ───────────────────────
        lower = ttk.Frame(self)
        lower.pack(fill="both", expand=True)
        lower.rowconfigure(0, weight=1)
        lower.rowconfigure(1, weight=1)
        lower.columnconfigure(0, weight=1)

        # Equity curve frame
        self.eq_frame = tk.Frame(lower, bg=WIN11_CARD_BG, highlightbackground="#cbd5e1",
                                 highlightthickness=1, bd=0)
        self.eq_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        self._eq_placeholder = tk.Label(
            self.eq_frame,
            text="Run a backtest to see the strategy equity curve",
            font=("Segoe UI", 10), fg="#64748b", bg=WIN11_CARD_BG,
        )
        self._eq_placeholder.pack(expand=True)

        # Trade log table
        trade_frame = ttk.Frame(lower)
        trade_frame.grid(row=1, column=0, sticky="nsew")

        cols = ("entry_date", "exit_date", "side", "entry_p", "exit_p", "ret_pct", "pnl", "reason")
        self.trade_tree = SortableTreeview(trade_frame, columns=cols, height=8)
        self.trade_tree.heading("entry_date", text="Entry Date")
        self.trade_tree.heading("exit_date", text="Exit Date")
        self.trade_tree.heading("side", text="Side")
        self.trade_tree.heading("entry_p", text="Entry Price")
        self.trade_tree.heading("exit_p", text="Exit Price")
        self.trade_tree.heading("ret_pct", text="Return %")
        self.trade_tree.heading("pnl", text="P&L")
        self.trade_tree.heading("reason", text="Exit Reason")

        self.trade_tree.column("entry_date", width=95, minwidth=80)
        self.trade_tree.column("exit_date", width=95, minwidth=80)
        self.trade_tree.column("side", width=55, minwidth=45, anchor="center")
        self.trade_tree.column("entry_p", width=80, minwidth=60, anchor="e")
        self.trade_tree.column("exit_p", width=80, minwidth=60, anchor="e")
        self.trade_tree.column("ret_pct", width=80, minwidth=60, anchor="e")
        self.trade_tree.column("pnl", width=90, minwidth=65, anchor="e")
        self.trade_tree.column("reason", width=120, minwidth=80)

        scroller = ttk.Scrollbar(trade_frame, orient="vertical", command=self.trade_tree.yview)
        self.trade_tree.configure(yscrollcommand=scroller.set)
        self.trade_tree.pack(side="left", fill="both", expand=True)
        scroller.pack(side="right", fill="y")

        self.trade_tree.tag_configure("profit", foreground=WIN11_GREEN)
        self.trade_tree.tag_configure("loss", foreground=WIN11_RED)

        # Pre-populate symbols immediately
        self._load_symbols()

    def on_tab_shown(self):
        if not self.sym_combo["values"]:
            self._load_symbols()

    def _load_symbols(self):
        try:
            symbols = self.app.engine.get_symbol_list()
            self.sym_combo["values"] = symbols
            if symbols:
                self.sym_combo.current(0)
        except Exception:
            pass

    # ── Backtest Execution ──────────────────────────────────────────────

    def _run_backtest(self):
        symbol = self.sym_var.get().strip().upper()
        if not symbol:
            return

        self.app.set_status(f"Running backtest on {symbol}...")
        self.app.start_progress()

        params = {
            "symbol": symbol,
            "rsi_period": self.rsi_var.get(),
            "sf": self.sf_var.get(),
            "qqe_factor": self.qqe_var.get(),
            "threshold": self.thresh_var.get(),
            "initial_capital": float(self.capital_var.get()),
            "commission_pct": float(self.comm_var.get()),
            "stop_loss_pct": float(self.sl_var.get()),
            "take_profit_pct": float(self.tp_var.get()),
        }

        ThreadedTask(
            self.app.root,
            target=self.app.engine.run_backtest,
            kwargs=params,
            on_done=self._on_backtest_done,
            on_error=self._on_error,
        ).start()

    def _on_backtest_done(self, results: dict):
        stats = results["stats"]
        equity_df = results["equity_curve"]
        trades_df = results["trades"]

        ret_val = stats.get("Total Return (%)", 0)
        ret_color = WIN11_GREEN if float(ret_val) >= 0 else WIN11_RED

        self.stat_return.set(f"{ret_val}%", color=ret_color)
        self.stat_trades.set(str(stats.get("Total Trades", 0)))
        self.stat_winrate.set(f"{stats.get('Win Rate (%)', '—')}%")
        self.stat_pf.set(str(stats.get("Profit Factor", "—")))
        self.stat_avgwin.set(fmt_currency(float(stats.get("Avg. Win (LKR)", 0)), "₨ "), color=WIN11_GREEN)
        self.stat_avgloss.set(fmt_currency(float(stats.get("Avg. Loss (LKR)", 0)), "₨ "), color=WIN11_RED)
        self.stat_dd.set(f"{stats.get('Max. Drawdown (%)', '—')}%")

        # Equity curve chart
        self._render_equity_curve(equity_df)

        # Trade log
        self.trade_tree.delete(*self.trade_tree.get_children())
        if not trades_df.empty:
            for _, t in trades_df.iterrows():
                pnl_val = float(t.get("pnl", 0))
                tag = "profit" if pnl_val >= 0 else "loss"
                self.trade_tree.insert("", "end", values=(
                    t.get("entry_date", ""),
                    t.get("exit_date", ""),
                    t.get("side", ""),
                    f"{float(t.get('entry_price', 0)):.2f}",
                    f"{float(t.get('exit_price', 0)):.2f}",
                    f"{float(t.get('return_pct', 0)):+.2f}%",
                    fmt_currency(pnl_val, "₨ "),
                    t.get("exit_reason", ""),
                ), tags=(tag,))

        self.app.stop_progress()
        self.app.set_status(f"Backtest complete: {stats.get('Total Trades', 0)} trades")

    def _render_equity_curve(self, equity_df: pd.DataFrame):
        if self._eq_canvas:
            self._eq_canvas.get_tk_widget().destroy()
        self._eq_placeholder.pack_forget()

        fig = Figure(figsize=(10, 3), dpi=90, facecolor="#ffffff")
        ax = fig.add_subplot(111)

        dates = pd.to_datetime(equity_df["date"])
        equity = equity_df["equity"].astype(float)

        ax.fill_between(dates, equity, alpha=0.15, color="#0067c0")
        ax.plot(dates, equity, color="#0067c0", linewidth=1.8)

        # Initial capital line
        init_cap = equity.iloc[0]
        ax.axhline(y=init_cap, color="#94a3b8", linestyle="--", linewidth=1.0, alpha=0.8)

        ax.set_facecolor("#ffffff")
        ax.tick_params(colors="#475569", labelsize=8)
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, linestyle="--", alpha=0.5, color="#f1f5f9")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(
            lambda x, p: f"₨{x / 1000:.0f}K" if x >= 1000 else f"₨{x:.0f}"
        ))
        fig.tight_layout(pad=1.5)

        self._eq_canvas = FigureCanvasTkAgg(fig, master=self.eq_frame)
        self._eq_canvas.draw()
        self._eq_canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Backtest error: {exc}")
