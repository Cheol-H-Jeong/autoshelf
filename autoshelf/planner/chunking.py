from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from autoshelf.planner.models import FileBriefModel

FileBrief = FileBriefModel


def chunk_briefs(briefs: Iterable[FileBrief], max_tokens: int) -> list[list[FileBrief]]:
    chunks: list[list[FileBrief]] = []
    current: list[FileBrief] = []
    current_tokens = 0
    for brief in briefs:
        estimate = max(1, len(brief.summary) // 4)
        if current and current_tokens + estimate > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(brief)
        current_tokens += estimate
    if current:
        chunks.append(current)
    return chunks


def count_tokens(briefs: Iterable[FileBrief], counter: object | None = None) -> int:
    text = "\n".join(brief.summary for brief in briefs)
    if not text:
        return 0
    if counter is not None:
        count_tokens_fn = getattr(counter, "count_tokens", None)
        if callable(count_tokens_fn):
            try:
                result = count_tokens_fn(text)
                if isinstance(result, int):
                    return result
                output_tokens = getattr(result, "input_tokens", None)
                if isinstance(output_tokens, int):
                    return output_tokens
            except Exception:
                pass
        messages = getattr(counter, "messages", None)
        nested_count = getattr(messages, "count_tokens", None)
        if callable(nested_count):
            try:
                result = nested_count(model="unused", messages=[{"role": "user", "content": text}])
                input_tokens = getattr(result, "input_tokens", None)
                if isinstance(input_tokens, int):
                    return input_tokens
            except Exception:
                pass
    return max(1, int(len(text) / 3.5))


def brief_path_name(path: str) -> str:
    return Path(path).name
