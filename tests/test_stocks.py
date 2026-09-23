import unittest
import numpy as np
import pandas as pd

from stocks import compute_qqe_from_closes


class TestComputeQQEFromCloses(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        np.random.seed(42)
        # Create price series with trend changes to ensure signals generate
        trend1 = np.linspace(100, 150, 40)
        trend2 = np.linspace(150, 90, 30)
        trend3 = np.linspace(90, 160, 30)
        closes_arr = np.concatenate([trend1, trend2, trend3]) + np.random.normal(0, 1, 100)
        self.closes = pd.Series(closes_arr, index=dates, name="close")

    def test_qqe_happy_path(self):
        df_qqe = compute_qqe_from_closes(self.closes)

        self.assertIsInstance(df_qqe, pd.DataFrame)
        self.assertEqual(len(df_qqe), len(self.closes))
        pd.testing.assert_index_equal(df_qqe.index, self.closes.index)

        expected_columns = [
            "rsi_val", "rsi_ma", "longband", "shortband",
            "fast_tl", "trend", "qqe_long", "qqe_short", "signal"
        ]
        self.assertListEqual(list(df_qqe.columns), expected_columns)

        # Check value bounds / sets
        unique_signals = set(df_qqe["signal"].unique())
        self.assertTrue(unique_signals.issubset({-1, 0, 1}))

        unique_trends = set(df_qqe["trend"].unique())
        self.assertTrue(unique_trends.issubset({-1, 0, 1}))

    def test_qqe_empty_series(self):
        empty_closes = pd.Series([], dtype=float)

        # compute_qqe_from_closes uses start = int(np.argmax(~np.isnan(rs_np)))
        # which raises ValueError on empty series. Verify this behaviour or handle empty inputs.
        with self.assertRaises(ValueError):
            compute_qqe_from_closes(empty_closes)

    def test_qqe_all_nan_series(self):
        nan_closes = pd.Series([np.nan] * 20)
        df_qqe = compute_qqe_from_closes(nan_closes)

        self.assertIsInstance(df_qqe, pd.DataFrame)
        self.assertEqual(len(df_qqe), 20)
        self.assertTrue((df_qqe["signal"] == 0).all())

    def test_qqe_constant_prices(self):
        constant_closes = pd.Series([100.0] * 50)
        df_qqe = compute_qqe_from_closes(constant_closes)

        self.assertIsInstance(df_qqe, pd.DataFrame)
        self.assertEqual(len(df_qqe), 50)
        self.assertFalse(df_qqe["rsi_val"].isna().all())

    def test_qqe_custom_parameters(self):
        df_custom = compute_qqe_from_closes(
            self.closes,
            rsi_period=10,
            sf=3,
            qqe_factor=3.0,
            threshold=5
        )
        self.assertIsInstance(df_custom, pd.DataFrame)
        self.assertEqual(len(df_custom), len(self.closes))

    def test_qqe_threshold_none(self):
        df_none_thresh = compute_qqe_from_closes(
            self.closes,
            threshold=None
        )
        self.assertIsInstance(df_none_thresh, pd.DataFrame)
        self.assertEqual(len(df_none_thresh), len(self.closes))

    def test_qqe_signal_generation(self):
        df_qqe = compute_qqe_from_closes(self.closes, rsi_period=14, sf=5, threshold=5)
        self.assertIn("signal", df_qqe.columns)
        self.assertTrue((df_qqe["signal"].isin([-1, 0, 1])).all())


if __name__ == "__main__":
    unittest.main()
