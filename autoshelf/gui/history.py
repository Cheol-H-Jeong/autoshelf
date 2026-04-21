from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from autoshelf.i18n import t


class HistoryScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("history.title")))
        self.table = QTableWidget(1, 5)
        self.table.setHorizontalHeaderLabels(["Run ID", "Root", "Moved", "Status", "Action"])
        for column, value in enumerate(["demo-run", "/tmp", "3", "applied", "Undo"]):
            self.table.setItem(0, column, QTableWidgetItem(value))
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        actions.addWidget(QPushButton(t("button.undo")))
        actions.addWidget(QPushButton("Open folder"))
        actions.addWidget(QPushButton("Show manifest"))
        layout.addLayout(actions)
