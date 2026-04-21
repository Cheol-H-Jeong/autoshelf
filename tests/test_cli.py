from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autoshelf.applier import apply_plan
from autoshelf.apply_state import run_state_path, write_run_plan, write_run_state
from autoshelf.planner.models import PlannerAssignment


def test_import_package():
    __import__("autoshelf")


def test_cli_help_lists_expected_subcommands():
    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = completed.stdout
    for name in [
        "scan",
        "plan",
        "apply",
        "undo",
        "history",
        "verify",
        "export",
        "import",
        "stats",
        "gui",
        "doctor",
        "version",
    ]:
        assert name in output


def test_cli_doctor_exits_zero():
    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "doctor"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def test_cli_verify_exits_zero_for_clean_tree(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    apply_plan(tmp_path, [assignment], {"Docs": {}}, dry_run=False)
    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "verify", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert completed.returncode == 0
    assert '"issues": []' in completed.stdout


def test_cli_verify_exits_nonzero_for_incomplete_run(tmp_path):
    (tmp_path / "draft.txt").write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    run_id = "cli-verify-run"
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
    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "verify", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert completed.returncode == 1
    assert '"code": "incomplete_run"' in completed.stdout


def test_cli_plan_uses_rules_file(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
mappings:
  - glob: "*.invoice.pdf"
    target: Finance/Invoices
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "acme.invoice.pdf").write_text("invoice", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "plan", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert completed.returncode == 0
    assert "Finance" in completed.stdout
    assert "Invoices" in completed.stdout


def test_cli_plan_progress_json_streams_events_and_result(tmp_path):
    (tmp_path / "draft.txt").write_text("hello", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "--progress", "json", "plan", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert events
    assert all("event" in event for event in events)
    assert events[-1]["event"] == "result"
    assert "tree" in events[-1]["payload"]
    assert any(event.get("phase") == "plan.parse" for event in events[:-1])


def test_cli_apply_progress_json_streams_events_and_result(tmp_path):
    (tmp_path / "draft.txt").write_text("hello", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "--progress", "json", "apply", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert events[-1]["event"] == "result"
    assert "run_id" in events[-1]["payload"]
    assert any(event.get("phase") == "apply.moved" for event in events[:-1])
