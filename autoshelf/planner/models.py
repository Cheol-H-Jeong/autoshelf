from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FileBriefModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    parent_name: str = ""
    parent_path: str = ""
    filename: str
    extension: str
    mtime: float
    title: str = ""
    head_text: str = ""
    duplicate_group_size: int = Field(default=1, ge=1)

    @property
    def summary(self) -> str:
        excerpt = self.head_text.replace("\n", " ").strip()[:180]
        parent = self.parent_name.strip() or "-"
        ancestry = self.parent_path.strip() or "-"
        return (
            f"{self.filename} | parent={parent} | ancestry={ancestry} | ext={self.extension} | "
            f"dupes={self.duplicate_group_size} | mtime={int(self.mtime)} | title={self.title} | "
            f"excerpt={excerpt}"
        )[:300]


class PlannerAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    primary_dir: list[str]
    also_relevant: list[list[str]] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    fallback: bool = False

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        return min(1.0, max(0.0, value))


class PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree: dict[str, Any] = Field(default_factory=dict)
    assignments: list[PlannerAssignment] = Field(default_factory=list)
    unsure_paths: list[str] = Field(default_factory=list)


class PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processed_chunks: int = 0
    tree: dict[str, Any] = Field(default_factory=dict)
    assignments: list[PlannerAssignment] = Field(default_factory=list)
    unsure_paths: list[str] = Field(default_factory=list)


class PlannerUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    fallback_chunks: int = 0

    def add_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_creation_input_tokens += cache_creation_input_tokens
        self.cache_read_input_tokens += cache_read_input_tokens
