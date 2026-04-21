from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["progress"] = "progress"
    command: str
    phase: str
    timestamp: str
    current: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ResultEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["result"] = "result"
    command: str
    timestamp: str
    payload: Any


class ProgressReporter:
    def __init__(self, command: str, mode: str = "off") -> None:
        self.command = command
        self.mode = mode

    @property
    def enabled(self) -> bool:
        return self.mode == "json"

    def emit(
        self,
        phase: str,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        event = ProgressEvent(
            command=self.command,
            phase=phase,
            timestamp=_timestamp(),
            current=current,
            total=total,
            message=message,
            data=data or {},
        )
        print(json.dumps(event.model_dump(mode="json"), ensure_ascii=False), flush=True)

    def print_result(self, payload: Any) -> None:
        if self.enabled:
            event = ResultEvent(command=self.command, timestamp=_timestamp(), payload=payload)
            print(json.dumps(event.model_dump(mode="json"), ensure_ascii=False), flush=True)
            return
        if isinstance(payload, str):
            print(payload)
            return
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()
