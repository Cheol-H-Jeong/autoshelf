from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from autoshelf.gui.icons import icon
from autoshelf.gui.widgets.button import PrimaryButton


class EmptyState(QWidget):
    def __init__(self, icon_name: str, headline: str, hint: str, cta: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon(icon_name).pixmap(48, 48))
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.headline = QLabel(headline)
        self.headline.setAlignment(Qt.AlignCenter)
        self.hint = QLabel(hint)
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.headline)
        layout.addWidget(self.hint)
        self.primary_button: PrimaryButton | None = None
        if cta:
            self.primary_button = PrimaryButton(cta)
            layout.addWidget(self.primary_button, alignment=Qt.AlignCenter)
        self.setAccessibleName(headline)
