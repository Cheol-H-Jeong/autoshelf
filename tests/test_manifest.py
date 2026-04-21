from __future__ import annotations

import json

from autoshelf.manifest import GENESIS_HASH, load_manifest_entries, write_manifests
from autoshelf.planner.models import PlannerAssignment


def test_manifest_contains_fallback_marker(tmp_path):
    assignment = PlannerAssignment(
        path="draft.txt",
        primary_dir=["Documents"],
        also_relevant=[],
        summary="draft",
        fallback=True,
    )
    write_manifests(tmp_path, {"Documents": {}}, [assignment])
    assert "fallback" in (tmp_path / "FILE_INDEX.md").read_text(encoding="utf-8")


def test_manifest_jsonl_contains_assignment_data(tmp_path):
    (tmp_path / "draft.txt").write_text("draft", encoding="utf-8")
    assignment = PlannerAssignment(
        path="draft.txt",
        primary_dir=["Documents"],
        also_relevant=[["Archive"]],
        summary="draft",
        confidence=0.6,
    )
    write_manifests(tmp_path, {"Documents": {}}, [assignment])
    line = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["target"] == "Documents/draft.txt"
    assert payload["also_relevant"] == ["Archive"]


def test_manifest_jsonl_contains_hash_chain_and_content_hash(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("draft", encoding="utf-8")
    assignment = PlannerAssignment(
        path="draft.txt",
        primary_dir=["Documents"],
        summary="draft",
    )
    write_manifests(tmp_path, {"Documents": {}}, [assignment])
    entries = load_manifest_entries(tmp_path / "manifest.jsonl")
    assert entries[0].prev_hash == GENESIS_HASH
    assert entries[0].content_hash
    assert entries[0].entry_hash == entries[0].computed_entry_hash()
