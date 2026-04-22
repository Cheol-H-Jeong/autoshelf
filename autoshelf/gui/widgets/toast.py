from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from autoshelf.gui.design import TOAST_DURATION_MS


class ToastHost(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setAccessibleName("알림 목록")

    def show_toast(self, message: str) -> None:
        label = QLabel(message)
        label.setAccessibleName(message)
        self.layout.addWidget(label)
        QTimer.singleShot(TOAST_DURATION_MS, label.deleteLater)
