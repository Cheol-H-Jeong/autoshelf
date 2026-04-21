from __future__ import annotations

from pathlib import Path


def test_docs_and_templates_exist_with_expected_sections() -> None:
    root = Path(__file__).resolve().parents[1]
    expected_snippets = {
        "docs/ARCHITECTURE.md": ["Component Map", "Data Flow", "manifest.jsonl"],
        "CONTRIBUTING.md": ["Required Gates", "pytest -q", "pyright --outputjson"],
        ".github/ISSUE_TEMPLATE/bug_report.md": ["Steps To Reproduce", "Actual Result"],
        ".github/ISSUE_TEMPLATE/feature_request.md": [
            "Safety Considerations",
            "Alternatives Considered",
        ],
        ".github/PULL_REQUEST_TEMPLATE.md": ["Validation", "Risk Review"],
    }

    for relative_path, snippets in expected_snippets.items():
        content = (root / relative_path).read_text(encoding="utf-8")
        assert content.strip()
        for snippet in snippets:
            assert snippet in content
