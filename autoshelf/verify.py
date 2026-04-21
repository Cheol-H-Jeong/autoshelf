from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from autoshelf.apply_state import (
    RunPlanEntry,
    load_all_run_states,
    load_run_plan_entries,
    run_plan_path,
    run_staging_dir,
)
from autoshelf.manifest import (
    GENESIS_HASH,
    ManifestEntry,
    expected_shortcut_paths,
    load_manifest_entries,
)
from autoshelf.scanner import _hash_file

IGNORED_ROOT_FILES = {"manifest.jsonl", "FILE_INDEX.md", "FOLDER_GUIDE.md"}
IGNORED_ROOT_DIRS = {".autoshelf"}


class VerifyIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    path: str
    message: str


class VerifyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    manifest_path: str
    manifest_entries: int = 0
    scanned_files: int = 0
    issues: list[VerifyIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def verify_root(root: Path) -> VerifyReport:
    manifest_path = root / "manifest.jsonl"
    report = VerifyReport(root=str(root), manifest_path=str(manifest_path))
    if not manifest_path.exists():
        report.issues.append(
            VerifyIssue(
                code="manifest_missing",
                path="manifest.jsonl",
                message="manifest.jsonl is missing",
            )
        )
        report.issues.extend(_validate_run_state(root))
        return report
    try:
        entries = load_manifest_entries(manifest_path)
    except Exception as exc:  # pragma: no cover - exercised through CLI and malformed files
        logger.warning("manifest parse failed for {}: {}", manifest_path, exc)
        report.issues.append(
            VerifyIssue(
                code="manifest_parse_error",
                path="manifest.jsonl",
                message=str(exc),
            )
        )
        report.issues.extend(_validate_run_state(root))
        return report

    report.manifest_entries = len(entries)
    report.issues.extend(_validate_hash_chain(entries))
    expected_files = set()
    for entry in entries:
        expected_files.add(entry.target)
        target = root / entry.target
        source = root / entry.source
        if not target.exists():
            if source.exists():
                report.issues.append(
                    VerifyIssue(
                        code="pending_apply",
                        path=entry.target,
                        message=f"expected target missing; source still exists at {entry.source}",
                    )
                )
            else:
                report.issues.append(
                    VerifyIssue(
                        code="missing_target",
                        path=entry.target,
                        message="expected target file is missing",
                    )
                )
        elif not target.is_file():
            report.issues.append(
                VerifyIssue(
                    code="target_not_file",
                    path=entry.target,
                    message="expected target exists but is not a regular file",
                )
            )
        elif entry.content_hash and _hash_file(target) != entry.content_hash:
            report.issues.append(
                VerifyIssue(
                    code="hash_mismatch",
                    path=entry.target,
                    message="target content hash does not match manifest",
                )
            )

        for shortcut in expected_shortcut_paths(entry):
            expected_files.add(shortcut)
            shortcut_path = root / shortcut
            if not (shortcut_path.exists() or shortcut_path.is_symlink()):
                report.issues.append(
                    VerifyIssue(
                        code="missing_shortcut",
                        path=shortcut,
                        message="expected related-location shortcut is missing",
                    )
                )

    actual_files = _collect_actual_files(root)
    report.scanned_files = len(actual_files)
    for unexpected in sorted(actual_files - expected_files):
        report.issues.append(
            VerifyIssue(
                code="unexpected_file",
                path=unexpected,
                message="file exists on disk but is not described by the manifest",
            )
        )
    report.issues.extend(_validate_run_state(root))
    return report


def verify_exit_code(report: VerifyReport) -> int:
    return 0 if report.ok else 1


def _validate_hash_chain(entries: list[ManifestEntry]) -> list[VerifyIssue]:
    issues: list[VerifyIssue] = []
    previous_hash = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != previous_hash:
            issues.append(
                VerifyIssue(
                    code="chain_prev_mismatch",
                    path=entry.target,
                    message="manifest prev_hash does not match the previous entry",
                )
            )
        computed_hash = entry.computed_entry_hash()
        if entry.entry_hash != computed_hash:
            issues.append(
                VerifyIssue(
                    code="chain_hash_mismatch",
                    path=entry.target,
                    message="manifest entry_hash does not match the entry payload",
                )
            )
        previous_hash = entry.entry_hash
    return issues


def _collect_actual_files(root: Path) -> set[str]:
    actual_files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(root)
        if _is_ignored(relative):
            continue
        actual_files.add(relative.as_posix())
    return actual_files


def _is_ignored(relative: Path) -> bool:
    if relative.name in IGNORED_ROOT_FILES:
        return True
    return any(part in IGNORED_ROOT_DIRS for part in relative.parts)


def _validate_run_state(root: Path) -> list[VerifyIssue]:
    issues: list[VerifyIssue] = []
    for state in load_all_run_states(root):
        if state.status == "completed":
            continue
        issues.append(
            VerifyIssue(
                code="incomplete_run",
                path=f".autoshelf/runs/{state.run_id}.state.json",
                message=(
                    f"run {state.run_id} is {state.status} at {state.current_path or '<idle>'}; "
                    "resume or inspect the run plan before trusting the tree"
                ),
            )
        )
        plan_path = run_plan_path(root, state.run_id)
        for entry in load_run_plan_entries(plan_path):
            if entry.status == "applied":
                continue
            issues.append(
                VerifyIssue(
                    code="incomplete_entry",
                    path=entry.target_path or entry.path,
                    message=f"run {state.run_id} still has entry status {entry.status}",
                )
            )
            issues.extend(_validate_incomplete_entry(root, state.run_id, entry))
        staging_dir = run_staging_dir(root, state.run_id)
        if staging_dir.exists():
            for staged in sorted(path for path in staging_dir.rglob("*") if path.is_file()):
                issues.append(
                    VerifyIssue(
                        code="staged_artifact",
                        path=str(staged.relative_to(root)),
                        message="staged recovery artifact remains from an incomplete run",
                    )
                )
    return issues


def _validate_incomplete_entry(root: Path, run_id: str, entry: RunPlanEntry) -> list[VerifyIssue]:
    issues: list[VerifyIssue] = []
    entry_path = Path(entry.path)
    source = root / entry.path
    target = root / entry.target_path if entry.target_path else None
    staged = root / entry.staged_path if entry.staged_path else None
    if (
        target is not None
        and target.exists()
        and source.exists()
        and _matching_content(entry.source_hash, source, target)
    ):
        issues.append(
            VerifyIssue(
                code="duplicate_source",
                path=entry.path,
                message=(
                    f"run {run_id} promoted {entry_path.name} to {entry.target_path} but left the "
                    "source copy behind; resume can safely prune the duplicate"
                ),
            )
        )
    if entry.copy_stage == "staged" and staged is not None and not staged.exists():
        issues.append(
            VerifyIssue(
                code="missing_staged_artifact",
                path=entry.path,
                message=(
                    f"run {run_id} expected staged copy {entry.staged_path} before target promotion"
                ),
            )
        )
    return issues


def _matching_content(source_hash: str, source: Path, target: Path) -> bool:
    if source_hash:
        return _hash_file(source) == source_hash and _hash_file(target) == source_hash
    return _hash_file(source) == _hash_file(target)
