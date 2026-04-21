from __future__ import annotations

from autoshelf.planner.models import PlannerAssignment
from autoshelf.rules import (
    MappingRule,
    PlanningRules,
    apply_assignment_rules,
    filter_paths_by_rules,
    is_path_excluded,
    load_planning_rules,
    match_mapping_rule,
    merge_exclude_patterns,
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
exclude_globs:
  - "*.tmp"
  - Inbox/**
mappings:
  - glob: "*.invoice.pdf"
    priority: 5
    target: Finance/Invoices
    also_relevant:
      - Documents
""".strip(),
        encoding="utf-8",
    )

    rules = load_planning_rules(tmp_path)

    assert rules.pinned_dirs == [["Finance", "Taxes"], ["Documents", "Receipts"]]
    assert rules.exclude_globs == ["*.tmp", "Inbox/**"]
    assert rules.mappings[0].priority == 5
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


def test_assignment_rules_drop_excluded_paths():
    assignment = PlannerAssignment(
        path="Inbox/draft.txt",
        primary_dir=["Documents"],
        summary="draft",
        confidence=0.8,
    )

    adjusted = apply_assignment_rules(
        [assignment],
        PlanningRules(exclude_globs=["Inbox/**"]),
    )

    assert adjusted == []


def test_higher_priority_mapping_rule_wins():
    rules = PlanningRules(
        mappings=[
            MappingRule(glob="*.pdf", priority=1, target=["Documents", "General"]),
            MappingRule(glob="invoice-*.pdf", priority=10, target=["Finance", "Invoices"]),
        ]
    )

    matched = match_mapping_rule("incoming/invoice-april.pdf", rules)

    assert matched is not None
    assert matched.target == ["Finance", "Invoices"]


def test_filter_paths_by_rules_removes_matching_items():
    paths = ["Inbox/draft.txt", "Finance/invoice.pdf"]

    filtered = filter_paths_by_rules(
        paths,
        PlanningRules(exclude_globs=["Inbox/**"]),
        lambda item: item,
    )

    assert filtered == ["Finance/invoice.pdf"]


def test_merge_exclude_patterns_preserves_order_and_dedupes():
    merged = merge_exclude_patterns(
        [".git", "*.tmp"],
        PlanningRules(exclude_globs=["*.tmp", "Inbox/**"]),
    )

    assert merged == [".git", "*.tmp", "Inbox/**"]


def test_is_path_excluded_matches_relative_path_and_filename():
    assert is_path_excluded("Inbox/draft.txt", ["Inbox/**"])
    assert is_path_excluded("notes/draft.tmp", ["*.tmp"])
    assert not is_path_excluded("notes/final.txt", ["Inbox/**", "*.tmp"])


def test_render_rules_prompt_includes_constraints():
    rules = PlanningRules(
        pinned_dirs=[["Finance", "Taxes"]],
        exclude_globs=["Inbox/**"],
        mappings=[MappingRule(glob="*.pdf", priority=3, target=["Documents", "PDFs"])],
    )

    prompt = render_rules_prompt(rules)

    assert "keep folder available: Finance/Taxes" in prompt
    assert "ignore paths matching Inbox/**" in prompt
    assert "glob *.pdf [priority 3] must map to Documents/PDFs" in prompt
