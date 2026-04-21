from __future__ import annotations

from loguru import logger
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
from autoshelf.i18n import t


class HistoryScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.undo_requests = 0
        layout = QVBoxLayout(self)
        self.title_label = QLabel("")
        layout.addWidget(self.title_label)
        self.table = QTableWidget(1, 5)
        self.table.setHorizontalHeaderLabels(["Run ID", "Root", "Moved", "Status", "Action"])
        for column, value in enumerate(["demo-run", "/tmp", "3", "applied", "Undo"]):
            self.table.setItem(0, column, QTableWidgetItem(value))
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.undo_button = QPushButton("")
        self.open_button = QPushButton("")
        self.manifest_button = QPushButton("")
        actions.addWidget(self.undo_button)
        actions.addWidget(self.open_button)
        actions.addWidget(self.manifest_button)
        layout.addLayout(actions)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self.apply_config()

    def trigger_undo(self, config: AppConfig | None = None) -> None:
        self.undo_requests += 1
        self.status_label.setText(
            t("history.undo_requested", config, count=self.undo_requests)
        )
        logger.debug("Queued GUI undo request {}", self.undo_requests)

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.title_label.setText(t("history.title", config))
        self.undo_button.setText(t("button.undo", config))
        self.open_button.setText(t("history.open_folder", config))
        self.manifest_button.setText(t("history.show_manifest", config))
