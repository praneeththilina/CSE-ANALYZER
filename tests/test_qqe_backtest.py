import unittest
import numpy as np
import pandas as pd
import qqe_backtest_signals as qbs


class TestQQEBacktest(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        np.random.seed(42)
        closes = np.linspace(100.0, 150.0, 100) + np.random.normal(0, 2, 100)
        highs = closes + np.random.uniform(1.0, 5.0, 100)
        lows = closes - np.random.uniform(1.0, 5.0, 100)
        opens = closes + np.random.uniform(-1.0, 1.0, 100)
        volumes = np.random.randint(1000, 50000, 100)

        self.df = pd.DataFrame(
            {
                "open": opens,
                "close": closes,
                "high": highs,
                "low": lows,
                "volume": volumes,
            },
            index=dates,
        )

    def test_run_full_backtest_structure_and_types(self):
        params = {
            "initial_capital": 100000.0,
            "commission_pct": 0.001,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "rsi_period": 14,
            "sf": 5,
            "qqe_factor": 4.238,
            "threshold": 10,
        }
        res = qbs.run_full_backtest(self.df, params)

        self.assertIn("stats", res)
        self.assertIn("equity_curve", res)
        self.assertIn("trades", res)

        stats = res["stats"]
        expected_stat_keys = [
            "Total Return (%)",
            "Total Trades",
            "Win Rate (%)",
            "Profit Factor",
            "Avg. Win (LKR)",
            "Avg. Loss (LKR)",
            "Max. Drawdown (%)",
            "Final Equity (LKR)",
        ]
        for key in expected_stat_keys:
            self.assertIn(key, stats)

        self.assertIsInstance(res["equity_curve"], pd.DataFrame)
        self.assertIsInstance(res["trades"], pd.DataFrame)
        self.assertGreater(stats["Total Trades"], 0)

    def test_run_full_backtest_no_trades(self):
        # Flat prices will not generate QQE signal threshold triggers
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        flat_df = pd.DataFrame(
            {
                "open": [100.0] * 50,
                "close": [100.0] * 50,
                "high": [100.0] * 50,
                "low": [100.0] * 50,
                "volume": [1000] * 50,
            },
            index=dates,
        )
        res = qbs.run_full_backtest(flat_df, {})

        self.assertIn("stats", res)
        self.assertEqual(res["stats"]["Total Trades"], 0)
        self.assertEqual(res["stats"]["Total Return (%)"], "0.00")
        self.assertTrue(res["trades"].empty)


if __name__ == "__main__":
    unittest.main()
