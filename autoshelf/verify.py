from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

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
