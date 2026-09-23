# core/gemini_engine.py  –  Gemini AI wrapper for CSE Analyzer
"""
Provides convenient functions for running Gemini analyses in background
threads.  Re-uses the parent project's gemini_analyzer.py module.
"""
from __future__ import annotations

from typing import Dict, Any

import pandas as pd

# Parent-project module
import gemini_analyzer as ga


def analyze_stock(symbol: str, df: pd.DataFrame, summary: Dict[str, Any]) -> str:
    """
    Run Gemini analysis on a single stock.
    Returns the analysis text (markdown) or an error string starting with "Error:".
    """
    system_prompt, user_prompt = ga.prepare_prompt(symbol, df, summary)
    return ga.generate_analysis(system_prompt, user_prompt)


def market_summary(gainers_raw: dict, losers_raw: dict) -> str:
    """
    Generate a Gemini-powered market summary from today's top movers.
    Returns the summary text or an error string starting with "Error:".
    """
    system_prompt, user_prompt = ga.prepare_market_summary_prompt(gainers_raw, losers_raw)
    return ga.generate_analysis(system_prompt, user_prompt)
