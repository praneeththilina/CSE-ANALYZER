import unittest
import tempfile
import sqlite3
import tkinter as tk
import pandas as pd
import numpy as np
from unittest.mock import patch

from core.data_engine import DataEngine
import app as main_app_mod


class TestUIViewsHeadless(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.has_tk = True
        except Exception:
            cls.has_tk = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "has_tk", False):
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.has_tk:
            self.skipTest("Tkinter display not available")

        # Create temporary database for testing
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp_db.name

        con = sqlite3.connect(self.db_path)
        con.execute("CREATE TABLE symbols (symbol TEXT PRIMARY KEY, industry TEXT, enabled INTEGER)")
        con.execute("CREATE TABLE bars (symbol TEXT, date TEXT, close REAL, high REAL, low REAL, volume REAL)")
        con.execute("CREATE TABLE signals (date TEXT, symbol TEXT, signal INTEGER)")
        con.execute("CREATE TABLE portfolio (id INTEGER PRIMARY KEY, symbol TEXT, side TEXT, quantity REAL, entry_price REAL, trade_date TEXT)")

        con.execute("INSERT INTO symbols VALUES ('COMB.N0000', 'Banking', 1)")
        con.execute("INSERT INTO symbols VALUES ('JKH.N0000', 'Conglomerates', 1)")

        dates = pd.date_range("2023-01-01", periods=60, freq="D")
        for dt in dates:
            d_str = str(dt)[:10]
            con.execute("INSERT INTO bars VALUES ('COMB.N0000', ?, 120.0, 125.0, 115.0, 10000)", (d_str,))
            con.execute("INSERT INTO bars VALUES ('JKH.N0000', ?, 20.0, 22.0, 19.0, 50000)", (d_str,))

        con.commit()
        con.close()

    def test_main_app_instantiation_and_tabs(self):
        """Test full MainApp creation and switching between all 9 tabs."""
        db_path = self.db_path
        orig_init = DataEngine.__init__

        def custom_init(self_de, *args, **kwargs):
            kwargs["db_path"] = db_path
            orig_init(self_de, *args, **kwargs)

        with patch.object(DataEngine, "__init__", custom_init):
            app = main_app_mod.MainApp(self.root)

        tabs = [
            "dashboard", "scanner", "chart", "watchlist",
            "market_intel", "portfolio", "backtest", "ai_analysis", "settings"
        ]

        for tab_key in tabs:
            app._show_page(tab_key)
            active = app.get_active_page()
            self.assertIsNotNone(active)

        # Test switching to chart with loaded symbol
        app.switch_to_chart("COMB.N0000", entry=120.0, stop_loss=115.0)
        self.assertEqual(app._current_page_key, "chart")

        # Test switching to portfolio
        app.switch_to_portfolio("COMB.N0000", 120.0, 500)
        self.assertEqual(app._current_page_key, "portfolio")

        # Test switching to watchlist
        app.switch_to_watchlist("COMB.N0000")
        self.assertEqual(app._current_page_key, "watchlist")

        # Test switching to intel
        app.switch_to_intel("COMB.N0000")
        self.assertEqual(app._current_page_key, "market_intel")

        app.destroy()


if __name__ == "__main__":
    unittest.main()
