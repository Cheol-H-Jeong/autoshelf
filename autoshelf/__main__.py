from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from autoshelf.__init__ import __version__
from autoshelf.applier import apply_plan
from autoshelf.config import AppConfig
from autoshelf.db import ContextRecord, Database, FileRecord, default_db_path
from autoshelf.doctor import doctor_exit_code, run_diagnostics
from autoshelf.logging_utils import configure_logging
from autoshelf.parsers import parse_file
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.scanner import scan_directory
from autoshelf.stats import collect_stats, record_event
from autoshelf.undo import undo_last_apply


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    config = AppConfig.load(Path(args.config) if args.config else None)
    configure_logging(args.log_level)
    if args.command is None or args.command == "gui":
        from autoshelf.gui.app import launch_gui

        launch_gui(test_mode=False)
        return
    if args.command == "version":
        print(__version__)
        return
    if args.command == "stats":
        print(json.dumps(collect_stats(), ensure_ascii=False, indent=2))
        return
    if args.command == "doctor":
        report = run_diagnostics(Path(args.root).resolve() if getattr(args, "root", None) else None)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit(doctor_exit_code(report))

    root = Path(args.root).expanduser().resolve()
    if getattr(args, "exclude", None):
        config.exclude = list(dict.fromkeys([*config.exclude, *args.exclude]))
    if getattr(args, "chunk_tokens", None):
        config.max_chunk_tokens = args.chunk_tokens
    if getattr(args, "model", None):
        config.llm.planning_model = args.model
    if args.command == "scan":
        files = scan_directory(root, config)
        _persist_scan(root, files, config)
        record_event("scan", {"files": len(files)})
        print(json.dumps({"files": len(files)}, ensure_ascii=False))
        return
    if args.command == "plan":
        result = _plan(root, config, resume=args.resume)
        record_event("plan", result.usage.model_dump())
        print(
            json.dumps(
                {"tree": result.tree, "unsure_paths": result.unsure_paths},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "apply":
        result = _plan(root, config, resume=False)
        outcome = apply_plan(
            root,
            result.assignments,
            result.tree,
            dry_run=args.dry_run,
            db_path=default_db_path(root),
            run_id=args.resume,
            resume=bool(args.resume),
            conflict_policy=args.policy,
        )
        record_event("apply", {"moved": len(outcome.moved), **result.usage.model_dump()})
        print(
            json.dumps({"run_id": outcome.run_id, "dry_run": outcome.dry_run}, ensure_ascii=False)
        )
        return
    if args.command == "undo":
        outcome = undo_last_apply(
            root, default_db_path(root), run_id=args.run_id, dry_run=args.dry_run
        )
        record_event("undo", {"undone": outcome.undone, "conflicts": len(outcome.conflicts)})
        print(json.dumps(outcome.__dict__, ensure_ascii=False, default=str))
        return
    if args.command == "history":
        history = Database(default_db_path(root)).run_history(root, limit=args.limit)
        print(json.dumps(history, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoshelf")
    parser.add_argument(
        "--log-level", default="info", choices=["debug", "info", "warning", "error"]
    )
    parser.add_argument("--config", default=None)
    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser("scan")
    scan.add_argument("root")
    scan.add_argument("--exclude", action="append", default=[])
    scan.add_argument("--json", action="store_true", default=False)

    plan = subparsers.add_parser("plan")
    plan.add_argument("root")
    plan.add_argument("--resume", action="store_true", default=False)
    plan.add_argument("--model", default=None)
    plan.add_argument("--chunk-tokens", type=int, default=None)
    plan.add_argument("--dry-run", action="store_true", default=False)

    apply = subparsers.add_parser("apply")
    apply.add_argument("root")
    apply.add_argument("--resume", default=None)
    apply.add_argument("--dry-run", action="store_true", default=False)
    apply.add_argument("--policy", default="append-counter")
    apply.add_argument("--yes", action="store_true", default=False)

    undo = subparsers.add_parser("undo")
    undo.add_argument("root")
    undo.add_argument("--run-id", default=None)
    undo.add_argument("--dry-run", action="store_true", default=False)

    history = subparsers.add_parser("history")
    history.add_argument("root")
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--json", action="store_true", default=False)

    subparsers.add_parser("stats")
    subparsers.add_parser("gui")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("root", nargs="?")
    subparsers.add_parser("version")
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
                file_id=record.id, title="", head_text="", extra_meta={}
            )
            context_record.title = context.title
            context_record.head_text = context.head_text
            context_record.extra_meta = context.extra_meta
            session.add(context_record)
    return contexts


def _plan(root: Path, config: AppConfig, resume: bool = False):
    files = scan_directory(root, config)
    contexts = {
        file_info.absolute_path: parse_file(file_info.absolute_path, config.max_head_chars)
        for file_info in files
    }
    pipeline = PlannerPipeline(config)
    return pipeline.plan(files, contexts, root=root, resume=resume)


if __name__ == "__main__":
    logger.disable("autoshelf")
    main()
