from __future__ import annotations

from autoshelf.applier import apply_plan
from autoshelf.planner.llm import PlannerAssignment
from autoshelf.undo import undo_last_apply


def test_apply_dry_run_noop(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(
        path="draft.txt",
        primary_dir=["문서"],
        also_relevant=[],
        summary="hello",
    )
    result = apply_plan(tmp_path, [assignment], {"문서": {}}, dry_run=True)
    assert result.dry_run is True
    assert source.exists()


def test_apply_and_undo_round_trip(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(
        path="draft.txt",
        primary_dir=["문서"],
        also_relevant=[["문서", "참고"]],
        summary="hello",
    )
    apply_plan(tmp_path, [assignment], {"문서": {"참고": {}}}, dry_run=False)
    moved = tmp_path / "문서" / "draft.txt"
    shortcut = tmp_path / "문서" / "참고" / "draft.txt"
    assert moved.exists()
    assert shortcut.exists() or shortcut.is_symlink()
    undone = undo_last_apply(tmp_path)
    assert undone >= 1
    assert source.exists()
