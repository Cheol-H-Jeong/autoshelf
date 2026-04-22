from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from autoshelf.gui.design import SPACE_8, SPACE_16
from autoshelf.gui.icons import icon


class Banner(QFrame):
    def __init__(self, tone: str = "info", headline: str = "", body: str = "") -> None:
        super().__init__()
        self.setProperty("component", "banner")
        self.setProperty("tone", tone)
        self.setAccessibleName(headline or "알림")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(SPACE_16, SPACE_8, SPACE_16, SPACE_8)
        outer.setSpacing(SPACE_8)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon(_tone_icon(tone)).pixmap(20, 20))
        outer.addWidget(self.icon_label)
        texts = QVBoxLayout()
        self.headline = QLabel(headline)
        self.headline.setObjectName("bannerHeadline")
        self.body = QLabel(body)
        self.body.setWordWrap(True)
        texts.addWidget(self.headline)
        texts.addWidget(self.body)
        outer.addLayout(texts)

    def set_message(self, headline: str, body: str = "", tone: str = "info") -> None:
        self.setProperty("tone", tone)
        self.headline.setText(headline)
        self.body.setText(body)
        self.icon_label.setPixmap(icon(_tone_icon(tone)).pixmap(20, 20))
        self.setAccessibleName(headline)


def _tone_icon(tone: str) -> str:
    return {
        "success": "check",
        "warning": "alert-triangle",
        "danger": "alert-triangle",
        "info": "info",
    }.get(tone, "info")
