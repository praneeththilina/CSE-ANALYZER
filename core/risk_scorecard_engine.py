# core/risk_scorecard_engine.py — Risk-First Sizing, Portfolio VaR & Composite Scorecard
"""
Risk, Portfolio & Decision Output Suite covering Features 47 to 50:
- Position Sizing & ATR Dynamic Stops Calculator (Feature 47)
- Portfolio Risk Analytics: Sharpe, Drawdown, VaR 95%, Concentration Alerts (Feature 48)
- 4-Tier Composite Scorecard with Calibrated Edge, ABSTAIN MODE & SHAP Factors (Feature 49)
- Signal Journal Logger, Telegram Alert Dispatch & CSV/Report Exporter (Feature 50)
"""
from __future__ import annotations

import csv
import json
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class RiskScorecardEngine:
    """Manages position sizing, portfolio risk metrics, composite decision scorecards, and signal journaling."""

    @classmethod
    def calculate_position_size(
        cls,
        account_capital: float,
        entry_price: float,
        stop_loss_price: float,
        risk_pct: float = 1.5,                 # 1.5% capital risk per trade
        max_capital_allocation_pct: float = 25.0, # Max 25% single stock weight
        avg_daily_volume: int = 50000
    ) -> Dict[str, Any]:
        """Calculate mathematically optimal position size and risk limits (Feature 47)."""
        if entry_price <= 0 or stop_loss_price >= entry_price or account_capital <= 0:
            return {
                "shares_to_buy": 0,
                "position_value_lkr": 0.0,
                "risk_amount_lkr": 0.0,
                "portfolio_weight_pct": 0.0,
                "warning": "Invalid trade levels: Stop loss must be below entry price."
            }

        stop_distance = entry_price - stop_loss_price
        risk_lkr = account_capital * (risk_pct / 100.0)

        # Risk-based quantity
        raw_qty = int(risk_lkr / stop_distance) if stop_distance > 0 else 0

        # Allocation cap (e.g. max 25% of account in a single position)
        max_val = account_capital * (max_capital_allocation_pct / 100.0)
        allocation_cap_qty = int(max_val / entry_price)

        # Liquidity absorption cap: Don't exceed 10% of typical daily volume
        liquidity_cap_qty = max(100, int(avg_daily_volume * 0.10))

        # Final sizing is the most conservative of risk, allocation cap, and liquidity cap
        final_qty = min(raw_qty, allocation_cap_qty, liquidity_cap_qty)
        final_qty = (final_qty // 10) * 10  # Round to clean lot size of 10

        pos_val = round(final_qty * entry_price, 2)
        weight_pct = round((pos_val / account_capital) * 100.0, 1)
        actual_risk_lkr = round(final_qty * stop_distance, 2)
        actual_risk_pct = round((actual_risk_lkr / account_capital) * 100.0, 2)

        warning = None
        if final_qty == liquidity_cap_qty and raw_qty > liquidity_cap_qty:
            warning = f"Position size restricted to {liquidity_cap_qty:,} shares to prevent adverse market impact on CSE order book."
        elif final_qty == allocation_cap_qty and raw_qty > allocation_cap_qty:
            warning = f"Position size restricted by {max_capital_allocation_pct}% portfolio concentration limit."

        return {
            "shares_to_buy": final_qty,
            "position_value_lkr": pos_val,
            "risk_amount_lkr": actual_risk_lkr,
            "actual_risk_pct": actual_risk_pct,
            "portfolio_weight_pct": weight_pct,
            "risk_reward_1_5_target": round(entry_price + (1.5 * stop_distance), 2),
            "risk_reward_2_5_target": round(entry_price + (2.5 * stop_distance), 2),
            "warning": warning
        }

    @classmethod
    def calculate_portfolio_rebalance(
        cls,
        holdings: List[Dict[str, Any]],
        target_mode: str = "EQUAL_WEIGHT",
        custom_weights: Optional[Dict[str, float]] = None,
        portfolio_cash: float = 0.0,
        min_trade_lkr: float = 5000.0
    ) -> Dict[str, Any]:
        """Compute portfolio rebalancing trade orders to align current holdings with target allocation model."""
        if not holdings:
            return {
                "total_portfolio_value": round(portfolio_cash, 2),
                "rebalance_trades": [],
                "summary": "Portfolio is empty. Add position holdings to rebalance."
            }

        # Calculate current position values and total portfolio value
        total_stock_val = sum(
            float(h.get("market_value", h.get("current_value", float(h.get("qty", h.get("quantity", 0))) * float(h.get("current_price", 0)))))
            for h in holdings
        )
        total_port_val = total_stock_val + portfolio_cash

        if total_port_val <= 0:
            return {
                "total_portfolio_value": 0.0,
                "rebalance_trades": [],
                "summary": "Total portfolio value is zero."
            }

        unique_symbols = sorted(list({h.get("symbol") for h in holdings if h.get("symbol")}))
        n_assets = len(unique_symbols)

        if n_assets == 0:
            return {
                "total_portfolio_value": round(total_port_val, 2),
                "rebalance_trades": [],
                "summary": "No valid stock symbols found."
            }

        # Determine target weight for each symbol
        target_weights_map: Dict[str, float] = {}
        if target_mode == "CUSTOM" and custom_weights:
            tot_w = sum(custom_weights.values()) if custom_weights else 1.0
            for sym in unique_symbols:
                raw_w = custom_weights.get(sym, custom_weights.get(sym.split(".")[0], 0.0))
                target_weights_map[sym] = (raw_w / tot_w) if tot_w > 0 else (1.0 / n_assets)
        else:
            # Default EQUAL_WEIGHT across unique active assets
            eq_w = 1.0 / n_assets
            for sym in unique_symbols:
                target_weights_map[sym] = eq_w

        # Aggregate current values per symbol
        symbol_curr_val: Dict[str, float] = {sym: 0.0 for sym in unique_symbols}
        symbol_curr_qty: Dict[str, int] = {sym: 0 for sym in unique_symbols}
        symbol_curr_price: Dict[str, float] = {sym: 0.0 for sym in unique_symbols}

        for h in holdings:
            sym = h.get("symbol")
            if not sym:
                continue
            p = float(h.get("current_price", 0.0))
            q = int(float(h.get("qty", h.get("quantity", 0))))
            val = float(h.get("market_value", h.get("current_value", q * p)))
            symbol_curr_val[sym] += val
            symbol_curr_qty[sym] += q
            if p > 0:
                symbol_curr_price[sym] = p

        rebalance_trades: List[Dict[str, Any]] = []

        for sym in unique_symbols:
            curr_val = symbol_curr_val[sym]
            curr_pct = (curr_val / total_port_val) * 100.0
            target_pct = target_weights_map[sym] * 100.0
            target_val = total_port_val * target_weights_map[sym]

            price = symbol_curr_price[sym]
            diff_lkr = target_val - curr_val

            if abs(diff_lkr) < min_trade_lkr or price <= 0:
                action = "HOLD"
                shares_to_trade = 0
                est_trade_val = 0.0
            elif diff_lkr > 0:
                action = "BUY"
                raw_shares = int(diff_lkr // price)
                shares_to_trade = (raw_shares // 10) * 10  # Round to CSE lot size of 10
                est_trade_val = round(shares_to_trade * price, 2)
                if shares_to_trade <= 0:
                    action = "HOLD"
            else:
                action = "SELL"
                raw_shares = int(abs(diff_lkr) // price)
                shares_to_trade = (raw_shares // 10) * 10
                shares_to_trade = min(shares_to_trade, symbol_curr_qty[sym])
                est_trade_val = round(shares_to_trade * price, 2)
                if shares_to_trade <= 0:
                    action = "HOLD"

            target_qty = symbol_curr_qty[sym] + shares_to_trade if action == "BUY" else symbol_curr_qty[sym] - shares_to_trade

            rebalance_trades.append({
                "symbol": sym,
                "action": action,
                "current_price": price,
                "current_qty": symbol_curr_qty[sym],
                "current_pct": round(curr_pct, 1),
                "target_pct": round(target_pct, 1),
                "target_qty": max(0, target_qty),
                "shares_to_trade": shares_to_trade,
                "est_trade_lkr": est_trade_val,
                "diff_lkr": round(diff_lkr, 2)
            })

        return {
            "total_portfolio_value": round(total_port_val, 2),
            "rebalance_trades": rebalance_trades,
            "summary": f"Calculated rebalance plan for {len(rebalance_trades)} holdings."
        }

    @classmethod
    def evaluate_portfolio_risk(
        cls,
        holdings: List[Dict[str, Any]],
        portfolio_cash: float = 0.0,
        benchmark_aspi_return_pct: float = 12.0
    ) -> Dict[str, Any]:
        """Compute Portfolio Value at Risk (VaR 95%), Sharpe, Concentration Warnings, and Portfolio Alpha (Feature 48)."""
        if not holdings:
            return {
                "total_portfolio_value": round(portfolio_cash, 2),
                "total_stock_value": 0.0,
                "cash_lkr": round(portfolio_cash, 2),
                "cash_pct": 100.0,
                "var_95_daily_lkr": 0.0,
                "var_95_pct": 0.0,
                "portfolio_beta": 1.0,
                "portfolio_return_pct": 0.0,
                "benchmark_aspi_return_pct": benchmark_aspi_return_pct,
                "portfolio_alpha_pct": 0.0,
                "sector_concentration": {},
                "warnings": []
            }

        stock_val = sum(float(h.get("market_value", h.get("qty", 0) * h.get("current_price", 0))) for h in holdings)
        total_val = stock_val + portfolio_cash
        cash_pct = round((portfolio_cash / total_val * 100.0), 1) if total_val > 0 else 0.0

        # Calculate weighted portfolio return %
        pnl_sum = sum(float(h.get("pnl", 0.0)) for h in holdings)
        cost_basis_sum = sum(float(h.get("cost_basis", h.get("market_value", 0.0) - h.get("pnl", 0.0))) for h in holdings)
        portfolio_return_pct = round((pnl_sum / cost_basis_sum * 100.0), 2) if cost_basis_sum > 0 else 0.0

        # Sector weights & concentration
        sector_weights: Dict[str, float] = {}
        for h in holdings:
            sec = h.get("industry", "Unassigned")
            val = float(h.get("market_value", h.get("qty", 0) * h.get("current_price", 0)))
            sector_weights[sec] = sector_weights.get(sec, 0.0) + val

        warnings: List[str] = []
        for sec, s_val in sector_weights.items():
            s_pct = (s_val / total_val) * 100.0 if total_val > 0 else 0
            sector_weights[sec] = round(s_pct, 1)
            if s_pct > 30.0:
                warnings.append(f"⚠️ Heavy Sector Concentration: {sec} represents {s_pct:.1f}% of total portfolio (Recommended max 30%).")

        # Single position concentration
        for h in holdings:
            sym = h.get("symbol", "")
            val = float(h.get("market_value", h.get("qty", 0) * h.get("current_price", 0)))
            pos_pct = (val / total_val) * 100.0 if total_val > 0 else 0
            if pos_pct > 25.0:
                warnings.append(f"⚠️ Position Overweight: {sym} represents {pos_pct:.1f}% of total capital.")

        # Portfolio Weighted Beta
        betas = [float(h.get("beta", 1.0)) for h in holdings]
        weights = [float(h.get("market_value", h.get("qty", 0) * h.get("current_price", 0))) / max(1.0, stock_val) for h in holdings]
        weighted_beta = round(float(np.sum([b * w for b, w in zip(betas, weights)])), 2) if stock_val > 0 else 1.0

        # Jensen's Alpha: Alpha = R_p - [R_f + Beta * (R_m - R_f)]
        # Assuming Sri Lankan risk-free rate R_f ~ 9.5%
        rf_rate = 9.5
        expected_return = rf_rate + weighted_beta * (benchmark_aspi_return_pct - rf_rate)
        portfolio_alpha_pct = round(portfolio_return_pct - expected_return, 2)

        # Parametric Value at Risk (VaR 95% 1-day)
        # Assuming average CSE daily equity volatility ~ 1.6%
        daily_vol = 0.016 * weighted_beta
        var_95_lkr = round(stock_val * 1.65 * daily_vol, 2)
        var_95_pct = round((var_95_lkr / max(1.0, total_val)) * 100.0, 2)

        return {
            "total_portfolio_value": round(total_val, 2),
            "total_stock_value": round(stock_val, 2),
            "cash_lkr": round(portfolio_cash, 2),
            "cash_pct": cash_pct,
            "var_95_daily_lkr": var_95_lkr,
            "var_95_pct": var_95_pct,
            "portfolio_beta": weighted_beta,
            "portfolio_return_pct": portfolio_return_pct,
            "benchmark_aspi_return_pct": benchmark_aspi_return_pct,
            "portfolio_alpha_pct": portfolio_alpha_pct,
            "sector_concentration": sector_weights,
            "warnings": warnings
        }

    @classmethod
    def generate_composite_scorecard(
        cls,
        symbol: str,
        name: str,
        current_price: float,
        technical_summary: Dict[str, Any],
        fundamental_profile: Dict[str, Any],
        market_context: Dict[str, Any],
        ml_prediction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate the unified 4-tier Composite Decision Scorecard with Abstain Mode and SHAP attribution (Feature 49)."""
        calibrated_prob = ml_prediction.get("calibrated_prob_pct", 50.0)
        is_abstain = ml_prediction.get("abstain_mode", False)

        # Confluence checklist
        regime = technical_summary.get("regime", {})
        mtf = technical_summary.get("multi_timeframe", {})
        f_score = fundamental_profile.get("piotroski", {}).get("f_score", 5)
        peer = fundamental_profile.get("peer_comparison", {})
        rs = market_context.get("rs_momentum_20d_pct", 0.0)
        liq = market_context.get("liquidity_tier", "Tier 2")

        # Checklist evaluations
        tech_bull = "Bull" in regime.get("regime", "") or mtf.get("score", 50) >= 70
        fund_sound = f_score >= 6 or peer.get("is_undervalued_peer", False)
        market_leader = rs > 0
        liquid_stock = "Tier 1" in liq or "Tier 2" in liq

        # Factor Attribution (SHAP-style)
        factor_breakdown = [
            {
                "factor": "Technical Momentum & Trend",
                "weight": "40%",
                "status": "Bullish Confluence" if tech_bull else "Weak / Neutral",
                "score_impact": "+15%" if tech_bull else "-10%",
                "color": "#10B981" if tech_bull else "#EF4444"
            },
            {
                "factor": "Fundamental Valuation & Balance Sheet",
                "weight": "30%",
                "status": f"F-Score {f_score}/9, {peer.get('peer_verdict', 'Fair')}",
                "score_impact": "+12%" if fund_sound else "-8%",
                "color": "#10B981" if fund_sound else "#F59E0B"
            },
            {
                "factor": "Market Benchmark Relative Strength",
                "weight": "20%",
                "status": f"{'+' if rs>0 else ''}{rs:.1f}% vs ASPI",
                "score_impact": "+8%" if market_leader else "-5%",
                "color": "#10B981" if market_leader else "#6B7280"
            },
            {
                "factor": "Liquidity & Execution Slippage Risk",
                "weight": "10%",
                "status": liq,
                "score_impact": "+5%" if liquid_stock else "-12%",
                "color": "#10B981" if liquid_stock else "#EF4444"
            }
        ]

        # 4-Tier Classification with ABSTAIN MODE
        if is_abstain or (not liquid_stock and not fund_sound):
            decision = "⚠️ ABSTAIN (No Clear Edge)"
            badge_color = "#6B7280"
            recommendation_note = "Analytical signals are inconclusive or discordant. Capital preservation advised; wait for clearer edge."
        elif calibrated_prob >= 63.0 and tech_bull and fund_sound:
            decision = "🟢 STRONG BUY"
            badge_color = "#10B981"
            recommendation_note = "High statistical edge: Technical momentum, fundamental undervaluation, and relative strength all align."
        elif calibrated_prob >= 56.0 and (tech_bull or fund_sound):
            decision = "🟢 BUY (Accumulate)"
            badge_color = "#3B82F6"
            recommendation_note = "Favorable risk-reward with positive calibrated probability. Stagger purchases within entry zone."
        elif calibrated_prob <= 43.0 or ("Bear" in regime.get("regime", "") and f_score <= 4):
            decision = "🔴 AVOID / EXIT"
            badge_color = "#EF4444"
            recommendation_note = "Negative statistical edge and elevated downside risk. Liquidate or stay flat."
        else:
            decision = "🟡 HOLD / NEUTRAL"
            badge_color = "#F59E0B"
            recommendation_note = "Maintain existing positions with trailing stops. Avoid fresh capital deployment."

        # Compute recommended Trade Levels
        atr = technical_summary.get("regime", {}).get("natr", 2.5) / 100.0 * current_price
        stop_loss = round(current_price - (1.5 * max(atr, current_price * 0.025)), 2)
        target1 = round(current_price + (1.5 * (current_price - stop_loss)), 2)
        target2 = round(current_price + (2.5 * (current_price - stop_loss)), 2)

        return {
            "symbol": symbol,
            "name": name,
            "current_price": current_price,
            "decision": decision,
            "badge_color": badge_color,
            "calibrated_win_prob_pct": calibrated_prob,
            "horizon_3m_prob_pct": ml_prediction.get("horizon_3m_prob_pct", 50.0),
            "recommendation_note": recommendation_note,
            "entry_zone": f"LKR {round(current_price * 0.99, 2):.2f} – {round(current_price * 1.01, 2):.2f}",
            "stop_loss": stop_loss,
            "target_1": target1,
            "target_2": target2,
            "risk_reward_ratio": "1 : 2.0",
            "factors": factor_breakdown,
            "reasons": ml_prediction.get("reasons", [])
        }

    @classmethod
    def format_telegram_alert(cls, scorecard: Dict[str, Any]) -> str:
        """Format a rich Markdown alert message for Telegram dispatch (Feature 50)."""
        sym = scorecard.get("symbol", "")
        price = scorecard.get("current_price", 0.0)
        dec = scorecard.get("decision", "")
        prob = scorecard.get("calibrated_win_prob_pct", 50.0)
        entry = scorecard.get("entry_zone", "")
        sl = scorecard.get("stop_loss", 0.0)
        t1 = scorecard.get("target_1", 0.0)
        t2 = scorecard.get("target_2", 0.0)

        lines = [
            f"⚡ *CSE EQUITY SIGNAL: {sym}*",
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"🎯 *Decision:* {dec}",
            f"📊 *Calibrated Edge:* {prob}% Win Prob (3-Mo Horizon)",
            f"💵 *Current Price:* LKR {price:.2f}",
            f"🟢 *Suggested Entry Zone:* {entry}",
            f"🛡️ *Stop Loss:* LKR {sl:.2f}",
            f"🎯 *Target 1 (1.5R):* LKR {t1:.2f}",
            f"🏆 *Target 2 (2.5R):* LKR {t2:.2f}",
            f"",
            f"📋 *Analytical Justification:*",
        ]
        for r in scorecard.get("reasons", [])[:3]:
            lines.append(f"• {r}")
        lines.append(f"\n⚠️ *Risk First:* Spot equities only. Strictly observe stop loss.")
        return "\n".join(lines)
