from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from autoshelf.db import Database, TransactionRecord, default_db_path


@dataclass(slots=True)
class UndoResult:
    run_id: str | None
    undone: int
    conflicts: list[str]
    planned: list[tuple[Path, Path]]


def undo_last_apply(
    root: Path,
    db_path: Path | None = None,
    run_id: str | None = None,
    dry_run: bool = False,
) -> UndoResult:
    database = Database(db_path or default_db_path(root))
    target_run_id = run_id or database.last_run_id(root)
    if target_run_id is None:
        return UndoResult(run_id=None, undone=0, conflicts=[], planned=[])
    conflicts: list[str] = []
    planned: list[tuple[Path, Path]] = []
    undone = 0
    with database.session() as session:
        records = list(
            session.scalars(
                select(TransactionRecord)
                .where(
                    TransactionRecord.root == str(root), TransactionRecord.run_id == target_run_id
                )
                .order_by(TransactionRecord.sequence.desc(), TransactionRecord.id.desc())
            )
        )
        for record in records:
            target = Path(record.target_path)
            source = Path(record.source_path)
            planned.append((target, source))
            if dry_run:
                continue
            if record.action == "dedupe":
                canonical = Path(str(record.details.get("canonical_target", "")))
                link_created = bool(record.details.get("link_created", False))
                if not canonical.exists():
                    conflicts.append(str(canonical))
                    continue
                if link_created and (target.exists() or target.is_symlink()):
                    target.unlink()
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(canonical, source)
                record.status = "reverted"
                undone += 1
                continue
            if record.action == "shortcut":
                if target.exists() or target.is_symlink():
                    target.unlink()
                    record.status = "reverted"
                    undone += 1
                continue
            if not target.exists():
                conflicts.append(str(target))
                continue
            source.parent.mkdir(parents=True, exist_ok=True)
            target.replace(source)
            record.status = "reverted"
            undone += 1
    return UndoResult(run_id=target_run_id, undone=undone, conflicts=conflicts, planned=planned)
