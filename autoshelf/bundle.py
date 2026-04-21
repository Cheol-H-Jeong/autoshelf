from __future__ import annotations

import inspect
import json
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from autoshelf.db import Database, default_db_path


class BundleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_version: int = 1
    exported_at: str
    source_root: str
    manifest_entries: int = Field(ge=0)
    run_plans: list[str] = Field(default_factory=list)
    history: list[dict[str, object]] = Field(default_factory=list)


@dataclass(slots=True)
class ExportBundleResult:
    archive_path: Path
    metadata: BundleMetadata


@dataclass(slots=True)
class ImportBundleResult:
    archive_path: Path
    destination_dir: Path
    metadata: BundleMetadata


def export_bundle(root: Path, destination: Path | None = None) -> ExportBundleResult:
    resolved_root = root.expanduser().resolve()
    archive_path = _resolve_archive_path(resolved_root, destination)
    metadata = _build_metadata(resolved_root)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        _add_bytes(
            archive,
            "bundle/metadata.json",
            json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2).encode(
                "utf-8"
            ),
        )
        for name in ("manifest.jsonl", "FOLDER_GUIDE.md", "FILE_INDEX.md"):
            _add_file_if_present(archive, resolved_root / name, f"bundle/{name}")
        runs_dir = resolved_root / ".autoshelf" / "runs"
        for plan_path in sorted(runs_dir.glob("*.plan.jsonl")) if runs_dir.exists() else []:
            _add_file_if_present(archive, plan_path, f"bundle/runs/{plan_path.name}")
    logger.info("Exported autoshelf bundle to {}", archive_path)
    return ExportBundleResult(archive_path=archive_path, metadata=metadata)


def import_bundle(archive_path: Path, root: Path) -> ImportBundleResult:
    resolved_archive = archive_path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    destination_dir = resolved_root / ".autoshelf" / "imports" / resolved_archive.stem.replace(
        ".tar", ""
    )
    if destination_dir.exists():
        raise FileExistsError(f"bundle import already exists: {destination_dir}")
    destination_dir.mkdir(parents=True, exist_ok=False)
    with tarfile.open(resolved_archive, "r:gz") as archive:
        _extract_bundle(archive, destination_dir)
    metadata_path = destination_dir / "bundle" / "metadata.json"
    metadata = BundleMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    logger.info("Imported autoshelf bundle from {} into {}", resolved_archive, destination_dir)
    return ImportBundleResult(
        archive_path=resolved_archive, destination_dir=destination_dir, metadata=metadata
    )


def _resolve_archive_path(root: Path, destination: Path | None) -> Path:
    if destination is None:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        return root / ".autoshelf" / "exports" / f"{root.name}-{timestamp}.tar.gz"
    target = destination.expanduser()
    if target.suffixes[-2:] == [".tar", ".gz"]:
        return target.resolve()
    return target.resolve() / f"{root.name}.tar.gz"


def _build_metadata(root: Path) -> BundleMetadata:
    manifest_path = root / "manifest.jsonl"
    manifest_entries = 0
    if manifest_path.exists():
        manifest_entries = sum(
            1 for line in manifest_path.read_text(encoding="utf-8").splitlines() if line
        )
    runs_dir = root / ".autoshelf" / "runs"
    run_plans = (
        sorted(plan_path.name for plan_path in runs_dir.glob("*.plan.jsonl"))
        if runs_dir.exists()
        else []
    )
    database = Database(default_db_path(root))
    history = database.run_history(root, limit=50) if database.path.exists() else []
    return BundleMetadata(
        exported_at=datetime.now(tz=UTC).isoformat(),
        source_root=str(root),
        manifest_entries=manifest_entries,
        run_plans=run_plans,
        history=history,
    )


def _add_file_if_present(archive: tarfile.TarFile, source: Path, name: str) -> None:
    if source.exists():
        archive.add(source, arcname=name, recursive=False)


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    import io

    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mtime = int(datetime.now(tz=UTC).timestamp())
    archive.addfile(info, io.BytesIO(payload))


def _extract_bundle(archive: tarfile.TarFile, destination_dir: Path) -> None:
    destination_root = destination_dir.resolve()
    for member in archive.getmembers():
        member_path = destination_root / member.name
        resolved_member = member_path.resolve(strict=False)
        if resolved_member != destination_root and destination_root not in resolved_member.parents:
            raise ValueError(f"bundle member escapes destination: {member.name}")
    extractall_parameters = inspect.signature(archive.extractall).parameters
    if "filter" in extractall_parameters:
        archive.extractall(destination_dir, filter="data")
        return
    archive.extractall(destination_dir)
