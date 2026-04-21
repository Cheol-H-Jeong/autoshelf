from __future__ import annotations

from loguru import logger
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from autoshelf.config import AppConfig


def apply_theme(app: QApplication, config: AppConfig) -> str:
    theme = config.theme.lower()
    if theme == "dark":
        app.setPalette(_dark_palette())
        app.setStyleSheet(_theme_stylesheet("dark"))
        logger.debug("Applied GUI theme: dark")
        return "dark"
    if theme == "light":
        app.setPalette(_light_palette())
        app.setStyleSheet(_theme_stylesheet("light"))
        logger.debug("Applied GUI theme: light")
        return "light"
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet(_theme_stylesheet("system"))
    logger.debug("Applied GUI theme: system")
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


def _theme_stylesheet(theme: str) -> str:
    tokens = _theme_tokens(theme)
    return f"""
QMainWindow {{
    background: {tokens["window"]};
}}
QWidget {{
    background-color: {tokens["window"]};
    color: {tokens["text"]};
    selection-background-color: {tokens["accent"]};
    selection-color: {tokens["accent_text"]};
}}
QLineEdit, QTextEdit, QListWidget, QTreeWidget, QTableWidget, QComboBox, QSpinBox, QSlider {{
    background-color: {tokens["surface"]};
    color: {tokens["text"]};
    border: 1px solid {tokens["border"]};
    border-radius: 6px;
}}
QPushButton {{
    background-color: {tokens["button"]};
    color: {tokens["button_text"]};
    border: 1px solid {tokens["border"]};
    border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton:hover {{
    background-color: {tokens["button_hover"]};
}}
QPushButton:disabled {{
    background-color: {tokens["disabled"]};
    color: {tokens["muted_text"]};
}}
QHeaderView::section {{
    background-color: {tokens["surface_alt"]};
    color: {tokens["text"]};
    border: 0;
    border-bottom: 1px solid {tokens["border"]};
    padding: 6px;
}}
QTabWidget::pane {{
    border: 1px solid {tokens["border"]};
}}
QTabBar::tab {{
    background-color: {tokens["surface_alt"]};
    color: {tokens["muted_text"]};
    padding: 8px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {tokens["surface"]};
    color: {tokens["text"]};
}}
QProgressBar {{
    border: 1px solid {tokens["border"]};
    border-radius: 6px;
    background-color: {tokens["surface_alt"]};
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {tokens["accent"]};
    border-radius: 5px;
}}
""".strip()


def _theme_tokens(theme: str) -> dict[str, str]:
    if theme == "dark":
        return {
            "window": "#172027",
            "surface": "#11181e",
            "surface_alt": "#23303a",
            "text": "#edf2f7",
            "muted_text": "#b9c4cd",
            "border": "#35505d",
            "button": "#2c4951",
            "button_hover": "#355a64",
            "button_text": "#edf2f7",
            "disabled": "#23303a",
            "accent": "#5fb3a1",
            "accent_text": "#0d1318",
        }
    if theme == "light":
        return {
            "window": "#f6f1e8",
            "surface": "#fffdf8",
            "surface_alt": "#eee6d8",
            "text": "#1e1f24",
            "muted_text": "#5f6670",
            "border": "#d1c2a7",
            "button": "#d9c4a2",
            "button_hover": "#e3d3b8",
            "button_text": "#1e1f24",
            "disabled": "#e6ddcf",
            "accent": "#3b7f6b",
            "accent_text": "#ffffff",
        }
    return {
        "window": "#f4f4f5",
        "surface": "#ffffff",
        "surface_alt": "#ececee",
        "text": "#171717",
        "muted_text": "#52525b",
        "border": "#d4d4d8",
        "button": "#e4e4e7",
        "button_hover": "#d4d4d8",
        "button_text": "#171717",
        "disabled": "#e4e4e7",
        "accent": "#2563eb",
        "accent_text": "#ffffff",
    }
