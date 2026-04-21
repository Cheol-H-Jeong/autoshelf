from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from autoshelf.__init__ import __version__
from autoshelf.applier import ApplyInterruptedError, apply_plan
from autoshelf.bundle import export_bundle, import_bundle
from autoshelf.config import AppConfig
from autoshelf.config_admin import inspect_config, migrate_config_file
from autoshelf.db import ContextRecord, Database, FileRecord, default_db_path
from autoshelf.doctor import doctor_exit_code, run_diagnostics
from autoshelf.logging_utils import configure_logging
from autoshelf.parsers import parse_file
from autoshelf.planner.draft import load_draft
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.preview import build_preview
from autoshelf.progress import ProgressReporter
from autoshelf.rules import filter_paths_by_rules, load_planning_rules, merge_exclude_patterns
from autoshelf.scanner import scan_directory
from autoshelf.stats import collect_stats, record_event
from autoshelf.undo import undo_last_apply
from autoshelf.verify import verify_exit_code, verify_root


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)
    reporter = ProgressReporter(args.command or "gui", args.progress)
    if args.command is None or args.command == "gui":
        config = AppConfig.load(Path(args.config) if args.config else None)
        from autoshelf.gui.app import launch_gui

        launch_gui(test_mode=False)
        return
    if args.command == "version":
        reporter.print_result(__version__)
        return
    if args.command == "stats":
        reporter.print_result(collect_stats())
        return
    if args.command == "config":
        config_path = Path(args.config) if args.config else None
        if args.config_command == "show":
            reporter.print_result(inspect_config(config_path).model_dump(mode="json"))
            return
        if args.config_command == "migrate":
            reporter.emit("config.migrate.started")
            result = migrate_config_file(
                config_path,
                write=args.write,
                create_backup=not args.no_backup,
            )
            reporter.emit(
                "config.migrate.completed",
                data={"updated": result.updated, "backup_path": result.backup_path},
            )
            reporter.print_result(result.model_dump(mode="json"))
            return
    if args.command == "doctor":
        reporter.emit("doctor.started")
        report = run_diagnostics(Path(args.root).resolve() if getattr(args, "root", None) else None)
        reporter.emit("doctor.completed", data={"status": doctor_exit_code(report)})
        reporter.print_result(report)
        raise SystemExit(doctor_exit_code(report))
    if args.command == "verify":
        reporter.emit("verify.started")
        report = verify_root(Path(args.root).expanduser().resolve())
        reporter.emit("verify.completed", data={"status": verify_exit_code(report)})
        reporter.print_result(report.model_dump(mode="json"))
        raise SystemExit(verify_exit_code(report))
    if args.command == "export":
        reporter.emit("export.started")
        result = export_bundle(
            Path(args.root).expanduser().resolve(),
            Path(args.output).expanduser() if args.output else None,
        )
        payload = {
            "archive_path": str(result.archive_path),
            "bundle_version": result.metadata.bundle_version,
            "manifest_entries": result.metadata.manifest_entries,
            "files": len(result.metadata.files),
            "run_plans": result.metadata.run_plans,
            "run_states": result.metadata.run_states,
            "verify_issues": result.metadata.verify_issues,
            "history_entries": len(result.metadata.history),
        }
        reporter.emit("export.completed", data={"archive_path": str(result.archive_path)})
        reporter.print_result(payload)
        return
    if args.command == "import":
        reporter.emit("import.started")
        result = import_bundle(
            Path(args.archive).expanduser(),
            Path(args.root).expanduser().resolve(),
        )
        payload = {
            "archive_path": str(result.archive_path),
            "destination_dir": str(result.destination_dir),
            "bundle_version": result.metadata.bundle_version,
            "files": len(result.metadata.files),
            "guide_path": str(result.destination_dir / "bundle" / "IMPORT_GUIDE.md"),
            "source_root": result.metadata.source_root,
            "run_plans": result.metadata.run_plans,
            "run_states": result.metadata.run_states,
            "verify_issues": result.metadata.verify_issues,
            "history_entries": len(result.metadata.history),
        }
        reporter.emit("import.completed", data={"destination_dir": str(result.destination_dir)})
        reporter.print_result(payload)
        return

    config = AppConfig.load(Path(args.config) if args.config else None)
    root = Path(args.root).expanduser().resolve()
    rules = load_planning_rules(root)
    if getattr(args, "exclude", None):
        config.exclude = list(dict.fromkeys([*config.exclude, *args.exclude]))
    config.exclude = merge_exclude_patterns(config.exclude, rules)
    if getattr(args, "chunk_tokens", None):
        config.max_chunk_tokens = args.chunk_tokens
    if getattr(args, "model", None):
        config.llm.planning_model = args.model
    if args.command == "scan":
        reporter.emit("scan.started", message=str(root))
        files = scan_directory(
            root,
            config,
            on_progress=lambda current, total, path: reporter.emit(
                "scan.walk",
                current=current,
                total=total,
                data={"path": str(path.relative_to(root))},
            ),
        )
        _persist_scan(root, files, config)
        record_event("scan", {"files": len(files)})
        reporter.emit("scan.completed", current=len(files), total=len(files))
        reporter.print_result({"files": len(files)})
        return
    if args.command == "plan":
        reporter.emit("plan.started", message=str(root))
        result = _plan(root, config, resume=args.resume, reporter=reporter)
        record_event("plan", result.usage.model_dump())
        reporter.emit("plan.completed", data={"unsure_paths": len(result.unsure_paths)})
        reporter.print_result({"tree": result.tree, "unsure_paths": result.unsure_paths})
        return
    if args.command == "preview":
        reporter.emit("preview.started", message=str(root))
        draft = load_draft(root) if not args.refresh else None
        reused_draft = draft is not None and bool(draft.assignments)
        if reused_draft:
            assignments = filter_paths_by_rules(draft.assignments, rules, lambda item: item.path)
            reporter.emit("preview.plan.reused", current=len(assignments), total=len(assignments))
        else:
            plan_result = _plan(root, config, resume=args.resume, reporter=reporter)
            record_event("plan", plan_result.usage.model_dump())
            assignments = plan_result.assignments
        result = build_preview(
            root,
            assignments,
            conflict_policy=args.policy,
            reused_draft=reused_draft,
        )
        reporter.emit(
            "preview.completed",
            current=result.assignments,
            total=result.assignments,
            data={"preview_dir": result.preview_dir, "shortcuts": result.shortcuts},
        )
        reporter.print_result(result.model_dump(mode="json"))
        return
    if args.command == "apply":
        reporter.emit("apply.plan.started", message=str(root))
        result = _plan(root, config, resume=False, reporter=reporter)
        try:
            outcome = apply_plan(
                root,
                filter_paths_by_rules(result.assignments, rules, lambda item: item.path),
                result.tree,
                dry_run=args.dry_run,
                db_path=default_db_path(root),
                run_id=args.resume,
                resume=bool(args.resume),
                conflict_policy=args.policy,
                on_progress=lambda phase, current, total, path, target: reporter.emit(
                    f"apply.{phase}",
                    current=current,
                    total=total,
                    data={
                        "path": path,
                        "target": str(target.relative_to(root)) if target is not None else None,
                    },
                ),
            )
        except ApplyInterruptedError as exc:
            reporter.emit("apply.interrupted", message=str(exc))
            raise SystemExit(130) from exc
        record_event("apply", {"moved": len(outcome.moved), **result.usage.model_dump()})
        reporter.emit("apply.completed", data={"moved": len(outcome.moved)})
        reporter.print_result({"run_id": outcome.run_id, "dry_run": outcome.dry_run})
        return
    if args.command == "undo":
        reporter.emit("undo.started", message=str(root))
        outcome = undo_last_apply(
            root, default_db_path(root), run_id=args.run_id, dry_run=args.dry_run
        )
        record_event("undo", {"undone": outcome.undone, "conflicts": len(outcome.conflicts)})
        reporter.emit("undo.completed", data={"undone": outcome.undone})
        reporter.print_result(asdict(outcome))
        return
    if args.command == "history":
        history = Database(default_db_path(root)).run_history(root, limit=args.limit)
        reporter.print_result(history)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoshelf")
    parser.add_argument(
        "--log-level", default="info", choices=["debug", "info", "warning", "error"]
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--progress", default="off", choices=["off", "json"])
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

    preview = subparsers.add_parser("preview")
    preview.add_argument("root")
    preview.add_argument("--resume", action="store_true", default=False)
    preview.add_argument("--refresh", action="store_true", default=False)
    preview.add_argument("--policy", default="append-counter")

    undo = subparsers.add_parser("undo")
    undo.add_argument("root")
    undo.add_argument("--run-id", default=None)
    undo.add_argument("--dry-run", action="store_true", default=False)

    history = subparsers.add_parser("history")
    history.add_argument("root")
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--json", action="store_true", default=False)

    verify = subparsers.add_parser("verify")
    verify.add_argument("root")

    export = subparsers.add_parser("export")
    export.add_argument("root")
    export.add_argument("--output", default=None)

    bundle_import = subparsers.add_parser("import")
    bundle_import.add_argument("archive")
    bundle_import.add_argument("root")

    subparsers.add_parser("stats")
    subparsers.add_parser("gui")
    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show")
    config_migrate = config_subparsers.add_parser("migrate")
    config_migrate.add_argument("--write", action="store_true", default=False)
    config_migrate.add_argument("--no-backup", action="store_true", default=False)
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


def _plan(
    root: Path,
    config: AppConfig,
    resume: bool = False,
    reporter: ProgressReporter | None = None,
):
    files = scan_directory(
        root,
        config,
        on_progress=(
            lambda current, total, path: reporter.emit(
                "plan.scan",
                current=current,
                total=total,
                data={"path": str(path.relative_to(root))},
            )
            if reporter is not None
            else None
        ),
    )
    if reporter is not None:
        reporter.emit("plan.parse.started", current=0, total=len(files))
    contexts = {}
    for index, file_info in enumerate(files, start=1):
        contexts[file_info.absolute_path] = parse_file(
            file_info.absolute_path, config.max_head_chars
        )
        if reporter is not None:
            reporter.emit(
                "plan.parse",
                current=index,
                total=len(files),
                data={"path": str(file_info.relative_path)},
            )
    pipeline = PlannerPipeline(config)
    if reporter is not None:
        reporter.emit("plan.chunk.started", current=0, total=len(files))
    return pipeline.plan(
        files,
        contexts,
        root=root,
        resume=resume,
        on_chunk_progress=(
            lambda current, total, size: reporter.emit(
                "plan.chunk",
                current=current,
                total=total,
                data={"chunk_size": size},
            )
            if reporter is not None
            else None
        ),
    )


if __name__ == "__main__":
    logger.disable("autoshelf")
    main()
