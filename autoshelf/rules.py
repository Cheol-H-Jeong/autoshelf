from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULES_FILE_NAME = ".autoshelfrc.yaml"
CURRENT_TARGET = "@current"
T = TypeVar("T")


class MappingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    glob: str
    priority: int = 0
    source_globs: list[str] = Field(default_factory=list)
    target: list[str]
    target_mode: Literal["fixed", "current"] = "fixed"
    also_relevant: list[list[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_dynamic_target(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if normalized.get("target") == CURRENT_TARGET:
            normalized["target"] = []
            normalized["target_mode"] = "current"
        return normalized

    @field_validator("target", mode="before")
    @classmethod
    def _normalize_target(cls, value: object) -> list[str]:
        if value == CURRENT_TARGET:
            return []
        if value == []:
            return []
        return _normalize_folder_path(value)

    @field_validator("source_globs", mode="before")
    @classmethod
    def _normalize_source_globs(cls, value: object) -> list[str]:
        return _normalize_glob_list(value, field_name="source_globs")

    @field_validator("also_relevant", mode="before")
    @classmethod
    def _normalize_also_relevant(cls, value: object) -> list[list[str]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("also_relevant must be a list")
        return [_normalize_folder_path(item) for item in value]

    @model_validator(mode="after")
    def _validate_target(self) -> MappingRule:
        if self.target_mode == "fixed" and not self.target:
            raise ValueError("target cannot be empty unless target is @current")
        return self

    def matches(self, relative_path: str) -> bool:
        posix_path = relative_path.replace("\\", "/")
        if not _matches_glob(posix_path, self.glob):
            return False
        if not self.source_globs:
            return True
        parent_path = _parent_relative_path(posix_path)
        return any(_matches_glob(parent_path, pattern) for pattern in self.source_globs)

    def resolve_target(self, relative_path: str) -> list[str]:
        if self.target_mode == "current":
            source_parent = _parent_relative_path(relative_path)
            return [part for part in source_parent.split("/") if part]
        return list(self.target)


class RuleDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    excluded: bool = False
    matched: bool = False
    target: list[str] = Field(default_factory=list)
    target_mode: Literal["fixed", "current"] | None = None
    mapping_glob: str | None = None
    source_globs: list[str] = Field(default_factory=list)
    priority: int | None = None
    reason: str


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
        return _normalize_glob_list(value, field_name="exclude_globs")

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
        if rule.target_mode == "fixed":
            _insert_tree_path(merged, rule.target)
        for extra in rule.also_relevant:
            _insert_tree_path(merged, extra)
    return merged


def apply_assignment_rules(assignments: list, rules: PlanningRules) -> list:
    if rules.is_empty:
        return assignments
    adjusted = []
    for assignment in assignments:
        decision = evaluate_path_rules(assignment.path, rules)
        if decision.excluded:
            continue
        matched = match_mapping_rule(assignment.path, rules)
        if matched is None:
            adjusted.append(assignment)
            continue
        updated = assignment.model_copy(
            update={
                "primary_dir": decision.target,
                "also_relevant": matched.also_relevant[:2],
                "confidence": 1.0,
                "summary": _rule_summary(assignment.summary, decision),
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
    matches.sort(key=_mapping_priority_key, reverse=True)
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


def evaluate_path_rules(relative_path: str, rules: PlanningRules) -> RuleDecision:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    if is_path_excluded(normalized, rules.exclude_globs):
        return RuleDecision(
            path=normalized,
            excluded=True,
            reason="Excluded by exclude_globs",
        )
    matched = match_mapping_rule(normalized, rules)
    if matched is None:
        return RuleDecision(
            path=normalized,
            reason="No mapping rule matched",
        )
    return RuleDecision(
        path=normalized,
        matched=True,
        target=matched.resolve_target(normalized),
        target_mode=matched.target_mode,
        mapping_glob=matched.glob,
        source_globs=list(matched.source_globs),
        priority=matched.priority,
        reason=_decision_reason(matched),
    )


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
        target = CURRENT_TARGET if rule.target_mode == "current" else _display_path(rule.target)
        lines.append(f"- glob {rule.glob}{priority} must map to {target}")
        for source_glob in rule.source_globs:
            lines.append(f"- glob {rule.glob} only applies under source {source_glob}")
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


def _normalize_glob_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")
    globs = [str(item).strip() for item in value if str(item).strip()]
    if not globs:
        return []
    return globs


def _rule_summary(summary: str, decision: RuleDecision) -> str:
    prefix = f"[rule:{decision.mapping_glob}]"
    if decision.target_mode == "current":
        prefix = f"{prefix}[current]"
    return prefix if not summary else f"{prefix} {summary}"[:120]


def _decision_reason(rule: MappingRule) -> str:
    if rule.target_mode == "current":
        base = f"Matched mapping {rule.glob} and kept the file in its current source folder"
    else:
        base = f"Matched mapping {rule.glob} and forced placement into {_display_path(rule.target)}"
    if not rule.source_globs:
        return base
    scopes = ", ".join(rule.source_globs)
    return f"{base}; source folder must match one of: {scopes}"


def _mapping_priority_key(rule: MappingRule) -> tuple[int, int, int]:
    return (rule.priority, len(rule.source_globs), len(rule.glob))


def _matches_glob(posix_path: str, pattern: str) -> bool:
    normalized = posix_path.lstrip("./")
    basename = Path(normalized).name
    return fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(basename, pattern)


def _parent_relative_path(relative_path: str) -> str:
    parent = Path(relative_path).parent.as_posix()
    return "" if parent == "." else parent


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
