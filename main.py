# main.py  –  CSE Stock Analyzer entry-point (Native Windows 11 Fast Launch)
"""
Launch the Colombo Stock Exchange Analyzer desktop app.
Sets up sys.path so we can reuse the parent project's data modules,
loads .env, applies the Windows 11 Fluent Light theme, and starts the UI
with seamless, flicker-free instant window appearance.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path

# Suppress matplotlib font fallback warnings
logging.getLogger("matplotlib").setLevel(logging.ERROR)

# ── Resolve directories ────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_PARENT_DIR = _THIS_DIR.parent

# Add THIS directory first so our packages (core, views, ui_utils) are found
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
# Add parent so stocks.py, gemini_analyzer.py, qqe_backtest_signals.py work
if str(_PARENT_DIR) not in sys.path:
    sys.path.append(str(_PARENT_DIR))

# ── Load environment variables from parent .env ─────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(_PARENT_DIR / ".env")
except Exception:
    pass

# ── Tkinter + Windows 11 Light Theme ───────────────────────────────────
import tkinter as tk
import sv_ttk
from ui_utils import setup_win11_styles, WIN11_BG


def _load_local_app_module():
    """Import our local app.py explicitly by file path to avoid collision
    with the parent project's Flask-based app.py."""
    spec = importlib.util.spec_from_file_location("cse_app", _THIS_DIR / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    root = tk.Tk()

    # Hide window immediately while building to prevent element-by-element pop-in / flicker
    root.withdraw()
    root.title("CSE Stock Analyzer")

    # Center window on screen
    w, h = 1400, 850
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = max(0, (screen_w - w) // 2)
    y = max(0, (screen_h - h) // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.minsize(1100, 700)

    # Sun-Valley Windows 11 Light theme
    sv_ttk.set_theme("light")
    setup_win11_styles(root)

    # Match the Windows title-bar to native Windows 11 light surface
    try:
        import pywinstyles
        pywinstyles.apply_style(root, "mica")
        pywinstyles.change_header_color(root, WIN11_BG)
    except Exception:
        pass

    # App icon (reuse parent icon if available)
    icon_path = _PARENT_DIR / "icon.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    # ── Build & Pack MainApp ────────────────────────────────────────────
    app_mod = _load_local_app_module()
    app = app_mod.MainApp(root)
    app.pack(fill="both", expand=True)

    # Process pending geometry calculations off-screen
    root.update_idletasks()

    # Instant reveal — window appears fully styled with zero flicker
    root.deiconify()
    root.lift()

    root.mainloop()


if __name__ == "__main__":
    main()
