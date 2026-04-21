from __future__ import annotations

import errno
from pathlib import Path

from autoshelf.apply_state import RunPlanEntry
from autoshelf.fileops import FileMover
from autoshelf.filesystem import FakeFilesystem


def _append_update(
    updates: list[dict[str, str]],
    _plan_path: Path,
    source_path: str,
    **kwargs: str | None,
) -> None:
    payload = {"source_path": source_path}
    payload.update({key: value for key, value in kwargs.items() if value is not None})
    updates.append(payload)


def test_file_mover_cross_device_move_uses_staging_and_updates_run_state():
    root = Path("/virtual")
    source = root / "draft.txt"
    target = root / "Documents" / "draft.txt"
    filesystem = FakeFilesystem()
    filesystem.write_text(source, "hello")
    filesystem.queue_failure("replace", source, OSError(errno.EXDEV, "cross-device"))
    updates: list[dict[str, str]] = []
    mover = FileMover(
        root=root,
        plan_path=root / ".autoshelf" / "runs" / "run.plan.jsonl",
        staging_dir=root / ".autoshelf" / "staging" / "run",
        filesystem=filesystem,
        run_entry_updater=lambda plan_path, source_path, **kwargs: _append_update(
            updates, plan_path, source_path, **kwargs
        ),
        stage_name_factory=lambda _target: "staged-copy.txt.part",
    )

    moved_target = mover.move("draft.txt", source, target)

    assert moved_target == target
    assert filesystem.exists(target)
    assert not filesystem.exists(source)
    assert not filesystem.exists(root / ".autoshelf" / "staging" / "run" / "staged-copy.txt.part")
    assert updates == [
        {
            "source_path": "draft.txt",
            "copy_stage": "staged",
            "staged_path": ".autoshelf/staging/run/staged-copy.txt.part",
        },
        {
            "source_path": "draft.txt",
            "copy_stage": "target-written",
            "staged_path": "",
        },
    ]


def test_file_mover_recovers_staged_copy_and_clears_duplicate_source():
    root = Path("/virtual")
    source = root / "draft.txt"
    staged = root / ".autoshelf" / "staging" / "run" / "staged-copy.txt.part"
    target = root / "Documents" / "draft.txt"
    filesystem = FakeFilesystem()
    filesystem.write_text(source, "hello")
    filesystem.write_text(staged, "hello")
    updates: list[dict[str, str]] = []
    mover = FileMover(
        root=root,
        plan_path=root / ".autoshelf" / "runs" / "run.plan.jsonl",
        staging_dir=root / ".autoshelf" / "staging" / "run",
        filesystem=filesystem,
        run_entry_updater=lambda plan_path, source_path, **kwargs: _append_update(
            updates, plan_path, source_path, **kwargs
        ),
    )
    entry = RunPlanEntry(
        path="draft.txt",
        primary_dir=["Documents"],
        source_hash=filesystem.hash_file(source),
        copy_stage="staged",
        staged_path=".autoshelf/staging/run/staged-copy.txt.part",
    )

    recovered_target = mover.recover(entry, target)

    assert recovered_target == target
    assert filesystem.exists(target)
    assert not filesystem.exists(source)
    assert not filesystem.exists(staged)
    assert updates == [
        {
            "source_path": "draft.txt",
            "target_path": "Documents/draft.txt",
            "copy_stage": "target-written",
            "staged_path": ".autoshelf/staging/run/staged-copy.txt.part",
        },
        {
            "source_path": "draft.txt",
            "target_path": "Documents/draft.txt",
            "copy_stage": "pending",
            "staged_path": "",
        },
    ]


def test_file_mover_recovers_duplicate_source_when_target_was_already_promoted():
    root = Path("/virtual")
    source = root / "draft.txt"
    target = root / "Documents" / "draft.txt"
    filesystem = FakeFilesystem()
    filesystem.write_text(source, "hello")
    filesystem.write_text(target, "hello")
    updates: list[dict[str, str]] = []
    mover = FileMover(
        root=root,
        plan_path=root / ".autoshelf" / "runs" / "run.plan.jsonl",
        staging_dir=root / ".autoshelf" / "staging" / "run",
        filesystem=filesystem,
        run_entry_updater=lambda plan_path, source_path, **kwargs: _append_update(
            updates, plan_path, source_path, **kwargs
        ),
    )
    entry = RunPlanEntry(
        path="draft.txt",
        primary_dir=["Documents"],
        source_hash=filesystem.hash_file(source),
        copy_stage="target-written",
    )

    recovered_target = mover.recover(entry, target)

    assert recovered_target == target
    assert filesystem.exists(target)
    assert not filesystem.exists(source)
    assert updates == [
        {
            "source_path": "draft.txt",
            "target_path": "Documents/draft.txt",
            "copy_stage": "pending",
            "staged_path": "",
        }
    ]
