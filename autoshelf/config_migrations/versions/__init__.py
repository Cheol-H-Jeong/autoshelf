from __future__ import annotations

from autoshelf.config_migrations.versions.v1_normalize_legacy_fields import (
    MIGRATION as V1_MIGRATION,
)
from autoshelf.config_migrations.versions.v2_add_planner_reliability_defaults import (
    MIGRATION as V2_MIGRATION,
)

MIGRATIONS = [V1_MIGRATION, V2_MIGRATION]

__all__ = ["MIGRATIONS"]
