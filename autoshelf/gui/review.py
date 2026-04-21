from __future__ import annotations


def ReviewScreen():
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Review"))
    layout.addWidget(QLabel("Planned tree and assignments will appear here."))
    return widget
