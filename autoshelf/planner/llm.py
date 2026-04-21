from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from autoshelf.config import AppConfig
from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.models import PlannerAssignment, PlannerResponse, PlannerUsage
from autoshelf.planner.naming import normalize_folder_name
from autoshelf.planner.prompts import FEW_SHOT_PROMPT, SYSTEM_PROMPT
from autoshelf.planner.rate_limit import RateLimiter
from autoshelf.planner.reliability import CircuitBreaker, RetryPolicy
from autoshelf.rules import PlanningRules, render_rules_prompt


class PlannerLLM(Protocol):
    """Planner LLM interface."""

    def propose(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> PlannerResponse: ...

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]: ...

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]: ...

    @property
    def usage(self) -> PlannerUsage: ...

    def count_tokens(self, briefs: list[FileBrief]) -> int: ...


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
                    confidence=0.92,
                )
            )
        return assignments

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


class AnthropicPlannerLLM:
    """Anthropic-backed planner with offline fallback expectations handled by the caller."""

    def __init__(self, config: AppConfig, rules: PlanningRules | None = None) -> None:
        self._config = config
        from anthropic import Anthropic  # type: ignore[import-not-found]

        self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._rate_limiter = RateLimiter(
            requests_per_second=config.llm.requests_per_second,
            concurrency=config.llm.concurrency,
        )
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
        self._fallback = FakeLLM()
        self._usage = PlannerUsage()
        self._rules = rules or PlanningRules()
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
        prompt = "Propose or refine the folder tree and tentative assignments for this chunk."

        def fallback() -> PlannerResponse:
            return self._fallback.propose(draft_tree, briefs)

        return self._request(
            model=self._config.llm.planning_model,
            draft_tree=draft_tree,
            briefs=briefs,
            prompt=prompt,
            fallback=fallback,
        )

    def finalize(self, draft_tree: dict[str, Any], briefs: list[FileBrief]) -> dict[str, Any]:
        prompt = "Finalize the folder tree. Improve naming, merge duplicates, and keep depth <= 3."

        def fallback() -> PlannerResponse:
            return PlannerResponse(
                tree=self._fallback.finalize(draft_tree, briefs),
                assignments=[],
                unsure_paths=[],
            )

        response = self._request(
            model=self._config.llm.review_model,
            draft_tree=draft_tree,
            briefs=briefs,
            prompt=prompt,
            fallback=fallback,
        )
        return response.tree

    def assign(
        self,
        final_tree: dict[str, Any],
        briefs: list[FileBrief],
    ) -> list[PlannerAssignment]:
        prompt = "Assign every file to the final folder tree. Return primary_dir and also_relevant."

        def fallback() -> PlannerResponse:
            return PlannerResponse(
                tree=final_tree,
                assignments=self._fallback.assign(final_tree, briefs),
                unsure_paths=[],
            )

        response = self._request(
            model=self._config.llm.classification_model,
            draft_tree=final_tree,
            briefs=briefs,
            prompt=prompt,
            fallback=fallback,
        )
        return response.assignments

    @property
    def usage(self) -> PlannerUsage:
        return self._usage

    def count_tokens(self, briefs: list[FileBrief]) -> int:
        from autoshelf.planner.chunking import count_tokens

        return count_tokens(briefs, counter=self._client)

    def _messages_payload(
        self, briefs: list[FileBrief], tree: dict[str, Any], model: str
    ) -> dict[str, Any]:
        guide_text = self._existing_folder_guide()
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": SYSTEM_PROMPT}]
        if self._config.llm.prompt_cache_enabled:
            system_blocks.append(
                {
                    "type": "text",
                    "text": FEW_SHOT_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        else:
            system_blocks.append({"type": "text", "text": FEW_SHOT_PROMPT})
        if guide_text:
            system_blocks.append({"type": "text", "text": f"Existing guide:\n{guide_text}"})
        rules_text = render_rules_prompt(self._rules)
        if rules_text:
            system_blocks.append({"type": "text", "text": rules_text})
        brief_payload = [brief.model_dump() for brief in briefs]
        return {
            "model": model,
            "max_tokens": 4096,
            "system": system_blocks,
            "tools": [
                {
                    "name": "emit_plan",
                    "description": "Emit the current autoshelf plan as structured JSON.",
                    "input_schema": self._tool_schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": "emit_plan"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"tree={tree}\nbriefs={brief_payload}",
                        }
                    ],
                }
            ],
        }

    def _request(
        self,
        model: str,
        draft_tree: dict[str, Any],
        briefs: list[FileBrief],
        prompt: str,
        fallback,
    ) -> PlannerResponse:
        payload = self._messages_payload(briefs, draft_tree, model)
        payload["messages"][0]["content"][0]["text"] = (
            f"{prompt}\n\n{payload['messages'][0]['content'][0]['text']}"
        )
        if not self._circuit_breaker.allow_request():
            logger.bind(component="planner").warning(
                "anthropic circuit breaker open; using fallback for model={}",
                model,
            )
            return self._fallback_response(fallback())
        errors = self._retryable_errors()
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                with self._rate_limiter:
                    response = self._client.messages.create(**payload)
                parsed = self._parse_response(response)
                self._circuit_breaker.record_success()
                usage = getattr(response, "usage", None)
                self._usage.add_usage(
                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                    cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0)
                    or 0,
                    cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                )
                logger.bind(component="planner").info(
                    "anthropic call model={} in={} out={} cache_create={} cache_read={}",
                    model,
                    getattr(usage, "input_tokens", 0) or 0,
                    getattr(usage, "output_tokens", 0) or 0,
                    getattr(usage, "cache_creation_input_tokens", 0) or 0,
                    getattr(usage, "cache_read_input_tokens", 0) or 0,
                )
                return parsed
            except errors as exc:
                if attempt >= self._retry_policy.max_retries:
                    break
                delay = self._retry_policy.sleep_for_attempt(attempt)
                logger.bind(component="planner").warning(
                    "retryable anthropic error on attempt {} after {:.2f}s delay: {}",
                    attempt + 1,
                    delay,
                    exc,
                )
            except Exception:
                break
        self._circuit_breaker.record_failure()
        return self._fallback_response(fallback())

    def _parse_response(self, response: Any) -> PlannerResponse:
        for block in getattr(response, "content", []):
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "emit_plan"
            ):
                return PlannerResponse.model_validate(block.input)
        raise ValueError("Anthropic response did not include emit_plan tool_use output")

    def _existing_folder_guide(self) -> str:
        candidates = [Path.cwd() / "FOLDER_GUIDE.md"]
        for candidate in candidates:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        return ""

    def _retryable_errors(self) -> tuple[type[BaseException], ...]:
        import anthropic  # type: ignore[import-not-found]

        return (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        )

    def _fallback_response(self, result: PlannerResponse) -> PlannerResponse:
        self._usage.fallback_chunks += 1
        for assignment in result.assignments:
            assignment.fallback = True
        return result


def get_planner_llm(
    config: AppConfig | None = None, rules: PlanningRules | None = None
) -> PlannerLLM:
    from autoshelf.planner.providers import load_llm_provider

    cfg = config or AppConfig()
    if cfg.llm.provider.lower() == "fake" or not os.environ.get("ANTHROPIC_API_KEY"):
        return FakeLLM()
    return load_llm_provider(cfg, rules)


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
