"""Slide-down warning banner shown when a teacher sends a message.

Designed as a child overlay of ``SecureBrowser.browser`` (the QWebEngineView)
so it floats above the web content without dimming it. Uses theme tokens
from ``ui.theme`` so it matches the rest of the kiosk chrome.

Severity → behaviour:
  * ``info``     - auto-dismisses after 30 s
  * ``warn``     - auto-dismisses after 60 s
  * ``critical`` - never auto-dismisses; teacher's intervention requires
                   the candidate to explicitly acknowledge.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import DANGER, DANGER_DARK, SURFACE_3, TEXT, WARNING


_AUTO_DISMISS_MS = {
    "info": 30_000,
    "warn": 60_000,
    "critical": 0,  # never
}


class WarningBanner(QFrame):
    """Non-modal teacher warning overlay."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("warningBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide_banner)

        self._build_ui()
        self.hide()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(76)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 14, 16, 14)
        outer.setSpacing(14)

        self._icon = QLabel("!")
        self._icon.setFixedSize(40, 40)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setObjectName("warningBannerIcon")
        outer.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._title = QLabel("Proctor message")
        title_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self._title.setFont(title_font)
        self._title.setStyleSheet(f"color: {TEXT};")
        text_col.addWidget(self._title)

        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setStyleSheet(f"color: {TEXT};")
        msg_font = QFont("Segoe UI", 10)
        self._message.setFont(msg_font)
        text_col.addWidget(self._message)

        self._meta = QLabel("")
        self._meta.setStyleSheet("color: rgba(255,255,255,0.75);")
        meta_font = QFont("Segoe UI", 9)
        self._meta.setFont(meta_font)
        text_col.addWidget(self._meta)

        outer.addLayout(text_col, 1)

        self._ack_button = QPushButton("Acknowledge")
        self._ack_button.setObjectName("warningBannerAck")
        self._ack_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ack_button.clicked.connect(self.hide_banner)
        outer.addWidget(self._ack_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._apply_styles("warn")

    def _apply_styles(self, severity: str) -> None:
        if severity == "critical":
            bg = DANGER_DARK
            border = DANGER
        elif severity == "warn":
            bg = "#8a4b00"   # amber-tinted dark
            border = WARNING
        else:
            bg = SURFACE_3
            border = "#3a4f5a"

        self.setStyleSheet(
            f"""
            QFrame#warningBanner {{
                background-color: {bg};
                border-bottom: 2px solid {border};
            }}
            QLabel#warningBannerIcon {{
                background-color: rgba(255,255,255,0.15);
                color: {TEXT};
                border-radius: 20px;
                font-weight: 800;
                font-size: 18px;
            }}
            QPushButton#warningBannerAck {{
                background-color: rgba(255,255,255,0.15);
                color: {TEXT};
                border: 1px solid rgba(255,255,255,0.4);
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton#warningBannerAck:hover {{
                background-color: rgba(255,255,255,0.25);
            }}
            """
        )

    # ------------------------------------------------------------------
    def show_warning(self, warning: dict) -> None:
        severity = (warning.get("severity") or "warn").lower()
        if severity not in {"info", "warn", "critical"}:
            severity = "warn"

        message = warning.get("message", "")[:1000]
        sender = warning.get("sender_name") or warning.get("sender") or "Proctor"
        ts = warning.get("created_at") or warning.get("delivered_at")
        try:
            dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
            ts_human = dt.strftime("%H:%M:%S")
        except Exception:
            ts_human = ""

        self._icon.setText("!" if severity != "critical" else "X")
        self._title.setText(
            "Critical proctor warning" if severity == "critical"
            else "Proctor message"
        )
        self._message.setText(message or "(no message)")
        self._meta.setText(
            f"From {sender}" + (f" · {ts_human}" if ts_human else "")
        )
        self._apply_styles(severity)

        # Position: pin to the top of our parent (the QWebEngineView).
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), self.sizeHint().height())
        self.raise_()
        self.show()

        timeout = _AUTO_DISMISS_MS.get(severity, 0)
        if timeout:
            self._dismiss_timer.start(timeout)
        else:
            self._dismiss_timer.stop()

    def hide_banner(self) -> None:
        self._dismiss_timer.stop()
        self.hide()

    def reposition(self) -> None:
        """Called from the main window's resizeEvent so we always span the top."""
        parent = self.parentWidget()
        if parent is not None and self.isVisible():
            self.setGeometry(0, 0, parent.width(), self.sizeHint().height())
