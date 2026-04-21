from __future__ import annotations

from typing import Any

from autoshelf.config_migrations.helpers import (
    normalize_bool,
    normalize_choice,
    normalize_positive_int,
    normalize_string_list,
)
from autoshelf.config_migrations.models import MigrationStep


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    migrated["exclude"] = normalize_string_list(
        migrated.get("exclude"),
        default=[".git", "node_modules", "__pycache__", ".venv"],
    )
    migrated["recent_roots"] = normalize_string_list(migrated.get("recent_roots"), default=[])
    migrated["theme"] = normalize_choice(
        migrated.get("theme"),
        allowed={"system", "light", "dark"},
        fallback="system",
    )
    migrated["language_preference"] = normalize_choice(
        migrated.get("language_preference"),
        allowed={"auto", "ko", "en"},
        fallback="auto",
    )
    migrated["max_head_chars"] = normalize_positive_int(
        migrated.get("max_head_chars"),
        fallback=2000,
    )
    migrated["max_chunk_tokens"] = normalize_positive_int(
        migrated.get("max_chunk_tokens"),
        fallback=20_000,
    )
    llm = migrated.get("llm")
    llm_payload = dict(llm) if isinstance(llm, dict) else {}
    llm_payload["prompt_cache_enabled"] = normalize_bool(
        llm_payload.get("prompt_cache_enabled"),
        fallback=True,
    )
    migrated["llm"] = llm_payload
    return migrated


MIGRATION = (
    MigrationStep(
        version=1,
        name="normalize-legacy-fields",
        description="Normalize legacy autoshelf config fields",
    ),
    migrate,
)
