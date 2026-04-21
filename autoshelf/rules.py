from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULES_FILE_NAME = ".autoshelfrc.yaml"
T = TypeVar("T")


class MappingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    glob: str
    priority: int = 0
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
    exclude_globs: list[str] = Field(default_factory=list)
    mappings: list[MappingRule] = Field(default_factory=list)

    @field_validator("pinned_dirs", mode="before")
    @classmethod
    def _normalize_pinned_dirs(cls, value: object) -> list[list[str]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("pinned_dirs must be a list")
        return [_normalize_folder_path(item) for item in value]

    @field_validator("exclude_globs", mode="before")
    @classmethod
    def _normalize_exclude_globs(cls, value: object) -> list[str]:
        return _normalize_glob_list(value)

    @model_validator(mode="after")
    def _validate_version(self) -> PlanningRules:
        if self.version != 1:
            raise ValueError("only rules version 1 is supported")
        return self

    @property
    def is_empty(self) -> bool:
        return not self.pinned_dirs and not self.exclude_globs and not self.mappings


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
        "loaded rules from {} pinned_dirs={} exclude_globs={} mappings={}",
        path,
        len(rules.pinned_dirs),
        len(rules.exclude_globs),
        len(rules.mappings),
    )
    return rules


def merge_exclude_patterns(patterns: list[str], rules: PlanningRules) -> list[str]:
    return list(dict.fromkeys([*patterns, *rules.exclude_globs]))


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
        if is_path_excluded(assignment.path, rules.exclude_globs):
            continue
        matched = match_mapping_rule(assignment.path, rules)
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


def filter_paths_by_rules(
    paths: list[T],
    rules: PlanningRules,
    path_getter: Callable[[T], str],
) -> list[T]:
    if not rules.exclude_globs:
        return paths
    return [item for item in paths if not is_path_excluded(path_getter(item), rules.exclude_globs)]


def match_mapping_rule(relative_path: str, rules: PlanningRules) -> MappingRule | None:
    matches = [rule for rule in rules.mappings if rule.matches(relative_path)]
    if not matches:
        return None
    matches.sort(key=lambda rule: rule.priority, reverse=True)
    return matches[0]


def is_path_excluded(relative_path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    normalized = relative_path.replace("\\", "/").lstrip("./")
    basename = Path(normalized).name
    parts = Path(normalized).parts
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(basename, pattern):
            return True
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def render_rules_prompt(rules: PlanningRules) -> str:
    if rules.is_empty:
        return ""
    lines = ["Rules file constraints:"]
    for parts in rules.pinned_dirs:
        lines.append(f"- keep folder available: {_display_path(parts)}")
    for pattern in rules.exclude_globs:
        lines.append(f"- ignore paths matching {pattern}")
    for rule in rules.mappings:
        priority = f" [priority {rule.priority}]" if rule.priority else ""
        lines.append(f"- glob {rule.glob}{priority} must map to {_display_path(rule.target)}")
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


def _normalize_glob_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("exclude_globs must be a list")
    globs = [str(item).strip() for item in value if str(item).strip()]
    if not globs:
        return []
    return globs


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
