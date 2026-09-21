# ui/theme/tokens.py  –  Design System Tokens for Windows 11 Look & Feel
"""
Centralized design tokens for Windows 11 Light & Dark modes.
Controls all surface colors, state borders, typography, radii, and spacing.
"""
from __future__ import annotations

from typing import Dict, Any, Callable, List

# ── Color Palette Definitions ─────────────────────────────────────────────

DARK: Dict[str, str] = {
    "bg": "#1c1c1e",          # Main window canvas
    "surface": "#2a2a2d",     # Card background / elevated panels
    "surface_hi": "#343438",  # Hover / highlight state
    "surface_card": "#262629",# Nested card surface
    "border": "#3f3f46",      # Subtle borders / dividers
    "text": "#f4f4f5",        # Primary foreground text
    "text_dim": "#a1a1aa",    # Secondary / muted text
    "text_subtle": "#71717a", # Tertiary text / placeholders
    "accent": "#4cc2ff",      # Windows 11 Fluent Blue (Dark)
    "accent_hover": "#3ab0ec",
    "accent_bg": "#1e3a5f",   # Subtle accent tint
    "gain": "#22c55e",        # Bullish / positive green
    "gain_bg": "#0f2e1b",     # Soft green background
    "loss": "#ef4444",        # Bearish / negative red
    "loss_bg": "#2e1215",     # Soft red background
    "warn": "#f59e0b",        # Warning / attention amber
    "warn_bg": "#2e1e0a",     # Soft amber background
    "info": "#8b5cf6",        # Intel / purple accent
    "select_bg": "#1e3a5f",   # Selection row highlight
    "select_fg": "#ffffff",   # Selected text
    "header_bg": "#222225",   # Table header background
}

LIGHT: Dict[str, str] = {
    "bg": "#f3f3f3",          # Main window canvas
    "surface": "#ffffff",     # Card background / elevated panels
    "surface_hi": "#f0f0f0",  # Hover / highlight state
    "surface_card": "#fafafa",# Nested card surface
    "border": "#e0e0e0",      # Subtle borders / dividers
    "text": "#1a1a1a",        # Primary foreground text (slate 900)
    "text_dim": "#6b6b6b",    # Secondary / muted text (slate 500)
    "text_subtle": "#94a3b8", # Tertiary text / placeholders
    "accent": "#0067c0",      # Windows 11 Fluent Blue (Light)
    "accent_hover": "#1879cd",
    "accent_bg": "#e0f2fe",   # Subtle accent tint
    "gain": "#15803d",        # Bullish / positive green
    "gain_bg": "#f0fdf4",     # Soft green background
    "loss": "#b91c1c",        # Bearish / negative red
    "loss_bg": "#fef2f2",     # Soft red background
    "warn": "#b45309",        # Warning / attention amber
    "warn_bg": "#fffbeb",     # Soft amber background
    "info": "#6d28d9",        # Intel / purple accent
    "select_bg": "#e0f2fe",   # Selection row highlight
    "select_fg": "#0369a1",   # Selected text
    "header_bg": "#f8fafc",   # Table header background
}

# State-Based Input Border Colors
INPUT_STATES: Dict[str, Dict[str, str]] = {
    "dark": {
        "default": DARK["border"],
        "focused": DARK["accent"],
        "valid": DARK["gain"],
        "error": DARK["loss"],
        "warn": DARK["warn"],
    },
    "light": {
        "default": LIGHT["border"],
        "focused": LIGHT["accent"],
        "valid": LIGHT["gain"],
        "error": LIGHT["loss"],
        "warn": LIGHT["warn"],
    },
}

# Signal Confluence Grades
GRADES: Dict[str, Dict[str, str]] = {
    "A+": {"color": "#059669", "bg": "#ecfdf5", "label": "Strong High Conviction"},
    "A":  {"color": "#0284c7", "bg": "#f0f9ff", "label": "Solid Setup"},
    "B":  {"color": "#d97706", "bg": "#fffbeb", "label": "Moderate Setup"},
    "C":  {"color": "#e11d48", "bg": "#fff1f2", "label": "Low Confluence / Caution"},
}

# Spacing Scale (4, 8, 12, 16, 24, 32 px)
SPACING: Dict[str, int] = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 24,
    "xl": 32,
}

# Border Radii (Corner Rounding)
RADII: Dict[str, int] = {
    "sm": 6,
    "md": 10,
    "lg": 14,
    "pill": 999,
}

# Typography Hierarchy
FONT_PRIMARY = "Segoe UI Variable Text"
FONT_DISPLAY = "Segoe UI Variable Display"
FONT_FALLBACK = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"
FONT_MONO = "Cascadia Mono"
FONT_MONO_FALLBACK = "Consolas"

