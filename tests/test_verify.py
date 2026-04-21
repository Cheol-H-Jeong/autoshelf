from __future__ import annotations

import json

from autoshelf.applier import apply_plan
from autoshelf.apply_state import (
    run_staging_dir,
    run_state_path,
    update_run_entry,
    write_run_plan,
    write_run_state,
)
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


def test_verify_root_detects_incomplete_run_and_staged_artifact(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = _assignment("draft.txt", ["Docs"])
    run_id = "verify-run"
    write_run_plan(tmp_path, [assignment], run_id)
    write_run_state(
        run_state_path(tmp_path, run_id),
        run_id=run_id,
        status="interrupted",
        current_path="draft.txt",
        completed_entries=0,
        total_entries=1,
        last_error="simulated interruption",
    )
    staged = run_staging_dir(tmp_path, run_id) / "partial.txt.part"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("partial", encoding="utf-8")

    report = verify_root(tmp_path)

    assert {issue.code for issue in report.issues} >= {
        "incomplete_run",
        "incomplete_entry",
        "staged_artifact",
    }


def test_verify_root_flags_duplicate_source_left_after_target_promotion(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = _assignment("draft.txt", ["Docs"])
    run_id = "verify-duplicate"
    plan_path = write_run_plan(tmp_path, [assignment], run_id)
    target = tmp_path / "Docs" / "draft.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")
    update_run_entry(
        plan_path,
        "draft.txt",
        status="running",
        target_path="Docs/draft.txt",
        copy_stage="target-written",
    )
    write_run_state(
        run_state_path(tmp_path, run_id),
        run_id=run_id,
        status="interrupted",
        current_path="draft.txt",
        completed_entries=0,
        total_entries=1,
        last_error="simulated interruption",
    )

    report = verify_root(tmp_path)

    assert {issue.code for issue in report.issues} >= {"duplicate_source"}


def test_verify_root_flags_missing_staged_artifact_for_interrupted_copy(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = _assignment("draft.txt", ["Docs"])
    run_id = "verify-missing-stage"
    plan_path = write_run_plan(tmp_path, [assignment], run_id)
    update_run_entry(
        plan_path,
        "draft.txt",
        status="running",
        target_path="Docs/draft.txt",
        copy_stage="staged",
        staged_path=".autoshelf/staging/verify-missing-stage/draft.part",
    )
    write_run_state(
        run_state_path(tmp_path, run_id),
        run_id=run_id,
        status="interrupted",
        current_path="draft.txt",
        completed_entries=0,
        total_entries=1,
        last_error="simulated interruption",
    )

    report = verify_root(tmp_path)

    assert {issue.code for issue in report.issues} >= {"missing_staged_artifact"}
