from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from autoshelf.db import Database, TransactionRecord, default_db_path
from autoshelf.manifest import write_manifests
from autoshelf.planner.llm import PlannerAssignment
from autoshelf.shortcuts import create_shortcut


@dataclass(slots=True)
class ApplyResult:
    """Outcome of an apply operation."""

    run_id: str
    moved: list[tuple[Path, Path]]
    shortcuts: list[Path]
    dry_run: bool


def apply_plan(
    root: Path,
    assignments: list[PlannerAssignment],
    tree: dict[str, object],
    dry_run: bool = True,
    db_path: Path | None = None,
) -> ApplyResult:
    """Apply a planned organization to the filesystem."""

    run_id = uuid.uuid4().hex
    if dry_run:
        return ApplyResult(run_id=run_id, moved=[], shortcuts=[], dry_run=True)

    database = Database(db_path or default_db_path(root))
    moved: list[tuple[Path, Path]] = []
    created_shortcuts: list[Path] = []
    with database.session() as session:
        for assignment in assignments:
            source = root / assignment.path
            target_dir = _safe_target_dir(root, assignment.primary_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = _dedupe_target(target_dir / source.name)
            shutil.move(str(source), str(target))
            moved.append((source, target))
            session.add(
                TransactionRecord(
                    root=str(root),
                    run_id=run_id,
                    action="move",
                    source_path=str(source),
                    target_path=str(target),
                    details={},
                )
            )
            for extra in assignment.also_relevant:
                shortcut_dir = _safe_target_dir(root, extra)
                shortcut_name = f"{target.name}.lnk" if _windows_path() else target.name
                shortcut = create_shortcut(target, shortcut_dir / shortcut_name)
                created_shortcuts.append(shortcut)
                session.add(
                    TransactionRecord(
                        root=str(root),
                        run_id=run_id,
                        action="shortcut",
                        source_path=str(target),
                        target_path=str(shortcut),
                        details={},
                    )
                )
    write_manifests(root, tree, assignments)
    return ApplyResult(run_id=run_id, moved=moved, shortcuts=created_shortcuts, dry_run=False)


def _safe_target_dir(root: Path, parts: list[str]) -> Path:
    target = root
    for part in parts:
        target = target / part
    resolved_root = root.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_root not in resolved_target.parents and resolved_target != resolved_root:
        raise ValueError("target directory escapes the selected root")
    return target


def _dedupe_target(target: Path) -> Path:
    if not target.exists():
        return target
    counter = 2
    while True:
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _windows_path() -> bool:
    import sys

    return sys.platform == "win32"
