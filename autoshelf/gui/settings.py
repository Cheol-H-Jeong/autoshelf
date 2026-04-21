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

from autoshelf.config import AppConfig
from autoshelf.i18n import t


class SettingsScreen(QWidget):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("settings.title", self.config)))
        form = QFormLayout()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.classification_model = QComboBox()
        self.classification_model.addItems(
            ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]
        )
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
        self.test_connection = QPushButton(t("settings.test_connection", self.config))
        self.save_button = QPushButton(t("settings.save", self.config))
        actions.addWidget(self.test_connection)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self._load_config()
        self.save_button.clicked.connect(self.save_config)

    def save_config(self) -> None:
        config = self.config.model_copy(deep=True)
        config.llm.classification_model = self.classification_model.currentText()
        config.llm.planning_model = self.planning_model.currentText()
        config.llm.review_model = self.review_model.currentText()
        config.max_chunk_tokens = self.chunk_slider.value()
        config.language_preference = self.language.currentText()
        config.theme = self.theme.currentText()
        config.dry_run_default = self.dry_run.isChecked()
        config.exclude = [
            line.strip() for line in self.exclude_globs.toPlainText().splitlines() if line.strip()
        ]
        config.save()
        self.config = config
        self.status_label.setText(
            t("settings.saved", self.config, path=str(AppConfig.default_path()))
        )

    def _load_config(self) -> None:
        self.classification_model.setCurrentText(self.config.llm.classification_model)
        self.planning_model.setCurrentText(self.config.llm.planning_model)
        self.review_model.setCurrentText(self.config.llm.review_model)
        self.chunk_slider.setValue(self.config.max_chunk_tokens)
        self.language.setCurrentText(self.config.language_preference)
        self.theme.setCurrentText(self.config.theme)
        self.dry_run.setChecked(self.config.dry_run_default)
        self.exclude_globs.setPlainText("\n".join(self.config.exclude))
