from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from autoshelf.paths import config_dir


class LLMSettings(BaseModel):
    """LLM provider and model settings."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "auto"
    classification_model: str = "claude-haiku-4-5"
    planning_model: str = "claude-sonnet-4-6"
    review_model: str = "claude-sonnet-4-6"
    requests_per_second: int = 2
    concurrency: int = 3
    max_retries: int = 4
    prompt_cache_enabled: bool = True


class AppConfig(BaseModel):
    """Autoshelf configuration."""

    model_config = ConfigDict(extra="forbid")

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
        data = _parse_toml(config_path)
        return cls.model_validate(data)

    def save(self, path: Path | None = None) -> Path:
        config_path = path or self.default_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(_to_toml(self.model_dump()), encoding="utf-8")
        return config_path


def _parse_toml(path: Path) -> dict[str, object]:
    import tomllib

    with path.open("rb") as handle:
        return tomllib.load(handle)


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
