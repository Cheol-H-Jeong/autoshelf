from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from autoshelf.gui.widgets.toggle import ThemeToggle


class TitleBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        self.title = QLabel("autoshelf")
        self.privacy = QLabel("100% 온디바이스")
        self.ram = QLabel("RAM")
        self.model = QLabel("Model")
        self.theme = ThemeToggle()
        layout.addWidget(self.title)
        layout.addWidget(self.privacy)
        layout.addStretch()
        layout.addWidget(self.ram)
        layout.addWidget(self.model)
        layout.addWidget(self.theme)
        self.setAccessibleName("상태 표시줄")
