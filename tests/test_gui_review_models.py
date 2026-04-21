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
    }
