from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext
from autoshelf.parsers.hwp import parse_hwp
from autoshelf.parsers.office import parse_office
from autoshelf.parsers.pdf import parse_pdf
from autoshelf.parsers.text import parse_text


def parse_file(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return parse_text(path, max_head_chars=max_head_chars)
    if suffix == ".pdf":
        return parse_pdf(path, max_head_chars=max_head_chars)
    if suffix in {".pptx", ".xlsx", ".xls", ".docx"}:
        return parse_office(path, max_head_chars=max_head_chars)
    if suffix == ".hwp":
        return parse_hwp(path, max_head_chars=max_head_chars)
    return ParsedContext(title=path.stem, head_text="", extra_meta={})
