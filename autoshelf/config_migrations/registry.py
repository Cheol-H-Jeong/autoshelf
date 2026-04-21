from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from autoshelf.config_migrations.models import MigrationResult, MigrationStep
from autoshelf.config_migrations.versions import MIGRATIONS

LATEST_CONFIG_VERSION = 2

MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]
_MIGRATIONS: list[tuple[MigrationStep, MigrationFunc]] = sorted(
    MIGRATIONS,
    key=lambda item: item[0].version,
)


def list_migration_steps() -> list[MigrationStep]:
    return [step.model_copy(deep=True) for step, _ in _MIGRATIONS]


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
            ", ".join(
                f"v{step.version}:{step.name}"
                for step, _ in _MIGRATIONS
                if step.version in applied_versions
            ),
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
