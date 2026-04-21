from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field


class DemoFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    relative_path: str
    content: str


class DemoFixture(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    files: tuple[DemoFile, ...] = Field(default_factory=tuple)
    rules_file: str = ""


DEMO_FIXTURE = DemoFixture(
    name="customer-eval",
    description=(
        "Mixed business, study, screenshot, and duplicate-content inbox for local evaluation."
    ),
    files=(
        DemoFile(
            relative_path="Inbox/acme-renewal-proposal.txt",
            content="Acme renewal proposal\nStatement of work for Q3 renewal and pricing.",
        ),
        DemoFile(
            relative_path="receipts/2026-03-tax.invoice.pdf",
            content="Invoice\nTax invoice for March advisory services.",
        ),
        DemoFile(
            relative_path="clients/bluebird/meeting-notes.md",
            content="# Meeting notes\nBluebird contract renewal risks and action items.",
        ),
        DemoFile(
            relative_path="Screenshots/Screenshot 2026-04-20 at 09.00.00.png",
            content="fake-png-binary",
        ),
        DemoFile(
            relative_path="Inbox/duplicate-budget.csv",
            content="quarter,amount\nQ1,12000\nQ2,13500\n",
        ),
        DemoFile(
            relative_path="Archive/duplicate-budget-copy.csv",
            content="quarter,amount\nQ1,12000\nQ2,13500\n",
        ),
        DemoFile(
            relative_path="Study/week-02-transformer-notes.md",
            content="# Transformer notes\nAttention layers, residuals, and feed-forward blocks.",
        ),
    ),
    rules_file=(
        "version: 1\n"
        "pinned_dirs:\n"
        "  - Finance/Taxes\n"
        "  - Clients/Archive\n"
        "exclude_globs:\n"
        "  - \"*.tmp\"\n"
        "mappings:\n"
        "  - glob: \"*.invoice.pdf\"\n"
        "    priority: 10\n"
        "    target: Finance/Invoices\n"
        "    also_relevant:\n"
        "      - Documents\n"
    ),
)


def generate_demo_fixture(destination: Path) -> Path:
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for demo_file in DEMO_FIXTURE.files:
        file_path = root / demo_file.relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(demo_file.content, encoding="utf-8")
    (root / ".autoshelfrc.yaml").write_text(DEMO_FIXTURE.rules_file, encoding="utf-8")
    metadata = {
        "fixture": DEMO_FIXTURE.name,
        "description": DEMO_FIXTURE.description,
        "file_count": len(DEMO_FIXTURE.files),
        "rules_file": ".autoshelfrc.yaml",
    }
    (root / "fixture-manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.bind(component="examples").info("generated demo fixture at {}", root)
    return root


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_demo",
        description="Generate a deterministic autoshelf evaluation fixture",
    )
    parser.add_argument("destination")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    root = generate_demo_fixture(Path(args.destination))
    print(root)


if __name__ == "__main__":
    main()
