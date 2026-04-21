from __future__ import annotations

import subprocess
import sys


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
    for name in ["scan", "plan", "apply", "undo", "history", "stats", "gui", "doctor", "version"]:
        assert name in output


def test_cli_doctor_exits_zero():
    completed = subprocess.run(
        [sys.executable, "-m", "autoshelf", "doctor"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
