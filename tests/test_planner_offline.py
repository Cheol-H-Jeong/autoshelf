from __future__ import annotations

from datetime import datetime
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.naming import validate_folder_name
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.scanner import FileInfo


def test_fake_llm_produces_valid_tree(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()
    file_info = FileInfo(
        absolute_path=tmp_path / "budget.xlsx",
        relative_path=Path("budget.xlsx"),
        parent_name="",
        filename="budget.xlsx",
        stem="budget",
        extension="xlsx",
        size_bytes=3,
        mtime=mtime,
        ctime=mtime,
        file_hash="abc",
    )
    contexts = {file_info.absolute_path: ParsedContext("Budget", "quarterly budget", {})}
    result = PlannerPipeline(config).plan([file_info], contexts)
    assert result.assignments
    assert result.assignments[0].primary_dir[0] in {"Spreadsheets", "스프레드시트"}
    for name in result.tree:
        validate_folder_name(name)


def test_naming_validator_rejects_misc():
    try:
        validate_folder_name("misc")
    except ValueError as exc:
        assert "vague" in str(exc)
    else:
        raise AssertionError("expected ValueError")
