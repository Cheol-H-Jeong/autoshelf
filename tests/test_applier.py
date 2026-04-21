from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest
from sqlalchemy import select

import autoshelf.shortcuts as shortcuts_module
from autoshelf.applier import ApplyRecoveryError, apply_plan, load_run_plan
from autoshelf.apply_state import (
    run_staging_dir,
    run_state_path,
    update_run_entry,
    write_run_plan,
    write_run_state,
)
from autoshelf.db import Database, TransactionRecord
from autoshelf.filesystem import FakeFilesystem
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


def test_apply_collapses_duplicate_hashes_into_single_canonical_copy(tmp_path):
    first = tmp_path / "incoming" / "draft.txt"
    second = tmp_path / "copies" / "draft-copy.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("hello", encoding="utf-8")
    second.write_text("hello", encoding="utf-8")

    result = apply_plan(
        tmp_path,
        [
            _assignment("incoming/draft.txt", ["Docs"]),
            _assignment("copies/draft-copy.txt", ["Archive"]),
        ],
        {"Docs": {}, "Archive": {}},
        dry_run=False,
    )

    canonical = tmp_path / "Docs" / "draft.txt"
    duplicate = tmp_path / "Archive" / "draft-copy.txt"
    assert canonical.exists()
    assert duplicate.exists()
    assert duplicate.is_symlink()
    assert duplicate.resolve() == canonical.resolve()
    assert not first.exists()
    assert not second.exists()
    assert result.moved == [(first, canonical)]
    assert result.shortcuts == [duplicate]

    with Database(tmp_path / ".autoshelf" / "autoshelf.sqlite").session() as session:
        records = json.dumps(
            [
                {
                    "action": record.action,
                    "target_path": record.target_path,
                    "details": record.details,
                }
                for record in session.scalars(
                    select(TransactionRecord).where(TransactionRecord.run_id == result.run_id)
                )
            ],
            ensure_ascii=False,
        )
    assert '"action": "dedupe"' in records
    assert '"canonical_target"' in records


def test_undo_restores_duplicate_sources_after_deduped_apply(tmp_path):
    first = tmp_path / "incoming" / "draft.txt"
    second = tmp_path / "copies" / "draft-copy.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("hello", encoding="utf-8")
    second.write_text("hello", encoding="utf-8")

    result = apply_plan(
        tmp_path,
        [
            _assignment("incoming/draft.txt", ["Docs"]),
            _assignment("copies/draft-copy.txt", ["Archive"]),
        ],
        {"Docs": {}, "Archive": {}},
        dry_run=False,
    )

    undone = undo_last_apply(tmp_path, run_id=result.run_id)

    assert undone.undone == 2
    assert first.exists()
    assert second.exists()
    assert first.read_text(encoding="utf-8") == "hello"
    assert second.read_text(encoding="utf-8") == "hello"
    assert not (tmp_path / "Docs" / "draft.txt").exists()
    assert not (tmp_path / "Archive" / "draft-copy.txt").exists()


def test_apply_cross_device_copy_verifies_hash(tmp_path, monkeypatch):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    original_replace = Path.replace

    def raise_exdev(self: Path, target: Path):
        if self == source:
            raise OSError(errno.EXDEV, "cross-device")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", raise_exdev)
    try:
        result = apply_plan(
            tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False
        )
    finally:
        monkeypatch.setattr(Path, "replace", original_replace)
    assert result.moved[0][1].exists()
    assert not source.exists()
    assert not run_staging_dir(tmp_path, result.run_id).exists()


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


