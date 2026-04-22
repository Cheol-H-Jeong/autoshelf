from __future__ import annotations

from PySide6.QtWidgets import QTreeWidget


class TreeView(QTreeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("트리 비교")
        self.setHeaderLabels(["폴더", "상태"])
