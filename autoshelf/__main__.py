from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from autoshelf.applier import apply_plan
from autoshelf.config import AppConfig
from autoshelf.db import ContextRecord, Database, FileRecord, default_db_path
from autoshelf.gui.app import launch_gui
from autoshelf.manifest import write_manifests
from autoshelf.parsers import parse_file
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.scanner import scan_directory
from autoshelf.undo import undo_last_apply


def main() -> None:
    """CLI entry point."""

    parser = _build_parser()
    args = parser.parse_args()
    if args.command is None:
        launch_gui()
        return
    if args.command == "gui":
        launch_gui()
        return
    config = AppConfig.load()
    root = Path(args.root).expanduser().resolve()
    if args.command == "scan":
        files = scan_directory(root, config)
        _persist_scan(root, files, config)
        print(json.dumps({"files": len(files)}, ensure_ascii=False))
        return
    if args.command == "plan":
        result = _plan(root, config)
        print(json.dumps({"tree": result.tree}, ensure_ascii=False, indent=2))
        return
    if args.command == "apply":
        result = _plan(root, config)
        outcome = apply_plan(
            root,
            result.assignments,
            result.tree,
            dry_run=args.dry_run,
            db_path=default_db_path(root),
        )
        if outcome.dry_run:
            write_manifests(root, result.tree, result.assignments)
        payload = {"run_id": outcome.run_id, "dry_run": outcome.dry_run}
        print(json.dumps(payload, ensure_ascii=False))
        return
    if args.command == "undo":
        count = undo_last_apply(root, default_db_path(root))
        print(json.dumps({"undone": count}, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoshelf")
    subparsers = parser.add_subparsers(dest="command")
    for name in ["scan", "plan", "apply", "undo"]:
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("root")
        if name == "apply":
            command_parser.add_argument("--dry-run", action="store_true", default=False)
    subparsers.add_parser("gui")
    return parser


def _persist_scan(root: Path, files: list, config: AppConfig) -> dict[Path, object]:
    database = Database(default_db_path(root))
    contexts = {}
    with database.session() as session:
        for file_info in files:
            existing = session.execute(
                select(FileRecord).where(FileRecord.path == str(file_info.absolute_path))
            ).scalar_one_or_none()
            record = existing or FileRecord(
                root=str(root),
                path=str(file_info.absolute_path),
                parent_name="",
                filename="",
                stem="",
                extension="",
                size_bytes=0,
                mtime=0.0,
                ctime=0.0,
                file_hash="",
            )
            record.root = str(root)
            record.parent_name = file_info.parent_name
            record.filename = file_info.filename
            record.stem = file_info.stem
            record.extension = file_info.extension
            record.size_bytes = file_info.size_bytes
            record.mtime = file_info.mtime
            record.ctime = file_info.ctime
            record.file_hash = file_info.file_hash
            session.add(record)
            session.flush()
            context = parse_file(file_info.absolute_path, config.max_head_chars)
            contexts[file_info.absolute_path] = context
            existing_context = session.execute(
                select(ContextRecord).where(ContextRecord.file_id == record.id)
            ).scalar_one_or_none()
            context_record = existing_context or ContextRecord(
                file_id=record.id,
                title="",
                head_text="",
                extra_meta={},
            )
            context_record.title = context.title
            context_record.head_text = context.head_text
            context_record.extra_meta = context.extra_meta
            session.add(context_record)
    return contexts


def _plan(root: Path, config: AppConfig):
    files = scan_directory(root, config)
    contexts = {
        file_info.absolute_path: parse_file(file_info.absolute_path, config.max_head_chars)
        for file_info in files
    }
    pipeline = PlannerPipeline(config)
    return pipeline.plan(files, contexts)


if __name__ == "__main__":
    logger.disable("autoshelf")
    main()
