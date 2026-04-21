from __future__ import annotations

from pathlib import Path

from autoshelf.db import Database, TransactionRecord, default_db_path


def undo_last_apply(root: Path, db_path: Path | None = None) -> int:
    """Undo the most recent apply run and return the number of reversed actions."""

    database = Database(db_path or default_db_path(root))
    run_id = database.last_run_id(root)
    if run_id is None:
        return 0
    count = 0
    with database.session() as session:
        records = (
            session.query(TransactionRecord)
            .filter(TransactionRecord.root == str(root), TransactionRecord.run_id == run_id)
            .order_by(TransactionRecord.id.desc())
            .all()
        )
        for record in records:
            target = Path(record.target_path)
            source = Path(record.source_path)
            if record.action == "shortcut":
                if target.exists() or target.is_symlink():
                    target.unlink()
                    count += 1
            elif record.action == "move":
                source.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.replace(source)
                    count += 1
            session.delete(record)
    return count
