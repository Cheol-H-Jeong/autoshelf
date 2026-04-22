from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from autoshelf import __version__
from autoshelf.config import AppConfig
from autoshelf.gui.widgets import Banner, Card, DangerButton, PrimaryButton, SecondaryButton
from autoshelf.i18n import t
from autoshelf.llm.model_registry import list_variants
from autoshelf.llm.system_probe import probe_hardware


class SettingsScreen(QWidget):
    config_saved = Signal(AppConfig)

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        self.hardware = probe_hardware()
        self.setAccessibleName("설정")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self.title_label = QLabel("")
        self.privacy_label = QLabel("")
        self.privacy_label.setWordWrap(True)
        self.first_run_label = QLabel("")
        self.first_run_label.setWordWrap(True)
        self.low_ram_label = QLabel("")
        self.low_ram_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(Banner("info", "개인정보", "이 앱이 외부로 보내는 데이터 목록: 없음."))
        layout.addWidget(self.low_ram_label)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("설정 탭")
        layout.addWidget(self.tabs)

        general = Card()
        general_form = QFormLayout()
        self.language = QComboBox()
        self.language.addItems(["auto", "ko", "en"])
        self.language.setAccessibleName("언어")
        self.theme = QComboBox()
        self.theme.addItems(["system", "light", "dark"])
        self.theme.setAccessibleName("테마")
        self.dry_run = QCheckBox()
        self.dry_run.setAccessibleName("기본 드라이런")
        self.exclude_globs = QTextEdit()
        self.exclude_globs.setAccessibleName("기본 제외 패턴")
        self.language_label = QLabel("")
        self.theme_label = QLabel("")
        self.dry_run_label = QLabel("")
        self.exclude_globs_label = QLabel("")
        general_form.addRow(self.language_label, self.language)
        general_form.addRow(self.theme_label, self.theme)
        general_form.addRow(self.dry_run_label, self.dry_run)
        general_form.addRow(self.exclude_globs_label, self.exclude_globs)
        general.body.addLayout(general_form)
        self.tabs.addTab(general, "General")

        model = Card()
        model_form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["auto", "embedded", "local_http", "fake"])
        self.provider.setAccessibleName("LLM 공급자")
        self.model_picker = QComboBox()
        self.model_picker.setAccessibleName("모델")
        for variant in list_variants():
            self.model_picker.addItem(variant.model_id)
        self.model_details = QLabel("")
        self.model_details.setWordWrap(True)
        self.current_ram = QLabel("")
        self.download_button: QPushButton = SecondaryButton("")
        self.chunk_slider = QSlider(Qt.Horizontal)
        self.chunk_slider.setRange(2048, 8192)
        self.chunk_slider.setSingleStep(512)
        self.chunk_slider.setPageStep(1024)
        self.chunk_slider.setAccessibleName("컨텍스트 창")
        self.chunk_budget_label = QLabel("")
        model_form.addRow(t("settings.model.title", self.config), self.model_picker)
        model_form.addRow(t("settings.provider", self.config), self.provider)
        model_form.addRow(t("settings.system_ram", self.config), self.current_ram)
        model_form.addRow(self.chunk_budget_label, self.chunk_slider)
        model_form.addRow("", self.model_details)
        model_form.addRow("", self.download_button)
        model.body.addLayout(model_form)
        self.tabs.addTab(model, "Model")

        privacy = Card()
        self.privacy_label.setText("이 앱이 외부로 보내는 데이터 목록: 없음.")
        self.first_run_label.setText("로컬에는 설정, 실행 이력, 다운로드한 모델만 저장됩니다.")
        privacy.body.addWidget(self.privacy_label)
        privacy.body.addWidget(self.first_run_label)
        privacy.body.addWidget(DangerButton("모든 로컬 데이터 초기화…"))
        self.tabs.addTab(privacy, "Privacy")

        advanced = Card()
        self.remote_toggle = QCheckBox("AUTOSHELF_ALLOW_REMOTE_LLM")
        self.remote_toggle.setAccessibleName("원격 LLM 허용")
        advanced.body.addWidget(
            Banner("warning", "원격 LLM", "켜면 파일 요약이 외부 서비스로 나갈 수 있습니다.")
        )
        advanced.body.addWidget(self.remote_toggle)
        advanced.body.addWidget(SecondaryButton("로그 폴더 열기"))
        advanced.body.addWidget(SecondaryButton("설정 파일 열기"))
        self.tabs.addTab(advanced, "Advanced")

        about = Card()
        about.body.addWidget(QLabel(f"autoshelf {__version__}"))
        about.body.addWidget(QLabel("License: MIT"))
        self.update_toggle = QCheckBox("사용자 동의 후 업데이트 확인")
        self.update_toggle.setAccessibleName("업데이트 확인 동의")
        about.body.addWidget(self.update_toggle)
        self.tabs.addTab(about, "About")

        self.save_button: QPushButton = PrimaryButton("")
        self.status_label = QLabel("")
        layout.addWidget(self.save_button)
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
            line.strip()
            for line in self.exclude_globs.toPlainText().splitlines()
            if line.strip()
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
