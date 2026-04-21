from __future__ import annotations

from pathlib import Path

from loguru import logger

from autoshelf.parsers.base import ParsedContext, ParserSpec


def parse_pdf(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        reader = PdfReader(str(path))
        texts = [(page.extract_text() or "") for page in reader.pages[:3]]
        head = "\n".join(texts).strip()[:max_head_chars]
        if not head:
            head = _pdfminer_fallback(path, max_head_chars)
        if not head:
            logger.bind(component="parser").info("scanned PDF — no OCR: {}", path)
        title = (reader.metadata.title if reader.metadata else None) or path.stem
        return ParsedContext(
            title=title[:120],
            head_text=head,
            extra_meta={"pages": len(reader.pages)},
        )
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})


def _pdfminer_fallback(path: Path, max_head_chars: int) -> str:
    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-not-found]
    except ImportError:
        return ""
    try:
        return extract_text(str(path), maxpages=3)[:max_head_chars].strip()
    except Exception:
        return ""


PARSER_SPEC = ParserSpec(name="pdf", suffixes=(".pdf",), parse=parse_pdf)
