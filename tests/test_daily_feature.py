import unittest
import tempfile
import sqlite3
import datetime
import tkinter as tk
from tkinter import ttk

import pandas as pd
import numpy as np

from core.data_engine import DataEngine
from views.dashboard import DashboardTab


class MockMainApp:
    def __init__(self, engine):
        self.engine = engine
        self.root = None

    def switch_to_chart(self, symbol, entry=None, stop_loss=None):
        self.switched_chart = symbol

    def switch_to_watchlist(self, symbol=None):
        self.switched_watchlist = symbol

    def switch_to_portfolio(self, symbol, price, qty):
        self.switched_portfolio = (symbol, price, qty)

    def switch_to_intel(self, symbol=None):
        self.switched_intel = symbol

    def set_status(self, msg):
        self.status = msg

    def start_progress(self):
        pass

    def stop_progress(self):
        pass


class TestDailyFeature(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp_db.name

        # Create test DB schema
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE symbols (symbol TEXT PRIMARY KEY, industry TEXT, enabled INTEGER)")
        conn.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        conn.execute("CREATE TABLE signals (date TEXT, symbol TEXT, signal INTEGER)")

        # Populate sample bars for 2 symbols
        dates = [f"2023-01-{i:02d}" for i in range(1, 35)]
        for sym in ["COMB.N0000", "JKH.N0000"]:
            conn.execute("INSERT INTO symbols VALUES (?, 'Banking', 1)", (sym,))
            for d in dates:
                close_p = 100.0 + np.random.uniform(-2, 5)
                conn.execute(
                    "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?)",
                    (sym, d, close_p, close_p + 3, close_p - 3, 5000)
                )
        conn.commit()
        conn.close()

        self.engine = DataEngine(db_path=self.db_path)

    def test_get_daily_featured_stock_empty_db(self):
        empty_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        conn = sqlite3.connect(empty_tmp.name)
        conn.execute("CREATE TABLE symbols (symbol TEXT PRIMARY KEY, industry TEXT, enabled INTEGER)")
        conn.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        conn.execute("CREATE TABLE signals (date TEXT, symbol TEXT, signal INTEGER)")
        conn.commit()
        conn.close()

        empty_engine = DataEngine(db_path=empty_tmp.name)
        feat = empty_engine.get_daily_featured_stock()

        self.assertIn("symbol", feat)
        self.assertIn("name", feat)
        self.assertIn("sector", feat)
        self.assertIn("price", feat)
        self.assertIn("composite_score", feat)
        self.assertIn("recommendation", feat)
        self.assertIn("target_price", feat)
        self.assertIn("stop_loss", feat)
        self.assertIn("highlight_reason", feat)
        self.assertEqual(feat["symbol"], "COMB.N0000")

    def test_get_daily_featured_stock_with_data(self):
        feat = self.engine.get_daily_featured_stock()

        self.assertIn(feat["symbol"], ["COMB.N0000", "JKH.N0000"])
        self.assertGreater(feat["price"], 0)
        self.assertGreater(feat["composite_score"], 0)
        self.assertIn(feat["recommendation"], ["STRONG BUY", "ACCUMULATE", "WATCH", "BUY"])
        self.assertGreater(feat["target_price"], 0)
        self.assertGreater(feat["stop_loss"], 0)
        self.assertTrue(len(feat["highlight_reason"]) > 0)

    def test_dashboard_ui_daily_feature_section(self):
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tkinter display not available.")

        app = MockMainApp(self.engine)
        app.root = root

        tab = DashboardTab(root, app)
        self.assertTrue(hasattr(tab, "lbl_f_sym"))
        self.assertTrue(hasattr(tab, "card_f_score"))
        self.assertTrue(hasattr(tab, "lbl_f_insight"))

        # Verify button callbacks work cleanly
        tab._on_f_view_chart()
        self.assertIsNotNone(getattr(app, "switched_chart", None))

        tab._on_f_add_watchlist()
        self.assertIsNotNone(getattr(app, "switched_watchlist", None))

        tab._on_f_add_portfolio()
        self.assertIsNotNone(getattr(app, "switched_portfolio", None))

        tab._on_f_ai_intel()
        self.assertIsNotNone(getattr(app, "switched_intel", None))

        root.destroy()


if __name__ == "__main__":
    unittest.main()
