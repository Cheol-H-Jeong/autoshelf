from __future__ import annotations

from autoshelf.doctor import doctor_exit_code, run_diagnostics


def test_doctor_report_contains_required_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    report = run_diagnostics(tmp_path)
    assert "python_ok" in report["checks"]
    assert "rules_file_status" in report["checks"]
    assert "llama_cpp" in report["dependencies"]
    assert "rules" in report
    assert "privacy" in report
    assert "llm" in report


def test_doctor_exit_code_is_zero_when_core_checks_pass():
    report = {
        "checks": {
            "python_ok": True,
            "state_dir_writable": True,
        },
        "llm": {"selected_provider": "fake"},
    }
    assert doctor_exit_code(report) == 0


def test_doctor_reports_invalid_rules_file(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text("mappings: [", encoding="utf-8")

    report = run_diagnostics(tmp_path)

    assert report["checks"]["rules_file_status"] == "invalid"


def test_doctor_reports_rule_counts(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
pinned_dirs:
  - Finance/Taxes
exclude_globs:
  - Inbox/**
mappings:
  - glob: "*.pdf"
    source_globs:
      - Inbox/**
    target: Documents/PDFs
  - glob: "*.txt"
    target: "@current"
""".strip(),
        encoding="utf-8",
    )

    report = run_diagnostics(tmp_path)

    assert report["checks"]["rules_file_status"] == "ok"
    assert report["rules"] == {
        "pinned_dirs": 1,
        "exclude_globs": 1,
        "mappings": 2,
        "source_scoped_mappings": 1,
        "current_targets": 1,
    }
