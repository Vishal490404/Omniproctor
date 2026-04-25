"""Themed message-box wrapper used by all kiosk modal alerts."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QMessageBox, QWidget

from .top_bar import KioskTopBar


class OmniProctorMessageBox:
    """Drop-in replacement for ``QMessageBox.{critical,warning,question,info}``.

    Adds the OmniProctor window icon and centers the dialog over its parent.
    Returns the same ``QMessageBox.StandardButton`` value as the original.
    """

    @staticmethod
    def _show(
        icon: QMessageBox.Icon,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default_button: Optional[QMessageBox.StandardButton] = None,
    ) -> QMessageBox.StandardButton:
        box = QMessageBox(parent)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button is not None:
            box.setDefaultButton(default_button)
        try:
            box.setWindowIcon(KioskTopBar.make_window_icon())
        except Exception:
            pass
        return QMessageBox.StandardButton(box.exec())

    @staticmethod
    def critical(parent: Optional[QWidget], title: str, text: str) -> QMessageBox.StandardButton:
        return OmniProctorMessageBox._show(
            QMessageBox.Icon.Critical, parent, title, text
        )

    @staticmethod
    def warning(parent: Optional[QWidget], title: str, text: str) -> QMessageBox.StandardButton:
        return OmniProctorMessageBox._show(
            QMessageBox.Icon.Warning, parent, title, text
        )

    @staticmethod
    def info(parent: Optional[QWidget], title: str, text: str) -> QMessageBox.StandardButton:
        return OmniProctorMessageBox._show(
            QMessageBox.Icon.Information, parent, title, text
        )

    @staticmethod
    def question(
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = (
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ),
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
    ) -> QMessageBox.StandardButton:
        return OmniProctorMessageBox._show(
            QMessageBox.Icon.Question,
            parent,
            title,
            text,
            buttons=buttons,
            default_button=default_button,
        )
