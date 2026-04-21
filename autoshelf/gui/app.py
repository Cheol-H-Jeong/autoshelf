from __future__ import annotations


def launch_gui() -> None:
    """Launch the PySide6 GUI."""

    try:
        from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for the GUI. Install autoshelf[gui].") from exc

    from autoshelf.gui.apply import ApplyScreen
    from autoshelf.gui.history import HistoryScreen
    from autoshelf.gui.home import HomeScreen
    from autoshelf.gui.review import ReviewScreen
    from autoshelf.gui.settings import SettingsScreen

    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setWindowTitle("autoshelf")
    tabs = QTabWidget()
    tabs.addTab(HomeScreen(), "Home")
    tabs.addTab(ReviewScreen(), "Review")
    tabs.addTab(ApplyScreen(), "Apply")
    tabs.addTab(HistoryScreen(), "History")
    tabs.addTab(SettingsScreen(), "Settings")
    window.setCentralWidget(tabs)
    window.resize(960, 640)
    window.show()
    app.exec()
