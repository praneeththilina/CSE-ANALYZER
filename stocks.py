# stocks.py
from __future__ import annotations

import argparse
import os
import re
import sqlite3
from html.parser import HTMLParser
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
    TZ_COLOMBO = ZoneInfo("Asia/Colombo")
except Exception:
    TZ_COLOMBO = None

# ---------------- Config ----------------
BASE = "https://www.cse.lk/api/"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/",
}
DEFAULT_DB = "cse_signals.db"

# Load .env file
load_dotenv()


# --------------- HTTP -------------------
def mk_session(timeout: int = 30) -> requests.Session:
    s = requests.Session()
    s.headers.update(HDRS)
    s.timeout = timeout
    return s

def post(s: requests.Session, ep: str, data: Dict[str, Any] | None = None) -> requests.Response:
    r = s.post(BASE + ep, data=data or {})
    r.raise_for_status()
    return r

def get(s: requests.Session, url: str) -> requests.Response:
    r = s.get(url)
    r.raise_for_status()
    return r

# --- CSE utility calls you asked for ---
def api_company_profile(s: requests.Session, symbol: str) -> dict:
    return post(s, "companyProfile", {"symbol": symbol}).json()

def api_days_trade(s: requests.Session, symbol: str) -> dict:
    return post(s, "daysTrade", {"symbol": symbol}).json()

def api_order_book(s: requests.Session, symbol: str, token: str | None = None) -> dict:
    data = {"symbol": symbol}
    if token:
        data["token"] = token
    return post(s, "orderBook", data).json()

def api_company_news(s: requests.Session, symbol: str, news_type: str = "BN", top: bool = False) -> dict:
    """Fetch company news and announcements from CSE API.

    Args:
        s: Active requests.Session instance.
        symbol: Security symbol (e.g., COMB.N0000).
        news_type: Type filter for news (default 'BN').
        top: Whether to fetch top news only (default False).

    Returns:
        JSON dict response containing news entries.
    """
    url = f"{BASE}news/web?top={'true' if top else 'false'}&type={news_type}&security={symbol}"
    return get(s, url).json()

def api_top_gainers(s: requests.Session) -> dict:
    return post(s, "topGainers").json()

def api_top_losers(s: requests.Session) -> dict:
    return post(s, "topLooses").json()

def api_new_listings_ann(s: requests.Session) -> dict:
    return post(s, "getNewListingsRelatedNoticesAnnouncements").json()

# --- Synthetic order book fallback from trades ---
def synthetic_order_book_from_trades(s: requests.Session, symbol: str, tick: float = 0.10, levels: int = 10):
    """
    Approximate an order book by binning intraday trades into price buckets
    around the last price. This is NOT real depth, but it gives a sense of
    liquidity pockets when L2 is unavailable.
    """
    trades = api_days_trade(s, symbol)
    # Find an array of trade rows
    rows = []
    for k, v in (trades or {}).items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            rows = v
            break
    if not rows:
        return {"symbol": symbol, "method": "synthetic_from_daysTrade", "bids": [], "asks": []}

    # Extract price, qty fields under common aliases
    def pick(d, *keys, default=None):
        for kk in keys:
            if kk in d and d[kk] is not None:
                return d[kk]
        return default

    parsed = []
    for r in rows:
        p = float(pick(r, "price", "tradePrice", "ltp", "LastTradedPrice", default=0) or 0)
        q = float(pick(r, "qty", "quantity", "volume", "tradeQty", default=0) or 0)
        if p > 0 and q > 0:
            parsed.append((p, q))
    if not parsed:
        return {"symbol": symbol, "method": "synthetic_from_daysTrade", "bids": [], "asks": []}

    last = parsed[-1][0]
    # Bucketize
    from math import floor
    def bucket(price):
        return round(floor(price / tick) * tick, 2)

    by_price = {}
    for p, q in parsed:
        b = bucket(p)
        by_price[b] = by_price.get(b, 0.0) + q

    # Split into bid-ish (<= last) and ask-ish (> last), sort by proximity
    bids = sorted([(bp, by_price[bp]) for bp in by_price if bp <= last],
                  key=lambda x: x[0], reverse=True)[:levels]
    asks = sorted([(ap, by_price[ap]) for ap in by_price if ap > last],
                  key=lambda x: x[0])[:levels]

    return {
        "symbol": symbol,
        "method": "synthetic_from_daysTrade",
        "tick": tick,
        "last": last,
        "bids": [{"price": p, "qty": round(q, 2)} for p, q in bids],
        "asks": [{"price": p, "qty": round(q, 2)} for p, q in asks],
    }


