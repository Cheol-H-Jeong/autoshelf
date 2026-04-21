from __future__ import annotations

import errno
from pathlib import Path

import autoshelf.shortcuts as shortcuts_module
from autoshelf.applier import apply_plan, load_run_plan
from autoshelf.manifest import write_manifests
from autoshelf.planner.models import PlannerAssignment
from autoshelf.shortcuts import create_shortcut
from autoshelf.undo import undo_last_apply


def _assignment(
    path: str, primary: list[str], also: list[list[str]] | None = None
) -> PlannerAssignment:
    return PlannerAssignment(
        path=path, primary_dir=primary, also_relevant=also or [], summary="hello"
    )


def test_apply_dry_run_noop(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    result = apply_plan(tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=True)
    assert result.dry_run is True
    assert source.exists()
    assert (tmp_path / "FILE_INDEX.md").exists()


def test_apply_and_undo_round_trip(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = _assignment("draft.txt", ["문서"], [["문서", "참고"]])
    apply_plan(tmp_path, [assignment], {"문서": {"참고": {}}}, dry_run=False)
    moved = tmp_path / "문서" / "draft.txt"
    shortcut = tmp_path / "문서" / "참고" / "draft.txt"
    assert moved.exists()
    assert shortcut.exists() or shortcut.is_symlink()
    undone = undo_last_apply(tmp_path)
    assert undone.undone >= 1
    assert source.exists()


def test_apply_cross_device_copy_verifies_hash(tmp_path, monkeypatch):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    original_rename = Path.rename

    def raise_exdev(self: Path, target: Path):
        raise OSError(errno.EXDEV, "cross-device")

    monkeypatch.setattr(Path, "rename", raise_exdev)
    try:
        result = apply_plan(
            tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False
        )
    finally:
        monkeypatch.setattr(Path, "rename", original_rename)
    assert result.moved[0][1].exists()
    assert not source.exists()


def test_apply_collision_appends_counter(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    target_dir = tmp_path / "문서"
    target_dir.mkdir()
    (target_dir / "draft.txt").write_text("existing", encoding="utf-8")
    result = apply_plan(tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False)
    assert result.moved[0][1].name == "draft (2).txt"


def test_apply_resume_skips_completed_entries(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    result = apply_plan(tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False)
    resumed = apply_plan(
        tmp_path,
        [_assignment("draft.txt", ["문서"])],
        {"문서": {}},
        dry_run=False,
        run_id=result.run_id,
        resume=True,
    )
    plan = load_run_plan(tmp_path / ".autoshelf" / "runs" / f"{result.run_id}.plan.jsonl")
    assert resumed.resumed is True
    assert plan[0]["status"] == "applied"


def test_apply_skip_policy_leaves_existing_target(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    target_dir = tmp_path / "문서"
    target_dir.mkdir()
    (target_dir / "draft.txt").write_text("existing", encoding="utf-8")
    result = apply_plan(
        tmp_path,
        [_assignment("draft.txt", ["문서"])],
        {"문서": {}},
        dry_run=False,
        conflict_policy="skip",
    )
    assert result.moved == []
    assert source.exists()


def test_manifest_write_is_idempotent(tmp_path):
    assignments = [_assignment("draft.txt", ["문서"])]
    write_manifests(tmp_path, {"문서": {}}, assignments)
    first = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8")
    write_manifests(tmp_path, {"문서": {}}, assignments)
    second = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8")
    assert first == second


def test_shortcut_windows_uses_lnk(monkeypatch, tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("hello", encoding="utf-8")
    created: list[tuple[str, str]] = []

    def fake_create(src: str, dest: str) -> None:
        created.append((src, dest))
        Path(dest).write_text("lnk", encoding="utf-8")

    monkeypatch.setattr(shortcuts_module.sys, "platform", "win32")
    monkeypatch.setitem(
        __import__("sys").modules, "pylnk3", type("P", (), {"create": staticmethod(fake_create)})
    )
    path = create_shortcut(target, tmp_path / "shortcut")
    assert path.suffix == ".lnk"
    assert created


def test_undo_specific_run(tmp_path):
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    run_one = apply_plan(tmp_path, [_assignment("one.txt", ["문서"])], {"문서": {}}, dry_run=False)
    run_two = apply_plan(tmp_path, [_assignment("two.txt", ["자료"])], {"자료": {}}, dry_run=False)
    result = undo_last_apply(tmp_path, run_id=run_one.run_id)
    assert result.run_id == run_one.run_id
    assert (tmp_path / "one.txt").exists()
    assert (tmp_path / "자료" / "two.txt").exists()
    assert run_two.run_id != run_one.run_id


def test_undo_conflict_detection(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    run = apply_plan(tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False)
    moved = tmp_path / "문서" / "draft.txt"
    moved.unlink()
    conflict = undo_last_apply(tmp_path, run_id=run.run_id)
    assert conflict.conflicts
