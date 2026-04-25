"""Theme + asset path resolution for the kiosk UI.

Works in both source-tree runs (``Browser/browser/...``) and PyInstaller
frozen runs (data files copied next to ``sys._MEIPASS``).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QGuiApplication

logger = logging.getLogger(__name__)

PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
DANGER = "#dc2626"
DANGER_DARK = "#991b1b"
SUCCESS = "#16a34a"
WARNING = "#d97706"
SURFACE = "#0f172a"
SURFACE_2 = "#1e293b"
TEXT = "#f8fafc"
TEXT_MUTED = "#94a3b8"


def _project_roots() -> list[Path]:
    """All places we should look for theme.qss / assets/."""
    roots: list[Path] = []

    here = Path(__file__).resolve()
    roots.append(here.parent)                     # browser/ui
    roots.append(here.parent.parent)              # browser/
    roots.append(here.parent.parent.parent)       # repo Browser/

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.insert(0, Path(meipass))
        roots.insert(1, Path(meipass) / "browser")

    return roots


def asset_path(name: str) -> Optional[Path]:
    """Find an asset file (icon.ico, logo.png, ...) anywhere reasonable."""
    candidates = [
        Path(name),
        Path("assets") / name,
        Path("browser") / "assets" / name,
    ]
    for root in _project_roots():
        for c in candidates:
            full = root / c
            if full.exists():
                return full
    return None


def _theme_qss_path() -> Optional[Path]:
    for root in _project_roots():
        for rel in ("theme.qss", "ui/theme.qss", "browser/ui/theme.qss"):
            p = root / rel
            if p.exists():
                return p
    return None


def _qss_with_substitutions() -> str:
    qss_file = _theme_qss_path()
    if not qss_file:
        logger.warning("theme.qss not found - using fallback inline style")
        return _FALLBACK_QSS

    raw = qss_file.read_text(encoding="utf-8")
    return (
        raw.replace("@primary", PRIMARY)
        .replace("@primarydark", PRIMARY_DARK)
        .replace("@danger", DANGER)
        .replace("@dangerdark", DANGER_DARK)
        .replace("@success", SUCCESS)
        .replace("@warning", WARNING)
        .replace("@surface2", SURFACE_2)
        .replace("@surface", SURFACE)
        .replace("@textmuted", TEXT_MUTED)
        .replace("@text", TEXT)
    )


def apply_theme(app: QGuiApplication) -> None:
    """Apply the kiosk QSS theme to the running QApplication."""
    try:
        app.setStyleSheet(_qss_with_substitutions())
        logger.info("Kiosk theme applied")
    except Exception as exc:
        logger.warning("Failed to apply kiosk theme: %s", exc)


_FALLBACK_QSS = f"""
QWidget {{ background-color: {SURFACE}; color: {TEXT}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
QPushButton {{ background-color: {PRIMARY}; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; }}
QPushButton:hover {{ background-color: {PRIMARY_DARK}; }}
QPushButton#dangerButton {{ background-color: {DANGER}; }}
QPushButton#dangerButton:hover {{ background-color: {DANGER_DARK}; }}
"""
