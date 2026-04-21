from __future__ import annotations

from autoshelf.planner.models import PlannerAssignment
from autoshelf.rules import (
    MappingRule,
    PlanningRules,
    apply_assignment_rules,
    load_planning_rules,
    merge_rule_paths,
    render_rules_prompt,
)


def test_load_rules_file_normalizes_paths(tmp_path):
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
pinned_dirs:
  - Finance/Taxes
  - [Documents, Receipts]
mappings:
  - glob: "*.invoice.pdf"
    target: Finance/Invoices
    also_relevant:
      - Documents
""".strip(),
        encoding="utf-8",
    )

    rules = load_planning_rules(tmp_path)

    assert rules.pinned_dirs == [["Finance", "Taxes"], ["Documents", "Receipts"]]
    assert rules.mappings[0].target == ["Finance", "Invoices"]
    assert rules.mappings[0].also_relevant == [["Documents"]]


def test_merge_rule_paths_seeds_tree():
    rules = PlanningRules(
        pinned_dirs=[["Finance", "Taxes"]],
        mappings=[MappingRule(glob="*.pdf", target=["Documents", "PDFs"])],
    )

    tree = merge_rule_paths({"Documents": {"Existing": {}}}, rules)

    assert tree["Finance"] == {"Taxes": {}}
    assert tree["Documents"]["PDFs"] == {}
    assert tree["Documents"]["Existing"] == {}


def test_assignment_rules_override_matching_paths():
    assignment = PlannerAssignment(
        path="incoming/acme.invoice.pdf",
        primary_dir=["Documents"],
        also_relevant=[["Archive"]],
        summary="invoice",
        confidence=0.4,
    )
    rules = PlanningRules(
        mappings=[
            MappingRule(
                glob="*.invoice.pdf",
                target=["Finance", "Invoices"],
                also_relevant=[["Documents"]],
            )
        ]
    )

    adjusted = apply_assignment_rules([assignment], rules)

    assert adjusted[0].primary_dir == ["Finance", "Invoices"]
    assert adjusted[0].also_relevant == [["Documents"]]
    assert adjusted[0].confidence == 1.0
    assert adjusted[0].summary.startswith("[rule:*.invoice.pdf]")


def test_render_rules_prompt_includes_constraints():
    rules = PlanningRules(
        pinned_dirs=[["Finance", "Taxes"]],
        mappings=[MappingRule(glob="*.pdf", target=["Documents", "PDFs"])],
    )

    prompt = render_rules_prompt(rules)

    assert "keep folder available: Finance/Taxes" in prompt
    assert "glob *.pdf must map to Documents/PDFs" in prompt
