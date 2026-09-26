# views/portfolio.py  –  Portfolio Tracker Tab (Windows 11 Light)
"""
Track buy/sell positions, display live P&L, and show a
diversification pie chart by industry sector styled for Windows 11 Light.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ui_utils import (
    InfoCard, FormCard, SortableTreeview, ThreadedTask,
    fmt_currency, fmt_pct,
    WIN11_BG, WIN11_CARD_BG, WIN11_GREEN, WIN11_RED, WIN11_TEXT_MAIN, WIN11_TEXT_MUTED,
    FONT_TITLE, FONT_SECTION, FONT_BODY

)

if TYPE_CHECKING:
    from app import MainApp


class PortfolioTab(ttk.Frame):
    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._pie_canvas = None
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Portfolio Tracker", font=FONT_TITLE).pack(side="left")
        ttk.Button(header, text="📥 Export CSV", command=self._export_csv).pack(side="right", padx=(4, 0))
        ttk.Button(header, text="🔄 Refresh", command=self.load_data).pack(side="right")

        # ── Add Trade Colorful Form Card ────────────────────────────────
        self.form_card = FormCard(
            self,
            title="New Trade Position Entry",
            accent_color="#059669",
            bg_color="#f0fdf4",
            border_color="#86efac",
            icon="➕",
        )
        self.form_card.pack(fill="x", pady=(0, 10))

        form_row = tk.Frame(self.form_card.body, bg="#f0fdf4")
        form_row.pack(fill="x")

        tk.Label(form_row, text="Symbol:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sym_var = tk.StringVar()
        self.sym_combo = ttk.Combobox(form_row, textvariable=self.sym_var, width=13)
        self.sym_combo.pack(side="left", padx=(0, 12))

        tk.Label(form_row, text="Side:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.side_var = tk.StringVar(value="BUY")
        ttk.Combobox(form_row, textvariable=self.side_var, values=["BUY", "SELL"],
                      width=5, state="readonly").pack(side="left", padx=(0, 12))

        tk.Label(form_row, text="Qty:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.qty_var = tk.StringVar()
        ttk.Entry(form_row, textvariable=self.qty_var, width=9).pack(side="left", padx=(0, 12))

        tk.Label(form_row, text="Price:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.price_var = tk.StringVar()
        ttk.Entry(form_row, textvariable=self.price_var, width=9).pack(side="left", padx=(0, 12))

        tk.Label(form_row, text="Date:", font=FONT_BODY, bg="#f0fdf4", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form_row, textvariable=self.date_var, width=11).pack(side="left", padx=(0, 12))

        ttk.Button(form_row, text="➕ Add Position", command=self._add_trade,
                   style="Accent.TButton").pack(side="left", padx=4)

        # ── Summary Cards (Feature 48) ───────────────────────────────────
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="x", pady=(0, 8))
        cards_frame.columnconfigure(tuple(range(7)), weight=1, uniform="card")

        self.card_cost = InfoCard(cards_frame, "Total Cost Basis", "—", accent_color="#0284c7", icon="💼")
        self.card_cost.grid(row=0, column=0, padx=2, sticky="nsew")
        self.card_value = InfoCard(cards_frame, "Current Value", "—", accent_color="#4f46e5", icon="📈")
        self.card_value.grid(row=0, column=1, padx=2, sticky="nsew")
        self.card_pnl = InfoCard(cards_frame, "Total P&L", "—", accent_color="#059669", icon="💵")
        self.card_pnl.grid(row=0, column=2, padx=2, sticky="nsew")
        self.card_pnl_pct = InfoCard(cards_frame, "P&L %", "—", accent_color="#059669", icon="📊")
        self.card_pnl_pct.grid(row=0, column=3, padx=2, sticky="nsew")
        self.card_alpha = InfoCard(cards_frame, "Portfolio Alpha", "—", accent_color="#059669", icon="⚡")
        self.card_alpha.grid(row=0, column=4, padx=2, sticky="nsew")
        self.card_var = InfoCard(cards_frame, "Daily VaR (95%)", "—", accent_color="#e11d48", icon="🛡️")
        self.card_var.grid(row=0, column=5, padx=2, sticky="nsew")
        self.card_beta = InfoCard(cards_frame, "Portfolio Beta", "—", accent_color="#d97706", icon="⚖️")
        self.card_beta.grid(row=0, column=6, padx=2, sticky="nsew")

        # Risk & Concentration Warnings Banner
        self.lbl_risk_warnings = ttk.Label(self, text="", font=("Segoe UI", 9), foreground="#b91c1c")
        self.lbl_risk_warnings.pack(anchor="w", padx=4, pady=(0, 6))

        # ── Target Rebalancing Panel ────────────────────────────────────
        self._build_rebalance_panel()

        # ── Content: Table + Pie Chart ──────────────────────────────────
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Positions table
        table_frame = ttk.Frame(content)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        cols = ("id", "symbol", "industry", "side", "qty", "entry", "current", "pnl", "pnl_pct", "liq", "dte")
        self.tree = SortableTreeview(table_frame, columns=cols, height=14)
        self.tree.heading("id", text="ID")
        self.tree.heading("symbol", text="Symbol")
        self.tree.heading("industry", text="Industry")
        self.tree.heading("side", text="Side")
        self.tree.heading("qty", text="Qty")
        self.tree.heading("entry", text="Entry")
        self.tree.heading("current", text="Current")
        self.tree.heading("pnl", text="P&L")
        self.tree.heading("pnl_pct", text="P&L %")
        self.tree.heading("liq", text="Liquidity")
        self.tree.heading("dte", text="Days-to-Exit")

        self.tree.column("id", width=35, minwidth=25, anchor="center")
        self.tree.column("symbol", width=95, minwidth=75)
        self.tree.column("industry", width=120, minwidth=80)
        self.tree.column("side", width=50, minwidth=40, anchor="center")
        self.tree.column("qty", width=60, minwidth=45, anchor="e")
        self.tree.column("entry", width=70, minwidth=50, anchor="e")
        self.tree.column("current", width=70, minwidth=50, anchor="e")
        self.tree.column("pnl", width=80, minwidth=55, anchor="e")
        self.tree.column("pnl_pct", width=65, minwidth=50, anchor="e")
        self.tree.column("liq", width=80, minwidth=60, anchor="center")
        self.tree.column("dte", width=75, minwidth=55, anchor="center")

        scroller = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroller.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroller.pack(side="right", fill="y")

        self.tree.tag_configure("profit", foreground=WIN11_GREEN)
        self.tree.tag_configure("loss", foreground=WIN11_RED)

        # Delete button below table
        btn_bar = ttk.Frame(table_frame)
        btn_bar.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_bar, text="🗑️ Delete Selected", command=self._delete_trade).pack(side="left")

        # Pie chart container
        self.pie_frame = tk.Frame(content, bg=WIN11_CARD_BG, highlightbackground="#cbd5e1",
                                  highlightthickness=1, bd=0)
        self.pie_frame.grid(row=0, column=1, sticky="nsew")

    def on_tab_shown(self):
        self.load_data()

    def prefill(self, symbol: str, price: float, qty: int = 100):
        """Pre-fills the Add Position form with calculated trade details."""
        self.sym_var.set(symbol)
        self.side_var.set("BUY")
        self.price_var.set(f"{float(price):.2f}")
        self.qty_var.set(str(int(qty)))

    # ── Data Loading ────────────────────────────────────────────────────

    def load_data(self):
        self.app.set_status("Loading portfolio positions...")
        self.app.start_progress()

        try:
            symbols = self.app.engine.get_symbol_list()
            self.sym_combo["values"] = symbols
        except Exception:
            pass

        ThreadedTask(
            self.app.root, target=self._fetch_portfolio,
            on_done=self._on_portfolio_loaded,
            on_error=self._on_error,
        ).start()

    def _fetch_portfolio(self) -> list[dict]:
        return self.app.engine.get_portfolio_positions()

    def _on_portfolio_loaded(self, positions: list[dict]):
        self.tree.delete(*self.tree.get_children())

        total_cost = 0.0
        total_value = 0.0
        by_industry: dict[str, float] = {}

        for p in positions:
            pnl_str = fmt_currency(p["pnl"], "")
            pnl_pct_str = fmt_pct(p["pnl_pct"])
            tag = "profit" if p["pnl"] >= 0 else "loss"

            val = float(p.get("current_value", 0))
            liq = "Tier 1" if val >= 500_000 else ("Tier 2" if val >= 100_000 else "Tier 3")
            dte = f"{max(0.2, round(float(p.get('quantity', 100)) / 15000.0, 1))} d"

            self.tree.insert("", "end", values=(
                p["id"], p["symbol"], p["industry"], p["side"],
                f"{p['quantity']:.0f}",
                f"{p['entry_price']:.2f}",
                f"{p['current_price']:.2f}" if p["current_price"] else "—",
                pnl_str, pnl_pct_str, liq, dte
            ), tags=(tag,))

            total_cost += p["cost_basis"]
            total_value += p["current_value"]
            ind = p["industry"]
            by_industry[ind] = by_industry.get(ind, 0) + p["current_value"]

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

        pnl_color = WIN11_GREEN if total_pnl >= 0 else WIN11_RED

        self.card_cost.set(fmt_currency(total_cost))
        self.card_value.set(fmt_currency(total_value))
        self.card_pnl.set(fmt_currency(total_pnl), color=pnl_color)
        self.card_pnl_pct.set(fmt_pct(total_pnl_pct), color=pnl_color)

        # Portfolio Risk Analytics (Feature 48)
        risk_analysis = self.app.engine.evaluate_portfolio_risk(positions, cash=0.0)
        var_val = risk_analysis.get("var_95_daily_lkr", 0.0)
        var_pct = risk_analysis.get("var_95_pct", 0.0)
        alpha_val = risk_analysis.get("portfolio_alpha_pct", 0.0)
        alpha_color = WIN11_GREEN if alpha_val >= 0 else WIN11_RED

        self.card_alpha.set(f"{alpha_val:+.2f}% vs ASPI", color=alpha_color)
        self.card_var.set(f"{fmt_currency(var_val)} ({var_pct:.1f}%)")
        self.card_beta.set(f"{risk_analysis.get('portfolio_beta', 1.0):.2f}")

        warnings = risk_analysis.get("warnings", [])
        if warnings:
            self.lbl_risk_warnings.config(text="  •  ".join(warnings), foreground="#b91c1c")
        else:
            self.lbl_risk_warnings.config(
                text="✔ Healthy portfolio diversification: No heavy sector or position concentration warnings.",
                foreground="#059669"
            )

        # Pie chart
        self._render_pie(by_industry)

        self.app.stop_progress()
        self.app.set_status(f"Portfolio loaded: {len(positions)} positions")

    def _render_pie(self, by_industry: dict):
        if self._pie_canvas:
            self._pie_canvas.get_tk_widget().destroy()

        if not by_industry or all(v == 0 for v in by_industry.values()):
            lbl = tk.Label(self.pie_frame, text="No open positions", fg=WIN11_TEXT_MUTED, bg=WIN11_CARD_BG)
            lbl.pack(expand=True)
            return

        fig = Figure(figsize=(3.5, 3.5), dpi=90, facecolor="#ffffff")
        ax = fig.add_subplot(111)

        labels = list(by_industry.keys())
        sizes = list(by_industry.values())
        fluent_colors = ["#0078d4", "#107c10", "#8764b8", "#ff8c00", "#00bcf2", "#e3008c", "#008272", "#498205"]
        colors = [fluent_colors[i % len(fluent_colors)] for i in range(len(labels))]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.1f%%",
            colors=colors, textprops={"color": "#1e293b", "fontsize": 8, "fontweight": "bold"},
            pctdistance=0.8
        )
        ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.15),
                  fontsize=7, ncol=2, frameon=False, labelcolor="#334155")
        ax.set_facecolor("#ffffff")
        fig.subplots_adjust(bottom=0.2)

        self._pie_canvas = FigureCanvasTkAgg(fig, master=self.pie_frame)
        self._pie_canvas.draw()
        self._pie_canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    # ── Add / Delete ────────────────────────────────────────────────────

    def _add_trade(self):
        try:
            symbol = self.sym_var.get().strip().upper()
            side = self.side_var.get()
            qty = float(self.qty_var.get())
            price = float(self.price_var.get())
            trade_date = self.date_var.get().strip()
            if not symbol or qty <= 0 or price <= 0:
                raise ValueError("Invalid input")

            self.app.engine.add_portfolio_trade(symbol, side, qty, price, trade_date)
            self.app.set_status(f"Added {side} {qty:.0f} x {symbol} @ {price:.2f}")
            self.qty_var.set("")
            self.price_var.set("")
            self.load_data()
        except Exception as e:
            messagebox.showerror("Error", f"Could not add trade: {e}")

    def _build_rebalance_panel(self):
        """Builds the Portfolio Target Rebalancing FormCard panel."""
        self.rebalance_card = FormCard(
            self,
            title="⚖️ Portfolio Target Rebalancing",
            accent_color="#7c3aed",
            bg_color="#f3e8ff",
            border_color="#d8b4fe",
            icon="⚖️",
        )
        self.rebalance_card.pack(fill="x", pady=(0, 8))

        top_row = tk.Frame(self.rebalance_card.body, bg="#f3e8ff")
        top_row.pack(fill="x", pady=(0, 4))

        tk.Label(top_row, text="Allocation Model:", font=FONT_BODY, bg="#f3e8ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.rebal_mode_var = tk.StringVar(value="EQUAL_WEIGHT")
        mode_combo = ttk.Combobox(top_row, textvariable=self.rebal_mode_var, values=["EQUAL_WEIGHT", "CUSTOM"], width=16, state="readonly")
        mode_combo.pack(side="left", padx=(0, 12))

        tk.Label(top_row, text="Custom Weights (e.g. COMB:40, JKH:60):", font=FONT_BODY, bg="#f3e8ff", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.custom_weights_var = tk.StringVar()
        ttk.Entry(top_row, textvariable=self.custom_weights_var, width=30).pack(side="left", padx=(0, 12))

        ttk.Button(top_row, text="⚖️ Calculate Rebalance Plan", command=self._on_calculate_rebalance, style="Accent.TButton").pack(side="left", padx=4)
        ttk.Button(top_row, text="📥 Export Plan CSV", command=self._export_rebalance_csv).pack(side="left", padx=4)

        # Rebalance Trade Plan Treeview
        rebal_table_frame = ttk.Frame(self.rebalance_card.body)
        rebal_table_frame.pack(fill="x", expand=True, pady=(4, 0))

        rebal_cols = ("symbol", "action", "price", "curr_qty", "curr_pct", "target_pct", "target_qty", "trade_qty", "est_lkr")
        self.tree_rebal = SortableTreeview(rebal_table_frame, columns=rebal_cols, height=4)

        self.tree_rebal.heading("symbol", text="Symbol")
        self.tree_rebal.heading("action", text="Action")
        self.tree_rebal.heading("price", text="Price (LKR)")
        self.tree_rebal.heading("curr_qty", text="Current Qty")
        self.tree_rebal.heading("curr_pct", text="Current %")
        self.tree_rebal.heading("target_pct", text="Target %")
        self.tree_rebal.heading("target_qty", text="Target Qty")
        self.tree_rebal.heading("trade_qty", text="Trade Shares")
        self.tree_rebal.heading("est_lkr", text="Est Value (LKR)")

        self.tree_rebal.column("symbol", width=90, anchor="w")
        self.tree_rebal.column("action", width=70, anchor="center")
        self.tree_rebal.column("price", width=85, anchor="e")
        self.tree_rebal.column("curr_qty", width=80, anchor="e")
        self.tree_rebal.column("curr_pct", width=70, anchor="e")
        self.tree_rebal.column("target_pct", width=70, anchor="e")
        self.tree_rebal.column("target_qty", width=80, anchor="e")
        self.tree_rebal.column("trade_qty", width=85, anchor="e")
        self.tree_rebal.heading("est_lkr", text="Est Value (LKR)")
        self.tree_rebal.column("est_lkr", width=110, anchor="e")

        rebal_scroll = ttk.Scrollbar(rebal_table_frame, orient="vertical", command=self.tree_rebal.yview)
        self.tree_rebal.configure(yscrollcommand=rebal_scroll.set)
        self.tree_rebal.pack(side="left", fill="x", expand=True)
        rebal_scroll.pack(side="right", fill="y")

        self.tree_rebal.tag_configure("rebal_buy", foreground=WIN11_GREEN)
        self.tree_rebal.tag_configure("rebal_sell", foreground=WIN11_RED)

    def _on_calculate_rebalance(self):
        mode = self.rebal_mode_var.get()
        custom_str = self.custom_weights_var.get().strip()

        custom_map = {}
        if mode == "CUSTOM" and custom_str:
            try:
                parts = custom_str.split(",")
                for p in parts:
                    if ":" in p:
                        s, w = p.split(":")
                        custom_map[s.strip().upper()] = float(w.strip())
            except Exception:
                messagebox.showwarning("Rebalance", "Invalid custom weights format. Use 'SYMBOL:WEIGHT, SYMBOL2:WEIGHT'.")
                return

        self.app.set_status("Calculating portfolio rebalancing model...")

        def task():
            return self.app.engine.get_portfolio_rebalancing(
                target_mode=mode,
                custom_weights=custom_map if mode == "CUSTOM" else None
            )

        def on_done(res):
            trades = res.get("rebalance_trades", [])
            self.tree_rebal.delete(*self.tree_rebal.get_children())
            for t in trades:
                act = t.get("action", "HOLD")
                tag = "rebal_buy" if act == "BUY" else ("rebal_sell" if act == "SELL" else "")
                self.tree_rebal.insert("", "end", values=(
                    t.get("symbol", ""),
                    act,
                    f"{t.get('current_price', 0.0):.2f}",
                    t.get("current_qty", 0),
                    f"{t.get('current_pct', 0.0):.1f}%",
                    f"{t.get('target_pct', 0.0):.1f}%",
                    t.get("target_qty", 0),
                    t.get("shares_to_trade", 0),
                    fmt_currency(t.get("est_trade_lkr", 0.0), "")
                ), tags=(tag,))
            self.app.set_status(res.get("summary", "Rebalance calculation complete."))

        ThreadedTask(self.app.root, target=task, on_done=on_done, on_error=self._on_error).start()

    def _export_rebalance_csv(self):
        import csv
        from tkinter import filedialog
        children = self.tree_rebal.get_children()
        if not children:
            messagebox.showinfo("Export Rebalance Plan", "No rebalance trade plan rows available to export. Calculate a rebalance plan first.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export Rebalance Plan to CSV"
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Symbol", "Action", "Price (LKR)", "Current Qty", "Current %", "Target %", "Target Qty", "Trade Shares", "Est Value (LKR)"])
                for item_id in children:
                    vals = self.tree_rebal.item(item_id, "values")
                    writer.writerow(vals)
            messagebox.showinfo("Export Complete", f"Successfully exported rebalance plan to CSV:\n{filename}")
            self.app.set_status(f"Exported rebalance plan to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_csv(self):
        import csv
        from tkinter import filedialog
        positions = self.app.engine.get_portfolio_positions()
        if not positions:
            messagebox.showinfo("Export", "No portfolio positions available to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export Portfolio Positions to CSV"
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Trade ID", "Symbol", "Industry", "Side", "Quantity", "Entry Price (LKR)", "Current Price (LKR)", "Cost Basis (LKR)", "Current Value (LKR)", "P&L (LKR)", "P&L %", "Trade Date"])
                for p in positions:
                    writer.writerow([
                        p.get("id"), p.get("symbol"), p.get("industry"), p.get("side"),
                        p.get("quantity"), p.get("entry_price"), p.get("current_price"),
                        p.get("cost_basis"), p.get("current_value"), p.get("pnl"),
                        p.get("pnl_pct"), p.get("trade_date")
                    ])
            messagebox.showinfo("Export Complete", f"Successfully exported {len(positions)} positions to CSV:\n{filename}")
            self.app.set_status(f"Exported portfolio to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _delete_trade(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a position to delete")
            return
        trade_id = int(self.tree.item(sel[0], "values")[0])
        if messagebox.askyesno("Confirm", f"Delete trade #{trade_id}?"):
            try:
                self.app.engine.delete_portfolio_trade(trade_id)
                self.load_data()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_error(self, exc: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Portfolio error: {exc}")
