from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec


def parse_archive(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    suffix = path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()[:20]
        elif suffix in {".tar", ".gz", ".tgz"}:
            with tarfile.open(path) as archive:
                names = archive.getnames()[:20]
        else:
            return ParsedContext(
                title=path.stem, head_text="", extra_meta={"parser": "unsupported"}
            )
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
    top_entries = "\n".join(names)[:max_head_chars]
    return ParsedContext(title=path.stem, head_text=top_entries, extra_meta={"entries": len(names)})


PARSER_SPEC = ParserSpec(
    name="archive", suffixes=(".zip", ".tar", ".gz", ".tgz", ".7z"), parse=parse_archive
)
