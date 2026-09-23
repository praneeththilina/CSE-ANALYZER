# ui/theme/icons.py  –  Icon System for Windows 11 Fluent UI
"""
Icon definitions with scalable Unicode glyphs and FontAwesome support.
Provides robust fallback characters that render crisply on Windows 11 Segoe UI.
"""
from __future__ import annotations

from typing import Dict

# Scalable Unicode & Symbol Map
ICONS: Dict[str, str] = {
    # Navigation Rail
    "home": "📊",
    "dashboard": "📊",
    "scanner": "🔍",
    "search": "🔍",
    "chart": "📈",
    "charts": "📈",
    "candlestick": "📈",
    "watchlist": "⭐",
    "star": "⭐",
    "intel": "🏛️",
    "market_intel": "🏛️",
    "portfolio": "💼",
    "wallet": "💼",
    "backtest": "⚡",
    "lightning": "⚡",
    "ai": "🤖",
    "ai_analysis": "🤖",
    "brain": "🤖",
    "settings": "⚙️",
    "gear": "⚙️",

    # Indicators & Actions
    "up": "▲",
    "down": "▼",
    "arrow_up": "▲",
    "arrow_down": "▼",
    "refresh": "🔄",
    "sun": "☀️",
    "moon": "🌙",
    "theme_light": "☀️",
    "theme_dark": "🌙",
    "bell": "🔔",
    "alert": "⚠️",
    "check": "✔",
    "cross": "✖",
    "filter": "🌪️",
    "target": "🎯",
    "trophy": "🏆",
    "shield": "🛡️",
    "lock": "🔒",
    "calendar": "📅",
    "news": "📰",
    "info_circle": "ℹ️",
    "question": "❓",
    "expand": "⤢",
    "collapse": "⤡",
    "chevron_right": "›",
    "chevron_left": "‹",
    "chevron_down": "˅",
}


def get_icon(name: str, fallback: str = "•") -> str:
    """Retrieve an icon by identifier with a graceful fallback."""
    return ICONS.get(name.lower(), fallback)
