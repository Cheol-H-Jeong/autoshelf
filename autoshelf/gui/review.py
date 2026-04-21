from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
from autoshelf.i18n import t
from autoshelf.planner.models import PlannerAssignment

from .review_models import PreviewItem, build_preview_items

STATUS_ROLE = Qt.UserRole + 1
HINT_ROLE = Qt.UserRole + 2


class ReviewScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        splitter = QSplitter()
        self.current_tree = QTreeWidget()
        self.current_tree.setHeaderLabels(["Current Tree"])
        self.proposed_tree = QTreeWidget()
        self.proposed_tree.setHeaderLabels(["Proposed Tree", "Preview"])
        self.proposed_tree.setDragDropMode(QTreeWidget.InternalMove)
        self.proposed_tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        self.proposed_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.proposed_tree.itemSelectionChanged.connect(self._update_hint_panel)
        splitter.addWidget(self.current_tree)
        splitter.addWidget(self.proposed_tree)
        layout.addWidget(splitter)

        self.assignment_table = QTableWidget(0, 5)
        self.assignment_table.setHorizontalHeaderLabels(
            ["Path", "Target", "Confidence", "Why this folder?", "Also relevant"]
        )
        self.title_label = QLabel("")
        layout.addWidget(self.title_label)
        layout.addWidget(self.assignment_table)
        self.folder_hint = QTextEdit()
        self.folder_hint.setReadOnly(True)
        layout.addWidget(self.folder_hint)

        button_row = QHBoxLayout()
        self.rerun_button = QPushButton("")
        self.approve_button = QPushButton("")
        button_row.addWidget(self.rerun_button)
        button_row.addWidget(self.approve_button)
        layout.addLayout(button_row)
        self.apply_config()
        self.load_preview(self._demo_assignments())

    def load_preview(self, assignments: list[PlannerAssignment]) -> None:
        preview_items = build_preview_items(assignments)
        self.current_tree.clear()
        self.proposed_tree.clear()
        self.assignment_table.setRowCount(0)

        self._populate_current_tree(preview_items)
        self._populate_proposed_tree(preview_items)
        self._populate_assignment_table(preview_items)
        self.current_tree.expandAll()
        self.proposed_tree.expandAll()
        self.assignment_table.resizeColumnsToContents()
        if self.proposed_tree.topLevelItemCount():
            first_item = self.proposed_tree.topLevelItem(0)
            self.proposed_tree.setCurrentItem(first_item)
            self._update_hint_panel()

    def _populate_current_tree(self, items: list[PreviewItem]) -> None:
        root_items: dict[str, QTreeWidgetItem] = {}
        for item in items:
            cursor = self.current_tree.invisibleRootItem()
            for part in item.source_parts:
                parent_key = self._node_path(cursor)
                key = f"{parent_key}/{part}"
                node = root_items.get(key)
                if node is None:
                    node = QTreeWidgetItem([part])
                    cursor.addChild(node)
                    root_items[key] = node
                cursor = node

    def _populate_proposed_tree(self, items: list[PreviewItem]) -> None:
        root_items: dict[str, QTreeWidgetItem] = {}
        folder_hints = self._folder_hints(items)
        for item in items:
            cursor = self.proposed_tree.invisibleRootItem()
            for depth, part in enumerate(item.target_parts):
                parent_key = self._node_path(cursor)
                key = f"{parent_key}/{part}"
                node = root_items.get(key)
                if node is None:
                    preview = ""
                    if depth == len(item.target_parts) - 1:
                        preview = self._preview_message(item)
                    node = QTreeWidgetItem([part, preview])
                    cursor.addChild(node)
                    root_items[key] = node
                    if depth < len(item.target_parts) - 1:
                        hint_key = tuple(item.target_parts[: depth + 1])
                        node.setData(0, HINT_ROLE, folder_hints.get(hint_key, ""))
                cursor = node
            cursor.setData(0, STATUS_ROLE, item.status)
            cursor.setData(0, HINT_ROLE, self._item_hint(item))
            self._apply_status_style(cursor, item.status)

    def _populate_assignment_table(self, items: list[PreviewItem]) -> None:
        for row, item in enumerate(items):
            self.assignment_table.insertRow(row)
            values = [
                item.source_path,
                item.target_folder,
                f"{item.confidence:.2f}",
                item.rationale or "No rationale recorded",
                ", ".join("/".join(parts) for parts in item.also_relevant) or "—",
            ]
            for column, value in enumerate(values):
                self.assignment_table.setItem(row, column, QTableWidgetItem(value))

    def _update_hint_panel(self) -> None:
        item = self.proposed_tree.currentItem()
        if item is None:
            self.folder_hint.clear()
            return
        hint = item.data(0, HINT_ROLE) or t("review.hint_placeholder")
        self.folder_hint.setPlainText(str(hint))

    def _folder_hints(self, items: list[PreviewItem]) -> dict[tuple[str, ...], str]:
        grouped: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for item in items:
            rationale = item.rationale or (
                f"Receives {item.filename} from {item.source_folder or '.'}."
            )
            for depth in range(1, len(item.target_parts)):
                grouped[tuple(item.target_parts[:depth])].append(rationale)
        return {
            key: "\n".join(dict.fromkeys(lines))
            for key, lines in grouped.items()
        }

    def _item_hint(self, item: PreviewItem) -> str:
        rationale = item.rationale or "No rationale recorded."
        related = ", ".join("/".join(parts) for parts in item.also_relevant) or "none"
        return (
            f"Move: {item.source_folder or '.'} -> {item.target_folder or '.'}\n"
            f"Why this folder: {rationale}\n"
            f"Also relevant: {related}"
        )

    def _preview_message(self, item: PreviewItem) -> str:
        if item.status == "moved":
            return t(
                "review.preview_move",
                source=item.source_folder or ".",
                target=item.target_folder or ".",
            )
        if item.status == "kept":
            return t("review.preview_kept")
        return t("review.preview_added")

    def _apply_status_style(self, item: QTreeWidgetItem, status: str) -> None:
        colors = {
            "moved": QColor("#1f9d55"),
            "kept": QColor("#6b7280"),
            "added": QColor("#2563eb"),
        }
        item.setForeground(0, QBrush(colors.get(status, QColor("#111827"))))
        item.setForeground(1, QBrush(colors.get(status, QColor("#111827"))))

    def _node_path(self, item: QTreeWidgetItem) -> str:
        parts: list[str] = []
        cursor = item
        while cursor and cursor.parent() is not None:
            parts.append(cursor.text(0))
            cursor = cursor.parent()
        return "/".join(reversed(parts))

    def _demo_assignments(self) -> list[PlannerAssignment]:
        return [
            PlannerAssignment(
                path="Inbox/draft.txt",
                primary_dir=["Documents", "Writing"],
                also_relevant=[["Archive", "Drafts"]],
                summary="Draft notes grouped with other working documents for faster review.",
                confidence=0.90,
            ),
            PlannerAssignment(
                path="Downloads/invoice.pdf",
                primary_dir=["Finance", "2026"],
                also_relevant=[["Documents", "Reference"]],
                summary=(
                    "Invoices stay under Finance by year so monthly statements remain together."
                ),
                confidence=0.94,
            ),
        ]

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.title_label.setText(t("review.title", config))
        self.folder_hint.setPlaceholderText(t("review.hint_placeholder", config))
        self.rerun_button.setText(t("review.rerun", config))
        self.approve_button.setText(f"{t('button.apply', config)} →")
