import os

from PySide6.QtWidgets import QApplication

from autoshelf.gui.widgets import (
    Banner,
    Card,
    ConfidenceMeter,
    Dropzone,
    EmptyState,
    PrimaryButton,
    ProgressOverlay,
    Spinner,
    StatusDot,
    ThemeToggle,
    ToastHost,
    TreeView,
)


def test_widget_library_smoke_instantiates(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QApplication.instance() or QApplication([])
    widgets = [
        PrimaryButton("계속"),
        Card(),
        Banner("info", "알림", "본문"),
        Dropzone(),
        EmptyState("folder", "비어 있음", "힌트"),
        ConfidenceMeter(0.8),
        ProgressOverlay(),
        Spinner(),
        StatusDot(),
        ThemeToggle(),
        ToastHost(),
        TreeView(),
    ]
    assert all(widget.accessibleName() for widget in widgets)

