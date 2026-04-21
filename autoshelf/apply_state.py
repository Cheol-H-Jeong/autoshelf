from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autoshelf.planner.models import PlannerAssignment
from autoshelf.scanner import _hash_file

RunEntryStatus = Literal["planned", "running", "applied", "skipped"]
RunStatus = Literal["planned", "running", "interrupted", "completed"]
CopyStage = Literal["pending", "staged", "target-written"]


class RunPlanEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    primary_dir: list[str]
    also_relevant: list[list[str]] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    fallback: bool = False
    status: RunEntryStatus = "planned"
    source_hash: str = ""
    target_path: str = ""
    copy_stage: CopyStage = "pending"
    staged_path: str = ""


class RunState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: RunStatus
    current_path: str = ""
    started_at: str
    updated_at: str
    completed_entries: int = 0
    total_entries: int = 0
    last_error: str = ""


def write_run_plan(root: Path, assignments: list[PlannerAssignment], run_id: str) -> Path:
    plan_path = run_plan_path(root, run_id)
    if plan_path.exists():
        return plan_path
    entries = [
        RunPlanEntry(
            path=assignment.path,
            primary_dir=assignment.primary_dir,
            also_relevant=assignment.also_relevant,
            summary=assignment.summary,
            confidence=assignment.confidence,
            fallback=assignment.fallback,
            source_hash=_source_hash(root, assignment),
        )
        for assignment in assignments
    ]
    save_run_plan_entries(plan_path, entries)
    return plan_path


def load_run_plan_entries(plan_path: Path) -> list[RunPlanEntry]:
    if not plan_path.exists():
        return []
    return [
        RunPlanEntry.model_validate_json(line)
        for line in plan_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def save_run_plan_entries(plan_path: Path, entries: list[RunPlanEntry]) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) for entry in entries
    )
    temp_path = plan_path.with_suffix(".tmp")
    temp_path.write_text(payload + ("\n" if entries else ""), encoding="utf-8")
    temp_path.replace(plan_path)


def update_run_entry(
    plan_path: Path,
    source_path: str,
    *,
    status: RunEntryStatus | None = None,
    target_path: str | None = None,
    copy_stage: CopyStage | None = None,
    staged_path: str | None = None,
) -> RunPlanEntry | None:
    entries = load_run_plan_entries(plan_path)
    updated: RunPlanEntry | None = None
    for entry in entries:
        if entry.path != source_path:
            continue
        if status is not None:
            entry.status = status
        if target_path is not None:
            entry.target_path = target_path
        if copy_stage is not None:
            entry.copy_stage = copy_stage
        if staged_path is not None:
            entry.staged_path = staged_path
        updated = entry
        break
    save_run_plan_entries(plan_path, entries)
    return updated


def load_run_state(state_path: Path) -> RunState | None:
    if not state_path.exists():
        return None
    return RunState.model_validate_json(state_path.read_text(encoding="utf-8"))


def write_run_state(
    state_path: Path,
    *,
    run_id: str,
    status: RunStatus,
    current_path: str = "",
    completed_entries: int = 0,
    total_entries: int = 0,
    last_error: str = "",
) -> RunState:
    existing = load_run_state(state_path)
    state = RunState(
        run_id=run_id,
        status=status,
        current_path=current_path,
        started_at=existing.started_at if existing is not None else _timestamp(),
        updated_at=_timestamp(),
        completed_entries=completed_entries,
        total_entries=total_entries,
        last_error=last_error,
    )
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = state_path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(state_path)
    return state


def run_plan_path(root: Path, run_id: str) -> Path:
    return root / ".autoshelf" / "runs" / f"{run_id}.plan.jsonl"


def run_state_path(root: Path, run_id: str) -> Path:
    return root / ".autoshelf" / "runs" / f"{run_id}.state.json"


def run_staging_dir(root: Path, run_id: str) -> Path:
    return root / ".autoshelf" / "staging" / run_id


def load_all_run_states(root: Path) -> list[RunState]:
    runs_dir = root / ".autoshelf" / "runs"
    if not runs_dir.exists():
        return []
    states: list[RunState] = []
    for state_file in sorted(runs_dir.glob("*.state.json")):
        state = load_run_state(state_file)
        if state is not None:
            states.append(state)
    return states


def load_run_plan(plan_path: Path) -> list[dict[str, object]]:
    return [entry.model_dump(mode="json") for entry in load_run_plan_entries(plan_path)]


def _source_hash(root: Path, assignment: PlannerAssignment) -> str:
    source = root / assignment.path
    return _hash_file(source) if source.exists() else ""


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()
