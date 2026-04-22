from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autoshelf import __version__
from autoshelf.applier import apply_plan
from autoshelf.apply_state import run_state_path, write_run_plan, write_run_state
from autoshelf.config import AppConfig
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
        "preview",
        "apply",
        "undo",
        "history",
        "verify",
        "export",
        "import",
        "config",
        "stats",
        "gui",
        "doctor",
        "model",
        "rules",
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


def test_cli_rules_show_reports_normalized_rules(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
mappings:
  - glob: "*.txt"
    source_globs:
      - Inbox/**
    target: "@current"
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "rules", "show", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["rules"]["mappings"][0]["target_mode"] == "current"
    assert payload["rules"]["mappings"][0]["source_globs"] == ["Inbox/**"]


def test_cli_rules_match_explains_current_target_mapping(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
mappings:
  - glob: "*.txt"
    source_globs:
      - Inbox/**
    target: "@current"
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoshelf",
            "rules",
            "match",
            str(tmp_path),
            "Inbox/Notes/draft.txt",
            "Archive/draft.txt",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload[0]["matched"] is True
    assert payload[0]["target"] == ["Inbox", "Notes"]
    assert payload[0]["target_mode"] == "current"
    assert payload[1]["matched"] is False


def test_cli_plan_skips_paths_excluded_by_rules_file(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
exclude_globs:
  - Inbox/**
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "Inbox").mkdir()
    (tmp_path / "Inbox" / "draft.txt").write_text("ignore me", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("keep me", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "plan", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    assert completed.returncode == 0
    draft = json.loads((tmp_path / ".autoshelf" / "plan_draft.json").read_text(encoding="utf-8"))

    assert [entry["path"] for entry in draft["assignments"]] == ["keep.txt"]


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
    assert events[0]["event"] == "command"
    assert events[0]["status"] == "started"
    assert all("event" in event for event in events)
    assert events[-1]["event"] == "result"
    assert events[-2]["event"] == "command"
    assert events[-2]["status"] == "completed"
    assert "tree" in events[-1]["payload"]
    assert any(event.get("phase") == "plan.parse" for event in events[:-1])


def test_cli_version_progress_json_reports_command_lifecycle():
    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "--progress", "json", "version"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]

    assert [event["event"] for event in events] == ["command", "command", "result"]
    assert events[0]["status"] == "started"
    assert events[0]["argv"] == ["--progress", "json", "version"]
    assert events[0]["version"] == __version__
    assert events[1]["status"] == "completed"
    assert events[1]["exit_code"] == 0
    assert events[2]["payload"] == __version__


def test_cli_verify_progress_json_marks_failed_command_and_keeps_report_payload(tmp_path):
    (tmp_path / "draft.txt").write_text("hello", encoding="utf-8")
    assignment = PlannerAssignment(path="draft.txt", primary_dir=["Docs"], summary="hello")
    run_id = "cli-progress-verify-failure"
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
        [sys.executable, "-m", "autoshelf", "--progress", "json", "verify", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert completed.returncode == 1
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]

    assert events[0]["event"] == "command"
    assert events[0]["status"] == "started"
    assert events[-2]["event"] == "command"
    assert events[-2]["status"] == "failed"
    assert events[-2]["exit_code"] == 1
    assert events[-1]["event"] == "result"
    assert any(issue["code"] == "incomplete_run" for issue in events[-1]["payload"]["issues"])


def test_cli_config_show_reports_pending_migrations(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('theme = "MIDNIGHT"\n', encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "--config", str(config_path), "config", "show"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == 0
    assert payload["up_to_date"] is False
    assert [step["version"] for step in payload["pending_migrations"]] == [1, 2, 3]


def test_cli_config_migrate_writes_backup_and_updated_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('theme = "MIDNIGHT"\n', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoshelf",
            "--config",
            str(config_path),
            "config",
            "migrate",
            "--write",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["updated"] is True
    assert payload["backup_path"]
    assert Path(payload["backup_path"]).exists()
    assert AppConfig.load(config_path).schema_version > 0


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


def test_cli_preview_builds_browsable_tree_from_draft(tmp_path):
    (tmp_path / "draft.txt").write_text("hello", encoding="utf-8")

    planned = subprocess.run(
        [sys.executable, "-m", "autoshelf", "plan", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )
    assert '"tree"' in planned.stdout
    assert (tmp_path / ".autoshelf" / "plan_draft.json").exists()

    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "preview", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = json.loads(completed.stdout)
    preview_dir = Path(payload["preview_dir"])
    links = payload["links"]
    assert payload["reused_draft"] is True
    assert preview_dir.exists()
    assert links
    assert (preview_dir / links[0]["preview_path"]).is_symlink()
