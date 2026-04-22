from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from autoshelf.config import AppConfig
from autoshelf.gui.apply import ApplyScreen
from autoshelf.gui.history import HistoryScreen
from autoshelf.gui.home import HomeScreen
from autoshelf.gui.options import OptionsScreen
from autoshelf.gui.review import ReviewScreen
from autoshelf.gui.settings import SettingsScreen
from autoshelf.gui.theme import apply_theme
from autoshelf.gui.tray import TrayController
from autoshelf.i18n import t


class AutoshelfWindow(QMainWindow):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()
        self.tabs = QTabWidget()
        self.home_screen = HomeScreen()
        self.options_screen = OptionsScreen(config=self.config)
        self.review_screen = ReviewScreen()
        self.apply_screen = ApplyScreen()
        self.history_screen = HistoryScreen()
        self.settings_screen = SettingsScreen(config=self.config)
        self.tabs.addTab(self.home_screen, "")
        self.tabs.addTab(self.options_screen, "")
        self.tabs.addTab(self.review_screen, "")
        self.tabs.addTab(self.apply_screen, "")
        self.tabs.addTab(self.history_screen, "")
        self.tabs.addTab(self.settings_screen, "")
        self.setCentralWidget(self.tabs)
        self.resize(1200, 760)
        self.tray_controller = TrayController(self, self.config)
        self._bind_shortcuts()
        self._bind_tray()
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
        self.cheatsheet_shortcut = QShortcut(QKeySequence("Ctrl+?"), self)
        self.cheatsheet_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.cheatsheet_shortcut.activated.connect(self._show_cheatsheet)

    def _show_cheatsheet(self) -> None:
        self.statusBar().showMessage("Ctrl+Enter 적용 · Ctrl+Z 되돌리기 · F5 다시 스캔", 4000)

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

    def _bind_tray(self) -> None:
        self.tray_controller.scan_downloads_requested.connect(self._scan_downloads_from_tray)
        self.tray_controller.toggle_window_requested.connect(self._toggle_window_visibility)
        self.tray_controller.quit_requested.connect(self.close)
        self.home_screen.scan_started.connect(self._update_scan_status)
        self.home_screen.scan_finished.connect(self._complete_scan_status)
        self.home_screen.plan_requested.connect(self._on_plan_requested)
        self.apply_screen.apply_started.connect(self._set_apply_started_status)
        self.apply_screen.apply_progressed.connect(self._update_apply_status)
        self.apply_screen.apply_finished.connect(self._complete_apply_status)
        self.history_screen.undo_queued.connect(self._update_undo_status)

    def _apply_runtime_config(self, config: AppConfig) -> None:
        self.config = config
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, config)
        self._refresh_labels()
        self.settings_screen.apply_config(config)
        self.tray_controller.refresh_labels(config)
        logger.debug("Applied runtime GUI configuration update")

    def _refresh_labels(self) -> None:
        self.setWindowTitle(t("app.title", self.config))
        self.tabs.setTabText(0, t("home.title", self.config))
        self.tabs.setTabText(1, "옵션")
        self.tabs.setTabText(2, t("review.title", self.config))
        self.tabs.setTabText(3, t("apply.title", self.config))
        self.tabs.setTabText(4, t("history.title", self.config))
        self.tabs.setTabText(5, t("settings.title", self.config))
        self.home_screen.apply_config(self.config)
        self.review_screen.apply_config(self.config)
        self.apply_screen.apply_config(self.config)
        self.history_screen.apply_config(self.config)

    def _on_plan_requested(self, root: str) -> None:
        logger.debug("Plan requested from Home for root={}", root)
        self.tabs.setCurrentWidget(self.options_screen)
        self.statusBar().showMessage(f"옵션을 확인한 뒤 '계획 세우기'를 눌러 주세요 · {root}", 6000)
        if hasattr(self.options_screen, "set_root"):
            self.options_screen.set_root(root)
        self.home_screen.plan_button.setEnabled(True)
        self.home_screen.plan_button.setText(
            f"{t('button.plan', self.config)} 세우기 →"
        )

    def _scan_downloads_from_tray(self) -> None:
        downloads_path = self.tray_controller.downloads_path
        self.tabs.setCurrentWidget(self.home_screen)
        self.home_screen.start_scan(downloads_path)
        self._restore_window()

    def _toggle_window_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self._restore_window()
        self.tray_controller.sync_window_visibility()

    def _restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.tray_controller.sync_window_visibility()

    def _update_scan_status(self, root: str) -> None:
        target = root or str(Path.home())
        self.tray_controller.set_status(
            t("tray.status_scan_running", self.config, path=target),
            message_key="tray.notification_scan_started",
            message_kwargs={"path": target},
        )

    def _complete_scan_status(self, root: str, stats: dict) -> None:
        files = int(stats.get("files", 0))
        target = root or str(Path.home())
        self.tray_controller.set_status(
            t("tray.status_scan_complete", self.config, count=files),
            message_key="tray.notification_scan_complete",
            message_kwargs={"count": files, "path": target},
        )

    def _set_apply_started_status(self) -> None:
        self.tray_controller.set_status(
            t("tray.status_apply_running", self.config),
            message_key="tray.notification_apply_started",
        )

    def _update_apply_status(self, value: int, _message: str) -> None:
        self.tray_controller.set_status(t("tray.status_apply_progress", self.config, percent=value))

    def _complete_apply_status(self) -> None:
        self.tray_controller.set_status(
            t("tray.status_apply_complete", self.config),
            message_key="tray.notification_apply_complete",
        )

    def _update_undo_status(self, count: int) -> None:
        self.tray_controller.set_status(
            t("tray.status_undo_ready", self.config, count=count),
            message_key="tray.notification_undo_ready",
            message_kwargs={"count": count},
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.tray_controller.handle_close_event(event):
            return
        super().closeEvent(event)


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
