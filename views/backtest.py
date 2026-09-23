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
            title="CSE Spot Equity Strategy & Risk Management Simulator",
            accent_color="#059669",
            bg_color="#f0fdf4",
            border_color="#86efac",
            icon="⚡",
        )
        self.config_card.pack(fill="x", pady=(0, 10))

        row1 = tk.Frame(self.config_card.body, bg="#f0fdf4")
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(row1, text="Symbol:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sym_var = tk.StringVar()
        self.sym_combo = ttk.Combobox(row1, textvariable=self.sym_var, width=14)
        self.sym_combo.pack(side="left", padx=(0, 12))

        tk.Label(row1, text="Capital (LKR):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.capital_var = tk.StringVar(value="500000")
        ttk.Entry(row1, textvariable=self.capital_var, width=9).pack(side="left", padx=(0, 12))

        tk.Label(row1, text="CSE Fees %:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.comm_var = tk.StringVar(value="1.12")
        ttk.Entry(row1, textvariable=self.comm_var, width=5).pack(side="left", padx=(0, 12))

        tk.Label(row1, text="Allocation %:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.alloc_var = tk.IntVar(value=100)
        ttk.Spinbox(row1, from_=10, to=100, increment=10, textvariable=self.alloc_var, width=4).pack(side="left", padx=(0, 12))

        tk.Label(row1, text="Strategy:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.strat_var = tk.StringVar(value="All Spot Setups")
        strat_cb = ttk.Combobox(row1, textvariable=self.strat_var, width=22, state="readonly")
        strat_cb["values"] = [
            "All Spot Setups",
            "🚀 Breakout BUY",
            "💎 Pullback BUY",
            "⚡ Golden Cross BUY",
            "📊 Dual MA Crossover",
            "📉 RSI Oversold Reversion"
        ]
        strat_cb.pack(side="left")

        row2 = tk.Frame(self.config_card.body, bg="#f0fdf4")
        row2.pack(fill="x")

        tk.Label(row2, text="Target 1 (R:R):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.t1_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(row2, from_=1.0, to=5.0, increment=0.5, textvariable=self.t1_var, width=5).pack(side="left", padx=(0, 14))

        tk.Label(row2, text="Target 2 (R:R):", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.t2_var = tk.DoubleVar(value=2.5)
        ttk.Spinbox(row2, from_=1.5, to=8.0, increment=0.5, textvariable=self.t2_var, width=5).pack(side="left", padx=(0, 14))

        tk.Label(row2, text="Stop Loss ATR:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sl_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(row2, from_=1.0, to=4.0, increment=0.5, textvariable=self.sl_var, width=5).pack(side="left", padx=(0, 14))

        self.trail_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Trailing Stop (2.0 ATR)", variable=self.trail_var).pack(side="left", padx=(0, 16))

        ttk.Button(row2, text="⚡ Run Spot Backtest", command=self._run_backtest,
                   style="Accent.TButton").pack(side="right", padx=4)
        ttk.Button(row2, text="🛠️ Optimize Parameters", command=self._run_optimizer
                   ).pack(side="right", padx=4)
        ttk.Button(row2, text="🔄 Walk-Forward Validation", command=self._run_walk_forward
                   ).pack(side="right", padx=4)

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

        self.app.set_status(f"Running spot equity backtest on {symbol}...")
        self.app.start_progress()

        strat_map = {
            "All Spot Setups": "all",
            "🚀 Breakout BUY": "breakout",
            "💎 Pullback BUY": "pullback",
            "⚡ Golden Cross BUY": "golden_cross",
            "📊 Dual MA Crossover": "dual_ma_crossover",
            "📉 RSI Oversold Reversion": "rsi_reversion",
        }
        params = {
            "symbol": symbol,
            "initial_capital": float(self.capital_var.get().replace(",", "").strip() or 500000),
            "commission_pct": float(self.comm_var.get().replace(",", "").strip() or 1.12),
            "allocation_pct": float(self.alloc_var.get()),
            "strategy": strat_map.get(self.strat_var.get(), "all"),
            "target1_r": float(self.t1_var.get()),
            "target2_r": float(self.t2_var.get()),
            "sl_atr_mult": float(self.sl_var.get()),
            "use_trailing": self.trail_var.get(),
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
                    "🟢 BUY",
                    f"{float(t.get('entry_price', 0)):.2f}",
                    f"{float(t.get('exit_price', 0)):.2f}",
                    f"{float(t.get('return_pct', 0)):+.2f}%",
                    fmt_currency(pnl_val, "₨ "),
                    t.get("exit_reason", ""),
                ), tags=(tag,))

        self.app.stop_progress()
        self.app.set_status(f"Spot backtest complete: {stats.get('Total Trades', 0)} closed trades | Return: {ret_val}%")

    def _render_equity_curve(self, equity_df: pd.DataFrame):
        if self._eq_canvas:
            self._eq_canvas.get_tk_widget().destroy()
        self._eq_placeholder.pack_forget()

        fig = Figure(figsize=(10, 3), dpi=90, facecolor="#ffffff")
        ax = fig.add_subplot(111)

        if "date" in equity_df.columns:
            dates = pd.to_datetime(equity_df["date"], errors="coerce")
        else:
            dates = pd.to_datetime(equity_df.index, errors="coerce")
        if dates.isna().all():
            dates = np.arange(len(equity_df))
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

    def _run_optimizer(self):
        sym = self.sym_var.get().strip().upper()
        if not sym:
            return

        self.app.set_status(f"Running strategy parameter optimization for {sym}...")
        self.app.start_progress()

        strat = self.strat_var.get()

        def task():
            return self.app.engine.run_strategy_optimization(symbol=sym, strategy_mode=strat)

        def on_done(results):
            self.app.stop_progress()
            self.app.set_status(f"Parameter optimization complete for {sym}")
            self._show_optimizer_modal(sym, results)

        ThreadedTask(self.app.root, target=task, on_done=on_done, on_error=self._on_error).start()

    def _show_optimizer_modal(self, symbol: str, results: list):
        win = tk.Toplevel(self.app.root)
        win.title(f"Strategy Parameter Optimization — {symbol}")
        win.geometry("680x520")
        win.configure(bg=WIN11_BG)
        win.transient(self.app.root)
        win.grab_set()

        hdr = tk.Frame(win, bg="#059669", padx=16, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"🛠️ Parameter Optimization Results: {symbol}", font=("Segoe UI Semibold", 13), bg="#059669", fg="#ffffff").pack(anchor="w")
        top_res = results[0] if results else {}
        ret = top_res.get("return_pct", 0.0)
        sharpe = top_res.get("sharpe_ratio", 0.0)
        tk.Label(hdr, text=f"Top Config: Target 1 ({top_res.get('target1_rr')}R), Target 2 ({top_res.get('target2_rr')}R), ATR Stop ({top_res.get('atr_stop_multiplier')}x) | Return: {ret:+.2f}% | Sharpe: {sharpe:.2f}", font=("Segoe UI", 9), bg="#059669", fg="#d1fae5").pack(anchor="w")

        body = FormCard(win, title=f"Ranked Strategy Configurations ({len(results)} Combinations Tested)")
        body.pack(fill="both", expand=True, padx=12, pady=10)

        cols = [
            ("t1", "Target 1 (R)", 90),
            ("t2", "Target 2 (R)", 90),
            ("atr", "ATR Stop (x)", 90),
            ("risk", "Risk %", 75),
            ("return", "Return %", 90),
            ("winrate", "Win Rate %", 90),
            ("pf", "Profit Factor", 90),
            ("sharpe", "Sharpe Ratio", 90),
        ]
        tree = SortableTreeview(body, cols, selectmode="browse")
        tree.pack(fill="both", expand=True, padx=4, pady=4)

        for res in results:
            ret_val = float(res.get("return_pct", 0.0))
            tag = "pos" if ret_val >= 0 else "neg"
            tree.insert("", "end", values=(
                f"{res.get('target1_rr')}R",
                f"{res.get('target2_rr')}R",
                f"{res.get('atr_stop_multiplier')}x",
                f"{res.get('risk_per_trade_pct')}%",
                f"{ret_val:+.2f}%",
                f"{res.get('win_rate_pct', 0.0):.1f}%",
                f"{res.get('profit_factor', 0.0):.2f}",
                f"{res.get('sharpe_ratio', 0.0):.2f}"
            ), tags=(tag,))

        tree.tag_configure("pos", foreground=WIN11_GREEN)
        tree.tag_configure("neg", foreground=WIN11_RED)

    def _run_walk_forward(self):
        sym = self.sym_var.get().strip()
        if not sym:
            return

        self.app.set_status(f"Running rolling walk-forward validation on {sym}...")
        self.app.start_progress()

        def task():
            return self.app.engine.run_walk_forward_validation(sym)

        def on_done(result):
            self.app.stop_progress()
            self.app.set_status(f"Walk-forward validation complete for {sym}")
            self._show_walk_forward_modal(sym, result)

        ThreadedTask(self.app.root, target=task, on_done=on_done, on_error=self._on_error).start()

    def _show_walk_forward_modal(self, symbol: str, res: dict):
        win = tk.Toplevel(self.app.root)
        win.title(f"Walk-Forward Validation — {symbol}")
        win.geometry("620x520")
        win.configure(bg=WIN11_BG)
        win.transient(self.app.root)
        win.grab_set()

        hdr = tk.Frame(win, bg="#059669", padx=16, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"🛡️ Walk-Forward Validation: {symbol}", font=("Segoe UI Semibold", 13), bg="#059669", fg="#ffffff").pack(anchor="w")
        verdict = res.get("robustness_verdict", "N/A")
        score = res.get("profitable_periods_pct", 0.0)
        ret = res.get("avg_out_of_sample_return_pct", 0.0)
        tk.Label(hdr, text=f"Verdict: {verdict} | Out-of-Sample Profitable Periods: {score}% | Avg Return: {ret:+.2f}%", font=("Segoe UI", 9), bg="#059669", fg="#d1fae5").pack(anchor="w")

        body = FormCard(win, title=f"Rolling Out-of-Sample Window Folds ({res.get('total_folds', 0)} Folds Tested)")
        body.pack(fill="both", expand=True, padx=12, pady=10)

        cols = [
            ("fold", "Fold #", 60),
            ("start", "Start Date", 95),
            ("end", "End Date", 95),
            ("return", "Return %", 90),
            ("winrate", "Win Rate %", 90),
            ("trades", "Trades", 70),
            ("dd", "Max DD %", 80),
        ]
        tree = SortableTreeview(body, cols, selectmode="browse")
        tree.pack(fill="both", expand=True, padx=4, pady=4)

        for f in res.get("folds", []):
            ret_val = float(f.get("return_pct", 0.0))
            tag = "pos" if ret_val >= 0 else "neg"
            tree.insert("", "end", values=(
                f"Fold {f.get('fold', 1)}",
                f.get("start_date", ""),
                f.get("end_date", ""),
                f"{ret_val:+.2f}%",
                f"{f.get('win_rate_pct', 0.0):.1f}%",
                f.get("trades", 0),
                f"{f.get('max_drawdown_pct', 0.0):.2f}%"
            ), tags=(tag,))

        tree.tag_configure("pos", foreground=WIN11_GREEN)
        tree.tag_configure("neg", foreground=WIN11_RED)
