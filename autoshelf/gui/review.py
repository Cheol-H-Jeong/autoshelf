from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autoshelf.i18n import t


class ReviewScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        splitter = QSplitter()
        self.current_tree = QTreeWidget()
        self.current_tree.setHeaderLabels(["Current Tree"])
        self.proposed_tree = QTreeWidget()
        self.proposed_tree.setHeaderLabels(["Proposed Tree"])
        self.proposed_tree.setDragDropMode(QTreeWidget.InternalMove)
        self.proposed_tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        splitter.addWidget(self.current_tree)
        splitter.addWidget(self.proposed_tree)
        layout.addWidget(splitter)

        self.assignment_table = QTableWidget(0, 4)
        self.assignment_table.setHorizontalHeaderLabels(["Path", "Confidence", "Primary", "Also relevant"])
        layout.addWidget(QLabel(t("review.title")))
        layout.addWidget(self.assignment_table)

        button_row = QHBoxLayout()
        self.rerun_button = QPushButton("Re-run Planner")
        self.approve_button = QPushButton(f"{t('button.apply')} →")
        button_row.addWidget(self.rerun_button)
        button_row.addWidget(self.approve_button)
        layout.addLayout(button_row)
        self._seed_demo()

    def _seed_demo(self) -> None:
        current = QTreeWidgetItem(["Inbox"])
        proposed = QTreeWidgetItem(["Documents"])
        self.current_tree.addTopLevelItem(current)
        self.proposed_tree.addTopLevelItem(proposed)
        self.assignment_table.insertRow(0)
        for index, value in enumerate(["draft.txt", "0.90", "Documents", "Archive"]):
            self.assignment_table.setItem(0, index, QTableWidgetItem(value))
