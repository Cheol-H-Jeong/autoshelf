from __future__ import annotations

import json
from pathlib import Path

from autoshelf.planner.models import PlannerAssignment


def write_manifests(
    root: Path,
    tree: dict[str, object],
    assignments: list[PlannerAssignment],
) -> None:
    korean = _prefer_korean(assignments)
    guide = _render_folder_guide(tree, korean)
    index = _render_file_index(assignments, korean)
    manifest_lines = _render_manifest_lines(assignments)
    _atomic_write(root / "FOLDER_GUIDE.md", guide)
    _atomic_write(root / "FILE_INDEX.md", index)
    _atomic_write(root / "manifest.jsonl", manifest_lines)


def _render_folder_guide(tree: dict[str, object], korean: bool) -> str:
    intro = (
        [
            "# FOLDER_GUIDE",
            "",
            "이 구조는 사람이 기억하기 쉬운 폴더 이름을 우선합니다.",
            "상위 폴더는 주제 또는 문서 유형을 나타내며, 필요할 때만 연도를 하위에 둡니다.",
            "",
        ]
        if korean
        else [
            "# FOLDER_GUIDE",
            "",
            "This structure favors folder names that are easy for humans to remember.",
            (
                "Top-level folders represent themes or document types, "
                "with year subfolders only when helpful."
            ),
            "",
        ]
    )
    for name in sorted(tree):
        description = (
            f"여기에는 {name} 관련 파일이 들어갑니다."
            if korean
            else f"Files related to {name} belong here."
        )
        intro.append(f"- `{name}`: {description}")
    return "\n".join(intro) + "\n"


def _render_file_index(assignments: list[PlannerAssignment], korean: bool) -> str:
    lines = ["# FILE_INDEX", ""]
    for assignment in sorted(assignments, key=lambda item: item.path):
        target = "/".join([*assignment.primary_dir, Path(assignment.path).name])
        extras = ["/".join(parts) for parts in assignment.also_relevant]
        fallback_flag = " ⚠ fallback" if assignment.fallback else ""
        if korean:
            extra_text = f" | 바로가기: {', '.join(extras)}" if extras else ""
            summary = assignment.summary or "요약 없음"
            lines.append(f"- `{target}` | 요약: {summary}{extra_text}{fallback_flag}")
        else:
            extra_text = f" | Shortcuts: {', '.join(extras)}" if extras else ""
            summary = assignment.summary or "No summary"
            lines.append(f"- `{target}` | Summary: {summary}{extra_text}{fallback_flag}")
    return "\n".join(lines) + "\n"


def _render_manifest_lines(assignments: list[PlannerAssignment]) -> str:
    lines = []
    for assignment in sorted(assignments, key=lambda item: item.path):
        payload = {
            "source": assignment.path,
            "target": "/".join([*assignment.primary_dir, Path(assignment.path).name]),
            "also_relevant": ["/".join(parts) for parts in assignment.also_relevant],
            "summary": assignment.summary,
            "confidence": assignment.confidence,
            "fallback": assignment.fallback,
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _prefer_korean(assignments: list[PlannerAssignment]) -> bool:
    hangul = 0
    english = 0
    for assignment in assignments:
        text = f"{assignment.path} {assignment.summary}"
        hangul += sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
        english += sum(1 for char in text if char.isascii() and char.isalpha())
    return hangul >= english
