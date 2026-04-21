from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
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
    config_saved = Signal(AppConfig)

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        layout = QVBoxLayout(self)
        self.title_label = QLabel("")
        layout.addWidget(self.title_label)
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
        self.api_key_label = QLabel("")
        self.classification_model_label = QLabel("")
        self.planning_model_label = QLabel("")
        self.review_model_label = QLabel("")
        self.chunk_budget_label = QLabel("")
        self.language_label = QLabel("")
        self.theme_label = QLabel("")
        self.dry_run_label = QLabel("")
        self.exclude_globs_label = QLabel("")
        form.addRow(self.api_key_label, self.api_key)
        form.addRow(self.classification_model_label, self.classification_model)
        form.addRow(self.planning_model_label, self.planning_model)
        form.addRow(self.review_model_label, self.review_model)
        form.addRow(self.chunk_budget_label, self.chunk_slider)
        form.addRow(self.language_label, self.language)
        form.addRow(self.theme_label, self.theme)
        form.addRow(self.dry_run_label, self.dry_run)
        form.addRow(self.exclude_globs_label, self.exclude_globs)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.test_connection = QPushButton("")
        self.save_button = QPushButton("")
        actions.addWidget(self.test_connection)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self._load_config()
        self.apply_config(self.config)
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
        logger.debug(
            "Saved GUI settings with theme={} language={}",
            config.theme,
            config.language_preference,
        )
        self.apply_config(config)
        self.status_label.setText(
            t("settings.saved", self.config, path=str(AppConfig.default_path()))
        )
        self.config_saved.emit(config)

    def _load_config(self) -> None:
        self.classification_model.setCurrentText(self.config.llm.classification_model)
        self.planning_model.setCurrentText(self.config.llm.planning_model)
        self.review_model.setCurrentText(self.config.llm.review_model)
        self.chunk_slider.setValue(self.config.max_chunk_tokens)
        self.language.setCurrentText(self.config.language_preference)
        self.theme.setCurrentText(self.config.theme)
        self.dry_run.setChecked(self.config.dry_run_default)
        self.exclude_globs.setPlainText("\n".join(self.config.exclude))

    def apply_config(self, config: AppConfig) -> None:
        self.title_label.setText(t("settings.title", config))
        self.api_key_label.setText(t("settings.api_key", config))
        self.classification_model_label.setText(t("settings.classification_model", config))
        self.planning_model_label.setText(t("settings.planning_model", config))
        self.review_model_label.setText(t("settings.review_model", config))
        self.chunk_budget_label.setText(t("settings.chunk_budget", config))
        self.language_label.setText(t("settings.language", config))
        self.theme_label.setText(t("settings.theme", config))
        self.dry_run_label.setText(t("settings.dry_run", config))
        self.exclude_globs_label.setText(t("settings.exclude_globs", config))
        self.test_connection.setText(t("settings.test_connection", config))
        self.save_button.setText(t("settings.save", config))
