from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
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
        self.thread: QThread | None = None
        self.worker: ScanWorker | None = None
        self.scan_requests = 0
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        self.banner = QLabel("")
        self.root_input = QLineEdit()
        self.root_input.setPlaceholderText("/path/to/folder")
        self.browse_button = QPushButton("")
        row = QHBoxLayout()
        self.title_label = QLabel("")
        row.addWidget(self.title_label)
        row.addWidget(self.root_input)
        row.addWidget(self.browse_button)
        layout.addWidget(self.banner)
        layout.addLayout(row)
        self.recent_list = QListWidget()
        self.recent_list.addItem("Recent folders")
        layout.addWidget(self.recent_list)
        self.stats_view = QTextEdit()
        self.stats_view.setReadOnly(True)
        self.stats_view.setPlainText("Scan stats will appear here.")
        layout.addWidget(self.stats_view)
        self.plan_button = QPushButton("")
        self.plan_button.setEnabled(False)
        layout.addWidget(self.plan_button)
        self.apply_config()

    def start_scan(self) -> None:
        if self.thread is not None and self.thread.isRunning():
            logger.debug("Ignoring scan request because a scan is already running")
            return
        self.scan_requests += 1
        self.thread = QThread(self)
        self.worker = ScanWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._render_stats)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        logger.debug("Starting GUI scan request {}", self.scan_requests)
        self.thread.start()

    def _render_stats(self, stats: dict) -> None:
        self.stats_view.setPlainText(str(stats))
        self.plan_button.setEnabled(True)
        logger.debug("Rendered GUI scan stats")

    def _cleanup_thread(self) -> None:
        logger.debug("Cleaning up GUI scan worker thread")
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.banner.setText(t("status.offline", config))
        self.title_label.setText(t("home.title", config))
        self.browse_button.setText(t("home.browse", config))
        self.plan_button.setText(f"{t('button.plan', config)} →")
