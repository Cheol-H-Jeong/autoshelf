from __future__ import annotations

from pathlib import Path


def test_docs_and_templates_exist_with_expected_sections() -> None:
    root = Path(__file__).resolve().parents[1]
    expected_snippets = {
        "docs/ARCHITECTURE.md": ["Component Map", "Data Flow", "manifest.jsonl"],
        "docs/USER_GUIDE.md": ["Recommended Operator Flow", "Examples", "generate_demo.py"],
        "examples/README.md": ["generate_demo.py", "fixture-manifest.json"],
        "packaging/linux/autoshelf.1": [".TH AUTOSHELF 1", ".SH COMMANDS", ".SS apply"],
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


def test_readme_documents_verified_packaging_workflow() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "python packaging/build.py --verify-install --verify-wheel" in readme
    assert "python packaging/generate_manpage.py" in readme
    assert "bundle-manifest.json" in readme
    assert "examples/fixtures/generate_demo.py" in readme
    assert "pipx install dist/autoshelf-*.whl" in readme
