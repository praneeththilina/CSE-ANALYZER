# core/data_engine.py  –  Data access layer for CSE Analyzer
"""
Wraps the parent project's stocks.py & qqe_backtest_signals.py so that the
desktop UI never imports them directly.  All heavy I/O runs in background
threads via ThreadedTask (see ui_utils.py).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Parent-project modules (available via sys.path set in main.py)
import stocks
import qqe_backtest_signals as qbs


class DataEngine:
    """Singleton-ish data access object."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            parent_dir = Path(__file__).resolve().parent.parent.parent
            db_path = parent_dir / "cse_signals.db"
        self.db_path = str(db_path)
        self._session = stocks.mk_session(timeout=40)
        self._symbol_cache: list[str] | None = None

    # ── Connection helpers ──────────────────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        return stocks.db_connect(self.db_path)

    @property
    def session(self):
        return self._session

    # ── Symbols ─────────────────────────────────────────────────────────

    def get_all_symbols(self) -> List[Dict[str, Any]]:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT symbol, COALESCE(industry,''), COALESCE(enabled,0) "
                "FROM symbols ORDER BY symbol"
            ).fetchall()
            return [{"symbol": r[0], "industry": r[1], "enabled": int(r[2])} for r in rows]
        finally:
            con.close()

    def get_enabled_symbols(self) -> List[str]:
        con = self.connect()
        try:
            return stocks.fetch_symbols_from_db(con, only_enabled=True)
        finally:
            con.close()

    def get_symbol_list(self, force_refresh: bool = False) -> List[str]:
        if self._symbol_cache is not None and not force_refresh:
            return self._symbol_cache
        con = self.connect()
        try:
            rows = con.execute("SELECT symbol FROM symbols ORDER BY symbol").fetchall()
            self._symbol_cache = [r[0] for r in rows]
            return self._symbol_cache
        finally:
            con.close()

    def toggle_symbol(self, symbol: str, enabled: int):
        con = self.connect()
        try:
            con.execute("UPDATE symbols SET enabled=? WHERE symbol=?", (enabled, symbol))
            con.commit()
        finally:
            con.close()

    # ── Bars / Price data ───────────────────────────────────────────────

    def get_bars(self, symbol: str) -> pd.DataFrame:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT date, close, high, low, volume FROM bars "
                "WHERE symbol=? ORDER BY date", (symbol,)
            ).fetchall()
            if not rows:
                return pd.DataFrame(columns=["date", "close", "high", "low", "volume"])
            df = pd.DataFrame(rows, columns=["date", "close", "high", "low", "volume"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            for c in ["close", "high", "low", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["volume"] = df["volume"].fillna(0)
            # Synthesize 'open' from previous close
            df["open"] = df["close"].shift(1)
            if not df.empty:
                df.iloc[0, df.columns.get_loc("open")] = df.iloc[0]["close"]
            return df.dropna(subset=["close"])
        finally:
            con.close()

    def get_latest_prices(self) -> Dict[str, float]:
        con = self.connect()
        try:
            q = """
            SELECT symbol, close
            FROM (
                SELECT symbol, close,
                       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) as rn
                FROM bars
            ) WHERE rn = 1;
            """
            rows = con.execute(q).fetchall()
            return {sym: float(price) for sym, price in rows}
        finally:
            con.close()

    def get_symbol_industries(self) -> Dict[str, str]:
        con = self.connect()
        try:
            rows = con.execute("SELECT symbol, industry FROM symbols").fetchall()
            return {sym: (ind or "Unknown") for sym, ind in rows}
        finally:
            con.close()

    # ── Dashboard summary ───────────────────────────────────────────────

    def get_dashboard_summary(self) -> Dict[str, Any]:
        con = self.connect()
        try:
            def safe(sql, params=(), default=0):
                try:
                    row = con.execute(sql, params).fetchone()
                    return row[0] if row and row[0] is not None else default
                except Exception:
                    return default

            seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
            return {
                "symbols_total": safe("SELECT COUNT(*) FROM symbols"),
                "symbols_enabled": safe("SELECT COUNT(*) FROM symbols WHERE enabled=1"),
                "bars_total": safe("SELECT COUNT(*) FROM bars"),
                "last_bar_date": safe("SELECT MAX(date) FROM bars", default="—"),
                "last_signal_date": safe("SELECT MAX(date) FROM signals", default="—"),
                "long_7d": safe("SELECT COUNT(*) FROM signals WHERE date>=? AND signal=1", (seven_days_ago,)),
                "short_7d": safe("SELECT COUNT(*) FROM signals WHERE date>=? AND signal=-1", (seven_days_ago,)),
            }
        finally:
            con.close()

    def get_recent_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT date, symbol, signal FROM signals ORDER BY date DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [{"date": r[0], "symbol": r[1], "signal": int(r[2])} for r in rows]
        finally:
            con.close()

    # ── CSE Live API calls & Database Movers ─────────────────────────────

    def get_db_movers(self, limit: int = 15) -> Tuple[List[Dict], List[Dict]]:
        """Calculate top gainers and losers from historical bars in the database in ~15ms."""
        con = self.connect()
        try:
            latest_date_row = con.execute("SELECT MAX(date) FROM bars").fetchone()
            if not latest_date_row or not latest_date_row[0]:
                return [], []
            latest_date = latest_date_row[0]

            q_base = """
            SELECT b1.symbol, b1.close,
                   ROUND(((b1.close - b2.close) / b2.close) * 100, 2) as pct_change,
                   b1.volume
            FROM bars b1
            JOIN (
                SELECT symbol, close,
                       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) as rn
                FROM bars
            ) b2 ON b1.symbol = b2.symbol AND b2.rn = 2
            WHERE b1.date = ? AND b1.close > 0 AND b2.close > 0
            """

            gainers_rows = con.execute(f"{q_base} AND pct_change > 0 ORDER BY pct_change DESC LIMIT ?", (latest_date, limit)).fetchall()
            losers_rows = con.execute(f"{q_base} AND pct_change < 0 ORDER BY pct_change ASC LIMIT ?", (latest_date, limit)).fetchall()

            gainers = [
                {"symbol": r[0], "price": float(r[1]), "change": float(r[2]), "volume": float(r[3])}
                for r in gainers_rows
            ]
            losers = [
                {"symbol": r[0], "price": float(r[1]), "change": float(r[2]), "volume": float(r[3])}
                for r in losers_rows
            ]
            return gainers, losers
        except Exception:
            return [], []
        finally:
            con.close()

    def get_top_gainers(self) -> List[Dict]:
        try:
            data = stocks.api_top_gainers(self._session)
            return self._extract_top_list(data)
        except Exception:
            return []

    def get_top_losers(self) -> List[Dict]:
        try:
            data = stocks.api_top_losers(self._session)
            return self._extract_top_list(data)
        except Exception:
            return []

    def get_top_gainers_raw(self) -> dict:
        try:
            return stocks.api_top_gainers(self._session)
        except Exception:
            return {}

    def get_top_losers_raw(self) -> dict:
        try:
            return stocks.api_top_losers(self._session)
        except Exception:
            return {}

    def get_company_profile(self, symbol: str) -> dict:
        try:
            return stocks.api_company_profile(self._session, symbol)
        except Exception:
            return {}

    @staticmethod
    def _extract_top_list(data: dict | list) -> List[Dict]:
        items = []
        possible_keys = ["reqTradeSummery", "data", "records"]
        data_list = data if isinstance(data, list) else None
        if not data_list:
            for key in possible_keys:
                if isinstance(data, dict) and isinstance(data.get(key), list):
                    data_list = data[key]
                    break
        if not data_list:
            return []
        for item in data_list[:15]:
            symbol = item.get("symbol") or item.get("security") or ""
            pct = item.get("percentageChange") or item.get("changePer") or 0
            price = item.get("closingPrice") or item.get("price") or item.get("lastTradedPrice") or 0
            vol = item.get("shareVolume") or item.get("volume") or 0
            try:
                items.append({
                    "symbol": str(symbol),
                    "change": float(pct),
                    "price": float(price),
                    "volume": float(vol),
                })
            except (ValueError, TypeError):
                continue
        return items

    # ── Advanced Technical Engines (Divergence, Multi-Timeframe, Fibonacci) ─

    @staticmethod
    def detect_divergence(df: pd.DataFrame, lookback: int = 30) -> Dict[str, Any]:
        """
        Detects Regular Bullish or Bearish Divergence between Price and 14-day RSI.
        """
        if df.empty or len(df) < 25:
            return {"bullish": False, "bearish": False, "text": "—"}

        close = df["close"]
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        recent_close = close.tail(lookback).values
        recent_rsi = rsi.tail(lookback).values
        n = len(recent_close)

        # Detect local swing lows
        lows = []
        for i in range(2, n - 2):
            if recent_close[i] <= recent_close[i - 1] and recent_close[i] <= recent_close[i - 2] and \
               recent_close[i] <= recent_close[i + 1] and recent_close[i] <= recent_close[i + 2]:
                lows.append((i, recent_close[i], recent_rsi[i]))

        bullish = False
        if len(lows) >= 2:
            prev_low, curr_low = lows[-2], lows[-1]
            if curr_low[1] < prev_low[1] and curr_low[2] > (prev_low[2] + 1.0) and curr_low[2] < 50:
                bullish = True

        # Detect local swing highs
        highs = []
        for i in range(2, n - 2):
            if recent_close[i] >= recent_close[i - 1] and recent_close[i] >= recent_close[i - 2] and \
               recent_close[i] >= recent_close[i + 1] and recent_close[i] >= recent_close[i + 2]:
                highs.append((i, recent_close[i], recent_rsi[i]))

        bearish = False
        if len(highs) >= 2:
            prev_high, curr_high = highs[-2], highs[-1]
            if curr_high[1] > prev_high[1] and curr_high[2] < (prev_high[2] - 1.0) and curr_high[2] > 50:
                bearish = True

        text = "🎯 Bullish Div" if bullish else ("⚠️ Bearish Div" if bearish else "—")
        return {"bullish": bullish, "bearish": bearish, "text": text}

    @staticmethod
    def compute_weekly_trend(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Resamples daily bars to weekly bars and checks 20-week EMA macro trend.
        """
        if df.empty or len(df) < 25:
            return {"weekly_bullish": True, "weekly_text": "▲ Bullish"}

        try:
            df_w = df.resample("W-FRI").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum"
            }).dropna(subset=["close"])

            if len(df_w) < 5:
                return {"weekly_bullish": True, "weekly_text": "▲ Bullish"}

            span = min(20, len(df_w))
            w_ema = df_w["close"].ewm(span=span, adjust=False).mean()
            last_close = float(df_w["close"].iloc[-1])
            last_w_ema = float(w_ema.iloc[-1])

            is_bull = last_close >= last_w_ema
            return {
                "weekly_bullish": is_bull,
                "weekly_text": "▲ Bullish" if is_bull else "▼ Bearish",
                "weekly_ema": round(last_w_ema, 2),
            }
        except Exception:
            return {"weekly_bullish": True, "weekly_text": "▲ Bullish"}

    @staticmethod
    def compute_fibonacci_levels(df: pd.DataFrame, lookback: int = 120) -> Dict[str, float]:
        """
        Computes standard Fibonacci retracement levels from highest high to lowest low.
        """
        if df.empty or len(df) < 10:
            return {}

        sub = df.tail(lookback)
        high_max = float(sub["high"].max())
        low_min = float(sub["low"].min())
        diff = high_max - low_min
        if diff <= 0:
            return {}

        return {
            "fib_0": round(high_max, 2),
            "fib_236": round(high_max - 0.236 * diff, 2),
            "fib_382": round(high_max - 0.382 * diff, 2),
            "fib_500": round(high_max - 0.500 * diff, 2),
            "fib_618": round(high_max - 0.618 * diff, 2),
            "fib_786": round(high_max - 0.786 * diff, 2),
            "fib_100": round(low_min, 2),
        }

    def send_telegram_signals(self, signals: List[Dict[str, Any]]) -> str:
        """
        Broadcasts high-conviction signals to Telegram using formatted cards.
        """
        if not signals:
            return "No signals provided to send."

        top_signals = [s for s in signals if s.get("grade") in ["A+", "A"]][:5]
        if not top_signals:
            top_signals = signals[:3]

        lines = [
            "🚀 *CSE High-Conviction Signal Alert*",
            f"📅 *Date:* `{top_signals[0].get('date', 'Today')}`",
            "────────────────────────",
        ]
        for s in top_signals:
            sym = s.get("symbol", "")
            sig = s.get("signal_text", "LONG")
            grade = s.get("grade", "A")
            stars = s.get("stars", "★★★★")
            price = s.get("price", "0.00")
            sl = s.get("stop_loss", "0.00")
            t1 = s.get("target1", "0.00")
            t2 = s.get("target2", "0.00")
            vol = s.get("vol_ratio", "1.0x")
            div = s.get("divergence", "—")
            weekly = s.get("weekly_trend", "▲ Bullish")

            lines.append(f"*{sym}* | `{sig}` ({grade} {stars})")
            lines.append(f"• *Entry:* `{price} LKR` | *Stop:* `{sl} LKR`")
            lines.append(f"• *Target 1:* `{t1}` | *Target 2:* `{t2}`")
            lines.append(f"• *Volume:* `{vol}` | *Weekly:* `{weekly}` | *Div:* `{div}`")
            lines.append("────────────────────────")

        lines.append("⚠️ _CSE Analyzer Decision Support • Manage risk strictly_")
        text = "\n".join(lines)
        stocks.send_telegram_message(text, force=True)
        return f"Successfully sent {len(top_signals)} signals to Telegram!"

    @staticmethod
    def detect_candlestick_pattern(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Identifies high-probability reversal and continuation candlestick patterns
        on the most recent daily bars: Hammer, Bullish Engulfing, Morning Star,
        Shooting Star, Evening Star, and Doji.
        """
        if df.empty or len(df) < 3:
            return {"pattern": "—", "bias": "Neutral"}

        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]

        c, o, h, l = float(last["close"]), float(last["open"]), float(last["high"]), float(last["low"])
        pc, po, ph, pl = float(prev["close"]), float(prev["open"]), float(prev["high"]), float(prev["low"])
        p2c, p2o, p2h, p2l = float(prev2["close"]), float(prev2["open"]), float(prev2["high"]), float(prev2["low"])

        body = abs(c - o)
        tot_range = max(h - l, 0.001)
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l

        prev_body = abs(pc - po)
        prev_range = max(ph - pl, 0.001)

        # 1. Bullish Hammer (Lower wick >= 1.8x body, small upper wick)
        if lower_wick >= 1.8 * body and upper_wick <= 0.35 * body and body > 0.05 * tot_range:
            return {"pattern": "Hammer 🔨", "bias": "Bullish"}

        # 2. Bullish Engulfing (Previous red, current green completely engulfs)
        if pc < po and c > o and c >= po and o <= pc and body > prev_body:
            return {"pattern": "Engulfing 🟢", "bias": "Bullish"}

        # 3. Morning Star (Bearish, Small star, Bullish recovery)
        if p2c < p2o and prev_body <= 0.35 * (p2h - p2l) and c > o and c > (p2o + p2c) / 2.0:
            return {"pattern": "Morning Star ☀️", "bias": "Bullish"}

        # 4. Shooting Star / Inverted Hammer (Upper wick >= 1.8x body, small lower wick)
        if upper_wick >= 1.8 * body and lower_wick <= 0.35 * body and body > 0.05 * tot_range:
            return {"pattern": "Shooting Star ⚠️", "bias": "Bearish"}

        # 5. Bearish Engulfing (Previous green, current red completely engulfs)
        if pc > po and c < o and c <= po and o >= pc and body > prev_body:
            return {"pattern": "Engulfing 🔴", "bias": "Bearish"}

        # 6. Doji (Indecision / Equilibrium)
        if body <= 0.10 * tot_range:
            return {"pattern": "Doji ⚖️", "bias": "Neutral"}

        return {"pattern": "—", "bias": "Neutral"}

    @staticmethod
    def compute_52w_extremes(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes distance from 52-week High and Low.
        """
        if df.empty or len(df) < 10:
            return {"high_52w": 0.0, "low_52w": 0.0, "dist_high_pct": 0.0, "dist_low_pct": 0.0, "near_breakout": False, "dist_high_str": "0.0%"}

        sub = df.tail(min(250, len(df)))
        high_52w = float(sub["high"].max())
        low_52w = float(sub["low"].min())
        c_last = float(df["close"].iloc[-1])

        dist_high_pct = round(((c_last - high_52w) / high_52w) * 100.0, 1) if high_52w > 0 else 0.0
        dist_low_pct = round(((c_last - low_52w) / low_52w) * 100.0, 1) if low_52w > 0 else 0.0
        near_breakout = dist_high_pct >= -5.0  # within 5% of 52W High

        return {
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_high_pct": dist_high_pct,
            "dist_low_pct": dist_low_pct,
            "near_breakout": near_breakout,
            "dist_high_str": f"{dist_high_pct:+.1f}%" + (" 🔥" if near_breakout else ""),
        }

    # ── Confluence & Risk Decision Support ─────────────────────────────

    def compute_confluence(self, df: pd.DataFrame, signal: int = 1) -> Dict[str, Any]:
        """
        Computes multi-indicator confluence score (0-100), quality grade,
        divergence, weekly trend, candlestick pattern, 52W breakout, and Fibonacci levels.
        """
        if df.empty or len(df) < 20:
            return {
                "score": 50,
                "grade": "B",
                "stars": "★★★",
                "trend_status": "Neutral",
                "trend_text": "—",
                "divergence": "—",
                "weekly_trend": "▲ Bullish",
                "pattern": "—",
                "pattern_bias": "Neutral",
                "dist_52w_high": "0.0%",
                "near_breakout": False,
                "high_52w": 0.0,
                "low_52w": 0.0,
                "vol_ratio": 1.0,
                "vol_ratio_str": "1.0x",
                "atr": 1.0,
                "ema50": 0.0,
                "ema200": 0.0,
                "support1": 0.0,
                "support2": 0.0,
                "resistance1": 0.0,
                "resistance2": 0.0,
                "suggested_stop": 0.0,
                "trailing_stop": 0.0,
                "target1": 0.0,
                "target2": 0.0,
                "fibonacci": {},
            }

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        c_last = float(close.iloc[-1])

        # 1. Trend Analysis (EMA 50 & EMA 200)
        ema50 = close.ewm(span=min(50, len(close)), adjust=False).mean()
        ema200 = close.ewm(span=min(200, len(close)), adjust=False).mean() if len(close) >= 50 else ema50
        e50_last = float(ema50.iloc[-1])
        e200_last = float(ema200.iloc[-1])

        is_above_200 = c_last >= e200_last
        is_above_50 = c_last >= e50_last
        is_golden_cross = e50_last >= e200_last

        # 2. Volume Analysis (20-day SMA)
        vol_window = min(20, len(volume))
        vol_ma20 = volume.rolling(vol_window).mean()
        avg_vol = float(vol_ma20.iloc[-1]) if not np.isnan(vol_ma20.iloc[-1]) else 1.0
        v_last = float(volume.iloc[-1])
        vol_ratio = (v_last / avg_vol) if avg_vol > 0 else 1.0

        # 3. ATR (Average True Range - 14 period)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(min(14, len(tr))).mean()
        atr = float(atr_series.iloc[-1]) if not np.isnan(atr_series.iloc[-1]) and atr_series.iloc[-1] > 0 else max(c_last * 0.02, 0.5)

        # 4. Support and Resistance levels
        s1 = float(low.tail(min(20, len(low))).min())
        s2 = float(low.tail(min(50, len(low))).min())
        r1 = float(high.tail(min(20, len(high))).max())
        r2 = float(high.tail(min(250, len(high))).max())

        # 5. Advanced Engines: Divergence, Weekly Trend, Pattern, 52W Extremes & Fib
        div_info = self.detect_divergence(df, lookback=30)
        weekly_info = self.compute_weekly_trend(df)
        pattern_info = self.detect_candlestick_pattern(df)
        extremes_52w = self.compute_52w_extremes(df)
        fib_levels = self.compute_fibonacci_levels(df, lookback=120)

        # 6. Confluence Scoring (0 - 100)
        score = 25  # Base score for valid crossover signal

        # Trend scoring
        if signal == 1:  # LONG
            trend_text = "▲ Bullish" if is_above_200 else "▼ Below 200 EMA"
            trend_status = "Bullish" if is_above_200 else "Counter-Trend"
            if is_above_200:
                score += 15
            elif is_above_50:
                score += 10
            if is_golden_cross:
                score += 10
            if weekly_info.get("weekly_bullish"):
                score += 10
            if div_info.get("bullish"):
                score += 15
            if pattern_info.get("bias") == "Bullish":
                score += 10
            if extremes_52w.get("near_breakout"):
                score += 10
        else:  # SHORT
            trend_text = "▼ Bearish" if not is_above_200 else "▲ Above 200 EMA"
            trend_status = "Bearish" if not is_above_200 else "Counter-Trend"
            if not is_above_200:
                score += 15
            elif not is_above_50:
                score += 10
            if not is_golden_cross:
                score += 10
            if not weekly_info.get("weekly_bullish"):
                score += 10
            if div_info.get("bearish"):
                score += 15
            if pattern_info.get("bias") == "Bearish":
                score += 10

        # Volume surge scoring
        if vol_ratio >= 2.0:
            score += 15
        elif vol_ratio >= 1.5:
            score += 10
        elif vol_ratio >= 1.2:
            score += 5

        # Volatility & price sanity bonus
        if 0 < (atr / c_last) < 0.08:
            score += 10
        else:
            score += 5

        score = max(10, min(100, score))

        # Assign Grade
        if score >= 80:
            grade = "A+"
            stars = "★★★★★"
        elif score >= 65:
            grade = "A"
            stars = "★★★★"
        elif score >= 50:
            grade = "B"
            stars = "★★★"
        else:
            grade = "C"
            stars = "★★"

        # Suggested Stop Loss, Trailing Stop, and Targets
        if signal == 1:  # LONG
            suggested_stop = max(round(c_last - 1.5 * atr, 2), round(c_last * 0.90, 2))
            if suggested_stop >= c_last:
                suggested_stop = round(c_last * 0.95, 2)
            trailing_stop = round(max(0.1, c_last - 2.0 * atr), 2)
            risk_unit = c_last - suggested_stop
            target1 = round(c_last + 1.5 * risk_unit, 2)
            target2 = round(c_last + 2.5 * risk_unit, 2)
        else:  # SHORT
            suggested_stop = min(round(c_last + 1.5 * atr, 2), round(c_last * 1.10, 2))
            if suggested_stop <= c_last:
                suggested_stop = round(c_last * 1.05, 2)
            trailing_stop = round(c_last + 2.0 * atr, 2)
            risk_unit = suggested_stop - c_last
            target1 = round(max(0.1, c_last - 1.5 * risk_unit), 2)
            target2 = round(max(0.1, c_last - 2.5 * risk_unit), 2)

        return {
            "score": score,
            "grade": grade,
            "stars": stars,
            "trend_status": trend_status,
            "trend_text": trend_text,
            "divergence": div_info.get("text", "—"),
            "weekly_trend": weekly_info.get("weekly_text", "▲ Bullish"),
            "pattern": pattern_info.get("pattern", "—"),
            "pattern_bias": pattern_info.get("bias", "Neutral"),
            "dist_52w_high": extremes_52w.get("dist_high_str", "0.0%"),
            "dist_52w_high_num": extremes_52w.get("dist_high_pct", 0.0),
            "near_breakout": extremes_52w.get("near_breakout", False),
            "high_52w": extremes_52w.get("high_52w", 0.0),
            "low_52w": extremes_52w.get("low_52w", 0.0),
            "vol_ratio": round(vol_ratio, 2),
            "vol_ratio_str": f"{vol_ratio:.1f}x",
            "atr": round(atr, 2),
            "ema50": round(e50_last, 2),
            "ema200": round(e200_last, 2),
            "support1": round(s1, 2),
            "support2": round(s2, 2),
            "resistance1": round(r1, 2),
            "resistance2": round(r2, 2),
            "suggested_stop": suggested_stop,
            "trailing_stop": trailing_stop,
            "target1": target1,
            "target2": target2,
            "fibonacci": fib_levels,
        }

    def calculate_trade_risk(
        self,
        capital: float = 500000.0,
        risk_pct: float = 2.0,
        entry: float = 100.0,
        stop_loss: float = 95.0,
        fee_pct: float = 1.12,
    ) -> Dict[str, Any]:
        """
        Calculates position sizing and risk/reward parameters for CSE trading
        accounting for Sri Lankan broker fees and regulatory cess (~1.12% roundtrip).
        """
        import math
        capital = max(1000.0, float(capital))
        risk_pct = max(0.1, min(100.0, float(risk_pct)))
        entry = max(0.1, float(entry))
        stop_loss = float(stop_loss)

        risk_amount = capital * (risk_pct / 100.0)
        risk_per_share = abs(entry - stop_loss)
        if risk_per_share <= 0:
            risk_per_share = entry * 0.05  # fallback 5%

        shares = int(math.floor(risk_amount / risk_per_share))
        max_possible_shares = int(capital // entry)
        shares = max(1, min(shares, max_possible_shares))

        total_cost = round(shares * entry, 2)
        half_fee_rate = (fee_pct / 100.0) / 2.0  # 0.56% on buy, 0.56% on sell
        buy_fee = total_cost * half_fee_rate

        is_long = entry >= stop_loss
        if is_long:
            t1 = round(entry + 1.5 * risk_per_share, 2)
            t2 = round(entry + 2.5 * risk_per_share, 2)
        else:
            t1 = round(max(0.1, entry - 1.5 * risk_per_share), 2)
            t2 = round(max(0.1, entry - 2.5 * risk_per_share), 2)

        sell_val_t1 = shares * t1
        sell_fee_t1 = sell_val_t1 * half_fee_rate
        net_profit_t1 = round((sell_val_t1 - total_cost) - (buy_fee + sell_fee_t1), 2)

        sell_val_t2 = shares * t2
        sell_fee_t2 = sell_val_t2 * half_fee_rate
        net_profit_t2 = round((sell_val_t2 - total_cost) - (buy_fee + sell_fee_t2), 2)

        sell_val_sl = shares * stop_loss
        sell_fee_sl = sell_val_sl * half_fee_rate
        net_loss_sl = round(abs(total_cost - sell_val_sl) + (buy_fee + sell_fee_sl), 2)

        est_roundtrip_fee = round(buy_fee + (total_cost * half_fee_rate), 2)

        return {
            "capital": capital,
            "risk_pct": risk_pct,
            "risk_amount": round(risk_amount, 2),
            "entry": entry,
            "stop_loss": stop_loss,
            "risk_per_share": round(risk_per_share, 2),
            "shares": shares,
            "total_cost": total_cost,
            "capital_allocated_pct": round((total_cost / capital) * 100.0, 1),
            "roundtrip_fee": est_roundtrip_fee,
            "target1": t1,
            "net_profit_t1": net_profit_t1,
            "target2": t2,
            "net_profit_t2": net_profit_t2,
            "net_loss_sl": net_loss_sl,
            "rr_ratio_t1": "1:1.5",
            "rr_ratio_t2": "1:2.5",
        }

    # ── QQE scanning ────────────────────────────────────────────────────

    def run_qqe_scan(
        self,
        rsi_period: int = 14,
        sf: int = 5,
        qqe_factor: float = 4.238,
        threshold: int = 10,
    ) -> List[Dict[str, Any]]:
        """Run QQE on all enabled symbols and return enriched signal rows."""
        con = self.connect()
        try:
            enabled = stocks.fetch_symbols_from_db(con, only_enabled=True)
            if not enabled:
                enabled = stocks.fetch_symbols_from_db(con, only_enabled=None)

            ind_map = {sym: ind for sym, ind in
                       con.execute("SELECT symbol, industry FROM symbols").fetchall()}
            results = []
            for sym in enabled:
                try:
                    closes = stocks.get_symbol_closes(con, sym)
                    if len(closes) < 60:
                        continue
                    qqe = stocks.compute_qqe_from_closes(
                        closes, rsi_period=rsi_period, sf=sf,
                        qqe_factor=qqe_factor, threshold=threshold,
                    )
                    df = pd.concat([closes.rename("close"), qqe], axis=1).dropna(subset=["close"])
                    if df.empty:
                        continue
                    last = df.iloc[-1]
                    sig = int(last["signal"])
                    if sig != 0:
                        # Compute full confluence metrics using historical bars
                        bars_df = self.get_bars(sym)
                        conf = self.compute_confluence(bars_df, sig)

                        results.append({
                            "symbol": sym,
                            "industry": ind_map.get(sym, ""),
                            "signal": sig,
                            "signal_text": "LONG" if sig == 1 else "SHORT",
                            "grade": conf["grade"],
                            "stars": conf["stars"],
                            "score": conf["score"],
                            "trend": conf["trend_text"],
                            "vol_ratio": conf["vol_ratio_str"],
                            "divergence": conf["divergence"],
                            "weekly_trend": conf["weekly_trend"],
                            "pattern": conf["pattern"],
                            "dist_52w": conf["dist_52w_high"],
                            "near_breakout": conf["near_breakout"],
                            "rsi_ma": f"{last.get('rsi_ma', 0):.2f}",
                            "fast_tl": f"{last.get('fast_tl', 0):.2f}",
                            "price": f"{last['close']:.2f}",
                            "date": df.index[-1].strftime("%Y-%m-%d"),
                            "atr": conf["atr"],
                            "stop_loss": conf["suggested_stop"],
                            "trailing_stop": conf["trailing_stop"],
                            "target1": conf["target1"],
                            "target2": conf["target2"],
                            "support": conf["support1"],
                            "resistance": conf["resistance1"],
                        })
                except Exception:
                    continue
            return results
        finally:
            con.close()

    scan_qqe_signals = run_qqe_scan

    # ── Daily scan (bars + signals) ─────────────────────────────────────

    def run_daily_scan(
        self,
        period: int = 5,
        update_symbols: bool = False,
        rsi_period: int = 14,
        sf: int = 5,
        qqe_factor: float = 4.238,
        threshold: int = 10,
    ) -> str:
        """Run the full daily scan pipeline, returning a log string."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                stocks.run(
                    db_path=self.db_path,
                    timeout=40,
                    update_symbols_flag=update_symbols,
                    allow_scrape=False,
                    update_only=False,
                    enable_all=False,
                    disable_all=False,
                    enable_file=None,
                    disable_file=None,
                    symbol_only=None,
                    period=period,
                    rsi_period=rsi_period,
                    sf=sf,
                    qqe_factor=qqe_factor,
                    threshold=threshold,
                    min_bars=60,
                    dry_run=False,
                )
        except SystemExit:
            pass
        except Exception as e:
            buf.write(f"\n[ERROR] {e}")
        return buf.getvalue()

    # ── Backtest ────────────────────────────────────────────────────────

    def run_backtest(self, symbol: str, params: Dict[str, Any]) -> Dict[str, Any]:
        con = self.connect()
        try:
            bars_df = qbs.load_bars_full(con, symbol)
            if bars_df.empty:
                raise ValueError(f"No data for {symbol}")
            return qbs.run_full_backtest(bars_df, params)
        finally:
            con.close()

    def run_quick_backtest(
        self,
        count: int = 50,
        rsi_period: int = 14,
        sf: int = 5,
        qqe_factor: float = 4.238,
        threshold: int = 10,
        horizons: List[int] | None = None,
    ) -> pd.DataFrame:
        if horizons is None:
            horizons = [5, 10, 20]
        con = self.connect()
        try:
            symbols = stocks.fetch_symbols_from_db(con, only_enabled=True)
            if not symbols:
                symbols = stocks.fetch_symbols_from_db(con, only_enabled=None)
            return qbs.run_backtest_signals(
                con=con, symbols=symbols, per_symbol=False, count=count,
                rsi_period=rsi_period, sf=sf, qqe_factor=qqe_factor,
                threshold=threshold, horizons=horizons,
            )
        finally:
            con.close()

    # ── Portfolio ───────────────────────────────────────────────────────

    def get_portfolio(self) -> List[Dict[str, Any]]:
        con = self.connect()
        try:
            trades = con.execute(
                "SELECT id, symbol, side, quantity, entry_price, trade_date "
                "FROM portfolio ORDER BY symbol"
            ).fetchall()
            latest = self.get_latest_prices()
            industries = self.get_symbol_industries()
            positions = []
            for tid, sym, side, qty, price, tdate in trades:
                cost = float(qty) * float(price)
                cur_price = latest.get(sym)
                cur_val = float(qty) * cur_price if cur_price else 0
                if cur_price and side.upper() == "BUY":
                    pnl = cur_val - cost
                elif cur_price:
                    pnl = cost - cur_val
                else:
                    pnl = 0
                pnl_pct = (pnl / cost * 100) if cost else 0
                positions.append({
                    "id": tid, "symbol": sym,
                    "industry": industries.get(sym, "Unknown"),
                    "side": side.upper(), "quantity": float(qty),
                    "entry_price": float(price), "cost_basis": cost,
                    "current_price": cur_price, "current_value": cur_val,
                    "pnl": pnl, "pnl_pct": pnl_pct,
                    "trade_date": tdate,
                })
            return positions
        finally:
            con.close()

    get_portfolio_positions = get_portfolio

    def add_portfolio_trade(self, symbol: str, side: str, qty: float,
                            price: float, trade_date: str):
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO portfolio (symbol, side, quantity, entry_price, trade_date) "
                "VALUES (?, ?, ?, ?, ?)",
                (symbol.upper(), side.upper(), qty, price, trade_date)
            )
            con.commit()
        finally:
            con.close()

    def delete_portfolio_trade(self, trade_id: int):
        con = self.connect()
        try:
            con.execute("DELETE FROM portfolio WHERE id=?", (trade_id,))
            con.commit()
        finally:
            con.close()

    # ── Stock analysis data prep ────────────────────────────────────────

    def get_stock_analysis_data(self, symbol: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Get price data + calculated summary for AI analysis."""
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT date, close, high, low, volume FROM bars "
                "WHERE symbol=? ORDER BY date", (symbol,)
            ).fetchall()
            if not rows or len(rows) < 60:
                raise ValueError("Not enough data (minimum 60 days)")
            df = pd.DataFrame(rows, columns=["date", "close", "high", "low", "volume"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

            summary = {
                "52_week_high": df["high"].rolling(252).max().iloc[-1],
                "52_week_low": df["low"].rolling(252).min().iloc[-1],
                "50_day_ma": df["close"].rolling(50).mean().iloc[-1],
                "200_day_ma": df["close"].rolling(200).mean().iloc[-1],
                "avg_volume_30d": df["volume"].rolling(30).mean().iloc[-1],
                "current_price": df["close"].iloc[-1],
                "volatility_30d": df["close"].pct_change().rolling(30).std().iloc[-1] * (252 ** 0.5),
            }
            for k, v in summary.items():
                if isinstance(v, (int, float)):
                    summary[k] = f"{v:.2f}"
            return df, summary
        finally:
            con.close()
