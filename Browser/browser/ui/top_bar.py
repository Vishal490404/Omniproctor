"""Kiosk top bar with branding, live timer, and status pills."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import asset_path


class StatusPill(QLabel):
    """Tiny rounded pill used in the top bar for live status indicators."""

    STATES = {"ok", "warn", "bad", "idle"}

    def __init__(self, label: str, parent: Optional[QWidget] = None):
        super().__init__(label, parent)
        self.setProperty("class", "statusPill")
        self.setProperty("status", "idle")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._base_label = label

    def set_state(self, state: str, label: Optional[str] = None) -> None:
        if state not in self.STATES:
            state = "idle"
        self.setProperty("status", state)
        if label is not None:
            self.setText(label)
        else:
            self.setText(self._base_label)
        # Force Qt to re-evaluate stylesheet selectors that depend on a
        # dynamic property.
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)


class KioskTopBar(QWidget):
    """The persistent top bar shown above the embedded web view."""

    exit_requested = pyqtSignal()
    back_requested = pyqtSignal()
    forward_requested = pyqtSignal()

    def __init__(
        self,
        test_title: str = "OmniProctor Secure Session",
        assignee: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("kioskTopBar")
        self.setFixedHeight(58)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 6, 14, 6)
        root.setSpacing(14)

        # ---- Brand ---------------------------------------------------------
        brand_box = QHBoxLayout()
        brand_box.setSpacing(8)
        brand_icon = QLabel()
        icon_file = (
            asset_path("icon.png")
            or asset_path("icon.ico")
            or asset_path("icon.svg")
        )
        if icon_file:
            pix = QPixmap(str(icon_file))
            if not pix.isNull():
                brand_icon.setPixmap(
                    pix.scaledToHeight(28, Qt.TransformationMode.SmoothTransformation)
                )
        brand_text = QLabel("OmniProctor")
        brand_text.setObjectName("kioskBrand")
        brand_box.addWidget(brand_icon)
        brand_box.addWidget(brand_text)
        root.addLayout(brand_box)

        # ---- Back / Forward navigation ------------------------------------
        # Surface ONLY back / forward (no reload, no address bar) so the
        # candidate can recover from accidental navigations inside the
        # exam UI (e.g. opening a help link) without ever having a way to
        # type a new URL.
        nav_box = QHBoxLayout()
        nav_box.setSpacing(6)
        # Triangle glyphs (◀ / ▶) render solid in every Windows system font
        # and stay sharply visible against the dark surface; the lighter
        # arrow characters (←/→) end up looking like 1px hairlines on
        # high-DPI laptops.
        self.back_button = QPushButton("\u25C0")  # ◀
        self.back_button.setObjectName("ghostButton")
        self.back_button.setToolTip("Back")
        self.back_button.setFixedSize(40, 36)
        self.back_button.setEnabled(False)
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.back_requested.emit)
        nav_box.addWidget(self.back_button)

        self.forward_button = QPushButton("\u25B6")  # ▶
        self.forward_button.setObjectName("ghostButton")
        self.forward_button.setToolTip("Forward")
        self.forward_button.setFixedSize(40, 36)
        self.forward_button.setEnabled(False)
        self.forward_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forward_button.clicked.connect(self.forward_requested.emit)
        nav_box.addWidget(self.forward_button)

        root.addLayout(nav_box)

        # ---- Test info -----------------------------------------------------
        info_box = QVBoxLayout()
        info_box.setSpacing(0)
        self.title_label = QLabel(test_title)
        self.title_label.setObjectName("kioskTitle")
        self.subtitle_label = QLabel(assignee or "Secure exam in progress")
        self.subtitle_label.setObjectName("kioskSubtitle")
        info_box.addWidget(self.title_label)
        info_box.addWidget(self.subtitle_label)
        root.addLayout(info_box)

        root.addStretch(1)

        # ---- Live timer ----------------------------------------------------
        self._started_at = datetime.now()
        self._countdown_target: Optional[datetime] = None
        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("kioskTimer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.timer_label)

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._update_timer)
        self._tick.start()

        root.addStretch(1)

        # ---- Status pills --------------------------------------------------
        pill_box = QHBoxLayout()
        pill_box.setSpacing(6)
        self.network_pill = StatusPill("Network …")
        self.firewall_pill = StatusPill("Firewall …")
        self.camera_pill = StatusPill("Camera idle")
        self.monitor_pill = StatusPill("Display …")
        for pill in (self.network_pill, self.firewall_pill, self.camera_pill, self.monitor_pill):
            pill_box.addWidget(pill)
        root.addLayout(pill_box)

        # ---- End session ---------------------------------------------------
        self.exit_button = QPushButton("End Session")
        self.exit_button.setObjectName("dangerButton")
        self.exit_button.setMinimumHeight(36)
        self.exit_button.clicked.connect(self.exit_requested.emit)
        root.addWidget(self.exit_button)

    # Public state-update API ------------------------------------------------
    def set_test_info(self, title: str, assignee: str = "") -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(assignee or "Secure exam in progress")

    def set_network_status(self, ok: bool, label: Optional[str] = None) -> None:
        self.network_pill.set_state(
            "ok" if ok else "bad",
            label or ("Network OK" if ok else "Network down"),
        )

    def set_firewall_status(self, ok: bool, label: Optional[str] = None) -> None:
        self.firewall_pill.set_state(
            "ok" if ok else "bad",
            label or ("Firewall ON" if ok else "Firewall OFF"),
        )

    def set_camera_status(self, state: str, label: Optional[str] = None) -> None:
        """state: 'ok' (granted), 'idle', 'warn', or 'bad' (denied)."""
        self.camera_pill.set_state(state, label)

    def set_monitor_status(self, count: int) -> None:
        if count <= 1:
            self.monitor_pill.set_state("ok", "1 Display")
        else:
            self.monitor_pill.set_state("bad", f"{count} Displays!")

    def set_navigation_state(self, can_go_back: bool, can_go_forward: bool) -> None:
        """Sync back/forward button enabled state with the page history."""
        try:
            self.back_button.setEnabled(bool(can_go_back))
            self.forward_button.setEnabled(bool(can_go_forward))
        except Exception:
            pass

    def set_countdown(self, total_seconds: int) -> None:
        """Switch the timer from elapsed-since-start to count-down."""
        self._countdown_target = datetime.now() + timedelta(seconds=total_seconds)

    def reset_elapsed(self) -> None:
        self._started_at = datetime.now()
        self._countdown_target = None

    # Internal ---------------------------------------------------------------
    def _update_timer(self) -> None:
        if self._countdown_target:
            remaining = self._countdown_target - datetime.now()
            secs = int(remaining.total_seconds())
            if secs <= 0:
                self.timer_label.setText("00:00")
                return
            self.timer_label.setText(self._format_seconds(secs))
        else:
            elapsed = datetime.now() - self._started_at
            self.timer_label.setText(self._format_seconds(int(elapsed.total_seconds())))

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def make_window_icon() -> QIcon:
        """Helper for the main window / app to set its window icon."""
        for name in ("icon.ico", "icon.png", "icon.svg"):
            p = asset_path(name)
            if p:
                return QIcon(str(p))
        return QIcon()
