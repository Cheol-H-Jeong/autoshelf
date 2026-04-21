from __future__ import annotations

from collections.abc import Collection
from pathlib import Path


def safe_target_dir(root: Path, parts: list[str]) -> Path:
    target = root.joinpath(*parts)
    resolved_root = root.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError("target directory escapes the selected root")
    return target


def resolve_assignment_target(
    root: Path,
    source_path: str,
    primary_dir: list[str],
    conflict_policy: str,
    occupied_targets: Collection[Path] | None = None,
) -> Path:
    target_dir = safe_target_dir(root, primary_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    return resolve_target(target_dir / Path(source_path).name, conflict_policy, occupied_targets)


def resolve_target(
    target: Path,
    conflict_policy: str,
    occupied_targets: Collection[Path] | None = None,
) -> Path:
    if conflict_policy == "overwrite":
        return target
    if conflict_policy == "skip" and not _target_is_occupied(target, occupied_targets):
        return target
    if conflict_policy == "append-counter":
        return dedupe_target(target, occupied_targets)
    return target


def dedupe_target(target: Path, occupied_targets: Collection[Path] | None = None) -> Path:
    if not _target_is_occupied(target, occupied_targets):
        return target
    counter = 2
    while True:
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        if not _target_is_occupied(candidate, occupied_targets):
            return candidate
        counter += 1


def _target_is_occupied(target: Path, occupied_targets: Collection[Path] | None = None) -> bool:
    return target.exists() or (occupied_targets is not None and target in occupied_targets)
