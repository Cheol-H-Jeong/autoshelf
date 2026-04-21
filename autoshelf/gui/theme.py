from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from autoshelf.config import AppConfig


def apply_theme(app: QApplication, config: AppConfig) -> str:
    theme = config.theme.lower()
    if theme == "dark":
        app.setPalette(_dark_palette())
        return "dark"
    if theme == "light":
        app.setPalette(_light_palette())
        return "light"
    app.setPalette(app.style().standardPalette())
    return "system"


def _light_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f6f1e8"))
    palette.setColor(QPalette.WindowText, QColor("#1e1f24"))
    palette.setColor(QPalette.Base, QColor("#fffdf8"))
    palette.setColor(QPalette.AlternateBase, QColor("#eee6d8"))
    palette.setColor(QPalette.ToolTipBase, QColor("#fffdf8"))
    palette.setColor(QPalette.ToolTipText, QColor("#1e1f24"))
    palette.setColor(QPalette.Text, QColor("#1e1f24"))
    palette.setColor(QPalette.Button, QColor("#d9c4a2"))
    palette.setColor(QPalette.ButtonText, QColor("#1e1f24"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor("#3b7f6b"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor("#2f6fdb"))
    return palette


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#172027"))
    palette.setColor(QPalette.WindowText, QColor("#edf2f7"))
    palette.setColor(QPalette.Base, QColor("#11181e"))
    palette.setColor(QPalette.AlternateBase, QColor("#23303a"))
    palette.setColor(QPalette.ToolTipBase, QColor("#23303a"))
    palette.setColor(QPalette.ToolTipText, QColor("#edf2f7"))
    palette.setColor(QPalette.Text, QColor("#edf2f7"))
    palette.setColor(QPalette.Button, QColor("#2c4951"))
    palette.setColor(QPalette.ButtonText, QColor("#edf2f7"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor("#5fb3a1"))
    palette.setColor(QPalette.HighlightedText, QColor("#0d1318"))
    palette.setColor(QPalette.Link, QColor("#7cc9ff"))
    return palette
