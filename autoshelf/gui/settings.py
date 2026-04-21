from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from autoshelf.i18n import t


class SettingsScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("settings.title")))
        form = QFormLayout()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.classification_model = QComboBox()
        self.classification_model.addItems(["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"])
        self.planning_model = QComboBox()
        self.planning_model.addItems(["claude-sonnet-4-6", "claude-opus-4-7"])
        self.review_model = QComboBox()
        self.review_model.addItems(["claude-sonnet-4-6", "claude-opus-4-7"])
        self.chunk_slider = QSlider(Qt.Horizontal)
        self.chunk_slider.setRange(4000, 32000)
        self.chunk_slider.setValue(20000)
        self.language = QComboBox()
        self.language.addItems(["auto", "ko", "en"])
        self.theme = QComboBox()
        self.theme.addItems(["system", "light", "dark"])
        self.dry_run = QCheckBox()
        self.exclude_globs = QTextEdit()
        form.addRow("API key", self.api_key)
        form.addRow("Classification model", self.classification_model)
        form.addRow("Planning model", self.planning_model)
        form.addRow("Review model", self.review_model)
        form.addRow("Chunk budget", self.chunk_slider)
        form.addRow("Language", self.language)
        form.addRow("Theme", self.theme)
        form.addRow("Dry-run", self.dry_run)
        form.addRow("Exclude globs", self.exclude_globs)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.test_connection = QPushButton(t("settings.test_connection"))
        self.save_button = QPushButton("Save")
        actions.addWidget(self.test_connection)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
