from __future__ import annotations

import json

from autoshelf.applier import apply_plan
from autoshelf.planner.models import PlannerAssignment
from autoshelf.verify import verify_root


def _assignment(
    path: str, primary: list[str], also: list[list[str]] | None = None
) -> PlannerAssignment:
    return PlannerAssignment(
        path=path, primary_dir=primary, also_relevant=also or [], summary="hello"
    )


def test_verify_root_accepts_clean_applied_tree(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    apply_plan(
        tmp_path,
        [_assignment("draft.txt", ["Docs"], [["Archive"]])],
        {"Docs": {}},
        dry_run=False,
    )
    report = verify_root(tmp_path)
    assert report.ok is True
    assert report.issues == []


def test_verify_root_detects_tampered_manifest_chain(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    apply_plan(tmp_path, [_assignment("draft.txt", ["Docs"])], {"Docs": {}}, dry_run=False)
    manifest_path = tmp_path / "manifest.jsonl"
    payload = json.loads(manifest_path.read_text(encoding="utf-8").strip())
    payload["summary"] = "tampered"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    report = verify_root(tmp_path)
    assert {issue.code for issue in report.issues} >= {"chain_hash_mismatch"}


def test_verify_root_detects_hash_drift_and_unexpected_file(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    apply_plan(tmp_path, [_assignment("draft.txt", ["Docs"])], {"Docs": {}}, dry_run=False)
    moved = tmp_path / "Docs" / "draft.txt"
    moved.write_text("changed", encoding="utf-8")
    (tmp_path / "surprise.txt").write_text("extra", encoding="utf-8")
    report = verify_root(tmp_path)
    assert {issue.code for issue in report.issues} >= {"hash_mismatch", "unexpected_file"}
