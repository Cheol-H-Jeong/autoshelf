from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from autoshelf.planner.models import PlannerAssignment
from autoshelf.scanner import _hash_file

GENESIS_HASH = "0" * 32


class ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    source: str
    target: str
    also_relevant: list[str] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    fallback: bool = False
    content_hash: str = ""
    prev_hash: str = GENESIS_HASH
    entry_hash: str = ""

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        return min(1.0, max(0.0, value))

    def payload_for_hash(self) -> dict[str, object]:
        return self.model_dump(exclude={"entry_hash"})

    def computed_entry_hash(self) -> str:
        return _hash_payload(self.payload_for_hash())


def write_manifests(
    root: Path,
    tree: dict[str, object],
    assignments: list[PlannerAssignment],
) -> None:
    korean = _prefer_korean(assignments)
    guide = _render_folder_guide(tree, korean)
    index = _render_file_index(assignments, korean)
    manifest_lines = _render_manifest_lines(root, assignments)
    _atomic_write(root / "FOLDER_GUIDE.md", guide)
    _atomic_write(root / "FILE_INDEX.md", index)
    _atomic_write(root / "manifest.jsonl", manifest_lines)


def load_manifest_entries(path: Path) -> list[ManifestEntry]:
    if not path.exists():
        return []
    return [
        ManifestEntry.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _render_manifest_lines(root: Path, assignments: list[PlannerAssignment]) -> str:
    entries = _build_manifest_entries(root, assignments)
    return "\n".join(json.dumps(entry.model_dump(), ensure_ascii=False) for entry in entries) + (
        "\n" if entries else ""
    )


def _build_manifest_entries(
    root: Path, assignments: list[PlannerAssignment]
) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    previous_hash = GENESIS_HASH
    for index, assignment in enumerate(sorted(assignments, key=lambda item: item.path), start=1):
        entry = ManifestEntry(
            index=index,
            source=assignment.path,
            target=_target_path(assignment),
            also_relevant=["/".join(parts) for parts in assignment.also_relevant],
            summary=assignment.summary,
            confidence=assignment.confidence,
            fallback=assignment.fallback,
            content_hash=_assignment_content_hash(root, assignment),
            prev_hash=previous_hash,
        )
        entry.entry_hash = entry.computed_entry_hash()
        entries.append(entry)
        previous_hash = entry.entry_hash
    return entries


def _assignment_content_hash(root: Path, assignment: PlannerAssignment) -> str:
    source = root / assignment.path
    target = root / _target_path(assignment)
    if source.exists():
        return _hash_file(source)
    if target.exists():
        return _hash_file(target)
    return ""


def _target_path(assignment: PlannerAssignment) -> str:
    return "/".join([*assignment.primary_dir, Path(assignment.path).name])


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.blake2b(encoded, digest_size=16).hexdigest()


def expected_shortcut_paths(entry: ManifestEntry) -> list[str]:
    lines = []
    target_name = Path(entry.target).name
    shortcut_name = f"{target_name}.lnk" if _windows_path() else target_name
    for folder in entry.also_relevant:
        lines.append(str(Path(folder) / shortcut_name))
    return lines


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


def _windows_path() -> bool:
    import sys

    return sys.platform == "win32"
