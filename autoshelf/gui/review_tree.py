from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

STATUS_ROLE = Qt.UserRole + 1
HINT_ROLE = Qt.UserRole + 2
SUMMARY_ROLE = Qt.UserRole + 3
SOURCE_ROLE = Qt.UserRole + 4


class ReviewTreeWidget(QTreeWidget):
    file_reassigned = Signal(str, list)

    def dropEvent(self, event: QDropEvent) -> None:
        source_item = self.currentItem()
        if source_item is None:
            event.ignore()
            return
        source_path = source_item.data(0, SOURCE_ROLE)
        if not isinstance(source_path, str):
            event.ignore()
            return
        destination_item = self.itemAt(event.position().toPoint())
        target_dir = self._target_dir_parts(destination_item)
        if target_dir is None:
            event.ignore()
            return
        self.file_reassigned.emit(source_path, target_dir)
        event.acceptProposedAction()

    def mark_folder_item(self, item: QTreeWidgetItem) -> None:
        item.setFlags(
            (item.flags() | Qt.ItemIsDropEnabled) & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsEditable
        )

    def mark_file_item(self, item: QTreeWidgetItem) -> None:
        item.setFlags(
            (item.flags() | Qt.ItemIsDragEnabled)
            & ~Qt.ItemIsDropEnabled
            & ~Qt.ItemIsEditable
        )

    def select_source_path(self, source_path: str) -> bool:
        matches = self.findItems(Path(source_path).name, Qt.MatchExactly | Qt.MatchRecursive, 0)
        for item in matches:
            if item.data(0, SOURCE_ROLE) == source_path:
                self.setCurrentItem(item)
                return True
        return False

    def _target_dir_parts(self, item: QTreeWidgetItem | None) -> list[str] | None:
        if item is None:
            return None
        parts = self._node_parts(item)
        source_path = item.data(0, SOURCE_ROLE)
        if isinstance(source_path, str):
            return parts[:-1]
        return parts

    def _node_parts(self, item: QTreeWidgetItem) -> list[str]:
        parts: list[str] = []
        cursor: QTreeWidgetItem | None = item
        while cursor is not None and cursor.parent() is not None:
            parts.append(cursor.text(0))
            cursor = cursor.parent()
        return list(reversed(parts))
