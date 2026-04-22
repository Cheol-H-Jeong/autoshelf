from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
from autoshelf.gui.widgets import Banner, Card, PrimaryButton, SecondaryButton


class OptionsScreen(QWidget):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.setAccessibleName("계획 옵션")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            Banner("info", "계획 전 확인", "기본값은 안전하게 계획만 보는 모드입니다.")
        )
        card = Card()
        self.dry_run = QRadioButton("안전하게 계획만 보기")
        self.apply_now = QRadioButton("즉시 적용")
        self.dry_run.setChecked(True)
        self.dry_run.setAccessibleName("안전하게 계획만 보기")
        self.apply_now.setAccessibleName("즉시 적용")
        self.conflict_policy = QComboBox()
        self.conflict_policy.addItems(["append", "skip", "overwrite", "prompt"])
        self.conflict_policy.setAccessibleName("충돌 정책")
        self.exclude_input = QComboBox()
        self.exclude_input.addItems(["node_modules", ".git", "photos>100MB", "+ 패턴 추가"])
        self.exclude_input.setAccessibleName("제외 패턴")
        self.gpu_toggle = QCheckBox("GPU 오프로드")
        self.gpu_toggle.setAccessibleName("GPU 오프로드")
        self.n_ctx = QSlider(Qt.Horizontal)
        self.n_ctx.setRange(2048, 8192)
        self.n_ctx.setValue(self.config.llm.context_window)
        self.n_ctx.setAccessibleName("컨텍스트 창")
        card.body.addWidget(QLabel("대상 동작"))
        card.body.addWidget(self.dry_run)
        card.body.addWidget(self.apply_now)
        card.body.addWidget(QLabel("충돌 정책"))
        card.body.addWidget(self.conflict_policy)
        card.body.addWidget(QLabel("제외 패턴"))
        card.body.addWidget(self.exclude_input)
        card.body.addWidget(QLabel("고급 옵션"))
        card.body.addWidget(self.n_ctx)
        card.body.addWidget(self.gpu_toggle)
        layout.addWidget(card)
        actions = QHBoxLayout()
        actions.addStretch()
        self.secondary = SecondaryButton("이전")
        self.primary = PrimaryButton("계획 세우기 →", "play")
        actions.addWidget(self.secondary)
        actions.addWidget(self.primary)
        layout.addLayout(actions)
