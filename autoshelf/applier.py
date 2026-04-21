from __future__ import annotations

import errno
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from autoshelf.db import Database, TransactionRecord, default_db_path
from autoshelf.manifest import write_manifests
from autoshelf.planner.models import PlannerAssignment
from autoshelf.scanner import _hash_file
from autoshelf.shortcuts import copy_fallback, create_shortcut


@dataclass(slots=True)
class ApplyResult:
    run_id: str
    moved: list[tuple[Path, Path]]
    shortcuts: list[Path]
    dry_run: bool
    resumed: bool = False


def apply_plan(
    root: Path,
    assignments: list[PlannerAssignment],
    tree: dict[str, object],
    dry_run: bool = True,
    db_path: Path | None = None,
    run_id: str | None = None,
    resume: bool = False,
    conflict_policy: str = "append-counter",
) -> ApplyResult:
    run_identifier = run_id or uuid.uuid4().hex
    if dry_run:
        write_manifests(root, tree, assignments)
        return ApplyResult(
            run_id=run_identifier, moved=[], shortcuts=[], dry_run=True, resumed=resume
        )

    plan_path = write_run_plan(root, assignments, run_identifier)
    database = Database(db_path or default_db_path(root))
    planned_entries = load_run_plan(plan_path)
    moved: list[tuple[Path, Path]] = []
    created_shortcuts: list[Path] = []
    with database.session() as session:
        for sequence, entry in enumerate(planned_entries, start=1):
            if resume and entry.get("status") == "applied":
                continue
            source = root / entry["path"]
            target_dir = _safe_target_dir(root, entry["primary_dir"])
            target_dir.mkdir(parents=True, exist_ok=True)
            target = _resolve_target(target_dir / Path(entry["path"]).name, conflict_policy)
            if conflict_policy == "skip" and target.exists():
                _update_plan_status(
                    plan_path, entry["path"], "skipped", str(target.relative_to(root))
                )
                session.add(
                    _transaction_record(
                        root, run_identifier, sequence, "move", source, target, "skipped"
                    )
                )
                continue
            if not source.exists():
                _update_plan_status(plan_path, entry["path"], "skipped")
                session.add(
                    _transaction_record(
                        root, run_identifier, sequence, "move", source, target, "skipped"
                    )
                )
                continue
            final_target = _move_file(source, target)
            _verify_move(source, final_target, entry["source_hash"])
            moved.append((source, final_target))
            _update_plan_status(
                plan_path, entry["path"], "applied", str(final_target.relative_to(root))
            )
            session.add(
                _transaction_record(
                    root, run_identifier, sequence, "move", source, final_target, "applied"
                )
            )
            for extra in entry["also_relevant"]:
                shortcut_dir = _safe_target_dir(root, extra)
                shortcut_dir.mkdir(parents=True, exist_ok=True)
                shortcut_name = f"{final_target.name}.lnk" if _windows_path() else final_target.name
                shortcut_path = shortcut_dir / shortcut_name
                try:
                    shortcut = create_shortcut(final_target, shortcut_path)
                except OSError:
                    shortcut = copy_fallback(final_target, shortcut_path)
                created_shortcuts.append(shortcut)
                sequence += 1
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
    write_manifests(root, tree, assignments)
    return ApplyResult(
        run_id=run_identifier,
        moved=moved,
        shortcuts=created_shortcuts,
        dry_run=False,
        resumed=resume,
    )


def write_run_plan(root: Path, assignments: list[PlannerAssignment], run_id: str) -> Path:
    plan_path = root / ".autoshelf" / "runs" / f"{run_id}.plan.jsonl"
    if plan_path.exists():
        return plan_path
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for assignment in assignments:
        source = root / assignment.path
        payload = {
            "path": assignment.path,
            "primary_dir": assignment.primary_dir,
            "also_relevant": assignment.also_relevant,
            "summary": assignment.summary,
            "confidence": assignment.confidence,
            "fallback": assignment.fallback,
            "status": "planned",
            "source_hash": _hash_file(source) if source.exists() else "",
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    temp_path = plan_path.with_suffix(".tmp")
    temp_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    temp_path.replace(plan_path)
    return plan_path


def load_run_plan(plan_path: Path) -> list[dict[str, object]]:
    if not plan_path.exists():
        return []
    return [
        json.loads(line)
        for line in plan_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _update_plan_status(
    plan_path: Path, source_path: str, status: str, target_path: str | None = None
) -> None:
    entries = load_run_plan(plan_path)
    for entry in entries:
        if entry["path"] == source_path:
            entry["status"] = status
            if target_path is not None:
                entry["target_path"] = target_path
            break
    temp_path = plan_path.with_suffix(".tmp")
    temp_path.write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries)
        + ("\n" if entries else ""),
        encoding="utf-8",
    )
    temp_path.replace(plan_path)


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


def _safe_target_dir(root: Path, parts: list[str]) -> Path:
    target = root.joinpath(*parts)
    resolved_root = root.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError("target directory escapes the selected root")
    return target


def _resolve_target(target: Path, conflict_policy: str) -> Path:
    if conflict_policy == "overwrite":
        return target
    if conflict_policy == "skip" and target.exists():
        return target
    if conflict_policy == "append-counter":
        return _dedupe_target(target)
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


def _move_file(source: Path, target: Path) -> Path:
    if target.exists():
        target.unlink()
    try:
        source.rename(target)
        return target
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    shutil.copy2(source, target)
    if _hash_file(source) != _hash_file(target):
        raise ValueError("copy verification failed")
    source.unlink()
    return target


def _verify_move(source: Path, target: Path, source_hash: str) -> None:
    if source.exists():
        raise ValueError(f"source still exists after move: {source}")
    if not target.exists():
        raise ValueError(f"target missing after move: {target}")
    if source_hash and _hash_file(target) != source_hash:
        raise ValueError("target hash mismatch after move")


def _windows_path() -> bool:
    import sys

    return sys.platform == "win32"
