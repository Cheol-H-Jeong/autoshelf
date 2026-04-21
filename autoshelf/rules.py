from __future__ import annotations

import fnmatch
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULES_FILE_NAME = ".autoshelfrc.yaml"


class MappingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    glob: str
    target: list[str]
    also_relevant: list[list[str]] = Field(default_factory=list)

    @field_validator("target", mode="before")
    @classmethod
    def _normalize_target(cls, value: object) -> list[str]:
        return _normalize_folder_path(value)

    @field_validator("also_relevant", mode="before")
    @classmethod
    def _normalize_also_relevant(cls, value: object) -> list[list[str]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("also_relevant must be a list")
        return [_normalize_folder_path(item) for item in value]

    def matches(self, relative_path: str) -> bool:
        posix_path = relative_path.replace("\\", "/")
        return fnmatch.fnmatch(posix_path, self.glob) or fnmatch.fnmatch(
            Path(posix_path).name, self.glob
        )


class PlanningRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    pinned_dirs: list[list[str]] = Field(default_factory=list)
    mappings: list[MappingRule] = Field(default_factory=list)

    @field_validator("pinned_dirs", mode="before")
    @classmethod
    def _normalize_pinned_dirs(cls, value: object) -> list[list[str]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("pinned_dirs must be a list")
        return [_normalize_folder_path(item) for item in value]

    @model_validator(mode="after")
    def _validate_version(self) -> PlanningRules:
        if self.version != 1:
            raise ValueError("only rules version 1 is supported")
        return self

    @property
    def is_empty(self) -> bool:
        return not self.pinned_dirs and not self.mappings


def rules_path(root: Path) -> Path:
    return root / RULES_FILE_NAME


def load_planning_rules(root: Path | None) -> PlanningRules:
    if root is None:
        return PlanningRules()
    path = rules_path(root)
    if not path.exists():
        return PlanningRules()
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "YAML rules require PyYAML. Install autoshelf with the 'rules' extra."
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = PlanningRules.model_validate(data)
    logger.bind(component="rules").info(
        "loaded rules from {} pinned_dirs={} mappings={}",
        path,
        len(rules.pinned_dirs),
        len(rules.mappings),
    )
    return rules


def merge_rule_paths(tree: dict[str, object], rules: PlanningRules) -> dict[str, object]:
    merged = _deep_copy_tree(tree)
    for parts in rules.pinned_dirs:
        _insert_tree_path(merged, parts)
    for rule in rules.mappings:
        _insert_tree_path(merged, rule.target)
        for extra in rule.also_relevant:
            _insert_tree_path(merged, extra)
    return merged


def apply_assignment_rules(assignments: list, rules: PlanningRules) -> list:
    if rules.is_empty:
        return assignments
    adjusted = []
    for assignment in assignments:
        matched = next((rule for rule in rules.mappings if rule.matches(assignment.path)), None)
        if matched is None:
            adjusted.append(assignment)
            continue
        updated = assignment.model_copy(
            update={
                "primary_dir": matched.target,
                "also_relevant": matched.also_relevant[:2],
                "confidence": 1.0,
                "summary": _rule_summary(assignment.summary, matched.glob),
            }
        )
        adjusted.append(updated)
    return adjusted


def render_rules_prompt(rules: PlanningRules) -> str:
    if rules.is_empty:
        return ""
    lines = ["Rules file constraints:"]
    for parts in rules.pinned_dirs:
        lines.append(f"- keep folder available: {_display_path(parts)}")
    for rule in rules.mappings:
        lines.append(f"- glob {rule.glob} must map to {_display_path(rule.target)}")
        for extra in rule.also_relevant:
            lines.append(f"- glob {rule.glob} may also appear in {_display_path(extra)}")
    return "\n".join(lines)


def _display_path(parts: list[str]) -> str:
    return "/".join(parts)


def _normalize_folder_path(value: object) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("\\", "/").split("/") if part.strip()]
    elif isinstance(value, list):
        parts = [str(part).strip() for part in value if str(part).strip()]
    else:
        raise TypeError("folder paths must be strings or string lists")
    if not parts:
        raise ValueError("folder paths cannot be empty")
    return parts


def _rule_summary(summary: str, glob: str) -> str:
    prefix = f"[rule:{glob}]"
    return prefix if not summary else f"{prefix} {summary}"[:120]


def _deep_copy_tree(tree: dict[str, object]) -> dict[str, object]:
    copied: dict[str, object] = {}
    for key, value in tree.items():
        copied[key] = _deep_copy_tree(value) if isinstance(value, dict) else {}
    return copied


def _insert_tree_path(tree: dict[str, object], parts: list[str]) -> None:
    current = tree
    for part in parts:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
