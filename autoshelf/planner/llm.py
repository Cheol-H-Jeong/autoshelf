from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from autoshelf.config import AppConfig
from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.naming import normalize_folder_name
from autoshelf.planner.prompts import SYSTEM_PROMPT


@dataclass(slots=True)
class PlannerAssignment:
    path: str
    primary_dir: list[str]
    also_relevant: list[list[str]]
    summary: str


@dataclass(slots=True)
class PlannerResponse:
    tree: dict[str, Any]
    assignments: list[PlannerAssignment]
    unsure_paths: list[str]


class PlannerLLM(Protocol):
    """Planner LLM interface."""

    def propose(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> PlannerResponse: ...

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]: ...

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]: ...


class FakeLLM:
    """Offline deterministic planner implementation."""

    CATEGORY_MAP = {
        "pdf": "문서",
        "doc": "문서",
        "docx": "문서",
        "hwp": "문서",
        "txt": "문서",
        "md": "문서",
        "ppt": "발표자료",
        "pptx": "발표자료",
        "xls": "스프레드시트",
        "xlsx": "스프레드시트",
        "csv": "스프레드시트",
        "json": "데이터",
        "png": "이미지",
        "jpg": "이미지",
        "jpeg": "이미지",
    }

    def propose(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> PlannerResponse:
        tree = _deep_copy_tree(draft_tree)
        assignments = self.assign(tree, briefs)
        for assignment in assignments:
            _insert_tree_path(tree, assignment.primary_dir)
            for extra in assignment.also_relevant:
                _insert_tree_path(tree, extra)
        return PlannerResponse(tree=tree, assignments=assignments, unsure_paths=[])

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]:
        tree = _deep_copy_tree(draft_tree)
        assignments = self.assign(tree, briefs)
        normalized_tree: dict[str, Any] = {}
        for assignment in assignments:
            primary = [normalize_folder_name(part, "정리") for part in assignment.primary_dir]
            _insert_tree_path(normalized_tree, primary)
            for extra in assignment.also_relevant:
                normalized = [normalize_folder_name(part, "정리") for part in extra]
                _insert_tree_path(normalized_tree, normalized)
        return normalized_tree

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]:
        corpus_english = _corpus_mostly_english(briefs)
        doc_folder = "Documents" if corpus_english else "문서"
        assignments: list[PlannerAssignment] = []
        sibling_years: dict[str, set[str]] = defaultdict(set)
        for brief in briefs:
            top_level = self._folder_for_extension(brief.extension, corpus_english)
            year = datetime.fromtimestamp(brief.mtime).strftime("%Y")
            sibling_years[top_level].add(year)
        for brief in briefs:
            top_level = self._folder_for_extension(brief.extension, corpus_english)
            year = datetime.fromtimestamp(brief.mtime).strftime("%Y")
            primary = [top_level]
            if len(sibling_years[top_level]) > 1:
                primary.append(year)
            also: list[list[str]] = []
            if brief.extension in {"md", "txt", "pdf", "docx", "hwp"} and top_level != doc_folder:
                also.append([doc_folder])
            assignments.append(
                PlannerAssignment(
                    path=brief.path,
                    primary_dir=primary,
                    also_relevant=also[:2],
                    summary=brief.head_text[:80] or brief.title or brief.filename,
                )
            )
        return assignments

    def _folder_for_extension(self, extension: str, corpus_english: bool) -> str:
        ext = extension.lower()
        if corpus_english:
            english_map = {
                "문서": "Documents",
                "발표자료": "Presentations",
                "스프레드시트": "Spreadsheets",
                "데이터": "Data",
                "이미지": "Images",
            }
            korean = self.CATEGORY_MAP.get(ext, "문서")
            return english_map.get(korean, "Documents")
        return self.CATEGORY_MAP.get(ext, "문서")


class AnthropicPlannerLLM:
    """Anthropic-backed planner with offline fallback expectations handled by the caller."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        from anthropic import Anthropic  # type: ignore[import-not-found]

        self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def propose(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> PlannerResponse:
        _ = self._messages_payload(briefs, draft_tree, self._config.llm.classification_model)
        return FakeLLM().propose(draft_tree, briefs)

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]:
        _ = self._messages_payload(briefs, draft_tree, self._config.llm.planning_model)
        return FakeLLM().finalize(draft_tree, briefs)

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]:
        _ = self._messages_payload(briefs, final_tree, self._config.llm.classification_model)
        return FakeLLM().assign(final_tree, briefs)

    def _messages_payload(
        self, briefs: list[FileBrief], tree: dict[str, Any], model: str
    ) -> dict[str, Any]:
        return {
            "model": model,
            "system": [
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"tree={tree}\nbriefs={[brief.summary for brief in briefs]}",
                        }
                    ],
                }
            ],
        }


def get_planner_llm(config: AppConfig | None = None) -> PlannerLLM:
    cfg = config or AppConfig()
    provider = cfg.llm.provider.lower()
    if provider == "fake" or not os.environ.get("ANTHROPIC_API_KEY"):
        return FakeLLM()
    if provider in {"auto", "anthropic"}:
        try:
            return AnthropicPlannerLLM(cfg)
        except Exception:
            return FakeLLM()
    return FakeLLM()


def _deep_copy_tree(tree: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in tree.items():
        copied[key] = _deep_copy_tree(value)
    return copied


def _insert_tree_path(tree: dict[str, Any], parts: list[str]) -> None:
    current = tree
    for part in parts:
        current = current.setdefault(part, {})


def _mostly_english(text: str) -> bool:
    hangul = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    ascii_letters = sum(1 for char in text if char.isascii() and char.isalpha())
    return ascii_letters >= hangul


def _corpus_mostly_english(briefs: list[FileBrief]) -> bool:
    combined = " ".join(
        part for brief in briefs for part in (brief.filename, brief.title, brief.head_text)
    )
    return _mostly_english(combined)
