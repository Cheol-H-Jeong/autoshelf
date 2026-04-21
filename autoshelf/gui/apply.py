from __future__ import annotations


def ApplyScreen():
    from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Apply"))
    layout.addWidget(QProgressBar())
    return widget
