from __future__ import annotations


def SettingsScreen():
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Settings"))
    layout.addWidget(QLabel("LLM, parser, and language settings will appear here."))
    return widget
