from __future__ import annotations

from pathlib import Path

from autoshelf.planner.llm import PlannerAssignment


def write_manifests(
    root: Path,
    tree: dict[str, object],
    assignments: list[PlannerAssignment],
) -> None:
    """Generate FOLDER_GUIDE.md and FILE_INDEX.md."""

    korean = _prefer_korean(assignments)
    guide = _render_folder_guide(tree, korean)
    index = _render_file_index(assignments, korean)
    (root / "FOLDER_GUIDE.md").write_text(guide, encoding="utf-8")
    (root / "FILE_INDEX.md").write_text(index, encoding="utf-8")


def _render_folder_guide(tree: dict[str, object], korean: bool) -> str:
    if korean:
        lines = [
            "# FOLDER_GUIDE",
            "",
            "이 구조는 사람이 기억하기 쉬운 폴더 이름을 우선합니다.",
            "상위 폴더는 주제 또는 문서 유형을 나타내며, 필요할 때만 연도를 하위에 둡니다.",
            "",
        ]
        for name in tree:
            lines.append(f"- `{name}`: 여기에는 {name} 관련 파일이 들어갑니다.")
        return "\n".join(lines) + "\n"
    lines = [
        "# FOLDER_GUIDE",
        "",
        "This structure favors folder names that are easy for humans to remember.",
        (
            "Top-level folders represent themes or document types, "
            "with year subfolders only when helpful."
        ),
        "",
    ]
    for name in tree:
        lines.append(f"- `{name}`: Files related to {name} belong here.")
    return "\n".join(lines) + "\n"


def _render_file_index(assignments: list[PlannerAssignment], korean: bool) -> str:
    lines = ["# FILE_INDEX", ""]
    for assignment in sorted(assignments, key=lambda item: item.path):
        target = "/".join([*assignment.primary_dir, Path(assignment.path).name])
        extras = ["/".join(parts) for parts in assignment.also_relevant]
        if korean:
            extra_text = f" | 바로가기: {', '.join(extras)}" if extras else ""
            lines.append(f"- `{target}` | 요약: {assignment.summary or '요약 없음'}{extra_text}")
        else:
            extra_text = f" | Shortcuts: {', '.join(extras)}" if extras else ""
            summary = assignment.summary or "No summary"
            lines.append(f"- `{target}` | Summary: {summary}{extra_text}")
    return "\n".join(lines) + "\n"


def _prefer_korean(assignments: list[PlannerAssignment]) -> bool:
    hangul = 0
    english = 0
    for assignment in assignments:
        text = f"{assignment.path} {assignment.summary}"
        hangul += sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
        english += sum(1 for char in text if char.isascii() and char.isalpha())
    return hangul >= english
