from __future__ import annotations

from pathlib import Path

from autoshelf.planner.contextual import contextual_primary_dir
from autoshelf.planner.models import FileBriefModel, PlannerAssignment

QUARANTINE_DIR = [".autoshelf", "quarantine"]

_ENGLISH_CATEGORY_MAP = {
    "csv": "Spreadsheets",
    "doc": "Documents",
    "docx": "Documents",
    "hwp": "Documents",
    "jpeg": "Images",
    "jpg": "Images",
    "json": "Data",
    "md": "Documents",
    "pdf": "Documents",
    "png": "Images",
    "ppt": "Presentations",
    "pptx": "Presentations",
    "txt": "Documents",
    "xls": "Spreadsheets",
    "xlsx": "Spreadsheets",
}

_KOREAN_CATEGORY_MAP = {
    "csv": "스프레드시트",
    "doc": "문서",
    "docx": "문서",
    "hwp": "문서",
    "jpeg": "이미지",
    "jpg": "이미지",
    "json": "데이터",
    "md": "문서",
    "pdf": "문서",
    "png": "이미지",
    "ppt": "발표자료",
    "pptx": "발표자료",
    "txt": "문서",
    "xls": "스프레드시트",
    "xlsx": "스프레드시트",
}


def is_quarantine_path(parts: list[str]) -> bool:
    return parts[: len(QUARANTINE_DIR)] == QUARANTINE_DIR


def is_quarantined_assignment(assignment: PlannerAssignment) -> bool:
    return is_quarantine_path(assignment.primary_dir)


def quarantine_paths(assignments: list[PlannerAssignment]) -> set[str]:
    return {
        assignment.path for assignment in assignments if is_quarantined_assignment(assignment)
    }


def clear_quarantine_assignments(
    assignments: list[PlannerAssignment],
    *,
    selected_paths: set[str] | None = None,
) -> list[PlannerAssignment]:
    selected = _selected_quarantine_paths(assignments, selected_paths)
    updated: list[PlannerAssignment] = []
    for assignment in assignments:
        if assignment.path not in selected:
            updated.append(assignment)
            continue
        source_parent = _source_parent_parts(assignment.path)
        updated.append(
            assignment.model_copy(
                update={
                    "primary_dir": source_parent,
                    "summary": _clear_summary(assignment.path, source_parent),
                    "confidence": max(assignment.confidence, 0.4),
                    "fallback": False,
                }
            )
        )
    return updated


def replan_quarantine_assignments(
    assignments: list[PlannerAssignment],
    *,
    selected_paths: set[str] | None = None,
) -> list[PlannerAssignment]:
    selected = _selected_quarantine_paths(assignments, selected_paths)
    if not selected:
        return list(assignments)
    corpus_english = _prefer_english(assignments)
    updated: list[PlannerAssignment] = []
    for assignment in assignments:
        if assignment.path not in selected:
            updated.append(assignment)
            continue
        target = _replanned_primary_dir(assignment.path, corpus_english=corpus_english)
        updated.append(
            assignment.model_copy(
                update={
                    "primary_dir": target,
                    "summary": _replan_summary(assignment.path, target),
                    "confidence": max(assignment.confidence, 0.55),
                    "fallback": False,
                }
            )
        )
    return updated


def _selected_quarantine_paths(
    assignments: list[PlannerAssignment],
    selected_paths: set[str] | None,
) -> set[str]:
    available = quarantine_paths(assignments)
    if not available:
        return set()
    if not selected_paths:
        return available
    return available & selected_paths


def _source_parent_parts(path: str) -> list[str]:
    parent = Path(path).parent
    if str(parent) in {"", "."}:
        return []
    return [part for part in parent.parts if part not in {"", "."}]


def _replanned_primary_dir(path: str, *, corpus_english: bool) -> list[str]:
    source = Path(path)
    extension = source.suffix.lower().lstrip(".")
    default_top_level = _default_top_level(extension, corpus_english=corpus_english)
    parent_parts = _source_parent_parts(path)
    brief = FileBriefModel(
        path=path,
        parent_name=parent_parts[-1] if parent_parts else "",
        parent_path="/".join(parent_parts),
        filename=source.name,
        extension=extension,
        mtime=0.0,
        title=source.stem,
        head_text="",
    )
    return contextual_primary_dir(
        brief,
        default_top_level=default_top_level,
        corpus_english=corpus_english,
    )


def _default_top_level(extension: str, *, corpus_english: bool) -> str:
    if corpus_english:
        return _ENGLISH_CATEGORY_MAP.get(extension, "Documents")
    return _KOREAN_CATEGORY_MAP.get(extension, "문서")


def _prefer_english(assignments: list[PlannerAssignment]) -> bool:
    hangul = 0
    english = 0
    for assignment in assignments:
        text = " ".join([assignment.path, *assignment.primary_dir, assignment.summary])
        hangul += sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
        english += sum(1 for char in text if char.isascii() and char.isalpha())
    return english >= hangul


def _replan_summary(path: str, target: list[str]) -> str:
    destination = "/".join(target) or "."
    return (
        "Quarantine re-plan used source path context to place "
        f"{Path(path).name} under {destination}."
    )


def _clear_summary(path: str, target: list[str]) -> str:
    destination = "/".join(target) or "."
    return (
        f"Quarantine was cleared and {Path(path).name} stays "
        f"in its current folder {destination}."
    )
