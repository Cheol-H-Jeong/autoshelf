from __future__ import annotations

from datetime import datetime
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.naming import validate_folder_name
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.planner.draft import draft_path
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


def test_fake_llm_picks_one_language_for_whole_corpus(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()

    def make(name, ext, title, head):
        return FileInfo(
            absolute_path=tmp_path / name,
            relative_path=Path(name),
            parent_name="",
            filename=name,
            stem=name.rsplit(".", 1)[0],
            extension=ext,
            size_bytes=1,
            mtime=mtime,
            ctime=mtime,
            file_hash="h",
        )

    files = [
        make("budget.txt", "txt", "Budget", "english english english"),
        make("보고서.txt", "txt", "보고서", "한국어 본문입니다"),
    ]
    contexts = {
        files[0].absolute_path: ParsedContext("Budget", "english english english", {}),
        files[1].absolute_path: ParsedContext("보고서", "한국어 본문입니다", {}),
    }
    result = PlannerPipeline(config).plan(files, contexts)
    primaries = {a.primary_dir[0] for a in result.assignments}
    assert len(primaries) == 1, f"expected one top-level folder, got {primaries}"
    assert primaries & {"Documents", "문서"}


def test_resume_from_draft_skips_completed_chunks(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig(max_chunk_tokens=5)
    mtime = datetime(2024, 5, 1).timestamp()
    files = []
    contexts = {}
    for index in range(3):
        file_info = FileInfo(
            absolute_path=tmp_path / f"note-{index}.txt",
            relative_path=Path(f"note-{index}.txt"),
            parent_name="",
            filename=f"note-{index}.txt",
            stem=f"note-{index}",
            extension="txt",
            size_bytes=1,
            mtime=mtime,
            ctime=mtime,
            file_hash=str(index),
        )
        files.append(file_info)
        contexts[file_info.absolute_path] = ParsedContext(f"Title {index}", "english content", {})
    pipeline = PlannerPipeline(config)
    result = pipeline.plan(files, contexts, root=tmp_path)
    assert draft_path(tmp_path).exists()
    resumed = PlannerPipeline(config).plan(files, contexts, root=tmp_path, resume=True)
    assert resumed.tree == result.tree
    assert len(resumed.assignments) == len(result.assignments)
