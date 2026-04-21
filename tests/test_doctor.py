from __future__ import annotations

from autoshelf.doctor import doctor_exit_code, run_diagnostics


def test_doctor_report_contains_required_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    report = run_diagnostics(tmp_path)
    assert "python_ok" in report["checks"]
    assert "rules_file_status" in report["checks"]
    assert "anthropic" in report["dependencies"]


def test_doctor_exit_code_is_zero_when_core_checks_pass():
    report = {
        "checks": {
            "python_ok": True,
            "state_dir_writable": True,
        }
    }
    assert doctor_exit_code(report) == 0


def test_doctor_reports_invalid_rules_file(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text("mappings: [", encoding="utf-8")

    report = run_diagnostics(tmp_path)

    assert report["checks"]["rules_file_status"] == "invalid"
