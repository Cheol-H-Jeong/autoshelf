from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_demo_fixture_generator_creates_expected_corpus(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path / "demo"

    completed = subprocess.run(
        [sys.executable, "examples/fixtures/generate_demo.py", str(destination)],
        capture_output=True,
        text=True,
        cwd=root,
        check=True,
    )

    generated_root = Path(completed.stdout.strip())
    assert generated_root == destination.resolve()
    manifest = json.loads((generated_root / "fixture-manifest.json").read_text(encoding="utf-8"))
    assert manifest["fixture"] == "customer-eval"
    assert manifest["file_count"] == 7
    assert (generated_root / ".autoshelfrc.yaml").exists()
    assert (generated_root / "receipts" / "2026-03-tax.invoice.pdf").exists()
    assert (generated_root / "Archive" / "duplicate-budget-copy.csv").exists()


def test_examples_readme_documents_eval_loop():
    root = Path(__file__).resolve().parents[1]
    content = (root / "examples" / "README.md").read_text(encoding="utf-8")

    assert "generate_demo.py" in content
    assert "python -m autoshelf preview" in content
    assert "fixture-manifest.json" in content
