# views/watchlist.py  –  Smart Watchlist & Price Alerts Tab (Windows 11 Light)
"""
Real-time multi-watchlist management with threshold alert monitoring,
instant chart navigation, confluence badges, and Telegram push notifications.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import TYPE_CHECKING, Any, Dict, List

from ui_utils import (
    InfoCard, FormCard, SortableTreeview, ThreadedTask,
    fmt_currency, fmt_pct,
    WIN11_BG, WIN11_CARD_BG, WIN11_GREEN, WIN11_RED, WIN11_TEXT_MAIN,
    WIN11_TEXT_MUTED, FONT_TITLE, FONT_SECTION, FONT_BODY, FONT_BODY_BOLD,
    GRADE_A_PLUS, GRADE_A, GRADE_B, GRADE_C
)

if TYPE_CHECKING:
    from app import MainApp


class WatchlistTab(ttk.Frame):
    """Interactive multi-watchlist view with price alert detection and action triggers."""

    def __init__(self, parent, app: MainApp):
        super().__init__(parent, padding=(16, 12))
        self.app = app
        self._watchlist_items: List[Dict[str, Any]] = []
        self._build_ui()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))

        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="Smart Watchlist & Price Alerts", font=FONT_TITLE).pack(anchor="w")
        ttk.Label(title_box, text="Monitor your high-conviction CSE setups with automated upper & lower threshold detection",
                  font=("Segoe UI", 8), foreground=WIN11_TEXT_MUTED).pack(anchor="w")

        btn_box = ttk.Frame(header)
        btn_box.pack(side="right")
        ttk.Button(btn_box, text="🔔 Check Alerts Now", command=self._on_check_alerts).pack(side="left", padx=3)
        ttk.Button(btn_box, text="📱 Push to Telegram", command=self._on_push_telegram, style="Accent.TButton").pack(side="left", padx=3)
        ttk.Button(btn_box, text="🔄 Refresh", command=self.load_data).pack(side="left", padx=3)

        # ── Summary KPI Cards ───────────────────────────────────────────
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="x", pady=(0, 8))
        cards_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="wcards")

        self.card_list_name = InfoCard(cards_frame, "Active Watchlist", "—", accent_color="#d97706", icon="⭐")
        self.card_list_name.grid(row=0, column=0, padx=3, sticky="nsew")

        self.card_count = InfoCard(cards_frame, "Total Monitored", "0", accent_color="#0284c7", icon="📋")
        self.card_count.grid(row=0, column=1, padx=3, sticky="nsew")

        self.card_high_alerts = InfoCard(cards_frame, "High Alerts Hit", "0", accent_color="#059669", icon="🚀")
        self.card_high_alerts.grid(row=0, column=2, padx=3, sticky="nsew")

        self.card_low_alerts = InfoCard(cards_frame, "Support Breached", "0", accent_color="#c42b1c", icon="⚠️")
        self.card_low_alerts.grid(row=0, column=3, padx=3, sticky="nsew")

        # ── Watchlist Selector & Form Card ──────────────────────────────
        self.form_card = FormCard(
            self,
            title="Watchlist Manager & Stock Alert Entry",
            accent_color="#b45309",
            bg_color="#fffbeb",
            border_color="#fde68a",
            icon="⭐",
        )
        self.form_card.pack(fill="x", pady=(0, 8))

        form_top = tk.Frame(self.form_card.body, bg="#fffbeb")
        form_top.pack(fill="x", pady=(0, 4))

        # Watchlist Switcher row
        tk.Label(form_top, text="Select List:", font=FONT_BODY_BOLD, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.list_var = tk.StringVar()
        self.list_combo = ttk.Combobox(form_top, textvariable=self.list_var, width=22, state="readonly")
        self.list_combo.pack(side="left", padx=(0, 6))
        self.list_combo.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Button(form_top, text="➕ New List", command=self._create_new_list).pack(side="left", padx=2)
        ttk.Button(form_top, text="🗑 Delete List", command=self._delete_current_list).pack(side="left", padx=2)

        ttk.Separator(form_top, orient="vertical").pack(side="left", fill="y", padx=10)

        # Stock Add Row
        tk.Label(form_top, text="Symbol:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.sym_var = tk.StringVar()
        self.sym_combo = ttk.Combobox(form_top, textvariable=self.sym_var, width=13)
        self.sym_combo.pack(side="left", padx=(0, 8))

        tk.Label(form_top, text="Alert High ≥:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.alert_high_var = tk.StringVar()
        ttk.Entry(form_top, textvariable=self.alert_high_var, width=8).pack(side="left", padx=(0, 8))

        tk.Label(form_top, text="Alert Low ≤:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.alert_low_var = tk.StringVar()
        ttk.Entry(form_top, textvariable=self.alert_low_var, width=8).pack(side="left", padx=(0, 8))

        tk.Label(form_top, text="Notes:", font=FONT_BODY, bg="#fffbeb", fg=WIN11_TEXT_MAIN).pack(side="left", padx=(0, 4))
        self.notes_var = tk.StringVar()
        ttk.Entry(form_top, textvariable=self.notes_var, width=20).pack(side="left", padx=(0, 8))

        ttk.Button(form_top, text="➕ Add / Update", command=self._add_or_update_item, style="Accent.TButton").pack(side="left", padx=4)

        # ── Main Table Frame ────────────────────────────────────────────
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, pady=(0, 8))

        cols = [
            ("symbol", "Symbol", 120),
            ("industry", "Industry / Sector", 150),
            ("price", "Price (LKR)", 95),
            ("day_chg", "Day Chg %", 90),
            ("grade", "Confluence", 95),
            ("trend", "Trend", 120),
            ("alert_high", "Alert High (≥)", 105),
            ("alert_low", "Alert Low (≤)", 105),
            ("alert_status", "Alert Status", 150),
            ("notes", "Notes & Strategy", 220),
        ]
        self.tree = SortableTreeview(table_frame, cols)
        self.tree.pack(fill="both", expand=True)

        # Tree tags for color highlighting
        self.tree.tag_configure("positive", foreground=WIN11_GREEN)
        self.tree.tag_configure("negative", foreground=WIN11_RED)
        self.tree.tag_configure("alert_hit", background="#fef3c7", foreground="#92400e", font=FONT_BODY_BOLD)

        # Double click opens in Chart
        self.tree.bind("<Double-1>", lambda e: self._open_selected_in_chart())

        # ── Action Toolbar (Bottom) ─────────────────────────────────────
        action_bar = ttk.Frame(self)
        action_bar.pack(fill="x")

        ttk.Button(action_bar, text="📈 Open in Chart", command=self._open_selected_in_chart, style="Accent.TButton").pack(side="left", padx=3)
        ttk.Button(action_bar, text="💼 Send to Portfolio", command=self._send_selected_to_portfolio).pack(side="left", padx=3)
        ttk.Button(action_bar, text="🗑 Remove from Watchlist", command=self._remove_selected).pack(side="left", padx=3)
        ttk.Button(action_bar, text="💡 Set Quick ±5% Alerts", command=self._set_quick_pct_alerts).pack(side="left", padx=3)

        self.lbl_count_status = ttk.Label(action_bar, text="Tip: Double-click any stock to inspect on Interactive Chart.",
                                          font=("Segoe UI", 8), foreground=WIN11_TEXT_MUTED)
        self.lbl_count_status.pack(side="right", padx=6)

    # ── Lifecycle & Loading ─────────────────────────────────────────────

    def on_tab_shown(self):
        """Lazy loader when tab is selected."""
        self._refresh_watchlist_names()
        self._refresh_symbols_autocomplete()
        self.load_data()

    def _refresh_watchlist_names(self):
        try:
            names = self.app.engine.get_watchlist_names()
            self.list_combo["values"] = names
            if not self.list_var.get() or self.list_var.get() not in names:
                if names:
                    self.list_combo.current(0)
        except Exception:
            pass

    def _refresh_symbols_autocomplete(self):
        try:
            syms = self.app.engine.get_symbol_list()
            self.sym_combo["values"] = syms
        except Exception:
            pass

    def load_data(self):
        """Fetches items for the currently selected watchlist in a background thread."""
        lname = self.list_var.get()
        if not lname:
            self._refresh_watchlist_names()
            lname = self.list_var.get()
        if not lname:
            return

        self.app.set_status(f"Loading watchlist '{lname}'...")
        self.app.start_progress()

        ThreadedTask(
            self.app.root,
            target=lambda: self.app.engine.get_watchlist_items(lname),
            on_done=self._on_data_loaded,
            on_error=self._on_load_error,
        ).start()

    def _on_data_loaded(self, items: List[Dict[str, Any]]):
        self.app.stop_progress()
        self._watchlist_items = items
        self.tree.clear()

        high_hits = 0
        low_hits = 0

        for item in items:
            sym = item.get("symbol", "")
            ind = item.get("industry", "—")
            price = item.get("price", 0.0)
            chg = item.get("day_chg_pct", 0.0)
            grade = f"{item.get('grade', '—')} {item.get('stars', '')}".strip()
            trend = item.get("trend", "—")
            a_high = item.get("alert_high", 0.0)
            a_low = item.get("alert_low", 0.0)
            status = item.get("alert_status", "— Normal")
            notes = item.get("notes", "")

            # Tag evaluation
            tags = []
            if "High Hit" in status:
                tags.append("alert_hit")
                high_hits += 1
            elif "Low Hit" in status:
                tags.append("alert_hit")
                low_hits += 1
            elif chg > 0:
                tags.append("positive")
            elif chg < 0:
                tags.append("negative")

            row_vals = (
                sym,
                ind,
                f"{price:.2f}" if price > 0 else "—",
                f"{chg:+.2f}%" if price > 0 else "—",
                grade,
                trend,
                f"{a_high:.2f}" if a_high > 0 else "—",
                f"{a_low:.2f}" if a_low > 0 else "—",
                status,
                notes,
            )
            self.tree.insert("", "end", values=row_vals, tags=tags)

        # Update summary cards
        lname = self.list_var.get()
        self.card_list_name.set_value(lname[:18] + ("…" if len(lname) > 18 else ""))
        self.card_count.set_value(str(len(items)))
        self.card_high_alerts.set_value(str(high_hits))
        self.card_low_alerts.set_value(str(low_hits))

        msg = f"Watchlist '{lname}' loaded ({len(items)} stocks)."
        if high_hits > 0 or low_hits > 0:
            msg += f" ⚠️ {high_hits + low_hits} alert threshold(s) active!"
        self.app.set_status(msg)

    def _on_load_error(self, err: Exception):
        self.app.stop_progress()
        self.app.set_status(f"Error loading watchlist: {err}")

    # ── User Actions ────────────────────────────────────────────────────

    def _add_or_update_item(self):
        lname = self.list_var.get().strip()
        sym = self.sym_var.get().strip().upper()
        if not lname:
            messagebox.showwarning("Watchlist", "Please select or create a watchlist first.", parent=self)
            return
        if not sym:
            messagebox.showwarning("Watchlist", "Please enter or select a valid CSE symbol.", parent=self)
            return

        try:
            ah = float(self.alert_high_var.get().strip()) if self.alert_high_var.get().strip() else 0.0
        except ValueError:
            ah = 0.0

        try:
            al = float(self.alert_low_var.get().strip()) if self.alert_low_var.get().strip() else 0.0
        except ValueError:
            al = 0.0

        notes = self.notes_var.get().strip()

        try:
            self.app.engine.add_to_watchlist(lname, sym, alert_high=ah, alert_low=al, notes=notes)
            self.sym_var.set("")
            self.alert_high_var.set("")
            self.alert_low_var.set("")
            self.notes_var.set("")
            self.app.set_status(f"Added {sym} to {lname}")
            self.load_data()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add to watchlist: {e}", parent=self)

    def _create_new_list(self):
        new_name = simpledialog.askstring("New Watchlist", "Enter new watchlist name (e.g. '🔥 Breakouts'):", parent=self)
        if new_name and new_name.strip():
            clean_name = new_name.strip()
            self.list_var.set(clean_name)
            self._refresh_watchlist_names()
            self.list_var.set(clean_name)
            self.load_data()

    def _delete_current_list(self):
        lname = self.list_var.get()
        if not lname:
            return
        if messagebox.askyesno("Delete Watchlist", f"Are you sure you want to delete '{lname}' and all its items?", parent=self):
            try:
                self.app.engine.delete_watchlist(lname)
                self._refresh_watchlist_names()
                self.load_data()
                self.app.set_status(f"Deleted watchlist '{lname}'")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete watchlist: {e}", parent=self)

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Watchlist", "Please select a stock to remove.", parent=self)
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        sym = vals[0]
        lname = self.list_var.get()
        if messagebox.askyesno("Remove Stock", f"Remove {sym} from '{lname}'?", parent=self):
            try:
                self.app.engine.remove_from_watchlist(lname, sym)
                self.load_data()
                self.app.set_status(f"Removed {sym} from {lname}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove: {e}", parent=self)

    def _open_selected_in_chart(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        sym = vals[0]
        self.app.switch_to_chart(sym)

    def _send_selected_to_portfolio(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Watchlist", "Please select a stock first.", parent=self)
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        sym = vals[0]
        try:
            price = float(vals[2])
        except (ValueError, IndexError):
            price = 0.0
        self.app.switch_to_portfolio(sym, price, 1000)

    def _set_quick_pct_alerts(self):
        """Sets quick +5% upper alert and -5% lower alert for the selected stock."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Quick Alerts", "Please select a stock to set ±5% alerts.", parent=self)
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        sym = vals[0]
        try:
            cur_price = float(vals[2])
        except (ValueError, IndexError):
            cur_price = 0.0
        if cur_price <= 0:
            return

        high_tgt = round(cur_price * 1.05, 2)
        low_stop = round(cur_price * 0.95, 2)
        lname = self.list_var.get()

        self.app.engine.add_to_watchlist(
            lname, sym, alert_high=high_tgt, alert_low=low_stop,
            notes=f"Auto ±5% alert ({low_stop} - {high_tgt})"
        )
        self.app.set_status(f"Set ±5% alerts for {sym}: High={high_tgt}, Low={low_stop}")
        self.load_data()

    def _on_check_alerts(self):
        """Evaluates all watchlists and presents active alerts."""
        self.app.set_status("Scanning watchlists for triggered price alerts...")
        self.app.start_progress()

        def _do_check():
            return self.app.engine.check_watchlist_alerts()

        def _on_done(alerts: List[Dict[str, Any]]):
            self.app.stop_progress()
            self.load_data()
            if not alerts:
                messagebox.showinfo(
                    "Price Alerts",
                    "✅ All monitored stocks are within normal price ranges.\nNo alert thresholds triggered at this time.",
                    parent=self
                )
                self.app.set_status("Alert scan complete: No thresholds breached.")
                return

            # Display modal with triggered alerts
            lines = [f"Found {len(alerts)} active price alert(s):\n"]
            for a in alerts:
                kind = "🚀 TARGET HIT" if a['type'] == "HIGH_BREAKOUT" else "⚠️ SUPPORT BREACH"
                lines.append(f"• {a['symbol']} in [{a['list_name']}] | Price: {a['current_price']:.2f} LKR ({kind} threshold: {a['threshold']:.2f})")

            lines.append("\nWould you like to dispatch these alerts to Telegram now?")
            if messagebox.askyesno("Active Price Alerts", "\n".join(lines), parent=self):
                self._dispatch_telegram(alerts)

        ThreadedTask(self.app.root, target=_do_check, on_done=_on_done).start()

    def _on_push_telegram(self):
        """Fetches active alerts and pushes them directly to Telegram."""
        self.app.set_status("Preparing Telegram alert broadcast...")
        self.app.start_progress()

        def _do_fetch_and_push():
            alerts = self.app.engine.check_watchlist_alerts(self.list_var.get())
            if not alerts:
                items = self.app.engine.get_watchlist_items(self.list_var.get())
                if not items:
                    return "Watchlist is empty."
                return f"No price alerts currently triggered for '{self.list_var.get()}'. Set tighter alert high/low thresholds to receive alerts."
            return self.app.engine.send_watchlist_telegram_alerts(alerts)

        def _on_done(msg: str):
            self.app.stop_progress()
            self.app.set_status(msg)
            messagebox.showinfo("Telegram Dispatch", msg, parent=self)

        ThreadedTask(self.app.root, target=_do_fetch_and_push, on_done=_on_done).start()

    def _dispatch_telegram(self, alerts: List[Dict[str, Any]]):
        self.app.set_status("Sending alerts to Telegram...")
        ThreadedTask(
            self.app.root,
            target=lambda: self.app.engine.send_watchlist_telegram_alerts(alerts),
            on_done=lambda msg: messagebox.showinfo("Telegram Dispatch", msg, parent=self),
        ).start()
