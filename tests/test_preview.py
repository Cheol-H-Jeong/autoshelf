from __future__ import annotations

from autoshelf.planner.models import PlannerAssignment
from autoshelf.preview import build_preview, preview_dir


def test_build_preview_creates_symlink_tree_for_assignments_and_shortcuts(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignments = [
        PlannerAssignment(
            path="draft.txt",
            primary_dir=["Docs"],
            also_relevant=[["Archive"]],
            summary="hello",
        )
    ]

    result = build_preview(tmp_path, assignments)

    primary = preview_dir(tmp_path) / "Docs" / "draft.txt"
    shortcut = preview_dir(tmp_path) / "Archive" / "draft.txt"
    assert result.assignments == 1
    assert result.shortcuts == 1
    assert primary.is_symlink()
    assert shortcut.is_symlink()
    assert primary.resolve() == source.resolve()
    assert shortcut.resolve() == primary.resolve()


def test_build_preview_dedupes_primary_targets_like_apply(tmp_path):
    first = tmp_path / "one" / "report.txt"
    second = tmp_path / "two" / "report.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    assignments = [
        PlannerAssignment(path="one/report.txt", primary_dir=["Docs"], summary="one"),
        PlannerAssignment(path="two/report.txt", primary_dir=["Docs"], summary="two"),
    ]

    build_preview(tmp_path, assignments)

    preview_root = preview_dir(tmp_path) / "Docs"
    assert (preview_root / "report.txt").is_symlink()
    assert (preview_root / "report (2).txt").is_symlink()


def test_build_preview_collapses_duplicate_content_to_canonical_preview_target(tmp_path):
    first = tmp_path / "incoming" / "draft.txt"
    second = tmp_path / "copies" / "draft-copy.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("hello", encoding="utf-8")
    second.write_text("hello", encoding="utf-8")
    assignments = [
        PlannerAssignment(path="incoming/draft.txt", primary_dir=["Docs"], summary="one"),
        PlannerAssignment(path="copies/draft-copy.txt", primary_dir=["Archive"], summary="two"),
    ]

    build_preview(tmp_path, assignments)

    canonical = preview_dir(tmp_path) / "Docs" / "draft.txt"
    duplicate = preview_dir(tmp_path) / "Archive" / "draft-copy.txt"
    assert canonical.is_symlink()
    assert duplicate.is_symlink()
    assert canonical.resolve() == first.resolve()
    assert duplicate.resolve() == canonical.resolve()
