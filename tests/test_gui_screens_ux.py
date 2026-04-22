import inspect
import os

from PySide6.QtWidgets import QApplication, QPushButton

from autoshelf.gui.apply import ApplyScreen
from autoshelf.gui.history import HistoryScreen
from autoshelf.gui.home import HomeScreen
from autoshelf.gui.options import OptionsScreen
from autoshelf.gui.review import ReviewScreen
from autoshelf.gui.settings import SettingsScreen


def test_each_screen_has_one_primary_action(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QApplication.instance() or QApplication([])
    screens = [HomeScreen(), OptionsScreen(), ApplyScreen()]
    screens += [ReviewScreen(), HistoryScreen(), SettingsScreen()]
    for screen in screens:
        primary = screen.findChildren(QPushButton, "primaryAction")
        assert len(primary) == 1
        assert primary[0].accessibleName()


def test_no_bare_qmessagebox_in_gui_screens():
    for module in [
        __import__("autoshelf.gui.home", fromlist=["x"]),
        __import__("autoshelf.gui.options", fromlist=["x"]),
        __import__("autoshelf.gui.apply", fromlist=["x"]),
        __import__("autoshelf.gui.review", fromlist=["x"]),
        __import__("autoshelf.gui.history", fromlist=["x"]),
        __import__("autoshelf.gui.settings", fromlist=["x"]),
    ]:
        assert "QMessageBox" not in inspect.getsource(module)
