from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from loguru import logger

from autoshelf.config import AppConfig
from autoshelf.llm.embedded import EmbeddedLlamaRuntime
from autoshelf.llm.model_registry import get_variant
from autoshelf.llm.openai_local import chat_completion, ollama_is_up, probe_openai_compatible
from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.contextual import contextual_primary_dir
from autoshelf.planner.models import PlannerAssignment, PlannerResponse, PlannerUsage
from autoshelf.planner.naming import normalize_folder_name
from autoshelf.planner.prompts import build_system_prompt_blocks
from autoshelf.planner.reliability import CircuitBreaker, RetryPolicy
from autoshelf.planner.review import (
    build_assignment_rationale,
    build_tree_from_assignments,
    review_assignments,
)
from autoshelf.rules import PlanningRules, render_rules_prompt


class PlannerLLM(Protocol):
    def propose(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> PlannerResponse: ...

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]: ...

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]: ...

    def review(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
        assignments: list[PlannerAssignment],
    ) -> PlannerResponse: ...

    @property
    def usage(self) -> PlannerUsage: ...

    def count_tokens(self, briefs: list[FileBrief]) -> int: ...


class FakeLLM:
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

    def __init__(self) -> None:
        self._usage = PlannerUsage()

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
        base_primaries = [
            contextual_primary_dir(
                brief,
                default_top_level=self._folder_for_extension(brief.extension, corpus_english),
                corpus_english=corpus_english,
            )
            for brief in briefs
        ]
        base_primaries = self._apply_near_duplicate_anchors(
            briefs,
            base_primaries,
            doc_folder=doc_folder,
        )
        assignments: list[PlannerAssignment] = []
        sibling_years: dict[tuple[str, ...], set[str]] = defaultdict(set)
        for brief, base_primary in zip(briefs, base_primaries, strict=False):
            year = datetime.fromtimestamp(brief.mtime).strftime("%Y")
            sibling_years[tuple(base_primary)].add(year)
        for brief, base_primary in zip(briefs, base_primaries, strict=False):
            top_level = base_primary[0]
            primary = list(base_primary)
            year = datetime.fromtimestamp(brief.mtime).strftime("%Y")
            if len(primary) < 3 and len(sibling_years[tuple(base_primary)]) > 1:
                primary.append(year)
            also: list[list[str]] = []
            if brief.extension in {"md", "txt", "pdf", "docx", "hwp"} and top_level != doc_folder:
                also.append([doc_folder])
            assignments.append(
                PlannerAssignment(
                    path=brief.path,
                    primary_dir=primary,
                    also_relevant=also[:2],
                    summary=build_assignment_rationale(
                        brief,
                        primary,
                        also[:2],
                        corpus_english=corpus_english,
                    ),
                    confidence=0.92,
                )
            )
        return assignments

    def review(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
        assignments: list[PlannerAssignment],
    ) -> PlannerResponse:
        reviewed = review_assignments(
            assignments,
            briefs,
            corpus_english=_corpus_mostly_english(briefs),
        )
        return PlannerResponse(
            tree=build_tree_from_assignments(reviewed) or _deep_copy_tree(final_tree),
            assignments=reviewed,
            unsure_paths=[],
        )

    @property
    def usage(self) -> PlannerUsage:
        return self._usage

    def count_tokens(self, briefs: list[FileBrief]) -> int:
        from autoshelf.planner.chunking import count_tokens

        return count_tokens(briefs)

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

    def _apply_near_duplicate_anchors(
        self,
        briefs: list[FileBrief],
        base_primaries: list[list[str]],
        *,
        doc_folder: str,
    ) -> list[list[str]]:
        adjusted = [list(parts) for parts in base_primaries]
        briefs_by_group: dict[str, list[int]] = defaultdict(list)
        for index, brief in enumerate(briefs):
            if brief.near_duplicate_group_size > 1 and brief.near_duplicate_group_id:
                briefs_by_group[brief.near_duplicate_group_id].append(index)
        for indices in briefs_by_group.values():
            anchor_index = max(
                indices,
                key=lambda index: (
                    self._semantic_signal_score(briefs[index]),
                    len(adjusted[index]),
                    briefs[index].path,
                ),
            )
            anchor_primary = adjusted[anchor_index]
            anchor_score = self._semantic_signal_score(briefs[anchor_index])
            for index in indices:
                if index == anchor_index:
                    continue
                current_primary = adjusted[index]
                current_score = self._semantic_signal_score(briefs[index])
                if current_score >= anchor_score:
                    continue
                if current_primary == anchor_primary:
                    continue
                if current_primary[0] != doc_folder and len(current_primary) >= len(anchor_primary):
                    continue
                adjusted[index] = list(anchor_primary)
        return adjusted

    def _semantic_signal_score(self, brief: FileBrief) -> int:
        return (
            min(len(brief.title.strip()), 80)
            + min(len(brief.head_text.strip()), 180)
            + (40 if brief.meaningful_parent_hint.strip() else 0)
            + int(brief.near_duplicate_similarity * 100)
        )


