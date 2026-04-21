from __future__ import annotations

import errno
import shutil
import signal
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from autoshelf.apply_state import (
    RunPlanEntry,
    load_run_plan_entries,
    run_staging_dir,
    run_state_path,
    update_run_entry,
    write_run_plan,
    write_run_state,
)
from autoshelf.db import Database, TransactionRecord, default_db_path
from autoshelf.manifest import write_manifests
from autoshelf.planner.models import PlannerAssignment
from autoshelf.scanner import _hash_file
from autoshelf.shortcuts import copy_fallback, create_shortcut
from autoshelf.targeting import resolve_assignment_target, safe_target_dir


@dataclass(slots=True)
class ApplyResult:
    run_id: str
    moved: list[tuple[Path, Path]]
    shortcuts: list[Path]
    dry_run: bool
    resumed: bool = False


class ApplyInterruptedError(RuntimeError):
    pass


def apply_plan(
    root: Path,
    assignments: list[PlannerAssignment],
    tree: dict[str, object],
    dry_run: bool = True,
    db_path: Path | None = None,
    run_id: str | None = None,
    resume: bool = False,
    conflict_policy: str = "append-counter",
    on_progress: Callable[[str, int, int, str, Path | None], None] | None = None,
) -> ApplyResult:
    run_identifier = run_id or uuid.uuid4().hex
    if dry_run:
        write_manifests(root, tree, assignments)
        return ApplyResult(
            run_id=run_identifier, moved=[], shortcuts=[], dry_run=True, resumed=resume
        )

    plan_path = write_run_plan(root, assignments, run_identifier)
    database = Database(db_path or default_db_path(root))
    planned_entries = load_run_plan_entries(plan_path)
    total_entries = len(planned_entries)
    state_path = run_state_path(root, run_identifier)
    staging_dir = run_staging_dir(root, run_identifier)
    moved: list[tuple[Path, Path]] = []
    created_shortcuts: list[Path] = []
    completed_entries = sum(1 for entry in planned_entries if entry.status == "applied")
    write_run_state(
        state_path,
        run_id=run_identifier,
        status="running",
        completed_entries=completed_entries,
        total_entries=total_entries,
    )
    try:
        with _interrupt_guard(
            lambda current_path: write_run_state(
                state_path,
                run_id=run_identifier,
                status="interrupted",
                current_path=current_path,
                completed_entries=completed_entries,
                total_entries=total_entries,
                last_error="apply interrupted by signal",
            )
        ) as interrupt_guard:
            with database.session() as session:
                sequence = 0
                for entry in planned_entries:
                    sequence += 1
                    if resume and entry.status == "applied":
                        if on_progress is not None:
                            on_progress("resume-skip", sequence, total_entries, entry.path, None)
                        continue
                    interrupt_guard.check(entry.path)
                    final_target = _target_for_entry(root, entry, conflict_policy)
                    entry = update_run_entry(
                        plan_path,
                        entry.path,
                        status="running",
                        target_path=str(final_target.relative_to(root)),
                    ) or entry
                    source = root / entry.path
                    if conflict_policy == "skip" and final_target.exists() and source.exists():
                        update_run_entry(plan_path, entry.path, status="skipped")
                        session.add(
                            _transaction_record(
                                root,
                                run_identifier,
                                sequence,
                                "move",
                                source,
                                final_target,
                                "skipped",
                            )
                        )
                        if on_progress is not None:
                            on_progress(
                                "skipped",
                                sequence,
                                total_entries,
                                entry.path,
                                final_target,
                            )
                        continue
                    reconciled = _reconcile_completed_move(root, entry, final_target)
                    if reconciled is None and not source.exists():
                        update_run_entry(plan_path, entry.path, status="skipped")
                        session.add(
                            _transaction_record(
                                root,
                                run_identifier,
                                sequence,
                                "move",
                                source,
                                final_target,
                                "skipped",
                            )
                        )
                        if on_progress is not None:
                            on_progress(
                                "missing-source", sequence, total_entries, entry.path, final_target
                            )
                        continue
                    final_target = reconciled or _move_file(source, final_target, staging_dir)
                    _verify_move(
                        source,
                        final_target,
                        entry.source_hash,
                        reconciled=reconciled is not None,
                    )
                    if reconciled is None:
                        moved.append((source, final_target))
                    session.add(
                        _transaction_record(
                            root, run_identifier, sequence, "move", source, final_target, "applied"
                        )
                    )
                    if on_progress is not None:
                        on_progress("moved", sequence, total_entries, entry.path, final_target)
                    interrupt_guard.check(entry.path)
                    for extra in entry.also_relevant:
                        sequence += 1
                        shortcut = _create_entry_shortcut(root, final_target, extra)
                        created_shortcuts.append(shortcut)
                        session.add(
                            _transaction_record(
                                root,
                                run_identifier,
                                sequence,
                                "shortcut",
                                final_target,
                                shortcut,
                                "applied",
                            )
                        )
                        if on_progress is not None:
                            on_progress("shortcut", sequence, total_entries, entry.path, shortcut)
                        interrupt_guard.check(entry.path)
                    update_run_entry(
                        plan_path,
                        entry.path,
                        status="applied",
                        target_path=str(final_target.relative_to(root)),
                    )
                    completed_entries += 1
                    write_run_state(
                        state_path,
                        run_id=run_identifier,
                        status="running",
                        completed_entries=completed_entries,
                        total_entries=total_entries,
                    )
    except ApplyInterruptedError:
        logger.warning("apply interrupted for run {}", run_identifier)
        raise
    except Exception as exc:
        write_run_state(
            state_path,
            run_id=run_identifier,
            status="interrupted",
            completed_entries=completed_entries,
            total_entries=total_entries,
            last_error=str(exc),
        )
        raise
    _cleanup_staging_dir(staging_dir)
    write_run_state(
        state_path,
        run_id=run_identifier,
        status="completed",
        completed_entries=completed_entries,
        total_entries=total_entries,
    )
    write_manifests(root, tree, assignments)
    return ApplyResult(
        run_id=run_identifier,
        moved=moved,
        shortcuts=created_shortcuts,
        dry_run=False,
        resumed=resume,
    )


