from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from autoshelf.planner.models import PlannerAssignment
from autoshelf.scanner import _hash_file
from autoshelf.targeting import resolve_assignment_target, safe_target_dir


class PreviewLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    preview_path: str
    kind: str = Field(pattern="^(primary|shortcut)$")


class PreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_dir: str
    assignments: int = Field(ge=0)
    shortcuts: int = Field(ge=0)
    reused_draft: bool = False
    links: list[PreviewLink] = Field(default_factory=list)


def preview_dir(root: Path) -> Path:
    return root / ".autoshelf" / "preview"


def build_preview(
    root: Path,
    assignments: list[PlannerAssignment],
    *,
    conflict_policy: str = "append-counter",
    reused_draft: bool = False,
) -> PreviewResult:
    resolved_root = root.resolve()
    destination = preview_dir(resolved_root)
    temp_destination = destination.parent / f".preview-{uuid.uuid4().hex}.tmp"
    occupied_targets: set[Path] = set()
    primary_preview_paths: dict[str, Path] = {}
    canonical_preview_paths: dict[str, Path] = {}
    links: list[PreviewLink] = []

    if temp_destination.exists():
        shutil.rmtree(temp_destination)
    temp_destination.mkdir(parents=True, exist_ok=True)
    try:
        for assignment in assignments:
            source = resolved_root / assignment.path
            if not source.exists():
                logger.warning("skipping preview entry for missing source {}", assignment.path)
                continue
            final_target = resolve_assignment_target(
                resolved_root,
                assignment.path,
                assignment.primary_dir,
                conflict_policy,
                occupied_targets,
            )
            occupied_targets.add(final_target)
            primary_link = temp_destination / final_target.relative_to(resolved_root)
            file_hash = _hash_file(source)
            canonical_link = canonical_preview_paths.get(file_hash)
            _create_preview_link(canonical_link or source, primary_link)
            canonical_preview_paths.setdefault(file_hash, primary_link)
            primary_preview_paths[assignment.path] = primary_link
            links.append(
                PreviewLink(
                    source_path=assignment.path,
                    preview_path=str(primary_link.relative_to(temp_destination)),
                    kind="primary",
                )
            )
            for extra in assignment.also_relevant:
                shortcut_dir = safe_target_dir(temp_destination, extra)
                shortcut_dir.mkdir(parents=True, exist_ok=True)
                shortcut_link = shortcut_dir / primary_link.name
                _create_preview_link(primary_link, shortcut_link)
                links.append(
                    PreviewLink(
                        source_path=assignment.path,
                        preview_path=str(shortcut_link.relative_to(temp_destination)),
                        kind="shortcut",
                    )
                )
        _swap_preview_tree(temp_destination, destination)
    except Exception:
        shutil.rmtree(temp_destination, ignore_errors=True)
        raise
    return PreviewResult(
        preview_dir=str(destination),
        assignments=sum(1 for link in links if link.kind == "primary"),
        shortcuts=sum(1 for link in links if link.kind == "shortcut"),
        reused_draft=reused_draft,
        links=links,
    )


def _create_preview_link(target: Path, link_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_dir() and not link_path.is_symlink():
            shutil.rmtree(link_path)
        else:
            link_path.unlink()
    relative_target = Path(os.path.relpath(target, start=link_path.parent))
    link_path.symlink_to(relative_target)


def _swap_preview_tree(temp_destination: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    temp_destination.replace(destination)
