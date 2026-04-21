from __future__ import annotations


def HistoryScreen():
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("History"))
    layout.addWidget(QLabel("Past runs and undo actions will appear here."))
    return widget
