# core/technical_engine.py — Advanced Technical Analysis Toolkit
"""
Technical Analysis Suite covering Features 9 to 20:
- Moving Averages (SMA/EMA, Golden/Death cross)
- RSI with Bullish/Bearish Divergence Detection
- MACD with Crossover & Histogram Momentum
- Bollinger Bands & Volatility Squeeze Detection
- ATR & Volatility Metrics (Normalized ATR %, Historical Volatility)
- Stochastic & ADX (Average Directional Index)
- Volume Analysis (OBV, VWAP, Volume Spikes)
- Auto Support & Resistance Clustering
- Candlestick Pattern Recognition (Hammer, Engulfing, Morning Star, Doji)
- Trend & Regime Classifier (Bull, Bear, Sideways, High Volatility)
- Multi-Timeframe Alignment (Daily, Weekly, Monthly)
- Breakout Scanner (52-Week Highs/Lows, 20-Day Range Breaks)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class TechnicalEngine:
    """High-performance vectorized technical indicator and pattern analyzer."""

    @staticmethod
    def compute_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
        """Compute standard SMA and EMA spans (Features 9)."""
        df = df.copy()
        close = df["close"]

        df["sma_20"] = close.rolling(window=20, min_periods=5).mean()
        df["sma_50"] = close.rolling(window=50, min_periods=10).mean()
        df["sma_100"] = close.rolling(window=100, min_periods=20).mean()
        df["sma_200"] = close.rolling(window=200, min_periods=30).mean()

        df["ema_9"] = close.ewm(span=9, adjust=False).mean()
        df["ema_21"] = close.ewm(span=21, adjust=False).mean()
        df["ema_50"] = close.ewm(span=50, adjust=False).mean()
        df["ema_200"] = close.ewm(span=200, adjust=False).mean()

        # Golden Cross (EMA 50 crosses above EMA 200) & Death Cross
        df["golden_cross"] = (df["ema_50"] > df["ema_200"]) & (df["ema_50"].shift(1) <= df["ema_200"].shift(1))
        df["death_cross"] = (df["ema_50"] < df["ema_200"]) & (df["ema_50"].shift(1) >= df["ema_200"].shift(1))

        # Short term cross: EMA 20 over EMA 50
        df["bull_cross_20_50"] = (df["ema_21"] > df["ema_50"]) & (df["ema_21"].shift(1) <= df["ema_50"].shift(1))
        df["bear_cross_20_50"] = (df["ema_21"] < df["ema_50"]) & (df["ema_21"].shift(1) >= df["ema_50"].shift(1))

        return df

    @staticmethod
    def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Compute RSI with overbought/oversold and divergence detection (Feature 10)."""
        df = df.copy()
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / (avg_loss.replace(0, np.nan))
        df["rsi"] = 100 - (100 / (1 + rs))
        df["rsi"] = df["rsi"].fillna(50.0)

        # Divergence Detection over a 15-bar lookback window
        # Bullish Divergence: Price forms lower low, while RSI forms higher low
        bull_div = [False] * len(df)
        bear_div = [False] * len(df)

        close_vals = df["close"].values
        rsi_vals = df["rsi"].values
        n = len(df)

        for i in range(15, n):
            # Check price swing lows
            window_price = close_vals[i - 15: i + 1]
            window_rsi = rsi_vals[i - 15: i + 1]

            # Current bar near low of window
            if close_vals[i] <= np.min(window_price) * 1.01:
                prior_min_idx = int(np.argmin(window_price[:-3]))
                if close_vals[i] < window_price[prior_min_idx]:
                    if rsi_vals[i] > window_rsi[prior_min_idx] + 2.0 and rsi_vals[i] < 45:
                        bull_div[i] = True

            # Bearish Divergence: Price forms higher high, while RSI forms lower high
            if close_vals[i] >= np.max(window_price) * 0.99:
                prior_max_idx = int(np.argmax(window_price[:-3]))
                if close_vals[i] > window_price[prior_max_idx]:
                    if rsi_vals[i] < window_rsi[prior_max_idx] - 2.0 and rsi_vals[i] > 55:
                        bear_div[i] = True

        df["rsi_bull_div"] = bull_div
        df["rsi_bear_div"] = bear_div
        return df

    @staticmethod
    def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """Compute MACD, signal line, and histogram (Feature 11)."""
        df = df.copy()
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        df["macd_line"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd_line"].ewm(span=signal, adjust=False).mean()
        df["macd_hist"] = df["macd_line"] - df["macd_signal"]

        df["macd_bull_cross"] = (df["macd_line"] > df["macd_signal"]) & (df["macd_line"].shift(1) <= df["macd_signal"].shift(1))
        df["macd_bear_cross"] = (df["macd_line"] < df["macd_signal"]) & (df["macd_line"].shift(1) >= df["macd_signal"].shift(1))
        return df

    @staticmethod
    def compute_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """Compute Bollinger Bands, Bandwidth, %B, and Squeeze (Feature 12)."""
        df = df.copy()
        sma = df["close"].rolling(window=period, min_periods=5).mean()
        rstd = df["close"].rolling(window=period, min_periods=5).std().fillna(0.0)

        df["bb_upper"] = sma + (rstd * std_dev)
        df["bb_lower"] = sma - (rstd * std_dev)
        df["bb_mid"] = sma

        # Bandwidth %
        df["bb_bandwidth"] = np.where(sma > 0, (df["bb_upper"] - df["bb_lower"]) / sma * 100.0, 0.0)
        # %B position
        denom = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
        df["bb_percent_b"] = (df["close"] - df["bb_lower"]) / denom

        # Squeeze detection: Bandwidth is at its lowest 10-bar percentile or below 5%
        bw_min_50 = df["bb_bandwidth"].rolling(window=50, min_periods=10).min()
        df["bb_squeeze"] = (df["bb_bandwidth"] <= bw_min_50 * 1.15) | (df["bb_bandwidth"] < 5.0)

        return df

    @staticmethod
    def compute_atr_and_volatility(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Compute True Range, ATR, Normalized ATR %, and Historical Volatility (Feature 13)."""
        df = df.copy()
        high = df["high"]
        low = df["low"]
        close_prev = df["close"].shift(1)

        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        df["atr"] = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean().fillna(tr)
        df["natr"] = np.where(df["close"] > 0, (df["atr"] / df["close"]) * 100.0, 0.0)

        # 20-day annualized historical volatility (assuming 252 CSE trading days)
        log_ret = np.log(df["close"] / df["close"].shift(1).replace(0, np.nan)).fillna(0.0)
        df["hv_20"] = log_ret.rolling(window=20, min_periods=5).std() * np.sqrt(252) * 100.0
        df["hv_20"] = df["hv_20"].fillna(0.0)

        return df

    @staticmethod
    def compute_stochastic_and_adx(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, adx_period: int = 14) -> pd.DataFrame:
        """Compute Stochastic Oscillator and Average Directional Index (ADX) (Feature 14)."""
        df = df.copy()

        # Stochastic
        low_min = df["low"].rolling(window=k_period, min_periods=3).min()
        high_max = df["high"].rolling(window=k_period, min_periods=3).max()
        stoch_denom = (high_max - low_min).replace(0, np.nan)
        df["stoch_k"] = ((df["close"] - low_min) / stoch_denom) * 100.0
        df["stoch_k"] = df["stoch_k"].fillna(50.0)
        df["stoch_d"] = df["stoch_k"].rolling(window=d_period, min_periods=1).mean()

        # ADX (Directional Movement)
        high_diff = df["high"].diff()
        low_diff = -df["low"].diff()

        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)

        plus_dm_s = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / adx_period, min_periods=adx_period).mean()
        minus_dm_s = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / adx_period, min_periods=adx_period).mean()

        atr = df["atr"] if "atr" in df.columns else (df["high"] - df["low"]).rolling(adx_period).mean()
        atr_safe = atr.replace(0, np.nan)

        df["plus_di"] = (plus_dm_s / atr_safe) * 100.0
        df["minus_di"] = (minus_dm_s / atr_safe) * 100.0

        dx_denom = (df["plus_di"] + df["minus_di"]).replace(0, np.nan)
        dx = ((df["plus_di"] - df["minus_di"]).abs() / dx_denom) * 100.0
        df["adx"] = dx.ewm(alpha=1.0 / adx_period, min_periods=adx_period).mean().fillna(15.0)

        return df

    @staticmethod
    def compute_volume_analysis(df: pd.DataFrame) -> pd.DataFrame:
        """Compute OBV, daily VWAP proxy, and volume surge multipliers (Feature 15)."""
        df = df.copy()

        # On-Balance Volume (OBV)
        close_diff = df["close"].diff()
        vol = df["volume"].fillna(0)
        direction = np.sign(close_diff).fillna(0)
        df["obv"] = (direction * vol).cumsum()
        df["obv_ema"] = df["obv"].ewm(span=20, adjust=False).mean()

        # VWAP Cumulative Approximation for daily data
        # Typical price = (High + Low + Close) / 3
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        cum_tp_vol = (typical_price * vol).cumsum()
        cum_vol = vol.cumsum().replace(0, np.nan)
        df["vwap"] = cum_tp_vol / cum_vol
        df["vwap"] = df["vwap"].fillna(df["close"])

        # Volume Surge vs 20-day Volume SMA
        vol_sma20 = vol.rolling(window=20, min_periods=3).mean().replace(0, np.nan)
        df["vol_sma20"] = vol_sma20.fillna(vol)
        df["volume_surge"] = np.where(vol_sma20 > 0, vol / vol_sma20, 1.0)

        return df

    @staticmethod
    def detect_support_resistance(df: pd.DataFrame, window: int = 10, tolerance: float = 0.02) -> Dict[str, Any]:
        """Detect key Support and Resistance levels using pivot clustering (Feature 16)."""
        if len(df) < window * 2:
            return {"supports": [], "resistances": [], "nearest_support": 0.0, "nearest_resistance": 0.0}

        highs = df["high"].values
        lows = df["low"].values
        current_price = df["close"].iloc[-1]

        pivot_highs: List[float] = []
        pivot_lows: List[float] = []

        for i in range(window, len(df) - window):
            # Local peak
            if highs[i] == max(highs[i - window: i + window + 1]):
                pivot_highs.append(float(highs[i]))
            # Local trough
            if lows[i] == min(lows[i - window: i + window + 1]):
                pivot_lows.append(float(lows[i]))

        # Cluster pivots within tolerance
        def cluster_levels(levels: List[float]) -> List[Tuple[float, int]]:
            if not levels:
                return []
            levels = sorted(levels)
            clusters: List[Tuple[float, int]] = []
            curr_cluster = [levels[0]]

            for lv in levels[1:]:
                if (lv - curr_cluster[0]) / curr_cluster[0] <= tolerance:
                    curr_cluster.append(lv)
                else:
                    clusters.append((float(np.mean(curr_cluster)), len(curr_cluster)))
                    curr_cluster = [lv]
            if curr_cluster:
                clusters.append((float(np.mean(curr_cluster)), len(curr_cluster)))
            # Sort by touch count (strength) descending
            return sorted(clusters, key=lambda x: x[1], reverse=True)

        res_clusters = cluster_levels(pivot_highs)
        sup_clusters = cluster_levels(pivot_lows)

        # Filter: resistances > current_price, supports < current_price
        resistances = [round(r[0], 2) for r in res_clusters if r[0] > current_price][:5]
        supports = [round(s[0], 2) for s in sup_clusters if s[0] < current_price][:5]

        nearest_res = min(resistances) if resistances else round(current_price * 1.10, 2)
        nearest_sup = max(supports) if supports else round(current_price * 0.90, 2)

        return {
            "supports": supports,
            "resistances": resistances,
            "nearest_support": nearest_sup,
            "nearest_resistance": nearest_res
        }

    @staticmethod
    def recognize_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
        """Identify key candlestick patterns: Hammer, Engulfing, Morning Star, Doji (Feature 17)."""
        df = df.copy()
        if "open" not in df.columns:
            df["open"] = df["close"].shift(1).fillna(df["close"])
        o = df["open"]
        h = df["high"]
        l = df["low"]
        c = df["close"]

        body = (c - o).abs()
        range_tot = (h - l).replace(0, np.nan)
        upper_shadow = h - np.maximum(o, c)
        lower_shadow = np.minimum(o, c) - l

        # Doji: body < 10% of total bar range
        df["pat_doji"] = (body / range_tot) < 0.10

        # Hammer: Bullish candle with long lower shadow (>= 2x body) and tiny upper shadow
        is_bullish_close = c > o
        df["pat_hammer"] = (lower_shadow >= 2.0 * body) & (upper_shadow <= 0.3 * body) & (lower_shadow > 0)

        # Bullish Engulfing: Prior candle red, current candle green completely engulfs prior body
        prior_o = o.shift(1)
        prior_c = c.shift(1)
        prior_red = prior_c < prior_o
        curr_green = c > o
        df["pat_engulfing"] = prior_red & curr_green & (c >= prior_o) & (o <= prior_c)

        # Morning Star: 3-bar pattern (1: long red, 2: small body gap down, 3: strong green closing > 50% into bar 1)
        bar1_red = (c.shift(2) < o.shift(2)) & (body.shift(2) / range_tot.shift(2) > 0.5)
        bar2_star = (body.shift(1) / range_tot.shift(1) < 0.3)
        bar3_green = (c > o) & (c > (o.shift(2) + c.shift(2)) / 2.0)
        df["pat_morning_star"] = bar1_red & bar2_star & bar3_green

        # Bullish Marubozu: Strong conviction full body (body > 85% of total range)
        df["pat_marubozu"] = curr_green & ((body / range_tot) >= 0.85)

        return df

    @staticmethod
    def classify_market_regime(df: pd.DataFrame) -> Dict[str, Any]:
        """Classify current market regime (Feature 18)."""
        if len(df) < 50:
            return {"regime": "Insufficient Data", "color": "#718096", "adx": 0.0, "trend_strength": "Unknown"}

        last = df.iloc[-1]
        c = float(last["close"])
        ema50 = float(last.get("ema_50", c))
        ema200 = float(last.get("ema_200", c))
        adx = float(last.get("adx", 15.0))
        natr = float(last.get("natr", 2.5))
        squeeze = bool(last.get("bb_squeeze", False))

        if adx >= 25:
            if c > ema50 > ema200:
                regime = "Bull Trending (Strong Momentum)"
                color = "#10B981"
                strength = "High Trend"
            elif c < ema50 < ema200:
                regime = "Bear Trending (Downtrend)"
                color = "#EF4444"
                strength = "High Trend"
            else:
                regime = "Transitional Trend"
                color = "#3B82F6"
                strength = "Moderate Trend"
        else:
            if squeeze:
                regime = "Squeeze / Low Volatility Accumulation"
                color = "#8B5CF6"
                strength = "Breakout Imminent"
            elif natr > 4.5:
                regime = "High Volatility Chop"
                color = "#F59E0B"
                strength = "No Direction"
            else:
                regime = "Sideways / Range-bound"
                color = "#6B7280"
                strength = "Low Trend"

        return {
            "regime": regime,
            "color": color,
            "adx": round(adx, 1),
            "trend_strength": strength,
            "natr": round(natr, 2),
            "bb_squeeze": squeeze
        }

    @staticmethod
    def compute_multi_timeframe_alignment(daily_df: pd.DataFrame) -> Dict[str, Any]:
        """Resample daily bars into Weekly & Monthly and determine multi-timeframe trend agreement (Feature 19)."""
        if len(daily_df) < 60:
            return {"alignment": "Neutral", "daily": "Neutral", "weekly": "Neutral", "monthly": "Neutral", "score": 50}

        df = daily_df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.set_index("trade_date")
            elif "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")

        # Resample Weekly
        weekly = df.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()

        # Resample Monthly
        monthly = df.resample("ME").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()

        def get_trend(frame: pd.DataFrame) -> str:
            if len(frame) < 5:
                return "Neutral"
            c = frame["close"]
            ema20 = c.ewm(span=20, adjust=False).mean()
            last_c = float(c.iloc[-1])
            last_ema = float(ema20.iloc[-1])
            if last_c > last_ema * 1.01:
                return "Bullish"
            elif last_c < last_ema * 0.99:
                return "Bearish"
            return "Neutral"

        daily_trend = get_trend(df)
        weekly_trend = get_trend(weekly)
        monthly_trend = get_trend(monthly)

        bull_count = [daily_trend, weekly_trend, monthly_trend].count("Bullish")
        bear_count = [daily_trend, weekly_trend, monthly_trend].count("Bearish")

        if bull_count == 3:
            alignment = "Triple Bullish Alignment (Grade A+)"
            score = 95
        elif bull_count == 2 and bear_count == 0:
            alignment = "Bullish Bias (Daily + Weekly)"
            score = 75
        elif bear_count >= 2:
            alignment = "Bearish Alignment"
            score = 25
        else:
            alignment = "Mixed / Conflicted"
            score = 50

        return {
            "alignment": alignment,
            "daily": daily_trend,
            "weekly": weekly_trend,
            "monthly": monthly_trend,
            "score": score
        }

    @staticmethod
    def check_breakouts(df: pd.DataFrame) -> Dict[str, Any]:
        """Scan for 52-week Highs/Lows and 20-day channel breakouts (Feature 20)."""
        if len(df) < 20:
            return {"is_52w_high": False, "is_52w_low": False, "is_20d_breakout": False, "dist_52w_high_pct": 0.0}

        c = df["close"]
        h = df["high"]
        l = df["low"]
        last_c = float(c.iloc[-1])

        lookback_52w = min(252, len(df))
        high_52w = float(h.iloc[-lookback_52w:].max())
        low_52w = float(l.iloc[-lookback_52w:].min())

        is_52w_high = last_c >= high_52w * 0.995
        is_52w_low = last_c <= low_52w * 1.005

        # 20-day range breakout
        high_20d = float(h.iloc[-21:-1].max()) if len(df) >= 21 else float(h.max())
        is_20d_breakout = last_c > high_20d

        dist_high = round(((last_c - high_52w) / high_52w) * 100.0, 2)
        dist_low = round(((last_c - low_52w) / low_52w) * 100.0, 2)

        return {
            "is_52w_high": is_52w_high,
            "is_52w_low": is_52w_low,
            "is_20d_breakout": is_20d_breakout,
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_52w_high_pct": dist_high,
            "dist_52w_low_pct": dist_low
        }

    @classmethod
    def analyze_full_technical_suite(cls, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Run the comprehensive technical engine and return enriched DataFrame and summary metrics."""
        if df.empty or len(df) < 5:
            return df, {}

        df = cls.compute_moving_averages(df)
        df = cls.compute_rsi(df)
        df = cls.compute_macd(df)
        df = cls.compute_bollinger_bands(df)
        df = cls.compute_atr_and_volatility(df)
        df = cls.compute_stochastic_and_adx(df)
        df = cls.compute_volume_analysis(df)
        df = cls.recognize_candlestick_patterns(df)

        sr_levels = cls.detect_support_resistance(df)
        regime = cls.classify_market_regime(df)
        mtf = cls.compute_multi_timeframe_alignment(df)
        breakout = cls.check_breakouts(df)

        summary = {
            "regime": regime,
            "support_resistance": sr_levels,
            "multi_timeframe": mtf,
            "breakouts": breakout
        }
        return df, summary