def test_apply_resume_reconciles_completed_move_before_shortcut(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = _assignment("draft.txt", ["문서"], [["문서", "참고"]])
    run_id = "resume-run"
    plan_path = write_run_plan(tmp_path, [assignment], run_id)
    moved_target = tmp_path / "문서" / "draft.txt"
    moved_target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(moved_target)
    update_run_entry(plan_path, "draft.txt", status="running", target_path="문서/draft.txt")
    write_run_state(
        run_state_path(tmp_path, run_id),
        run_id=run_id,
        status="interrupted",
        current_path="draft.txt",
        completed_entries=0,
        total_entries=1,
        last_error="simulated interruption",
    )

    result = apply_plan(
        tmp_path,
        [assignment],
        {"문서": {"참고": {}}},
        dry_run=False,
        run_id=run_id,
        resume=True,
    )

    assert result.resumed is True
    assert moved_target.exists()
    assert (tmp_path / "문서" / "참고" / "draft.txt").exists()
    assert not source.exists()
    state_payload = run_state_path(tmp_path, run_id).read_text(encoding="utf-8")
    assert '"status": "completed"' in state_payload


def test_apply_records_staged_copy_metadata_for_cross_device_runs(tmp_path, monkeypatch):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    original_replace = Path.replace

    def raise_exdev(self: Path, target: Path):
        if self == source:
            raise OSError(errno.EXDEV, "cross-device")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", raise_exdev)
    try:
        result = apply_plan(
            tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False
        )
    finally:
        monkeypatch.setattr(Path, "replace", original_replace)

    plan = load_run_plan(tmp_path / ".autoshelf" / "runs" / f"{result.run_id}.plan.jsonl")
    assert plan[0]["copy_stage"] == "pending"
    assert plan[0]["staged_path"] == ""


def test_apply_resume_recovers_staged_copy_after_interrupted_cross_device_move(
    tmp_path, monkeypatch
):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    original_replace = Path.replace
    promoted = False

    def flaky_replace(self: Path, target: Path):
        nonlocal promoted
        if self == source:
            raise OSError(errno.EXDEV, "cross-device")
        if self.suffix == ".part" and not promoted:
            promoted = True
            raise RuntimeError("simulated crash before promote")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    try:
        try:
            apply_plan(tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False)
        except RuntimeError as exc:
            assert "simulated crash" in str(exc)
    finally:
        monkeypatch.setattr(Path, "replace", original_replace)

    staged_files = list((tmp_path / ".autoshelf" / "staging").rglob("*.part"))
    assert len(staged_files) == 1
    assert source.exists()
    assert not (tmp_path / "문서" / "draft.txt").exists()

    run_id = staged_files[0].parent.name
    resumed = apply_plan(
        tmp_path,
        [_assignment("draft.txt", ["문서"])],
        {"문서": {}},
        dry_run=False,
        run_id=run_id,
        resume=True,
    )

    assert resumed.resumed is True
    assert not source.exists()
    assert (tmp_path / "문서" / "draft.txt").exists()
    assert not run_staging_dir(tmp_path, run_id).exists()


def test_apply_resume_removes_duplicate_source_after_target_written_interrupt(
    tmp_path, monkeypatch
):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    original_replace = Path.replace
    original_unlink = Path.unlink

    def cross_device_replace(self: Path, target: Path):
        if self == source:
            raise OSError(errno.EXDEV, "cross-device")
        return original_replace(self, target)

    def fail_unlink(self: Path, *args, **kwargs):
        if self == source:
            raise RuntimeError("simulated crash after promote")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", cross_device_replace)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    try:
        try:
            apply_plan(tmp_path, [_assignment("draft.txt", ["문서"])], {"문서": {}}, dry_run=False)
        except RuntimeError as exc:
            assert "simulated crash" in str(exc)
    finally:
        monkeypatch.setattr(Path, "replace", original_replace)
        monkeypatch.setattr(Path, "unlink", original_unlink)

    target = tmp_path / "문서" / "draft.txt"
    assert source.exists()
    assert target.exists()

    run_id = next((tmp_path / ".autoshelf" / "runs").glob("*.plan.jsonl")).stem.replace(".plan", "")
    resumed = apply_plan(
        tmp_path,
        [_assignment("draft.txt", ["문서"])],
        {"문서": {}},
        dry_run=False,
        run_id=run_id,
        resume=True,
    )

    assert resumed.resumed is True
    assert not source.exists()
    assert target.exists()
    state_payload = run_state_path(tmp_path, run_id).read_text(encoding="utf-8")
    assert '"status": "completed"' in state_payload


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


def test_apply_resume_raises_for_missing_source_with_mismatched_target(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = _assignment("draft.txt", ["문서"])
    run_id = "resume-mismatch"
    plan_path = write_run_plan(tmp_path, [assignment], run_id)
    target = tmp_path / "문서" / "draft.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("wrong", encoding="utf-8")
    source.unlink()
    update_run_entry(plan_path, "draft.txt", status="running", target_path="문서/draft.txt")
    write_run_state(
        run_state_path(tmp_path, run_id),
        run_id=run_id,
        status="interrupted",
        current_path="draft.txt",
        completed_entries=0,
        total_entries=1,
        last_error="simulated interruption",
    )

    with pytest.raises(ApplyRecoveryError):
        apply_plan(
            tmp_path,
            [assignment],
            {"문서": {}},
            dry_run=False,
            run_id=run_id,
            resume=True,
        )

    plan = load_run_plan(tmp_path / ".autoshelf" / "runs" / f"{run_id}.plan.jsonl")
    assert plan[0]["status"] == "running"
    assert target.read_text(encoding="utf-8") == "wrong"


def test_apply_plan_supports_fake_filesystem_backend(tmp_path):
    filesystem = FakeFilesystem()
    filesystem.write_text(tmp_path / "draft.txt", "hello")

    result = apply_plan(
        tmp_path,
        [_assignment("draft.txt", ["문서"])],
        {"문서": {}},
        dry_run=False,
        filesystem=filesystem,
    )

    target = tmp_path / "문서" / "draft.txt"
    assert result.moved == [(tmp_path / "draft.txt", target)]
    assert filesystem.exists(target)
    assert not filesystem.exists(tmp_path / "draft.txt")
    manifest_line = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").strip()
    manifest = json.loads(manifest_line)
    assert manifest["content_hash"] == filesystem.hash_file(target)
    state_payload = run_state_path(tmp_path, result.run_id).read_text(encoding="utf-8")
    assert '"status": "completed"' in state_payload


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
