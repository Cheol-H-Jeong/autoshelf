from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
from autoshelf.i18n import t
from autoshelf.llm.model_registry import list_variants
from autoshelf.llm.system_probe import probe_hardware


class SettingsScreen(QWidget):
    config_saved = Signal(AppConfig)

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        self.hardware = probe_hardware()
        layout = QVBoxLayout(self)
        self.title_label = QLabel("")
        self.privacy_label = QLabel("")
        self.privacy_label.setWordWrap(True)
        self.first_run_label = QLabel("")
        self.first_run_label.setWordWrap(True)
        self.low_ram_label = QLabel("")
        self.low_ram_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.privacy_label)
        layout.addWidget(self.first_run_label)
        layout.addWidget(self.low_ram_label)

        model_box = QGroupBox()
        model_form = QFormLayout(model_box)
        self.provider = QComboBox()
        self.provider.addItems(["auto", "embedded", "local_http", "fake"])
        self.model_picker = QComboBox()
        for variant in list_variants():
            self.model_picker.addItem(variant.model_id)
        self.model_details = QLabel("")
        self.model_details.setWordWrap(True)
        self.current_ram = QLabel("")
        self.download_button = QPushButton("")
        model_form.addRow(t("settings.model.title", self.config), self.model_picker)
        model_form.addRow(t("settings.provider", self.config), self.provider)
        model_form.addRow(t("settings.system_ram", self.config), self.current_ram)
        model_form.addRow("", self.model_details)
        model_form.addRow("", self.download_button)
        layout.addWidget(model_box)

        form = QFormLayout()
        self.chunk_slider = QSlider(Qt.Horizontal)
        self.chunk_slider.setRange(2048, 8192)
        self.chunk_slider.setSingleStep(512)
        self.chunk_slider.setPageStep(1024)
        self.language = QComboBox()
        self.language.addItems(["auto", "ko", "en"])
        self.theme = QComboBox()
        self.theme.addItems(["system", "light", "dark"])
        self.dry_run = QCheckBox()
        self.exclude_globs = QTextEdit()
        self.chunk_budget_label = QLabel("")
        self.language_label = QLabel("")
        self.theme_label = QLabel("")
        self.dry_run_label = QLabel("")
        self.exclude_globs_label = QLabel("")
        form.addRow(self.chunk_budget_label, self.chunk_slider)
        form.addRow(self.language_label, self.language)
        form.addRow(self.theme_label, self.theme)
        form.addRow(self.dry_run_label, self.dry_run)
        form.addRow(self.exclude_globs_label, self.exclude_globs)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.save_button = QPushButton("")
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self._load_config()
        self.apply_config(self.config)
        self.save_button.clicked.connect(self.save_config)
        self.model_picker.currentTextChanged.connect(self._refresh_model_details)

    def save_config(self) -> None:
        config = self.config.model_copy(deep=True)
        config.llm.provider = self.provider.currentText()
        config.llm.model_id = self.model_picker.currentText()
        config.llm.planning_model = config.llm.model_id
        config.llm.classification_model = config.llm.model_id
        config.llm.review_model = config.llm.model_id
        config.llm.context_window = self.chunk_slider.value()
        config.max_chunk_tokens = config.llm.context_window // 4
        config.language_preference = self.language.currentText()
        config.theme = self.theme.currentText()
        config.dry_run_default = self.dry_run.isChecked()
        config.exclude = [
            line.strip() for line in self.exclude_globs.toPlainText().splitlines() if line.strip()
        ]
        config.save()
        self.config = config
        logger.debug(
            "Saved GUI settings with theme={} language={} provider={} model={}",
            config.theme,
            config.language_preference,
            config.llm.provider,
            config.llm.model_id,
        )
        self.apply_config(config)
        self.status_label.setText(
            t("settings.saved", self.config, path=str(AppConfig.default_path()))
        )
        self.config_saved.emit(config)

    def _load_config(self) -> None:
        self.provider.setCurrentText(self.config.llm.provider)
        self.model_picker.setCurrentText(self.config.llm.model_id)
        self.chunk_slider.setValue(self.config.llm.context_window)
        self.language.setCurrentText(self.config.language_preference)
        self.theme.setCurrentText(self.config.theme)
        self.dry_run.setChecked(self.config.dry_run_default)
        self.exclude_globs.setPlainText("\n".join(self.config.exclude))
        self.current_ram.setText(f"{self.hardware.ram_gb} GB")
        self._refresh_model_details()

    def apply_config(self, config: AppConfig) -> None:
        self.title_label.setText(t("settings.title", config))
        self.privacy_label.setText(t("settings.privacy.headline", config))
        self.first_run_label.setText(t("home.banner.first_run", config))
        self.low_ram_label.setText(
            t("settings.low_ram_warning", config, ram_gb=self.hardware.ram_gb)
            if self.hardware.ram_gb < 8
            else ""
        )
        self.chunk_budget_label.setText(t("settings.chunk_budget", config))
        self.language_label.setText(t("settings.language", config))
        self.theme_label.setText(t("settings.theme", config))
        self.dry_run_label.setText(t("settings.dry_run", config))
        self.exclude_globs_label.setText(t("settings.exclude_globs", config))
        self.download_button.setText(t("settings.model.download", config))
        self.save_button.setText(t("settings.save", config))
        self._refresh_model_details()

    def _refresh_model_details(self) -> None:
        current = next(
            variant
            for variant in list_variants()
            if variant.model_id == self.model_picker.currentText()
        )
        self.model_details.setText(
            " | ".join(
                [
                    t("settings.model.download_size", self.config, size=current.download_mb),
                    t(
                        "settings.model.recommended_ram",
                        self.config,
                        ram=current.recommended_ram_gb,
                    ),
                    current.license_name,
                    current.throughput_hint,
                ]
            )
        )
