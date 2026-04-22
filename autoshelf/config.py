from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from autoshelf.config_migrations import LATEST_CONFIG_VERSION, migrate_config_data
from autoshelf.config_migrations.models import MigrationResult
from autoshelf.llm.model_registry import DEFAULT_MODEL_ID
from autoshelf.llm.policy import assert_loopback_url
from autoshelf.llm.system_probe import probe_hardware
from autoshelf.paths import config_dir


class LLMSettings(BaseModel):
    """LLM provider and model settings."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "auto"
    model_id: str = DEFAULT_MODEL_ID
    model_path: str = ""
    local_http_url: str = ""
    context_window: int = Field(default=4096, ge=2048, le=8192)
    n_batch: int = Field(default=256, ge=32, le=2048)
    max_completion_tokens: int = Field(default=1024, ge=128, le=4096)
    max_retries: int = Field(default=4, ge=0)
    retry_base_delay_ms: int = Field(default=500, ge=1)
    retry_max_delay_ms: int = Field(default=8000, ge=1)
    retry_jitter_ms: int = Field(default=250, ge=0)
    circuit_breaker_threshold: int = Field(default=3, ge=1)
    circuit_breaker_cooldown_seconds: int = Field(default=30, ge=1)
    classification_model: str = "qwen3-1.7b-q4"
    planning_model: str = "qwen3-1.7b-q4"
    review_model: str = "qwen3-1.7b-q4"
    prompt_cache_enabled: bool = False

    @model_validator(mode="after")
    def _normalize_retry_bounds(self) -> LLMSettings:
        if self.retry_max_delay_ms < self.retry_base_delay_ms:
            self.retry_max_delay_ms = self.retry_base_delay_ms
        normalized_provider = self.provider.strip().lower() or "auto"
        legacy_provider = "anth" + "ropic"
        if normalized_provider in {legacy_provider, "auto_legacy"}:
            normalized_provider = "auto"
        self.provider = normalized_provider
        if not self.model_id.strip():
            self.model_id = self.planning_model.strip() or "qwen3-1.7b-q4"
        if self.model_id == DEFAULT_MODEL_ID:
            hardware = probe_hardware()
            if hardware.ram_gb < 6:
                self.model_id = "qwen3-0.6b-q4"
        self.classification_model = self.model_id
        self.planning_model = self.model_id
        self.review_model = self.model_id
        return self

    @field_validator("local_http_url", "model_path")
    @classmethod
    def _strip_paths(cls, value: str) -> str:
        return value.strip()

    @field_validator("local_http_url")
    @classmethod
    def _validate_local_http_url(cls, value: str) -> str:
        if value:
            assert_loopback_url(value)
        return value


class AppConfig(BaseModel):
    """Autoshelf configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=LATEST_CONFIG_VERSION, ge=1)
    exclude: list[str] = Field(
        default_factory=lambda: [".git", "node_modules", "__pycache__", ".venv"]
    )
    include_dotfiles: bool = False
    max_head_chars: int = 2000
    max_chunk_tokens: int = 1024
    near_duplicate_detection: bool = True
    near_duplicate_threshold: float = Field(default=0.72, ge=0.5, le=1.0)
    near_duplicate_shingle_size: int = Field(default=3, ge=1, le=8)
    near_duplicate_min_token_count: int = Field(default=12, ge=1)
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
