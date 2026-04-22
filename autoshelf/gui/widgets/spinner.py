from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel


class Spinner(QLabel):
    def __init__(self) -> None:
        super().__init__("◜")
        self._frames = ["◜", "◠", "◝", "◞", "◡", "◟"]
        self._index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setAccessibleName("진행 표시")

    def start(self) -> None:
        self._timer.start(150)

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._index = (self._index + 1) % len(self._frames)
        self.setText(self._frames[self._index])
