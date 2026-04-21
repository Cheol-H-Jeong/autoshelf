from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CommandEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["command"] = "command"
    command: str
    status: Literal["started", "completed", "failed"]
    timestamp: str
    argv: list[str] = Field(default_factory=list)
    cwd: str = ""
    version: str = ""
    exit_code: int = Field(default=0, ge=0)
    data: dict[str, Any] = Field(default_factory=dict)


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


class ErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["error"] = "error"
    command: str
    timestamp: str
    error_type: str
    message: str
    exit_code: int = Field(default=1, ge=1)
    data: dict[str, Any] = Field(default_factory=dict)


class ProgressReporter:
    def __init__(
        self,
        command: str,
        mode: str = "off",
        *,
        argv: list[str] | None = None,
        cwd: str = "",
        version: str = "",
    ) -> None:
        self.command = command
        self.mode = mode
        self.argv = list(argv or [])
        self.cwd = cwd
        self.version = version

    @property
    def enabled(self) -> bool:
        return self.mode == "json"

    def emit_command(
        self,
        status: Literal["started", "completed", "failed"],
        *,
        exit_code: int = 0,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        event = CommandEvent(
            command=self.command,
            status=status,
            timestamp=_timestamp(),
            argv=self.argv,
            cwd=self.cwd,
            version=self.version,
            exit_code=exit_code,
            data=data or {},
        )
        self._print_json(event.model_dump(mode="json"))

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
        self._print_json(event.model_dump(mode="json"))

    def emit_error(
        self,
        error: BaseException,
        *,
        exit_code: int = 1,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        event = ErrorEvent(
            command=self.command,
            timestamp=_timestamp(),
            error_type=type(error).__name__,
            message=str(error),
            exit_code=exit_code,
            data=data or {},
        )
        self._print_json(event.model_dump(mode="json"))

    def print_result(self, payload: Any) -> None:
        if self.enabled:
            event = ResultEvent(command=self.command, timestamp=_timestamp(), payload=payload)
            self._print_json(event.model_dump(mode="json"))
            return
        if isinstance(payload, str):
            print(payload)
            return
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    @staticmethod
    def _print_json(payload: dict[str, Any]) -> None:
        print(json.dumps(payload, ensure_ascii=False), flush=True)


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()
