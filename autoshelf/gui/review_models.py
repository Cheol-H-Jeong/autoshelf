from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from autoshelf.planner.models import PlannerAssignment


class PreviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_parts: list[str]
    target_parts: list[str]
    confidence: float
    rationale: str = ""
    also_relevant: list[list[str]] = Field(default_factory=list)

    @property
    def filename(self) -> str:
        return Path(self.source_path).name

    @property
    def action(self) -> str:
        if self.source_parts == self.target_parts:
            return "kept"
        if self.source_folder:
            return "moved"
        return "placed"

    @property
    def target_folder(self) -> str:
        return "/".join(self.target_parts[:-1])

    @property
    def source_folder(self) -> str:
        return "/".join(self.source_parts[:-1])

    @property
    def action_summary(self) -> str:
        if self.action == "kept":
            return f"Keep {self.filename} in {self.target_folder or '.'}"
        if self.action == "moved":
            return (
                f"Move {self.filename} from {self.source_folder or '.'} "
                f"to {self.target_folder or '.'}"
            )
        return f"Place {self.filename} into {self.target_folder or '.'}"

    @property
    def destination_path(self) -> str:
        return "/".join(self.target_parts)

    @property
    def source_display(self) -> str:
        return self.source_path or self.filename


def summarize_actions(items: list[PreviewItem]) -> dict[str, int]:
    counts = {"kept": 0, "moved": 0, "placed": 0}
    for item in items:
        counts[item.action] += 1
    return counts


def build_preview_items(assignments: list[PlannerAssignment]) -> list[PreviewItem]:
    items: list[PreviewItem] = []
    for assignment in assignments:
        source_parts = _source_parts(assignment.path)
        target_parts = [*assignment.primary_dir, Path(assignment.path).name]
        items.append(
            PreviewItem(
                source_path=assignment.path,
                source_parts=source_parts,
                target_parts=target_parts,
                confidence=assignment.confidence,
                rationale=assignment.summary,
                also_relevant=assignment.also_relevant,
            )
        )
    return items


def _source_parts(path: str) -> list[str]:
    parts = [part for part in Path(path).parts if part not in {".", ""}]
    return parts or [Path(path).name]