# -------------- Telegram --------------
def send_telegram_message(text: str, force: bool = False) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        # Always print for visibility
        print(f"[Telegram skipped] {text}")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=25)
    except Exception as e:
        print(f"Telegram send failed: {e}")

# ---------------- SQLite ----------------
DDL = """
CREATE TABLE IF NOT EXISTS symbols(
    symbol   TEXT PRIMARY KEY,
    industry TEXT,
    enabled  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS bars(
    symbol TEXT,
    date   TEXT,           -- YYYY-MM-DD (Colombo)
    close  REAL,
    high   REAL,
    low    REAL,
    volume REAL,
    PRIMARY KEY(symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_bars_symbol_date ON bars(symbol, date);
CREATE TABLE IF NOT EXISTS signals(
    symbol TEXT,
    date   TEXT,
    signal INTEGER,        -- 1 long, -1 short, 0 none
    PRIMARY KEY(symbol, date)
);
-- *** ADDED portfolio table definition ***
CREATE TABLE IF NOT EXISTS portfolio(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL, -- 'BUY' or 'SELL'
    quantity    REAL NOT NULL,
    entry_price REAL NOT NULL,
    trade_date  TEXT NOT NULL -- YYYY-MM-DD
);
"""

def db_connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    # Ensure all statements in DDL are executed
    for stmt in filter(None, DDL.split(";\n")):
        try:
            con.execute(stmt)
        except Exception as e:
            print(f"Error executing DDL: {stmt}\n{e}")
            raise # Re-raise error if schema fails
    return con

def upsert_symbol(con: sqlite3.Connection, symbol: str, industry: str | None, enabled_default: int = 1) -> None:
    # Keep existing enabled unless explicitly overridden; refresh industry if provided
    con.execute(
        """
        INSERT INTO symbols(symbol, industry, enabled)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            industry = COALESCE(excluded.industry, symbols.industry)
        """,
        (symbol, industry, enabled_default),
    )
    con.commit()

def upsert_symbols_bulk(con: sqlite3.Connection, rows: List[Tuple[str, str | None]]) -> None:
    con.executemany(
        """
        INSERT INTO symbols(symbol, industry, enabled)
        VALUES (?, ?, 1)
        ON CONFLICT(symbol) DO UPDATE SET
            industry = COALESCE(excluded.industry, symbols.industry)
        """,
        rows,
    )
    con.commit()

def fetch_symbols_from_db(con: sqlite3.Connection, only_enabled: bool | None = None) -> List[str]:
    if only_enabled is True:
        cur = con.execute("SELECT symbol FROM symbols WHERE enabled=1 ORDER BY symbol")
    elif only_enabled is False:
        cur = con.execute("SELECT symbol FROM symbols WHERE enabled=0 ORDER BY symbol")
    else:
        cur = con.execute("SELECT symbol FROM symbols ORDER BY symbol")
    return [r[0] for r in cur.fetchall()]

def set_enabled_all(con: sqlite3.Connection, value: int) -> None:
    con.execute("UPDATE symbols SET enabled=?", (int(value),))
    con.commit()

def set_enabled_from_file(con: sqlite3.Connection, path: str, value: int) -> None:
    with open(path, "r", encoding="utf-8") as f:
        syms = [ln.strip() for ln in f if ln.strip()]
    con.executemany("UPDATE symbols SET enabled=? WHERE symbol=?", [(int(value), s) for s in syms])
    con.commit()

