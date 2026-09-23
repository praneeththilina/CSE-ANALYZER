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
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        np.random.seed(42)
        closes = np.linspace(100.0, 150.0, 100) + np.random.normal(0, 2, 100)
        highs = closes + np.random.uniform(1.0, 5.0, 100)
        lows = closes - np.random.uniform(1.0, 5.0, 100)
        volumes = np.random.randint(1000, 50000, 100)

        self.df = pd.DataFrame({
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

    def test_compute_piotroski_f_score(self):
        # 1. Test Perfect Score (9/9)
        perfect_data = {
            "net_income": 1000.0,
            "operating_cash_flow": 1200.0,
            "roa": 10.0,
            "roa_prior": 8.0,
            "debt_to_equity": 0.5,
            "debt_to_equity_prior": 0.6,
            "current_ratio": 2.0,
            "current_ratio_prior": 1.5,
            "shares_out": 100,
            "shares_out_prior": 100,
            "gross_margin": 30.0,
            "gross_margin_prior": 28.0,
            "asset_turnover": 1.2,
            "asset_turnover_prior": 1.0,
        }
        res_perfect = FundamentalEngine.compute_piotroski_f_score(perfect_data)
        self.assertEqual(res_perfect["f_score"], 9)
        self.assertEqual(res_perfect["max_score"], 9)
        self.assertEqual(res_perfect["rating"], "Strong (Piotroski 7-9)")
        self.assertEqual(res_perfect["color"], "#10B981")
        self.assertEqual(len(res_perfect["breakdown"]), 9)

        # 2. Test Zero Score (0/9)
        zero_data = {
            "net_income": -500.0,
            "operating_cash_flow": -600.0,
            "roa": -2.0,
            "roa_prior": -1.0,
            "debt_to_equity": 1.2,
            "debt_to_equity_prior": 1.0,
            "current_ratio": 1.1,
            "current_ratio_prior": 1.5,
            "shares_out": 120,
            "shares_out_prior": 100,
            "gross_margin": 15.0,
            "gross_margin_prior": 20.0,
            "asset_turnover": 0.5,
            "asset_turnover_prior": 0.6,
        }
        res_zero = FundamentalEngine.compute_piotroski_f_score(zero_data)
        self.assertEqual(res_zero["f_score"], 0)
        self.assertEqual(res_zero["rating"], "Weak (Piotroski 0-3)")
        self.assertEqual(res_zero["color"], "#EF4444")

        # 3. Test Moderate Score (Moderate rating 4-6)
        moderate_data = dict(perfect_data)
        moderate_data.update({
            "net_income": -100.0,          # Loss (-1)
            "operating_cash_flow": -50.0, # Negative CFO (-1)
            "roa": -1.0,                   # Negative ROA (-1)
            "gross_margin": 25.0,          # Compressed GM vs 28.0 (-1)
        })
        res_moderate = FundamentalEngine.compute_piotroski_f_score(moderate_data)
        self.assertEqual(res_moderate["f_score"], 5)
        self.assertEqual(res_moderate["rating"], "Moderate (Piotroski 4-6)")
        self.assertEqual(res_moderate["color"], "#F59E0B")

        # 4. Test Empty Data / Default Fallbacks
        res_empty = FundamentalEngine.compute_piotroski_f_score({})
        self.assertIn("f_score", res_empty)
        self.assertIn("rating", res_empty)
        self.assertIn("breakdown", res_empty)
        self.assertEqual(len(res_empty["breakdown"]), 9)

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

    def test_compute_benchmark_relative_strength_edge_cases(self):
        # 1. Empty dataframe
        empty_df = pd.DataFrame()
        res_empty = MarketContextEngine.compute_benchmark_relative_strength(empty_df)
        self.assertEqual(res_empty["beta"], 1.0)
        self.assertEqual(res_empty["verdict"], "Neutral")

        # 2. Short dataframe (< 20 rows)
        short_df = pd.DataFrame({"close": [10.0] * 10})
        res_short = MarketContextEngine.compute_benchmark_relative_strength(short_df)
        self.assertEqual(res_short["beta"], 1.0)
        self.assertEqual(res_short["verdict"], "Neutral")

        # 3. Aligned length < 15 rows
        # stock_df has 20 rows, but NaNs cause aligned return series to have < 15 rows.
        dates_20 = pd.date_range("2023-01-01", periods=20, freq="D")
        aspi_20 = pd.DataFrame({"close": np.linspace(100.0, 110.0, 20)}, index=dates_20)
        stock_20 = pd.DataFrame({"close": [10.0] * 10 + [np.nan] * 10}, index=dates_20)
        res_aligned_short = MarketContextEngine.compute_benchmark_relative_strength(stock_20, aspi_20)
        self.assertEqual(res_aligned_short["beta"], 1.0)
        self.assertEqual(res_aligned_short["verdict"], "Neutral")

        # 4. Standard case with aspi_df = None (synthesized benchmark)
        res_synthesized = MarketContextEngine.compute_benchmark_relative_strength(self.df, aspi_df=None)
        self.assertIn("beta", res_synthesized)
        self.assertIn("alpha", res_synthesized)
        self.assertIn("rs_momentum_20d_pct", res_synthesized)
        self.assertIn("verdict", res_synthesized)

        # 5. Provided valid aspi_df with strong outperformance vs underperformance
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        # Stock surging upwards
        stock_outperform = pd.DataFrame({"close": np.linspace(100.0, 200.0, 100)}, index=dates)
        # ASPI remaining flat/decreasing
        aspi_flat = pd.DataFrame({"close": np.linspace(100.0, 100.0, 100)}, index=dates)
        res_strong = MarketContextEngine.compute_benchmark_relative_strength(stock_outperform, aspi_flat)
        self.assertTrue(res_strong["outperforming_aspi"])
        self.assertEqual(res_strong["verdict"], "Strong Outperformer vs ASPI")

        # Underperforming stock
        stock_underperform = pd.DataFrame({"close": np.linspace(200.0, 100.0, 100)}, index=dates)
        res_weak = MarketContextEngine.compute_benchmark_relative_strength(stock_underperform, aspi_flat)
        self.assertFalse(res_weak["outperforming_aspi"])
        self.assertEqual(res_weak["verdict"], "Underperforming ASPI")

        # Mild outperformer (+2% RS momentum)
        stock_mild = pd.DataFrame({"close": np.linspace(100.0, 102.0, 100)}, index=dates)
        res_mild = MarketContextEngine.compute_benchmark_relative_strength(stock_mild, aspi_flat)
        self.assertTrue(res_mild["outperforming_aspi"])
        self.assertEqual(res_mild["verdict"], "Mild Outperformer")

        # In-Line with market (-2% RS momentum)
        stock_inline = pd.DataFrame({"close": np.linspace(100.0, 98.0, 100)}, index=dates)
        res_inline = MarketContextEngine.compute_benchmark_relative_strength(stock_inline, aspi_flat)
        self.assertFalse(res_inline["outperforming_aspi"])
        self.assertEqual(res_inline["verdict"], "In-Line with Market")

        # 6. Zero variance benchmark returns (var_m <= 1e-8) -> Beta defaults to 1.0
        # Constant ASPI price gives 0 return variance
        res_zero_var = MarketContextEngine.compute_benchmark_relative_strength(self.df, aspi_flat)
        self.assertEqual(res_zero_var["beta"], 1.0)

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

    def test_compute_52w_extremes(self):
        # 1. Empty DataFrame and DataFrame with < 10 rows
        empty_df = pd.DataFrame(columns=["close", "high", "low"])
        default_res = DataEngine.compute_52w_extremes(empty_df)
        self.assertEqual(default_res["high_52w"], 0.0)
        self.assertEqual(default_res["low_52w"], 0.0)
        self.assertEqual(default_res["dist_high_pct"], 0.0)
        self.assertEqual(default_res["dist_low_pct"], 0.0)
        self.assertFalse(default_res["near_breakout"])
        self.assertEqual(default_res["dist_high_str"], "0.0%")

        small_df = pd.DataFrame({
            "close": [10.0] * 5,
            "high": [12.0] * 5,
            "low": [8.0] * 5
        })
        self.assertEqual(DataEngine.compute_52w_extremes(small_df), default_res)

        # 2. Standard DataFrame with >= 10 rows (not near breakout)
        df_standard = pd.DataFrame({
            "close": [100.0] * 10 + [120.0],
            "high": [150.0] * 10 + [125.0],
            "low": [80.0] * 10 + [110.0]
        })
        res_std = DataEngine.compute_52w_extremes(df_standard)
        self.assertEqual(res_std["high_52w"], 150.0)
        self.assertEqual(res_std["low_52w"], 80.0)
        # close=120, high_52w=150 -> (120-150)/150 * 100 = -20.0%
        self.assertEqual(res_std["dist_high_pct"], -20.0)
        # close=120, low_52w=80 -> (120-80)/80 * 100 = 50.0%
        self.assertEqual(res_std["dist_low_pct"], 50.0)
        self.assertFalse(res_std["near_breakout"])
        self.assertEqual(res_std["dist_high_str"], "-20.0%")

        # 3. Near breakout condition (dist_high_pct >= -5.0%)
        df_breakout = pd.DataFrame({
            "close": [100.0] * 10 + [147.0],
            "high": [150.0] * 10 + [148.0],
            "low": [80.0] * 10 + [140.0]
        })
        res_breakout = DataEngine.compute_52w_extremes(df_breakout)
        # close=147, high_52w=150 -> (147-150)/150 * 100 = -2.0%
        self.assertEqual(res_breakout["dist_high_pct"], -2.0)
        self.assertTrue(res_breakout["near_breakout"])
        self.assertIn("🔥", res_breakout["dist_high_str"])
        self.assertEqual(res_breakout["dist_high_str"], "-2.0% 🔥")

        # 4. Windowing test: > 250 rows (sub = df.tail(250))
        dates = pd.date_range("2020-01-01", periods=300, freq="D")
        highs = [200.0] * 50 + [150.0] * 250
        lows = [50.0] * 50 + [80.0] * 250
        closes = [100.0] * 50 + [120.0] * 250
        df_long = pd.DataFrame({"close": closes, "high": highs, "low": lows}, index=dates)

        res_long = DataEngine.compute_52w_extremes(df_long)
        # Old high 200.0 was in the first 50 rows, so tail(250) high should be 150.0
        self.assertEqual(res_long["high_52w"], 150.0)
        self.assertEqual(res_long["low_52w"], 80.0)

        # 5. Zero high edge case
        df_zero = pd.DataFrame({
            "close": [0.0] * 10,
            "high": [0.0] * 10,
            "low": [0.0] * 10
        })
        res_zero = DataEngine.compute_52w_extremes(df_zero)
        self.assertEqual(res_zero["high_52w"], 0.0)
        self.assertEqual(res_zero["dist_high_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
