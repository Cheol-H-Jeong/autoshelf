from __future__ import annotations

from datetime import datetime
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.near_duplicates import detect_near_duplicates
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.scanner import FileInfo


def test_detect_near_duplicates_groups_similar_variants(tmp_path):
    config = AppConfig(
        near_duplicate_threshold=0.55,
        near_duplicate_shingle_size=2,
        near_duplicate_min_token_count=6,
    )
    first = _file_info(tmp_path, "inbox/invoice-v1.txt", "hash-a")
    second = _file_info(tmp_path, "archive/invoice-v2.txt", "hash-b")
    third = _file_info(tmp_path, "notes/meeting.txt", "hash-c")
    contexts = {
        first.absolute_path: ParsedContext(
            "April invoice",
            "Acme April invoice payment due for design retainer and support services",
            {},
        ),
        second.absolute_path: ParsedContext(
            "April invoice rev 2",
            "Acme April invoice payment due for design retainer and support services updated",
            {},
        ),
        third.absolute_path: ParsedContext(
            "Team notes",
            "Weekly hiring sync and project kickoff notes for the design team",
            {},
        ),
    }

    detected = detect_near_duplicates([first, second, third], contexts, config)

    assert detected["inbox/invoice-v1.txt"].group_size == 2
    assert detected["archive/invoice-v2.txt"].group_size == 2
    assert detected["inbox/invoice-v1.txt"].group_id == detected["archive/invoice-v2.txt"].group_id
    assert detected["inbox/invoice-v1.txt"].strongest_similarity >= 0.55
    assert "notes/meeting.txt" not in detected


def test_fake_llm_uses_near_duplicate_anchor_for_weak_variant(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig(
        near_duplicate_threshold=0.5,
        near_duplicate_shingle_size=2,
        near_duplicate_min_token_count=4,
    )
    strong = _file_info(tmp_path, "receipts/april-invoice.txt", "hash-a")
    weak = _file_info(tmp_path, "misc/april-invoice-copy.txt", "hash-b")
    contexts = {
        strong.absolute_path: ParsedContext(
            "April invoice",
            "Invoice payment due for April consulting retainer",
            {},
        ),
        weak.absolute_path: ParsedContext(
            "",
            "Invoice payment due for April consulting",
            {},
        ),
    }

    result = PlannerPipeline(config).plan([strong, weak], contexts)
    assignments = {item.path: item for item in result.assignments}

    assert assignments["receipts/april-invoice.txt"].primary_dir == ["Finance", "Invoices"]
    assert assignments["misc/april-invoice-copy.txt"].primary_dir == ["Finance", "Invoices"]
    assert "close variants" in assignments["misc/april-invoice-copy.txt"].summary


def _file_info(root: Path, relative_path: str, file_hash: str) -> FileInfo:
    timestamp = datetime(2024, 5, 1).timestamp()
    path = Path(relative_path)
    return FileInfo(
        absolute_path=root / path,
        relative_path=path,
        parent_name=path.parent.name,
        filename=path.name,
        stem=path.stem,
        extension=path.suffix.lstrip("."),
        size_bytes=10,
        mtime=timestamp,
        ctime=timestamp,
        file_hash=file_hash,
    )
