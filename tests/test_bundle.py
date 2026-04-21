from __future__ import annotations

import json
import tarfile
from pathlib import Path

from autoshelf.applier import apply_plan
from autoshelf.bundle import export_bundle, import_bundle
from autoshelf.planner.models import PlannerAssignment


def test_export_bundle_captures_manifest_and_runs(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    apply_plan(tmp_path, [assignment], {"Docs": {}}, dry_run=False)

    result = export_bundle(tmp_path)

    assert result.archive_path.exists()
    assert result.metadata.manifest_entries == 1
    assert len(result.metadata.run_plans) == 1
    with tarfile.open(result.archive_path, "r:gz") as archive:
        names = set(archive.getnames())
    assert "bundle/metadata.json" in names
    assert "bundle/manifest.jsonl" in names
    assert "bundle/FOLDER_GUIDE.md" in names
    assert "bundle/FILE_INDEX.md" in names
    assert any(name.startswith("bundle/runs/") for name in names)


def test_import_bundle_extracts_into_auditable_directory(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    apply_plan(source_root, [assignment], {"Docs": {}}, dry_run=False)
    exported = export_bundle(source_root, tmp_path / "exports")

    destination_root = tmp_path / "destination"
    destination_root.mkdir()
    imported = import_bundle(exported.archive_path, destination_root)

    metadata_path = imported.destination_dir / "bundle" / "metadata.json"
    manifest_path = imported.destination_dir / "bundle" / "manifest.jsonl"
    assert metadata_path.exists()
    assert manifest_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["manifest_entries"] == 1
    assert Path(metadata["source_root"]) == source_root.resolve()


def test_cli_export_and_import_round_trip(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    apply_plan(source_root, [assignment], {"Docs": {}}, dry_run=False)

    import subprocess
    import sys

    export_completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "export", str(source_root)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
    export_payload = json.loads(export_completed.stdout)
    archive_path = Path(export_payload["archive_path"])
    assert archive_path.exists()

    destination_root = tmp_path / "imported"
    destination_root.mkdir()
    import_completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "import", str(archive_path), str(destination_root)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
    import_payload = json.loads(import_completed.stdout)
    imported_dir = Path(import_payload["destination_dir"])
    assert imported_dir.exists()
    assert (imported_dir / "bundle" / "FILE_INDEX.md").exists()
