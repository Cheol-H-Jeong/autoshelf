from __future__ import annotations

import json
from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec


def parse_text(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    text = _read_text(path)
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            text = json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    head = text[:max_head_chars].strip()
    title = next((line.strip() for line in text.splitlines() if line.strip()), path.stem)
    return ParsedContext(title=title[:120], head_text=head, extra_meta={"encoding": "auto"})


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        from charset_normalizer import from_bytes  # type: ignore[import-not-found]
    except ImportError:
        return raw.decode("utf-8", errors="ignore")
    match = from_bytes(raw).best()
    if match is None:
        return raw.decode("utf-8", errors="ignore")
    return str(match)


PARSER_SPEC = ParserSpec(
    name="text",
    suffixes=(".txt", ".md", ".csv", ".json", ".log", ".rtf", ".epub"),
    parse=parse_text,
)
