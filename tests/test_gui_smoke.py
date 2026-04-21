from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from autoshelf.gui.app import launch_gui
from autoshelf.gui.apply import ApplyScreen
from autoshelf.gui.history import HistoryScreen
from autoshelf.gui.home import HomeScreen
from autoshelf.gui.review import ReviewScreen
from autoshelf.gui.settings import SettingsScreen


def test_offscreen_gui_instantiates_all_screens(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    screens = [HomeScreen(), ReviewScreen(), ApplyScreen(), HistoryScreen(), SettingsScreen()]
    assert all(screen is not None for screen in screens)
    window = launch_gui(test_mode=True)
    assert window is not None
    app.processEvents()
