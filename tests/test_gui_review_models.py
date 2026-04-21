from __future__ import annotations

from autoshelf.gui.review_models import PreviewItem, summarize_actions


def test_preview_item_actions_cover_kept_moved_and_placed() -> None:
    kept = PreviewItem(
        source_path="Finance/invoice.pdf",
        source_parts=["Finance", "invoice.pdf"],
        target_parts=["Finance", "invoice.pdf"],
        confidence=0.9,
    )
    moved = PreviewItem(
        source_path="Downloads/invoice.pdf",
        source_parts=["Downloads", "invoice.pdf"],
        target_parts=["Finance", "2026", "invoice.pdf"],
        confidence=0.8,
    )
    placed = PreviewItem(
        source_path="invoice.pdf",
        source_parts=["invoice.pdf"],
        target_parts=["Finance", "invoice.pdf"],
        confidence=0.7,
    )

    assert kept.action == "kept"
    assert moved.action == "moved"
    assert moved.action_summary == "Move invoice.pdf from Downloads to Finance/2026"
    assert placed.action == "placed"
    assert summarize_actions([kept, moved, placed]) == {
        "kept": 1,
        "moved": 1,
        "placed": 1,
        "quarantine": 0,
        "reassigned": 0,
    }


def test_preview_item_reports_quarantine_action() -> None:
    quarantined = PreviewItem(
        source_path="incoming/client-a/proposal.txt",
        source_parts=["incoming", "client-a", "proposal.txt"],
        target_parts=[".autoshelf", "quarantine", "proposal.txt"],
        confidence=0.22,
    )

    assert quarantined.is_quarantined is True
    assert quarantined.action == "quarantine"
    assert summarize_actions([quarantined]) == {
        "kept": 0,
        "moved": 0,
        "placed": 0,
        "quarantine": 1,
        "reassigned": 0,
    }


def test_preview_item_reports_manual_reassignment_separately() -> None:
    reassigned = PreviewItem(
        source_path="Inbox/draft.txt",
        source_parts=["Inbox", "draft.txt"],
        target_parts=["Archive", "Writing", "draft.txt"],
        confidence=0.9,
        baseline_target_parts=["Documents", "Writing", "draft.txt"],
    )

    assert reassigned.action == "moved"
    assert reassigned.operator_modified is True
    assert reassigned.display_action == "reassigned"
    assert summarize_actions([reassigned]) == {
        "kept": 0,
        "moved": 0,
        "placed": 0,
        "quarantine": 0,
        "reassigned": 1,
    }
