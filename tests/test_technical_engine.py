import unittest
import pandas as pd
import numpy as np
from core.technical_engine import TechnicalEngine


class TestTechnicalEngineUnit(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        close = 100.0 + np.cumsum(np.random.randn(100))
        high = close + np.random.rand(100) * 2.0
        low = close - np.random.rand(100) * 2.0
        open_p = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1000, 50000, size=100)

        self.df = pd.DataFrame({
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume
        }, index=dates)

    def test_compute_moving_averages(self):
        res = TechnicalEngine.compute_moving_averages(self.df)
        self.assertIn("sma_20", res.columns)
        self.assertIn("ema_50", res.columns)
        self.assertIn("golden_cross", res.columns)

    def test_compute_rsi(self):
        res = TechnicalEngine.compute_rsi(self.df)
        self.assertIn("rsi", res.columns)
        self.assertIn("rsi_bull_div", res.columns)
        self.assertTrue((res["rsi"] >= 0).all() and (res["rsi"] <= 100).all())

    def test_compute_rsi_flat_prices(self):
        flat_df = self.df.copy()
        flat_df["close"] = 100.0
        res = TechnicalEngine.compute_rsi(flat_df)
        self.assertEqual(res["rsi"].iloc[-1], 50.0)

    def test_compute_macd(self):
        res = TechnicalEngine.compute_macd(self.df)
        self.assertIn("macd_line", res.columns)
        self.assertIn("macd_signal", res.columns)
        self.assertIn("macd_hist", res.columns)

    def test_compute_bollinger_bands(self):
        res = TechnicalEngine.compute_bollinger_bands(self.df)
        self.assertIn("bb_upper", res.columns)
        self.assertIn("bb_lower", res.columns)
        self.assertIn("bb_squeeze", res.columns)

    def test_compute_atr_and_volatility(self):
        res = TechnicalEngine.compute_atr_and_volatility(self.df)
        self.assertIn("atr", res.columns)
        self.assertIn("natr", res.columns)
        self.assertIn("hv_20", res.columns)

    def test_compute_stochastic_and_adx(self):
        res = TechnicalEngine.compute_stochastic_and_adx(self.df)
        self.assertIn("stoch_k", res.columns)
        self.assertIn("adx", res.columns)

    def test_compute_volume_analysis(self):
        res = TechnicalEngine.compute_volume_analysis(self.df)
        self.assertIn("obv", res.columns)
        self.assertIn("vwap", res.columns)
        self.assertIn("volume_surge", res.columns)

    def test_detect_support_resistance(self):
        res = TechnicalEngine.detect_support_resistance(self.df, window=5)
        self.assertIn("supports", res)
        self.assertIn("resistances", res)

    def test_recognize_candlestick_patterns(self):
        res = TechnicalEngine.recognize_candlestick_patterns(self.df)
        self.assertIn("pat_doji", res.columns)
        self.assertIn("pat_hammer", res.columns)
        self.assertIn("pat_engulfing", res.columns)

    def test_classify_market_regime(self):
        df_full = TechnicalEngine.compute_moving_averages(self.df)
        df_full = TechnicalEngine.compute_atr_and_volatility(df_full)
        df_full = TechnicalEngine.compute_stochastic_and_adx(df_full)
        df_full = TechnicalEngine.compute_bollinger_bands(df_full)
        regime = TechnicalEngine.classify_market_regime(df_full)
        self.assertIn("regime", regime)
        self.assertIn("color", regime)

    def test_compute_pivot_points(self):
        pivots_std = TechnicalEngine.compute_pivot_points(self.df, method="standard")
        pivots_fib = TechnicalEngine.compute_pivot_points(self.df, method="fibonacci")
        pivots_cam = TechnicalEngine.compute_pivot_points(self.df, method="camarilla")
        self.assertIn("P", pivots_std)
        self.assertIn("R1", pivots_fib)
        self.assertIn("S1", pivots_cam)

    def test_check_breakouts(self):
        res = TechnicalEngine.check_breakouts(self.df)
        self.assertIn("is_52w_high", res)
        self.assertIn("is_20d_breakout", res)

    def test_analyze_full_technical_suite(self):
        res_df, summary = TechnicalEngine.analyze_full_technical_suite(self.df)
        self.assertFalse(res_df.empty)
        self.assertIn("regime", summary)
        self.assertIn("support_resistance", summary)


if __name__ == "__main__":
    unittest.main()
