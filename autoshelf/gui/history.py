from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from autoshelf.config import AppConfig
from autoshelf.gui.widgets import Card, EmptyState, PrimaryButton, SecondaryButton
from autoshelf.i18n import t


class HistoryScreen(QWidget):
    undo_queued = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.undo_requests = 0
        self.setAccessibleName("이력")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self.title_label = QLabel("")
        layout.addWidget(self.title_label)
        self.filter_bar = QHBoxLayout()
        self.filter_bar.addWidget(QLabel("기간"))
        self.filter_bar.addWidget(QLabel("root"))
        self.filter_bar.addWidget(QLabel("상태"))
        layout.addLayout(self.filter_bar)
        self.timeline = QVBoxLayout()
        layout.addLayout(self.timeline)
        self.empty_state = EmptyState(
            "clock",
            "아직 실행 이력이 없습니다",
            "폴더를 스캔하고 계획을 적용하면 여기에 표시됩니다.",
        )
        layout.addWidget(self.empty_state)
        self.run_card = Card()
        self.run_card.body.addWidget(QLabel("오늘"))
        self.run_card.body.addWidget(QLabel("demo-run · /tmp · 이동 3 · 충돌 0 · 격리 0 · 2초"))
        actions = QHBoxLayout()
        self.undo_button: QPushButton = PrimaryButton("")
        self.open_button: QPushButton = SecondaryButton("")
        self.manifest_button: QPushButton = SecondaryButton("")
        actions.addWidget(self.undo_button)
        actions.addWidget(self.open_button)
        actions.addWidget(self.manifest_button)
        self.run_card.body.addLayout(actions)
        layout.addWidget(self.run_card)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self.empty_state.hide()
        self.apply_config()

    def trigger_undo(self, config: AppConfig | None = None) -> None:
        self.undo_requests += 1
        self.status_label.setText(t("history.undo_requested", config, count=self.undo_requests))
        self.undo_queued.emit(self.undo_requests)
        logger.debug("Queued GUI undo request {}", self.undo_requests)

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.title_label.setText(t("history.title", config))
        self.undo_button.setText(t("button.undo", config))
        self.open_button.setText(t("history.open_folder", config))
        self.manifest_button.setText(t("history.show_manifest", config))
