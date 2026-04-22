import os

from PySide6.QtWidgets import QApplication, QLabel

from autoshelf.config import AppConfig
from autoshelf.gui.theme import apply_theme


def test_theme_switch_updates_stylesheet(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    label = QLabel("sentinel")
    apply_theme(app, AppConfig(theme="light"))
    light_qss = label.qApp.styleSheet() if hasattr(label, "qApp") else app.styleSheet()
    apply_theme(app, AppConfig(theme="dark"))
    assert app.styleSheet() != light_qss
