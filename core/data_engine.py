# core/data_engine.py  –  Data access layer for CSE Analyzer
"""
Wraps the parent project's stocks.py & qqe_backtest_signals.py so that the
desktop UI never imports them directly.  All heavy I/O runs in background
threads via ThreadedTask (see ui_utils.py).
"""
from __future__ import annotations
import sqlite3
from datetime import date, timedelta, datetime
from pathlib import Path

from typing import Any, Dict, List, Tuple, Optional, Union

import numpy as np
import pandas as pd

# Parent-project modules (available via sys.path set in main.py)
import stocks
import qqe_backtest_signals as qbs

from core.technical_engine import TechnicalEngine
from core.fundamental_engine import FundamentalEngine
from core.market_context_engine import MarketContextEngine
from core.news_events_engine import NewsEventsEngine
from core.ml_engine import MLEngine
from core.backtest_engine import BacktestEngine
from core.risk_scorecard_engine import RiskScorecardEngine


class DataEngine:
    """Singleton-ish data access object."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            parent_dir = Path(__file__).resolve().parent.parent.parent
            db_path = parent_dir / "cse_signals.db"
        self.db_path = str(db_path)
        self._session = stocks.mk_session(timeout=40)
        self._symbol_cache: list[str] | None = None
        self._company_profile_cache: dict[str, dict] = {}
        self._init_watchlist_table()

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
            b7d = safe("SELECT COUNT(*) FROM signals WHERE date>=? AND signal=1", (seven_days_ago,))
            e7d = safe("SELECT COUNT(*) FROM signals WHERE date>=? AND signal=-1", (seven_days_ago,))
            return {
                "symbols_total": safe("SELECT COUNT(*) FROM symbols"),
                "symbols_enabled": safe("SELECT COUNT(*) FROM symbols WHERE enabled=1"),
                "bars_total": safe("SELECT COUNT(*) FROM bars"),
                "last_bar_date": safe("SELECT MAX(date) FROM bars", default="—"),
                "last_signal_date": safe("SELECT MAX(date) FROM signals", default="—"),
                "long_7d": b7d,
                "short_7d": e7d,
                "buy_7d": b7d,
                "exit_7d": e7d,
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
    def compute_pivot_points(df: pd.DataFrame, method: str = "standard") -> Dict[str, float]:
        """Compute intraday/daily Pivot Points (P, R1, R2, R3, S1, S2, S3)."""
        return TechnicalEngine.compute_pivot_points(df, method=method)

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
        Broadcasts high-conviction spot BUY setups and EXIT alerts to Telegram.
        """
        if not signals:
            return "No signals provided to send."

        top_signals = [s for s in signals if s.get("grade") in ["A+", "A"]][:5]
        if not top_signals:
            top_signals = signals[:4]

        lines = [
            "🚀 *CSE Spot Equity Trade Alert*",
            f"📅 *Date:* `{top_signals[0].get('date', 'Today')}`",
            "────────────────────────",
        ]
        for s in top_signals:
            sym = s.get("symbol", "")
            action = s.get("action", "BUY")
            sig = s.get("signal_text", "BUY Setup")
            grade = s.get("grade", "A")
            stars = s.get("stars", "★★★★")
            price = s.get("price", "0.00")
            sl = s.get("stop_loss", "0.00")
            t1 = s.get("target1", "0.00")
            t2 = s.get("target2", "0.00")
            vol = s.get("vol_ratio", "1.0x")
            trend = s.get("trend", "▲ Bullish")
            reason = s.get("reason", "")

            icon = "🟢" if action == "BUY" else "🔴"
            lines.append(f"{icon} *{sym}* | `{sig}` ({grade} {stars})")
            lines.append(f"• *Price / Entry:* `{price} LKR`")
            lines.append(f"• *🎯 Target 1 (1:1.5):* `{t1} LKR` | *🏆 Target 2:* `{t2} LKR`")
            lines.append(f"• *🛡️ Stop Loss:* `{sl} LKR` | *Vol:* `{vol}` | *Trend:* `{trend}`")
            if reason:
                lines.append(f"• *Rationale:* _{reason}_")
            lines.append("────────────────────────")

        lines.append("⚠️ _CSE Spot Equity Decision Support • Strict Risk Management_")
        text = "\n".join(lines)
        stocks.send_telegram_message(text, force=True)
        return f"Successfully sent {len(top_signals)} spot trade signals to Telegram!"

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
            return {"pattern": "Bullish Hammer", "bias": "Bullish"}

        # 2. Bullish Engulfing (Previous red, current green completely engulfs)
        if pc < po and c > o and c >= po and o <= pc and body > prev_body:
            return {"pattern": "Bullish Engulfing", "bias": "Bullish"}

        # 3. Morning Star (Bearish, Small star, Bullish recovery)
        if p2c < p2o and prev_body <= 0.35 * (p2h - p2l) and c > o and c > (p2o + p2c) / 2.0:
            return {"pattern": "Morning Star", "bias": "Bullish"}

        # 4. Shooting Star / Inverted Hammer (Upper wick >= 1.8x body, small lower wick)
        if upper_wick >= 1.8 * body and lower_wick <= 0.35 * body and body > 0.05 * tot_range:
            return {"pattern": "Shooting Star", "bias": "Bearish"}

        # 5. Bearish Engulfing (Previous green, current red completely engulfs)
        if pc > po and c < o and c <= po and o >= pc and body > prev_body:
            return {"pattern": "Bearish Engulfing", "bias": "Bearish"}

        # 6. Doji (Indecision / Equilibrium)
        if body <= 0.10 * tot_range:
            return {"pattern": "Doji", "bias": "Neutral"}

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

        # 6. Confluence Scoring (0 - 100) — Spot Long Equity Quality
        score = 25  # Base score

        # Macro Trend scoring
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

        # Spot Equities Suggested Stop Loss, Trailing Stop, and Targets (Long-Only)
        suggested_stop = max(round(c_last - 1.5 * atr, 2), round(c_last * 0.92, 2))
        if suggested_stop >= c_last:
            suggested_stop = round(c_last * 0.95, 2)
        trailing_stop = round(max(0.1, c_last - 2.0 * atr), 2)
        risk_unit = max(c_last - suggested_stop, c_last * 0.03)
        target1 = round(c_last + 1.5 * risk_unit, 2)
        target2 = round(c_last + 2.5 * risk_unit, 2)

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

        t1 = round(entry + 1.5 * risk_per_share, 2)
        t2 = round(entry + 2.5 * risk_per_share, 2)

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

    # ── Spot Equity Decision Engine (BUY & EXIT Areas) ──────────────────

    def compute_spot_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Spot Equities Decision Engine for Colombo Stock Exchange.
        Evaluates 3 high-conviction BUY setups and 4 EXIT areas for cash holdings.
        No short selling or futures logic.
        """
        if df.empty or len(df) < 25:
            return {
                "action": "HOLD",
                "setup_type": "Insufficient Data",
                "signal_text": "HOLD",
                "is_buy": False,
                "is_exit": False,
                "current_price": 0.0,
                "entry_price": 0.0,
                "target1": 0.0,
                "target2": 0.0,
                "stop_loss": 0.0,
                "trailing_stop": 0.0,
                "score": 0,
                "grade": "C",
                "stars": "★★",
                "reason": "Minimum 25 daily price bars required.",
            }

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        c_last = float(close.iloc[-1])
        c_prev = float(close.iloc[-2]) if len(close) >= 2 else c_last
        o_last = float(df["open"].iloc[-1]) if "open" in df else c_prev

        # EMAs: 20, 50, 200
        ema20 = close.ewm(span=min(20, len(close)), adjust=False).mean()
        ema50 = close.ewm(span=min(50, len(close)), adjust=False).mean()
        ema200 = close.ewm(span=min(200, len(close)), adjust=False).mean() if len(close) >= 50 else ema50

        e20_last = float(ema20.iloc[-1])
        e20_prev = float(ema20.iloc[-2]) if len(ema20) >= 2 else e20_last
        e50_last = float(ema50.iloc[-1])
        e50_prev = float(ema50.iloc[-2]) if len(ema50) >= 2 else e50_last
        e200_last = float(ema200.iloc[-1])

        is_above_200 = c_last >= e200_last
        is_above_50 = c_last >= e50_last
        is_golden_cross = e50_last >= e200_last
        is_ema20_cross = (e20_prev <= e50_prev) and (e20_last > e50_last)

        # 20-day Volume Surge
        vol_window = min(20, len(volume))
        vol_ma20 = volume.rolling(vol_window).mean()
        avg_vol = float(vol_ma20.iloc[-1]) if not np.isnan(vol_ma20.iloc[-1]) else 1.0
        v_last = float(volume.iloc[-1])
        vol_ratio = (v_last / avg_vol) if avg_vol > 0 else 1.0

        # ATR 14
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(min(14, len(tr))).mean()
        atr = float(atr_series.iloc[-1]) if not np.isnan(atr_series.iloc[-1]) and atr_series.iloc[-1] > 0 else max(c_last * 0.02, 0.5)

        # 20-day High & Low
        high_20d = float(high.iloc[:-1].tail(20).max()) if len(high) > 20 else float(high.max())
        low_20d = float(low.iloc[:-1].tail(20).min()) if len(low) > 20 else float(low.min())

        # Confluence metrics
        conf = self.compute_confluence(df, signal=1)

        # Default Spot Targets & Stops
        suggested_stop = conf["suggested_stop"]
        trailing_stop = conf["trailing_stop"]
        target1 = conf["target1"]
        target2 = conf["target2"]

        # ── Spot Decision Logic ─────────────────────────────────────────
        action = "HOLD"
        setup_type = "Consolidation / Hold"
        reason = "Price within established range; no immediate entry or exit triggered."

        # 1. EVALUATE BUY SETUPS
        # Setup A: Momentum Breakout BUY
        if c_last >= high_20d and is_above_50 and vol_ratio >= 1.20 and conf["score"] >= 60:
            action = "BUY"
            setup_type = "🚀 Breakout BUY"
            reason = f"Broke 20-day high ({high_20d:.2f}) with {vol_ratio:.1f}x volume surge."

        # Setup B: Pullback to Value BUY
        elif is_above_200 and abs(c_last - e50_last) / c_last < 0.035 and c_last >= o_last and conf["score"] >= 55:
            action = "BUY"
            setup_type = "💎 Pullback BUY"
            reason = f"Testing 50 EMA dynamic support ({e50_last:.2f}) with bullish candle."

        # Setup C: Golden Crossover BUY
        elif is_ema20_cross and is_above_200 and conf["score"] >= 50:
            action = "BUY"
            setup_type = "⚡ Golden Cross BUY"
            reason = f"EMA 20 crossed above EMA 50 with macro trend alignment."

        # 2. EVALUATE EXIT CONDITIONS (For closing existing holdings)
        # Condition A: Target 2 Reached
        elif c_last >= target2:
            action = "EXIT"
            setup_type = "🏆 Target 2 Hit"
            reason = f"Hit Target 2 ({target2:.2f} LKR, ~2.5R). Lock in full profits."

        # Condition B: Target 1 Reached
        elif c_last >= target1:
            action = "EXIT"
            setup_type = "🎯 Target 1 Hit"
            reason = f"Hit Target 1 ({target1:.2f} LKR, ~1.5R). Lock in 50% profit and trail stop."

        # Condition C: Stop Loss Breached
        elif c_last <= suggested_stop:
            action = "EXIT"
            setup_type = "⚠️ Stop Loss Breached"
            reason = f"Fell below risk boundary ({suggested_stop:.2f} LKR). Protect capital."

        # Condition D: Trend Breakdown below 50 EMA
        elif not is_above_50 and c_prev >= e50_prev and vol_ratio >= 1.3:
            action = "EXIT"
            setup_type = "🔻 Trend Breakdown"
            reason = f"Broke below 50 EMA support ({e50_last:.2f} LKR) on high volume."

        return {
            "action": action,
            "setup_type": setup_type,
            "signal_text": setup_type,
            "is_buy": action == "BUY",
            "is_exit": action == "EXIT",
            "is_hold": action == "HOLD",
            "current_price": c_last,
            "entry_price": c_last,
            "target1": target1,
            "target2": target2,
            "stop_loss": suggested_stop,
            "trailing_stop": trailing_stop,
            "risk_unit": round(abs(c_last - suggested_stop), 2),
            "score": conf["score"],
            "grade": conf["grade"],
            "stars": conf["stars"],
            "trend": conf["trend_text"],
            "vol_ratio": conf["vol_ratio_str"],
            "divergence": conf["divergence"],
            "weekly_trend": conf["weekly_trend"],
            "pattern": conf["pattern"],
            "dist_52w": conf["dist_52w_high"],
            "near_breakout": conf["near_breakout"],
            "reason": reason,
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "atr": conf["atr"],
            "support": conf["support1"],
            "resistance": conf["resistance1"],
        }

    # ── Spot Equity Scanner ─────────────────────────────────────────────

    def scan_equity_signals(
        self,
        strategy_mode: str = "all",
        min_score: int = 50,
        min_vol: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Scans all enabled CSE stocks for spot BUY setups and EXIT areas.
        Completely replaces QQE scanning with long-only cash equities intelligence.
        """
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
                    bars_df = self.get_bars(sym)
                    if bars_df.empty or len(bars_df) < 25:
                        continue

                    spot = self.compute_spot_signals(bars_df)
                    action = spot["action"]

                    # Filter out non-actionable holds if requested
                    if action == "HOLD" and strategy_mode not in ["all", "all_including_hold"]:
                        continue

                    if spot["score"] < min_score:
                        continue

                    # Volume filter
                    try:
                        v_ratio = float(spot["vol_ratio"].replace("x", ""))
                        if v_ratio < min_vol:
                            continue
                    except Exception:
                        pass

                    # Strategy mode filter
                    if strategy_mode == "buy_only" and action != "BUY":
                        continue
                    elif strategy_mode == "exit_only" and action != "EXIT":
                        continue
                    elif strategy_mode == "breakout" and "Breakout" not in spot["setup_type"]:
                        continue
                    elif strategy_mode == "pullback" and "Pullback" not in spot["setup_type"]:
                        continue
                    elif strategy_mode == "golden_cross" and "Golden Cross" not in spot["setup_type"]:
                        continue

                    results.append({
                        "symbol": sym,
                        "industry": ind_map.get(sym, ""),
                        "action": action,
                        "signal": 1 if action == "BUY" else (-1 if action == "EXIT" else 0),
                        "signal_text": spot["setup_type"],
                        "grade": spot["grade"],
                        "stars": spot["stars"],
                        "score": spot["score"],
                        "trend": spot["trend"],
                        "vol_ratio": spot["vol_ratio"],
                        "divergence": spot["divergence"],
                        "weekly_trend": spot["weekly_trend"],
                        "pattern": spot["pattern"],
                        "dist_52w": spot["dist_52w"],
                        "near_breakout": spot["near_breakout"],
                        "price": f"{spot['current_price']:.2f}",
                        "date": spot["date"],
                        "atr": spot["atr"],
                        "stop_loss": spot["stop_loss"],
                        "trailing_stop": spot["trailing_stop"],
                        "target1": spot["target1"],
                        "target2": spot["target2"],
                        "support": spot["support"],
                        "resistance": spot["resistance"],
                        "reason": spot["reason"],
                    })
                except Exception:
                    continue
            return results
        finally:
            con.close()

    run_qqe_scan = scan_equity_signals
    scan_qqe_signals = scan_equity_signals

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

    # ── Spot Chart Signals & Spot Equity Backtest Engine ────────────────

    def compute_chart_signals(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Generate historical spot BUY and EXIT signals for charting on CSE equities.
        Long-only setups (Breakout, Pullback, Golden Cross) and EXIT zones (Target 1, Target 2, Stop Loss, Breakdown).
        """
        if df.empty or len(df) < 25:
            empty_s = pd.Series(np.nan, index=df.index if not df.empty else [])
            return {"buy_signals": empty_s, "exit_signals": empty_s}

        close = df["close"]
        high = df["high"]
        low = df["low"]
        vol = df["volume"]
        o = df["open"] if "open" in df else close

        # EMAs
        ema20 = close.ewm(span=min(20, len(close)), adjust=False).mean()
        ema50 = close.ewm(span=min(50, len(close)), adjust=False).mean()
        ema200 = close.ewm(span=min(200, len(close)), adjust=False).mean() if len(close) >= 50 else ema50

        # Rolling 20-day high and volume SMA
        high_20d = high.shift(1).rolling(min(20, len(high))).max()
        vol_ma20 = vol.rolling(min(20, len(vol))).mean()

        # ATR 14
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr_series = tr.rolling(min(14, len(tr))).mean().fillna(close * 0.02)

        buy_signals = pd.Series(np.nan, index=df.index)
        exit_signals = pd.Series(np.nan, index=df.index)

        in_pos = False
        entry_p = 0.0
        stop_p = 0.0
        t1_p = 0.0
        t2_p = 0.0
        trail_p = 0.0
        bars_since_buy = 999

        for i in range(25, len(df)):
            idx = df.index[i]
            c = float(close.iloc[i])
            h = float(high.iloc[i])
            l = float(low.iloc[i])
            op = float(o.iloc[i])
            v = float(vol.iloc[i])
            v_ma = float(vol_ma20.iloc[i]) if not np.isnan(vol_ma20.iloc[i]) else 1.0
            v_ratio = (v / v_ma) if v_ma > 0 else 1.0
            e20 = float(ema20.iloc[i])
            e50 = float(ema50.iloc[i])
            e200 = float(ema200.iloc[i])
            e20_prev = float(ema20.iloc[i-1])
            e50_prev = float(ema50.iloc[i-1])
            h20 = float(high_20d.iloc[i]) if not np.isnan(high_20d.iloc[i]) else c
            cur_atr = float(atr_series.iloc[i]) if not np.isnan(atr_series.iloc[i]) else c * 0.02

            bars_since_buy += 1

            if in_pos:
                hit_exit = False
                if l <= stop_p:
                    hit_exit = True
                elif trail_p > stop_p and l <= trail_p:
                    hit_exit = True
                elif h >= t2_p:
                    hit_exit = True
                elif c < e50 and float(close.iloc[i-1]) >= e50_prev and v_ratio >= 1.25:
                    hit_exit = True

                if hit_exit:
                    exit_signals.loc[idx] = h * 1.02
                    in_pos = False
                else:
                    new_trail = round(h - (2.0 * cur_atr), 2)
                    trail_p = max(trail_p, new_trail)

            if not in_pos and bars_since_buy >= 5:
                is_breakout = (c >= h20 and c >= e50 and v_ratio >= 1.20)
                is_pullback = (c >= e200 and abs(c - e50) / c < 0.035 and c >= op and c >= float(close.iloc[i-1]))
                is_cross = (e20_prev <= e50_prev and e20 > e50 and c >= e200)

                if is_breakout or is_pullback or is_cross:
                    buy_signals.loc[idx] = l * 0.98
                    in_pos = True
                    entry_p = c
                    stop_p = round(max(0.1, entry_p - (1.5 * cur_atr)), 2)
                    risk = max(entry_p - stop_p, entry_p * 0.03)
                    t1_p = round(entry_p + 1.5 * risk, 2)
                    t2_p = round(entry_p + 2.5 * risk, 2)
                    trail_p = stop_p
                    bars_since_buy = 0

        return {"buy_signals": buy_signals, "exit_signals": exit_signals}

    def run_spot_backtest(self, bars_df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pure Spot Cash Equity Long-Only Backtesting Simulator for CSE equities.
        Takes into account Sri Lankan brokerage + CSE transaction fees (~1.12% roundtrip).
        Simulates capital allocation, Target 1 (~1.5R), Target 2 (~2.5R), Stop Loss, and Trailing Stops.
        """
        if bars_df.empty or len(bars_df) < 30:
            raise ValueError("Insufficient price data for backtest (minimum 30 daily bars required).")

        df = bars_df.sort_index().copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        vol = df["volume"]
        op = df["open"] if "open" in df else close

        initial_capital = float(params.get("initial_capital", 500000.0))
        comm_rate = float(params.get("commission_pct", 1.12)) / 100.0
        half_comm = comm_rate / 2.0
        alloc_pct = float(params.get("allocation_pct", 100.0)) / 100.0
        sl_atr_mult = float(params.get("sl_atr_mult", 1.5))
        custom_sl_pct = float(params.get("stop_loss_pct", 0.0)) / 100.0
        custom_tp_pct = float(params.get("take_profit_pct", 0.0)) / 100.0
        t1_r = float(params.get("target1_r", 1.5))
        t2_r = float(params.get("target2_r", 2.5))
        strat_filter = str(params.get("strategy_mode", params.get("strategy", "all"))).lower()
        use_trailing = bool(params.get("use_trailing", True))

        ema20 = close.ewm(span=min(20, len(close)), adjust=False).mean()
        ema50 = close.ewm(span=min(50, len(close)), adjust=False).mean()
        ema200 = close.ewm(span=min(200, len(close)), adjust=False).mean() if len(close) >= 50 else ema50

        high_20d = high.shift(1).rolling(min(20, len(high))).max()
        vol_ma20 = vol.rolling(min(20, len(vol))).mean()

        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr_series = tr.rolling(min(14, len(tr))).mean().fillna(close * 0.02)

        cash = initial_capital
        position = 0
        shares = 0
        entry_price = 0.0
        entry_date = None
        buy_cost = 0.0
        stop_price = 0.0
        trail_price = 0.0
        target1 = 0.0
        target2 = 0.0
        t1_hit = False

        trades = []
        equity_records = []

        start_idx = 25
        for i in range(start_idx, len(df)):
            dt = df.index[i]
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            c = float(close.iloc[i])
            h = float(high.iloc[i])
            l = float(low.iloc[i])
            o_bar = float(op.iloc[i])
            v = float(vol.iloc[i])
            v_avg = float(vol_ma20.iloc[i]) if not np.isnan(vol_ma20.iloc[i]) else 1.0
            v_ratio = (v / v_avg) if v_avg > 0 else 1.0

            e20 = float(ema20.iloc[i])
            e50 = float(ema50.iloc[i])
            e200 = float(ema200.iloc[i])
            e20_prev = float(ema20.iloc[i-1])
            e50_prev = float(ema50.iloc[i-1])
            c_prev = float(close.iloc[i-1])
            h20 = float(high_20d.iloc[i]) if not np.isnan(high_20d.iloc[i]) else c
            cur_atr = float(atr_series.iloc[i]) if not np.isnan(atr_series.iloc[i]) else max(c * 0.02, 0.5)

            if position == 1:
                exit_reason = None
                exit_price = 0.0

                if custom_sl_pct > 0 and l <= entry_price * (1 - custom_sl_pct):
                    exit_reason = "Stop Loss"
                    exit_price = round(entry_price * (1 - custom_sl_pct), 2)
                elif l <= stop_price:
                    exit_reason = "Stop Loss"
                    exit_price = stop_price
                elif use_trailing and trail_price > stop_price and l <= trail_price:
                    exit_reason = "Trailing Stop"
                    exit_price = trail_price
                elif custom_tp_pct > 0 and h >= entry_price * (1 + custom_tp_pct):
                    exit_reason = "Take Profit"
                    exit_price = round(entry_price * (1 + custom_tp_pct), 2)
                elif h >= target2:
                    exit_reason = "Target 2 Hit"
                    exit_price = target2
                elif h >= target1 and not t1_hit:
                    t1_hit = True
                    trail_price = max(trail_price, entry_price)
                elif c < e50 and c_prev >= e50_prev and v_ratio >= 1.25:
                    exit_reason = "Trend Breakdown"
                    exit_price = c

                if exit_reason:
                    sell_val = shares * exit_price
                    sell_fee = sell_val * half_comm
                    net_proceeds = sell_val - sell_fee
                    net_pnl = net_proceeds - buy_cost
                    ret_pct = ((exit_price - entry_price) / entry_price) * 100.0

                    cash += net_proceeds
                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": date_str,
                        "side": "BUY",
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "return_pct": round(ret_pct, 2),
                        "pnl": round(net_pnl, 2),
                        "exit_reason": exit_reason,
                    })
                    position = 0
                    shares = 0
                else:
                    if use_trailing:
                        new_trail = round(h - (2.0 * cur_atr), 2)
                        trail_price = max(trail_price, new_trail)

            if position == 0:
                is_breakout = (c >= h20 and c >= e50 and v_ratio >= 1.20)
                is_pullback = (c >= e200 and abs(c - e50) / c < 0.035 and c >= o_bar and c >= c_prev)
                is_cross = (e20_prev <= e50_prev and e20 > e50 and c >= e200)

                trigger_buy = False
                if strat_filter in ["breakout", "🚀 breakout buy"]:
                    trigger_buy = is_breakout
                elif strat_filter in ["pullback", "💎 pullback buy"]:
                    trigger_buy = is_pullback
                elif strat_filter in ["cross", "golden_cross", "⚡ golden cross buy"]:
                    trigger_buy = is_cross
                else:
                    trigger_buy = (is_breakout or is_pullback or is_cross)

                if trigger_buy and c > 0:
                    entry_price = c
                    entry_date = date_str
                    risk_dist = max(sl_atr_mult * cur_atr, entry_price * 0.03)
                    stop_price = round(max(0.1, entry_price - risk_dist), 2)
                    trail_price = stop_price
                    target1 = round(entry_price + (t1_r * risk_dist), 2)
                    target2 = round(entry_price + (t2_r * risk_dist), 2)
                    t1_hit = False

                    trade_alloc = cash * alloc_pct
                    shares = int(trade_alloc // entry_price)
                    if shares > 0:
                        trade_gross = shares * entry_price
                        buy_fee = trade_gross * half_comm
                        buy_cost = trade_gross + buy_fee
                        cash -= buy_cost
                        position = 1

            cur_holding_val = (shares * c) if position == 1 else 0.0
            cur_equity = cash + cur_holding_val
            equity_records.append({"date": dt, "equity": round(cur_equity, 2)})

        if position == 1 and shares > 0:
            last_c = float(close.iloc[-1])
            sell_val = shares * last_c
            sell_fee = sell_val * half_comm
            net_proceeds = sell_val - sell_fee
            net_pnl = net_proceeds - buy_cost
            ret_pct = ((last_c - entry_price) / entry_price) * 100.0
            cash += net_proceeds
            trades.append({
                "entry_date": entry_date,
                "exit_date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1])[:10],
                "side": "BUY",
                "entry_price": round(entry_price, 2),
                "exit_price": round(last_c, 2),
                "return_pct": round(ret_pct, 2),
                "pnl": round(net_pnl, 2),
                "exit_reason": "Open Position (Mark-to-Market)",
            })
            equity_records[-1]["equity"] = round(cash, 2)

        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_records).set_index("date") if equity_records else pd.DataFrame({"equity": [initial_capital]})

        final_equity = equity_records[-1]["equity"] if equity_records else initial_capital
        total_ret = round(((final_equity - initial_capital) / initial_capital) * 100.0, 2)

        n_trades = len(trades)
        if n_trades > 0:
            wins = [t for t in trades if t["pnl"] > 0]
            losses = [t for t in trades if t["pnl"] <= 0]
            win_rate = round((len(wins) / n_trades) * 100.0, 1)
            gross_win = sum(t["pnl"] for t in wins)
            gross_loss = abs(sum(t["pnl"] for t in losses))
            profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.9 if gross_win > 0 else 0.0)
            avg_win = round(gross_win / len(wins), 2) if wins else 0.0
            avg_loss = round(gross_loss / len(losses), 2) if losses else 0.0
        else:
            win_rate = 0.0
            profit_factor = 0.0
            avg_win = 0.0
            avg_loss = 0.0

        if not equity_df.empty and "equity" in equity_df.columns:
            peak = equity_df["equity"].cummax()
            dd = (equity_df["equity"] - peak) / peak * 100.0
            max_dd = round(abs(float(dd.min())), 2)
        else:
            max_dd = 0.0

        stats = {
            "Total Return (%)": total_ret,
            "Total Trades": n_trades,
            "Win Rate (%)": win_rate,
            "Profit Factor": profit_factor,
            "Avg. Win (LKR)": avg_win,
            "Avg. Loss (LKR)": avg_loss,
            "Max. Drawdown (%)": max_dd,
            "Net Profit (LKR)": round(final_equity - initial_capital, 2),
            "Final Capital (LKR)": round(final_equity, 2),
        }

        return {
            "stats": stats,
            "equity_curve": equity_df,
            "trades": trades_df,
        }

    def run_backtest(self, symbol: str = "", params: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        if params is None:
            params = {}
        params.update(kwargs)
        if not symbol and "symbol" in params:
            symbol = params["symbol"]
        bars_df = self.get_bars(symbol)
        if bars_df.empty:
            raise ValueError(f"No price bars found for symbol '{symbol}'")
        return self.run_spot_backtest(bars_df, params)

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

    # ── Watchlists & Price Alerts ───────────────────────────────────────

    def _init_watchlist_table(self):
        """Initializes the watchlists SQLite table and seeds default watchlists if empty."""
        con = self.connect()
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS watchlists (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_name       TEXT NOT NULL,
                    symbol          TEXT NOT NULL,
                    alert_high      REAL DEFAULT 0,
                    alert_low       REAL DEFAULT 0,
                    notes           TEXT DEFAULT '',
                    alert_frequency TEXT DEFAULT 'ALWAYS',
                    expiry_days     INTEGER DEFAULT 30,
                    last_triggered_at TEXT DEFAULT NULL,
                    created_at      TEXT DEFAULT (datetime('now')),
                    UNIQUE(list_name, symbol)
                );
            """)
            # Schema migration check for existing databases
            cols = [r[1] for r in con.execute("PRAGMA table_info(watchlists)").fetchall()]
            if "alert_frequency" not in cols:
                con.execute("ALTER TABLE watchlists ADD COLUMN alert_frequency TEXT DEFAULT 'ALWAYS'")
            if "expiry_days" not in cols:
                con.execute("ALTER TABLE watchlists ADD COLUMN expiry_days INTEGER DEFAULT 30")
            if "last_triggered_at" not in cols:
                con.execute("ALTER TABLE watchlists ADD COLUMN last_triggered_at TEXT DEFAULT NULL")
            con.execute("CREATE INDEX IF NOT EXISTS idx_watchlists_list ON watchlists(list_name);")

            # Check if default watchlists should be seeded
            count = con.execute("SELECT COUNT(*) FROM watchlists").fetchone()[0]
            if count == 0:
                defaults = [
                    ("⭐ Blue Chips", "COMB.N0000", 125.0, 95.0, "Tier-1 Commercial Bank"),
                    ("⭐ Blue Chips", "JKH.N0000", 24.0, 18.0, "Conglomerate market leader"),
                    ("⭐ Blue Chips", "HNB.N0000", 220.0, 175.0, "Strong banking franchise"),
                    ("⭐ Blue Chips", "SAMP.N0000", 95.0, 75.0, "High ROE private bank"),
                    ("⚡ High Momentum", "HAYL.N0000", 120.0, 95.0, "Export & manufacturing leader"),
                    ("⚡ High Momentum", "DIPD.N0000", 42.0, 32.0, "Gloves & rubber export play"),
                    ("⚡ High Momentum", "CALT.N0000", 75.0, 50.0, "Primary dealer / financial momentum"),
                    ("🏦 Banking & Finance", "COMB.N0000", 125.0, 95.0, "Core banking position"),
                    ("🏦 Banking & Finance", "HNB.N0000", 220.0, 175.0, "Top private lender"),
                    ("🏦 Banking & Finance", "SAMP.N0000", 95.0, 75.0, "Solid credit growth"),
                    ("🏦 Banking & Finance", "NTB.N0000", 145.0, 115.0, "High digital banking penetration"),
                    ("💎 Dividend Aristocrats", "CTC.N0000", 1300.0, 1050.0, "Consistent dividend yield > 10%"),
                    ("💎 Dividend Aristocrats", "CHEV.N0000", 140.0, 110.0, "Lubricants cash-cow"),
                    ("💎 Dividend Aristocrats", "LLUB.N0000", 135.0, 105.0, "High payout ratio"),
                ]
                valid_syms = set(r[0] for r in con.execute("SELECT symbol FROM symbols").fetchall())
                for lname, sym, a_high, a_low, notes in defaults:
                    if not valid_syms or sym in valid_syms:
                        con.execute(
                            "INSERT OR IGNORE INTO watchlists (list_name, symbol, alert_high, alert_low, notes) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (lname, sym, a_high, a_low, notes)
                        )
            con.commit()
        finally:
            con.close()

    def get_watchlist_names(self) -> List[str]:
        """Returns all distinct watchlist names."""
        con = self.connect()
        try:
            rows = con.execute("SELECT DISTINCT list_name FROM watchlists ORDER BY list_name").fetchall()
            names = [r[0] for r in rows]
            if not names:
                names = ["⭐ Blue Chips"]
            return names
        finally:
            con.close()

    def get_watchlist_items(self, list_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all items in a watchlist enriched with current price,
        day change %, confluence grade, trend status, and price alert status.
        Batch fetches bars for all symbols in the watchlist to avoid N+1 queries.
        """
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT id, symbol, alert_high, alert_low, notes, alert_frequency, expiry_days, last_triggered_at, created_at FROM watchlists "
                "WHERE list_name=? ORDER BY symbol", (list_name,)
            ).fetchall()
            if not rows:
                return []

            ind_map = {r[0]: r[1] for r in con.execute("SELECT symbol, COALESCE(industry, '') FROM symbols").fetchall()}

            symbols_in_list = list({r[1] for r in rows})
            bars_by_symbol: Dict[str, list] = {}
            if symbols_in_list:
                placeholders = ",".join("?" for _ in symbols_in_list)
                raw_bars = con.execute(
                    f"SELECT symbol, date, close, high, low, volume FROM bars "
                    f"WHERE symbol IN ({placeholders}) ORDER BY symbol, date",
                    symbols_in_list
                ).fetchall()
                for r in raw_bars:
                    bars_by_symbol.setdefault(r[0], []).append(r[1:])

            items = []
            for wid, sym, a_high, a_low, notes, afreq, exp_days, last_trig, created_at in rows:
                afreq = afreq or "ALWAYS"
                exp_days = int(exp_days if exp_days is not None else 30)

                sym_rows = bars_by_symbol.get(sym, [])
                if sym_rows:
                    bars_df = pd.DataFrame(sym_rows, columns=["date", "close", "high", "low", "volume"])
                    bars_df["date"] = pd.to_datetime(bars_df["date"])
                    bars_df = bars_df.set_index("date").sort_index()
                    for c in ["close", "high", "low", "volume"]:
                        bars_df[c] = pd.to_numeric(bars_df[c], errors="coerce")
                    bars_df["volume"] = bars_df["volume"].fillna(0)
                    bars_df["open"] = bars_df["close"].shift(1)
                    if not bars_df.empty:
                        bars_df.iloc[0, bars_df.columns.get_loc("open")] = bars_df.iloc[0]["close"]
                    bars_df = bars_df.dropna(subset=["close"])
                else:
                    bars_df = pd.DataFrame(columns=["date", "close", "high", "low", "volume"])

                c_last = 0.0
                day_chg_pct = 0.0
                confluence = {"grade": "—", "stars": "—", "trend_text": "—", "score": 0}
                if not bars_df.empty and len(bars_df) >= 2:
                    c_last = float(bars_df["close"].iloc[-1])
                    c_prev = float(bars_df["close"].iloc[-2])
                    if c_prev > 0:
                        day_chg_pct = round(((c_last - c_prev) / c_prev) * 100.0, 2)
                    confluence = self.compute_confluence(bars_df, signal=1 if c_last >= c_prev else -1)
                elif not bars_df.empty:
                    c_last = float(bars_df["close"].iloc[-1])

                a_high_val = float(a_high or 0.0)
                a_low_val = float(a_low or 0.0)

                # Expiry evaluation
                is_expired = False
                if exp_days > 0 and created_at:
                    try:
                        c_date = datetime.strptime(created_at[:10], "%Y-%m-%d")
                        if datetime.now() > c_date + timedelta(days=exp_days):
                            is_expired = True
                    except Exception:
                        pass

                alert_status = "— Normal"
                if is_expired:
                    alert_status = f"⌛ Expired ({exp_days}d limit)"
                elif a_high_val > 0 and c_last >= a_high_val:
                    alert_status = f"🔔 High Hit (>= {a_high_val:.2f})"
                elif a_low_val > 0 and c_last <= a_low_val:
                    alert_status = f"⚠️ Low Hit (<= {a_low_val:.2f})"

                items.append({
                    "id": wid,
                    "symbol": sym,
                    "industry": ind_map.get(sym, "—"),
                    "price": c_last,
                    "day_chg_pct": day_chg_pct,
                    "grade": confluence.get("grade", "—"),
                    "stars": confluence.get("stars", "—"),
                    "trend": confluence.get("trend_text", "—"),
                    "score": confluence.get("score", 0),
                    "alert_high": a_high_val,
                    "alert_low": a_low_val,
                    "alert_status": alert_status,
                    "alert_frequency": afreq,
                    "expiry_days": exp_days,
                    "last_triggered_at": last_trig or "Never",
                    "is_expired": is_expired,
                    "notes": notes or "",
                })
            return items
        finally:
            con.close()

    def add_to_watchlist(
        self,
        list_name: str,
        symbol: str,
        alert_high: float = 0.0,
        alert_low: float = 0.0,
        notes: str = "",
        alert_frequency: str = "ALWAYS",
        expiry_days: int = 30
    ):
        """Inserts or updates a symbol in the specified watchlist."""
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO watchlists (list_name, symbol, alert_high, alert_low, notes, alert_frequency, expiry_days, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(list_name, symbol) DO UPDATE SET "
                "alert_high=excluded.alert_high, alert_low=excluded.alert_low, notes=excluded.notes, "
                "alert_frequency=excluded.alert_frequency, expiry_days=excluded.expiry_days",
                (list_name.strip(), symbol.strip().upper(), float(alert_high), float(alert_low), notes.strip(), alert_frequency.strip().upper(), int(expiry_days))
            )
            con.commit()
        finally:
            con.close()

    def remove_from_watchlist(self, list_name: str, symbol: str):
        """Deletes a symbol from a specific watchlist."""
        con = self.connect()
        try:
            con.execute("DELETE FROM watchlists WHERE list_name=? AND symbol=?", (list_name, symbol))
            con.commit()
        finally:
            con.close()

    def delete_watchlist(self, list_name: str):
        """Deletes an entire watchlist and its items."""
        con = self.connect()
        try:
            con.execute("DELETE FROM watchlists WHERE list_name=?", (list_name,))
            con.commit()
        finally:
            con.close()

    def check_watchlist_alerts(self, list_name: str | None = None) -> List[Dict[str, Any]]:
        """
        Scans watchlists and identifies all positions that breached alert_high or alert_low levels,
        enforcing expiry days and alert trigger frequency logic.
        """
        con = self.connect()
        try:
            query = "SELECT id, list_name, symbol, alert_high, alert_low, notes, alert_frequency, expiry_days, last_triggered_at, created_at FROM watchlists"
            params = ()
            if list_name:
                query += " WHERE list_name=?"
                params = (list_name,)
            rows = con.execute(query, params).fetchall()

            alerts = []
            now_dt = datetime.now()
            today_str = now_dt.strftime("%Y-%m-%d")
            now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

            candidates = []
            for wid, lname, sym, a_high, a_low, notes, afreq, exp_days, last_trig, created_at in rows:
                a_high_val = float(a_high or 0.0)
                a_low_val = float(a_low or 0.0)
                if a_high_val <= 0 and a_low_val <= 0:
                    continue

                afreq = (afreq or "ALWAYS").upper()
                exp_days = int(exp_days if exp_days is not None else 30)

                # Check Expiry
                if exp_days > 0 and created_at:
                    try:
                        c_date = datetime.strptime(created_at[:10], "%Y-%m-%d")
                        if now_dt > c_date + timedelta(days=exp_days):
                            continue  # Alert is expired
                    except Exception:
                        pass

                # Check Frequency Suppression
                if last_trig:
                    if afreq == "ONCE":
                        continue  # Already triggered once
                    elif afreq == "DAILY" and last_trig[:10] == today_str:
                        continue  # Already triggered today

                candidates.append((wid, lname, sym, a_high_val, a_low_val, notes, afreq))

            if not candidates:
                con.commit()
                return []

            # Bulk fetch latest close prices for candidate symbols
            unique_syms = list({c[2] for c in candidates})
            placeholders = ",".join("?" for _ in unique_syms)
            price_query = f"""
            SELECT symbol, close
            FROM (
                SELECT symbol, close,
                       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) as rn
                FROM bars
                WHERE symbol IN ({placeholders})
            ) WHERE rn = 1
            """
            price_rows = con.execute(price_query, unique_syms).fetchall()
            latest_prices = {r[0]: float(r[1]) for r in price_rows}

            for wid, lname, sym, a_high_val, a_low_val, notes, afreq in candidates:
                c_last = latest_prices.get(sym)
                if c_last is None:
                    continue

                triggered_type = None
                thresh = 0.0
                if a_high_val > 0 and c_last >= a_high_val:
                    triggered_type = "HIGH_BREAKOUT"
                    thresh = a_high_val
                elif a_low_val > 0 and c_last <= a_low_val:
                    triggered_type = "LOW_SUPPORT_BREACH"
                    thresh = a_low_val

                if triggered_type:
                    # Record trigger timestamp in DB
                    con.execute("UPDATE watchlists SET last_triggered_at=? WHERE id=?", (now_str, wid))

                    alerts.append({
                        "id": wid,
                        "list_name": lname,
                        "symbol": sym,
                        "current_price": c_last,
                        "type": triggered_type,
                        "threshold": thresh,
                        "alert_high": a_high_val,
                        "alert_low": a_low_val,
                        "alert_frequency": afreq,
                        "notes": notes or "",
                    })

            con.commit()
            return alerts
        finally:
            con.close()

    def send_watchlist_telegram_alerts(self, alerts: List[Dict[str, Any]]) -> str:
        """Dispatches triggered price alerts to Telegram."""
        if not alerts:
            return "No triggered alerts to send."

        lines = [
            "🔔 *CSE WATCHLIST PRICE ALERT* 🔔",
            f"📅 *Timestamp:* `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
            "────────────────────────",
        ]
        for a in alerts:
            sym = a["symbol"]
            cur = a["current_price"]
            atype = a["type"]
            thresh = a["threshold"]
            lname = a["list_name"]

            if atype == "HIGH_BREAKOUT":
                icon = "🚀"
                desc = f"Hit target level *>= {thresh:.2f} LKR*"
            else:
                icon = "⚠️"
                desc = f"Breached support level *<= {thresh:.2f} LKR*"

            lines.append(f"{icon} *{sym}* in [{lname}]")
            lines.append(f"• *Current Price:* `{cur:.2f} LKR`")
            lines.append(f"• *Trigger:* {desc}")
            if a.get("notes"):
                lines.append(f"• *Note:* _{a['notes']}_")
            lines.append("────────────────────────")

        lines.append("⚠️ _CSE Analyzer Watchlist Alert • Verify before executing_")
        text = "\n".join(lines)
        stocks.send_telegram_message(text, force=True)
        return f"Successfully sent {len(alerts)} alerts to Telegram!"

    # ── Official CSE Company Profile ────────────────────────────────────

    def get_formatted_company_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches official CSE company profile, board directors, top executive posts,
        and business summary from CSE API with caching.
        """
        clean_sym = symbol.split(".")[0].strip().upper()
        if clean_sym in self._company_profile_cache:
            return self._company_profile_cache[clean_sym]

        try:
            data = stocks.api_company_profile(self.session, clean_sym)
        except Exception as e:
            return {
                "symbol": clean_sym,
                "name": clean_sym,
                "sector": "—",
                "board_type": "—",
                "established": "—",
                "auditors": "—",
                "web": "—",
                "email": "—",
                "tel": "—",
                "registered_office": "—",
                "business_summary": "Profile information currently unavailable.",
                "leadership": [],
                "directors": [],
                "error": str(e),
            }

        # Parse reqComSumInfo
        sum_info = data.get("reqComSumInfo") or [{}]
        first_sum = sum_info[0] if isinstance(sum_info, list) and sum_info else {}

        # Parse topPosts (Executive Leadership)
        top_posts = data.get("topPosts") or []
        leadership = []
        if isinstance(top_posts, list):
            for post in top_posts:
                name = f"{post.get('firstName', '')} {post.get('lastName', '')}".strip()
                desig = post.get("designationOther", "").strip()
                if name or desig:
                    leadership.append({"name": name, "designation": desig})

        # Parse infoCompanyDirector
        directors_raw = data.get("infoCompanyDirector") or []
        directors = []
        if isinstance(directors_raw, list):
            for d in directors_raw:
                dname = f"{d.get('firstName', '')} {d.get('lastName', '')}".strip()
                dcat = d.get("category", "") or d.get("directorType", "")
                if dname:
                    directors.append({"name": dname, "category": dcat})

        # Parse business summary
        biz_list = data.get("infoCompanyBusinessSummary") or []
        biz_summary = ""
        if isinstance(biz_list, list) and biz_list:
            bodies = [b.get("body", "").strip() for b in biz_list if b.get("body")]
            biz_summary = " ".join(bodies)
        if not biz_summary:
            biz_summary = "Official business summary registered with Colombo Stock Exchange."

        profile = {
            "symbol": clean_sym,
            "name": first_sum.get("name", clean_sym),
            "sector": first_sum.get("sector", "—"),
            "board_type": first_sum.get("boardType", "Main Board"),
            "established": first_sum.get("established", "—"),
            "auditors": first_sum.get("auditors", "—"),
            "web": first_sum.get("web", "—"),
            "email": first_sum.get("email1", "—"),
            "tel": first_sum.get("tel1", "—"),
            "registered_office": first_sum.get("registeredOffice", "—"),
            "business_summary": biz_summary,
            "leadership": leadership,
            "directors": directors,
        }

        self._company_profile_cache[clean_sym] = profile
        return profile

    # ── Data Infrastructure & Quality (Features 1–7) ────────────────────

    def clean_bars_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean bars data for missing days, zero-volume days, and bad ticks (Feature 4)."""
        if df.empty:
            return df
        df = df.copy()

        # Remove duplicate index timestamps if any
        df = df[~df.index.duplicated(keep="last")].sort_index()

        # Ensure numeric types and handle non-positive prices
        for col in ["close", "high", "low"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df[df[col] > 0]

        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

        # Flag and filter extreme bad ticks (> 50% jump in 1 bar that reverses immediately)
        if len(df) >= 3:
            ret = df["close"].pct_change()
            bad_spike = (ret.abs() > 0.50) & (df["close"].pct_change(-1).abs() > 0.40) & (np.sign(ret) != np.sign(df["close"].pct_change(-1)))
            if bad_spike.any():
                df.loc[bad_spike, "close"] = (df["close"].shift(1) + df["close"].shift(-1)) / 2.0

        return df

    def adjust_corporate_actions(
        self,
        df: pd.DataFrame,
        split_ratio: float = 1.0,
        dividend_adjustment_lkr: float = 0.0
    ) -> pd.DataFrame:
        """Adjust historical prices for stock splits and dividends (Feature 5)."""
        if df.empty:
            return df
        df = df.copy()

        if split_ratio != 1.0 and split_ratio > 0:
            df["close"] = df["close"] / split_ratio
            df["high"] = df["high"] / split_ratio
            df["low"] = df["low"] / split_ratio
            if "open" in df.columns:
                df["open"] = df["open"] / split_ratio
            if "volume" in df.columns:
                df["volume"] = df["volume"] * split_ratio

        if dividend_adjustment_lkr > 0:
            df["close"] = (df["close"] - dividend_adjustment_lkr).clip(lower=0.1)

        return df

    def validate_data_quality(self, symbol: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Validate historical data quality, flagging gaps, zero-volume spells, or tick jumps (Feature 6)."""
        if df is None:
            df = self.get_bars(symbol)

        if df.empty:
            return {"symbol": symbol, "status": "Error", "is_healthy": False, "issues": ["No historical bars found."]}

        issues: List[str] = []
        n_bars = len(df)

        if n_bars < 30:
            issues.append(f"Short historical depth ({n_bars} bars, recommended >= 50).")

        # Zero volume days
        if "volume" in df.columns:
            zero_vol_pct = (df["volume"] == 0).sum() / float(n_bars) * 100.0
            if zero_vol_pct > 40.0:
                issues.append(f"High illiquidity: {zero_vol_pct:.1f}% of trading days have zero recorded volume.")

        # Large price gaps (> 25% single-day jump)
        if len(df) >= 2:
            max_jump = float(df["close"].pct_change().abs().max()) * 100.0
            if max_jump >= 25.0:
                issues.append(f"Significant price jump ({max_jump:.1f}%) detected.")

        is_healthy = len(issues) == 0
        return {
            "symbol": symbol,
            "total_bars": n_bars,
            "status": "Healthy" if is_healthy else "Review Required",
            "is_healthy": is_healthy,
            "issues": issues,
            "last_date": str(df.index[-1].strftime("%Y-%m-%d")) if isinstance(df.index, pd.DatetimeIndex) else "—"
        }

    def get_universe_by_sector(self) -> Dict[str, List[Dict[str, Any]]]:
        """Universe manager with sector grouping (Feature 7)."""
        all_syms = self.get_all_symbols()
        sectors: Dict[str, List[Dict[str, Any]]] = {}
        for s in all_syms:
            sec = s.get("industry") or "Unclassified"
            if sec not in sectors:
                sectors[sec] = []
            sectors[sec].append(s)
        return sectors

    # ── Unified Analytical Suite (Features 8–50) ────────────────────────

    def get_company_name(self, symbol: str) -> str:
        """Return human-readable company name from local mapping or symbol string."""
        clean = symbol.split(".")[0].strip().upper()
        cse_names = {
            "COMB": "Commercial Bank of Ceylon",
            "JKH": "John Keells Holdings",
            "SAMP": "Sampath Bank",
            "HNB": "Hatton National Bank",
            "DIST": "Distilleries Company",
            "MELS": "Melstacorp PLC",
            "LOLC": "LOLC Holdings",
            "DIAL": "Dialog Axiata",
            "HAYL": "Hayleys PLC",
            "CARG": "Cargills (Ceylon)",
            "LION": "Lion Brewery Ceylon",
            "CTC": "Ceylon Tobacco Company",
            "AEL": "Access Engineering",
            "RICH": "Richard Pieris & Co",
            "EXPO": "Expolanka Holdings",
            "SLTL": "Sri Lanka Telecom",
            "VONE": "Vallibel One",
            "DIPD": "Dipped Products",
            "ACL": "ACL Cables",
            "TKYO": "Tokyo Cement Company"
        }
        return cse_names.get(clean, symbol)

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        """Alias for get_formatted_company_profile."""
        return self.get_formatted_company_profile(symbol)

    def get_technical_analysis(self, symbol: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Run technical suite (Features 9–20) on a CSE stock."""
        df = self.get_bars(symbol)
        df = self.clean_bars_data(df)
        return TechnicalEngine.analyze_full_technical_suite(df)

    def get_fundamental_profile(self, symbol: str) -> Dict[str, Any]:
        """Generate fundamental valuation profile (Features 21–27)."""
        latest_prices = self.get_latest_prices()
        current_price = latest_prices.get(symbol, 50.0)
        industries = self.get_symbol_industries()
        industry = industries.get(symbol, "Diversified Financials")
        name = self.get_company_name(symbol)
        return FundamentalEngine.generate_fundamental_profile(symbol, name, industry, current_price)

    def get_market_context(self, symbol: str) -> Dict[str, Any]:
        """Compute benchmark comparison, liquidity, and circuit limit status (Features 28, 32, 33)."""
        df = self.get_bars(symbol)
        df = self.clean_bars_data(df)
        rs_data = MarketContextEngine.compute_benchmark_relative_strength(df)
        liq_data = MarketContextEngine.compute_liquidity_and_days_to_exit(df)
        latest_prices = self.get_latest_prices()
        curr_price = latest_prices.get(symbol, 50.0)
        prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else curr_price
        circuit_data = MarketContextEngine.check_circuit_breakers_and_bands(curr_price, prev_close)

        combined = {}
        combined.update(rs_data)
        combined.update(liq_data)
        combined.update(circuit_data)
        return combined

    def get_ml_prediction(self, symbol: str) -> Dict[str, Any]:
        """Extract multi-factor feature vector and compute calibrated outperformance probability (Features 37–41)."""
        df = self.get_bars(symbol)
        df = self.clean_bars_data(df)
        fund = self.get_fundamental_profile(symbol)
        mkt = self.get_market_context(symbol)
        features = MLEngine.extract_feature_vector(df, fundamental_profile=fund, market_context=mkt)
        pred = MLEngine.predict_calibrated_outperformance(features)
        pred["anomaly_check"] = MLEngine.detect_anomalies(df)
        pred["trend_forecast"] = MLEngine.forecast_baseline_trend(df)
        return pred

    def get_composite_scorecard(self, symbol: str) -> Dict[str, Any]:
        """Generate unified 4-tier decision scorecard with ABSTAIN MODE and SHAP factors (Feature 49)."""
        df, tech_summary = self.get_technical_analysis(symbol)
        latest_prices = self.get_latest_prices()
        curr_price = latest_prices.get(symbol, float(df["close"].iloc[-1]) if not df.empty else 50.0)
        fund = self.get_fundamental_profile(symbol)
        mkt = self.get_market_context(symbol)
        features = MLEngine.extract_feature_vector(df, fundamental_profile=fund, market_context=mkt)
        ml_pred = MLEngine.predict_calibrated_outperformance(features)

        name = self.get_company_name(symbol)

        return RiskScorecardEngine.generate_composite_scorecard(
            symbol=symbol,
            name=name,
            current_price=curr_price,
            technical_summary=tech_summary,
            fundamental_profile=fund,
            market_context=mkt,
            ml_prediction=ml_pred
        )

    def run_spot_backtest(
        self,
        symbol: Union[str, pd.DataFrame],
        starting_capital: float = 1_000_000.0,
        risk_per_trade_pct: float = 2.0,
        target1_rr: float = 1.5,
        target2_rr: float = 2.5,
        atr_stop_multiplier: float = 1.5,
        slippage_pct: float = 0.3,
        strategy_mode: str = "QQE / Momentum"
    ) -> Dict[str, Any]:
        """Run realistic CSE spot equity backtest with 1.12% fees and slippage (Feature 44)."""
        if isinstance(symbol, pd.DataFrame):
            df = symbol
        else:
            df = self.get_bars(symbol)
        df = self.clean_bars_data(df)
        return BacktestEngine.run_spot_backtest(
            df=df,
            starting_capital=starting_capital,
            risk_per_trade_pct=risk_per_trade_pct,
            target1_rr=target1_rr,
            target2_rr=target2_rr,
            atr_stop_multiplier=atr_stop_multiplier,
            slippage_pct=slippage_pct,
            strategy_mode=strategy_mode
        )

    def run_backtest(
        self,
        symbol: str,
        capital: float = 1_000_000.0,
        commission_pct: float = 1.12,
        allocation_pct: float = 100.0,
        strategy_mode: str = "all",
        strategy: str = "all",
        target1_rr: float = 1.5,
        target2_rr: float = 2.5,
        sl_atr: float = 1.5,
        use_trailing: bool = True
    ) -> Dict[str, Any]:
        """Run spot equity backtest and return structured dictionaries for BacktestTab UI."""
        strat = strategy if strategy != "all" else strategy_mode
        raw = self.run_spot_backtest(
            symbol=symbol,
            starting_capital=float(capital),
            target1_rr=float(target1_rr),
            target2_rr=float(target2_rr),
            atr_stop_multiplier=float(sl_atr),
            strategy_mode=strat
        )
        trades = raw.get("trades", [])
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        if not trades_df.empty:
            trades_df["return_pct"] = trades_df["pnl_pct"]
            trades_df["pnl"] = trades_df["pnl_lkr"]

        eq_curve = raw.get("equity_curve", [])
        equity_df = pd.DataFrame(eq_curve) if eq_curve else pd.DataFrame()
        if not equity_df.empty:
            equity_df["equity"] = equity_df["portfolio_value"]

        stats = {
            "Total Return (%)": f"{raw.get('return_pct', 0.0):.2f}",
            "Total Trades": raw.get("total_trades", 0),
            "Win Rate (%)": f"{raw.get('win_rate_pct', 0.0):.1f}",
            "Profit Factor": f"{raw.get('profit_factor', 0.0):.2f}",
            "Avg. Win (LKR)": raw.get("avg_win_pct", 0.0) * float(capital) / 100.0,
            "Avg. Loss (LKR)": raw.get("avg_loss_pct", 0.0) * float(capital) / 100.0,
            "Max. Drawdown (%)": f"{raw.get('max_drawdown_pct', 0.0):.2f}",
            "Net Profit (LKR)": raw.get("net_profit_lkr", 0.0),
            "Benchmark Excess (%)": raw.get("excess_return_vs_aspi", 0.0)
        }
        return {
            "stats": stats,
            "equity_curve": equity_df,
            "trades": trades_df,
            "raw": raw
        }

    def run_walk_forward_validation(self, symbol: Union[str, pd.DataFrame], n_splits: int = 3) -> Dict[str, Any]:
        """Run rolling walk-forward backtest validation to prevent lookahead overfitting (Feature 45)."""
        if isinstance(symbol, pd.DataFrame):
            df = symbol
        else:
            df = self.get_bars(symbol)
        df = self.clean_bars_data(df)
        return BacktestEngine.run_walk_forward_validation(df, n_splits=n_splits)

    run_walk_forward = run_walk_forward_validation

    def get_macro_overlay(self) -> Dict[str, Any]:
        """Get macroeconomic data overlay (CBSL rates, inflation, T-bills, USD/LKR) (Feature 30)."""
        return MarketContextEngine.get_macro_overlay()

    def get_sector_rotation(self) -> List[Dict[str, Any]]:
        """Get sector rotation performance heatmap (Feature 29)."""
        universe = self.get_universe_by_sector()
        return MarketContextEngine.compute_sector_rotation_matrix(universe)

    def get_news_and_events(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get corporate announcements and financial event calendar (Features 34–36)."""
        return {
            "announcements": NewsEventsEngine.get_recent_announcements(symbol),
            "calendar": NewsEventsEngine.get_event_calendar()
        }

    def calculate_position_size(
        self,
        account_capital: float,
        entry_price: float,
        stop_loss_price: float,
        risk_pct: float = 1.5,
        max_allocation_pct: float = 25.0,
        avg_daily_volume: int = 50000
    ) -> Dict[str, Any]:
        """Calculate optimal position sizing and stops (Feature 47)."""
        return RiskScorecardEngine.calculate_position_size(
            account_capital=account_capital,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            risk_pct=risk_pct,
            max_capital_allocation_pct=max_allocation_pct,
            avg_daily_volume=avg_daily_volume
        )

    def evaluate_portfolio_risk(self, holdings: List[Dict[str, Any]], cash: float = 0.0, benchmark_return_pct: float = 12.0) -> Dict[str, Any]:
        """Evaluate portfolio risk, VaR 95%, concentration warnings, and Portfolio Alpha (Feature 48)."""
        return RiskScorecardEngine.evaluate_portfolio_risk(holdings, portfolio_cash=cash, benchmark_aspi_return_pct=benchmark_return_pct)

    def run_strategy_optimization(
        self,
        symbol: str,
        starting_capital: float = 1_000_000.0,
        strategy_mode: str = "QQE / Momentum",
        param_grid: Optional[Dict[str, List[Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Run grid search parameter optimization for a stock strategy."""
        df = self.get_bars(symbol)
        df = self.clean_bars_data(df)
        return BacktestEngine.optimize_strategy_parameters(
            df=df,
            starting_capital=starting_capital,
            strategy_mode=strategy_mode,
            param_grid=param_grid
        )

    def get_portfolio_rebalancing(
        self,
        holdings: Optional[List[Dict[str, Any]]] = None,
        target_mode: str = "EQUAL_WEIGHT",
        custom_weights: Optional[Dict[str, float]] = None,
        portfolio_cash: float = 0.0,
        min_trade_lkr: float = 5000.0
    ) -> Dict[str, Any]:
        """Calculate recommended rebalancing trade orders for portfolio positions."""
        if holdings is None:
            holdings = self.get_portfolio_positions()
        return RiskScorecardEngine.calculate_portfolio_rebalance(
            holdings=holdings,
            target_mode=target_mode,
            custom_weights=custom_weights,
            portfolio_cash=portfolio_cash,
            min_trade_lkr=min_trade_lkr
        )

    def scan_equity_signals(
        self,
        strategy_mode: str = "all",
        min_score: int = 50,
        min_vol: float = 1.0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Scan enabled CSE equities using the 50-feature decision pipeline:
        - Evaluates Spot BUY Setups (Breakout, Pullback, Golden Cross) and EXIT areas
        - Evaluates Calibrated Probability with ABSTAIN MODE
        - Evaluates Confluence Score (0 to 100) and Grades (A+, A, B, C)
        - Computes exact Entry Zones, Stop Loss, Target 1, Target 2, and Liquidity Tiers
        """
        symbols = self.get_symbol_list()
        results: List[Dict[str, Any]] = []

        latest_prices = self.get_latest_prices()
        industries = self.get_symbol_industries()

        # Batch load all bars in single indexed query for instantaneous scan execution
        con = self.connect()
        bars_by_symbol: Dict[str, list] = {}
        try:
            raw_bars = con.execute("SELECT symbol, date, close, high, low, volume FROM bars ORDER BY symbol, date").fetchall()
            for r in raw_bars:
                bars_by_symbol.setdefault(r[0], []).append(r[1:])
        finally:
            con.close()

        for sym in symbols:
            try:
                sym_rows = bars_by_symbol.get(sym, [])
                if not sym_rows or len(sym_rows) < 25:
                    continue

                df = pd.DataFrame(sym_rows, columns=["date", "close", "high", "low", "volume"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                for col in ["close", "high", "low", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df["volume"] = df["volume"].fillna(0)
                df["open"] = df["close"].shift(1)
                if not df.empty:
                    df.iloc[0, df.columns.get_loc("open")] = df.iloc[0]["close"]

                df = self.clean_bars_data(df)
                if df.empty or len(df) < 25:
                    continue

                c = float(df["close"].iloc[-1])
                price = latest_prices.get(sym, c)
                industry = industries.get(sym, "Diversified")
                name = self.get_company_name(sym)

                # Fast vectorized technical evaluation
                df = TechnicalEngine.compute_moving_averages(df)
                df = TechnicalEngine.compute_rsi(df)
                df = TechnicalEngine.compute_atr_and_volatility(df)
                df = TechnicalEngine.compute_volume_analysis(df)
                breakout = TechnicalEngine.check_breakouts(df)

                last_bar = df.iloc[-1]
                vol_surge = float(last_bar.get("volume_surge", 1.0))
                if vol_surge < (min_vol * 0.8) and min_vol > 1.2:
                    continue

                # Quick fundamental profile
                fund = FundamentalEngine.generate_fundamental_profile(sym, name, industry, price)
                f_score = fund.get("piotroski", {}).get("f_score", 5)

                # Quick liquidity & relative strength
                liq = MarketContextEngine.compute_liquidity_and_days_to_exit(df)
                ret_20d = float((c / df["close"].iloc[-min(21, len(df))]) - 1.0) * 100.0
                rs_data = {"rs_momentum_20d_pct": round(ret_20d - 0.8, 1), "beta": 1.0}

                # ML Calibrated prediction
                features = MLEngine.extract_feature_vector(df, fundamental_profile=fund, market_context=rs_data)
                ml_pred = MLEngine.predict_calibrated_outperformance(features)
                calibrated_prob = ml_pred.get("calibrated_prob_pct", 50.0)
                is_abstain = ml_pred.get("abstain_mode", False)

                # Setup conditions
                ema21 = float(last_bar.get("ema_21", c))
                ema50 = float(last_bar.get("ema_50", c))
                ema200 = float(last_bar.get("ema_200", c))
                rsi = float(last_bar.get("rsi", 50.0))
                atr_val = float(last_bar.get("atr", c * 0.03))

                is_breakout = bool(breakout.get("is_20d_breakout", False)) or bool(breakout.get("is_52w_high", False))
                is_pullback = c >= ema200 and (c <= ema21 * 1.02 and c >= ema50 * 0.98) and rsi >= 45
                is_golden_cross = bool(last_bar.get("golden_cross", False)) or bool(last_bar.get("bull_cross_20_50", False))

                # Confluence score
                score = 30
                if c > ema50 > ema200:
                    score += 20
                if 50 < rsi < 70:
                    score += 15
                if vol_surge >= 1.25:
                    score += 15
                if f_score >= 6:
                    score += 10
                if rs_data.get("rs_momentum_20d_pct", 0) > 0:
                    score += 10

                score = min(98, score)
                if score < min_score:
                    continue

                grade = "A+" if score >= 85 else ("A" if score >= 70 else ("B" if score >= 55 else "C"))
                stars = "⭐⭐⭐⭐⭐" if grade == "A+" else ("⭐⭐⭐⭐" if grade == "A" else ("⭐⭐⭐" if grade == "B" else "⭐⭐"))

                # Action and setup text
                action = "HOLD"
                signal_text = "Consolidation"

                if is_abstain:
                    action = "ABSTAIN"
                    signal_text = "⚠️ No Clear Edge"
                elif is_breakout:
                    action = "BUY"
                    signal_text = "🚀 Momentum Breakout"
                elif is_pullback:
                    action = "BUY"
                    signal_text = "💎 Value Pullback"
                elif is_golden_cross:
                    action = "BUY"
                    signal_text = "⚡ Golden Cross"
                elif rsi >= 75:
                    action = "EXIT"
                    signal_text = "🎯 Overbought / Take Profit"
                elif c < ema50 * 0.96:
                    action = "EXIT"
                    signal_text = "🔻 Trend Breakdown"

                # Strategy mode filtering
                if strategy_mode == "breakout" and "Breakout" not in signal_text:
                    continue
                elif strategy_mode == "pullback" and "Pullback" not in signal_text:
                    continue
                elif strategy_mode == "golden_cross" and "Golden Cross" not in signal_text:
                    continue
                elif strategy_mode == "exit_only" and action != "EXIT":
                    continue

                stop_dist = max(atr_val * 1.5, c * 0.025)
                stop_loss = round(c - stop_dist, 2)
                trailing_stop = round(c - (atr_val * 1.5), 2)
                target1 = round(c + (stop_dist * 1.5), 2)
                target2 = round(c + (stop_dist * 2.5), 2)

                results.append({
                    "symbol": sym,
                    "name": name,
                    "industry": industry,
                    "action": action,
                    "signal_text": signal_text,
                    "grade": grade,
                    "stars": stars,
                    "score": score,
                    "price": f"{c:.2f}",
                    "stop_loss": stop_loss,
                    "trailing_stop": trailing_stop,
                    "target1": target1,
                    "target2": target2,
                    "vol_ratio": f"{vol_surge:.1f}x",
                    "trend": "Bullish" if c > ema50 > ema200 else ("Bearish" if c < ema50 < ema200 else "Neutral"),
                    "pattern": "Bullish Reversal" if last_bar.get("pat_hammer", False) or last_bar.get("pat_engulfing", False) else "Standard",
                    "date": str(df.index[-1].strftime("%Y-%m-%d")) if isinstance(df.index, pd.DatetimeIndex) else "—",
                    "calibrated_prob": calibrated_prob,
                    "is_abstain": is_abstain,
                    "weekly_trend": "Bullish" if c > ema21 else "Neutral",
                    "divergence": "Bullish Div" if last_bar.get("rsi_bull_div", False) else "None",
                    "dist_52w": f"{breakout.get('dist_52w_high_pct', 0.0):.1f}%",
                    "liquidity_tier": liq.get("liquidity_tier", "Tier 2"),
                    "days_to_exit": liq.get("days_to_exit", 1.0)
                })
            except Exception:
                continue

        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]

