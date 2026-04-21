from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedContext:
    """Normalized parser output."""

    title: str
    head_text: str
    extra_meta: dict[str, object]
