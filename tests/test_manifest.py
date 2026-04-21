from __future__ import annotations

import json

from autoshelf.manifest import write_manifests
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
