from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext


def parse_hwp(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    try:
        import olefile  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        is_ole = olefile.isOleFile(str(path))
        return ParsedContext(
            title=path.stem,
            head_text="",
            extra_meta={"ole_container": bool(is_ole), "max_head_chars": max_head_chars},
        )
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
