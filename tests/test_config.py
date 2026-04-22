from __future__ import annotations

from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.config_admin import inspect_config, migrate_config_file
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
planning_model = "legacy-remote-model"
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
    assert config.max_chunk_tokens == 1024
    assert config.llm.prompt_cache_enabled is False
    assert config.llm.retry_base_delay_ms == 500
    assert config.llm.retry_max_delay_ms == 8000
    assert config.llm.retry_jitter_ms == 250
    assert config.llm.circuit_breaker_threshold == 3
    assert config.llm.circuit_breaker_cooldown_seconds == 30
    assert config.llm.model_id == "legacy-remote-model"
    assert config.llm.provider == "auto"


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
                "prompt_cache_enabled": False,
                "retry_base_delay_ms": 500,
                "retry_max_delay_ms": 8000,
                "retry_jitter_ms": 250,
                "circuit_breaker_threshold": 3,
                "circuit_breaker_cooldown_seconds": 30,
                "model_id": "qwen3-1.7b-q4",
                "context_window": 4096,
                "n_batch": 256,
                "max_completion_tokens": 1024,
            },
        }
    )

    assert migrated.from_version == LATEST_CONFIG_VERSION
    assert migrated.to_version == LATEST_CONFIG_VERSION
    assert migrated.applied_versions == []
    assert migrated.data["theme"] == "dark"


def test_inspect_config_reports_pending_migrations(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('theme = "dark"\n', encoding="utf-8")

    report = inspect_config(config_path)

    assert report.exists is True
    assert report.schema_version == 0
    assert report.latest_version == LATEST_CONFIG_VERSION
    assert [step.version for step in report.pending_migrations] == [1, 2, 3]
    assert report.up_to_date is False


def test_migrate_config_file_writes_backup_and_upgraded_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
theme = "MIDNIGHT"

[llm]
prompt_cache_enabled = "off"
""".strip(),
        encoding="utf-8",
    )

    report = migrate_config_file(config_path, write=True)

    assert report.updated is True
    assert report.from_version == 0
    assert report.to_version == LATEST_CONFIG_VERSION
    assert [step.version for step in report.applied_migrations] == [1, 2, 3]
    assert report.backup_path is not None
    backup_path = Path(report.backup_path)
    assert backup_path.exists()
    assert 'theme = "MIDNIGHT"' in backup_path.read_text(encoding="utf-8")

    persisted = AppConfig.load(config_path)
    assert persisted.schema_version == LATEST_CONFIG_VERSION
    assert persisted.theme == "system"
    assert persisted.llm.prompt_cache_enabled is False
    assert persisted.llm.model_id == "qwen3-1.7b-q4"
