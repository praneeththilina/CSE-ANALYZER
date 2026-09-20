# core/data_engine.py  –  Data access layer for CSE Analyzer
"""
Wraps the parent project's stocks.py & qqe_backtest_signals.py so that the
desktop UI never imports them directly.  All heavy I/O runs in background
threads via ThreadedTask (see ui_utils.py).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Parent-project modules (available via sys.path set in main.py)
import stocks
import qqe_backtest_signals as qbs


class DataEngine:
    """Singleton-ish data access object."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            parent_dir = Path(__file__).resolve().parent.parent.parent
            db_path = parent_dir / "cse_signals.db"
        self.db_path = str(db_path)
        self._session = stocks.mk_session(timeout=40)
        self._symbol_cache: list[str] | None = None

    # ── Connection helpers ──────────────────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        return stocks.db_connect(self.db_path)

    @property
    def session(self):
        return self._session

    # ── Symbols ─────────────────────────────────────────────────────────

    def get_all_symbols(self) -> List[Dict[str, Any]]:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT symbol, COALESCE(industry,''), COALESCE(enabled,0) "
                "FROM symbols ORDER BY symbol"
            ).fetchall()
            return [{"symbol": r[0], "industry": r[1], "enabled": int(r[2])} for r in rows]
        finally:
            con.close()

    def get_enabled_symbols(self) -> List[str]:
        con = self.connect()
        try:
            return stocks.fetch_symbols_from_db(con, only_enabled=True)
        finally:
            con.close()

    def get_symbol_list(self, force_refresh: bool = False) -> List[str]:
        if self._symbol_cache is not None and not force_refresh:
            return self._symbol_cache
        con = self.connect()
        try:
            rows = con.execute("SELECT symbol FROM symbols ORDER BY symbol").fetchall()
            self._symbol_cache = [r[0] for r in rows]
            return self._symbol_cache
        finally:
            con.close()

    def toggle_symbol(self, symbol: str, enabled: int):
        con = self.connect()
        try:
            con.execute("UPDATE symbols SET enabled=? WHERE symbol=?", (enabled, symbol))
            con.commit()
        finally:
            con.close()

    # ── Bars / Price data ───────────────────────────────────────────────

    def get_bars(self, symbol: str) -> pd.DataFrame:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT date, close, high, low, volume FROM bars "
                "WHERE symbol=? ORDER BY date", (symbol,)
            ).fetchall()
            if not rows:
                return pd.DataFrame(columns=["date", "close", "high", "low", "volume"])
            df = pd.DataFrame(rows, columns=["date", "close", "high", "low", "volume"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            for c in ["close", "high", "low", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["volume"] = df["volume"].fillna(0)
            # Synthesize 'open' from previous close
            df["open"] = df["close"].shift(1)
            if not df.empty:
                df.iloc[0, df.columns.get_loc("open")] = df.iloc[0]["close"]
            return df.dropna(subset=["close"])
        finally:
            con.close()

    def get_latest_prices(self) -> Dict[str, float]:
        con = self.connect()
        try:
            q = """
            SELECT symbol, close
            FROM (
                SELECT symbol, close,
                       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) as rn
                FROM bars
            ) WHERE rn = 1;
            """
            rows = con.execute(q).fetchall()
            return {sym: float(price) for sym, price in rows}
        finally:
            con.close()

    def get_symbol_industries(self) -> Dict[str, str]:
        con = self.connect()
        try:
            rows = con.execute("SELECT symbol, industry FROM symbols").fetchall()
            return {sym: (ind or "Unknown") for sym, ind in rows}
        finally:
            con.close()

    # ── Dashboard summary ───────────────────────────────────────────────

    def get_dashboard_summary(self) -> Dict[str, Any]:
        con = self.connect()
        try:
            def safe(sql, params=(), default=0):
                try:
                    row = con.execute(sql, params).fetchone()
                    return row[0] if row and row[0] is not None else default
                except Exception:
                    return default

            seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
            return {
                "symbols_total": safe("SELECT COUNT(*) FROM symbols"),
                "symbols_enabled": safe("SELECT COUNT(*) FROM symbols WHERE enabled=1"),
                "bars_total": safe("SELECT COUNT(*) FROM bars"),
                "last_bar_date": safe("SELECT MAX(date) FROM bars", default="—"),
                "last_signal_date": safe("SELECT MAX(date) FROM signals", default="—"),
                "long_7d": safe("SELECT COUNT(*) FROM signals WHERE date>=? AND signal=1", (seven_days_ago,)),
                "short_7d": safe("SELECT COUNT(*) FROM signals WHERE date>=? AND signal=-1", (seven_days_ago,)),
            }
        finally:
            con.close()

    def get_recent_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT date, symbol, signal FROM signals ORDER BY date DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [{"date": r[0], "symbol": r[1], "signal": int(r[2])} for r in rows]
        finally:
            con.close()

    # ── CSE Live API calls & Database Movers ─────────────────────────────

    def get_db_movers(self, limit: int = 15) -> Tuple[List[Dict], List[Dict]]:
        """Calculate top gainers and losers from historical bars in the database in ~15ms."""
        con = self.connect()
        try:
            latest_date_row = con.execute("SELECT MAX(date) FROM bars").fetchone()
            if not latest_date_row or not latest_date_row[0]:
                return [], []
            latest_date = latest_date_row[0]

            q_base = """
            SELECT b1.symbol, b1.close,
                   ROUND(((b1.close - b2.close) / b2.close) * 100, 2) as pct_change,
                   b1.volume
            FROM bars b1
            JOIN (
                SELECT symbol, close,
                       ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) as rn
                FROM bars
            ) b2 ON b1.symbol = b2.symbol AND b2.rn = 2
            WHERE b1.date = ? AND b1.close > 0 AND b2.close > 0
            """

            gainers_rows = con.execute(f"{q_base} AND pct_change > 0 ORDER BY pct_change DESC LIMIT ?", (latest_date, limit)).fetchall()
            losers_rows = con.execute(f"{q_base} AND pct_change < 0 ORDER BY pct_change ASC LIMIT ?", (latest_date, limit)).fetchall()

            gainers = [
                {"symbol": r[0], "price": float(r[1]), "change": float(r[2]), "volume": float(r[3])}
                for r in gainers_rows
            ]
            losers = [
                {"symbol": r[0], "price": float(r[1]), "change": float(r[2]), "volume": float(r[3])}
                for r in losers_rows
            ]
            return gainers, losers
        except Exception:
            return [], []
        finally:
            con.close()

    def get_top_gainers(self) -> List[Dict]:
        try:
            data = stocks.api_top_gainers(self._session)
            return self._extract_top_list(data)
        except Exception:
            return []

    def get_top_losers(self) -> List[Dict]:
        try:
            data = stocks.api_top_losers(self._session)
            return self._extract_top_list(data)
        except Exception:
            return []

    def get_top_gainers_raw(self) -> dict:
        try:
            return stocks.api_top_gainers(self._session)
        except Exception:
            return {}

    def get_top_losers_raw(self) -> dict:
        try:
            return stocks.api_top_losers(self._session)
        except Exception:
            return {}

    def get_company_profile(self, symbol: str) -> dict:
        try:
            return stocks.api_company_profile(self._session, symbol)
        except Exception:
            return {}

    @staticmethod
    def _extract_top_list(data: dict | list) -> List[Dict]:
        items = []
        possible_keys = ["reqTradeSummery", "data", "records"]
        data_list = data if isinstance(data, list) else None
        if not data_list:
            for key in possible_keys:
                if isinstance(data, dict) and isinstance(data.get(key), list):
                    data_list = data[key]
                    break
        if not data_list:
            return []
        for item in data_list[:15]:
            symbol = item.get("symbol") or item.get("security") or ""
            pct = item.get("percentageChange") or item.get("changePer") or 0
            price = item.get("closingPrice") or item.get("price") or item.get("lastTradedPrice") or 0
            vol = item.get("shareVolume") or item.get("volume") or 0
            try:
                items.append({
                    "symbol": str(symbol),
                    "change": float(pct),
                    "price": float(price),
                    "volume": float(vol),
                })
            except (ValueError, TypeError):
                continue
        return items

    # ── QQE scanning ────────────────────────────────────────────────────

    def run_qqe_scan(
        self,
        rsi_period: int = 14,
        sf: int = 5,
        qqe_factor: float = 4.238,
        threshold: int = 10,
    ) -> List[Dict[str, Any]]:
        """Run QQE on all enabled symbols and return signal rows."""
        con = self.connect()
        try:
            enabled = stocks.fetch_symbols_from_db(con, only_enabled=True)
            if not enabled:
                enabled = stocks.fetch_symbols_from_db(con, only_enabled=None)

            ind_map = {sym: ind for sym, ind in
                       con.execute("SELECT symbol, industry FROM symbols").fetchall()}
            results = []
            for sym in enabled:
                try:
                    closes = stocks.get_symbol_closes(con, sym)
                    if len(closes) < 60:
                        continue
                    qqe = stocks.compute_qqe_from_closes(
                        closes, rsi_period=rsi_period, sf=sf,
                        qqe_factor=qqe_factor, threshold=threshold,
                    )
                    df = pd.concat([closes.rename("close"), qqe], axis=1).dropna(subset=["close"])
                    if df.empty:
                        continue
                    last = df.iloc[-1]
                    sig = int(last["signal"])
                    if sig != 0:
                        results.append({
                            "symbol": sym,
                            "industry": ind_map.get(sym, ""),
                            "signal": sig,
                            "signal_text": "LONG" if sig == 1 else "SHORT",
                            "rsi_ma": f"{last.get('rsi_ma', 0):.2f}",
                            "fast_tl": f"{last.get('fast_tl', 0):.2f}",
                            "price": f"{last['close']:.2f}",
                            "date": df.index[-1].strftime("%Y-%m-%d"),
                        })
                except Exception:
                    continue
            return results
        finally:
            con.close()

    # ── Daily scan (bars + signals) ─────────────────────────────────────

    def run_daily_scan(
        self,
        period: int = 5,
        update_symbols: bool = False,
        rsi_period: int = 14,
        sf: int = 5,
        qqe_factor: float = 4.238,
        threshold: int = 10,
    ) -> str:
        """Run the full daily scan pipeline, returning a log string."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                stocks.run(
                    db_path=self.db_path,
                    timeout=40,
                    update_symbols_flag=update_symbols,
                    allow_scrape=False,
                    update_only=False,
                    enable_all=False,
                    disable_all=False,
                    enable_file=None,
                    disable_file=None,
                    symbol_only=None,
                    period=period,
                    rsi_period=rsi_period,
                    sf=sf,
                    qqe_factor=qqe_factor,
                    threshold=threshold,
                    min_bars=60,
                    dry_run=False,
                )
        except SystemExit:
            pass
        except Exception as e:
            buf.write(f"\n[ERROR] {e}")
        return buf.getvalue()

    # ── Backtest ────────────────────────────────────────────────────────

    def run_backtest(self, symbol: str, params: Dict[str, Any]) -> Dict[str, Any]:
        con = self.connect()
        try:
            bars_df = qbs.load_bars_full(con, symbol)
            if bars_df.empty:
                raise ValueError(f"No data for {symbol}")
            return qbs.run_full_backtest(bars_df, params)
        finally:
            con.close()

    def run_quick_backtest(
        self,
        count: int = 50,
        rsi_period: int = 14,
        sf: int = 5,
        qqe_factor: float = 4.238,
        threshold: int = 10,
        horizons: List[int] | None = None,
    ) -> pd.DataFrame:
        if horizons is None:
            horizons = [5, 10, 20]
        con = self.connect()
        try:
            symbols = stocks.fetch_symbols_from_db(con, only_enabled=True)
            if not symbols:
                symbols = stocks.fetch_symbols_from_db(con, only_enabled=None)
            return qbs.run_backtest_signals(
                con=con, symbols=symbols, per_symbol=False, count=count,
                rsi_period=rsi_period, sf=sf, qqe_factor=qqe_factor,
                threshold=threshold, horizons=horizons,
            )
        finally:
            con.close()

    # ── Portfolio ───────────────────────────────────────────────────────

    def get_portfolio(self) -> List[Dict[str, Any]]:
        con = self.connect()
        try:
            trades = con.execute(
                "SELECT id, symbol, side, quantity, entry_price, trade_date "
                "FROM portfolio ORDER BY symbol"
            ).fetchall()
            latest = self.get_latest_prices()
            industries = self.get_symbol_industries()
            positions = []
            for tid, sym, side, qty, price, tdate in trades:
                cost = float(qty) * float(price)
                cur_price = latest.get(sym)
                cur_val = float(qty) * cur_price if cur_price else 0
                if cur_price and side.upper() == "BUY":
                    pnl = cur_val - cost
                elif cur_price:
                    pnl = cost - cur_val
                else:
                    pnl = 0
                pnl_pct = (pnl / cost * 100) if cost else 0
                positions.append({
                    "id": tid, "symbol": sym,
                    "industry": industries.get(sym, "Unknown"),
                    "side": side.upper(), "quantity": float(qty),
                    "entry_price": float(price), "cost_basis": cost,
                    "current_price": cur_price, "current_value": cur_val,
                    "pnl": pnl, "pnl_pct": pnl_pct,
                    "trade_date": tdate,
                })
            return positions
        finally:
            con.close()

    get_portfolio_positions = get_portfolio

    def add_portfolio_trade(self, symbol: str, side: str, qty: float,
                            price: float, trade_date: str):
        con = self.connect()
        try:
            con.execute(
                "INSERT INTO portfolio (symbol, side, quantity, entry_price, trade_date) "
                "VALUES (?, ?, ?, ?, ?)",
                (symbol.upper(), side.upper(), qty, price, trade_date)
            )
            con.commit()
        finally:
            con.close()

    def delete_portfolio_trade(self, trade_id: int):
        con = self.connect()
        try:
            con.execute("DELETE FROM portfolio WHERE id=?", (trade_id,))
            con.commit()
        finally:
            con.close()

    # ── Stock analysis data prep ────────────────────────────────────────

    def get_stock_analysis_data(self, symbol: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Get price data + calculated summary for AI analysis."""
        con = self.connect()
        try:
            rows = con.execute(
                "SELECT date, close, high, low, volume FROM bars "
                "WHERE symbol=? ORDER BY date", (symbol,)
            ).fetchall()
            if not rows or len(rows) < 60:
                raise ValueError("Not enough data (minimum 60 days)")
            df = pd.DataFrame(rows, columns=["date", "close", "high", "low", "volume"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

            summary = {
                "52_week_high": df["high"].rolling(252).max().iloc[-1],
                "52_week_low": df["low"].rolling(252).min().iloc[-1],
                "50_day_ma": df["close"].rolling(50).mean().iloc[-1],
                "200_day_ma": df["close"].rolling(200).mean().iloc[-1],
                "avg_volume_30d": df["volume"].rolling(30).mean().iloc[-1],
                "current_price": df["close"].iloc[-1],
                "volatility_30d": df["close"].pct_change().rolling(30).std().iloc[-1] * (252 ** 0.5),
            }
            for k, v in summary.items():
                if isinstance(v, (int, float)):
                    summary[k] = f"{v:.2f}"
            return df, summary
        finally:
            con.close()
