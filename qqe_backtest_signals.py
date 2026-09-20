# qqe_backtest_signals.py
from __future__ import annotations

import argparse
import sqlite3
from typing import List, Dict, Any
import math

import numpy as np
import pandas as pd


# ---------------- SQLite I/O ----------------

def db_connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path)

def load_symbols(con: sqlite3.Connection, enabled_only: bool) -> List[str]:
    q = "SELECT symbol FROM symbols WHERE enabled=1 ORDER BY symbol" if enabled_only \
        else "SELECT symbol FROM symbols ORDER BY symbol"
    return [r[0] for r in con.execute(q).fetchall()]

def load_symbol_industry(con: sqlite3.Connection) -> Dict[str, str | None]:
    return {sym: ind for sym, ind in con.execute("SELECT symbol, industry FROM symbols").fetchall()}

def load_bars(con: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    rows = con.execute(
        "SELECT date, close FROM bars WHERE symbol=? ORDER BY date", (symbol,)
    ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["close"])
    df = pd.DataFrame(rows, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["close"])

# *** FIX: Added the missing load_bars_full function ***
def load_bars_full(con: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    """Loads all OHLCV columns for a symbol."""
    # Note: The 'open' column is missing from the 'bars' table DDL in stocks.py
    # We will synthesize it from the previous day's close.
    rows = con.execute(
        "SELECT date, close, high, low, volume FROM bars WHERE symbol=? ORDER BY date", (symbol,)
    ).fetchall()
    
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        
    df = pd.DataFrame(rows, columns=["date", "close", "high", "low", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    
    # Synthesize 'open' from previous 'close'
    df["open"] = df["close"].shift(1)
    
    # Fill the first 'open' with the first 'close' (or 'low' if more conservative)
    if not df.empty:
        df.iloc[0, df.columns.get_loc('open')] = df.iloc[0]['close']
    
    # Ensure numeric
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if col == "volume":
            df[col] = df[col].fillna(0) # Volume can be 0
        
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


# ---------------- QQE (exact Pine mapping) ----------------

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def compute_qqe_pine_equiv(
    closes: pd.Series,
    rsi_period: int = 14,
    sf: int = 5,
    qqe_factor: float = 4.238,
    threshold: int = 10,
) -> pd.DataFrame:
    # ta.rsi (Wilder’s RSI)
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta.clip(upper=0.0))
    alpha = 1.0 / float(rsi_period)      # Wilder RMA
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    rsi_val = rsi_val.fillna(0.0)

    # rsi_ma = ta.ema(rsi_val, sf)
    rsi_ma = ema(rsi_val, sf)

    # wilders_period = rsi_period * 2 - 1
    wilders_period = rsi_period * 2 - 1

    # atr_rsi = abs(rsi_ma[1] - rsi_ma)
    atr_rsi = (rsi_ma.shift(1) - rsi_ma).abs()

    # ma_atr_rsi = ta.ema(atr_rsi, wilders_period)
    ma_atr_rsi = ema(atr_rsi, wilders_period)

    # dar = ta.ema(ma_atr_rsi, wilders_period) * qqe_factor
    dar = ema(ma_atr_rsi, wilders_period) * qqe_factor

    # Bands + trend (vectorized with explicit previous references)
    rs_index = rsi_ma
    n = len(rs_index)
    longband = np.zeros(n)
    shortband = np.zeros(n)
    trend = np.zeros(n, dtype=int)

    rs_np = rs_index.to_numpy()
    dar_np = dar.to_numpy()

    # Choose first valid index (Pine starts with var = 0.0; our first update will behave the same)
    start = int(np.argmax(~np.isnan(rs_np)))
    if start >= n or np.isnan(rs_np[start]):
        out = pd.DataFrame(index=closes.index)
        out["rsi_val"] = rsi_val
        out["rsi_ma"] = rsi_ma
        out["longband"] = np.nan
        out["shortband"] = np.nan
        out["fast_tl"] = np.nan
        out["signal"] = 0
        return out

    longband[start] = rs_np[start] - (0.0 if np.isnan(dar_np[start]) else dar_np[start])
    shortband[start] = rs_np[start] + (0.0 if np.isnan(dar_np[start]) else dar_np[start])
    trend[start] = 0  # nz(trend[1], 1) has no prior; we keep 0 and resolve next step

    for i in range(start + 1, n):
        rsi_i = rs_np[i]
        prev_lb = longband[i - 1]
        prev_sb = shortband[i - 1]
        prev_rs = rs_np[i - 1]
        d_i = 0.0 if np.isnan(dar_np[i]) else float(dar_np[i])

        # new bands
        newlongband = rsi_i - d_i
        newshortband = rsi_i + d_i

        # longband := rs_index[1] > longband[1] and rs_index > longband[1] ? max(longband[1], newlongband) : newlongband
        longband[i] = max(prev_lb, newlongband) if (prev_rs > prev_lb and rsi_i > prev_lb) else newlongband

        # shortband := rs_index[1] < shortband[1] and rs_index < shortband[1] ? min(shortband[1], newshortband) : newshortband
        shortband[i] = min(prev_sb, newshortband) if (prev_rs < prev_sb and rsi_i < prev_sb) else newshortband

        # trend := cross(rs_index, shortband[1]) ? 1 : cross(rs_index, longband[1]) ? -1 : nz(trend[1], 1)
        cross_up = (prev_rs <= prev_sb) and (rsi_i > prev_sb)
        cross_dn = (prev_rs >= prev_lb) and (rsi_i < prev_lb)
        if cross_up:
            trend[i] = 1
        elif cross_dn:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1] if trend[i - 1] != 0 else 1

    # fast_atr_rsi_tl = trend == 1 ? longband : shortband
    fast_tl = np.where(trend == 1, longband, shortband)

    # qqexlong/qqexshort counters
    qqexlong = np.zeros(n, dtype=int)
    qqexshort = np.zeros(n, dtype=int)
    for i in range(start, n):
        qqexlong[i] = (qqexlong[i - 1] + 1) if (i > 0 and fast_tl[i] < rs_np[i]) else (1 if fast_tl[i] < rs_np[i] else 0)
        qqexshort[i] = (qqexshort[i - 1] + 1) if (i > 0 and fast_tl[i] > rs_np[i]) else (1 if fast_tl[i] > rs_np[i] else 0)

    # qqe_long_val = fast_tl[1] - 50 ; qqe_short_val = fast_tl[1] - 50
    ft_prev = np.concatenate(([np.nan], fast_tl[:-1]))
    gate_val = ft_prev - 50.0

    # qqe_long / qqe_short as in Pine
    is_long = (qqexlong == 1) & (gate_val <= -float(threshold))
    is_short = (qqexshort == 1) & (gate_val >=  float(threshold))

    signal = np.where(is_long, 1, np.where(is_short, -1, 0))

    out = pd.DataFrame(index=closes.index)
    out["rsi_val"] = rsi_val
    out["rsi_ma"] = rsi_ma
    out["longband"] = longband
    out["shortband"] = shortband
    out["fast_tl"] = fast_tl
    out["signal"] = signal
    return out


# ---------------- Backtest extraction ----------------

def extract_events(df: pd.DataFrame) -> pd.DataFrame:
    # keep only bars where Pine gate fires (signal != 0)
    events = df[df["signal"] != 0].copy()
    events["side"] = events["signal"].map({1: "LONG", -1: "SHORT"})
    return events

def add_forward_returns(closes: pd.Series, events: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    out = events.copy()
    for h in horizons:
        fwd = closes.shift(-h)
        out[f"close_t+{h}"] = fwd.reindex(out.index)
        # signed return so LONG positive if price rises; SHORT positive if price falls
        out[f"ret_{h}d"] = (out[f"close_t+{h}"] / out["close"] - 1.0) * np.sign(out["signal"])
    return out


# ---------------- Orchestration (Quick Backtest) ----------------

def parse_horizons(text: str) -> List[int]:
    return [int(x) for x in text.split(",")] if text else [5, 10, 20]

def run_backtest_signals(
    con: sqlite3.Connection,
    symbols: List[str],
    per_symbol: bool,
    count: int,
    rsi_period: int,
    sf: int,
    qqe_factor: float,
    threshold: int,
    horizons: List[int],
) -> pd.DataFrame:
    """
    Core backtest logic, refactored to be callable and return a DataFrame.
    """
    if not symbols:
        print("No symbols found for backtest.")
        return pd.DataFrame()

    ind_map = load_symbol_industry(con)
    all_rows: List[pd.DataFrame] = []

    for sym in symbols:
        bars = load_bars(con, sym) # Uses only 'close'
        if bars.empty or len(bars) < max(30, rsi_period * 4):
            continue

        qqe = compute_qqe_pine_equiv(
            bars["close"],
            rsi_period=rsi_period,
            sf=sf,
            qqe_factor=qqe_factor,
            threshold=threshold,
        )
        df = pd.concat([bars, qqe], axis=1).dropna(subset=["close"])
        events = extract_events(df)
        if events.empty:
            continue

        events["symbol"] = sym
        events["industry"] = ind_map.get(sym)
        events = add_forward_returns(df["close"], events, horizons)

        if per_symbol:
            events = events.sort_index(ascending=False).head(count).sort_index()

        all_rows.append(events)

    if not all_rows:
        print("No signals produced with current settings.")
        return pd.DataFrame()

    merged = pd.concat(all_rows).sort_index()
    if not per_symbol:
        merged = merged.sort_index(ascending=False).head(count).sort_index()

    cols = (
        ["symbol", "industry", "side", "close", "rsi_ma", "fast_tl", "signal"]
        + [c for c in merged.columns if c.startswith("close_t+")]
        + [c for c in merged.columns if c.startswith("ret_")]
    )
    # Ensure columns exist before trying to select them
    final_cols = [c for c in cols if c in merged.columns]
    merged = merged[final_cols]
    
    merged.index.name = "date"
    return merged

# ---------------- Full Backtest Engine (New) ----------------

def run_full_backtest(bars_df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs a full vector-based backtest on a single symbol.
    """
    # 1. Get parameters
    initial_capital = params.get("initial_capital", 100000)
    commission_pct = params.get("commission_pct", 0.001)
    stop_loss_pct = params.get("stop_loss_pct", 0)
    take_profit_pct = params.get("take_profit_pct", 0)
    
    # 2. Generate QQE signals
    qqe_df = compute_qqe_pine_equiv(
        bars_df["close"],
        rsi_period=params.get("rsi_period", 14),
        sf=params.get("sf", 5),
        qqe_factor=params.get("qqe_factor", 4.238),
        threshold=params.get("threshold", 10),
    )
    
    df = pd.concat([bars_df, qqe_df], axis=1)
    df = df.dropna(subset=["close", "fast_tl"])
    df['date'] = df.index
    
    # 3. Simulate trades
    equity = initial_capital
    position = 0 # 0 = flat, 1 = long, -1 = short
    entry_price = 0.0
    entry_date = pd.NaT
    entry_equity = 0.0
    trades = []
    equity_curve = [{"date": df.index[0], "equity": initial_capital}]
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        
        # Check for exit conditions first
        if position == 1: # We are long
            exit_reason = None
            exit_price = 0.0
            
            # Check for SL/TP hits (simulating intrabar)
            sl_price = entry_price * (1 - stop_loss_pct)
            tp_price = entry_price * (1 + take_profit_pct)

            if stop_loss_pct > 0 and row['low'] <= sl_price:
                exit_reason = "Stop Loss"
                exit_price = sl_price # Assume SL price hit
            elif take_profit_pct > 0 and row['high'] >= tp_price:
                exit_reason = "Take Profit"
                exit_price = tp_price # Assume TP price hit
            elif row['signal'] == -1: # Opposite signal
                exit_reason = "Signal Exit"
                exit_price = row['open'] # Exit on next bar open

            if exit_reason:
                ret = (exit_price / entry_price) - 1
                equity_change = entry_equity * (1 + ret) * (1 - commission_pct) - entry_equity
                equity += equity_change
                
                trades.append({
                    "entry_date": entry_date, "exit_date": row['date'], "side": "Long",
                    "entry_price": entry_price, "exit_price": exit_price,
                    "return_pct": ret * 100, "pnl": equity_change, "exit_reason": exit_reason
                })
                position = 0

        elif position == -1: # We are short
            exit_reason = None
            exit_price = 0.0
            
            sl_price = entry_price * (1 + stop_loss_pct)
            tp_price = entry_price * (1 - take_profit_pct)

            if stop_loss_pct > 0 and row['high'] >= sl_price:
                exit_reason = "Stop Loss"
                exit_price = sl_price
            elif take_profit_pct > 0 and row['low'] <= tp_price:
                exit_reason = "Take Profit"
                exit_price = tp_price
            elif row['signal'] == 1: # Opposite signal
                exit_reason = "Signal Exit"
                exit_price = row['open']

            if exit_reason:
                ret = (entry_price / exit_price) - 1
                equity_change = entry_equity * (1 + ret) * (1 - commission_pct) - entry_equity
                equity += equity_change
                
                trades.append({
                    "entry_date": entry_date, "exit_date": row['date'], "side": "Short",
                    "entry_price": entry_price, "exit_price": exit_price,
                    "return_pct": ret * 100, "pnl": equity_change, "exit_reason": exit_reason
                })
                position = 0

        # Check for entry conditions
        if position == 0:
            if row['signal'] == 1: # Go long
                position = 1
                entry_price = row['open'] # Enter on next bar open
                entry_date = row['date']
                entry_equity = equity * (1 - commission_pct) # Apply commission on entry
                equity = entry_equity
            elif row['signal'] == -1: # Go short
                position = -1
                entry_price = row['open']
                entry_date = row['date']
                entry_equity = equity * (1 - commission_pct)
                equity = entry_equity
        
        # Update equity curve regardless of trade
        # If in position, mark equity to market
        current_equity = equity
        if position == 1:
            current_equity = entry_equity * (row['close'] / entry_price)
        elif position == -1:
            current_equity = entry_equity * (entry_price / row['close'])
            
        equity_curve.append({"date": row['date'], "equity": current_equity})

    # 4. Compile Report
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)

    # Calculate stats
    total_return = (equity_df['equity'].iloc[-1] / initial_capital - 1) * 100
    total_trades = len(trades_df)
    
    if total_trades > 0:
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] < 0]
        
        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0
        profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if losses['pnl'].sum() != 0 else float('inf')
        
        # Max Drawdown
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] / equity_df['peak']) - 1
        max_drawdown = equity_df['drawdown'].min() * 100
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
        max_drawdown = 0

    stats = {
        "Total Return (%)": f"{total_return:.2f}",
        "Total Trades": total_trades,
        "Win Rate (%)": f"{win_rate:.2f}",
        "Profit Factor": f"{profit_factor:.2f}" if profit_factor != float('inf') else "inf",
        "Avg. Win (LKR)": f"{avg_win:.2f}",
        "Avg. Loss (LKR)": f"{avg_loss:.2f}",
        "Max. Drawdown (%)": f"{max_drawdown:.2f}",
        "Final Equity (LKR)": f"{equity_df['equity'].iloc[-1]:.2f}",
    }
    
    # Ensure trades_df has correct dtypes for JSON conversion
    if not trades_df.empty:
        trades_df['entry_price'] = trades_df['entry_price'].astype(float)
        trades_df['exit_price'] = trades_df['exit_price'].astype(float)
        trades_df['return_pct'] = trades_df['return_pct'].astype(float)
        trades_df['pnl'] = trades_df['pnl'].astype(float)

    return {
        "stats": stats,
        "equity_curve": equity_df,
        "trades": trades_df
    }


# ---------------- CLI Wrapper (for original file) ----------------

def run_cli(
    db_path: str,
    symbol: str | None,
    enabled_only: bool,
    per_symbol: bool,
    count: int,
    rsi_period: int,
    sf: int,
    qqe_factor: float,
    threshold: int,
    horizons: List[int],
    out_csv: str,
) -> None:
    """
    The original function, now a CLI wrapper for run_backtest_signals.
    """
    con = db_connect(db_path)
    symbols_to_run = [symbol] if symbol else load_symbols(con, enabled_only=enabled_only)
    
    results = run_backtest_signals(
        con=con,
        symbols=symbols_to_run,
        per_symbol=per_symbol,
        count=count,
        rsi_period=rsi_period,
        sf=sf,
        qqe_factor=qqe_factor,
        threshold=threshold,
        horizons=horizons,
    )
    con.close()
    
    if results.empty:
        print("No signals produced with current settings.")
        return

    results.to_csv(out_csv)
    print(f"Saved {len(results)} rows to {out_csv}")


# ---------------- CLI ----------------

def main():
    ap = argparse.ArgumentParser(description="Backtest QQE signals identical to Pine logic using DB bars")
    ap.add_argument("--db", type=str, default="cse_signals.db", help="SQLite DB path")
    ap.add_argument("--symbol", type=str, default=None, help="Only this symbol (optional)")
    ap.add_argument("--enabled-only", action="store_true", help="Use only symbols with enabled=1")
    ap.add_argument("--per-symbol", action="store_true", help="Return N signals per symbol instead of N overall")
    ap.add_argument("--count", type=int, default=10, help="Number of signals to return")
    ap.add_argument("--horizons", type=str, default="5,10,20", help="Comma list of lookahead days for returns")
    ap.add_argument("--rsi-period", type=int, default=14)
    ap.add_argument("--sf", type=int, default=5)
    ap.add_argument("--qqe-factor", type=float, default=4.238)
    ap.add_argument("--threshold", type=int, default=10)
    ap.add_argument("--out", type=str, default="backtest_signals.csv")
    args = ap.parse_args()

    run_cli(
        db_path=args.db,
        symbol=args.symbol,
        enabled_only=args.enabled_only,
        per_symbol=args.per_symbol,
        count=args.count,
        rsi_period=args.rsi_period,
        sf=args.sf,
        qqe_factor=args.qqe_factor,
        threshold=args.threshold,
        horizons=parse_horizons(args.horizons),
        out_csv=args.out,
    )

if __name__ == "__main__":
    main()

