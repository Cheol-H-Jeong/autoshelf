from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget

from autoshelf.config import AppConfig
from autoshelf.i18n import t


class ApplyScreen(QWidget):
    apply_started = Signal()
    apply_progressed = Signal(int, str)
    apply_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.apply_in_progress = False
        self.apply_requests = 0
        layout = QVBoxLayout(self)
        self.title_label = QLabel("")
        layout.addWidget(self.title_label)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.token_label = QLabel("")
        layout.addWidget(self.token_label)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        self.cancel_button = QPushButton("")
        layout.addWidget(self.cancel_button)
        self.apply_config()

    def start_apply(self) -> None:
        if self.apply_in_progress:
            logger.debug("Ignoring apply request because an apply is already running")
            return
        self.apply_requests += 1
        self.apply_in_progress = True
        self.progress_bar.setValue(0)
        self.log_view.append(t("apply.started"))
        self.apply_started.emit()
        logger.debug("Starting GUI apply request {}", self.apply_requests)
        QTimer.singleShot(0, self._complete_demo_apply)

    def _update_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.log_view.append(message)
        self.apply_progressed.emit(value, message)

    def _complete_demo_apply(self) -> None:
        self._update_progress(100, "Ready")
        self.apply_in_progress = False
        self.apply_finished.emit()

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.title_label.setText(t("apply.title", config))
        self.token_label.setText(t("apply.tokens", config, count=0))
        self.cancel_button.setText(t("button.cancel", config))
