"""Branded splash screen shown while WFP + kiosk hooks initialize."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QSplashScreen

from .theme import PRIMARY, SURFACE, SURFACE_2, TEXT, TEXT_MUTED, asset_path


class KioskSplash(QSplashScreen):
    """Plain dark splash with the OmniProctor wordmark and a status line."""

    def __init__(self, parent: Optional[object] = None):
        pix = self._build_pixmap()
        super().__init__(pix)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._status = "Initializing secure environment…"

    @staticmethod
    def _build_pixmap() -> QPixmap:
        width, height = 520, 280
        pix = QPixmap(width, height)
        pix.fill(QColor(SURFACE))

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.fillRect(0, 0, width, height, QColor(SURFACE))
        painter.fillRect(0, height - 60, width, 60, QColor(SURFACE_2))

        icon_file = (
            asset_path("icon.png")
            or asset_path("icon.ico")
            or asset_path("icon.svg")
        )
        if icon_file:
            ip = QPixmap(str(icon_file))
            if not ip.isNull():
                ip = ip.scaledToHeight(72, Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap((width - ip.width()) // 2, 40, ip)

        painter.setPen(QColor(TEXT))
        title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            0,
            130,
            width,
            40,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
            "OmniProctor",
        )

        painter.setPen(QColor(TEXT_MUTED))
        sub_font = QFont("Segoe UI", 11)
        painter.setFont(sub_font)
        painter.drawText(
            0,
            170,
            width,
            24,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
            "Secure Kiosk Browser",
        )

        # Accent bar.
        painter.fillRect(0, height - 4, width, 4, QColor(PRIMARY))
        painter.end()
        return pix

    def set_status(self, message: str) -> None:
        self._status = message
        self.showMessage(
            message,
            int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
            QColor(TEXT_MUTED),
        )
