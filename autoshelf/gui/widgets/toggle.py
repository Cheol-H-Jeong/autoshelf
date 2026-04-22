from __future__ import annotations

from PySide6.QtWidgets import QComboBox


class ThemeToggle(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.addItems(["system", "light", "dark"])
        self.setAccessibleName("테마 선택")
        self.setAccessibleDescription("시스템, 밝게, 어둡게 중 테마를 선택합니다.")
