from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec
from autoshelf.parsers.registry import load_parser_specs, parse_with_registry


def parse_file(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    return parse_with_registry(path, max_head_chars=max_head_chars)


__all__ = ["ParsedContext", "ParserSpec", "load_parser_specs", "parse_file"]
