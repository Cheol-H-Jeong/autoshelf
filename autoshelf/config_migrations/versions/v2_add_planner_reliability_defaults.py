from __future__ import annotations

from typing import Any

from autoshelf.config_migrations.helpers import (
    normalize_non_negative_int,
    normalize_positive_int,
)
from autoshelf.config_migrations.models import MigrationStep


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    llm = migrated.get("llm")
    llm_payload = dict(llm) if isinstance(llm, dict) else {}
    llm_payload["retry_base_delay_ms"] = normalize_positive_int(
        llm_payload.get("retry_base_delay_ms"),
        fallback=500,
    )
    llm_payload["retry_max_delay_ms"] = normalize_positive_int(
        llm_payload.get("retry_max_delay_ms"),
        fallback=8_000,
    )
    llm_payload["retry_jitter_ms"] = normalize_non_negative_int(
        llm_payload.get("retry_jitter_ms"),
        fallback=250,
    )
    llm_payload["circuit_breaker_threshold"] = normalize_positive_int(
        llm_payload.get("circuit_breaker_threshold"),
        fallback=3,
    )
    llm_payload["circuit_breaker_cooldown_seconds"] = normalize_positive_int(
        llm_payload.get("circuit_breaker_cooldown_seconds"),
        fallback=30,
    )
    if llm_payload["retry_max_delay_ms"] < llm_payload["retry_base_delay_ms"]:
        llm_payload["retry_max_delay_ms"] = llm_payload["retry_base_delay_ms"]
    migrated["llm"] = llm_payload
    return migrated


MIGRATION = (
    MigrationStep(
        version=2,
        name="add-planner-reliability-defaults",
        description="Add planner reliability defaults for retries and circuit breaking",
    ),
    migrate,
)
