from __future__ import annotations

from autoshelf.planner.models import PlannerAssignment
from autoshelf.quarantine import (
    clear_quarantine_assignments,
    is_quarantined_assignment,
    replan_quarantine_assignments,
)


def test_replan_quarantine_assignments_uses_source_context() -> None:
    assignments = [
        PlannerAssignment(
            path="incoming/client-a/proposal.txt",
            primary_dir=[".autoshelf", "quarantine"],
            summary="Low-confidence draft kept in quarantine.",
            confidence=0.22,
            fallback=True,
        )
    ]

    replanned = replan_quarantine_assignments(assignments)

    assert replanned[0].primary_dir == ["Documents", "client-a"]
    assert replanned[0].confidence == 0.55
    assert replanned[0].fallback is False
    assert "source path context" in replanned[0].summary
    assert not is_quarantined_assignment(replanned[0])


def test_clear_quarantine_assignments_keeps_current_folder() -> None:
    assignments = [
        PlannerAssignment(
            path="incoming/client-a/proposal.txt",
            primary_dir=[".autoshelf", "quarantine"],
            summary="Low-confidence draft kept in quarantine.",
            confidence=0.22,
            fallback=True,
        )
    ]

    cleared = clear_quarantine_assignments(assignments)

    assert cleared[0].primary_dir == ["incoming", "client-a"]
    assert cleared[0].confidence == 0.4
    assert cleared[0].fallback is False
    assert "stays in its current folder incoming/client-a" in cleared[0].summary
    assert not is_quarantined_assignment(cleared[0])
