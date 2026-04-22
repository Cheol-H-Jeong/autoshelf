from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from autoshelf.gui.widgets.button import GhostButton
from autoshelf.gui.widgets.card import Card


class ConfidenceMeter(QWidget):
    def __init__(self, value: float = 0.0) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        layout.addWidget(self.bar)
        self.set_value(value)
        self.setAccessibleName("신뢰도")

    def set_value(self, value: float) -> None:
        percent = max(0, min(100, round(value * 100)))
        self.bar.setValue(percent)
        self.bar.setFormat(f"{percent}%")


class StatusDot(QLabel):
    def __init__(self, status: str = "idle") -> None:
        super().__init__("●")
        self.set_status(status)
        self.setAccessibleName("상태")

    def set_status(self, status: str) -> None:
        colors = {
            "success": "#047857",
            "working": "#2563EB",
            "idle": "#6B7280",
            "error": "#B91C1C",
        }
        self.setStyleSheet(f"color: {colors.get(status, colors['idle'])};")


class ProgressOverlay(Card):
    def __init__(self, title: str = "처리 중", can_cancel: bool = True) -> None:
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("progressHeadline")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.sub_text = QLabel("")
        self.cancel_button = GhostButton("취소")
        self.body.addWidget(self.title_label)
        self.body.addWidget(self.progress)
        self.body.addWidget(self.sub_text)
        if can_cancel:
            self.body.addWidget(self.cancel_button)
        self.setAccessibleName(title)

    def set_progress(self, value: int, sub_text: str = "") -> None:
        self.progress.setValue(value)
        self.sub_text.setText(sub_text)
