from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from autoshelf.i18n import t


class ScanWorker(QObject):
    finished = Signal(dict)

    def __init__(self) -> None:
        super().__init__()

    def run(self) -> None:
        self.finished.emit({"files": 0, "size_bytes": 0, "extensions": {}})


class HomeScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.thread = QThread(self)
        self.worker = ScanWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._render_stats)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        self.banner = QLabel(t("status.offline"))
        self.root_input = QLineEdit()
        self.root_input.setPlaceholderText("/path/to/folder")
        browse_button = QPushButton("Browse")
        row = QHBoxLayout()
        row.addWidget(QLabel(t("home.title")))
        row.addWidget(self.root_input)
        row.addWidget(browse_button)
        layout.addWidget(self.banner)
        layout.addLayout(row)
        self.recent_list = QListWidget()
        self.recent_list.addItem("Recent folders")
        layout.addWidget(self.recent_list)
        self.stats_view = QTextEdit()
        self.stats_view.setReadOnly(True)
        self.stats_view.setPlainText("Scan stats will appear here.")
        layout.addWidget(self.stats_view)
        self.plan_button = QPushButton(f"{t('button.plan')} →")
        self.plan_button.setEnabled(False)
        layout.addWidget(self.plan_button)

    def start_scan(self) -> None:
        if not self.thread.isRunning():
            self.thread.start()

    def _render_stats(self, stats: dict) -> None:
        self.stats_view.setPlainText(str(stats))
        self.plan_button.setEnabled(True)