FONTS: Dict[str, tuple[str, int, str]] = {
    "display": (FONT_SEMIBOLD, 24, "bold"),
    "title": (FONT_SEMIBOLD, 18, "bold"),
    "subtitle": (FONT_SEMIBOLD, 14, "normal"),
    "body": (FONT_FALLBACK, 10, "normal"),
    "body_bold": (FONT_SEMIBOLD, 10, "bold"),
    "caption": (FONT_FALLBACK, 9, "normal"),
    "card_title": (FONT_SEMIBOLD, 10, "normal"),
    "card_val": (FONT_SEMIBOLD, 18, "bold"),
    "mono": (FONT_MONO_FALLBACK, 10, "normal"),
    "mono_bold": (FONT_MONO_FALLBACK, 10, "bold"),
    "mono_lg": (FONT_MONO_FALLBACK, 14, "bold"),
}


# ── Global Theme Manager ──────────────────────────────────────────────────

class ThemeManager:
    """Manages active theme state and notifies registered observer callbacks."""
    _current_mode: str = "light"
    _listeners: List[Callable[[str], None]] = []

    @classmethod
    def get_mode(cls) -> str:
        return cls._current_mode

    @classmethod
    def set_mode(cls, mode: str) -> None:
        mode = mode.lower()
        if mode not in ("light", "dark"):
            mode = "light"
        if mode != cls._current_mode:
            cls._current_mode = mode
            for cb in cls._listeners:
                try:
                    cb(mode)
                except Exception:
                    pass

    @classmethod
    def toggle(cls) -> str:
        new_mode = "dark" if cls._current_mode == "light" else "light"
        cls.set_mode(new_mode)
        return new_mode

    @classmethod
    def register_listener(cls, callback: Callable[[str], None]) -> None:
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unregister_listener(cls, callback: Callable[[str], None]) -> None:
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def tokens(cls) -> Dict[str, str]:
        return DARK if cls._current_mode == "dark" else LIGHT

    @classmethod
    def get(cls, key: str, fallback: str = "#000000") -> str:
        return cls.tokens().get(key, fallback)


def get_token(key: str, fallback: str = "#000000") -> str:
    """Convenience getter for current theme token."""
    return ThemeManager.get(key, fallback)

def get_theme_mode() -> str:
    return ThemeManager.get_mode()

def set_theme_mode(mode: str) -> None:
    ThemeManager.set_mode(mode)


# ── Backward Compatibility Constants for Existing Views ───────────────────
# These map dynamically or provide light defaults for existing imports in views
WIN11_BG = LIGHT["bg"]
WIN11_CARD_BG = LIGHT["surface"]
WIN11_CARD_BORDER = LIGHT["border"]
WIN11_TEXT_MAIN = LIGHT["text"]
WIN11_TEXT_MUTED = LIGHT["text_dim"]
WIN11_TEXT_SUBTLE = LIGHT["text_subtle"]
WIN11_ACCENT = LIGHT["accent"]
WIN11_ACCENT_HOVER = LIGHT["accent_hover"]
WIN11_GREEN = LIGHT["gain"]
WIN11_GREEN_BG = LIGHT["gain_bg"]
WIN11_RED = LIGHT["loss"]
WIN11_RED_BG = LIGHT["loss_bg"]
WIN11_BORDER = LIGHT["border"]
WIN11_HEADER_BG = LIGHT["header_bg"]
WIN11_SELECT_BG = LIGHT["select_bg"]
WIN11_SELECT_FG = LIGHT["select_fg"]

GRADE_A_PLUS = GRADES["A+"]["color"]
GRADE_A_PLUS_BG = GRADES["A+"]["bg"]
GRADE_A = GRADES["A"]["color"]
GRADE_A_BG = GRADES["A"]["bg"]
GRADE_B = GRADES["B"]["color"]
GRADE_B_BG = GRADES["B"]["bg"]
GRADE_C = GRADES["C"]["color"]
GRADE_C_BG = GRADES["C"]["bg"]

FONT_TITLE = (FONT_SEMIBOLD, 15)
FONT_SECTION = (FONT_SEMIBOLD, 12)
FONT_SUBTITLE = (FONT_FALLBACK, 9)
FONT_BODY = (FONT_FALLBACK, 9)
FONT_BODY_BOLD = (FONT_SEMIBOLD, 9)
FONT_CAPTION = (FONT_FALLBACK, 8)
FONT_CARD_TITLE = (FONT_SEMIBOLD, 9)
FONT_CARD_VAL = (FONT_SEMIBOLD, 17)
FONT_MONO = (FONT_MONO_FALLBACK, 9)
