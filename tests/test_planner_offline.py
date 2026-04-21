from __future__ import annotations

from datetime import datetime
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.draft import draft_path
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
    assert result.assignments[0].path == "budget.xlsx"


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


def test_rules_file_seeds_tree_and_overrides_assignment(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
pinned_dirs:
  - Finance/Taxes
mappings:
  - glob: "*.invoice.pdf"
    target: Finance/Invoices
    also_relevant:
      - Documents
""".strip(),
        encoding="utf-8",
    )
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()
    file_info = FileInfo(
        absolute_path=tmp_path / "acme.invoice.pdf",
        relative_path=Path("acme.invoice.pdf"),
        parent_name="incoming",
        filename="acme.invoice.pdf",
        stem="acme.invoice",
        extension="pdf",
        size_bytes=3,
        mtime=mtime,
        ctime=mtime,
        file_hash="abc",
    )
    contexts = {file_info.absolute_path: ParsedContext("Invoice", "amount due", {})}

    result = PlannerPipeline(config).plan([file_info], contexts, root=tmp_path)

    assert result.tree["Finance"]["Taxes"] == {}
    assert result.tree["Finance"]["Invoices"] == {}
    assert result.assignments[0].primary_dir == ["Finance", "Invoices"]
    assert result.assignments[0].also_relevant == [["Documents"]]


def test_fake_llm_uses_meaningful_parent_folder_for_documents(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()
    file_info = FileInfo(
        absolute_path=tmp_path / "clients" / "acme" / "proposal.txt",
        relative_path=Path("clients/acme/proposal.txt"),
        parent_name="acme",
        filename="proposal.txt",
        stem="proposal",
        extension="txt",
        size_bytes=3,
        mtime=mtime,
        ctime=mtime,
        file_hash="abc",
    )
    contexts = {
        file_info.absolute_path: ParsedContext("Proposal", "Statement of work for renewal", {})
    }

    result = PlannerPipeline(config).plan([file_info], contexts)

    assert result.assignments[0].primary_dir == ["Documents", "acme"]
    assert result.assignments[0].summary.startswith("Preserves parent context 'acme'")


def test_fake_llm_routes_finance_documents_by_context(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()
    file_info = FileInfo(
        absolute_path=tmp_path / "receipts" / "april.invoice.pdf",
        relative_path=Path("receipts/april.invoice.pdf"),
        parent_name="receipts",
        filename="april.invoice.pdf",
        stem="april.invoice",
        extension="pdf",
        size_bytes=3,
        mtime=mtime,
        ctime=mtime,
        file_hash="abc",
    )
    contexts = {
        file_info.absolute_path: ParsedContext("Invoice", "payment due for April services", {})
    }

    result = PlannerPipeline(config).plan([file_info], contexts)

    assert result.assignments[0].primary_dir == ["Finance", "Invoices"]
    assert result.assignments[0].also_relevant == [["Documents"]]
    assert "Finance" in result.assignments[0].summary
    assert "Documents" in result.assignments[0].summary


def test_review_pass_prefers_stable_business_parent_over_workflow_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()

    def make_file(name: str) -> FileInfo:
        return FileInfo(
            absolute_path=tmp_path / "clients" / "acme" / "proposals" / name,
            relative_path=Path(f"clients/acme/proposals/{name}"),
            parent_name="proposals",
            filename=name,
            stem=name.rsplit(".", 1)[0],
            extension="txt",
            size_bytes=3,
            mtime=mtime,
            ctime=mtime,
            file_hash=name,
        )

    files = [make_file("renewal.txt"), make_file("pricing.txt")]
    contexts = {
        files[0].absolute_path: ParsedContext("Renewal proposal", "client renewal outline", {}),
        files[1].absolute_path: ParsedContext("Pricing proposal", "client pricing terms", {}),
    }

    result = PlannerPipeline(config).plan(files, contexts)

    assert {tuple(item.primary_dir) for item in result.assignments} == {("Documents", "acme")}
    assert "parent context 'acme'" in result.assignments[0].summary


def test_fake_llm_routes_screenshots_into_named_image_bucket(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig()
    mtime = datetime(2024, 5, 1).timestamp()
    file_info = FileInfo(
        absolute_path=tmp_path / "captures" / "Screenshot 2024-05-01.png",
        relative_path=Path("captures/Screenshot 2024-05-01.png"),
        parent_name="captures",
        filename="Screenshot 2024-05-01.png",
        stem="Screenshot 2024-05-01",
        extension="png",
        size_bytes=3,
        mtime=mtime,
        ctime=mtime,
        file_hash="abc",
    )
    contexts = {file_info.absolute_path: ParsedContext("Screenshot", "Settings page", {})}

    result = PlannerPipeline(config).plan([file_info], contexts)

    assert result.assignments[0].primary_dir == ["Images", "Screenshots"]


def test_brief_summary_includes_parent_folder_context():
    brief = FileBrief(
        path="inbox/client-a/proposal.txt",
        parent_name="client-a",
        parent_path="inbox/client-a",
        meaningful_parent_hint="client-a",
        filename="proposal.txt",
        extension="txt",
        mtime=datetime(2024, 5, 1).timestamp(),
        title="Proposal",
        head_text="Statement of work",
        duplicate_group_size=2,
    )

    assert "parent=client-a" in brief.summary
    assert "ancestry=inbox/client-a" in brief.summary
    assert "hint=client-a" in brief.summary
    assert "dupes=2" in brief.summary


def test_brief_prompt_text_calls_out_meaningful_parent_hint():
    brief = FileBrief(
        path="clients/acme/proposals/renewal.txt",
        parent_name="proposals",
        parent_path="clients/acme/proposals",
        meaningful_parent_hint="acme",
        filename="renewal.txt",
        extension="txt",
        mtime=datetime(2024, 5, 1).timestamp(),
        title="Renewal proposal",
        head_text="Statement of work for the next term.",
        duplicate_group_size=1,
    )

    assert "parent_folder=proposals" in brief.prompt_text
    assert "ancestor_folders=clients/acme/proposals" in brief.prompt_text
    assert "meaningful_parent_hint=acme" in brief.prompt_text
