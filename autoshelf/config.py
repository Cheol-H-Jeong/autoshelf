from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autoshelf.config_migrations import LATEST_CONFIG_VERSION, migrate_config_data
from autoshelf.config_migrations.models import MigrationResult
from autoshelf.paths import config_dir


class LLMSettings(BaseModel):
    """LLM provider and model settings."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "auto"
    classification_model: str = "claude-haiku-4-5"
    planning_model: str = "claude-sonnet-4-6"
    review_model: str = "claude-sonnet-4-6"
    requests_per_second: int = Field(default=2, ge=1)
    concurrency: int = Field(default=3, ge=1)
    max_retries: int = Field(default=4, ge=0)
    prompt_cache_enabled: bool = True
    retry_base_delay_ms: int = Field(default=500, ge=1)
    retry_max_delay_ms: int = Field(default=8000, ge=1)
    retry_jitter_ms: int = Field(default=250, ge=0)
    circuit_breaker_threshold: int = Field(default=3, ge=1)
    circuit_breaker_cooldown_seconds: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def _normalize_retry_bounds(self) -> LLMSettings:
        if self.retry_max_delay_ms < self.retry_base_delay_ms:
            self.retry_max_delay_ms = self.retry_base_delay_ms
        return self


class AppConfig(BaseModel):
    """Autoshelf configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=LATEST_CONFIG_VERSION, ge=1)
    exclude: list[str] = Field(
        default_factory=lambda: [".git", "node_modules", "__pycache__", ".venv"]
    )
    include_dotfiles: bool = False
    max_head_chars: int = 2000
    max_chunk_tokens: int = 20_000
    dry_run_default: bool = True
    theme: str = "system"
    language_preference: str = "auto"
    recent_roots: list[str] = Field(default_factory=list)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @classmethod
    def default_path(cls) -> Path:
        return config_dir() / "config.toml"

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        config_path = path or cls.default_path()
        if not config_path.exists():
            return cls()
        migration = load_raw_config(config_path)
        return cls.model_validate(migration.data)

    def save(self, path: Path | None = None) -> Path:
        config_path = path or self.default_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        write_config_text(config_path, _to_toml(self.model_dump()))
        return config_path


def load_raw_config(path: Path) -> MigrationResult:
    return migrate_config_data(parse_toml(path))


def parse_toml(path: Path) -> dict[str, object]:
    import tomllib

    with path.open("rb") as handle:
        return tomllib.load(handle)


def write_config_text(path: Path, content: str) -> None:
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _to_toml(data: dict[str, object], prefix: str = "") -> str:
    lines: list[str] = []
    scalars: list[tuple[str, object]] = []
    nested: list[tuple[str, dict[str, object]]] = []
    for key, value in data.items():
        if isinstance(value, dict):
            nested.append((key, value))
        else:
            scalars.append((key, value))
    if prefix:
        lines.append(f"[{prefix}]")
    for key, value in scalars:
        lines.append(f"{key} = {_format_toml_value(value)}")
    if scalars and nested:
        lines.append("")
    for index, (key, value) in enumerate(nested):
        section = f"{prefix}.{key}" if prefix else key
        lines.append(_to_toml(value, section).rstrip())
        if index != len(nested) - 1:
            lines.append("")
    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
