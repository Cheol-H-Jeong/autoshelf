from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


class KeyValueList(QWidget):
    def __init__(self, items: dict[str, str] | None = None) -> None:
        super().__init__()
        self.form = QFormLayout(self)
        self.setAccessibleName("상세 정보")
        for key, value in (items or {}).items():
            self.add_item(key, value)

    def add_item(self, key: str, value: str) -> None:
        self.form.addRow(QLabel(key), QLabel(value))
