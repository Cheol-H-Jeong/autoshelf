from __future__ import annotations

from collections import Counter
from pathlib import Path

from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.contextual import meaningful_parent_folder
from autoshelf.planner.models import PlannerAssignment

WORKFLOW_FOLDER_NAMES = {
    "archive",
    "archives",
    "attachments",
    "docs",
    "draft",
    "drafts",
    "files",
    "notes",
    "paperwork",
    "proposal",
    "proposals",
    "receipt",
    "receipts",
    "report",
    "reports",
    "scan",
    "scans",
    "자료",
    "문서",
    "보고서",
    "스캔",
    "영수증",
    "임시",
    "제안서",
    "초안",
    "첨부",
}

CONTAINER_FOLDER_NAMES = {
    "client",
    "clients",
    "customer",
    "customers",
    "project",
    "projects",
    "team",
    "teams",
    "vendor",
    "vendors",
    "거래처",
    "고객",
    "업체",
    "팀",
    "프로젝트",
}


def review_assignments(
    assignments: list[PlannerAssignment],
    briefs: list[FileBrief],
    *,
    corpus_english: bool,
) -> list[PlannerAssignment]:
    briefs_by_path = {brief.path: brief for brief in briefs}
    ancestor_counts = _shared_ancestor_counts(assignments, briefs_by_path)
    reviewed: list[PlannerAssignment] = []
    for assignment in assignments:
        brief = briefs_by_path.get(assignment.path)
        if brief is None:
            reviewed.append(assignment)
            continue
        updated_primary = _refined_primary_dir(assignment, brief, ancestor_counts)
        rationale = build_assignment_rationale(
            brief,
            updated_primary,
            assignment.also_relevant,
            corpus_english=corpus_english,
        )
        reviewed.append(
            assignment.model_copy(update={"primary_dir": updated_primary, "summary": rationale})
        )
    return reviewed


def build_assignment_rationale(
    brief: FileBrief,
    primary_dir: list[str],
    also_relevant: list[list[str]],
    *,
    corpus_english: bool,
) -> str:
    top_level = primary_dir[0] if primary_dir else ("Documents" if corpus_english else "문서")
    reasons: list[str] = []
    parent_reason = len(primary_dir) > 1 and primary_dir[1] in {
        value for value in _business_ancestors(brief)
    } | ({meaningful_parent_folder(brief, fallback=top_level)} - {None})
    if parent_reason:
        if corpus_english:
            reasons.append(f"Preserves parent context '{primary_dir[1]}' for faster recall")
        else:
            reasons.append(f"상위 맥락 '{primary_dir[1]}'을 유지해 다시 찾기 쉽게 정리")
    elif corpus_english:
        reasons.append(f"Grouped into {top_level} from file type and content signals")
    else:
        reasons.append(f"파일 형식과 내용 신호를 바탕으로 {top_level}에 분류")

    if brief.title.strip():
        if corpus_english:
            reasons.append(f"title '{brief.title.strip()[:40]}' reinforced the folder choice")
        else:
            reasons.append(f"제목 '{brief.title.strip()[:40]}' 정보도 함께 반영")
    elif brief.head_text.strip():
        if corpus_english:
            reasons.append("head text provided the strongest semantic clue")
        else:
            reasons.append("본문 앞부분이 가장 강한 분류 단서로 작용")

    if brief.duplicate_group_size > 1:
        if corpus_english:
            reasons.append(f"detected {brief.duplicate_group_size} identical copies")
        else:
            reasons.append(f"동일 해시 파일 {brief.duplicate_group_size}개를 함께 감안")

    if also_relevant:
        extras = ", ".join("/".join(parts) for parts in also_relevant)
        if corpus_english:
            reasons.append(f"shortcut targets kept in {extras}")
        else:
            reasons.append(f"바로가기 대상은 {extras}로 유지")

    text = ". ".join(reasons).strip()
    if not text.endswith("."):
        text += "."
    return text[:160]


def build_tree_from_assignments(assignments: list[PlannerAssignment]) -> dict[str, object]:
    tree: dict[str, object] = {}
    for assignment in assignments:
        current = tree
        for part in assignment.primary_dir:
            child = current.get(part)
            if not isinstance(child, dict):
                child = {}
                current[part] = child
            current = child
        for extra in assignment.also_relevant:
            current = tree
            for part in extra:
                child = current.get(part)
                if not isinstance(child, dict):
                    child = {}
                    current[part] = child
                current = child
    return tree


def _refined_primary_dir(
    assignment: PlannerAssignment,
    brief: FileBrief,
    ancestor_counts: Counter[tuple[str, str]],
) -> list[str]:
    if len(assignment.primary_dir) < 2:
        return assignment.primary_dir
    current_parent = assignment.primary_dir[1]
    if not _is_workflow_folder(current_parent):
        return assignment.primary_dir
    top_level = assignment.primary_dir[0]
    for candidate in _business_ancestors(brief):
        if candidate.casefold() == top_level.casefold():
            continue
        if ancestor_counts[(top_level.casefold(), candidate.casefold())] >= 2:
            return [top_level, candidate, *assignment.primary_dir[2:]]
    return assignment.primary_dir


def _shared_ancestor_counts(
    assignments: list[PlannerAssignment],
    briefs_by_path: dict[str, FileBrief],
) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for assignment in assignments:
        brief = briefs_by_path.get(assignment.path)
        if brief is None or not assignment.primary_dir:
            continue
        top_level = assignment.primary_dir[0]
        seen: set[tuple[str, str]] = set()
        for candidate in _business_ancestors(brief):
            key = (top_level.casefold(), candidate.casefold())
            if key not in seen:
                counts[key] += 1
                seen.add(key)
    return counts


def _business_ancestors(brief: FileBrief) -> list[str]:
    ancestors: list[str] = []
    for part in Path(brief.parent_path).parts:
        if part in {".", ""}:
            continue
        if _is_workflow_folder(part):
            continue
        if part.strip().casefold() in CONTAINER_FOLDER_NAMES:
            continue
        ancestors.append(part)
    return list(dict.fromkeys(ancestors[::-1]))


def _is_workflow_folder(name: str) -> bool:
    return name.strip().casefold() in WORKFLOW_FOLDER_NAMES
