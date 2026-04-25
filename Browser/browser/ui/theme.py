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

# Aligned with the WebClient Mantine theme (primaryColor='teal', accent
# blue=#228be6, dark surface gradient #10191f -> #0b1217). Keeps the
# kiosk visually consistent with the dashboard the candidate just left.
PRIMARY = "#12b886"          # mantine teal[6]
PRIMARY_DARK = "#0ca678"     # mantine teal[7]
ACCENT = "#228be6"           # mantine blue[6] - used in WebClient brand-dot
ACCENT_DARK = "#1c7ed6"      # mantine blue[7]
DANGER = "#fa5252"           # mantine red[5]
DANGER_DARK = "#e03131"      # mantine red[7]
SUCCESS = "#12b886"          # same as primary
WARNING = "#f59f00"          # mantine yellow[7]
SURFACE = "#0b1217"          # WebClient dark gradient bottom
SURFACE_2 = "#10191f"        # WebClient dark gradient top
SURFACE_3 = "#16222b"        # slightly lighter band for top bar / cards
TEXT = "#f1f5f6"
TEXT_MUTED = "#94a7a7"       # mantine 'mist[5]' from the WebClient palette
BORDER = "rgba(255, 255, 255, 0.08)"


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
        raw.replace("@primarydark", PRIMARY_DARK)
        .replace("@primary", PRIMARY)
        .replace("@accentdark", ACCENT_DARK)
        .replace("@accent", ACCENT)
        .replace("@dangerdark", DANGER_DARK)
        .replace("@danger", DANGER)
        .replace("@success", SUCCESS)
        .replace("@warning", WARNING)
        .replace("@surface3", SURFACE_3)
        .replace("@surface2", SURFACE_2)
        .replace("@surface", SURFACE)
        .replace("@border", BORDER)
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
QWidget {{ background-color: {SURFACE}; color: {TEXT}; font-family: 'Poppins', 'Segoe UI', sans-serif; font-size: 13px; }}
QPushButton {{ background-color: {PRIMARY}; color: white; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; }}
QPushButton:hover {{ background-color: {PRIMARY_DARK}; }}
QPushButton#dangerButton {{ background-color: {DANGER}; }}
QPushButton#dangerButton:hover {{ background-color: {DANGER_DARK}; }}
QPushButton#accentButton {{ background-color: {ACCENT}; }}
"""
