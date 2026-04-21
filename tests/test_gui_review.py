from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from autoshelf.gui.review import ReviewScreen


def test_review_screen_loads_preview_with_hints(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    screen = ReviewScreen()
    assert screen.assignment_table.rowCount() == 2
    assert screen.proposed_tree.topLevelItemCount() >= 1
    top = screen.proposed_tree.topLevelItem(0)
    assert top is not None
    screen.proposed_tree.setCurrentItem(top)
    screen._update_hint_panel()
    hint_text = screen.folder_hint.toPlainText().lower()
    assert "folder" in hint_text or "receives" in hint_text or "documents" in hint_text
    app.processEvents()
