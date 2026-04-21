from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from autoshelf.config import AppConfig, load_raw_config
from autoshelf.config_migrations import LATEST_CONFIG_VERSION, list_migration_steps
from autoshelf.config_migrations.models import MigrationResult, MigrationStep


class ConfigInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool
    schema_version: int = Field(ge=0)
    latest_version: int = Field(ge=1)
    up_to_date: bool
    pending_migrations: list[MigrationStep] = Field(default_factory=list)


class ConfigMigrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool
    from_version: int = Field(ge=0)
    to_version: int = Field(ge=1)
    applied_migrations: list[MigrationStep] = Field(default_factory=list)
    updated: bool = False
    backup_path: str | None = None
    config: AppConfig | None = None


def inspect_config(path: Path | None = None) -> ConfigInspection:
    config_path = (path or AppConfig.default_path()).expanduser().resolve()
    if not config_path.exists():
        return ConfigInspection(
            path=str(config_path),
            exists=False,
            schema_version=0,
            latest_version=LATEST_CONFIG_VERSION,
            up_to_date=False,
            pending_migrations=list_migration_steps(),
        )
    migration = load_raw_config(config_path)
    return _inspection_from_result(config_path, migration)


def migrate_config_file(
    path: Path | None = None,
    *,
    write: bool = False,
    create_backup: bool = True,
) -> ConfigMigrationReport:
    config_path = (path or AppConfig.default_path()).expanduser().resolve()
    if not config_path.exists():
        return ConfigMigrationReport(
            path=str(config_path),
            exists=False,
            from_version=0,
            to_version=LATEST_CONFIG_VERSION,
            applied_migrations=[],
            updated=False,
            config=None,
        )

    migration = load_raw_config(config_path)
    applied = _steps_for_versions(migration.applied_versions)
    config = AppConfig.model_validate(migration.data)
    backup_path: Path | None = None
    updated = False

    if write and applied:
        if create_backup:
            backup_path = _backup_path(config_path, migration.from_version, migration.to_version)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(config_path, backup_path)
        config.save(config_path)
        updated = True
        logger.bind(component="config").info(
            "migrated config {} from v{} to v{}",
            config_path,
            migration.from_version,
            migration.to_version,
        )

    return ConfigMigrationReport(
        path=str(config_path),
        exists=True,
        from_version=migration.from_version,
        to_version=migration.to_version,
        applied_migrations=applied,
        updated=updated,
        backup_path=str(backup_path) if backup_path is not None else None,
        config=config,
    )


def _inspection_from_result(path: Path, migration: MigrationResult) -> ConfigInspection:
    pending = _steps_for_versions(
        [
            step.version
            for step in list_migration_steps()
            if step.version > migration.from_version
        ]
    )
    return ConfigInspection(
        path=str(path),
        exists=True,
        schema_version=migration.from_version,
        latest_version=LATEST_CONFIG_VERSION,
        up_to_date=not pending,
        pending_migrations=pending,
    )


def _steps_for_versions(versions: list[int]) -> list[MigrationStep]:
    selected = {version for version in versions}
    return [step for step in list_migration_steps() if step.version in selected]


def _backup_path(path: Path, from_version: int, to_version: int) -> Path:
    return path.with_name(f"{path.name}.bak.v{from_version}-to-v{to_version}")
