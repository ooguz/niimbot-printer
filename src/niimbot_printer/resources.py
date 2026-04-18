"""Bundled assets (fonts, icons). Resolves paths in dev installs and PyInstaller bundles."""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["package_root", "bundled_bitter_font_path", "app_icon_path"]

FONT_FILE = "bitter-v40-latin_latin-ext-600.ttf"
ICON_FILE = "icon.png"


def package_root() -> Path:
    """Directory containing this package (``niimbot_printer``)."""
    return Path(__file__).resolve().parent


def bundled_bitter_font_path() -> Path | None:
    """Bitter Latin Ext 600 (SIL OFL 1.1). See ``data/fonts/OFL.txt``."""
    candidates: list[Path] = [
        package_root() / "data" / "fonts" / FONT_FILE,
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(getattr(sys, "_MEIPASS"))
        candidates.extend(
            [
                meipass / "niimbot_printer" / "data" / "fonts" / FONT_FILE,
                meipass / "data" / "fonts" / FONT_FILE,
            ]
        )
    for p in candidates:
        if p.is_file():
            return p
    return None


def app_icon_path() -> Path | None:
    """Window / desktop PNG (bundled under ``data/``)."""
    candidates: list[Path] = [
        package_root() / "data" / ICON_FILE,
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.extend(
            [
                meipass / "niimbot_printer" / "data" / ICON_FILE,
                meipass / "data" / ICON_FILE,
            ]
        )
    for p in candidates:
        if p.is_file():
            return p
    return None
