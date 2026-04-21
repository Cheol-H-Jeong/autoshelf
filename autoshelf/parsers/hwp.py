from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec


def parse_hwp(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    try:
        import pyhwp  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        pyhwp = None
    try:
        import olefile  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        is_ole = olefile.isOleFile(str(path))
        if pyhwp is not None:
            return ParsedContext(
                title=path.stem,
                head_text="HWP document",
                extra_meta={"ole_container": bool(is_ole), "parser": "pyhwp"},
            )
        if shutil.which("hwp5txt"):
            completed = subprocess.run(
                ["hwp5txt", str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
            text = completed.stdout[:max_head_chars].strip()
            return ParsedContext(
                title=path.stem,
                head_text=text,
                extra_meta={"ole_container": bool(is_ole), "parser": "hwp5txt"},
            )
        return ParsedContext(
            title=path.stem,
            head_text="",
            extra_meta={"ole_container": bool(is_ole), "max_head_chars": max_head_chars},
        )
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})


PARSER_SPEC = ParserSpec(name="hwp", suffixes=(".hwp",), parse=parse_hwp)
