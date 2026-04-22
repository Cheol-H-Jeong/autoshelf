from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from autoshelf.gui.design import SPACE_16


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("component", "card")
        self.setAccessibleName("카드")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_16, SPACE_16, SPACE_16, SPACE_16)
        layout.setSpacing(SPACE_16)

    @property
    def body(self) -> QVBoxLayout:
        return self.layout()  # type: ignore[return-value]
