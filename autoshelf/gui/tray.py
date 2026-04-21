from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon

from autoshelf.config import AppConfig
from autoshelf.i18n import t


class TrayController(QObject):
    scan_downloads_requested = Signal()
    toggle_window_requested = Signal()
    quit_requested = Signal()

    def __init__(self, window: QMainWindow, config: AppConfig) -> None:
        super().__init__(window)
        self.window = window
        self.config = config
        self.last_status = t("tray.status_idle", config)
        self.downloads_path = Path.home() / "Downloads"
        self.allow_close = False

        self.tray_icon = QSystemTrayIcon(_build_tray_icon(), self)
        self.menu = QMenu(window)
        self.status_action = QAction("", self.menu)
        self.status_action.setEnabled(False)
        self.toggle_action = QAction("", self.menu)
        self.scan_downloads_action = QAction("", self.menu)
        self.quit_action = QAction("", self.menu)

        self.menu.addAction(self.status_action)
        self.menu.addSeparator()
        self.menu.addAction(self.toggle_action)
        self.menu.addAction(self.scan_downloads_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.toggle_action.triggered.connect(self.toggle_window_requested.emit)
        self.scan_downloads_action.triggered.connect(self.scan_downloads_requested.emit)
        self.quit_action.triggered.connect(self.request_quit)
        self.tray_icon.activated.connect(self._handle_activation)
        self.tray_icon.setContextMenu(self.menu)
        self.refresh_labels(config)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
            logger.debug("Initialized GUI tray icon")
        else:
            logger.debug("System tray unavailable; tray actions remain inactive")

    def refresh_labels(self, config: AppConfig) -> None:
        self.config = config
        self.status_action.setText(
            t("tray.status_prefix", config, status=self.last_status)
        )
        self.toggle_action.setText(
            t("tray.hide_window", config)
            if self.window.isVisible()
            else t("tray.show_window", config)
        )
        self.scan_downloads_action.setText(
            t("tray.scan_downloads", config, path=str(self.downloads_path))
        )
        self.quit_action.setText(t("tray.quit", config))
        tooltip = t(
            "tray.tooltip",
            config,
            status=self.last_status,
            path=str(self.downloads_path),
        )
        self.tray_icon.setToolTip(tooltip)

    def set_status(
        self,
        status: str,
        *,
        message_key: str | None = None,
        message_kwargs: dict[str, object] | None = None,
    ) -> None:
        self.last_status = status
        self.refresh_labels(self.config)
        if message_key and self.tray_icon.isVisible():
            message = t(message_key, self.config, **(message_kwargs or {}))
            self.tray_icon.showMessage(t("app.title", self.config), message)

    def sync_window_visibility(self) -> None:
        self.refresh_labels(self.config)

    def handle_close_event(self, event: QCloseEvent) -> bool:
        if self.allow_close:
            self.allow_close = False
            return False
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.window.hide()
        self.sync_window_visibility()
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                t("app.title", self.config),
                t("tray.minimized", self.config),
            )
        event.ignore()
        logger.debug("Minimized main window to system tray")
        return True

    def request_quit(self) -> None:
        self.allow_close = True
        self.quit_requested.emit()

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_window_requested.emit()


def _build_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("#00000000"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#17312f"))
    painter.setBrush(QColor("#5fb3a1"))
    painter.drawRoundedRect(3, 3, 26, 26, 7, 7)
    painter.setBrush(QColor("#f5f5f4"))
    painter.drawRoundedRect(8, 8, 16, 5, 2, 2)
    painter.drawRoundedRect(8, 15, 16, 10, 2, 2)
    painter.end()
    return QIcon(pixmap)
