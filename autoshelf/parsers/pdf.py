from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext


def parse_pdf(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        reader = PdfReader(str(path))
        texts = [(page.extract_text() or "") for page in reader.pages[:3]]
        head = "\n".join(texts).strip()[:max_head_chars]
        title = (reader.metadata.title if reader.metadata else None) or path.stem
        return ParsedContext(
            title=title[:120],
            head_text=head,
            extra_meta={"pages": len(reader.pages)},
        )
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
