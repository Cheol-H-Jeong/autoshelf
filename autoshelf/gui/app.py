from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from autoshelf.gui.apply import ApplyScreen
from autoshelf.gui.history import HistoryScreen
from autoshelf.gui.home import HomeScreen
from autoshelf.gui.review import ReviewScreen
from autoshelf.gui.settings import SettingsScreen
from autoshelf.i18n import t


class AutoshelfWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("app.title"))
        tabs = QTabWidget()
        tabs.addTab(HomeScreen(), t("home.title"))
        tabs.addTab(ReviewScreen(), t("review.title"))
        tabs.addTab(ApplyScreen(), t("apply.title"))
        tabs.addTab(HistoryScreen(), t("history.title"))
        tabs.addTab(SettingsScreen(), t("settings.title"))
        self.setCentralWidget(tabs)
        self.resize(1200, 760)


def launch_gui(test_mode: bool = False):
    app = QApplication.instance() or QApplication([])
    window = AutoshelfWindow()
    window.show()
    if test_mode:
        app.processEvents()
        return window
    app.exec()
    return window