def upsert_bars(con: sqlite3.Connection, symbol: str, df: pd.DataFrame) -> None:
    rows = [
        (symbol, d.strftime("%Y-%m-%d"), float(c), float(h), float(l), float(v))
        for d, c, h, l, v in zip(df["date"], df["close"], df["high"], df["low"], df["volume"])
    ]
    con.executemany(
        "INSERT OR REPLACE INTO bars(symbol, date, close, high, low, volume) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()

def get_symbol_last_date(con: sqlite3.Connection, symbol: str) -> str | None:
    cur = con.execute("SELECT MAX(date) FROM bars WHERE symbol=?", (symbol,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None

def get_symbol_closes(con: sqlite3.Connection, symbol: str) -> pd.Series:
    cur = con.execute("SELECT date, close FROM bars WHERE symbol=? ORDER BY date", (symbol,))
    rows = cur.fetchall()
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df["close"]

def upsert_signal(con: sqlite3.Connection, symbol: str, date_str: str, sig: int) -> None:
    con.execute(
        "INSERT OR REPLACE INTO signals(symbol, date, signal) VALUES (?, ?, ?)",
        (symbol, date_str, int(sig)),
    )
    con.commit()

# -------------- Symbol Harvester --------------
SYMBOL_RX = re.compile(r"^[A-Z0-9]+\.N\d{4}$")  # e.g., LOLC.N0000

def _collect_symbols_from_json(obj: Any) -> set[str]:
    found: set[str] = set()
    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str):
                    val = v.strip().upper()
                    if SYMBOL_RX.match(val):
                        found.add(val)
                walk(v)
        elif isinstance(x, list):
            for it in x:
                walk(it)
    walk(obj)
    return found

class _DirParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.syms: set[str] = set()
    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        m = re.search(r"symbol=([A-Z0-9]+\.[A-Z0-9]+)", href.upper())
        if m:
            val = m.group(1)
            if SYMBOL_RX.match(val):
                self.syms.add(val)

def _try_post_json(s: requests.Session, endpoint: str, data: Dict[str, Any] | None = None):
    try:
        r = post(s, endpoint, data)
        return r.json()
    except Exception:
        return None

def harvest_all_symbols(s: requests.Session, allow_scrape: bool = False) -> List[str]:
    symbols: set[str] = set()
    # 1) tradeSummary with pagination guesses
    for payload in ({}, {"size": 2000}, {"limit": 2000}, {"pageSize": 2000}):
        js = _try_post_json(s, "tradeSummary", payload)
        if js:
            symbols |= _collect_symbols_from_json(js)
    # 2) todaySharePrice + top lists
    for ep in ("todaySharePrice", "mostActiveTrades", "topGainers", "topLooses"):
        js = _try_post_json(s, ep)
        if js:
            symbols |= _collect_symbols_from_json(js)
    # 3) optional HTML directory scrape to catch stragglers
    if allow_scrape:
        try:
            url = "https://www.cse.lk/pages/listed-company/listed-company.component.html?status=2"
            r = get(s, url)
            p = _DirParser()
            p.feed(r.text)
            symbols |= p.syms
        except Exception:
            pass
    return sorted(symbols)

# ------------- Company meta (industry) -------------
def get_stock_id(s: requests.Session, symbol: str) -> int | None:
    js = post(s, "homeCompanyData", {"symbol": symbol}).json()
    if isinstance(js, dict) and "id" in js:
        return int(js["id"])
    return None

def get_company_industry(s: requests.Session, symbol: str) -> str | None:
    """
    Try companyInfoSummery first; fall back to homeCompanyData keys.
    We accept keys: 'industryGroup', 'industry', 'sectorName', 'sector'
    """
    try:
        j = post(s, "companyInfoSummery", {"symbol": symbol}).json()
        if isinstance(j, dict):
            for k in ("industryGroup", "industry", "sectorName", "sector"):
                if k in j and isinstance(j[k], str) and j[k].strip():
                    return j[k].strip()
    except Exception:
        pass
    try:
        j = post(s, "homeCompanyData", {"symbol": symbol}).json()
        if isinstance(j, dict):
            for k in ("industryGroup", "industry", "sectorName", "sector"):
                if k in j and isinstance(j[k], str) and j[k].strip():
                    return j[k].strip()
    except Exception:
        pass
    return None

def refresh_symbols(con: sqlite3.Connection, s: requests.Session, allow_scrape: bool = False) -> int:
    syms = harvest_all_symbols(s, allow_scrape=allow_scrape)
    if not syms:
        print("No symbols harvested. Try during market hours or enable --allow-scrape.")
        return 0
    # Fetch industry for each symbol (best-effort)
    rows: List[Tuple[str, str | None]] = []
    for sym in syms:
        try:
            industry = get_company_industry(s, sym)
        except Exception:
            industry = None
        rows.append((sym, industry))
    upsert_symbols_bulk(con, rows)
    # Report enabled count
    cur = con.execute("SELECT COUNT(*) FROM symbols WHERE enabled=1")
    enabled_count = cur.fetchone()[0]
    print(f"Symbols in DB: {len(syms)}  (enabled for QQE: {enabled_count})")
    return len(syms)

# ------------- Bars (incremental) -------------
def to_colombo_date_index(ms: pd.Series) -> pd.Series:
    dt = pd.to_datetime(ms, unit="ms", utc=True)
    if TZ_COLOMBO is not None:
        return dt.dt.tz_convert(TZ_COLOMBO).dt.date
    return dt.dt.date

def get_company_chart_daily(s: requests.Session, stock_id: int, period: int = 5) -> List[Dict[str, Any]]:
    js = post(s, "companyChartDataByStock", {"stockId": stock_id, "period": period}).json()
    arr = js.get("chartData", []) if isinstance(js, dict) else []
    return arr if isinstance(arr, list) else []

def bars_to_df(arr: List[Dict[str, Any]]) -> pd.DataFrame:
    if not arr:
        return pd.DataFrame(columns=["date", "close", "high", "low", "volume"])
    df = pd.DataFrame(arr)
    if "t" not in df.columns or "p" not in df.columns:
        return pd.DataFrame(columns=["date", "close", "high", "low", "volume"])
    df["date"] = to_colombo_date_index(df["t"])
    df.rename(columns={"p": "close", "h": "high", "l": "low", "q": "volume"}, inplace=True)
    for col in ("close", "high", "low", "volume"):
        if col not in df.columns:
            df[col] = np.nan if col != "volume" else 0.0
    df = df[["date", "close", "high", "low", "volume"]]
    df = df.dropna(subset=["close"]).drop_duplicates(subset=["date"]).sort_values("date")
    return df

def incremental_upsert_bars(con: sqlite3.Connection, s: requests.Session, symbol: str, period: int) -> Tuple[int, int]:
    """
    Returns (inserted_rows, total_rows_returned)
    """
    sid = get_stock_id(s, symbol)
    if not sid:
        return (0, 0)
    arr = get_company_chart_daily(s, sid, period=period)
    df = bars_to_df(arr)
    if df.empty:
        return (0, 0)

    last_date_str = get_symbol_last_date(con, symbol)
    if last_date_str:
        last_date = pd.to_datetime(last_date_str).date()
        df = df[df["date"] > last_date]  # only new bars
    inserted = len(df)
    if inserted > 0:
        upsert_bars(con, symbol, df)
    return (inserted, len(arr))



# ------------- QQE (Pine-equivalent) -------------
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def compute_qqe_from_closes(
    closes: pd.Series,
    rsi_period: int = 14,
    sf: int = 5,
    qqe_factor: float = 4.238,
    threshold: int = 10,
) -> pd.DataFrame:
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    alpha = 1 / rsi_period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    rsi_val = rsi_val.fillna(0.0)

    rsi_ma = ema(rsi_val, sf)

    wilders_period = rsi_period * 2 - 1
    atr_rsi = (rsi_ma.shift(1) - rsi_ma).abs()
    ma_atr = ema(atr_rsi, wilders_period)
    dar = ema(ma_atr, wilders_period) * qqe_factor

    rs_index = rsi_ma
    n = len(rs_index)
    longband = np.zeros(n)
    shortband = np.zeros(n)
    trend = np.zeros(n, dtype=int)

    rs_np = rs_index.to_numpy()
    dar_np = dar.to_numpy()
    start = int(np.argmax(~np.isnan(rs_np)))
    if start >= n or np.isnan(rs_np[start]):
        out = pd.DataFrame(index=closes.index)
        out["rsi_val"] = rsi_val
        out["rsi_ma"] = rsi_ma
        out["longband"] = np.nan
        out["shortband"] = np.nan
        out["fast_tl"] = np.nan
        out["trend"] = 0
        out["qqe_long"] = np.nan
        out["qqe_short"] = np.nan
        out["signal"] = 0
        return out

    longband[start] = rs_np[start] - (0.0 if np.isnan(dar_np[start]) else dar_np[start])
    shortband[start] = rs_np[start] + (0.0 if np.isnan(dar_np[start]) else dar_np[start])
    trend[start] = 0

    for i in range(start + 1, n):
        rsi_i = rs_np[i]
        prev_lb = longband[i - 1]
        prev_sb = shortband[i - 1]
        prev_rs = rs_np[i - 1]
        d_i = 0.0 if np.isnan(dar_np[i]) else float(dar_np[i])

        lb_raw = rsi_i - d_i
        sb_raw = rsi_i + d_i

        longband[i] = max(prev_lb, lb_raw) if (prev_rs > prev_lb and rsi_i > prev_lb) else lb_raw
        shortband[i] = min(prev_sb, sb_raw) if (prev_rs < prev_sb and rsi_i < prev_sb) else sb_raw

        cross_up = (rs_np[i - 1] <= prev_sb) and (rsi_i > prev_sb)
        cross_dn = (rs_np[i - 1] >= prev_lb) and (rsi_i < prev_lb)
        if cross_up:
            trend[i] = 1
        elif cross_dn:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1] if trend[i - 1] != 0 else 1

    fast_tl = np.where(trend == 1, longband, shortband)

    qqexlong = np.zeros(n, dtype=int)
    qqexshort = np.zeros(n, dtype=int)
    for i in range(start, n):
        qqexlong[i] = (qqexlong[i - 1] + 1) if (i > 0 and fast_tl[i] < rs_np[i]) else (1 if fast_tl[i] < rs_np[i] else 0)
        qqexshort[i] = (qqexshort[i - 1] + 1) if (i > 0 and fast_tl[i] > rs_np[i]) else (1 if fast_tl[i] > rs_np[i] else 0)

    ft_prev = np.concatenate(([np.nan], fast_tl[:-1]))
    qqe_long_val = ft_prev - 50
    qqe_short_val = ft_prev - 50
    qqe_long = np.where((qqexlong == 1) & (qqe_long_val <= -10), qqe_long_val, np.nan) if threshold is None else np.where((qqexlong == 1) & (qqe_long_val <= -threshold), qqe_long_val, np.nan)
    qqe_short = np.where((qqexshort == 1) & (qqe_short_val >= 10), qqe_short_val, np.nan) if threshold is None else np.where((qqexshort == 1) & (qqe_short_val >= threshold), qqe_short_val, np.nan)
    signal = np.where(~np.isnan(qqe_long), 1, np.where(~np.isnan(qqe_short), -1, 0))

    out = pd.DataFrame(index=closes.index)
    out["rsi_val"] = rsi_val
    out["rsi_ma"] = rsi_ma
    out["longband"] = longband
    out["shortband"] = shortband
    out["fast_tl"] = fast_tl
    out["trend"] = trend
    out["qqe_long"] = qqe_long
    out["qqe_short"] = qqe_short
    out["signal"] = signal
    return out

# --------------- Runner ---------------
def run(
    db_path: str,
    timeout: int,
    update_symbols_flag: bool,
    allow_scrape: bool,
    update_only: bool,
    enable_all: bool,
    disable_all: bool,
    enable_file: str | None,
    disable_file: str | None,
    symbol_only: str | None,
    period: int,
    rsi_period: int,
    sf: int,
    qqe_factor: float,
    threshold: int,
    min_bars: int,
    dry_run: bool,
) -> None:
    con = db_connect(db_path)
    s = mk_session(timeout=timeout)

    # Telegram connection test on startup
    ts = datetime.now(TZ_COLOMBO).strftime("%Y-%m-%d %H:%M %Z") if TZ_COLOMBO else datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    send_telegram_message(f"✅ CSE QQE app started @ {ts}", force=True)

    # Symbol table maintenance
    if enable_all:
        set_enabled_all(con, 1)
    if disable_all:
        set_enabled_all(con, 0)
    if enable_file:
        set_enabled_from_file(con, enable_file, 1)
    if disable_file:
        set_enabled_from_file(con, disable_file, 0)

    if update_symbols_flag:
        refresh_symbols(con, s, allow_scrape=allow_scrape)
        if update_only:
            return

    # Choose symbols
    symbols = fetch_symbols_from_db(con)
    if not symbols:
        print("No symbols in DB. Run with --update-symbols first or insert manually.")
        return

    print(f"Symbols in DB: {len(symbols)} total.")
    # Fetch/insert bars incrementally for ALL symbols (regardless of enabled)
    for sym in ([symbol_only] if symbol_only else symbols):
        try:
            inserted, total = incremental_upsert_bars(con, s, sym, period=period)
            last = get_symbol_last_date(con, sym)
            print(f"[bars] {sym}: +{inserted} new / {total} fetched (last={last})")
        except Exception as e:
            print(f"[bars error] {sym}: {e}")

    # Now compute QQE only for enabled symbols
    enabled_symbols = fetch_symbols_from_db(con, only_enabled=True)
    if symbol_only and symbol_only not in enabled_symbols:
        enabled_symbols = [symbol_only]  # allow one-off test

    if TZ_COLOMBO is not None:
        today_colombo = datetime.now(TZ_COLOMBO).date().strftime("%Y-%m-%d")
    else:
        today_colombo = datetime.utcnow().date().strftime("%Y-%m-%d")

    long_hits, short_hits = [], []
    for sym in enabled_symbols:
        try:
            closes = get_symbol_closes(con, sym)
            if len(closes) < min_bars:
                continue
            qqe = compute_qqe_from_closes(
                closes,
                rsi_period=rsi_period,
                sf=sf,
                qqe_factor=qqe_factor,
                threshold=threshold,
            )
            df = pd.concat([closes.rename("close"), qqe], axis=1).dropna(subset=["close"])
            if df.empty:
                continue
            last_date = df.index[-1].strftime("%Y-%m-%d")
            last_sig = int(df["signal"].iloc[-1])
            upsert_signal(con, sym, last_date, last_sig)
            if last_date == today_colombo:
                if last_sig == 1:
                    long_hits.append(sym)
                elif last_sig == -1:
                    short_hits.append(sym)
        except Exception as e:
            print(f"[qqe error] {sym}: {e}")

    # Telegram signals summary
    if not dry_run and (long_hits or short_hits):
        lines = [f"*CSE QQE Daily Signals ({today_colombo})*"]
        if long_hits:
            lines.append("🟢 Long: " + ", ".join(long_hits[:200]))
        if short_hits:
            lines.append("🔴 Short: " + ", ".join(short_hits[:200]))
        send_telegram_message("\n".join(lines))
        print("Telegram summary sent.")
    else:
        print("No new signals for today or Telegram disabled.")

# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser(description="CSE symbols updater, incremental daily bars, and QQE scanner")
    ap.add_argument("--db", type=str, default=DEFAULT_DB, help="SQLite path")
    ap.add_argument("--timeout", type=int, default=40)

    # Symbol refresh & controls
    ap.add_argument("--update-symbols", action="store_true", help="Harvest and store all symbols (with industry) into DB")
    ap.add_argument("--allow-scrape", action="store_true", help="Also parse the Listed Company Directory HTML")
    ap.add_argument("--update-only", action="store_true", help="Only update symbols then exit")

    # Enabled flags maintenance (optional)
    ap.add_argument("--enable-all", action="store_true", help="Mark all symbols enabled for QQE")
    ap.add_argument("--disable-all", action="store_true", help="Mark all symbols disabled for QQE")
    ap.add_argument("--enable-file", type=str, default=None, help="File with one symbol per line to enable")
    ap.add_argument("--disable-file", type=str, default=None, help="File with one symbol per line to disable")

    # Processing scope
    ap.add_argument("--symbol", type=str, default=None, help="Process only this symbol (bars+signals)")
    ap.add_argument("--period", type=int, default=5, choices=[1, 2, 3, 4, 5], help="Chart period: 1D=1, 1W=2, 1M=3, 1Q=4, 1Y=5")

    # QQE parameters
    ap.add_argument("--rsi-period", type=int, default=14)
    ap.add_argument("--sf", type=int, default=5, help="RSI smoothing EMA")
    ap.add_argument("--qqe-factor", type=float, default=4.238)
    ap.add_argument("--threshold", type=int, default=10)
    ap.add_argument("--min-bars", type=int, default=60, help="Minimum bars for QQE")

    # Misc
    ap.add_argument("--dry-run", action="store_true", help="Skip Telegram signal summary (startup test still sent)")

    args = ap.parse_args()

    run(
        db_path=args.db,
        timeout=args.timeout,
        update_symbols_flag=args.update_symbols,
        allow_scrape=args.allow_scrape,
        update_only=args.update_only,
        enable_all=args.enable_all,
        disable_all=args.disable_all,
        enable_file=args.enable_file,
        disable_file=args.disable_file,
        symbol_only=args.symbol,
        period=args.period,
        rsi_period=args.rsi_period,
        sf=args.sf,
        qqe_factor=args.qqe_factor,
        threshold=args.threshold,
        min_bars=args.min_bars,
        dry_run=args.dry_run,
    )

if __name__ == "__main__":
    main()

