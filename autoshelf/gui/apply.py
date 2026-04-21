from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QProgressBar, QTextEdit, QVBoxLayout, QWidget

from autoshelf.i18n import t


class ApplyWorker(QObject):
    progress = Signal(int, str)
    finished = Signal()

    def run(self) -> None:
        self.progress.emit(100, "Ready")
        self.finished.emit()


class ApplyScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.thread = QThread(self)
        self.worker = ApplyWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._update_progress)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("apply.title")))
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.token_label = QLabel("Tokens: 0")
        layout.addWidget(self.token_label)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        self.cancel_button = QPushButton("Cancel")
        layout.addWidget(self.cancel_button)

    def start_apply(self) -> None:
        if not self.thread.isRunning():
            self.thread.start()

    def _update_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.log_view.append(message)