def load_run_plan(plan_path: Path) -> list[dict[str, object]]:
    return [entry.model_dump(mode="json") for entry in load_run_plan_entries(plan_path)]


def _transaction_record(
    root: Path,
    run_id: str,
    sequence: int,
    action: str,
    source: Path,
    target: Path,
    status: str,
) -> TransactionRecord:
    return TransactionRecord(
        root=str(root),
        run_id=run_id,
        sequence=sequence,
        action=action,
        status=status,
        source_path=str(source),
        target_path=str(target),
        details={},
    )


def _target_for_entry(root: Path, entry: RunPlanEntry, conflict_policy: str) -> Path:
    if entry.target_path:
        return root / entry.target_path
    return resolve_assignment_target(root, entry.path, entry.primary_dir, conflict_policy)


def _move_file(source: Path, target: Path, staging_dir: Path) -> Path:
    try:
        source.replace(target)
        return target
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    staged_target = _stage_copy(source, target, staging_dir)
    staged_target.replace(target)
    source.unlink()
    return target


def _stage_copy(source: Path, target: Path, staging_dir: Path) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_target = staging_dir / f"{uuid.uuid4().hex}{target.suffix}.part"
    shutil.copy2(source, staged_target)
    if _hash_file(source) != _hash_file(staged_target):
        raise ValueError("copy verification failed")
    return staged_target


def _reconcile_completed_move(root: Path, entry: RunPlanEntry, target: Path) -> Path | None:
    source = root / entry.path
    if source.exists() or not target.exists():
        return None
    if entry.source_hash and _hash_file(target) != entry.source_hash:
        return None
    logger.info("resuming completed move for {}", entry.path)
    return target


def _create_entry_shortcut(root: Path, final_target: Path, extra: list[str]) -> Path:
    shortcut_dir = safe_target_dir(root, extra)
    shortcut_dir.mkdir(parents=True, exist_ok=True)
    shortcut_name = f"{final_target.name}.lnk" if _windows_path() else final_target.name
    shortcut_path = shortcut_dir / shortcut_name
    try:
        return create_shortcut(final_target, shortcut_path)
    except OSError:
        return copy_fallback(final_target, shortcut_path)


def _verify_move(source: Path, target: Path, source_hash: str, *, reconciled: bool = False) -> None:
    if source.exists() and not reconciled:
        raise ValueError(f"source still exists after move: {source}")
    if not target.exists():
        raise ValueError(f"target missing after move: {target}")
    if source_hash and _hash_file(target) != source_hash:
        raise ValueError("target hash mismatch after move")


def _cleanup_staging_dir(staging_dir: Path) -> None:
    if staging_dir.exists():
        shutil.rmtree(staging_dir)


@dataclass(slots=True)
class _InterruptGuard:
    on_interrupt: Callable[[str], None]
    interrupted: bool = False

    def check(self, current_path: str) -> None:
        if not self.interrupted:
            return
        self.on_interrupt(current_path)
        raise ApplyInterruptedError(current_path)


class _interrupt_guard:
    def __init__(self, on_interrupt: Callable[[str], None]) -> None:
        self._guard = _InterruptGuard(on_interrupt=on_interrupt)
        self._previous_handlers: dict[int, object] = {}

    def __enter__(self) -> _InterruptGuard:
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._previous_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._handler)
        return self._guard

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        for sig, previous in self._previous_handlers.items():
            signal.signal(sig, previous)

    def _handler(self, signum: int, frame: object) -> None:
        logger.warning("received signal {} during apply", signum)
        self._guard.interrupted = True


def _windows_path() -> bool:
    import sys

    return sys.platform == "win32"