class StructuredPlannerLLM:
    def __init__(self, config: AppConfig, rules: PlanningRules | None = None) -> None:
        self._config = config
        self._rules = rules or PlanningRules()
        self._fallback = FakeLLM()
        self._usage = PlannerUsage()
        self._retry_policy = RetryPolicy(
            max_retries=config.llm.max_retries,
            base_delay_seconds=config.llm.retry_base_delay_ms / 1000,
            max_delay_seconds=config.llm.retry_max_delay_ms / 1000,
            jitter_seconds=config.llm.retry_jitter_ms / 1000,
        )
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=config.llm.circuit_breaker_threshold,
            cooldown_seconds=float(config.llm.circuit_breaker_cooldown_seconds),
        )
        self._tool_schema = {
            "type": "object",
            "properties": {
                "tree": {"type": "object"},
                "assignments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "primary_dir": {"type": "array", "items": {"type": "string"}},
                            "also_relevant": {
                                "type": "array",
                                "items": {"type": "array", "items": {"type": "string"}},
                            },
                            "summary": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": [
                            "path",
                            "primary_dir",
                            "also_relevant",
                            "summary",
                            "confidence",
                        ],
                    },
                },
                "unsure_paths": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tree", "assignments", "unsure_paths"],
        }

    def propose(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> PlannerResponse:
        return self._request(
            draft_tree=draft_tree,
            briefs=briefs,
            prompt="Propose or refine the folder tree and tentative assignments for this chunk.",
            fallback=lambda: self._fallback.propose(draft_tree, briefs),
        )

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]:
        response = self._request(
            draft_tree=draft_tree,
            briefs=briefs,
            prompt=(
                "Finalize the folder tree. Improve naming, merge duplicates, and keep depth <= 3."
            ),
            fallback=lambda: PlannerResponse(
                tree=self._fallback.finalize(draft_tree, briefs),
                assignments=[],
                unsure_paths=[],
            ),
        )
        return response.tree

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]:
        response = self._request(
            draft_tree=final_tree,
            briefs=briefs,
            prompt=(
                "Assign every file to the final folder tree. Return primary_dir and "
                "also_relevant."
            ),
            fallback=lambda: PlannerResponse(
                tree=final_tree,
                assignments=self._fallback.assign(final_tree, briefs),
                unsure_paths=[],
            ),
        )
        return response.assignments

    def review(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
        assignments: list[PlannerAssignment],
    ) -> PlannerResponse:
        return self._request(
            draft_tree=final_tree,
            briefs=briefs,
            prompt=(
                "Review the full tree and current assignments. Merge or split weak folders "
                "when the "
                "full corpus supports it, and rewrite every summary as concise folder rationale."
            ),
            assignments=assignments,
            fallback=lambda: self._fallback.review(final_tree, briefs, assignments),
        )

    @property
    def usage(self) -> PlannerUsage:
        return self._usage

    def count_tokens(self, briefs: list[FileBrief]) -> int:
        from autoshelf.planner.chunking import count_tokens

        return count_tokens(briefs)

    def _request(
        self,
        *,
        draft_tree: dict[str, Any],
        briefs: list[FileBrief],
        prompt: str,
        fallback,
        assignments: list[PlannerAssignment] | None = None,
    ) -> PlannerResponse:
        if not self._circuit_breaker.allow_request():
            return self._fallback_response(fallback())
        messages = self._messages_payload(prompt, briefs, draft_tree, assignments)
        response_format = {"type": "json_object"}
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "emit_plan",
                    "description": "Emit the current autoshelf plan as structured JSON.",
                    "parameters": self._tool_schema,
                },
            }
        ]
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                started = perf_counter()
                response = self._create_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice={"type": "function", "function": {"name": "emit_plan"}},
                    response_format=response_format,
                )
                elapsed = int((perf_counter() - started) * 1000)
                parsed = self._parse_response(response)
                usage = response.get("usage", {})
                self._usage.add_usage(
                    input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    output_tokens=int(usage.get("completion_tokens", 0) or 0),
                )
                logger.bind(component="planner").info(
                    "llm call provider={} model={} probe_ms={}",
                    type(self).__name__,
                    self._config.llm.model_id,
                    elapsed,
                )
                self._circuit_breaker.record_success()
                return parsed
            except Exception as exc:
                if attempt >= self._retry_policy.max_retries:
                    break
                delay = self._retry_policy.sleep_for_attempt(attempt)
                logger.bind(component="planner").warning(
                    "retryable llm error on attempt {} after {:.2f}s delay: {}",
                    attempt + 1,
                    delay,
                    exc,
                )
        self._circuit_breaker.record_failure()
        return self._fallback_response(fallback())

    def _messages_payload(
        self,
        prompt: str,
        briefs: list[FileBrief],
        tree: dict[str, Any],
        assignments: list[PlannerAssignment] | None = None,
    ) -> list[dict[str, str]]:
        guide_text = self._existing_folder_guide()
        rules_text = render_rules_prompt(self._rules)
        system_blocks = build_system_prompt_blocks(
            guide_text=guide_text,
            rules_text=rules_text,
            prompt_cache_enabled=False,
        )
        brief_payload = [brief.prompt_text for brief in briefs]
        assignment_payload = (
            [assignment.model_dump() for assignment in assignments]
            if assignments is not None
            else None
        )
        request_text = f"{prompt}\n\ntree={tree}\nbriefs={brief_payload}"
        if assignment_payload is not None:
            request_text += f"\ncurrent_assignments={assignment_payload}"
        return [
            {"role": "system", "content": "\n\n".join(block["text"] for block in system_blocks)},
            {"role": "user", "content": request_text},
        ]

    def _parse_response(self, response: dict[str, Any]) -> PlannerResponse:
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("LLM response did not include choices")
        message = choices[0].get("message", {})
        for tool_call in message.get("tool_calls", []):
            function = tool_call.get("function", {})
            if function.get("name") == "emit_plan":
                return PlannerResponse.model_validate_json(function.get("arguments", "{}"))
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return PlannerResponse.model_validate(json.loads(str(content)))

    def _existing_folder_guide(self) -> str:
        guide = Path.cwd() / "FOLDER_GUIDE.md"
        return guide.read_text(encoding="utf-8") if guide.exists() else ""

    def _fallback_response(self, result: PlannerResponse) -> PlannerResponse:
        self._usage.fallback_chunks += 1
        for assignment in result.assignments:
            assignment.fallback = True
        return result

    def _create_completion(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        tool_choice: dict[str, Any] | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class LocalHTTPPlannerLLM(StructuredPlannerLLM):
    def __init__(
        self,
        config: AppConfig,
        base_url: str,
        rules: PlanningRules | None = None,
    ) -> None:
        super().__init__(config, rules)
        self.base_url = base_url

    def _create_completion(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        tool_choice: dict[str, Any] | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return chat_completion(
            base_url=self.base_url,
            model=self._config.llm.model_id,
            messages=messages,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=self._config.llm.max_completion_tokens,
        )


class EmbeddedPlannerLLM(StructuredPlannerLLM):
    def __init__(self, config: AppConfig, rules: PlanningRules | None = None) -> None:
        super().__init__(config, rules)
        self.runtime = EmbeddedLlamaRuntime(config)

    def _create_completion(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        tool_choice: dict[str, Any] | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self.runtime.create_chat_completion(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
        )

    def unload(self) -> None:
        self.runtime.unload()


def select_auto_provider(config: AppConfig) -> tuple[str, str | None]:
    env_url = os.environ.get("AUTOSHELF_LLM_URL", "").strip()
    if env_url:
        probe = probe_openai_compatible(env_url, timeout=2.0)
        if probe.ok:
            return "local_http", probe.base_url
    preferred = probe_openai_compatible("http://127.0.0.1:8081/v1", timeout=0.25)
    if preferred.ok:
        return "local_http", preferred.base_url
    if ollama_is_up("http://127.0.0.1:11434", timeout=0.25):
        return "local_http", "http://127.0.0.1:11434/v1"
    return "embedded", None


def get_planner_llm(
    config: AppConfig | None = None, rules: PlanningRules | None = None
) -> PlannerLLM:
    cfg = config or AppConfig()
    provider = cfg.llm.provider.lower()
    if provider == "fake":
        return FakeLLM()
    if provider == "local_http":
        base_url = cfg.llm.local_http_url or os.environ.get("AUTOSHELF_LLM_URL", "").strip()
        if not base_url:
            return FakeLLM()
        return LocalHTTPPlannerLLM(cfg, base_url, rules)
    if provider == "embedded":
        try:
            return EmbeddedPlannerLLM(cfg, rules)
        except Exception:
            return FakeLLM()
    if provider == "auto":
        selected, base_url = select_auto_provider(cfg)
        if selected == "local_http" and base_url:
            return LocalHTTPPlannerLLM(cfg, base_url, rules)
        try:
            return EmbeddedPlannerLLM(cfg, rules)
        except Exception:
            return FakeLLM()
    return FakeLLM()


def estimate_resident_footprint_mb(config: AppConfig) -> int:
    variant = get_variant(config.llm.model_id)
    return variant.resident_footprint_mb_est


def _deep_copy_tree(tree: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in tree.items():
        copied[key] = _deep_copy_tree(value) if isinstance(value, dict) else {}
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
