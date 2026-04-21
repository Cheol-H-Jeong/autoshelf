from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from autoshelf.config import AppConfig
from autoshelf.gui.apply import ApplyScreen
from autoshelf.gui.history import HistoryScreen
from autoshelf.gui.home import HomeScreen
from autoshelf.gui.review import ReviewScreen
from autoshelf.gui.settings import SettingsScreen
from autoshelf.gui.theme import apply_theme
from autoshelf.i18n import t


class AutoshelfWindow(QMainWindow):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        self.setWindowTitle(t("app.title", self.config))
        tabs = QTabWidget()
        tabs.addTab(HomeScreen(), t("home.title", self.config))
        tabs.addTab(ReviewScreen(), t("review.title", self.config))
        tabs.addTab(ApplyScreen(), t("apply.title", self.config))
        tabs.addTab(HistoryScreen(), t("history.title", self.config))
        tabs.addTab(SettingsScreen(config=self.config), t("settings.title", self.config))
        self.setCentralWidget(tabs)
        self.resize(1200, 760)


def launch_gui(test_mode: bool = False, config: AppConfig | None = None):
    app = QApplication.instance() or QApplication([])
    resolved_config = config or AppConfig.load()
    apply_theme(app, resolved_config)
    window = AutoshelfWindow(config=resolved_config)
    window.show()
    if test_mode:
        app.processEvents()
        return window
    app.exec()
    return window
