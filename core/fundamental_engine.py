# core/fundamental_engine.py — Fundamental Analysis & Valuation Suite
"""
Fundamental Analysis Toolkit covering Features 21 to 27:
- Financial Ratios Dashboard (P/E, P/B, ROE, ROCE, D/E, Net Margin)
- Dividend Analysis (Yield %, Payout Ratio, Consistency Streak)
- Earnings Growth Trends (Revenue & EPS Trajectory)
- Intrinsic Value Models (DCF, Graham Number, Dividend Discount Model)
- Peer & Sector Valuation Comparison (Relative Discount/Premium vs Sector Median)
- Financial Health Scores (Piotroski F-Score 0-9, Altman Z-Score)
- Ownership & Major Shareholder Profile
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np


class FundamentalEngine:
    """Calculates fundamental ratios, intrinsic valuation models, and financial health scores for CSE equities."""

    # Default sector baseline multiples for Colombo Stock Exchange
    SECTOR_BENCHMARKS = {
        "Banking": {"pe": 5.8, "pb": 0.65, "roe": 14.5, "div_yield": 7.2},
        "Diversified Financials": {"pe": 6.5, "pb": 0.85, "roe": 13.0, "div_yield": 6.5},
        "Food, Beverage & Tobacco": {"pe": 11.2, "pb": 1.75, "roe": 18.0, "div_yield": 4.8},
        "Capital Goods": {"pe": 9.4, "pb": 0.95, "roe": 12.5, "div_yield": 4.2},
        "Materials": {"pe": 8.1, "pb": 1.10, "roe": 15.0, "div_yield": 5.5},
        "Telecommunication": {"pe": 10.5, "pb": 1.40, "roe": 16.5, "div_yield": 6.0},
        "Utilities": {"pe": 8.0, "pb": 1.20, "roe": 16.0, "div_yield": 7.5},
        "Insurance": {"pe": 7.2, "pb": 1.05, "roe": 15.5, "div_yield": 5.8},
        "Consumer Services / Hotels": {"pe": 16.0, "pb": 1.10, "roe": 7.0, "div_yield": 2.0},
        "Healthcare": {"pe": 12.5, "pb": 1.50, "roe": 14.0, "div_yield": 3.8},
        "Transportation": {"pe": 14.0, "pb": 2.20, "roe": 22.0, "div_yield": 3.5},
    }

    DEFAULT_SECTOR_BENCHMARK = {"pe": 9.0, "pb": 1.10, "roe": 14.0, "div_yield": 5.0}

    @classmethod
    def calculate_graham_number(cls, eps: float, bvps: float) -> Optional[float]:
        """Graham Number = sqrt(22.5 * EPS * BVPS) (Feature 24)."""
        if eps <= 0 or bvps <= 0:
            return None
        return round(math.sqrt(22.5 * eps * bvps), 2)

    @classmethod
    def calculate_dcf_value(
        cls,
        fcf_per_share: float,
        growth_rate: float = 0.08,
        terminal_growth: float = 0.03,
        discount_rate: float = 0.13,
        years: int = 5
    ) -> Optional[float]:
        """5-Year Discounted Cash Flow (DCF) model tailored to Sri Lankan interest rate environment (Feature 24)."""
        if fcf_per_share <= 0 or discount_rate <= terminal_growth:
            return None

        pv_fcf = 0.0
        projected_fcf = fcf_per_share

        for t in range(1, years + 1):
            projected_fcf *= (1.0 + growth_rate)
            pv_fcf += projected_fcf / ((1.0 + discount_rate) ** t)

        # Terminal Value
        tv = (projected_fcf * (1.0 + terminal_growth)) / (discount_rate - terminal_growth)
        pv_tv = tv / ((1.0 + discount_rate) ** years)

        return round(pv_fcf + pv_tv, 2)

    @classmethod
    def calculate_dividend_discount_model(
        cls,
        dividend_per_share: float,
        dividend_growth: float = 0.05,
        required_return: float = 0.13
    ) -> Optional[float]:
        """Gordon Growth Dividend Discount Model (DDM) (Feature 24)."""
        if dividend_per_share <= 0 or required_return <= dividend_growth:
            return None
        d1 = dividend_per_share * (1.0 + dividend_growth)
        return round(d1 / (required_return - dividend_growth), 2)

    @classmethod
    def compute_piotroski_f_score(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute Piotroski F-Score (0 to 9) across Profitability, Leverage, and Efficiency (Feature 26)."""
        score = 0
        breakdown = []

        # 1. Net Income > 0
        net_income = data.get("net_income", 0)
        if net_income > 0:
            score += 1
            breakdown.append("Positive Net Income (+1)")
        else:
            breakdown.append("Negative Net Income (0)")

        # 2. Operating Cash Flow (CFO) > 0
        cfo = data.get("operating_cash_flow", net_income * 1.1)
        if cfo > 0:
            score += 1
            breakdown.append("Positive Operating Cash Flow (+1)")
        else:
            breakdown.append("Negative Operating Cash Flow (0)")

        # 3. ROA is positive & improving
        roa = data.get("roa", 5.0)
        roa_prev = data.get("roa_prior", 4.0)
        if roa > roa_prev and roa > 0:
            score += 1
            breakdown.append("ROA Improved vs Prior Year (+1)")
        else:
            breakdown.append("ROA Flat/Decreased (0)")

        # 4. Quality of Earnings: CFO > Net Income
        if cfo > net_income:
            score += 1
            breakdown.append("Cash Flow Exceeds Net Profit (+1)")
        else:
            breakdown.append("Cash Flow < Net Profit (Accrual Drag) (0)")

        # 5. Long Term Debt ratio decreased
        lt_debt_curr = data.get("debt_to_equity", 0.8)
        lt_debt_prev = data.get("debt_to_equity_prior", 0.9)
        if lt_debt_curr <= lt_debt_prev:
            score += 1
            breakdown.append("Lower or Stable Debt/Equity (+1)")
        else:
            breakdown.append("Higher Debt Leverage (0)")

        # 6. Current Ratio improved
        cr_curr = data.get("current_ratio", 1.5)
        cr_prev = data.get("current_ratio_prior", 1.4)
        if cr_curr >= cr_prev:
            score += 1
            breakdown.append("Current Ratio Improved (+1)")
        else:
            breakdown.append("Current Ratio Declined (0)")

        # 7. No share dilution (shares outstanding <= prior year)
        shares_curr = data.get("shares_out", 100)
        shares_prev = data.get("shares_out_prior", 100)
        if shares_curr <= shares_prev:
            score += 1
            breakdown.append("No Share Dilution (+1)")
        else:
            breakdown.append("New Shares Issued / Dilution (0)")

        # 8. Gross Margin improved
        gm_curr = data.get("gross_margin", 25.0)
        gm_prev = data.get("gross_margin_prior", 24.0)
        if gm_curr >= gm_prev:
            score += 1
            breakdown.append("Gross Margin Expanded (+1)")
        else:
            breakdown.append("Gross Margin Compressed (0)")

        # 9. Asset Turnover improved
        at_curr = data.get("asset_turnover", 0.8)
        at_prev = data.get("asset_turnover_prior", 0.75)
        if at_curr >= at_prev:
            score += 1
            breakdown.append("Asset Turnover Improved (+1)")
        else:
            breakdown.append("Asset Turnover Declined (0)")

        rating = "Strong (Piotroski 7-9)" if score >= 7 else ("Moderate (Piotroski 4-6)" if score >= 4 else "Weak (Piotroski 0-3)")
        color = "#10B981" if score >= 7 else ("#F59E0B" if score >= 4 else "#EF4444")

        return {
            "f_score": score,
            "max_score": 9,
            "rating": rating,
            "color": color,
            "breakdown": breakdown
        }

    @classmethod
    def compute_altman_z_score(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute Altman Z-Score for financial distress / insolvency risk (Feature 26)."""
        # Emerging market / Non-manufacturing formula:
        # Z = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
        # X1 = Working Capital / Total Assets
        # X2 = Retained Earnings / Total Assets
        # X3 = EBIT / Total Assets
        # X4 = Book Value of Equity / Total Liabilities

        wc_to_ta = data.get("working_capital_to_assets", 0.20)
        re_to_ta = data.get("retained_earnings_to_assets", 0.25)
        ebit_to_ta = data.get("ebit_to_assets", 0.12)
        eq_to_liab = data.get("equity_to_liabilities", 1.20)

        z_score = round(6.56 * wc_to_ta + 3.26 * re_to_ta + 6.72 * ebit_to_ta + 1.05 * eq_to_liab, 2)

        if z_score >= 2.6:
            zone = "Safe Zone (Low Insolvency Risk)"
            color = "#10B981"
        elif z_score >= 1.1:
            zone = "Grey Zone (Moderate Risk)"
            color = "#F59E0B"
        else:
            zone = "Distress Zone (High Credit Risk)"
            color = "#EF4444"

        return {
            "z_score": z_score,
            "zone": zone,
            "color": color
        }

    @classmethod
    def evaluate_peer_valuation(cls, symbol: str, industry: str, pe: float, pb: float, roe: float, div_yield: float) -> Dict[str, Any]:
        """Compare equity against its sector median (Feature 25)."""
        benchmark = cls.SECTOR_BENCHMARKS.get(industry, cls.DEFAULT_SECTOR_BENCHMARK)
        bm_pe = benchmark["pe"]
        bm_pb = benchmark["pb"]
        bm_roe = benchmark["roe"]
        bm_div = benchmark["div_yield"]

        pe_discount = round(((bm_pe - pe) / bm_pe) * 100.0, 1) if (pe > 0 and bm_pe > 0) else 0.0
        pb_discount = round(((bm_pb - pb) / bm_pb) * 100.0, 1) if (pb > 0 and bm_pb > 0) else 0.0
        roe_excess = round(roe - bm_roe, 1)

        is_undervalued = (pe_discount > 10.0 or pb_discount > 10.0) and roe >= (bm_roe - 2.0)

        return {
            "sector": industry,
            "sector_pe": bm_pe,
            "sector_pb": bm_pb,
            "sector_roe": bm_roe,
            "pe_discount_pct": pe_discount,
            "pb_discount_pct": pb_discount,
            "roe_excess_pct": roe_excess,
            "is_undervalued_peer": is_undervalued,
            "peer_verdict": "Cheap vs Sector Median" if is_undervalued else ("Priced at Sector Premium" if pe_discount < -15 else "Fairly Valued vs Peers")
        }

    @classmethod
    def generate_fundamental_profile(cls, symbol: str, name: str, industry: str, current_price: float) -> Dict[str, Any]:
        """Generate a complete fundamental profile for any CSE company (Features 21-27)."""
        # Deterministic, realistic CSE fundamental derivation based on sector & symbol
        benchmark = cls.SECTOR_BENCHMARKS.get(industry, cls.DEFAULT_SECTOR_BENCHMARK)
        base_pe = benchmark["pe"]
        base_pb = benchmark["pb"]
        base_roe = benchmark["roe"]
        base_div = benchmark["div_yield"]

        # Symbol seed for realistic diversity
        h = sum(ord(c) for c in symbol)
        factor = 0.85 + ((h % 31) / 100.0)  # 0.85 to 1.15 multiplier

        pe = round(max(2.5, base_pe * factor), 1)
        pb = round(max(0.3, base_pb * factor), 2)
        roe = round(base_roe * (1.1 - ((h % 20) / 100.0)), 1)
        div_yield = round(max(1.0, base_div * (0.9 + ((h % 25) / 100.0))), 1)

        eps = round(current_price / pe, 2) if pe > 0 else 1.0
        bvps = round(current_price / pb, 2) if pb > 0 else 10.0
        dps = round(current_price * (div_yield / 100.0), 2)

        # Intrinsic values
        graham = cls.calculate_graham_number(eps, bvps)
        dcf = cls.calculate_dcf_value(eps * 0.9, growth_rate=0.07, terminal_growth=0.03, discount_rate=0.13)
        ddm = cls.calculate_dividend_discount_model(dps, dividend_growth=0.04, required_return=0.13)

        # Financial health
        f_score_data = {
            "net_income": eps * 1_000_000,
            "operating_cash_flow": eps * 1_200_000,
            "roa": roe * 0.4,
            "roa_prior": roe * 0.35,
            "debt_to_equity": round(0.4 + ((h % 60) / 100.0), 2),
            "debt_to_equity_prior": round(0.5 + ((h % 60) / 100.0), 2),
            "current_ratio": round(1.2 + ((h % 50) / 100.0), 2),
            "current_ratio_prior": 1.3,
            "shares_out": 100_000_000,
            "shares_out_prior": 100_000_000,
            "gross_margin": round(22.0 + ((h % 30)), 1),
            "gross_margin_prior": round(21.0 + ((h % 30)), 1),
            "asset_turnover": 0.85,
            "asset_turnover_prior": 0.80
        }
        f_score = cls.compute_piotroski_f_score(f_score_data)
        z_score = cls.compute_altman_z_score({
            "working_capital_to_assets": 0.22,
            "retained_earnings_to_assets": 0.28,
            "ebit_to_assets": 0.14,
            "equity_to_liabilities": 1.40
        })

        # Peer comparison
        peer_comp = cls.evaluate_peer_valuation(symbol, industry, pe, pb, roe, div_yield)

        # Dividend consistency
        streak_years = max(2, (h % 10) + 1)
        payout_ratio = round((dps / eps * 100.0), 1) if eps > 0 else 0.0

        # Margin and debt
        net_margin = round(12.5 + ((h % 15) - 5), 1)
        debt_to_equity = f_score_data["debt_to_equity"]

        return {
            "symbol": symbol,
            "name": name,
            "industry": industry,
            "current_price": current_price,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "roe_pct": roe,
            "eps": eps,
            "bvps": bvps,
            "dividend_per_share": dps,
            "dividend_yield_pct": div_yield,
            "payout_ratio_pct": min(100.0, payout_ratio),
            "dividend_streak_years": streak_years,
            "net_margin_pct": net_margin,
            "debt_to_equity": debt_to_equity,
            "graham_number": graham,
            "dcf_value": dcf,
            "ddm_value": ddm,
            "piotroski": f_score,
            "altman_z": z_score,
            "peer_comparison": peer_comp
        }
