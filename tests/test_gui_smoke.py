from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from autoshelf.config import AppConfig
from autoshelf.gui.app import AutoshelfWindow, launch_gui
from autoshelf.gui.apply import ApplyScreen
from autoshelf.gui.history import HistoryScreen
from autoshelf.gui.home import HomeScreen
from autoshelf.gui.settings import SettingsScreen
from autoshelf.gui.theme import apply_theme


def test_offscreen_gui_instantiates_all_screens(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    from autoshelf.gui.review import ReviewScreen

    screens = [HomeScreen(), ReviewScreen(), ApplyScreen(), HistoryScreen(), SettingsScreen()]
    assert all(screen is not None for screen in screens)
    window = launch_gui(test_mode=True)
    assert window is not None
    app.processEvents()


def test_apply_theme_sets_expected_dark_palette(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    selected = apply_theme(app, AppConfig(theme="dark"))
    assert selected == "dark"
    assert app.palette().color(QPalette.Window).name() == "#172027"
    assert "QMainWindow" in app.styleSheet()


def test_settings_save_updates_window_theme_and_language(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(AppConfig, "default_path", classmethod(lambda cls: Path(config_path)))
    window = AutoshelfWindow(config=AppConfig(theme="light", language_preference="en"))
    window.settings_screen.theme.setCurrentText("dark")
    window.settings_screen.language.setCurrentText("ko")
    window.settings_screen.save_config()
    app.processEvents()
    assert window.windowTitle() == "오토셸프"
    assert app.palette().color(QPalette.Window).name() == "#172027"
    assert window.tabs.tabText(0) == "홈"


def test_window_shortcuts_trigger_apply_undo_and_rescan(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    window = AutoshelfWindow(config=AppConfig(language_preference="en"))
    window.show()
    window.tabs.setFocus()
    app.processEvents()
    QTest.keyClick(window.tabs, Qt.Key_F5)
    QTest.keyClick(window.tabs, Qt.Key_Return, Qt.ControlModifier)
    QTest.keyClick(window.tabs, Qt.Key_Z, Qt.ControlModifier)
    app.processEvents()
    QTest.qWait(50)
    app.processEvents()
    assert window.home_screen.scan_requests == 1
    assert window.apply_screen.apply_requests == 1
    assert window.apply_screen.progress_bar.value() == 100
    assert window.history_screen.undo_requests == 1


def test_settings_screen_saves_config(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(AppConfig, "default_path", classmethod(lambda cls: Path(config_path)))
    screen = SettingsScreen(config=AppConfig())
    screen.theme.setCurrentText("dark")
    screen.language.setCurrentText("ko")
    screen.chunk_slider.setValue(16000)
    screen.exclude_globs.setPlainText(".git\nbuild")
    screen.save_config()
    saved = AppConfig.load(config_path)
    assert saved.theme == "dark"
    assert saved.language_preference == "ko"
    assert saved.max_chunk_tokens == 16000
    assert saved.exclude == [".git", "build"]
    assert "Saved" in screen.status_label.text() or "저장" in screen.status_label.text()
    app.processEvents()
