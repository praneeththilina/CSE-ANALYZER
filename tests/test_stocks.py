import unittest
import numpy as np
import pandas as pd
from stocks import ema


class TestStocksEMA(unittest.TestCase):
    def test_ema_constant_series(self):
        """EMA of a constant series should be equal to the constant value."""
        s = pd.Series([10.0, 10.0, 10.0, 10.0, 10.0])
        result = ema(s, length=3)
        pd.testing.assert_series_equal(result, s)

    def test_ema_calculation(self):
        """Verify EMA calculation against standard formula with adjust=False."""
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        length = 3
        # alpha = 2 / (3 + 1) = 0.5
        # EMA_0 = 10.0
        # EMA_1 = 0.5 * 20.0 + 0.5 * 10.0 = 15.0
        # EMA_2 = 0.5 * 30.0 + 0.5 * 15.0 = 22.5
        # EMA_3 = 0.5 * 40.0 + 0.5 * 22.5 = 31.25
        # EMA_4 = 0.5 * 50.0 + 0.5 * 31.25 = 40.625
        expected = pd.Series([10.0, 15.0, 22.5, 31.25, 40.625])
        result = ema(s, length=length)
        pd.testing.assert_series_equal(result, expected)

    def test_ema_length_one(self):
        """When length=1, alpha=1.0, EMA should equal the original series."""
        s = pd.Series([10.0, 25.0, 15.0, 30.0])
        result = ema(s, length=1)
        pd.testing.assert_series_equal(result, s)

    def test_ema_empty_series(self):
        """EMA of an empty series should return an empty series."""
        s = pd.Series([], dtype=float)
        result = ema(s, length=5)
        self.assertTrue(result.empty)

    def test_ema_single_element(self):
        """EMA of a single element series should return that element."""
        s = pd.Series([42.5])
        result = ema(s, length=10)
        expected = pd.Series([42.5])
        pd.testing.assert_series_equal(result, expected)

    def test_ema_with_nan_values(self):
        """Check behavior when series contains leading or middle NaN values."""
        # Leading NaNs produce NaNs until first valid value
        s_leading = pd.Series([np.nan, 10.0, 20.0])
        result_leading = ema(s_leading, length=3)
        expected_leading = pd.Series([np.nan, 10.0, 15.0])
        pd.testing.assert_series_equal(result_leading, expected_leading)

        # Middle NaNs carry forward prior EMA value
        s_middle = pd.Series([10.0, np.nan, 20.0, 30.0])
        result_middle = ema(s_middle, length=3)
        expected_middle = pd.Series([10.0, 10.0, 17.5, 23.75])
        pd.testing.assert_series_equal(result_middle, expected_middle)

    def test_ema_custom_index(self):
        """Ensure index and name are preserved in output series."""
        dates = pd.date_range("2023-01-01", periods=4, freq="D")
        s = pd.Series([100.0, 102.0, 104.0, 108.0], index=dates, name="close")
        result = ema(s, length=2)
        pd.testing.assert_series_equal(result.index.to_series(), dates.to_series())
        self.assertEqual(result.name, "close")

    def test_ema_negative_and_float_values(self):
        """Verify EMA calculation with negative floats."""
        s = pd.Series([-10.0, -5.0, 0.0, 5.0])
        length = 3
        # alpha = 0.5
        # EMA_0 = -10.0
        # EMA_1 = 0.5 * (-5.0) + 0.5 * (-10.0) = -7.5
        # EMA_2 = 0.5 * (0.0) + 0.5 * (-7.5) = -3.75
        # EMA_3 = 0.5 * (5.0) + 0.5 * (-3.75) = 0.625
        expected = pd.Series([-10.0, -7.5, -3.75, 0.625])
        result = ema(s, length=length)
        pd.testing.assert_series_equal(result, expected)


if __name__ == "__main__":
    unittest.main()
