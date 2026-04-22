from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget

from autoshelf.config import AppConfig
from autoshelf.gui.widgets import Card, GhostButton, PrimaryButton, SecondaryButton
from autoshelf.i18n import t


class ApplyScreen(QWidget):
    apply_started = Signal()
    apply_progressed = Signal(int, str)
    apply_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.apply_in_progress = False
        self.apply_requests = 0
        self.setAccessibleName("진행")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self.card = Card()
        self.title_label = QLabel("")
        self.title_label.setObjectName("progressPhase")
        self.progress_bar = QProgressBar()
        self.progress_bar.setAccessibleName("전체 진행률")
        self.token_label = QLabel("")
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setAccessibleName("실행 로그")
        self.cancel_button: QPushButton = GhostButton("")
        self.wait_button = SecondaryButton("완료까지 대기")
        self.finish_button = PrimaryButton("파일 인덱스 열기", "file-text")
        self.finish_button.hide()
        self.card.body.addWidget(self.title_label)
        self.card.body.addWidget(self.progress_bar)
        self.card.body.addWidget(self.token_label)
        self.card.body.addWidget(self.log_view)
        self.card.body.addWidget(self.cancel_button)
        self.card.body.addWidget(self.wait_button)
        self.card.body.addWidget(self.finish_button)
        layout.addStretch()
        layout.addWidget(self.card)
        layout.addStretch()
        self.apply_config()

    def start_apply(self) -> None:
        if self.apply_in_progress:
            logger.debug("Ignoring apply request because an apply is already running")
            return
        self.apply_requests += 1
        self.apply_in_progress = True
        self.finish_button.hide()
        self.progress_bar.setValue(0)
        self.log_view.setPlainText(t("apply.started"))
        self.title_label.setText("모델 로딩 중")
        self.apply_started.emit()
        logger.debug("Starting GUI apply request {}", self.apply_requests)
        QTimer.singleShot(
            0, lambda: self._update_progress(35, "파일 분석 중 · 14 / 42 · 31 files/sec")
        )
        QTimer.singleShot(
            10, lambda: self._update_progress(72, "폴더 계획 중 · 30 / 42 · 18 tokens/sec")
        )
        QTimer.singleShot(20, self._complete_demo_apply)

    def _update_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.title_label.setText("파일 이동 중" if value >= 70 else "파일 분석 중")
        self.token_label.setText(message)
        self.log_view.append(message)
        self.apply_progressed.emit(value, message)

    def _complete_demo_apply(self) -> None:
        self._update_progress(100, "완료 · 42 / 42 · 2초")
        self.title_label.setText("정리가 완료되었습니다")
        self.log_view.append("파일 인덱스와 매니페스트를 기록했습니다.")
        self.finish_button.show()
        self.apply_in_progress = False
        self.apply_finished.emit()

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.title_label.setText(t("apply.title", config))
        self.token_label.setText(t("apply.tokens", config, count=0))
        self.cancel_button.setText(t("button.cancel", config))
