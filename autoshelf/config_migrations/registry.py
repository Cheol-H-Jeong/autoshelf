from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from autoshelf.config_migrations.models import MigrationResult, MigrationStep

LATEST_CONFIG_VERSION = 2

MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: list[tuple[MigrationStep, MigrationFunc]] = []


def _register(version: int, description: str):
    def decorator(func: MigrationFunc) -> MigrationFunc:
        _MIGRATIONS.append((MigrationStep(version=version, description=description), func))
        _MIGRATIONS.sort(key=lambda item: item[0].version)
        return func

    return decorator


def migrate_config_data(raw: dict[str, object]) -> MigrationResult:
    data: dict[str, Any] = dict(raw)
    from_version = _coerce_version(data.get("schema_version"))
    applied_versions: list[int] = []
    for step, migration in _MIGRATIONS:
        if step.version <= from_version:
            continue
        data = migration(data)
        data["schema_version"] = step.version
        applied_versions.append(step.version)
    result = MigrationResult(
        from_version=from_version,
        to_version=int(data.get("schema_version", LATEST_CONFIG_VERSION)),
        applied_versions=applied_versions,
        data=data,
    )
    if applied_versions:
        logger.info(
            "Migrated config schema from v{} to v{} via {}",
            from_version,
            result.to_version,
            ", ".join(f"v{version}" for version in applied_versions),
        )
    return result


def _coerce_version(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str) and value.isdigit():
        return max(0, int(value))
    return 0


@_register(1, "Normalize legacy autoshelf config fields")
def _migrate_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    migrated["exclude"] = _normalize_string_list(
        migrated.get("exclude"),
        default=[".git", "node_modules", "__pycache__", ".venv"],
    )
    migrated["recent_roots"] = _normalize_string_list(migrated.get("recent_roots"), default=[])
    migrated["theme"] = _normalize_choice(
        migrated.get("theme"),
        allowed={"system", "light", "dark"},
        fallback="system",
    )
    migrated["language_preference"] = _normalize_choice(
        migrated.get("language_preference"),
        allowed={"auto", "ko", "en"},
        fallback="auto",
    )
    migrated["max_head_chars"] = _normalize_positive_int(
        migrated.get("max_head_chars"),
        fallback=2000,
    )
    migrated["max_chunk_tokens"] = _normalize_positive_int(
        migrated.get("max_chunk_tokens"),
        fallback=20_000,
    )
    llm = migrated.get("llm")
    llm_payload = dict(llm) if isinstance(llm, dict) else {}
    llm_payload["prompt_cache_enabled"] = _normalize_bool(
        llm_payload.get("prompt_cache_enabled"),
        fallback=True,
    )
    migrated["llm"] = llm_payload
    return migrated


@_register(2, "Add planner reliability defaults for retries and circuit breaking")
def _migrate_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    llm = migrated.get("llm")
    llm_payload = dict(llm) if isinstance(llm, dict) else {}
    llm_payload["retry_base_delay_ms"] = _normalize_positive_int(
        llm_payload.get("retry_base_delay_ms"),
        fallback=500,
    )
    llm_payload["retry_max_delay_ms"] = _normalize_positive_int(
        llm_payload.get("retry_max_delay_ms"),
        fallback=8_000,
    )
    llm_payload["retry_jitter_ms"] = _normalize_non_negative_int(
        llm_payload.get("retry_jitter_ms"),
        fallback=250,
    )
    llm_payload["circuit_breaker_threshold"] = _normalize_positive_int(
        llm_payload.get("circuit_breaker_threshold"),
        fallback=3,
    )
    llm_payload["circuit_breaker_cooldown_seconds"] = _normalize_positive_int(
        llm_payload.get("circuit_breaker_cooldown_seconds"),
        fallback=30,
    )
    if llm_payload["retry_max_delay_ms"] < llm_payload["retry_base_delay_ms"]:
        llm_payload["retry_max_delay_ms"] = llm_payload["retry_base_delay_ms"]
    migrated["llm"] = llm_payload
    return migrated


def _normalize_string_list(value: object, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    seen: set[str] = set()
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        items.append(text)
        seen.add(text)
    return items or list(default)


def _normalize_choice(value: object, allowed: set[str], fallback: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in allowed:
            return normalized
    return fallback


def _normalize_positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value if value > 0 else fallback
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    return fallback


def _normalize_non_negative_int(value: object, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value if value >= 0 else fallback
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed >= 0 else fallback
    return fallback


def _normalize_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return fallback
