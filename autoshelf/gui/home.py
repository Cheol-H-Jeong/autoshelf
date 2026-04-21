from __future__ import annotations


def HomeScreen():
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Autoshelf Home"))
    row = QHBoxLayout()
    row.addWidget(QLabel("Folder"))
    row.addWidget(QLineEdit())
    row.addWidget(QPushButton("Browse"))
    layout.addLayout(row)
    stats = QTextEdit()
    stats.setReadOnly(True)
    stats.setPlainText("Scan stats will appear here.")
    layout.addWidget(stats)
    layout.addWidget(QPushButton("Start"))
    return widget
