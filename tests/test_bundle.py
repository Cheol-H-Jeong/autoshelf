from __future__ import annotations

import json
import tarfile
from pathlib import Path

from autoshelf.applier import apply_plan
from autoshelf.apply_state import run_state_path, write_run_state
from autoshelf.bundle import export_bundle, import_bundle
from autoshelf.planner.draft import save_draft
from autoshelf.planner.models import PlanDraft, PlannerAssignment


def test_export_bundle_captures_manifest_and_runs(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    (tmp_path / ".autoshelfrc.yaml").write_text("version: 1\n", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    save_draft(tmp_path, PlanDraft(assignments=[assignment], tree={"Docs": {}}, unsure_paths=[]))
    outcome = apply_plan(tmp_path, [assignment], {"Docs": {}}, dry_run=False)
    write_run_state(
        run_state_path(tmp_path, "pending-review"),
        run_id="pending-review",
        status="interrupted",
        current_path="draft.txt",
        completed_entries=0,
        total_entries=1,
        last_error="support capture",
    )

    result = export_bundle(tmp_path)

    assert result.archive_path.exists()
    assert result.metadata.manifest_entries == 1
    assert len(result.metadata.run_plans) == 1
    assert sorted(result.metadata.run_states) == [
        f"{outcome.run_id}.state.json",
        "pending-review.state.json",
    ]
    assert result.metadata.verify_issues == 2
    assert any(entry.path == "bundle/plan_draft.json" for entry in result.metadata.files)
    assert any(entry.path == "bundle/.autoshelfrc.yaml" for entry in result.metadata.files)
    assert any(entry.path == "bundle/VERIFY_REPORT.json" for entry in result.metadata.files)
    assert any(entry.path == "bundle/history.json" for entry in result.metadata.files)
    assert any(entry.path == "bundle/IMPORT_GUIDE.md" for entry in result.metadata.files)
    with tarfile.open(result.archive_path, "r:gz") as archive:
        names = set(archive.getnames())
    assert "bundle/metadata.json" in names
    assert "bundle/manifest.jsonl" in names
    assert "bundle/FOLDER_GUIDE.md" in names
    assert "bundle/FILE_INDEX.md" in names
    assert "bundle/plan_draft.json" in names
    assert "bundle/.autoshelfrc.yaml" in names
    assert "bundle/VERIFY_REPORT.json" in names
    assert "bundle/history.json" in names
    assert "bundle/IMPORT_GUIDE.md" in names
    assert f"bundle/runs/{outcome.run_id}.plan.jsonl" in names
    assert f"bundle/runs/{outcome.run_id}.state.json" in names
    assert "bundle/runs/pending-review.state.json" in names


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
    guide_path = imported.destination_dir / "bundle" / "IMPORT_GUIDE.md"
    verify_path = imported.destination_dir / "bundle" / "VERIFY_REPORT.json"
    history_path = imported.destination_dir / "bundle" / "history.json"
    assert metadata_path.exists()
    assert manifest_path.exists()
    assert guide_path.exists()
    assert verify_path.exists()
    assert history_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["manifest_entries"] == 1
    assert metadata["verify_issues"] == 0
    assert Path(metadata["source_root"]) == source_root.resolve()
    verify_payload = json.loads(verify_path.read_text(encoding="utf-8"))
    assert verify_payload["issues"] == []
    assert json.loads(history_path.read_text(encoding="utf-8"))


def test_import_bundle_rejects_checksum_mismatch_and_cleans_staging(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    apply_plan(source_root, [assignment], {"Docs": {}}, dry_run=False)
    exported = export_bundle(source_root, tmp_path / "exports")

    tampered_archive = tmp_path / "tampered.tar.gz"
    with tarfile.open(exported.archive_path, "r:gz") as source_archive, tarfile.open(
        tampered_archive, "w:gz"
    ) as target_archive:
        for member in source_archive.getmembers():
            extracted = source_archive.extractfile(member) if member.isfile() else None
            payload = extracted.read() if extracted is not None else b""
            if member.name == "bundle/manifest.jsonl":
                payload = b'{"tampered":true}\n'
                member = tarfile.TarInfo(member.name)
                member.size = len(payload)
            target_archive.addfile(member, fileobj=None if member.isdir() else _bytes_io(payload))

    destination_root = tmp_path / "destination"
    destination_root.mkdir()

    try:
        import_bundle(tampered_archive, destination_root)
    except ValueError as exc:
        assert "size mismatch" in str(exc) or "checksum mismatch" in str(exc)
    else:
        raise AssertionError("import_bundle accepted a tampered archive")

    imports_root = destination_root / ".autoshelf" / "imports"
    assert not any(path.name.startswith(".import-") for path in imports_root.glob("*"))


def test_import_bundle_rejects_members_outside_bundle_prefix(tmp_path):
    archive_path = tmp_path / "malicious.tar.gz"
    metadata = {
        "bundle_version": 3,
        "exported_at": "2026-04-22T00:00:00+00:00",
        "source_root": "/tmp/source",
        "manifest_entries": 0,
        "run_plans": [],
        "run_states": [],
        "verify_issues": 0,
        "history": [],
        "files": [],
    }
    with tarfile.open(archive_path, "w:gz") as archive:
        metadata_bytes = json.dumps(metadata).encode("utf-8")
        metadata_info = tarfile.TarInfo("bundle/metadata.json")
        metadata_info.size = len(metadata_bytes)
        archive.addfile(metadata_info, fileobj=_bytes_io(metadata_bytes))

        bad_bytes = b"oops"
        bad_info = tarfile.TarInfo("../escape.txt")
        bad_info.size = len(bad_bytes)
        archive.addfile(bad_info, fileobj=_bytes_io(bad_bytes))

    destination_root = tmp_path / "destination"
    destination_root.mkdir()

    try:
        import_bundle(archive_path, destination_root)
    except ValueError as exc:
        assert "escapes destination" in str(exc)
    else:
        raise AssertionError("import_bundle accepted an unsafe archive member")


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
    assert export_payload["bundle_version"] == 3
    assert export_payload["files"] >= 6
    assert export_payload["history_entries"] >= 1
    assert export_payload["run_states"]
    assert export_payload["verify_issues"] == 0

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
    assert import_payload["bundle_version"] == 3
    assert import_payload["files"] >= 6
    assert import_payload["history_entries"] >= 1
    assert import_payload["run_states"]
    assert import_payload["verify_issues"] == 0
    assert (imported_dir / "bundle" / "FILE_INDEX.md").exists()
    assert (imported_dir / "bundle" / "IMPORT_GUIDE.md").exists()
    assert (imported_dir / "bundle" / "VERIFY_REPORT.json").exists()
    assert (imported_dir / "bundle" / "history.json").exists()
    assert Path(import_payload["guide_path"]) == imported_dir / "bundle" / "IMPORT_GUIDE.md"


def _bytes_io(payload: bytes):
    from io import BytesIO

    return BytesIO(payload)
