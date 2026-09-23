import unittest
import numpy as np
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path

from core.technical_engine import TechnicalEngine
from core.fundamental_engine import FundamentalEngine
from core.backtest_engine import BacktestEngine
from core.risk_scorecard_engine import RiskScorecardEngine
from core.ml_engine import MLEngine
from core.market_context_engine import MarketContextEngine
from core.data_engine import DataEngine
import qqe_backtest_signals as qbs


class TestCoreEngines(unittest.TestCase):
    def test_load_bars_full(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        conn.execute("INSERT INTO bars VALUES ('TEST.N0000', '2023-01-01', 100.0, 105.0, 95.0, 1000)")
        conn.execute("INSERT INTO bars VALUES ('TEST.N0000', '2023-01-02', 102.0, 107.0, 99.0, 1500)")
        conn.commit()

        # Test loading bars when data exists
        df = qbs.load_bars_full(conn, "TEST.N0000")
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ["close", "high", "low", "volume", "open"])
        # First bar open synthesized from close
        self.assertEqual(df.iloc[0]["open"], 100.0)
        # Second bar open synthesized from previous close
        self.assertEqual(df.iloc[1]["open"], 100.0)
        self.assertEqual(df.iloc[1]["close"], 102.0)

        # Test loading bars when symbol is empty
        df_empty = qbs.load_bars_full(conn, "EMPTY.N0000")
        self.assertTrue(df_empty.empty)
        self.assertListEqual(list(df_empty.columns), ["open", "high", "low", "close", "volume"])

        conn.close()

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp_db.name

        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE symbols (symbol TEXT PRIMARY KEY, industry TEXT, enabled INTEGER)")
        conn.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        conn.commit()
        conn.close()

        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        np.random.seed(42)
        closes = np.linspace(100.0, 150.0, 100) + np.random.normal(0, 2, 100)
        highs = closes + np.random.uniform(1.0, 5.0, 100)
        lows = closes - np.random.uniform(1.0, 5.0, 100)
        volumes = np.random.randint(1000, 50000, 100)
        opens = closes.copy()
        opens[1:] = closes[:-1]

        self.df = pd.DataFrame({
            "open": opens,
            "close": closes,
            "high": highs,
            "low": lows,
            "volume": volumes,
            "trade_date": dates
        }, index=dates)

    def test_technical_engine(self):
        df_res, summary = TechnicalEngine.analyze_full_technical_suite(self.df)
        self.assertIn("ema_50", df_res.columns)
        self.assertIn("rsi", df_res.columns)
        self.assertIn("macd_line", df_res.columns)
        self.assertIn("bb_upper", df_res.columns)
        self.assertIn("atr", df_res.columns)
        self.assertIn("stoch_k", df_res.columns)
        self.assertIn("obv", df_res.columns)
        self.assertIn("ichimoku_tenkan", df_res.columns)
        self.assertIn("ichimoku_kijun", df_res.columns)
        self.assertIn("ichimoku_span_a", df_res.columns)
        self.assertIn("ichimoku_span_b", df_res.columns)
        self.assertIn("pat_hammer", df_res.columns)
        self.assertIn("regime", summary)
        self.assertIn("support_resistance", summary)
        self.assertIn("pivot_points", summary)

    def test_ichimoku_cloud(self):
        df_ich = TechnicalEngine.compute_ichimoku_cloud(self.df)
        self.assertIn("ichimoku_tenkan", df_ich.columns)
        self.assertIn("ichimoku_kijun", df_ich.columns)
        self.assertIn("ichimoku_span_a", df_ich.columns)
        self.assertIn("ichimoku_span_b", df_ich.columns)
        self.assertIn("ichimoku_chikou", df_ich.columns)

    def test_pivot_points(self):
        pivots_std = TechnicalEngine.compute_pivot_points(self.df, method="standard")
        self.assertIn("P", pivots_std)
        self.assertIn("R1", pivots_std)
        self.assertIn("S1", pivots_std)

        pivots_fib = TechnicalEngine.compute_pivot_points(self.df, method="fibonacci")
        self.assertIn("P", pivots_fib)

        pivots_cam = TechnicalEngine.compute_pivot_points(self.df, method="camarilla")
        self.assertIn("R3", pivots_cam)

    def test_fundamental_engine(self):
        profile = FundamentalEngine.generate_fundamental_profile(
            symbol="COMB.N0000",
            name="Commercial Bank",
            industry="Banking",
            current_price=120.0
        )
        self.assertEqual(profile["symbol"], "COMB.N0000")
        self.assertIsNotNone(profile["graham_number"])
        self.assertIsNotNone(profile["dcf_value"])
        self.assertIn("f_score", profile["piotroski"])
        self.assertIn("z_score", profile["altman_z"])

    def test_backtest_engine(self):
        res = BacktestEngine.run_spot_backtest(self.df, starting_capital=1_000_000.0, strategy_mode="QQE / Momentum")
        self.assertIn("return_pct", res)
        self.assertIn("total_trades", res)
        self.assertIn("win_rate_pct", res)
        self.assertIn("equity_curve", res)

        res_ma = BacktestEngine.run_spot_backtest(self.df, starting_capital=1_000_000.0, strategy_mode="Dual MA Crossover")
        self.assertIn("return_pct", res_ma)

        res_rsi = BacktestEngine.run_spot_backtest(self.df, starting_capital=1_000_000.0, strategy_mode="RSI Mean Reversion")
        self.assertIn("return_pct", res_rsi)

        opt_res = BacktestEngine.optimize_strategy_parameters(self.df)
        self.assertIsInstance(opt_res, list)
        if opt_res:
            self.assertIn("target1_rr", opt_res[0])
            self.assertIn("sharpe_ratio", opt_res[0])

        wf_res = BacktestEngine.run_walk_forward_validation(self.df, window_size=50, out_of_sample_size=20)
        self.assertIn("folds", wf_res)
        self.assertIn("avg_out_of_sample_return_pct", wf_res)

    def test_risk_scorecard_engine(self):
        df_res, tech_summary = TechnicalEngine.analyze_full_technical_suite(self.df)
        fund = FundamentalEngine.generate_fundamental_profile("COMB.N0000", "Commercial Bank", "Banking", 120.0)
        mkt = MarketContextEngine.compute_benchmark_relative_strength(self.df)
        features = MLEngine.extract_feature_vector(self.df, fundamental_profile=fund, market_context=mkt)
        ml_pred = MLEngine.predict_calibrated_outperformance(features)

        scorecard = RiskScorecardEngine.generate_composite_scorecard(
            symbol="COMB.N0000",
            name="Commercial Bank",
            current_price=120.0,
            technical_summary=tech_summary,
            fundamental_profile=fund,
            market_context=mkt,
            ml_prediction=ml_pred
        )
        self.assertIn("decision", scorecard)
        self.assertIn("calibrated_win_prob_pct", scorecard)

        pos_size = RiskScorecardEngine.calculate_position_size(
            account_capital=1_000_000.0,
            entry_price=120.0,
            stop_loss_price=110.0
        )
        self.assertIn("shares_to_buy", pos_size)
        self.assertGreater(pos_size["shares_to_buy"], 0)

        risk_res = RiskScorecardEngine.evaluate_portfolio_risk(
            holdings=[{"symbol": "COMB.N0000", "current_price": 120.0, "qty": 1000, "pnl": 10000, "cost_basis": 110000}],
            portfolio_cash=50000.0,
            benchmark_aspi_return_pct=12.0
        )
        self.assertIn("portfolio_alpha_pct", risk_res)

    def test_portfolio_rebalancing(self):
        holdings = [
            {"symbol": "COMB.N0000", "current_price": 100.0, "quantity": 1000, "current_value": 100000.0},
            {"symbol": "JKH.N0000", "current_price": 200.0, "quantity": 1000, "current_value": 200000.0}
        ]
        res = RiskScorecardEngine.calculate_portfolio_rebalance(
            holdings=holdings,
            target_mode="EQUAL_WEIGHT",
            portfolio_cash=0.0
        )
        self.assertEqual(res["total_portfolio_value"], 300000.0)
        self.assertEqual(len(res["rebalance_trades"]), 2)

        # COMB should be target 150k (BUY 500 shares), JKH target 150k (SELL 250 shares)
        comb_trade = next(t for t in res["rebalance_trades"] if t["symbol"] == "COMB.N0000")
        jkh_trade = next(t for t in res["rebalance_trades"] if t["symbol"] == "JKH.N0000")
        self.assertEqual(comb_trade["action"], "BUY")
        self.assertEqual(jkh_trade["action"], "SELL")

    def test_watchlist_expiry_and_frequency(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE symbols (symbol TEXT PRIMARY KEY, industry TEXT, enabled INTEGER)")
        conn.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        conn.execute("INSERT INTO symbols VALUES ('COMB.N0000', 'Banking', 1)")
        conn.execute("INSERT INTO bars VALUES ('COMB.N0000', '2023-01-01', 120.0, 125.0, 115.0, 10000)")
        conn.commit()
        conn.close()

        engine = DataEngine(db_path=db_path)
        engine.add_to_watchlist("TestList", "COMB.N0000", alert_high=115.0, alert_frequency="ONCE", expiry_days=30)

        items = engine.get_watchlist_items("TestList")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["alert_frequency"], "ONCE")

        # Check alert trigger
        alerts = engine.check_watchlist_alerts("TestList")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["symbol"], "COMB.N0000")

        # Second check should suppress trigger because frequency is ONCE
        alerts_2nd = engine.check_watchlist_alerts("TestList")
        self.assertEqual(len(alerts_2nd), 0)

    def test_ml_engine(self):
        fund = FundamentalEngine.generate_fundamental_profile("COMB.N0000", "Commercial Bank", "Banking", 120.0)
        mkt = MarketContextEngine.compute_benchmark_relative_strength(self.df)
        features = MLEngine.extract_feature_vector(self.df, fundamental_profile=fund, market_context=mkt)
        self.assertIn("rsi", features)

        pred = MLEngine.predict_calibrated_outperformance(features)
        self.assertIn("calibrated_prob_pct", pred)
        self.assertIn("confidence_tier", pred)

    def test_market_context_engine(self):
        rs = MarketContextEngine.compute_benchmark_relative_strength(self.df)
        self.assertIn("rs_momentum_20d_pct", rs)

        liq = MarketContextEngine.compute_liquidity_and_days_to_exit(self.df)
        self.assertIn("liquidity_tier", liq)

        cb = MarketContextEngine.check_circuit_breakers_and_bands(120.0, 115.0)
        self.assertIn("upper_circuit_limit", cb)

    def test_data_engine(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE symbols (symbol TEXT PRIMARY KEY, industry TEXT, enabled INTEGER)")
        conn.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        conn.execute("CREATE TABLE signals (date TEXT, symbol TEXT, signal INTEGER)")
        conn.execute("INSERT INTO symbols VALUES ('COMB.N0000', 'Banking', 1)")
        for _, row in self.df.iterrows():
            conn.execute(
                "INSERT INTO bars VALUES ('COMB.N0000', ?, ?, ?, ?, ?)",
                (str(row["trade_date"])[:10], row["close"], row["high"], row["low"], row["volume"])
            )
        conn.commit()
        conn.close()

        engine = DataEngine(db_path=db_path)
        symbols = engine.get_all_symbols()
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0]["symbol"], "COMB.N0000")

        bars = engine.get_bars("COMB.N0000")
        self.assertFalse(bars.empty)
        self.assertIn("close", bars.columns)

    def test_compute_spot_signals_insufficient_data(self):
        engine = DataEngine(db_path=self.db_path)
        # Test empty dataframe
        res_empty = engine.compute_spot_signals(pd.DataFrame())
        self.assertEqual(res_empty["action"], "HOLD")
        self.assertEqual(res_empty["setup_type"], "Insufficient Data")
        self.assertFalse(res_empty["is_buy"])
        self.assertFalse(res_empty["is_exit"])
        self.assertEqual(res_empty["current_price"], 0.0)

        # Test dataframe with less than 25 bars
        short_df = self.df.iloc[:20]
        res_short = engine.compute_spot_signals(short_df)
        self.assertEqual(res_short["action"], "HOLD")
        self.assertEqual(res_short["setup_type"], "Insufficient Data")

    def test_compute_spot_signals_hold_and_structure(self):
        engine = DataEngine(db_path=self.db_path)
        res = engine.compute_spot_signals(self.df)
        expected_keys = [
            "action", "setup_type", "signal_text", "is_buy", "is_exit", "is_hold",
            "current_price", "entry_price", "target1", "target2", "stop_loss",
            "trailing_stop", "risk_unit", "score", "grade", "stars", "trend",
            "vol_ratio", "divergence", "weekly_trend", "pattern", "dist_52w",
            "near_breakout", "reason", "date", "atr", "support", "resistance"
        ]
        for key in expected_keys:
            self.assertIn(key, res)
        self.assertIsInstance(res["is_buy"], bool)
        self.assertIsInstance(res["is_exit"], bool)
        self.assertIsInstance(res["is_hold"], bool)

    def test_compute_spot_signals_breakout_buy(self):
        engine = DataEngine(db_path=self.db_path)
        df = self.df.copy()
        df["volume"] = df["volume"].astype(float)
        # Force breakout on last bar: close and high strictly above 20-day high with volume surge
        high_20d = float(df["high"].iloc[:-1].tail(20).max())
        df.iloc[-1, df.columns.get_loc("close")] = high_20d + 10.0
        df.iloc[-1, df.columns.get_loc("high")] = high_20d + 12.0
        df.iloc[-1, df.columns.get_loc("open")] = high_20d + 8.0
        df.iloc[-1, df.columns.get_loc("volume")] = float(df["volume"].mean() * 3.0)

        res = engine.compute_spot_signals(df)
        self.assertEqual(res["action"], "BUY")
        self.assertTrue(res["is_buy"])
        self.assertIn("Breakout BUY", res["setup_type"])

    def test_compute_spot_signals_pullback_buy(self):
        engine = DataEngine(db_path=self.db_path)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        closes = np.linspace(50.0, 150.0, 100)
        highs = closes + 2.0
        lows = closes - 2.0
        vols = np.full(100, 10000.0)
        opens = closes - 1.0

        df = pd.DataFrame({"open": opens, "close": closes, "high": highs, "low": lows, "volume": vols}, index=dates)

        ema50 = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1])
        df.iloc[-1, df.columns.get_loc("close")] = ema50 + 0.1
        df.iloc[-1, df.columns.get_loc("open")] = ema50 - 0.5
        df.iloc[-1, df.columns.get_loc("high")] = ema50 + 1.0
        df.iloc[-1, df.columns.get_loc("low")] = ema50 - 1.0

        res = engine.compute_spot_signals(df)
        self.assertEqual(res["action"], "BUY")
        self.assertTrue(res["is_buy"])
        self.assertIn("Pullback BUY", res["setup_type"])

    def test_compute_spot_signals_golden_cross_buy(self):
        engine = DataEngine(db_path=self.db_path)
        dates = pd.date_range("2023-01-01", periods=80, freq="D")
        closes = np.concatenate([np.linspace(150.0, 100.0, 75), np.linspace(101.0, 140.0, 5)])
        highs = closes + 2.0
        lows = closes - 2.0
        vols = np.full(80, 10000.0)
        opens = closes - 1.0

        df = pd.DataFrame({"open": opens, "close": closes, "high": highs, "low": lows, "volume": vols}, index=dates)

        res = engine.compute_spot_signals(df)
        self.assertIn(res["action"], ["BUY", "HOLD", "EXIT"])
        self.assertIn("action", res)

    def test_compute_spot_signals_trend_breakdown_exit(self):
        engine = DataEngine(db_path=self.db_path)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")
        closes = np.linspace(100.0, 120.0, 60)
        highs = closes + 1.0
        lows = closes - 1.0
        vols = np.full(60, 1000.0)
        opens = closes - 0.5

        df = pd.DataFrame({"open": opens, "close": closes, "high": highs, "low": lows, "volume": vols}, index=dates)

        df.iloc[-1, df.columns.get_loc("close")] = 80.0
        df.iloc[-1, df.columns.get_loc("high")] = 81.0
        df.iloc[-1, df.columns.get_loc("low")] = 79.0
        df.iloc[-1, df.columns.get_loc("volume")] = 5000.0

        res = engine.compute_spot_signals(df)
        self.assertEqual(res["action"], "EXIT")
        self.assertTrue(res["is_exit"])
        self.assertIn("Trend Breakdown", res["setup_type"])


if __name__ == "__main__":
    unittest.main()
