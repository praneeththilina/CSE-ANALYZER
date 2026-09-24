# ui/charts/canvas_candlestick.py  –  Ultra-Fast Pure Canvas Candlestick Chart
"""
Zero-lag 60 FPS pure Tkinter Canvas candlestick renderer with visible-window
drawing, vectorized NumPy coordinate scaling, drag-to-pan, mouse-wheel zoom,
crosshair with dynamic OHLCV readout, indicator overlays, and trade levels.
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from ui.theme.tokens import ThemeManager, FONTS


class CanvasCandlestick(tk.Frame):
    """High-performance pure Canvas candlestick chart without Matplotlib CPU freeze."""

    def __init__(
        self,
        parent,
        df: Optional[pd.DataFrame] = None,
        overlays: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        tokens = ThemeManager.tokens()
        super().__init__(parent, bg=tokens["surface"], **kwargs)

        self._df: pd.DataFrame = pd.DataFrame()
        self._overlays: Dict[str, Any] = overlays or {}

        # Viewport state
        self._visible_count: int = 120    # Number of visible candles
        self._end_index: int = 0          # Rightmost visible bar index
        self._drag_start_x: Optional[int] = None
        self._drag_start_end_index: int = 0
        self._last_motion_time: float = 0.0

        # Layout margins
        self.m_left = 10
        self.m_right = 75   # Price axis
        self.m_top = 34     # Header OHLC status
        self.m_bottom = 28  # Date axis
        self.vol_height_pct = 0.20

        # Header OHLC readout bar
        self._header_frame = tk.Frame(self, bg=tokens["surface"], padx=10, pady=4)
        self._header_frame.pack(fill="x")

        self._sym_label = tk.Label(
            self._header_frame,
            text="",
            font=FONTS["body_bold"],
            fg=tokens["text"],
            bg=tokens["surface"]
        )
        self._sym_label.pack(side="left", padx=(0, 10))

        self._ohlc_label = tk.Label(
            self._header_frame,
            text="Hover over chart for OHLCV data",
            font=FONTS["mono"],
            fg=tokens["text_dim"],
            bg=tokens["surface"]
        )
        self._ohlc_label.pack(side="left")

        # Main Interactive Canvas
        self.canvas = tk.Canvas(
            self,
            bg=tokens["surface"],
            highlightthickness=0,
            bd=0,
            cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True)

        # Event bindings
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

        ThemeManager.register_listener(self._on_theme_change)

        if df is not None and not df.empty:
            self.set_data(df, overlays)

    def set_data(self, df: pd.DataFrame, overlays: Optional[Dict[str, Any]] = None, symbol: str = ""):
        """Load new historical bars and redraw."""
        if df is None or df.empty:
            self._df = pd.DataFrame()
            self._redraw()
            return

        self._df = df.copy()
        self._overlays = overlays or {}
        self._end_index = len(self._df)
        self._visible_count = min(120, len(self._df))

        if symbol:
            self._sym_label.config(text=symbol)
        elif "symbol" in self._df.columns:
            self._sym_label.config(text=str(self._df["symbol"].iloc[-1]))

        self._redraw()

    def _on_resize(self, _):
        self._redraw()

    def _on_mouse_down(self, event):
        self._drag_start_x = event.x
        self._drag_start_end_index = self._end_index

    def _on_mouse_drag(self, event):
        if self._drag_start_x is None or self._df.empty:
            return
        dx = event.x - self._drag_start_x
        bar_width = max(1, (self.canvas.winfo_width() - self.m_left - self.m_right) / max(1, self._visible_count))
        bars_shifted = int(dx / bar_width)

        new_end = self._drag_start_end_index - bars_shifted
        new_end = max(self._visible_count, min(len(self._df), new_end))

        if new_end != self._end_index:
            self._end_index = new_end
            self._redraw()

    def _on_mouse_up(self, _):
        self._drag_start_x = None

    def _on_mouse_wheel(self, event):
        """Zoom in or out centered on the cursor."""
        if self._df.empty:
            return
        # event.delta is typically +120 (zoom in) or -120 (zoom out)
        factor = -1 if event.delta > 0 else 1
        delta_bars = int(self._visible_count * 0.15) * factor
        new_count = max(20, min(len(self._df), self._visible_count + delta_bars))

        if new_count != self._visible_count:
            self._visible_count = new_count
            self._end_index = max(self._visible_count, min(len(self._df), self._end_index))
            self._redraw()

    def _on_double_click(self, _):
        """Reset zoom to default right-aligned 120 bars."""
        if not self._df.empty:
            self._visible_count = min(120, len(self._df))
            self._end_index = len(self._df)
            self._redraw()

    def _on_mouse_move(self, event):
        """Update crosshair and OHLCV readout on mouse hover."""
        if self._df.empty:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        chart_w = w - self.m_left - self.m_right

        if event.x < self.m_left or event.x > (w - self.m_right) or event.y < self.m_top or event.y > (h - self.m_bottom):
            self.canvas.delete("crosshair")
            return

        tokens = ThemeManager.tokens()

        # Delete previous crosshair lines and axis labels
        self.canvas.delete("crosshair")

        # Draw vertical line
        self.canvas.create_line(
            event.x, self.m_top, event.x, h - self.m_bottom,
            fill=tokens["border"], dash=(2, 2), tags="crosshair"
        )

        # Draw horizontal line
        self.canvas.create_line(
            self.m_left, event.y, w - self.m_right, event.y,
            fill=tokens["border"], dash=(2, 2), tags="crosshair"
        )

        # Determine hovered bar index
        start_idx = max(0, self._end_index - self._visible_count)
        slice_df = self._df.iloc[start_idx:self._end_index]
        n_bars = len(slice_df)

        if n_bars > 0:
            rel_x = event.x - self.m_left
            bar_w = chart_w / n_bars
            bar_idx = min(n_bars - 1, max(0, int(rel_x / bar_w)))
            bar = slice_df.iloc[bar_idx]

            # Price calculations for Y-axis tag
            chart_h = (h - self.m_top - self.m_bottom) * (1.0 - self.vol_height_pct)
            highs = slice_df["high"].values
            lows = slice_df["low"].values
            min_p = float(np.nanmin(lows)) * 0.995
            max_p = float(np.nanmax(highs)) * 1.005
            p_range = max_p - min_p if max_p > min_p else 1.0

            cursor_price = max_p - ((event.y - self.m_top) / max(1, chart_h)) * p_range

            # Price pill on right axis
            self.canvas.create_rectangle(
                w - self.m_right + 2, event.y - 10, w - 4, event.y + 10,
                fill=tokens["accent"], outline=tokens["accent"], tags="crosshair"
            )
            self.canvas.create_text(
                w - (self.m_right / 2), event.y,
                text=f"{cursor_price:.2f}",
                fill="#ffffff", font=FONTS["mono_bold"], tags="crosshair"
            )

            # Update Header OHLC Text
            o_val = float(bar.get("open", bar["close"]))
            h_val = float(bar["high"])
            l_val = float(bar["low"])
            c_val = float(bar["close"])
            v_val = int(bar.get("volume", 0))
            chg = ((c_val - o_val) / o_val) * 100.0 if o_val > 0 else 0.0

            d_str = str(bar.name if isinstance(bar.name, (str, pd.Timestamp)) else bar.get("date", ""))[:10]
            chg_sign = "+" if chg >= 0 else ""
            chg_col = tokens["gain"] if chg >= 0 else tokens["loss"]

            self._ohlc_label.config(
                text=f"Date: {d_str}  |  O: {o_val:.2f}  H: {h_val:.2f}  L: {l_val:.2f}  C: {c_val:.2f}  Vol: {v_val:,}  Chg: {chg_sign}{chg:.2f}%",
                fg=chg_col
            )

    def _redraw(self):
        """Full canvas render pass."""
        self.canvas.delete("all")
        if self._df.empty:
            tokens = ThemeManager.tokens()
            w = self.canvas.winfo_width() or 600
            h = self.canvas.winfo_height() or 400
            self.canvas.create_text(
                w / 2, h / 2,
                text="No chart data available. Select a symbol to display.",
                fill=tokens["text_dim"], font=FONTS["subtitle"]
            )
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:
            return

        tokens = ThemeManager.tokens()

        # Dimensions
        chart_w = w - self.m_left - self.m_right
        total_chart_h = h - self.m_top - self.m_bottom
        vol_h = total_chart_h * self.vol_height_pct
        price_h = total_chart_h - vol_h - 10

        # Visible slice
        start_idx = max(0, self._end_index - self._visible_count)
        slice_df = self._df.iloc[start_idx:self._end_index]
        n_bars = len(slice_df)
        if n_bars < 2:
            return

        close = slice_df["close"].values.astype(float)
        high = slice_df["high"].values.astype(float)
        low = slice_df["low"].values.astype(float)
        op = (slice_df["open"].values if "open" in slice_df.columns else close).astype(float)
        vol = (slice_df["volume"].values if "volume" in slice_df.columns else np.zeros(n_bars)).astype(float)

        min_p = float(np.nanmin(low)) * 0.995
        max_p = float(np.nanmax(high)) * 1.005
        p_range = max_p - min_p if max_p > min_p else 1.0

        max_v = float(np.nanmax(vol)) if np.nanmax(vol) > 0 else 1.0

        bar_w = chart_w / n_bars
        candle_body_w = max(2, bar_w * 0.68)

        # ── 1. Draw Grid Lines & Price Axis ─────────────────────────────
        n_grid_lines = 6
        for g in range(n_grid_lines + 1):
            py = self.m_top + (g / n_grid_lines) * price_h
            price_val = max_p - (g / n_grid_lines) * p_range
            self.canvas.create_line(
                self.m_left, py, w - self.m_right, py,
                fill=tokens["surface_hi"], width=1, tags="grid"
            )
            self.canvas.create_text(
                w - self.m_right + 8, py,
                text=f"{price_val:.2f}",
                anchor="w",
                fill=tokens["text_dim"], font=FONTS["mono"], tags="axis"
            )

        # Volume separator line
        vol_top_y = self.m_top + price_h + 10
        self.canvas.create_line(
            self.m_left, vol_top_y, w - self.m_right, vol_top_y,
            fill=tokens["border"], width=1, tags="grid"
        )
        self.canvas.create_text(
            w - self.m_right + 8, vol_top_y + (vol_h / 2),
            text=f"Vol {max_v / 1000:.0f}K",
            anchor="w",
            fill=tokens["text_subtle"], font=FONTS["caption"], tags="axis"
        )

        # ── 2. Vectorized Math & Candle Drawing ─────────────────────────
        xs = self.m_left + (np.arange(n_bars) + 0.5) * bar_w
        high_ys = self.m_top + (1.0 - (high - min_p) / p_range) * price_h
        low_ys = self.m_top + (1.0 - (low - min_p) / p_range) * price_h
        open_ys = self.m_top + (1.0 - (op - min_p) / p_range) * price_h
        close_ys = self.m_top + (1.0 - (close - min_p) / p_range) * price_h

        gain_color = tokens["gain"]
        loss_color = tokens["loss"]

        for i in range(n_bars):
            x = xs[i]
            hy = high_ys[i]
            ly = low_ys[i]
            oy = open_ys[i]
            cy = close_ys[i]

            is_up = close[i] >= op[i]
            c_color = gain_color if is_up else loss_color

            # Wick line
            self.canvas.create_line(x, hy, x, ly, fill=c_color, width=1, tags="candles")

            # Candle Body
            top_b = min(oy, cy)
            bot_b = max(oy, cy)
            if (bot_b - top_b) < 1.5:
                bot_b = top_b + 1.5

            self.canvas.create_rectangle(
                x - candle_body_w / 2, top_b,
                x + candle_body_w / 2, bot_b,
                fill=c_color, outline=c_color, tags="candles"
            )

            # Volume Bar
            v_val = vol[i]
            v_bar_h = (v_val / max_v) * (vol_h - 4) if max_v > 0 else 0
            v_top = vol_top_y + vol_h - v_bar_h
            v_bot = vol_top_y + vol_h

            v_fill = tokens["gain_bg"] if is_up else tokens["loss_bg"]
            self.canvas.create_rectangle(
                x - candle_body_w / 2, v_top,
                x + candle_body_w / 2, v_bot,
                fill=v_fill, outline=c_color, width=1, tags="volume"
            )

        # ── 3. Date Axis Ticks ──────────────────────────────────────────
        step = max(1, n_bars // 6)
        for i in range(0, n_bars, step):
            bar = slice_df.iloc[i]
            d_val = str(bar.name if isinstance(bar.name, (str, pd.Timestamp)) else bar.get("date", ""))[:10]
            x = xs[i]
            self.canvas.create_text(
                x, h - (self.m_bottom / 2),
                text=d_val,
                fill=tokens["text_dim"], font=FONTS["caption"], tags="axis"
            )

        # ── 4. Technical Indicator Overlays ─────────────────────────────
        # 20 EMA & 50 EMA
        if "ema20" in self._overlays and len(self._overlays["ema20"]) == len(self._df):
            self._draw_overlay_line(xs, self._overlays["ema20"][start_idx:self._end_index], min_p, p_range, price_h, "#3b82f6", width=1.5)
        elif len(self._df) >= 20:
            ema20_vals = self._df["close"].ewm(span=20, adjust=False).mean().values[start_idx:self._end_index]
            self._draw_overlay_line(xs, ema20_vals, min_p, p_range, price_h, "#3b82f6", width=1.5)

        if "ema50" in self._overlays and len(self._overlays["ema50"]) == len(self._df):
            self._draw_overlay_line(xs, self._overlays["ema50"][start_idx:self._end_index], min_p, p_range, price_h, "#f59e0b", width=1.5)
        elif len(self._df) >= 50:
            ema50_vals = self._df["close"].ewm(span=50, adjust=False).mean().values[start_idx:self._end_index]
            self._draw_overlay_line(xs, ema50_vals, min_p, p_range, price_h, "#f59e0b", width=1.5)

        # Trade Level Lines (Entry, Targets, Stops)
        trade_levels = self._overlays.get("levels", {})
        if trade_levels:
            self._draw_level_line("Entry", trade_levels.get("entry"), tokens["accent"], min_p, p_range, price_h, chart_w)
            self._draw_level_line("Target 1", trade_levels.get("target1"), tokens["gain"], min_p, p_range, price_h, chart_w)
            self._draw_level_line("Target 2", trade_levels.get("target2"), "#059669", min_p, p_range, price_h, chart_w)
            self._draw_level_line("Stop Loss", trade_levels.get("stop_loss"), tokens["loss"], min_p, p_range, price_h, chart_w)

    def _draw_overlay_line(self, xs: np.ndarray, vals: np.ndarray, min_p: float, p_range: float, price_h: float, color: str, width: float = 1.5):
        ys = self.m_top + (1.0 - (vals - min_p) / p_range) * price_h
        pts = []
        for i in range(len(xs)):
            if not np.isnan(ys[i]):
                pts.extend([float(xs[i]), float(ys[i])])
        if len(pts) >= 4:
            self.canvas.create_line(*pts, fill=color, width=width, smooth=True, tags="overlays")

    def _draw_level_line(self, label: str, price: Optional[float], color: str, min_p: float, p_range: float, price_h: float, chart_w: float):
        if price is None or price <= 0:
            return
        if price < min_p or price > (min_p + p_range):
            return
        y = self.m_top + (1.0 - (price - min_p) / p_range) * price_h
        self.canvas.create_line(self.m_left, y, self.m_left + chart_w, y, fill=color, dash=(3, 3), width=1.5, tags="levels")
        self.canvas.create_text(
            self.m_left + 8, y - 8,
            text=f"{label}: LKR {price:.2f}",
            anchor="w",
            fill=color, font=FONTS["caption"], tags="levels"
        )

    def _on_theme_change(self, mode: str):
        tokens = ThemeManager.tokens()
        self.configure(bg=tokens["surface"])
        self._header_frame.configure(bg=tokens["surface"])
        self._sym_label.configure(bg=tokens["surface"], fg=tokens["text"])
        self._ohlc_label.configure(bg=tokens["surface"], fg=tokens["text_dim"])
        self.canvas.configure(bg=tokens["surface"])
        self._redraw()
