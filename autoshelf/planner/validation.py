from __future__ import annotations

from typing import Any

from autoshelf.planner.naming import normalize_folder_name, validate_folder_name, validate_sibling_names


def validate_and_normalize_tree(tree: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, child in tree.items():
        clean_name = normalize_folder_name(name, "정리")
        normalized[clean_name] = _normalize_child(child, depth=1)
    _validate_tree(normalized, depth=1)
    return normalized


def _normalize_child(node: Any, depth: int) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {}
    if depth >= 3 and not bool(node.get("deep_ok")):
        return {}
    normalized: dict[str, Any] = {}
    for name, child in node.items():
        if name == "deep_ok":
            continue
        clean_name = normalize_folder_name(name, "정리")
        normalized[clean_name] = _normalize_child(child, depth + 1)
    return normalized


def _validate_tree(tree: dict[str, Any], depth: int) -> None:
    validate_sibling_names(list(tree.keys()))
    for name, child in tree.items():
        validate_folder_name(name)
        if depth > 3:
            raise ValueError("folder depth cannot exceed 3 without deep_ok")
        _validate_tree(child, depth + 1)

