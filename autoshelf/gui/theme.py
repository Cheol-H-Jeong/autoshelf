from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from autoshelf.config import AppConfig
from autoshelf.gui.design import DARK, LIGHT, PALETTES, Palette


def resolve_theme_name(config: AppConfig | None = None) -> str:
    requested = (config.theme if config else "system").lower()
    if requested in PALETTES:
        return requested
    app = QGuiApplication.instance()
    if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
        return "dark"
    return "light"


def current_palette(config: AppConfig | None = None) -> Palette:
    return PALETTES[resolve_theme_name(config)]


def apply_theme(app: QApplication, config: AppConfig | None = None) -> str:
    theme_name = resolve_theme_name(config)
    palette = PALETTES[theme_name]
    qt_palette = QPalette()
    qt_palette.setColor(QPalette.Window, palette.app_bg)
    qt_palette.setColor(QPalette.WindowText, palette.text)
    qt_palette.setColor(QPalette.Base, palette.surface)
    qt_palette.setColor(QPalette.AlternateBase, palette.surface_muted)
    qt_palette.setColor(QPalette.Text, palette.text)
    qt_palette.setColor(QPalette.Button, palette.surface)
    qt_palette.setColor(QPalette.ButtonText, palette.text)
    qt_palette.setColor(QPalette.Highlight, palette.accent)
    qt_palette.setColor(QPalette.HighlightedText, palette.accent_text)
    app.setPalette(qt_palette)
    app.setStyleSheet(render_qss(palette))
    app.setProperty("autoshelfTheme", theme_name)
    return theme_name


def render_qss(palette: Palette) -> str:
    template_path = Path(__file__).resolve().parents[2] / "resources" / "styles" / "app.qss"
    if not template_path.exists():
        template_path = Path(__file__).resolve().parents[3] / "resources" / "styles" / "app.qss"
    text = template_path.read_text(encoding="utf-8")
    for key, value in palette.__dict__.items():
        text = text.replace("{{ " + key + " }}", value)
    return text


__all__ = ["DARK", "LIGHT", "Palette", "apply_theme", "current_palette", "render_qss"]
