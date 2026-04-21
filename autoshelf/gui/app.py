from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
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
        self.tabs = QTabWidget()
        self.home_screen = HomeScreen()
        self.review_screen = ReviewScreen()
        self.apply_screen = ApplyScreen()
        self.history_screen = HistoryScreen()
        self.settings_screen = SettingsScreen(config=self.config)
        self.tabs.addTab(self.home_screen, "")
        self.tabs.addTab(self.review_screen, "")
        self.tabs.addTab(self.apply_screen, "")
        self.tabs.addTab(self.history_screen, "")
        self.tabs.addTab(self.settings_screen, "")
        self.setCentralWidget(self.tabs)
        self.resize(1200, 760)
        self._bind_shortcuts()
        self.settings_screen.config_saved.connect(self._apply_runtime_config)
        self._refresh_labels()
        logger.debug("Initialized autoshelf main window")

    def _bind_shortcuts(self) -> None:
        self.apply_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.apply_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.apply_shortcut.activated.connect(self._shortcut_apply)

        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self._shortcut_undo)

        self.rescan_shortcut = QShortcut(QKeySequence("F5"), self)
        self.rescan_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.rescan_shortcut.activated.connect(self._shortcut_rescan)

    def _shortcut_apply(self) -> None:
        logger.debug("Triggered Ctrl+Enter apply shortcut")
        self.tabs.setCurrentWidget(self.apply_screen)
        self.apply_screen.start_apply()

    def _shortcut_undo(self) -> None:
        logger.debug("Triggered Ctrl+Z undo shortcut")
        self.tabs.setCurrentWidget(self.history_screen)
        self.history_screen.trigger_undo(self.config)

    def _shortcut_rescan(self) -> None:
        logger.debug("Triggered F5 rescan shortcut")
        self.tabs.setCurrentWidget(self.home_screen)
        self.home_screen.start_scan()

    def _apply_runtime_config(self, config: AppConfig) -> None:
        self.config = config
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, config)
        self._refresh_labels()
        self.settings_screen.apply_config(config)
        logger.debug("Applied runtime GUI configuration update")

    def _refresh_labels(self) -> None:
        self.setWindowTitle(t("app.title", self.config))
        self.tabs.setTabText(0, t("home.title", self.config))
        self.tabs.setTabText(1, t("review.title", self.config))
        self.tabs.setTabText(2, t("apply.title", self.config))
        self.tabs.setTabText(3, t("history.title", self.config))
        self.tabs.setTabText(4, t("settings.title", self.config))
        self.home_screen.apply_config(self.config)
        self.review_screen.apply_config(self.config)
        self.apply_screen.apply_config(self.config)
        self.history_screen.apply_config(self.config)


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
