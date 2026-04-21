from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ParsedContext:
    """Normalized parser output."""

    title: str
    head_text: str
    extra_meta: dict[str, object]


@dataclass(frozen=True, slots=True)
class ParserSpec:
    name: str
    suffixes: tuple[str, ...]
    parse: Callable[[Path, int], ParsedContext]
