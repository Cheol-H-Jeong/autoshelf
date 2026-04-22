from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget

from autoshelf.gui.icons import icon


class Dropzone(QWidget):
    folderSelected = Signal(Path)

    def __init__(self, label: str = "정리할 폴더를 여기에 놓거나 클릭해서 선택하세요") -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("폴더 선택 영역")
        self.setAccessibleDescription(label)
        self.setMinimumHeight(280)
        self.setStyleSheet(
            "Dropzone { border: 2px dashed #9CA3AF; border-radius: 12px; background: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon("upload-cloud").pixmap(48, 48))
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            selected = QFileDialog.getExistingDirectory(self, "정리할 폴더 선택")
            if selected:
                self.folderSelected.emit(Path(selected))
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.folderSelected.emit(path)
                event.acceptProposedAction()
                return
