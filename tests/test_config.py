from __future__ import annotations

from autoshelf.config import AppConfig
from autoshelf.config_migrations import LATEST_CONFIG_VERSION, migrate_config_data


def test_load_migrates_legacy_config_file(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
exclude = [".git", " build ", ".git"]
theme = "MIDNIGHT"
language_preference = "kr"
recent_roots = [" /tmp/downloads ", "/tmp/downloads", ""]
max_head_chars = "4096"
max_chunk_tokens = 0

[llm]
provider = "auto"
planning_model = "claude-sonnet-4-6"
prompt_cache_enabled = "off"
""".strip(),
        encoding="utf-8",
    )

    config = AppConfig.load(config_path)

    assert config.schema_version == LATEST_CONFIG_VERSION
    assert config.exclude == [".git", "build"]
    assert config.theme == "system"
    assert config.language_preference == "auto"
    assert config.recent_roots == ["/tmp/downloads"]
    assert config.max_head_chars == 4096
    assert config.max_chunk_tokens == 20_000
    assert config.llm.prompt_cache_enabled is False
    assert config.llm.retry_base_delay_ms == 500
    assert config.llm.retry_max_delay_ms == 8000
    assert config.llm.retry_jitter_ms == 250
    assert config.llm.circuit_breaker_threshold == 3
    assert config.llm.circuit_breaker_cooldown_seconds == 30


def test_migrate_config_data_is_idempotent():
    migrated = migrate_config_data(
        {
            "schema_version": LATEST_CONFIG_VERSION,
            "exclude": [".git"],
            "theme": "dark",
            "language_preference": "en",
            "recent_roots": ["/tmp/downloads"],
            "max_head_chars": 1024,
            "max_chunk_tokens": 8192,
            "llm": {
                "prompt_cache_enabled": True,
                "retry_base_delay_ms": 500,
                "retry_max_delay_ms": 8000,
                "retry_jitter_ms": 250,
                "circuit_breaker_threshold": 3,
                "circuit_breaker_cooldown_seconds": 30,
            },
        }
    )

    assert migrated.from_version == LATEST_CONFIG_VERSION
    assert migrated.to_version == LATEST_CONFIG_VERSION
    assert migrated.applied_versions == []
    assert migrated.data["theme"] == "dark"
