from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MigrationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    description: str


class MigrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_version: int = Field(ge=0)
    to_version: int = Field(ge=1)
    applied_versions: list[int] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
