from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QTreeWidgetItem

from autoshelf.gui.review import ReviewScreen
from autoshelf.planner.models import PlannerAssignment


def _first_leaf(screen: ReviewScreen) -> QTreeWidgetItem | None:
    item = screen.proposed_tree.topLevelItem(0)
    while item is not None and item.childCount():
        item = item.child(0)
    return item


def test_review_screen_loads_preview_with_hints(monkeypatch):
    import locale as _locale

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(_locale, "getlocale", lambda *a, **k: ("en_US", "UTF-8"))
    from autoshelf import i18n as _i18n

    _i18n._catalog.cache_clear()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    screen = ReviewScreen()
    assert screen.assignment_table.rowCount() == 3
    assert screen.proposed_tree.topLevelItemCount() >= 1
    assert "planned files" in screen.summary_label.text().lower()
    assert "quarantined" in screen.summary_label.text().lower()
    top = screen.proposed_tree.topLevelItem(0)
    assert top is not None
    screen.proposed_tree.setCurrentItem(top)
    screen._update_hint_panel()
    hint_text = screen.folder_hint.toPlainText().lower()
    assert "folder" in hint_text or "receives" in hint_text or "documents" in hint_text
    draft = _first_leaf(screen)
    assert draft is not None
    screen.proposed_tree.setCurrentItem(draft)
    screen._update_hint_panel()
    selection_text = screen.selection_summary.toPlainText().lower()
    assert "before:" in selection_text
    assert "after:" in selection_text
    assert "confidence:" in selection_text
    app.processEvents()


def test_review_screen_replans_and_clears_quarantine(monkeypatch):
    import locale as _locale

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(_locale, "getlocale", lambda *a, **k: ("en_US", "UTF-8"))
    from autoshelf import i18n as _i18n

    _i18n._catalog.cache_clear()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    screen = ReviewScreen()
    screen.load_preview(
        [
            PlannerAssignment(
                path="incoming/client-a/proposal.txt",
                primary_dir=[".autoshelf", "quarantine"],
                summary="Low-confidence draft kept in quarantine until an operator reviews it.",
                confidence=0.22,
                fallback=True,
            )
        ]
    )
    assert "quarantined" in screen.summary_label.text().lower()
    assert screen.replan_quarantine_button.isEnabled() is True
    draft = _first_leaf(screen)
    assert draft is not None
    screen.proposed_tree.setCurrentItem(draft)

    screen.replan_selected_quarantine()
    assert screen.loaded_assignments[0].primary_dir == ["Documents", "client-a"]
    assert "source path context" in screen.loaded_assignments[0].summary
    assert "no files are currently quarantined" in screen.quarantine_label.text().lower()

    screen.load_preview(
        [
            PlannerAssignment(
                path="incoming/client-a/proposal.txt",
                primary_dir=[".autoshelf", "quarantine"],
                summary="Low-confidence draft kept in quarantine until an operator reviews it.",
                confidence=0.22,
                fallback=True,
            )
        ]
    )
    draft = _first_leaf(screen)
    assert draft is not None
    screen.proposed_tree.setCurrentItem(draft)

    screen.clear_selected_quarantine()
    assert screen.loaded_assignments[0].primary_dir == ["incoming", "client-a"]
    assert "stays in its current folder" in screen.loaded_assignments[0].summary
    app.processEvents()


def test_review_screen_manual_reassignment_updates_preview_state(monkeypatch):
    import locale as _locale

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(_locale, "getlocale", lambda *a, **k: ("en_US", "UTF-8"))
    from autoshelf import i18n as _i18n

    _i18n._catalog.cache_clear()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])
    screen = ReviewScreen()

    screen.apply_manual_reassignment("Inbox/draft.txt", ["Archive", "Client A"])

    assert screen.loaded_assignments[0].primary_dir == ["Archive", "Client A"]
    assert "manually reassigned" in screen.summary_label.text().lower()
    selected = screen.proposed_tree.currentItem()
    assert selected is not None
    selection_text = screen.selection_summary.toPlainText().lower()
    hint_text = screen.folder_hint.toPlainText().lower()
    assert "operator override from:" in selection_text
    assert "documents/writing/draft.txt" in selection_text
    assert "operator override: originally planned for" in hint_text
    assert screen.assignment_table.item(0, 1).text() == "Reassign"
    app.processEvents()
