import unittest
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch
import pandas as pd
import stocks


class TestStocksRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.con = stocks.db_connect(self.db_path)

    def tearDown(self):
        self.con.close()

    def test_manage_symbol_flags(self):
        stocks.upsert_symbol(self.con, "TEST1.N0000", "Tech", enabled_default=1)
        stocks.upsert_symbol(self.con, "TEST2.N0000", "Tech", enabled_default=1)

        stocks._manage_symbol_flags(
            self.con,
            enable_all=False,
            disable_all=True,
            enable_file=None,
            disable_file=None,
        )
        enabled = stocks.fetch_symbols_from_db(self.con, only_enabled=True)
        self.assertEqual(len(enabled), 0)

        stocks._manage_symbol_flags(
            self.con,
            enable_all=True,
            disable_all=False,
            enable_file=None,
            disable_file=None,
        )
        enabled = stocks.fetch_symbols_from_db(self.con, only_enabled=True)
        self.assertEqual(len(enabled), 2)

    @patch("stocks.incremental_upsert_bars")
    def test_update_symbol_bars(self, mock_upsert):
        mock_upsert.return_value = (5, 10)
        session = MagicMock()
        symbols = ["TEST1.N0000", "TEST2.N0000"]

        stocks._update_symbol_bars(self.con, session, symbols, symbol_only="TEST1.N0000", period=5)
        mock_upsert.assert_called_once_with(self.con, session, "TEST1.N0000", period=5)

    def test_scan_qqe_signals(self):
        sym = "TEST1.N0000"
        stocks.upsert_symbol(self.con, sym, "Tech", enabled_default=1)

        dates = pd.date_range("2023-01-01", periods=70, freq="D")
        closes = [100.0 + i * 0.5 for i in range(70)]
        df = pd.DataFrame({
            "date": dates,
            "close": closes,
            "high": closes,
            "low": closes,
            "volume": [1000] * 70,
        })
        stocks.upsert_bars(self.con, sym, df)

        today_str = dates[-1].strftime("%Y-%m-%d")
        long_hits, short_hits = stocks._scan_qqe_signals(
            self.con,
            enabled_symbols=[sym],
            today_str=today_str,
            rsi_period=14,
            sf=5,
            qqe_factor=4.238,
            threshold=10,
            min_bars=60,
        )
        self.assertIsInstance(long_hits, list)
        self.assertIsInstance(short_hits, list)

    @patch("stocks.send_telegram_message")
    def test_send_signals_summary(self, mock_send):
        stocks._send_signals_summary("2023-01-01", ["TEST1.N0000"], [], dry_run=False)
        mock_send.assert_called_once()

        mock_send.reset_mock()
        stocks._send_signals_summary("2023-01-01", ["TEST1.N0000"], [], dry_run=True)
        mock_send.assert_not_called()

    @patch("stocks.send_telegram_message")
    @patch("stocks.incremental_upsert_bars", return_value=(0, 0))
    def test_run_orchestrator(self, mock_upsert, mock_telegram):
        stocks.upsert_symbol(self.con, "TEST1.N0000", "Tech", enabled_default=1)

        dates = pd.date_range("2023-01-01", periods=70, freq="D")
        closes = [100.0 + i * 0.1 for i in range(70)]
        df = pd.DataFrame({
            "date": dates,
            "close": closes,
            "high": closes,
            "low": closes,
            "volume": [1000] * 70,
        })
        stocks.upsert_bars(self.con, "TEST1.N0000", df)

        stocks.run(
            db_path=self.db_path,
            timeout=10,
            update_symbols_flag=False,
            allow_scrape=False,
            update_only=False,
            enable_all=False,
            disable_all=False,
            enable_file=None,
            disable_file=None,
            symbol_only=None,
            period=5,
            rsi_period=14,
            sf=5,
            qqe_factor=4.238,
            threshold=10,
            min_bars=60,
            dry_run=True,
        )
        mock_telegram.assert_called_once()  # Startup message in dry_run


if __name__ == "__main__":
    unittest.main()
