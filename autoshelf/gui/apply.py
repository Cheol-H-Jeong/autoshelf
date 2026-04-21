from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget

from autoshelf.config import AppConfig
from autoshelf.i18n import t


class ApplyWorker(QObject):
    progress = Signal(int, str)
    finished = Signal()

    def run(self) -> None:
        self.progress.emit(100, "Ready")
        self.finished.emit()


class ApplyScreen(QWidget):
    apply_started = Signal()
    apply_progressed = Signal(int, str)
    apply_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: ApplyWorker | None = None
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
        if self.thread is not None and self.thread.isRunning():
            logger.debug("Ignoring apply request because an apply is already running")
            return
        self.apply_requests += 1
        self.progress_bar.setValue(0)
        self.log_view.append(t("apply.started"))
        self.apply_started.emit()
        self.thread = QThread(self)
        self.worker = ApplyWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self.apply_finished.emit)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        logger.debug("Starting GUI apply request {}", self.apply_requests)
        self.thread.start()

    def _update_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.log_view.append(message)
        self.apply_progressed.emit(value, message)

    def _cleanup_thread(self) -> None:
        logger.debug("Cleaning up GUI apply worker thread")
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.title_label.setText(t("apply.title", config))
        self.token_label.setText(t("apply.tokens", config, count=0))
        self.cancel_button.setText(t("button.cancel", config))
