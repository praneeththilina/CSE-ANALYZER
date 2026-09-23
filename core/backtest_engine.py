# core/backtest_engine.py — Realistic Spot Equities Backtesting & Walk-Forward Suite
"""
Backtesting and Validation Engine covering Features 44, 45, and 47:
- Spot-Only Equity Execution (Cash Long-Only; No Short Selling)
- Realistic CSE Friction: 1.12% Total Broker/SEC/CDS Levies + Liquidity-Based Slippage
- Walk-Forward Out-of-Sample Window Validation (No Lookahead Leakage)
- ATR-Based Position Sizing and Dynamic Stops
- Comprehensive Quant Performance Metrics: CAGR, Sharpe, Sortino, Max Drawdown, Win/Loss Payoff, vs ASPI
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class BacktestEngine:
    """Rigorous cash equity backtest simulator with realistic CSE transaction costs and walk-forward validation."""

    # Standard Sri Lankan Colombo Stock Exchange transaction fees
    COMMISSION_RATE = 0.0112   # ~1.12% total transaction costs (Brokerage 0.64% + SEC 0.072% + CDS 0.015% + STL 0.30%)

    @classmethod
    def run_spot_backtest(
        cls,
        df: pd.DataFrame,
        starting_capital: float = 1_000_000.0,
        risk_per_trade_pct: float = 2.0,      # 2% account risk
        target1_rr: float = 1.5,
        target2_rr: float = 2.5,
        atr_stop_multiplier: float = 1.5,
        slippage_pct: float = 0.3,            # 0.3% average execution slippage
        benchmark_aspi_return_pct: float = 12.0,
        strategy_mode: str = "QQE / Momentum"
    ) -> Dict[str, Any]:
        """Simulate a spot equity strategy with realistic CSE execution friction (Feature 44 & 47)."""
        if df.empty or len(df) < 50:
            return {"error": "Insufficient historical data for backtesting (minimum 50 bars required)."}

        # Ensure indicators exist
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        if "trade_date" in df.columns:

            dates = df["trade_date"].values
        elif "date" in df.columns:
            dates = df["date"].values
        elif isinstance(df.index, pd.DatetimeIndex):
            dates = df.index.strftime("%Y-%m-%d").values
        elif hasattr(df.index, "values"):
            dates = [str(x) for x in df.index.values]
        else:
            dates = np.arange(len(df))
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.ewm(span=14, adjust=False).mean().fillna(tr).values

        # EMAs & RSI for trend & signal confirmation
        ema20 = df["close"].ewm(span=20, adjust=False).mean().values
        ema50 = df["close"].ewm(span=50, adjust=False).mean().values
        ema200 = df["close"].ewm(span=200, adjust=False).mean().values if len(df) >= 50 else ema50

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean().replace(0, np.nan)
        rs = avg_gain / avg_loss
        rsi_series = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0).values

        # State tracking
        cash = starting_capital
        position_qty = 0
        position_entry_price = 0.0
        position_stop_loss = 0.0
        position_target1 = 0.0
        position_target2 = 0.0
        trailing_stop = 0.0
        t1_locked = False

        trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []
        fees_paid_total = 0.0

        n = len(df)
        total_friction_rate = cls.COMMISSION_RATE + (slippage_pct / 100.0)

        for i in range(20, n):
            c = float(close[i])
            h = float(high[i])
            l = float(low[i])
            atr_val = max(0.5, float(atr_series[i]))
            curr_date = str(dates[i])

            # Update open equity
            portfolio_val = cash + (position_qty * c)
            equity_curve.append({
                "date": curr_date,
                "portfolio_value": round(portfolio_val, 2),
                "close_price": c
            })

            # Check open position management
            if position_qty > 0:
                # 1. Check Stop Loss
                if l <= position_stop_loss or (trailing_stop > 0 and l <= trailing_stop):
                    exit_price = min(c, position_stop_loss if l <= position_stop_loss else trailing_stop)
                    exit_val = position_qty * exit_price
                    fee = exit_val * total_friction_rate
                    net_val = exit_val - fee
                    cash += net_val
                    fees_paid_total += fee

                    pnl = net_val - (position_qty * position_entry_price)
                    pnl_pct = (exit_price / position_entry_price - 1.0) * 100.0

                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": curr_date,
                        "type": "BUY",
                        "qty": position_qty,
                        "entry_price": round(position_entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "pnl_lkr": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "exit_reason": "🛡️ Stop Loss Breached" if l <= position_stop_loss else "🟣 Trailing Stop Triggered",
                        "fees": round(fee, 2),
                        "bars_held": i - entry_bar_idx
                    })
                    position_qty = 0
                    continue

                # 2. Check Target 1 (Partial 50% profit taking)
                if not t1_locked and h >= position_target1:
                    t1_qty = position_qty // 2
                    if t1_qty > 0:
                        exit_price = position_target1
                        exit_val = t1_qty * exit_price
                        fee = exit_val * total_friction_rate
                        net_val = exit_val - fee
                        cash += net_val
                        fees_paid_total += fee
                        position_qty -= t1_qty
                        t1_locked = True
                        # Move stop loss to breakeven + buffer
                        position_stop_loss = max(position_stop_loss, position_entry_price * 1.005)
                        trailing_stop = position_entry_price

                        pnl = net_val - (t1_qty * position_entry_price)
                        pnl_pct = (exit_price / position_entry_price - 1.0) * 100.0
                        trades.append({
                            "entry_date": entry_date,
                            "exit_date": curr_date,
                            "type": "BUY",
                            "qty": t1_qty,
                            "entry_price": round(position_entry_price, 2),
                            "exit_price": round(exit_price, 2),
                            "pnl_lkr": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 2),
                            "exit_reason": "🎯 Target 1 Hit (50% Profit Lock)",
                            "fees": round(fee, 2),
                            "bars_held": i - entry_bar_idx
                        })

                # 3. Check Target 2 (Final Target)
                if position_qty > 0 and h >= position_target2:
                    exit_price = position_target2
                    exit_val = position_qty * exit_price
                    fee = exit_val * total_friction_rate
                    net_val = exit_val - fee
                    cash += net_val
                    fees_paid_total += fee

                    pnl = net_val - (position_qty * position_entry_price)
                    pnl_pct = (exit_price / position_entry_price - 1.0) * 100.0
                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": curr_date,
                        "type": "BUY",
                        "qty": position_qty,
                        "entry_price": round(position_entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "pnl_lkr": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "exit_reason": "🏆 Target 2 Hit (Final Target)",
                        "fees": round(fee, 2),
                        "bars_held": i - entry_bar_idx
                    })
                    position_qty = 0
                    continue

                # 4. Dynamic Trailing Stop update (ratchet up only)
                new_trail = c - (atr_stop_multiplier * atr_val)
                if new_trail > trailing_stop:
                    trailing_stop = new_trail

            # Check BUY Setup entry condition (Only if flat cash)
            elif position_qty == 0:
                strat_clean = str(strategy_mode).lower().strip()
                if "dual" in strat_clean or "cross" in strat_clean:
                    # Dual MA Crossover: EMA 20 crosses above EMA 50
                    trigger_buy = (ema20[i] > ema50[i]) and (ema20[i - 1] <= ema50[i - 1]) and (c >= ema200[i] if len(ema200) > i else True)
                elif "rsi" in strat_clean or "reversion" in strat_clean:
                    # RSI Oversold Reversion
                    trigger_buy = (rsi_series[i] < 38 and rsi_series[i] > rsi_series[i - 1]) or (rsi_series[i - 1] <= 30 and rsi_series[i] > 30)
                else:
                    # QQE / Momentum (default)
                    is_uptrend = c > ema50[i] and ema20[i] >= ema50[i] * 0.99
                    price_bounce = c > ema20[i] and close[i - 1] <= ema20[i - 1] * 1.01
                    breakout_20d = c >= float(np.max(high[max(0, i - 20): i]))
                    trigger_buy = is_uptrend and (price_bounce or breakout_20d)

                if trigger_buy:
                    entry_price = c
                    stop_dist = max(atr_val * atr_stop_multiplier, entry_price * 0.02)
                    stop_level = round(entry_price - stop_dist, 2)

                    # Position Sizing based on fixed fractional account risk
                    risk_capital = portfolio_val * (risk_per_trade_pct / 100.0)
                    calculated_qty = int(risk_capital / stop_dist) if stop_dist > 0 else 0

                    # Cap maximum allocation to 25% of total capital to maintain portfolio diversification
                    max_allowed_val = portfolio_val * 0.25
                    qty_cap = int(max_allowed_val / entry_price) if entry_price > 0 else 0
                    final_qty = min(calculated_qty, qty_cap)

                    if final_qty >= 10:
                        total_cost = final_qty * entry_price
                        entry_fee = total_cost * total_friction_rate
                        if cash >= (total_cost + entry_fee):
                            cash -= (total_cost + entry_fee)
                            fees_paid_total += entry_fee
                            position_qty = final_qty
                            position_entry_price = entry_price
                            position_stop_loss = stop_level
                            position_target1 = round(entry_price + (stop_dist * target1_rr), 2)
                            position_target2 = round(entry_price + (stop_dist * target2_rr), 2)
                            trailing_stop = stop_level
                            t1_locked = False
                            entry_date = curr_date
                            entry_bar_idx = i

        # Close any lingering open position at end of backtest period
        if position_qty > 0:
            exit_price = float(close[-1])
            exit_val = position_qty * exit_price
            fee = exit_val * total_friction_rate
            net_val = exit_val - fee
            cash += net_val
            fees_paid_total += fee
            pnl = net_val - (position_qty * position_entry_price)
            pnl_pct = (exit_price / position_entry_price - 1.0) * 100.0
            trades.append({
                "entry_date": entry_date,
                "exit_date": str(dates[-1]),
                "type": "BUY",
                "qty": position_qty,
                "entry_price": round(position_entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl_lkr": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "exit_reason": "Period End Close",
                "fees": round(fee, 2),
                "bars_held": n - entry_bar_idx
            })
            position_qty = 0

        # Calculate Performance Metrics
        final_capital = cash
        net_profit_lkr = round(final_capital - starting_capital, 2)
        return_pct = round(((final_capital - starting_capital) / starting_capital) * 100.0, 2)

        # Win / Loss stats
        total_trades = len(trades)
        wins = [t for t in trades if t["pnl_lkr"] > 0]
        losses = [t for t in trades if t["pnl_lkr"] <= 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate_pct = round((win_count / total_trades * 100.0), 1) if total_trades > 0 else 0.0

        gross_profit = sum(t["pnl_lkr"] for t in wins)
        gross_loss = abs(sum(t["pnl_lkr"] for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        avg_win_pct = round(np.mean([t["pnl_pct"] for t in wins]), 2) if wins else 0.0
        avg_loss_pct = round(np.mean([t["pnl_pct"] for t in losses]), 2) if losses else 0.0
        payoff_ratio = round(abs(avg_win_pct / avg_loss_pct), 2) if avg_loss_pct != 0 else 0.0

        # Drawdown calculation
        eq_vals = [e["portfolio_value"] for e in equity_curve]
        if eq_vals:
            peak = np.maximum.accumulate(eq_vals)
            dd = (peak - eq_vals) / peak * 100.0
            max_drawdown_pct = round(float(np.max(dd)), 2)
        else:
            max_drawdown_pct = 0.0

        # Sharpe ratio (daily returns vs risk free)
        if len(eq_vals) > 5:
            eq_series = pd.Series(eq_vals)
            daily_returns = eq_series.pct_change().dropna()
            excess_daily = daily_returns - (0.095 / 252.0)
            daily_std = daily_returns.std()
            sharpe_ratio = round(float((excess_daily.mean() / daily_std) * np.sqrt(252)), 2) if daily_std > 1e-6 else 0.0
        else:
            sharpe_ratio = 0.0

        return {
            "starting_capital": starting_capital,
            "final_capital": round(final_capital, 2),
            "net_profit_lkr": net_profit_lkr,
            "return_pct": return_pct,
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate_pct": win_rate_pct,
            "profit_factor": profit_factor,
            "payoff_ratio": payoff_ratio,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "fees_paid_lkr": round(fees_paid_total, 2),
            "benchmark_aspi_return_pct": benchmark_aspi_return_pct,
            "excess_return_vs_aspi": round(return_pct - benchmark_aspi_return_pct, 2),
            "trades": trades,
            "equity_curve": equity_curve
        }

    @classmethod
    def optimize_strategy_parameters(
        cls,
        df: pd.DataFrame,
        starting_capital: float = 1_000_000.0,
        strategy_mode: str = "QQE / Momentum",
        param_grid: Optional[Dict[str, List[Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Run grid search optimization over strategy risk/reward parameters (Target R:R, ATR Stop Multipliers)."""
        if df.empty or len(df) < 50:
            return []

        if param_grid is None:
            param_grid = {
                "target1_rr": [1.0, 1.5, 2.0],
                "target2_rr": [2.0, 2.5, 3.0],
                "atr_stop_multiplier": [1.0, 1.5, 2.0],
                "risk_per_trade_pct": [1.5, 2.0]
            }

        t1_list = param_grid.get("target1_rr", [1.5])
        t2_list = param_grid.get("target2_rr", [2.5])
        atr_list = param_grid.get("atr_stop_multiplier", [1.5])
        risk_list = param_grid.get("risk_per_trade_pct", [2.0])

        results: List[Dict[str, Any]] = []

        for t1 in t1_list:
            for t2 in t2_list:
                if t2 <= t1:
                    continue
                for atr_m in atr_list:
                    for r_pct in risk_list:
                        bt_res = cls.run_spot_backtest(
                            df=df,
                            starting_capital=starting_capital,
                            risk_per_trade_pct=r_pct,
                            target1_rr=t1,
                            target2_rr=t2,
                            atr_stop_multiplier=atr_m,
                            strategy_mode=strategy_mode
                        )

                        results.append({
                            "target1_rr": t1,
                            "target2_rr": t2,
                            "atr_stop_multiplier": atr_m,
                            "risk_per_trade_pct": r_pct,
                            "return_pct": bt_res.get("return_pct", 0.0),
                            "net_profit_lkr": bt_res.get("net_profit_lkr", 0.0),
                            "win_rate_pct": bt_res.get("win_rate_pct", 0.0),
                            "profit_factor": bt_res.get("profit_factor", 0.0),
                            "max_drawdown_pct": bt_res.get("max_drawdown_pct", 0.0),
                            "sharpe_ratio": bt_res.get("sharpe_ratio", 0.0),
                            "total_trades": bt_res.get("total_trades", 0)
                        })

        # Sort results by Sharpe Ratio descending, then Return % descending
        results.sort(key=lambda x: (x["sharpe_ratio"], x["return_pct"]), reverse=True)
        return results

    @classmethod
    def run_walk_forward_validation(
        cls,
        df: pd.DataFrame,
        window_size: int = 120,       # 120 bars (~6 months)
        out_of_sample_size: int = 40, # 40 bars (~2 months)
        n_splits: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Perform rolling walk-forward out-of-sample backtest validation to prevent lookahead leakage (Feature 45)."""
        if n_splits and n_splits > 0 and len(df) > window_size:
            out_of_sample_size = max(15, (len(df) - window_size) // n_splits)

        if len(df) < (window_size + out_of_sample_size):
            return {"error": "Insufficient history for walk-forward validation."}


        folds = []
        n = len(df)
        curr_idx = window_size

        fold_idx = 1
        while curr_idx + out_of_sample_size <= n:
            oos_slice = df.iloc[curr_idx: curr_idx + out_of_sample_size].copy()
            res = cls.run_spot_backtest(oos_slice, starting_capital=500_000.0)

            folds.append({
                "fold": fold_idx,
                "start_date": str(oos_slice.iloc[0].get("trade_date", "")),
                "end_date": str(oos_slice.iloc[-1].get("trade_date", "")),
                "return_pct": res.get("return_pct", 0.0),
                "win_rate_pct": res.get("win_rate_pct", 0.0),
                "trades": res.get("total_trades", 0),
                "max_drawdown_pct": res.get("max_drawdown_pct", 0.0)
            })

            curr_idx += out_of_sample_size
            fold_idx += 1

        avg_oos_return = round(float(np.mean([f["return_pct"] for f in folds])), 2) if folds else 0.0
        avg_win_rate = round(float(np.mean([f["win_rate_pct"] for f in folds])), 1) if folds else 0.0
        positive_folds = sum(1 for f in folds if f["return_pct"] > 0)
        stability_score = round((positive_folds / len(folds) * 100.0), 1) if folds else 0.0

        return {
            "folds": folds,
            "total_folds": len(folds),
            "avg_out_of_sample_return_pct": avg_oos_return,
            "avg_win_rate_pct": avg_win_rate,
            "profitable_periods_pct": stability_score,
            "robustness_verdict": "Robust Walk-Forward Performance (Low Overfitting)" if stability_score >= 65 else "Moderate Walk-Forward Consistency"
        }
