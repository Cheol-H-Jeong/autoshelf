from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from autoshelf.db import Database, default_db_path


class BundleFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    size: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)


class BundleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_version: int = 2
    exported_at: str
    source_root: str
    manifest_entries: int = Field(ge=0)
    run_plans: list[str] = Field(default_factory=list)
    history: list[dict[str, object]] = Field(default_factory=list)
    files: list[BundleFileEntry] = Field(default_factory=list)


@dataclass(slots=True)
class ExportBundleResult:
    archive_path: Path
    metadata: BundleMetadata


@dataclass(slots=True)
class ImportBundleResult:
    archive_path: Path
    destination_dir: Path
    metadata: BundleMetadata


@dataclass(slots=True)
class _BundleItem:
    archive_path: str
    payload: bytes


def export_bundle(root: Path, destination: Path | None = None) -> ExportBundleResult:
    resolved_root = root.expanduser().resolve()
    archive_path = _resolve_archive_path(resolved_root, destination)
    bundle_items = _build_bundle_items(resolved_root)
    metadata = _build_metadata(resolved_root, bundle_items)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        _add_bytes(
            archive,
            "bundle/metadata.json",
            json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2).encode(
                "utf-8"
            ),
        )
        for item in bundle_items:
            _add_bytes(archive, item.archive_path, item.payload)
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
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(resolved_archive, "r:gz") as archive:
        metadata = _read_metadata(archive)
        _validate_archive_members(archive, metadata)
        with tempfile.TemporaryDirectory(dir=destination_dir.parent, prefix=".import-") as temp_dir:
            staging_dir = Path(temp_dir)
            _extract_bundle(archive, staging_dir, metadata)
            staging_dir.replace(destination_dir)
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


def _build_metadata(root: Path, bundle_items: list[_BundleItem]) -> BundleMetadata:
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
        files=[
            BundleFileEntry(
                path=item.archive_path,
                size=len(item.payload),
                sha256=hashlib.sha256(item.payload).hexdigest(),
            )
            for item in bundle_items
        ],
    )


def _build_bundle_items(root: Path) -> list[_BundleItem]:
    bundle_items: list[_BundleItem] = []
    for name in ("manifest.jsonl", "FOLDER_GUIDE.md", "FILE_INDEX.md"):
        file_path = root / name
        if file_path.exists():
            bundle_items.append(
                _BundleItem(
                    archive_path=f"bundle/{name}",
                    payload=file_path.read_bytes(),
                )
            )
    draft_path = root / ".autoshelf" / "plan_draft.json"
    if draft_path.exists():
        bundle_items.append(
            _BundleItem(
                archive_path="bundle/plan_draft.json",
                payload=draft_path.read_bytes(),
            )
        )
    rules_path = root / ".autoshelfrc.yaml"
    if rules_path.exists():
        bundle_items.append(
            _BundleItem(
                archive_path="bundle/.autoshelfrc.yaml",
                payload=rules_path.read_bytes(),
            )
        )
    runs_dir = root / ".autoshelf" / "runs"
    for plan_path in sorted(runs_dir.glob("*.plan.jsonl")) if runs_dir.exists() else []:
        bundle_items.append(
            _BundleItem(
                archive_path=f"bundle/runs/{plan_path.name}",
                payload=plan_path.read_bytes(),
            )
        )
    bundle_items.append(
        _BundleItem(
            archive_path="bundle/IMPORT_GUIDE.md",
            payload=_build_import_guide(root, bundle_items).encode("utf-8"),
        )
    )
    return bundle_items


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mtime = int(datetime.now(tz=UTC).timestamp())
    info.mode = 0o644
    archive.addfile(info, BytesIO(payload))


def _build_import_guide(root: Path, bundle_items: list[_BundleItem]) -> str:
    exported_at = datetime.now(tz=UTC).isoformat()
    included_paths = "\n".join(f"- `{item.archive_path}`" for item in bundle_items) or "- none"
    return (
        "# Autoshelf Import Guide\n\n"
        f"- Exported at: `{exported_at}`\n"
        f"- Source root: `{root}`\n"
        f"- Included files:\n{included_paths}\n\n"
        "## How To Use\n\n"
        "1. Run `autoshelf import <archive> <audit-root>` to unpack this bundle into "
        "`<audit-root>/.autoshelf/imports/`.\n"
        "2. Review `bundle/metadata.json` for the bundle inventory and checksums.\n"
        "3. Open `bundle/manifest.jsonl`, `bundle/FOLDER_GUIDE.md`, `bundle/FILE_INDEX.md`, "
        "and any run plans before changing the live tree.\n"
        "4. If the bundle includes `plan_draft.json` or `.autoshelfrc.yaml`, compare them with "
        "the source environment before replaying or debugging a run.\n"
    )


def _read_metadata(archive: tarfile.TarFile) -> BundleMetadata:
    try:
        metadata_member = archive.getmember("bundle/metadata.json")
    except KeyError as exc:
        raise ValueError("bundle metadata.json is missing") from exc
    extracted = archive.extractfile(metadata_member)
    if extracted is None:
        raise ValueError("bundle metadata is unreadable")
    try:
        return BundleMetadata.model_validate_json(extracted.read().decode("utf-8"))
    except ValidationError as exc:
        raise ValueError("bundle metadata is invalid") from exc


def _validate_archive_members(archive: tarfile.TarFile, metadata: BundleMetadata) -> None:
    expected = {entry.path: entry for entry in metadata.files}
    actual_regular_files: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        _validate_member_path(member.name)
        if member.issym() or member.islnk():
            raise ValueError(f"bundle member is not a regular file: {member.name}")
        if member.isdir():
            continue
        if not member.isfile():
            raise ValueError(f"unsupported bundle member type: {member.name}")
        if member.name == "bundle/metadata.json":
            continue
        if member.name in actual_regular_files:
            raise ValueError(f"duplicate bundle member: {member.name}")
        actual_regular_files[member.name] = member
    if set(actual_regular_files) != set(expected):
        missing = sorted(set(expected) - set(actual_regular_files))
        extra = sorted(set(actual_regular_files) - set(expected))
        raise ValueError(
            "bundle inventory mismatch: "
            f"missing={missing or ['<none>']} extra={extra or ['<none>']}"
        )
    for path, member in actual_regular_files.items():
        expected_entry = expected[path]
        if member.size != expected_entry.size:
            raise ValueError(f"bundle member size mismatch for {path}")


def _validate_member_path(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"bundle member escapes destination: {name}")
    if not name.startswith("bundle/"):
        raise ValueError(f"bundle member must live under bundle/: {name}")


def _extract_bundle(
    archive: tarfile.TarFile, destination_dir: Path, metadata: BundleMetadata
) -> None:
    destination_root = destination_dir.resolve()
    for member in archive.getmembers():
        if member.isdir():
            continue
        target_path = destination_root / member.name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError(f"bundle member is unreadable: {member.name}")
        target_path.write_bytes(extracted.read())
    _verify_extracted_files(destination_root, metadata)


def _verify_extracted_files(destination_root: Path, metadata: BundleMetadata) -> None:
    for entry in metadata.files:
        extracted_path = destination_root / entry.path
        if not extracted_path.exists():
            raise ValueError(f"bundle member missing after import: {entry.path}")
        payload = extracted_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != entry.sha256:
            raise ValueError(f"bundle checksum mismatch for {entry.path}")
    metadata_path = destination_root / "bundle" / "metadata.json"
    if not metadata_path.exists():
        raise ValueError("bundle metadata missing after import")
