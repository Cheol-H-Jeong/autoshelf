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


def test_migrate_config_data_is_idempotent():
    migrated = migrate_config_data(
        {
            "schema_version": 1,
            "exclude": [".git"],
            "theme": "dark",
            "language_preference": "en",
            "recent_roots": ["/tmp/downloads"],
            "max_head_chars": 1024,
            "max_chunk_tokens": 8192,
            "llm": {"prompt_cache_enabled": True},
        }
    )

    assert migrated.from_version == 1
    assert migrated.to_version == 1
    assert migrated.applied_versions == []
    assert migrated.data["theme"] == "dark"
